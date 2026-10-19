from harness.metrics import EvaluationMetrics, ScoredResult, score_single_case


def test_top1_correct():
    result = {
        "diagnosis": {
            "differential_diagnosis": [
                {"diagnosis": "Bacterial meningitis", "confidence": 85},
                {"diagnosis": "Viral meningitis", "confidence": 60},
            ],
        },
        "critic_review": {"safety_flag": "red"},
        "debate_outcome": {"total_challenges": 1, "accepted": 1, "refuted": 0},
    }
    ground_truth = {
        "primary_diagnosis": "Bacterial meningitis",
        "expected_in_ddx": ["Bacterial meningitis", "Viral meningitis"],
        "expected_safety_flag": "red",
    }
    scored = score_single_case(result, ground_truth)
    assert scored.top1_correct is True
    assert scored.top3_recall is True
    assert scored.safety_flag_correct is True


def test_top1_wrong():
    result = {
        "diagnosis": {
            "differential_diagnosis": [
                {"diagnosis": "Tension headache", "confidence": 70},
            ],
        },
        "critic_review": {"safety_flag": "green"},
        "debate_outcome": None,
    }
    ground_truth = {
        "primary_diagnosis": "Bacterial meningitis",
        "expected_in_ddx": ["Bacterial meningitis"],
        "expected_safety_flag": "red",
    }
    scored = score_single_case(result, ground_truth)
    assert scored.top1_correct is False
    assert scored.safety_flag_correct is False
