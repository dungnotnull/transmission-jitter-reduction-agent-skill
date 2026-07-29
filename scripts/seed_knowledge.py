#!/usr/bin/env python3
"""scripts/seed_knowledge.py -- seed the knowledge base from the references.

Ensures the Tier 1 baseline references (RFCs + key papers) referenced in
``references/rfc-index.md`` and ``SECOND-KNOWLEDGE-BRAIN.md`` are present in
Section 2 of the brain file. Idempotent: uses the same SHA-256 dedup as
``tjr.knowledge_updater`` so re-runs never duplicate entries.

This is a *local seeding* routine, not a network crawl (use
``scripts/run_crawl.py`` for live fetching). It guarantees the knowledge base
always carries the authoritative baseline even offline.

Run::

    python scripts/seed_knowledge.py            # write
    python scripts/seed_knowledge.py --dry-run   # preview
    python scripts/seed_knowledge.py --json       # JSON summary
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tjr.knowledge_updater import BRAIN_PATH, compute_hash, load_existing_hashes, format_entry

# Tier 1/2 baseline seed entries (must cite sources in references/rfc-index.md).
SEED_ENTRIES = [
    {"title": "Controlling Queue Delay: CoDel", "authors": ["Nichols", "Jacobson"],
     "year": 2012, "venue": "ACM Queue", "doi_or_url": "10.1145/2539071",
     "abstract": "CoDel controls queueing delay directly without per-flow state.",
     "citation_count": 0, "source": "seed", "tier": 2},
    {"title": "RFC 8289 -- CoDel AQM", "authors": ["Nichols", "Jacobson et al."],
     "year": 2018, "venue": "IETF", "doi_or_url": "https://www.rfc-editor.org/rfc/rfc8289",
     "abstract": "CoDel as an IETF AQM standard; grounds bufferbloat grading.",
     "citation_count": 0, "source": "seed", "tier": 1},
    {"title": "RFC 8290 -- FQ-CoDel scheduler", "authors": ["Hoeiland-Jorgensen et al."],
     "year": 2018, "venue": "IETF", "doi_or_url": "https://www.rfc-editor.org/rfc/rfc8290",
     "abstract": "Fair queuing + CoDel; the lean AQM default for gaming hosts.",
     "citation_count": 0, "source": "seed", "tier": 1},
    {"title": "RFC 8033 -- PIE AQM", "authors": ["Pan et al."],
     "year": 2017, "venue": "IETF", "doi_or_url": "https://www.rfc-editor.org/rfc/rfc8033",
     "abstract": "Proportional Integral Controller Enhanced AQM.",
     "citation_count": 0, "source": "seed", "tier": 1},
    {"title": "RFC 9330 -- L4S architecture", "authors": ["Briscoe", "Schepper", "Bagnulo"],
     "year": 2023, "venue": "IETF", "doi_or_url": "https://www.rfc-editor.org/rfc/rfc9330",
     "abstract": "Low Latency, Low Loss, Scalable Throughput architecture.",
     "citation_count": 0, "source": "seed", "tier": 1},
    {"title": "Latency and Player Actions in Online Games", "authors": ["Claypool", "Claypool"],
     "year": 2005, "venue": "Commun. ACM / NetGames", "doi_or_url": "10.1145/1103599.1103602",
     "abstract": "Effects of latency on online game performance; grounds jitter-buffer sizing.",
     "citation_count": 0, "source": "seed", "tier": 2},
    {"title": "IEEE 802.11e -- WMM QoS", "authors": ["IEEE"],
     "year": 2005, "venue": "IEEE Std", "doi_or_url": "https://standards.ieee.org/ieee/802.11e/",
     "abstract": "WMM access categories (AC_VO/AC_VI/AC_BE/AC_BK).",
     "citation_count": 0, "source": "seed", "tier": 1},
]


def seed(dry_run: bool, brain_path: Path = BRAIN_PATH) -> dict:
    if not brain_path.exists():
        return {"ok": False, "error": f"brain file not found: {brain_path}"}
    existing = load_existing_hashes(brain_path)
    new = [e for e in SEED_ENTRIES if compute_hash(e["doi_or_url"]) not in existing]
    if not new:
        return {"ok": True, "appended": 0, "dry_run": dry_run, "message": "all baseline entries already present"}
    # Seed entries are appended under Section 7 (Update Log) with a note.
    header = "\n<!-- baseline seed (scripts/seed_knowledge.py) -->\n"
    text = header + "".join(format_entry(e, 10.0) for e in new)
    if not dry_run:
        content = brain_path.read_text(encoding="utf-8")
        if "## 7. Knowledge Update Log" in content:
            brain_path.write_text(content + text, encoding="utf-8")
        else:
            brain_path.write_text(content + "\n## 7. Knowledge Update Log\n" + text, encoding="utf-8")
    return {"ok": True, "appended": len(new), "dry_run": dry_run, "appended_titles": [e["title"] for e in new]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seed the knowledge base from the references.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = seed(args.dry_run)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not result["ok"]:
            print(f"[seed] ERROR: {result['error']}", file=sys.stderr)
            return 1
        action = "would append" if args.dry_run else "appended"
        print(f"[seed] {action} {result['appended']} baseline entries")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())