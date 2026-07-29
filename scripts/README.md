# scripts/ -- automation, seeding, ingestion and local setup

Operational scripts for the `transmission-jitter-reduction` toolkit. Each is a
standalone, idempotent Python entry point (run with `python scripts/<name>.py`).

| Script | Purpose |
|--------|---------|
| `setup.py` | Local setup: create runtime dirs, validate config, optional `pip install -e .` |
| `seed_knowledge.py` | Seed the `SECOND-KNOWLEDGE-BRAIN.md` Tier-1 baseline from `references/` (offline, idempotent via SHA-256 dedup) |
| `ingest_measurements.py` | Parse a ping/MTR/Wireshark capture into a `HarnessInput` JSON, optionally run the agent |
| `run_crawl.py` | Seed baseline then run the live knowledge crawl (`tjr-knowledge`) |
| `validate.py` | Single gate: runs `validate_project.py` + `run_test_scenarios.py` + `pytest` |

All scripts add the repo root to `sys.path` so they work without an installed
package (`python scripts/setup.py` from a fresh checkout).