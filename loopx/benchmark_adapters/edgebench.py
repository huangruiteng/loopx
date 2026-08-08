from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any


EDGEBENCH_BENCHMARK_ID = "edgebench"
EDGEBENCH_UPSTREAM_REPOSITORY = "https://github.com/ByteDance-Seed/EdgeBench"
EDGEBENCH_OPEN_TASK_COUNT = 51
EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS = 43_200
EDGEBENCH_TIME_CHECKPOINT_SECONDS = (7_200, 14_400, 21_600, 28_800, 36_000, 43_200)
EDGEBENCH_PREFLIGHT_SCHEMA_VERSION = "edgebench_sforge_preflight_v0"
EDGEBENCH_RUN_PLAN_SCHEMA_VERSION = "edgebench_sforge_run_plan_v0"
EDGEBENCH_RESULT_SCHEMA_VERSION = "edgebench_compact_result_v0"

_PUBLIC_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}")


def _public_label(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not _PUBLIC_LABEL.fullmatch(text):
        raise ValueError(f"{field} must be a public-safe label")
    return text


def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_non_negative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _boundary() -> dict[str, bool]:
    return {
        "no_execution": True,
        "container_started": False,
        "task_body_read": False,
        "hidden_tests_read": False,
        "model_api_invoked": False,
        "raw_logs_read": False,
        "raw_trajectory_read": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
        "command_argv_recorded": False,
        "upload_invoked": False,
        "submit_invoked": False,
        "leaderboard_evidence": False,
    }


def build_edgebench_sforge_preflight(
    *,
    task_id: str,
    backend: str,
    linux_host: bool,
    sforge_available: bool,
    container_runtime_available: bool,
    task_catalog_ready: bool,
    task_images_ready: bool,
    judge_ready: bool,
) -> dict[str, Any]:
    task_label = _public_label(task_id, field="task_id")
    if backend not in {"docker", "kubernetes"}:
        raise ValueError("backend must be docker or kubernetes")

    checks = {
        "linux_host": bool(linux_host),
        "sforge_available": bool(sforge_available),
        "container_runtime_available": bool(container_runtime_available),
        "task_catalog_ready": bool(task_catalog_ready),
        "task_images_ready": bool(task_images_ready),
        "judge_ready": bool(judge_ready),
    }
    blocker_order = (
        ("linux_host", "edgebench_linux_host_required"),
        ("sforge_available", "sforge_not_available"),
        ("container_runtime_available", f"{backend}_runtime_not_available"),
        ("task_catalog_ready", "edgebench_task_catalog_not_ready"),
        ("task_images_ready", "edgebench_task_images_not_ready"),
        ("judge_ready", "edgebench_judge_not_ready"),
    )
    blockers = [blocker for check, blocker in blocker_order if not checks[check]]
    ready = not blockers
    return {
        "schema_version": EDGEBENCH_PREFLIGHT_SCHEMA_VERSION,
        "benchmark_id": EDGEBENCH_BENCHMARK_ID,
        "upstream_repository": EDGEBENCH_UPSTREAM_REPOSITORY,
        "open_task_count": EDGEBENCH_OPEN_TASK_COUNT,
        "task_id": task_label,
        "backend": backend,
        "ready": ready,
        "first_blocker": blockers[0] if blockers else "ready_for_edgebench_run_plan",
        "blockers": blockers,
        "checks": checks,
        "score_policy": {
            "selection": "best_submission_over_time",
            "time_checkpoints_seconds": list(EDGEBENCH_TIME_CHECKPOINT_SECONDS),
            "official_timeout_seconds": EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS,
        },
        "boundary": _boundary(),
        "decision": {
            "next_allowed_action": (
                "build_single_task_edgebench_run_plan"
                if ready
                else "repair_edgebench_preflight_before_run_plan"
            ),
            "must_not_claim": [
                "task execution",
                "official EdgeBench score",
                "leaderboard comparability",
                "LoopX treatment benefit",
            ],
        },
    }


def build_edgebench_sforge_run_plan(
    *,
    preflight: Mapping[str, Any],
    agent: str,
    model: str,
    timeout_seconds: int,
    run_id: str,
) -> dict[str, Any]:
    task_id = _public_label(preflight.get("task_id"), field="task_id")
    agent_label = _public_label(agent, field="agent")
    model_label = _public_label(model, field="model")
    run_label = _public_label(run_id, field="run_id")
    if timeout_seconds <= 0 or timeout_seconds > EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS:
        raise ValueError(
            f"timeout_seconds must be between 1 and {EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS}"
        )

    checks = preflight.get("checks")
    canonical_preflight = (
        preflight.get("schema_version") == EDGEBENCH_PREFLIGHT_SCHEMA_VERSION
        and preflight.get("benchmark_id") == EDGEBENCH_BENCHMARK_ID
        and preflight.get("backend") in {"docker", "kubernetes"}
        and isinstance(checks, Mapping)
        and all(
            checks.get(field) is True
            for field in (
                "linux_host",
                "sforge_available",
                "container_runtime_available",
                "task_catalog_ready",
                "task_images_ready",
                "judge_ready",
            )
        )
    )
    preflight_ready = preflight.get("ready") is True and canonical_preflight
    blockers = (
        []
        if preflight_ready
        else [
            (
                str(preflight.get("first_blocker") or "edgebench_preflight_not_ready")
                if canonical_preflight
                else "edgebench_preflight_contract_invalid"
            )
        ]
    )
    return {
        "schema_version": EDGEBENCH_RUN_PLAN_SCHEMA_VERSION,
        "benchmark_id": EDGEBENCH_BENCHMARK_ID,
        "task_id": task_id,
        "ready": preflight_ready,
        "first_blocker": blockers[0] if blockers else "ready_for_private_sforge_launch",
        "blockers": blockers,
        "runner": {
            "provider": "sforge",
            "backend": preflight.get("backend"),
            "entrypoint": "sforge run",
            "agent": agent_label,
            "model": model_label,
            "run_id": run_label,
            "timeout_seconds": timeout_seconds,
            "required_secret_names": ["SFORGE_AGENT_API_KEY"],
            "optional_endpoint_names": ["SFORGE_AGENT_API_BASE_URL"],
        },
        "evaluation": {
            "iterative_feedback": True,
            "selection": "best_submission_over_time",
            "judge_isolated_from_work_container": True,
            "official_setting": False,
            "leaderboard_eligible": False,
        },
        "boundary": _boundary(),
        "decision": {
            "next_allowed_action": (
                "launch_private_single_task_sforge_run"
                if preflight_ready
                else "repair_edgebench_preflight_before_launch"
            ),
            "requires_explicit_launch_authority": True,
            "requires_private_credentials": True,
            "must_not_claim": [
                "official EdgeBench setting",
                "leaderboard comparability",
                "task success before compact result ingest",
            ],
        },
    }


def reduce_edgebench_final_result(
    *,
    task_id: str,
    run_id: str,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    task_label = _public_label(task_id, field="task_id")
    run_label = _public_label(run_id, field="run_id")
    best_score = _optional_number(result.get("best_score"))
    best_pass_rate = _optional_number(result.get("best_pass_rate"))
    total_rounds = _optional_non_negative_int(result.get("total_rounds"))
    agent_submissions = _optional_non_negative_int(result.get("agent_submissions"))
    auto_submissions = _optional_non_negative_int(result.get("auto_submissions"))
    runtime_seconds = _optional_number(result.get("runtime_seconds"))
    resume_count = _optional_non_negative_int(result.get("resume_count"))
    best_round = result.get("best_round")
    best_round_label = (
        _public_label(best_round, field="best_round")
        if isinstance(best_round, str) and best_round.strip()
        else None
    )

    blockers: list[str] = []
    if best_score is None and best_pass_rate is None:
        blockers.append("edgebench_best_metric_missing")
    if total_rounds is None or total_rounds <= 0:
        blockers.append("edgebench_submission_rounds_missing")
    elif (
        agent_submissions is not None
        and auto_submissions is not None
        and total_rounds != agent_submissions + auto_submissions
    ):
        blockers.append("edgebench_submission_rounds_mismatch")
    if runtime_seconds is None or runtime_seconds < 0:
        blockers.append("edgebench_runtime_missing")

    countable = not blockers
    return {
        "schema_version": EDGEBENCH_RESULT_SCHEMA_VERSION,
        "benchmark_id": EDGEBENCH_BENCHMARK_ID,
        "task_id": task_label,
        "run_id": run_label,
        "countable": countable,
        "first_blocker": blockers[0] if blockers else "compact_edgebench_result_ready",
        "blockers": blockers,
        "metrics": {
            "best_score": best_score,
            "best_pass_rate": best_pass_rate,
            "best_round": best_round_label,
            "total_rounds": total_rounds,
            "agent_submissions": agent_submissions,
            "auto_submissions": auto_submissions,
            "runtime_seconds": runtime_seconds,
            "resume_count": resume_count,
            "timed_out": result.get("timed_out") is True,
        },
        "score_policy": {
            "selection": "best_submission_over_time",
            "official_score_claimed": False,
            "leaderboard_comparable": False,
        },
        "boundary": {
            **_boundary(),
            "compact_result_read": True,
            "raw_logs_read": False,
            "raw_trajectory_read": False,
        },
        "decision": {
            "next_allowed_action": (
                "ingest_compact_edgebench_result_into_benchmark_ledger"
                if countable
                else "repair_compact_edgebench_result"
            ),
            "must_not_claim": [
                "official EdgeBench score",
                "leaderboard comparability",
                "LoopX treatment benefit",
            ],
        },
    }
