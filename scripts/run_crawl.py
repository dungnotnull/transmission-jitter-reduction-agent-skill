#!/usr/bin/env python3
"""scripts/run_crawl.py -- run the knowledge crawl pipeline.

Thin wrapper around ``tjr.knowledge_updater`` (the ``tjr-knowledge`` CLI) that
also seeds the baseline first (``scripts/seed_knowledge.py``) so the brain file
always carries the authoritative offline baseline before any live fetch.

Run::

    python scripts/run_crawl.py --dry-run
    python scripts/run_crawl.py --news-only --json
    python scripts/run_crawl.py --keywords "FQ-CoDel" "CAKE" "L4S"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tjr import knowledge_updater as ku


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the knowledge crawl pipeline (seed + live fetch).")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--news-only", action="store_true")
    ap.add_argument("--keywords", nargs="+", default=ku.KNOWLEDGE_CONFIG["keywords"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-seed", action="store_true", help="Skip the baseline seed step.")
    args = ap.parse_args(argv)

    if not args.no_seed:
        import importlib.util
        spec = importlib.util.spec_from_file_location("seed_knowledge", ROOT / "scripts" / "seed_knowledge.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        seed_result = mod.seed(dry_run=args.dry_run)
        if not args.json:
            print(f"[crawl] seed: appended={seed_result.get('appended', 0)} (dry_run={args.dry_run})")

    argv = []
    if args.dry_run:
        argv.append("--dry-run")
    if args.news_only:
        argv.append("--news-only")
    if args.json:
        argv.append("--json")
    if args.keywords and not args.news_only:
        argv += ["--keywords", *args.keywords]
    return ku.run(argv if argv else None)


if __name__ == "__main__":
    sys.exit(main())