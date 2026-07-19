"""SkillsBench route and public evidence helpers for LoopX Turn."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


LOOPX_TURN_PUBLIC_BOUNDARY_FIELDS = (
    "raw_task_text_recorded",
    "raw_verifier_output_recorded",
    "raw_agent_trajectory_recorded",
    "raw_host_output_recorded",
    "credentials_recorded",
    "local_paths_recorded",
)


def skillsbench_loopx_turn_route_contract() -> dict[str, Any]:
    return {
        "mode": "skillsbench_loopx_turn_agent_cli_treatment",
        "arm_id": "loopx_turn_agent_cli",
        "source_runner": "loopx_skillsbench_turn_agent_cli_runtime",
        "inner_codex_goal_mode": False,
        "native_goal_mode_requested": False,
        "native_goal_mode_invoked": False,
        "native_goal_mode_confirmation_status": "not_requested",
        "codex_acp_protocol_used": True,
        "skillsbench_route_semantics": (
            "host_agent_cli_inside_real_case_local_loopx_turn_with_"
            "independent_scored_workspace_validation_no_reward_feedback"
        ),
        "curated_skills_visible": False,
        "loopx_automation_loop": True,
        "loopx_inside_case": True,
        "loopx_turn_transaction_required": True,
        "loopx_turn_execution_mode": "isolated-headless",
        "loopx_turn_host_kind": "generic-cli",
        "independent_scored_workspace_validation_required": True,
        "product_mode": True,
        "blind_loop": False,
        "official_feedback_blinded": True,
        "reward_feedback_forwarded": False,
        "case_semantics_changed_by_harness": False,
        "official_score_comparable_to_native_codex": True,
        "official_score_comparable_to_loopx_treatment": True,
        "first_blocker": "none",
        "next_action": (
            "run each host Agent CLI prompt through one real case-local LoopX "
            "Turn transaction, validate a private scored-workspace postcondition "
            "independently, and emit only compact public-safe receipt evidence"
        ),
    }


def skillsbench_loopx_turn_validation_signals() -> list[str]:
    return [
        "generic_agent_cli_actor",
        "real_loopx_turn_transaction",
        "isolated_headless",
        "independent_scored_workspace_validation",
        "official_feedback_withheld",
        "fixture_only",
        "no_upload",
        "single_task_planned",
    ]


def add_skillsbench_loopx_turn_arguments(parser: Any) -> None:
    parser.add_argument(
        "--loopx-turn-validation-command",
        default=None,
        help=(
            "Private scored-workspace postcondition command for the experimental "
            "LoopX Turn Agent CLI route. The command is executed only through "
            "the sandbox bridge and is never written to public compact traces."
        ),
    )


def skillsbench_loopx_turn_runner_prerequisites(
    route: str,
    validation_command: Any,
) -> dict[str, Any]:
    enabled = route == "loopx-turn-agent-cli"
    return {
        "loopx_turn_agent_cli": enabled,
        "loopx_turn_execution_mode": "isolated-headless"
        if enabled
        else "not_applicable",
        "loopx_turn_validation_required": enabled,
        "loopx_turn_validation_configured": bool(
            enabled and str(validation_command or "").strip()
        ),
        "loopx_turn_validation_command_recorded": False,
    }


def _public_label(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").strip().split())
    text = re.sub(r"[^A-Za-z0-9@._:+= -]+", "_", text)
    return text[:limit]


def _public_label_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [label for item in value[:12] if (label := _public_label(item, limit=limit))]


def _public_execution(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    execution: dict[str, Any] = {}
    for key in (
        "schema_version",
        "mode",
        "status",
        "execution_mode",
        "result_kind",
    ):
        if label := _public_label(value.get(key), limit=120):
            execution[key] = label
    for key in ("execute", "replayed"):
        if isinstance(value.get(key), bool):
            execution[key] = value[key]
    quota_count = value.get("quota_slot_spend_count")
    if isinstance(quota_count, int) and not isinstance(quota_count, bool):
        execution["quota_slot_spend_count"] = max(0, quota_count)

    host = value.get("host") if isinstance(value.get("host"), dict) else {}
    public_host = {
        key: label
        for key in ("kind", "executable")
        if (label := _public_label(host.get(key), limit=80))
    }
    if isinstance(host.get("argv"), list):
        public_host["argv_count"] = len(host["argv"])
    if public_host:
        execution["host"] = public_host

    validation = value.get("validation")
    if isinstance(validation, dict):
        public_validation = {
            key: label
            for key in (
                "schema_version",
                "status",
                "validator_kind",
                "summary",
                "recovery_kind",
            )
            if (label := _public_label(validation.get(key), limit=160))
        }
        exit_code = validation.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            public_validation["exit_code"] = exit_code
        if public_validation:
            execution["validation"] = public_validation

    receipt = value.get("receipt")
    if isinstance(receipt, dict):
        public_receipt = {
            key: label
            for key in (
                "schema_version",
                "status",
                "result_kind",
                "failed_phase",
                "next_phase",
            )
            if (label := _public_label(receipt.get(key), limit=120))
        }
        phases = _public_label_list(receipt.get("completed_phases"), limit=80)
        if phases:
            public_receipt["completed_phases"] = phases
        if public_receipt:
            execution["receipt"] = public_receipt

    failure = value.get("failure")
    if isinstance(failure, dict):
        public_failure: dict[str, Any] = {}
        if category := _public_label(failure.get("category"), limit=120):
            public_failure["category"] = category
        exit_code = failure.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            public_failure["exit_code"] = exit_code
        if public_failure:
            execution["failure"] = public_failure

    effects = value.get("effects")
    if isinstance(effects, dict):
        execution["effects"] = {
            key: effects.get(key) is True
            for key in (
                "host_invoked",
                "state_written",
                "quota_spent",
                "scheduler_acknowledged",
            )
        }
    return execution


def _public_validation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    validation = {
        key: label
        for key in ("schema_version", "status", "validator_kind")
        if (label := _public_label(value.get(key), limit=120))
    }
    for key in (
        "independent",
        "oracle_feedback_used",
        "raw_validator_output_recorded",
        "raw_task_text_recorded",
        "raw_verifier_output_recorded",
    ):
        if isinstance(value.get(key), bool):
            validation[key] = value[key]
    operation_count = value.get("meaningful_operation_count")
    if isinstance(operation_count, int) and not isinstance(operation_count, bool):
        validation["meaningful_operation_count"] = max(0, operation_count)
    return validation


def _aggregate_validations(validations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "skillsbench_scored_workspace_validation_v0",
        "status": (
            "passed"
            if validations
            and all(item.get("status") == "passed" for item in validations)
            else "failed"
        ),
        "independent": bool(
            validations and all(item.get("independent") is True for item in validations)
        ),
        "validator_kind": "skillsbench_scored_workspace_command",
        "oracle_feedback_used": any(
            item.get("oracle_feedback_used") is True for item in validations
        ),
        "meaningful_operation_count": sum(
            max(0, int(item.get("meaningful_operation_count") or 0))
            for item in validations
            if not isinstance(item.get("meaningful_operation_count"), bool)
        ),
        "raw_validator_output_recorded": any(
            item.get("raw_validator_output_recorded") is True for item in validations
        ),
        "raw_task_text_recorded": any(
            item.get("raw_task_text_recorded") is True for item in validations
        ),
        "raw_verifier_output_recorded": any(
            item.get("raw_verifier_output_recorded") is True for item in validations
        ),
    }


@dataclass
class SkillsBenchTurnTraceSummary:
    executions: list[dict[str, Any]] = field(default_factory=list)
    validations: list[dict[str, Any]] = field(default_factory=list)
    boundary: dict[str, bool] = field(
        default_factory=lambda: dict.fromkeys(LOOPX_TURN_PUBLIC_BOUNDARY_FIELDS, False)
    )

    def merge(self, payload: Mapping[str, Any], boundary: Mapping[str, Any]) -> None:
        if execution := _public_execution(payload.get("loopx_turn_execution")):
            self.executions.append(execution)
        if validation := _public_validation(payload.get("scored_workspace_validation")):
            self.validations.append(validation)
        source_fields = {
            "raw_task_text_recorded": ("raw_task_text_recorded",),
            "raw_verifier_output_recorded": ("raw_verifier_output_recorded",),
            "raw_agent_trajectory_recorded": ("raw_trajectory_recorded",),
            "raw_host_output_recorded": ("raw_stdout_recorded", "raw_stderr_recorded"),
            "credentials_recorded": ("credential_values_recorded",),
            "local_paths_recorded": ("host_paths_recorded", "remote_paths_recorded"),
        }
        for target, sources in source_fields.items():
            self.boundary[target] |= any(boundary.get(key) is True for key in sources)

    def apply(self, trace: dict[str, Any]) -> None:
        if not self.executions:
            return
        trace["loopx_turn_executions"] = list(self.executions)
        trace["scored_workspace_validation"] = _aggregate_validations(self.validations)
        trace["loopx_turn_public_boundary"] = dict(self.boundary)
        trace["official_feedback_blinded"] = True
        trace["reward_feedback_forwarded"] = False


def sync_skillsbench_loopx_turn_trace_into_compact(
    compact: dict[str, Any],
    trace: Mapping[str, Any] | None,
) -> None:
    if not isinstance(trace, Mapping):
        return
    executions = trace.get("loopx_turn_executions")
    if not isinstance(executions, list) or not executions:
        return
    compact["loopx_turn_executions"] = [
        dict(item) for item in executions if isinstance(item, dict)
    ]
    validation = trace.get("scored_workspace_validation")
    if isinstance(validation, dict):
        compact["scored_workspace_validation"] = dict(validation)
    trace_boundary = trace.get("loopx_turn_public_boundary")
    trace_boundary = trace_boundary if isinstance(trace_boundary, dict) else {}
    boundary = compact.get("public_boundary")
    boundary = dict(boundary) if isinstance(boundary, dict) else {}
    for key in LOOPX_TURN_PUBLIC_BOUNDARY_FIELDS:
        boundary[key] = bool(
            boundary.get(key) is True or trace_boundary.get(key) is True
        )
    compact["public_boundary"] = boundary
    compact["official_feedback_blinded"] = True
    compact["reward_feedback_forwarded"] = False


def skillsbench_loopx_turn_launch_error(args: Any) -> dict[str, Any] | None:
    if str(getattr(args, "route", "") or "") != "loopx-turn-agent-cli":
        return None
    inspection_only = any(
        bool(getattr(args, key, False))
        for key in (
            "local_driver_worker_handshake_preflight",
            "plan_only",
            "reduce_only",
            "setup_only_public_preflight",
        )
    )
    if inspection_only:
        return None
    common = {
        "ok": False,
        "route": args.route,
        "raw_logs_recorded": False,
        "raw_task_text_read": False,
        "raw_trajectory_recorded": False,
        "credential_values_recorded": False,
    }
    if not bool(getattr(args, "host_local_acp_launch", False)):
        return {
            **common,
            "error_type": "SkillsBenchLoopXTurnCanonicalDriverRequired",
            "reason": (
                "LoopX Turn treatment must run through the host-local Agent CLI "
                "relay while case-local Turn state remains in the scored sandbox."
            ),
            "next_action": (
                "rerun with --host-local-acp-launch, a materialized command/file "
                "bridge, and --loopx-turn-validation-command"
            ),
        }
    if not str(getattr(args, "loopx_turn_validation_command", "") or "").strip():
        return {
            **common,
            "error_type": "SkillsBenchLoopXTurnValidationRequired",
            "reason": (
                "countable LoopX Turn treatment requires an independent scored-"
                "workspace postcondition before writeback and quota spend"
            ),
            "next_action": "configure --loopx-turn-validation-command",
            "validation_command_recorded": False,
        }
    return None
