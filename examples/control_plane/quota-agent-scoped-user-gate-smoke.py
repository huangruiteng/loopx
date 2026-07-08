#!/usr/bin/env python3
"""Smoke-test agent-scoped user gates and exact gate-to-todo dependencies."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.decision_scope import todo_gate_relation  # noqa: E402
from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "agent-scoped-user-gate-fixture"
PRIMARY_AGENT = "codex-main-control"
PRODUCT_AGENT = "codex-product-capability"
VALUE_AGENT = "codex-value-explorer"


def coordination(*agents: str, primary_agent: str = PRIMARY_AGENT) -> dict:
    return {
        "primary_agent": primary_agent,
        "registered_agents": [primary_agent, *agents],
    }


def todo_item(
    *,
    todo_id: str,
    text: str,
    role: str = "agent",
    task_class: str = "advancement_task",
    claimed_by: str | None = None,
    action_kind: str | None = None,
    blocks_agent: str | None = None,
    cadence: str | None = None,
    next_due_at: str | None = None,
    target_key: str | None = None,
) -> dict:
    metadata = {
        key: value
        for key, value in {
            "cadence": cadence,
            "next_due_at": next_due_at,
            "target_key": target_key,
        }.items()
        if value is not None
    }
    return quota_todo_item(
        todo_id=todo_id,
        text=text,
        role=role,
        task_class=task_class,
        claimed_by=claimed_by,
        action_kind=action_kind,
        blocks_agent=blocks_agent,
        **metadata,
    )


def todo_summary(item: dict, *, source_section: str) -> dict:
    return todo_summary_items([item], source_section=source_section)


def todo_summary_items(items: list[dict], *, source_section: str) -> dict:
    role = "user" if source_section.lower().startswith("user") else "agent"
    return quota_todo_summary(items, role=role)


def status_fixture_payload(
    *,
    status: str,
    recommended_action: str,
    user_todos: dict,
    agent_todos: dict,
    quota_state: str = "eligible",
    quota_extra: dict | None = None,
    waiting_on: str | None = None,
    severity: str = "info",
    source: str = "active_state",
    coordination_payload: dict | None = None,
) -> dict:
    quota = {
        "allowed_slots": 1440,
        "spent_slots": 0,
    }
    if quota_extra:
        quota.update(quota_extra)
    return quota_status_payload(
        goal_id=GOAL_ID,
        status=status,
        recommended_action=recommended_action,
        user_todos=user_todos,
        agent_todos=agent_todos,
        quota_state=quota_state,
        quota_extra=quota,
        waiting_on=waiting_on,
        source=source,
        coordination=coordination_payload,
        registry_status="active",
        item_extra={"severity": severity},
        goal_extra={
            "adapter_kind": "fixture_adapter_v0",
            "adapter_status": "connected",
        },
    )


def status_payload(*, blocks_agent: str | None = "codex-product-capability") -> dict:
    user_gate = todo_item(
        todo_id="todo_lark_kanban_gate",
        text="Choose the Lark Kanban target Base before product-capability setup.",
        role="user",
        task_class="user_gate",
        action_kind="lark_kanban_target_decision",
        blocks_agent=blocks_agent,
    )
    agent_todo = todo_item(
        todo_id="todo_benchmark_driver",
        text="[P1] Debug benchmark lifecycle counters and validate the driver.",
        claimed_by="codex-main-control",
    )
    return status_fixture_payload(
        status="active",
        waiting_on="controller",
        severity="blocked",
        recommended_action=(
            "Ask for the Lark Kanban target while benchmark work may "
            "continue on independent agent todos."
        ),
        quota_state="operator_gate",
        quota_extra={"reason": "open user gate"},
        user_todos=todo_summary(user_gate, source_section="User Todo"),
        agent_todos=todo_summary(agent_todo, source_section="Agent Todo"),
        coordination_payload=coordination(PRODUCT_AGENT),
    )


def scoped_no_candidate_status_payload() -> dict:
    primary_agent_todo = todo_item(
        todo_id="todo_primary_benchmark",
        text="[P0] Repair the primary-owned benchmark lifecycle driver.",
        claimed_by="codex-main-control",
    )
    product_monitor = todo_item(
        todo_id="todo_product_monitor",
        text="[P2] Monitor product-capability rollout evidence.",
        task_class="continuous_monitor",
        claimed_by="codex-product-capability",
        cadence="15m",
        next_due_at="2099-01-01T00:00:00Z",
        target_key="product-capability-rollout",
    )
    return status_fixture_payload(
        status="skillsbench_retry_running_result_marker",
        waiting_on="",
        severity="active",
        recommended_action="Monitor run_group retry2b-running-result-marker from public compact artifacts only.",
        quota_extra={"reason": "eligible"},
        user_todos=quota_todo_summary([], role="user"),
        agent_todos=todo_summary_items(
            [primary_agent_todo, product_monitor],
            source_section="Agent Todo",
        ),
        coordination_payload=coordination(PRODUCT_AGENT),
    )


def other_agent_gate_with_non_due_monitor_payload() -> dict:
    primary_review_gate = todo_item(
        todo_id="todo_primary_pr_review_gate",
        text="Review the main-control PR gate before primary merge.",
        role="user",
        task_class="user_gate",
        action_kind="review_pr",
        blocks_agent="codex-main-control",
    )
    primary_agent_todo = todo_item(
        todo_id="todo_primary_pr_review",
        text="[P0] Review and merge the primary-control PR.",
        claimed_by="codex-main-control",
    )
    value_monitor = todo_item(
        todo_id="todo_value_external_signal_monitor",
        text="[P1-monitor] Monitor value-lane external signal when it becomes due.",
        task_class="continuous_monitor",
        claimed_by="codex-value-explorer",
        cadence="1h",
        next_due_at="2099-01-01T00:00:00Z",
    )
    return status_fixture_payload(
        status="active_state_user_todo",
        waiting_on="controller",
        severity="action",
        recommended_action="Primary-control PR review gate is pending.",
        quota_state="operator_gate",
        quota_extra={"reason": "open user gate"},
        user_todos=todo_summary_items([primary_review_gate], source_section="User Todo"),
        agent_todos=todo_summary_items(
            [primary_agent_todo, value_monitor],
            source_section="Agent Todo",
        ),
        coordination_payload=coordination(VALUE_AGENT),
    )


def assert_other_agent_user_gate_does_not_block_current_agent() -> None:
    payload = build_quota_should_run(
        status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is True, payload
    assert payload["normal_delivery_allowed"] is True, payload
    assert payload["decision"] == "run", payload
    assert payload["effective_action"] == "normal_run", payload
    assert payload["requires_user_action"] is False, payload
    contract = payload["interaction_contract"]
    assert contract["user_channel"]["action_required"] is False, contract
    assert payload["action_required"] is False, payload
    assert contract["agent_channel"]["delivery_allowed"] is True, contract
    summary = payload["user_todo_summary"]
    assert summary["open_count"] == 0, summary
    assert payload["open_count"] == 0, payload
    assert summary["other_agent_scoped_open_count"] == 1, summary
    assert summary["other_agent_scoped_items"][0]["blocks_agent"] == "codex-product-capability"
    override = payload["agent_scoped_user_gate_override"]
    assert override["from_state"] == "operator_gate", override
    assert override["to_state"] == "eligible", override
    assert payload["agent_lane_next_action"]["todo_id"] == "todo_benchmark_driver", payload


def assert_other_agent_user_gate_does_not_notify_non_due_monitor_lane() -> None:
    payload = build_quota_should_run(
        other_agent_gate_with_non_due_monitor_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-value-explorer",
    )
    assert payload["decision"] == "skip", payload
    assert payload["effective_action"] == "monitor_quiet_skip", payload
    assert payload["should_run"] is False, payload
    assert payload["requires_user_action"] is False, payload
    assert payload["action_required"] is False, payload
    assert payload["heartbeat_recommendation"]["notify"] == "DONT_NOTIFY", payload
    assert payload["interaction_contract"]["user_channel"]["action_required"] is False, payload
    assert payload["interaction_contract"]["user_channel"]["notify"] == "DONT_NOTIFY", payload
    assert payload["interaction_contract"]["mode"] == "monitor_quiet_skip", payload
    assert "scoped_user_gate_fallback" not in payload, payload
    summary = payload["user_todo_summary"]
    assert summary["open_count"] == 0, summary
    assert summary["other_agent_scoped_open_count"] == 1, summary
    assert summary["other_agent_scoped_items"][0]["blocks_agent"] == "codex-main-control", summary
    agent_summary = payload["agent_todo_summary"]
    assert agent_summary["current_agent_claimed_monitor_count"] == 1, agent_summary
    claim_scope = agent_summary["claim_scope"]
    assert claim_scope["other_agent_claimed_weight"] == "diagnostic_only", claim_scope


def assert_target_agent_still_blocks_on_its_user_gate() -> None:
    payload = build_quota_should_run(
        status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-product-capability",
    )
    assert payload["should_run"] is False, payload
    assert payload["normal_delivery_allowed"] is False, payload
    assert payload["requires_user_action"] is True, payload
    contract = payload["interaction_contract"]
    assert contract["mode"] == "user_gate", contract
    assert contract["user_channel"]["action_required"] is True, contract
    assert payload["action_required"] is True, payload
    assert contract["agent_channel"]["delivery_allowed"] is False, contract
    summary = payload["user_todo_summary"]
    assert summary["open_count"] == 1, summary
    assert payload["open_count"] == 1, payload
    assert "agent_scoped_user_gate_override" not in payload, payload


def assert_unscoped_user_gate_remains_global() -> None:
    payload = build_quota_should_run(
        status_payload(blocks_agent=None),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is False, payload
    assert payload["requires_user_action"] is True, payload
    assert payload["action_required"] is True, payload
    assert payload["interaction_contract"]["mode"] == "user_gate", payload
    assert payload["user_todo_summary"]["open_count"] == 1, payload
    assert payload["open_count"] == 1, payload
    assert "agent_scoped_user_gate_override" not in payload, payload


def unrelated_gate_status_payload() -> dict:
    publication_gate = todo_item(
        todo_id="todo_publication_gate",
        text="Grant GitHub publication path for the LoopX card reply branch.",
        role="user",
        task_class="user_gate",
        action_kind="github_publication_permission",
    )
    publication_gate["unblocks_todo_id"] = "todo_publish_card_reply"
    feishu_request = todo_item(
        todo_id="todo_feishu_ping",
        text="Handle Feishu bot request and reply to message_id=om_ping when done. Request: 你还在吗",
        claimed_by="codex-main-control",
        action_kind="feishu_user_request",
    )
    return status_fixture_payload(
        status="active_state_user_todo",
        waiting_on="controller",
        severity="action",
        recommended_action="Grant GitHub publication path.",
        quota_state="operator_gate",
        quota_extra={
            "blocked_action_scope": "gated_delivery",
            "safe_bypass_allowed": True,
            "safe_bypass_policy": (
                "Only the gated path is blocked; independent public-safe "
                "agent work may continue."
            ),
            "reason": "operator gate blocks gated delivery; safe non-gated steering may continue",
        },
        user_todos=todo_summary(publication_gate, source_section="User Todo"),
        agent_todos=todo_summary(feishu_request, source_section="Agent Todo"),
        coordination_payload=coordination(),
    )


def assert_unrelated_user_gate_allows_feishu_fallback() -> None:
    payload = build_quota_should_run(
        unrelated_gate_status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is True, payload
    assert payload["decision"] == "safe_bypass_user_gate_fallback", payload
    assert payload["actionable_by_codex"] is True, payload
    assert payload["interaction_contract"]["agent_channel"]["delivery_allowed"] is True, payload
    assert payload["interaction_contract"]["agent_channel"]["must_attempt"] is True, payload
    assert payload["execution_obligation"]["kind"] == "scoped_user_gate_fallback", payload
    assert payload["agent_lane_next_action"]["todo_id"] == "todo_feishu_ping", payload
    assert "om_ping" in payload["recommended_action"], payload


def exact_todo_gate_status_payload(*, include_fallback: bool = True) -> dict:
    benchmark_gate = todo_item(
        todo_id="todo_benchmark_owner_gate",
        text="Owner must choose the benchmark run target before benchmark execution.",
        role="user",
        task_class="user_gate",
        action_kind="benchmark_run",
        blocks_agent="codex-main-control",
    )
    benchmark_gate["unblocks_todo_id"] = "todo_blocked_benchmark_run"
    blocked_benchmark = todo_item(
        todo_id="todo_blocked_benchmark_run",
        text="[P1] Run the gated benchmark target after owner choice.",
        claimed_by="codex-main-control",
        action_kind="benchmark_run",
    )
    unavailable_auto_research = todo_item(
        todo_id="todo_unavailable_auto_research",
        text="[P0] Validate the frontier with an unavailable auto-research capability.",
        claimed_by="codex-main-control",
        action_kind="auto_research_frontier",
    )
    unavailable_auto_research["required_capabilities"] = ["auto_research_frontier"]
    independent_benchmark = todo_item(
        todo_id="todo_benchmark_ledger_cleanup",
        text="[P1] Clean public-safe benchmark ledger summaries while target choice is pending.",
        claimed_by="codex-main-control",
        action_kind="benchmark_run",
    )
    external_publish_monitor = todo_item(
        todo_id="todo_x_launch_monitor",
        text=(
            "[P0-revenue monitor] Monitor corrected X launch timing; surface an "
            "exact publish gate, but do not post automatically."
        ),
        task_class="continuous_monitor",
        claimed_by="codex-main-control",
        action_kind="corrected_x_launch_timing_monitor",
        cadence="1h",
        next_due_at="2099-01-01T00:00:00Z",
    )
    agent_items = [unavailable_auto_research, blocked_benchmark]
    if include_fallback:
        agent_items.append(independent_benchmark)
    agent_items.append(external_publish_monitor)
    return status_fixture_payload(
        status="active_state_user_todo",
        waiting_on="controller",
        severity="action",
        recommended_action="Choose benchmark target.",
        quota_state="operator_gate",
        quota_extra={
            "blocked_action_scope": "gated_delivery",
            "safe_bypass_allowed": True,
            "safe_bypass_policy": (
                "Only the gated todo is blocked; independent public-safe "
                "agent work may continue."
            ),
            "reason": "operator gate blocks gated delivery; safe non-gated steering may continue",
        },
        user_todos=todo_summary(benchmark_gate, source_section="User Todo"),
        agent_todos=todo_summary_items(agent_items, source_section="Agent Todo"),
        coordination_payload=coordination(),
    )


def exact_todo_gate_with_decision_scope_migration_payload() -> dict:
    benchmark_gate = todo_item(
        todo_id="todo_benchmark_owner_gate",
        text="Owner must choose the benchmark run target before benchmark execution.",
        role="user",
        task_class="user_gate",
        action_kind="benchmark_run",
        blocks_agent="codex-main-control",
    )
    benchmark_gate["unblocks_todo_id"] = "todo_blocked_benchmark_run"
    benchmark_gate["decision_scope"] = {
        "schema_version": "decision_scope_v0",
        "kind": "direction",
        "granularity": "action",
        "scope_key": "benchmark_target_choice",
    }
    blocked_benchmark = todo_item(
        todo_id="todo_blocked_benchmark_run",
        text="[P1] Run the gated benchmark target after owner choice.",
        claimed_by="codex-main-control",
        action_kind="benchmark_run",
    )
    independent_benchmark = todo_item(
        todo_id="todo_benchmark_ledger_cleanup",
        text="[P1] Clean public-safe benchmark ledger summaries while target choice is pending.",
        claimed_by="codex-main-control",
        action_kind="benchmark_run",
    )
    return status_fixture_payload(
        status="active_state_user_todo",
        waiting_on="controller",
        severity="action",
        recommended_action="Choose benchmark target.",
        quota_state="operator_gate",
        quota_extra={
            "blocked_action_scope": "gated_delivery",
            "safe_bypass_allowed": True,
            "safe_bypass_policy": (
                "Only the exact gated todo is blocked; independent "
                "public-safe agent work may continue during scope migration."
            ),
            "reason": "operator gate blocks gated delivery; safe non-gated steering may continue",
        },
        user_todos=todo_summary(benchmark_gate, source_section="User Todo"),
        agent_todos=todo_summary_items(
            [blocked_benchmark, independent_benchmark],
            source_section="Agent Todo",
        ),
        coordination_payload=coordination(),
    )


def decision_scope_status_payload() -> dict:
    benchmark_gate = todo_item(
        todo_id="todo_benchmark_scope_gate",
        text="Owner must choose the benchmark target before the target run.",
        role="user",
        task_class="user_gate",
        action_kind="benchmark_run",
        blocks_agent="codex-main-control",
    )
    benchmark_gate["decision_scope"] = {
        "schema_version": "decision_scope_v0",
        "kind": "direction",
        "granularity": "action",
        "scope_key": "benchmark_target_choice",
    }
    blocked_target_run = todo_item(
        todo_id="todo_target_benchmark_run",
        text="[P1] Run the chosen benchmark target after owner decision.",
        claimed_by="codex-main-control",
        action_kind="benchmark_run",
    )
    blocked_target_run["required_decision_scopes"] = [
        {
            "schema_version": "decision_scope_v0",
            "kind": "direction",
            "granularity": "action",
            "scope_key": "benchmark_target_choice",
        }
    ]
    independent_helper = todo_item(
        todo_id="todo_benchmark_helper_cleanup",
        text="[P1] Clean benchmark helper ledger summaries while target choice waits.",
        claimed_by="codex-main-control",
        action_kind="benchmark_run",
    )
    independent_helper["required_decision_scopes"] = [
        {
            "schema_version": "decision_scope_v0",
            "kind": "direction",
            "granularity": "action",
            "scope_key": "helper_ledger_cleanup",
        }
    ]
    return status_fixture_payload(
        status="active_state_user_todo",
        waiting_on="controller",
        severity="action",
        recommended_action="Choose benchmark target.",
        quota_state="operator_gate",
        quota_extra={
            "blocked_action_scope": "gated_delivery",
            "safe_bypass_allowed": True,
            "safe_bypass_policy": (
                "Only the gated decision scope is blocked; independent "
                "public-safe agent work may continue."
            ),
            "reason": "operator gate blocks gated delivery; safe non-gated steering may continue",
        },
        user_todos=todo_summary(benchmark_gate, source_section="User Todo"),
        agent_todos=todo_summary_items(
            [blocked_target_run, independent_helper],
            source_section="Agent Todo",
        ),
        coordination_payload=coordination(),
    )


def assert_exact_todo_gate_only_blocks_target_todo() -> None:
    payload = build_quota_should_run(
        exact_todo_gate_status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is True, payload
    assert payload["decision"] == "safe_bypass_user_gate_fallback", payload
    fallback = payload["scoped_user_gate_fallback"]
    blocked = fallback["blocked_agent_items"][0]
    assert blocked["todo_id"] == "todo_blocked_benchmark_run", fallback
    assert blocked["todo_gate_relation"]["state"] == "gate_targets_todo", blocked
    selected = fallback["selected_executable"]
    assert selected["todo_id"] == "todo_benchmark_ledger_cleanup", fallback
    assert selected["todo_gate_relation"]["state"] == "independent", selected
    lane_action = payload["agent_lane_next_action"]
    assert lane_action["todo_id"] == "todo_benchmark_ledger_cleanup", payload
    assert lane_action["source"] == "scoped_user_gate_fallback.selected_executable", lane_action
    assert lane_action["selected_by"] == "scoped_user_gate_fallback", lane_action
    assert lane_action["replaces_gated_goal_next_action"] is True, lane_action
    assert "todo_benchmark_ledger_cleanup" in payload["protocol_action_packet"]["summary"], payload
    monitor_ids = {
        item["todo_id"]
        for item in payload["agent_todo_summary"]["first_open_items"]
        if item.get("task_class") == "continuous_monitor"
    }
    assert "todo_x_launch_monitor" in monitor_ids, payload["agent_todo_summary"]

    blocked_payload = build_quota_should_run(
        exact_todo_gate_status_payload(include_fallback=False),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert blocked_payload["should_run"] is False, blocked_payload
    assert blocked_payload["interaction_contract"]["mode"] == "user_gate", blocked_payload
    assert "scoped_user_gate_fallback" not in blocked_payload, blocked_payload
    blocked_monitor_ids = {
        item["todo_id"]
        for item in blocked_payload["agent_todo_summary"]["first_open_items"]
        if item.get("task_class") == "continuous_monitor"
    }
    assert "todo_x_launch_monitor" in blocked_monitor_ids, blocked_payload["agent_todo_summary"]


def assert_exact_todo_gate_survives_decision_scope_migration() -> None:
    payload = build_quota_should_run(
        exact_todo_gate_with_decision_scope_migration_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is True, payload
    assert payload["decision"] == "safe_bypass_user_gate_fallback", payload
    fallback = payload["scoped_user_gate_fallback"]
    blocked = fallback["blocked_agent_items"][0]
    assert blocked["todo_id"] == "todo_blocked_benchmark_run", fallback
    relation = blocked["todo_gate_relation"]
    assert relation["source"] == "unblocks_todo_id", relation
    assert relation["state"] == "gate_targets_todo", relation
    scope_relation = relation["decision_scope_relation"]
    assert scope_relation["source"] == "decision_scope", scope_relation
    assert scope_relation["state"] == "independent", scope_relation
    assert scope_relation["reason"] == "agent_todo_has_no_required_decision_scopes", scope_relation
    selected = fallback["selected_executable"]
    assert selected["todo_id"] == "todo_benchmark_ledger_cleanup", fallback
    assert selected["todo_gate_relation"]["source"] == "unblocks_todo_id", selected
    assert selected["todo_gate_relation"]["state"] == "independent", selected


def assert_conflicting_exact_and_decision_scope_requires_projection_repair() -> None:
    gate = {
        "todo_id": "todo_gate_conflict",
        "task_class": "user_gate",
        "unblocks_todo_id": "todo_exact_target",
        "decision_scope": {
            "schema_version": "decision_scope_v0",
            "kind": "direction",
            "granularity": "action",
            "scope_key": "benchmark_target_choice",
        },
    }
    agent_item = {
        "todo_id": "todo_semantic_target",
        "task_class": "advancement_task",
        "required_decision_scopes": [
            {
                "schema_version": "decision_scope_v0",
                "kind": "direction",
                "granularity": "action",
                "scope_key": "benchmark_target_choice",
            }
        ],
    }
    relation = todo_gate_relation(gate, agent_item)
    assert relation["source"] == "unblocks_todo_id+decision_scope", relation
    assert relation["state"] == "projection_repair_required", relation
    assert relation["reason"] == (
        "decision_scope_covers_agent_todo_but_unblocks_todo_targets_different_todo"
    ), relation
    assert relation["exact_todo_relation"]["state"] == "independent", relation
    assert relation["decision_scope_relation"]["state"] == "gate_covers_action", relation


def assert_decision_scope_overrides_shared_action_kind_tokens() -> None:
    payload = build_quota_should_run(
        decision_scope_status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is True, payload
    assert payload["decision"] == "safe_bypass_user_gate_fallback", payload
    fallback = payload["scoped_user_gate_fallback"]
    blocked = fallback["blocked_agent_items"][0]
    assert blocked["todo_id"] == "todo_target_benchmark_run", fallback
    assert blocked["todo_gate_relation"]["source"] == "decision_scope", blocked
    assert blocked["todo_gate_relation"]["state"] == "gate_covers_action", blocked
    selected = fallback["selected_executable"]
    assert selected["todo_id"] == "todo_benchmark_helper_cleanup", fallback
    assert selected["todo_gate_relation"]["source"] == "decision_scope", selected
    assert selected["todo_gate_relation"]["state"] == "independent", selected


def assert_agent_without_advancement_candidate_and_only_monitor_work_stays_quiet() -> None:
    payload = build_quota_should_run(
        scoped_no_candidate_status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-product-capability",
    )
    assert payload["decision"] == "skip", payload
    assert payload["effective_action"] == "monitor_quiet_skip", payload
    assert payload["should_run"] is False, payload
    assert payload["normal_delivery_allowed"] is False, payload
    assert "external_evidence_observation" not in payload, payload
    assert payload["work_lane_contract"]["monitor_kind"] == "todo_monitor", payload
    assert payload.get("agent_lane_next_action") is None, payload
    assert "agent_scope_frontier" not in payload, payload
    hint = payload["agent_lane_frontier_hint"]
    assert hint["decision"] == "quiet_noop_blocker", hint
    assert hint["source"] == "agent_todo_summary", hint
    assert hint["reason_code"] == "only_current_agent_monitor_work_remains", hint
    assert hint["quiet_noop_allowed"] is True, hint
    claim_scope = payload["agent_todo_summary"]["claim_scope"]
    assert claim_scope["other_agent_claimed_weight"] == "diagnostic_only", claim_scope
    assert claim_scope["other_agent_claimed_open_count"] == 1, claim_scope
    contract = payload["interaction_contract"]
    assert contract["user_channel"]["action_required"] is False, contract
    assert contract["agent_channel"]["must_attempt"] is False, contract
    assert contract["agent_channel"]["delivery_allowed"] is False, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is True, contract
    assert contract["mode"] == "monitor_quiet_skip", contract
    scheduler = payload["scheduler_hint"]
    assert scheduler["schema_version"] == "scheduler_hint_v0", scheduler
    assert scheduler["action"] == "backoff_until_material_transition", scheduler
    assert scheduler["codex_app"]["recommended_interval_minutes"] == 15, scheduler
    assert scheduler["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=15", scheduler
    # A far-future monitor keeps the host floor at 15m, but may back off more
    # coarsely until the scheduled window gets near.
    progression = scheduler["codex_app"]["example_progression_minutes"]
    assert progression == [15, 30, 60], scheduler
    assert scheduler["unchanged_poll"]["limits"]["codex_cli_tui"] == 3, scheduler
    assert scheduler["unchanged_poll"]["final_quota_replan_check_enabled"] is True, scheduler
    assert scheduler["unchanged_poll"]["after_limits"]["claude_code_loop"] == "stop_loop", scheduler
    assert scheduler["unchanged_poll"]["limits"]["claude_code_loop"] == 3, scheduler
    assert "local_scheduler" not in scheduler, scheduler
    assert "codex_cli_tui" not in scheduler, scheduler
    assert "claude_code_loop" not in scheduler, scheduler
    assert "cold_path_detail" not in scheduler, scheduler
    reset = scheduler["reset_policy"]
    assert isinstance(reset["reset_token"], str) and len(reset["reset_token"]) == 16, reset
    assert reset["host_state_key"] == "scheduler_hint.reset_policy.reset_token", reset
    assert reset["codex_app_initial_interval_minutes"] == 15, reset
    assert reset["codex_app_initial_rrule"] == "FREQ=MINUTELY;INTERVAL=15", reset
    assert scheduler["codex_app"]["max_interval_minutes"] == 60, scheduler
    assert len(reset["identity_signature"]) == 12, reset
    assert "identity_snapshot" not in reset, reset
    assert "profile_snapshot" not in reset, reset
    assert "identity_keys" not in reset, reset
    assert "profile_signature" not in reset, reset
    assert "reset_condition_summary" not in reset, reset
    assert "no_spend_for_reset" not in reset, reset
    assert "scheduler=backoff_until_material_transition" in payload["protocol_action_packet"]["summary"], payload


def main() -> int:
    assert_other_agent_user_gate_does_not_block_current_agent()
    assert_other_agent_user_gate_does_not_notify_non_due_monitor_lane()
    assert_target_agent_still_blocks_on_its_user_gate()
    assert_unscoped_user_gate_remains_global()
    assert_unrelated_user_gate_allows_feishu_fallback()
    assert_exact_todo_gate_only_blocks_target_todo()
    assert_exact_todo_gate_survives_decision_scope_migration()
    assert_conflicting_exact_and_decision_scope_requires_projection_repair()
    assert_decision_scope_overrides_shared_action_kind_tokens()
    assert_agent_without_advancement_candidate_and_only_monitor_work_stays_quiet()
    print("quota-agent-scoped-user-gate-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
