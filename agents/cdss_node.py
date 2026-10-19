"""CDSS Selector node.

Sits between Diagnostician and Debate Round. Uses one LLM call to decide
which deterministic clinical scoring tools (Wells, CURB-65, CHA2DS2-VASc,
HEART, qSOFA, PHQ-9) apply to the current DDx, extracts the required
parameters from the patient history, then calls the real Python scoring
functions in `cdss/scoring.py` and stores the results in
`state["cdss_scores"]`.

Downstream consumers:
- Critic / Diagnostician debate prompts already accept `cdss_scores`
- Coordinator already reads `cdss_scores` for the patient-facing summary
- Frontend DiagnosisPanel renders a "Clinical Scoring (CDSS)" card

The node is deliberately tolerant: if the LLM fails, returns malformed
params, or picks an unknown tool, we log and skip that selection rather
than crashing the graph. An empty `cdss_scores` is a valid pipeline state.
"""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import get_structured_llm
from cdss.scoring import (
    calculate_wells_score, WellsInput,
    calculate_curb65, CURB65Input,
    calculate_cha2ds2_vasc, CHA2DS2VASCInput,
    calculate_heart_score, HEARTInput,
    calculate_qsofa, QSOFAInput,
    screen_phq9, PHQ9Input,
)
from models.schemas import CDSSEvaluation
from prompts.cdss_prompt import CDSS_SELECTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# Map LLM-selectable tool names to (Python score function, Pydantic input schema).
_TOOL_REGISTRY: dict[str, tuple] = {
    "wells_score":   (calculate_wells_score,   WellsInput),
    "curb65":        (calculate_curb65,        CURB65Input),
    "cha2ds2_vasc":  (calculate_cha2ds2_vasc,  CHA2DS2VASCInput),
    "heart_score":   (calculate_heart_score,   HEARTInput),
    "qsofa":         (calculate_qsofa,         QSOFAInput),
    "phq9":          (screen_phq9,             PHQ9Input),
}


# Deterministic fallback rules: if LLM selector returns an empty scores_to_run
# but the DDx or chief complaint hits a high-value keyword, force-candidate the
# corresponding tool. We still attempt to compute it — if param validation fails
# we record a "skipped" entry with reason so the UI shows "considered but not
# enough data" rather than a silent omission.
_FALLBACK_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # tool_name, keywords (case-insensitive substring match)
    ("heart_score",   ("chest pain", "ami", "acute myocardial", "unstable angina", "acs", "acute coronary")),
    ("curb65",        ("pneumonia", "cap", "community-acquired")),
    ("wells_score",   ("pulmonary embolism", "pe ", " pe,", " dvt", "deep vein thrombosis")),
    ("qsofa",         ("sepsis", "septic shock", "bacteremia")),
    ("cha2ds2_vasc",  ("atrial fibrillation", "afib", "a-fib")),
    ("phq9",          ("major depressive", "depression screen", "phq-9", "phq9")),
]


def _heuristic_params(tool_name: str, patient_history: dict, ddx: list[dict]) -> dict:
    """Best-effort param extraction from free-text patient history when the
    LLM selector failed validation. Each tool needs only enough fields to
    compute a real (rather than mocked) score; missing dimensions default
    to the most conservative non-zero value so the score reflects suspicion
    rather than asserting absent findings."""
    text = " ".join([
        str(patient_history.get("chief_complaint") or ""),
        str(patient_history.get("history_of_present_illness") or ""),
        str(patient_history.get("past_medical_history") or ""),
        str(patient_history.get("review_of_systems") or ""),
        str((ddx[0] if ddx else {}).get("diagnosis") or ""),
    ]).lower()

    if tool_name == "heart_score":
        suspicious_phrases = (
            "crushing", "radiating", "left arm", "jaw", "diaphor", "sweating",
            "shortness of breath", "pressure", "tightness",
        )
        history = 2 if sum(p in text for p in suspicious_phrases) >= 2 else 1
        ecg = 1  # no ECG data → assume non-specific changes (conservative)
        try:
            import re
            m = re.search(r"(\d{2,3})[\s\-]*(?:y|year|yo)", text)
            age_n = int(m.group(1)) if m else 50
        except Exception:
            age_n = 50
        age = 2 if age_n >= 65 else (1 if age_n >= 45 else 0)
        rf_terms = ("hypertension", "htn", "diabetes", "dm ", "hyperlipid",
                    "cholesterol", "smok", "obese", "family history", "father had",
                    "mother had", "atherosclero")
        rf_count = sum(1 for t in rf_terms if t in text)
        risk_factors = 2 if rf_count >= 3 else (1 if rf_count >= 1 else 0)
        troponin = 1  # not measured at this point in workup
        return {"history": history, "ecg": ecg, "age": age,
                "risk_factors": risk_factors, "troponin": troponin}

    if tool_name == "wells_score":
        return {
            "clinical_signs_dvt": False, "pe_most_likely": True,
            "heart_rate_over_100": "tachycard" in text or "hr 1" in text,
            "immobilization_or_surgery": "immobil" in text or "surgery" in text,
            "previous_pe_or_dvt": "previous pe" in text or "prior dvt" in text,
            "hemoptysis": "hemoptysis" in text or "coughing blood" in text,
            "malignancy": "cancer" in text or "malignan" in text,
        }

    if tool_name == "curb65":
        try:
            import re
            m = re.search(r"(\d{2,3})[\s\-]*(?:y|year|yo)", text)
            age_n = int(m.group(1)) if m else 60
        except Exception:
            age_n = 60
        return {
            "confusion": "confus" in text, "urea_high": False,
            "respiratory_rate_high": "tachypn" in text or "rr 3" in text,
            "low_blood_pressure": "hypotens" in text,
            "age_65_or_more": age_n >= 65,
        }

    if tool_name == "qsofa":
        return {
            "respiratory_rate_22_or_more": "tachypn" in text,
            "altered_mentation": "confus" in text or "altered" in text,
            "systolic_bp_100_or_less": "hypotens" in text,
        }

    # cha2ds2_vasc / phq9 not heuristically guessable from a single ED note
    return {}


def _fallback_candidates(ddx: list[dict], patient_history: dict) -> list[str]:
    """Identify CDSS tools that should be attempted based on DDx / complaint keywords."""
    haystack_parts = []
    for d in ddx[:3]:
        haystack_parts.append(str(d.get("diagnosis", "")))
        haystack_parts.append(str(d.get("reasoning_chain", "")))
    cc = patient_history.get("chief_complaint") or patient_history.get("presentation") or ""
    haystack_parts.append(str(cc))
    haystack = " ".join(haystack_parts).lower()

    hits: list[str] = []
    for tool, kws in _FALLBACK_KEYWORDS:
        if any(kw in haystack for kw in kws):
            hits.append(tool)
    return hits


def cdss_node(state: dict) -> dict:
    """Select + run CDSS scoring tools applicable to the current DDx."""
    diagnosis = state.get("diagnosis") or {}
    ddx = diagnosis.get("differential_diagnosis") or []
    patient_history = state.get("patient_history") or {}
    agent_logs: list[dict] = []

    if not ddx:
        agent_logs.append({"agent": "cdss", "action": "skip", "reason": "no DDx available"})
        return {"cdss_scores": {}, "agent_logs": agent_logs}

    # Step 1: ask the LLM which scores apply + extract params
    try:
        llm = get_structured_llm(
            CDSSEvaluation,
            temperature=0.1,
            model_override=state.get("llm_model"),
            node="cdss",
            session_id=state.get("session_id"),
        )
        user_msg = (
            f"## Patient History\n{json.dumps(patient_history, ensure_ascii=False, indent=2)}\n\n"
            f"## Differential Diagnosis (top 3)\n"
            f"{json.dumps(ddx[:3], ensure_ascii=False, indent=2)}\n\n"
            f"Decide which clinical scoring tools apply and extract their parameters."
        )
        evaluation: CDSSEvaluation = llm.invoke([
            SystemMessage(content=CDSS_SELECTOR_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
    except Exception as e:
        logger.warning("CDSS selector LLM call failed: %s", e)
        agent_logs.append({"agent": "cdss", "action": "error", "detail": str(e)[:200]})
        return {"cdss_scores": {}, "agent_logs": agent_logs}

    # Step 2: run each selected tool with the LLM-extracted params
    cdss_scores: dict[str, dict] = {}
    for selection in evaluation.scores_to_run:
        tool_name = (selection.tool or "").strip().lower()
        if tool_name not in _TOOL_REGISTRY:
            logger.warning("CDSS selector picked unknown tool: %s", tool_name)
            continue
        score_fn, input_schema = _TOOL_REGISTRY[tool_name]
        try:
            input_obj = input_schema.model_validate(selection.params or {})
            result = score_fn(input_obj)
            entry = result.model_dump()
            entry["rationale"] = selection.rationale or ""
            cdss_scores[tool_name] = entry
        except Exception as e:
            logger.warning("CDSS tool '%s' failed: %s", tool_name, e)
            cdss_scores[tool_name] = {
                "error": str(e)[:200],
                "rationale": selection.rationale or "",
            }

    # Step 2.5: deterministic fallback — if no valid score landed (selector
    # returned empty OR every selected tool errored on param validation),
    # try the keyword-matched candidates with heuristic param extraction
    # from the patient text. Heuristic params are flagged in the rationale
    # so the UI / coordinator can communicate the lower confidence.
    has_valid = any(
        "error" not in v and "skipped_reason" not in v
        for v in cdss_scores.values()
    )
    if not has_valid:
        candidates = _fallback_candidates(ddx, patient_history)
        if candidates:
            fallback_run: list[str] = []
            for tool_name in candidates:
                if tool_name not in _TOOL_REGISTRY:
                    continue
                score_fn, input_schema = _TOOL_REGISTRY[tool_name]
                heuristic_params = _heuristic_params(tool_name, patient_history, ddx)
                try:
                    input_obj = input_schema.model_validate(heuristic_params)
                    result = score_fn(input_obj)
                    entry = result.model_dump()
                    entry["rationale"] = (
                        f"Heuristic estimate from patient text features "
                        f"(no structured ECG/troponin data; treat as preliminary)."
                    )
                    entry["fallback"] = True
                    cdss_scores[tool_name] = entry
                    fallback_run.append(tool_name)
                except Exception as e:
                    cdss_scores[tool_name] = {
                        "skipped_reason": f"insufficient params for {tool_name}: {str(e)[:160]}",
                        "fallback": True,
                        "rationale": "heuristic fallback attempted",
                    }
            if fallback_run:
                agent_logs.append({
                    "agent": "cdss",
                    "action": "fallback",
                    "tools_run": fallback_run,
                    "reason": "no valid LLM-extracted score; ran keyword-matched candidates with heuristic params",
                })

    agent_logs.append({
        "agent": "cdss",
        "action": "scores_computed",
        "tools_run": list(cdss_scores.keys()),
        "count": sum(1 for v in cdss_scores.values() if "skipped_reason" not in v),
        "selector_reasoning": (evaluation.reasoning or "")[:200],
    })
    return {"cdss_scores": cdss_scores, "agent_logs": agent_logs}
