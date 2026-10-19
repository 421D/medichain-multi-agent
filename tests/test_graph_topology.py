"""Test that the new graph has correct node and edge structure."""
from orchestrator.graph import create_graph


def test_graph_has_debate_node():
    graph = create_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert "debate_round" in node_names
    assert "interviewer" in node_names
    assert "diagnostician" in node_names
    assert "coordinator" in node_names


def test_graph_compiles():
    graph = create_graph()
    assert graph is not None
