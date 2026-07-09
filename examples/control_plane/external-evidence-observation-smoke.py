#!/usr/bin/env python3
"""Smoke-test external-evidence monitor observation as a scheduler seam."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.control_plane.scheduler.external_evidence_observation import (  # noqa: E402
    build_external_evidence_observation_obligation,
    build_external_evidence_poll_signal,
    projected_monitor_handle,
)
from loopx.control_plane.scheduler.monitor_poll_policy import (  # noqa: E402
    allows_no_spend_external_monitor_poll,
)
from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.control_plane.todos.contract import (  # noqa: E402
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
)
from loopx.control_plane.todos.projection import (  # noqa: E402
    todo_summary_open_task_counts,
)
from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "external-evidence-observation-fixture"
AGENT_ID = "codex-product-capability"
PAST_DUE_AT = "2000-01-01T00:00:00+00:00"
FUTURE_DUE_AT = "2999-01-01T00:00:00+00:00"


def todo(
    index: int,
    text: str,
    *,
    task_class: str,
    todo_id: str,
    **metadata: Any,
) -> dict[str, Any]:
    return quota_todo_item(
        todo_id=todo_id,
        role="agent",
        status="open",
        index=index,
        text=text,
        task_class=task_class,
        **metadata,
    )


def agent_todos(items: list[dict[str, Any]]) -> dict[str, Any]:
    return quota_todo_summary(
        items,
        role="agent",
        claim_scope_agent_id=AGENT_ID,
    )


def monitor_todo(
    *,
    todo_id: str = "todo_monitor_result",
    priority: str = "P1",
    next_due_at: str = PAST_DUE_AT,
) -> dict[str, Any]:
    return todo(
        1,
        f"[{priority}] Monitor compact result marker and write back only if it changed.",
        task_class=TODO_TASK_CLASS_MONITOR,
        todo_id=todo_id,
        target_key="job:compact-result",
        next_due_at=next_due_at,
        claimed_by=AGENT_ID,
    )


def pr_dependency_monitor_todo(
    *,
    result_hash: str | None = None,
    last_checked_at: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "target_key": "pr_merged:#532",
        "next_due_at": FUTURE_DUE_AT,
        "claimed_by": AGENT_ID,
    }
    if result_hash:
        metadata["result_hash"] = result_hash
    if last_checked_at:
        metadata["last_checked_at"] = last_checked_at
    return todo(
        3,
        "[P0] Monitor PR #532 review/merge state before resuming the rerun lane.",
        task_class=TODO_TASK_CLASS_MONITOR,
        todo_id="todo_pr_dependency_monitor",
        **metadata,
    )


def advancement_todo() -> dict[str, Any]:
    return todo(
        2,
        "[P0] Advance the canary/refactor slice with a validated patch.",
        task_class=TODO_TASK_CLASS_ADVANCEMENT,
        todo_id="todo_advancement_now",
        claimed_by=AGENT_ID,
    )


def unavailable_advancement_todo() -> dict[str, Any]:
    item = advancement_todo()
    item["required_capabilities"] = ["private_read"]
    return item


def status_payload(
    summary: dict[str, Any],
    *,
    status: str = "launched_polling_result",
    waiting_on: str = "codex",
    next_action: str = "Observe compact result marker for remote job handle.",
    latest_runs: list[dict[str, Any]] | None = None,
    lifecycle_flags: list[str] | None = None,
) -> dict[str, Any]:
    return quota_status_payload(
        goal_id=GOAL_ID,
        status=status,
        waiting_on=waiting_on,
        recommended_action=next_action,
        next_action=next_action,
        agent_todos=summary,
        quota_extra={"allowed_slots": 1440},
        coordination={
            "primary_agent": "codex-main-control",
            "registered_agents": ["codex-main-control", AGENT_ID],
        },
        latest_runs=latest_runs or [],
        item_extra={
            "lifecycle_flags": lifecycle_flags
            if lifecycle_flags is not None
            else ["launched polling result marker"]
        },
    )


def selected_item(payload: dict[str, Any]) -> dict[str, Any]:
    return payload["attention_queue"]["items"][0]


def assert_monitor_only_launched_poll_requires_observation() -> None:
    summary = agent_todos([monitor_todo()])
    item = selected_item(status_payload(summary))

    handle = projected_monitor_handle(summary)
    assert handle and handle["todo_id"] == "todo_monitor_result", handle
    assert handle["target_key"] == "job:compact-result", handle

    signal = build_external_evidence_poll_signal(item, agent_todo_summary=summary)
    assert signal and signal["matched_signal"] == "launched_wait", signal
    assert signal["monitor_handle"]["todo_id"] == "todo_monitor_result", signal

    obligation = build_external_evidence_observation_obligation(
        item,
        state="active",
        agent_todo_summary=summary,
        work_lane_contract={"lane": "continuous_monitor"},
    )
    assert obligation and obligation["kind"] == "launched_external_work_monitor", obligation
    assert obligation["monitor_handle"]["target_key"] == "job:compact-result", obligation

    guard = build_quota_should_run(status_payload(summary), goal_id=GOAL_ID, agent_id=AGENT_ID)
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "continuous_monitor", guard
    assert lane["monitor_kind"] == "external_evidence", guard
    assert guard["effective_action"] == "external_evidence_observe", guard
    assert guard["execution_obligation"]["kind"] == "external_evidence_observation_required", guard
    assert allows_no_spend_external_monitor_poll(guard) is True, guard


def assert_recent_unchanged_observation_quiets_external_monitor() -> None:
    summary = agent_todos(
        [
            monitor_todo(next_due_at=FUTURE_DUE_AT),
            unavailable_advancement_todo(),
        ]
    )
    guard = build_quota_should_run(
        status_payload(
            summary,
            latest_runs=[
                {
                    "classification": "quota_slot_spent",
                    "agent_id": AGENT_ID,
                    "recommended_action": "wait quietly for material monitor evidence",
                },
                {
                    "classification": "quota_monitor_poll",
                    "agent_id": AGENT_ID,
                    "delivery_outcome": "surface_only",
                    "health_check": "external monitor observation unchanged; no quota spend; no material transition",
                },
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert guard["decision"] == "skip", guard
    assert guard["should_run"] is False, guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert "external_evidence_observation" not in guard, guard
    assert guard["external_evidence_observation_recent"]["classification"] == "quota_monitor_poll", guard
    interaction = guard["interaction_contract"]
    assert interaction["mode"] == "monitor_quiet_skip", interaction
    assert interaction["agent_channel"]["must_attempt"] is False, interaction
    assert interaction["agent_channel"]["quiet_noop_allowed"] is True, interaction


def assert_recent_due_monitor_no_change_quiets_external_monitor() -> None:
    summary = agent_todos(
        [
            monitor_todo(next_due_at=FUTURE_DUE_AT),
            unavailable_advancement_todo(),
        ]
    )
    guard = build_quota_should_run(
        status_payload(
            summary,
            latest_runs=[
                {
                    "classification": "quota_slot_spent",
                    "agent_id": AGENT_ID,
                    "recommended_action": "wait quietly for material monitor evidence",
                },
                {
                    "classification": "external_monitor_observation_cooldown_repaired",
                    "agent_id": AGENT_ID,
                    "delivery_outcome": "outcome_progress",
                    "recommended_action": "wait quietly for material monitor evidence",
                },
                {
                    "classification": "quota_monitor_poll",
                    "agent_id": AGENT_ID,
                    "delivery_outcome": "surface_only",
                    "health_check": "due monitor observation unchanged; no quota spend; next due updated",
                    "monitor_event": {
                        "monitor_mode": "due_monitor_observed_without_material_transition",
                        "material_change": False,
                    },
                },
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert guard["decision"] == "skip", guard
    assert guard["should_run"] is False, guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert "external_evidence_observation" not in guard, guard
    recent = guard["external_evidence_observation_recent"]
    assert recent["classification"] == "quota_monitor_poll", guard
    assert recent["monitor_mode"] == "due_monitor_observed_without_material_transition", guard
    assert recent["reason"] == "recent monitor observation was unchanged", guard
    interaction = guard["interaction_contract"]
    assert interaction["agent_channel"]["must_attempt"] is False, interaction
    assert interaction["agent_channel"]["quiet_noop_allowed"] is True, interaction


def assert_advancement_lane_keeps_external_monitor_as_context() -> None:
    summary = agent_todos(
        [
            monitor_todo(todo_id="todo_monitor_context", priority="P2"),
            advancement_todo(),
        ]
    )
    item = selected_item(status_payload(summary))
    assert build_external_evidence_poll_signal(item, agent_todo_summary=summary), item

    guard = build_quota_should_run(status_payload(summary), goal_id=GOAL_ID, agent_id=AGENT_ID)
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", guard
    assert lane["obligation"] == "advance_one_bounded_segment", guard
    assert "external_monitor_context" in lane["reason_codes"], guard
    assert "external_evidence_observation" not in guard, guard
    assert guard["execution_obligation"]["kind"] == "work_lane_contract", guard
    assert guard["agent_lane_next_action"]["todo_id"] == "todo_advancement_now", guard


def assert_future_scoped_monitor_does_not_fake_external_poll() -> None:
    summary = agent_todos(
        [
            monitor_todo(
                todo_id="todo_monitor_future",
                priority="P1",
                next_due_at=FUTURE_DUE_AT,
            )
        ]
    )
    item = selected_item(status_payload(summary))
    counts = todo_summary_open_task_counts(summary)
    assert counts["monitor"] == 1 and counts["advancement"] == 0, counts
    assert build_external_evidence_poll_signal(item, agent_todo_summary=summary) is None

    obligation = build_external_evidence_observation_obligation(
        item,
        state="active",
        agent_todo_summary=summary,
        work_lane_contract={"lane": "continuous_monitor"},
    )
    assert obligation is None, obligation

    guard = build_quota_should_run(status_payload(summary), goal_id=GOAL_ID, agent_id=AGENT_ID)
    lane = guard["work_lane_contract"]
    assert lane["obligation"] == "quiet_until_material_monitor_transition", guard
    assert lane["must_attempt_work"] is False, guard
    assert "external_evidence_observation" not in guard, guard


def assert_pr_dependency_wait_requires_first_observation() -> None:
    summary = agent_todos([pr_dependency_monitor_todo()])
    next_action = (
        "Keep PR #532 in review-required state; after maintainer review/merge, "
        "resume dependent validation lane."
    )
    item = selected_item(
        status_payload(
            summary,
            status="active",
            next_action=next_action,
            latest_runs=[],
            lifecycle_flags=[],
        )
    )
    signal = build_external_evidence_poll_signal(item, agent_todo_summary=summary)
    assert signal and signal["matched_signal"] == "external_dependency_wait", signal
    assert signal["monitor_handle"]["target_key"] == "pr_merged:#532", signal

    guard = build_quota_should_run(
        status_payload(
            summary,
            status="active",
            next_action=next_action,
            latest_runs=[],
            lifecycle_flags=[],
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "external_evidence_observe", guard
    observation = guard["external_evidence_observation"]
    assert observation["kind"] == "launched_external_work_monitor", observation
    assert observation["monitor_handle"]["target_key"] == "pr_merged:#532", observation
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard


def assert_pr_dependency_wait_with_observation_does_not_reobserve_before_due() -> None:
    summary = agent_todos(
        [
            pr_dependency_monitor_todo(
                result_hash="pr_532_open_review_required",
                last_checked_at="2026-07-08T18:00:00+08:00",
            )
        ]
    )
    next_action = (
        "Keep PR #532 in review-required state; after maintainer review/merge, "
        "resume dependent validation lane."
    )
    item = selected_item(
        status_payload(
            summary,
            status="active",
            next_action=next_action,
            lifecycle_flags=[],
        )
    )
    assert build_external_evidence_poll_signal(item, agent_todo_summary=summary) is None

    guard = build_quota_should_run(
        status_payload(
            summary,
            status="active",
            next_action=next_action,
            lifecycle_flags=[],
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert "external_evidence_observation" not in guard, guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard


def assert_explicit_external_wait_builds_registry_obligation() -> None:
    summary = agent_todos([])
    payload = status_payload(
        summary,
        status="waiting",
        waiting_on="external_evidence",
        next_action="Wait for compact result marker before continuing.",
    )
    item = selected_item(payload)
    obligation = build_external_evidence_observation_obligation(
        item,
        state="waiting",
        agent_todo_summary=summary,
        work_lane_contract=None,
    )
    assert obligation and obligation["kind"] == "external_evidence_monitor", obligation
    assert obligation["trigger"] == "registry_waiting_on_external_evidence", obligation
    assert obligation["signal_source"] == "registry", obligation


def main() -> int:
    assert_monitor_only_launched_poll_requires_observation()
    assert_recent_unchanged_observation_quiets_external_monitor()
    assert_recent_due_monitor_no_change_quiets_external_monitor()
    assert_advancement_lane_keeps_external_monitor_as_context()
    assert_future_scoped_monitor_does_not_fake_external_poll()
    assert_pr_dependency_wait_requires_first_observation()
    assert_pr_dependency_wait_with_observation_does_not_reobserve_before_due()
    assert_explicit_external_wait_builds_registry_obligation()
    print("external-evidence-observation-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
