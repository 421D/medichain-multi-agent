"""Evaluation harness API routes.

Exposes the offline eval harness (harness/run.py) through REST so the
frontend Evaluation page can:
  - show the latest eval report (metrics + per-case breakdown + ground truth)
  - list available test cases
  - trigger a new evaluation run (async background task)
"""
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harness.test_cases import EVALUATION_CASES

router = APIRouter(prefix="/api/v1/evaluation", tags=["Evaluation"])

# Reports are written here by `python -m harness.run`
REPO_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = REPO_ROOT / "reports"
LATEST_JSON = REPORTS_DIR / "evaluation_latest.json"

# Track the currently running evaluation (if any)
_run_state: dict = {
    "status": "idle",  # idle | running | completed | failed
    "started_at": None,
    "completed_at": None,
    "error": None,
}


class EvaluationSummary(BaseModel):
    status: str
    generated_at: str | None = None
    variants: list = []


class EvalRunRequest(BaseModel):
    limit: int | None = None  # run first N cases; omit/null = all
    case_id: str | None = None  # run a specific case


@router.get("/latest")
async def get_latest_evaluation():
    """Return the latest evaluation report (metrics + per-case details).

    Reads reports/evaluation_latest.json which is written by `python -m harness.run`.
    If no report exists yet, returns an empty shape so the frontend can show
    a helpful "run an evaluation first" state.
    """
    if not LATEST_JSON.exists():
        return {
            "generated_at": None,
            "variants": [],
            "has_data": False,
            "message": "No evaluation run yet. Click 'Run Evaluation' to generate a report.",
        }

    try:
        data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        data["has_data"] = True
        return data
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Corrupted evaluation report: {e}",
        )


@router.get("/cases")
async def list_evaluation_cases():
    """List all ground-truth test cases with their expected diagnosis.

    Used by the frontend to show what the eval harness is testing against,
    even before any run has happened.
    """
    return {
        "total": len(EVALUATION_CASES),
        "cases": [
            {
                "case_id": c["case_id"],
                "name": c["name"],
                "initial_message": c["initial_message"],
                "follow_up_answers": c.get("follow_up_answers", []),
                "ground_truth": c["ground_truth"],
            }
            for c in EVALUATION_CASES
        ],
    }


@router.get("/status")
async def get_evaluation_status():
    """Current running status of the eval harness (idle/running/completed/failed)."""
    return _run_state


def _run_harness_subprocess(limit: int | None, case_id: str | None):
    """Spawn `python -m harness.run` as a subprocess so the API doesn't block."""
    global _run_state
    _run_state["status"] = "running"
    _run_state["started_at"] = datetime.now().isoformat()
    _run_state["completed_at"] = None
    _run_state["error"] = None

    cmd = [sys.executable, "-m", "harness.run"]
    if case_id:
        cmd += ["--case", case_id]
    elif limit and limit > 0:
        cmd += ["--limit", str(limit)]

    try:
        env = {"TOKENIZERS_PARALLELISM": "false"}
        # Inherit parent env so API keys are available
        import os
        full_env = {**os.environ, **env}

        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min hard cap
            env=full_env,
        )
        if result.returncode != 0:
            _run_state["status"] = "failed"
            _run_state["error"] = result.stderr[-500:] or "unknown error"
        else:
            _run_state["status"] = "completed"
    except subprocess.TimeoutExpired:
        _run_state["status"] = "failed"
        _run_state["error"] = "Evaluation timed out after 30 minutes"
    except Exception as e:
        _run_state["status"] = "failed"
        _run_state["error"] = f"{type(e).__name__}: {e}"
    finally:
        _run_state["completed_at"] = datetime.now().isoformat()


@router.post("/run")
async def trigger_evaluation(req: EvalRunRequest):
    """Trigger a new evaluation run in the background.

    Returns immediately with status='running'. Frontend can poll /status
    to know when it's done, then GET /latest for the new results.

    Note: under multi-worker uvicorn the `_run_state` module-level dict is
    only visible to the worker that handled the trigger; another worker
    polling /status will see "idle". Keep `--workers 1` for evaluation
    runs, or persist run-state to the database.
    """
    if _run_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="An evaluation is already running. Poll /api/v1/evaluation/status.",
        )

    # Run in a thread pool so the event loop stays responsive. We don't use
    # FastAPI's BackgroundTasks because that runs after the response is sent
    # but blocks the worker; an executor frees the event loop immediately.
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_harness_subprocess, req.limit, req.case_id)

    _run_state["status"] = "running"
    _run_state["started_at"] = datetime.now().isoformat()

    return {
        "status": "started",
        "limit": req.limit,
        "case_id": req.case_id,
        "started_at": _run_state["started_at"],
    }
