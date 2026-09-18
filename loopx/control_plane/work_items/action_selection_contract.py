from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any

from ..agents.capability_gate import runtime_capabilities_for_cli_projection


def render_cli_command_prefix(*, runtime_root: str | None = None) -> str:
    return (
        f"loopx --runtime-root {shlex.quote(str(runtime_root))}"
        if runtime_root
        else "loopx"
    )


def action_portfolio_requires_explicit_selection(
    payload: Mapping[str, Any],
) -> bool:
    portfolio = payload.get("action_portfolio")
    if not isinstance(portfolio, Mapping):
        return False
    policy = portfolio.get("selection_policy")
    return bool(
        isinstance(policy, Mapping)
        and policy.get("requires_explicit_turn_binding") is True
    )


def action_portfolio_selection_command_template(
    payload: Mapping[str, Any],
    *,
    scoped_cli_args: str,
    scheduler_args: str,
    turn_instance_id: str | None,
    runtime_root: str | None = None,
) -> str | None:
    if not action_portfolio_requires_explicit_selection(payload):
        return None
    goal_id = str(payload.get("goal_id") or "").strip()
    if not goal_id:
        return None
    turn_arg = (
        f" --turn-instance-id {shlex.quote(turn_instance_id)}"
        if turn_instance_id
        else ""
    )
    command_prefix = "loopx"
    if runtime_root:
        command_prefix += f" --runtime-root {shlex.quote(str(runtime_root))}"
    return (
        f"{command_prefix} --format json quota should-run"
        f" --goal-id {shlex.quote(goal_id)}"
        " --todo-id {todo_id}"
        f"{scoped_cli_args}{scheduler_args}{turn_arg}"
    )


def apply_action_selection_agent_gate(
    channel: dict[str, Any],
    payload: Mapping[str, Any],
) -> None:
    if not action_portfolio_requires_explicit_selection(payload):
        return
    portfolio = payload.get("action_portfolio")
    suggested_actions = (
        portfolio.get("suggested_actions")
        if isinstance(portfolio, Mapping)
        else None
    )
    channel.update(
        {
            "selection_required": True,
            "delivery_allowed": False,
            "primary_action": (
                "choose any current eligible Todo; recommendations are non-binding"
            ),
            "suggested_action_count": (
                len(suggested_actions)
                if isinstance(suggested_actions, list)
                else 0
            ),
        }
    )


def apply_action_selection_cli_gate(
    channel: dict[str, Any],
    payload: Mapping[str, Any],
) -> None:
    if not action_portfolio_requires_explicit_selection(payload):
        return
    actions = channel.get("next_cli_actions")
    command_template = (
        actions[0]
        if isinstance(actions, list)
        and len(actions) == 1
        and isinstance(actions[0], str)
        else None
    )
    channel["next_cli_actions"] = []
    goal_id = str(payload.get("goal_id") or "").strip()
    command_args_template: str | None = None
    route_prefix = "loopx --format json"
    if command_template:
        try:
            command_tokens = shlex.split(command_template)
        except ValueError:
            command_tokens = []
        try:
            format_index = command_tokens.index("--format")
        except ValueError:
            format_index = -1
        if (
            format_index >= 1
            and command_tokens[format_index : format_index + 2]
            == ["--format", "json"]
            and command_tokens[0] == "loopx"
        ):
            command_args_template = shlex.join(command_tokens[format_index + 2 :])
            route_prefix = shlex.join(command_tokens[: format_index + 2])
        else:
            route_prefix = "loopx --format json"
    if command_args_template is None:
        raise RuntimeError(
            "explicit action selection requires one typed quota command template"
        )
    channel.update(
        {
            "selection_required": True,
            "selection_policy_ref": "$.action_portfolio.selection_policy",
            "spend_policy": (
                "no delivery or quota spend until one eligible action is "
                "explicitly bound by rerunning quota in this turn"
            ),
            "selection_command": {
                "schema_version": "action_selection_cli_command_v1",
                "route_prefix": route_prefix,
                "command_args_template": command_args_template,
                "candidate_discovery_args": (
                    "todo list"
                    f" --goal-id {shlex.quote(goal_id)}"
                    " --role agent --status open --limit 50"
                ),
            },
        }
    )


def delivery_spend_allowed(
    payload: Mapping[str, Any],
    spend_after_validation: bool,
) -> bool:
    return spend_after_validation and not action_portfolio_requires_explicit_selection(
        payload
    )


def apply_action_selection_recovery(
    payload: dict[str, Any],
    *,
    registry_path: str,
    runtime_root: str,
    goal_id: str,
    agent_id: str,
    turn_instance_id: str | None,
    scheduler_args: str,
    available_capabilities: Any = None,
) -> None:
    """Render typed selection recovery before offering any settlement effects."""
    qualification = payload.get("action_selection_qualification") or {}
    if qualification.get("recovery_action") != "reenter_guard_without_selection":
        raise RuntimeError("rejected action selection omitted its typed recovery action")
    argv = ["loopx", "--registry", registry_path, "--runtime-root", runtime_root,
            "--format", "json", "quota", "should-run", "--goal-id", goal_id,
            "--agent-id", agent_id]
    if turn_instance_id:
        argv.extend(["--turn-instance-id", turn_instance_id])
    for capability in runtime_capabilities_for_cli_projection(available_capabilities):
        argv.extend(["--available-capability", capability])
    command = shlex.join(argv) + scheduler_args
    payload["spend_allowed_now"] = False
    payload["spend_after_validation"] = False
    # The current replan has not been admitted for this turn. Keeping its
    # action packet would replace recovery in the compact TurnEnvelope.
    payload.pop("replan_action_packet", None)
    interaction = payload.get("interaction_contract") or {}
    agent = interaction.get("agent_channel") or {}
    agent.update(must_attempt=False, delivery_allowed=False, primary_action=command)
    cli = interaction.get("cli_channel") or {}
    for field in ("settlement_plan", "replan_settlement_contract", "selection_command", "selection_policy_ref"):
        cli.pop(field, None)
    cli.update(next_cli_actions=[command], selection_required=False,
               spend_allowed_now=False, spend_after_validation=False,
               spend_policy="rerun this turn's guard before delivery or settlement")
    interaction.update(agent_channel=agent, cli_channel=cli)
    payload["interaction_contract"] = interaction
