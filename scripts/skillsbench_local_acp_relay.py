#!/usr/bin/env python3
"""Serve the Goal Harness SkillsBench local ACP relay over stdio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Local Codex CLI binary used outside dry-run mode.",
    )
    parser.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
        help="Sandbox mode passed to local codex exec outside dry-run mode.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model passed to local codex exec.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=7200,
        help="Per-prompt local codex exec timeout outside dry-run mode.",
    )
    parser.add_argument(
        "--dry-run-response",
        default=None,
        help=(
            "Return this fixed response for session/prompt instead of invoking "
            "Codex. Intended for handshake/preflight smokes."
        ),
    )
    parser.add_argument(
        "--app-server-goal-worker",
        action="store_true",
        help=(
            "Delegate each ACP prompt to scripts/skillsbench_host_codex_goal_worker.py "
            "instead of codex exec. This is the native Codex Goal baseline path."
        ),
    )
    parser.add_argument("--dataset", default="skillsbench-v1.1")
    parser.add_argument("--task-id", default="llm-prefix-cache-replay")
    parser.add_argument("--approval-policy", default="never")
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        help=(
            "Codex app-server turn/start effort for --app-server-goal-worker. "
            "Formal benchmark runs default to high."
        ),
    )
    parser.add_argument(
        "--response-timeout-sec",
        type=float,
        default=30.0,
        help="Timeout for the worker to observe initial app-server response events.",
    )
    parser.add_argument(
        "--stream-heartbeat-interval-sec",
        type=float,
        default=120.0,
        help=(
            "Interval for public-safe ACP thought keepalives while the host "
            "app-server Goal worker is still executing."
        ),
    )
    parser.add_argument(
        "--worker-script",
        default=None,
        help="Optional path to skillsbench_host_codex_goal_worker.py.",
    )
    parser.add_argument(
        "--worker-public-trace-dir",
        default=None,
        help=(
            "Optional directory for public-safe host app-server Goal worker "
            "compact traces. Response text and raw app-server streams are not "
            "written there."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(
            codex_bin=args.codex_bin,
            sandbox=args.sandbox,
            model=args.model,
            timeout_sec=args.timeout_sec,
            dry_run_response=args.dry_run_response,
            app_server_goal_worker=args.app_server_goal_worker,
            dataset=args.dataset,
            task_id=args.task_id,
            approval_policy=args.approval_policy,
            reasoning_effort=args.reasoning_effort,
            response_timeout_sec=args.response_timeout_sec,
            worker_script=args.worker_script,
            stream_heartbeat_interval_sec=args.stream_heartbeat_interval_sec,
            worker_public_trace_dir=args.worker_public_trace_dir,
        )
    )
    return relay.serve()


if __name__ == "__main__":
    raise SystemExit(main())
