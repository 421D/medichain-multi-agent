"""Test debate_round_node with mocked LLM responses."""
import pytest
from unittest.mock import patch, MagicMock
from agents.debate import debate_round_node
from models.schemas import (
    CriticDebateOutput, DebateChallenge,
    DiagnosticianDebateOutput, DebateResponse,
)


def _make_state(diagnosis=None, debate_rounds=None):
    return {
        "patient_history": {"chief_complaint": "headache"},
        "diagnosis": diagnosis or {
            "differential_diagnosis": [
                {"diagnosis": "Migraine", "confidence": 80, "supporting_evidence": ["throbbing"]},
            ],
            "recommended_tests": ["CT head"],
            "reasoning_chain": "Throbbing headache suggests migraine",
        },
        "debate_rounds": debate_rounds or [],
        "cdss_scores": {},
        "rag_context": [],
        "agent_logs": [],
    }


def _mock_critic_no_challenges():
    return CriticDebateOutput(
        challenges=[], safety_flag="green",
        overall_assessment="Diagnosis is adequate",
    )


def _mock_critic_with_challenge():
    return CriticDebateOutput(
        challenges=[DebateChallenge(
            challenge_id="c1", type="missed_diagnosis",
            claim="Tension headache not considered",
            evidence=["Patient has stress history"],
            suggested_action="Add tension headache to DDx",
        )],
        safety_flag="green",
        overall_assessment="Missing alternative diagnosis",
    )


def _mock_diagnostician_accept():
    return DiagnosticianDebateOutput(
        responses=[DebateResponse(
            challenge_id="c1", action="accept",
            reasoning="Agreed, adding tension headache",
            evidence=["Stress is a known trigger"],
            updated_diagnosis={"diagnosis": "Tension headache", "confidence": 40},
        )],
        updated_reasoning="Added tension headache as secondary candidate",
    )


@patch("agents.debate.get_structured_llm")
def test_no_challenges_goes_to_coordinator(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _mock_critic_no_challenges()
    mock_get_llm.return_value = mock_llm

    state = _make_state()
    result = debate_round_node(state)
    assert result["current_agent"] == "complete"
    assert len(result["debate_rounds"]) == 1
    assert result["debate_rounds"][0]["resolution"] == "resolved"


@patch("agents.debate.get_structured_llm")
def test_challenge_accepted_updates_diagnosis(mock_get_llm):
    critic_llm = MagicMock()
    critic_llm.invoke.return_value = _mock_critic_with_challenge()

    diag_llm = MagicMock()
    diag_llm.invoke.return_value = _mock_diagnostician_accept()

    mock_get_llm.side_effect = [critic_llm, diag_llm]

    state = _make_state()
    result = debate_round_node(state)
    assert result["current_agent"] == "complete"
    debate = result["debate_rounds"][0]
    assert len(debate["challenges"]) == 1
    assert len(debate["responses"]) == 1
    assert debate["responses"][0]["action"] == "accept"


@patch("agents.debate.get_structured_llm")
def test_max_rounds_forces_completion(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _mock_critic_with_challenge()

    diag_llm = MagicMock()
    diag_llm.invoke.return_value = DiagnosticianDebateOutput(
        responses=[DebateResponse(
            challenge_id="c1", action="refute",
            reasoning="Disagree", evidence=["No evidence"],
        )],
    )
    mock_get_llm.side_effect = [mock_llm, diag_llm]

    # Simulate already having 2 rounds
    existing = [{"round_number": i, "challenges": [], "responses": [], "resolution": "escalated"}
                for i in range(1, 3)]
    state = _make_state(debate_rounds=existing)
    result = debate_round_node(state)
    # Round 3 = max, should go to coordinator
    assert result["current_agent"] == "complete"
