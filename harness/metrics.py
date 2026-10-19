from dataclasses import dataclass, field


@dataclass
class ScoredResult:
    case_id: str = ""
    case_name: str = ""
    top1_correct: bool = False
    top3_recall: bool = False
    safety_flag_correct: bool = False
    debate_rounds: int = 0
    challenges_accepted: int = 0
    challenges_refuted: int = 0
    total_time_seconds: float = 0.0
    # Fields preserved for frontend display (AI output vs ground truth)
    ai_primary_diagnosis: str = ""
    ai_top3: list = field(default_factory=list)
    ai_safety_flag: str = ""
    ai_final_assessment: str = ""
    ground_truth_primary: str = ""
    ground_truth_safety: str = ""
    ground_truth_ddx: list = field(default_factory=list)
    ground_truth_tests: list = field(default_factory=list)
    debate_summary: list = field(default_factory=list)
    error: str = ""


@dataclass
class EvaluationMetrics:
    top1_accuracy: float = 0.0
    top3_recall: float = 0.0
    safety_flag_recall: float = 0.0
    missed_critical: int = 0
    debate_rounds_avg: float = 0.0
    challenge_acceptance_rate: float = 0.0
    diagnosis_revision_rate: float = 0.0
    total_cases: int = 0


_STOPWORDS = {
    "acute", "chronic", "the", "of", "and", "a", "an", "with", "without",
    "disease", "disorder", "syndrome", "condition",
}


def _name_match(a: str, b: str) -> bool:
    """Fuzzy medical-diagnosis name match.

    Returns True if either:
      - one name is a substring of the other (e.g. "UTI" in "lower UTI"), OR
      - token overlap >= 50% of the shorter side, excluding stopwords.

    This handles cases like "Bacterial meningitis" vs "Meningococcal meningitis"
    where the AI gives a more specific subtype but the key token matches.
    """
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    a_tokens = set(a.split()) - _STOPWORDS
    b_tokens = set(b.split()) - _STOPWORDS
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens) / min(len(a_tokens), len(b_tokens))
    return overlap >= 0.5


def score_single_case(result: dict, ground_truth: dict, case: dict | None = None) -> ScoredResult:
    """Score a single case result against ground truth.

    Fills in both scoring fields AND verbose display fields so the frontend
    can render AI output vs ground truth side by side.
    """
    ddx = result.get("diagnosis", {}).get("differential_diagnosis", []) or []
    ddx_names = [d.get("diagnosis", "") for d in ddx]

    primary = ground_truth.get("primary_diagnosis", "")
    expected_in_ddx = ground_truth.get("expected_in_ddx", [])
    expected_flag = ground_truth.get("expected_safety_flag", "green")

    top1_correct = _name_match(primary, ddx_names[0]) if ddx_names else False
    top3_recall = any(
        _name_match(exp, name)
        for exp in expected_in_ddx
        for name in ddx_names[:3]
    ) if ddx_names else False

    critic_review = result.get("critic_review") or {}
    actual_flag = critic_review.get("safety_flag", "green")
    safety_correct = actual_flag == expected_flag

    debate = result.get("debate_outcome") or {}
    rounds_list = debate.get("rounds", []) or []
    rounds = len(rounds_list)
    accepted = debate.get("accepted", 0)
    refuted = debate.get("refuted", 0)

    # Debate summary for frontend: round number + challenge count + resolution
    debate_summary = [
        {
            "round_number": r.get("round_number", i + 1),
            "challenges_count": len(r.get("challenges", [])),
            "responses_count": len(r.get("responses", [])),
            "resolution": r.get("resolution", "unknown"),
        }
        for i, r in enumerate(rounds_list)
    ]

    case_id = case.get("case_id", "") if case else ""
    case_name = case.get("name", "") if case else ""

    return ScoredResult(
        case_id=case_id,
        case_name=case_name,
        top1_correct=top1_correct,
        top3_recall=top3_recall,
        safety_flag_correct=safety_correct,
        debate_rounds=rounds,
        challenges_accepted=accepted,
        challenges_refuted=refuted,
        ai_primary_diagnosis=ddx_names[0] if ddx_names else "(none)",
        ai_top3=ddx_names[:3],
        ai_safety_flag=actual_flag,
        ai_final_assessment=(critic_review.get("final_assessment") or "")[:300],
        ground_truth_primary=primary,
        ground_truth_safety=expected_flag,
        ground_truth_ddx=expected_in_ddx,
        ground_truth_tests=ground_truth.get("expected_tests", []),
        debate_summary=debate_summary,
    )


def aggregate_metrics(scored_results: list) -> EvaluationMetrics:
    """Aggregate scored results into evaluation metrics."""
    # Exclude errored cases from scoring averages but count them as missed
    valid = [r for r in scored_results if not r.error]
    n = len(valid)
    if n == 0:
        return EvaluationMetrics(missed_critical=len(scored_results), total_cases=len(scored_results))

    top1 = sum(1 for r in valid if r.top1_correct) / n
    top3 = sum(1 for r in valid if r.top3_recall) / n
    safety = sum(1 for r in valid if r.safety_flag_correct) / n
    missed = sum(1 for r in valid if not r.safety_flag_correct) + (len(scored_results) - n)
    debate_avg = sum(r.debate_rounds for r in valid) / n
    total_accepted = sum(r.challenges_accepted for r in valid)
    total_challenges = total_accepted + sum(r.challenges_refuted for r in valid)
    acceptance_rate = total_accepted / total_challenges if total_challenges > 0 else 0.0
    revision_rate = sum(1 for r in valid if r.challenges_accepted > 0) / n

    return EvaluationMetrics(
        top1_accuracy=top1, top3_recall=top3,
        safety_flag_recall=safety, missed_critical=missed,
        debate_rounds_avg=debate_avg,
        challenge_acceptance_rate=acceptance_rate,
        diagnosis_revision_rate=revision_rate,
        total_cases=len(scored_results),
    )
