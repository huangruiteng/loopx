#!/usr/bin/env python3
"""Run the public canary-promotion readiness smoke group.

This command is a preflight for promoting the live checkout into the default
local release snapshot. It validates the public boundary, status projections,
installer wrappers, and dashboard demo-readiness path without mutating the
installed release. By default, a successful run appends one public-safe
promotion-readiness evidence event to the LoopX run history so status,
doctor, and quota guards can clear stale or missing readiness warnings from the
append-only ledger.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

COMMON_NODE_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
]
READINESS_GOAL_ID = "loopx-meta"
READINESS_CLASSIFICATION = "canary_promotion_readiness_smoke_group"
READINESS_RECOMMENDED_ACTION = (
    "Canary promotion-readiness smoke passed; promotion may proceed after doctor/status reports fresh evidence."
)

BASE_COMMANDS = [
    (
        "public boundary contract",
        [sys.executable, "-m", "loopx.cli", "check", "--scan-path", str(REPO_ROOT)],
    ),
    ("status markdown projection", [sys.executable, "examples/status-markdown-smoke.py"]),
    ("usage/event/decision projections", [sys.executable, "examples/usage-summary-smoke.py"]),
    ("installer release/canary wrappers", [sys.executable, "examples/install-local-smoke.py"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-browser",
        action="store_true",
        help="Also run browser-backed dashboard demo-readiness smokes.",
    )
    parser.add_argument(
        "--no-write-evidence",
        action="store_true",
        help="Run checks only; do not append the promotion-readiness evidence event.",
    )
    return parser.parse_args()


def build_env() -> dict[str, str]:
    path_parts = [path for path in COMMON_NODE_PATHS if Path(path).exists()]
    path_parts.append(os.environ.get("PATH", ""))
    return {
        **os.environ,
        "PATH": ":".join(part for part in path_parts if part),
        "PYTHONPATH": str(REPO_ROOT),
    }


def run_command(label: str, command: list[str], env: dict[str, str]) -> None:
    print(f"[canary-promotion] {label}: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)


def write_readiness_evidence(env: dict[str, str]) -> None:
    run_command(
        "promotion readiness evidence writeback",
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "refresh-state",
            "--goal-id",
            READINESS_GOAL_ID,
            "--classification",
            READINESS_CLASSIFICATION,
            "--recommended-action",
            READINESS_RECOMMENDED_ACTION,
            "--delivery-batch-scale",
            "multi_surface",
            "--delivery-outcome",
            "primary_goal_outcome",
        ],
        env,
    )


def main() -> int:
    args = parse_args()
    env = build_env()
    commands = list(BASE_COMMANDS)
    dashboard_command = [sys.executable, "examples/dashboard-demo-readiness-smoke.py"]
    if not args.include_browser:
        dashboard_command.append("--skip-browser")
    commands.append(("dashboard demo readiness", dashboard_command))

    for label, command in commands:
        run_command(label, command, env)

    evidence_suffix = " without evidence writeback"
    if not args.no_write_evidence:
        write_readiness_evidence(env)
        evidence_suffix = " with evidence writeback"

    suffix = " with browser smokes" if args.include_browser else " without browser smokes"
    print(f"canary-promotion-readiness-smoke ok{suffix}{evidence_suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
