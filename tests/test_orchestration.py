"""
Unit tests for MediChain Agent Orchestration (v2 — debate-based)
Tests cover: GraphState structure, routing logic, graph compilation, node completeness.
"""

from orchestrator.state import GraphState
from orchestrator.graph import create_graph, _route_after_debate, _route_after_interviewer


# --- 1. GraphState structure tests ---

def test_graph_state_has_required_fields():
    """GraphState contains all required fields including v2 additions."""
    state: GraphState = {
        "messages": [],
        "patient_history": None,
        "diagnosis": None,
        "critic_review": None,
        "rag_context": None,
        "iteration_count": 0,
        "current_agent": "interviewer",
        "coordinator_response": None,
        "agent_logs": [],
        "debate_rounds": None,
        "debate_outcome": None,
        "cdss_scores": None,
        "drug_interactions": None,
    }
    required = [
        "messages", "patient_history", "diagnosis", "critic_review",
        "rag_context", "iteration_count", "current_agent",
        "coordinator_response", "agent_logs",
        "debate_rounds", "debate_outcome", "cdss_scores", "drug_interactions",
    ]
    for field in required:
        assert field in state, f"Missing field: {field}"


# --- 2. Routing logic tests (v2: debate-based) ---

def test_route_after_debate_complete():
    """Debate resolved -> coordinator"""
    state = {"current_agent": "complete", "debate_rounds": [{"round_number": 1}]}
    assert _route_after_debate(state) == "coordinator"


def test_route_after_debate_continue():
    """Debate unresolved -> another round"""
    state = {"current_agent": "debate", "debate_rounds": [{"round_number": 1}]}
    assert _route_after_debate(state) == "debate_round"


def test_route_after_debate_back_to_diagnostician():
    """Debate requests more info -> diagnostician"""
    state = {"current_agent": "diagnostician", "debate_rounds": [{"round_number": 1}]}
    assert _route_after_debate(state) == "diagnostician"


def test_route_after_debate_max_rounds():
    """Max debate rounds -> force coordinator"""
    state = {"current_agent": "debate", "debate_rounds": [
        {"round_number": 1}, {"round_number": 2}, {"round_number": 3}]}
    assert _route_after_debate(state) == "coordinator"


def test_route_after_interviewer_to_diagnostician():
    """Interviewer complete -> diagnostician"""
    state = {"patient_history": {"chief_complaint": "headache"}, "messages": []}
    assert _route_after_interviewer(state) == "diagnostician"


def test_route_after_interviewer_continue():
    """Interviewer needs more info -> stay on interviewer"""
    state = {"patient_history": None, "messages": []}
    assert _route_after_interviewer(state) == "interviewer"


# --- 3. Graph compilation tests ---

def test_graph_compiles():
    """Graph compiles without errors."""
    graph = create_graph()
    assert graph is not None


def test_graph_has_v2_nodes():
    """Graph contains debate_round node instead of critic."""
    graph = create_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert "interviewer" in node_names
    assert "diagnostician" in node_names
    assert "debate_round" in node_names
    assert "coordinator" in node_names


def test_route_after_debate_unknown_defaults_coordinator():
    """Unknown current_agent defaults to coordinator"""
    state = {"current_agent": "something_unexpected", "debate_rounds": []}
    assert _route_after_debate(state) == "coordinator"
