#!/usr/bin/env python3
"""scripts/ingest_measurements.py -- ingest a measurement file into a run.

Convenience ingestion helper: parses a ping/MTR/Wireshark capture with
``tjr.jitter_analysis.load_rtt_samples`` (optionally enriching it with idle /
loaded latency + bandwidth + game), writes a ``HarnessInput``-conforming JSON
file ready for ``tjr-harness`` / ``tjr-agent``, and optionally runs the agent
over it immediately.

Run::

    python scripts/ingest_measurements.py tests/fixtures/ping_capture.txt \
        --idle 14 --lul 78 --upload 20 --download 100 --game valorant \
        --out tests/fixtures/ingested.json --run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tjr import jitter_analysis as ja


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Ingest a measurement capture into a HarnessInput JSON file.")
    ap.add_argument("capture", help="Path to a ping/MTR/Wireshark export, or '-' for stdin.")
    ap.add_argument("--fmt", default="auto", choices=["auto", "ping", "mtr", "wireshark"])
    ap.add_argument("--idle", type=float, help="Idle/baseline latency (ms).")
    ap.add_argument("--lul", type=float, help="Latency under load (ms).")
    ap.add_argument("--upload", type=float, help="Measured upload bandwidth (Mbps).")
    ap.add_argument("--download", type=float, help="Measured download bandwidth (Mbps).")
    ap.add_argument("--flows", type=int, default=1)
    ap.add_argument("--game", help="Game key (valorant, csgo, cs2, dota2, lol, overwatch, apex, fortnite, pubg).")
    ap.add_argument("--tickrate", type=int, default=64)
    ap.add_argument("--band", default="5", choices=["2.4", "5", "6"])
    ap.add_argument("--out", help="Write the assembled HarnessInput JSON to this file.")
    ap.add_argument("--run", action="store_true", help="Run the agent over the assembled input and print the verdict.")
    ap.add_argument("--query", default="", help="Optional free-text query attached to the input.")
    return ap


def assemble(args) -> dict:
    if args.capture == "-":
        text = sys.stdin.read()
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix=".txt")
        try:
            os.write(fd, text.encode("utf-8")); os.close(fd)
            rtts = ja.load_rtt_samples(tmp, args.fmt)
        finally:
            os.unlink(tmp)
    else:
        rtts = ja.load_rtt_samples(args.capture, args.fmt)
    return {
        "query": args.query,
        "rtt_samples": rtts,
        "idle_latency_ms": args.idle,
        "latency_under_load_ms": args.lul,
        "upload_mbps": args.upload,
        "download_mbps": args.download,
        "flow_count": args.flows,
        "game": args.game,
        "tickrate_hz": args.tickrate,
        "wifi_band": args.band,
        "evidence": [],
        "knowledge_citations": [],
    }


def main(argv=None) -> int:
    args = build_argparser().parse_args(argv)
    data = assemble(args)
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ingest] wrote {args.out} ({len(data['rtt_samples'])} samples)")
    if args.run:
        from tjr.agents import OrchestratorAgent
        result = OrchestratorAgent().run(data)
        print(f"[ingest] verdict={result.verdict} degraded={result.degraded} "
              f"plan={' -> '.join(result.plan)}")
        if args.out is None:
            print("\n" + "=" * 72 + "\n")
            print(result.report_markdown)
    if not args.out and not args.run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())