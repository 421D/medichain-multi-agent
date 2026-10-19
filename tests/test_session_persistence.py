"""Tests for session state persistence — diagnosis, debate, and session metadata.

Covers the fix for: page reload losing DiagnosisPanel, DebateView, and
Consultations page metadata (preliminary_diagnosis, safety_flags, agent_participation).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.db.models import AgentLog, Session
from tests.conftest import TestSessionLocal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FULL_DIAGNOSIS_DATA = {
    "differential_diagnosis": [
        {
            "diagnosis": "Pulmonary Embolism",
            "confidence": 85,
            "supporting_evidence": ["chest pain", "dyspnea"],
            "against_evidence": [],
            "source": "RAG",
        },
        {
            "diagnosis": "Pneumonia",
            "confidence": 60,
            "supporting_evidence": ["cough"],
            "against_evidence": ["no fever"],
            "source": "RAG",
        },
    ],
    "recommended_tests": ["CT-PA", "D-dimer"],
    "reasoning_chain": "Step 1 → Step 2",
    "critic_review": {
        "approval": True,
        "safety_flag": "urgent",
        "issues": [],
        "final_assessment": "Approved with urgent flag",
    },
    "debate_outcome": {
        "rounds": [
            {
                "round_number": 1,
                "challenges": [
                    {
                        "challenge_id": "c1",
                        "type": "evidence_gap",
                        "claim": "Missing D-dimer result",
                        "evidence": ["No lab data"],
                        "suggested_action": "Order D-dimer",
                    }
                ],
                "responses": [
                    {
                        "challenge_id": "c1",
                        "action": "accept",
                        "reasoning": "Will add D-dimer to recommended tests",
                        "evidence": ["Guidelines recommend D-dimer"],
                    }
                ],
                "resolution": "resolved",
            }
        ],
        "final_verdict": "resolved",
        "total_challenges": 1,
        "accepted": 1,
        "refuted": 0,
        "summary": "One challenge accepted, diagnosis refined.",
    },
    "cdss_scores": {
        "wells": {"score": 5, "risk_level": "high"},
    },
    "coordinator_response": "Based on our analysis...",
}


async def _create_session(title: str = "Test Session") -> str:
    """Insert a session directly into the test DB, return its ID."""
    async with TestSessionLocal() as db:
        s = Session(title=title)
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return s.id


async def _add_agent_log(
    session_id: str,
    agent_name: str,
    action: str,
    output_data: dict | None = None,
):
    """Insert an agent log directly into the test DB."""
    async with TestSessionLocal() as db:
        log = AgentLog(
            session_id=session_id,
            agent_name=agent_name,
            action=action,
            output_data=output_data,
        )
        db.add(log)
        await db.commit()


# ---------------------------------------------------------------------------
# Normal tests — GET /sessions/{id}/diagnosis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_returns_full_data(client: AsyncClient):
    """Diagnosis endpoint returns the complete structured data persisted by WebSocket."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", FULL_DIAGNOSIS_DATA)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    assert resp.status_code == 200
    data = resp.json()

    assert data["differential_diagnosis"][0]["diagnosis"] == "Pulmonary Embolism"
    assert data["recommended_tests"] == ["CT-PA", "D-dimer"]
    assert data["critic_review"]["safety_flag"] == "urgent"
    assert data["debate_outcome"]["final_verdict"] == "resolved"
    assert len(data["debate_outcome"]["rounds"]) == 1
    assert data["debate_outcome"]["rounds"][0]["challenges"][0]["claim"] == "Missing D-dimer result"
    assert data["coordinator_response"] == "Based on our analysis..."


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_returns_null_when_no_diagnosis(client: AsyncClient):
    """Sessions with no completed diagnosis return null."""
    sid = await _create_session()

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_debate_outcome_contains_rounds(client: AsyncClient):
    """The debate_outcome.rounds array has all challenge/response pairs."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", FULL_DIAGNOSIS_DATA)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    rounds = resp.json()["debate_outcome"]["rounds"]
    r1 = rounds[0]

    assert r1["round_number"] == 1
    assert r1["resolution"] == "resolved"
    assert len(r1["challenges"]) == 1
    assert len(r1["responses"]) == 1
    assert r1["responses"][0]["action"] == "accept"


# ---------------------------------------------------------------------------
# Normal tests — GET /sessions/ (enriched list)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_sessions_includes_diagnosis_metadata(client: AsyncClient):
    """Session list includes preliminary_diagnosis and safety_flags from agent_logs."""
    sid = await _create_session("Chest Pain Case")
    await _add_agent_log(sid, "coordinator", "diagnosis_result", FULL_DIAGNOSIS_DATA)
    await _add_agent_log(sid, "interviewer", "transition", {"content": "Starting..."})

    resp = await client.get("/api/v1/sessions/")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1

    s = sessions[0]
    assert s["preliminary_diagnosis"] == "Pulmonary Embolism"
    assert s["safety_flags"] == ["urgent"]
    assert "coordinator" in s["agent_participation"]
    assert "interviewer" in s["agent_participation"]


@pytest.mark.asyncio(loop_scope="function")
async def test_list_sessions_no_diagnosis_returns_defaults(client: AsyncClient):
    """Sessions without diagnosis logs have null/empty metadata fields."""
    sid = await _create_session("New Session")

    resp = await client.get("/api/v1/sessions/")
    sessions = resp.json()
    s = sessions[0]

    assert s["preliminary_diagnosis"] is None
    assert s["safety_flags"] == []
    assert s["agent_participation"] == []


# ---------------------------------------------------------------------------
# Normal tests — agent logs content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_agent_logs_content_from_content_field(client: AsyncClient):
    """Logs persisted with content= are readable via the REST endpoint."""
    sid = await _create_session()
    await _add_agent_log(sid, "debate_round", "debate_challenge", {"content": "R1 challenge: Missing labs"})

    resp = await client.get(f"/api/v1/agents/logs/{sid}")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 1
    assert logs[0]["content"] == "R1 challenge: Missing labs"


@pytest.mark.asyncio(loop_scope="function")
async def test_agent_logs_data_path_falls_back_to_action(client: AsyncClient):
    """Logs persisted with data= (no content key) fall back to action name."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", {"differential_diagnosis": []})

    resp = await client.get(f"/api/v1/agents/logs/{sid}")
    logs = resp.json()
    # output_data has no "content" key → falls back to log.action
    assert logs[0]["content"] == "diagnosis_result"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_empty_output_data(client: AsyncClient):
    """Diagnosis log with empty dict output_data returns null (empty dict is falsy)."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", {})

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_null_output_data(client: AsyncClient):
    """Diagnosis log with None output_data returns null."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", None)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_multiple_logs_returns_latest(client: AsyncClient):
    """When multiple diagnosis_result logs exist, the latest one is returned."""
    sid = await _create_session()

    old_data = {
        "differential_diagnosis": [{"diagnosis": "Old Diagnosis", "confidence": 50, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "recommended_tests": [],
        "reasoning_chain": "",
        "critic_review": {},
        "debate_outcome": {},
        "coordinator_response": "old",
    }
    new_data = {
        "differential_diagnosis": [{"diagnosis": "Updated Diagnosis", "confidence": 90, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "recommended_tests": ["MRI"],
        "reasoning_chain": "",
        "critic_review": {},
        "debate_outcome": {},
        "coordinator_response": "new",
    }
    await _add_agent_log(sid, "coordinator", "diagnosis_result", old_data)
    await _add_agent_log(sid, "coordinator", "diagnosis_result", new_data)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    data = resp.json()
    assert data["differential_diagnosis"][0]["diagnosis"] == "Updated Diagnosis"
    assert data["coordinator_response"] == "new"


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_no_debate_outcome(client: AsyncClient):
    """Diagnosis without debate_outcome (V1 flow) still returns valid data."""
    data_no_debate = {
        "differential_diagnosis": [
            {"diagnosis": "Migraine", "confidence": 70, "supporting_evidence": ["headache"], "against_evidence": [], "source": "RAG"},
        ],
        "recommended_tests": ["CT Head"],
        "reasoning_chain": "Simple case",
        "critic_review": {"approval": True, "safety_flag": "", "issues": [], "final_assessment": "OK"},
        "coordinator_response": "Simple response",
    }
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", data_no_debate)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    data = resp.json()
    assert data["differential_diagnosis"][0]["diagnosis"] == "Migraine"
    assert "debate_outcome" not in data


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_nonexistent_session(client: AsyncClient):
    """Diagnosis endpoint for a nonexistent session returns null (not 404)."""
    resp = await client.get("/api/v1/sessions/nonexistent-id/diagnosis")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio(loop_scope="function")
async def test_list_sessions_no_critic_review_no_safety_flags(client: AsyncClient):
    """Diagnosis without critic_review produces empty safety_flags."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", {
        "differential_diagnosis": [{"diagnosis": "Flu", "confidence": 80, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "critic_review": {},
    })

    resp = await client.get("/api/v1/sessions/")
    s = resp.json()[0]
    assert s["preliminary_diagnosis"] == "Flu"
    assert s["safety_flags"] == []


@pytest.mark.asyncio(loop_scope="function")
async def test_list_sessions_empty_differential(client: AsyncClient):
    """Diagnosis with empty differential_diagnosis produces null preliminary."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", {
        "differential_diagnosis": [],
        "critic_review": {"safety_flag": "caution"},
    })

    resp = await client.get("/api/v1/sessions/")
    s = resp.json()[0]
    assert s["preliminary_diagnosis"] is None
    assert s["safety_flags"] == ["caution"]


@pytest.mark.asyncio(loop_scope="function")
async def test_list_sessions_uses_latest_diagnosis_result(client: AsyncClient):
    """Session list enrichment should use the newest diagnosis_result log."""
    sid = await _create_session("Repeated Run")
    await _add_agent_log(sid, "coordinator", "diagnosis_result", {
        "differential_diagnosis": [{"diagnosis": "Old Diagnosis", "confidence": 40, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "critic_review": {"safety_flag": "yellow"},
    })
    await _add_agent_log(sid, "coordinator", "diagnosis_result", {
        "differential_diagnosis": [{"diagnosis": "New Diagnosis", "confidence": 90, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "critic_review": {"safety_flag": "red"},
    })

    resp = await client.get("/api/v1/sessions/")
    s = resp.json()[0]
    assert s["preliminary_diagnosis"] == "New Diagnosis"
    assert s["safety_flags"] == ["red"]


@pytest.mark.asyncio(loop_scope="function")
async def test_list_multiple_sessions_batch_enrichment(client: AsyncClient):
    """Multiple sessions are enriched in batch, not N+1."""
    sid1 = await _create_session("Session A")
    sid2 = await _create_session("Session B")
    sid3 = await _create_session("Session C (no diagnosis)")

    await _add_agent_log(sid1, "coordinator", "diagnosis_result", {
        "differential_diagnosis": [{"diagnosis": "Asthma", "confidence": 75, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "critic_review": {"safety_flag": "caution"},
    })
    await _add_agent_log(sid1, "interviewer", "reasoning", {"content": "Asking questions"})

    await _add_agent_log(sid2, "coordinator", "diagnosis_result", {
        "differential_diagnosis": [{"diagnosis": "COPD", "confidence": 65, "supporting_evidence": [], "against_evidence": [], "source": "RAG"}],
        "critic_review": {},
    })

    resp = await client.get("/api/v1/sessions/")
    sessions = {s["title"]: s for s in resp.json()}

    assert sessions["Session A"]["preliminary_diagnosis"] == "Asthma"
    assert sessions["Session A"]["safety_flags"] == ["caution"]
    assert "interviewer" in sessions["Session A"]["agent_participation"]

    assert sessions["Session B"]["preliminary_diagnosis"] == "COPD"
    assert sessions["Session B"]["safety_flags"] == []

    assert sessions["Session C (no diagnosis)"]["preliminary_diagnosis"] is None
    assert sessions["Session C (no diagnosis)"]["agent_participation"] == []


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_with_cdss_scores(client: AsyncClient):
    """CDSS scores are preserved in the diagnosis response."""
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", FULL_DIAGNOSIS_DATA)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    data = resp.json()
    assert "cdss_scores" in data
    assert data["cdss_scores"]["wells"]["risk_level"] == "high"


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnosis_multi_round_debate(client: AsyncClient):
    """Diagnosis with multiple debate rounds preserves all rounds."""
    multi_round_data = {
        **FULL_DIAGNOSIS_DATA,
        "debate_outcome": {
            "rounds": [
                {
                    "round_number": 1,
                    "challenges": [{"challenge_id": "c1", "type": "evidence_gap", "claim": "Round 1 issue", "evidence": [], "suggested_action": "Fix"}],
                    "responses": [{"challenge_id": "c1", "action": "refute", "reasoning": "Evidence exists", "evidence": ["Ref A"]}],
                    "resolution": "resolved",
                },
                {
                    "round_number": 2,
                    "challenges": [{"challenge_id": "c2", "type": "safety_concern", "claim": "Round 2 issue", "evidence": [], "suggested_action": "Escalate"}],
                    "responses": [{"challenge_id": "c2", "action": "accept", "reasoning": "Valid concern", "evidence": []}],
                    "resolution": "resolved",
                },
            ],
            "final_verdict": "resolved",
            "total_challenges": 2,
            "accepted": 1,
            "refuted": 1,
            "summary": "Two rounds, mixed outcomes.",
        },
    }
    sid = await _create_session()
    await _add_agent_log(sid, "coordinator", "diagnosis_result", multi_round_data)

    resp = await client.get(f"/api/v1/sessions/{sid}/diagnosis")
    rounds = resp.json()["debate_outcome"]["rounds"]
    assert len(rounds) == 2
    assert rounds[0]["challenges"][0]["claim"] == "Round 1 issue"
    assert rounds[1]["challenges"][0]["type"] == "safety_concern"
    assert rounds[0]["responses"][0]["action"] == "refute"
    assert rounds[1]["responses"][0]["action"] == "accept"
