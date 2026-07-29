"""tools/test_jitter_analysis.py â€” unit tests for tjr.jitter_analysis.

Run: ``python tools/test_jitter_analysis.py``  (or ``pytest tools/test_jitter_analysis.py``)
Pure, deterministic, no network. Uses hand-checked values.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402  (optional; the __main__ block works without it)
from tjr import jitter_analysis as ja  # noqa: E402


# --------------------------------------------------------------------------- #
# Jitter / mdev / RTP / PDV
# --------------------------------------------------------------------------- #
def test_ping_mdev_constant_series():
    assert ja.ping_mdev([10, 10, 10, 10]) == 0.0


def test_ping_mdev_known_value():
    # pstdev([2,4,4,4,5,5,7,9]) == 2.0 (classic textbook sample -> population stdev 2.0)
    assert abs(ja.ping_mdev([2, 4, 4, 4, 5, 5, 7, 9]) - 2.0) < 1e-9


def test_consecutive_jitter_constant():
    assert ja.consecutive_jitter([10, 10, 10]) == 0.0


def test_consecutive_jitter_known():
    # |12-10|,|11-12|,|13-11|,|9-13|,|14-9|,|10-14|,|11-10| = 2,1,2,4,5,4,1 -> mean=19/7
    assert abs(ja.consecutive_jitter([10, 12, 11, 13, 9, 14, 10, 11]) - 19 / 7) < 1e-9


def test_rtp_jitter_requires_two_samples():
    assert ja.rtp_jitter([10]) is None


def test_rtp_jitter_index_clock_smoothing():
    # With index-clock, first delta D = |(12-10) - (1-0)| = 1; J0 = 1/16 = 0.0625
    j = ja.rtp_jitter([10, 12])
    assert abs(j - 0.0625) < 1e-9


def test_rtp_jitter_timestamp_clock_matches_length():
    with pytest.raises(ValueError):
        ja.rtp_jitter([10, 12, 11], timestamps_ms=[0, 20])


def test_pdv_range_form():
    assert ja.packet_delay_variation([5, 8, 3, 9]) == 6.0


def test_compute_jitter_report_fields():
    r = ja.compute_jitter([10, 12, 11, 13, 9, 14, 10, 11])
    assert r.n == 8
    assert r.min_ms == 9.0 and r.max_ms == 14.0
    assert r.pdv_ms == 5.0
    assert r.rtp_jitter_ms is not None and r.rtp_jitter_ms >= 0


def test_compute_jitter_empty_raises():
    with pytest.raises(ValueError):
        ja.compute_jitter([])


def test_compute_jitter_negative_raises():
    with pytest.raises(ValueError):
        ja.compute_jitter([10, -1])


def test_compute_jitter_nonfinite_raises():
    with pytest.raises(ValueError):
        ja.compute_jitter([10, float("nan")])


# --------------------------------------------------------------------------- #
# Bufferbloat grading
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("added,expected", [
    (0.0, "A"), (5.0, "A"), (5.1, "B"), (15.0, "B"), (15.1, "C"),
    (30.0, "C"), (30.1, "D"), (60.0, "D"), (60.1, "F"), (200.0, "F"),
])
def test_bufferbloat_grades(added, expected):
    g = ja.bufferbloat_grade(10 + added, 10)
    assert g.grade == expected
    assert g.added_latency_ms == round(added, 3)


def test_bufferbloat_negative_clamped():
    g = ja.bufferbloat_grade(8, 10)  # negative added -> clamp to 0
    assert g.grade == "A" and g.added_latency_ms == 0.0


def test_bufferbloat_nonfinite_raises():
    with pytest.raises(ValueError):
        ja.bufferbloat_grade(float("inf"), 10)


# --------------------------------------------------------------------------- #
# AQM recommendation
# --------------------------------------------------------------------------- #
def test_aqm_few_flows_picks_fq_codel():
    a = ja.aqm_recommend(upload_mbps=20, download_mbps=100, flow_count=1)
    assert a.algorithm == "FQ-CoDel"
    assert a.target_ms == 5.0 and a.interval_ms == 100.0
    assert a.shape_upload_mbps == round(20 * 0.95, 2)
    assert a.shape_download_mbps == round(100 * 0.95, 2)


def test_aqm_many_flows_picks_cake():
    a = ja.aqm_recommend(flow_count=5)
    assert a.algorithm == "CAKE"


def test_aqm_shared_link_picks_cake():
    a = ja.aqm_recommend(link_type="household")
    assert a.algorithm == "CAKE"


def test_aqm_no_bandwidth_no_shape():
    a = ja.aqm_recommend(flow_count=1)
    assert a.shape_upload_mbps is None and a.shape_download_mbps is None


def test_aqm_invalid_flow_count():
    with pytest.raises(ValueError):
        ja.aqm_recommend(flow_count=0)


# --------------------------------------------------------------------------- #
# QoS / DSCP marking
# --------------------------------------------------------------------------- #
def test_dscp_game_marking():
    q = ja.dscp_marking("game", "valorant")
    assert q.dscp == 34 and q.dscp_name == "AF41" and q.wmm_ac == "AC_VI"
    assert 7000 in q.ports


def test_dscp_voice_marking():
    q = ja.dscp_marking("voice")
    assert q.dscp == 46 and q.dscp_name == "EF" and q.wmm_ac == "AC_VO"


def test_dscp_unknown_class_raises():
    with pytest.raises(ValueError):
        ja.dscp_marking("nonexistent")


def test_dscp_general_game_has_no_ports():
    q = ja.dscp_marking("game", "unknown-game")
    assert q.ports == ()


# --------------------------------------------------------------------------- #
# Wi-Fi channel selection
# --------------------------------------------------------------------------- #
def test_wifi_picks_less_congested_channel():
    # Put a strong, busy AP on every preferred 5 GHz channel except 149, so 149
    # is the uniquely least-cost choice.
    scans = []
    for ch in ja.PREFERRED_5GHZ_CHANNELS:
        if ch == 149:
            scans.append(ja.APScan("clean", "clean", 149, "5", -85, 2))
        else:
            scans.append(ja.APScan(f"ap{ch}", f"ap{ch}", ch, "5", -45, 90))
    rec = ja.wifi_channel_recommend("5", scans, 80)
    assert rec.channel == 149
    assert rec.band == "5" and rec.channel_width_mhz == 80


def test_wifi_avoids_congested_channel():
    # A single strong AP on channel 36 must not be selected.
    scans = [ja.APScan("aa", "neighbour", 36, "5", -45, 90)]
    rec = ja.wifi_channel_recommend("5", scans, 80)
    assert rec.channel != 36
    assert rec.channel in ja.PREFERRED_5GHZ_CHANNELS


def test_wifi_24ghz_only_non_overlapping():
    rec = ja.wifi_channel_recommend("2.4", [], 20)
    assert rec.channel in (1, 6, 11)


def test_wifi_6ghz_channel():
    rec = ja.wifi_channel_recommend("6", [], 160)
    assert rec.channel in (37, 69, 101, 133, 165, 197)


def test_wifi_invalid_band():
    with pytest.raises(ValueError):
        ja.wifi_channel_recommend("3.5")


# --------------------------------------------------------------------------- #
# Jitter buffer sizing
# --------------------------------------------------------------------------- #
def test_jitter_buffer_at_least_one_tick():
    jb = ja.jitter_buffer_sizing(0.5, 64)
    assert jb.buffer_ticks >= 1
    assert jb.tick_ms == pytest.approx(1000 / 64)


def test_jitter_buffer_known_ticks():
    # tick = 1000/64 = 15.625 ms; jitter 40 ms -> 40/15.625 = 2.56 ticks * 1.5 = 3.84 -> ceil = 4
    jb = ja.jitter_buffer_sizing(40, 64, safety_factor=1.5)
    assert jb.buffer_ticks == 4


def test_jitter_buffer_invalid_inputs():
    with pytest.raises(ValueError):
        ja.jitter_buffer_sizing(10, 0)
    with pytest.raises(ValueError):
        ja.jitter_buffer_sizing(-1, 64)
    with pytest.raises(ValueError):
        ja.jitter_buffer_sizing(10, 64, safety_factor=0)


# --------------------------------------------------------------------------- #
# Scenarios + verdict
# --------------------------------------------------------------------------- #
def test_generate_scenarios_three_rows():
    sc = ja.generate_scenarios([10, 12, 11, 13, 9, 14, 10, 11], 10, 40)
    assert [s.name for s in sc] == ["Best", "Base", "Worst"]
    assert sc[0].jitter_ms == 9.0


def test_verdict_low_jitter():
    assert ja.verdict_from_scorecard(3, "A", isp_limited=False) == ja.Verdict.LOW_JITTER


def test_verdict_conditional_isp_limited():
    assert ja.verdict_from_scorecard(10, "B", isp_limited=True) == ja.Verdict.CONDITIONAL


def test_verdict_high_jitter():
    assert ja.verdict_from_scorecard(50, "F") == ja.Verdict.HIGH_JITTER
    assert ja.verdict_from_scorecard(80, "F") == ja.Verdict.HIGH_JITTER


def test_verdict_inconclusive_no_data():
    assert ja.verdict_from_scorecard(0, "A", data_available=False) == ja.Verdict.INCONCLUSIVE


# --------------------------------------------------------------------------- #
# Sample loader
# --------------------------------------------------------------------------- #
def test_load_rtt_samples_ping(tmp_path):
    p = tmp_path / "ping.txt"
    p.write_text("64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=12.3 ms\n"
                 "64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=11.8 ms\n"
                 "rtt min/av/max/mdev = 11.8/12.0/12.3/0.2 ms\n", encoding="utf-8")
    vals = ja.load_rtt_samples(str(p))
    assert 12.3 in vals and 11.8 in vals


def test_load_rtt_samples_empty_raises(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("nothing useful here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ja.load_rtt_samples(str(p))


# --------------------------------------------------------------------------- #
# __main__ runner (no pytest dependency required)
# --------------------------------------------------------------------------- #
def _expand_parametrize(fn):
    """Yield (args, kwargs) call sites for a test function, expanding
    pytest.mark.parametrize when present (so the standalone runner works
    without the pytest runner)."""
    import inspect
    sig = inspect.signature(fn)
    marks = getattr(fn, "pytestmark", []) or []
    param = None
    for m in marks:
        if getattr(m, "name", None) == "parametrize" or "parametrize" in str(getattr(m, "name", "")):
            param = m
            break
    if param is None:
        # No parametrize: single call.
        kwargs = {}
        if "tmp_path" in sig.parameters:
            import tempfile
            kwargs["tmp_path"] = Path(tempfile.mkdtemp())
        return [({}, kwargs)]
    # m.args = (argnames, values); m.name == 'parametrize'
    argnames = param.args[0]
    argnames = [a.strip() for a in argnames.split(",")] if isinstance(argnames, str) else list(argnames)
    values = param.args[1]
    calls = []
    for v in values:
        if len(argnames) == 1:
            calls.append(({argnames[0]: v}, {}))
        else:
            calls.append((dict(zip(argnames, v)), {}))
    return calls


def _run_all() -> int:
    import inspect
    failures = 0
    g = globals()
    for name, fn in list(g.items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            for args, extra in _expand_parametrize(fn):
                kwargs = dict(extra)
                if "tmp_path" in inspect.signature(fn).parameters and "tmp_path" not in kwargs:
                    import tempfile
                    kwargs["tmp_path"] = Path(tempfile.mkdtemp())
                fn(*[], **{**args, **kwargs})
            print(f"[OK] {name}")
        except Exception as ex:
            print(f"[FAIL] {name}: {ex}")
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)