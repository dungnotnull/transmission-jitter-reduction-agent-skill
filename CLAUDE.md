# CLAUDE.md â€” Skill 262: transmission-jitter-reduction

## Skill Identity
- **Skill Name:** `transmission-jitter-reduction`
- **Tagline:** Transmission Jitter Reduction Solutions for Gamers â€” Network
  Jitter & Real-Time Transport Optimization analysis & decision-support harness.
- **Current Phase:** Phase 6 â€” Production Hardening & Open-Source Readiness (complete)
- **Version:** 1.2.0
- **Folder:** `D:\972026\262-transmission-jitter-reduction\`

---

## Problem This Skill Solves

This skill provides a structured, evidence-backed analytical workflow for
**Network Jitter & Real-Time Transport Optimization**. It gathers authoritative
real-time and reference data, applies recognized domain methods (RFC-graded:
RFC 3550 jitter, RFC 3393 PDV, RFC 8289 CoDel, RFC 8290 FQ-CoDel, RFC 8033 PIE,
RFC 2474/3246/2597 DSCP/WMM), cross-references academic research, and delivers
actionable outputs that are fully evidenced, risk/limitation-disclosed, and
traceable to authoritative sources â€” continuously self-improving through an
automated knowledge crawl pipeline. A runnable Python core (`tjr`) makes the
decision logic regression-testable without an LLM in the loop.

---

## Harness Flow Summary

```
/transmission-jitter-reduction invoked
â”‚
â”œâ”€ Pre-Flight: language detection (en / vi)
â”œâ”€ Step 1: sub-gather-requirements   â†’ Clarify object, scope, timeframe, inputs, audience, language.
â”œâ”€ Step 2: sub-evidence-collector    â†’ Fetch authoritative real-time + reference + academic data.
â”œâ”€ Step 3: sub-core-analysis         â†’ Jitter/PDV/bufferbloat + AQM + QoS/DSCP + Wi-Fi + buffer sizing.
â”œâ”€ Step 4: sub-knowledge-updater     â†’ Query SECOND-KNOWLEDGE-BRAIN.md; tier-labelled citations; flag gaps.
â”œâ”€ Step 5: sub-advisor               â†’ Risk-disclosed conclusion + scenarios + evidence chain + actions.
â””â”€ Step 6: main (quality gate)       â†’ verify U1â€“U6 + G1â€“G4; auto-fix + 2-retry budget; deliver.
```

The exact same contract is implemented in runnable form by `tjr.harness.Harness`.

---

## Sub-Skills

| File | Purpose |
|------|---------|
| `skills/sub-gather-requirements.md` | Clarify the object of analysis, constraints, timeframe, available inputs, target audience, and language before any data fetching. |
| `skills/sub-evidence-collector.md` | Fetch authoritative real-time and reference data: current status/parameters, authoritative documents/standards, recent developments. |
| `skills/sub-core-analysis.md` | Analyze and reduce transmission jitter for gamers via AQM, QoS, traffic shaping, and Wi-Fi tuning, using authoritative measurement methods. |
| `skills/sub-knowledge-updater.md` | Query SECOND-KNOWLEDGE-BRAIN.md for authoritative academic and professional evidence; surface citations with tier labels and flag gaps. |
| `skills/sub-advisor.md` | Synthesize all prior analysis into a risk-disclosed conclusion with a full evidence chain and recommended actions. |

---

## Tools Required

- **WebSearch** / **WebFetch** â€” live domain news, reports, standards updates
- **Read / Write** â€” read SECOND-KNOWLEDGE-BRAIN.md; append knowledge entries
- **Bash** â€” run `tools/knowledge_updater.py` (or `tjr-knowledge`) for periodic crawl
- **Skill** â€” invoke sub-skills sequentially through the harness

---

## Python Toolkit (`tjr`)

The `tjr` package is the runnable, production-grade core behind the markdown
skill. It can be used standalone (no LLM) for measurement analysis and CI
regression of the decision logic.

| Module | Purpose |
|--------|---------|
| `tjr/jitter_analysis.py` | RFC 3550 jitter, RFC 3393 PDV, ping mdev, bufferbloat grading, AQM/CAKE/FQ-CoDel recommendation, DSCP/WMM QoS map, Wi-Fi channel selection, jitter-buffer sizing, scenarios + verdict. |
| `tjr/quality_gates.py` | Programmatic U1â€“U6 + G1â€“G4 gate engine with auto-fix + 2-retry budget. |
| `tjr/harness.py` | Reference orchestrator of the 6-step protocol: language detection, degradation levels, gate enforcement, bilingual Markdown + JSON output. |
| `tjr/knowledge_updater.py` | ArXiv / Semantic Scholar / RSS crawl + SHA-256 dedup + composite scoring + backoff. |
| `tjr/cli.py` / `jitter_cli.py` / `knowledge_cli.py` | Console entry points: `tjr-harness`, `tjr-jitter`, `tjr-knowledge`. |
| `tjr/config.py` | Type-safe layered configuration (defaults < TOML < env < overrides) + feature flags. |
| `tjr/logging_utils.py` | Structured JSON/text logging. |
| `tjr/context.py` | Context window + token-budget management. |
| `tjr/tools.py` | Tool registry (JSON-Schema tools + handlers). |
| `tjr/hooks.py` | Lifecycle hooks + event bus. |
| `tjr/skills.py` | Skill registry + chain-of-thought router. |
| `tjr/agents.py` / `agent_cli.py` | Sub-agents + orchestrator; `tjr-agent` CLI. |
| `SKILL.md` | Skill registry documentation. |
| `config/` `references/` `assets/` `scripts/` | Modular directories: config, RAG grounding, schemas/diagrams, automation. |
| `tools/knowledge_updater.py` | Backward-compatible shim â†’ `tjr.knowledge_updater`. |
| `tools/validate_project.py` | 8-File Contract validator. |
| `tools/run_test_scenarios.py` | Structural + runtime scenario validator. |

---

## Knowledge Sources

### Domain Authoritative Sources
- Network measurement tools (Wireshark, ping, MTR, OONI, iperf3, DSLReports)
- QoS/AQM references (CoDel RFC 8289, FQ-CoDel RFC 8290, PIE RFC 8033, CAKE)
- Bufferbloat references (bufferbloat.net, DSLReports bufferbloat grade)
- Game netcode/interpolation refs (per-game docs, Claypool & Claypool studies)
- Router firmware refs (OpenWrt, Asuswrt-Merlin, pfSense/OPNsense)
- ISP/peering references (PeeringDB, RIPE Atlas)

### Academic & Research Sources
- IEEE/ACM Transactions on Networking
- Computer Networks (Elsevier)
- IEEE Communications Surveys & Tutorials
- Performance Evaluation (Elsevier)
- IEEE Transactions on Games
- Journal of Network and Computer Applications (Elsevier)
- ArXiv: cs.NI, eess.SP, cs.GT

### Academic Crawl Targets
- ArXiv categories [cs.NI, eess.SP, cs.GT]
- Semantic Scholar keyword clusters
- RSS feeds: RFC editor, OpenWrt news, Bufferbloat project, APNIC blog, IFIP Networking

---

## Supporting Python Tools

| File | Purpose |
|------|---------|
| `tjr/knowledge_updater.py` | Crawl pipeline: fetches latest papers + news â†’ scores â†’ appends to SECOND-KNOWLEDGE-BRAIN.md |
| `tjr/harness.py` | Runnable 6-step harness orchestrator |
| `tjr/jitter_analysis.py` | Domain math core (RFC-graded) |
| `tjr/quality_gates.py` | Gate engine |
| `tools/validate_project.py` | 8-File Contract validator |
| `tools/run_test_scenarios.py` | Structural + runtime scenario validator |

---

## Automated Knowledge Update Schedule

```cron
# Weekly academic update (Mondays 08:00)
0 8 * * 1 tjr-knowledge >> logs/knowledge_update.log 2>&1

# Daily news update (07:00)
0 7 * * * tjr-knowledge --news-only >> logs/knowledge_news.log 2>&1
```

Manual:
```bash
tjr-knowledge --dry-run
tjr-knowledge --news-only --json
tjr-knowledge --keywords "FQ-CoDel" "CAKE" "L4S"
# legacy entry point still works:
python tools/knowledge_updater.py --dry-run
```

---

## Active Development Tasks

- [x] Phase 0: Architecture & source map
- [x] Phase 1: Core sub-skills (production-grade)
- [x] Phase 2: Main harness + 10 quality gates + degradation
- [x] Phase 3: Knowledge pipeline + tests + cron
- [x] Phase 4: Testing & validation (all validators pass)
- [x] Phase 5: Integration & polish (PRODUCTION READY v1.0.0)
- [x] Phase 6: Production hardening & open-source readiness
      (`tjr` package, CLIs, RFC-graded brain, full unit + integration
      coverage, MIT license, pyproject.toml) -- v1.1.0
- [x] Phase 7: agent framework & modular skill registry -- config, logging,
      context, tools, hooks, skills, agents, `tjr-agent` CLI, SKILL.md
      registry, `config/` `references/` `assets/` `scripts/` modular
      directories, `tools/test_agent_framework.py` -- v1.2.0

---

## References

- `PROJECT-detail.md` â€” full technical specification
- `PROJECT-DEVELOPMENT-PHASE-TRACKING.md` â€” build roadmap
- `SECOND-KNOWLEDGE-BRAIN.md` â€” self-improving knowledge base
- `D:\972026\SKILL-STANDARD.md` â€” library-wide standard
- Reference impl: `D:\vn-finance-analysis-hd-skill`