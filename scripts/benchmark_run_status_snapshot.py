#!/usr/bin/env python3
"""Emit a compact public-safe status snapshot for benchmark run directories."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.rollout_event_log import (  # noqa: E402
    append_rollout_event,
    build_rollout_event,
    rollout_event_log_path,
)
from loopx.benchmark_core import (  # noqa: E402
    build_benchmark_observable_handle_policy,
)


DEFAULT_COMPACT_KEYS = (
    "schema_version",
    "benchmark_id",
    "case_id",
    "mode",
    "thread_id_present",
    "goal_get_present",
    "goal_status",
    "turn_id_present",
    "raw_transcript_recorded",
    "official_score_status",
    "official_score",
    "official_task_score",
    "score_failure_attribution",
    "first_blocker",
    "ready_for_compact_result_ingest",
    "ready_for_compact_failure_marker",
    "compact_failure_class",
    "failure_class",
    "terminal_closeout",
    "external_handle_terminal",
    "runner_return_status",
    "accuracy",
    "n_resolved",
    "n_unresolved",
)

DEFAULT_ARTIFACT_NAMES = ("result.json", "results.json", "run_metadata.json")


def _pid_alive(pid_text: str) -> bool:
    try:
        pid = int(pid_text)
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _public_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def _compact_summary(path: Path, base: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read_text(path))
    except Exception as exc:
        return {
            "path": _public_path(path, base),
            "readable": False,
            "error_type": type(exc).__name__,
        }
    compact = payload.get("compact_benchmark_run")
    if not isinstance(compact, dict):
        compact = payload
    return {
        "path": _public_path(path, base),
        "readable": True,
        "summary": {
            key: compact.get(key)
            for key in DEFAULT_COMPACT_KEYS
            if key in compact
        },
    }


def _capture_summary(path: Path, base: Path, patterns: list[str], now: float) -> dict[str, Any]:
    text = _read_text(path)
    return {
        "path": _public_path(path, base),
        "bytes": len(text.encode("utf-8")),
        "mtime_age_sec": int(now - path.stat().st_mtime),
        "patterns": {pattern: (pattern in text) for pattern in patterns},
    }


def snapshot_run(
    run_dir: Path,
    *,
    label: str,
    patterns: list[str],
    max_compacts: int,
    max_captures: int,
) -> dict[str, Any]:
    now = time.time()
    item: dict[str, Any] = {
        "label": label,
        "run_dir_recorded": False,
        "exists": run_dir.exists(),
    }
    if not run_dir.exists():
        return item

    status_file = run_dir / "status.env"
    item["status"] = _read_text(status_file).strip() if status_file.exists() else "running/no-status"

    pid_file = run_dir / "pid.private"
    if pid_file.exists():
        pid_text = _read_text(pid_file).strip()
        item["pid"] = pid_text
        item["pid_alive"] = _pid_alive(pid_text)

    item["compact_results"] = [
        _compact_summary(path, run_dir)
        for path in sorted(run_dir.glob("**/*compact*.json"))[:max_compacts]
    ]
    item["artifact_presence"] = {
        name: [
            str(path.relative_to(run_dir))
            for path in sorted(run_dir.glob(f"**/{name}"))[:5]
        ]
        for name in DEFAULT_ARTIFACT_NAMES
    }
    item["bridge_request_dirs"] = [
        {
            "path": str(path.relative_to(run_dir)),
            "json_count": len(list(path.glob("*.json"))),
            "request_count": len(list(path.glob("*.request.json"))),
            "running_count": len(list(path.glob("*.running.json"))),
            "response_count": len(list(path.glob("*.response.json"))),
        }
        for path in sorted(run_dir.glob("**/requests"))[:max_captures]
    ]
    if patterns:
        item["capture_files"] = [
            _capture_summary(path, run_dir, patterns, now)
            for path in sorted(run_dir.glob("**/tmux_capture.txt"))[:max_captures]
        ]
    item["observable_handle_policy"] = build_benchmark_observable_handle_policy(item)
    return item


def build_snapshot(
    *,
    run_root: Path,
    labels: list[str],
    patterns: list[str],
    max_compacts: int,
    max_captures: int,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_status_snapshot_v0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_root_recorded": False,
        "boundary": {
            "raw_task_text_read": False,
            "raw_trajectories_read": False,
            "raw_logs_emitted": False,
            "capture_content_emitted": False,
            "local_paths_recorded": False,
        },
        "runs": [
            snapshot_run(
                run_root / label,
                label=label,
                patterns=patterns,
                max_compacts=max_compacts,
                max_captures=max_captures,
            )
            for label in labels
        ],
    }


def _snapshot_rollout_status(payload: dict[str, Any]) -> str:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    if not runs:
        return "empty_snapshot"
    existing = [run for run in runs if isinstance(run, dict) and run.get("exists")]
    alive = [run for run in existing if run.get("pid_alive") is True]
    compact_results = sum(
        len(run.get("compact_results") or [])
        for run in existing
        if isinstance(run, dict)
    )
    if alive:
        return "running"
    if compact_results:
        return "compact_artifact_seen"
    if len(existing) < len(runs):
        return "missing_run_dir"
    return "polled"


def _snapshot_rollout_details(payload: dict[str, Any]) -> dict[str, Any]:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    run_items = [run for run in runs if isinstance(run, dict)]
    existing = [run for run in run_items if run.get("exists")]
    return {
        "command": "benchmark_run_status_snapshot",
        "run_count": len(run_items),
        "exists_count": len(existing),
        "missing_count": len(run_items) - len(existing),
        "pid_alive_count": sum(1 for run in existing if run.get("pid_alive") is True),
        "compact_result_count": sum(
            len(run.get("compact_results") or []) for run in existing
        ),
        "bridge_request_dir_count": sum(
            len(run.get("bridge_request_dirs") or []) for run in existing
        ),
        "capture_file_count": sum(
            len(run.get("capture_files") or []) for run in existing
        ),
        "terminal_closeout_count": sum(
            1
            for run in existing
            if isinstance(run.get("observable_handle_policy"), dict)
            and run["observable_handle_policy"].get("terminal_closeout") is True
        ),
        "cleanup_required_count": sum(
            1
            for run in existing
            if isinstance(run.get("observable_handle_policy"), dict)
            and run["observable_handle_policy"].get("cleanup_required") is True
        ),
        "monitor_poll_allowed_count": sum(
            1
            for run in existing
            if isinstance(run.get("observable_handle_policy"), dict)
            and run["observable_handle_policy"].get("monitor_poll_allowed") is True
        ),
        "blocker_required_count": sum(
            1
            for run in existing
            if isinstance(run.get("observable_handle_policy"), dict)
            and run["observable_handle_policy"].get("blocker_required_before_rerun")
            is True
        ),
    }


def _snapshot_rollout_labels(payload: dict[str, Any]) -> list[str]:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    labels: list[str] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        label = str(run.get("label") or "").strip()
        if label:
            labels.append(f"run:{label}")
    return labels[:20]


def append_status_rollout_event(
    payload: dict[str, Any],
    *,
    goal_id: str,
    runtime_root: Path,
    agent_id: str | None = None,
    todo_id: str | None = None,
) -> dict[str, Any]:
    status = _snapshot_rollout_status(payload)
    details = _snapshot_rollout_details(payload)
    event = build_rollout_event(
        goal_id=goal_id,
        event_kind="benchmark_status",
        agent_id=agent_id,
        todo_id=todo_id,
        status=status,
        labels=_snapshot_rollout_labels(payload),
        summary=(
            "benchmark status snapshot recorded: "
            f"runs={details['run_count']} existing={details['exists_count']} "
            f"alive={details['pid_alive_count']} compacts={details['compact_result_count']} "
            f"cleanup={details['cleanup_required_count']}"
        ),
        details=details,
    )
    appended = append_rollout_event(rollout_event_log_path(runtime_root, goal_id), event)
    payload["rollout_event"] = {
        "schema_version": appended["schema_version"],
        "event_id": appended["event_id"],
        "event_kind": appended["event_kind"],
        "recorded_at": appended["recorded_at"],
        "status": appended.get("status"),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize benchmark run dirs without emitting raw logs."
    )
    parser.add_argument("--run-root", required=True)
    parser.add_argument(
        "--label",
        action="append",
        required=True,
        help="Run directory label under --run-root. Repeat for multiple runs.",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Keyword to report as a boolean in tmux captures; content is not emitted.",
    )
    parser.add_argument("--max-compacts", type=int, default=12)
    parser.add_argument("--max-captures", type=int, default=3)
    parser.add_argument(
        "--record-rollout-event",
        action="store_true",
        help="Append a public-safe benchmark_status event to the LoopX rollout log.",
    )
    parser.add_argument("--goal-id", help="Goal id for --record-rollout-event.")
    parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".codex" / "loopx"),
        help="LoopX runtime root for --record-rollout-event.",
    )
    parser.add_argument("--agent-id", help="Optional public-safe agent id.")
    parser.add_argument("--todo-id", help="Optional structured todo id.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.record_rollout_event and not args.goal_id:
        parser.error("--record-rollout-event requires --goal-id")

    payload = build_snapshot(
        run_root=Path(args.run_root),
        labels=args.label,
        patterns=list(args.pattern),
        max_compacts=args.max_compacts,
        max_captures=args.max_captures,
    )
    if args.record_rollout_event:
        payload = append_status_rollout_event(
            payload,
            goal_id=args.goal_id,
            runtime_root=Path(args.runtime_root),
            agent_id=args.agent_id,
            todo_id=args.todo_id,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
