"""CLI entry point for running MediChain evaluation harness.

Usage:
    python -m harness.run                    # Run all cases (live LLM)
    python -m harness.run --case EVAL-001    # Run single case
    python -m harness.run --limit 2          # Run first N cases (for quick test)
    python -m harness.run --offline          # Offline mock mode (no LLM calls)
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from harness.metrics import score_single_case, aggregate_metrics, ScoredResult
from harness.test_cases import EVALUATION_CASES
from harness.reporter import generate_report, generate_json_report

RESULTS_DIR = Path(__file__).parent.parent / "reports"


def _build_patient_history(case: dict) -> dict:
    """Build a pre-populated patient_history dict from test case.

    The harness pipeline bypasses the Interviewer agent (which requires
    multi-turn interrupt/resume) and feeds a synthetic patient_history
    directly to the Diagnostician. This isolates evaluation to the
    diagnostic + debate pipeline.
    """
    chief = case["initial_message"]
    follow_ups = case.get("follow_up_answers", [])
    hpi_lines = [chief] + [f"- {ans}" for ans in follow_ups]

    # Field set must match models.schemas.PatientSummary (which is what the
    # diagnostician prompt expects). `social_history` and `raw_transcript`
    # are not part of that schema; the latter is kept for harness debugging
    # but neither field is read downstream.
    return {
        "chief_complaint": chief[:120],
        "history_of_present_illness": "\n".join(hpi_lines),
        "past_medical_history": "",
        "medications": "",
        "allergies": "",
        "family_history": "",
        "review_of_systems": "\n".join(follow_ups),
        "raw_transcript": "\n".join(hpi_lines),
    }


def run_offline_evaluation(cases: list[dict]) -> dict[str, list[ScoredResult]]:
    """Run evaluation in offline mode (no LLM calls, mock results).

    Used for smoke-testing the scoring pipeline without burning LLM credits.
    """
    print(f"Running offline evaluation on {len(cases)} cases...")
    print("(Offline mode: scoring pipeline smoke test only)\n")

    scored = []
    for case in cases:
        mock_result = {
            "diagnosis": {"differential_diagnosis": []},
            "critic_review": {"safety_flag": "green"},
            "debate_outcome": None,
        }
        s = score_single_case(mock_result, case["ground_truth"], case=case)
        scored.append(s)
        print(f"  [{case['case_id']}] {case['name']}: scored (offline)")

    return {"offline": scored}


def run_live_evaluation(cases: list[dict]) -> dict[str, list[ScoredResult]]:
    """Run full LLM-powered evaluation using the V2 debate pipeline.

    Pipeline per case:
        patient_history (pre-filled) -> diagnostician -> debate_round -> (coordinator)

    Interviewer is bypassed because it requires multi-turn interrupt/resume
    which is not needed for offline scoring.
    """
    from agents.cdss_node import cdss_node
    from agents.debate import debate_round_node
    from agents.diagnostician import diagnostician_node, set_retriever
    from agents.coordinator import coordinator_node
    from rag.knowledge_base import KnowledgeBase
    from rag.retriever import Retriever

    print(f"Running LIVE evaluation on {len(cases)} cases (V2 debate pipeline)...")
    print("Loading medical knowledge base...")
    kb = KnowledgeBase()
    n_chunks = kb.load()
    if n_chunks == 0:
        print(
            "WARNING: knowledge base loaded 0 chunks — RAG retrieval will be inert.\n"
            "         Diagnoses will rely solely on LLM pretraining knowledge.\n"
            "         Check that data/ contains statpearls_all.jsonl / textbooks_all.jsonl,\n"
            "         or that chroma_data/ has a populated collection.",
            file=sys.stderr,
        )
    retriever = Retriever(kb)
    set_retriever(retriever)
    print(f"Knowledge base ready ({n_chunks if n_chunks else 'collection cached'}).\n")

    scored = []
    for case in cases:
        case_id = case["case_id"]
        case_name = case["name"]
        print(f"  [{case_id}] {case_name}: running...", flush=True)
        start = time.time()

        try:
            # Step 1: seed state with pre-built patient_history
            state = {
                "messages": [],
                "patient_history": _build_patient_history(case),
                "diagnosis": None,
                "critic_review": None,
                "rag_context": None,
                "iteration_count": 0,
                "current_agent": "diagnostician",
                "coordinator_response": None,
                "agent_logs": [],
                "debate_rounds": None,
                "debate_outcome": None,
                "cdss_scores": None,
                "drug_interactions": None,
                "session_id": case_id,
            }

            # Step 2: Diagnostician (RAG + differential diagnosis)
            diag_update = diagnostician_node(state)
            state.update({k: v for k, v in diag_update.items() if k != "agent_logs"})
            state["agent_logs"] = state.get("agent_logs", []) + diag_update.get("agent_logs", [])

            # Step 2b: CDSS selector — pick + run applicable clinical scores so
            # they're visible to the debate critic and the harness metrics.
            try:
                cdss_update = cdss_node(state)
                state.update({k: v for k, v in cdss_update.items() if k != "agent_logs"})
                state["agent_logs"] = state.get("agent_logs", []) + cdss_update.get("agent_logs", [])
            except Exception as cdss_err:
                print(f"    cdss selector failed (non-fatal): {cdss_err}", flush=True)

            # Step 3: Debate round(s) — loop manually until complete or MAX_DEBATE_ROUNDS
            # +1 outer iteration as a safety stop in case the inner cap doesn't trigger.
            from agents.debate import MAX_DEBATE_ROUNDS
            max_iterations = MAX_DEBATE_ROUNDS + 1
            for _ in range(max_iterations):
                dbt_update = debate_round_node(state)
                state.update({k: v for k, v in dbt_update.items() if k != "agent_logs"})
                state["agent_logs"] = state.get("agent_logs", []) + dbt_update.get("agent_logs", [])
                if state.get("current_agent") == "complete":
                    break

            # Step 4: Coordinator (optional, patient-facing response)
            try:
                coord_update = coordinator_node(state)
                state.update({k: v for k, v in coord_update.items() if k != "agent_logs"})
                state["agent_logs"] = state.get("agent_logs", []) + coord_update.get("agent_logs", [])
            except Exception as coord_err:
                print(f"    coordinator failed (non-fatal): {coord_err}", flush=True)

            duration = time.time() - start
            s = score_single_case(state, case["ground_truth"], case=case)
            s.total_time_seconds = duration

            t1 = "✓" if s.top1_correct else "✗"
            sf = "✓" if s.safety_flag_correct else "✗"
            print(
                f"    → top1={t1} safety={sf} rounds={s.debate_rounds} "
                f"primary='{s.ai_primary_diagnosis[:40]}' ({duration:.1f}s)",
                flush=True,
            )
            scored.append(s)

        except Exception as e:
            duration = time.time() - start
            err_msg = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"    ✗ ERROR: {err_msg} ({duration:.1f}s)", flush=True)
            traceback.print_exc()
            s = ScoredResult(
                case_id=case_id,
                case_name=case_name,
                ground_truth_primary=case["ground_truth"].get("primary_diagnosis", ""),
                ground_truth_safety=case["ground_truth"].get("expected_safety_flag", ""),
                ground_truth_ddx=case["ground_truth"].get("expected_in_ddx", []),
                ground_truth_tests=case["ground_truth"].get("expected_tests", []),
                total_time_seconds=duration,
                error=err_msg,
            )
            scored.append(s)

    return {"v2_debate": scored}


def main():
    parser = argparse.ArgumentParser(description="MediChain Evaluation Harness")
    parser.add_argument("--case", type=str, help="Run a specific case by ID")
    parser.add_argument("--limit", type=int, default=0, help="Run first N cases (0 = all)")
    parser.add_argument("--offline", action="store_true", help="Offline mock mode (no LLM)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)

    if args.case:
        cases = [c for c in EVALUATION_CASES if c["case_id"] == args.case]
        if not cases:
            print(f"Case {args.case} not found. Available: {[c['case_id'] for c in EVALUATION_CASES]}")
            sys.exit(1)
    else:
        cases = EVALUATION_CASES
        if args.limit > 0:
            cases = cases[: args.limit]

    if args.offline:
        results = run_offline_evaluation(cases)
    else:
        results = run_live_evaluation(cases)

    # Aggregate
    variant_metrics = {name: aggregate_metrics(lst) for name, lst in results.items()}

    # Markdown report
    md_report = generate_report(variant_metrics, scored_by_variant=results)
    md_path = RESULTS_DIR / f"evaluation_{datetime.now().strftime('%Y-%m-%d')}.md"
    md_path.write_text(md_report, encoding="utf-8")

    # JSON report (for frontend)
    json_report = generate_json_report(variant_metrics, results)
    json_path = RESULTS_DIR / "evaluation_latest.json"
    json_path.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Also save a dated JSON snapshot
    dated_json = RESULTS_DIR / f"evaluation_{datetime.now().strftime('%Y-%m-%d')}.json"
    dated_json.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nMarkdown report: {md_path}")
    print(f"JSON report:     {json_path}")
    print("\n" + md_report)


if __name__ == "__main__":
    main()
