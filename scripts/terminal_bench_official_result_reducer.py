#!/usr/bin/env python3
"""Reduce official Terminal-Bench result metadata into compact public evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import compact_benchmark_run  # noqa: E402


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
SAFE_TRIAL_SUMMARY_KEYS = frozenset(
    {
        "failure_mode",
        "is_resolved",
        "task_id",
        "total_input_tokens",
        "total_output_tokens",
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


def _safe_trial_summary(results: dict[str, Any]) -> dict[str, Any]:
    rows = results.get("results")
    if not isinstance(rows, list):
        return {
            "trial_count": 0,
            "failure_modes": {},
            "resolved_trial_count": 0,
            "unresolved_trial_count": 0,
            "token_totals": {"input": None, "output": None},
        }
    failure_modes: dict[str, int] = {}
    resolved = 0
    unresolved = 0
    input_total = 0
    output_total = 0
    input_seen = False
    output_seen = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        failure_mode = row.get("failure_mode")
        if isinstance(failure_mode, str) and failure_mode:
            failure_modes[failure_mode] = failure_modes.get(failure_mode, 0) + 1
        if row.get("is_resolved") is True:
            resolved += 1
        elif row.get("is_resolved") is False:
            unresolved += 1
        if isinstance(row.get("total_input_tokens"), int):
            input_total += row["total_input_tokens"]
            input_seen = True
        if isinstance(row.get("total_output_tokens"), int):
            output_total += row["total_output_tokens"]
            output_seen = True
    return {
        "trial_count": len(rows),
        "failure_modes": failure_modes,
        "resolved_trial_count": resolved,
        "unresolved_trial_count": unresolved,
        "token_totals": {
            "input": input_total if input_seen else None,
            "output": output_total if output_seen else None,
        },
    }


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
    mode: str,
    metadata_only: bool,
) -> dict[str, Any]:
    metadata = _load_json_object(run_metadata_json)
    results: dict[str, Any] = {}
    if not metadata_only and results_json:
        results = _load_json_object(results_json)
    # Official results.json commonly contains a trial-level "results" array with
    # instruction, parser output, and recording paths.  The public reducer only
    # projects top-level run summary fields from that file.
    top_level_results = {
        key: value for key, value in results.items() if key != "results"
    }
    forbidden = sorted(
        set(_forbidden_keys(top_level_results)) | set(_forbidden_keys(metadata))
    )
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
    resolved_ids = _safe_string_list(top_level_results.get("resolved_ids"))
    unresolved_ids = _safe_string_list(top_level_results.get("unresolved_ids"))
    run_id = metadata.get("run_id") or top_level_results.get("id")
    run_duration = _duration_seconds(metadata.get("start_time"), metadata.get("end_time"))
    accuracy = top_level_results.get("accuracy")
    if accuracy is None:
        accuracy = metadata.get("accuracy")
    trial_summary = _safe_trial_summary(results) if not metadata_only else _safe_trial_summary({})

    accuracy_number = (
        float(accuracy)
        if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool)
        else None
    )
    score_completed = accuracy_number is not None
    case_id = task_ids[0] if len(task_ids) == 1 else Path(str(run_id)).name
    failure_labels: list[str] = []
    failure_class = "none"
    if score_completed and accuracy_number < 1.0:
        failure_class = "official_verifier_solution_failure"
        failure_labels.append(failure_class)
    benchmark_run = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "case_ids": task_ids,
        "mode": mode,
        "job_name": Path(str(run_id)).name if run_id is not None else "",
        "runner_return_status": "completed",
        "official_score_status": "completed" if score_completed else "missing",
        "official_score": accuracy_number,
        "official_score_source": (
            "terminal_bench_run_metadata_accuracy"
            if metadata_only
            else "terminal_bench_top_level_accuracy"
        ),
        "official_task_score": (
            {
                "kind": "terminal_bench_accuracy",
                "passed": accuracy_number == 1.0,
                "value": accuracy_number,
            }
            if score_completed
            else None
        ),
        "score_failure_attribution": failure_class,
        "failure_attribution_labels": failure_labels,
        "loopx_inside_case": False,
        "leaderboard_evidence": False,
        "submit_eligible": False,
        "agent_model": metadata.get("model_name"),
        "trial_count": metadata.get("dataset_size"),
        "trials": [
            {
                "task_id": task_id,
                "trial_name": task_id,
                "reward": {"reward": accuracy_number},
                "verifier_reward_present": score_completed,
                "trajectory_present": False,
                "trial_result_present": score_completed,
                "official_zero_observation": {
                    "schema_version": "terminal_bench_official_zero_observation_v0",
                    "detected": score_completed and accuracy_number == 0.0,
                    "reward_value": accuracy_number,
                    "verifier_completed": score_completed,
                    "raw_logs_read": False,
                    "raw_trace_recorded": False,
                    "task_text_read": False,
                },
            }
            for task_id in task_ids[:3]
        ],
        "source_runner": "terminal-bench",
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "upload_invoked": False,
            "model_api_invoked": False,
            "local_paths_recorded": False,
        },
    }
    compact_run = compact_benchmark_run(benchmark_run) or benchmark_run
    if case_id and "case_id" not in compact_run:
        compact_run["case_id"] = case_id
    if task_ids and "case_ids" not in compact_run:
        compact_run["case_ids"] = task_ids

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
        "n_resolved": top_level_results.get("n_resolved"),
        "n_unresolved": top_level_results.get("n_unresolved"),
        "trial_summary": trial_summary,
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
        "compact_benchmark_run": compact_run,
        "source_contract": {
            "results_json": (
                "not_read_metadata_only"
                if metadata_only
                else "official_top_level_summary_only"
            ),
            "run_metadata_json": "official_metadata_allowed_fields_only",
            "trial_level_results_json": (
                "not_read"
                if metadata_only
                else "safe_whitelisted_fields_only"
            ),
            "trial_summary_allowed_keys": sorted(SAFE_TRIAL_SUMMARY_KEYS),
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
    parser.add_argument("--mode", default="terminal_bench_host_codex_app_server_goal")
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
        mode=args.mode,
        metadata_only=args.metadata_only,
    )
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
