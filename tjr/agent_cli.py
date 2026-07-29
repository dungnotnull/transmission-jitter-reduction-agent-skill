"""tjr.agent_cli -- ``tjr-agent`` entry point.

Runs the full agent framework (config -> router -> sub-agents -> hooks -> tools
-> deterministic harness delegation) over a JSON input file and prints the
verdict + chain-of-thought plan + metrics (and optionally the full JSON result).

This is the agent-layer counterpart of ``tjr-harness``: where ``tjr-harness``
runs the deterministic reference orchestrator only, ``tjr-agent`` additionally
emits the routing trace, skill results, metrics and token accounting from the
production agent framework, while delegating the authoritative gate-enforced
result to the same ``tjr.harness.Harness``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import OrchestratorAgent
from .config import load_settings


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tjr-agent",
        description="Run the transmission-jitter-reduction agent framework over a JSON input file.",
    )
    ap.add_argument("input", help="Path to a JSON file with the run context (HarnessInput-compatible fields).")
    ap.add_argument("--json", action="store_true", help="Print the full JSON agent result.")
    ap.add_argument("--trace", action="store_true", help="Print the chain-of-thought routing trace.")
    ap.add_argument("-o", "--output", help="Write the Markdown report to this file.")
    ap.add_argument("--config", help="Path to a TOML config file (default: config/default.toml).")
    ap.add_argument("--quiet", action="store_true", help="Set logging level to WARNING.")
    return ap


def main(argv=None) -> int:
    args = build_argparser().parse_args(argv)
    overrides = {}
    if args.quiet:
        overrides["logging"] = {"level": "WARNING"}
    settings = load_settings(path=Path(args.config) if args.config else None, overrides=overrides)
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input file not found: {in_path}", file=sys.stderr)
        return 2
    with in_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    result = OrchestratorAgent(settings=settings).run(data)
    if args.json:
        print(result.to_json())
    else:
        print(f"verdict: {result.verdict} | plan: {' -> '.join(result.plan)} "
              f"| degraded: {result.degraded} | gates: {result.harness_result['gate_summary']['checklist']}")
        if args.trace:
            print("\n# Chain-of-thought trace:")
            for i, t in enumerate(result.trace, 1):
                print(f"  {i}. {t}")
        if result.metrics:
            print(f"# metrics: {result.metrics}")
        if result.token_summary.get("enabled", True) is not False:
            print(f"# tokens: spent={result.token_summary.get('spent')} "
                  f"remaining={result.token_summary.get('remaining')}")
        print("\n" + "=" * 72 + "\n")
        print(result.report_markdown)
    if args.output:
        Path(args.output).write_text(result.report_markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())