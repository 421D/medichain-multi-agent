"""Tests for `_build_patient_history` and `run_offline_evaluation` in harness/run.py."""
import pytest

from harness.run import _build_patient_history, run_offline_evaluation
from harness.test_cases import EVALUATION_CASES


# ─────────────────────── _build_patient_history ────────────────────────

def test_build_patient_history_emits_required_schema_keys():
    """Output must match `models.schemas.PatientSummary` field names — the
    diagnostician prompt JSON-formats it and silently drops missing keys."""
    case = {
        "case_id": "T-001",
        "name": "test_case",
        "initial_message": "I have crushing chest pain radiating to my left arm.",
        "follow_up_answers": [
            "Started 2 hours ago, severity 9/10.",
            "I am 60 with hypertension and diabetes.",
        ],
    }

    history = _build_patient_history(case)

    expected_keys = {
        "chief_complaint",
        "history_of_present_illness",
        "past_medical_history",
        "medications",
        "allergies",
        "family_history",
        "review_of_systems",
        "raw_transcript",
    }
    assert set(history.keys()) == expected_keys


def test_build_patient_history_truncates_chief_complaint_to_120_chars():
    long_msg = "x" * 500
    history = _build_patient_history({
        "case_id": "T-002",
        "initial_message": long_msg,
        "follow_up_answers": [],
    })
    # Chief complaint slot is bounded so it doesn't push the rest of the
    # prompt off the LLM's effective context window.
    assert len(history["chief_complaint"]) == 120


def test_build_patient_history_includes_followups_in_hpi():
    history = _build_patient_history({
        "case_id": "T-003",
        "initial_message": "headache for 3 days",
        "follow_up_answers": ["worse at night", "pain 7/10"],
    })
    # HPI starts with the chief complaint and bullets each follow-up.
    assert history["history_of_present_illness"].startswith("headache for 3 days")
    assert "- worse at night" in history["history_of_present_illness"]
    assert "- pain 7/10" in history["history_of_present_illness"]


def test_build_patient_history_handles_no_followups():
    history = _build_patient_history({
        "case_id": "T-004",
        "initial_message": "fever and chills",
        "follow_up_answers": [],
    })
    assert history["review_of_systems"] == ""
    assert history["history_of_present_illness"] == "fever and chills"


# ──────────────────────── run_offline_evaluation ────────────────────────

def test_run_offline_evaluation_returns_one_scored_result_per_case(capsys):
    """Smoke test: offline mode should never invoke an LLM and should produce
    exactly one ScoredResult per input case under the "offline" variant key."""
    # Use the first 2 real ground-truth cases so we exercise the actual scoring
    # pipeline rather than synthetic fixtures.
    sample = EVALUATION_CASES[:2]

    results = run_offline_evaluation(sample)

    assert set(results.keys()) == {"offline"}
    assert len(results["offline"]) == 2
    for scored in results["offline"]:
        # Each ScoredResult should carry the case id from the input case.
        assert scored.case_id in {c["case_id"] for c in sample}

    # Verify the function actually printed progress (proves we exercised the
    # full loop, not a no-op short-circuit).
    out = capsys.readouterr().out
    assert "offline" in out.lower()


def test_run_offline_evaluation_with_empty_case_list_is_noop():
    results = run_offline_evaluation([])
    assert results == {"offline": []}
