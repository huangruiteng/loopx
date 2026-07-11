from __future__ import annotations

import json
import shlex
from enum import Enum
from typing import Any, Mapping

from ...agent_registry import normalize_registered_agents
from ..todos.contract import normalize_todo_claimed_by


PEER_SUPERVISOR_SCHEMA_VERSION = "peer_supervisor_v0"
SUPERVISOR_CONTRACT_SCHEMA_VERSION = "peer_supervisor_contract_v0"
SUPERVISOR_DECISION_SCHEMA_VERSION = "supervisor_decision_v0"


class SupervisorDecisionKind(str, Enum):
    OBSERVE = "observe"
    INJECT = "inject"
    HANDOFF = "handoff"
    DISCARD = "discard"


HOST_CAPABILITIES_BY_DECISION = {
    SupervisorDecisionKind.OBSERVE.value: [],
    SupervisorDecisionKind.INJECT.value: ["session_message_injection"],
    SupervisorDecisionKind.HANDOFF.value: [
        "session_state_fork",
        "workspace_state_transfer",
    ],
    SupervisorDecisionKind.DISCARD.value: ["session_termination"],
}


def _normalized_tokens(values: Any, *, field: str) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{field} must be a list")
    normalized = []
    for value in values:
        token = normalize_todo_claimed_by(value)
        if not token:
            raise ValueError(f"{field} must contain public-safe tokens")
        if token not in normalized:
            normalized.append(token)
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def _required_text(payload: Mapping[str, Any], field: str, *, limit: int = 400) -> str:
    value = " ".join(str(payload.get(field) or "").strip().split())
    if not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


def normalize_peer_supervisor(
    raw: Any,
    *,
    registered_agents: list[str] | tuple[str, ...],
) -> dict[str, Any] | None:
    if raw in (None, {}):
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("coordination.supervisor must be an object")
    if raw.get("enabled") is False:
        return None

    registered = normalize_registered_agents(list(registered_agents))
    agent_id = normalize_todo_claimed_by(raw.get("agent_id"))
    if not agent_id:
        raise ValueError("coordination.supervisor.agent_id must be a registered agent id")
    if agent_id not in registered:
        raise ValueError(
            f"supervisor agent_id={agent_id!r} is not registered; "
            f"registered_agents={', '.join(registered)}"
        )

    raw_supervised = raw.get("supervised_agents")
    supervised = (
        normalize_registered_agents(raw_supervised)
        if raw_supervised is not None
        else [agent for agent in registered if agent != agent_id]
    )
    if agent_id in supervised:
        raise ValueError("a supervisor cannot supervise its own agent session")
    unknown = [agent for agent in supervised if agent not in registered]
    if unknown:
        raise ValueError(
            "supervised agents must be registered peers; unknown=" + ", ".join(unknown)
        )
    if not supervised:
        raise ValueError("a supervisor requires at least one other supervised peer")

    return {
        "schema_version": PEER_SUPERVISOR_SCHEMA_VERSION,
        "enabled": True,
        "agent_id": agent_id,
        "supervised_agents": supervised,
        "execution_mode": "proposal_only",
    }


def peer_supervisor_for_goal(goal: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(goal, Mapping):
        return None
    coordination = goal.get("coordination")
    if not isinstance(coordination, Mapping):
        return None
    return normalize_peer_supervisor(
        coordination.get("supervisor"),
        registered_agents=normalize_registered_agents(
            coordination.get("registered_agents")
        ),
    )


def build_peer_supervisor_contract(
    *,
    goal_id: str,
    supervisor: Mapping[str, Any],
) -> dict[str, Any]:
    agent_id = str(supervisor.get("agent_id") or "")
    supervised_agents = normalize_registered_agents(
        supervisor.get("supervised_agents")
    )
    return {
        "schema_version": SUPERVISOR_CONTRACT_SCHEMA_VERSION,
        "goal_id": goal_id,
        "supervisor_agent_id": agent_id,
        "supervised_agents": supervised_agents,
        "peer_authority": "equal_identity_authority",
        "supervisor_authority": "proposal_only",
        "user_interaction": {
            "recommended_channel": agent_id,
            "reason": "one synthesis channel is useful while several peers run",
            "user_may_interact_with_any_peer": True,
            "user_gates_remain_loopx_state": True,
        },
        "observation_sources": [
            "goal_status",
            "supervisor_quota_contract",
            "agent_status_projections",
            "todo_projection",
            "agent_evidence_logs",
            "compact_runtime_effect_refs",
        ],
        "decision_contract": {
            "schema_version": SUPERVISOR_DECISION_SCHEMA_VERSION,
            "kinds": [kind.value for kind in SupervisorDecisionKind],
            "required_fields": [
                "decision_id",
                "kind",
                "reason_codes",
                "evidence_refs",
                "execution_status",
            ],
            "conditional_fields": {
                "inject": ["target_agent_id", "message"],
                "handoff": [
                    "source_agent_id",
                    "target_agent_id",
                    "state_ref",
                ],
                "discard": ["target_agent_id", "state_ref"],
            },
        },
        "execution_policy": {
            "mode": "proposal_only",
            "required_host_capabilities_by_kind": HOST_CAPABILITIES_BY_DECISION,
            "missing_capability_behavior": "leave proposal unexecuted",
            "destructive_actions_require_explicit_host_authority": True,
        },
    }


def normalize_supervisor_decision(
    raw: Mapping[str, Any],
    *,
    supervisor: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("supervisor decision must be an object")
    try:
        kind = SupervisorDecisionKind(str(raw.get("kind") or ""))
    except ValueError as exc:
        choices = ", ".join(item.value for item in SupervisorDecisionKind)
        raise ValueError(f"kind must be one of: {choices}") from exc

    decision_id = normalize_todo_claimed_by(raw.get("decision_id"))
    if not decision_id:
        raise ValueError("decision_id must be a public-safe token")
    supervised = normalize_registered_agents(supervisor.get("supervised_agents"))
    result = {
        "schema_version": SUPERVISOR_DECISION_SCHEMA_VERSION,
        "decision_id": decision_id,
        "kind": kind.value,
        "reason_codes": _normalized_tokens(raw.get("reason_codes"), field="reason_codes"),
        "evidence_refs": _normalized_tokens(raw.get("evidence_refs"), field="evidence_refs"),
        "execution_status": "proposal_only",
        "required_host_capabilities": list(HOST_CAPABILITIES_BY_DECISION[kind.value]),
    }
    if kind is SupervisorDecisionKind.OBSERVE:
        return result

    target_agent_id = normalize_todo_claimed_by(raw.get("target_agent_id"))
    if target_agent_id not in supervised:
        raise ValueError("target_agent_id must be one of the configured supervised peers")
    result["target_agent_id"] = target_agent_id

    if kind is SupervisorDecisionKind.INJECT:
        result["message"] = _required_text(raw, "message")
    elif kind is SupervisorDecisionKind.HANDOFF:
        source_agent_id = normalize_todo_claimed_by(raw.get("source_agent_id"))
        if source_agent_id not in supervised:
            raise ValueError("source_agent_id must be one of the configured supervised peers")
        if source_agent_id == target_agent_id:
            raise ValueError("handoff source and target agents must differ")
        result["source_agent_id"] = source_agent_id
        result["state_ref"] = _required_text(raw, "state_ref", limit=240)
    elif kind is SupervisorDecisionKind.DISCARD:
        result["state_ref"] = _required_text(raw, "state_ref", limit=240)
    return result


def build_supervisor_prompt(
    *,
    goal_id: str,
    active_state: str,
    supervisor: Mapping[str, Any],
    cli_bin: str = "loopx",
) -> dict[str, Any]:
    contract = build_peer_supervisor_contract(
        goal_id=goal_id,
        supervisor=supervisor,
    )
    agent_id = str(contract["supervisor_agent_id"])
    supervised_agents = list(contract["supervised_agents"])
    status_commands = [
        (
            f"{cli_bin} --format json status --goal-id "
            f"{shlex.quote(goal_id)} --agent-id {shlex.quote(peer)}"
        )
        for peer in supervised_agents
    ]
    evidence_commands = [
        (
            f"{cli_bin} --format json evidence-log --goal-id "
            f"{shlex.quote(goal_id)} --agent-id {shlex.quote(peer)} --thin"
        )
        for peer in supervised_agents
    ]
    decision_template = {
        "schema_version": SUPERVISOR_DECISION_SCHEMA_VERSION,
        "decision_id": "<stable_public_safe_id>",
        "kind": "observe|inject|handoff|discard",
        "target_agent_id": "<required_except_observe>",
        "source_agent_id": "<required_for_handoff>",
        "message": "<required_for_inject>",
        "state_ref": "<required_for_handoff_or_discard>",
        "reason_codes": ["<typed_reason>"],
        "evidence_refs": ["<public_safe_compact_ref>"],
        "execution_status": "proposal_only",
        "required_host_capabilities": ["<from_contract>"],
    }
    task_body = f"""Supervise `{goal_id}` using `{active_state}`.

You are `{agent_id}`, an equal LoopX peer with an additional opt-in supervisor
observation responsibility. You are not a durable leader and do not own other
peers' todos, sessions, merge rights, user gates, or quota.

The user may use this task as the preferred synthesis channel while several
peers run, but may still talk to any peer. Keep all user decisions and gates in
LoopX state so every peer sees the same authority.

Run your own quota guard. Then read each supervised peer through its read-only
agent status projection and thin evidence log. Do not impersonate another
peer's quota guard. Prefer compact runtime effect references over raw
transcripts or private logs:

```bash
{cli_bin} --format json quota should-run --goal-id {shlex.quote(goal_id)} --agent-id {shlex.quote(agent_id)}
{chr(10).join(status_commands)}
{chr(10).join(evidence_commands)}
```

Compare the peers' claimed work, evidence freshness, blockers, workspace state,
and effect references. Emit at most one typed decision:

- `observe`: no intervention; evidence does not justify changing a run.
- `inject`: propose a bounded message to one existing session.
- `handoff`: propose continuing a target session from a named source state.
- `discard`: propose terminating a failed or harmful branch while preserving its
  compact evidence reference.

Return the decision in this shape:

```json
{json.dumps(decision_template, ensure_ascii=True, indent=2)}
```

This prototype is proposal-only. Never claim an injection, handoff, discard, or
session termination happened unless a host adapter exposes every required
capability and returns execution evidence. Missing capabilities leave the
proposal unexecuted. Do not mutate peer claims merely to make the proposal look
resolved.
"""
    return {
        "ok": True,
        "goal_id": goal_id,
        "active_state": active_state,
        "agent_id": agent_id,
        "supervisor_contract": contract,
        "task_body": task_body,
    }


def render_supervisor_prompt_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "\n".join(
            [
                "# LoopX Supervisor Prompt",
                "",
                "- ok: `False`",
                f"- error: {payload.get('error') or 'unknown error'}",
            ]
        )
    contract = payload.get("supervisor_contract") or {}
    return "\n".join(
        [
            "# LoopX Supervisor Prompt",
            "",
            "- ok: `True`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- agent_id: `{payload.get('agent_id')}`",
            "- supervised_agents: `"
            + ", ".join(contract.get("supervised_agents") or [])
            + "`",
            "- execution_mode: `proposal_only`",
            "",
            "## Task Body",
            "",
            str(payload.get("task_body") or ""),
        ]
    )
