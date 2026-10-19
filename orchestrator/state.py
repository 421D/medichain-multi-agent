from typing import Annotated, TypedDict
from operator import add


class GraphState(TypedDict, total=False):
    messages: list                     # Conversation history
    patient_history: dict | None       # Structured patient history from interviewer
    diagnosis: dict | None             # Diagnosis result from diagnostician
    critic_review: dict | None         # Review from critic (kept for backward compat)
    rag_context: list | None           # RAG retrieval results
    iteration_count: int               # Current iteration cycle count
    current_agent: str                 # Name of current/next agent
    coordinator_response: str | None   # Final patient-facing response
    agent_logs: Annotated[list, add]   # Accumulates across nodes
    # v2 additions
    debate_rounds: list | None         # DebateRound history
    debate_outcome: dict | None        # Final debate outcome
    cdss_scores: dict | None           # CDSS scoring results
    drug_interactions: dict | None     # Drug interaction check results
    # Per-session LLM provider override (resolved from session.llm_model).
    # When None/missing, get_llm() falls back to MEDICHAIN_LLM_MODEL env var.
    llm_model: str | None
    # Session id propagated into LLM tracer records so we can join a trace
    # back to the session it served (no PII; the session_id is already a UUID
    # or case_id, never the raw user message).
    session_id: str | None
