"""tjr.jitter_analysis — real domain computation for transmission jitter reduction.

All functions are pure, deterministic and unit-tested. No network access, no
LLM calls — this module is the evidence-graded numerical core that the skill
harness and the CLI tools build on.

The metrics implemented here follow recognised references:

* RFC 3550 (RTP) interarrival jitter.
* RFC 3393 (IP Packet Delay Variation).
* The bufferbloat grading popularised by DSLReports / the Bufferbloat project
  (Nichols & Jacobson, RFC 8289 "CoDel"; Hoeiland-Jorgensen et al., RFC 8290
  "FQ-CoDel"; RFC 8033 "PIE").
* DSCP / Per-Hop Behaviour markings per RFC 2474 / RFC 3246 (EF) / RFC 2597
  (AF) as used in WMM (IEEE 802.11e) and home-router QoS presets.

Where a recommendation is domain-dependent we return explicit, machine-readable
fields (with the evidence reference attached) instead of free text so the
advisor sub-skill and the harness can render them in any language.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from statistics import fmean, pstdev
from typing import Iterable, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Reference constants (cited; see SECOND-KNOWLEDGE-BRAIN.md Section 2).
# --------------------------------------------------------------------------- #
RTP_JITTER_GAIN = 1.0 / 16.0  # RFC 3550 smoothing factor for interarrival jitter.
FQ_CODEL_TARGET_MS = 5.0      # RFC 8290 default target.
FQ_CODEL_INTERVAL_MS = 100.0  # RFC 8290 default interval.
SHAPER_HEADROOM = 0.95        # Shape to 95% of measured link rate (avoid ISP tail-drop).
MIN_RTTS_FOR_STATS = 4        # Below this we cannot meaningfully compute mdev/PDV.

# Bufferbloat grading thresholds on the added latency under load (ms).
BUFFERBLOAT_THRESHOLDS: Tuple[Tuple[float, str], ...] = (
    (5.0,  "A"),   # <= 5 ms added  — Excellent
    (15.0, "B"),   # <= 15 ms added — Good
    (30.0, "C"),   # <= 30 ms added — Moderate
    (60.0, "D"),   # <= 60 ms added — Poor
    (math.inf, "F"),  # > 60 ms added — Severe bufferbloat
)

# DSCP / WMM access-category markings for common real-time traffic classes.
# (dscp decimal, dscp name, WMM access category, RFC reference)
_DSCP_TABLE = {
    "voice":  (46, "EF",  "AC_VO", "RFC 3246"),
    "game":   (34, "AF41", "AC_VI", "RFC 2597"),  # interactive game traffic
    "game_tcp": (32, "CS4", "AC_VI", "RFC 2474"), # game login/ matchmaking (TCP)
    "video":  (36, "AF42", "AC_VI", "RFC 2597"),
    "signaling": (24, "CS3", "AC_VI", "RFC 2474"),
    "background": (8, "CS1", "AC_BK", "RFC 2474"),
    "best_effort": (0, "BE",  "AC_BE", "RFC 2474"),
}

# 5 GHz non-DFS channels (UNII-1 + UNII-3) preferred for gaming because they
# do not require radar avoidance and are widely supported.
PREFERRED_5GHZ_CHANNELS: Tuple[int, ...] = (36, 40, 44, 48, 149, 153, 157, 161)
DFS_5GHZ_CHANNELS: Tuple[int, ...] = (52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144)


class Verdict(str, Enum):
    """Declared advisor conclusion categories (exactly one per report)."""

    LOW_JITTER = "Low Jitter"
    CONDITIONAL = "Conditional (ISP-limited)"
    HIGH_JITTER = "High Jitter"
    INCONCLUSIVE = "Inconclusive"


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class JitterReport:
    """Summary statistics over a sequence of RTT samples (milliseconds)."""

    n: int
    mean_ms: float
    mdev_ms: float           # population standard deviation (ping-style)
    consecutive_jitter_ms: float  # mean |rtt[i] - rtt[i-1]|
    min_ms: float
    max_ms: float
    pdv_ms: float            # max - min (RFC 3393 range form)
    rtp_jitter_ms: Optional[float]  # RFC 3550 smoothed jitter (None if <2 samples)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["rtp_jitter_ms"] = None if self.rtp_jitter_ms is None else round(self.rtp_jitter_ms, 3)
        return d


@dataclass(frozen=True)
class BufferbloatGrade:
    added_latency_ms: float
    grade: str                # A–F
    label: str
    reference: str = "RFC 8289 (CoDel) / DSLReports bufferbloat scale"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AQMRecommendation:
    algorithm: str            # "CAKE" | "FQ-CoDel"
    target_ms: float
    interval_ms: float
    shape_upload_mbps: Optional[float]
    shape_download_mbps: Optional[float]
    rationale: str
    reference: str = "RFC 8289 / RFC 8290"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class QoSMarking:
    traffic_class: str
    dscp: int
    dscp_name: str
    wmm_ac: str
    reference: str
    ports: Tuple[int, ...] = ()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["ports"] = list(self.ports)
        return d


@dataclass(frozen=True)
class WiFiChannelRecommendation:
    band: str                 # "2.4" | "5" | "6"
    channel: int
    channel_width_mhz: int
    reason: str
    reference: str = "IEEE 802.11ax/ay; UNII band plan"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class JitterBufferRecommendation:
    jitter_ms: float
    tickrate_hz: int
    tick_ms: float
    buffer_ticks: int
    buffer_ms: float
    safety_factor: float
    reference: str = "Game netcode interpolation practice (Claypool & Claypool)"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Scenario:
    name: str                 # "Best" | "Base" | "Worst"
    jitter_ms: float
    latency_under_load_ms: float
    notes: str

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Core measurement functions
# --------------------------------------------------------------------------- #
def _coerce_positive_samples(rtts: Iterable[float]) -> List[float]:
    out: List[float] = []
    for r in rtts:
        try:
            v = float(r)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"non-numeric RTT sample: {r!r}") from exc
        if not math.isfinite(v):
            raise ValueError(f"non-finite RTT sample: {r!r}")
        if v < 0:
            raise ValueError(f"negative RTT sample: {r!r}")
        out.append(v)
    return out


def ping_mdev(rtts: Sequence[float]) -> float:
    """Population standard deviation of RTT samples (the ``mdev`` ping reports).

    Uses population (not sample) standard deviation to match the behaviour of
    iputils ``ping`` which reports the standard deviation of the observed
    population.
    """
    samples = _coerce_positive_samples(rtts)
    if len(samples) < 2:
        return 0.0
    return float(pstdev(samples))


def consecutive_jitter(rtts: Sequence[float]) -> float:
    """Mean absolute difference between consecutive samples (instantaneous jitter)."""
    samples = _coerce_positive_samples(rtts)
    if len(samples) < 2:
        return 0.0
    diffs = [abs(samples[i] - samples[i - 1]) for i in range(1, len(samples))]
    return fmean(diffs)


def rtp_jitter(rtts: Sequence[float], timestamps_ms: Optional[Sequence[float]] = None) -> Optional[float]:
    """RFC 3550 interarrival jitter.

    Two calling conventions:

    1. ``rtp_jitter(rtts)`` — treats the RTT samples as a one-way-delay proxy
       and uses the sample *index* as the RTP timestamp clock (tick = 1 ms).
       This yields a smoothed, comparable jitter number from plain ping data.
    2. ``rtp_jitter(rtts, timestamps_ms)`` — uses the supplied RTP timestamp
       clock (in ms) for the canonical ``D = (Rj - Ri) - (Sj - Si)`` form.
    """
    samples = _coerce_positive_samples(rtts)
    if len(samples) < 2:
        return None
    if timestamps_ms is not None:
        ts = [float(t) for t in timestamps_ms]
        if len(ts) != len(samples):
            raise ValueError("timestamps_ms length must match rtts length")
    else:
        ts = [float(i) for i in range(len(samples))]
    j = 0.0
    for i in range(1, len(samples)):
        # Arrival difference approximated by RTT delta; timestamp difference by clock.
        arrival_delta = samples[i] - samples[i - 1]
        ts_delta = ts[i] - ts[i - 1]
        d = abs(arrival_delta - ts_delta)
        j += (d - j) * RTP_JITTER_GAIN
    return j


def packet_delay_variation(rtts: Sequence[float]) -> float:
    """Range-form PDV (max − min) per RFC 3393."""
    samples = _coerce_positive_samples(rtts)
    if not samples:
        return 0.0
    return max(samples) - min(samples)


def compute_jitter(rtts: Sequence[float], timestamps_ms: Optional[Sequence[float]] = None) -> JitterReport:
    """Full jitter report over an RTT sequence.

    Raises:
        ValueError: if the input is empty or contains non-numeric / negative /
            non-finite values.
    """
    samples = _coerce_positive_samples(rtts)
    if not samples:
        raise ValueError("compute_jitter requires at least one RTT sample")
    n = len(samples)
    mean_ms = fmean(samples)
    mdev = ping_mdev(samples)
    cj = consecutive_jitter(samples)
    rtp = rtp_jitter(samples, timestamps_ms)
    return JitterReport(
        n=n,
        mean_ms=round(mean_ms, 3),
        mdev_ms=round(mdev, 3),
        consecutive_jitter_ms=round(cj, 3),
        min_ms=round(min(samples), 3),
        max_ms=round(max(samples), 3),
        pdv_ms=round(packet_delay_variation(samples), 3),
        rtp_jitter_ms=None if rtp is None else round(rtp, 3),
    )


# --------------------------------------------------------------------------- #
# Bufferbloat grading
# --------------------------------------------------------------------------- #
def bufferbloat_grade(latency_under_load_ms: float, idle_latency_ms: float) -> BufferbloatGrade:
    """Grade the added latency (latency under load − idle latency).

    Negative added latency is clamped to 0 (clock noise / measurement artefact).
    """
    lul = float(latency_under_load_ms)
    idle = float(idle_latency_ms)
    if not math.isfinite(lul) or not math.isfinite(idle):
        raise ValueError("latency values must be finite")
    added = max(0.0, lul - idle)
    for threshold, grade in BUFFERBLOAT_THRESHOLDS:
        if added <= threshold:
            label = {
                "A": "Excellent (bufferbloat well controlled)",
                "B": "Good (minor buffering under load)",
                "C": "Moderate (visible bufferbloat; AQM advised)",
                "D": "Poor (significant bufferbloat; AQM required)",
                "F": "Severe (ISP / CPE queue unchecked; AQM + shaping required)",
            }[grade]
            return BufferbloatGrade(added_latency_ms=round(added, 3), grade=grade, label=label)
    # Unreachable; satisfies type checkers.
    raise RuntimeError("bufferbloat grade not determined")


# --------------------------------------------------------------------------- #
# AQM recommendation
# --------------------------------------------------------------------------- #
def aqm_recommend(
    upload_mbps: Optional[float] = None,
    download_mbps: Optional[float] = None,
    flow_count: int = 1,
    link_type: str = "generic",
) -> AQMRecommendation:
    """Recommend an AQM algorithm + shaper configuration.

    Selection logic:

    * ``CAKE`` is preferred on links that host many concurrent flows (>= 4) or
      where per-host / per-flow fairness matters (typical shared household),
      because CAKE combines FQ-CoDel-style flow scheduling with integral
      shaper + Diffserv awareness in one qdisc.
    * ``FQ-CoDel`` is the lean default for single/dual-flow gaming hosts: lower
      CPU, equally low latency under load, widely deployed on OpenWrt.

    The shaper is set to ``SHAPER_HEADROOM`` (95 %) of the *measured* link rate
    when bandwidth is supplied, so the bottleneck moves into the router where
    AQM can act on it (the canonical bufferbloat remediation).
    """
    if flow_count < 1:
        raise ValueError("flow_count must be >= 1")
    use_cake = flow_count >= 4 or link_type.lower() in {"shared", "household", "family"}
    algorithm = "CAKE" if use_cake else "FQ-CoDel"
    shape_up = round(upload_mbps * SHAPER_HEADROOM, 2) if upload_mbps else None
    shape_down = round(download_mbps * SHAPER_HEADROOM, 2) if download_mbps else None
    if use_cake:
        rationale = (
            "Many concurrent flows or a shared link: CAKE provides flow-isolation "
            "fairness, an integral shaper and Diffserv-aware tiering in one qdisc."
        )
    else:
        rationale = (
            "Few flows on a gaming host: FQ-CoDel keeps latency low under load with "
            "minimal CPU; pair with an explicit HTB/etree shaper at 95% of link rate."
        )
    return AQMRecommendation(
        algorithm=algorithm,
        target_ms=FQ_CODEL_TARGET_MS,
        interval_ms=FQ_CODEL_INTERVAL_MS,
        shape_upload_mbps=shape_up,
        shape_download_mbps=shape_down,
        rationale=rationale,
    )


# --------------------------------------------------------------------------- #
# QoS / DSCP marking
# --------------------------------------------------------------------------- #
# Common real-time game UDP ports (illustrative defaults; the advisor sub-skill
# confirms actual ports from the evidence bundle / game docs).
GAME_PORTS = {
    "valorant":    (7000, 7001, 7002),
    "csgo":        (27015, 27036),
    "cs2":         (27015, 27036),
    "dota2":       (27015, 27036),
    "lol":         (5000, 5001, 5002),
    "overwatch":   (3478, 3479, 5060, 5062, 12000),
    "apex":        (37000, 37001, 37002),
    "fortnite":    (7000, 7001),
    "pubg":        (7000, 7001, 7022),
    "general":     (),
}


def dscp_marking(traffic_class: str = "game", game: Optional[str] = None) -> QoSMarking:
    """Return the DSCP / WMM marking for a traffic class, with optional game ports."""
    key = traffic_class.strip().lower()
    if key not in _DSCP_TABLE:
        raise ValueError(
            f"unknown traffic_class {traffic_class!r}; expected one of {sorted(_DSCP_TABLE)}"
        )
    dscp, name, wmm, ref = _DSCP_TABLE[key]
    ports: Tuple[int, ...] = ()
    if game:
        ports = GAME_PORTS.get(game.strip().lower(), GAME_PORTS["general"])
    return QoSMarking(
        traffic_class=key,
        dscp=dscp,
        dscp_name=name,
        wmm_ac=wmm,
        reference=ref,
        ports=ports,
    )


# --------------------------------------------------------------------------- #
# Wi-Fi channel selection
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class APScan:
    """A single access-point scan row used for channel recommendation."""

    bssid: str
    ssid: str
    channel: int
    band: str          # "2.4" | "5" | "6"
    rssi_dbm: int
    utilisation_pct: float = 0.0  # busy time % where available


def wifi_channel_recommend(
    band: str = "5",
    scans: Sequence[APScan] = (),
    width_mhz: int = 80,
) -> WiFiChannelRecommendation:
    """Pick the least-congested preferred channel for the requested band.

    Strategy:

    * Prefer non-DFS UNII-1 / UNII-3 channels for 5 GHz (no radar downtime).
    * Score each candidate by (count of neighbours on/adjacent channel weighted
      by RSSI) + reported utilisation; choose the lowest score.
    * 2.4 GHz: only 1, 6, 11 are non-overlapping at 20 MHz — recommend the
      least busy of those.
    * 6 GHz: prefer a high UNII-5 channel (e.g. 37 / 69) which is typically empty.
    """
    band = str(band)
    width = int(width_mhz)
    if band == "5":
        candidates = list(PREFERRED_5GHZ_CHANNELS)
        if not candidates:
            candidates = list(DFS_5GHZ_CHANNELS)
    elif band == "2.4":
        candidates = [1, 6, 11]
    elif band == "6":
        candidates = [37, 69, 101, 133, 165, 197]
    else:
        raise ValueError(f"unsupported band {band!r}; expected '2.4', '5' or '6'")

    def neighbour_cost(ch: int) -> float:
        cost = 0.0
        for ap in scans:
            if str(ap.band) != band:
                continue
            # adjacent-channel overlap: weight decays with distance and RSSI.
            dist = abs(ap.channel - ch)
            if dist > 4:
                continue
            rssi_weight = max(0.0, (ap.rssi_dbm + 90.0) / 60.0)  # -90..-30 -> 0..1
            overlap = max(0.0, 1.0 - dist / 4.0)
            cost += overlap * rssi_weight * (1.0 + ap.utilisation_pct / 100.0)
        return cost

    best = min(candidates, key=neighbour_cost)
    reason = (
        f"Lowest weighted neighbour+utilisation cost on {band} GHz "
        f"(width {width} MHz). Preferred non-DFS channel."
        if band == "5" and best in PREFERRED_5GHZ_CHANNELS
        else f"Lowest weighted neighbour+utilisation cost on {band} GHz (width {width} MHz)."
    )
    return WiFiChannelRecommendation(
        band=band, channel=best, channel_width_mhz=width, reason=reason
    )


# --------------------------------------------------------------------------- #
# Jitter-buffer / interpolation sizing
# --------------------------------------------------------------------------- #
def jitter_buffer_sizing(jitter_ms: float, tickrate_hz: int, safety_factor: float = 1.5) -> JitterBufferRecommendation:
    """Recommend an interpolation/jitter-buffer depth in game ticks.

    The buffer must cover the worst-case jitter the client is willing to
    tolerate before showing rubber-banding. We round the jitter expressed in
    ticks up to the next whole tick and apply a safety factor; we never return
    fewer than 1 tick.
    """
    if tickrate_hz <= 0:
        raise ValueError("tickrate_hz must be > 0")
    if jitter_ms < 0:
        raise ValueError("jitter_ms must be >= 0")
    if safety_factor <= 0:
        raise ValueError("safety_factor must be > 0")
    tick_ms = 1000.0 / float(tickrate_hz)
    raw_ticks = (jitter_ms / tick_ms) * safety_factor
    buffer_ticks = max(1, int(math.ceil(raw_ticks)))
    return JitterBufferRecommendation(
        jitter_ms=round(jitter_ms, 3),
        tickrate_hz=int(tickrate_hz),
        tick_ms=round(tick_ms, 3),
        buffer_ticks=buffer_ticks,
        buffer_ms=round(buffer_ticks * tick_ms, 3),
        safety_factor=safety_factor,
    )


# --------------------------------------------------------------------------- #
# Scenarios + verdict
# --------------------------------------------------------------------------- #
def generate_scenarios(
    rtt_samples: Sequence[float],
    idle_latency_ms: float,
    latency_under_load_ms: float,
) -> List[Scenario]:
    """Derive Best / Base / Worst jitter scenarios from measurements.

    * Best  — minimum observed RTT (network floor).
    * Base  — mean RTT (steady state).
    * Worst — mean + 2·mdev (~95th percentile under a near-normal assumption).
    """
    report = compute_jitter(rtt_samples)
    best = Scenario(name="Best", jitter_ms=report.min_ms, latency_under_load_ms=idle_latency_ms,
                    notes="Network floor (minimum observed RTT).")
    base = Scenario(name="Base", jitter_ms=report.mean_ms,
                    latency_under_load_ms=round((idle_latency_ms + latency_under_load_ms) / 2.0, 3),
                    notes="Steady-state mean RTT.")
    worst_jitter = report.mean_ms + 2.0 * report.mdev_ms
    worst = Scenario(name="Worst", jitter_ms=round(worst_jitter, 3),
                     latency_under_load_ms=latency_under_load_ms,
                     notes="Mean + 2·mdev (~p95); assumes near-normal delay distribution.")
    return [best, base, worst]


def verdict_from_scorecard(
    jitter_ms: float,
    bufferbloat_grade_letter: str,
    isp_limited: bool = False,
    data_available: bool = True,
) -> Verdict:
    """Map a measurement scorecard to one of the declared verdicts.

    Decision table (authoritative in skills/sub-advisor.md):

    | jitter_ms | bufferbloat | isp_limited | data_available | verdict             |
    |-----------|-------------|-------------|----------------|---------------------|
    | any       | any         | any         | False          | Inconclusive        |
    | <= 5      | A or B      | False       | True           | Low Jitter          |
    | <= 15     | A/B/C       | True        | True           | Conditional         |
    | <= 15     | A/B/C       | False       | True           | Low Jitter          |
    | <= 30     | C/D         | any         | True           | Conditional         |
    | > 30      | D/F         | any         | True           | High Jitter         |
    | > 60      | F           | any         | True           | High Jitter         |
    """
    if not data_available:
        return Verdict.INCONCLUSIVE
    grade = bufferbloat_grade_letter.upper()
    if jitter_ms <= 5.0 and grade in {"A", "B"} and not isp_limited:
        return Verdict.LOW_JITTER
    if jitter_ms <= 15.0 and grade in {"A", "B", "C"}:
        return Verdict.CONDITIONAL if isp_limited else Verdict.LOW_JITTER
    if jitter_ms <= 30.0 and grade in {"C", "D"}:
        return Verdict.CONDITIONAL
    if jitter_ms > 60.0 and grade == "F":
        return Verdict.HIGH_JITTER
    if jitter_ms > 30.0 or grade in {"D", "F"}:
        return Verdict.HIGH_JITTER
    return Verdict.CONDITIONAL


# --------------------------------------------------------------------------- #
# Sample loaders (ping / mtr / wireshark text exports)
# --------------------------------------------------------------------------- #
_PING_RTT_RE = re.compile(r"(?:time=|rtt\s*=\s*)([\d.]+)\s*ms", re.IGNORECASE)
_MTR_RTT_RE = re.compile(r"^\s*[\d.]+\s*[\w.\-:]+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\d+\.\d+)\s*$")
_WS_RTT_RE = re.compile(r"\b(\d+\.\d+)\s*ms\b")


def load_rtt_samples(path: str, fmt: str = "auto") -> List[float]:
    """Parse an RTT-sample text export into a list of float milliseconds.

    Supported ``fmt`` values: ``"auto"`` (default), ``"ping"``, ``"mtr"``,
    ``"wireshark"``. ``auto`` tries ping first, then mtr, then a generic
    ``N.NN ms`` scan.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if fmt == "auto":
        if "time=" in text or "rtt min" in text or "rtt/av" in text:
            fmt = "ping"
        elif "MTR" in text or "HOST" in text and "Loss%" in text:
            fmt = "mtr"
        else:
            fmt = "wireshark"
    if fmt == "ping":
        values = [float(m.group(1)) for m in _PING_RTT_RE.finditer(text)]
    elif fmt == "mtr":
        values = [float(m.group(1)) for m in _MTR_RTT_RE.finditer(text)]
    else:
        values = [float(m.group(1)) for m in _WS_RTT_RE.finditer(text)]
    if not values:
        raise ValueError(f"no RTT samples parsed from {path!r} (fmt={fmt})")
    return values


__all__ = [
    "Verdict", "JitterReport", "BufferbloatGrade", "AQMRecommendation",
    "QoSMarking", "WiFiChannelRecommendation", "JitterBufferRecommendation",
    "Scenario", "APScan", "GAME_PORTS",
    "compute_jitter", "ping_mdev", "consecutive_jitter", "rtp_jitter",
    "packet_delay_variation", "bufferbloat_grade", "aqm_recommend",
    "dscp_marking", "wifi_channel_recommend", "jitter_buffer_sizing",
    "generate_scenarios", "verdict_from_scorecard", "load_rtt_samples",
]