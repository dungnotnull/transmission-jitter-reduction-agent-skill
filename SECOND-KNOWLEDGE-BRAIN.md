# SECOND-KNOWLEDGE-BRAIN.md â€” Skill 262: transmission-jitter-reduction

> **Living Knowledge Base** â€” updated by `tools/knowledge_updater.py` (the
> `tjr.knowledge_updater` crawl pipeline) on a weekly schedule. All entries are
> date-stamped; new entries are appended under Section 7. Evidence hierarchy:
> Systematic Review > Meta-Analysis > Guideline/Standard/RCT > Cohort > Expert
> Consensus > News.

---

## 1. Core Concepts & Frameworks

### 1.1 Network Jitter & Real-Time Transport Optimization â€” Foundational Methods

**Jitter causes.** Queuing delay in over-sized buffers (bufferbloat), route
changes, congestion, Wi-Fi retransmissions, and ISP last-mile variability.
Latency under load (LUL) is the diagnostic signal popularised by DSLReports and
the Bufferbloat project.

**Active Queue Management (AQM).** CoDel (RFC 8289), PIE (RFC 8033), FQ-CoDel
(RFC 8290), and CAKE (RFC 8325 / OpenWrt `sqm-scripts`) prevent bufferbloat
without sacrificing throughput by controlling queueing delay directly.

**QoS / shaping.** DSCP per-hop-behaviour markings (RFC 2474; EF RFC 3246;
AF RFC 2597) mapped to WMM access categories (IEEE 802.11e). Per-flow shaping
of the upload direction, ACK prioritisation, and game-traffic prioritisation
move the bottleneck into the router where AQM can act on it.

**Wi-Fi & jitter buffer.** WMM QoS, 5/6 GHz non-DFS channel selection, channel
width, roaming; jitter buffer & interpolation depth in netcode; packet pacing.

Knowledge categories covered:
- Jitter causes (queuing, bufferbloat, route change, Wi-Fi retransmission)
- AQM (CoDel, PIE, FQ-CoDel, CAKE)
- QoS/DSCP & traffic shaping (EF/AF/WMM)
- Jitter buffer & interpolation sizing
- Bufferbloat diagnosis (DSLreports, latency under load, CPE)
- Wired vs wireless & Wi-Fi QoS

### 1.2 Evidence Hierarchy (this domain)
- **Tier 1**: Systematic review / meta-analysis / official standard (IETF RFC,
  IEEE standard, ISO).
- **Tier 2**: Peer-reviewed academic paper / RCT.
- **Tier 3**: Industry report / professional association guideline / vendor
  reference implementation.
- **Tier 4**: News / blog / vendor marketing material.

---

## 2. Key Research Papers & Standards

| Title | Authors | Year | Venue | DOI/URL | Tier |
|------|---------|------|-------|---------|------|
| Controlling Queue Delay: CoDel | Nichols & Jacobson | 2012 | ACM Queue | 10.1145/2539071 | 1 |
| RFC 8289 â€” CoDel AQM | Nichols, Jacobson et al. | 2018 | IETF | https://www.rfc-editor.org/rfc/rfc8289 | 1 |
| RFC 8290 â€” FQ-CoDel scheduler | Hoeiland-Jorgensen et al. | 2018 | IETF | https://www.rfc-editor.org/rfc/rfc8290 | 1 |
| RFC 8033 â€” PIE AQM | Pan et al. | 2017 | IETF | https://www.rfc-editor.org/rfc/rfc8033 | 1 |
| RFC 9330 â€” L4S architecture | Briscoe, Schepper, Bagnulo | 2023 | IETF | https://www.rfc-editor.org/rfc/rfc9330 | 1 |
| The Flow Queue CoDel packet scheduler | Hoeiland-Jorgensen et al. | 2018 | ACM Queue | 10.1145/3123248 | 1 |
| Latency and Player Actions in Online Games | Claypool & Claypool | 2005 | Commun. ACM / NetGames | 10.1145/1103599.1103602 | 2 |
| The effects of latency on online competitive game performance | Stahl, D., et al. (Claypool lab) | 2005 | NetGames workshop | 10.1145/1103599.1103602 | 2 |
| BBR: Congestion-Based Congestion Control | Cardwell, Cheng, Gunn, Yeganeh, Jacobson | 2016 | ACM Queue | 10.1145/3022184.3022189 | 1 |
| A Queueing-theoretic model for AQM | Hollot, Misra, Towsley, Gong | 2001 | IEEE/ACM ToN | 10.1109/90.928853 | 2 |
| IEEE 802.11e â€” WMM QoS | IEEE | 2005 | IEEE Std | https://standards.ieee.org/ieee/802.11e/ | 1 |

Authoritative sources registered:
- IEEE/ACM Transactions on Networking
- Computer Networks (Elsevier)
- IEEE Communications Surveys & Tutorials
- Performance Evaluation (Elsevier)
- IEEE Transactions on Games
- Journal of Network and Computer Applications (Elsevier)
- IETF RFCs (8289 CoDel, 8290 FQ-CoDel, 8033 PIE, 8325 CAKE guidance, 8888 FQ-PIE, 9330 L4S)

---

## 3. State-of-the-Art Methods & Tools

**State of the art (2026):** CAKE and FQ-CoDel qdiscs on OpenWrt `sqm-scripts`;
BBRv2/v3 congestion control; L4S (RFC 9330) low-latency low-loss scalable
throughput with dual-queue PIE/FQ-CoDel; Wi-Fi 6/7 (802.11ax/be) WMM-AC and
multi-link operation; ML-based congestion/jitter prediction; edge anycast for
game relays; per-host/per-flow fair queuing on the home gateway.

**Crawl targets:** IEEE/ACM ToN, Comput. Netw., IEEE Commun. Surv. Tutor.,
Perform. Eval., IEEE Trans. Games, ArXiv (cs.NI, eess.SP, cs.GT), IETF RFC
stream, OpenWrt news, APNIC blog, Bufferbloat project.

---

## 4. Authoritative Data Sources

### 4.1 Domain authoritative sources
- Network measurement tools: Wireshark, `ping` (iputils), `mtr`, `tcpdump`,
  OONI Probe, `iperf3` (latency under load), DSLReports speedtest.
- QoS/AQM references: CoDel (RFC 8289), FQ-CoDel (RFC 8290), PIE (RFC 8033),
  CAKE (OpenWrt sqm-scripts).
- Bufferbloat references: bufferbloat.net, DSLReports bufferbloat grade.
- Game netcode/interpolation refs: per-game documentation (tick rate,
  interpolation buffer), Claypool & Claypool latency studies.
- Router firmware refs: OpenWrt, DD-WRT, Asuswrt-Merlin, pfSense/OPNsense.
- ISP/peering references: PeeringDB, RIPE Atlas, MTR path analysis.

### 4.2 Academic & research sources
- IEEE/ACM Transactions on Networking
- Computer Networks (Elsevier)
- IEEE Communications Surveys & Tutorials
- Performance Evaluation (Elsevier)
- IEEE Transactions on Games
- Journal of Network and Computer Applications (Elsevier)
- ArXiv categories: cs.NI, eess.SP, cs.GT

---

## 5. Analytical Frameworks

Knowledge categories covered (cross-reference the sub-skill workflows in
`skills/*.md`):

- **Jitter measurement**: RFC 3550 interarrival jitter; ping `mdev` (population
  stdev); RFC 3393 packet delay variation; consecutive-sample absolute jitter.
- **Bufferbloat diagnosis**: latency under load âˆ’ idle latency â†’ Aâ€“F grade.
- **AQM selection**: FQ-CoDel (lean, single/dual-flow gaming host) vs CAKE
  (many flows / shared household); shape to 95 % of measured link rate.
- **QoS/DSCP**: game â†’ AF41 (DSCP 34, WMM AC_VI); voice â†’ EF (46, AC_VO);
  background â†’ CS1 (8, AC_BK).
- **Wi-Fi**: non-DFS 5 GHz channel selection by weighted neighbour + utilisation
  cost; 6 GHz UNII-5/6 preferred.
- **Jitter buffer**: depth in game ticks = ceil(jitter / tick_ms Ă— safety) â‰¥ 1.

The fixed bookends (requirements â†’ evidence â†’ knowledge â†’ synthesis â†’ quality
gate) are mandatory; the core-analysis sub-skills implement the domain-specific
methods.

---

## 6. Self-Update Protocol

- **Crawl pipeline:** `tjr.knowledge_updater` (CLI: `tjr-knowledge`,
  legacy entry point `tools/knowledge_updater.py`).
- **Schedule:** weekly academic (Mondays 08:00) + daily news (07:00); documented
  in `CLAUDE.md`.
- **Dedup:** SHA-256 of DOI/URL (case/whitespace-insensitive).
- **Scoring:** composite 0â€“10 = recency(0.4) + keyword_relevance(0.4) +
  citation_count(0.2), with token-level partial-credit matching.
- **Crawl targets:** ArXiv categories [cs.NI, eess.SP, cs.GT]; Semantic Scholar
  keyword clusters; RSS feeds [RFC editor, OpenWrt news, Bufferbloat, APNIC
  blog, IFIP Networking].
- **Gap-fill:** `sub-knowledge-updater` flags missing values as crawl queries.
- **Append rule:** new entries appended under Section 7 with date stamp +
  relevance score; idempotent (hash dedup) so cron re-runs are safe.
- **Backoff:** exponential backoff + Retry-After handling on 429/5xx; one
  source failing never aborts the run.
- **Registry binding:** the `knowledge_updater` skill is a registered skill in
  `tjr.skills` (JSON-Schema contract, see `SKILL.md`); its Tier labels follow
  `references/evidence-hierarchy.md` and its citation sources are listed in
  `references/rfc-index.md`.
- **Baseline seeding:** `scripts/seed_knowledge.py` idempotently seeds the
  Tier 1 baseline (RFCs + key papers) offline so the brain always carries the
  authoritative references before any live crawl.

---

## 7. Knowledge Update Log

_(Appended automatically by the crawl pipeline. Baseline seeded with the
references in Section 2 â€” CoDel, FQ-CoDel, PIE, L4S, BBR, WMM, and the Claypool
latency studies.)_