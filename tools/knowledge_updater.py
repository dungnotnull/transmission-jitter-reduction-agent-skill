"""tools/knowledge_updater.py — backward-compatible CLI shim.

The real implementation lives in :mod:`tjr.knowledge_updater`. This shim keeps
the historical ``tools/knowledge_updater.py`` entry point working for existing
cron entries and for the test files that do ``import knowledge_updater as ku``.

It re-exports the stable public API (``KNOWLEDGE_CONFIG``, ``compute_hash``,
``score_entry``, ``format_entry``, ``fetch_with_retry``, ``load_existing_hashes``,
``append_to_brain``, ``fetch_arxiv``, ``fetch_semantic_scholar``, ``fetch_rss``,
``main``) so existing imports keep working unchanged.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the ``tjr`` package importable when this shim is run directly or imported
# via an inserted tools/ sys.path entry.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tjr.knowledge_updater import (  # noqa: E402
    KNOWLEDGE_CONFIG,
    KnowledgeEntry,
    KnowledgeUpdater,
    append_to_brain,
    compute_hash,
    fetch_arxiv,
    fetch_rss,
    fetch_semantic_scholar,
    fetch_with_retry,
    format_entry,
    load_existing_hashes,
    main,
    run,
    score_entry,
    BRAIN_PATH,
)

__all__ = [
    "KNOWLEDGE_CONFIG", "KnowledgeEntry", "KnowledgeUpdater", "BRAIN_PATH",
    "append_to_brain", "compute_hash", "fetch_arxiv", "fetch_rss",
    "fetch_semantic_scholar", "fetch_with_retry", "format_entry",
    "load_existing_hashes", "main", "run", "score_entry",
]


if __name__ == "__main__":
    main()