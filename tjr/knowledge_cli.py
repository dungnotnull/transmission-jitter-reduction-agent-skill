"""tjr.knowledge_cli — ``tjr-knowledge`` entry point.

Thin CLI shim over :mod:`tjr.knowledge_updater` so users can run the crawl
pipeline as a console script (``tjr-knowledge --dry-run``).
"""
from __future__ import annotations

import sys

from .knowledge_updater import run


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()