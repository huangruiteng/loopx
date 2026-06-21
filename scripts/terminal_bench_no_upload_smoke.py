#!/usr/bin/env python3
"""Launch or preview a public-safe Terminal-Bench no-upload smoke."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.terminal_bench import (  # noqa: E402
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_MODEL,
    TERMINAL_BENCH_DEFAULT_TASK,
    launch_terminal_bench_worker_materialization_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or launch the smallest Terminal-Bench no-upload worker "
            "materialization probe. Dry-run is the default."
        )
    )
    parser.add_argument("--dataset", default=TERMINAL_BENCH_DEFAULT_DATASET)
    parser.add_argument("--task-id", default=TERMINAL_BENCH_DEFAULT_TASK)
    parser.add_argument("--model", default=TERMINAL_BENCH_DEFAULT_MODEL)
    parser.add_argument(
        "--mode",
        choices=("codex-goal-mode", "hardened-codex"),
        default="codex-goal-mode",
    )
    parser.add_argument(
        "--jobs-dir",
        default="runs/terminal-bench/jobs",
        help="Private jobs directory for executed probes.",
    )
    parser.add_argument(
        "--run-root",
        default="runs/terminal-bench/worker-materialization-probe",
        help="Private run directory for executed probe artifacts.",
    )
    parser.add_argument("--job-name")
    parser.add_argument("--wait-seconds", type=int, default=20)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually launch the no-upload probe. Without this flag only a command-shape preview is emitted.",
    )
    parser.add_argument("--output-json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload: dict[str, Any] = launch_terminal_bench_worker_materialization_probe(
        jobs_dir=args.jobs_dir,
        run_root=args.run_root,
        dataset=args.dataset,
        task_id=args.task_id,
        model=args.model,
        mode=args.mode,
        job_name=args.job_name,
        wait_seconds=args.wait_seconds,
        execute=args.execute,
    )
    payload["developer_entrypoint"] = {
        "name": "terminal_bench_no_upload_smoke",
        "dry_run_default": True,
        "public_safe": True,
    }
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
