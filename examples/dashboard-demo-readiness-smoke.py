#!/usr/bin/env python3
"""Run the public dashboard demo-readiness smoke group."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard"

BASE_COMMANDS = [
    ("launchagent status output", [sys.executable, "examples/macos-dashboard-launchagent-status-smoke.py"], REPO_ROOT),
    ("promotion gate structured contract", [sys.executable, "examples/promotion-gate-smoke.py"], REPO_ROOT),
    ("dashboard home route", ["npm", "run", "smoke:home-route"], DASHBOARD_DIR),
    ("dashboard usage/progress source contract", ["npm", "run", "smoke:usage-progress"], DASHBOARD_DIR),
]

BROWSER_COMMANDS = [
    ("dashboard home browser", ["npm", "run", "smoke:home-browser"], DASHBOARD_DIR),
    ("dashboard ops decision freshness browser", ["npm", "run", "smoke:ops-decision-freshness"], DASHBOARD_DIR),
    ("dashboard promotion readiness browser", ["npm", "run", "smoke:promotion-readiness"], DASHBOARD_DIR),
]

COMMON_NODE_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-browser",
        action="store_true",
        help="Run only non-browser checks for CI environments without Playwright/Chrome.",
    )
    return parser.parse_args()


def run_command(label: str, command: list[str], cwd: Path, env: dict[str, str]) -> None:
    print(f"[demo-readiness] {label}: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def build_env() -> dict[str, str]:
    path_parts = [path for path in COMMON_NODE_PATHS if Path(path).exists()]
    path_parts.append(os.environ.get("PATH", ""))
    return {
        **os.environ,
        "PATH": ":".join(part for part in path_parts if part),
    }


def ensure_dashboard_dependencies(env: dict[str, str]) -> bool:
    if shutil.which("npm", path=env.get("PATH")) is None:
        print(
            "dashboard demo-readiness smoke requires npm; install Node/npm "
            "before running apps/dashboard smokes"
        )
        return False
    tsc_bin = DASHBOARD_DIR / "node_modules" / ".bin" / ("tsc.cmd" if os.name == "nt" else "tsc")
    if not tsc_bin.exists():
        print(
            "dashboard npm dependencies are missing; run "
            "`cd apps/dashboard && npm ci` before "
            "`npm run smoke:demo-readiness -- --skip-browser`"
        )
        return False
    return True


def main() -> int:
    args = parse_args()
    env = build_env()
    if not ensure_dashboard_dependencies(env):
        print("dashboard-demo-readiness-smoke skipped: dashboard dependencies unavailable")
        return 0
    commands = list(BASE_COMMANDS)
    if not args.skip_browser:
        commands.extend(BROWSER_COMMANDS)

    for label, command, cwd in commands:
        run_command(label, command, cwd, env)

    suffix = " without browser smokes" if args.skip_browser else ""
    print(f"dashboard-demo-readiness-smoke ok{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
