from harness.metrics import EvaluationMetrics, ScoredResult
from harness.reporter import generate_report


def test_report_contains_table():
    metrics = {
        "baseline": EvaluationMetrics(
            top1_accuracy=0.6, top3_recall=0.75,
            safety_flag_recall=0.7, total_cases=7,
        ),
        "full": EvaluationMetrics(
            top1_accuracy=0.8, top3_recall=0.9,
            safety_flag_recall=0.95, total_cases=7,
        ),
    }
    report = generate_report(metrics)
    assert "baseline" in report
    assert "full" in report
    assert "Top-1" in report
    assert "Safety" in report


def test_report_markdown_format():
    metrics = {
        "test": EvaluationMetrics(top1_accuracy=0.5, total_cases=1),
    }
    report = generate_report(metrics)
    assert report.startswith("# MediChain Evaluation Report")
