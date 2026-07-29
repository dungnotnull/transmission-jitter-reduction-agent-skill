# assets/ -- static resources, schemas and diagrams

Static, versioned assets for the `transmission-jitter-reduction` toolkit.

## schemas/

JSON Schema (draft 2020-12) definitions for the agent + core contracts:

| Schema | Describes |
|--------|-----------|
| `harness_input.schema.json` | Run context accepted by `tjr-harness` / `tjr-agent` |
| `harness_result.schema.json` | Authoritative deterministic result from `tjr.harness.Harness` |
| `skill_spec.schema.json` | `SkillSpec` declaration shape |
| `tool.schema.json` | `Tool` declaration shape |

These are the canonical contracts; the in-code registries (`tjr.skills`,
`tjr.tools`) embed equivalent JSON-Schema subsets and validate against them at
runtime.

## diagrams/

Mermaid diagrams (render on GitHub or with `mermaid-cli`):

| Diagram | Shows |
|---------|-------|
| `architecture.mmd` | Agent framework architecture (config -> agents -> registry -> core) |
| `harness-flow.mmd` | The 6-step harness execution flow + gate retry/degradation |