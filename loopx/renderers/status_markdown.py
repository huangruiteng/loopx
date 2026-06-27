from __future__ import annotations

from collections.abc import Collection
from typing import Any


def markdown_scalar(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def goals_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    run_history = payload.get("run_history") if isinstance(payload.get("run_history"), dict) else {}
    goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        goal_id = str(goal.get("id") or "")
        if goal_id:
            result[goal_id] = goal
    return result


def authority_registry_markdown_summary(goal: dict[str, Any] | None) -> str | None:
    registry = goal.get("authority_registry") if isinstance(goal, dict) else None
    if not isinstance(registry, dict) or not registry.get("declared"):
        return None
    materials = int(registry.get("project_material_count") or 0)
    topics = int(registry.get("topic_authority_count") or 0)
    if materials <= 0 and topics <= 0:
        return None
    return (
        f"entries={int(registry.get('default_entries_present') or 0)}/"
        f"{int(registry.get('default_entry_count') or 0)} "
        f"topics={topics} "
        f"materials={materials} "
        f"repositories={int(registry.get('project_material_repository_count') or 0)} "
        f"owner_review_required={int(registry.get('project_material_owner_review_required_count') or 0)} "
        f"stale={int(registry.get('project_material_stale_count') or 0)} "
        f"current_authority={int(registry.get('project_material_current_authority_count') or 0)} "
        f"risk={markdown_scalar(registry.get('conflict_risk') or 'unknown')}"
    )


def append_human_reward_markdown(lines: list[str], goal_id: Any, reward: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("recorded_at", "decision", "reward"):
        value = reward.get(field)
        if value:
            headline_parts.append(f"{field}={markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - human_reward: {' '.join(headline_parts)}")
    reason = reward.get("reason_summary")
    if reason:
        lines.append(f"      - reason_summary: {markdown_scalar(reason)}")
    follow_up = reward.get("follow_up")
    if follow_up:
        lines.append(f"      - follow_up: {markdown_scalar(follow_up)}")
    lesson = reward.get("lesson") if isinstance(reward.get("lesson"), dict) else {}
    if lesson:
        lines.append(
            "      - lesson: "
            f"kind={markdown_scalar(lesson.get('kind') or '')} "
            f"summary={markdown_scalar(lesson.get('summary') or '')}"
        )
        for field in ("avoid", "prefer"):
            values = lesson.get(field) if isinstance(lesson.get(field), list) else []
            if values:
                lines.append(
                    f"        - lesson_{field}: "
                    + ", ".join(markdown_scalar(value) for value in values[:5])
                )
    if goal_id:
        lines.append(
            "      - project_agent_visibility: "
            f"`loopx history --goal-id {markdown_scalar(goal_id)} --limit 3`"
        )


def append_operator_gate_resume_contract_markdown(lines: list[str], contract: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("version", "gate_id", "operator_decision"):
        value = contract.get(field)
        if value:
            headline_parts.append(f"{field}={markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - operator_gate_resume_contract: {' '.join(headline_parts)}")
    for field in (
        "latest_state_ref",
        "freshness_check",
        "precondition_check",
        "migration_or_rebase_result",
        "validation_after_resume",
    ):
        value = contract.get(field)
        if value:
            lines.append(f"      - {field}: {markdown_scalar(value)}")


def event_class_count_text(counts: dict[str, Any], event_classes: Collection[str]) -> str:
    return " ".join(
        f"{event_class}={counts.get(event_class, 0)}"
        for event_class in event_classes
    )


def append_event_ledger_summary_markdown(
    lines: list[str],
    event_ledger: dict[str, Any],
    *,
    event_classes: Collection[str],
) -> None:
    event_totals = (
        event_ledger.get("totals")
        if isinstance(event_ledger.get("totals"), dict)
        else {}
    )
    if not event_ledger.get("available") or not event_totals:
        return

    by_class_24h = (
        event_totals.get("by_class_24h")
        if isinstance(event_totals.get("by_class_24h"), dict)
        else {}
    )
    by_class_7d = (
        event_totals.get("by_class_7d")
        if isinstance(event_totals.get("by_class_7d"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## Event Ledger Summary",
            "- summary: "
            f"source={markdown_scalar(event_ledger.get('source') or '')} "
            f"samples={event_ledger.get('sample_run_count')} "
            f"events_24h={event_totals.get('events_24h')} "
            f"events_7d={event_totals.get('events_7d')} "
            f"benchmark_runs_24h={event_totals.get('benchmark_runs_24h', 0)} "
            f"benchmark_runs_7d={event_totals.get('benchmark_runs_7d', 0)} "
            f"classes_24h={event_class_count_text(by_class_24h, event_classes)} "
            f"classes_7d={event_class_count_text(by_class_7d, event_classes)}",
        ]
    )

    event_goals = (
        event_ledger.get("goals")
        if isinstance(event_ledger.get("goals"), list)
        else []
    )
    for goal in event_goals[:3]:
        if not isinstance(goal, dict):
            continue
        goal_by_class_24h = (
            goal.get("by_class_24h")
            if isinstance(goal.get("by_class_24h"), dict)
            else {}
        )
        lines.append(
            "- "
            f"`{markdown_scalar(goal.get('goal_id') or '')}`: "
            f"events_24h={goal.get('events_24h')} "
            f"events_7d={goal.get('events_7d')} "
            f"benchmark_runs_24h={goal.get('benchmark_runs_24h', 0)} "
            f"benchmark_runs_7d={goal.get('benchmark_runs_7d', 0)} "
            f"latest={markdown_scalar(goal.get('latest_event_class') or '')} "
            f"classes_24h={event_class_count_text(goal_by_class_24h, event_classes)}"
        )


def append_promotion_readiness_summary_markdown(
    lines: list[str],
    promotion_readiness: dict[str, Any],
) -> None:
    if not promotion_readiness:
        return
    lines.extend(
        [
            "",
            "## Promotion Readiness Summary",
            "- summary: "
            f"source={markdown_scalar(promotion_readiness.get('source') or '')} "
            f"available={promotion_readiness.get('available')} "
            f"samples={promotion_readiness.get('sample_run_count')} "
            f"freshness={markdown_scalar(promotion_readiness.get('freshness_status') or '')} "
            f"age_hours={promotion_readiness.get('age_hours')} "
            f"requires_readiness_run={promotion_readiness.get('requires_readiness_run')} "
            f"window_hours={promotion_readiness.get('freshness_window_hours')}",
            "- latest: "
            f"goal={markdown_scalar(promotion_readiness.get('goal_id') or '')} "
            f"generated_at={markdown_scalar(promotion_readiness.get('generated_at') or '')} "
            f"classification={markdown_scalar(promotion_readiness.get('classification') or '')} "
            f"outcome={markdown_scalar(promotion_readiness.get('delivery_outcome') or '')} "
            f"artifacts={promotion_readiness.get('json_exists')}/{promotion_readiness.get('markdown_exists')}",
        ]
    )


def append_promotion_gate_markdown(
    lines: list[str],
    promotion_gate: dict[str, Any],
) -> None:
    if not promotion_gate:
        return
    promotion_gate_readiness = (
        promotion_gate.get("readiness")
        if isinstance(promotion_gate.get("readiness"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## Promotion Gate",
            "- gate: "
            f"state={markdown_scalar(promotion_gate.get('gate_state') or '')} "
            f"can_promote={promotion_gate.get('can_promote')} "
            f"should_warn={promotion_gate.get('should_warn')} "
            f"non_blocking={promotion_gate.get('non_blocking')} "
            f"freshness={markdown_scalar(promotion_gate_readiness.get('freshness_status') or '')} "
            f"requires_readiness_run={promotion_gate_readiness.get('requires_readiness_run')}",
            "- latest: "
            f"generated_at={markdown_scalar(promotion_gate_readiness.get('generated_at') or '')} "
            f"age_hours={promotion_gate_readiness.get('age_hours')} "
            f"action={markdown_scalar(promotion_gate.get('recommended_action') or '')}",
        ]
    )
    if promotion_gate.get("warning_message"):
        lines.append(
            "- warning: "
            f"{markdown_scalar(promotion_gate.get('warning_message') or '')}"
        )
