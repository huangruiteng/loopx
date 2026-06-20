#!/usr/bin/env python3
"""Emit a compact public-safe status snapshot for benchmark run directories."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any


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
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_snapshot(
        run_root=Path(args.run_root),
        labels=args.label,
        patterns=list(args.pattern),
        max_compacts=args.max_compacts,
        max_captures=args.max_captures,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
