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


def append_decision_freshness_summary_markdown(
    lines: list[str],
    decision_freshness: dict[str, Any],
) -> None:
    decision_summary = (
        decision_freshness.get("summary")
        if isinstance(decision_freshness.get("summary"), dict)
        else {}
    )
    if not decision_freshness.get("available") or not decision_summary:
        return

    lines.extend(
        [
            "",
            "## Decision Freshness Summary",
            "- summary: "
            f"source={markdown_scalar(decision_freshness.get('source') or '')} "
            f"samples={decision_freshness.get('sample_run_count')} "
            f"window_days={decision_freshness.get('window_days')} "
            f"decisions={decision_summary.get('decision_count')} "
            f"stale={decision_summary.get('stale_count')} "
            f"rebase_required={decision_summary.get('rebase_required_count')} "
            f"fresh={decision_summary.get('fresh_count')}",
        ]
    )
    decision_items = (
        decision_freshness.get("items")
        if isinstance(decision_freshness.get("items"), list)
        else []
    )
    for item in decision_items[:3]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- "
            f"`{markdown_scalar(item.get('goal_id') or '')}`: "
            f"kind={markdown_scalar(item.get('decision_kind') or '')} "
            f"state={markdown_scalar(item.get('freshness_state') or '')} "
            f"age_days={item.get('age_days')} "
            f"newer_7d={item.get('newer_event_count_7d')} "
            f"decision_at={markdown_scalar(item.get('decision_at') or '')}"
        )


def append_usage_summary_markdown(lines: list[str], usage: dict[str, Any]) -> None:
    usage_totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    if not usage.get("available") or not usage_totals:
        return

    lines.extend(
        [
            "",
            "## Usage Summary",
            "- summary: "
            f"source={markdown_scalar(usage.get('source') or '')} "
            f"samples={usage.get('sample_run_count')} "
            f"runs_24h={usage_totals.get('runs_24h')} "
            f"runs_7d={usage_totals.get('runs_7d')} "
            f"quota_slots_24h={usage_totals.get('quota_spend_slots_24h')} "
            f"quota_slots_7d={usage_totals.get('quota_spend_slots_7d')} "
            f"automation_24h={usage_totals.get('automation_run_count_24h')} "
            f"automation_7d={usage_totals.get('automation_run_count_7d')} "
            f"progress_signals_24h={usage_totals.get('progress_signal_run_count_24h')} "
            f"progress_signals_7d={usage_totals.get('progress_signal_run_count_7d')}",
        ]
    )
    usage_goals = usage.get("goals") if isinstance(usage.get("goals"), list) else []
    for goal in usage_goals[:3]:
        if not isinstance(goal, dict):
            continue
        lines.append(
            "- "
            f"`{markdown_scalar(goal.get('goal_id') or '')}`: "
            f"runs_24h={goal.get('runs_24h')} "
            f"runs_7d={goal.get('runs_7d')} "
            f"quota_slots_24h={goal.get('quota_spend_slots_24h')} "
            f"automation_24h={goal.get('automation_run_count_24h')} "
            f"progress_signals_24h={goal.get('progress_signal_run_count_24h')} "
            f"share_24h={goal.get('project_share_24h')}"
        )


def append_attention_queue_summary_markdown(
    lines: list[str],
    queue: dict[str, Any],
) -> None:
    lines.extend(
        [
            "",
            "## Attention Queue",
            "- summary: "
            f"items={queue.get('item_count')}, "
            f"needs_user_or_controller={queue.get('needs_user_or_controller')}, "
            f"needs_controller={queue.get('needs_controller')}, "
            f"needs_codex={queue.get('needs_codex')}, "
            f"watching_external_evidence={queue.get('watching_external_evidence')}, "
            f"watching_monitor={queue.get('watching_monitor')}",
        ]
    )
    backlog = (
        queue.get("autonomous_backlog_candidates")
        if isinstance(queue.get("autonomous_backlog_candidates"), dict)
        else {}
    )
    append_attention_queue_candidate_group_markdown(
        lines,
        backlog,
        group_name="autonomous_backlog_candidates",
        item_name="autonomous_candidate",
    )
    monitor_candidates = (
        queue.get("autonomous_monitor_candidates")
        if isinstance(queue.get("autonomous_monitor_candidates"), dict)
        else {}
    )
    append_attention_queue_candidate_group_markdown(
        lines,
        monitor_candidates,
        group_name="autonomous_monitor_candidates",
        item_name="autonomous_monitor_candidate",
    )


def append_attention_queue_candidate_group_markdown(
    lines: list[str],
    candidates: dict[str, Any],
    *,
    group_name: str,
    item_name: str,
) -> None:
    if not candidates:
        return
    lines.append(
        f"- {group_name}: "
        f"open={candidates.get('open_count')} "
        f"task_class={markdown_scalar(candidates.get('task_class') or '')} "
        f"source={markdown_scalar(candidates.get('source') or '')}"
    )
    for candidate in candidates.get("items") or []:
        if not isinstance(candidate, dict):
            continue
        priority_text = ""
        if candidate.get("priority"):
            priority_text = f" priority={markdown_scalar(candidate.get('priority') or '')}"
        lines.append(
            f"  - {item_name}: "
            f"goal={markdown_scalar(candidate.get('goal_id') or '')}"
            f"{priority_text} "
            f"text={markdown_scalar(candidate.get('text') or '')}"
        )


def append_attention_queue_item_header_markdown(
    lines: list[str],
    item: dict[str, Any],
    *,
    authority_summary: str | None = None,
) -> None:
    action = str(item.get("recommended_action") or "").replace("|", "\\|")
    lines.append(
        "- "
        f"`{item.get('goal_id')}`: "
        f"status={item.get('status')} "
        f"phase={item.get('lifecycle_phase')} "
        f"waiting_on={item.get('waiting_on')} "
        f"severity={item.get('severity')} "
        f"source={item.get('source')}"
    )
    if action:
        lines.append(f"  - action: {action}")
    active_state_action = markdown_scalar(item.get("active_state_next_action") or "")
    if active_state_action:
        lines.append(f"  - active_state_next_action: {active_state_action}")
    latest_run_action = markdown_scalar(item.get("latest_run_recommended_action") or "")
    if latest_run_action:
        lines.append(f"  - latest_run_recommended_action: {latest_run_action}")
    if authority_summary:
        lines.append(f"  - authority_material: {authority_summary}")
