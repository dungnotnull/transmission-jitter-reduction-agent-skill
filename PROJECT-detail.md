# PROJECT-detail.md â€” Skill 262: transmission-jitter-reduction

## Executive Summary

`transmission-jitter-reduction` is a professional-grade harness for Claude Code
targeting the **Network Jitter & Real-Time Transport Optimization** domain. It
transforms Claude into a domain expert that delivers structured, evidence-backed
outputs by combining real-time data aggregation, recognized domain methods
(RFC-graded), and academic research into a single orchestrated workflow ending
in a risk/limitation-disclosed recommendation. A runnable Python core (`tjr`)
makes the decision logic regression-testable without an LLM in the loop.

---

## Problem Statement

Practitioners in this domain face three structural gaps:
1. **Data fragmentation**: authoritative data scattered across sources.
2. **Methodology gaps**: most advice lacks systematic, evidence-graded methods.
3. **No self-improvement**: static tools don't learn from new research.

This skill addresses all three via real-time aggregation, professional
frameworks (RFC-graded), and a continuously-updated knowledge crawl pipeline.

---

## Target Users & Use Cases

| User | Trigger Example | Skill Response |
|------|----------------|----------------|
| Practitioner | "Analyze Network Jitter & Real-Time Transport Optimization case X" | Full evidenced report |
| Researcher | "What methods apply to Y?" | Method-grounded guidance with citations |
| Decision-maker | "Assess risk/feasibility of Z" | Risk-disclosed assessment with scenarios |
| Learner | "Explain method M in this domain" | Educational framing with evidence |

---

## Harness Architecture

```
USER INPUT
    â”‚
    â–¼
[main.md â€” transmission-jitter-reduction]   (contract)
    â”‚
    â”œâ”€â–º Pre-Flight: language detection (en / vi)
    â”œâ”€â–º sub-gather-requirements.md  â†’ Clarify object, scope, timeframe, inputs, audience, language.
    â”œâ”€â–º sub-evidence-collector.md   â†’ Fetch authoritative real-time + reference + academic data.
    â”œâ”€â–º sub-core-analysis.md        â†’ Jitter/PDV/bufferbloat + AQM + QoS/DSCP + Wi-Fi + buffer sizing.
    â”œâ”€â–º sub-knowledge-updater.md    â†’ Query SECOND-KNOWLEDGE-BRAIN.md; tier-labelled citations; gaps.
    â”œâ”€â–º sub-advisor.md              â†’ Risk-disclosed conclusion + scenarios + evidence chain + actions.

    â””â”€â–º [QUALITY GATE â€” main.md]   (also enforced by tjr.quality_gates)
            âœ“ U1 â‰¥3 sources, â‰¥1 academic      âœ“ U2 disclosure before recommendation
            âœ“ U3 evidence hierarchy (Tier 1-4) âœ“ U4 language matches user preference
            âœ“ U5 declared template (all sections) âœ“ U6 every claim traceable
            âœ“ G1 jitter measured & bufferbloat diagnosed
            âœ“ G2 AQM applied (FQ-CoDel/CAKE)   âœ“ G3 QoS/DSCP & shaping
            âœ“ G4 Wi-Fi (WMM/channel) or wired optimized
```

The same contract is executed headlessly by `tjr.harness.Harness`, which runs
the 6 steps over a `HarnessInput` (measurements + evidence + knowledge
citations) and emits a `HarnessResult` (verdict, recommendations, gate summary,
bilingual Markdown + JSON).

---

## Full Sub-Skill Catalog

### 1. `sub-gather-requirements.md`
- **Purpose:** Clarify the object of analysis, constraints, timeframe, available inputs, target audience, and language before any data fetching.
- **Role:** intake specialist for a Network Jitter & Real-Time Transport Optimization engagement.
- **Inputs:** Raw user message + any provided materials/inputs.
- **Outputs:** Structured requirements: {object, scope, timeframe, available_inputs, target_audience, language, analysis_type}.
- **Tools:** Conversation only (no external tools).
- **Quality Gate:** At least one object of analysis confirmed before proceeding.

### 2. `sub-evidence-collector.md`
- **Purpose:** Fetch authoritative real-time and reference data: current status/parameters, authoritative documents/standards, and recent developments.
- **Role:** Network Jitter & Real-Time Transport Optimization data librarian.
- **Inputs:** Requirements object from Step 1.
- **Outputs:** Evidence bundle: {current_data, authoritative_docs, recent_news, reference_benchmarks} with source + date per item.
- **Tools:** WebSearch, WebFetch (domain + academic sources); Read (SECOND-KNOWLEDGE-BRAIN.md for cached benchmarks).
- **Quality Gate:** At least current data + 1 authoritative document retrieved, or a limitation flag if unavailable.

### 3. `sub-core-analysis.md`
- **Purpose:** Analyze and reduce transmission jitter for gamers via AQM, QoS, traffic shaping, and Wi-Fi tuning, using authoritative measurement methods.
- **Role:** network jitter & real-time transport optimizer.
- **Inputs:** Network/ISP, hardware, game, language.
- **Outputs:** Measurement + AQM + QoS/shaping + buffer tuning + Wi-Fi/wired + scenarios.
- **Tools:** Read (SECOND-KNOWLEDGE-BRAIN.md); WebFetch (OpenWrt, AQM docs, bufferbloat.org); `tjr.jitter_analysis` for the math.
- **Quality Gate:** Jitter measured & bufferbloat diagnosed; AQM & QoS applied; Wi-Fi/wired optimized (G1â€“G4).

### 4. `sub-knowledge-updater.md`
- **Purpose:** Query SECOND-KNOWLEDGE-BRAIN.md for authoritative academic and professional evidence; surface citations with tier labels and flag gaps for the crawl pipeline.
- **Role:** research librarian for Network Jitter & Real-Time Transport Optimization.
- **Inputs:** Topic keywords from the current analysis.
- **Outputs:** 3-5 knowledge-base citations with Tier labels + flagged gaps.
- **Tools:** Read (SECOND-KNOWLEDGE-BRAIN.md); WebSearch (gap-fill, max 2 queries); `tjr.knowledge_updater` for the crawl.
- **Quality Gate:** At least 1 academic/authoritative source surfaced; coverage rating provided.

### 5. `sub-advisor.md`
- **Purpose:** Synthesize all prior analysis into a risk-disclosed conclusion with a full evidence chain and recommended actions.
- **Role:** senior Network Jitter & Real-Time Transport Optimization advisor.
- **Inputs:** Core analysis scorecard + evidence bundle + knowledge-base evidence.
- **Outputs:** Conclusion (one of 4 declared categories) + scenarios + key risks + evidence chain + remediation + mandatory disclosure.
- **Tools:** Reasoning / synthesis; Skill('sub-knowledge-updater') optional; `tjr.jitter_analysis.verdict_from_scorecard`.
- **Quality Gate:** Conclusion is exactly one of: Low Jitter / Conditional (ISP-limited) / High Jitter / Inconclusive; disclosure appears before the conclusion.

---

## Runnable Python Toolkit (`tjr`)

The `tjr` package is the production-grade, runnable core behind the markdown
skill. No network access is required for the analysis path.

| Module | Responsibility |
|--------|----------------|
| `tjr/jitter_analysis.py` | RFC 3550 interarrival jitter; RFC 3393 PDV; ping `mdev`; consecutive-sample jitter; bufferbloat Aâ€“F grading; AQM (FQ-CoDel vs CAKE) + 95% shaping; DSCP/WMM QoS map with per-game ports; 5/6 GHz non-DFS Wi-Fi channel selection; jitter-buffer tick sizing; Best/Base/Worst scenarios; 4-verdict decision table; ping/mtr/wireshark sample loaders. |
| `tjr/quality_gates.py` | `Scorecard` + `GateEngine` implementing U1â€“U6 + G1â€“G4 with auto-fix callables and a 2-retry budget per gate; explicit limitation emission on persistent failure. |
| `tjr/harness.py` | `Harness` orchestrator: pre-flight language detection (en/vi), 6-step execution, 5-level graceful degradation, gate review, bilingual Markdown + JSON rendering. |
| `tjr/knowledge_updater.py` | `KnowledgeUpdater`: ArXiv (cs.NI/eess.SP/cs.GT) + Semantic Scholar + RSS crawl, SHA-256 dedup, composite scoring (recency + token-level keyword relevance + citations), exponential backoff + Retry-After, `--dry-run` / `--news-only` / `--json`. |
| `tjr/cli.py`, `tjr/jitter_cli.py`, `tjr/knowledge_cli.py` | Console entry points `tjr-harness`, `tjr-jitter`, `tjr-knowledge`. |
| `tjr/config.py` | Type-safe layered configuration + feature flags (defaults < `config/default.toml` < `TJR_*` env < overrides). |
| `tjr/logging_utils.py` | Structured (JSON/text) logging with file fallback. |
| `tjr/context.py` | Token estimator + token budget + context window with safe truncation. |
| `tjr/tools.py` | Tool registry: JSON-Schema input/output validation + 9 built-in deterministic tools. |
| `tjr/hooks.py` | Lifecycle event bus (14 event types) + logging/metrics/token/state-snapshot hooks. |
| `tjr/skills.py` | Skill registry (JSON-Schema contracts) + chain-of-thought router (deterministic plan + trace). |
| `tjr/agents.py`, `tjr/agent_cli.py` | Sub-agents + orchestrator delegating the authoritative result to `tjr.harness.Harness`; `tjr-agent` CLI. |

**CLIs:**
```bash
tjr-harness tests/fixtures/harness_input.json --json
tjr-agent tests/fixtures/harness_input.json --json --trace   # full agent framework + chain-of-thought
tjr-jitter tests/fixtures/ping_capture.txt --idle 14 --lul 78 --upload 20 --download 100 --game valorant
tjr-knowledge --dry-run --json
```

---

## Agent Framework & Modular Skill Registry (v1.2.0)

The harness contract is now realised by a **flexible agent & skill
architecture** in `tjr` (see [`SKILL.md`](SKILL.md)):

* **Skill registry** (`tjr.skills.SkillRegistry`) -- each of the 6 steps is a
  registered skill with a JSON-Schema input/output contract, validated before
  and after execution.
* **Chain-of-thought router** (`tjr.skills.ChainOfThoughtRouter`) -- produces a
  deterministic, transparent plan + reasoning trace; special-cases informational
  queries and degraded (no-data) inputs.
* **Specialized sub-agents** (`tjr.agents.SubAgent`) -- one per skill, bound to
  the shared tool registry + hooks.
* **Tools** (`tjr.tools.ToolRegistry`) -- 9 deterministic, JSON-Schema-validated
  tools wrapping the RFC-graded core (compute_jitter, bufferbloat_grade,
  aqm_recommend, dscp_marking, wifi_channel_recommend, jitter_buffer_sizing,
  generate_scenarios, verdict_from_scorecard, detect_language).
* **Hooks** (`tjr.hooks.EventBus`) -- 14 lifecycle events with fault-isolated
  handlers (logging, metrics, token accounting, state snapshots).
* **Config / context / logging** (`tjr.config`, `tjr.context`,
  `tjr.logging_utils`) -- type-safe layered config, token budgeting +
  context-window truncation, structured observability.
* **Modular directories** -- `config/` (settings), `references/` (RAG
  grounding: prompt templates, domain guidelines, evidence hierarchy, RFC
  index), `assets/` (JSON schemas + Mermaid diagrams), `scripts/` (setup,
  seeding, ingestion, crawl, validation).

The agent layer **reuses** the deterministic core as the single source of
truth: `tjr.agents.OrchestratorAgent` delegates the authoritative,
gate-enforced result to `tjr.harness.Harness` and adds routing/tools/hooks/
context on top -- it never re-implements the RFC-graded math or the gate
engine.
## Skill File Format Specification

```markdown
---
name: {skill-name}
description: {one-line summary}
---
## Role & Persona
## Workflow (Harness Flow)
## Sub-skills Available   (main.md only)
## Tools
## Output Format
## Quality Gates
```

---

## E2E Execution Flow

```
1. User invokes /transmission-jitter-reduction [query]
2. main.md â†’ sub-gather-requirements â†’ structured requirements
3. sub-evidence-collector â†’ data bundle
4. core analysis sub-skills â†’ scorecard / signal set
5. sub-knowledge-updater â†’ academic evidence entries
6. sub-advisor/synthesizer â†’ final draft
7. main.md Quality Gate â†’ verify (U1â€“U6 + G1â€“G4), auto-fix, deliver
```

**Error handling:** primary sources fail â†’ fallback chain â†’ knowledge base â†’
explicit limitation flag; never silently proceed with stale data. The 5-level
degradation table is enforced both in `skills/main.md` and `tjr.harness`.

---

## SECOND-KNOWLEDGE-BRAIN Integration

- **Sources crawled:** ArXiv (cs.NI, eess.SP, cs.GT) + Semantic Scholar + domain RSS (RFC editor, OpenWrt, Bufferbloat, APNIC, IFIP Networking).
- **Crawl config:** `KNOWLEDGE_CONFIG` in `tjr/knowledge_updater.py`.
- **Dedup:** SHA-256 of DOI/URL (case/whitespace-insensitive).
- **Scoring:** recency(0.4) + keyword_relevance(0.4, token-level partial credit) + citation_count(0.2) â†’ 0â€“10.

---

## Quality Gates Definition

Universal gates U1â€“U6 (see library SKILL-STANDARD.md) plus the domain gates
defined in `skills/main.md` and enforced in `tjr/quality_gates.py`: G1, G2, G3, G4.

---

## Test Scenarios

See `tests/test-scenarios.md` for 5 concrete scenario tests, and
`tests/fixtures/` for the runnable fixture inputs exercised by
`tools/run_test_scenarios.py` and `tools/test_harness.py`.

---

## Key Design Decisions

1. Domain sub-skills kept separate (distinct methods/data).
2. Authoritative domain sources as primary; global fallback secondary.
3. Disclosure enforced at the quality-gate level, not optional.
4. SECOND-KNOWLEDGE-BRAIN as living memory updated by crawl pipeline.
5. Graceful degradation to knowledge base with explicit limitation flags.
6. **Runnable Python core (`tjr`)** mirrors the markdown contract so the
   decision logic is unit + integration tested without an LLM, and is reusable
   as a CLI / library in production.
7. **RFC-graded methods**: every domain metric traces to a cited RFC/standard.

---

## Idea (Vietnamese)

> Táº¡o skill tá»± Ä‘á»™ng hĂ³a quy trĂ¬nh phĂ¢n tĂ­ch vĂ  Ä‘á» xuáº¥t giáº£i phĂ¡p giáº£m thiá»ƒu Ä‘á»™
> trá»… Ä‘Æ°á»ng truyá»n (Jitter) khi chÆ¡i game qua máº¡ng khĂ´ng dĂ¢y, viá»‡c Ä‘Ă¡nh giĂ¡ vĂ 
> Ä‘Æ°a Ä‘á» xuáº¥t pháº£i dá»±a trĂªn cĂ¡c phÆ°Æ¡ng phĂ¡p Ä‘Ă¡nh giĂ¡ uy tĂ­n trĂªn tháº¿ giá»›i (RFC,
> IEEE) vĂ  Ä‘Æ°a ra cĂ¡c Ä‘á» xuáº¥t, giáº£i phĂ¡p cáº£i tiáº¿n, khĂ´ng ngá»«ng Ä‘i crawl data tá»«
> cĂ¡c tiĂªu chuáº©n cĂ´ng nghá»‡ máº¡ng khĂ´ng dĂ¢y má»›i nháº¥t hoáº·c document uy tĂ­n liĂªn quan
> Ä‘á»ƒ cáº­p nháº­t kiáº¿n thá»©c cho skill ngĂ y cĂ ng tá»‘t hÆ¡n, xu hÆ°á»›ng hÆ¡n.