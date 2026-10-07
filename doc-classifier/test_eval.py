"""run_eval.py 指标计算自检（不调 LLM）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "eval"))

from run_eval import LEVELS, report_levels, report_pii


def test_report_levels_counts():
    rows = [
        {"mode": "levels", "file": "a", "expected": "public", "predicted": "public", "error": ""},
        {"mode": "levels", "file": "b", "expected": "internal", "predicted": "public", "error": ""},
        {"mode": "levels", "file": "c", "expected": "confidential", "predicted": "restricted", "error": ""},
        {"mode": "levels", "file": "d", "expected": "restricted", "predicted": "", "error": "boom"},
    ]
    report = report_levels(rows)
    assert "accuracy: 1/3 = 33.3%" in report
    assert "under-classification (安全风险): 2/3 = 66.7%" in report
    assert "over-classification: 0/3 = 0.0%" in report


def test_report_pii_confusion():
    rows = [
        {"mode": "pii", "file": "p0", "expected": "pii", "predicted": "confidential", "error": ""},
        {"mode": "pii", "file": "p1", "expected": "pii", "predicted": "internal", "error": ""},
        {"mode": "pii", "file": "c0", "expected": "clean", "predicted": "confidential", "error": ""},
        {"mode": "pii", "file": "c1", "expected": "clean", "predicted": "public", "error": ""},
    ]
    report = report_pii(rows)
    assert "recall (PII 被判为机密): 1/2 = 50.0%" in report
    assert "false positive rate (干净文本被判机密): 1/2 = 50.0%" in report


def test_levels_order():
    assert LEVELS == ["public", "internal", "restricted", "confidential"]
