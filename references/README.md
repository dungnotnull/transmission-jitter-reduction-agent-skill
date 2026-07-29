# references/ -- domain knowledge & prompt base-templates

Grounding material for the `transmission-jitter-reduction` agent framework.
These files are the **RAG / agent grounding** layer: prompt base-templates and
raw context guidelines that the Claude sub-skills (and the `tjr.skills` skill
handlers) anchor on, ensuring consistent, evidence-graded outputs.

| File | Purpose |
|------|---------|
| `prompt-templates.md` | Base prompt templates for each of the 5 sub-skills (intake, evidence, core analysis, knowledge, advisor). |
| `domain-guidelines.md` | Domain knowledge, measurement methods, and grounding rules for Network Jitter & Real-Time Transport Optimization. |
| `evidence-hierarchy.md` | Tier 1-4 evidence definitions and citation rules used by the quality gates (U1, U3). |
| `rfc-index.md` | Authoritative RFC/IEEE standard index for the domain, with the metric each one grounds. |

These references are consumed by:

* `skills/sub-*.md` -- the markdown contract refers to these for shared grounding.
* `tjr.skills` handlers -- the deterministic skill bodies encode the same
  methods (RFC 3550 jitter, RFC 8289 bufferbloat, etc.) referenced here.
* `SECOND-KNOWLEDGE-BRAIN.md` -- the crawl pipeline appends entries that must
  cite sources present in `rfc-index.md` or the academic source list.