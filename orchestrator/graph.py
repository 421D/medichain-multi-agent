import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.cdss_node import cdss_node
from agents.coordinator import coordinator_node
from agents.debate import MAX_DEBATE_ROUNDS, debate_round_node
from agents.diagnostician import diagnostician_node
from agents.interviewer import interviewer_node
from orchestrator.state import GraphState

logger = logging.getLogger(__name__)

DEBATE_CONFIDENCE_THRESHOLD = int(os.getenv("DEBATE_CONFIDENCE_THRESHOLD", "85"))


# --- Routing logic ---


def _route_after_interviewer(state: GraphState) -> str:
    """Route based on interviewer output."""
    if state.get("patient_history"):
        return "diagnostician"
    messages = state.get("messages", [])
    if len(messages) > 10:
        return "diagnostician"
    return "interviewer"


def _route_after_diagnostician(state: GraphState) -> str:
    """Route diagnostician output:
      - error fallback (current_agent=='complete') → coordinator
      - empty DDx → coordinator (CDSS / debate would have nothing to work with)
      - otherwise → cdss (which then routes to debate_round)
    """
    if state.get("current_agent") == "complete":
        return "coordinator"
    diagnosis = state.get("diagnosis") or {}
    ddx = diagnosis.get("differential_diagnosis") or []
    if not ddx:
        return "coordinator"
    return "cdss"


def _route_after_debate(state: GraphState) -> str:
    """Route based on debate outcome."""
    current = state.get("current_agent", "complete")
    debate_rounds = state.get("debate_rounds") or []

    if current == "complete" or len(debate_rounds) >= MAX_DEBATE_ROUNDS:
        return "coordinator"
    elif current == "debate":
        return "debate_round"
    elif current == "diagnostician":
        return "diagnostician"
    else:
        return "coordinator"


# --- Graph construction ---


def create_graph():
    """Build the multi-agent diagnostic graph with debate protocol.

    Flow: Interviewer -> Diagnostician -> Debate Round -> Coordinator -> END
    Debate can loop up to MAX_DEBATE_ROUNDS rounds (default 2; env override).
    """
    builder = StateGraph(GraphState)

    builder.add_node("interviewer", interviewer_node)
    builder.add_node("diagnostician", diagnostician_node)
    builder.add_node("cdss", cdss_node)
    builder.add_node("debate_round", debate_round_node)
    builder.add_node("coordinator", coordinator_node)

    builder.add_edge(START, "interviewer")
    builder.add_conditional_edges("interviewer", _route_after_interviewer)
    builder.add_conditional_edges("diagnostician", _route_after_diagnostician)
    builder.add_edge("cdss", "debate_round")
    builder.add_conditional_edges("debate_round", _route_after_debate)
    builder.add_edge("coordinator", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
