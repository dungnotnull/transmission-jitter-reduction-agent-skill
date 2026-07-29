#!/usr/bin/env python3
"""scripts/setup.py -- local setup routine for transmission-jitter-reduction.

Idempotent local setup:

* creates the runtime directories (logs/, etc.);
* optionally installs runtime + dev dependencies into the current environment;
* reports the resolved :class:`tjr.config.Settings` so misconfiguration surfaces
  before any real run.

Run::

    python scripts/setup.py            # dirs + config check, no pip
    python scripts/setup.py --install  # also pip install -e . + dev extras
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNTIME_DIRS = ["logs"]


def ensure_dirs() -> list:
    created = []
    for d in RUNTIME_DIRS:
        p = ROOT / d
        if not p.exists():
            p.mkdir(parents=True)
            created.append(str(p))
    return created


def check_config() -> dict:
    from tjr.config import load_settings, ConfigError
    try:
        s = load_settings()
        return {"ok": True, "environment": s.environment, "model": s.llm.model,
                "features": s.features.as_dict()}
    except ConfigError as ex:
        return {"ok": False, "error": str(ex)}


def pip_install(dev: bool) -> int:
    cmd = [sys.executable, "-m", "pip", "install"]
    cmd.append(".")
    if dev:
        cmd.append("pytest>=7.4")
    print("[setup] running:", " ".join(cmd))
    return subprocess.call(cmd)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Local setup for transmission-jitter-reduction.")
    ap.add_argument("--install", action="store_true", help="pip install the package (editable) + dev extras.")
    ap.add_argument("--no-dev", action="store_true", help="with --install, skip dev extras.")
    args = ap.parse_args(argv)

    created = ensure_dirs()
    print(f"[setup] runtime dirs ready; created={created or 'none'}")

    cfg = check_config()
    if not cfg["ok"]:
        print(f"[setup] CONFIG ERROR: {cfg['error']}", file=sys.stderr)
        return 1
    print(f"[setup] config OK: env={cfg['environment']} model={cfg['model']} "
          f"agent_framework={cfg['features']['agent_framework']}")

    if args.install:
        rc = pip_install(dev=not args.no_dev)
        if rc != 0:
            print(f"[setup] pip install failed (rc={rc})", file=sys.stderr)
            return rc

    print("[setup] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())