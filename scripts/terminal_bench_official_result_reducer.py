#!/usr/bin/env python3
"""Reduce official Terminal-Bench result metadata into compact public evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


FORBIDDEN_RAW_KEYS = frozenset(
    {
        "command",
        "commands",
        "instruction",
        "log",
        "logs",
        "messages",
        "output",
        "parser_results",
        "prompt",
        "recording_path",
        "stderr",
        "stdout",
        "trajectory",
    }
)


def _load_json_object(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _forbidden_keys(data: Any) -> list[str]:
    found: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key) in FORBIDDEN_RAW_KEYS:
                    found.add(str(key))
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return sorted(found)


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    safe: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        if "/" in item or "\\" in item or len(item) > 100:
            continue
        safe.append(item)
    return safe


def _duration_seconds(start: Any, end: Any) -> float | None:
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        return None
    return max(0.0, (end_dt - start_dt).total_seconds())


def build_reduction(
    *,
    results_json: str | None,
    run_metadata_json: str,
    benchmark_id: str,
    metadata_only: bool,
) -> dict[str, Any]:
    metadata = _load_json_object(run_metadata_json)
    results: dict[str, Any] = {}
    if not metadata_only and results_json:
        results = _load_json_object(results_json)
    forbidden = sorted(set(_forbidden_keys(results)) | set(_forbidden_keys(metadata)))
    if forbidden:
        return {
            "schema_version": "terminal_bench_official_result_reducer_v0",
            "ok": False,
            "rejection_reason": "raw_or_private_result_fields_present",
            "forbidden_keys": forbidden,
            "boundary": {
                "raw_values_recorded": False,
                "private_paths_recorded": False,
                "command_argv_recorded": False,
            },
        }

    task_ids = _safe_string_list(metadata.get("task_ids"))
    resolved_ids = _safe_string_list(results.get("resolved_ids"))
    unresolved_ids = _safe_string_list(results.get("unresolved_ids"))
    run_id = metadata.get("run_id") or results.get("id")
    run_duration = _duration_seconds(metadata.get("start_time"), metadata.get("end_time"))
    accuracy = results.get("accuracy")
    if accuracy is None:
        accuracy = metadata.get("accuracy")

    return {
        "schema_version": "terminal_bench_official_result_reducer_v0",
        "ok": True,
        "evidence_kind": (
            "official_run_metadata_only"
            if metadata_only
            else "official_top_level_result_summary"
        ),
        "benchmark_id": benchmark_id,
        "run_id": Path(str(run_id)).name if run_id is not None else None,
        "agent_name": metadata.get("agent_name"),
        "model_name": metadata.get("model_name"),
        "accuracy": accuracy,
        "n_resolved": results.get("n_resolved"),
        "n_unresolved": results.get("n_unresolved"),
        "dataset_size": metadata.get("dataset_size"),
        "n_attempts": metadata.get("n_attempts"),
        "n_concurrent_trials": metadata.get("n_concurrent_trials"),
        "no_rebuild": metadata.get("no_rebuild"),
        "cleanup": metadata.get("cleanup"),
        "task_ids": task_ids,
        "resolved_ids": resolved_ids,
        "unresolved_ids": unresolved_ids,
        "task_count": len(task_ids) or metadata.get("dataset_size"),
        "run_duration_seconds": run_duration,
        "source_contract": {
            "results_json": (
                "not_read_metadata_only"
                if metadata_only
                else "official_top_level_summary_only"
            ),
            "run_metadata_json": "official_metadata_allowed_fields_only",
            "trial_level_results_json": "not_read",
            "raw_field_rejection": sorted(FORBIDDEN_RAW_KEYS),
            "score_resolution": (
                "official_metadata_accuracy"
                if metadata_only
                else "official_top_level_result_accuracy"
            ),
        },
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_read": False,
            "private_paths_recorded": False,
            "command_argv_recorded": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce official Terminal-Bench result metadata into compact public "
            "evidence without recording raw task text, logs, trajectories, paths, "
            "or command argv."
        )
    )
    parser.add_argument("--results-json")
    parser.add_argument("--run-metadata-json", required=True)
    parser.add_argument("--benchmark-id", default="terminal-bench@2.0")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help=(
            "Read only run_metadata.json. Use this when official results.json "
            "contains trial-level raw fields such as instruction or recording_path."
        ),
    )
    parser.add_argument("--output-json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if not args.metadata_only and not args.results_json:
        parser.error("provide --results-json unless --metadata-only is set")

    payload = build_reduction(
        results_json=args.results_json,
        run_metadata_json=args.run_metadata_json,
        benchmark_id=args.benchmark_id,
        metadata_only=args.metadata_only,
    )
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
