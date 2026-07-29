"""tjr.cli — ``tjr-harness`` entry point.

Runs the 6-step transmission-jitter-reduction harness over a JSON measurement
file and prints the verdict + a full Markdown report (and optionally the JSON
result object).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .harness import Harness, HarnessInput


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tjr-harness",
        description="Run the transmission-jitter-reduction harness over a JSON measurement file.",
    )
    ap.add_argument("input", help="Path to a JSON file conforming to HarnessInput fields.")
    ap.add_argument("--json", action="store_true", help="Print the full JSON result object.")
    ap.add_argument("--markdown-only", action="store_true",
                    help="Print only the Markdown report (default prints both header + report).")
    ap.add_argument("-o", "--output", help="Write the Markdown report to this file.")
    return ap


def main(argv=None) -> int:
    args = build_argparser().parse_args(argv)
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input file not found: {in_path}", file=sys.stderr)
        return 2
    with in_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    result = Harness().run(HarnessInput.from_dict(data))
    if args.json:
        print(result.to_json())
    else:
        if not args.markdown_only:
            print(f"verdict: {result.verdict} | gates: {result.gate_summary['checklist']} "
                  f"| degradation: L{result.degradation_level}")
            print("\n" + "=" * 72 + "\n")
        print(result.report_markdown)
    if args.output:
        Path(args.output).write_text(result.report_markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())