# references/domain-guidelines.md -- domain knowledge & grounding rules

Grounding for the Network Jitter & Real-Time Transport Optimization domain.
These are the authoritative methods every sub-skill and `tjr.skills` handler
must anchor on. Each method traces to a cited RFC/standard (see
`rfc-index.md`).

## 1. Jitter measurement

- **RFC 3550 interarrival jitter** -- smoothed, gain 1/16. Used for RTP-style
  real-time transport. `tjr.jitter_analysis.rtp_jitter`.
- **RFC 3393 IP Packet Delay Variation** -- range form (max - min).
  `packet_delay_variation`.
- **ping `mdev`** -- population standard deviation of RTT (iputils `ping`).
  `ping_mdev`.
- **Consecutive-sample jitter** -- mean |rtt[i] - rtt[i-1]|; the instantaneous
  jitter most relevant to game rubber-banding. `consecutive_jitter`.

Rule: report all four when RTT samples are available; never report a single
jitter number in isolation.

## 2. Bufferbloat diagnosis

Added latency under load = `latency_under_load_ms - idle_latency_ms`
(clamped to >= 0). Grade on the DSLReports / RFC 8289 scale:

| Added (ms) | Grade | Meaning |
|------------|-------|---------|
| <= 5  | A | Excellent |
| <= 15 | B | Good |
| <= 30 | C | Moderate (AQM advised) |
| <= 60 | D | Poor (AQM required) |
| > 60  | F | Severe (AQM + shaping required) |

`tjr.jitter_analysis.bufferbloat_grade`.

## 3. AQM selection

- **FQ-CoDel** (RFC 8290) -- lean default for 1-3 flow gaming hosts; pair with
  an HTB/etree shaper at 95% of measured link rate.
- **CAKE** (RFC 8325 / OpenWrt `sqm-scripts`) -- many concurrent flows or shared
  households; integral shaper + Diffserv-aware tiering in one qdisc.

Shape to **95%** of the measured link rate so the bottleneck moves into the
router where AQM can act on it. `tjr.jitter_analysis.aqm_recommend`.

## 4. QoS / DSCP / WMM

| Class | DSCP | Name | WMM AC | RFC |
|-------|------|------|--------|-----|
| voice | 46 | EF | AC_VO | RFC 3246 |
| game (interactive UDP) | 34 | AF41 | AC_VI | RFC 2597 |
| game TCP (matchmaking) | 32 | CS4 | AC_VI | RFC 2474 |
| video | 36 | AF42 | AC_VI | RFC 2597 |
| signaling | 24 | CS3 | AC_VI | RFC 2474 |
| background | 8 | CS1 | AC_BK | RFC 2474 |
| best effort | 0 | BE | AC_BE | RFC 2474 |

`tjr.jitter_analysis.dscp_marking` (with per-game port tables).

## 5. Wi-Fi tuning

- Prefer **non-DFS** 5 GHz channels (UNII-1/3: 36,40,44,48,149,153,157,161) --
  no radar downtime. Score by weighted neighbour + utilisation cost.
- 2.4 GHz: only 1/6/11 are non-overlapping at 20 MHz.
- 6 GHz: prefer high UNII-5/6 channels (e.g. 37/69/101) -- typically empty.
- Enable WMM; disable legacy b/g rates on 5/6 GHz-only deployments.

`tjr.jitter_analysis.wifi_channel_recommend`.

## 6. Jitter buffer / interpolation

`buffer_ticks = max(1, ceil(jitter_ms / tick_ms * safety_factor))` where
`tick_ms = 1000 / tickrate_hz`. Default safety factor 1.5. The buffer must
cover worst-case jitter before rubber-banding. `jitter_buffer_sizing`.

## 7. Verdict decision table

Authoritative in `skills/sub-advisor.md` and `tjr.jitter_analysis.verdict_from_scorecard`:

| jitter_ms | bufferbloat | isp_limited | data | verdict |
|-----------|-------------|-------------|------|---------|
| any | any | any | False | Inconclusive |
| <= 5 | A/B | False | True | Low Jitter |
| <= 15 | A/B/C | True | True | Conditional |
| <= 15 | A/B/C | False | True | Low Jitter |
| <= 30 | C/D | any | True | Conditional |
| > 30 | D/F | any | True | High Jitter |
| > 60 | F | any | True | High Jitter |

## 8. General grounding rules

- Every claim must trace to >= 1 cited source or be flagged `[analyst judgment]` (U6).
- Disclosure / limitations MUST appear before the recommendation (U2).
- Use the declared template with all mandatory sections (U5).
- Output language MUST match the user's pre-flight preference (U4).
- Never fabricate numbers when data is missing -- emit "DATA UNAVAILABLE" and
  degrade (see the 5-level degradation table in `skills/main.md`).