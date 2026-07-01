from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .benchmark_core import (
    classify_benchmark_artifact_path,
    classify_product_mode_main_table_pair,
)
from .benchmark_adapters.skillsbench_signals import (
    build_skillsbench_solution_quality_signals,
)


BENCHMARK_RUN_LEDGER_SCHEMA_VERSION = "benchmark_run_ledger_v0"
BENCHMARK_RUN_LEDGER_CURRENT_AGGREGATE_SCHEMA_VERSION = (
    "benchmark_run_ledger_current_aggregate_v0"
)
BENCHMARK_RUN_LEDGER_DEFAULT_PATH = Path(
    "docs/research/long-horizon-agent-benchmarks/benchmark-run-ledger.json"
)
DEFAULT_CODEX_GOAL_MODE_REPAIR_MODEL_ROUTE = "gpt-5.5"
DEFAULT_AGENT_TIMEOUT_REPAIR_MULTIPLIER = 8
DEFAULT_AGENT_SETUP_TIMEOUT_REPAIR_MULTIPLIER = 8
DEFAULT_CODEX_SETUP_TIMEOUT_REPAIR_INSTALL_STRATEGY = "require_existing_codex"
RUNTIME_CODEX_INSTALL_STRATEGY = "runtime_install_if_missing"
LEDGER_LOGICAL_BACKFILL_FIELDS = (
    "artifact_refs",
    "solution_quality_signals",
    "round_reward_count",
    "round_success_observed",
    "max_rounds_budget",
    "official_feedback_blinded",
    "reward_feedback_forwarded",
    "task_setup_preflight",
    "task_staging",
)
TERMINAL_BENCH_JOB_CASE_ARM_MARKERS = (
    "_codex_goal_mode_baseline",
    "_codex_loopx_treatment",
    "_codex_loopx",
    "_hardened_codex_baseline",
    "_baseline",
    "_treatment",
)
PRIVATE_ARTIFACT_REF_PATH_MARKERS = (
    ".local/",
    "/private/",
    "private-benchmark-jobs",
    "/Users/",
    "/Volumes/",
    "/var/folders/",
    "/tmp/",
)
PUBLIC_LEDGER_LINEAGE_RESULT_FILENAMES = {
    "benchmark-run.json",
    "benchmark_run.json",
    "compact-run.json",
    "loopx-worker-benchmark-run.json",
    "result.json",
    "skillsbench-compact-benchmark-run-v0.json",
}
PRIVATE_ARTIFACT_REF_PATH_PARTS = {
    ".local",
    "private",
    "private-benchmark-jobs",
    "users",
    "volumes",
    "var",
    "tmp",
}


def _now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _compact_text(value: Any, *, limit: int = 160) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _compact_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _compact_text(item, limit=120)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _compact_round_reward_records(value: Any, *, limit: int = 32) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    records: list[dict[str, Any]] = []
    seen_rounds: set[int] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        agent_round = item.get("agent_round")
        if (
            not isinstance(agent_round, int)
            or isinstance(agent_round, bool)
            or agent_round <= 0
            or agent_round in seen_rounds
        ):
            continue
        seen_rounds.add(agent_round)
        record: dict[str, Any] = {"agent_round": agent_round}
        for field in ("reward_present", "passed"):
            if isinstance(item.get(field), bool):
                record[field] = item[field]
        reward = item.get("reward")
        if isinstance(reward, (int, float)) and not isinstance(reward, bool):
            record["reward"] = float(reward)
        tool_calls = item.get("tool_calls")
        if (
            isinstance(tool_calls, int)
            and not isinstance(tool_calls, bool)
            and tool_calls >= 0
        ):
            record["tool_calls"] = tool_calls
        records.append(record)
        if len(records) >= limit:
            break
    return sorted(records, key=lambda record: record["agent_round"])


def _codex_acp_runtime_preflight_passed(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("codex_acp_runtime_launch_preflight") is True:
        return True
    return (
        _compact_text(value.get("codex_acp_runtime_launch_preflight_status"), limit=80)
        == "passed"
    )


def _compact_task_staging(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in (
        "staged",
        "include_task_skills",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
        "dockerfile_pip_bootstrap_patch_applied",
        "dockerfile_package_bootstrap_risk_preflight_blocked",
        "app_skills_mount_patch_applied",
        "apt_retry_patch_applied",
        "apt_risk_preflight_blocked",
        "bootstrap_light_preflight_blocked",
        "bootstrap_light_fail_fast_defaulted",
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_uv_bootstrap_mirror_patch_required",
        "verifier_uv_bootstrap_mirror_patch_applied",
        "verifier_bootstrap_risk_preflight_blocked",
        "dockerfile_apache_archive_mirror_patch_required",
        "dockerfile_apache_archive_mirror_patch_applied",
        "dockerfile_apache_archive_raw_url_recorded",
        "dockerfile_maven_mirror_patch_required",
        "dockerfile_maven_mirror_patch_applied",
        "dockerfile_maven_mirror_raw_url_recorded",
        "codex_acp_runtime_tools_patch_applied",
        "task_skills_removed",
        "original_task_mutated",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "dockerfile_pip_index_host",
        "bootstrap_light_blocker_kind",
        "verifier_uv_bootstrap_version",
        "verifier_uv_bootstrap_mirror_host",
        "dockerfile_apache_archive_mirror_host",
        "dockerfile_maven_mirror_host",
    ):
        text = _compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    count = value.get("bootstrap_light_blocking_field_count")
    if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
        compact["bootstrap_light_blocking_field_count"] = count
    cap = value.get("resource_cap_patch")
    if isinstance(cap, dict):
        safe_cap: dict[str, Any] = {}
        for field in ("applied", "original_task_mutated"):
            if isinstance(cap.get(field), bool):
                safe_cap[field] = cap[field]
        for field in ("host_cpus", "requested_cpus", "effective_cpus"):
            raw = cap.get(field)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                safe_cap[field] = raw
        reason = _compact_text(cap.get("reason"), limit=120)
        if reason:
            safe_cap["reason"] = reason
        if safe_cap:
            compact["resource_cap_patch"] = safe_cap
    return compact


def _compact_task_setup_preflight(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "status",
        "sandbox",
        "task_id",
        "first_blocker",
        "alternate_source_kind",
        "selection_recommendation",
    ):
        text = _compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "raw_task_text_read",
        "raw_logs_read",
        "raw_trajectory_read",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
        "verifier_present",
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_external_download_risk_detected",
        "verifier_package_install_risk_detected",
        "dockerfile_present",
        "canonical_task_present",
        "alternate_source_supported_by_runner",
        "task_source_path_recorded",
        "task_source_content_recorded",
        "bootstrap_light_candidate_eligible",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    text = _compact_text(value.get("verifier_uv_bootstrap_version"), limit=140)
    if text:
        compact["verifier_uv_bootstrap_version"] = text
    nearest_ids = value.get("nearest_canonical_task_ids")
    if isinstance(nearest_ids, list):
        compact_nearest: list[str] = []
        for item in nearest_ids[:5]:
            text = _compact_text(item, limit=120)
            if text:
                compact_nearest.append(text)
        if compact_nearest:
            compact["nearest_canonical_task_ids"] = compact_nearest
    verifier_categories = value.get("verifier_bootstrap_risk_categories")
    if isinstance(verifier_categories, list):
        compact_categories: list[str] = []
        for item in verifier_categories[:5]:
            text = _compact_text(item, limit=120)
            if text:
                compact_categories.append(text)
        if compact_categories:
            compact["verifier_bootstrap_risk_categories"] = compact_categories
    return compact


def _compact_compose_setup_diagnostic(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "status",
        "route",
        "failure_class",
        "runner_prerequisite_status",
        "task_setup_preflight_status",
        "runner_error_len_bucket",
        "next_diagnostic_action",
    ):
        text = _compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "compose_setup_failure",
        "unclassified_compose_failure",
        "docker_daemon_unavailable",
        "volume_mount_failure",
        "environment_setup_failure",
        "agent_rounds_started",
        "official_score_missing",
        "official_result_json_materialized",
        "case_attempt_budget_should_count",
        "runner_launch_preflight_passed",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_uv_bootstrap_mirror_patch_required",
        "verifier_uv_bootstrap_mirror_patch_applied",
        "staged_task_prepared",
        "task_skills_removed",
        "codex_acp_runtime_tools_patch_applied",
        "resource_cap_applied",
        "raw_error_recorded",
        "raw_logs_read",
        "raw_task_text_read",
        "raw_trajectory_read",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "heartbeat_count",
        "controller_action_decision_count",
        "trajectory_round_count",
        "trajectory_tool_call_count",
        "loopx_cli_call_count",
        "round_reward_count",
        "progress_completed_trials",
        "progress_errored_trials",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    patterns = _compact_list(value.get("fingerprint_matched_patterns"), limit=8)
    if patterns:
        compact["fingerprint_matched_patterns"] = patterns
    return compact


def _compact_positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _compact_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _round_reward_best_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        agent_round = record.get("agent_round")
        reward = record.get("reward")
        if (
            not isinstance(agent_round, int)
            or isinstance(agent_round, bool)
            or agent_round <= 0
            or not isinstance(reward, (int, float))
            or isinstance(reward, bool)
        ):
            continue
        numeric_records.append(
            {
                "agent_round": agent_round,
                "reward": float(reward),
                "passed": (
                    record.get("passed")
                    if isinstance(record.get("passed"), bool)
                    else reward >= 1
                ),
            }
        )
    if not numeric_records:
        return {}
    by_round = sorted(numeric_records, key=lambda item: item["agent_round"])
    best = max(by_round, key=lambda item: (item["reward"], -item["agent_round"]))
    final = by_round[-1]
    return {
        "final_round": final["agent_round"],
        "final_round_reward": final["reward"],
        "final_round_passed": final["passed"],
        "best_reward_round": best["agent_round"],
        "best_round_reward": best["reward"],
        "best_round_passed": best["passed"],
        "best_round_is_final": final["reward"] == best["reward"],
    }


def _round_reward_summary(run: dict[str, Any]) -> str:
    records = run.get("round_rewards")
    if not isinstance(records, list):
        return ""
    parts: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        agent_round = record.get("agent_round")
        if not isinstance(agent_round, int) or isinstance(agent_round, bool):
            continue
        reward = record.get("reward")
        if isinstance(reward, (int, float)) and not isinstance(reward, bool):
            reward_text = f"{float(reward):g}"
        elif record.get("reward_present") is False:
            reward_text = "missing"
        else:
            reward_text = "unknown"
        if record.get("passed") is True:
            reward_text += "*"
        parts.append(f"{agent_round}:{reward_text}")
    return ",".join(parts)


def _attempt_label_from_accounting(run: dict[str, Any]) -> str:
    accounting = (
        run.get("attempt_accounting")
        if isinstance(run.get("attempt_accounting"), dict)
        else {}
    )
    if not accounting:
        return ""
    for field, label in (
        ("official_score_attempt_countable", "official_score_attempt"),
        ("verifier_attempt_countable", "verifier_attempt"),
        ("solver_attempt_countable", "solver_attempt"),
        ("case_attempt_countable", "case_attempt"),
        ("launcher_attempt_countable", "launcher_attempt"),
    ):
        if accounting.get(field) is True:
            return label
    return ""


def _compact_first_from_lists(
    benchmark_run: dict[str, Any],
    *field_names: str,
) -> str:
    for field_name in field_names:
        for item in _compact_list(benchmark_run.get(field_name), limit=8):
            if item and item not in {"none", "None"}:
                return item
    return ""


def _compact_counter(benchmark_run: dict[str, Any], field_name: str) -> int:
    value = benchmark_run.get(field_name)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _source_schema(payload: dict[str, Any]) -> str:
    return _compact_text(payload.get("schema_version"), limit=120)


def _run_identity_tokens(run: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in ("arm_id", "mode", "route"):
        text = _compact_text(run.get(field), limit=160)
        if text:
            tokens.add(text.lower())
    contract = run.get("benchmark_loop_contract")
    if isinstance(contract, dict):
        for field in ("route", "protocol_id"):
            text = _compact_text(contract.get(field), limit=160)
            if text:
                tokens.add(text.lower())
    return tokens


def _run_matches_token(run: dict[str, Any], *needles: str) -> bool:
    tokens = _run_identity_tokens(run)
    for needle in needles:
        lower_needle = needle.lower()
        if lower_needle in tokens:
            return True
        if any(lower_needle in token for token in tokens):
            return True
    return False


def _ledger_missing_value(value: Any) -> bool:
    return value is None or value in ("", [], {})


def _ledger_logical_backfill_key(run: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for field in ("run_group_id", "arm_id", "job_name", "mode"):
        text = _compact_text(run.get(field), limit=220)
        if not text:
            return ()
        values.append(text)
    return tuple(values)


def _ledger_result_equivalent_for_backfill(
    run: dict[str, Any],
    entry: dict[str, Any],
) -> bool:
    for field in ("status", "score_status", "official_passed", "failure_class"):
        if run.get(field) != entry.get(field):
            return False
    return run.get("official_score") == entry.get("official_score")


def _merge_ledger_logical_backfill_fields(
    run: dict[str, Any],
    entry: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    merged = dict(run)
    changed = False
    for field in LEDGER_LOGICAL_BACKFILL_FIELDS:
        if _ledger_missing_value(merged.get(field)) and not _ledger_missing_value(
            entry.get(field)
        ):
            merged[field] = entry[field]
            changed = True
    return merged, changed


def _product_mode_baseline_run(run: dict[str, Any]) -> bool:
    return _run_matches_token(
        run,
        "raw-codex-autonomous-max5",
        "raw_codex_autonomous_max5",
        "skillsbench_raw_codex_autonomous_max5",
    )


def _product_mode_treatment_run(run: dict[str, Any]) -> bool:
    return _run_matches_token(
        run,
        "loopx-product-mode",
        "loopx_product_mode",
        "skillsbench_loopx_product_mode",
    )


def _compact_product_mode_pair_review(review: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "comparison_id",
        "main_table_claim_allowed",
        "product_mode_pair_complete",
        "claim_blocker",
        "benchmark_id",
        "case_id",
        "max_rounds_budget",
        "baseline_route_valid",
        "treatment_route_valid",
        "treatment_loopx_lifecycle_observed",
        "official_feedback_blinded",
    ):
        value = review.get(field)
        if value not in (None, "", []):
            compact[field] = value
    headline_metrics = review.get("headline_metrics")
    if isinstance(headline_metrics, list):
        compact["headline_metrics"] = [
            metric
            for metric in (_compact_text(item, limit=80) for item in headline_metrics)
            if metric
        ][:8]
    return compact


def _compact_product_mode_lifecycle_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = _compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "satisfied",
        "countable_treatment",
        "checkpoint_required",
        "orchestrated_driver_lifecycle_satisfied",
        "orchestrated_driver_counts_as_product_mode",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "state_read_count",
        "state_write_count",
        "checkpoint_count",
        "checkpoint_round",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    missing_reason = _compact_text(value.get("missing_reason"), limit=140)
    if missing_reason:
        compact["missing_reason"] = missing_reason
    execution_style = _compact_text(value.get("execution_style"), limit=120)
    if execution_style:
        compact["execution_style"] = execution_style
    return compact


def _compact_skillsbench_solution_quality_signals(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "source",
        "outcome_class",
        "rubric_miss_label_status",
    ):
        text = _compact_text(value.get(field), limit=120)
        if text:
            compact[field] = text
    for field in ("solution_action_labels", "rubric_miss_labels", "public_limits"):
        labels = _compact_list(value.get(field), limit=12)
        if labels:
            compact[field] = labels
    worker_activity = (
        value.get("worker_activity")
        if isinstance(value.get("worker_activity"), dict)
        else {}
    )
    compact_worker_activity: dict[str, Any] = {}
    for field in (
        "task_facing_activity_observed",
        "worker_turn_or_bridge_observed",
    ):
        if isinstance(worker_activity.get(field), bool):
            compact_worker_activity[field] = worker_activity[field]
    for field in (
        "tool_call_count",
        "bridge_task_facing_operation_count",
        "bridge_task_facing_success_count",
    ):
        raw = worker_activity.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact_worker_activity[field] = max(0, raw)
    if compact_worker_activity:
        compact["worker_activity"] = compact_worker_activity
    return compact


def _ledger_skillsbench_solution_quality_signals(
    benchmark_run: dict[str, Any],
    *,
    benchmark_id: str,
) -> dict[str, Any]:
    signals = _compact_skillsbench_solution_quality_signals(
        benchmark_run.get("solution_quality_signals")
    )
    if signals or not benchmark_id.lower().startswith("skillsbench"):
        return signals
    return _compact_skillsbench_solution_quality_signals(
        build_skillsbench_solution_quality_signals(benchmark_run)
    )


def _terminal_bench_case_id_from_job_name(
    *,
    benchmark_id: str,
    job_name: str,
) -> str:
    if not job_name:
        return ""
    if benchmark_id != "terminal-bench@2.0" and not job_name.startswith("terminal_bench_"):
        return ""
    remainder = job_name
    if remainder.startswith("terminal_bench_"):
        remainder = remainder[len("terminal_bench_") :]
    parts = remainder.split("_")
    while parts and parts[0].isdigit():
        parts.pop(0)
    if not parts:
        return ""
    remainder = "_".join(parts)
    for marker in TERMINAL_BENCH_JOB_CASE_ARM_MARKERS:
        marker_index = remainder.find(marker)
        if marker_index > 0:
            candidate = remainder[:marker_index]
            return candidate.replace("_", "-")
    return ""


def _relative_ref(value: str | Path | None, *, cwd: Path | None = None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    base = (cwd or Path.cwd()).resolve()
    if path.is_absolute():
        try:
            return path.resolve().relative_to(base).as_posix()
        except ValueError:
            return None
    return path.as_posix()


def _public_ledger_artifact_ref(
    value: str | Path | None,
    *,
    cwd: Path | None = None,
) -> str | None:
    ref = _relative_ref(value, cwd=cwd)
    if not ref:
        return None
    classification = classify_benchmark_artifact_path(ref)
    if classification.get("allowed_to_read") is not True:
        normalized = ref.replace("\\", "/").strip("/")
        parts = [part for part in normalized.split("/") if part]
        if (
            not normalized
            or ref.startswith("/")
            or ref.startswith("~")
            or ":" in normalized
            or len(parts) != len(normalized.split("/"))
            or any(part in {".", ".."} or part.startswith(".") for part in parts)
            or any(part.lower() in PRIVATE_ARTIFACT_REF_PATH_PARTS for part in parts)
            or classification.get("private_raw_surface") is True
        ):
            return None
        basename = _compact_text(classification.get("basename"), limit=160)
        if basename in PUBLIC_LEDGER_LINEAGE_RESULT_FILENAMES:
            return normalized
        if "." not in basename:
            return normalized
        return None
    normalized = ref.replace("\\", "/")
    if any(marker in normalized for marker in PRIVATE_ARTIFACT_REF_PATH_MARKERS):
        basename = _compact_text(classification.get("basename"), limit=160)
        return basename or None
    return normalized


def _case_ids(benchmark_run: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    case_id = _compact_text(benchmark_run.get("case_id"), limit=140)
    if case_id:
        ids.append(case_id)
    case_ids = benchmark_run.get("case_ids")
    if isinstance(case_ids, list):
        for item in case_ids:
            text = _compact_text(item, limit=140)
            if text and text not in ids:
                ids.append(text)
    if ids:
        return ids
    trials = benchmark_run.get("trials")
    if isinstance(trials, list):
        for trial in trials:
            if not isinstance(trial, dict):
                continue
            task_id = _compact_text(trial.get("task_id"), limit=140)
            if task_id and task_id not in ids:
                ids.append(task_id)
    if ids:
        return ids
    job_name = _compact_text(benchmark_run.get("job_name"), limit=140)
    fallback_case = _terminal_bench_case_id_from_job_name(
        benchmark_id=_compact_text(benchmark_run.get("benchmark_id"), limit=120),
        job_name=job_name,
    )
    if fallback_case:
        return [fallback_case]
    return [job_name] if job_name else ["unknown-case"]


def _official_score(benchmark_run: dict[str, Any]) -> tuple[float | int | None, bool | None]:
    official = (
        benchmark_run.get("official_task_score")
        if isinstance(benchmark_run.get("official_task_score"), dict)
        else {}
    )
    value = official.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        passed = official.get("passed")
        return value, passed if isinstance(passed, bool) else value >= 1
    value = benchmark_run.get("official_score")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, value >= 1
    return None, None


def _infer_arm_id_from_job_name(job_name: str) -> str:
    if not job_name:
        return ""
    if "codex_app_server_goal_baseline" in job_name:
        return "codex_app_server_goal_baseline"
    if "codex_goal_mode_baseline" in job_name:
        return "codex_goal_mode_baseline"
    if "hardened_codex_baseline" in job_name:
        return "hardened_codex_baseline"
    if "codex_loopx_treatment" in job_name:
        return "codex_loopx_treatment"
    if "loopx_automation_loop_treatment" in job_name:
        return "loopx_automation_loop_treatment"
    if job_name.endswith("_baseline") or "_baseline_" in job_name:
        return "baseline"
    if job_name.endswith("_treatment") or "_treatment_" in job_name:
        return "treatment"
    return ""


def _infer_arm_id(benchmark_run: dict[str, Any]) -> str:
    mode = _compact_text(benchmark_run.get("mode"), limit=120)
    if mode == "skillsbench_codex_app_server_goal_baseline":
        return "codex_app_server_goal_baseline"
    if mode == "codex_goal_mode_baseline":
        return "codex_goal_mode_baseline"
    if mode in {"hardened_codex_baseline", "hardened-codex"}:
        return "hardened_codex_baseline"
    if "automation_loop" in mode and "loopx" in mode:
        return "loopx_automation_loop_treatment"
    if "curated_skills" in mode:
        return "curated_skills_baseline"
    if mode in {"no_skills_baseline", "skillsbench_no_skills_baseline"}:
        return "no_skills_baseline"
    if "loopx" in mode or "codex-loopx" in mode:
        return "codex_loopx_treatment"
    from_job_name = _infer_arm_id_from_job_name(
        _compact_text(benchmark_run.get("job_name"), limit=160)
    )
    if from_job_name:
        return from_job_name
    return mode or "unknown_arm"


def _resolved_arm_id(benchmark_run: dict[str, Any], arm_id: str | None) -> str:
    inferred = _infer_arm_id(benchmark_run)
    explicit = _compact_text(arm_id, limit=120)
    if explicit in {"baseline", "treatment"} and inferred not in {"", "unknown_arm"}:
        return inferred
    return explicit or inferred


def _score_status(benchmark_run: dict[str, Any], score: float | int | None, passed: bool | None) -> str:
    if _source_schema(benchmark_run) == "terminal_bench_post_launch_materialization_v0":
        return "missing"
    explicit = _compact_text(benchmark_run.get("official_score_status"), limit=80)
    if explicit and explicit != "completed":
        return explicit
    if score is None:
        return "missing"
    return "passed" if passed else "failed"


_SKILLSBENCH_PRE_AGENT_SETUP_STATUS_LABELS = {
    "compose_setup_blocked_before_agent_rounds": (
        "skillsbench_compose_setup_blocked_before_agent_rounds"
    ),
    "runner_setup_blocked_before_agent_rounds": (
        "skillsbench_runner_setup_blocked_before_agent_rounds"
    ),
}


def _skillsbench_pre_agent_setup_failure_class(
    benchmark_run: dict[str, Any],
) -> str:
    diagnostic = (
        benchmark_run.get("compose_setup_diagnostic")
        if isinstance(benchmark_run.get("compose_setup_diagnostic"), dict)
        else {}
    )
    label = _SKILLSBENCH_PRE_AGENT_SETUP_STATUS_LABELS.get(
        _compact_text(diagnostic.get("status"), limit=120)
    )
    if not label:
        return ""
    mode = _compact_text(benchmark_run.get("mode"), limit=120)
    route = _compact_text(benchmark_run.get("route"), limit=120)
    if mode != "skillsbench_codex_app_server_goal_baseline" and route != (
        "codex-app-server-goal-baseline"
    ):
        return ""
    if diagnostic.get("agent_rounds_started") is True:
        return ""
    return label


def _failure_class(benchmark_run: dict[str, Any], score: float | int | None) -> str:
    if _source_schema(benchmark_run) == "terminal_bench_post_launch_materialization_v0":
        compact_failure = _compact_text(
            benchmark_run.get("compact_failure_class"),
            limit=120,
        )
        if compact_failure:
            return compact_failure
        marker = (
            benchmark_run.get("compact_failure_marker")
            if isinstance(benchmark_run.get("compact_failure_marker"), dict)
            else {}
        )
        marker_failure = _compact_text(marker.get("failure_class"), limit=120)
        if marker_failure:
            return marker_failure
        first_blocker = _compact_text(benchmark_run.get("first_blocker"), limit=120)
        return first_blocker or "post_launch_compact_result_missing"
    if score is not None and score != 0:
        return "none"
    if score is None:
        pre_agent_setup = _skillsbench_pre_agent_setup_failure_class(benchmark_run)
        if pre_agent_setup:
            return pre_agent_setup
    setup_blocker = _compact_first_from_lists(
        benchmark_run,
        "worker_setup_diagnostic_blockers",
        "worker_startup_blockers",
    )
    if setup_blocker:
        return setup_blocker
    labels = _compact_list(benchmark_run.get("failure_attribution_labels"), limit=12)
    if (
        "official_verifier_solution_failure" in labels
        and "worker_bridge_connected_official_score_failure" in labels
        and _compact_text(benchmark_run.get("worker_bridge_materialization_status"), limit=80)
        == "verified"
        and _compact_counter(benchmark_run, "worker_self_validation_official_score_mismatch_count") == 0
        and _compact_counter(benchmark_run, "worker_validation_scope_ambiguous_official_score_failure_count") == 0
        and _compact_counter(benchmark_run, "worker_submit_eligible_mismatch_count") == 0
        and _compact_counter(benchmark_run, "worker_bridge_writeback_loss_count") == 0
        and _compact_counter(benchmark_run, "worker_startup_blocker_count") == 0
        and _compact_counter(benchmark_run, "environment_setup_failure_before_worker_count") == 0
        and _compact_counter(benchmark_run, "pre_worker_agent_setup_failure_count") == 0
    ):
        return "official_verifier_solution_failure"
    for label in (
        "codex_model_access_unsupported_for_account",
        "codex_model_access_failure_before_solution_attempt",
        "agent_setup_timeout_before_worker_start",
        "agent_setup_failed_before_worker_start",
        "environment_setup_failed_before_worker",
        "worker_self_validation_official_score_mismatch",
        "worker_validation_scope_ambiguous_official_score_failure",
        "worker_bridge_connected_official_score_failure",
        "verifier_dependency_install_failure",
        "verifier_platform_probe_failure",
        "agent_timeout_before_solution_completion",
    ):
        if label in labels:
            return label
    attribution = _compact_text(
        benchmark_run.get("score_failure_attribution"),
        limit=120,
    )
    if attribution and attribution != "none":
        return attribution
    trial_exception = _trial_exception_failure_class(benchmark_run)
    if trial_exception:
        return trial_exception
    blocker = _compact_text(benchmark_run.get("first_blocker"), limit=120)
    if blocker:
        return blocker
    return "score_failure_unattributed" if score is not None else "score_missing"


def _trial_exception_failure_class(benchmark_run: dict[str, Any]) -> str:
    trials = benchmark_run.get("trials")
    if not isinstance(trials, list):
        return ""
    exceptions: list[str] = []
    for trial in trials:
        if not isinstance(trial, dict):
            continue
        exception_type = _compact_text(trial.get("exception_type"), limit=80)
        if exception_type and exception_type not in {"none", "None"}:
            exceptions.append(exception_type)
    if not exceptions:
        return ""
    lowered = {item.lower() for item in exceptions}
    if any("setup" in item and "timeout" in item for item in lowered):
        return "agent_setup_timeout_before_worker_start"
    if any("setup" in item for item in lowered):
        return "agent_setup_exception_before_solution_attempt"
    if any("timeout" in item for item in lowered):
        return "agent_timeout_before_solution_completion"
    return "agent_exception_before_solution_completion"


def _failure_scope(failure_class: str, score: float | int | None, passed: bool | None) -> str:
    if passed is True:
        return "passed"
    if failure_class in {
        "not_applicable_worker_materialization_probe",
        "not_applicable_worker_materialization_probe_no_trial_result",
    }:
        return "startup_surface"
    if failure_class in {
        "stale_active_job_without_trial_result",
        "detached_worker_ended_active_without_trial_result",
        "detached_worker_ended_without_trial_result",
        "post_launch_compact_result_missing",
    }:
        return "runner_or_setup"
    if score is None:
        return "score_missing"
    if failure_class == "score_failure_unattributed":
        return "attribution_required"
    if failure_class in {
        "none",
        "official_verifier_solution_failure",
        "official_score_zero_case_failure",
        "model_solution_failure",
        "agent_solution_failure",
        "task_solution_failure",
        "solution_incorrect",
        "agent_timeout_before_solution_completion",
        "agent_exception_before_solution_completion",
    }:
        return "case_or_solution"
    if failure_class.startswith("verifier_"):
        return "verifier_or_infra"
    return "runner_or_setup"


def _repair_route(
    failure_class: str,
    failure_scope: str,
    *,
    agent_model: str = "",
    round_success_observed: bool = False,
    runtime_preflight_passed: bool = False,
) -> dict[str, Any]:
    if (
        failure_class.startswith("codex_cli_")
        or failure_class.startswith("worker_install_failed")
    ):
        return {
            "repair_priority": "P0",
            "repair_class": "runner_codex_cli_materialization",
            "next_action": (
                "materialize an existing Codex CLI on the worker PATH or provide "
                "an equivalent launcher before rerunning; require a compact setup "
                "diagnostic that proves the Codex preflight reached ok instead of "
                "only a generic pre-worker agent failure"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "runner_codex_cli_materialization",
                "required_launch_overrides": {
                    "codex_install_strategy": "require_existing_codex",
                },
                "disallowed_launch_overrides": {
                    "codex_install_strategy": "runtime_install_if_missing",
                },
                "required_preflight": [
                    "codex_cli_existing_in_worker_or_fail_fast_blocker",
                    "worker_setup_diagnostic.schema_ok",
                    "worker_setup_diagnostic.first_blocker_or_ok",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
                "rerun_allowed_after_profile_applied": True,
            },
        }
    if failure_class == "environment_setup_failed_before_worker":
        return {
            "repair_priority": "P0",
            "repair_class": "benchmark_environment_setup_contract",
            "next_action": (
                "repair or preflight the benchmark environment setup layer before "
                "rerunning this case; the failure occurred before Codex/worker "
                "startup, so require compact environment setup readiness evidence "
                "instead of treating it as an adapter startup issue"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "benchmark_environment_setup_contract",
                "rerun_allowed_after_profile_applied": True,
                "required_preflight": [
                    "environment_setup_readiness_preflight_before_repeat",
                    "compact_environment_setup_failure_context",
                    "worker_not_started_before_environment_ready",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class in {
        "agent_setup_timeout_before_worker_start",
        "agent_setup_failed_before_worker_start",
        "agent_setup_exception_before_solution_attempt",
    }:
        return {
            "repair_priority": "P0",
            "repair_class": "runner_setup_timeout",
            "next_action": (
                "repair the Codex worker setup path before rerunning this case; "
                "do not rely on runtime Codex install inside Harbor setup; use "
                "a materialized launcher or require_existing_codex fail-fast probe "
                "with compact setup-readiness proof"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "runner_setup_timeout",
                "rerun_allowed_after_profile_applied": True,
                "disallowed_launch_overrides": {
                    "codex_install_strategy": RUNTIME_CODEX_INSTALL_STRATEGY,
                },
                "required_launch_overrides": {
                    "codex_install_strategy": (
                        DEFAULT_CODEX_SETUP_TIMEOUT_REPAIR_INSTALL_STRATEGY
                    ),
                    "agent_setup_timeout_multiplier": DEFAULT_AGENT_SETUP_TIMEOUT_REPAIR_MULTIPLIER,
                    "agent_timeout_multiplier": DEFAULT_AGENT_TIMEOUT_REPAIR_MULTIPLIER,
                },
                "required_preflight": [
                    "private_runner_launch_summary.agent_setup_readiness",
                    "private_runner_launch_summary.timeout_multiplier_policy",
                    "codex_cli_existing_in_worker_or_fail_fast_blocker",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class in {
        "codex_model_access_unsupported_for_account",
        "codex_model_access_failure_before_solution_attempt",
    }:
        blocked_model = _compact_text(agent_model, limit=120)
        recommended_model = (
            DEFAULT_CODEX_GOAL_MODE_REPAIR_MODEL_ROUTE
            if blocked_model != DEFAULT_CODEX_GOAL_MODE_REPAIR_MODEL_ROUTE
            else "current_local_codex_config_model_after_probe"
        )
        return {
            "repair_priority": "P0",
            "repair_class": "runner_model_access",
            "next_action": (
                "rerun only after selecting a Codex model route proven usable for this account"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "runner_model_access",
                "blocked_model_route": blocked_model,
                "recommended_model_route": recommended_model,
                "required_preflight": ["codex_cli_minimal_model_probe"],
                "rerun_allowed_after_profile_applied": True,
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if (
        failure_class.startswith("skillsbench_codex_acp_")
        and round_success_observed
        and runtime_preflight_passed
    ):
        return {
            "repair_priority": "P0",
            "repair_class": "skillsbench_codex_acp_post_success_finalization",
            "next_action": (
                "separate post-success Codex ACP transport/finalization closeout "
                "from runtime startup preflight: preserve the blinded round "
                "reward trace, keep official-score status separate, and rerun "
                "only after the compact finalization classifier is corrected"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "skillsbench_codex_acp_post_success_finalization",
                "required_preflight": [
                    "round_reward_trace.success_observed",
                    "codex_acp_runtime_launch_preflight",
                    "skillsbench_compact_failure_class",
                ],
                "rerun_allowed_after_profile_applied": True,
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class.startswith("skillsbench_codex_acp_"):
        return {
            "repair_priority": "P0",
            "repair_class": "skillsbench_codex_acp_runtime_preflight",
            "next_action": (
                "prove the Codex ACP runtime can start inside the SkillsBench "
                "sandbox before rerunning or launching treatment; require compact "
                "dependency and launch preflight evidence instead of a generic "
                "ACP launch failure"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "skillsbench_codex_acp_runtime_preflight",
                "required_preflight": [
                    "codex_acp_runtime_dependency_preflight",
                    "codex_acp_runtime_launch_preflight",
                    "skillsbench_compact_failure_class",
                ],
                "rerun_allowed_after_profile_applied": True,
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class in {
        "skillsbench_docker_apt_setup_risk_preflight_blocked",
        "skillsbench_dockerfile_package_bootstrap_risk_preflight_blocked",
    }:
        return {
            "repair_priority": "P1",
            "repair_class": "skillsbench_setup_preflight_selection",
            "next_action": (
                "select a SkillsBench task without Docker package-bootstrap "
                "setup risk for the next full baseline/treatment pair, or "
                "repair the Docker setup route before rerunning this task"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "skillsbench_setup_preflight_selection",
                "rerun_allowed_after_profile_applied": True,
                "required_preflight": [
                    "skillsbench_task_setup_preflight",
                    "task_staging.bootstrap_light_preflight_blocked",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class == "skillsbench_verifier_bootstrap_risk_preflight_blocked":
        return {
            "repair_priority": "P1",
            "repair_class": "skillsbench_verifier_bootstrap_preflight_selection",
            "next_action": (
                "select a SkillsBench task whose verifier does not require "
                "network/package bootstrap, or repair/cache the verifier "
                "bootstrap route before spending another full arm"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "skillsbench_verifier_bootstrap_preflight_selection",
                "rerun_allowed_after_profile_applied": True,
                "required_preflight": [
                    "skillsbench_task_setup_preflight",
                    "verifier_bootstrap_risk_detected",
                    "task_staging.verifier_bootstrap_risk_preflight_blocked",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class == "skillsbench_task_source_preflight_blocked":
        return {
            "repair_priority": "P1",
            "repair_class": "skillsbench_task_source_preflight_selection",
            "next_action": (
                "select a SkillsBench task from the canonical tasks source, or "
                "use an explicit sanity-source runner before spending a full "
                "baseline/treatment arm"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "skillsbench_task_source_preflight_selection",
                "rerun_allowed_after_profile_applied": True,
                "required_preflight": [
                    "skillsbench_task_setup_preflight",
                    "canonical_task_present",
                    "nearest_canonical_task_ids",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
            },
        }
    if failure_class == "score_missing":
        return {
            "repair_priority": "P0",
            "repair_class": "runner_result_materialization",
            "next_action": (
                "repair or ignore the incomplete runner materialization before treating this as case evidence"
            ),
        }
    if failure_class in {
        "stale_active_job_without_trial_result",
        "detached_worker_ended_active_without_trial_result",
        "detached_worker_ended_without_trial_result",
        "post_launch_compact_result_missing",
    }:
        return {
            "repair_priority": "P0",
            "repair_class": "runner_result_finalization",
            "next_action": (
                "repair Harbor/worker finalization or rerun after proving the "
                "worker can close with a compact trial result; do not treat "
                "connectivity or active job state as case success"
            ),
            "repair_profile": {
                "schema_version": "benchmark_repair_profile_v0",
                "repair_class": "runner_result_finalization",
                "rerun_allowed_after_profile_applied": True,
                "required_preflight": [
                    "post_launch_compact_polling_contract",
                    "stale_active_job_reconciliation_marker",
                    "worker_closes_with_trial_result_or_terminal_marker",
                ],
                "raw_logs_required": False,
                "raw_task_text_required": False,
                "trajectory_required": False,
            },
        }
    if failure_class == "score_failure_unattributed" or failure_scope == "attribution_required":
        return {
            "repair_priority": "P0",
            "repair_class": "verifier_attribution_required",
            "next_action": (
                "collect finer compact failure attribution before launching treatment"
            ),
        }
    if failure_class in {
        "worker_self_validation_official_score_mismatch",
        "worker_validation_scope_ambiguous_official_score_failure",
        "worker_bridge_connected_official_score_failure",
    }:
        return {
            "repair_priority": "P0",
            "repair_class": "worker_verifier_alignment",
            "next_action": (
                "align worker self-validation with verifier-facing compact evidence before repeating"
            ),
        }
    if failure_class.startswith("verifier_") or failure_scope == "verifier_or_infra":
        return {
            "repair_priority": "P0",
            "repair_class": "verifier_or_infra_repair",
            "next_action": "repair verifier or infra attribution before comparing arms",
        }
    if failure_class == "agent_timeout_before_solution_completion":
        return {
            "repair_priority": "P1",
            "repair_class": "case_timeout_research",
            "next_action": (
                "inspect compact timeout context and decide whether the run needs a private long-horizon timeout tier"
            ),
        }
    if failure_class == "agent_exception_before_solution_completion":
        return {
            "repair_priority": "P1",
            "repair_class": "case_exception_research",
            "next_action": "inspect compact exception attribution and form a case-level intervention hypothesis",
        }
    return {}


def _repair_profile_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    repair_class = _compact_text(value.get("repair_class"), limit=80)
    if repair_class == "runner_model_access":
        blocked = _compact_text(value.get("blocked_model_route"), limit=80) or "unknown"
        recommended = _compact_text(value.get("recommended_model_route"), limit=80) or "probe_required"
        return f"blocked_model={blocked}; rerun_model={recommended}; preflight=codex_cli_minimal_model_probe"
    if repair_class == "runner_setup_timeout":
        overrides = value.get("required_launch_overrides")
        if not isinstance(overrides, dict):
            return "required_launch_overrides=missing"
        strategy = _compact_text(overrides.get("codex_install_strategy"), limit=80)
        setup = overrides.get("agent_setup_timeout_multiplier")
        agent = overrides.get("agent_timeout_multiplier")
        parts = []
        if strategy:
            parts.append(f"codex_install_strategy={strategy}")
        parts.extend(
            [
                f"agent_setup_timeout_multiplier={setup}",
                f"agent_timeout_multiplier={agent}",
            ]
        )
        disallowed = value.get("disallowed_launch_overrides")
        if isinstance(disallowed, dict):
            disallowed_strategy = _compact_text(
                disallowed.get("codex_install_strategy"),
                limit=80,
            )
            if disallowed_strategy:
                parts.append(f"disallow={disallowed_strategy}")
        return "; ".join(parts)
    if repair_class in {
        "skillsbench_codex_acp_runtime_preflight",
        "skillsbench_codex_acp_post_success_finalization",
    }:
        required = _compact_list(value.get("required_preflight"), limit=3)
        return "required_preflight=" + ",".join(required) if required else repair_class
    if repair_class == "runner_result_finalization":
        required = _compact_list(value.get("required_preflight"), limit=3)
        return "required_preflight=" + ",".join(required) if required else repair_class
    return repair_class


def _case_routing_taxonomy(
    runs: list[dict[str, Any]],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Summarize case-history routing hints that should survive latest-pair churn."""

    if not runs:
        return {}
    repair_counts: dict[str, int] = {}
    bridge_signal_run_count = 0
    for run in runs:
        repair_class = _compact_text(run.get("repair_class"), limit=120)
        if repair_class:
            repair_counts[repair_class] = repair_counts.get(repair_class, 0) + 1
        failure_class = _compact_text(run.get("failure_class"), limit=120)
        labels = _compact_list(run.get("failure_labels"), limit=20) or _compact_list(
            run.get("failure_attribution_labels"),
            limit=20,
        )
        if (
            failure_class == "worker_bridge_connected_official_score_failure"
            or "worker_bridge_connected_official_score_failure" in labels
        ):
            bridge_signal_run_count += 1

    if repair_counts.get("case_exception_research", 0) > 0:
        return {
            "class": "case_exception_research",
            "priority": "P1",
            "evidence": (
                f"case_exception_research_count="
                f"{repair_counts['case_exception_research']}"
            ),
            "next_action": (
                "inspect compact exception attribution and form a case-level "
                "intervention hypothesis before rerunning this case"
            ),
        }

    timeout_count = repair_counts.get("case_timeout_research", 0)
    if timeout_count >= 2:
        return {
            "class": "timeout_tier_policy_candidate",
            "priority": "P1",
            "evidence": f"case_timeout_research_count={timeout_count}",
            "next_action": (
                "decide the timeout tier and continuation cadence before "
                "rerunning; separate setup timeout from solver timeout evidence"
            ),
        }
    if timeout_count == 1:
        return {
            "class": "case_timeout_research",
            "priority": "P1",
            "evidence": "case_timeout_research_count=1",
            "next_action": (
                "inspect compact timeout context and decide whether this case "
                "needs a private long-horizon timeout tier"
            ),
        }

    decision_name = _compact_text(decision.get("decision"), limit=120)
    no_score_uplift = (
        decision.get("official_score_delta") == 0
        or decision_name
        in {
            "paired_no_score_uplift",
            "paired_no_score_uplift_case_research_required",
        }
    )
    if bridge_signal_run_count and no_score_uplift:
        return {
            "class": "bridge_connected_no_uplift",
            "priority": "P1",
            "evidence": (
                f"worker_bridge_connected_official_score_failure_runs="
                f"{bridge_signal_run_count}; official_score_delta=0"
            ),
            "next_action": (
                "treat the bridge as connected and analyze case or solution "
                "quality; do not relaunch this case as a bridge repair"
            ),
        }
    return {}


def _run_status(benchmark_run: dict[str, Any], score: float | int | None) -> str:
    if _source_schema(benchmark_run) == "terminal_bench_post_launch_materialization_v0":
        if benchmark_run.get("ready_for_compact_failure_marker") is True:
            return "blocked"
        if benchmark_run.get("job_active_without_trial_result") is True:
            return "running"
        return "recorded"
    progress = benchmark_run.get("progress") if isinstance(benchmark_run.get("progress"), dict) else {}
    running = progress.get("n_running_trials")
    if isinstance(running, int) and not isinstance(running, bool) and running > 0:
        return "running"
    if score is not None or _compact_text(benchmark_run.get("runner_return_status")):
        return "completed"
    return "recorded"


def build_benchmark_run_ledger_entry(
    benchmark_run: dict[str, Any],
    *,
    artifact_ref: str | Path | None = None,
    result_ref: str | Path | None = None,
    compact_artifact_ref: str | Path | None = None,
    run_group_id: str | None = None,
    arm_id: str | None = None,
    notes: str | None = None,
    recorded_at: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    source_schema = _source_schema(benchmark_run)
    benchmark_id = _compact_text(benchmark_run.get("benchmark_id"), limit=120)
    if not benchmark_id and source_schema == "terminal_bench_post_launch_materialization_v0":
        benchmark_id = "terminal-bench@2.0"
    benchmark_id = benchmark_id or "unknown-benchmark"
    case_ids = _case_ids(benchmark_run)
    job_name = _compact_text(benchmark_run.get("job_name"), limit=160)
    mode = _compact_text(benchmark_run.get("mode"), limit=120)
    score, passed = _official_score(benchmark_run)
    score_status = _score_status(benchmark_run, score, passed)
    failure_class = _failure_class(benchmark_run, score)
    failure_scope = _failure_scope(failure_class, score, passed)
    resolved_arm_id = _resolved_arm_id(benchmark_run, arm_id)
    identity_artifact = _relative_ref(artifact_ref, cwd=cwd)
    identity_result = _relative_ref(result_ref, cwd=cwd)
    identity_compact_artifact = _relative_ref(compact_artifact_ref, cwd=cwd)
    artifact = _public_ledger_artifact_ref(artifact_ref, cwd=cwd)
    result = _public_ledger_artifact_ref(result_ref, cwd=cwd)
    compact_artifact = _public_ledger_artifact_ref(compact_artifact_ref, cwd=cwd)
    resolved_run_group_id = _compact_text(run_group_id, limit=160) or job_name
    identity = "|".join(
        str(part)
        for part in (
            benchmark_id,
            case_ids[0],
            resolved_arm_id,
            resolved_run_group_id,
            job_name,
            identity_artifact
            or identity_result
            or identity_compact_artifact
            or artifact
            or result
            or compact_artifact
            or "",
        )
    )
    run_id = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    agent = benchmark_run.get("agent") if isinstance(benchmark_run.get("agent"), dict) else {}
    agent_model = _compact_text(agent.get("model"), limit=120)
    model_control = (
        benchmark_run.get("model_control")
        if isinstance(benchmark_run.get("model_control"), dict)
        else {}
    )
    model_control_status = _compact_text(
        model_control.get("control_status"),
        limit=120,
    )
    model_actual_verified = model_control.get("actual_model_verified")
    model_warning_labels = _compact_list(
        model_control.get("warning_labels")
        or benchmark_run.get("runner_warning_labels"),
        limit=6,
    )
    round_reward_trace = (
        benchmark_run.get("round_reward_trace")
        if isinstance(benchmark_run.get("round_reward_trace"), dict)
        else {}
    )
    round_rewards = _compact_round_reward_records(
        round_reward_trace.get("records") if isinstance(round_reward_trace, dict) else []
    )
    first_success_round = (
        _compact_positive_int(round_reward_trace.get("first_success_round"))
        if isinstance(round_reward_trace, dict)
        else None
    )
    if first_success_round is None:
        for record in round_rewards:
            if record.get("passed") is True:
                first_success_round = int(record["agent_round"])
                break
    max_rounds_budget = (
        round_reward_trace.get("max_rounds_budget")
        if isinstance(round_reward_trace, dict)
        else None
    )
    round_reward_stats = _round_reward_best_stats(round_rewards)
    final_round = _compact_positive_int(round_reward_trace.get("final_round"))
    final_round_reward = _compact_number(round_reward_trace.get("final_round_reward"))
    final_round_passed = round_reward_trace.get("final_round_passed")
    best_reward_round = _compact_positive_int(
        round_reward_trace.get("best_reward_round")
    )
    best_round_reward = _compact_number(round_reward_trace.get("best_round_reward"))
    best_round_passed = round_reward_trace.get("best_round_passed")
    best_round_is_final = round_reward_trace.get("best_round_is_final")
    declared_done_round = _compact_positive_int(
        round_reward_trace.get("declared_done_round")
    )
    declared_done_score = _compact_number(round_reward_trace.get("declared_done_score"))
    agent_declared_done = round_reward_trace.get("agent_declared_done")
    if final_round is None:
        final_round = round_reward_stats.get("final_round")
    if final_round_reward is None:
        final_round_reward = round_reward_stats.get("final_round_reward")
    if not isinstance(final_round_passed, bool):
        final_round_passed = round_reward_stats.get("final_round_passed")
    if best_reward_round is None:
        best_reward_round = round_reward_stats.get("best_reward_round")
    if best_round_reward is None:
        best_round_reward = round_reward_stats.get("best_round_reward")
    if not isinstance(best_round_passed, bool):
        best_round_passed = round_reward_stats.get("best_round_passed")
    if not isinstance(best_round_is_final, bool):
        best_round_is_final = round_reward_stats.get("best_round_is_final")
    runner_prerequisites = (
        benchmark_run.get("runner_prerequisites")
        if isinstance(benchmark_run.get("runner_prerequisites"), dict)
        else {}
    )
    runner_failure = (
        benchmark_run.get("runner_failure")
        if isinstance(benchmark_run.get("runner_failure"), dict)
        else {}
    )
    verifier_reward_artifact_recovery = (
        benchmark_run.get("verifier_reward_artifact_recovery")
        if isinstance(benchmark_run.get("verifier_reward_artifact_recovery"), dict)
        else {}
    )
    validation = (
        benchmark_run.get("validation")
        if isinstance(benchmark_run.get("validation"), dict)
        else {}
    )
    runtime_preflight_passed = _codex_acp_runtime_preflight_passed(
        runner_prerequisites
    )
    round_success_observed = (
        round_reward_trace.get("success_observed")
        if isinstance(round_reward_trace, dict)
        and isinstance(round_reward_trace.get("success_observed"), bool)
        else (first_success_round is not None)
    )
    repair_route = _repair_route(
        failure_class,
        failure_scope,
        agent_model=agent_model,
        round_success_observed=round_success_observed,
        runtime_preflight_passed=runtime_preflight_passed,
    )

    entry: dict[str, Any] = {
        "run_id": run_id,
        "recorded_at": recorded_at or _now_local_iso(),
        "benchmark_id": benchmark_id,
        "case_id": case_ids[0],
        "case_ids": case_ids,
        "run_group_id": resolved_run_group_id or run_id,
        "arm_id": resolved_arm_id,
        "mode": mode,
        "route": _compact_text(benchmark_run.get("route"), limit=120),
        "job_name": job_name,
        "status": _run_status(benchmark_run, score),
        "score_status": score_status,
        "official_score": score,
        "official_passed": passed,
        "first_success_round": first_success_round,
        "final_round": final_round,
        "final_round_reward": final_round_reward,
        "final_round_passed": final_round_passed,
        "best_reward_round": best_reward_round,
        "best_round_reward": best_round_reward,
        "best_round_passed": best_round_passed,
        "best_round_is_final": best_round_is_final,
        "agent_declared_done": agent_declared_done
        if isinstance(agent_declared_done, bool)
        else False,
        "declared_done_round": declared_done_round,
        "declared_done_score": declared_done_score,
        "loop_score_policy": _compact_text(
            round_reward_trace.get("loop_score_policy"),
            limit=120,
        )
        or ("best_round_for_offline_controller_analysis" if round_rewards else ""),
        "official_score_policy": _compact_text(
            round_reward_trace.get("official_score_policy"),
            limit=120,
        )
        or ("final_workspace_official_result" if round_rewards else ""),
        "round_rewards": round_rewards,
        "round_reward_count": len(round_rewards),
        "round_success_observed": round_success_observed,
        "codex_acp_runtime_preflight_passed": runtime_preflight_passed,
        "max_rounds_budget": max_rounds_budget
        if isinstance(max_rounds_budget, int) and not isinstance(max_rounds_budget, bool)
        else None,
        "official_feedback_blinded": round_reward_trace.get("official_feedback_blinded")
        if isinstance(round_reward_trace, dict)
        and isinstance(round_reward_trace.get("official_feedback_blinded"), bool)
        else None,
        "reward_feedback_forwarded": round_reward_trace.get("reward_feedback_forwarded")
        if isinstance(round_reward_trace, dict)
        and isinstance(round_reward_trace.get("reward_feedback_forwarded"), bool)
        else None,
        "failure_class": failure_class,
        "failure_scope": failure_scope,
        "failure_labels": _compact_list(
            benchmark_run.get("failure_attribution_labels"),
            limit=8,
        ),
        "runner_return_status": _compact_text(
            benchmark_run.get("runner_return_status"),
            limit=120,
        ),
        "runner_score_recovered_from_verifier_artifact": (
            runner_failure.get("score_recovered_from_verifier_artifact")
            if isinstance(
                runner_failure.get("score_recovered_from_verifier_artifact"),
                bool,
            )
            else None
        ),
        "verifier_reward_artifact_recovery_status": _compact_text(
            verifier_reward_artifact_recovery.get("status"),
            limit=120,
        ),
        "verifier_reward_artifact_recovered": (
            validation.get("verifier_reward_artifact_recovered")
            if isinstance(validation.get("verifier_reward_artifact_recovered"), bool)
            else (
                verifier_reward_artifact_recovery.get("reward_present")
                if isinstance(
                    verifier_reward_artifact_recovery.get("reward_present"),
                    bool,
                )
                else None
            )
        ),
        "official_result_json_materialized": (
            verifier_reward_artifact_recovery.get("official_result_json_materialized")
            if isinstance(
                verifier_reward_artifact_recovery.get("official_result_json_materialized"),
                bool,
            )
            else (
                validation.get("official_result_json_materialized")
                if isinstance(validation.get("official_result_json_materialized"), bool)
                else None
            )
        ),
        "setup_blockers": _compact_list(
            benchmark_run.get("worker_setup_diagnostic_blockers"),
            limit=4,
        )
        or _compact_list(benchmark_run.get("worker_startup_blockers"), limit=4),
        "loopx_inside_case": benchmark_run.get("loopx_inside_case")
        if isinstance(benchmark_run.get("loopx_inside_case"), bool)
        else None,
        "worker_bridge_status": _compact_text(
            benchmark_run.get("worker_bridge_materialization_status"),
            limit=120,
        ),
        "loopx_prompt_driven_lifecycle_observed": benchmark_run.get(
            "loopx_prompt_driven_lifecycle_observed"
        )
        if isinstance(benchmark_run.get("loopx_prompt_driven_lifecycle_observed"), bool)
        else None,
        "worker_loopx_cli_call_total": benchmark_run.get("worker_loopx_cli_call_total")
        if isinstance(benchmark_run.get("worker_loopx_cli_call_total"), int)
        and not isinstance(benchmark_run.get("worker_loopx_cli_call_total"), bool)
        else None,
        "loopx_prompt_driven_case_cli_call_count": benchmark_run.get(
            "loopx_prompt_driven_case_cli_call_count"
        )
        if isinstance(
            benchmark_run.get("loopx_prompt_driven_case_cli_call_count"),
            int,
        )
        and not isinstance(
            benchmark_run.get("loopx_prompt_driven_case_cli_call_count"),
            bool,
        )
        else None,
        "agent_model": agent_model,
        "model_control_status": model_control_status,
        "actual_model_verified": model_actual_verified
        if isinstance(model_actual_verified, bool)
        else None,
        "model_warning_labels": model_warning_labels,
        "submit_eligible": benchmark_run.get("submit_eligible")
        if isinstance(benchmark_run.get("submit_eligible"), bool)
        else None,
        "leaderboard_evidence": benchmark_run.get("leaderboard_evidence")
        if isinstance(benchmark_run.get("leaderboard_evidence"), bool)
        else None,
        "source_event_schema": source_schema,
    }
    product_mode_lifecycle_contract = _compact_product_mode_lifecycle_contract(
        benchmark_run.get("product_mode_lifecycle_contract")
    )
    if product_mode_lifecycle_contract:
        entry["product_mode_lifecycle_contract"] = product_mode_lifecycle_contract
    solution_quality_signals = _ledger_skillsbench_solution_quality_signals(
        benchmark_run,
        benchmark_id=benchmark_id,
    )
    if solution_quality_signals:
        entry["solution_quality_signals"] = solution_quality_signals
    attempt_accounting = (
        benchmark_run.get("attempt_accounting")
        if isinstance(benchmark_run.get("attempt_accounting"), dict)
        else {}
    )
    if (
        not attempt_accounting
        and source_schema == "terminal_bench_post_launch_materialization_v0"
    ):
        marker = (
            benchmark_run.get("compact_failure_marker")
            if isinstance(benchmark_run.get("compact_failure_marker"), dict)
            else {}
        )
        attempt_accounting = (
            marker.get("attempt_accounting")
            if isinstance(marker.get("attempt_accounting"), dict)
            else {}
        )
    if attempt_accounting:
        for source_field, entry_field in (
            ("lifecycle_phase", "attempt_lifecycle_phase"),
            ("failure_label", "attempt_failure_label"),
            ("failure_class", "attempt_failure_class"),
        ):
            text = _compact_text(attempt_accounting.get(source_field), limit=120)
            if text:
                entry[entry_field] = text
        for field in (
            "launcher_attempt_countable",
            "case_attempt_countable",
            "solver_attempt_countable",
            "verifier_attempt_countable",
            "official_score_attempt_countable",
        ):
            if isinstance(attempt_accounting.get(field), bool):
                entry[field] = attempt_accounting[field]
    if source_schema == "terminal_bench_post_launch_materialization_v0":
        marker = (
            benchmark_run.get("compact_failure_marker")
            if isinstance(benchmark_run.get("compact_failure_marker"), dict)
            else {}
        )
        entry.update(
            {
                "post_launch_first_blocker": _compact_text(
                    benchmark_run.get("first_blocker"),
                    limit=120,
                ),
                "compact_monitor_class": _compact_text(
                    benchmark_run.get("compact_monitor_class"),
                    limit=120,
                ),
                "job_active_without_trial_result": benchmark_run.get(
                    "job_active_without_trial_result"
                )
                if isinstance(
                    benchmark_run.get("job_active_without_trial_result"),
                    bool,
                )
                else None,
                "job_stale_active_without_trial_result": benchmark_run.get(
                    "job_stale_active_without_trial_result"
                )
                if isinstance(
                    benchmark_run.get("job_stale_active_without_trial_result"),
                    bool,
                )
                else None,
                "stale_active_reconcile_requested": benchmark_run.get(
                    "stale_active_reconcile_requested"
                )
                if isinstance(
                    benchmark_run.get("stale_active_reconcile_requested"),
                    bool,
                )
                else None,
                "compact_failure_evidence_kind": _compact_text(
                    marker.get("evidence_kind"),
                    limit=120,
                ),
                "ledger_attempt_kind": _compact_text(
                    marker.get("ledger_attempt_kind"),
                    limit=120,
                ),
                "terminal_closeout": marker.get("terminal_closeout")
                if isinstance(marker.get("terminal_closeout"), bool)
                else None,
                "case_attempt_countable": marker.get("case_attempt_countable")
                if isinstance(marker.get("case_attempt_countable"), bool)
                else None,
                "benchmark_budget_countable": marker.get(
                    "benchmark_budget_countable"
                )
                if isinstance(marker.get("benchmark_budget_countable"), bool)
                else None,
            }
        )
    entry.update(repair_route)
    task_setup_preflight = _compact_task_setup_preflight(
        benchmark_run.get("task_setup_preflight")
    )
    if task_setup_preflight:
        entry["task_setup_preflight"] = task_setup_preflight
    task_staging = _compact_task_staging(benchmark_run.get("task_staging"))
    if task_staging:
        entry["task_staging"] = task_staging
    compose_setup_diagnostic = _compact_compose_setup_diagnostic(
        benchmark_run.get("compose_setup_diagnostic")
    )
    if compose_setup_diagnostic:
        entry["compose_setup_diagnostic"] = compose_setup_diagnostic
    refs: dict[str, str] = {}
    if artifact:
        refs["artifact_ref"] = artifact
    if result:
        refs["result_ref"] = result
    if compact_artifact:
        refs["compact_artifact_ref"] = compact_artifact
    if refs:
        entry["artifact_refs"] = refs
    note = _compact_text(notes, limit=220)
    if note:
        entry["notes"] = note
    return {key: value for key, value in entry.items() if value not in (None, "", [])}


def _entry_is_public_ledger_closeout(entry: dict[str, Any]) -> bool:
    """Return whether a compact run is terminal enough for the public run ledger."""

    if entry.get("status") == "running":
        return False
    return True


def _ledger_run_archived(run: dict[str, Any]) -> bool:
    return _compact_text(run.get("archive_state"), limit=40) == "archived"


def _active_ledger_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [run for run in runs if not _ledger_run_archived(run)]


def _archived_ledger_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [run for run in runs if _ledger_run_archived(run)]


def _empty_ledger() -> dict[str, Any]:
    return {
        "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
        "updated_at": _now_local_iso(),
        "update_policy": {
            "source_of_truth": "benchmark_run_v0 compact run events",
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "absolute_paths_recorded": False,
            "update_rule": "upsert one run entry when a benchmark case is ingested or closed",
        },
        "benchmarks": {},
    }


def load_benchmark_run_ledger(path: str | Path) -> dict[str, Any]:
    ledger_path = Path(path)
    if not ledger_path.exists():
        return _empty_ledger()
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark run ledger must be a JSON object")
    if payload.get("schema_version") != BENCHMARK_RUN_LEDGER_SCHEMA_VERSION:
        raise ValueError(
            f"benchmark run ledger must use schema_version={BENCHMARK_RUN_LEDGER_SCHEMA_VERSION}"
        )
    payload.setdefault("benchmarks", {})
    return _normalize_benchmark_run_ledger(payload)


def _normalize_ledger_run(run: dict[str, Any], *, fallback_benchmark_id: str) -> dict[str, Any]:
    normalized = dict(run)
    benchmark_id = _compact_text(
        normalized.get("benchmark_id") or fallback_benchmark_id,
        limit=120,
    )
    job_name = _compact_text(normalized.get("job_name"), limit=160)
    case_id = _compact_text(normalized.get("case_id"), limit=160)
    if job_name and (
        not case_id
        or case_id.startswith("terminal_bench_")
        or case_id == "unknown-case"
    ):
        parsed_case = _terminal_bench_case_id_from_job_name(
            benchmark_id=benchmark_id,
            job_name=job_name,
        )
        if parsed_case:
            normalized["case_id"] = parsed_case
            normalized["case_ids"] = [parsed_case]
    resolved_arm = _resolved_arm_id(normalized, _compact_text(normalized.get("arm_id"), limit=120))
    if resolved_arm:
        normalized["arm_id"] = resolved_arm
    normalized["benchmark_id"] = benchmark_id
    repair_route = _repair_route(
        _compact_text(normalized.get("failure_class"), limit=120),
        _compact_text(normalized.get("failure_scope"), limit=80),
        agent_model=_compact_text(normalized.get("agent_model"), limit=120),
        round_success_observed=normalized.get("round_success_observed") is True
        or normalized.get("first_success_round") is not None
        or normalized.get("best_round_passed") is True
        or normalized.get("final_round_passed") is True,
        runtime_preflight_passed=(
            normalized.get("codex_acp_runtime_preflight_passed") is True
        ),
    )
    for key in ("repair_priority", "repair_class", "next_action", "repair_profile"):
        normalized.pop(key, None)
    normalized.update(repair_route)
    archive_state = _compact_text(normalized.get("archive_state"), limit=40)
    if archive_state == "archived":
        normalized["archive_state"] = "archived"
        for key, limit in (
            ("archive_reason", 220),
            ("archive_batch_id", 120),
            ("archived_at", 80),
        ):
            value = _compact_text(normalized.get(key), limit=limit)
            if value:
                normalized[key] = value
            else:
                normalized.pop(key, None)
    else:
        for key in ("archive_state", "archive_reason", "archive_batch_id", "archived_at"):
            normalized.pop(key, None)
    refs = normalized.get("artifact_refs")
    if isinstance(refs, dict):
        safe_refs: dict[str, str] = {}
        for key in ("artifact_ref", "result_ref", "compact_artifact_ref"):
            value = refs.get(key)
            if not isinstance(value, str):
                continue
            safe_ref = _public_ledger_artifact_ref(value)
            if safe_ref:
                safe_refs[key] = safe_ref
        if safe_refs:
            normalized["artifact_refs"] = safe_refs
        else:
            normalized.pop("artifact_refs", None)
    return normalized


def _normalize_benchmark_run_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    benchmarks = ledger.get("benchmarks")
    if not isinstance(benchmarks, dict):
        ledger["benchmarks"] = {}
        return ledger
    normalized_benchmarks: dict[str, Any] = {}
    for benchmark_id, benchmark in benchmarks.items():
        if not isinstance(benchmark, dict):
            continue
        normalized_benchmark = normalized_benchmarks.setdefault(
            benchmark_id,
            {"benchmark_id": benchmark_id, "cases": {}},
        )
        cases = benchmark.get("cases")
        if not isinstance(cases, dict):
            continue
        for fallback_case_id, case in cases.items():
            if not isinstance(case, dict):
                continue
            runs = case.get("runs")
            if not isinstance(runs, list):
                continue
            for run in runs:
                if not isinstance(run, dict):
                    continue
                normalized_run = _normalize_ledger_run(
                    run,
                    fallback_benchmark_id=str(benchmark_id),
                )
                case_id = _compact_text(
                    normalized_run.get("case_id") or fallback_case_id,
                    limit=160,
                )
                normalized_case = normalized_benchmark["cases"].setdefault(
                    case_id,
                    {"case_id": case_id, "runs": []},
                )
                normalized_case["runs"].append(normalized_run)
    for benchmark in normalized_benchmarks.values():
        cases = benchmark.get("cases")
        if not isinstance(cases, dict):
            continue
        for case in cases.values():
            if not isinstance(case, dict):
                continue
            runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
            deduped: dict[str, dict[str, Any]] = {}
            for run in runs:
                run_id = _compact_text(run.get("run_id"), limit=80)
                deduped[run_id or json.dumps(run, sort_keys=True)] = run
            ordered_runs = sorted(
                deduped.values(),
                key=lambda run: (str(run.get("recorded_at", "")), str(run.get("run_id", ""))),
            )
            case["runs"] = ordered_runs
            case["active_run_count"] = len(_active_ledger_runs(ordered_runs))
            case["archived_run_count"] = len(_archived_ledger_runs(ordered_runs))
            case["latest_decision"] = _case_decision(case)
        benchmark["case_count"] = len(cases)
        benchmark["run_count"] = sum(
            len(value.get("runs", []))
            for value in cases.values()
            if isinstance(value, dict)
        )
        benchmark["active_case_count"] = sum(
            1
            for value in cases.values()
            if isinstance(value, dict)
            and value.get("active_run_count", 0)
        )
        benchmark["active_run_count"] = sum(
            int(value.get("active_run_count", 0))
            for value in cases.values()
            if isinstance(value, dict)
        )
        benchmark["archived_run_count"] = sum(
            int(value.get("archived_run_count", 0))
            for value in cases.values()
            if isinstance(value, dict)
        )
    ledger["benchmarks"] = normalized_benchmarks
    return ledger


class _LedgerWriteLock:
    def __init__(self, path: Path, *, timeout_seconds: float = 10.0) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> "_LedgerWriteLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for ledger lock: {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def _case_decision(case: dict[str, Any]) -> dict[str, Any]:
    all_runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
    runs = _active_ledger_runs(all_runs)
    if not runs and all_runs:
        return {
            "decision": "archived_only",
            "archived_run_count": len(all_runs),
        }
    baselines = [
        run
        for run in runs
        if "baseline" in str(run.get("arm_id", ""))
        or _product_mode_baseline_run(run)
    ]
    treatments = [
        run
        for run in runs
        if "treatment" in str(run.get("arm_id", ""))
        or _product_mode_treatment_run(run)
    ]
    latest_baseline = baselines[-1] if baselines else None
    latest_treatment = treatments[-1] if treatments else None

    def with_case_routing(result: dict[str, Any]) -> dict[str, Any]:
        routing = _case_routing_taxonomy(runs, result)
        if routing:
            result["case_routing"] = routing
        return result

    def repair_decision(prefix: str, run: dict[str, Any]) -> dict[str, Any]:
        failure_class = _compact_text(run.get("failure_class"), limit=120)
        repair_class = _compact_text(run.get("repair_class"), limit=120)
        if repair_class == "runner_setup_timeout":
            decision = f"{prefix}_setup_timeout_repair_required"
        elif repair_class == "benchmark_environment_setup_contract":
            decision = f"{prefix}_environment_setup_repair_required"
        elif repair_class == "runner_model_access":
            decision = f"{prefix}_model_access_repair_required"
        elif repair_class == "runner_result_materialization":
            decision = f"{prefix}_result_materialization_repair_required"
        elif repair_class == "runner_result_finalization":
            decision = f"{prefix}_result_finalization_repair_required"
        elif repair_class == "skillsbench_codex_acp_runtime_preflight":
            decision = f"{prefix}_codex_acp_runtime_preflight_required"
        elif repair_class == "skillsbench_codex_acp_post_success_finalization":
            decision = f"{prefix}_codex_acp_post_success_finalization_required"
        elif repair_class == "skillsbench_setup_preflight_selection":
            decision = f"{prefix}_setup_preflight_selection_required"
        elif repair_class == "skillsbench_verifier_bootstrap_preflight_selection":
            decision = f"{prefix}_verifier_bootstrap_preflight_selection_required"
        elif repair_class == "skillsbench_task_source_preflight_selection":
            decision = f"{prefix}_task_source_preflight_selection_required"
        elif repair_class == "worker_verifier_alignment":
            decision = f"{prefix}_worker_verifier_alignment_required"
        elif repair_class == "verifier_or_infra_repair":
            decision = f"{prefix}_verifier_or_infra_repair_required"
        else:
            decision = f"{prefix}_runner_or_setup_repair_required"
        return {
            "decision": decision,
            "repair_priority": _compact_text(run.get("repair_priority"), limit=20),
            "repair_class": repair_class,
            "failure_class": failure_class,
            "next_action": _compact_text(run.get("next_action"), limit=220),
        }

    def case_research_decision(run: dict[str, Any]) -> dict[str, Any]:
        repair_class = _compact_text(run.get("repair_class"), limit=120)
        if repair_class == "case_timeout_research":
            decision = "paired_no_score_uplift_timeout_research_required"
        elif repair_class == "case_exception_research":
            decision = "paired_no_score_uplift_exception_research_required"
        else:
            decision = "paired_no_score_uplift_case_research_required"
        return {
            "decision": decision,
            "repair_priority": _compact_text(run.get("repair_priority"), limit=20),
            "repair_class": repair_class,
            "failure_class": _compact_text(run.get("failure_class"), limit=120),
            "next_action": _compact_text(run.get("next_action"), limit=220),
        }

    if latest_baseline and latest_treatment:
        product_mode_pair_review: dict[str, Any] | None = None
        if _product_mode_treatment_run(latest_treatment):
            product_mode_pair_review = _compact_product_mode_pair_review(
                classify_product_mode_main_table_pair(
                    baseline_run=latest_baseline,
                    treatment_run=latest_treatment,
                    benchmark_id=_compact_text(
                        latest_baseline.get("benchmark_id")
                        or latest_treatment.get("benchmark_id")
                        or "skillsbench@1.1",
                        limit=120,
                    )
                    or "skillsbench@1.1",
                )
            )
            if product_mode_pair_review.get("main_table_claim_allowed") is not True:
                return with_case_routing(
                    {
                        "decision": "product_mode_pair_incomplete",
                        "baseline_run_id": latest_baseline.get("run_id"),
                        "treatment_run_id": latest_treatment.get("run_id"),
                        "product_mode_main_table_pair": product_mode_pair_review,
                    }
                )
        b_score = latest_baseline.get("official_score")
        t_score = latest_treatment.get("official_score")
        b_scope = _compact_text(latest_baseline.get("failure_scope"), limit=80)
        t_scope = _compact_text(latest_treatment.get("failure_scope"), limit=80)
        delta = (
            t_score - b_score
            if isinstance(b_score, (int, float))
            and not isinstance(b_score, bool)
            and isinstance(t_score, (int, float))
            and not isinstance(t_score, bool)
            else None
        )
        if "attribution_required" in {b_scope, t_scope}:
            decision = "paired_result_requires_attribution"
        elif "verifier_or_infra" in {b_scope, t_scope}:
            decision = "paired_result_blocked_by_verifier_or_infra"
        elif b_scope in {"runner_or_setup", "score_missing"}:
            decision_info = repair_decision("paired_baseline", latest_baseline)
            decision = decision_info["decision"]
        elif t_scope in {"runner_or_setup", "score_missing"}:
            decision_info = repair_decision("paired_treatment", latest_treatment)
            decision = decision_info["decision"]
        elif delta is None:
            decision = "paired_result_needs_score_review"
        elif delta > 0:
            decision = "paired_treatment_improved"
        elif delta == 0:
            case_research_run = next(
                (
                    run
                    for run in (latest_treatment, latest_baseline)
                    if _compact_text(run.get("repair_priority"), limit=20) == "P1"
                ),
                None,
            )
            if b_scope == "case_or_solution" and t_scope == "case_or_solution" and case_research_run:
                decision_info = case_research_decision(case_research_run)
                decision = decision_info["decision"]
            elif b_scope == "passed" and t_scope == "passed":
                decision = "paired_baseline_solved_treatment_preserved"
            else:
                decision = "paired_no_score_uplift"
        else:
            decision = "paired_treatment_regressed"
        result = {
            "decision": decision,
            "baseline_run_id": latest_baseline.get("run_id"),
            "treatment_run_id": latest_treatment.get("run_id"),
            "official_score_delta": delta,
            "baseline_failure_scope": b_scope,
            "treatment_failure_scope": t_scope,
        }
        if product_mode_pair_review:
            result["product_mode_main_table_pair"] = product_mode_pair_review
        if "decision_info" in locals():
            result.update(
                {
                    key: value
                    for key, value in decision_info.items()
                    if key != "decision" and value
                }
            )
            del decision_info
        return with_case_routing(result)
    if latest_baseline:
        if latest_baseline.get("official_passed") is True:
            decision = "baseline_passed_not_current_treatment_priority"
        elif latest_baseline.get("failure_scope") == "attribution_required":
            decision = "baseline_failed_requires_attribution"
            decision_info = repair_decision("baseline", latest_baseline)
        elif latest_baseline.get("failure_scope") == "case_or_solution":
            decision = "baseline_failed_treatment_candidate"
            case_route = _repair_route(
                _compact_text(latest_baseline.get("failure_class"), limit=120),
                _compact_text(latest_baseline.get("failure_scope"), limit=120),
                agent_model=_compact_text(latest_baseline.get("agent_model"), limit=120),
            )
            if case_route:
                decision_info = {
                    "decision": decision,
                    **case_route,
                    "failure_class": _compact_text(
                        latest_baseline.get("failure_class"),
                        limit=120,
                    ),
                }
        else:
            decision_info = repair_decision("baseline", latest_baseline)
            decision = decision_info["decision"]
        result = {
            "decision": decision,
            "baseline_run_id": latest_baseline.get("run_id"),
            "failure_scope": latest_baseline.get("failure_scope"),
        }
        if "decision_info" in locals():
            result.update(
                {
                    key: value
                    for key, value in decision_info.items()
                    if key != "decision" and value
                }
            )
            del decision_info
        return with_case_routing(result)
    if runs:
        return with_case_routing(
            {"decision": "single_arm_recorded", "latest_run_id": runs[-1].get("run_id")}
        )
    return {"decision": "no_runs_recorded"}


def upsert_benchmark_run_ledger_entry(
    ledger: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    benchmark_id = entry["benchmark_id"]
    case_id = entry["case_id"]
    benchmarks = ledger.setdefault("benchmarks", {})
    benchmark = benchmarks.setdefault(
        benchmark_id,
        {"benchmark_id": benchmark_id, "cases": {}},
    )
    cases = benchmark.setdefault("cases", {})
    case = cases.setdefault(case_id, {"case_id": case_id, "runs": []})
    runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
    replaced = False
    for index, run in enumerate(runs):
        if run.get("run_id") == entry.get("run_id"):
            if _ledger_run_archived(run) and "archive_state" not in entry:
                entry = {
                    **entry,
                    "archive_state": "archived",
                    "archive_reason": run.get("archive_reason"),
                    "archive_batch_id": run.get("archive_batch_id"),
                    "archived_at": run.get("archived_at"),
                }
                entry = {
                    key: value
                    for key, value in entry.items()
                    if value not in (None, "", [])
                }
            runs[index] = entry
            replaced = True
            break
    if not replaced:
        entry_backfill_key = _ledger_logical_backfill_key(entry)
        if entry_backfill_key:
            for index, run in enumerate(runs):
                if (
                    run.get("run_id") == entry.get("run_id")
                    or _ledger_logical_backfill_key(run) != entry_backfill_key
                    or not _ledger_result_equivalent_for_backfill(run, entry)
                ):
                    continue
                merged, changed = _merge_ledger_logical_backfill_fields(run, entry)
                if changed:
                    runs[index] = merged
                replaced = True
                break
    if not replaced:
        runs.append(entry)
    runs.sort(key=lambda run: (str(run.get("recorded_at", "")), str(run.get("run_id", ""))))
    case["runs"] = runs
    case["active_run_count"] = len(_active_ledger_runs(runs))
    case["archived_run_count"] = len(_archived_ledger_runs(runs))
    case["latest_decision"] = _case_decision(case)
    benchmark["case_count"] = len(cases)
    benchmark["run_count"] = sum(
        len(value.get("runs", []))
        for value in cases.values()
        if isinstance(value, dict)
    )
    benchmark["active_case_count"] = sum(
        1
        for value in cases.values()
        if isinstance(value, dict)
        and value.get("active_run_count", 0)
    )
    benchmark["active_run_count"] = sum(
        int(value.get("active_run_count", 0))
        for value in cases.values()
        if isinstance(value, dict)
    )
    benchmark["archived_run_count"] = sum(
        int(value.get("archived_run_count", 0))
        for value in cases.values()
        if isinstance(value, dict)
    )
    ledger["updated_at"] = _now_local_iso()
    return ledger


def render_benchmark_run_ledger_markdown(ledger: dict[str, Any]) -> str:
    benchmarks = ledger.get("benchmarks") if isinstance(ledger.get("benchmarks"), dict) else {}
    total_active_runs = 0
    total_archived_runs = 0
    total_active_cases = 0
    for benchmark in benchmarks.values():
        if not isinstance(benchmark, dict):
            continue
        cases = benchmark.get("cases") if isinstance(benchmark.get("cases"), dict) else {}
        if not isinstance(cases, dict):
            continue
        for case in cases.values():
            if not isinstance(case, dict):
                continue
            runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
            active_runs = _active_ledger_runs(runs)
            archived_runs = _archived_ledger_runs(runs)
            if active_runs:
                total_active_cases += 1
            total_active_runs += len(active_runs)
            total_archived_runs += len(archived_runs)
    lines = [
        "# Benchmark Run Ledger",
        "",
        "This file is generated from `benchmark_run_ledger_v0`. It records compact",
        "benchmark case outcomes and artifact references; it must not contain raw",
        "logs, task prompts, trajectories, credentials, uploads, or absolute paths.",
        "Archived runs remain in JSON for traceability but are excluded from the",
        "default case decisions, repair backlog, and active runs table.",
        "",
        f"- schema_version: `{ledger.get('schema_version')}`",
        f"- updated_at: `{ledger.get('updated_at')}`",
        f"- active_case_count: `{total_active_cases}`",
        f"- active_run_count: `{total_active_runs}`",
        f"- archived_run_count: `{total_archived_runs}`",
        "",
        "## Case Decisions",
        "",
        "| Benchmark | Case | Decision | Product Pair | Case Routing | Runs |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for benchmark_id in sorted(benchmarks):
        benchmark = benchmarks[benchmark_id]
        cases = benchmark.get("cases") if isinstance(benchmark, dict) else {}
        if not isinstance(cases, dict):
            continue
        for case_id in sorted(cases):
            case = cases[case_id]
            runs = case.get("runs", []) if isinstance(case, dict) else []
            active_runs = _active_ledger_runs(
                [run for run in runs if isinstance(run, dict)]
            )
            archived_count = len(
                _archived_ledger_runs([run for run in runs if isinstance(run, dict)])
            )
            if not active_runs:
                continue
            decision = (
                case.get("latest_decision")
                if isinstance(case, dict) and isinstance(case.get("latest_decision"), dict)
                else {}
            )
            routing = (
                decision.get("case_routing")
                if isinstance(decision.get("case_routing"), dict)
                else {}
            )
            routing_class = _compact_text(routing.get("class"), limit=120)
            routing_cell = f"`{routing_class}`" if routing_class else "-"
            pair_review = (
                decision.get("product_mode_main_table_pair")
                if isinstance(decision.get("product_mode_main_table_pair"), dict)
                else {}
            )
            product_pair_cell = "-"
            if pair_review:
                if pair_review.get("main_table_claim_allowed") is True:
                    product_pair_cell = "`main_table_ready`"
                else:
                    blocker = _compact_text(
                        pair_review.get("claim_blocker"),
                        limit=120,
                    )
                    product_pair_cell = f"`{blocker or 'pair_incomplete'}`"
            run_cell = str(len(active_runs))
            if archived_count:
                run_cell = f"{run_cell} active / {archived_count} archived"
            lines.append(
                f"| `{benchmark_id}` | `{case_id}` | "
                f"`{decision.get('decision', 'unknown')}` | "
                f"{product_pair_cell} | "
                f"{routing_cell} | `{run_cell}` |"
            )
    repair_rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    for benchmark_id in sorted(benchmarks):
        benchmark = benchmarks[benchmark_id]
        cases = benchmark.get("cases") if isinstance(benchmark, dict) else {}
        if not isinstance(cases, dict):
            continue
        for case_id in sorted(cases):
            case = cases[case_id]
            runs = _active_ledger_runs(
                [
                    run
                    for run in (case.get("runs", []) if isinstance(case, dict) else [])
                    if isinstance(run, dict)
                ]
            )
            latest_run_by_arm: dict[str, dict[str, Any]] = {}
            for run in runs:
                if not isinstance(run, dict):
                    continue
                arm = _compact_text(run.get("arm_id"), limit=80)
                if arm:
                    latest_run_by_arm[arm] = run
            for run in runs:
                if not isinstance(run, dict):
                    continue
                priority = _compact_text(run.get("repair_priority"), limit=20)
                repair_class = _compact_text(run.get("repair_class"), limit=80)
                if not priority or not repair_class:
                    continue
                arm = _compact_text(run.get("arm_id"), limit=80)
                if arm and latest_run_by_arm.get(arm) is not run:
                    continue
                repair_rows.append(
                    (
                        priority,
                        benchmark_id,
                        case_id,
                        arm,
                        repair_class,
                        _compact_text(run.get("failure_class"), limit=120),
                        _repair_profile_summary(run.get("repair_profile")),
                        _compact_text(run.get("next_action"), limit=180),
                    )
                )
    repair_rows.sort(
        key=lambda row: (
            priority_order.get(row[0], 99),
            row[4],
            row[1],
            row[2],
            row[3],
        )
    )
    if repair_rows:
        lines.extend(
            [
                "",
                "## Repair Backlog",
                "",
                "| Priority | Benchmark | Case | Arm | Repair Class | Failure | Repair Profile | Next Action |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for priority, benchmark_id, case_id, arm, repair_class, failure, profile, next_action in repair_rows:
            lines.append(
                "| "
                f"`{priority}` | "
                f"`{benchmark_id}` | "
                f"`{case_id}` | "
                f"`{arm}` | "
                f"`{repair_class}` | "
                f"`{failure}` | "
                f"{profile} | "
                f"{next_action} |"
            )
    archived_summary: list[tuple[str, int, int]] = []
    for benchmark_id in sorted(benchmarks):
        benchmark = benchmarks[benchmark_id]
        cases = benchmark.get("cases") if isinstance(benchmark, dict) else {}
        if not isinstance(cases, dict):
            continue
        archived_case_count = 0
        archived_run_count = 0
        for case in cases.values():
            if not isinstance(case, dict):
                continue
            runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
            archived_runs = _archived_ledger_runs(runs)
            if archived_runs:
                archived_case_count += 1
                archived_run_count += len(archived_runs)
        if archived_run_count:
            archived_summary.append(
                (benchmark_id, archived_case_count, archived_run_count)
            )
    if archived_summary:
        lines.extend(
            [
                "",
                "## Archived Run Summary",
                "",
                "| Benchmark | Archived Cases | Archived Runs |",
                "| --- | --- | --- |",
            ]
        )
        for benchmark_id, case_count, run_count in archived_summary:
            lines.append(
                f"| `{benchmark_id}` | `{case_count}` | `{run_count}` |"
            )
    lines.extend(
        [
            "",
                "## Runs",
                "",
                "| Benchmark | Case | Arm | Attempt | Score | First Success Round | Round Rewards | Failure | Artifact |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for benchmark_id in sorted(benchmarks):
        benchmark = benchmarks[benchmark_id]
        cases = benchmark.get("cases") if isinstance(benchmark, dict) else {}
        if not isinstance(cases, dict):
            continue
        for case_id in sorted(cases):
            case = cases[case_id]
            runs = _active_ledger_runs(
                [
                    run
                    for run in (case.get("runs", []) if isinstance(case, dict) else [])
                    if isinstance(run, dict)
                ]
            )
            for run in runs:
                refs = run.get("artifact_refs") if isinstance(run.get("artifact_refs"), dict) else {}
                artifact = refs.get("compact_artifact_ref") or refs.get("result_ref") or refs.get("artifact_ref") or ""
                score = run.get("official_score")
                score_text = "missing" if score is None else str(score)
                first_success_round = run.get("first_success_round")
                first_success_text = (
                    str(first_success_round)
                    if isinstance(first_success_round, int)
                    and not isinstance(first_success_round, bool)
                    else ""
                )
                round_rewards_text = _round_reward_summary(run)
                attempt = _compact_text(run.get("ledger_attempt_kind"), limit=80)
                if not attempt:
                    attempt = _attempt_label_from_accounting(run)
                if not attempt:
                    attempt = (
                        "case_attempt"
                        if run.get("case_attempt_countable") is True
                        else ""
                    )
                lines.append(
                    "| "
                    f"`{benchmark_id}` | "
                    f"`{case_id}` | "
                    f"`{run.get('arm_id', '')}` | "
                    f"`{attempt}` | "
                    f"`{score_text}` | "
                    f"`{first_success_text}` | "
                    f"`{round_rewards_text}` | "
                    f"`{run.get('failure_class', 'none')}` | "
                    f"`{artifact}` |"
                )
    return "\n".join(lines) + "\n"


def update_benchmark_run_ledger(
    *,
    ledger_path: str | Path,
    benchmark_run: dict[str, Any],
    artifact_ref: str | Path | None = None,
    result_ref: str | Path | None = None,
    compact_artifact_ref: str | Path | None = None,
    run_group_id: str | None = None,
    arm_id: str | None = None,
    notes: str | None = None,
    recorded_at: str | None = None,
    dry_run: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    path = Path(ledger_path)
    entry = build_benchmark_run_ledger_entry(
        benchmark_run,
        artifact_ref=artifact_ref,
        result_ref=result_ref,
        compact_artifact_ref=compact_artifact_ref,
        run_group_id=run_group_id,
        arm_id=arm_id,
        notes=notes,
        recorded_at=recorded_at,
        cwd=cwd,
    )
    markdown_path = path.with_suffix(".md")
    if not _entry_is_public_ledger_closeout(entry):
        return {
            "ok": True,
            "dry_run": dry_run,
            "updated": False,
            "skipped": True,
            "skip_reason": "benchmark_run_not_terminal_for_public_ledger",
            "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
            "ledger_path": str(path),
            "markdown_path": str(markdown_path),
            "entry": entry,
            "case_decision": {},
        }
    if dry_run:
        updated = upsert_benchmark_run_ledger_entry(load_benchmark_run_ledger(path), entry)
    else:
        with _LedgerWriteLock(path):
            updated = upsert_benchmark_run_ledger_entry(
                load_benchmark_run_ledger(path),
                entry,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            tmp_markdown_path = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp_markdown_path.write_text(
                render_benchmark_run_ledger_markdown(updated),
                encoding="utf-8",
            )
            tmp_path.replace(path)
            tmp_markdown_path.replace(markdown_path)
    return {
        "ok": True,
        "dry_run": dry_run,
        "updated": not dry_run,
        "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
        "ledger_path": str(path),
        "markdown_path": str(markdown_path),
        "entry": entry,
        "case_decision": updated["benchmarks"][entry["benchmark_id"]]["cases"][
            entry["case_id"]
        ]["latest_decision"],
    }


def _matches_any_pattern(value: str, patterns: list[str]) -> bool:
    return any(pattern and pattern in value for pattern in patterns)


def archive_benchmark_run_ledger_runs(
    *,
    ledger_path: str | Path,
    benchmark_id: str,
    reason: str,
    run_group_contains: list[str] | None = None,
    keep_run_group_contains: list[str] | None = None,
    case_ids: list[str] | None = None,
    arm_ids: list[str] | None = None,
    archive_all_matching_benchmark: bool = False,
    archive_batch_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Mark matching run-ledger rows archived without deleting traceable evidence."""

    benchmark_filter = _compact_text(benchmark_id, limit=120)
    archive_reason = _compact_text(reason, limit=220)
    if not benchmark_filter:
        raise ValueError("benchmark_id is required")
    if not archive_reason:
        raise ValueError("archive reason is required")
    run_group_patterns = [
        _compact_text(item, limit=160)
        for item in (run_group_contains or [])
        if _compact_text(item, limit=160)
    ]
    keep_patterns = [
        _compact_text(item, limit=160)
        for item in (keep_run_group_contains or [])
        if _compact_text(item, limit=160)
    ]
    case_filters = {
        _compact_text(item, limit=160)
        for item in (case_ids or [])
        if _compact_text(item, limit=160)
    }
    arm_filters = {
        _compact_text(item, limit=120)
        for item in (arm_ids or [])
        if _compact_text(item, limit=120)
    }
    if not (
        archive_all_matching_benchmark
        or run_group_patterns
        or case_filters
        or arm_filters
    ):
        raise ValueError(
            "provide a run/case/arm filter, or pass --archive-all-matching-benchmark"
        )

    path = Path(ledger_path)
    markdown_path = path.with_suffix(".md")
    archived_at = _now_local_iso()
    batch_id = _compact_text(archive_batch_id, limit=120) or hashlib.sha1(
        f"{benchmark_filter}|{archive_reason}|{archived_at}".encode("utf-8")
    ).hexdigest()[:12]

    def apply_archive(ledger: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        normalized = _normalize_benchmark_run_ledger(dict(ledger))
        benchmarks = (
            normalized.get("benchmarks")
            if isinstance(normalized.get("benchmarks"), dict)
            else {}
        )
        matched_run_count = 0
        newly_archived_run_count = 0
        already_archived_run_count = 0
        kept_run_count = 0
        archived_samples: list[dict[str, Any]] = []
        benchmark = benchmarks.get(benchmark_filter)
        if isinstance(benchmark, dict):
            cases = benchmark.get("cases") if isinstance(benchmark.get("cases"), dict) else {}
            for case in cases.values():
                if not isinstance(case, dict):
                    continue
                case_id = _compact_text(case.get("case_id"), limit=160)
                runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
                for run in runs:
                    run_group_id = _compact_text(run.get("run_group_id"), limit=160)
                    arm = _compact_text(run.get("arm_id"), limit=120)
                    if keep_patterns and _matches_any_pattern(run_group_id, keep_patterns):
                        kept_run_count += 1
                        continue
                    if case_filters and case_id not in case_filters:
                        continue
                    if arm_filters and arm not in arm_filters:
                        continue
                    if run_group_patterns and not _matches_any_pattern(
                        run_group_id,
                        run_group_patterns,
                    ):
                        continue
                    matched_run_count += 1
                    if _ledger_run_archived(run):
                        already_archived_run_count += 1
                        continue
                    run["archive_state"] = "archived"
                    run["archive_reason"] = archive_reason
                    run["archive_batch_id"] = batch_id
                    run["archived_at"] = archived_at
                    newly_archived_run_count += 1
                    if len(archived_samples) < 20:
                        archived_samples.append(
                            {
                                "run_id": run.get("run_id"),
                                "case_id": case_id,
                                "arm_id": arm,
                                "run_group_id": run_group_id,
                                "official_score": run.get("official_score"),
                                "failure_class": run.get("failure_class"),
                            }
                        )
                case["runs"] = sorted(
                    runs,
                    key=lambda run: (
                        str(run.get("recorded_at", "")),
                        str(run.get("run_id", "")),
                    ),
                )
                case["active_run_count"] = len(_active_ledger_runs(case["runs"]))
                case["archived_run_count"] = len(_archived_ledger_runs(case["runs"]))
                case["latest_decision"] = _case_decision(case)
            benchmark["case_count"] = len(cases)
            benchmark["run_count"] = sum(
                len(value.get("runs", []))
                for value in cases.values()
                if isinstance(value, dict)
            )
            benchmark["active_case_count"] = sum(
                1
                for value in cases.values()
                if isinstance(value, dict)
                and value.get("active_run_count", 0)
            )
            benchmark["active_run_count"] = sum(
                int(value.get("active_run_count", 0))
                for value in cases.values()
                if isinstance(value, dict)
            )
            benchmark["archived_run_count"] = sum(
                int(value.get("archived_run_count", 0))
                for value in cases.values()
                if isinstance(value, dict)
            )
        normalized["updated_at"] = archived_at
        summary = {
            "schema_version": "benchmark_run_ledger_archive_v0",
            "archive_batch_id": batch_id,
            "benchmark_id": benchmark_filter,
            "reason": archive_reason,
            "matched_run_count": matched_run_count,
            "newly_archived_run_count": newly_archived_run_count,
            "already_archived_run_count": already_archived_run_count,
            "kept_run_count": kept_run_count,
            "archived_samples": archived_samples,
            "truncated": newly_archived_run_count > len(archived_samples),
        }
        return normalized, summary

    if dry_run:
        updated, summary = apply_archive(load_benchmark_run_ledger(path))
    else:
        with _LedgerWriteLock(path):
            updated, summary = apply_archive(load_benchmark_run_ledger(path))
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            tmp_markdown_path = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp_markdown_path.write_text(
                render_benchmark_run_ledger_markdown(updated),
                encoding="utf-8",
            )
            tmp_path.replace(path)
            tmp_markdown_path.replace(markdown_path)
    return {
        "ok": True,
        "dry_run": dry_run,
        "updated": not dry_run,
        "ledger_path": str(path),
        "markdown_path": str(markdown_path),
        "archive": summary,
    }


def _ledger_entry_signature(entry: dict[str, Any]) -> tuple[str, ...]:
    return (
        _compact_text(entry.get("benchmark_id"), limit=120),
        _compact_text(entry.get("case_id"), limit=160),
        _compact_text(entry.get("arm_id"), limit=120),
        _compact_text(entry.get("mode"), limit=120),
        _compact_text(entry.get("job_name"), limit=160),
        _compact_text(entry.get("score_status"), limit=80),
        _compact_text(entry.get("official_score"), limit=80),
        _compact_text(entry.get("failure_class"), limit=120),
    )


def _iter_ledger_runs(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    benchmarks = ledger.get("benchmarks") if isinstance(ledger.get("benchmarks"), dict) else {}
    for benchmark in benchmarks.values():
        if not isinstance(benchmark, dict):
            continue
        cases = benchmark.get("cases") if isinstance(benchmark.get("cases"), dict) else {}
        for case in cases.values():
            if not isinstance(case, dict):
                continue
            for run in case.get("runs") or []:
                if isinstance(run, dict):
                    runs.append(run)
    return runs


def _ledger_score_value(run: dict[str, Any]) -> float | None:
    value = run.get("official_score")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _current_aggregate_bucket(run: dict[str, Any] | None) -> str:
    if not isinstance(run, dict):
        return "missing"
    score = _ledger_score_value(run)
    if score is not None:
        if score >= 1.0:
            return "pass"
        if score > 0.0:
            return "partial"
        return "official_zero"
    labels = set(_compact_list(run.get("failure_labels"), limit=16))
    failure_class = _compact_text(run.get("failure_class"), limit=120)
    failure_scope = _compact_text(run.get("failure_scope"), limit=120)
    score_status = _compact_text(run.get("score_status"), limit=120)
    if (
        "verifier_no_reward" in labels
        or "verifier_reward_missing" in labels
        or "reward_missing" in failure_class
        or "verifier_no_reward" in failure_class
    ):
        return "verifier_no_reward"
    if (
        failure_scope == "runner_or_setup"
        or failure_scope == "score_missing"
        or "infrastructure" in failure_class
        or "setup" in failure_class
        or "runner" in failure_class
        or any("infra" in label or "setup" in label for label in labels)
    ):
        return "setup_runner_infra"
    if score_status == "missing":
        return "missing"
    return "missing"


_CURRENT_AGGREGATE_BUCKET_RANK = {
    "missing": 0,
    "setup_runner_infra": 1,
    "verifier_no_reward": 2,
    "official_zero": 3,
    "partial": 4,
    "pass": 5,
}


def _current_aggregate_run_sort_key(run: dict[str, Any]) -> tuple[Any, ...]:
    bucket = _current_aggregate_bucket(run)
    score = _ledger_score_value(run)
    score_rank = score if score is not None else -1.0
    return (
        _CURRENT_AGGREGATE_BUCKET_RANK.get(bucket, 0),
        score_rank,
        _compact_text(run.get("recorded_at"), limit=80),
        _compact_text(run.get("run_group_id"), limit=160),
        _compact_text(run.get("run_id"), limit=80),
    )


def _current_aggregate_run_summary(run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {"bucket": "missing"}
    keys = (
        "run_id",
        "recorded_at",
        "benchmark_id",
        "case_id",
        "run_group_id",
        "arm_id",
        "route",
        "artifact_refs",
        "status",
        "score_status",
        "official_score",
        "official_passed",
        "round_reward_count",
        "round_success_observed",
        "max_rounds_budget",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
        "failure_class",
        "failure_scope",
        "failure_labels",
        "attempt_lifecycle_phase",
        "attempt_failure_label",
        "attempt_failure_class",
        "runner_return_status",
        "runner_score_recovered_from_verifier_artifact",
        "verifier_reward_artifact_recovery_status",
        "verifier_reward_artifact_recovered",
        "official_result_json_materialized",
        "solution_quality_signals",
        "task_setup_preflight",
        "task_staging",
        "repair_class",
        "repair_priority",
    )
    summary = {key: run[key] for key in keys if key in run}
    summary["bucket"] = _current_aggregate_bucket(run)
    return summary


def build_benchmark_run_ledger_current_aggregate(
    ledger: dict[str, Any],
    *,
    benchmark_id: str = "skillsbench@1.1",
    canonical_case_ids: list[str] | None = None,
    source_ledger_count: int = 1,
) -> dict[str, Any]:
    """Build a current-case aggregate, preferring countable results over missing rows."""

    normalized = _normalize_benchmark_run_ledger(dict(ledger))
    benchmark = (
        normalized.get("benchmarks", {}).get(benchmark_id)
        if isinstance(normalized.get("benchmarks"), dict)
        else None
    )
    cases = benchmark.get("cases") if isinstance(benchmark, dict) else {}
    if not isinstance(cases, dict):
        cases = {}
    canonical_ids = [
        _compact_text(case_id, limit=160)
        for case_id in (canonical_case_ids or sorted(cases))
        if _compact_text(case_id, limit=160)
    ]
    if not canonical_case_ids:
        canonical_ids = sorted(cases)
    distribution = {
        "missing": 0,
        "setup_runner_infra": 0,
        "verifier_no_reward": 0,
        "official_zero": 0,
        "partial": 0,
        "pass": 0,
    }
    cases_by_bucket = {bucket: [] for bucket in distribution}
    case_best: dict[str, dict[str, Any]] = {}
    deduped_run_ids: set[str] = set()
    for case in cases.values():
        if not isinstance(case, dict):
            continue
        for run in _active_ledger_runs(
            [item for item in case.get("runs", []) if isinstance(item, dict)]
        ):
            run_id = _compact_text(run.get("run_id"), limit=80)
            if run_id:
                deduped_run_ids.add(run_id)
    for case_id in canonical_ids:
        case = cases.get(case_id)
        runs = []
        if isinstance(case, dict):
            runs = _active_ledger_runs(
                [item for item in case.get("runs", []) if isinstance(item, dict)]
            )
        best = max(runs, key=_current_aggregate_run_sort_key) if runs else None
        summary = _current_aggregate_run_summary(best)
        bucket = summary["bucket"]
        distribution[bucket] = distribution.get(bucket, 0) + 1
        cases_by_bucket.setdefault(bucket, []).append(case_id)
        case_best[case_id] = summary
    return {
        "schema_version": BENCHMARK_RUN_LEDGER_CURRENT_AGGREGATE_SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "canonical_total": len(canonical_ids),
        "canonical_covered": sum(
            count for bucket, count in distribution.items() if bucket != "missing"
        ),
        "distribution": distribution,
        "cases_by_bucket": {
            bucket: sorted(case_ids) for bucket, case_ids in cases_by_bucket.items()
        },
        "case_best": case_best,
        "deduped_run_count": len(deduped_run_ids),
        "source_ledger_files": source_ledger_count,
        "selection_policy": {
            "schema_version": "benchmark_run_ledger_current_selection_policy_v0",
            "rule": "prefer_countable_official_result_over_missing_or_infra_rows",
            "bucket_precedence": [
                "pass",
                "partial",
                "official_zero",
                "verifier_no_reward",
                "setup_runner_infra",
                "missing",
            ],
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "source_paths_recorded": False,
        },
    }


def merge_benchmark_run_ledgers(
    *,
    target_ledger_path: str | Path,
    source_ledger_paths: list[str | Path],
    benchmark_ids: list[str] | None = None,
    run_group_contains: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge public benchmark_run_ledger_v0 files into one canonical ledger."""

    if not source_ledger_paths:
        raise ValueError("at least one source benchmark run ledger is required")
    target_path = Path(target_ledger_path).expanduser()
    markdown_path = target_path.with_suffix(".md")
    benchmark_filter = {
        _compact_text(value, limit=120)
        for value in (benchmark_ids or [])
        if _compact_text(value, limit=120)
    }
    run_group_filters = [
        _compact_text(value, limit=160)
        for value in (run_group_contains or [])
        if _compact_text(value, limit=160)
    ]
    unique_sources: list[Path] = []
    seen_sources: set[str] = set()
    for source in source_ledger_paths:
        source_path = Path(source).expanduser()
        source_key = str(source_path.resolve(strict=False))
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        unique_sources.append(source_path)

    def apply_merge(start_ledger: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        updated = _normalize_benchmark_run_ledger(dict(start_ledger))
        before_run_ids = {
            _compact_text(run.get("run_id"), limit=80)
            for run in _iter_ledger_runs(updated)
            if _compact_text(run.get("run_id"), limit=80)
        }
        before_signatures = {_ledger_entry_signature(run) for run in _iter_ledger_runs(updated)}
        source_ledger_count = 0
        missing_source_count = 0
        source_run_count = 0
        considered_run_count = 0
        merged_run_count = 0
        skipped_run_count = 0
        skipped_by_reason: dict[str, int] = {}

        def skip(reason: str) -> None:
            nonlocal skipped_run_count
            skipped_run_count += 1
            skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1

        for source_path in unique_sources:
            if not source_path.exists():
                missing_source_count += 1
                continue
            source_ledger_count += 1
            source_ledger = load_benchmark_run_ledger(source_path)
            for run in _iter_ledger_runs(source_ledger):
                if not isinstance(run, dict):
                    continue
                source_run_count += 1
                benchmark_id = _compact_text(run.get("benchmark_id"), limit=120)
                if benchmark_filter and benchmark_id not in benchmark_filter:
                    skip("benchmark_filter")
                    continue
                run_group_id = _compact_text(run.get("run_group_id"), limit=160)
                if run_group_filters and not any(
                    token in run_group_id for token in run_group_filters
                ):
                    skip("run_group_filter")
                    continue
                if not _entry_is_public_ledger_closeout(run):
                    skip("non_terminal")
                    continue
                considered_run_count += 1
                updated = upsert_benchmark_run_ledger_entry(updated, dict(run))
                merged_run_count += 1

        updated = _normalize_benchmark_run_ledger(updated)
        after_runs = _iter_ledger_runs(updated)
        after_run_ids = {
            _compact_text(run.get("run_id"), limit=80)
            for run in after_runs
            if _compact_text(run.get("run_id"), limit=80)
        }
        after_signatures = {_ledger_entry_signature(run) for run in after_runs}
        summary = {
            "schema_version": "benchmark_run_ledger_merge_v0",
            "ok": True,
            "dry_run": dry_run,
            "updated": not dry_run,
            "ledger_path": str(target_path),
            "markdown_path": str(markdown_path),
            "source_ledger_count": source_ledger_count,
            "missing_source_count": missing_source_count,
            "source_run_count": source_run_count,
            "considered_run_count": considered_run_count,
            "merged_run_count": merged_run_count,
            "new_run_id_count": len(after_run_ids - before_run_ids),
            "new_signature_count": len(after_signatures - before_signatures),
            "target_run_count": len(after_runs),
            "skipped_run_count": skipped_run_count,
            "skipped_by_reason": skipped_by_reason,
            "benchmark_ids": sorted(benchmark_filter),
            "run_group_contains": run_group_filters,
            "source_paths_recorded": False,
        }
        return updated, summary

    if dry_run:
        _, summary = apply_merge(load_benchmark_run_ledger(target_path))
    else:
        with _LedgerWriteLock(target_path):
            updated, summary = apply_merge(load_benchmark_run_ledger(target_path))
            target_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
            tmp_markdown_path = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
            tmp_path.write_text(
                json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp_markdown_path.write_text(
                render_benchmark_run_ledger_markdown(updated),
                encoding="utf-8",
            )
            tmp_path.replace(target_path)
            tmp_markdown_path.replace(markdown_path)
    return {
        "ok": True,
        "dry_run": dry_run,
        "updated": not dry_run,
        "ledger_path": str(target_path),
        "markdown_path": str(markdown_path),
        "merge": summary,
    }


def _history_benchmark_run(record: dict[str, Any]) -> dict[str, Any] | None:
    if record.get("schema_version") == "benchmark_run_v0":
        return record
    nested = record.get("benchmark_run")
    if isinstance(nested, dict) and nested.get("schema_version") == "benchmark_run_v0":
        return nested
    return None


def check_benchmark_run_ledger_drift(
    *,
    history_records: list[dict[str, Any]],
    ledger: dict[str, Any],
    ledger_path: str | Path | None = None,
    limit: int = 20,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Compare compact benchmark_run_v0 history events with the public run ledger."""

    normalized_ledger = _normalize_benchmark_run_ledger(dict(ledger))
    ledger_runs = _iter_ledger_runs(normalized_ledger)
    ledger_run_ids = {
        _compact_text(run.get("run_id"), limit=80)
        for run in ledger_runs
        if _compact_text(run.get("run_id"), limit=80)
    }
    ledger_signatures = {_ledger_entry_signature(run) for run in ledger_runs}

    checked_history_run_count = 0
    terminal_history_run_count = 0
    matched_count = 0
    non_terminal_skipped_count = 0
    missing: list[dict[str, Any]] = []
    for record in history_records:
        if not isinstance(record, dict):
            continue
        benchmark_run = _history_benchmark_run(record)
        if not benchmark_run:
            continue
        checked_history_run_count += 1
        entry = build_benchmark_run_ledger_entry(
            benchmark_run,
            compact_artifact_ref=record.get("json_path")
            if isinstance(record.get("json_path"), str)
            else None,
            recorded_at=record.get("generated_at")
            if isinstance(record.get("generated_at"), str)
            else None,
            cwd=cwd,
        )
        if not _entry_is_public_ledger_closeout(entry):
            non_terminal_skipped_count += 1
            continue
        terminal_history_run_count += 1
        run_id = _compact_text(entry.get("run_id"), limit=80)
        signature = _ledger_entry_signature(entry)
        if run_id in ledger_run_ids or signature in ledger_signatures:
            matched_count += 1
            continue
        catch_up = "loopx benchmark run-ledger-upsert --benchmark-run-json <compact-benchmark-run-v0.json>"
        if ledger_path:
            ledger_ref_path = Path(ledger_path)
            ledger_ref = (
                "<benchmark-run-ledger.json>"
                if ledger_ref_path.is_absolute()
                else ledger_ref_path.as_posix()
            )
            catch_up += f" --run-ledger-path {ledger_ref}"
        if entry.get("run_group_id"):
            catch_up += f" --run-group-id {entry['run_group_id']}"
        if entry.get("arm_id"):
            catch_up += f" --arm-id {entry['arm_id']}"
        catch_up += " --execute"
        missing.append(
            {
                "run_id": run_id,
                "generated_at": _compact_text(record.get("generated_at"), limit=80),
                "benchmark_id": entry.get("benchmark_id"),
                "case_id": entry.get("case_id"),
                "arm_id": entry.get("arm_id"),
                "mode": entry.get("mode"),
                "job_name": entry.get("job_name"),
                "score_status": entry.get("score_status"),
                "official_score": entry.get("official_score"),
                "failure_class": entry.get("failure_class"),
                "catch_up_command_template": catch_up,
            }
        )

    limited_missing = missing[: max(0, limit)]
    return {
        "schema_version": "benchmark_run_ledger_drift_v0",
        "ok": True,
        "drift_detected": bool(missing),
        "ledger_schema_version": normalized_ledger.get("schema_version"),
        "ledger_run_count": len(ledger_runs),
        "checked_history_run_count": checked_history_run_count,
        "terminal_history_run_count": terminal_history_run_count,
        "matched_history_run_count": matched_count,
        "non_terminal_skipped_count": non_terminal_skipped_count,
        "missing_ledger_run_count": len(missing),
        "missing_runs": limited_missing,
        "truncated": len(missing) > len(limited_missing),
        "limit": limit,
        "read_boundary": {
            "compact_only": True,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }
