# test-scenarios.md â€” Skill 262: transmission-jitter-reduction

Five concrete end-to-end scenarios. Each lists inputs, expected steps, and
applicable quality gates. The scenarios exercise all universal gates U1â€“U6 and
the domain gates G1, G2, G3, G4, plus all four verdict categories.

Scenarios **S1** and **S5** are runnable end-to-end via `tjr.harness` against
the fixtures in `tests/fixtures/` (see `tools/run_test_scenarios.py` and
`tools/test_harness.py`). The remaining scenarios are exercised programmatically
through `tjr.jitter_analysis.verdict_from_scorecard` and the gate engine.

---

## Scenario 1: Standard analysis (object in scope) â€” runnable
- **Fixture:** `tests/fixtures/harness_input.json` (12 RTT samples, Valorant,
  household 5 GHz Wi-Fi, 20/100 Mbps, 3 RFC citations, 2 industry sources).
- **Expected:** sub-gather-requirements â†’ sub-evidence-collector â†’
  sub-core-analysis â†’ sub-knowledge-updater â†’ sub-advisor â†’ quality gate.
- **Runtime assertions:** degradation Level 0; verdict in the declared set;
  all 10 gates pass; 12 RTT samples processed; gate checklist (G1â€“G4) present
  in the Markdown report; result JSON-serialisable.
- **Gates:** U1â€“U6 + G1, G2, G3, G4.
- **Verdict target:** High Jitter (latency under load = 78 ms â‡’ bufferbloat F).

## Scenario 2: Minimal-input analysis (defaults)
- **Input:** terse request with minimal data.
- **Expected:** defaults applied with explicit assumption statement; never
  fabricate missing values. The harness fills defaults (tickrate 64, traffic
  class `game`, Wi-Fi band 5) and states assumptions.
- **Gates:** U1â€“U6 + G1â€“G4 (where data permits).

## Scenario 3: Comparison scenario
- **Input:** compare two objects/cases within the domain (e.g. FQ-CoDel vs CAKE
  on the same link, or wired vs Wi-Fi).
- **Expected:** side-by-side scorecard + evidence-based winner;
  `tjr.jitter_analysis.aqm_recommend` applied with `flow_count` to drive the
  FQ-CoDel-vs-CAKE choice.
- **Gates:** U3 (evidence hierarchy), U6, G1, G2.

## Scenario 4: Risk / feasibility or conflict scenario
- **Input:** assess risk of a borderline case (jitter â‰¤ 15 ms but
  ISP-limited), or resolve conflicting signals/actions.
- **Expected:** multi-scenario (Best/Base/Worst) risk output with stated
  precedence where conflicts exist. `verdict_from_scorecard(jitter=10, grade='B',
  isp_limited=True)` â‡’ `Conditional (ISP-limited)`.
- **Gates:** U2 (disclosure), G1, G2, G3, G4.

## Scenario 5: Degraded-mode scenario â€” runnable
- **Fixture:** `tests/fixtures/harness_input_degraded.json` (no RTT samples, no
  latency, no evidence, no citations).
- **Expected:** fallback chain + LIMITATION notice (degradation Level 4); no
  fabricated values; verdict `Inconclusive`; empty jitter report.
- **Runtime assertions:** degradation Level 4; verdict `Inconclusive`;
  `jitter_report == {}`; LIMITATION banner present.
- **Gates:** U2, graceful-degradation levels, G1â€“G4 (flagged as limitations).

### Gate coverage matrix

| Gate | S1 | S2 | S3 | S4 | S5 |
|------|----|----|----|----|----|
| G1 | âœ“ | âœ“ | âœ“ | âœ“ | â  (limitation) |
| G2 | âœ“ | âœ“ | âœ“ | âœ“ | â  (limitation) |
| G3 | âœ“ | âœ“ | âœ“ | âœ“ | â  (limitation) |
| G4 | âœ“ | âœ“ | âœ“ | âœ“ | â  (limitation) |
| U1â€“U6 | âœ“ | âœ“ | âœ“ | âœ“ | âœ“ (auto-fix where applicable) |

### Verdict coverage
Low Jitter, Conditional (ISP-limited), High Jitter, Inconclusive â€” all four
exercised by `tools/run_test_scenarios.py` via `verdict_from_scorecard`.


---

## S6 -- Agent framework end-to-end (Phase 7)

**Trigger:** `tjr-agent tests/fixtures/harness_input.json --json --trace`

**Asserts:**
- The orchestrator runs the 5-skill plan (`gather_requirements -> evidence_collector ->
  core_analysis -> knowledge_updater -> advisor`).
- A non-empty chain-of-thought trace is emitted.
- The verdict is in the declared set and matches the deterministic harness
  result (single source of truth).
- 5 skill results are reported with per-skill `ok`/`duration_ms`.
- Metrics include `steps_run`, `degradations`, `gates_failed`, `tools_called`.
- Token accounting is reported (spent/remaining).
- The report Markdown contains the G1-G4 gate checklist.

**Degraded variant:** `tjr-agent {}` -> verdict `Inconclusive`, `degraded=True`
(router short-circuit), proving graceful degradation through the agent layer.

Covered by `tools/test_agent_framework.py` and the Layer-4 runtime checks in
`tools/run_test_scenarios.py`.