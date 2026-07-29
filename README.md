# transmission-jitter-reduction

**Transmission Jitter Reduction Solutions for Gamers** â€” an evidence-backed
analysis harness for **Network Jitter & Real-Time Transport Optimization**.

[![Claude Skill](https://img.shields.io/badge/Claude-Skill-blue)](https://claude.ai/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Production Stable](https://img.shields.io/badge/status-production%20stable-brightgreen)](#status)

A professional-grade Claude Code skill **and** a standalone Python toolkit
(`tjr`) that gathers authoritative real-time data, applies recognized domain
methods (AQM, QoS/DSCP, traffic shaping, Wi-Fi tuning, jitter-buffer sizing),
integrates academic research, and delivers evidence-backed, risk-disclosed
outputs. The knowledge base self-improves via a weekly ArXiv / Semantic Scholar
/ RSS crawl pipeline.

---

## Features
- Real-time data aggregation from authoritative Network Jitter & Real-Time
  Transport Optimization sources.
- Systematic domain analysis methods (RFC 3550 jitter, RFC 3393 PDV, RFC 8289
  bufferbloat grading, RFC 8290/8325 AQM, RFC 2474/3246/2597 DSCP/WMM).
- Academic research integration with an auto-updating knowledge base.
- Risk/limitation-disclosed outputs with Best/Base/Worst scenario coverage.
- **10 quality gates** (U1â€“U6 universal + G1â€“G4 domain) with auto-fix + retry.
- 5-level graceful degradation with explicit LIMITATION banners.
- Bilingual output (English / Tiáº¿ng Viá»‡t) via pre-flight language detection.
- Self-improving knowledge pipeline (weekly academic + daily news crawl).
- Runnable Python reference orchestrator (`tjr.harness`) + CLIs, fully unit
  and integration tested.

---

## Status

**Production Ready v1.2.0** â€” all 6 (+1 production-hardening) phases complete,
100 % of tasks done. See
[`PROJECT-DEVELOPMENT-PHASE-TRACKING.md`](PROJECT-DEVELOPMENT-PHASE-TRACKING.md).

---

## Repository layout

```
.
â”œâ”€â”€ skills/                      # Claude skill markdown (the harness contract)
â”‚   â”œâ”€â”€ main.md                  # 6-step harness + 10 quality gates + degradation
â”‚   â”œâ”€â”€ sub-gather-requirements.md
â”‚   â”œâ”€â”€ sub-evidence-collector.md
â”‚   â”œâ”€â”€ sub-core-analysis.md
â”‚   â”œâ”€â”€ sub-knowledge-updater.md
â”‚   â””â”€â”€ sub-advisor.md
â”œâ”€â”€ tjr/                         # Production Python toolkit (the runnable core)
â”‚   â”œâ”€â”€ jitter_analysis.py       # RFC 3550 jitter, PDV, bufferbloat, AQM/QoS/Wi-Fi/buffer
â”‚   â”œâ”€â”€ quality_gates.py         # U1â€“U6 + G1â€“G4 gate engine with auto-fix
â”‚   â”œâ”€â”€ harness.py               # 6-step reference orchestrator + bilingual rendering
â”‚   â”œâ”€â”€ knowledge_updater.py     # ArXiv/Semantic Scholar/RSS crawl + SHA-256 dedup
â”‚   â”œâ”€â”€ cli.py                   # tjr-harness
â”‚   â”œâ”€â”€ jitter_cli.py            # tjr-jitter
â”‚   â””â”€â”€ knowledge_cli.py         # tjr-knowledge
â”œâ”€â”€ tjr/ (agent framework)       # config, logging, context, tools, hooks, skills, agents
â”‚   â”œâ”€â”€ config.py  logging_utils.py  context.py
â”‚   â”œâ”€â”€ tools.py   hooks.py   skills.py   agents.py   agent_cli.py
â”œâ”€â”€ tools/                       # Backward-compat shims + validators + tests
â”‚   â”œâ”€â”€ knowledge_updater.py     # shim -> tjr.knowledge_updater
â”‚   â”œâ”€â”€ validate_project.py      # 8-File Contract + agent-framework validator
â”‚   â”œâ”€â”€ run_test_scenarios.py    # structural + runtime scenario validator
â”‚   â”œâ”€â”€ test_jitter_analysis.py  test_quality_gates.py  test_harness.py
â”‚   â””â”€â”€ test_knowledge_updater.py  test_agent_framework.py
â”œâ”€â”€ config/                     # type-safe config (default.toml + README)
â”œâ”€â”€ references/                 # RAG/agent grounding (prompt-templates, domain-guidelines,
â”‚                              # evidence-hierarchy, rfc-index)
â”œâ”€â”€ assets/                     # JSON schemas + Mermaid diagrams
â”œâ”€â”€ scripts/                    # setup, seed_knowledge, ingest_measurements, run_crawl, validate
â”œâ”€â”€ SKILL.md                    # skill registry documentation
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ test-scenarios.md
â”‚   â”œâ”€â”€ TEST_RESULTS.md
â”‚   â””â”€â”€ fixtures/                # ping capture + harness input JSON
â”œâ”€â”€ SECOND-KNOWLEDGE-BRAIN.md    # living knowledge base (auto-updated)
â”œâ”€â”€ CLAUDE.md  PROJECT-detail.md  PROJECT-DEVELOPMENT-PHASE-TRACKING.md
â”œâ”€â”€ pyproject.toml  requirements.txt  progression.json  LICENSE
```

---

## Installation

```bash
pip install -r requirements.txt
# or, for an editable install exposing the console scripts:
pip install -e .
```

Install the skill markdown into `~/.claude/skills/` or use it via the project
`CLAUDE.md`.

---

## Usage

### As a Claude Code skill
```
/transmission-jitter-reduction [your query]
```

### As a standalone CLI (the `tjr` toolkit)

**1. Run the full 6-step harness over a measurement file:**
```bash
tjr-harness tests/fixtures/harness_input.json
tjr-harness tests/fixtures/harness_input.json --json        # full JSON result
tjr-harness tests/fixtures/harness_input.json -o report.md  # write Markdown
```

**1b. Run the full agent framework (router + sub-agents + hooks + trace):**
```bash
tjr-agent tests/fixtures/harness_input.json --json --trace   # full AgentResult + chain-of-thought
tjr-agent tests/fixtures/harness_input.json -o report.md      # write Markdown
```

**2. Compute jitter + recommendations from a ping/mtr/wireshark capture:**
```bash
tjr-jitter tests/fixtures/ping_capture.txt --idle 14 --lul 78 --upload 20 --download 100 --game valorant
tjr-jitter tests/fixtures/ping_capture.txt --json
```

**3. Run the knowledge crawl pipeline:**
```bash
tjr-knowledge --dry-run            # preview without writing
tjr-knowledge --news-only --json   # daily news, JSON summary
tjr-knowledge --keywords "FQ-CoDel" "CAKE" "L4S"
```

### Python API
```python
from tjr import Harness, HarnessInput, compute_jitter, bufferbloat_grade

report = compute_jitter([14.2, 13.9, 15.1, 22.8, 14.1, 13.8])
print(report.consecutive_jitter_ms, report.mdev_ms, report.rtp_jitter_ms)

bb = bufferbloat_grade(latency_under_load_ms=78, idle_latency_ms=14)
print(bb.grade, bb.added_latency_ms)

result = Harness().run(HarnessInput.from_dict({...}))
print(result.verdict, result.gate_summary["checklist"])

from tjr.agents import OrchestratorAgent
agent_result = OrchestratorAgent().run({...})
print(agent_result.verdict, agent_result.plan, agent_result.trace, agent_result.metrics)
```

---

## Architecture

Harness flow: **requirements â†’ evidence â†’ core analysis â†’ knowledge â†’
synthesis â†’ quality gate**, with pre-flight language detection and graceful
degradation. See [`PROJECT-detail.md`](PROJECT-detail.md) for the full
architecture diagram and [`tjr/harness.py`](tjr/harness.py) for the runnable
reference implementation.

### Quality gates
Universal gates U1â€“U6 plus domain gates (defined in `skills/main.md` and
enforced in `tjr/quality_gates.py`):

| Gate | Check |
|------|-------|
| U1 | â‰¥3 sources cited, â‰¥1 academic/authoritative |
| U2 | Disclosure/limitations present before recommendation |
| U3 | Evidence hierarchy (Tier 1â€“4) stated per source |
| U4 | Output language matches user preference |
| U5 | Output uses the declared template (all sections) |
| U6 | Every claim traceable to a source or flagged |
| G1 | Jitter measured & bufferbloat diagnosed |
| G2 | AQM applied (FQ-CoDel / CAKE) |
| G3 | QoS/DSCP & shaping for game traffic |
| G4 | Wi-Fi (WMM/channel) or wired optimized |

### Verdict categories
`Low Jitter` Â· `Conditional (ISP-limited)` Â· `High Jitter` Â· `Inconclusive`

---

## Data Sources
- Network measurement tools (Wireshark, ping, MTR, OONI, iperf3, DSLReports)
- QoS/AQM references (CoDel RFC 8289, FQ-CoDel RFC 8290, PIE RFC 8033, CAKE)
- Bufferbloat references (bufferbloat.net, DSLReports grade)
- Game netcode/interpolation refs (per-game docs, Claypool & Claypool studies)
- Router firmware refs (OpenWrt, Asuswrt-Merlin, pfSense/OPNsense)
- ISP/peering references (PeeringDB, RIPE Atlas)
- Academic: IEEE/ACM ToN, Computer Networks, IEEE Commun. Surv. Tutor.,
  Performance Evaluation, IEEE Trans. Games, JNCA; ArXiv cs.NI/eess.SP/cs.GT

---

## Testing

```bash
# Unit + integration tests (standalone runners, no pytest required):
python tools/test_jitter_analysis.py
python tools/test_quality_gates.py
python tools/test_harness.py
python tools/test_knowledge_updater.py

# Or via pytest:
pytest

# Structural + runtime scenario validator + 8-File Contract validator:
python tools/run_test_scenarios.py
python tools/validate_project.py
```

All tests are deterministic and require **no network access** (the crawl
pipeline is only exercised against a temp brain file in the unit tests).

---

## Knowledge Base

`SECOND-KNOWLEDGE-BRAIN.md` is auto-updated weekly via
`tools/knowledge_updater.py` (`tjr-knowledge`). New entries are SHA-256
de-duplicated and scored 0â€“10 (recency + keyword relevance + citations).

Cron schedule (documented in `CLAUDE.md`):
```cron
# Weekly academic update (Mondays 08:00)
0 8 * * 1 tjr-knowledge >> logs/knowledge_update.log 2>&1
# Daily news update (07:00)
0 7 * * * tjr-knowledge --news-only >> logs/knowledge_news.log 2>&1
```

---

## Roadmap
- [x] Phase 0: Architecture & source map
- [x] Phase 1: Core sub-skills (5)
- [x] Phase 2: Main harness + 10 quality gates + degradation
- [x] Phase 3: Knowledge pipeline + tests + cron
- [x] Phase 4: Testing & validation
- [x] Phase 5: Integration & polish
- [x] Phase 6: Production hardening & open-source readiness (`tjr` package,
      CLIs, RFC-graded brain, full unit + integration coverage)
- [x] Phase 7: Agent framework & modular skill registry (config, logging,
      context, tools, hooks, skills, agents, SKILL.md, references/assets/
      scripts/config directories, full tests)

---

## License
MIT â€” see [LICENSE](LICENSE).

## Citation
```bibtex
@software{transmission-jitter-reduction,
  title  = {transmission-jitter-reduction: Transmission Jitter Reduction
            Solutions for Gamers},
  year   = {2026},
  version = {1.2.0},
  url    = {https://github.com/transmission-jitter-reduction/transmission-jitter-reduction}
}
```

## Why This Skill
Network Jitter & Real-Time Transport Optimization practitioners face
fragmented data, inconsistent methodology, and tools that do not self-improve.
This skill unifies authoritative real-time data, recognized domain methods
(RFC-graded), and a continuously-updated academic knowledge base into one
evidence-backed, risk-disclosed workflow â€” and ships a runnable Python core
so the decision logic can be regression-tested without an LLM in the loop.