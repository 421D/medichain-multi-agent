import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import get_llm
from prompts.coordinator_prompt import COORDINATOR_SYSTEM

logger = logging.getLogger(__name__)


def coordinator_node(state: dict) -> dict:
    """Coordinator: synthesise upstream agent state into the patient-facing reply."""
    patient_history = state.get("patient_history", {})
    diagnosis = state.get("diagnosis", {})
    critic_review = state.get("critic_review", {})
    debate_outcome = state.get("debate_outcome", {})
    cdss_scores = state.get("cdss_scores", {})
    agent_logs = []

    # Use indented JSON rather than `repr()` so the LLM sees field names and
    # nesting clearly; otherwise it confuses sub-fields and writes hallucinated
    # totals into the response.
    history_str = json.dumps(patient_history, ensure_ascii=False, indent=2)
    diagnosis_str = json.dumps(diagnosis, ensure_ascii=False, indent=2)
    critic_str = json.dumps(critic_review, ensure_ascii=False, indent=2)

    # Debate + CDSS get their own headed sections rather than being nested
    # inside `diagnosis_str`. Headers anchor the LLM's attention so it doesn't
    # silently drop "we ran a Wells score of 6" from the patient-facing reply.
    debate_section = ""
    if debate_outcome:
        debate_section = (
            f"\n## Debate Summary\n"
            f"Verdict: {debate_outcome.get('final_verdict', 'N/A')}\n"
            f"Total challenges: {debate_outcome.get('total_challenges', 0)}\n"
            f"Accepted: {debate_outcome.get('accepted', 0)}, Refuted: {debate_outcome.get('refuted', 0)}\n"
        )

    cdss_section = ""
    if cdss_scores:
        cdss_section = f"\n## CDSS Risk Scores\n{json.dumps(cdss_scores, ensure_ascii=False, indent=2)}\n"

    user_message = (
        f"## Patient History Summary\n{history_str}\n\n"
        f"## Differential Diagnosis Result\n{diagnosis_str}\n\n"
        f"## Critic Review\n{critic_str}\n"
        f"{debate_section}"
        f"{cdss_section}\n"
        f"Please synthesise the above into a final patient-facing response."
    )

    # temperature=0.5 is intentionally higher than the diagnostic agents
    # (0.0–0.3): the Coordinator is paraphrasing settled facts into natural
    # language, so a touch of variation reads less robotic — but still anchored
    # to the structured input so safety claims don't drift.
    llm = get_llm(
        temperature=0.5,
        model_override=state.get("llm_model"),
        node="coordinator",
        session_id=state.get("session_id"),
    )
    result = llm.invoke(
        [
            SystemMessage(content=COORDINATOR_SYSTEM),
            HumanMessage(content=user_message),
        ]
    )

    response_text = result.content if hasattr(result, "content") else str(result)

    # Keep the agent log row small — full response is already persisted as a
    # Message; storing it again here would double DB write volume for no gain.
    agent_logs.append({
        "agent": "coordinator",
        "action": "response_generated",
        "preview": response_text[:200],
        "debate_verdict": debate_outcome.get("final_verdict", "N/A") if debate_outcome else "no_debate",
    })

    return {
        "coordinator_response": response_text,
        # Terminal marker: the graph router uses this to short-circuit out of
        # any pending debate/diagnostician loop.
        "current_agent": "complete",
        "agent_logs": agent_logs,
    }
