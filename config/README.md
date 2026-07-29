# config/ -- type-safe configuration management

This directory holds the baseline configuration for the
`transmission-jitter-reduction` toolkit, loaded and validated by
[`tjr.config`](../tjr/config.py).

## Hierarchy (low -> high precedence)

1. **Dataclass defaults** -- built into `tjr.config.Settings`.
2. **`default.toml`** (this file) -- shipped baseline, safe to edit.
3. **`TJR_*` environment variables** -- e.g. `TJR_LLM_TEMPERATURE=0.1`,
   `TJR_LOGGING_LEVEL=DEBUG`, `TJR_FEATURES_KNOWLEDGE_CRAWL=false`.
   Sectioned keys follow `TJR_<SECTION>_<KEY>` (sections: `FEATURES`, `LLM`,
   `CRAWL`, `LOGGING`); top-level keys use `TJR_<KEY>`
   (e.g. `TJR_ENVIRONMENT=development`).
4. **Explicit overrides** -- passed programmatically to
   `tjr.config.load_settings(overrides={...})`.

Every value is coerced to its declared type and range-validated on load. An
invalid value raises `tjr.config.ConfigError` *before* the toolkit starts, so
misconfiguration never produces a silent, half-broken run.

## Example

```bash
# Run the agent harness in development with debug logging and the crawl off:
TJR_ENVIRONMENT=development TJR_LOGGING_LEVEL=DEBUG TJR_FEATURES_KNOWLEDGE_CRAWL=false \
    tjr-agent tests/fixtures/harness_input.json --json
```

```python
from tjr.config import load_settings
s = load_settings(overrides={"llm": {"temperature": 0.1}})
print(s.llm.temperature, s.features.knowledge_crawl)
```