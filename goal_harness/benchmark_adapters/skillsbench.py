from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from ..benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_path,
)
from ..codex_goal_baseline import build_codex_app_server_goal_worker_plan


SKILLSBENCH_DEFAULT_DATASET = "skillsbench@1.1"
SKILLSBENCH_DEFAULT_TASK = "citation-check"
SKILLSBENCH_DEFAULT_MODEL = "gpt-5.5"
SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID = "skillsbench-case"
SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH = benchmark_case_active_state_path(
    SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID
)
SKILLSBENCH_ROUTES = (
    "codex-acp-blind-loop-baseline",
    "goal-harness-blind-loop-treatment",
    "codex-app-server-goal-baseline",
    "codex-goal-mode-baseline",
    "automation-loop-treatment",
    "curated-skills-baseline",
    "raw-codex-autonomous-max5",
    "goal-harness-product-mode",
)
SKILLSBENCH_DEFAULT_ROUTE = "goal-harness-blind-loop-treatment"


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
    "raw-codex-autonomous-max5",
    "goal-harness-product-mode",
)


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
            "source_runner": "goal_harness_skillsbench_codex_acp_blind_loop_baseline_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_ordinary_agent_blind_loop_no_goal_no_reward_feedback",
            "curated_skills_visible": False,
            "goal_harness_automation_loop": False,
            "goal_harness_inside_case": False,
            "blind_loop": True,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run ordinary Codex ACP/CLI with the same fixed blind loop budget "
                "as treatment, with no /goal mode and no official reward/pass-fail "
                "or verifier output returned to the agent"
            ),
        }
    if route == "goal-harness-blind-loop-treatment":
        return {
            "mode": "skillsbench_goal_harness_blind_loop_treatment",
            "arm_id": "goal_harness_blind_loop_treatment",
            "source_runner": "goal_harness_skillsbench_blind_loop_treatment_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_ordinary_agent_with_outer_goal_harness_blind_loop_no_reward_feedback",
            "curated_skills_visible": False,
            "goal_harness_automation_loop": True,
            "goal_harness_inside_case": False,
            "blind_loop": True,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run Goal Harness outer automation with a fixed blind loop budget; "
                "do not return official reward, pass/fail, verifier error, or "
                "verifier output to the in-case agent during the loop"
            ),
        }
    if route == "raw-codex-autonomous-max5":
        return {
            "mode": "skillsbench_raw_codex_autonomous_max5_baseline",
            "arm_id": "raw_codex_autonomous_max5",
            "source_runner": "goal_harness_skillsbench_raw_codex_autonomous_max5_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "raw_codex_autonomous_max5_no_goal_harness_no_reward_feedback",
            "curated_skills_visible": False,
            "goal_harness_automation_loop": False,
            "goal_harness_inside_case": False,
            "product_mode": True,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run raw Codex autonomous max5 with no Goal Harness state/todo/"
                "replan/CLI surface and no official reward or verifier feedback "
                "returned during execution"
            ),
        }
    if route == "goal-harness-product-mode":
        return {
            "mode": "skillsbench_goal_harness_product_mode_treatment",
            "arm_id": "goal_harness_product_mode",
            "source_runner": "goal_harness_skillsbench_product_mode_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_agent_with_goal_harness_state_todo_replan_cli_no_reward_feedback",
            "curated_skills_visible": False,
            "goal_harness_automation_loop": True,
            "goal_harness_inside_case": True,
            "product_mode": True,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": True,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run Goal Harness product-mode treatment with goal state, todos, "
                "replan/status writeback, and GH CLI/ledger surfaces; do not "
                "return official reward or verifier feedback during execution"
            ),
        }
    if route == "codex-goal-mode-baseline":
        return {
            "mode": "codex_goal_mode_baseline",
            "arm_id": "codex_goal_mode_baseline",
            "source_runner": "goal_harness_skillsbench_codex_goal_mode_baseline_skeleton",
            "inner_codex_goal_mode": True,
            "native_goal_mode_requested": True,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": (
                "unconfirmed_acp_prompt_text_not_interactive_cli_slash_command"
            ),
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_goal_prompt_request_no_reward_followup_unconfirmed_native_goal_mode",
            "curated_skills_visible": False,
            "goal_harness_automation_loop": False,
            "goal_harness_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
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
            "source_runner": "goal_harness_skillsbench_host_codex_app_server_goal_worker",
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
            "goal_harness_automation_loop": False,
            "goal_harness_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
            "first_blocker": "skillsbench_app_server_goal_worker_compact_proof_missing",
            "next_action": (
                "launch SkillsBench through Codex app-server Goal APIs "
                "thread/start plus thread/goal/set/get plus turn/start, ingest "
                "only compact no-upload evidence, and fail closed rather than "
                "falling back to ACP or slash-prefix prompt experiments"
            ),
        }
    if route == "automation-loop-treatment":
        return {
            "mode": "skillsbench_goal_harness_automation_loop_treatment",
            "arm_id": "goal_harness_automation_loop_treatment",
            "source_runner": "goal_harness_skillsbench_automation_loop_treatment_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_ordinary_agent_with_outer_reward_feedback_loop",
            "curated_skills_visible": False,
            "goal_harness_automation_loop": True,
            "goal_harness_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": False,
            "reward_feedback_forwarded": True,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": True,
            "first_blocker": "skillsbench_adapter_skeleton_no_real_case",
            "next_action": (
                "run the automation-loop treatment only after the paired baseline "
                "failure is compact-attributed and control-plane-addressable; the "
                "inner case actor must be ordinary Codex CLI, not Codex goal mode"
            ),
        }
    if route == "curated-skills-baseline":
        return {
            "mode": "skillsbench_curated_skills_baseline",
            "arm_id": "curated_skills_baseline",
            "source_runner": "goal_harness_skillsbench_curated_skills_baseline_skeleton",
            "inner_codex_goal_mode": False,
            "native_goal_mode_requested": False,
            "native_goal_mode_invoked": False,
            "native_goal_mode_confirmation_status": "not_requested",
            "codex_acp_protocol_used": True,
            "skillsbench_route_semantics": "codex_acp_curated_skills_visible_control",
            "curated_skills_visible": True,
            "goal_harness_automation_loop": False,
            "goal_harness_inside_case": False,
            "blind_loop": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "official_score_comparable_to_goal_harness_treatment": False,
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


def build_skillsbench_app_server_goal_worker_contract(
    *,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = SKILLSBENCH_DEFAULT_TASK,
    cwd: str = "<skillsbench-task-workspace>",
    model: str = SKILLSBENCH_DEFAULT_MODEL,
    reasoning_effort: str = "high",
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
    include_goal_harness_state: bool = False,
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
    if include_goal_harness_state:
        blockers.append("skillsbench_native_baseline_must_not_include_goal_harness_state")
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
        "worker_adapter": {
            "label": "skillsbench_host_codex_app_server_goal_worker",
            "script": "scripts/skillsbench_host_codex_goal_worker.py",
            "codex_bin": _skillsbench_public_safe_label(codex_bin, limit=80) or "codex",
            "reasoning_effort": _skillsbench_public_safe_label(
                reasoning_effort, limit=40
            )
            or "high",
            "agent_execution_mode": "host_codex_app_server_goal_worker",
            "worker_surface": "codex_app_server",
            "native_goal_methods_required": list(worker_plan["methods"]),
            "thread_goal_get_required": True,
            "turn_start_required": True,
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
            "goal_harness_state_included": False,
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
                "goal_harness_state",
                "planning_and_patch_generation",
            ],
            "keeps_local": [
                "codex_auth",
                "model_invocation",
                "goal_harness_state",
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
    if "acp error -32603" in text and "internal error" in text:
        label = "skillsbench_codex_acp_jsonrpc_internal_error"
        return label, label, [label, "skillsbench_codex_acp_transport_error"]
    if "benchflow result.json not found" in text:
        label = "skillsbench_result_json_missing_after_runner_exit"
        return label, label, [label, "skillsbench_runner_setup_error"]
    if (
        "could not find the file /app" in text
        or "main:/app/skills" in text
        or "/app/skills" in text
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
        "image_build": r"failed to solve|failed to build|dockerfile|pull access denied|manifest unknown",
        "port_conflict": r"port is already allocated|address already in use|ports are not available|bind for",
        "apt_failure": r"apt-get|apt update|apt |gpg error|hash sum mismatch|failed to fetch",
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
                    "goal_harness_product_mode",
                    "goal_state_todos_replan_cli",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "goal-harness-product-mode"
                else [
                    "ordinary_codex_cli_actor",
                    "goal_harness_blind_loop",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "goal-harness-blind-loop-treatment"
                else [
                    "ordinary_codex_cli_actor",
                    "goal_harness_automation_loop",
                    "reward_feedback_ablation",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "automation-loop-treatment"
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
            "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
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
            "goal_harness_state_reads": 0,
            "goal_harness_state_writes": 0,
            "goal_harness_case_state_reads": 0,
            "goal_harness_case_state_writes": 0,
            "heartbeat_count": 0,
            "case_goal_state_packet_present": route == "goal-harness-product-mode",
            "case_goal_state_init_required": route == "goal-harness-product-mode",
            "case_goal_state_initialized_before_agent": False,
            "case_goal_state_init_status": (
                "not_run_adapter_skeleton"
                if route == "goal-harness-product-mode"
                else ""
            ),
            "case_goal_state_schema_version": (
                BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
                if route == "goal-harness-product-mode"
                else ""
            ),
            "case_goal_state_path": (
                SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH
                if route == "goal-harness-product-mode"
                else ""
            ),
            "declared_done_requires_no_remaining_goals": route
            == "goal-harness-product-mode",
            "case_result_writeback": "not_run_adapter_skeleton",
            "counter_trust_level": "adapter_contract_fixture",
        },
        "episode_policy": {
            "schema_version": "skillsbench_episode_policy_v0",
            "route": route,
            "outer_controller": (
                "goal_harness_blind_automation_loop"
                if route == "goal-harness-blind-loop-treatment"
                else "goal_harness_product_mode"
                if route == "goal-harness-product-mode"
                else "reward_feedback_automation_loop_ablation"
                if route == "automation-loop-treatment"
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
                    "automation-loop-treatment",
                    "goal-harness-blind-loop-treatment",
                    "codex-acp-blind-loop-baseline",
                    "raw-codex-autonomous-max5",
                    "goal-harness-product-mode",
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
            "goal_harness_inside_case": contract["goal_harness_inside_case"],
            "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
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
            "official_score_comparable_to_goal_harness_treatment": contract[
                "official_score_comparable_to_goal_harness_treatment"
            ],
            "leaderboard_evidence": False,
        },
        "evidence_files": [
            "doc:automation-loop-treatment-case-selection-20260614.md",
            "doc:benchmark-run-ledger-v0.md",
            "smoke:skillsbench-benchmark-run-smoke.py",
        ],
        "resume_or_inspect_commands": [
            (
                "goal-harness benchmark run skillsbench "
                f"--skillsbench-route {route} --include-task-name {task_id}"
            ),
            (
                "goal-harness benchmark run-ledger-upsert "
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
        "goal_harness_inside_case": contract["goal_harness_inside_case"],
        "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
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
        "official_score_comparable_to_goal_harness_treatment": contract[
            "official_score_comparable_to_goal_harness_treatment"
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
    if schema_version != "skillsbench_goal_harness_controller_trace_v0":
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
        "official_feedback_forwarded": controller_trace.get(
            "official_feedback_forwarded"
        )
        is True,
        "blind_loop": controller_trace.get("blind_loop") is True,
        "product_mode": controller_trace.get("product_mode") is True,
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
        "agent_declared_done": controller_trace.get("agent_declared_done") is True,
        "agent_declared_no_remaining_goals": controller_trace.get(
            "agent_declared_no_remaining_goals"
        )
        is True,
        "max_rounds_budget": count("max_rounds_budget"),
        "goal_harness_state_reads": count("goal_harness_state_reads"),
        "goal_harness_state_writes": count("goal_harness_state_writes"),
        "goal_harness_case_state_reads": count("goal_harness_case_state_reads"),
        "goal_harness_case_state_writes": count("goal_harness_case_state_writes"),
        "native_goal_worker_route": controller_trace.get("native_goal_worker_route")
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
        "native_goal_worker_ok_count": count("native_goal_worker_ok_count"),
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
    }
    last_decision = _skillsbench_public_safe_label(
        controller_trace.get("last_decision") or ""
    )
    if last_decision:
        counters["last_decision"] = last_decision
    init_status = _skillsbench_public_safe_label(
        controller_trace.get("case_goal_state_init_status") or ""
    )
    if init_status:
        counters["case_goal_state_init_status"] = init_status
    case_state_schema = _skillsbench_public_safe_label(
        controller_trace.get("case_goal_state_schema_version") or ""
    )
    if case_state_schema:
        counters["case_goal_state_schema_version"] = case_state_schema
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
                "goal_harness_cli_call_count",
                "goal_harness_cli_calls",
                "goal_harness_cli_state_usage_counts",
                "goal_harness_cli_state_read_count",
                "goal_harness_cli_state_write_count",
                "goal_harness_case_state_path_count",
                "goal_harness_case_state_read_count",
                "goal_harness_case_state_write_count",
                "protected_path_mention_count",
                "protected_path_edit_signal_count",
                "codex_acp_text_present",
                "codex_acp_text_bytes",
            )
            if trajectory_summary.get(key) is not None
        }
    return counters


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
    contract_goal_harness_automation_loop = (
        False if is_oracle_runner else contract["goal_harness_automation_loop"]
    )
    contract_goal_harness_inside_case = (
        False if is_oracle_runner else contract["goal_harness_inside_case"]
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
    contract_official_score_comparable_to_goal_harness_treatment = (
        False
        if is_oracle_runner
        else contract["official_score_comparable_to_goal_harness_treatment"]
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
        else "goal_harness_blind_automation_loop"
        if route == "goal-harness-blind-loop-treatment"
        else "goal_harness_product_mode"
        if route == "goal-harness-product-mode"
        else "reward_feedback_automation_loop_ablation"
        if route == "automation-loop-treatment"
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
            "automation-loop-treatment",
            "goal-harness-blind-loop-treatment",
            "codex-acp-blind-loop-baseline",
            "raw-codex-autonomous-max5",
            "goal-harness-product-mode",
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
    official_passed = bool(reward_value is not None and reward_value >= 1)

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
        exception_type = "skillsbench_verifier_error"
        failure_labels.append("verifier_infrastructure_failure")
        score_failure_attribution = "verifier_infrastructure_failure"

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
            "official_benchflow_compact_result_plus_goal_harness_controller_trace"
        )
    evidence_files = [
        "official_skillsbench:result.json",
        "official_skillsbench:timing.json" if timing else "official_skillsbench:timing_missing",
    ]
    if reward_artifact_source:
        evidence_files.append("official_skillsbench:verifier/reward.txt")
    if controller_trace_present:
        evidence_files.append("goal_harness:controller_trace.public.json")
    trajectory_summary = (
        controller_counters.get("acp_trajectory_summary")
        if isinstance(controller_counters.get("acp_trajectory_summary"), dict)
        else {}
    )
    if trajectory_summary:
        evidence_files.append("goal_harness:acp_trajectory_summary")
    runner_failure: dict[str, Any] | None = None
    if error_text:
        runner_failure = {
            "schema_version": "skillsbench_runner_failure_v0",
            "exception_type": exception_type,
            "failure_class": runner_score_failure_attribution,
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }
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
            "source": "goal_harness_controller_trace",
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
        }
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
                "goal_harness_controller_trace_post_success_official_reward_recovery"
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
            "goal_harness_controller_trace_best_round_reward_post_success_acp_closeout"
        )
        validation_scope = (
            "official_benchflow_result_json_plus_goal_harness_controller_trace"
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
            "goal_harness_automation_loop": contract_goal_harness_automation_loop,
            "inner_codex_goal_mode": contract_inner_codex_goal_mode,
            "native_goal_mode_requested": contract_native_goal_mode_requested,
            "native_goal_mode_invoked": contract_native_goal_mode_invoked,
            "native_goal_mode_confirmation_status": contract_native_goal_mode_confirmation_status,
            "codex_acp_protocol_used": contract_codex_acp_protocol_used,
            "curated_skills_visible": contract_curated_skills_visible,
            "blind_loop": contract_blind_loop,
            "official_feedback_blinded": contract_official_feedback_blinded,
            "reward_feedback_forwarded": contract_reward_feedback_forwarded,
            "goal_harness_state_reads": controller_counters.get(
                "goal_harness_state_reads", 0
            ),
            "goal_harness_state_writes": controller_counters.get(
                "goal_harness_state_writes", 0
            ),
            "goal_harness_case_state_reads": controller_counters.get(
                "goal_harness_case_state_reads", 0
            ),
            "goal_harness_case_state_writes": controller_counters.get(
                "goal_harness_case_state_writes", 0
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
            "controller_official_feedback_forwarded": controller_counters.get(
                "official_feedback_forwarded", False
            ),
            "controller_blind_loop": controller_counters.get("blind_loop", False),
            "product_mode": controller_counters.get("product_mode", False),
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
            "case_goal_state_schema_version": controller_counters.get(
                "case_goal_state_schema_version", ""
            ),
            "case_goal_state_path": controller_counters.get(
                "case_goal_state_path", ""
            ),
            "declared_done_requires_no_remaining_goals": controller_counters.get(
                "declared_done_requires_no_remaining_goals", False
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
            "private_trajectory_summary_present": bool(trajectory_summary),
            "private_trajectory_event_count": trajectory_summary.get("event_count", 0),
            "private_trajectory_round_count": trajectory_summary.get("round_count", 0),
            "private_trajectory_tool_call_count": trajectory_summary.get(
                "tool_call_count", 0
            ),
            "goal_harness_cli_call_count": trajectory_summary.get(
                "goal_harness_cli_call_count", 0
            ),
            "goal_harness_cli_calls": trajectory_summary.get(
                "goal_harness_cli_calls", []
            ),
            "trajectory_action_category_counts": trajectory_summary.get(
                "action_category_counts", {}
            ),
            "goal_harness_cli_state_usage_counts": trajectory_summary.get(
                "goal_harness_cli_state_usage_counts", {}
            ),
            "goal_harness_cli_state_read_count": trajectory_summary.get(
                "goal_harness_cli_state_read_count", 0
            ),
            "goal_harness_cli_state_write_count": trajectory_summary.get(
                "goal_harness_cli_state_write_count", 0
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
            "native_goal_worker_ok_count": controller_counters.get(
                "native_goal_worker_ok_count", 0
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
            "goal_harness_case_state_path_count": trajectory_summary.get(
                "goal_harness_case_state_path_count", 0
            ),
            "goal_harness_case_state_read_count": trajectory_summary.get(
                "goal_harness_case_state_read_count", 0
            ),
            "goal_harness_case_state_write_count": trajectory_summary.get(
                "goal_harness_case_state_write_count", 0
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
            "goal_harness_controller_trace_present": controller_trace_present,
            "goal_harness_controller_trace_public_safe": not controller_raw_material_recorded,
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
            "goal_harness_inside_case": contract_goal_harness_inside_case,
            "goal_harness_automation_loop": contract_goal_harness_automation_loop,
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
            "official_score_comparable_to_goal_harness_treatment": contract_official_score_comparable_to_goal_harness_treatment,
            "leaderboard_evidence": False,
        },
        "evidence_files": evidence_files,
        "resume_or_inspect_commands": [
            (
                "goal-harness benchmark run skillsbench "
                "--skillsbench-result-json <official-skillsbench-result.json>"
            ),
            (
                "goal-harness benchmark run-ledger-upsert "
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
        "goal_harness_inside_case": contract_goal_harness_inside_case,
        "goal_harness_automation_loop": contract_goal_harness_automation_loop,
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
        "official_score_comparable_to_goal_harness_treatment": contract_official_score_comparable_to_goal_harness_treatment,
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
    if runner_failure is not None:
        benchmark_run["runner_failure"] = runner_failure
        benchmark_run["runner_failure_fingerprint"] = runner_failure_fingerprint
    if partial_trajectory:
        benchmark_run["failure_attribution_labels"].append("partial_trajectory")
    return benchmark_run


def skillsbench_recommended_action(*, route: str) -> str:
    contract = skillsbench_route_contract(route)
    return str(contract["next_action"])
