import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import get_structured_llm
from prompts.diagnostician_prompt import DIAGNOSTICIAN_SYSTEM_PROMPT
from models.schemas import DiagnosticianOutput
from rag.knowledge_base import KnowledgeBase
from rag.retriever import Retriever

logger = logging.getLogger(__name__)

# Use DC's prompt (more detailed than Winston's embedded one)
DIAGNOSTICIAN_SYSTEM = DIAGNOSTICIAN_SYSTEM_PROMPT

# Module-level retriever, initialized lazily
_retriever: Retriever | None = None


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        kb = KnowledgeBase()
        kb.load()
        _retriever = Retriever(kb)
    return _retriever


def set_retriever(retriever: Retriever) -> None:
    """Allow external injection of a retriever (e.g. from main.py startup)."""
    global _retriever
    _retriever = retriever


def diagnostician_node(state: dict) -> dict:
    """Diagnostician agent node: generates differential diagnosis using RAG."""
    patient_history = state.get("patient_history", {})
    agent_logs = []

    if not patient_history:
        # Error path: produce a minimal terminal state so the graph still
        # routes safely to the coordinator instead of running debate on
        # an empty diagnosis (which would crash downstream formatters).
        agent_logs.append(
            {
                "agent": "diagnostician",
                "action": "error",
                "detail": "No patient history available",
            }
        )
        return {
            "agent_logs": agent_logs,
            "current_agent": "complete",
            "diagnosis": {
                "differential_diagnosis": [],
                "recommended_tests": [],
                "reasoning_chain": "Cannot diagnose without patient history.",
            },
            "critic_review": {
                "approval": False,
                "safety_flag": "yellow",
                "issues": [],
                "final_assessment": "Insufficient history; please complete the interview.",
            },
        }

    # Build query from patient history for RAG retrieval
    chief_complaint = patient_history.get("chief_complaint", "")
    hpi = patient_history.get("history_of_present_illness", "")
    ros = patient_history.get("review_of_systems", "")
    query = f"{chief_complaint} {hpi} {ros}"

    # Retrieve relevant medical knowledge.
    # S5 fix: dropped top_k 5→3 and chunk limit 1500→1000 char. The prompt
    # prefill cost dominates Diagnostician latency; halving RAG context
    # saves ~1-2s per call and harness shows no accuracy drop because the
    # top 3 chunks carry the vast majority of relevance signal.
    retriever = _get_retriever()
    rag_results = retriever.retrieve(query, top_k=3)

    # ChromaDB returns each entry as {title, source, text, distance}. Earlier
    # versions of this loop tried to read 6 structured fields (diagnosis,
    # category, key_features, ...) that are NOT in the metadata, so the LLM
    # received empty placeholders and the actual document text was silently
    # dropped. Read `text` directly instead.
    rag_context_str = ""
    for i, entry in enumerate(rag_results, 1):
        doc_id = entry.get("id", f"source_{i}")
        title = entry.get("title", "") or "(untitled)"
        source = entry.get("source", "MedRAG")
        text = (entry.get("text") or "")[:1000]
        rag_context_str += (
            f"\n[Source {doc_id}] {title} — {source}\n"
            f"{text}\n"
        )

    agent_logs.append(
        {
            "agent": "diagnostician",
            "action": "rag_retrieval",
            "query": query[:100],
            "results_count": len(rag_results),
        }
    )

    # Build the prompt for the LLM
    history_str = json.dumps(patient_history, ensure_ascii=False, indent=2)
    user_message = (
        f"## Patient History\n{history_str}\n\n"
        f"## Medical Knowledge Base References\n{rag_context_str}\n\n"
        f"Please perform differential diagnosis analysis based on the above information."
    )

    structured_llm = get_structured_llm(
        DiagnosticianOutput,
        model_override=state.get("llm_model"),
        node="diagnostician",
        session_id=state.get("session_id"),
    )
    result: DiagnosticianOutput = structured_llm.invoke(
        [
            SystemMessage(content=DIAGNOSTICIAN_SYSTEM),
            HumanMessage(content=user_message),
        ]
    )

    diagnosis_dict = result.model_dump()
    agent_logs.append(
        {
            "agent": "diagnostician",
            "action": "diagnosis_complete",
            "diagnoses_count": len(result.differential_diagnosis),
            "reasoning_preview": result.reasoning_chain[:200],
        }
    )

    return {
        "diagnosis": diagnosis_dict,
        "rag_context": rag_results,
        "current_agent": "debate_round",
        "agent_logs": agent_logs,
    }
