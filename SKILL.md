# SKILL.md -- Skill Registry & Agent Architecture

> **Registry documentation for `transmission-jitter-reduction`.** This file is
> the authoritative reference for how skills, tools and hooks are registered,
> resolved, executed and validated by the production agent framework
> (`tjr.skills`, `tjr.tools`, `tjr.hooks`, `tjr.agents`).

The `transmission-jitter-reduction` skill is implemented as a **modular
skill-registry** rather than a fixed pipeline. The markdown contract in
`skills/main.md` describes the 6-step harness; the Python agent framework
(`tjr`) makes that contract a dynamically-composable, schema-validated,
hook-observable system. Each step is a *skill* with a JSON-Schema contract; a
*chain-of-thought router* plans which skills run and in what order; specialized
*sub-agents* execute them; *tools* provide the deterministic RFC-graded
capabilities; *hooks* synchronize state and emit observability events.

---

## 1. Architecture overview

```
User context (JSON)
        |
   OrchestratorAgent (tjr.agents)
        |-- pre-flight: language detection (tjr.harness.detect_language)
        |-- RouterAgent -> ChainOfThoughtRouter -> RoutingPlan + trace
        |-- for each skill in plan:
        |       SubAgent(skill) --emit hooks--> run skill handler
        |       validate inputs/outputs against JSON Schema
        |-- delegate authoritative core + gates to tjr.harness.Harness
        |-- emit gate / degradation / render / deliver events
        v
   AgentResult { verdict, plan, trace, skill_results, harness_result,
                 metrics, token_summary, report_markdown }
```

Layers (low -> high):

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Config | `tjr.config` | Type-safe, layered settings (defaults < TOML < env < overrides) |
| Logging | `tjr.logging_utils` | Structured JSON/text logging |
| Context | `tjr.context` | Context window + token budget |
| Tools | `tjr.tools` | Tool registry: schemas + handlers |
| Hooks | `tjr.hooks` | Lifecycle event bus + state sync |
| Skills | `tjr.skills` | Skill registry + chain-of-thought router |
| Agents | `tjr.agents` | Sub-agents + orchestrator |
| Core | `tjr.harness` / `tjr.jitter_analysis` / `tjr.quality_gates` | RFC-graded deterministic math + gates |

The agent layer **reuses** the deterministic core as the single source of
truth: the orchestrator delegates the authoritative, gate-enforced result to
`tjr.harness.Harness` and adds routing/tools/hooks/context on top. It never
re-implements the math.

---

## 2. Skill registry

A **skill** is declared as a `SkillSpec` (`tjr.skills.SkillSpec`):

| Field | Type | Purpose |
|-------|------|---------|
| `name` | str | Unique skill identity (registry key + routing signal) |
| `description` | str | Human + router-readable summary |
| `inputs_schema` | JSON Schema (subset) | Contract the skill accepts on input; validated **before** the handler runs |
| `outputs_schema` | JSON Schema (subset) | Contract the skill returns; validated **after** the handler runs |
| `tools` | list[str] | Registered tool names the skill is allowed to invoke |
| `quality_gates` | list[str] | Gate ids (U1-U6, G1-G4) the skill is responsible for |
| `handler` | callable(context, state) -> output | The deterministic skill body |
| `step` | int | 1-based position in the default 6-step plan |

### Registered skills (default registry)

| # | Skill | Description | Tools | Gates |
|---|-------|-------------|-------|-------|
| 1 | `gather_requirements` | Clarify object, scope, timeframe, inputs, audience, language | `detect_language` | U4 |
| 2 | `evidence_collector` | Fetch authoritative real-time + reference + academic evidence | - | U1, U3 |
| 3 | `core_analysis` | Jitter/PDV/bufferbloat + AQM + QoS/DSCP + Wi-Fi + buffer sizing | `compute_jitter`, `bufferbloat_grade`, `aqm_recommend`, `dscp_marking`, `wifi_channel_recommend`, `jitter_buffer_sizing`, `generate_scenarios` | G1, G2, G3, G4 |
| 4 | `knowledge_updater` | Query knowledge base; surface tier-labelled citations; flag gaps | - | U1 |
| 5 | `advisor` | Synthesize a risk-disclosed conclusion + scenarios + evidence chain | `verdict_from_scorecard` | U2, U6 |

### How skills are registered

```python
from tjr.skills import SkillSpec, SkillRegistry

registry = SkillRegistry()
registry.register(SkillSpec(
    name="my_skill",
    description="...",
    inputs_schema={"type": "object", "required": ["x"],
                   "properties": {"x": {"type": "number"}}},
    outputs_schema={"type": "object", "required": ["y"],
                    "properties": {"y": {"type": "number"}}},
    tools=["compute_jitter"],
    quality_gates=["G1"],
    handler=lambda ctx, state: {"y": ctx["x"] * 2},
    step=6,
))
```

`registry.register` raises `SkillError` on duplicate names. Use
`tjr.skills.default_registry()` to obtain a registry pre-populated with the
five built-in skills.

### How skills are resolved

Two resolution modes:

* **By name** -- `registry.get(name)` (exact; raises `SkillError` if unknown).
* **Fuzzy by query** -- `registry.resolve(query)` ranks skills by token
  overlap between the query and the skill name+description, breaking ties by
  the skill's `step` order. Used for ad-hoc single-skill routing.

### How skills are executed and validated

`registry.execute(name, context, state)`:

1. Looks up the spec (`SkillError` if unknown -> `SkillResult(ok=False)`).
2. Validates `context` against `inputs_schema` (subset of JSON Schema:
   type, required, properties, enum, const, minimum/maximum, min/maxItems,
   min/maxLength). On failure -> `SkillResult(ok=False)` with the path.
3. Calls `handler(context, state)`; normalises dataclass/enum/tuple results.
4. Validates the output against `outputs_schema`. On failure ->
   `SkillResult(ok=False)`.
5. Returns a `SkillResult{ok, output, error, skill, duration_ms}`.

The handler **never** raises to the caller: any exception is captured into a
`SkillResult(ok=False)` so the orchestrator can degrade gracefully.

---

## 3. Chain-of-thought router

`tjr.skills.ChainOfThoughtRouter` produces a `RoutingPlan{plan, trace,
degraded, short_circuit}` -- an ordered list of skill names plus a transparent
reasoning trace. It is **deterministic and side-effect free** (no LLM call) so
the plan is regression-testable.

Routing rules (in order):

1. Always run `gather_requirements`.
2. **Informational query** (`explain`/`what is`/`define`/...) with no
   measurements -> skip live-evidence field-work; run `knowledge_updater` +
   `advisor`; mark degraded with `short_circuit="Inconclusive"`.
3. Otherwise run `evidence_collector -> core_analysis -> knowledge_updater ->
   advisor`.
4. **No measurements, no evidence, no knowledge base** -> degraded Level 4,
   `short_circuit="Inconclusive"`.
5. **No measurements** (some context present) -> degraded; advisor short-circuits
   to `Inconclusive`.
6. **Missing evidence or knowledge base** (measurements present) -> degraded
   Level 1-2; advisor still concludes from measurements.

The trace is a list of human-readable reasoning steps; the orchestrator logs
and exposes it (`AgentResult.trace`, `tjr-agent --trace`) for full
chain-of-thought transparency.

---

## 4. Tool registry

A **tool** is a `Tool` (`tjr.tools.Tool`) with `name`, `description`,
`input_schema`, `output_schema`, `handler`. `ToolRegistry.execute(name, args)`
validates args against `input_schema`, runs the handler, validates the result
against `output_schema`, and returns a `ToolResult{ok, value, error, tool,
duration_ms}`. Schema failures raise a `ToolError` *before* the handler runs;
handler exceptions are captured, never raised to the caller.

### Registered tools (default registry)

| Tool | Description | Key output fields |
|------|-------------|-------------------|
| `detect_language` | Pre-flight en/vi language detection | `language` |
| `compute_jitter` | RFC 3550 jitter, mdev, PDV report | `n`, `mean_ms`, `consecutive_jitter_ms`, `rtp_jitter_ms`, `pdv_ms` |
| `bufferbloat_grade` | A-F grade for added latency under load | `grade`, `added_latency_ms` |
| `aqm_recommend` | FQ-CoDel / CAKE + 95% shaper config | `algorithm`, `target_ms`, `shape_upload_mbps` |
| `dscp_marking` | DSCP / WMM QoS marking (+ game ports) | `dscp`, `dscp_name`, `wmm_ac` |
| `wifi_channel_recommend` | Least-congested preferred Wi-Fi channel | `channel`, `band`, `channel_width_mhz` |
| `jitter_buffer_sizing` | Interpolation/jitter-buffer depth in ticks | `buffer_ticks`, `buffer_ms` |
| `generate_scenarios` | Best/Base/Worst jitter scenarios | `name`, `jitter_ms`, `latency_under_load_ms` |
| `verdict_from_scorecard` | Map scorecard -> one of 4 verdicts | `verdict` (string) |

Use `tjr.tools.default_registry()` to get a registry pre-populated with these.
External tools can be added with `registry.register(Tool(...))` (duplicate
names raise `ToolError`).

---

## 5. Hooks & lifecycle events

`tjr.hooks.EventBus` decouples cross-cutting concerns. The orchestrator emits
a closed set of `HookType` events:

| Event | When emitted |
|-------|--------------|
| `session.start` / `session.end` | Orchestrator run boundaries |
| `step.pre` / `step.post` | Around each sub-agent skill |
| `error` | On any skill/tool failure |
| `degradation` | When the router or harness marks a degraded level |
| `gate` | After each quality gate runs (with `passed` + `limitation`) |
| `render.pre` / `render.post` | Around report rendering |
| `deliver.pre` / `deliver.post` | Around final delivery |
| `tool.call` | On tool invocation |
| `skill.resolve` | When the router produces a plan |

Built-in hooks: `LoggingHook` (structured log per event), `MetricsHook`
(counters in `state["metrics"]`), `TokenAccountingHook` (spends step-output
tokens against the session budget), `StateSnapshotHook` (syncs selected step
outputs into shared `state` so later steps can read them without coupling).

**Fault isolation**: a handler that raises is logged and disabled for the rest
of the session, so a broken hook can never abort the run. Use
`tjr.hooks.default_hooks(estimator)` for the production setup.

---

## 6. Configuration

`tjr.config.load_settings()` builds a validated `Settings` from layers
(defaults < `config/default.toml` < `TJR_*` env vars < explicit overrides). All
values are coerced + range-validated; invalid values raise `ConfigError`
before the toolkit starts. Feature flags gate subsystems (`agent_framework`,
`chain_of_thought_router`, `structured_logging`, `token_accounting`,
`hooks_event_bus`, `tools_registry`, `knowledge_crawl`, `bilingual_output`,
`graceful_degradation`, `auto_fix_gates`). LLM parameters + token budget live
in `Settings.llm`. See [`config/README.md`](config/README.md).

---

## 7. Input / output JSON schemas

The skill and tool contracts are JSON Schema (draft 2020-12 subset). Canonical
schemas for the run context and result are published under
[`assets/schemas/`](assets/schemas/):

* [`harness_input.schema.json`](assets/schemas/harness_input.schema.json) --
  the run context accepted by `tjr-agent` / `tjr-harness`.
* [`harness_result.schema.json`](assets/schemas/harness_result.schema.json) --
  the authoritative deterministic result from `tjr.harness.Harness`.
* [`skill_spec.schema.json`](assets/schemas/skill_spec.schema.json) -- the
  `SkillSpec` declaration shape.
* [`tool.schema.json`](assets/schemas/tool.schema.json) -- the `Tool`
  declaration shape.

The `tjr-agent` CLI accepts any `harness_input.schema.json`-conforming object;
extra unknown keys are ignored (forward-compatible).

---

## 8. CLI surface

| Command | Layer | Purpose |
|---------|-------|---------|
| `tjr-harness <input.json>` | Core | Deterministic 6-step harness + gates |
| `tjr-agent <input.json>` | Agent | Full agent framework: router + sub-agents + hooks + trace |
| `tjr-jitter <capture>` | Core | Jitter/PDV/bufferbloat + recommendations |
| `tjr-knowledge [--dry-run]` | Core | Knowledge crawl pipeline |

`tjr-agent --json` emits the full `AgentResult`; `--trace` prints the
chain-of-thought plan reasoning.

---

## 9. Extending the registry

To add a new domain skill:

1. Implement a deterministic `handler(context, state) -> output`.
2. Declare `inputs_schema` / `outputs_schema` (JSON Schema subset).
3. Register the `SkillSpec` on the registry (or a fresh one).
4. (Optional) Register new `Tool`s the skill needs.
5. (Optional) Subscribe a `Hook` to relevant events for state sync/metrics.

Because every contract is schema-validated and the router is deterministic, new
skills are safe to add without touching the orchestrator or the deterministic
core -- the modular registry pattern keeps the system open to extension and
closed to modification.

---

## 10. Reference

* Implementation: `tjr/skills.py`, `tjr/tools.py`, `tjr/hooks.py`,
  `tjr/agents.py`, `tjr/config.py`, `tjr/context.py`, `tjr/logging_utils.py`.
* Markdown contract: `skills/main.md` and the five `skills/sub-*.md`.
* Deterministic core: `tjr/harness.py`, `tjr/jitter_analysis.py`,
  `tjr/quality_gates.py`.
* Modular directories: `config/` (settings), `references/` (prompt templates,
  domain guidelines, evidence hierarchy, RFC index), `assets/` (JSON schemas +
  diagrams), `scripts/` (setup, seeding, ingestion, crawl, validation).