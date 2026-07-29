"""tools/test_quality_gates.py — unit tests for tjr.quality_gates.

Run: ``python tools/test_quality_gates.py`` (or via pytest).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from tjr.quality_gates import (  # noqa: E402
    EvidenceItem, GateEngine, GateResult, GateStatus, Scorecard,
)


def _good_scorecard() -> Scorecard:
    sc = Scorecard(language="en")
    sc.add_source(EvidenceItem("RFC 8290 FQ-CoDel", tier=1, url="rfc8290"))
    sc.add_source(EvidenceItem("DSLReports", tier=3, url="dslreports"))
    sc.add_source(EvidenceItem("OpenWrt wiki", tier=3, url="openwrt"))
    sc.claims = [{"text": "jitter 3ms", "source": "RTT meas"},
                 {"text": "bufferbloat A", "source": "RFC 8289"}]
    sc.disclosure_present = True
    sc.output_sections = list(sc.template_sections)
    sc.jitter_measured = True
    sc.bufferbloat_diagnosed = True
    sc.aqm_applied = True
    sc.qos_applied = True
    sc.link_optimized = True
    sc.verdict = "Low Jitter"
    return sc


def test_all_gates_pass_on_good_scorecard():
    results = GateEngine().run(_good_scorecard())
    assert all(r.status in (GateStatus.PASSED, GateStatus.AUTO_FIXED) for r in results)
    summary = GateEngine.summarize(results)
    assert summary["all_pass"] is True
    assert summary["failed"] == 0
    assert summary["total"] == 10


def test_u1_fails_then_autofixes():
    sc = _good_scorecard()
    sc.sources = []  # strip sources -> U1 fails
    results = GateEngine().run(sc)
    u1 = next(r for r in results if r.gate_id == "U1")
    # auto-fix appends a fallback source; with the academic tier-2 fallback U1 passes.
    assert u1.status in (GateStatus.AUTO_FIXED, GateStatus.PASSED)


def test_u2_autofix_adds_disclosure():
    sc = _good_scorecard()
    sc.disclosure_present = False
    sc.output_sections = [s for s in sc.output_sections if s != "Disclosure / Limitations"]
    GateEngine().run(sc)
    assert sc.disclosure_present is True
    assert "Disclosure / Limitations" in sc.output_sections


def test_u5_autofix_fills_template_sections():
    sc = _good_scorecard()
    sc.output_sections = ["Executive Summary"]
    GateEngine().run(sc)
    assert all(sec in sc.output_sections for sec in sc.template_sections)


def test_u6_autofix_flags_unsourced_claims():
    sc = _good_scorecard()
    sc.claims = [{"text": "claim with no source", "source": ""}]
    GateEngine().run(sc)
    assert sc.claims[0]["source"] == "[analyst judgment]"


def test_g1_g4_have_no_autofix_and_fail_on_missing():
    sc = _good_scorecard()
    sc.jitter_measured = False
    sc.aqm_applied = False
    results = GateEngine().run(sc)
    g1 = next(r for r in results if r.gate_id == "G1")
    g2 = next(r for r in results if r.gate_id == "G2")
    assert g1.status == GateStatus.FAILED and bool(g1.limitation)
    assert g2.status == GateStatus.FAILED and bool(g2.limitation)


def test_summary_includes_limitations():
    sc = _good_scorecard()
    sc.qos_applied = False
    results = GateEngine().run(sc)
    summary = GateEngine.summarize(results)
    assert summary["failed"] == 1
    assert any("G3" in lim for lim in summary["limitations"])


def test_gate_result_as_dict_serialisable():
    r = GateResult("U1", GateStatus.PASSED, detail="x", retries=0, limitation="")
    d = r.as_dict()
    assert d["status"] == "passed" and d["gate_id"] == "U1"


def _run_all() -> int:
    import inspect, traceback
    failures = 0
    g = globals()
    for name, fn in list(g.items()):
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