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
LOOPX_TURN_RUNNER_READINESS_CHECKS = (
    "turn_transaction_committed",
    "independent_scored_workspace_validation_passed",
    "pre_agent_postcondition_checked",
    "pre_agent_postcondition_eligible",
    "post_agent_postcondition_validated",
    "post_agent_postcondition_satisfied",
    "official_feedback_blinded",
)
LOOPX_TURN_PROOF_CHECKS = (
    "turn_transaction_committed",
    "independent_scored_workspace_validation_passed",
    "pre_agent_postcondition_checked",
    "post_agent_postcondition_validated",
    "official_feedback_blinded",
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
            "run each host Agent CLI prompt through a bounded sequence of real "
            "case-local LoopX Turn transactions, continue only after independent "
            "progress validation, and emit compact public-safe receipt evidence"
        ),
    }


def skillsbench_loopx_turn_validation_signals() -> list[str]:
    return [
        "generic_agent_cli_actor",
        "real_loopx_turn_transaction",
        "isolated_headless",
        "independent_scored_workspace_validation",
        "official_feedback_withheld",
        "bounded_n_turn",
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
            "LoopX Turn Agent CLI route. It must be safe to run before and after "
            "each agent Turn; the pre-agent result qualifies the validation "
            "baseline without blocking later Turns whose overall postcondition "
            "is already satisfied. Per-Turn progress checks receive "
            "LOOPX_TURN_BASELINE_FILE; stability completion checks receive "
            "LOOPX_TURN_SEQUENCE_BASELINE_FILE. The command is executed only "
            "through the sandbox bridge and is never written to public compact "
            "traces."
        ),
    )
    parser.add_argument(
        "--loopx-turn-max-turns",
        type=int,
        default=1,
        help=(
            "Maximum independently validated Turns for the experimental LoopX "
            "Turn route. 1 preserves the single-Turn baseline."
        ),
    )
    parser.add_argument(
        "--loopx-turn-progress-exit-code",
        type=int,
        default=10,
        help=(
            "Private validator exit code meaning validated intermediate progress. "
            "Exit 0 means terminal completion; every other code fails closed."
        ),
    )
    parser.add_argument(
        "--loopx-turn-terminal-policy",
        choices=("validator", "fixed-n", "stability"),
        default="validator",
        help=(
            "How a successful per-Turn validator closes a bounded sequence. "
            "validator trusts exit 0 as terminal unless the Turn also proves "
            "a durable content change that requires one bounded review; fixed-n "
            "treats successful steps as progress until the configured final Turn; stability "
            "continues after exit-code progress or a verified write and stops "
            "after a no-change review whose completion postcondition passes."
        ),
    )


def skillsbench_loopx_turn_runner_prerequisites(
    route: str,
    validation_command: Any,
    *,
    max_turns: Any = 1,
    progress_exit_code: Any = 10,
    terminal_policy: Any = "validator",
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
        "loopx_turn_max_turns": (
            max_turns
            if enabled
            and isinstance(max_turns, int)
            and not isinstance(max_turns, bool)
            and max_turns >= 1
            else 0
        ),
        "loopx_turn_progress_exit_code_configured": bool(
            enabled
            and isinstance(progress_exit_code, int)
            and not isinstance(progress_exit_code, bool)
            and 1 <= progress_exit_code <= 255
        ),
        "loopx_turn_terminal_policy": (
            terminal_policy
            if enabled and terminal_policy in {"validator", "fixed-n", "stability"}
            else "not_applicable"
        ),
    }


def _public_label(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").strip().split())
    text = re.sub(r"[^A-Za-z0-9@._:+= -]+", "_", text)
    return text[:limit]


def _public_label_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [label for item in value[:12] if (label := _public_label(item, limit=limit))]


def _public_turn_sequence_ref(value: Any) -> str:
    label = _public_label(value, limit=80)
    if re.fullmatch(r"sequence:[0-9a-f]{16}", label):
        return label
    return ""


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
        for key in (
            "schema_version",
            "status",
            "validator_kind",
            "pre_agent_postcondition_status",
            "post_agent_postcondition_status",
            "baseline_contract",
            "sequence_stop_reason",
            "terminal_policy",
            "progress_evidence_kind",
        )
        if (label := _public_label(value.get(key), limit=120))
    }
    for key in (
        "independent",
        "pre_agent_postcondition_checked",
        "oracle_feedback_used",
        "raw_validator_output_recorded",
        "raw_task_text_recorded",
        "raw_verifier_output_recorded",
        "validated_progress",
        "terminal_complete",
        "sequence_terminal_complete",
        "sequence_baseline_configured",
        "stability_progress_detected",
        "stability_completion_checked",
        "stability_completion_satisfied",
    ):
        if isinstance(value.get(key), bool):
            validation[key] = value[key]
    operation_count = value.get("meaningful_operation_count")
    if isinstance(operation_count, int) and not isinstance(operation_count, bool):
        validation["meaningful_operation_count"] = max(0, operation_count)
    turn_index = value.get("turn_index")
    if isinstance(turn_index, int) and not isinstance(turn_index, bool):
        validation["turn_index"] = max(1, turn_index)
    if sequence_ref := _public_turn_sequence_ref(value.get("turn_sequence_ref")):
        validation["turn_sequence_ref"] = sequence_ref
    write_count = value.get("successful_task_file_write_count")
    if isinstance(write_count, int) and not isinstance(write_count, bool):
        validation["successful_task_file_write_count"] = max(0, write_count)
    change_count = value.get("successful_task_file_change_count")
    if isinstance(change_count, int) and not isinstance(change_count, bool):
        validation["successful_task_file_change_count"] = max(0, change_count)
    return validation


def _public_runner_readiness(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    receipt = {
        key: label
        for key in ("schema_version", "capability", "status", "evidence_kind")
        if (label := _public_label(value.get(key), limit=120))
    }
    if isinstance(value.get("ready"), bool):
        receipt["ready"] = value["ready"]
    if isinstance(value.get("turn_proven"), bool):
        receipt["turn_proven"] = value["turn_proven"]
    if sequence_ref := _public_turn_sequence_ref(value.get("turn_sequence_ref")):
        receipt["turn_sequence_ref"] = sequence_ref
    turn_index = value.get("turn_index")
    if isinstance(turn_index, int) and not isinstance(turn_index, bool):
        receipt["turn_index"] = max(1, turn_index)
    checks = value.get("checks")
    if isinstance(checks, dict):
        receipt["checks"] = {
            key: checks[key]
            for key in LOOPX_TURN_RUNNER_READINESS_CHECKS
            if isinstance(checks.get(key), bool)
        }
    blockers = [
        blocker
        for blocker in _public_label_list(value.get("blocker_codes"), limit=80)
        if blocker in LOOPX_TURN_RUNNER_READINESS_CHECKS
    ]
    if blockers:
        receipt["blocker_codes"] = blockers
    for key in (
        "raw_task_text_recorded",
        "raw_validator_output_recorded",
        "raw_verifier_output_recorded",
        "raw_trajectory_recorded",
        "credential_values_recorded",
        "local_paths_recorded",
    ):
        if isinstance(value.get(key), bool):
            receipt[key] = value[key]
    return receipt


def _aggregate_runner_readiness(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    ready_count = sum(item.get("ready") is True for item in receipts)
    committed_count = sum(
        isinstance(item.get("checks"), dict)
        and item["checks"].get("turn_transaction_committed") is True
        for item in receipts
    )
    proven_count = sum(
        item.get("turn_proven") is True
        or (
            not isinstance(item.get("turn_proven"), bool)
            and item.get("ready") is True
            and isinstance(item.get("checks"), dict)
            and item["checks"].get("turn_transaction_committed") is True
        )
        for item in receipts
    )
    blockers = sorted(
        {
            blocker
            for item in receipts
            for blocker in item.get("blocker_codes", [])
            if isinstance(blocker, str) and blocker
        }
    )
    aggregate = {
        "schema_version": "skillsbench_benchmark_runner_readiness_v0",
        "capability": "benchmark_runner",
        "status": "ready" if ready_count else "blocked",
        "ready": ready_count > 0,
        "runner_ready_turn_count": ready_count,
        "proven_turn_count": proven_count,
        "committed_turn_count": committed_count,
        "observed_turn_count": len(receipts),
        "blocker_codes": [] if ready_count else blockers,
        "raw_task_text_recorded": any(
            item.get("raw_task_text_recorded") is True for item in receipts
        ),
        "raw_validator_output_recorded": any(
            item.get("raw_validator_output_recorded") is True for item in receipts
        ),
        "raw_verifier_output_recorded": any(
            item.get("raw_verifier_output_recorded") is True for item in receipts
        ),
        "raw_trajectory_recorded": any(
            item.get("raw_trajectory_recorded") is True for item in receipts
        ),
        "credential_values_recorded": any(
            item.get("credential_values_recorded") is True for item in receipts
        ),
        "local_paths_recorded": any(
            item.get("local_paths_recorded") is True for item in receipts
        ),
    }
    receipts_by_sequence: dict[str, dict[int, list[dict[str, Any]]]] = {}
    unattributed_turn_count = 0
    unindexed_sequence_turn_count = 0
    for item in receipts:
        sequence_ref = _public_turn_sequence_ref(item.get("turn_sequence_ref"))
        if not sequence_ref:
            unattributed_turn_count += 1
            continue
        turn_index = item.get("turn_index")
        if not isinstance(turn_index, int) or isinstance(turn_index, bool):
            unindexed_sequence_turn_count += 1
            continue
        receipts_by_sequence.setdefault(sequence_ref, {}).setdefault(
            max(1, turn_index), []
        ).append(item)
    if receipts_by_sequence:
        committed_by_sequence = [
            sum(
                all(
                    isinstance(item.get("checks"), dict)
                    and item["checks"].get("turn_transaction_committed") is True
                    for item in turn_receipts
                )
                for turn_receipts in sequence_receipts.values()
            )
            for sequence_receipts in receipts_by_sequence.values()
        ]
        aggregate.update(
            {
                "turn_sequence_count": len(receipts_by_sequence),
                "turn_sequence_refs": sorted(receipts_by_sequence)[:12],
                "max_observed_turn_count_per_sequence": max(
                    len(sequence_receipts)
                    for sequence_receipts in receipts_by_sequence.values()
                ),
                "max_committed_turn_count_per_sequence": max(committed_by_sequence),
                "multi_turn_sequence_committed": max(committed_by_sequence) >= 2,
                "unattributed_turn_count": unattributed_turn_count,
                "unindexed_sequence_turn_count": unindexed_sequence_turn_count,
            }
        )
    return aggregate


def _aggregate_validations(validations: list[dict[str, Any]]) -> dict[str, Any]:
    terminal_policies = {
        item["terminal_policy"]
        for item in validations
        if item.get("terminal_policy") in {"validator", "fixed-n", "stability"}
    }
    aggregate = {
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
        "validated_progress": bool(
            validations
            and all(item.get("validated_progress") is True for item in validations)
        ),
        "terminal_complete": any(
            (
                item.get("sequence_terminal_complete")
                if isinstance(item.get("sequence_terminal_complete"), bool)
                else item.get("terminal_complete")
            )
            is True
            for item in validations
        ),
        "turn_count": len(validations),
        "successful_task_file_write_count": sum(
            max(0, int(item.get("successful_task_file_write_count") or 0))
            for item in validations
            if not isinstance(item.get("successful_task_file_write_count"), bool)
        ),
        "successful_task_file_change_count": sum(
            max(0, int(item.get("successful_task_file_change_count") or 0))
            for item in validations
            if not isinstance(item.get("successful_task_file_change_count"), bool)
        ),
    }
    progress_evidence_kinds = {
        str(item.get("progress_evidence_kind") or "")
        for item in validations
        if item.get("progress_evidence_kind")
    }
    if len(progress_evidence_kinds) == 1:
        aggregate["progress_evidence_kind"] = progress_evidence_kinds.pop()
    elif progress_evidence_kinds:
        aggregate["progress_evidence_kind"] = "mixed"
    if len(terminal_policies) == 1:
        aggregate["terminal_policy"] = terminal_policies.pop()
    if validations and validations[-1].get("terminal_policy") == "stability":
        final_validation = validations[-1]
        for key in (
            "sequence_baseline_configured",
            "stability_progress_detected",
            "stability_completion_checked",
            "stability_completion_satisfied",
        ):
            if isinstance(final_validation.get(key), bool):
                aggregate[key] = final_validation[key]
        aggregate["stability_repair_turn_count"] = sum(
            item.get("stability_progress_detected") is True for item in validations
        )
    if validations and validations[-1].get("sequence_stop_reason"):
        aggregate["sequence_stop_reason"] = validations[-1]["sequence_stop_reason"]
    return aggregate


@dataclass
class SkillsBenchTurnTraceSummary:
    executions: list[dict[str, Any]] = field(default_factory=list)
    validations: list[dict[str, Any]] = field(default_factory=list)
    readiness_receipts: list[dict[str, Any]] = field(default_factory=list)
    boundary: dict[str, bool] = field(
        default_factory=lambda: dict.fromkeys(LOOPX_TURN_PUBLIC_BOUNDARY_FIELDS, False)
    )

    def merge(self, payload: Mapping[str, Any], boundary: Mapping[str, Any]) -> None:
        if execution := _public_execution(payload.get("loopx_turn_execution")):
            self.executions.append(execution)
        if validation := _public_validation(payload.get("scored_workspace_validation")):
            self.validations.append(validation)
        if readiness := _public_runner_readiness(
            payload.get("benchmark_runner_readiness")
        ):
            self.readiness_receipts.append(readiness)
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
        if self.readiness_receipts:
            trace["benchmark_runner_readiness"] = _aggregate_runner_readiness(
                self.readiness_receipts
            )
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
    readiness = trace.get("benchmark_runner_readiness")
    if isinstance(readiness, dict):
        compact["benchmark_runner_readiness"] = dict(readiness)
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
    max_turns = getattr(args, "loopx_turn_max_turns", 1)
    if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
        return {
            **common,
            "error_type": "SkillsBenchLoopXTurnMaxTurnsInvalid",
            "reason": "LoopX Turn treatment requires max Turns of at least one",
            "next_action": "configure --loopx-turn-max-turns with a positive integer",
        }
    progress_exit_code = getattr(args, "loopx_turn_progress_exit_code", 10)
    if (
        not isinstance(progress_exit_code, int)
        or isinstance(progress_exit_code, bool)
        or not 1 <= progress_exit_code <= 255
    ):
        return {
            **common,
            "error_type": "SkillsBenchLoopXTurnProgressExitCodeInvalid",
            "reason": "validated progress requires a private exit code from 1 to 255",
            "next_action": "configure --loopx-turn-progress-exit-code from 1 to 255",
        }
    terminal_policy = getattr(args, "loopx_turn_terminal_policy", "validator")
    if terminal_policy not in {"validator", "fixed-n", "stability"}:
        return {
            **common,
            "error_type": "SkillsBenchLoopXTurnTerminalPolicyInvalid",
            "reason": (
                "LoopX Turn terminal policy must be validator, fixed-n, or stability"
            ),
            "next_action": "configure --loopx-turn-terminal-policy explicitly",
        }
    return None
