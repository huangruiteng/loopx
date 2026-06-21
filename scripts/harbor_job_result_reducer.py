#!/usr/bin/env python3
"""Reduce a Harbor job result into compact public benchmark evidence."""

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
    build_terminal_bench_harbor_result_benchmark_run,
)
from loopx.status import compact_benchmark_run  # noqa: E402


SCHEMA_VERSION = "harbor_job_result_reducer_v0"


def build_reduction(
    *,
    job_dir: Path,
    benchmark_id: str,
    mode: str,
) -> dict[str, Any]:
    run = build_terminal_bench_harbor_result_benchmark_run(job_dir, mode=mode)
    run["benchmark_id"] = benchmark_id
    run["harbor_reducer"] = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id_overridden_by_cli": True,
        "source_adapter": "harbor_job_result_via_terminal_bench_adapter",
    }
    compact = compact_benchmark_run(run)
    if not compact:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "first_blocker": "harbor_job_result_not_compactable",
            "boundary": {
                "raw_logs_read": False,
                "raw_task_text_read": False,
                "trajectory_read": False,
                "private_paths_recorded": False,
            },
        }
    compact["harbor_reducer"] = run["harbor_reducer"]
    compact["boundary"] = {
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
        "private_paths_recorded": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "first_blocker": "",
        "compact_benchmark_run": compact,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce a completed Harbor job directory into compact public-safe "
            "benchmark evidence."
        )
    )
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--benchmark-id", required=True)
    parser.add_argument("--mode", default="harbor_observed")
    parser.add_argument("--output-json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_reduction(
        job_dir=Path(args.job_dir),
        benchmark_id=args.benchmark_id,
        mode=args.mode,
    )
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        sort_keys=True,
    )
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
