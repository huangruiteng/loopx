from __future__ import annotations

from typing import Any, Callable, Optional


CompactProjection = Callable[[Any], Optional[dict[str, Any]]]


def ordered_lifecycle_flags(
    flags: list[str],
    *,
    lifecycle_priority: tuple[str, ...],
) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for flag in flags:
        if not flag or flag in seen:
            continue
        seen.add(flag)
        deduped.append(flag)
    priority = {phase: index for index, phase in enumerate(lifecycle_priority)}
    return sorted(deduped, key=lambda phase: priority.get(phase, len(priority)))


def primary_lifecycle_phase(
    flags: list[str],
    *,
    lifecycle_priority: tuple[str, ...],
    fallback: str = "registered",
) -> str:
    ordered = ordered_lifecycle_flags(flags, lifecycle_priority=lifecycle_priority)
    return ordered[0] if ordered else fallback


def run_lifecycle_flags(
    run: dict[str, Any] | None,
    *,
    lifecycle_priority: tuple[str, ...],
    compact_human_reward: CompactProjection,
    compact_operator_gate: CompactProjection,
    compact_controller_readiness: CompactProjection,
) -> list[str]:
    if not isinstance(run, dict):
        return []

    flags: list[str] = []
    classification = str(run.get("classification") or "")
    if classification == "state_refreshed":
        flags.append("refreshed")
    elif classification == "read_only_project_map" or isinstance(run.get("project_map"), dict):
        flags.append("mapped")
    elif classification:
        flags.append("adapter_inspected")
    else:
        flags.append("run_recorded")

    if compact_human_reward(run.get("human_reward")):
        flags.append("reward_judged")

    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if operator_gate:
        if operator_gate.get("decision") == "approve":
            flags.append("operator_approved")
        else:
            flags.append("operator_gated")

    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if readiness:
        if readiness.get("decision_advisor_ready") or readiness.get("write_controller_ready"):
            flags.append("controller_ready")
        elif readiness.get("read_only_observer_ready") or readiness.get("classification"):
            flags.append("controller_gated")

    return ordered_lifecycle_flags(flags, lifecycle_priority=lifecycle_priority)


def run_lifecycle_phase(
    run: dict[str, Any] | None,
    *,
    lifecycle_priority: tuple[str, ...],
    compact_human_reward: CompactProjection,
    compact_operator_gate: CompactProjection,
    compact_controller_readiness: CompactProjection,
) -> str:
    return primary_lifecycle_phase(
        run_lifecycle_flags(
            run,
            lifecycle_priority=lifecycle_priority,
            compact_human_reward=compact_human_reward,
            compact_operator_gate=compact_operator_gate,
            compact_controller_readiness=compact_controller_readiness,
        ),
        lifecycle_priority=lifecycle_priority,
        fallback="run_recorded",
    )


def goal_lifecycle_fields(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    *,
    lifecycle_priority: tuple[str, ...],
    connected_adapter_statuses: set[str],
    compact_human_reward: CompactProjection,
    compact_operator_gate: CompactProjection,
    compact_controller_readiness: CompactProjection,
) -> dict[str, Any]:
    if current_run:
        flags = run_lifecycle_flags(
            current_run,
            lifecycle_priority=lifecycle_priority,
            compact_human_reward=compact_human_reward,
            compact_operator_gate=compact_operator_gate,
            compact_controller_readiness=compact_controller_readiness,
        )
        return {
            "lifecycle_phase": primary_lifecycle_phase(
                flags,
                lifecycle_priority=lifecycle_priority,
            ),
            "lifecycle_flags": flags,
        }

    adapter_status = str(goal.get("adapter_status") or "")
    status = str(goal.get("status") or "")
    if adapter_status in connected_adapter_statuses:
        flags = ["connected"]
    elif "planned" in status or adapter_status == "planned":
        flags = ["planned"]
    else:
        flags = ["registered"]
    flags = ordered_lifecycle_flags(flags, lifecycle_priority=lifecycle_priority)
    return {
        "lifecycle_phase": primary_lifecycle_phase(
            flags,
            lifecycle_priority=lifecycle_priority,
        ),
        "lifecycle_flags": flags,
    }
