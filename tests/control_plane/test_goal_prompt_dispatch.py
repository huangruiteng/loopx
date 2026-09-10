"""Native Goal bootstrap delegates policy to the current quota contract."""

import pytest

from loopx.heartbeat_prompt import build_heartbeat_prompt


@pytest.mark.parametrize(
    "host", ["codex_cli", "codex_app_ssh_goal", "ark_managed_agent_goal", "traex"]
)
def test_goal_prompt_has_one_live_execution_entry(host: str) -> None:
    kwargs = {"visible_goal_host": "traex-cli", "runtime_profile": "generic_cli"} if host == "traex" else {
        "runtime_profile": host
    }
    packet = build_heartbeat_prompt(
        goal_id="contract-fixture", agent_id="worker-a",
        registered_agents=["worker-a"], **kwargs,
    )
    body = packet["task_body"]
    assert "Each work iteration" in body
    assert "complete successful JSON" in body
    assert "interaction_contract" in body
    assert "settlement_plan.ordered_steps" in body
    assert "selection_command" in body
    assert "next_cli_actions" in body
    assert packet["quota_spend_command"] not in body
    assert packet["progress_refresh_state_command"] not in body
    assert "Do not reconstruct" in body
    assert "new host Goal" in body
    assert "terminal no-follow-up" in body
    assert "notification" in body
    assert "no work/spend" in body
    assert "No permission asks in a trusted session" not in body
    assert len(body) < 2400


def test_codex_wait_rule_is_not_exported_to_other_goal_hosts() -> None:
    codex = build_heartbeat_prompt(goal_id="contract-fixture", runtime_profile="codex_cli")
    ark = build_heartbeat_prompt(goal_id="contract-fixture", runtime_profile="ark_managed_agent_goal")
    assert "status=blocked" in codex["task_body"]
    assert "status=blocked" not in ark["task_body"]
    assert "do not invoke LoopX Turn" in ark["task_body"]


def test_explicit_goal_policy_is_preserved_not_replaced_by_bootstrap_defaults() -> None:
    packet = build_heartbeat_prompt(
        goal_id="contract-fixture", runtime_profile="codex_cli",
        permission_rule="Only edit the assigned workspace.",
        material_queue_rule="Use the approved reference set only.",
    )
    assert "Only edit the assigned workspace." in packet["task_body"]
    assert "Use the approved reference set only." in packet["task_body"]
