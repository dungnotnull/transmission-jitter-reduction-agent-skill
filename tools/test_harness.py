"""tools/test_harness.py — integration tests for tjr.harness over fixtures.

Run: ``python tools/test_harness.py`` (or via pytest).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from tjr.harness import Harness, HarnessInput, Language, detect_language  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def test_detect_language_vietnamese():
    assert detect_language("Phân tích jitter cho game") == Language.VI


def test_detect_language_english():
    assert detect_language("analyze my network jitter please") == Language.EN


def test_detect_language_empty_defaults_english():
    assert detect_language("") == Language.EN


def test_harness_full_run_standard():
    data = json.loads((FIX / "harness_input.json").read_text(encoding="utf-8"))
    r = Harness().run(HarnessInput.from_dict(data))
    assert r.degradation_level == 0
    assert r.verdict in {"Low Jitter", "Conditional (ISP-limited)", "High Jitter", "Inconclusive"}
    assert r.gate_summary["all_pass"] is True
    assert r.jitter_report["n"] == 12
    assert "Wi-Fi" in r.report_markdown or "Wi" in r.report_markdown
    assert "## " in r.report_markdown


def test_harness_degraded_level4_inconclusive():
    data = json.loads((FIX / "harness_input_degraded.json").read_text(encoding="utf-8"))
    r = Harness().run(HarnessInput.from_dict(data))
    assert r.degradation_level == 4
    assert r.verdict == "Inconclusive"
    assert r.jitter_report == {}
    assert "LIMITATION" in r.report_markdown or "GIỚI HẠN" in r.report_markdown or "Limitations" in r.report_markdown


def test_harness_json_serialisable():
    data = json.loads((FIX / "harness_input.json").read_text(encoding="utf-8"))
    r = Harness().run(HarnessInput.from_dict(data))
    s = r.to_json()
    again = json.loads(s)
    assert again["verdict"] == r.verdict


def test_harness_verdict_high_jitter_when_bufferbloat_severe():
    data = json.loads((FIX / "harness_input.json").read_text(encoding="utf-8"))
    data["latency_under_load_ms"] = 200.0  # +186ms added -> grade F
    r = Harness().run(HarnessInput.from_dict(data))
    assert r.bufferbloat["grade"] == "F"


def test_harness_from_dict_ignores_unknown_fields():
    hi = HarnessInput.from_dict({"query": "x", "unknown_field": 1, "rtt_samples": [1, 2]})
    assert hi.query == "x" and hi.rtt_samples == [1, 2]


def _run_all() -> int:
    import traceback
    failures = 0
    for name, fn in list(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"[OK] {name}")
        except Exception:
            print(f"[FAIL] {name}")
            traceback.print_exc()
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)