#!/usr/bin/env python3
"""Build a public-safe index for benchmark debug bundle artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "loopx_benchmark_debug_bundle_import_v0"
ALLOWED_SUFFIXES = (".compact.json", ".public.json")
FILENAME_WARNING_MARKERS = (
    "raw",
    "private",
    "local",
    "trajectory",
    "verifier",
    "stderr",
    "stdout",
    "log",
)

SUMMARY_KEYS = (
    "schema_version",
    "benchmark_id",
    "case_id",
    "mode",
    "runner_return_status",
    "official_score_status",
    "official_score",
    "official_task_score",
    "score_failure_attribution",
    "first_blocker",
    "failure_class",
    "terminal_closeout",
    "ready_for_compact_result_ingest",
    "ready_for_compact_failure_marker",
    "compact_failure_class",
    "max_round_observed",
    "followup_prompt_count",
    "last_decision",
    "stop_reason",
    "command_count",
    "event_count",
    "lifecycle_observed",
    "closeout_summary",
    "case_goal_state_init_status",
    "loopx_case_todo_id",
    "loopx_case_agent_id",
)

TODO_FLOW_KEYS = (
    "loopx_case_todo_id",
    "selected_p0_todo_id",
    "selected_todo_id",
    "case_todo_id",
    "todo_id",
    "claimed_todo_id",
    "claimed_by",
    "claimant",
    "todo_status",
    "final_todo_status",
    "selected_todo_status",
    "case_todo_status",
    "open_todo_count",
    "todo_open_count",
    "agent_open_count",
    "user_open_count",
    "remaining_goal_count",
    "todo_update_count",
    "closeout_status",
)

PHASE_COUNTER_ALIASES = {
    "quota_should_run": ("quota_should_run", "quota-should-run", "quota should-run"),
    "todo_claim": ("todo_claim", "todo-claim", "todo claim"),
    "todo_update": ("todo_update", "todo-update", "todo update"),
    "status": ("status",),
    "refresh_state": ("refresh_state", "refresh-state", "refresh state"),
    "quota_spend": ("quota_spend", "spend_slot", "spend-slot", "quota spend"),
    "validation": ("validation", "validate"),
    "case_result": ("case_result", "case-result", "result"),
}


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _public_relative_path(path: Path, source_dir: Path) -> str:
    try:
        return path.relative_to(source_dir).as_posix()
    except ValueError:
        return path.name


def _is_allowed_artifact(path: Path) -> bool:
    return path.name.endswith(ALLOWED_SUFFIXES)


def _walk_allowed_artifacts(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.rglob("*") if path.is_file() and _is_allowed_artifact(path))


def _unwrap_compact_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    compact = payload.get("compact_benchmark_run")
    if isinstance(compact, dict):
        return compact
    return payload


def _safe_summary(payload: dict[str, Any]) -> dict[str, Any]:
    main = _unwrap_compact_payload(payload)
    return {key: main.get(key) for key in SUMMARY_KEYS if key in main}


def _dict_values_by_key(payload: Any, keys: Iterable[str], *, limit: int = 4) -> dict[str, Any]:
    wanted = set(keys)
    found: dict[str, list[Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in wanted and isinstance(child, (str, int, float, bool, type(None))):
                    bucket = found.setdefault(key, [])
                    if child not in bucket and len(bucket) < limit:
                        bucket.append(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return {key: values[0] if len(values) == 1 else values for key, values in found.items()}


def _event_kind_counts(payload: dict[str, Any]) -> dict[str, int]:
    main = _unwrap_compact_payload(payload)
    counts = payload.get("event_kind_counts")
    if not isinstance(counts, dict):
        counts = main.get("event_kind_counts")
    if not isinstance(counts, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, value in counts.items():
        if isinstance(value, int):
            normalized[str(key)] = value
    return normalized


def _phase_counters(payload: dict[str, Any]) -> dict[str, int]:
    event_counts = _event_kind_counts(payload)
    phases = {phase: 0 for phase in PHASE_COUNTER_ALIASES}
    for event_key, count in event_counts.items():
        normalized_key = event_key.lower().replace(".", "_")
        for phase, aliases in PHASE_COUNTER_ALIASES.items():
            if any(alias in normalized_key for alias in aliases):
                phases[phase] += count

    interaction = payload.get("interaction_counters")
    main = _unwrap_compact_payload(payload)
    if not isinstance(interaction, dict):
        interaction = main.get("interaction_counters")
    if isinstance(interaction, dict):
        phases["status"] += int(interaction.get("goal_harness_state_reads") or 0)
        phases["todo_update"] += int(interaction.get("goal_harness_case_state_writes") or 0)
    return {key: value for key, value in phases.items() if value}


def _filename_marker_warning(relative_path: str) -> list[str]:
    lower_parts = [part.lower() for part in Path(relative_path).parts]
    warnings: list[str] = []
    for marker in FILENAME_WARNING_MARKERS:
        if any(marker in part for part in lower_parts):
            warnings.append(marker)
    return warnings


def build_debug_bundle_index(source_dir: Path, *, max_items: int | None = None) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    artifact_paths = _walk_allowed_artifacts(source_dir)
    if max_items is not None:
        artifact_paths = artifact_paths[:max_items]

    items: list[dict[str, Any]] = []
    readable_count = 0
    filename_marker_warning_count = 0
    for path in artifact_paths:
        relative_path = _public_relative_path(path, source_dir)
        raw_bytes = path.read_bytes()
        item: dict[str, Any] = {
            "path": relative_path,
            "bytes": len(raw_bytes),
            "sha256_12": hashlib.sha256(raw_bytes).hexdigest()[:12],
        }
        warnings = _filename_marker_warning(relative_path)
        if warnings:
            item["filename_marker_warning"] = warnings
            filename_marker_warning_count += 1

        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            item.update(
                {
                    "readable": False,
                    "error_type": type(exc).__name__,
                }
            )
            items.append(item)
            continue

        readable_count += 1
        item["readable"] = True
        item["summary"] = _safe_summary(payload)
        counters: dict[str, Any] = {}
        event_counts = _event_kind_counts(payload)
        if event_counts:
            counters["event_kind_counts"] = event_counts
        phase_counters = _phase_counters(payload)
        if phase_counters:
            counters["phase_counters"] = phase_counters
        interaction = payload.get("interaction_counters")
        if not isinstance(interaction, dict):
            interaction = _unwrap_compact_payload(payload).get("interaction_counters")
        if isinstance(interaction, dict):
            counters["interaction_counters"] = interaction
        if counters:
            item["counters"] = counters
        todo_flow = _dict_values_by_key(payload, TODO_FLOW_KEYS)
        if todo_flow:
            item["todo_flow"] = todo_flow
        items.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_boundary": {
            "source_dir_recorded": False,
            "absolute_paths_recorded": False,
            "local_paths_recorded": False,
            "copied_patterns": ["*.compact.json", "*.public.json"],
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "raw_logs_read": False,
            "verifier_output_tail_read": False,
            "credentials_read": False,
        },
        "artifact_count": len(items),
        "readable_count": readable_count,
        "malformed_count": len(items) - readable_count,
        "filename_marker_warning_count": filename_marker_warning_count,
        "items": items,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--fail-on-empty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.source_dir.exists() or not args.source_dir.is_dir():
        raise SystemExit(f"source dir does not exist or is not a directory: {args.source_dir}")
    payload = build_debug_bundle_index(args.source_dir, max_items=args.max_items)
    if args.fail_on_empty and payload["artifact_count"] == 0:
        raise SystemExit("no compact/public benchmark artifacts found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_json_dump(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
