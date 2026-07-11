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
SUPERVISOR_OBSERVATION_SCHEMA_VERSION = "supervisor_observation_v0"


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


def _goal_attention_item(status_payload: Mapping[str, Any], goal_id: str) -> dict[str, Any]:
    attention = status_payload.get("attention_queue")
    items = attention.get("items") if isinstance(attention, Mapping) else None
    if not isinstance(items, list):
        return {}
    return next(
        (
            dict(item)
            for item in items
            if isinstance(item, Mapping) and str(item.get("goal_id") or "") == goal_id
        ),
        {},
    )


def _agent_management_items(status_payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    projection = status_payload.get("agent_management_projection")
    items = projection.get("agents") if isinstance(projection, Mapping) else None
    if not isinstance(items, list):
        return {}
    return {
        agent_id: dict(item)
        for item in items
        if isinstance(item, Mapping)
        for agent_id in [normalize_todo_claimed_by(item.get("agent_id"))]
        if agent_id
    }


def _evidence_refs(
    member: Mapping[str, Any],
    evidence_log: Mapping[str, Any],
) -> list[str]:
    refs = [
        str(value)
        for value in member.get("evidence_refs") or []
        if isinstance(value, str) and value.strip()
    ]
    ledger = evidence_log.get("ledger")
    for row in ledger if isinstance(ledger, list) else []:
        if not isinstance(row, Mapping):
            continue
        candidates = (
            ("rollout_event", row.get("event_id")),
            ("runtime_run", row.get("run_id")),
            ("run_history", row.get("run_ref")),
        )
        for kind, raw_value in candidates:
            value = " ".join(str(raw_value or "").split())
            ref = f"{kind}:{value}" if value else ""
            if ref and ref not in refs:
                refs.append(ref)
    return refs[:8]


def build_supervisor_observation_packet(
    *,
    goal_id: str,
    supervisor: Mapping[str, Any],
    status_payload: Mapping[str, Any],
    evidence_logs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one read-only public-safe supervisor input over existing projections."""

    contract = build_peer_supervisor_contract(goal_id=goal_id, supervisor=supervisor)
    attention = _goal_attention_item(status_payload, goal_id)
    members = _agent_management_items(status_payload)
    warnings = []
    if status_payload.get("ok") is not True:
        warnings.append("status_projection_degraded")
    if not attention:
        warnings.append(f"missing_goal_status:{goal_id}")
    peer_rows = []
    for agent_id in contract["supervised_agents"]:
        member = members.get(agent_id, {})
        evidence = evidence_logs.get(agent_id, {})
        ledger = evidence.get("ledger") if isinstance(evidence.get("ledger"), list) else []
        if not member:
            warnings.append(f"missing_agent_status:{agent_id}")
        if evidence.get("ok") is not True:
            warnings.append(f"missing_evidence_log:{agent_id}")
        current_todo = member.get("current_todo")
        peer_rows.append(
            {
                "agent_id": agent_id,
                "state": member.get("state") or "unknown",
                "current_todo": dict(current_todo) if isinstance(current_todo, Mapping) else None,
                "next_action": member.get("next_action"),
                "last_activity_at": member.get("last_activity_at"),
                "workspace_ref": member.get("workspace_ref"),
                "handoff_refs": list(member.get("handoff_refs") or [])[:4],
                "stale_claim_hint": member.get("stale_claim_hint"),
                "evidence": {
                    "ledger_count": int(evidence.get("ledger_count") or 0),
                    "matched_count": int(evidence.get("matched_count") or 0),
                    "truncated": evidence.get("truncated") is True,
                    "latest_recorded_at": ledger[0].get("recorded_at") if ledger else None,
                    "latest_rows": [dict(row) for row in ledger[:3] if isinstance(row, Mapping)],
                    "effect_refs": _evidence_refs(member, evidence),
                },
            }
        )
    project_asset = attention.get("project_asset")
    raw_user_todos = (
        project_asset.get("user_todos")
        if isinstance(project_asset, Mapping)
        else None
    )
    if not isinstance(raw_user_todos, Mapping):
        raw_user_todos = attention.get("user_todos")
    user_todos = raw_user_todos if isinstance(raw_user_todos, Mapping) else {}
    generated_at = None
    management = status_payload.get("agent_management_projection")
    if isinstance(management, Mapping):
        generated_at = management.get("generated_at")
    return {
        "ok": True,
        "schema_version": SUPERVISOR_OBSERVATION_SCHEMA_VERSION,
        "mode": "read_only",
        "goal_id": goal_id,
        "supervisor_agent_id": contract["supervisor_agent_id"],
        "observed_at": generated_at,
        "status_health": {
            "ok": status_payload.get("ok") is True,
            "contract_error_count": int(
                status_payload.get("contract_errors_total_count")
                or len(status_payload.get("contract_errors") or [])
            ),
            "contract_warning_count": int(
                status_payload.get("contract_warnings_total_count")
                or len(status_payload.get("contract_warnings") or [])
            ),
        },
        "goal": {
            "status": attention.get("status"),
            "waiting_on": attention.get("waiting_on"),
            "severity": attention.get("severity"),
            "recommended_action": attention.get("recommended_action"),
            "user_open_count": int(
                user_todos.get("open") or user_todos.get("open_count") or 0
            ),
        },
        "peers": peer_rows,
        "warnings": warnings,
        "decision_input_complete": not warnings,
        "decision_contract": contract["decision_contract"],
        "execution_policy": contract["execution_policy"],
        "boundary": {
            "source": "LoopX public-safe status and agent evidence projections",
            "raw_logs_included": False,
            "raw_trajectories_included": False,
            "raw_transcripts_included": False,
            "write_authority": "none",
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
    observe_command = (
        f"{cli_bin} --format json supervisor-observe --goal-id "
        f"{shlex.quote(goal_id)} --agent-id {shlex.quote(agent_id)}"
    )
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

Run your own quota guard. Then read one supervisor observation packet assembled
from read-only agent status and thin evidence projections. Do not impersonate
another peer's quota guard or reconstruct this packet from raw transcripts:

```bash
{cli_bin} --format json quota should-run --goal-id {shlex.quote(goal_id)} --agent-id {shlex.quote(agent_id)}
{observe_command}
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
        "observe_command": observe_command,
        "task_body": task_body,
    }


def render_supervisor_observation_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "\n".join(
            [
                "# LoopX Supervisor Observation",
                "",
                "- ok: `False`",
                f"- error: {payload.get('error') or 'unknown error'}",
            ]
        )
    lines = [
        "# LoopX Supervisor Observation",
        "",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- supervisor_agent_id: `{payload.get('supervisor_agent_id')}`",
        f"- observed_at: `{payload.get('observed_at') or ''}`",
        f"- decision_input_complete: `{payload.get('decision_input_complete')}`",
        f"- warning_count: `{len(payload.get('warnings') or [])}`",
        "",
        "## Peers",
        "",
    ]
    for peer in payload.get("peers") or []:
        if not isinstance(peer, dict):
            continue
        current_todo = peer.get("current_todo") or {}
        evidence = peer.get("evidence") or {}
        lines.append(
            f"- `{peer.get('agent_id')}` state=`{peer.get('state')}` "
            f"todo=`{current_todo.get('todo_id') or ''}` "
            f"evidence=`{evidence.get('ledger_count') or 0}`"
        )
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in warnings)
    return "\n".join(lines)


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
