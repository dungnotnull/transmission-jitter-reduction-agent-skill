"""tjr.jitter_cli — ``tjr-jitter`` entry point.

A focused CLI for the jitter-analysis primitives: feed it a ping/mtr/wireshark
text export (or a JSON list of RTT samples) and it prints the full jitter
report plus optional AQM/QoS/Wi-Fi/buffer recommendations.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import jitter_analysis as ja


def _read_rtts(path: str, fmt: str) -> list:
    if path == "-":
        text = sys.stdin.read()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [float(x) for x in data]
        except json.JSONDecodeError:
            pass
        # fall through to file-style parse on the stdin text
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix=".txt")
        try:
            os.write(fd, text.encode("utf-8")); os.close(fd)
            return ja.load_rtt_samples(tmp, fmt)
        finally:
            os.unlink(tmp)
    return ja.load_rtt_samples(path, fmt)


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="tjr-jitter",
                                 description="Compute jitter/PDV/bufferbloat + recommendations from RTT samples.")
    ap.add_argument("rtts", help="Path to a ping/mtr/wireshark export, '-' for stdin, or a JSON list file.")
    ap.add_argument("--fmt", default="auto", choices=["auto", "ping", "mtr", "wireshark"])
    ap.add_argument("--idle", type=float, default=None, help="Idle/baseline latency (ms).")
    ap.add_argument("--lul", type=float, default=None, help="Latency under load (ms).")
    ap.add_argument("--upload", type=float, default=None, help="Measured upload bandwidth (Mbps).")
    ap.add_argument("--download", type=float, default=None, help="Measured download bandwidth (Mbps).")
    ap.add_argument("--flows", type=int, default=1, help="Concurrent flow count (drives AQM choice).")
    ap.add_argument("--game", default=None, help="Game key (valorant, csgo, cs2, dota2, lol, overwatch, apex, fortnite, pubg).")
    ap.add_argument("--tickrate", type=int, default=64, help="Server tickrate (Hz).")
    ap.add_argument("--json", action="store_true")
    return ap


def main(argv=None) -> int:
    args = build_argparser().parse_args(argv)
    rtts = _read_rtts(args.rtts, args.fmt)
    report = ja.compute_jitter(rtts)
    out = {"jitter_report": report.as_dict()}
    if args.idle is not None and args.lul is not None:
        bb = ja.bufferbloat_grade(args.lul, args.idle)
        out["bufferbloat"] = bb.as_dict()
        out["verdict"] = ja.verdict_from_scorecard(
            report.consecutive_jitter_ms, bb.grade).value
        out["scenarios"] = [s.as_dict() for s in ja.generate_scenarios(rtts, args.idle, args.lul)]
    if args.upload or args.download or args.flows:
        out["aqm"] = ja.aqm_recommend(args.upload, args.download, args.flows).as_dict()
    out["qos"] = ja.dscp_marking("game", args.game).as_dict()
    out["jitter_buffer"] = ja.jitter_buffer_sizing(report.consecutive_jitter_ms, args.tickrate).as_dict()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"n={report.n} mean={report.mean_ms}ms mdev={report.mdev_ms}ms "
              f"jitter={report.consecutive_jitter_ms}ms rtp={report.rtp_jitter_ms}ms pdv={report.pdv_ms}ms")
        if "bufferbloat" in out:
            b = out["bufferbloat"]
            print(f"bufferbloat: grade {b['grade']} (+{b['added_latency_ms']}ms) -> verdict {out['verdict']}")
        if "aqm" in out:
            a = out["aqm"]
            print(f"AQM: {a['algorithm']} target={a['target_ms']}ms "
                  + (f"shape_up={a['shape_upload_mbps']}Mbps" if a['shape_upload_mbps'] else ""))
        q = out["qos"]
        print(f"QoS: DSCP {q['dscp_name']}({q['dscp']}) -> {q['wmm_ac']}")
        jb = out["jitter_buffer"]
        print(f"jitter buffer: {jb['buffer_ticks']} tick(s) = {jb['buffer_ms']}ms @ {jb['tickrate_hz']}Hz")
    return 0


if __name__ == "__main__":
    sys.exit(main())