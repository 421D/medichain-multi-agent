from models.schemas import (
    DebateChallenge, DebateResponse, DebateRound, DebateOutcome,
    CriticDebateOutput, DiagnosticianDebateOutput,
)


def test_debate_challenge_creation():
    c = DebateChallenge(
        challenge_id="c1", type="missed_diagnosis",
        claim="PE not in DDx despite Wells 6",
        evidence=["Wells Score = 6 (high risk)"],
        suggested_action="Add PE to differential",
    )
    assert c.challenge_id == "c1"
    assert c.tool_evidence is None


def test_debate_response_accept():
    r = DebateResponse(
        challenge_id="c1", action="accept",
        reasoning="Agreed — Wells 6 warrants PE in DDx",
        evidence=["Updated DDx to include PE"],
    )
    assert r.action == "accept"


def test_debate_round_serialization():
    dr = DebateRound(
        round_number=1,
        challenges=[DebateChallenge(
            challenge_id="c1", type="safety_concern",
            claim="test", evidence=[], suggested_action="test",
        )],
        responses=[DebateResponse(
            challenge_id="c1", action="refute",
            reasoning="test", evidence=[],
        )],
        resolution="resolved",
    )
    data = dr.model_dump()
    assert data["round_number"] == 1
    assert len(data["challenges"]) == 1


def test_debate_outcome():
    outcome = DebateOutcome(
        rounds=[], total_challenges=2, accepted=1, refuted=1,
        final_verdict="revised_and_approved",
    )
    assert outcome.final_verdict == "revised_and_approved"


def test_critic_debate_output():
    out = CriticDebateOutput(
        challenges=[],
        safety_flag="green",
        overall_assessment="Diagnosis is adequate",
    )
    assert out.safety_flag == "green"
