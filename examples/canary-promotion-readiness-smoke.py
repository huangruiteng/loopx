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
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard"

COMMON_NODE_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
]
READINESS_GOAL_ID = "loopx-meta"
DEFAULT_READINESS_AGENT_ID = "codex-product-capability"
DEFAULT_READINESS_AGENT_LANE = "product_capability_catalog_canary"
READINESS_CLASSIFICATION = "canary_promotion_readiness_smoke_group"
READINESS_RECOMMENDED_ACTION = (
    "Canary promotion-readiness smoke passed; promotion may proceed after doctor/status reports fresh evidence."
)
READINESS_RECOMMENDED_ACTION_DASHBOARD_SKIPPED = (
    "Canary promotion-readiness smoke passed for the installed release boundary; "
    "dashboard readiness was skipped because apps/dashboard is not shipped in the release snapshot."
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
        "--dashboard-mode",
        choices=("auto", "require", "skip"),
        default="auto",
        help=(
            "Dashboard readiness policy: auto runs it when apps/dashboard is present, "
            "require fails if the dashboard app is absent, and skip records the release-boundary omission."
        ),
    )
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
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("LOOPX_AGENT_ID") or DEFAULT_READINESS_AGENT_ID,
        help=(
            "Registered agent id used for the readiness evidence writeback. "
            "Defaults to LOOPX_AGENT_ID or codex-product-capability."
        ),
    )
    parser.add_argument(
        "--agent-lane",
        default=os.environ.get("LOOPX_AGENT_LANE") or DEFAULT_READINESS_AGENT_LANE,
        help=(
            "Public-safe agent lane label used for the readiness evidence writeback. "
            "Defaults to LOOPX_AGENT_LANE or product_capability_catalog_canary."
        ),
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


def write_readiness_evidence(
    env: dict[str, str],
    *,
    dashboard_skipped: bool,
    agent_id: str | None = None,
    agent_lane: str | None = None,
) -> None:
    recommended_action = (
        READINESS_RECOMMENDED_ACTION_DASHBOARD_SKIPPED
        if dashboard_skipped
        else READINESS_RECOMMENDED_ACTION
    )
    resolved_agent_id = (
        agent_id or os.environ.get("LOOPX_AGENT_ID") or DEFAULT_READINESS_AGENT_ID
    ).strip()
    resolved_agent_lane = (
        agent_lane or os.environ.get("LOOPX_AGENT_LANE") or DEFAULT_READINESS_AGENT_LANE
    ).strip()
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "refresh-state",
        "--goal-id",
        READINESS_GOAL_ID,
        "--classification",
        READINESS_CLASSIFICATION,
        "--recommended-action",
        recommended_action,
        "--delivery-batch-scale",
        "multi_surface",
        "--delivery-outcome",
        "primary_goal_outcome",
    ]
    if resolved_agent_id:
        command.extend(["--agent-id", resolved_agent_id])
    if resolved_agent_lane:
        command.extend(["--agent-lane", resolved_agent_lane])
    run_command(
        "promotion readiness evidence writeback",
        command,
        env,
    )


def dashboard_readiness_plan(
    *,
    dashboard_dir: Path = DASHBOARD_DIR,
    dashboard_mode: str = "auto",
    include_browser: bool = False,
) -> dict[str, object]:
    has_dashboard = (dashboard_dir / "package.json").is_file()
    if dashboard_mode == "skip":
        return {
            "status": "skip",
            "reason": "dashboard readiness explicitly skipped",
            "command": None,
        }
    if has_dashboard:
        command = [sys.executable, "examples/dashboard-demo-readiness-smoke.py"]
        if not include_browser:
            command.append("--skip-browser")
        return {
            "status": "run",
            "reason": None,
            "command": command,
        }
    reason = (
        "apps/dashboard is not present in this checkout or release snapshot; "
        "run from a source checkout or pass --dashboard-mode=skip to omit it intentionally"
    )
    if dashboard_mode == "require" or include_browser:
        return {
            "status": "fail",
            "reason": reason,
            "command": None,
        }
    return {
        "status": "skip",
        "reason": reason,
        "command": None,
    }


def main() -> int:
    args = parse_args()
    env = build_env()
    commands = list(BASE_COMMANDS)
    dashboard_plan = dashboard_readiness_plan(
        dashboard_mode=args.dashboard_mode,
        include_browser=args.include_browser,
    )
    if dashboard_plan["status"] == "fail":
        raise SystemExit(str(dashboard_plan["reason"]))
    if dashboard_plan["status"] == "run":
        dashboard_command = dashboard_plan["command"]
        assert isinstance(dashboard_command, list)
        commands.append(("dashboard demo readiness", dashboard_command))
    else:
        print(
            f"[canary-promotion] dashboard demo readiness: skipped ({dashboard_plan['reason']})",
            flush=True,
        )

    for label, command in commands:
        run_command(label, command, env)

    evidence_suffix = " without evidence writeback"
    if not args.no_write_evidence:
        write_readiness_evidence(
            env,
            dashboard_skipped=dashboard_plan["status"] == "skip",
            agent_id=args.agent_id,
            agent_lane=args.agent_lane,
        )
        evidence_suffix = " with evidence writeback"

    if dashboard_plan["status"] == "skip":
        suffix = " with dashboard readiness skipped"
    else:
        suffix = " with browser smokes" if args.include_browser else " without browser smokes"
    print(f"canary-promotion-readiness-smoke ok{suffix}{evidence_suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
