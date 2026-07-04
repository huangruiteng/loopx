from __future__ import annotations

from typing import Any, Callable, Optional


HUMAN_REWARD_COMPACT_FIELDS = (
    "recorded_at",
    "decision",
    "reward",
    "reason_summary",
    "follow_up",
    "lesson",
)
OPERATOR_GATE_COMPACT_FIELDS = (
    "recorded_at",
    "gate",
    "decision",
    "operator_question",
    "reason_summary",
    "follow_up",
    "agent_command",
)
OPERATOR_GATE_RESUME_CONTRACT_COMPACT_FIELDS = (
    "version",
    "goal_id",
    "run_id",
    "gate_id",
    "created_state_ref",
    "created_policy_version",
    "allowed_decisions",
    "operator_decision",
    "latest_state_ref",
    "freshness_check",
    "precondition_check",
    "migration_or_rebase_result",
    "resulting_action",
    "validation_after_resume",
)
CONTROLLER_READINESS_COMPACT_FIELDS = (
    "classification",
    "read_only_observer_ready",
    "decision_advisor_ready",
    "write_controller_ready",
    "missing_gates",
    "review_judgment",
    "next_handoff_condition",
)
CONTROLLER_READINESS_GATE_FIELDS = (
    "id",
    "ok",
    "review",
)

CompactProjection = Callable[[Any], Optional[dict[str, Any]]]
LifecycleFlags = Callable[[Optional[dict[str, Any]]], list[str]]
PrimaryLifecyclePhase = Callable[..., str]
TextCompactor = Callable[..., Any]
RunProjection = Callable[[dict[str, Any]], Optional[dict[str, Any]]]
SubagentRunCompactor = Callable[..., Optional[dict[str, Any]]]


def compact_human_reward(reward: Any) -> dict[str, Any] | None:
    if not isinstance(reward, dict):
        return None
    compact = {field: reward[field] for field in HUMAN_REWARD_COMPACT_FIELDS if field in reward}
    lesson = compact.get("lesson")
    if isinstance(lesson, dict):
        compact["lesson"] = {
            field: lesson[field]
            for field in ("schema_version", "kind", "summary", "avoid", "prefer")
            if field in lesson
        }
    return compact or None


def compact_operator_gate(operator_gate: Any) -> dict[str, Any] | None:
    if not isinstance(operator_gate, dict):
        return None
    compact = {field: operator_gate[field] for field in OPERATOR_GATE_COMPACT_FIELDS if field in operator_gate}
    return compact or None


def compact_operator_gate_resume_contract(contract: Any) -> dict[str, Any] | None:
    if not isinstance(contract, dict):
        return None
    compact = {
        field: contract[field]
        for field in OPERATOR_GATE_RESUME_CONTRACT_COMPACT_FIELDS
        if field in contract
    }
    interrupt = contract.get("interrupt_payload") if isinstance(contract.get("interrupt_payload"), dict) else {}
    if interrupt:
        compact["interrupt_payload"] = {
            field: interrupt[field]
            for field in ("question", "choices")
            if field in interrupt
        }
    return compact or None


def compact_controller_readiness(readiness: Any) -> dict[str, Any] | None:
    if not isinstance(readiness, dict):
        return None
    compact = {
        field: readiness[field]
        for field in CONTROLLER_READINESS_COMPACT_FIELDS
        if field in readiness
    }
    gates = []
    for gate in readiness.get("gates") or []:
        if not isinstance(gate, dict):
            continue
        gates.append({field: gate[field] for field in CONTROLLER_READINESS_GATE_FIELDS if field in gate})
    if gates:
        compact["gates"] = gates
    return compact or None


def compact_run_base(
    run: dict[str, Any],
    *,
    run_compact_fields: tuple[str, ...],
    run_lifecycle_flags: LifecycleFlags,
    primary_lifecycle_phase: PrimaryLifecyclePhase,
    compact_human_reward: CompactProjection,
    compact_operator_gate: CompactProjection,
    compact_autonomous_replan_ack: RunProjection,
    compact_operator_gate_resume_contract: CompactProjection,
    compact_controller_readiness: CompactProjection,
    public_safe_compact_text: TextCompactor,
    compact_subagent_run: SubagentRunCompactor,
    max_subagent_activity_items: int,
) -> dict[str, Any]:
    compact = {field: run[field] for field in run_compact_fields if field in run}
    flags = run_lifecycle_flags(run)
    compact.setdefault("lifecycle_phase", primary_lifecycle_phase(flags, fallback="run_recorded"))
    compact.setdefault("lifecycle_flags", flags)

    reward = compact_human_reward(run.get("human_reward"))
    if reward:
        compact["human_reward"] = reward

    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if operator_gate:
        compact["operator_gate"] = operator_gate

    replan_ack = compact_autonomous_replan_ack(run)
    if replan_ack:
        compact["autonomous_replan_ack"] = replan_ack

    resume_contract = compact_operator_gate_resume_contract(run.get("operator_gate_resume_contract"))
    if resume_contract:
        compact["operator_gate_resume_contract"] = resume_contract

    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if readiness:
        compact["controller_readiness"] = readiness

    merge_decision = public_safe_compact_text(run.get("merge_decision"), limit=240)
    if merge_decision:
        compact["merge_decision"] = merge_decision

    subagents = [
        child
        for child in (
            compact_subagent_run(
                child_run,
                parent_goal_id=str(run.get("goal_id") or ""),
                parent_run_id=str(run.get("run_id") or run.get("generated_at") or ""),
            )
            for child_run in (run.get("subagents") or [])
            if isinstance(child_run, dict)
        )
        if child
    ]
    if subagents:
        compact["subagents"] = subagents[:max_subagent_activity_items]
        compact["subagent_count"] = len(subagents)

    return compact
