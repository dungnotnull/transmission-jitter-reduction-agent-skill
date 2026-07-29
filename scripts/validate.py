#!/usr/bin/env python3
"""scripts/validate.py -- run the full validation suite.

Runs, in order:

1. ``tools/validate_project.py`` -- 8-File Contract + production-hardening checks.
2. ``tools/run_test_scenarios.py`` -- structural + runtime scenario validator.
3. ``pytest`` -- the unit + integration suite (if pytest is installed).

Exits 0 only if every layer passes. Use this as the single CI/local gate.

Run::

    python scripts/validate.py
    python scripts/validate.py --no-pytest   # skip pytest layer
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_step(label: str, cmd: list) -> int:
    print(f"\n{'='*72}\n[validate] {label}: {' '.join(cmd)}\n{'='*72}")
    return subprocess.call(cmd, cwd=str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the full validation suite.")
    ap.add_argument("--no-pytest", action="store_true", help="Skip the pytest layer.")
    args = ap.parse_args(argv)

    rc = run_step("8-File Contract validator", [sys.executable, "tools/validate_project.py"])
    if rc != 0:
        print("[validate] FAILED at validate_project.py", file=sys.stderr)
        return rc
    rc = run_step("scenario validator", [sys.executable, "tools/run_test_scenarios.py"])
    if rc != 0:
        print("[validate] FAILED at run_test_scenarios.py", file=sys.stderr)
        return rc

    if not args.no_pytest:
        rc = run_step("pytest", [sys.executable, "-m", "pytest", "-q", "--tb=short"])
        if rc != 0:
            print("[validate] FAILED at pytest", file=sys.stderr)
            return rc

    print("\n[validate] ALL LAYERS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())