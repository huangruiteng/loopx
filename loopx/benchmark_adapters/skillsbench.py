from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from ..benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE,
    benchmark_case_active_state_path,
)
from ..benchmark_core import (
    BenchmarkFailureClass,
    RunPermissionAction,
    build_benchmark_attempt_accounting,
    build_run_permission_policy,
    canonical_lifecycle,
)
from ..codex_goal_baseline import build_codex_app_server_goal_worker_plan
from .skillsbench_signals import build_skillsbench_solution_quality_signals
from .skillsbench_result_discovery import (
    SKILLSBENCH_RESULT_DISCOVERY_SCHEMA_VERSION,
    discover_skillsbench_benchflow_result_json,
)


SKILLSBENCH_DEFAULT_DATASET = "skillsbench@1.1"
SKILLSBENCH_DEFAULT_TASK = "citation-check"
SKILLSBENCH_DEFAULT_MODEL = "gpt-5.5"
SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID = "skillsbench-case"
SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH = benchmark_case_active_state_path(
    SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID
)
SKILLSBENCH_RAW_CODEX_AUTONOMOUS_ROUTE = "raw-codex-autonomous-max5"
SKILLSBENCH_LOOPX_PRODUCT_MODE_ROUTE = "loopx-product-mode"
SKILLSBENCH_LOOPX_GOAL_START_PRODUCT_MODE_ROUTE = "loopx-goal-start-product-mode"
SKILLSBENCH_LOOPX_PRODUCT_MODE_TREATMENT_ROUTES = frozenset(
    {
        SKILLSBENCH_LOOPX_PRODUCT_MODE_ROUTE,
        SKILLSBENCH_LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
    }
)
SKILLSBENCH_ROUTES = (
    "codex-acp-blind-loop-baseline",
    "loopx-blind-loop-treatment",
    "loopx-prompt-polling-test",
    "codex-app-server-goal-baseline",
    "codex-goal-mode-baseline",
    "curated-skills-baseline",
    SKILLSBENCH_RAW_CODEX_AUTONOMOUS_ROUTE,
    SKILLSBENCH_LOOPX_PRODUCT_MODE_ROUTE,
    SKILLSBENCH_LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
)
SKILLSBENCH_DEFAULT_ROUTE = "loopx-blind-loop-treatment"


BENCHMARK_MODEL_CONTROL_SCHEMA_VERSION = "benchmark_model_control_v0"
CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL = "codex_acp_set_model_unsupported"
SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION = (
    "skillsbench_local_driver_a2a_contract_v0"
)
SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION = (
    "skillsbench_worker_handshake_preflight_v0"
)
SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_SCHEMA_VERSION = (
    "skillsbench_verifier_dependency_prewarm_plan_v0"
)
SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION = (
    "skillsbench_app_server_goal_worker_contract_v0"
)
SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_BLOCKER = (
    "skillsbench_verifier_dependency_prewarm_required"
)
SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_APT_PACKAGES = (
    "python3",
    "python3-pip",
    "ca-certificates",
    "curl",
)
SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_REQUIRED_TOOLS = (
    "uv",
    "uvx",
)
SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_SCOPES = (
    "temporary_task_copy",
    "wrapper_layer",
    "derived_sandbox_image",
)
SKILLSBENCH_LOCAL_DRIVER_A2A_PAIR_ROUTES = (
    SKILLSBENCH_RAW_CODEX_AUTONOMOUS_ROUTE,
    SKILLSBENCH_LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
)


def _is_skillsbench_loopx_product_mode_treatment_route(route: str) -> bool:
    return route in SKILLSBENCH_LOOPX_PRODUCT_MODE_TREATMENT_ROUTES


def _is_skillsbench_goal_start_product_mode_route(route: str) -> bool:
    return route == SKILLSBENCH_LOOPX_GOAL_START_PRODUCT_MODE_ROUTE


def _skillsbench_product_mode_arm_id(route: str) -> str:
    if _is_skillsbench_goal_start_product_mode_route(route):
        return "loopx_goal_start_product_mode"
    return "loopx_product_mode"


def _skillsbench_product_mode_outer_controller(route: str) -> str:
    if _is_skillsbench_goal_start_product_mode_route(route):
        return "loopx_goal_start_product_mode"
    return "loopx_product_mode"


def _skillsbench_public_safe_label(value: Any, *, limit: int = 120) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    cleaned = []
    for char in text:
        cleaned.append(char.lower() if char.isalnum() or char in {"-", "_", ".", ":"} else "-")
    label = "".join(cleaned).strip("-_.:")
    while "--" in label:
        label = label.replace("--", "-")
    return (label or None)[:limit]


def _skillsbench_rollout_reward_artifact(
    result_path: Path,
) -> tuple[float | None, str | None]:
    reward_path = result_path.parent / "verifier" / "reward.txt"
    if not reward_path.exists():
        return None, None
    try:
        raw_reward = reward_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, None
    try:
        reward = float(raw_reward)
    except ValueError:
        return None, None
    if not math.isfinite(reward):
        return None, None
    return reward, "official_skillsbench_rollout_verifier_reward_txt"


def skillsbench_route_contract(route: str) -> dict[str, Any]:
    if route == "codex-acp-blind-loop-baseline":
        return {
            "mode": "skillsbench_codex_acp_blind_loop_baseline",
            "arm_id": "codex_acp_blind_loop_baseline",
            "source_runner": "loopx_skillsbench_codex_acp_blind_loop_baseline_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_ordinary_agent_blind_loop_no_goal_no_reward_feedback",
            "curated_skills_visible": False,
            "loopx_automation_loop": False,
            "loopx_inside_case": False,
            "blind_loop": True,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run ordinary Codex ACP/CLI with the same fixed blind loop budget "
                "as treatment, with no /goal mode and no official reward/pass-fail "
                "or verifier output returned to the agent"
            ),
        }
    if route in {
        "loopx-blind-loop-treatment",
        "loopx-prompt-polling-test",
    }:
        current_name = route == "loopx-prompt-polling-test"
        return {
            "mode": (
                "skillsbench_loopx_prompt_polling_test"
                if current_name
                else "skillsbench_loopx_blind_loop_treatment"
            ),
            "arm_id": (
                "loopx_prompt_polling_test"
                if current_name
                else "loopx_blind_loop_treatment"
            ),
            "source_runner": "loopx_skillsbench_blind_loop_treatment_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": (
                "codex_acp_ordinary_agent_with_outer_loopx_prompt_polling_no_reward_feedback"
                if current_name
                else "codex_acp_ordinary_agent_with_outer_loopx_blind_loop_no_reward_feedback"
            ),
            "curated_skills_visible": False,
            "loopx_automation_loop": True,
            "loopx_inside_case": False,
            "blind_loop": True,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run LoopX outer automation with a fixed blind loop budget; "
                "do not return official reward, pass/fail, verifier error, or "
                "verifier output to the in-case agent during the loop"
            ),
        }
    if route == SKILLSBENCH_RAW_CODEX_AUTONOMOUS_ROUTE:
        return {
            "mode": "skillsbench_raw_codex_autonomous_max5_baseline",
            "arm_id": "raw_codex_autonomous_max5",
            "source_runner": "loopx_skillsbench_raw_codex_autonomous_max5_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "raw_codex_autonomous_max5_no_loopx_no_reward_feedback",
            "curated_skills_visible": False,
            "loopx_automation_loop": False,
            "loopx_inside_case": False,
            "product_mode": True,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run raw Codex autonomous max5 with no LoopX state/todo/"
                "replan/CLI surface and no official reward or verifier feedback "
                "returned during execution"
            ),
        }
    if _is_skillsbench_loopx_product_mode_treatment_route(route):
        goal_start_product_mode = _is_skillsbench_goal_start_product_mode_route(route)
        return {
            "mode": (
                "skillsbench_loopx_goal_start_product_mode_treatment"
                if goal_start_product_mode
                else "skillsbench_loopx_product_mode_treatment"
            ),
            "arm_id": _skillsbench_product_mode_arm_id(route),
            "source_runner": (
                "loopx_skillsbench_goal_start_product_lifecycle_driver"
                if goal_start_product_mode
                else "loopx_skillsbench_canonical_product_lifecycle_driver"
            ),
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": (
                "codex_agent_with_loopx_goal_start_ranked_todo_plan_selected_p0_lifecycle_no_reward_feedback"
                if goal_start_product_mode
                else "codex_agent_with_loopx_state_todo_replan_cli_no_reward_feedback"
            ),
            "curated_skills_visible": False,
            "loopx_automation_loop": True,
            "loopx_inside_case": True,
            "product_mode": True,
            "verifier_failure_feedback_todo_route": False,
            "verifier_failure_feedback_forwarded": False,
            "verifier_failure_todo_required": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": True,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": True,
            "first_blocker": "none",
            "next_action": (
                "run LoopX goal-start product-mode treatment with a compact ranked "
                "todo plan, selected P0 todo lifecycle, replan/status writeback, "
                "and LoopX CLI/ledger surfaces; do not return official reward or "
                "verifier feedback during execution"
                if goal_start_product_mode
                else (
                    "run LoopX product-mode treatment with goal state, todos, "
                    "replan/status writeback, and LoopX CLI/ledger surfaces; do not "
                    "return official reward or verifier feedback during execution"
                )
            ),
        }
    if route == "codex-goal-mode-baseline":
        return {
            "mode": "codex_goal_mode_baseline",
            "arm_id": "codex_goal_mode_baseline",
            "source_runner": "loopx_skillsbench_codex_goal_mode_baseline_skeleton",
            "inner_codex_goal_mode": True,
            "native_goal_mode_requested": True,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": (
                "unconfirmed_acp_prompt_text_not_interactive_cli_slash_command"
            ),
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_goal_prompt_request_no_reward_followup_unconfirmed_native_goal_mode",
            "curated_skills_visible": False,
            "loopx_automation_loop": False,
            "loopx_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run a real no-skill Codex goal-mode SkillsBench baseline, ingest "
                "only compact benchmark_run_v0, and require attributable failure "
                "before any automation-loop treatment"
            ),
        }
    if route == "codex-app-server-goal-baseline":
        return {
            "mode": "skillsbench_codex_app_server_goal_baseline",
            "arm_id": "codex_app_server_goal_baseline",
            "source_runner": "loopx_skillsbench_host_codex_app_server_goal_worker",
            "inner_codex_goal_mode": True,
            "native_goal_mode_requested": True,
            "native_goal_mode_invoked": True,
            "native_goal_mode_confirmation_status": (
                "requires_thread_goal_set_get_and_turn_start_compact_proof"
            ),
            "codex_acp_protocol_used": False,
            "skillsbench_route_semantics": (
                "host_codex_app_server_goal_worker_no_reward_feedback"
            ),
            "curated_skills_visible": False,
            "loopx_automation_loop": False,
            "loopx_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": True,
            "first_blocker": "skillsbench_app_server_goal_worker_compact_proof_missing",
            "next_action": (
                "launch SkillsBench through Codex app-server Goal APIs "
                "thread/start plus thread/goal/set/get plus turn/start, ingest "
                "only compact no-upload evidence, and fail closed rather than "
                "falling back to ACP or slash-prefix prompt experiments"
            ),
        }
    if route == "curated-skills-baseline":
        return {
            "mode": "skillsbench_curated_skills_baseline",
            "arm_id": "curated_skills_baseline",
            "source_runner": "loopx_skillsbench_curated_skills_baseline_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_curated_skills_visible_control",
            "curated_skills_visible": True,
            "loopx_automation_loop": False,
            "loopx_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_loopx_treatment": False,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "use curated-skills baseline only as a SkillsBench-native control "
                "after the no-skill baseline and treatment routes are ledgered"
            ),
        }
    raise ValueError(f"unsupported SkillsBench route: {route}")




def skillsbench_job_name(dataset: str, task_id: str, route: str) -> str:
    raw = f"{dataset}_{task_id}_{route}"
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").lower()


def build_skillsbench_run_permission_policy(
    *,
    route: str = SKILLSBENCH_DEFAULT_ROUTE,
    max_wall_time_minutes: int = 480,
) -> dict[str, Any]:
    """Build the public no-upload execution boundary for SkillsBench routes."""

    safe_route = (
        _skillsbench_public_safe_label(route, limit=80)
        or SKILLSBENCH_DEFAULT_ROUTE
    )
    policy_route = re.sub(r"[^A-Za-z0-9]+", "_", safe_route).strip("_").lower()
    return build_run_permission_policy(
        policy_id=f"skillsbench_{policy_route}_no_upload_20260622",
        allowed_actions=(
            RunPermissionAction.CODEX_MODEL_INVOCATION.value,
            RunPermissionAction.LOCAL_DOCKER_RUNNER.value,
            RunPermissionAction.BENCHMARK_DEPENDENCY_FETCH.value,
            RunPermissionAction.COMPACT_RESULT_REDUCTION.value,
        ),
        max_wall_time_minutes=max_wall_time_minutes,
        no_upload_required=True,
        compact_observation_only=True,
    )


_SKILLSBENCH_SETUP_FAILURE_LABELS = {
    "skillsbench_result_json_missing_after_runner_exit",
    "skillsbench_runner_setup_error",
    "skillsbench_environment_setup_error",
    "skillsbench_docker_setup_preflight_blocked",
    "skillsbench_docker_compose_setup_failure",
    "skillsbench_docker_compose_unclassified_setup_failure",
    "skillsbench_compose_setup_blocked_before_agent_rounds",
    "skillsbench_runner_setup_blocked_before_agent_rounds",
    "skillsbench_app_server_goal_pre_agent_materialization_blocked",
}

_SKILLSBENCH_PRE_AGENT_SETUP_STATUS_LABELS = {
    "compose_setup_blocked_before_agent_rounds": (
        "skillsbench_compose_setup_blocked_before_agent_rounds"
    ),
    "runner_setup_blocked_before_agent_rounds": (
        "skillsbench_runner_setup_blocked_before_agent_rounds"
    ),
}

_SKILLSBENCH_PRE_AGENT_SETUP_REPLACEABLE_ATTRIBUTIONS = {
    "",
    "none",
    "score_missing",
    "skillsbench_runner_error",
    "skillsbench_result_json_missing_after_runner_exit",
    "official_score_zero_case_failure",
    "official_verifier_solution_failure",
    "verifier_infrastructure_failure",
}


def _skillsbench_number(value: Any) -> float | int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _skillsbench_official_score_missing(benchmark_run: dict[str, Any]) -> bool:
    official = (
        benchmark_run.get("official_task_score")
        if isinstance(benchmark_run.get("official_task_score"), dict)
        else {}
    )
    if _skillsbench_number(official.get("value")) is not None:
        return False
    return _skillsbench_number(benchmark_run.get("official_score")) is None


def _skillsbench_pre_agent_setup_diagnostic_label(
    benchmark_run: dict[str, Any],
) -> str:
    diagnostic = benchmark_run.get("compose_setup_diagnostic")
    if not isinstance(diagnostic, dict):
        return ""
    label = _SKILLSBENCH_PRE_AGENT_SETUP_STATUS_LABELS.get(
        str(diagnostic.get("status") or "")
    )
    if not label:
        return ""
    route = str(benchmark_run.get("route") or "")
    mode = str(benchmark_run.get("mode") or "")
    if route != "codex-app-server-goal-baseline" and mode != (
        "skillsbench_codex_app_server_goal_baseline"
    ):
        return ""
    if benchmark_run.get("native_goal_worker_route") is not True:
        validation = benchmark_run.get("validation")
        if not isinstance(validation, dict) or validation.get(
            "native_goal_worker_route"
        ) is not True:
            return ""
    if benchmark_run.get("native_goal_worker_connected") is True:
        return ""
    trace_count = benchmark_run.get("native_goal_worker_trace_count")
    if (
        isinstance(trace_count, int)
        and not isinstance(trace_count, bool)
        and trace_count > 0
    ):
        return ""
    if diagnostic.get("agent_rounds_started") is True:
        return ""
    if not _skillsbench_official_score_missing(benchmark_run):
        return ""
    return label


def apply_skillsbench_pre_agent_setup_diagnostic_attribution(
    benchmark_run: dict[str, Any],
) -> dict[str, Any]:
    """Project app-server pre-agent setup blockers into terminal attribution.

    The app-server Goal route can be selected before BenchFlow/compose has
    materialized the native worker. Without this projection, downstream
    reducers only see `native_goal_worker_route=true` plus no worker trace and
    report a misleading worker connection failure.
    """

    label = _skillsbench_pre_agent_setup_diagnostic_label(benchmark_run)
    if not label:
        return benchmark_run
    current = str(benchmark_run.get("score_failure_attribution") or "")
    if (
        current in _SKILLSBENCH_PRE_AGENT_SETUP_REPLACEABLE_ATTRIBUTIONS
        or current.startswith("skillsbench_native_goal_worker_")
    ):
        benchmark_run["score_failure_attribution"] = label
        benchmark_run["first_blocker"] = label
    benchmark_run["pre_agent_setup_materialization_blocked"] = True
    benchmark_run["native_goal_worker_pre_agent_setup_blocked"] = True

    labels = [
        item
        for item in benchmark_run.get("failure_attribution_labels", [])
        if isinstance(item, str) and item
    ]
    for item in (
        label,
        "skillsbench_app_server_goal_pre_agent_materialization_blocked",
        "skillsbench_runner_setup_error",
    ):
        if item not in labels:
            labels.append(item)
    benchmark_run["failure_attribution_labels"] = labels

    runner_failure = benchmark_run.get("runner_failure")
    if not isinstance(runner_failure, dict):
        runner_failure = {
            "schema_version": "skillsbench_runner_failure_v0",
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }
        benchmark_run["runner_failure"] = runner_failure
    runner_failure["exception_type"] = label
    runner_failure["failure_class"] = label
    runner_failure["pre_agent_setup_materialization_blocked"] = True

    attempt_accounting = benchmark_run.get("attempt_accounting")
    if isinstance(attempt_accounting, dict):
        attempt_accounting["failure_label"] = label
        attempt_accounting["failure_class"] = (
            BenchmarkFailureClass.JOB_MATERIALIZATION_FAILED.value
        )
    return benchmark_run


def _skillsbench_verifier_uv_bootstrap_failure(verifier_error_text: str) -> bool:
    text = str(verifier_error_text or "").lower()
    if not text:
        return False
    indicators = (
        "uvx: command not found",
        "uv: command not found",
        "failed to download",
        "releases.astral.sh",
        "astral.sh/uv",
        "uv-x86_64-unknown-linux-gnu",
        "uv-aarch64-unknown-linux-gnu",
        "installer_download_url",
    )
    if any(indicator in text for indicator in indicators) and re.search(
        r"\buvx?\b|astral|releases\.astral|installer_download_url",
        text,
    ):
        return True
    return bool(
        re.search(r"\buvx?\b.*(?:download|bootstrap|not found|installer)", text)
        or re.search(r"(?:download|bootstrap|installer).*\buvx?\b", text)
    )


def _skillsbench_attempt_setup_blocked(failure_labels: Iterable[str]) -> bool:
    return any(
        str(label) in _SKILLSBENCH_SETUP_FAILURE_LABELS for label in failure_labels
    )


def _skillsbench_attempt_failure_class(
    *,
    failure_labels: Iterable[str],
    reward_value: float | int | None,
    verifier_error_text: str,
    score_failure_attribution: str,
) -> BenchmarkFailureClass:
    if _skillsbench_attempt_setup_blocked(failure_labels):
        return BenchmarkFailureClass.JOB_MATERIALIZATION_FAILED
    if score_failure_attribution in {
        "skillsbench_host_local_acp_idle_no_task_output_progress",
        "skillsbench_product_mode_solver_activity_gap",
        "skillsbench_acp_agent_message_only_no_tool_calls",
    }:
        if (
            score_failure_attribution
            == "skillsbench_host_local_acp_idle_no_task_output_progress"
        ):
            return BenchmarkFailureClass.OFFICIAL_SCORE_FAILED
        return BenchmarkFailureClass.SOLVER_FAILED
    if score_failure_attribution.startswith("skillsbench_native_goal_worker_"):
        return BenchmarkFailureClass.JOB_MATERIALIZATION_FAILED
    if "skillsbench_verifier_uv_bootstrap_failure" in set(failure_labels):
        return BenchmarkFailureClass.VERIFIER_FAILED
    if verifier_error_text and reward_value is None:
        return BenchmarkFailureClass.VERIFIER_FAILED
    if reward_value is None and score_failure_attribution != "none":
        return BenchmarkFailureClass.OFFICIAL_SCORE_FAILED
    if reward_value == 0:
        return BenchmarkFailureClass.SOLVER_FAILED
    return BenchmarkFailureClass.NONE


def _skillsbench_attempt_lifecycle(
    *,
    setup_blocked: bool,
    reward_value: float | int | None,
    verifier_error_text: str,
    tool_calls: int,
    native_goal_worker_trace_observed: bool,
    controller_trace_present: bool,
) -> dict[str, Any]:
    if setup_blocked:
        return canonical_lifecycle(
            process_started=True,
            runner_accepted_args=True,
        )

    verifier_or_score_seen = reward_value is not None or bool(verifier_error_text)
    worker_seen = (
        tool_calls > 0
        or native_goal_worker_trace_observed
        or controller_trace_present
        or verifier_or_score_seen
    )
    return canonical_lifecycle(
        process_started=True,
        runner_accepted_args=True,
        job_root_materialized=True,
        trial_started=True,
        worker_started=worker_seen,
        result_written=True,
        verifier_scored=verifier_or_score_seen,
    )


def build_skillsbench_app_server_goal_worker_contract(
    *,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = SKILLSBENCH_DEFAULT_TASK,
    cwd: str = "<skillsbench-task-workspace>",
    model: str = SKILLSBENCH_DEFAULT_MODEL,
    reasoning_effort: str = "high",
    prompt_style: str = "bridge-only",
    codex_bin: str = "codex",
    sandbox: str = "workspace-write",
    approval_policy: str = "never",
    no_upload: bool = True,
    submit_enabled: bool = False,
    compact_reducer_ready: bool = True,
    runner_integration_ready: bool = False,
    raw_task_text_public: bool = False,
    raw_logs_public: bool = False,
    raw_trajectory_public: bool = False,
    include_loopx_state: bool = False,
    known_blockers: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the public-safe SkillsBench native Codex Goal worker contract.

    This contract is the benchmark-specific wrapper around the generic Codex
    app-server Goal worker plan. It intentionally records only task identity,
    route semantics, method requirements, and boundary flags. The task body
    itself stays inside the private SkillsBench sandbox and is not copied into
    public state.
    """

    safe_dataset = _skillsbench_public_safe_label(dataset, limit=80)
    safe_task_id = _skillsbench_public_safe_label(task_id, limit=120)
    blockers = [str(item) for item in known_blockers if str(item)]
    safe_prompt_style = _skillsbench_public_safe_label(prompt_style, limit=40)
    if safe_prompt_style not in {"bridge-only", "native-goal", "cli-exec-like"}:
        blockers.append("skillsbench_app_server_goal_prompt_style_invalid")
        safe_prompt_style = "bridge-only"
    if not safe_dataset:
        safe_dataset = SKILLSBENCH_DEFAULT_DATASET
        blockers.append("skillsbench_dataset_not_public_safe")
    if not safe_task_id:
        safe_task_id = SKILLSBENCH_DEFAULT_TASK
        blockers.append("skillsbench_task_id_not_public_safe")
    if not no_upload:
        blockers.append("skillsbench_no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("skillsbench_submit_must_remain_disabled")
    if raw_task_text_public:
        blockers.append("skillsbench_raw_task_text_publication_forbidden")
    if raw_logs_public:
        blockers.append("skillsbench_raw_logs_publication_forbidden")
    if raw_trajectory_public:
        blockers.append("skillsbench_raw_trajectory_publication_forbidden")
    if include_loopx_state:
        blockers.append("skillsbench_native_baseline_must_not_include_loopx_state")
    if not compact_reducer_ready:
        blockers.append("skillsbench_compact_reducer_not_ready")

    objective = f"Complete SkillsBench task {safe_task_id} with no upload"
    task_instruction = (
        "Solve the SkillsBench task mounted in the current benchmark workspace. "
        "Use the official private task files available in the sandbox, do not "
        "upload or submit externally, and do not copy raw task text, raw logs, "
        "or raw trajectories into public artifacts."
    )
    worker_plan = build_codex_app_server_goal_worker_plan(
        objective=objective,
        task_instruction=task_instruction,
        cwd=cwd,
        sandbox=sandbox,
        approval_policy=approval_policy,
        model=model,
        effort=reasoning_effort,
    )
    ready = not blockers and compact_reducer_ready and no_upload and not submit_enabled
    if ready:
        first_blocker = "ready_for_skillsbench_app_server_goal_worker"
        next_action = "wire_or_launch_skillsbench_native_app_server_goal_worker"
    else:
        first_blocker = blockers[0] if blockers else "skillsbench_goal_worker_contract_incomplete"
        next_action = "repair_skillsbench_app_server_goal_worker_contract"

    return {
        "schema_version": SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION,
        "benchmark_id": safe_dataset,
        "task_id": safe_task_id,
        "route": "codex-app-server-goal-baseline",
        "ready": ready,
        "runner_integration_ready": bool(runner_integration_ready),
        "first_blocker": first_blocker,
        "blockers": blockers,
        "next_action": next_action,
        "run_permission_policy": build_skillsbench_run_permission_policy(
            route="codex-app-server-goal-baseline"
        ),
        "worker_adapter": {
            "label": "skillsbench_host_codex_app_server_goal_worker",
            "script": "scripts/skillsbench_host_codex_goal_worker.py",
            "codex_bin": _skillsbench_public_safe_label(codex_bin, limit=80) or "codex",
            "reasoning_effort": _skillsbench_public_safe_label(
                reasoning_effort, limit=40
            )
            or "high",
            "prompt_style": safe_prompt_style,
            "agent_execution_mode": "host_codex_app_server_goal_worker",
            "worker_surface": "codex_app_server",
            "native_goal_methods_required": list(worker_plan["methods"]),
            "thread_goal_get_required": True,
            "turn_start_required": True,
            "context_only_followup_supported": True,
            "raw_transcript_recorded": False,
        },
        "worker_plan": {
            "schema_version": worker_plan["schema_version"],
            "surface": worker_plan["surface"],
            "worker_mode": worker_plan["worker_mode"],
            "methods": list(worker_plan["methods"]),
            "objective_sha256": worker_plan["objective_sha256"],
            "objective_chars": worker_plan["objective_chars"],
            "task_instruction_sha256": worker_plan["task_instruction_sha256"],
            "task_instruction_chars": worker_plan["task_instruction_chars"],
            "token_budget_present": worker_plan["token_budget_present"],
            "claim_boundary": worker_plan["claim_boundary"],
        },
        "runtime_layer_contract": {
            "agent_runtime_preinstalled": True,
            "case_container_runs": [
                "task_files",
                "benchmark_sandbox",
                "official_verifier",
            ],
            "case_container_does_not_install": [
                "codex_cli",
                "codex_acp",
                "node_runtime",
                "model_credentials",
            ],
        },
        "proof_required": {
            "thread_start": True,
            "thread_goal_set": True,
            "thread_goal_get": True,
            "turn_start": True,
            "compact_turn_metadata": True,
            "official_result_reducer": True,
        },
        "boundary": {
            "upload_allowed": False,
            "submit_allowed": False,
            "raw_task_text_read_into_public_state": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "loopx_state_included": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "remote_paths_recorded": False,
        },
    }


def build_skillsbench_verifier_dependency_prewarm_plan(
    *,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = "hello-world",
    patch_scope: str = "temporary_task_copy",
    no_upload: bool = True,
    submit_enabled: bool = False,
    oracle_sanity_required: bool = True,
    known_blockers: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a public-safe SkillsBench verifier dependency prewarm plan.

    The plan captures the reusable cloud-host lesson from oracle sanity probes:
    when the verifier sandbox lacks the dependency launcher substrate, extending
    timeouts is the wrong first repair. Prewarm the verifier dependency surface
    in a temporary wrapper/task-copy layer, prove oracle sanity, and only then
    claim no-upload case readiness.
    """

    safe_dataset = _skillsbench_public_safe_label(dataset, limit=80)
    safe_task_id = _skillsbench_public_safe_label(task_id, limit=120)
    blockers = [str(item) for item in known_blockers if str(item)]
    if not safe_dataset:
        safe_dataset = SKILLSBENCH_DEFAULT_DATASET
        blockers.append("skillsbench_dataset_not_public_safe")
    if not safe_task_id:
        safe_task_id = "hello-world"
        blockers.append("skillsbench_task_id_not_public_safe")

    normalized_scope = _skillsbench_public_safe_label(patch_scope, limit=80) or ""
    if normalized_scope not in SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_SCOPES:
        blockers.append("skillsbench_verifier_prewarm_scope_unsupported")
    if not no_upload:
        blockers.append("skillsbench_no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("skillsbench_submit_must_remain_disabled")
    if not oracle_sanity_required:
        blockers.append("skillsbench_oracle_sanity_probe_required")

    ready = not blockers
    first_blocker = (
        "ready_for_skillsbench_verifier_dependency_prewarm"
        if ready
        else blockers[0]
    )
    next_action = (
        "apply_verifier_dependency_prewarm_then_run_oracle_sanity"
        if ready
        else "repair_skillsbench_verifier_dependency_prewarm_plan"
    )

    return {
        "schema_version": SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_SCHEMA_VERSION,
        "benchmark_id": safe_dataset,
        "task_id": safe_task_id,
        "ready": ready,
        "first_blocker": first_blocker,
        "blockers": blockers,
        "next_action": next_action,
        "prewarm_blocker_label": SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_BLOCKER,
        "prewarm_scope": {
            "selected": normalized_scope or patch_scope,
            "allowed": list(SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_SCOPES),
            "forbidden": [
                "upstream_task_truth",
                "official_scorer",
                "official_prompt",
                "leaderboard_upload",
            ],
        },
        "dependency_contract": {
            "apt_packages": list(SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_APT_PACKAGES),
            "required_tools": list(SKILLSBENCH_VERIFIER_DEPENDENCY_PREWARM_REQUIRED_TOOLS),
            "launcher_surface": "uvx",
            "install_shape": "apt_minimal_python_plus_uv_installer",
            "dockerfile_snippet": [
                "RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates curl",
                "RUN rm -rf /var/lib/apt/lists/*",
                "RUN curl -LsSf https://astral.sh/uv/install.sh | sh",
                "ENV PATH=\"/root/.local/bin:${PATH}\"",
            ],
        },
        "oracle_sanity_contract": {
            "required": oracle_sanity_required,
            "agent": "oracle",
            "sandbox": "docker",
            "attempts": 1,
            "no_upload": no_upload,
            "submit_enabled": submit_enabled,
            "expected_reward": 1.0,
            "claim_policy": (
                "claim no-upload SkillsBench case readiness only after oracle "
                "sanity completes with reward 1.0 and verifier_errored=0"
            ),
        },
        "timeout_policy": {
            "generic_timeout_extension_first": False,
            "extend_timeout_after_dependency_substrate_verified": True,
            "timeout_blocker_label": "skillsbench_verifier_timeout",
        },
        "boundary": {
            "raw_task_text_read": False,
            "raw_logs_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "remote_paths_recorded": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
    }


def build_skillsbench_local_driver_a2a_contract(
    *,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = SKILLSBENCH_DEFAULT_TASK,
    pair_routes: Iterable[str] = SKILLSBENCH_LOCAL_DRIVER_A2A_PAIR_ROUTES,
    local_codex_driver_ready: bool = False,
    local_codex_cli_participant_ready: bool | None = None,
    local_a2a_worker_handshake_ready: bool | None = None,
    local_a2a_participant_ready: bool = False,
    remote_executor_ready: bool = False,
    remote_task_data_ready: bool = False,
    compact_artifact_reducer_ready: bool = True,
    no_upload: bool = True,
    submit_enabled: bool = False,
    known_blockers: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the public SkillsBench local-driver/remote-executor contract.

    The contract is intentionally a manifest, not a launcher. It lets private
    automation prove that Codex auth/model/state stay local while the remote
    side owns Docker, runner data, and compact artifact reduction. It never
    embeds task text, shell commands, argv, host paths, logs, trajectories, or
    credentials.
    """

    safe_dataset = _skillsbench_public_safe_label(dataset, limit=80)
    safe_task_id = _skillsbench_public_safe_label(task_id, limit=120)
    blockers = [str(item) for item in known_blockers if str(item)]
    if not safe_dataset:
        safe_dataset = SKILLSBENCH_DEFAULT_DATASET
        blockers.append("skillsbench_dataset_not_public_safe")
    if not safe_task_id:
        safe_task_id = SKILLSBENCH_DEFAULT_TASK
        blockers.append("skillsbench_task_id_not_public_safe")

    routes: list[str] = []
    for route in pair_routes:
        route_text = str(route)
        if route_text in SKILLSBENCH_ROUTES and route_text not in routes:
            routes.append(route_text)
        else:
            blockers.append("skillsbench_pair_route_unsupported")
    if not routes:
        routes = list(SKILLSBENCH_LOCAL_DRIVER_A2A_PAIR_ROUTES)
    missing_pair_routes = [
        route
        for route in SKILLSBENCH_LOCAL_DRIVER_A2A_PAIR_ROUTES
        if route not in routes
    ]
    if missing_pair_routes:
        blockers.append("skillsbench_mini_pair_routes_incomplete")
    if not no_upload:
        blockers.append("skillsbench_no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("skillsbench_submit_must_remain_disabled")
    if not compact_artifact_reducer_ready:
        blockers.append("skillsbench_compact_artifact_reducer_not_ready")
    if not remote_task_data_ready:
        blockers.append("skillsbench_remote_task_data_not_ready")
    if not remote_executor_ready:
        blockers.append("skillsbench_remote_executor_contract_missing")
    if not local_codex_driver_ready:
        blockers.append("skillsbench_local_codex_driver_not_ready")
    codex_cli_participant_ready = (
        local_a2a_participant_ready
        if local_codex_cli_participant_ready is None
        else local_codex_cli_participant_ready
    )
    a2a_worker_handshake_ready = (
        local_a2a_participant_ready
        if local_a2a_worker_handshake_ready is None
        else local_a2a_worker_handshake_ready
    )
    if local_codex_driver_ready and not codex_cli_participant_ready:
        blockers.append("skillsbench_local_codex_cli_participant_not_materialized")
    if (
        local_codex_driver_ready
        and codex_cli_participant_ready
        and not a2a_worker_handshake_ready
    ):
        blockers.append("skillsbench_local_acp_relay_missing")

    local_ready = (
        local_codex_driver_ready is True
        and codex_cli_participant_ready is True
        and a2a_worker_handshake_ready is True
    )
    remote_ready = (
        remote_executor_ready is True
        and remote_task_data_ready is True
        and compact_artifact_reducer_ready is True
        and no_upload is True
        and submit_enabled is False
    )
    route_contracts = {
        route: {
            "route": route,
            "arm_id": skillsbench_route_contract(route)["arm_id"],
            "job_name": skillsbench_job_name(safe_dataset, safe_task_id, route),
            "official_feedback_blinded": skillsbench_route_contract(route)[
                "official_feedback_blinded"
            ],
            "reward_feedback_forwarded": skillsbench_route_contract(route)[
                "reward_feedback_forwarded"
            ],
        }
        for route in routes
    }
    ready = (
        not blockers
        and local_ready is True
        and remote_ready is True
        and missing_pair_routes == []
    )
    if ready:
        first_blocker = "ready_for_skillsbench_local_driver_a2a_mini_pair"
        next_action = "launch_no_upload_skillsbench_local_driver_a2a_mini_pair"
    elif "skillsbench_local_codex_cli_participant_not_materialized" in blockers:
        first_blocker = "skillsbench_local_codex_cli_participant_not_materialized"
        next_action = "materialize_local_codex_cli_participant_before_mini_pair"
    elif "skillsbench_local_acp_relay_missing" in blockers:
        first_blocker = "skillsbench_local_acp_relay_missing"
        next_action = "wire_local_acp_relay_before_mini_pair"
    elif "skillsbench_remote_executor_contract_missing" in blockers:
        first_blocker = "skillsbench_remote_executor_contract_missing"
        next_action = "materialize_remote_executor_contract_before_mini_pair"
    else:
        first_blocker = blockers[0] if blockers else "skillsbench_contract_incomplete"
        next_action = "repair_skillsbench_local_driver_contract_before_mini_pair"

    return {
        "schema_version": SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION,
        "benchmark_id": safe_dataset,
        "task_id": safe_task_id,
        "ready": ready,
        "first_blocker": first_blocker,
        "blockers": blockers,
        "next_action": next_action,
        "mini_pair": {
            "required": True,
            "routes": routes,
            "missing_routes": missing_pair_routes,
            "comparison_policy": "same_task_same_budget_no_upload",
            "route_contracts": route_contracts,
        },
        "local_driver_contract": {
            "ready": local_ready,
            "driver_label": "skillsbench_local_codex_a2a_driver",
            "transport": "local_acp_relay",
            "worker_protocol": "acp_stdio",
            "owns": [
                "codex_cli",
                "codex_auth",
                "model_invocation",
                "loopx_state",
                "planning_and_patch_generation",
            ],
            "keeps_local": [
                "codex_auth",
                "model_invocation",
                "loopx_state",
                "raw_reasoning_trace",
                "private_agent_trajectory",
            ],
            "remote_request_fields": [
                "benchmark_id",
                "task_handle",
                "route",
                "execution_mode",
                "no_upload",
                "compact_artifact_ref",
            ],
            "participant_materialized": local_ready,
            "codex_cli_participant_materialized": codex_cli_participant_ready is True,
            "acp_relay_materialized": a2a_worker_handshake_ready is True,
            "a2a_worker_handshake_materialized": a2a_worker_handshake_ready is True,
            "credential_sync_allowed": False,
        },
        "remote_executor_contract": {
            "ready": remote_ready,
            "sandbox_label": "skillsbench_remote_executor_sandbox",
            "owns": [
                "docker",
                "benchflow_runner",
                "task_data_staging",
                "bounded_command_execution",
                "compact_result_reduction",
            ],
            "allowed_actions": [
                "runner_dependency_check",
                "task_data_staging_check",
                "bounded_command_execution",
                "compact_result_reduction",
                "cleanup",
            ],
            "disallowed_actions": [
                "codex_auth_sync",
                "credential_sync",
                "remote_codex_runtime",
                "remote_model_api_invocation",
                "raw_task_text_publication",
                "raw_log_publication",
                "raw_trajectory_publication",
                "upload",
                "submit",
            ],
            "returns": [
                "readiness_state",
                "job_handle",
                "compact_result_or_blocker",
                "cleanup_state",
            ],
            "remote_codex_runtime_allowed": False,
            "remote_model_api_invocation_allowed": False,
        },
        "boundary": {
            "shell_command_embedded": False,
            "argv_embedded": False,
            "host_path_embedded": False,
            "remote_path_embedded": False,
            "raw_task_text_public": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
            "credential_values_recorded": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "private_handle_values_recorded": False,
        },
    }


def build_skillsbench_worker_handshake_preflight(
    *,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = SKILLSBENCH_DEFAULT_TASK,
    benchflow_available: bool = False,
    benchflow_agent_registry_available: bool = False,
    benchflow_acp_runtime_available: bool = False,
    default_codex_agent: str = "codex-acp",
    codex_agent_protocol: str | None = None,
    codex_agent_launch_registered: bool = False,
    local_codex_cli_participant_ready: bool = False,
    local_acp_relay_ready: bool = False,
    local_acp_relay_probe: dict[str, Any] | None = None,
    host_local_acp_transport_ready: bool = False,
    host_local_acp_transport_probe: dict[str, Any] | None = None,
    remote_command_file_bridge_ready: bool = False,
    remote_command_file_bridge_probe: dict[str, Any] | None = None,
    remote_executor_ready: bool = True,
    remote_task_data_ready: bool = True,
    compact_artifact_reducer_ready: bool = True,
    no_upload: bool = True,
    submit_enabled: bool = False,
    known_blockers: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a public-safe SkillsBench local-driver worker handshake preflight.

    This preflight is intentionally narrower than a full benchmark run: it
    records the worker protocol that BenchFlow expects and checks whether the
    local Codex participant has a relay that can speak that protocol. It does
    not launch task sandboxes, copy credentials, read task text, or record raw
    logs/trajectories.
    """

    safe_dataset = _skillsbench_public_safe_label(dataset, limit=80)
    safe_task_id = _skillsbench_public_safe_label(task_id, limit=120)
    blockers = [str(item) for item in known_blockers if str(item)]
    if not safe_dataset:
        safe_dataset = SKILLSBENCH_DEFAULT_DATASET
        blockers.append("skillsbench_dataset_not_public_safe")
    if not safe_task_id:
        safe_task_id = SKILLSBENCH_DEFAULT_TASK
        blockers.append("skillsbench_task_id_not_public_safe")

    remote_command_file_bridge_probe_ready = (
        isinstance(remote_command_file_bridge_probe, dict)
        and remote_command_file_bridge_probe.get("ready") is True
    )
    remote_command_file_bridge_materialized = (
        remote_command_file_bridge_ready is True
        or remote_command_file_bridge_probe_ready is True
    )
    if remote_command_file_bridge_probe_ready:
        remote_command_file_bridge_readiness_source = "probe"
    elif remote_command_file_bridge_ready:
        remote_command_file_bridge_readiness_source = "manual_declaration"
    else:
        remote_command_file_bridge_readiness_source = "missing"

    protocol = str(codex_agent_protocol or "").strip().lower()
    worker_protocol = "acp_stdio" if protocol == "acp" else protocol or "unknown"
    if not benchflow_available:
        blockers.append("skillsbench_benchflow_runtime_missing")
    if not benchflow_agent_registry_available:
        blockers.append("skillsbench_benchflow_agent_registry_missing")
    if not benchflow_acp_runtime_available:
        blockers.append("skillsbench_benchflow_acp_runtime_missing")
    if protocol != "acp":
        blockers.append("skillsbench_codex_agent_protocol_not_acp")
    if not codex_agent_launch_registered:
        blockers.append("skillsbench_codex_agent_launch_not_registered")
    if not local_codex_cli_participant_ready:
        blockers.append("skillsbench_local_codex_cli_participant_not_materialized")
    if local_codex_cli_participant_ready and not local_acp_relay_ready:
        blockers.append("skillsbench_local_acp_relay_missing")
    if local_acp_relay_ready and not host_local_acp_transport_ready:
        blockers.append("skillsbench_host_local_acp_transport_missing")
    if host_local_acp_transport_ready and not remote_command_file_bridge_materialized:
        blockers.append("skillsbench_remote_command_file_bridge_missing")
    if not remote_executor_ready:
        blockers.append("skillsbench_remote_executor_contract_missing")
    if not remote_task_data_ready:
        blockers.append("skillsbench_remote_task_data_not_ready")
    if not compact_artifact_reducer_ready:
        blockers.append("skillsbench_compact_artifact_reducer_not_ready")
    if not no_upload:
        blockers.append("skillsbench_no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("skillsbench_submit_must_remain_disabled")

    ready = not blockers
    if ready:
        first_blocker = "ready_for_skillsbench_local_driver_worker_handshake"
        next_action = "launch_no_upload_skillsbench_local_driver_mini_pair"
    elif "skillsbench_benchflow_runtime_missing" in blockers:
        first_blocker = "skillsbench_benchflow_runtime_missing"
        next_action = "install_or_select_skillsbench_benchflow_runtime"
    elif "skillsbench_local_codex_cli_participant_not_materialized" in blockers:
        first_blocker = "skillsbench_local_codex_cli_participant_not_materialized"
        next_action = "materialize_local_codex_cli_participant_before_worker_handshake"
    elif "skillsbench_local_acp_relay_missing" in blockers:
        first_blocker = "skillsbench_local_acp_relay_missing"
        next_action = "implement_local_acp_stdio_relay_before_mini_pair"
    elif "skillsbench_host_local_acp_transport_missing" in blockers:
        first_blocker = "skillsbench_host_local_acp_transport_missing"
        next_action = "wire_host_local_acp_transport_before_mini_pair"
    elif "skillsbench_remote_command_file_bridge_missing" in blockers:
        first_blocker = "skillsbench_remote_command_file_bridge_missing"
        next_action = "wire_bounded_remote_command_file_bridge_before_mini_pair"
    else:
        first_blocker = blockers[0] if blockers else "skillsbench_worker_handshake_incomplete"
        next_action = "repair_skillsbench_worker_handshake_before_mini_pair"

    return {
        "schema_version": SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION,
        "benchmark_id": safe_dataset,
        "task_id": safe_task_id,
        "ready": ready,
        "first_blocker": first_blocker,
        "blockers": blockers,
        "next_action": next_action,
        "benchflow_contract": {
            "available": benchflow_available,
            "agent_registry_available": benchflow_agent_registry_available,
            "acp_runtime_available": benchflow_acp_runtime_available,
            "default_codex_agent": _skillsbench_public_safe_label(
                default_codex_agent, limit=80
            ),
            "codex_agent_protocol": protocol or None,
            "worker_protocol": worker_protocol,
            "codex_agent_launch_registered": codex_agent_launch_registered,
            "stdio_transport_required": protocol == "acp",
        },
        "local_driver_contract": {
            "codex_cli_participant_materialized": local_codex_cli_participant_ready,
            "acp_relay_materialized": local_acp_relay_ready,
            "acp_relay_probe": _skillsbench_public_acp_relay_probe(
                local_acp_relay_probe
            ),
            "host_local_acp_transport_materialized": host_local_acp_transport_ready,
            "host_local_acp_transport_probe": (
                _skillsbench_public_host_local_acp_transport_probe(
                    host_local_acp_transport_probe
                )
            ),
            "remote_command_file_bridge_materialized": (
                remote_command_file_bridge_materialized
            ),
            "remote_command_file_bridge_readiness_source": (
                remote_command_file_bridge_readiness_source
            ),
            "remote_command_file_bridge_probe": (
                _skillsbench_public_remote_command_file_bridge_probe(
                    remote_command_file_bridge_probe
                )
            ),
            "credential_sync_allowed": False,
            "remote_codex_runtime_allowed": False,
            "remote_model_api_invocation_allowed": False,
        },
        "remote_executor_contract": {
            "ready": remote_executor_ready,
            "task_data_ready": remote_task_data_ready,
            "compact_artifact_reducer_ready": compact_artifact_reducer_ready,
            "command_file_bridge_ready": remote_command_file_bridge_materialized,
            "owns": [
                "docker",
                "benchflow_runner",
                "task_data_staging",
                "bounded_command_execution",
                "compact_result_reduction",
            ],
        },
        "boundary": {
            "local_codex_auth_model_state": True,
            "remote_docker_and_runner_only": True,
            "raw_task_text_read": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
    }


def _skillsbench_public_acp_relay_probe(
    probe: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(probe, dict):
        return None
    compact: dict[str, Any] = {}
    for field in ("schema_version", "first_blocker", "stage", "worker_protocol"):
        value = probe.get(field)
        if isinstance(value, str) and value:
            compact[field] = _skillsbench_public_safe_label(value, limit=120)
    for field in (
        "ready",
        "codex_cli_invoked",
        "raw_output_recorded",
        "raw_event_jsonl_recorded",
        "credential_values_recorded",
        "host_paths_recorded",
    ):
        value = probe.get(field)
        if isinstance(value, bool):
            compact[field] = value
    value = probe.get("request_count")
    if isinstance(value, int) and not isinstance(value, bool):
        compact["request_count"] = max(0, min(value, 20))
    return compact or None


def _skillsbench_public_host_local_acp_transport_probe(
    probe: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(probe, dict):
        return None
    compact: dict[str, Any] = {}
    for field in ("schema_version", "first_blocker", "stage", "transport"):
        value = probe.get(field)
        if isinstance(value, str) and value:
            compact[field] = _skillsbench_public_safe_label(value, limit=120)
    for field in (
        "ready",
        "benchflow_acp_client_used",
        "container_transport_used",
        "codex_cli_invoked",
        "raw_output_recorded",
        "raw_event_jsonl_recorded",
        "credential_values_recorded",
        "host_paths_recorded",
    ):
        value = probe.get(field)
        if isinstance(value, bool):
            compact[field] = value
    value = probe.get("request_count")
    if isinstance(value, int) and not isinstance(value, bool):
        compact["request_count"] = max(0, min(value, 20))
    return compact or None


def _skillsbench_public_remote_command_file_bridge_probe(
    probe: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(probe, dict):
        return None
    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "first_blocker",
        "response_first_blocker",
        "stage",
        "request_schema_version",
        "response_schema_version",
    ):
        value = probe.get(field)
        if isinstance(value, str) and value:
            compact[field] = _skillsbench_public_safe_label(value, limit=120)
    for field in (
        "ready",
        "bridge_command_invoked",
        "raw_command_recorded",
        "raw_stdout_recorded",
        "raw_stderr_recorded",
        "raw_task_text_recorded",
        "raw_logs_recorded",
        "raw_trajectory_recorded",
        "credential_values_recorded",
        "host_paths_recorded",
        "remote_paths_recorded",
        "upload_performed",
        "submit_performed",
    ):
        value = probe.get(field)
        if isinstance(value, bool):
            compact[field] = value
    for field in ("elapsed_ms", "operation_count"):
        value = probe.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            compact[field] = max(0, min(value, 600_000))
    for field in (
        "required_operations",
        "missing_operations",
        "failed_operations",
        "boundary_violations",
    ):
        values = probe.get(field)
        if isinstance(values, list):
            compact[field] = [
                label
                for item in values[:12]
                if (label := _skillsbench_public_safe_label(item, limit=80))
            ]
    operations = probe.get("operations")
    if isinstance(operations, list):
        compact["operations"] = []
        for item in operations[:8]:
            if not isinstance(item, dict):
                continue
            op: dict[str, Any] = {}
            for field in ("kind", "label", "status"):
                value = item.get(field)
                if isinstance(value, str) and value:
                    op[field] = _skillsbench_public_safe_label(value, limit=80)
            for field in ("exit_code_zero", "content_match"):
                value = item.get(field)
                if isinstance(value, bool):
                    op[field] = value
            if op:
                compact["operations"].append(op)
    return compact or None


def skillsbench_runner_error_attribution(error_text: str) -> tuple[str, str, list[str]]:
    """Classify public-safe SkillsBench runner/setup failures."""

    text = error_text.lower()
    if (
        "suspected provider api error" in text
        and "zero tokens" in text
        and "zero tool calls" in text
    ) or (
        "agent ended with zero tokens" in text
        and "no scoreable model activity" in text
    ):
        label = "skillsbench_codex_acp_provider_zero_activity"
        return label, label, [
            label,
            "skillsbench_codex_acp_provider_error",
            "skillsbench_acp_zero_tool_call_observed",
        ]
    if "acp error -32603" in text and "internal error" in text:
        label = "skillsbench_codex_acp_jsonrpc_internal_error"
        return label, label, [label, "skillsbench_codex_acp_transport_error"]
    if "benchflow result.json not found" in text:
        label = "skillsbench_result_json_missing_after_runner_exit"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if (
        "skillsbench task source preflight blocked" in text
        or "task missing from canonical tasks source" in text
    ):
        label = "skillsbench_task_source_preflight_blocked"
        return label, label, [
            label,
            "skillsbench_runner_setup_error",
            "skillsbench_task_source_preflight",
        ]
    if (
        "could not find the file /app" in text
        or "main:/app/skills" in text
        or (
            "mkdir -p /app" in text
            and "permission denied" in text
        )
        or (
            "/app/skills" in text
            and (
                "bind source path" in text
                or "mount" in text
                or "volume" in text
                or "task skills" in text
                or "permission denied" in text
            )
        )
    ):
        label = "skillsbench_environment_app_mount_missing"
        return label, label, [label, "skillsbench_environment_setup_error"]
    if (
        "no such file or directory: 'docker'" in text
        or "no such file or directory: docker" in text
    ):
        label = "skillsbench_docker_cli_missing"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if "codex-acp" in text and "libssl.so.3" in text:
        label = "skillsbench_codex_acp_runtime_libssl_missing"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if "codex-acp" in text and "libssl3" in text:
        label = "skillsbench_codex_acp_runtime_libssl_missing"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if "codex-acp" in text and (
        "glibc" in text or "libc.so.6" in text or "glibc_2." in text
    ):
        label = "skillsbench_codex_acp_glibc_incompatible"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if (
        "codex-acp" in text
        and "runtime launch preflight failed" in text
        and "binary not on path" in text
    ):
        label = "skillsbench_codex_acp_binary_missing"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if "codex-acp" in text and "runtime launch preflight failed" in text:
        label = "skillsbench_codex_acp_launch_preflight_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if "codex-acp" in text and (
        "rc=127" in text
        or "not found" in text
        or "no such file or directory" in text
    ):
        label = "skillsbench_codex_acp_launch_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if (
        "range of cpus is from" in text
        or "only 2 cpus available" in text
        or "requested_cpus_exceeds_local_docker_daemon_capacity" in text
    ):
        label = "skillsbench_docker_host_cpu_limit"
        return label, label, [label, "skillsbench_environment_setup_error"]
    if (
        "apt setup risk preflight blocked" in text
        or "apt-based docker setup risk detected before full case run" in text
    ):
        label = "skillsbench_docker_apt_setup_risk_preflight_blocked"
        return label, label, [
            label,
            "skillsbench_docker_setup_preflight_blocked",
            "skillsbench_environment_setup_error",
        ]
    if (
        "dockerfile package bootstrap risk preflight blocked" in text
        or "dockerfile package bootstrap risk detected before full case run" in text
    ):
        label = "skillsbench_dockerfile_package_bootstrap_risk_preflight_blocked"
        return label, label, [
            label,
            "skillsbench_docker_setup_preflight_blocked",
            "skillsbench_environment_setup_error",
        ]
    if (
        "verifier bootstrap risk preflight blocked" in text
        or "verifier dependency bootstrap risk detected before full case run" in text
    ):
        label = "skillsbench_verifier_bootstrap_risk_preflight_blocked"
        return label, label, [
            label,
            "skillsbench_verifier_setup_preflight_blocked",
            "skillsbench_environment_setup_error",
        ]
    if "docker compose command failed" in text:
        if (
            "cannot connect to the docker daemon" in text
            or "is the docker daemon running" in text
            or "docker daemon is not running" in text
            or "colima is not running" in text
            or "error during connect" in text
        ):
            label = "skillsbench_docker_daemon_unavailable"
            return label, label, [
                label,
                "skillsbench_docker_compose_setup_failure",
                "skillsbench_environment_setup_error",
            ]
        if (
            "port is already allocated" in text
            or "address already in use" in text
            or "ports are not available" in text
            or ("bind for" in text and "failed" in text)
        ):
            label = "skillsbench_docker_compose_port_conflict"
            return label, label, [
                label,
                "skillsbench_docker_compose_setup_failure",
                "skillsbench_environment_setup_error",
            ]
        if (
            "pip install" in text
            or "python -m pip" in text
            or "python3 -m pip" in text
            or "files.pythonhosted.org" in text
            or "pypi.org" in text
            or "pypi.tuna.tsinghua.edu.cn" in text
            or "no matching distribution found" in text
            or "read timed out" in text
        ):
            label = "skillsbench_docker_compose_pip_bootstrap_failure"
            return label, label, [
                label,
                "skillsbench_docker_compose_setup_failure",
                "skillsbench_python_package_bootstrap_failure",
                "skillsbench_environment_setup_error",
            ]
        if (
            "apt-get" in text
            or "apt update" in text
            or "apt " in text
            or "gpg error" in text
            or "hash sum mismatch" in text
            or "failed to fetch" in text
        ):
            label = "skillsbench_docker_compose_apt_repository_failure"
            return label, label, [
                label,
                "skillsbench_docker_compose_setup_failure",
                "skillsbench_environment_setup_error",
            ]
        if (
            "mount" in text
            or "volume" in text
            or "bind source path" in text
        ):
            label = "skillsbench_docker_compose_volume_mount_failure"
            return label, label, [
                label,
                "skillsbench_docker_compose_setup_failure",
                "skillsbench_environment_setup_error",
            ]
        if (
            "failed to solve" in text
            or "failed to build" in text
            or "dockerfile" in text
            or "pull access denied" in text
            or "manifest unknown" in text
        ):
            label = "skillsbench_docker_compose_image_build_failure"
            return label, label, [
                label,
                "skillsbench_docker_compose_setup_failure",
                "skillsbench_environment_setup_error",
            ]
        label = "skillsbench_docker_compose_setup_failure"
        return label, label, [
            label,
            "skillsbench_docker_compose_unclassified_setup_failure",
            "skillsbench_environment_setup_error",
        ]
    if "codex_exec_task_output_quiet_timeout" in text:
        label = "skillsbench_host_local_acp_task_output_quiet_timeout"
        return label, label, [label, "skillsbench_host_local_acp_recoverable_timeout"]
    label = "skillsbench_runner_error"
    return label, label, [label]


def skillsbench_error_len_bucket(text: str) -> str:
    size = len(text)
    if size <= 0:
        return "empty"
    if size < 200:
        return "1_199"
    if size < 500:
        return "200_499"
    if size < 1000:
        return "500_999"
    if size < 2000:
        return "1000_1999"
    return "2000_plus"


def skillsbench_runner_error_fingerprint(error_text: str) -> dict[str, Any]:
    """Return a public-safe shape summary without copying raw error text."""

    text = error_text or ""
    lowered = text.lower()
    patterns = {
        "docker_compose_command_failed": r"docker compose command failed",
        "docker_daemon_unavailable": (
            r"cannot connect to the docker daemon|is the docker daemon running|"
            r"docker daemon is not running|colima is not running|error during connect"
        ),
        "service_unhealthy": r"unhealthy|healthcheck|health check",
        "container_exited": r"exited with code|container .* exited|exit code",
        "dependency_failed": r"dependency failed|depends_on|dependency",
        "network_failure": r"network|connection refused|could not connect",
        "volume_mount_failure": r"mount|volume|bind source path",
        "permission_denied": r"permission denied|operation not permitted",
        "missing_file": r"no such file|not found|does not exist",
        "codex_api_egress_failure": (
            r"codex api egress preflight|reverse tunnel proxy|"
            r"loopx_codex_api_reverse_tunnel_proxy"
        ),
        "task_output_quiet_timeout": r"codex_exec_task_output_quiet_timeout",
        "image_build": r"failed to solve|failed to build|dockerfile|pull access denied|manifest unknown",
        "port_conflict": r"port is already allocated|address already in use|ports are not available|bind for",
        "apt_failure": r"apt-get|apt update|apt |gpg error|hash sum mismatch|failed to fetch",
        "pip_bootstrap_failure": (
            r"pip install|python3? -m pip|files\.pythonhosted\.org|pypi\.org|"
            r"pypi\.tuna\.tsinghua\.edu\.cn|no matching distribution found"
        ),
        "subprocess_command_timeout": r"command timed out after \d+ seconds",
        "timeout": r"timeout|timed out|deadline",
    }
    matched = [
        label
        for label, pattern in patterns.items()
        if re.search(pattern, lowered)
    ]
    return {
        "schema_version": "skillsbench_runner_failure_fingerprint_v0",
        "error_present": bool(text),
        "error_len_bucket": skillsbench_error_len_bucket(text),
        "line_count": len(text.splitlines()) if text else 0,
        "matched_patterns": matched,
        "has_host_paths": bool(
            re.search(r"/Users/|/private/|/var/folders/", text)
        ),
        "has_urls": bool(re.search(r"https?://", text)),
        "has_secret_like_tokens": bool(
            re.search(r"(?i)(api[_-]?key|token|password|secret)", text)
        ),
        "raw_error_recorded": False,
        "fingerprint_confidence": "coarse_public_safe_pattern_match",
    }


def build_skillsbench_benchmark_run(
    *,
    route: str = SKILLSBENCH_DEFAULT_ROUTE,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = SKILLSBENCH_DEFAULT_TASK,
    agent: str = "codex",
    model: str = SKILLSBENCH_DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build a compact no-run SkillsBench benchmark_run_v0 skeleton."""

    if agent != "codex":
        raise ValueError("SkillsBench skeleton currently supports agent=codex only")
    if route not in SKILLSBENCH_ROUTES:
        raise ValueError(f"unsupported SkillsBench route: {route}")
    contract = skillsbench_route_contract(route)
    job_name = skillsbench_job_name(dataset, task_id, route)
    is_product_mode_treatment = _is_skillsbench_loopx_product_mode_treatment_route(
        route
    )
    is_goal_start_product_mode = _is_skillsbench_goal_start_product_mode_route(route)
    validation: dict[str, Any] = {
        "cli_skeleton_present": True,
        "skillsbench_route_declared": True,
        "compact_ingest_route_declared": True,
        "no_real_codex_invoked": True,
        "no_benchflow_invoked": True,
        "no_docker_or_cloud_invoked": True,
        "no_model_api_invoked": True,
        "no_leaderboard_upload_requested": True,
        "paths_redacted": True,
    }
    benchmark_run: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": contract["source_runner"],
        "benchmark_id": dataset,
        "job_name": job_name,
        "mode": contract["mode"],
        "route": route,
        "run_permission_policy": build_skillsbench_run_permission_policy(
            route=route
        ),
        "attempt_accounting": build_benchmark_attempt_accounting(
            lifecycle=canonical_lifecycle(),
            failure_label="not_run_adapter_skeleton",
            failure_class=BenchmarkFailureClass.NONE,
        ),
        "agent": {
            "name": agent,
            "model": model,
            "kwargs_keys": (
                [
                    "codex_goal_mode_invocation_surface",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "codex-goal-mode-baseline"
                else [
                    "codex_app_server_goal_worker",
                    "thread_goal_set_get",
                    "turn_start",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "codex-app-server-goal-baseline"
                else [
                    "ordinary_codex_cli_actor",
                    "fixed_blind_loop_budget",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "codex-acp-blind-loop-baseline"
                else [
                    "ordinary_codex_cli_actor",
                    "raw_codex_autonomous_max5",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "raw-codex-autonomous-max5"
                else [
                    "ordinary_codex_cli_actor",
                    "loopx_goal_start_product_mode"
                    if is_goal_start_product_mode
                    else "loopx_product_mode",
                    "ranked_todo_plan_selected_p0_lifecycle"
                    if is_goal_start_product_mode
                    else "goal_state_todos_replan_cli",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if is_product_mode_treatment
                else [
                    "ordinary_codex_cli_actor",
                    "loopx_prompt_polling_test",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "loopx-prompt-polling-test"
                else [
                    "ordinary_codex_cli_actor",
                    "loopx_blind_loop",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "loopx-blind-loop-treatment"
                else [
                    "skillsbench_curated_skills_visible",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
            ),
        },
        "progress": {
            "n_total_trials": 0,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
        },
        "interaction_counters": {
            "schema_version": "skillsbench_interaction_counters_v0",
            "loopx_automation_loop": contract["loopx_automation_loop"],
            "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
            "native_goal_mode_requested": contract["native_goal_mode_requested"],
            "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
            "native_goal_mode_confirmation_status": contract[
                "native_goal_mode_confirmation_status"
            ],
            "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
            "curated_skills_visible": contract["curated_skills_visible"],
            "product_mode": contract.get("product_mode") is True,
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "loopx_case_state_reads": 0,
            "loopx_case_state_writes": 0,
            "heartbeat_count": 0,
            "case_goal_state_packet_present": is_product_mode_treatment,
            "case_goal_state_init_required": is_product_mode_treatment,
            "case_goal_state_initialized_before_agent": False,
            "case_goal_state_init_status": (
                "not_run_adapter_skeleton"
                if is_product_mode_treatment
                else ""
            ),
            "case_goal_state_schema_version": (
                BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
                if is_product_mode_treatment
                else ""
            ),
            "case_goal_state_path": (
                SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH
                if is_product_mode_treatment
                else ""
            ),
            "declared_done_requires_no_remaining_goals": is_product_mode_treatment,
            "goal_start_product_mode": is_goal_start_product_mode,
            "verifier_failure_feedback_todo_route": False,
            "verifier_failure_feedback_forwarded_to_agent": False,
            "verifier_failure_todo_required": False,
            "goal_start_plan_observed": False,
            "planned_todo_count": 0,
            "planned_p0_count": 0,
            "selected_p0_todo_id": "",
            "case_result_writeback": "not_run_adapter_skeleton",
            "counter_trust_level": "adapter_contract_fixture",
        },
        "episode_policy": {
            "schema_version": "skillsbench_episode_policy_v0",
            "route": route,
            "outer_controller": (
                "loopx_prompt_polling_loop"
                if route == "loopx-prompt-polling-test"
                else "loopx_blind_automation_loop"
                if route == "loopx-blind-loop-treatment"
                else _skillsbench_product_mode_outer_controller(route)
                if is_product_mode_treatment
                else "raw_codex_autonomous_max5"
                if route == "raw-codex-autonomous-max5"
                else "fixed_blind_loop_runner"
                if route == "codex-acp-blind-loop-baseline"
                else "codex_app_server_goal_worker"
                if route == "codex-app-server-goal-baseline"
                else "runner_only"
            ),
            "inner_case_actor": (
                "ordinary_codex_acp_agent"
                if route
                in {
                    "loopx-blind-loop-treatment",
                    "loopx-prompt-polling-test",
                    "codex-acp-blind-loop-baseline",
                    "raw-codex-autonomous-max5",
                    *SKILLSBENCH_LOOPX_PRODUCT_MODE_TREATMENT_ROUTES,
                }
                else "codex_acp_goal_prompt_request_unconfirmed_native_goal_mode"
                if route == "codex-goal-mode-baseline"
                else "host_codex_app_server_goal_worker"
                if route == "codex-app-server-goal-baseline"
                else "codex_acp_with_curated_skills"
            ),
            "blind_loop": contract["blind_loop"],
            "product_mode": contract.get("product_mode") is True,
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "verifier_output_tail_forwarded_by_default": False,
            "raw_trace_recorded": False,
            "raw_task_text_recorded": False,
            "does_not_upload_or_submit": True,
        },
        "trials": [
            {
                "task_id": task_id,
                "trial_name": f"{task_id}_{route}",
                "source": dataset,
                "exception_type": contract["first_blocker"],
                "reward": {"reward": 0},
                "metrics": {
                    "input_tokens": 0,
                    "cache_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0,
                },
                "trajectory_present": False,
                "verifier_reward_present": False,
                "artifact_manifest_present": False,
                "trial_result_present": False,
            }
        ],
        "validation": validation,
        "authorization": {
            "real_case_execution_authorized": False,
            "submit_eligible": False,
        },
        "redaction": {
            "secret_values_recorded": False,
            "raw_sessions_recorded": False,
            "host_paths_recorded": False,
            "raw_prompts_recorded": False,
            "raw_solutions_recorded": False,
        },
        "mode_contract": {
            "requested_route": route,
            "arm_id": contract["arm_id"],
            "case_semantics_changed_by_harness": contract[
                "case_semantics_changed_by_harness"
            ],
            "loopx_inside_case": contract["loopx_inside_case"],
            "loopx_automation_loop": contract["loopx_automation_loop"],
            "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
            "native_goal_mode_requested": contract["native_goal_mode_requested"],
            "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
            "native_goal_mode_confirmation_status": contract[
                "native_goal_mode_confirmation_status"
            ],
            "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
            "skillsbench_route_semantics": contract["skillsbench_route_semantics"],
            "curated_skills_visible": contract["curated_skills_visible"],
            "product_mode": contract.get("product_mode") is True,
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "official_score_comparable_to_native_codex": contract[
                "official_score_comparable_to_native_codex"
            ],
            "official_score_comparable_to_loopx_treatment": contract[
                "official_score_comparable_to_loopx_treatment"
            ],
            "leaderboard_evidence": False,
        },
        "evidence_files": [
            "doc:benchmark-run-ledger-v0.md",
            "smoke:skillsbench-benchmark-run-smoke.py",
        ],
        "resume_or_inspect_commands": [
            (
                "loopx benchmark run skillsbench "
                f"--skillsbench-route {route} --include-task-name {task_id}"
            ),
            (
                "loopx benchmark run-ledger-upsert "
                "--benchmark-run-json <skillsbench-compact-benchmark-run-v0.json>"
            ),
        ],
        "real_run": False,
        "submit_eligible": False,
        "official_task_score": {
            "kind": "not_run",
            "value": None,
        },
        "case_semantics_changed_by_harness": contract[
            "case_semantics_changed_by_harness"
        ],
        "loopx_inside_case": contract["loopx_inside_case"],
        "loopx_automation_loop": contract["loopx_automation_loop"],
        "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
        "native_goal_mode_requested": contract["native_goal_mode_requested"],
        "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
        "native_goal_mode_confirmation_status": contract[
            "native_goal_mode_confirmation_status"
        ],
        "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
        "skillsbench_route_semantics": contract["skillsbench_route_semantics"],
        "curated_skills_visible": contract["curated_skills_visible"],
        "product_mode": contract.get("product_mode") is True,
        "blind_loop": contract["blind_loop"],
        "official_feedback_blinded": contract["official_feedback_blinded"],
        "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
        "official_score_comparable_to_native_codex": contract[
            "official_score_comparable_to_native_codex"
        ],
        "official_score_comparable_to_loopx_treatment": contract[
            "official_score_comparable_to_loopx_treatment"
        ],
        "leaderboard_evidence": False,
        "trace_publicness": "public_skillsbench_adapter_skeleton",
        "first_blocker": contract["first_blocker"],
        "stop_conditions": [
            "do_not_run_benchflow_from_skeleton",
            "do_not_invoke_real_codex_from_skeleton",
            "do_not_start_docker_or_cloud_from_skeleton",
            "do_not_call_model_api_from_skeleton",
            "do_not_read_raw_task_prompt_solution_or_trajectory",
            "do_not_upload_or_submit_leaderboard",
            "do_not_record_secrets_or_raw_sessions",
        ],
    }
    return benchmark_run


def _skillsbench_controller_trace_counters(
    controller_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(controller_trace, dict):
        return {}
    schema_version = str(controller_trace.get("schema_version") or "")
    if schema_version != "skillsbench_loopx_controller_trace_v0":
        return {}

    def count(key: str) -> int:
        value = controller_trace.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return 0

    def positive_int(key: str) -> int | None:
        value = controller_trace.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return None

    def subcommand_count(command: str) -> int:
        counts = controller_trace.get(
            "remote_command_file_bridge_agent_loopx_subcommand_counts"
        )
        if not isinstance(counts, dict):
            return 0
        value = counts.get(command)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return 0

    def successful_subcommand_count(command: str) -> int:
        counts = controller_trace.get(
            "remote_command_file_bridge_agent_successful_loopx_subcommand_counts"
        )
        if not isinstance(counts, dict):
            return 0
        value = counts.get(command)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return 0

    def driver_command_count(command: str) -> int:
        counts = controller_trace.get(
            "remote_command_file_bridge_driver_lifecycle_command_counts"
        )
        if not isinstance(counts, dict):
            return 0
        value = counts.get(command)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return 0

    def count_map(key: str) -> dict[str, int]:
        raw = controller_trace.get(key)
        if not isinstance(raw, dict):
            return {}
        counts: dict[str, int] = {}
        for name, value in raw.items():
            if (
                isinstance(name, str)
                and name
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            ):
                counts[name[:80]] = value
        return dict(sorted(counts.items()))

    def text_value(key: str, *, limit: int = 120) -> str:
        value = controller_trace.get(key)
        if not isinstance(value, str):
            return ""
        return value[:limit]

    def text_list(key: str, *, limit: int = 120, max_items: int = 12) -> list[str]:
        raw = controller_trace.get(key)
        if not isinstance(raw, list):
            return []
        items: list[str] = []
        for value in raw:
            if not isinstance(value, str) or not value:
                continue
            safe = value[:limit]
            if safe not in items:
                items.append(safe)
            if len(items) >= max_items:
                break
        return items

    def max_direct_or_subcommands(key: str, commands: tuple[str, ...]) -> int:
        direct = count(key)
        derived = sum(subcommand_count(command) for command in commands)
        return max(direct, derived)

    def round_reward_records() -> list[dict[str, Any]]:
        raw_records = controller_trace.get("round_rewards")
        if not isinstance(raw_records, list):
            return []
        records: list[dict[str, Any]] = []
        seen_rounds: set[int] = set()
        for item in raw_records:
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
        return sorted(records, key=lambda record: record["agent_round"])

    reward_records = round_reward_records()
    first_success_round = positive_int("first_success_round")
    if first_success_round is None:
        for record in reward_records:
            if record.get("passed") is True:
                first_success_round = int(record["agent_round"])
                break

    driver_lifecycle_command_successful = (
        count("remote_command_file_bridge_driver_lifecycle_failure_count") == 0
    )
    selected_todo_claimed = bool(
        controller_trace.get("selected_todo_claimed") is True
        or successful_subcommand_count("todo claim") > 0
        or (
            driver_lifecycle_command_successful
            and driver_command_count("todo claim") > 0
        )
    )
    selected_todo_updated_before_solver = bool(
        controller_trace.get("selected_todo_updated_before_solver") is True
        or successful_subcommand_count("todo update") > 0
        or (
            driver_lifecycle_command_successful
            and driver_command_count("todo update") > 0
        )
    )
    selected_todo_completed_before_spend = bool(
        controller_trace.get("selected_todo_completed_before_spend") is True
        or (
            successful_subcommand_count("todo complete") > 0
            and successful_subcommand_count("quota spend-slot") > 0
        )
    )

    counters: dict[str, Any] = {
        "controller_trace_present": True,
        "controller_trace_schema_version": schema_version,
        "controller_trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        "controller_action_decisions": count("controller_action_decisions"),
        "initial_prompt_count": count("initial_prompt_count"),
        "followup_prompt_count": count("followup_prompt_count"),
        "stop_decision_count": count("stop_decision_count"),
        "reward_observation_count": count("reward_observation_count"),
        "round_reward_count": len(reward_records),
        "official_success_observed": controller_trace.get("official_success_observed")
        is True
        or first_success_round is not None,
        "official_success_observation_count": count(
            "official_success_observation_count"
        ),
        "first_success_round": first_success_round,
        "verifier_feedback_observation_count": count(
            "verifier_feedback_observation_count"
        ),
        "official_feedback_blinded_count": count("official_feedback_blinded_count"),
        "official_feedback_forwarded_count": count("official_feedback_forwarded_count"),
        "official_feedback_forwarded": controller_trace.get(
            "official_feedback_forwarded"
        )
        is True,
        "blind_loop": controller_trace.get("blind_loop") is True,
        "product_mode": controller_trace.get("product_mode") is True,
        "goal_start_product_mode": controller_trace.get("goal_start_product_mode")
        is True,
        "verifier_failure_feedback_todo_route": controller_trace.get(
            "verifier_failure_feedback_todo_route"
        )
        is True,
        "verifier_failure_feedback_forwarded_to_agent": controller_trace.get(
            "verifier_failure_feedback_forwarded_to_agent"
        )
        is True,
        "verifier_failure_todo_required": controller_trace.get(
            "verifier_failure_todo_required"
        )
        is True,
        "goal_start_plan_observed": controller_trace.get("goal_start_plan_observed")
        is True,
        "planner_before_todo_write": controller_trace.get("planner_before_todo_write")
        is True,
        "same_priority_order_preserved": controller_trace.get(
            "same_priority_order_preserved"
        )
        is True,
        "selected_todo_claimed": selected_todo_claimed,
        "selected_todo_updated_before_solver": selected_todo_updated_before_solver,
        "selected_todo_completed_before_spend": selected_todo_completed_before_spend,
        "non_selected_todos_preserved_open_or_deferred": controller_trace.get(
            "non_selected_todos_preserved_open_or_deferred"
        )
        is True,
        "planned_todo_count": count("planned_todo_count"),
        "planned_p0_count": count("planned_p0_count"),
        "case_goal_state_packet_present": controller_trace.get(
            "case_goal_state_packet_present"
        )
        is True,
        "case_goal_state_init_required": controller_trace.get(
            "case_goal_state_init_required"
        )
        is True,
        "case_goal_state_initialized_before_agent": controller_trace.get(
            "case_goal_state_initialized_before_agent"
        )
        is True,
        "declared_done_requires_no_remaining_goals": controller_trace.get(
            "declared_done_requires_no_remaining_goals"
        )
        is True,
        "product_mode_lifecycle_checkpoint_required": controller_trace.get(
            "product_mode_lifecycle_checkpoint_required"
        )
        is True,
        "product_mode_solver_activity_required": controller_trace.get(
            "product_mode_solver_activity_required"
        )
        is True,
        "product_mode_solver_activity_gap": controller_trace.get(
            "product_mode_solver_activity_gap"
        )
        is True,
        "product_mode_declared_done_below_passing_reward": controller_trace.get(
            "product_mode_declared_done_below_passing_reward"
        )
        is True,
        "product_mode_no_open_todo_below_passing_reward_stop": controller_trace.get(
            "product_mode_no_open_todo_below_passing_reward_stop"
        )
        is True,
        "product_mode_host_local_idle_no_task_output_progress": controller_trace.get(
            "product_mode_host_local_idle_no_task_output_progress"
        )
        is True,
        "product_mode_host_local_idle_no_task_output_progress_stop": controller_trace.get(
            "product_mode_host_local_idle_no_task_output_progress_stop"
        )
        is True,
        "agent_declared_done": controller_trace.get("agent_declared_done") is True,
        "agent_declared_no_remaining_goals": controller_trace.get(
            "agent_declared_no_remaining_goals"
        )
        is True,
        "max_rounds_budget": count("max_rounds_budget"),
        "loopx_state_reads": count("loopx_state_reads"),
        "loopx_state_writes": count("loopx_state_writes"),
        "loopx_case_state_reads": count("loopx_case_state_reads"),
        "loopx_case_state_writes": count("loopx_case_state_writes"),
        "native_goal_worker_route": controller_trace.get("native_goal_worker_route")
        is True,
        "native_goal_worker_session_policy": text_value(
            "native_goal_worker_session_policy"
        ),
        "native_goal_worker_max_rounds_budget_applies_to": text_value(
            "native_goal_worker_max_rounds_budget_applies_to"
        ),
        "native_goal_worker_initial_goal_turn_budget": count(
            "native_goal_worker_initial_goal_turn_budget"
        ),
        "native_goal_worker_same_thread_followup_budget": count(
            "native_goal_worker_same_thread_followup_budget"
        ),
        "native_goal_worker_independent_attempt_budget": count(
            "native_goal_worker_independent_attempt_budget"
        ),
        "native_goal_worker_fresh_goal_thread_per_independent_attempt": controller_trace.get(
            "native_goal_worker_fresh_goal_thread_per_independent_attempt"
        )
        is True,
        "native_goal_worker_connected": controller_trace.get(
            "native_goal_worker_connected"
        )
        is True,
        "native_goal_worker_trace_dir_present": controller_trace.get(
            "native_goal_worker_trace_dir_present"
        )
        is True,
        "native_goal_worker_public_trace_read": controller_trace.get(
            "native_goal_worker_public_trace_read"
        )
        is True,
        "native_goal_worker_raw_material_recorded": controller_trace.get(
            "native_goal_worker_raw_material_recorded"
        )
        is True,
        "native_goal_worker_connect_count": count("native_goal_worker_connect_count"),
        "native_goal_worker_trace_count": count("native_goal_worker_trace_count"),
        "native_goal_worker_lifecycle_trace_count": count(
            "native_goal_worker_lifecycle_trace_count"
        ),
        "native_goal_worker_prompt_received_count": count(
            "native_goal_worker_prompt_received_count"
        ),
        "native_goal_worker_ok_count": count("native_goal_worker_ok_count"),
        "native_goal_worker_failure_trace_count": count(
            "native_goal_worker_failure_trace_count"
        ),
        "native_goal_worker_failure_category": text_value(
            "native_goal_worker_failure_category"
        ),
        "native_goal_worker_failure_categories": text_list(
            "native_goal_worker_failure_categories"
        ),
        "native_goal_worker_first_blocker": text_value(
            "native_goal_worker_first_blocker"
        ),
        "native_goal_worker_first_blockers": text_list(
            "native_goal_worker_first_blockers"
        ),
        "native_goal_worker_goal_get_count": count("native_goal_worker_goal_get_count"),
        "native_goal_worker_turn_start_count": count(
            "native_goal_worker_turn_start_count"
        ),
        "native_goal_worker_turn_completed_observed_count": count(
            "native_goal_worker_turn_completed_observed_count"
        ),
        "native_goal_worker_assistant_message_present_count": count(
            "native_goal_worker_assistant_message_present_count"
        ),
        "native_goal_worker_assistant_context_only_count": count(
            "native_goal_worker_assistant_context_only_count"
        ),
        "native_goal_worker_context_only_recovery_attempted_count": count(
            "native_goal_worker_context_only_recovery_attempted_count"
        ),
        "native_goal_worker_context_only_recovery_succeeded_count": count(
            "native_goal_worker_context_only_recovery_succeeded_count"
        ),
        "native_goal_worker_context_only_followup_start_attempted_count": count(
            "native_goal_worker_context_only_followup_start_attempted_count"
        ),
        "native_goal_worker_context_only_followup_start_succeeded_count": count(
            "native_goal_worker_context_only_followup_start_succeeded_count"
        ),
        "native_goal_worker_transport_reconnect_attempted_count": count(
            "native_goal_worker_transport_reconnect_attempted_count"
        ),
        "native_goal_worker_transport_reconnect_succeeded_count": count(
            "native_goal_worker_transport_reconnect_succeeded_count"
        ),
        "native_goal_worker_goal_reactivation_attempted_count": count(
            "native_goal_worker_goal_reactivation_attempted_count"
        ),
        "native_goal_worker_goal_reactivation_succeeded_count": count(
            "native_goal_worker_goal_reactivation_succeeded_count"
        ),
        "native_goal_worker_post_context_assistant_chars_total": count(
            "native_goal_worker_post_context_assistant_chars_total"
        ),
        "native_goal_worker_reasoning_effort": text_value(
            "native_goal_worker_reasoning_effort"
        ),
        "native_goal_worker_reasoning_efforts": text_list(
            "native_goal_worker_reasoning_efforts"
        ),
        "native_goal_worker_first_action_observed_count": count(
            "native_goal_worker_first_action_observed_count"
        ),
        "native_goal_worker_effective_action_observed_count": count(
            "native_goal_worker_effective_action_observed_count"
        ),
        "remote_command_file_bridge_consumed_by_solver": controller_trace.get(
            "remote_command_file_bridge_consumed_by_solver"
        )
        is True,
        "remote_command_file_bridge_solver_trace_dir_present": controller_trace.get(
            "remote_command_file_bridge_solver_trace_dir_present"
        )
        is True,
        "remote_command_file_bridge_solver_public_trace_read": controller_trace.get(
            "remote_command_file_bridge_solver_public_trace_read"
        )
        is True,
        "remote_command_file_bridge_solver_raw_material_recorded": controller_trace.get(
            "remote_command_file_bridge_solver_raw_material_recorded"
        )
        is True,
        "remote_command_file_bridge_solver_trace_count": count(
            "remote_command_file_bridge_solver_trace_count"
        ),
        "remote_command_file_bridge_solver_probe_ready_count": count(
            "remote_command_file_bridge_solver_probe_ready_count"
        ),
        "remote_command_file_bridge_solver_operation_count": count(
            "remote_command_file_bridge_solver_operation_count"
        ),
        "remote_command_file_bridge_agent_operation_trace_count": count(
            "remote_command_file_bridge_agent_operation_trace_count"
        ),
        "remote_command_file_bridge_agent_command_configured": controller_trace.get(
            "remote_command_file_bridge_agent_command_configured"
        )
        is True,
        "remote_command_file_bridge_agent_command_instrumented": controller_trace.get(
            "remote_command_file_bridge_agent_command_instrumented"
        )
        is True,
        "remote_command_file_bridge_agent_operation_trace_required": controller_trace.get(
            "remote_command_file_bridge_agent_operation_trace_required"
        )
        is True,
        "remote_command_file_bridge_agent_operation_trace_satisfied": controller_trace.get(
            "remote_command_file_bridge_agent_operation_trace_satisfied"
        )
        is True,
        "remote_command_file_bridge_agent_operation_trace_status": str(
            controller_trace.get(
                "remote_command_file_bridge_agent_operation_trace_status"
            )
            or ""
        )[:120],
        "remote_command_file_bridge_agent_request_count": count(
            "remote_command_file_bridge_agent_request_count"
        ),
        "remote_command_file_bridge_agent_success_count": count(
            "remote_command_file_bridge_agent_success_count"
        ),
        "remote_command_file_bridge_agent_failure_count": count(
            "remote_command_file_bridge_agent_failure_count"
        ),
        "remote_command_file_bridge_agent_failure_category_counts": count_map(
            "remote_command_file_bridge_agent_failure_category_counts"
        ),
        "remote_command_file_bridge_agent_loopx_cli_call_count": count(
            "remote_command_file_bridge_agent_loopx_cli_call_count"
        ),
        "remote_command_file_bridge_agent_loopx_state_read_count": count(
            "remote_command_file_bridge_agent_loopx_state_read_count"
        ),
        "remote_command_file_bridge_agent_loopx_state_write_count": count(
            "remote_command_file_bridge_agent_loopx_state_write_count"
        ),
        "remote_command_file_bridge_agent_todo_closeout_count": max_direct_or_subcommands(
            "remote_command_file_bridge_agent_todo_closeout_count",
            ("todo complete", "todo update"),
        ),
        "remote_command_file_bridge_agent_refresh_state_count": max_direct_or_subcommands(
            "remote_command_file_bridge_agent_refresh_state_count",
            ("refresh-state",),
        ),
        "remote_command_file_bridge_agent_quota_spend_slot_count": max_direct_or_subcommands(
            "remote_command_file_bridge_agent_quota_spend_slot_count",
            ("quota spend-slot",),
        ),
        "remote_command_file_bridge_agent_task_facing_operation_count": count(
            "remote_command_file_bridge_agent_task_facing_operation_count"
        ),
        "remote_command_file_bridge_agent_task_facing_success_count": count(
            "remote_command_file_bridge_agent_task_facing_success_count"
        ),
        "remote_command_file_bridge_agent_task_facing_failure_count": count(
            "remote_command_file_bridge_agent_task_facing_failure_count"
        ),
        "remote_command_file_bridge_agent_probe_operation_count": count(
            "remote_command_file_bridge_agent_probe_operation_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_trace_count": count(
            "remote_command_file_bridge_driver_lifecycle_trace_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count": count(
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_request_count": count(
            "remote_command_file_bridge_driver_lifecycle_request_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_success_count": count(
            "remote_command_file_bridge_driver_lifecycle_success_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_failure_count": count(
            "remote_command_file_bridge_driver_lifecycle_failure_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": count(
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": count(
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
        ),
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": count(
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
        ),
        "host_local_acp_codex_exec_failure_trace_count": count(
            "host_local_acp_codex_exec_failure_trace_count"
        ),
        "host_local_acp_codex_exec_failure_trace_present": controller_trace.get(
            "host_local_acp_codex_exec_failure_trace_present"
        )
        is True,
        "host_local_acp_codex_exec_failure_raw_material_recorded": controller_trace.get(
            "host_local_acp_codex_exec_failure_raw_material_recorded"
        )
        is True,
        "heartbeat_count": count("heartbeat_count"),
        "raw_task_text_recorded": controller_trace.get("raw_task_text_recorded")
        is True,
        "raw_verifier_output_recorded": controller_trace.get(
            "raw_verifier_output_recorded"
        )
        is True,
        "raw_agent_trajectory_recorded": controller_trace.get(
            "raw_agent_trajectory_recorded"
        )
        is True,
        "loopx_case_source_install_requested": controller_trace.get(
            "loopx_case_source_install_requested"
        )
        is True,
        "loopx_case_source_path_recorded": controller_trace.get(
            "loopx_case_source_path_recorded"
        )
        is True,
        "benchflow_user_loop_final_verify_recovery_enabled": controller_trace.get(
            "benchflow_user_loop_final_verify_recovery_enabled"
        )
        is True,
        "benchflow_user_loop_final_verify_recovery_triggered": controller_trace.get(
            "benchflow_user_loop_final_verify_recovery_triggered"
        )
        is True,
        "benchflow_user_loop_recovery_after_agent_activity": controller_trace.get(
            "benchflow_user_loop_recovery_after_agent_activity"
        )
        is True,
        "benchflow_user_loop_recovery_preserved_final_verify": controller_trace.get(
            "benchflow_user_loop_recovery_preserved_final_verify"
        )
        is True,
        "benchflow_user_loop_recovery_raw_error_recorded": controller_trace.get(
            "benchflow_user_loop_recovery_raw_error_recorded"
        )
        is True,
        "benchflow_user_loop_recovery_round": count(
            "benchflow_user_loop_recovery_round"
        ),
        "benchflow_user_loop_recovery_delta_events": count(
            "benchflow_user_loop_recovery_delta_events"
        ),
        "benchflow_user_loop_recovery_delta_tool_calls": count(
            "benchflow_user_loop_recovery_delta_tool_calls"
        ),
        "benchflow_user_loop_soft_verify_exception_continued": controller_trace.get(
            "benchflow_user_loop_soft_verify_exception_continued"
        )
        is True,
        "benchflow_user_loop_soft_verify_exception_raw_error_recorded": controller_trace.get(
            "benchflow_user_loop_soft_verify_exception_raw_error_recorded"
        )
        is True,
        "benchflow_user_loop_soft_verify_exception_stage": str(
            controller_trace.get("benchflow_user_loop_soft_verify_exception_stage")
            or ""
        )[:120],
        "benchflow_user_loop_soft_verify_exception_type": str(
            controller_trace.get("benchflow_user_loop_soft_verify_exception_type")
            or ""
        )[:120],
        "benchflow_user_loop_soft_verify_exception_count": count(
            "benchflow_user_loop_soft_verify_exception_count"
        ),
        "benchflow_user_loop_soft_verify_exception_round": count(
            "benchflow_user_loop_soft_verify_exception_round"
        ),
        "benchflow_user_loop_soft_verify_exception_delta_events": count(
            "benchflow_user_loop_soft_verify_exception_delta_events"
        ),
        "benchflow_user_loop_soft_verify_exception_delta_tool_calls": count(
            "benchflow_user_loop_soft_verify_exception_delta_tool_calls"
        ),
        "benchflow_intermediate_soft_verify_final_only": controller_trace.get(
            "benchflow_intermediate_soft_verify_final_only"
        )
        is True,
        "benchflow_intermediate_soft_verify_raw_output_recorded": controller_trace.get(
            "benchflow_intermediate_soft_verify_raw_output_recorded"
        )
        is True,
        "benchflow_intermediate_soft_verify_call_count": count(
            "benchflow_intermediate_soft_verify_call_count"
        ),
        "benchflow_intermediate_soft_verify_skipped_count": count(
            "benchflow_intermediate_soft_verify_skipped_count"
        ),
        "product_mode_lifecycle_checkpoint_count": count(
            "product_mode_lifecycle_checkpoint_count"
        ),
        "product_mode_lifecycle_checkpoint_round": count(
            "product_mode_lifecycle_checkpoint_round"
        ),
        "product_mode_solver_activity_gap_count": count(
            "product_mode_solver_activity_gap_count"
        ),
        "product_mode_solver_activity_gap_round": count(
            "product_mode_solver_activity_gap_round"
        ),
        "product_mode_declared_done_below_passing_reward_count": count(
            "product_mode_declared_done_below_passing_reward_count"
        ),
        "product_mode_declared_done_below_passing_reward_round": count(
            "product_mode_declared_done_below_passing_reward_round"
        ),
        "verifier_failure_feedback_todo_prompt_count": count(
            "verifier_failure_feedback_todo_prompt_count"
        ),
        "verifier_failure_feedback_todo_round": count(
            "verifier_failure_feedback_todo_round"
        ),
        "open_todo_count": count("open_todo_count"),
        "product_mode_no_open_todo_below_passing_reward_streak": count(
            "product_mode_no_open_todo_below_passing_reward_streak"
        ),
        "product_mode_no_open_todo_below_passing_reward_streak_threshold": count(
            "product_mode_no_open_todo_below_passing_reward_streak_threshold"
        ),
        "product_mode_no_open_todo_below_passing_reward_round": count(
            "product_mode_no_open_todo_below_passing_reward_round"
        ),
        "product_mode_no_open_todo_below_passing_reward_stop_count": count(
            "product_mode_no_open_todo_below_passing_reward_stop_count"
        ),
        "product_mode_no_open_todo_below_passing_reward_stop_round": count(
            "product_mode_no_open_todo_below_passing_reward_stop_round"
        ),
        "product_mode_no_open_todo_below_passing_reward_open_todo_count_public": count(
            "product_mode_no_open_todo_below_passing_reward_open_todo_count_public"
        ),
        "product_mode_host_local_idle_no_task_output_progress_streak": count(
            "product_mode_host_local_idle_no_task_output_progress_streak"
        ),
        "product_mode_host_local_idle_no_task_output_progress_streak_threshold": count(
            "product_mode_host_local_idle_no_task_output_progress_streak_threshold"
        ),
        "product_mode_host_local_idle_no_task_output_progress_round": count(
            "product_mode_host_local_idle_no_task_output_progress_round"
        ),
        "product_mode_host_local_idle_no_task_output_progress_stop_count": count(
            "product_mode_host_local_idle_no_task_output_progress_stop_count"
        ),
        "product_mode_host_local_idle_no_task_output_progress_stop_round": count(
            "product_mode_host_local_idle_no_task_output_progress_stop_round"
        ),
        "product_mode_host_local_idle_no_task_output_progress_last_failure_trace_count": count(
            "product_mode_host_local_idle_no_task_output_progress_last_failure_trace_count"
        ),
        "product_mode_host_local_idle_no_task_output_progress_acp_tool_calls": count(
            "product_mode_host_local_idle_no_task_output_progress_acp_tool_calls"
        ),
        "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops": count(
            "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops"
        ),
        "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes": count(
            "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes"
        ),
        "product_mode_final_closeout_superseded_by_official_success": (
            controller_trace.get(
                "product_mode_final_closeout_superseded_by_official_success"
            )
            is True
        ),
        "product_mode_final_closeout_superseded_round": count(
            "product_mode_final_closeout_superseded_round"
        ),
        "product_mode_no_tool_call_lifecycle_abort": controller_trace.get(
            "product_mode_no_tool_call_lifecycle_abort"
        )
        is True,
        "product_mode_no_tool_call_lifecycle_abort_count": count(
            "product_mode_no_tool_call_lifecycle_abort_count"
        ),
        "product_mode_no_tool_call_lifecycle_abort_round": count(
            "product_mode_no_tool_call_lifecycle_abort_round"
        ),
        "product_mode_no_lifecycle_request_abort": controller_trace.get(
            "product_mode_no_lifecycle_request_abort"
        )
        is True,
        "product_mode_no_lifecycle_request_abort_count": count(
            "product_mode_no_lifecycle_request_abort_count"
        ),
        "product_mode_no_lifecycle_request_abort_round": count(
            "product_mode_no_lifecycle_request_abort_round"
        ),
    }
    last_decision = _skillsbench_public_safe_label(
        controller_trace.get("last_decision") or ""
    )
    if last_decision:
        counters["last_decision"] = last_decision
    final_closeout_superseded_reason = _skillsbench_public_safe_label(
        controller_trace.get("product_mode_final_closeout_superseded_reason") or ""
    )
    if final_closeout_superseded_reason:
        counters["product_mode_final_closeout_superseded_reason"] = (
            final_closeout_superseded_reason
        )
    bridge_consumption_decision = _skillsbench_public_safe_label(
        controller_trace.get("remote_command_file_bridge_consumption_decision") or ""
    )
    if bridge_consumption_decision:
        counters["remote_command_file_bridge_consumption_decision"] = (
            bridge_consumption_decision
        )
    selected_p0_todo_id = _skillsbench_public_safe_label(
        controller_trace.get("selected_p0_todo_id") or ""
    )
    if selected_p0_todo_id:
        counters["selected_p0_todo_id"] = selected_p0_todo_id
    for source_key in (
        "remote_command_file_bridge_agent_loopx_subcommand_counts",
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts",
        "remote_command_file_bridge_driver_lifecycle_command_counts",
        "remote_command_file_bridge_driver_lifecycle_returncode_counts",
    ):
        counts = count_map(source_key)
        if counts:
            counters[source_key] = counts
    init_status = _skillsbench_public_safe_label(
        controller_trace.get("case_goal_state_init_status") or ""
    )
    if init_status:
        counters["case_goal_state_init_status"] = init_status
    init_failed_phase = _skillsbench_public_safe_label(
        controller_trace.get("case_goal_state_init_failed_phase") or ""
    )
    if init_failed_phase:
        counters["case_goal_state_init_failed_phase"] = init_failed_phase
    case_state_schema = _skillsbench_public_safe_label(
        controller_trace.get("case_goal_state_schema_version") or ""
    )
    if case_state_schema:
        counters["case_goal_state_schema_version"] = case_state_schema
    recovery_stage = _skillsbench_public_safe_label(
        controller_trace.get("benchflow_user_loop_recovery_stage") or ""
    )
    if recovery_stage:
        counters["benchflow_user_loop_recovery_stage"] = recovery_stage
    recovery_exception_type = _skillsbench_public_safe_label(
        controller_trace.get("benchflow_user_loop_recovery_exception_type") or ""
    )
    if recovery_exception_type:
        counters["benchflow_user_loop_recovery_exception_type"] = (
            recovery_exception_type
        )
    soft_verify_policy = _skillsbench_public_safe_label(
        controller_trace.get("benchflow_intermediate_soft_verify_policy") or ""
    )
    if soft_verify_policy:
        counters["benchflow_intermediate_soft_verify_policy"] = soft_verify_policy
    lifecycle_missing_reason = _skillsbench_public_safe_label(
        controller_trace.get("product_mode_lifecycle_checkpoint_missing_reason")
        or ""
    )
    if lifecycle_missing_reason:
        counters["product_mode_lifecycle_checkpoint_missing_reason"] = (
            lifecycle_missing_reason
        )
    solver_activity_missing_reason = _skillsbench_public_safe_label(
        controller_trace.get("product_mode_solver_activity_missing_reason") or ""
    )
    if solver_activity_missing_reason:
        counters["product_mode_solver_activity_missing_reason"] = (
            solver_activity_missing_reason
        )
    workflow_style = _skillsbench_public_safe_label(
        controller_trace.get(
            "remote_command_file_bridge_driver_lifecycle_execution_style"
        )
        or ""
    )
    if workflow_style:
        counters["remote_command_file_bridge_driver_lifecycle_execution_style"] = (
            workflow_style
        )
    host_codex_failure_category = _skillsbench_public_safe_label(
        controller_trace.get("host_local_acp_codex_exec_failure_category") or ""
    )
    if host_codex_failure_category:
        counters["host_local_acp_codex_exec_failure_category"] = (
            host_codex_failure_category
        )
    bridge_progress_status = _skillsbench_public_safe_label(
        controller_trace.get("host_local_acp_bridge_progress_status") or ""
    )
    if bridge_progress_status:
        counters["host_local_acp_bridge_progress_status"] = (
            bridge_progress_status
        )
    bridge_progress_source = _skillsbench_public_safe_label(
        controller_trace.get("host_local_acp_bridge_progress_signal_source") or ""
    )
    if bridge_progress_source:
        counters["host_local_acp_bridge_progress_signal_source"] = (
            bridge_progress_source
        )
    host_codex_failure_categories: list[str] = []
    raw_host_codex_failure_categories = controller_trace.get(
        "host_local_acp_codex_exec_failure_categories"
    )
    if isinstance(raw_host_codex_failure_categories, list):
        for item in raw_host_codex_failure_categories:
            category = _skillsbench_public_safe_label(item or "")
            if category and category not in host_codex_failure_categories:
                host_codex_failure_categories.append(category)
    elif host_codex_failure_category:
        host_codex_failure_categories.append(host_codex_failure_category)
    if host_codex_failure_categories:
        counters["host_local_acp_codex_exec_failure_categories"] = (
            host_codex_failure_categories[:8]
        )
    case_state_path = str(controller_trace.get("case_goal_state_path") or "")
    if (
        "/.codex/goals/" in case_state_path
        and case_state_path.endswith("/ACTIVE_GOAL_STATE.md")
        and not re.search(r"^/(Users|private|var/folders)/", case_state_path)
    ):
        counters["case_goal_state_path"] = case_state_path
    declared_done_round = positive_int("declared_done_round")
    if declared_done_round is not None:
        counters["declared_done_round"] = declared_done_round
    declared_done_score = controller_trace.get("declared_done_score")
    if (
        isinstance(declared_done_score, (int, float))
        and not isinstance(declared_done_score, bool)
    ):
        counters["declared_done_score"] = float(declared_done_score)
    below_passing_score = controller_trace.get(
        "product_mode_declared_done_below_passing_reward_score"
    )
    if (
        isinstance(below_passing_score, (int, float))
        and not isinstance(below_passing_score, bool)
    ):
        counters["product_mode_declared_done_below_passing_reward_score"] = float(
            below_passing_score
        )
    no_open_todo_score = controller_trace.get(
        "product_mode_no_open_todo_below_passing_reward_score"
    )
    if (
        isinstance(no_open_todo_score, (int, float))
        and not isinstance(no_open_todo_score, bool)
    ):
        counters["product_mode_no_open_todo_below_passing_reward_score"] = float(
            no_open_todo_score
        )
    below_passing_score_status = _skillsbench_public_safe_label(
        controller_trace.get(
            "product_mode_declared_done_below_passing_reward_score_status"
        )
        or ""
    )
    if below_passing_score_status:
        counters["product_mode_declared_done_below_passing_reward_score_status"] = (
            below_passing_score_status
        )
    no_open_todo_score_status = _skillsbench_public_safe_label(
        controller_trace.get(
            "product_mode_no_open_todo_below_passing_reward_score_status"
        )
        or ""
    )
    if no_open_todo_score_status:
        counters["product_mode_no_open_todo_below_passing_reward_score_status"] = (
            no_open_todo_score_status
        )
    host_idle_score = controller_trace.get(
        "product_mode_host_local_idle_no_task_output_progress_score"
    )
    if (
        isinstance(host_idle_score, (int, float))
        and not isinstance(host_idle_score, bool)
    ):
        counters["product_mode_host_local_idle_no_task_output_progress_score"] = float(
            host_idle_score
        )
    host_idle_score_status = _skillsbench_public_safe_label(
        controller_trace.get(
            "product_mode_host_local_idle_no_task_output_progress_score_status"
        )
        or ""
    )
    if host_idle_score_status:
        counters["product_mode_host_local_idle_no_task_output_progress_score_status"] = (
            host_idle_score_status
        )
    host_idle_category = _skillsbench_public_safe_label(
        controller_trace.get(
            "product_mode_host_local_idle_no_task_output_progress_category"
        )
        or ""
    )
    if host_idle_category:
        counters["product_mode_host_local_idle_no_task_output_progress_category"] = (
            host_idle_category
        )
    host_idle_policy = _skillsbench_public_safe_label(
        controller_trace.get(
            "product_mode_host_local_idle_no_task_output_progress_policy"
        )
        or ""
    )
    if host_idle_policy:
        counters["product_mode_host_local_idle_no_task_output_progress_policy"] = (
            host_idle_policy
        )
    declared_done_policy = _skillsbench_public_safe_label(
        controller_trace.get("product_mode_declared_done_policy") or ""
    )
    if declared_done_policy:
        counters["product_mode_declared_done_policy"] = declared_done_policy
    if reward_records:
        counters["round_rewards"] = reward_records
    trajectory_summary = (
        controller_trace.get("acp_trajectory_summary")
        if isinstance(controller_trace.get("acp_trajectory_summary"), dict)
        else {}
    )
    if trajectory_summary:
        counters["acp_trajectory_summary"] = {
            key: trajectory_summary.get(key)
            for key in (
                "schema_version",
                "private_trajectory_present",
                "raw_text_copied_to_public",
                "event_count",
                "round_count",
                "user_message_count",
                "agent_message_count",
                "tool_call_count",
                "action_category_counts",
                "round_action_category_counts",
                "loopx_cli_call_count",
                "loopx_cli_calls",
                "loopx_cli_state_usage_counts",
                "loopx_cli_state_read_count",
                "loopx_cli_state_write_count",
                "loopx_case_state_path_count",
                "loopx_case_state_read_count",
                "loopx_case_state_write_count",
                "protected_path_mention_count",
                "protected_path_edit_signal_count",
                "codex_acp_text_present",
                "codex_acp_text_bytes",
            )
            if trajectory_summary.get(key) is not None
        }
    return counters


def _skillsbench_native_goal_worker_trace_status(
    counters: dict[str, Any],
) -> str:
    if counters.get("native_goal_worker_route") is not True:
        return "not_native_goal_worker_route"
    trace_count = counters.get("native_goal_worker_trace_count")
    if (
        isinstance(trace_count, int)
        and not isinstance(trace_count, bool)
        and trace_count > 0
        and counters.get("native_goal_worker_public_trace_read") is True
    ):
        turn_start_count = counters.get("native_goal_worker_turn_start_count")
        goal_get_count = counters.get("native_goal_worker_goal_get_count")
        assistant_message_count = counters.get(
            "native_goal_worker_assistant_message_present_count"
        )
        if any(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in (turn_start_count, goal_get_count, assistant_message_count)
        ):
            return "public_trace_observed"
        prompt_received_count = counters.get(
            "native_goal_worker_prompt_received_count"
        )
        if (
            isinstance(prompt_received_count, int)
            and not isinstance(prompt_received_count, bool)
            and prompt_received_count > 0
        ):
            return "worker_prompt_received_no_turn_trace"
        lifecycle_trace_count = counters.get(
            "native_goal_worker_lifecycle_trace_count"
        )
        if (
            isinstance(lifecycle_trace_count, int)
            and not isinstance(lifecycle_trace_count, bool)
            and lifecycle_trace_count > 0
        ):
            return "worker_connected_no_prompt_trace"
        return "worker_connected_no_turn_trace"
    if counters.get("native_goal_worker_connected") is True:
        if counters.get("native_goal_worker_trace_dir_present") is not True:
            return "worker_connected_trace_dir_missing"
        return "worker_connected_no_public_trace"
    return "worker_route_selected_not_connected"


def _skillsbench_native_goal_worker_failure_label(
    counters: dict[str, Any],
    *,
    trace_status: str,
) -> str:
    if counters.get("native_goal_worker_route") is not True:
        return ""
    has_worker_failure_trace = bool(
        counters.get("native_goal_worker_failure_trace_count", 0)
        or counters.get("native_goal_worker_failure_category")
    )
    context_only_count = counters.get("native_goal_worker_assistant_context_only_count")
    post_context_chars = counters.get(
        "native_goal_worker_post_context_assistant_chars_total"
    )
    if (
        isinstance(context_only_count, int)
        and not isinstance(context_only_count, bool)
        and context_only_count > 0
        and (
            not isinstance(post_context_chars, int)
            or isinstance(post_context_chars, bool)
            or post_context_chars <= 0
        )
    ):
        return (
            "skillsbench_native_goal_worker_failed_"
            "codex_app_server_context_only_assistant_message"
        )

    if trace_status == "public_trace_observed" and not has_worker_failure_trace:
        return ""

    reason = ""
    for key in (
        "native_goal_worker_failure_category",
        "native_goal_worker_first_blocker",
    ):
        value = counters.get(key)
        if isinstance(value, str) and value:
            reason = value
            break
    if not reason:
        reason = trace_status or "compact_proof_missing"
    safe_reason = re.sub(r"[^a-zA-Z0-9]+", "_", reason).strip("_").lower()
    if not safe_reason:
        safe_reason = "compact_proof_missing"
    prefix = (
        "skillsbench_native_goal_worker_failed"
        if (
            counters.get("native_goal_worker_failure_trace_count", 0)
            or counters.get("native_goal_worker_failure_category")
        )
        else "skillsbench_native_goal_worker_uncountable"
    )
    return f"{prefix}_{safe_reason}"[:160]


def _round_reward_trace_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_records: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        agent_round = item.get("agent_round")
        reward = item.get("reward")
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
                "passed": item.get("passed") if isinstance(item.get("passed"), bool) else reward >= 1,
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
        "loop_score_policy": "best_round_for_offline_controller_analysis",
        "official_score_policy": "final_workspace_official_result",
    }


def _post_success_controller_trace_score(
    round_reward_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(round_reward_trace, dict):
        return {}
    if round_reward_trace.get("success_observed") is not True:
        return {}
    reward = round_reward_trace.get("best_round_reward")
    if not isinstance(reward, (int, float)) or isinstance(reward, bool):
        return {}
    round_index = round_reward_trace.get("best_reward_round")
    return {
        "value": float(reward),
        "passed": reward >= 1.0,
        "round": round_index
        if isinstance(round_index, int) and not isinstance(round_index, bool)
        else None,
        "policy": "best_round_for_post_success_acp_closeout_recovery",
    }


def build_skillsbench_benchflow_result_benchmark_run(
    result_json_path: str | Path,
    *,
    route: str = SKILLSBENCH_DEFAULT_ROUTE,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    agent: str = "codex",
    model: str | None = None,
    runner_warning_labels: Iterable[str] | None = None,
    controller_trace: dict[str, Any] | None = None,
    result_discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a public-safe benchmark_run_v0 from an official SkillsBench result.

    The official BenchFlow result.json already contains the compact fields we
    need for ledgering: task name, agent/model, reward, error, tool-call count,
    and timing. This reducer deliberately reads only result.json and sibling
    timing.json; it does not read prompts, trajectories, verifier stdout, task
    text, screenshots, or credential material.
    """

    result_path = Path(result_json_path).expanduser()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("SkillsBench result.json must contain a JSON object")

    task_id = str(result.get("task_name") or "").strip()
    if not task_id:
        raise ValueError("SkillsBench result.json is missing task_name")

    contract = skillsbench_route_contract(route)
    observed_agent = str(result.get("agent") or result.get("agent_name") or agent)
    if observed_agent not in {"codex", "codex-acp", "oracle"}:
        raise ValueError(
            "SkillsBench BenchFlow ingest currently supports codex/codex-acp/oracle only"
        )
    is_oracle_runner = observed_agent == "oracle"
    requested_model = str(
        model
        or result.get("model")
        or (
            "not_applicable_oracle_runner"
            if is_oracle_runner
            else SKILLSBENCH_DEFAULT_MODEL
        )
    )
    observed_model = str(result.get("model") or requested_model)
    warning_labels = [
        label
        for label in (
            _skillsbench_public_safe_label(item)
            for item in (runner_warning_labels or [])
        )
        if label
    ]
    model_control_status = "reported_model_from_result_metadata"
    actual_model_verified = False
    actual_model_source = "official_skillsbench_result_model_field"
    if is_oracle_runner:
        model_control_status = "not_applicable_oracle_runner"
        actual_model_verified = True
        actual_model_source = "official_skillsbench_oracle_runner_no_model"
    if CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL in warning_labels:
        model_control_status = "requested_model_not_enforced_by_acp"
        actual_model_verified = False
        actual_model_source = "codex_acp_default_or_launch_config"
    rollout_name = str(result.get("rollout_name") or f"{task_id}_{route}")
    contract_loopx_automation_loop = (
        False if is_oracle_runner else contract["loopx_automation_loop"]
    )
    contract_loopx_inside_case = (
        False if is_oracle_runner else contract["loopx_inside_case"]
    )
    contract_inner_codex_goal_mode = (
        False if is_oracle_runner else contract["inner_codex_goal_mode"]
    )
    contract_native_goal_mode_requested = (
        False if is_oracle_runner else contract["native_goal_mode_requested"]
    )
    contract_native_goal_mode_invoked = (
        False if is_oracle_runner else contract["native_goal_mode_invoked"]
    )
    contract_native_goal_mode_confirmation_status = (
        "not_applicable_oracle_runner"
        if is_oracle_runner
        else contract["native_goal_mode_confirmation_status"]
    )
    contract_codex_acp_protocol_used = (
        False if is_oracle_runner else contract["codex_acp_protocol_used"]
    )
    contract_curated_skills_visible = (
        False if is_oracle_runner else contract["curated_skills_visible"]
    )
    contract_blind_loop = False if is_oracle_runner else contract["blind_loop"]
    contract_official_feedback_blinded = (
        True if is_oracle_runner else contract["official_feedback_blinded"]
    )
    contract_reward_feedback_forwarded = (
        False if is_oracle_runner else contract["reward_feedback_forwarded"]
    )
    contract_case_semantics_changed_by_harness = (
        False if is_oracle_runner else contract["case_semantics_changed_by_harness"]
    )
    contract_skillsbench_route_semantics = (
        "skillsbench_oracle_solution_validation_no_model"
        if is_oracle_runner
        else contract["skillsbench_route_semantics"]
    )
    contract_official_score_comparable_to_native_codex = False
    if not is_oracle_runner:
        contract_official_score_comparable_to_native_codex = contract[
            "official_score_comparable_to_native_codex"
        ]
    contract_official_score_comparable_to_loopx_treatment = (
        False
        if is_oracle_runner
        else contract["official_score_comparable_to_loopx_treatment"]
    )
    agent_kwargs_keys = [
        "benchflow_agent=oracle",
        "sandbox=docker",
        "no_upload",
        "single_task",
        "no_model_api",
    ] if is_oracle_runner else [
        "benchflow_agent=codex-acp",
        "sandbox=docker",
        "no_upload",
        "single_task",
    ]
    outer_controller = (
        "official_skillsbench_oracle_validation"
        if is_oracle_runner
        else "loopx_blind_automation_loop"
        if route == "loopx-blind-loop-treatment"
        else "loopx_prompt_polling_loop"
        if route == "loopx-prompt-polling-test"
        else _skillsbench_product_mode_outer_controller(route)
        if _is_skillsbench_loopx_product_mode_treatment_route(route)
        else "raw_codex_autonomous_max5"
        if route == "raw-codex-autonomous-max5"
        else "fixed_blind_loop_runner"
        if route == "codex-acp-blind-loop-baseline"
        else "runner_only"
    )
    inner_case_actor = (
        "skillsbench_oracle_solution_runner"
        if is_oracle_runner
        else "ordinary_codex_acp_agent"
        if route
        in {
            "loopx-blind-loop-treatment",
            "loopx-prompt-polling-test",
            "codex-acp-blind-loop-baseline",
            "raw-codex-autonomous-max5",
            *SKILLSBENCH_LOOPX_PRODUCT_MODE_TREATMENT_ROUTES,
        }
        else "codex_acp_goal_prompt_request_unconfirmed_native_goal_mode"
        if route == "codex-goal-mode-baseline"
        else "codex_acp_with_curated_skills"
    )

    rewards = result.get("rewards") if isinstance(result.get("rewards"), dict) else {}
    reward_value = rewards.get("reward")
    if not isinstance(reward_value, (int, float)) or isinstance(reward_value, bool):
        reward_value = None
    reward_artifact_source: str | None = None
    if reward_value is None:
        reward_value, reward_artifact_source = _skillsbench_rollout_reward_artifact(
            result_path
        )

    timing_path = result_path.with_name("timing.json")
    timing: dict[str, Any] = {}
    if timing_path.exists():
        raw_timing = json.loads(timing_path.read_text(encoding="utf-8"))
        if isinstance(raw_timing, dict):
            timing = raw_timing
    timing_summary = {
        key: value
        for key, value in timing.items()
        if key
        in {
            "environment_setup",
            "agent_setup",
            "agent_execution",
            "verifier",
            "total",
        }
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    }

    error = result.get("error")
    verifier_error = result.get("verifier_error")
    error_text = str(error).strip() if error else ""
    verifier_error_text = str(verifier_error).strip() if verifier_error else ""
    verifier_uv_bootstrap_failure = _skillsbench_verifier_uv_bootstrap_failure(
        verifier_error_text
    )
    if (
        verifier_uv_bootstrap_failure
        and reward_value == 0
        and reward_artifact_source is None
    ):
        reward_value = None
        warning_labels.append("skillsbench_verifier_uv_bootstrap_zero_reward_ignored")
    official_passed = bool(reward_value is not None and reward_value >= 1)
    failure_labels: list[str] = []
    exception_type = "none"
    score_failure_attribution = "none"
    runner_score_failure_attribution = "none"
    if error_text:
        exception_type, score_failure_attribution, failure_labels = (
            skillsbench_runner_error_attribution(error_text)
        )
        runner_score_failure_attribution = score_failure_attribution
    if verifier_error_text and reward_artifact_source:
        warning_labels.append(
            "skillsbench_result_json_reward_missing_recovered_from_reward_txt"
        )
    elif verifier_error_text:
        if score_failure_attribution in {"none", "skillsbench_runner_error"}:
            if verifier_uv_bootstrap_failure:
                exception_type = "skillsbench_verifier_uv_bootstrap_failure"
                failure_labels.extend(
                    [
                        "skillsbench_verifier_uv_bootstrap_failure",
                        "skillsbench_verifier_bootstrap_failure",
                        "verifier_infrastructure_failure",
                    ]
                )
                score_failure_attribution = (
                    "skillsbench_verifier_uv_bootstrap_failure"
                )
            else:
                exception_type = "skillsbench_verifier_error"
                failure_labels.append("verifier_infrastructure_failure")
                score_failure_attribution = "verifier_infrastructure_failure"
        elif "verifier_infrastructure_failure" not in failure_labels:
            failure_labels.append("verifier_infrastructure_failure")
        if (
            verifier_uv_bootstrap_failure
            and "skillsbench_verifier_uv_bootstrap_failure" not in failure_labels
        ):
            failure_labels.append("skillsbench_verifier_uv_bootstrap_failure")
            if "skillsbench_verifier_bootstrap_failure" not in failure_labels:
                failure_labels.append("skillsbench_verifier_bootstrap_failure")

    n_tool_calls = result.get("n_tool_calls")
    tool_calls = n_tool_calls if isinstance(n_tool_calls, int) else 0
    partial_trajectory = bool(result.get("partial_trajectory") is True)
    if reward_value == 0 and not failure_labels and not partial_trajectory:
        failure_labels.append("official_verifier_solution_failure")
        score_failure_attribution = "official_verifier_solution_failure"
    elif (
        reward_value == 0
        and reward_artifact_source
        and score_failure_attribution == "skillsbench_runner_error"
        and failure_labels == ["skillsbench_runner_error"]
    ):
        failure_labels.append("official_score_zero_case_failure")
        score_failure_attribution = "official_score_zero_case_failure"
    elif reward_value == 0 and not failure_labels:
        failure_labels.append("official_score_zero_case_failure")
    real_run_completed = not error_text and (
        not verifier_error_text or reward_artifact_source is not None
    )
    job_name = skillsbench_job_name(dataset, task_id, route)
    controller_counters = _skillsbench_controller_trace_counters(controller_trace)
    controller_trace_present = bool(controller_counters.get("controller_trace_present"))
    controller_raw_material_recorded = bool(
        controller_counters.get("raw_task_text_recorded")
        or controller_counters.get("raw_verifier_output_recorded")
        or controller_counters.get("raw_agent_trajectory_recorded")
    )
    counter_trust_level = "official_benchflow_compact_result"
    if controller_trace_present:
        counter_trust_level = (
            "official_benchflow_compact_result_plus_loopx_controller_trace"
        )
    evidence_files = [
        "official_skillsbench:result.json",
        "official_skillsbench:timing.json" if timing else "official_skillsbench:timing_missing",
    ]
    if reward_artifact_source:
        evidence_files.append("official_skillsbench:verifier/reward.txt")
    if controller_trace_present:
        evidence_files.append("loopx:controller_trace.public.json")
    trajectory_summary = (
        controller_counters.get("acp_trajectory_summary")
        if isinstance(controller_counters.get("acp_trajectory_summary"), dict)
        else {}
    )
    controller_initial_prompt_count = controller_counters.get("initial_prompt_count", 0)
    if not isinstance(controller_initial_prompt_count, int) or isinstance(
        controller_initial_prompt_count, bool
    ):
        controller_initial_prompt_count = 0
    controller_followup_prompt_count = controller_counters.get("followup_prompt_count", 0)
    if not isinstance(controller_followup_prompt_count, int) or isinstance(
        controller_followup_prompt_count, bool
    ):
        controller_followup_prompt_count = 0
    controller_stop_decision_count = controller_counters.get("stop_decision_count", 0)
    if not isinstance(controller_stop_decision_count, int) or isinstance(
        controller_stop_decision_count, bool
    ):
        controller_stop_decision_count = 0
    controller_max_rounds_budget = controller_counters.get("max_rounds_budget", 0)
    if not isinstance(controller_max_rounds_budget, int) or isinstance(
        controller_max_rounds_budget, bool
    ):
        controller_max_rounds_budget = 0

    def _controller_public_count(name: str) -> int:
        value = controller_counters.get(name, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    def _trajectory_public_count(name: str) -> int:
        value = trajectory_summary.get(name, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    native_goal_worker_trace_count = controller_counters.get(
        "native_goal_worker_trace_count", 0
    )
    if not isinstance(native_goal_worker_trace_count, int) or isinstance(
        native_goal_worker_trace_count, bool
    ):
        native_goal_worker_trace_count = 0
    native_goal_worker_trace_observed = native_goal_worker_trace_count > 0
    native_goal_worker_trace_status = _skillsbench_native_goal_worker_trace_status(
        controller_counters
    )
    native_goal_worker_failure_label = (
        _skillsbench_native_goal_worker_failure_label(
            controller_counters,
            trace_status=native_goal_worker_trace_status,
        )
    )
    native_goal_worker_bridge_task_success_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_success_count"
    )
    native_goal_worker_bridge_task_operation_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_operation_count"
    )
    native_goal_worker_countable_via_bridge_activity = bool(
        route == "codex-app-server-goal-baseline"
        and native_goal_worker_failure_label
        and reward_value is not None
        and native_goal_worker_bridge_task_success_count > 0
    )
    native_goal_worker_countable = bool(
        not native_goal_worker_failure_label
        or native_goal_worker_countable_via_bridge_activity
    )
    native_goal_worker_contract = {
        "schema_version": "skillsbench_native_goal_worker_contract_v0",
        "required": controller_counters.get("native_goal_worker_route") is True,
        "session_policy": (
            controller_counters.get("native_goal_worker_session_policy")
            or (
                "single_initial_goal_turn"
                if controller_counters.get("native_goal_worker_route") is True
                else ""
            )
        ),
        "max_rounds_budget_applies_to": (
            controller_counters.get("native_goal_worker_max_rounds_budget_applies_to")
            or (
                "benchflow_outer_controller_budget_not_native_goal_attempts"
                if controller_counters.get("native_goal_worker_route") is True
                else ""
            )
        ),
        "benchflow_max_rounds_budget": controller_counters.get("max_rounds_budget"),
        "initial_goal_turn_budget": (
            controller_counters.get("native_goal_worker_initial_goal_turn_budget")
            or (1 if controller_counters.get("native_goal_worker_route") is True else 0)
        ),
        "same_thread_followup_budget": controller_counters.get(
            "native_goal_worker_same_thread_followup_budget"
        ),
        "independent_attempt_budget": (
            controller_counters.get("native_goal_worker_independent_attempt_budget")
            or (1 if controller_counters.get("native_goal_worker_route") is True else 0)
        ),
        "fresh_goal_thread_per_independent_attempt": controller_counters.get(
            "native_goal_worker_fresh_goal_thread_per_independent_attempt"
        )
        is True,
        "official_reward_feedback_forwarded_to_worker": False,
        "verifier_output_forwarded_to_worker": False,
        "countable_baseline": native_goal_worker_countable,
        "countability_source": (
            "remote_command_file_bridge_task_facing_success"
            if native_goal_worker_countable_via_bridge_activity
            else "app_server_turn_trace"
            if not native_goal_worker_failure_label
            else "none"
        ),
        "trace_status": native_goal_worker_trace_status,
        "trace_count": native_goal_worker_trace_count,
        "ok_count": _controller_public_count("native_goal_worker_ok_count"),
        "goal_get_count": _controller_public_count("native_goal_worker_goal_get_count"),
        "turn_start_count": _controller_public_count(
            "native_goal_worker_turn_start_count"
        ),
        "assistant_message_present_count": _controller_public_count(
            "native_goal_worker_assistant_message_present_count"
        ),
        "assistant_context_only_count": _controller_public_count(
            "native_goal_worker_assistant_context_only_count"
        ),
        "context_only_recovery_attempted_count": _controller_public_count(
            "native_goal_worker_context_only_recovery_attempted_count"
        ),
        "context_only_recovery_succeeded_count": _controller_public_count(
            "native_goal_worker_context_only_recovery_succeeded_count"
        ),
        "context_only_followup_start_attempted_count": _controller_public_count(
            "native_goal_worker_context_only_followup_start_attempted_count"
        ),
        "context_only_followup_start_succeeded_count": _controller_public_count(
            "native_goal_worker_context_only_followup_start_succeeded_count"
        ),
        "transport_reconnect_attempted_count": _controller_public_count(
            "native_goal_worker_transport_reconnect_attempted_count"
        ),
        "transport_reconnect_succeeded_count": _controller_public_count(
            "native_goal_worker_transport_reconnect_succeeded_count"
        ),
        "goal_reactivation_attempted_count": _controller_public_count(
            "native_goal_worker_goal_reactivation_attempted_count"
        ),
        "goal_reactivation_succeeded_count": _controller_public_count(
            "native_goal_worker_goal_reactivation_succeeded_count"
        ),
        "post_context_assistant_chars_total": _controller_public_count(
            "native_goal_worker_post_context_assistant_chars_total"
        ),
        "reasoning_effort": str(
            controller_counters.get("native_goal_worker_reasoning_effort") or ""
        )[:40],
        "first_action_observed_count": _controller_public_count(
            "native_goal_worker_first_action_observed_count"
        ),
        "effective_action_observed_count": _controller_public_count(
            "native_goal_worker_effective_action_observed_count"
        ),
        "failure_trace_count": _controller_public_count(
            "native_goal_worker_failure_trace_count"
        ),
        "failure_category": str(
            controller_counters.get("native_goal_worker_failure_category") or ""
        )[:120],
        "bridge_task_facing_operation_count": native_goal_worker_bridge_task_operation_count,
        "bridge_task_facing_success_count": native_goal_worker_bridge_task_success_count,
        "first_blocker": str(
            controller_counters.get("native_goal_worker_first_blocker") or ""
        )[:120],
        "failure_label": native_goal_worker_failure_label,
    }
    app_server_goal_round_semantics: dict[str, Any] = {}
    if route == "codex-app-server-goal-baseline":
        same_thread_followup_budget = native_goal_worker_contract.get(
            "same_thread_followup_budget"
        )
        if not isinstance(same_thread_followup_budget, int) or isinstance(
            same_thread_followup_budget, bool
        ):
            same_thread_followup_budget = 0
        independent_attempt_budget = native_goal_worker_contract.get(
            "independent_attempt_budget"
        )
        if not isinstance(independent_attempt_budget, int) or isinstance(
            independent_attempt_budget, bool
        ):
            independent_attempt_budget = 1
        app_server_goal_round_semantics = {
            "schema_version": "skillsbench_app_server_goal_round_semantics_v0",
            "route": route,
            "session_policy": native_goal_worker_contract.get("session_policy")
            or "single_initial_goal_turn",
            "benchflow_max_rounds_budget": controller_max_rounds_budget,
            "max_rounds_budget_applies_to": native_goal_worker_contract.get(
                "max_rounds_budget_applies_to"
            )
            or "benchflow_outer_controller_budget_not_native_goal_attempts",
            "initial_goal_turn_budget": native_goal_worker_contract.get(
                "initial_goal_turn_budget"
            )
            or 1,
            "same_thread_followup_budget": max(0, same_thread_followup_budget),
            "independent_attempt_budget": max(1, independent_attempt_budget),
            "fresh_goal_thread_per_independent_attempt": native_goal_worker_contract.get(
                "fresh_goal_thread_per_independent_attempt"
            )
            is True,
            "official_reward_feedback_forwarded_to_worker": False,
            "verifier_output_forwarded_to_worker": False,
        }

    product_mode_lifecycle_required = _is_skillsbench_loopx_product_mode_treatment_route(
        route
    )
    workflow_execution_style = controller_counters.get(
        "remote_command_file_bridge_driver_lifecycle_execution_style"
    )
    driver_lifecycle_read_count = _controller_public_count(
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
    )
    driver_lifecycle_write_count = _controller_public_count(
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
    )
    driver_lifecycle_checkpoint_count = _controller_public_count(
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count"
    )
    driver_lifecycle_success_count = _controller_public_count(
        "remote_command_file_bridge_driver_lifecycle_success_count"
    )
    driver_lifecycle_failure_count = _controller_public_count(
        "remote_command_file_bridge_driver_lifecycle_failure_count"
    )
    driver_lifecycle_loopx_cli_call_count = _controller_public_count(
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count"
    )
    orchestrated_driver_lifecycle_satisfied = bool(
        workflow_execution_style == BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE
        and driver_lifecycle_checkpoint_count > 0
        and driver_lifecycle_success_count > 0
        and driver_lifecycle_failure_count == 0
        and driver_lifecycle_loopx_cli_call_count > 0
        and driver_lifecycle_read_count > 0
        and driver_lifecycle_write_count > 0
    )
    remote_agent_operation_trace_required_raw = (
        controller_counters.get(
            "remote_command_file_bridge_agent_operation_trace_required"
        )
        is True
    )
    remote_agent_operation_trace_satisfied_raw_field = (
        controller_counters.get(
            "remote_command_file_bridge_agent_operation_trace_satisfied"
        )
        is True
    )
    remote_agent_operation_trace_status = str(
        controller_counters.get(
            "remote_command_file_bridge_agent_operation_trace_status", ""
        )
    )
    remote_agent_task_facing_operation_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_operation_count"
    )
    remote_agent_task_facing_success_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_success_count"
    )
    remote_agent_task_facing_failure_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_failure_count"
    )
    remote_agent_success_count = _controller_public_count(
        "remote_command_file_bridge_agent_success_count"
    )
    remote_agent_failure_count = _controller_public_count(
        "remote_command_file_bridge_agent_failure_count"
    )
    legacy_satisfied_without_task_facing_success_counters = bool(
        remote_agent_operation_trace_satisfied_raw_field
        and remote_agent_task_facing_success_count == 0
        and remote_agent_task_facing_failure_count == 0
        and remote_agent_success_count > 0
        and remote_agent_failure_count == 0
        and remote_agent_task_facing_operation_count > 0
        and remote_agent_operation_trace_status == "agent_operation_trace_recorded"
    )
    remote_agent_operation_trace_satisfied_raw = bool(
        remote_agent_operation_trace_satisfied_raw_field
        and (
            remote_agent_task_facing_success_count > 0
            or legacy_satisfied_without_task_facing_success_counters
        )
    )
    orchestrated_driver_counts_as_product_mode = bool(
        orchestrated_driver_lifecycle_satisfied
        and (
            not remote_agent_operation_trace_required_raw
            or (
                controller_counters.get(
                    "remote_command_file_bridge_agent_command_instrumented"
                )
                is True
                and remote_agent_operation_trace_satisfied_raw
            )
        )
    )
    remote_agent_operation_trace_required = bool(
        remote_agent_operation_trace_required_raw
        and not orchestrated_driver_counts_as_product_mode
    )
    remote_agent_operation_trace_satisfied = remote_agent_operation_trace_satisfied_raw
    remote_agent_operation_trace_missing = bool(
        remote_agent_operation_trace_required
        and not remote_agent_operation_trace_satisfied
    )
    remote_agent_operation_trace_no_requests = bool(
        remote_agent_operation_trace_missing
        and remote_agent_operation_trace_status
        == "agent_operation_trace_present_no_requests"
    )
    remote_agent_operation_trace_recorded_no_success = bool(
        remote_agent_operation_trace_missing
        and remote_agent_operation_trace_status
        == "agent_operation_trace_recorded_no_success"
    )
    remote_agent_operation_failure_category = "bridge_operation_failed"
    failure_category_counts = controller_counters.get(
        "remote_command_file_bridge_agent_failure_category_counts"
    )
    if isinstance(failure_category_counts, dict):
        for category_key, category_count in sorted(failure_category_counts.items()):
            if (
                isinstance(category_key, str)
                and category_key
                and isinstance(category_count, int)
                and not isinstance(category_count, bool)
                and category_count > 0
            ):
                remote_agent_operation_failure_category = category_key[:80]
                break
    remote_agent_operation_failure_label = (
        "skillsbench_remote_bridge_agent_operation_failed_"
        f"{remote_agent_operation_failure_category}"
    )
    agent_bridge_lifecycle_read_count = _controller_public_count(
        "remote_command_file_bridge_agent_loopx_state_read_count"
    )
    agent_bridge_lifecycle_write_count = _controller_public_count(
        "remote_command_file_bridge_agent_loopx_state_write_count"
    )
    agent_bridge_todo_closeout_count = _controller_public_count(
        "remote_command_file_bridge_agent_todo_closeout_count"
    )
    agent_bridge_refresh_state_count = _controller_public_count(
        "remote_command_file_bridge_agent_refresh_state_count"
    )
    agent_bridge_quota_spend_slot_count = _controller_public_count(
        "remote_command_file_bridge_agent_quota_spend_slot_count"
    )
    agent_bridge_closeout_satisfied = bool(
        remote_agent_operation_trace_satisfied
        and agent_bridge_todo_closeout_count > 0
        and agent_bridge_refresh_state_count > 0
        and agent_bridge_quota_spend_slot_count > 0
    )
    lifecycle_read_sources = [
        _controller_public_count("loopx_state_reads"),
        _controller_public_count("loopx_case_state_reads"),
        agent_bridge_lifecycle_read_count,
        _trajectory_public_count("loopx_cli_state_read_count"),
        _trajectory_public_count("loopx_case_state_read_count"),
    ]
    lifecycle_write_sources = [
        _controller_public_count("loopx_state_writes"),
        _controller_public_count("loopx_case_state_writes"),
        agent_bridge_lifecycle_write_count,
        _trajectory_public_count("loopx_cli_state_write_count"),
        _trajectory_public_count("loopx_case_state_write_count"),
    ]
    if not remote_agent_operation_trace_required:
        lifecycle_read_sources.append(driver_lifecycle_read_count)
        lifecycle_write_sources.append(driver_lifecycle_write_count)
    product_mode_lifecycle_read_count = max(lifecycle_read_sources)
    product_mode_lifecycle_write_count = max(lifecycle_write_sources)
    product_mode_lifecycle_checkpoint_required = bool(
        controller_counters.get("product_mode_lifecycle_checkpoint_required")
        or _controller_public_count(
            "remote_command_file_bridge_driver_lifecycle_trace_count"
        )
        > 0
    )
    product_mode_lifecycle_checkpoint_count = max(
        _controller_public_count("product_mode_lifecycle_checkpoint_count"),
        _controller_public_count(
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count"
        ),
    )
    product_mode_lifecycle_attempt_observed = bool(
        product_mode_lifecycle_checkpoint_required
        or product_mode_lifecycle_checkpoint_count > 0
        or controller_followup_prompt_count > 0
        or controller_stop_decision_count > 0
        or controller_max_rounds_budget > 1
    )
    product_mode_lifecycle_closeout_required = bool(
        remote_agent_operation_trace_required
        or agent_bridge_lifecycle_read_count > 0
        or agent_bridge_lifecycle_write_count > 0
        or _controller_public_count(
            "remote_command_file_bridge_driver_lifecycle_trace_count"
        )
        > 0
    )
    product_mode_lifecycle_closeout_satisfied = bool(
        not product_mode_lifecycle_closeout_required
        or orchestrated_driver_counts_as_product_mode
        or agent_bridge_closeout_satisfied
    )
    product_mode_lifecycle_satisfied = bool(
        not product_mode_lifecycle_required
        or (
            not remote_agent_operation_trace_missing
            and
            product_mode_lifecycle_read_count > 0
            and product_mode_lifecycle_write_count > 0
            and product_mode_lifecycle_closeout_satisfied
        )
    )
    product_mode_lifecycle_missing = bool(
        product_mode_lifecycle_required
        and controller_trace_present
        and product_mode_lifecycle_attempt_observed
        and not product_mode_lifecycle_satisfied
    )
    product_mode_lifecycle_contract = {
        "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
        "required": product_mode_lifecycle_required,
        "satisfied": product_mode_lifecycle_satisfied,
        "countable_treatment": not product_mode_lifecycle_missing,
        "state_read_count": product_mode_lifecycle_read_count,
        "state_write_count": product_mode_lifecycle_write_count,
        "checkpoint_required": product_mode_lifecycle_checkpoint_required,
        "checkpoint_count": product_mode_lifecycle_checkpoint_count,
        "closeout_required": product_mode_lifecycle_closeout_required,
        "closeout_satisfied": product_mode_lifecycle_closeout_satisfied,
        "agent_operation_trace_required": remote_agent_operation_trace_required,
        "agent_operation_trace_satisfied": remote_agent_operation_trace_satisfied,
        "agent_operation_trace_status": remote_agent_operation_trace_status,
        "agent_operation_trace_missing": remote_agent_operation_trace_missing,
        "orchestrated_driver_lifecycle_satisfied": (
            orchestrated_driver_lifecycle_satisfied
        ),
        "orchestrated_driver_counts_as_product_mode": (
            orchestrated_driver_counts_as_product_mode
        ),
        "agent_bridge_state_read_count": agent_bridge_lifecycle_read_count,
        "agent_bridge_state_write_count": agent_bridge_lifecycle_write_count,
        "agent_bridge_todo_closeout_count": agent_bridge_todo_closeout_count,
        "agent_bridge_refresh_state_count": agent_bridge_refresh_state_count,
        "agent_bridge_quota_spend_slot_count": agent_bridge_quota_spend_slot_count,
        "driver_lifecycle_state_read_count": driver_lifecycle_read_count,
        "driver_lifecycle_state_write_count": driver_lifecycle_write_count,
        "checkpoint_round": controller_counters.get(
            "product_mode_lifecycle_checkpoint_round", 0
        ),
        "missing_reason": (
            "remote_command_file_bridge_agent_no_requests"
            if remote_agent_operation_trace_no_requests
            else (
                "remote_command_file_bridge_agent_operation_failed_"
                f"{remote_agent_operation_failure_category}"
            )
            if remote_agent_operation_trace_recorded_no_success
            else "remote_command_file_bridge_agent_operation_trace_missing"
            if remote_agent_operation_trace_missing
            else "missing_case_local_loopx_closeout"
            if (
                product_mode_lifecycle_closeout_required
                and not product_mode_lifecycle_closeout_satisfied
                and product_mode_lifecycle_read_count > 0
                and product_mode_lifecycle_write_count > 0
            )
            else controller_counters.get(
                "product_mode_lifecycle_checkpoint_missing_reason", ""
            )
        )
        if product_mode_lifecycle_missing
        else "",
    }
    if isinstance(workflow_execution_style, str) and workflow_execution_style:
        product_mode_lifecycle_contract["execution_style"] = workflow_execution_style
    if product_mode_lifecycle_required and product_mode_lifecycle_satisfied:
        controller_counters["product_mode_lifecycle_checkpoint_missing_reason"] = ""
        controller_counters["product_mode_no_tool_call_lifecycle_abort"] = False
        controller_counters["product_mode_no_tool_call_lifecycle_abort_count"] = 0
        controller_counters["product_mode_no_tool_call_lifecycle_abort_round"] = 0
        controller_counters["product_mode_no_lifecycle_request_abort"] = False
        controller_counters["product_mode_no_lifecycle_request_abort_count"] = 0
        controller_counters["product_mode_no_lifecycle_request_abort_round"] = 0
    agent_bridge_final_closeout_satisfied = bool(
        agent_bridge_todo_closeout_count > 0
        and agent_bridge_refresh_state_count > 0
        and agent_bridge_quota_spend_slot_count > 0
    )
    agent_bridge_task_facing_operation_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_operation_count"
    )
    agent_bridge_success_count = _controller_public_count(
        "remote_command_file_bridge_agent_success_count"
    )
    agent_bridge_failure_count = _controller_public_count(
        "remote_command_file_bridge_agent_failure_count"
    )
    agent_bridge_task_facing_success_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_success_count"
    )
    agent_bridge_task_facing_failure_count = _controller_public_count(
        "remote_command_file_bridge_agent_task_facing_failure_count"
    )
    legacy_recorded_without_success_counters = bool(
        agent_bridge_success_count == 0
        and agent_bridge_failure_count == 0
        and agent_bridge_task_facing_success_count == 0
        and agent_bridge_task_facing_failure_count == 0
        and remote_agent_operation_trace_status == "agent_operation_trace_recorded"
        and agent_bridge_task_facing_operation_count > 0
    )
    agent_bridge_activity_observed = bool(
        agent_bridge_task_facing_success_count > 0
        or remote_agent_operation_trace_satisfied
        or legacy_recorded_without_success_counters
    )
    declared_done_round_count = _controller_public_count("declared_done_round")
    trajectory_tool_calls = _trajectory_public_count("tool_call_count")
    no_solver_tool_calls = bool(tool_calls == 0 and trajectory_tool_calls == 0)
    product_mode_solver_activity_gap_derived = bool(
        product_mode_lifecycle_required
        and product_mode_lifecycle_satisfied
        and controller_trace_present
        and controller_counters.get("agent_declared_done") is True
        and declared_done_round_count > 0
        and reward_value is None
        and no_solver_tool_calls
        and agent_bridge_activity_observed
        and not agent_bridge_final_closeout_satisfied
    )
    if product_mode_solver_activity_gap_derived:
        controller_counters["product_mode_solver_activity_required"] = True
        controller_counters["product_mode_solver_activity_gap"] = True
        controller_counters["product_mode_solver_activity_gap_count"] = max(
            1,
            _controller_public_count("product_mode_solver_activity_gap_count"),
        )
        controller_counters["product_mode_solver_activity_gap_round"] = max(
            declared_done_round_count,
            _controller_public_count("product_mode_solver_activity_gap_round"),
        )
        controller_counters.setdefault(
            "product_mode_solver_activity_missing_reason",
            "missing_task_facing_activity_or_agent_closeout_before_declared_done",
        )
    product_mode_solver_activity_gap_observed = bool(
        controller_counters.get("product_mode_solver_activity_gap") is True
    )
    product_mode_solver_activity_gap_superseded = bool(
        product_mode_solver_activity_gap_observed
        and agent_bridge_task_facing_operation_count > 0
        and agent_bridge_final_closeout_satisfied
    )
    if product_mode_solver_activity_gap_superseded:
        controller_counters[
            "product_mode_solver_activity_gap_superseded_by_final_activity"
        ] = True
    product_mode_solver_activity_gap_corroborated = bool(
        product_mode_solver_activity_gap_observed
        and not product_mode_solver_activity_gap_superseded
        and (
            controller_counters.get("product_mode_solver_activity_missing_reason")
            == "missing_task_facing_activity_or_agent_closeout_before_declared_done"
            or _controller_public_count("product_mode_solver_activity_gap_count") > 0
            or (
                "remote_command_file_bridge_agent_task_facing_operation_count"
                in controller_counters
                and _controller_public_count(
                    "remote_command_file_bridge_agent_task_facing_operation_count"
                )
                == 0
            )
            or (
                "remote_command_file_bridge_agent_todo_closeout_count"
                in controller_counters
                and _controller_public_count(
                    "remote_command_file_bridge_agent_todo_closeout_count"
                )
                == 0
            )
        )
    )
    if (
        product_mode_solver_activity_gap_corroborated
        and not official_passed
    ):
        label = "skillsbench_product_mode_solver_activity_gap"
        exception_type = label
        if score_failure_attribution in {
            "",
            "none",
            "skillsbench_runner_error",
            "verifier_infrastructure_failure",
            "official_verifier_solution_failure",
            "official_score_zero_case_failure",
        }:
            score_failure_attribution = label
            runner_score_failure_attribution = label
            failure_labels = [
                item
                for item in failure_labels
                if item
                not in {
                    "official_verifier_solution_failure",
                    "official_score_zero_case_failure",
                    "verifier_infrastructure_failure",
                }
            ]
        for item in (
            label,
            "skillsbench_agent_behavior_gap",
            "skillsbench_reward_artifact_missing" if reward_value is None else "",
            "skillsbench_verifier_error_subtype_unavailable_public"
            if verifier_error_text
            else "",
        ):
            if item and item not in failure_labels:
                failure_labels.append(item)
    product_mode_declared_done_below_passing_reward = bool(
        controller_counters.get("product_mode_declared_done_below_passing_reward")
        is True
    )
    if product_mode_declared_done_below_passing_reward and not official_passed:
        for item in (
            "skillsbench_product_mode_declared_done_below_passing_reward",
            "skillsbench_agent_premature_done_signal",
        ):
            if item not in failure_labels:
                failure_labels.append(item)
    product_mode_no_open_todo_below_passing_reward_stop = bool(
        controller_counters.get(
            "product_mode_no_open_todo_below_passing_reward_stop"
        )
        is True
    )
    if product_mode_no_open_todo_below_passing_reward_stop and not official_passed:
        for item in (
            "skillsbench_product_mode_no_open_todo_below_passing_reward_stop",
            "skillsbench_solver_exhausted_no_open_todos",
        ):
            if item not in failure_labels:
                failure_labels.append(item)
    user_loop_final_verify_recovery_triggered = bool(
        controller_counters.get("benchflow_user_loop_final_verify_recovery_triggered")
    )
    controller_budget_cutoff_before_followup = (
        bool(error_text)
        and reward_value is None
        and controller_trace_present
        and not user_loop_final_verify_recovery_triggered
        and controller_max_rounds_budget > 1
        and controller_initial_prompt_count > 0
        and controller_followup_prompt_count == 0
        and controller_stop_decision_count == 0
        and (partial_trajectory or tool_calls > 0)
    )
    controller_budget_cutoff_reason = (
        "result_error_after_agent_round_no_reward_artifact"
        if controller_budget_cutoff_before_followup
        else "none"
    )
    if controller_budget_cutoff_before_followup:
        for item in (
            "skillsbench_controller_budget_not_exercised",
            "skillsbench_result_error_cut_off_followup_loop",
        ):
            if item and item not in failure_labels:
                failure_labels.append(item)
    if (
        error_text
        and reward_value is None
        and re.search(r"timeout|timed out|deadline", error_text, re.I)
        and controller_trace_present
        and user_loop_final_verify_recovery_triggered
    ):
        label = "skillsbench_final_verify_timeout_after_user_loop_recovery_no_reward_artifact"
        exception_type = label
        score_failure_attribution = label
        runner_score_failure_attribution = label
        failure_labels = [
            item
            for item in failure_labels
            if item
            not in {
                "skillsbench_runner_error",
                "skillsbench_controller_budget_not_exercised",
                "skillsbench_result_error_cut_off_followup_loop",
            }
        ]
        for item in (
            label,
            "skillsbench_final_verify_attempted_after_user_loop_recovery",
            "skillsbench_reward_artifact_missing",
        ):
            if item not in failure_labels:
                failure_labels.append(item)
    elif (
        error_text
        and reward_value is None
        and re.search(r"timeout|timed out|deadline", error_text, re.I)
        and controller_trace_present
        and (partial_trajectory or tool_calls > 0)
    ):
        label = "skillsbench_result_timeout_after_agent_round_no_reward_artifact"
        exception_type = label
        score_failure_attribution = label
        runner_score_failure_attribution = label
        failure_labels = [
            item for item in failure_labels if item != "skillsbench_runner_error"
        ]
        for item in (
            label,
            "skillsbench_result_error_after_agent_round",
            "skillsbench_reward_artifact_missing",
        ):
            if item not in failure_labels:
                failure_labels.append(item)
    host_local_acp_codex_exec_failure_present = bool(
        controller_counters.get("host_local_acp_codex_exec_failure_trace_present")
        is True
    )
    host_local_acp_codex_exec_failure_category = str(
        controller_counters.get("host_local_acp_codex_exec_failure_category") or ""
    )
    host_local_acp_idle_timeout_after_countable_closeout = bool(
        host_local_acp_codex_exec_failure_present
        and host_local_acp_codex_exec_failure_category == "codex_exec_bridge_idle_timeout"
        and reward_value is not None
        and product_mode_lifecycle_satisfied
        and agent_bridge_task_facing_operation_count > 0
        and agent_bridge_final_closeout_satisfied
    )
    host_local_acp_idle_no_task_output_progress_stop = bool(
        controller_counters.get(
            "product_mode_host_local_idle_no_task_output_progress_stop"
        )
        is True
    )
    host_local_acp_task_output_quiet_after_bridge_attempt = bool(
        host_local_acp_codex_exec_failure_present
        and host_local_acp_codex_exec_failure_category
        == "codex_exec_task_output_quiet_timeout"
        and reward_value is not None
        and agent_bridge_task_facing_success_count > 0
    )
    if (
        host_local_acp_codex_exec_failure_present
        and not official_passed
        and not host_local_acp_idle_timeout_after_countable_closeout
        and not host_local_acp_task_output_quiet_after_bridge_attempt
    ):
        if host_local_acp_idle_no_task_output_progress_stop:
            host_failure_label = (
                "skillsbench_host_local_acp_idle_no_task_output_progress"
            )
        else:
            host_failure_label = "skillsbench_host_local_acp_codex_exec_failed"
        if (
            host_local_acp_codex_exec_failure_category
            and not host_local_acp_idle_no_task_output_progress_stop
        ):
            host_failure_label = (
                f"{host_failure_label}_{host_local_acp_codex_exec_failure_category}"
            )
        exception_type = host_failure_label
        score_failure_attribution = host_failure_label
        runner_score_failure_attribution = host_failure_label
        contract_official_score_comparable_to_native_codex = False
        contract_official_score_comparable_to_loopx_treatment = False
        failure_labels = [
            item
            for item in failure_labels
            if item
            not in {
                "skillsbench_runner_error",
                "skillsbench_codex_acp_jsonrpc_internal_error",
                "skillsbench_codex_acp_transport_error",
                "skillsbench_controller_budget_not_exercised",
                "skillsbench_result_error_cut_off_followup_loop",
                "skillsbench_result_timeout_after_agent_round_no_reward_artifact",
                "skillsbench_result_error_after_agent_round",
                "skillsbench_reward_artifact_missing",
                "verifier_infrastructure_failure",
                "official_score_zero_case_failure",
                "official_verifier_solution_failure",
            }
        ]
        controller_budget_cutoff_before_followup = False
        controller_budget_cutoff_reason = "none"
        host_failure_extra_labels = [
            host_failure_label,
            "skillsbench_product_mode_transport_failure"
            if _is_skillsbench_loopx_product_mode_treatment_route(route)
            else "",
        ]
        if not host_local_acp_idle_no_task_output_progress_stop:
            host_failure_extra_labels.extend(
                [
                    "skillsbench_host_local_acp_codex_exec_failed",
                    "skillsbench_runner_setup_error",
                ]
            )
        for item in host_failure_extra_labels:
            if item and item not in failure_labels:
                failure_labels.append(item)
    elif host_local_acp_task_output_quiet_after_bridge_attempt:
        warning_label = (
            "skillsbench_host_local_acp_task_output_quiet_after_bridge_attempt"
        )
        failure_labels = [
            item
            for item in failure_labels
            if item
            not in {
                "skillsbench_runner_error",
                "skillsbench_host_local_acp_task_output_quiet_timeout",
                "verifier_infrastructure_failure",
                "official_verifier_solution_failure",
            }
        ]
        if reward_value == 0 and score_failure_attribution in {
            "",
            "none",
            "skillsbench_runner_error",
            "skillsbench_host_local_acp_task_output_quiet_timeout",
        }:
            exception_type = "none"
            score_failure_attribution = "official_score_zero_case_failure"
            runner_score_failure_attribution = "none"
            if "official_score_zero_case_failure" not in failure_labels:
                failure_labels.append("official_score_zero_case_failure")
        if warning_label not in warning_labels:
            warning_labels.append(warning_label)
    elif host_local_acp_idle_timeout_after_countable_closeout:
        warning_label = (
            "skillsbench_host_local_acp_idle_timeout_after_countable_closeout"
        )
        failure_labels = [
            item for item in failure_labels if item != "skillsbench_runner_error"
        ]
        if reward_value == 0 and score_failure_attribution in {
            "",
            "none",
            "skillsbench_runner_error",
            "official_score_zero_case_failure",
        }:
            exception_type = warning_label
            score_failure_attribution = "official_score_zero_case_failure"
            runner_score_failure_attribution = warning_label
            if "official_score_zero_case_failure" not in failure_labels:
                failure_labels.append("official_score_zero_case_failure")
        for item in (
            warning_label,
            "skillsbench_host_local_acp_codex_exec_failed",
        ):
            if item not in warning_labels:
                warning_labels.append(item)
    setup_failure_observed = _skillsbench_attempt_setup_blocked(failure_labels)
    native_goal_worker_uncountable = bool(
        native_goal_worker_failure_label
        and not official_passed
        and not native_goal_worker_countable_via_bridge_activity
        and not setup_failure_observed
    )
    if native_goal_worker_uncountable:
        exception_type = native_goal_worker_failure_label
        score_failure_attribution = native_goal_worker_failure_label
        runner_score_failure_attribution = native_goal_worker_failure_label
        contract_official_score_comparable_to_native_codex = False
        contract_official_score_comparable_to_loopx_treatment = False
        failure_labels = [
            item
            for item in failure_labels
            if item
            not in {
                "skillsbench_runner_error",
                "skillsbench_codex_acp_jsonrpc_internal_error",
                "skillsbench_codex_acp_transport_error",
                "skillsbench_controller_budget_not_exercised",
                "skillsbench_result_error_cut_off_followup_loop",
                "skillsbench_result_timeout_after_agent_round_no_reward_artifact",
                "skillsbench_result_error_after_agent_round",
                "skillsbench_reward_artifact_missing",
                "verifier_infrastructure_failure",
                "official_score_zero_case_failure",
                "official_verifier_solution_failure",
            }
        ]
        for item in (
            native_goal_worker_failure_label,
            "skillsbench_native_goal_worker_uncountable_baseline",
            "skillsbench_app_server_goal_worker_compact_proof_missing",
            "skillsbench_runner_setup_error",
        ):
            if item and item not in failure_labels:
                failure_labels.append(item)
    if trajectory_summary:
        evidence_files.append("loopx:acp_trajectory_summary")
    runner_failure: dict[str, Any] | None = None
    runner_failure_fingerprint: dict[str, Any] | None = None
    if (
        error_text
        and not host_local_acp_task_output_quiet_after_bridge_attempt
    ) or native_goal_worker_uncountable:
        runner_failure = {
            "schema_version": "skillsbench_runner_failure_v0",
            "exception_type": exception_type,
            "failure_class": runner_score_failure_attribution,
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }
        if controller_budget_cutoff_before_followup:
            runner_failure["controller_cutoff"] = {
                "schema_version": "skillsbench_controller_cutoff_v0",
                "cutoff_before_followup": True,
                "reason": controller_budget_cutoff_reason,
                "max_rounds_budget": controller_max_rounds_budget,
                "initial_prompt_count": controller_initial_prompt_count,
                "followup_prompt_count": controller_followup_prompt_count,
                "stop_decision_count": controller_stop_decision_count,
            }
        if user_loop_final_verify_recovery_triggered:
            runner_failure["user_loop_recovery"] = {
                "schema_version": "skillsbench_user_loop_recovery_v0",
                "preserved_final_verify": bool(
                    controller_counters.get(
                        "benchflow_user_loop_recovery_preserved_final_verify"
                    )
                ),
                "stage": controller_counters.get(
                    "benchflow_user_loop_recovery_stage",
                    "",
                ),
                "exception_type": controller_counters.get(
                    "benchflow_user_loop_recovery_exception_type",
                    "",
                ),
                "round": controller_counters.get(
                    "benchflow_user_loop_recovery_round",
                    0,
                ),
                "delta_events": controller_counters.get(
                    "benchflow_user_loop_recovery_delta_events",
                    0,
                ),
                "delta_tool_calls": controller_counters.get(
                    "benchflow_user_loop_recovery_delta_tool_calls",
                    0,
                ),
                "raw_error_recorded": bool(
                    controller_counters.get(
                        "benchflow_user_loop_recovery_raw_error_recorded"
                    )
                ),
            }
        if native_goal_worker_uncountable:
            runner_failure["native_goal_worker"] = {
                "schema_version": "skillsbench_native_goal_worker_failure_v0",
                "trace_status": native_goal_worker_trace_status,
                "failure_label": native_goal_worker_failure_label,
                "failure_category": native_goal_worker_contract.get(
                    "failure_category", ""
                ),
                "first_blocker": native_goal_worker_contract.get("first_blocker", ""),
                "trace_count": native_goal_worker_trace_count,
                "raw_transcript_recorded": False,
                "raw_assistant_message_recorded": False,
            }
        if error_text:
            runner_failure_fingerprint = skillsbench_runner_error_fingerprint(
                error_text
            )
    round_reward_records = controller_counters.get("round_rewards")
    if not isinstance(round_reward_records, list):
        round_reward_records = []
    first_success_round = controller_counters.get("first_success_round")
    first_success_round_value = (
        first_success_round
        if isinstance(first_success_round, int)
        and not isinstance(first_success_round, bool)
        and first_success_round > 0
        else None
    )
    round_reward_trace: dict[str, Any] | None = None
    if controller_trace_present:
        round_stats = _round_reward_trace_stats(round_reward_records)
        round_reward_trace = {
            "schema_version": "benchmark_round_reward_trace_v0",
            "source": "loopx_controller_trace",
            "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
            "records": round_reward_records,
            "first_success_round": first_success_round_value,
            "success_observed": controller_counters.get(
                "official_success_observed",
                False,
            ),
            "max_rounds_budget": controller_counters.get("max_rounds_budget", 0),
            "official_feedback_returned_to_agent": contract_reward_feedback_forwarded,
            "official_feedback_blinded": contract_official_feedback_blinded,
            "reward_feedback_forwarded": contract_reward_feedback_forwarded,
            "agent_declared_done": controller_counters.get("agent_declared_done")
            is True,
            "declared_done_requires_no_remaining_goals": controller_counters.get(
                "declared_done_requires_no_remaining_goals"
            )
            is True,
            "agent_declared_no_remaining_goals": controller_counters.get(
                "agent_declared_no_remaining_goals"
            )
            is True,
            "product_mode_no_open_todo_below_passing_reward_stop": (
                controller_counters.get(
                    "product_mode_no_open_todo_below_passing_reward_stop"
                )
                is True
            ),
        }
        for source_key in (
            "product_mode_no_open_todo_below_passing_reward_streak",
            "product_mode_no_open_todo_below_passing_reward_streak_threshold",
            "product_mode_no_open_todo_below_passing_reward_round",
            "product_mode_no_open_todo_below_passing_reward_stop_round",
            "product_mode_no_open_todo_below_passing_reward_open_todo_count_public",
        ):
            value = controller_counters.get(source_key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                round_reward_trace[source_key] = value
        score_status = controller_counters.get(
            "product_mode_no_open_todo_below_passing_reward_score_status"
        )
        if isinstance(score_status, str) and score_status:
            round_reward_trace[
                "product_mode_no_open_todo_below_passing_reward_score_status"
            ] = score_status
        declared_done_round = controller_counters.get("declared_done_round")
        if (
            isinstance(declared_done_round, int)
            and not isinstance(declared_done_round, bool)
            and declared_done_round > 0
        ):
            round_reward_trace["declared_done_round"] = declared_done_round
        declared_done_score = controller_counters.get("declared_done_score")
        if (
            isinstance(declared_done_score, (int, float))
            and not isinstance(declared_done_score, bool)
        ):
            round_reward_trace["declared_done_score"] = float(declared_done_score)
        no_open_todo_score = controller_counters.get(
            "product_mode_no_open_todo_below_passing_reward_score"
        )
        if (
            isinstance(no_open_todo_score, (int, float))
            and not isinstance(no_open_todo_score, bool)
        ):
            round_reward_trace[
                "product_mode_no_open_todo_below_passing_reward_score"
            ] = float(no_open_todo_score)
        round_reward_trace.update(round_stats)

    post_success_score = {}
    if (
        reward_value is None
        and score_failure_attribution == "skillsbench_codex_acp_jsonrpc_internal_error"
        and controller_trace_present
    ):
        post_success_score = _post_success_controller_trace_score(round_reward_trace)
        if post_success_score:
            reward_value = post_success_score["value"]
            official_passed = post_success_score["passed"]
            score_failure_attribution = "none"
            counter_trust_level = (
                "loopx_controller_trace_post_success_official_reward_recovery"
            )
            if round_reward_trace is not None:
                round_reward_trace["official_score_policy"] = post_success_score["policy"]
                round_reward_trace["official_score_recovered_from_controller_trace"] = True
                if post_success_score.get("round") is not None:
                    round_reward_trace["official_score_recovered_round"] = post_success_score[
                        "round"
                    ]

    official_score_kind = "skillsbench_verifier_reward"
    official_score_source = "official_skillsbench_benchflow_result_json"
    official_score_status = "completed" if reward_value is not None else "missing"
    validation_scope = "official_benchflow_result_json_only"
    if reward_artifact_source:
        official_score_kind = "skillsbench_verifier_reward_recovered_from_reward_txt"
        official_score_source = reward_artifact_source
        validation_scope = "official_benchflow_result_json_plus_rollout_reward_artifact"
        if not controller_trace_present:
            counter_trust_level = "official_benchflow_result_plus_rollout_reward_artifact"
    if post_success_score:
        official_score_kind = (
            "skillsbench_verifier_reward_recovered_from_controller_trace"
        )
        official_score_source = (
            "loopx_controller_trace_best_round_reward_post_success_acp_closeout"
        )
        validation_scope = (
            "official_benchflow_result_json_plus_loopx_controller_trace"
        )
    if product_mode_lifecycle_missing:
        label = (
            remote_agent_operation_failure_label
            if remote_agent_operation_trace_recorded_no_success
            else "skillsbench_product_mode_lifecycle_missing"
        )
        contract_official_score_comparable_to_native_codex = False
        contract_official_score_comparable_to_loopx_treatment = False
        product_mode_lifecycle_contract["countable_treatment"] = False
        preserve_primary_attribution = score_failure_attribution in {
            "skillsbench_codex_acp_provider_zero_activity",
        }
        if not official_passed and not preserve_primary_attribution:
            exception_type = label
            score_failure_attribution = label
            runner_score_failure_attribution = label
            failure_labels = [
                item
                for item in failure_labels
                if item
                not in {
                    "skillsbench_runner_error",
                    "verifier_infrastructure_failure",
                    "official_score_zero_case_failure",
                }
            ]
            if runner_failure is not None:
                runner_failure["exception_type"] = label
                runner_failure["failure_class"] = label
        for item in (
            label,
            "skillsbench_product_mode_lifecycle_missing"
            if label != "skillsbench_product_mode_lifecycle_missing"
            else "",
            "skillsbench_runner_setup_error"
            if remote_agent_operation_trace_recorded_no_success
            else "",
            "skillsbench_product_mode_uncountable_treatment",
            "skillsbench_case_local_loopx_state_not_observed",
            "skillsbench_remote_bridge_agent_no_requests"
            if remote_agent_operation_trace_no_requests
            else remote_agent_operation_failure_label
            if remote_agent_operation_trace_recorded_no_success
            else "skillsbench_remote_bridge_agent_operation_trace_missing"
            if remote_agent_operation_trace_missing
            else "",
        ):
            if item not in failure_labels:
                failure_labels.append(item)
        if (
            reward_value is None
            and "skillsbench_reward_artifact_missing" not in failure_labels
        ):
            failure_labels.append("skillsbench_reward_artifact_missing")
    elif (
        official_passed
        and score_failure_attribution == "skillsbench_runner_error"
        and failure_labels == ["skillsbench_runner_error"]
    ):
        warning_labels.append("skillsbench_runner_error_after_official_pass_ignored")
        exception_type = "none"
        score_failure_attribution = "none"
        runner_score_failure_attribution = "none"
        failure_labels = []
        runner_failure = None

    setup_blocked = _skillsbench_attempt_setup_blocked(failure_labels)
    attempt_accounting = build_benchmark_attempt_accounting(
        lifecycle=_skillsbench_attempt_lifecycle(
            setup_blocked=setup_blocked,
            reward_value=reward_value,
            verifier_error_text=verifier_error_text,
            tool_calls=tool_calls,
            native_goal_worker_trace_observed=native_goal_worker_trace_observed,
            controller_trace_present=controller_trace_present,
        ),
        failure_label=score_failure_attribution,
        failure_class=_skillsbench_attempt_failure_class(
            failure_labels=failure_labels,
            reward_value=reward_value,
            verifier_error_text=verifier_error_text,
            score_failure_attribution=score_failure_attribution,
        ),
        official_score_attempted=reward_value is not None and not setup_blocked,
    )

    benchmark_run: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "official_skillsbench_benchflow_result",
        "benchmark_id": dataset,
        "case_id": task_id,
        "case_ids": [task_id],
        "job_name": job_name,
        "mode": contract["mode"],
        "route": route,
        "attempt_accounting": attempt_accounting,
        "agent": {
            "name": observed_agent,
            "model": observed_model,
            "kwargs_keys": agent_kwargs_keys,
        },
        "model_control": {
            "schema_version": BENCHMARK_MODEL_CONTROL_SCHEMA_VERSION,
            "requested_model": requested_model,
            "reported_model": observed_model,
            "control_method": "benchflow_acp_session_set_model",
            "control_status": model_control_status,
            "actual_model_verified": actual_model_verified,
            "actual_model_source": actual_model_source,
            "warning_labels": warning_labels,
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 1 if real_run_completed else 0,
            "n_errored_trials": 0 if real_run_completed else 1,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
        },
        "interaction_counters": {
            "schema_version": "skillsbench_interaction_counters_v0",
            "loopx_automation_loop": contract_loopx_automation_loop,
            "inner_codex_goal_mode": contract_inner_codex_goal_mode,
            "native_goal_mode_requested": contract_native_goal_mode_requested,
            "native_goal_mode_invoked": contract_native_goal_mode_invoked,
            "native_goal_mode_confirmation_status": contract_native_goal_mode_confirmation_status,
            "codex_acp_protocol_used": contract_codex_acp_protocol_used,
            "curated_skills_visible": contract_curated_skills_visible,
            "blind_loop": contract_blind_loop,
            "official_feedback_blinded": contract_official_feedback_blinded,
            "reward_feedback_forwarded": contract_reward_feedback_forwarded,
            "loopx_state_reads": controller_counters.get(
                "loopx_state_reads", 0
            ),
            "loopx_state_writes": controller_counters.get(
                "loopx_state_writes", 0
            ),
            "loopx_case_state_reads": controller_counters.get(
                "loopx_case_state_reads", 0
            ),
            "loopx_case_state_writes": controller_counters.get(
                "loopx_case_state_writes", 0
            ),
            "round_result_trajectory_lifecycle_summary_present": controller_counters.get(
                "round_result_trajectory_lifecycle_summary_present", False
            ),
            "round_result_loopx_cli_call_count": controller_counters.get(
                "round_result_loopx_cli_call_count", 0
            ),
            "round_result_loopx_cli_state_read_count": controller_counters.get(
                "round_result_loopx_cli_state_read_count", 0
            ),
            "round_result_loopx_cli_state_write_count": controller_counters.get(
                "round_result_loopx_cli_state_write_count", 0
            ),
            "heartbeat_count": controller_counters.get("heartbeat_count", 0),
            "controller_trace_present": controller_trace_present,
            "controller_action_decisions": controller_counters.get(
                "controller_action_decisions", 0
            ),
            "controller_initial_prompt_count": controller_counters.get(
                "initial_prompt_count", 0
            ),
            "controller_followup_prompt_count": controller_counters.get(
                "followup_prompt_count", 0
            ),
            "controller_stop_decision_count": controller_counters.get(
                "stop_decision_count", 0
            ),
            "controller_budget_cutoff_before_followup": controller_budget_cutoff_before_followup,
            "controller_budget_cutoff_reason": controller_budget_cutoff_reason,
            "benchflow_user_loop_final_verify_recovery_enabled": controller_counters.get(
                "benchflow_user_loop_final_verify_recovery_enabled",
                False,
            ),
            "benchflow_user_loop_final_verify_recovery_triggered": controller_counters.get(
                "benchflow_user_loop_final_verify_recovery_triggered",
                False,
            ),
            "benchflow_user_loop_recovery_after_agent_activity": controller_counters.get(
                "benchflow_user_loop_recovery_after_agent_activity",
                False,
            ),
            "benchflow_user_loop_recovery_preserved_final_verify": controller_counters.get(
                "benchflow_user_loop_recovery_preserved_final_verify",
                False,
            ),
            "benchflow_user_loop_recovery_raw_error_recorded": controller_counters.get(
                "benchflow_user_loop_recovery_raw_error_recorded",
                False,
            ),
            "benchflow_user_loop_recovery_stage": controller_counters.get(
                "benchflow_user_loop_recovery_stage",
                "",
            ),
            "benchflow_user_loop_recovery_exception_type": controller_counters.get(
                "benchflow_user_loop_recovery_exception_type",
                "",
            ),
            "benchflow_user_loop_recovery_round": controller_counters.get(
                "benchflow_user_loop_recovery_round",
                0,
            ),
            "benchflow_user_loop_recovery_delta_events": controller_counters.get(
                "benchflow_user_loop_recovery_delta_events",
                0,
            ),
            "benchflow_user_loop_recovery_delta_tool_calls": controller_counters.get(
                "benchflow_user_loop_recovery_delta_tool_calls",
                0,
            ),
            "benchflow_user_loop_soft_verify_exception_continued": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_continued",
                False,
            ),
            "benchflow_user_loop_soft_verify_exception_raw_error_recorded": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_raw_error_recorded",
                False,
            ),
            "benchflow_user_loop_soft_verify_exception_stage": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_stage",
                "",
            ),
            "benchflow_user_loop_soft_verify_exception_type": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_type",
                "",
            ),
            "benchflow_user_loop_soft_verify_exception_count": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_count",
                0,
            ),
            "benchflow_user_loop_soft_verify_exception_round": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_round",
                0,
            ),
            "benchflow_user_loop_soft_verify_exception_delta_events": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_delta_events",
                0,
            ),
            "benchflow_user_loop_soft_verify_exception_delta_tool_calls": controller_counters.get(
                "benchflow_user_loop_soft_verify_exception_delta_tool_calls",
                0,
            ),
            "benchflow_intermediate_soft_verify_policy": controller_counters.get(
                "benchflow_intermediate_soft_verify_policy",
                "",
            ),
            "benchflow_intermediate_soft_verify_final_only": controller_counters.get(
                "benchflow_intermediate_soft_verify_final_only",
                False,
            ),
            "benchflow_intermediate_soft_verify_call_count": controller_counters.get(
                "benchflow_intermediate_soft_verify_call_count",
                0,
            ),
            "benchflow_intermediate_soft_verify_skipped_count": controller_counters.get(
                "benchflow_intermediate_soft_verify_skipped_count",
                0,
            ),
            "benchflow_intermediate_soft_verify_raw_output_recorded": controller_counters.get(
                "benchflow_intermediate_soft_verify_raw_output_recorded",
                False,
            ),
            "controller_reward_observation_count": controller_counters.get(
                "reward_observation_count", 0
            ),
            "controller_round_reward_count": controller_counters.get(
                "round_reward_count", 0
            ),
            "controller_official_success_observed": controller_counters.get(
                "official_success_observed", False
            ),
            "controller_official_success_observation_count": controller_counters.get(
                "official_success_observation_count", 0
            ),
            "controller_first_success_round": first_success_round_value or 0,
            "controller_verifier_feedback_observation_count": controller_counters.get(
                "verifier_feedback_observation_count", 0
            ),
            "controller_official_feedback_blinded_count": controller_counters.get(
                "official_feedback_blinded_count", 0
            ),
            "controller_official_feedback_forwarded_count": controller_counters.get(
                "official_feedback_forwarded_count", 0
            ),
            "controller_official_feedback_forwarded": controller_counters.get(
                "official_feedback_forwarded", False
            ),
            "controller_blind_loop": controller_counters.get("blind_loop", False),
            "product_mode": controller_counters.get("product_mode", False),
            "goal_start_product_mode": controller_counters.get(
                "goal_start_product_mode", False
            ),
            "verifier_failure_feedback_todo_route": controller_counters.get(
                "verifier_failure_feedback_todo_route", False
            ),
            "verifier_failure_feedback_forwarded_to_agent": controller_counters.get(
                "verifier_failure_feedback_forwarded_to_agent", False
            ),
            "verifier_failure_todo_required": controller_counters.get(
                "verifier_failure_todo_required", False
            ),
            "verifier_failure_feedback_todo_prompt_count": controller_counters.get(
                "verifier_failure_feedback_todo_prompt_count", 0
            ),
            "verifier_failure_feedback_todo_round": controller_counters.get(
                "verifier_failure_feedback_todo_round", 0
            ),
            "goal_start_plan_observed": controller_counters.get(
                "goal_start_plan_observed", False
            ),
            "planned_todo_count": controller_counters.get("planned_todo_count", 0),
            "planned_p0_count": controller_counters.get("planned_p0_count", 0),
            "planner_before_todo_write": controller_counters.get(
                "planner_before_todo_write", False
            ),
            "same_priority_order_preserved": controller_counters.get(
                "same_priority_order_preserved", False
            ),
            "selected_p0_todo_id": controller_counters.get(
                "selected_p0_todo_id", ""
            ),
            "selected_todo_claimed": controller_counters.get(
                "selected_todo_claimed", False
            ),
            "selected_todo_updated_before_solver": controller_counters.get(
                "selected_todo_updated_before_solver", False
            ),
            "selected_todo_completed_before_spend": controller_counters.get(
                "selected_todo_completed_before_spend", False
            ),
            "non_selected_todos_preserved_open_or_deferred": controller_counters.get(
                "non_selected_todos_preserved_open_or_deferred", False
            ),
            "case_goal_state_packet_present": controller_counters.get(
                "case_goal_state_packet_present", False
            ),
            "case_goal_state_init_required": controller_counters.get(
                "case_goal_state_init_required", False
            ),
            "case_goal_state_initialized_before_agent": controller_counters.get(
                "case_goal_state_initialized_before_agent", False
            ),
            "case_goal_state_init_status": controller_counters.get(
                "case_goal_state_init_status", ""
            ),
            "case_goal_state_init_failed_phase": controller_counters.get(
                "case_goal_state_init_failed_phase", ""
            ),
            "case_goal_state_schema_version": controller_counters.get(
                "case_goal_state_schema_version", ""
            ),
            "case_goal_state_path": controller_counters.get(
                "case_goal_state_path", ""
            ),
            "declared_done_requires_no_remaining_goals": controller_counters.get(
                "declared_done_requires_no_remaining_goals", False
            ),
            "product_mode_lifecycle_checkpoint_required": controller_counters.get(
                "product_mode_lifecycle_checkpoint_required", False
            ),
            "product_mode_solver_activity_required": controller_counters.get(
                "product_mode_solver_activity_required", False
            ),
            "product_mode_solver_activity_gap": controller_counters.get(
                "product_mode_solver_activity_gap", False
            ),
            "product_mode_declared_done_below_passing_reward": controller_counters.get(
                "product_mode_declared_done_below_passing_reward", False
            ),
            "product_mode_no_open_todo_below_passing_reward_stop": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_stop", False
            ),
            "product_mode_host_local_idle_no_task_output_progress": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress", False
            ),
            "product_mode_host_local_idle_no_task_output_progress_stop": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_stop",
                False,
            ),
            "product_mode_lifecycle_checkpoint_count": controller_counters.get(
                "product_mode_lifecycle_checkpoint_count", 0
            ),
            "product_mode_lifecycle_checkpoint_round": controller_counters.get(
                "product_mode_lifecycle_checkpoint_round", 0
            ),
            "product_mode_lifecycle_checkpoint_missing_reason": controller_counters.get(
                "product_mode_lifecycle_checkpoint_missing_reason", ""
            ),
            "product_mode_solver_activity_gap_count": controller_counters.get(
                "product_mode_solver_activity_gap_count", 0
            ),
            "product_mode_solver_activity_gap_round": controller_counters.get(
                "product_mode_solver_activity_gap_round", 0
            ),
            "product_mode_solver_activity_missing_reason": controller_counters.get(
                "product_mode_solver_activity_missing_reason", ""
            ),
            "product_mode_declared_done_below_passing_reward_count": controller_counters.get(
                "product_mode_declared_done_below_passing_reward_count", 0
            ),
            "product_mode_declared_done_below_passing_reward_round": controller_counters.get(
                "product_mode_declared_done_below_passing_reward_round", 0
            ),
            "product_mode_declared_done_below_passing_reward_score": controller_counters.get(
                "product_mode_declared_done_below_passing_reward_score"
            ),
            "product_mode_declared_done_below_passing_reward_score_status": controller_counters.get(
                "product_mode_declared_done_below_passing_reward_score_status", ""
            ),
            "product_mode_declared_done_policy": controller_counters.get(
                "product_mode_declared_done_policy", ""
            ),
            "open_todo_count": controller_counters.get("open_todo_count", 0),
            "product_mode_no_open_todo_below_passing_reward_streak": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_streak", 0
            ),
            "product_mode_no_open_todo_below_passing_reward_streak_threshold": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_streak_threshold",
                0,
            ),
            "product_mode_no_open_todo_below_passing_reward_round": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_round", 0
            ),
            "product_mode_no_open_todo_below_passing_reward_stop_count": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_stop_count", 0
            ),
            "product_mode_no_open_todo_below_passing_reward_stop_round": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_stop_round", 0
            ),
            "product_mode_no_open_todo_below_passing_reward_open_todo_count_public": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_open_todo_count_public",
                0,
            ),
            "product_mode_no_open_todo_below_passing_reward_score": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_score"
            ),
            "product_mode_no_open_todo_below_passing_reward_score_status": controller_counters.get(
                "product_mode_no_open_todo_below_passing_reward_score_status", ""
            ),
            "product_mode_host_local_idle_no_task_output_progress_streak": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_streak",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_streak_threshold": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_streak_threshold",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_round": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_round",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_stop_count": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_stop_count",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_stop_round": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_stop_round",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_acp_tool_calls": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_acp_tool_calls",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes",
                0,
            ),
            "product_mode_host_local_idle_no_task_output_progress_score": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_score"
            ),
            "product_mode_host_local_idle_no_task_output_progress_score_status": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_score_status",
                "",
            ),
            "product_mode_host_local_idle_no_task_output_progress_category": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_category",
                "",
            ),
            "product_mode_host_local_idle_no_task_output_progress_policy": controller_counters.get(
                "product_mode_host_local_idle_no_task_output_progress_policy",
                "",
            ),
            "product_mode_final_closeout_superseded_by_official_success": (
                controller_counters.get(
                    "product_mode_final_closeout_superseded_by_official_success",
                    False,
                )
            ),
            "product_mode_final_closeout_superseded_round": controller_counters.get(
                "product_mode_final_closeout_superseded_round", 0
            ),
            "product_mode_final_closeout_superseded_reason": controller_counters.get(
                "product_mode_final_closeout_superseded_reason", ""
            ),
            "product_mode_no_tool_call_lifecycle_abort": controller_counters.get(
                "product_mode_no_tool_call_lifecycle_abort", False
            ),
            "product_mode_no_tool_call_lifecycle_abort_count": controller_counters.get(
                "product_mode_no_tool_call_lifecycle_abort_count", 0
            ),
            "product_mode_no_tool_call_lifecycle_abort_round": controller_counters.get(
                "product_mode_no_tool_call_lifecycle_abort_round", 0
            ),
            "agent_declared_done": controller_counters.get(
                "agent_declared_done", False
            ),
            "agent_declared_no_remaining_goals": controller_counters.get(
                "agent_declared_no_remaining_goals", False
            ),
            "declared_done_round": controller_counters.get("declared_done_round", 0),
            "controller_max_rounds_budget": controller_counters.get(
                "max_rounds_budget", 0
            ),
            "controller_trace_schema_version": controller_counters.get(
                "controller_trace_schema_version", ""
            ),
            "controller_trace_publicness": controller_counters.get(
                "controller_trace_publicness", ""
            ),
            "remote_command_file_bridge_consumption_decision": controller_counters.get(
                "remote_command_file_bridge_consumption_decision", ""
            ),
            "private_trajectory_summary_present": bool(trajectory_summary),
            "private_trajectory_event_count": trajectory_summary.get("event_count", 0),
            "private_trajectory_round_count": trajectory_summary.get("round_count", 0),
            "private_trajectory_tool_call_count": trajectory_summary.get(
                "tool_call_count", 0
            ),
            "loopx_cli_call_count": trajectory_summary.get(
                "loopx_cli_call_count", 0
            ),
            "loopx_cli_calls": trajectory_summary.get(
                "loopx_cli_calls", []
            ),
            "trajectory_action_category_counts": trajectory_summary.get(
                "action_category_counts", {}
            ),
            "loopx_cli_state_usage_counts": trajectory_summary.get(
                "loopx_cli_state_usage_counts", {}
            ),
            "loopx_cli_state_read_count": trajectory_summary.get(
                "loopx_cli_state_read_count", 0
            ),
            "loopx_cli_state_write_count": trajectory_summary.get(
                "loopx_cli_state_write_count", 0
            ),
            "native_goal_worker_route": controller_counters.get(
                "native_goal_worker_route", False
            ),
            "native_goal_worker_connected": controller_counters.get(
                "native_goal_worker_connected", False
            ),
            "native_goal_worker_trace_dir_present": controller_counters.get(
                "native_goal_worker_trace_dir_present", False
            ),
            "native_goal_worker_public_trace_read": controller_counters.get(
                "native_goal_worker_public_trace_read", False
            ),
            "native_goal_worker_raw_material_recorded": controller_counters.get(
                "native_goal_worker_raw_material_recorded", False
            ),
            "native_goal_worker_connect_count": controller_counters.get(
                "native_goal_worker_connect_count", 0
            ),
            "native_goal_worker_trace_count": controller_counters.get(
                "native_goal_worker_trace_count", 0
            ),
            "native_goal_worker_lifecycle_trace_count": controller_counters.get(
                "native_goal_worker_lifecycle_trace_count", 0
            ),
            "native_goal_worker_prompt_received_count": controller_counters.get(
                "native_goal_worker_prompt_received_count", 0
            ),
            "native_goal_worker_ok_count": controller_counters.get(
                "native_goal_worker_ok_count", 0
            ),
            "native_goal_worker_failure_trace_count": controller_counters.get(
                "native_goal_worker_failure_trace_count", 0
            ),
            "native_goal_worker_failure_category": controller_counters.get(
                "native_goal_worker_failure_category", ""
            ),
            "native_goal_worker_first_blocker": controller_counters.get(
                "native_goal_worker_first_blocker", ""
            ),
            "native_goal_worker_goal_get_count": controller_counters.get(
                "native_goal_worker_goal_get_count", 0
            ),
            "native_goal_worker_turn_start_count": controller_counters.get(
                "native_goal_worker_turn_start_count", 0
            ),
            "native_goal_worker_turn_completed_observed_count": (
                controller_counters.get(
                    "native_goal_worker_turn_completed_observed_count", 0
                )
            ),
            "native_goal_worker_assistant_message_present_count": (
                controller_counters.get(
                    "native_goal_worker_assistant_message_present_count", 0
                )
            ),
            "native_goal_worker_assistant_context_only_count": (
                controller_counters.get(
                    "native_goal_worker_assistant_context_only_count", 0
                )
            ),
            "native_goal_worker_context_only_recovery_attempted_count": (
                controller_counters.get(
                    "native_goal_worker_context_only_recovery_attempted_count", 0
                )
            ),
            "native_goal_worker_context_only_recovery_succeeded_count": (
                controller_counters.get(
                    "native_goal_worker_context_only_recovery_succeeded_count", 0
                )
            ),
            "native_goal_worker_context_only_followup_start_attempted_count": (
                controller_counters.get(
                    "native_goal_worker_context_only_followup_start_attempted_count", 0
                )
            ),
            "native_goal_worker_context_only_followup_start_succeeded_count": (
                controller_counters.get(
                    "native_goal_worker_context_only_followup_start_succeeded_count", 0
                )
            ),
            "native_goal_worker_transport_reconnect_attempted_count": (
                controller_counters.get(
                    "native_goal_worker_transport_reconnect_attempted_count", 0
                )
            ),
            "native_goal_worker_transport_reconnect_succeeded_count": (
                controller_counters.get(
                    "native_goal_worker_transport_reconnect_succeeded_count", 0
                )
            ),
            "native_goal_worker_goal_reactivation_attempted_count": (
                controller_counters.get(
                    "native_goal_worker_goal_reactivation_attempted_count", 0
                )
            ),
            "native_goal_worker_goal_reactivation_succeeded_count": (
                controller_counters.get(
                    "native_goal_worker_goal_reactivation_succeeded_count", 0
                )
            ),
            "native_goal_worker_post_context_assistant_chars_total": (
                controller_counters.get(
                    "native_goal_worker_post_context_assistant_chars_total", 0
                )
            ),
            "native_goal_worker_reasoning_effort": controller_counters.get(
                "native_goal_worker_reasoning_effort", ""
            ),
            "remote_command_file_bridge_consumed_by_solver": (
                controller_counters.get(
                    "remote_command_file_bridge_consumed_by_solver", False
                )
            ),
            "remote_command_file_bridge_solver_trace_dir_present": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_trace_dir_present", False
                )
            ),
            "remote_command_file_bridge_solver_public_trace_read": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_public_trace_read", False
                )
            ),
            "remote_command_file_bridge_solver_raw_material_recorded": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_raw_material_recorded",
                    False,
                )
            ),
            "remote_command_file_bridge_solver_trace_count": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_trace_count", 0
                )
            ),
            "remote_command_file_bridge_solver_probe_ready_count": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_probe_ready_count", 0
                )
            ),
            "remote_command_file_bridge_solver_operation_count": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_operation_count", 0
                )
            ),
            "remote_command_file_bridge_agent_operation_trace_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_operation_trace_count", 0
                )
            ),
            "remote_command_file_bridge_agent_operation_trace_required": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_operation_trace_required",
                    False,
                )
            ),
            "remote_command_file_bridge_agent_operation_trace_satisfied": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_operation_trace_satisfied",
                    False,
                )
            ),
            "remote_command_file_bridge_agent_operation_trace_status": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_operation_trace_status", ""
                )
            ),
            "remote_command_file_bridge_agent_request_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_request_count", 0
                )
            ),
            "remote_command_file_bridge_agent_loopx_cli_call_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_loopx_cli_call_count", 0
                )
            ),
            "remote_command_file_bridge_agent_loopx_state_read_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_loopx_state_read_count", 0
                )
            ),
            "remote_command_file_bridge_agent_loopx_state_write_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_loopx_state_write_count", 0
                )
            ),
            "remote_command_file_bridge_agent_todo_closeout_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_todo_closeout_count", 0
                )
            ),
            "remote_command_file_bridge_agent_refresh_state_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_refresh_state_count", 0
                )
            ),
            "remote_command_file_bridge_agent_quota_spend_slot_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_quota_spend_slot_count", 0
                )
            ),
            "remote_command_file_bridge_agent_task_facing_operation_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_task_facing_operation_count", 0
                )
            ),
            "remote_command_file_bridge_agent_task_facing_success_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_task_facing_success_count", 0
                )
            ),
            "remote_command_file_bridge_agent_task_facing_failure_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_task_facing_failure_count", 0
                )
            ),
            "remote_command_file_bridge_agent_failure_category_counts": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_failure_category_counts", {}
                )
            ),
            "remote_command_file_bridge_agent_probe_operation_count": (
                controller_counters.get(
                    "remote_command_file_bridge_agent_probe_operation_count", 0
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_trace_count": (
                controller_counters.get(
                    "remote_command_file_bridge_driver_lifecycle_trace_count", 0
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count": (
                controller_counters.get(
                    "remote_command_file_bridge_driver_lifecycle_checkpoint_count",
                    0,
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_request_count": (
                controller_counters.get(
                    "remote_command_file_bridge_driver_lifecycle_request_count", 0
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_success_count": (
                controller_counters.get(
                    "remote_command_file_bridge_driver_lifecycle_success_count", 0
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_failure_count": (
                controller_counters.get(
                    "remote_command_file_bridge_driver_lifecycle_failure_count", 0
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": (
                controller_counters.get(
                    (
                        "remote_command_file_bridge_driver_lifecycle_"
                        "loopx_cli_call_count"
                    ),
                    0,
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": (
                controller_counters.get(
                    (
                        "remote_command_file_bridge_driver_lifecycle_"
                        "loopx_state_read_count"
                    ),
                    0,
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": (
                controller_counters.get(
                    (
                        "remote_command_file_bridge_driver_lifecycle_"
                        "loopx_state_write_count"
                    ),
                    0,
                )
            ),
            "remote_command_file_bridge_driver_lifecycle_execution_style": (
                controller_counters.get(
                    "remote_command_file_bridge_driver_lifecycle_execution_style",
                    "",
                )
            ),
            "host_local_acp_codex_exec_failure_trace_present": (
                controller_counters.get(
                    "host_local_acp_codex_exec_failure_trace_present", False
                )
            ),
            "host_local_acp_bridge_progress_status": controller_counters.get(
                "host_local_acp_bridge_progress_status", ""
            ),
            "host_local_acp_bridge_progress_signal_source": controller_counters.get(
                "host_local_acp_bridge_progress_signal_source", ""
            ),
            "host_local_acp_codex_exec_failure_trace_count": (
                controller_counters.get(
                    "host_local_acp_codex_exec_failure_trace_count", 0
                )
            ),
            "host_local_acp_codex_exec_failure_category": (
                controller_counters.get(
                    "host_local_acp_codex_exec_failure_category", ""
                )
            ),
            "host_local_acp_codex_exec_failure_raw_material_recorded": (
                controller_counters.get(
                    "host_local_acp_codex_exec_failure_raw_material_recorded",
                    False,
                )
            ),
            "loopx_case_state_path_count": trajectory_summary.get(
                "loopx_case_state_path_count", 0
            ),
            "loopx_case_state_read_count": trajectory_summary.get(
                "loopx_case_state_read_count", 0
            ),
            "loopx_case_state_write_count": trajectory_summary.get(
                "loopx_case_state_write_count", 0
            ),
            "protected_path_mention_count": trajectory_summary.get(
                "protected_path_mention_count", 0
            ),
            "protected_path_edit_signal_count": trajectory_summary.get(
                "protected_path_edit_signal_count", 0
            ),
            "codex_acp_text_bytes": trajectory_summary.get("codex_acp_text_bytes", 0),
            "last_decision": controller_counters.get("last_decision", ""),
            "case_result_writeback": official_score_source,
            "counter_trust_level": counter_trust_level,
        },
        "episode_policy": {
            "schema_version": "skillsbench_episode_policy_v0",
            "route": route,
            "outer_controller": outer_controller,
            "inner_case_actor": inner_case_actor,
            "product_mode": False if is_oracle_runner else contract.get("product_mode") is True,
            "blind_loop": contract_blind_loop,
            "official_feedback_blinded": contract_official_feedback_blinded,
            "reward_feedback_forwarded": contract_reward_feedback_forwarded,
            "verifier_output_tail_forwarded_by_default": False,
            "raw_trace_recorded": False,
            "raw_task_text_recorded": False,
            "controller_trace_recorded": controller_trace_present,
            "does_not_upload_or_submit": True,
        },
        "product_mode_lifecycle_contract": product_mode_lifecycle_contract,
        "native_goal_worker_contract": native_goal_worker_contract,
        "app_server_goal_round_semantics": app_server_goal_round_semantics,
        "trials": [
            {
                "task_id": task_id,
                "trial_name": rollout_name,
                "source": dataset,
                "exception_type": exception_type,
                "reward": {"reward": reward_value if reward_value is not None else 0},
                "metrics": {
                    "input_tokens": 0,
                    "cache_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0,
                },
                "trajectory_present": bool(result.get("trajectory_source")),
                "verifier_reward_present": reward_value is not None,
                "artifact_manifest_present": True,
                "trial_result_present": True,
            }
        ],
        "validation": {
            "official_verifier_validation_present": reward_value is not None,
            "official_case_success": official_passed,
            "no_upload": True,
            "no_submit": True,
            "no_raw_logs_public": True,
            "no_credential_values_recorded": True,
            "validation_scope": validation_scope,
            "official_verifier_status": official_score_status,
            "loopx_controller_trace_present": controller_trace_present,
            "loopx_controller_trace_public_safe": not controller_raw_material_recorded,
            "native_goal_worker_route": controller_counters.get(
                "native_goal_worker_route", False
            ),
            "native_goal_worker_connected": controller_counters.get(
                "native_goal_worker_connected", False
            ),
            "native_goal_worker_trace_dir_present": controller_counters.get(
                "native_goal_worker_trace_dir_present", False
            ),
            "native_goal_worker_public_trace_read": controller_counters.get(
                "native_goal_worker_public_trace_read", False
            ),
            "native_goal_worker_trace_observed": native_goal_worker_trace_observed,
            "native_goal_worker_trace_count": native_goal_worker_trace_count,
            "native_goal_worker_lifecycle_trace_count": controller_counters.get(
                "native_goal_worker_lifecycle_trace_count", 0
            ),
            "native_goal_worker_prompt_received_count": controller_counters.get(
                "native_goal_worker_prompt_received_count", 0
            ),
            "native_goal_worker_first_action_observed_count": controller_counters.get(
                "native_goal_worker_first_action_observed_count", 0
            ),
            "native_goal_worker_effective_action_observed_count": (
                controller_counters.get(
                    "native_goal_worker_effective_action_observed_count", 0
                )
            ),
            "native_goal_worker_assistant_context_only_count": (
                controller_counters.get(
                    "native_goal_worker_assistant_context_only_count", 0
                )
            ),
            "native_goal_worker_post_context_assistant_chars_total": (
                controller_counters.get(
                    "native_goal_worker_post_context_assistant_chars_total", 0
                )
            ),
            "native_goal_worker_reasoning_effort": controller_counters.get(
                "native_goal_worker_reasoning_effort", ""
            ),
            "native_goal_worker_trace_status": native_goal_worker_trace_status,
            "native_goal_worker_countable_baseline": native_goal_worker_countable,
            "native_goal_worker_failure_category": native_goal_worker_contract.get(
                "failure_category", ""
            ),
            "native_goal_worker_first_blocker": native_goal_worker_contract.get(
                "first_blocker", ""
            ),
            "remote_command_file_bridge_consumed_by_solver": (
                controller_counters.get(
                    "remote_command_file_bridge_consumed_by_solver", False
                )
            ),
            "remote_command_file_bridge_solver_public_trace_read": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_public_trace_read", False
                )
            ),
            "remote_command_file_bridge_solver_trace_count": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_trace_count", 0
                )
            ),
            "remote_command_file_bridge_solver_probe_ready_count": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_probe_ready_count", 0
                )
            ),
            "remote_command_file_bridge_solver_operation_count": (
                controller_counters.get(
                    "remote_command_file_bridge_solver_operation_count", 0
                )
            ),
        },
        "authorization": {
            "real_case_execution_authorized": True,
            "submit_eligible": False,
        },
        "redaction": {
            "secret_values_recorded": False,
            "raw_sessions_recorded": False,
            "host_paths_recorded": False,
            "raw_prompts_recorded": False,
            "raw_solutions_recorded": False,
        },
        "mode_contract": {
            "requested_route": route,
            "arm_id": contract["arm_id"],
            "case_semantics_changed_by_harness": contract_case_semantics_changed_by_harness,
            "loopx_inside_case": contract_loopx_inside_case,
            "loopx_automation_loop": contract_loopx_automation_loop,
            "inner_codex_goal_mode": contract_inner_codex_goal_mode,
            "native_goal_mode_requested": contract_native_goal_mode_requested,
            "native_goal_mode_invoked": contract_native_goal_mode_invoked,
            "native_goal_mode_confirmation_status": contract_native_goal_mode_confirmation_status,
            "codex_acp_protocol_used": contract_codex_acp_protocol_used,
            "skillsbench_route_semantics": contract_skillsbench_route_semantics,
            "curated_skills_visible": contract_curated_skills_visible,
            "product_mode": False if is_oracle_runner else contract.get("product_mode") is True,
            "blind_loop": contract_blind_loop,
            "official_feedback_blinded": contract_official_feedback_blinded,
            "reward_feedback_forwarded": contract_reward_feedback_forwarded,
            "official_score_comparable_to_native_codex": contract_official_score_comparable_to_native_codex,
            "official_score_comparable_to_loopx_treatment": contract_official_score_comparable_to_loopx_treatment,
            "product_mode_lifecycle": product_mode_lifecycle_contract,
            "native_goal_worker": native_goal_worker_contract,
            "leaderboard_evidence": False,
        },
        "evidence_files": evidence_files,
        "resume_or_inspect_commands": [
            (
                "loopx benchmark run skillsbench "
                "--skillsbench-result-json <official-skillsbench-result.json>"
            ),
            (
                "loopx benchmark run-ledger-upsert "
                "--benchmark-run-json <skillsbench-compact-benchmark-run-v0.json>"
            ),
        ],
        "real_run": True,
        "submit_eligible": False,
        "official_task_score": {
            "kind": official_score_kind,
            "value": reward_value,
            "passed": official_passed,
        },
        "official_score": reward_value,
        "official_score_status": official_score_status,
        "official_score_source": official_score_source,
        "score_failure_attribution": score_failure_attribution,
        "case_semantics_changed_by_harness": contract_case_semantics_changed_by_harness,
        "loopx_inside_case": contract_loopx_inside_case,
        "loopx_automation_loop": contract_loopx_automation_loop,
        "product_mode": False if is_oracle_runner else contract.get("product_mode") is True,
        "inner_codex_goal_mode": contract_inner_codex_goal_mode,
        "native_goal_mode_requested": contract_native_goal_mode_requested,
        "native_goal_mode_invoked": contract_native_goal_mode_invoked,
        "native_goal_mode_confirmation_status": contract_native_goal_mode_confirmation_status,
        "codex_acp_protocol_used": contract_codex_acp_protocol_used,
        "skillsbench_route_semantics": contract_skillsbench_route_semantics,
        "curated_skills_visible": contract_curated_skills_visible,
        "blind_loop": contract_blind_loop,
        "official_feedback_blinded": contract_official_feedback_blinded,
        "reward_feedback_forwarded": contract_reward_feedback_forwarded,
        "official_score_comparable_to_native_codex": contract_official_score_comparable_to_native_codex,
        "official_score_comparable_to_loopx_treatment": contract_official_score_comparable_to_loopx_treatment,
        "leaderboard_evidence": False,
        "trace_publicness": "public_skillsbench_official_compact_result_only",
        "failure_attribution_labels": failure_labels,
        "runner_warning_labels": warning_labels,
        "stop_conditions": [
            "do_not_read_raw_task_prompt_solution_or_trajectory",
            "do_not_record_absolute_job_paths_in_public_ledger",
            "do_not_upload_or_submit_leaderboard",
            "do_not_record_secrets_or_raw_sessions",
        ],
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "controller_trace_read": controller_trace_present,
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }
    if timing_summary:
        benchmark_run["timing"] = timing_summary
    if round_reward_trace is not None:
        benchmark_run["round_reward_trace"] = round_reward_trace
    if isinstance(result_discovery, dict) and result_discovery:
        benchmark_run["result_discovery"] = dict(result_discovery)
    if runner_failure is not None:
        benchmark_run["runner_failure"] = runner_failure
        if runner_failure_fingerprint is not None:
            benchmark_run["runner_failure_fingerprint"] = runner_failure_fingerprint
    if partial_trajectory and not host_local_acp_codex_exec_failure_present:
        benchmark_run["failure_attribution_labels"].append("partial_trajectory")
    benchmark_run["solution_quality_signals"] = (
        build_skillsbench_solution_quality_signals(benchmark_run)
    )
    return benchmark_run


def skillsbench_recommended_action(*, route: str) -> str:
    contract = skillsbench_route_contract(route)
    return str(contract["next_action"])
