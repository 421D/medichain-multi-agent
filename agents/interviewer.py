import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command, interrupt

from agents.base import get_llm
from prompts.interviewer_prompt import INTERVIEWER_SYSTEM_PROMPT
from models.schemas import InterviewerOutput

logger = logging.getLogger(__name__)

# Use DC's SOCRATES-based prompt (more detailed than Winston's embedded one)
INTERVIEWER_SYSTEM = INTERVIEWER_SYSTEM_PROMPT


def interviewer_node(state: dict) -> Command | dict:
    """Interviewer: SOCRATES-driven multi-turn history; uses LangGraph interrupt() to pause."""
    messages = state.get("messages", [])
    agent_logs = []

    # Low temperature: history-taking should be deterministic — the same
    # symptoms must produce the same follow-up questions across runs, otherwise
    # the SOCRATES protocol becomes inconsistent and the eval harness can't
    # measure regression.
    llm = get_llm(
        temperature=0.3,
        model_override=state.get("llm_model"),
        node="interviewer",
        session_id=state.get("session_id"),
    )
    # Structured output forces the LLM into a typed InterviewerOutput
    # (status enum + question + summary). Without this, the LLM occasionally
    # answers in prose and the downstream graph router can't decide whether
    # to interrupt-and-wait or proceed to the diagnostician.
    structured_llm = llm.with_structured_output(InterviewerOutput)

    # Build the LLM context. `messages` may contain raw dicts coming from the
    # WebSocket payload (`{role, content}`) AND already-typed LangChain Message
    # objects accumulated during the same session — handle both shapes so a
    # mid-session resume doesn't lose the conversation prefix.
    llm_messages = [SystemMessage(content=INTERVIEWER_SYSTEM)]
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "human")
            content = msg.get("content", "")
            if role == "human":
                llm_messages.append(HumanMessage(content=content))
            elif role == "ai":
                llm_messages.append(AIMessage(content=content))
        elif isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
            llm_messages.append(msg)

    result: InterviewerOutput = structured_llm.invoke(llm_messages)
    agent_logs.append(
        {
            "agent": "interviewer",
            "action": "llm_call",
            "status": result.status.value,
            "reasoning": result.reasoning,
        }
    )

    if result.status.value == "need_more_info":
        # Fallback question prevents an infinite-loop interrupt if the LLM
        # returned status=need_more_info but null question (rare but seen on
        # truncated outputs from rate-limited providers).
        question = result.question or "Could you tell me more about your symptoms?"

        # Add the AI question to messages
        new_messages = list(messages) + [
            {"role": "ai", "content": question}
        ]

        agent_logs.append(
            {"agent": "interviewer", "action": "asking_question", "question": question}
        )

        # Interrupt to wait for user response
        user_response = interrupt({"question": question})

        # After resume, add the user response and loop back
        new_messages = new_messages + [
            {"role": "human", "content": str(user_response)}
        ]

        return Command(
            goto="interviewer",
            update={
                "messages": new_messages,
                "current_agent": "interviewer",
                "agent_logs": agent_logs,
            },
        )

    # Status is "complete" - patient history collected
    summary_dict = result.summary.model_dump() if result.summary else {}
    agent_logs.append(
        {
            "agent": "interviewer",
            "action": "history_complete",
            "summary_keys": list(summary_dict.keys()),
        }
    )

    return {
        "patient_history": summary_dict,
        "current_agent": "diagnostician",
        "agent_logs": agent_logs,
    }
