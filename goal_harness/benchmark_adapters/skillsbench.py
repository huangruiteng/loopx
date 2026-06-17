from __future__ import annotations

import re
from typing import Any

from ..benchmark_case_state import benchmark_case_active_state_path


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
    "codex-goal-mode-baseline",
    "automation-loop-treatment",
    "curated-skills-baseline",
    "raw-codex-autonomous-max5",
    "goal-harness-product-mode",
)
SKILLSBENCH_DEFAULT_ROUTE = "goal-harness-blind-loop-treatment"


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
