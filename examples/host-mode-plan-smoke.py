#!/usr/bin/env python3
"""Smoke-test the LoopX Turn-based host-mode selector.

This proves the selector added for GH-C56 stays useful without becoming a
parallel runner:
- intent selects visible, isolated headless Turn, gateway, timer, and hybrid modes;
- headless modes map to the shipped `loopx turn plan` preview;
- scoped `--agent-id` flows into Turn and quota preview commands;
- readiness reports missing host capabilities instead of pretending execution is ready;
- no-spend, independent-validation, writeback-before-spend, and boundary rules remain visible;
- docs are wired without scanning unrelated catalog prose with broad private-word bans.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.host_mode_planner import (  # noqa: E402
    CANONICAL_MODES,
    SUPPORTED_TURN_HOST_IDENTITIES,
    MODE_HYBRID_HANDOFF,
    MODE_IM_GATEWAY,
    MODE_ISOLATED_HEADLESS_TURN,
    MODE_SHELL_SERVICE,
    MODE_VISIBLE_TUI,
    HostModePlanError,
    build_host_mode_plan,
    render_host_mode_plan_markdown,
)

CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "host-mode-plan-v0.md"
TURN_CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "loopx-turn-v0.md"
PROTOCOL_INDEX_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
CONNECTOR_CATALOG_PATH = REPO_ROOT / "docs" / "runtime-connector-catalog.md"

PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

INTENT_TO_MODE = {
    "watch_each_turn": MODE_VISIBLE_TUI,
    "continue_without_ui": MODE_ISOLATED_HEADLESS_TURN,
    "intake_from_chat": MODE_IM_GATEWAY,
    "timer_keepalive": MODE_SHELL_SERVICE,
    "escalate_between_modes": MODE_HYBRID_HANDOFF,
}


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def build_full_plan(intent: str) -> dict[str, object]:
    return build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent=intent,
        host_capabilities=[
            "visible_session",
            "loopx_turn",
            "typed_host_adapter",
            "independent_validator",
            "chat_gateway",
            "service_timer",
            "shell",
        ],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control", "codex-side-peer"],
        available_capabilities=["shell", "network"],
        host_identity="codex-cli",
    )


def option(plan: dict[str, object], mode: str) -> dict[str, object]:
    for item in plan["mode_options"]:  # type: ignore[index]
        if isinstance(item, dict) and item.get("mode") == mode:
            return item
    raise AssertionError(f"missing mode option {mode}")


def test_intent_selects_distinct_host_modes() -> None:
    for intent, expected_mode in INTENT_TO_MODE.items():
        plan = build_full_plan(intent)
        assert plan["ok"] is True, plan
        assert plan["schema_version"] == "host_mode_plan_v0", plan
        assert plan["mode"] == "dry_run_host_mode_selector", plan
        assert plan["selected_mode"] == expected_mode, (intent, plan)
        modes = [item["mode"] for item in plan["mode_options"]]  # type: ignore[index]
        assert set(modes) == set(CANONICAL_MODES), modes
        assert len(modes) == len(CANONICAL_MODES), modes


def test_headless_maps_to_loopx_turn_plan_not_parallel_runner() -> None:
    plan = build_full_plan("continue_without_ui")
    selected = plan["selected_turn_mapping"]
    assert selected["host"] == "generic-cli", selected
    assert selected["execution_mode"] == "isolated-headless", selected
    assert selected["scheduler_owner"] == "outer_controller", selected
    command = selected["plan_command"]
    assert "loopx turn plan" in command, command
    assert "--host generic-cli" in command, command
    assert "--execution-mode isolated-headless" in command, command
    assert "--scheduler-owner outer_controller" in command, command
    assert "--agent-id codex-main-control" in command, command
    assert "--available-capability shell" in command, command
    assert plan["turn_contract"]["schema_version"] == "loopx_turn_v0", plan
    assert plan["turn_contract"]["independent_validation_required"] is True, plan
    assert plan["turn_contract"]["writeback_before_quota_spend"] is True, plan


def test_visible_mode_stays_visible_and_scoped() -> None:
    plan = build_workflow_identity_plan("watch_each_turn", host_identity="codex-cli")
    selected = plan["selected_turn_mapping"]
    assert selected["host"] == "codex-cli", selected
    assert selected["execution_mode"] == "interactive-visible", selected
    assert selected["scheduler_owner"] == "agent_cli_loop", selected
    assert "--host codex-cli" in selected["plan_command"], selected
    assert "--agent-id codex-main-control" in selected["plan_command"], selected
    visible = option(plan, MODE_VISIBLE_TUI)
    assert visible["connector_id"] == "codex_cli_tui", visible
    assert visible["capability_ready"] is True, visible
    assert plan["host_identity"] == "codex-cli", plan


def build_workflow_identity_plan(intent: str, host_identity: str | None) -> dict[str, object]:
    return build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent=intent,
        host_capabilities=[
            "visible_session",
            "loopx_turn",
            "typed_host_adapter",
            "independent_validator",
            "chat_gateway",
            "service_timer",
            "shell",
        ],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control", "codex-side-peer"],
        available_capabilities=["shell", "network"],
        host_identity=host_identity,
    )


def test_visible_mode_preserves_distinct_host_identities() -> None:
    expected_connectors = {
        "codex-cli": "codex_cli_tui",
        "claude-code": "claude_code_loop",
    }
    for host_identity, connector_id in expected_connectors.items():
        plan = build_workflow_identity_plan("watch_each_turn", host_identity=host_identity)
        selected = plan["selected_turn_mapping"]
        assert selected["host"] == host_identity, (host_identity, selected)
        assert f"--host {host_identity}" in selected["plan_command"], selected
        visible = option(plan, MODE_VISIBLE_TUI)
        assert visible["connector_id"] == connector_id, visible
        assert visible["host_identity"] == host_identity, visible
        assert plan["host_identity"] == host_identity, plan
        assert plan["selected_connector_id"] == connector_id, plan


def test_visible_mode_fails_closed_without_host_identity() -> None:
    plan = build_workflow_identity_plan("watch_each_turn", host_identity=None)
    visible = option(plan, MODE_VISIBLE_TUI)
    assert visible["capability_ready"] is False, visible
    # Unresolved mapping must not emit a non-catalog connector id; the
    # resolution state lives in a separately typed field instead.
    assert visible["connector_id"] is None, visible
    assert visible["host_resolution"] == "identity_required", visible
    assert visible["host_identity"] is None, visible
    assert visible["turn_mapping"]["host"] is None, visible
    assert visible["recommended_next_steps"][0]["kind"] == "stop", visible
    assert plan["selected_capability_ready"] is False, plan
    assert plan["selected_connector_id"] is None, plan
    assert plan["selected_turn_mapping"]["host"] is None, plan
    assert any("host_identity" in reason for reason in plan["selected_blocking_reasons"]), plan
    assert plan["operator_next_steps"][0]["kind"] == "stop", plan
    # No fabricated codex-cli preview command when identity is unknown.
    assert "--host codex-cli" not in plan["next_preview_command"], plan
    assert "codex-cli" not in str(plan["next_preview_command"]), plan


def test_visible_mode_fails_closed_for_unregistered_host_identity() -> None:
    plan = build_workflow_identity_plan("watch_each_turn", host_identity="generic-cli")
    visible = option(plan, MODE_VISIBLE_TUI)
    assert visible["capability_ready"] is False, visible
    assert visible["connector_id"] is None, visible
    assert visible["host_resolution"] == "unregistered_host_identity", visible
    assert visible["host_identity"] == "generic-cli", visible
    assert visible["recommended_next_steps"][0]["kind"] == "stop", visible
    assert plan["selected_capability_ready"] is False, plan
    assert plan["selected_connector_id"] is None, plan
    assert any("no registered catalog connector" in reason for reason in plan["selected_blocking_reasons"]), plan


def test_emitted_connector_ids_exist_in_catalog() -> None:
    catalog = CONNECTOR_CATALOG_PATH.read_text()
    # Resolved identities emit only catalog-registered connector ids.
    for host_identity in ["codex-cli", "claude-code"]:
        plan = build_workflow_identity_plan("watch_each_turn", host_identity=host_identity)
        connector = plan["selected_connector_id"]
        assert connector is not None, (host_identity, plan)
        assert f"`{connector}`" in catalog, (connector, "missing from runtime connector catalog")
    # Unresolved paths (omitted or unregistered identity) must not emit any
    # non-catalog value in the connector id field.
    for host_identity in [None, "generic-cli"]:
        plan = build_workflow_identity_plan("watch_each_turn", host_identity=host_identity)
        assert plan["selected_connector_id"] is None, (host_identity, plan)
        visible = option(plan, MODE_VISIBLE_TUI)
        assert visible["connector_id"] is None, (host_identity, visible)
    for intent, mode in INTENT_TO_MODE.items():
        if mode == MODE_HYBRID_HANDOFF:
            continue  # selector-internal handoff contract, not a catalog connector
        plan = build_full_plan(intent)
        connector = plan["selected_connector_id"]
        assert connector is not None, (intent, plan)
        assert f"`{connector}`" in catalog, (intent, connector, "missing from runtime connector catalog")


def test_readiness_fails_closed_without_required_host_capabilities() -> None:
    plan = build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent="continue_without_ui",
        host_capabilities=["loopx_turn"],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control"],
    )
    headless = option(plan, MODE_ISOLATED_HEADLESS_TURN)
    assert headless["capability_ready"] is False, headless
    assert headless["required_host_capabilities"] == [
        "loopx_turn",
        "typed_host_adapter",
        "independent_validator",
    ], headless
    assert headless["missing_host_capabilities"] == [
        "typed_host_adapter",
        "independent_validator",
    ], headless
    assert any("typed host adapter" in reason for reason in headless["blocking_reasons"]), headless
    assert any("independent validator" in reason for reason in headless["blocking_reasons"]), headless
    steps = headless["recommended_next_steps"]
    assert steps[0]["kind"] == "stop", steps
    assert any(step["kind"] == "capability_gap" for step in steps), steps
    assert steps[-1]["kind"] == "repreview", steps
    assert plan["selected_capability_ready"] is False, plan
    assert plan["selected_missing_host_capabilities"] == [
        "typed_host_adapter",
        "independent_validator",
    ], plan
    assert plan["operator_next_steps"][0]["kind"] == "stop", plan


def test_shell_service_fails_closed_without_adapter_and_validator() -> None:
    # Regression: with only service_timer, shell, and loopx_turn the planner
    # previously reported shell_service ready even though its required proofs
    # include typed_host_adapter and independent_validation.
    plan = build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent="timer_keepalive",
        host_capabilities=["service_timer", "shell", "loopx_turn"],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control"],
    )
    shell_service = option(plan, MODE_SHELL_SERVICE)
    assert shell_service["capability_ready"] is False, shell_service
    assert shell_service["missing_host_capabilities"] == [
        "typed_host_adapter",
        "independent_validator",
    ], shell_service
    assert plan["selected_capability_ready"] is False, plan


def test_hybrid_requires_two_ready_modes_and_names_handoffs() -> None:
    one_ready = build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent="escalate_between_modes",
        host_capabilities=["visible_session"],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control"],
    )
    hybrid_one = option(one_ready, MODE_HYBRID_HANDOFF)
    assert hybrid_one["capability_ready"] is False, hybrid_one
    assert hybrid_one["blocking_reasons"], hybrid_one
    assert hybrid_one["recommended_next_steps"][0]["kind"] == "stop", hybrid_one

    two_ready = build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent="escalate_between_modes",
        host_capabilities=[
            "visible_session",
            "loopx_turn",
            "typed_host_adapter",
            "independent_validator",
        ],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control"],
        host_identity="codex-cli",
    )
    assert option(two_ready, MODE_HYBRID_HANDOFF)["capability_ready"] is True, two_ready
    transition_ids = {item["transition"] for item in two_ready["transitions"]}
    assert "visible_bootstrap_to_isolated_headless_turn" in transition_ids, transition_ids
    assert "isolated_headless_turn_to_visible_tui_escalation" in transition_ids, transition_ids
    for transition in two_ready["transitions"]:
        assert transition["preserves_agent_id"] is True, transition
        assert transition["spends_quota"] is False, transition
        assert "--agent-id codex-main-control" in transition["guard_command"], transition


def test_identity_gate_and_no_spend_boundary() -> None:
    plan = build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent="watch_each_turn",
        host_capabilities=["visible_session"],
        registered_agents=["codex-main-control", "codex-side-peer"],
    )
    identity = plan["identity_contract"]
    assert identity["state"] == "selection_required", identity
    assert identity["action_required"] is True, identity
    assert plan["agent_id"] is None, plan
    assert "--agent-id" not in plan["next_preview_command"], plan

    no_spend = plan["no_spend_policy"]
    assert no_spend["selector_preview"] is True, no_spend
    assert no_spend["turn_plan_preview"] is True, no_spend
    assert no_spend["quiet_monitor_skip"] is True, no_spend
    assert no_spend["spends_only_after_validated_delivery_writeback"] is True, no_spend
    boundary = plan["boundary"]
    assert boundary["selector_is_authoritative"] is False, boundary
    assert boundary["turn_envelope_is_authoritative_for_execution"] is True, boundary
    for key in [
        "starts_process",
        "writes_state",
        "spends_quota",
        "infers_production_permission",
        "infers_credential_access",
        "infers_destructive_authority",
    ]:
        assert boundary[key] is False, (key, boundary)


def test_unknown_values_fail_closed() -> None:
    try:
        build_host_mode_plan(goal_id="g", user_intent="launch_missiles")
    except HostModePlanError as exc:
        payload = exc.to_payload()
    else:
        raise AssertionError("unknown intent should fail")
    assert payload["ok"] is False, payload
    assert payload["field"] == "user_intent", payload
    assert "continue_without_ui" in payload["suggestions"], payload

    try:
        build_host_mode_plan(
            goal_id="g",
            user_intent="continue_without_ui",
            host_capabilities=["root_shell"],
        )
    except HostModePlanError as exc:
        payload = exc.to_payload()
    else:
        raise AssertionError("unknown capability should fail")
    assert payload["field"] == "host_capabilities", payload
    assert "independent_validator" in payload["suggestions"], payload


def test_markdown_and_docs_are_wired() -> None:
    plan = build_full_plan("continue_without_ui")
    markdown = render_host_mode_plan_markdown(plan)
    assert_contains(markdown, "LoopX Host Mode Plan", "markdown")
    assert_contains(markdown, "loopx turn plan", "markdown")
    assert_contains(markdown, "Operator Next Steps", "markdown")
    assert_contains(markdown, "Escalate back to visible_tui", "markdown")
    assert_contains(markdown, "Why This Helps", "markdown")
    assert_public_safe(markdown, "markdown")

    blocked = build_host_mode_plan(
        goal_id="workflow-selector-fixture",
        user_intent="continue_without_ui",
        host_capabilities=["loopx_turn"],
        agent_id="codex-main-control",
        registered_agents=["codex-main-control"],
    )
    blocked_markdown = render_host_mode_plan_markdown(blocked)
    assert_contains(blocked_markdown, "Blocking Reasons", "blocked markdown")
    assert_contains(blocked_markdown, "typed host adapter", "blocked markdown")
    assert_contains(blocked_markdown, "Stop before attempting this host mode", "blocked markdown")
    assert_public_safe(blocked_markdown, "blocked markdown")

    contract = CONTRACT_PATH.read_text()
    assert_contains(contract, "dry_run_host_mode_selector", "workflow contract")
    assert_contains(contract, "loopx turn plan", "workflow contract")
    assert_contains(contract, "independent validation", "workflow contract")
    assert_contains(contract, "typed_host_adapter", "workflow contract")
    assert_public_safe(contract, "workflow contract")

    turn_contract = TURN_CONTRACT_PATH.read_text()
    assert_contains(turn_contract, "LoopX decides -> agent CLI executes", "turn contract")
    assert_contains(turn_contract, "independent validator", "turn contract")

    protocol_index = PROTOCOL_INDEX_PATH.read_text()
    assert_contains(protocol_index, "host_mode_plan_v0", "protocol index")

    catalog = CONNECTOR_CATALOG_PATH.read_text()
    assert_contains(catalog, "`loopx_turn`", "connector catalog")
    assert_contains(catalog, "Host mode plan v0", "connector catalog")


def main() -> int:
    test_intent_selects_distinct_host_modes()
    test_headless_maps_to_loopx_turn_plan_not_parallel_runner()
    test_visible_mode_stays_visible_and_scoped()
    test_visible_mode_preserves_distinct_host_identities()
    test_visible_mode_fails_closed_without_host_identity()
    test_visible_mode_fails_closed_for_unregistered_host_identity()
    test_emitted_connector_ids_exist_in_catalog()
    test_readiness_fails_closed_without_required_host_capabilities()
    test_shell_service_fails_closed_without_adapter_and_validator()
    test_hybrid_requires_two_ready_modes_and_names_handoffs()
    test_identity_gate_and_no_spend_boundary()
    test_unknown_values_fail_closed()
    test_markdown_and_docs_are_wired()
    print("host-mode-planner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
