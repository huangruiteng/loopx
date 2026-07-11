from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..work_items.primary_action import protocol_action_text


TURN_ENVELOPE_SCHEMA_VERSION = "loopx_turn_envelope_v0"
TURN_ENVELOPE_BUDGET_BYTES = 8_192


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, *, limit: int) -> str | None:
    return protocol_action_text(value, limit=limit) or None


def _text_list(value: Any, *, limit: int, item_limit: int = 240) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item, limit=item_limit)
        if not text or text in result:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _selected_todo(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    source = _mapping(payload.get("selected_todo"))
    if not source:
        return None
    fields = (
        "todo_id",
        "priority",
        "status",
        "task_class",
        "action_kind",
        "claimed_by",
        "blocks_agent",
        "unblocks_todo_id",
        "next_due_at",
        "expires_at",
        "selected_by",
        "confidence",
    )
    compact = {field: source[field] for field in fields if source.get(field) is not None}
    text = _text(source.get("text"), limit=360)
    if text:
        compact["text"] = text
    return compact or None


def _user_channel(interaction: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(interaction.get("user_channel"))
    channel: dict[str, Any] = {
        "action_required": bool(source.get("action_required", payload.get("action_required"))),
        "open_count": int(payload.get("open_count") or 0),
        "notify": str(source.get("notify") or "DONT_NOTIFY"),
    }
    actions = _text_list(source.get("actions"), limit=3, item_limit=360)
    if actions:
        channel["actions"] = actions
    reason = _text(source.get("reason"), limit=360)
    if reason:
        channel["reason"] = reason
    return channel


def _required_reads(interaction: Mapping[str, Any], payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_reads = interaction.get("required_reads") or payload.get("required_reads")
    if not isinstance(raw_reads, list):
        return []
    reads: list[dict[str, Any]] = []
    for item in raw_reads[:5]:
        if not isinstance(item, Mapping):
            continue
        command = _text(item.get("command"), limit=360)
        if not command:
            continue
        compact = {"command": command}
        for field in ("kind", "reason", "source"):
            text = _text(item.get(field), limit=240)
            if text:
                compact[field] = text
        reads.append(compact)
    return reads


def _boundary(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(payload.get("goal_boundary"))
    boundary: dict[str, Any] = {
        "rule": str(source.get("rule") or "stay_in_scope_or_stop"),
    }
    adapter = _mapping(source.get("adapter"))
    if adapter:
        boundary["adapter"] = {
            field: adapter[field]
            for field in ("kind", "status")
            if adapter.get(field) is not None
        }
    for field in ("write_scope", "available_capabilities", "requires_parent_approval"):
        values = _text_list(source.get(field), limit=16, item_limit=180)
        if values:
            boundary[field] = values
    guards = _text_list(source.get("guards"), limit=8, item_limit=280)
    if guards:
        boundary["guards"] = guards
    stop_condition = _text(source.get("stop_condition"), limit=320)
    if stop_condition:
        boundary["stop_condition"] = stop_condition
    for field in ("execution_profile", "orchestration"):
        value = _mapping(source.get(field))
        if value:
            boundary[field] = value

    workspace_guard = _mapping(payload.get("workspace_guard"))
    if workspace_guard:
        boundary["workspace_guard"] = workspace_guard
    capability_gate = _mapping(payload.get("capability_gate"))
    if capability_gate:
        boundary["capability_gate"] = {
            field: capability_gate[field]
            for field in (
                "action",
                "reason",
                "required_capabilities",
                "missing_capabilities",
                "owner_action",
            )
            if capability_gate.get(field) is not None
        }
    return boundary


def _scheduler(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(payload.get("scheduler_hint"))
    scheduler: dict[str, Any] = {
        field: source[field]
        for field in ("action", "cadence_class", "spend_policy")
        if source.get(field) is not None
    }
    codex_app = _mapping(source.get("codex_app"))
    if not codex_app:
        return scheduler
    app: dict[str, Any] = {
        field: codex_app[field]
        for field in ("apply", "host_action", "recommended_rrule", "no_spend_for_cadence_change")
        if codex_app.get(field) is not None
    }
    state = _mapping(codex_app.get("stateful_backoff"))
    if state:
        app["stateful_backoff"] = {
            field: state[field]
            for field in ("state_key", "current_rrule", "apply_needed", "state_status")
            if state.get(field) is not None
        }
    ack = _mapping(codex_app.get("ack_hint"))
    cli_args = _text_list(ack.get("cli_args"), limit=20, item_limit=180)
    if cli_args:
        app["ack_cli_args"] = cli_args
    if app:
        scheduler["codex_app"] = app
    return scheduler


def _cold_path(payload: Mapping[str, Any], agent_id: str | None) -> dict[str, Any]:
    goal_id = str(payload.get("goal_id") or "<goal-id>")
    agent_arg = f" --agent-id {agent_id}" if agent_id else ""
    return {
        "full_decision": (
            f"loopx --format json quota should-run --goal-id {goal_id}{agent_arg}"
        ),
        "todo_detail": f"loopx --format json todo list --goal-id {goal_id}",
        "status_detail": f"loopx --format json status --goal-id {goal_id}",
        "contains": [
            "quota accounting detail",
            "goal frontier and route diagnostics",
            "full todo summaries",
            "handoff and readiness diagnostics",
            "promotion, archive, and projection warnings",
            "scheduler runtime detail",
        ],
    }


def build_turn_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project a full quota decision into an additive, model-facing hot-path view."""

    interaction = _mapping(payload.get("interaction_contract"))
    agent_channel = _mapping(interaction.get("agent_channel"))
    cli_channel = _mapping(interaction.get("cli_channel"))
    agent_identity = _mapping(payload.get("agent_identity"))
    agent_id = str(agent_identity.get("agent_id") or "").strip() or None

    envelope: dict[str, Any] = {
        "ok": bool(payload.get("ok")),
        "schema_version": TURN_ENVELOPE_SCHEMA_VERSION,
        "mode": "should-run",
        "view": "turn_envelope",
        "goal_id": payload.get("goal_id"),
        "agent_id": agent_id,
        "decision": payload.get("decision"),
        "should_run": bool(payload.get("should_run")),
        "effective_action": payload.get("effective_action"),
        "state": payload.get("state"),
        "reason": _text(payload.get("reason"), limit=360),
        "action_required": bool(payload.get("action_required")),
        "open_count": int(payload.get("open_count") or 0),
        "action": {
            "recommended_action": _text(payload.get("recommended_action"), limit=480),
            "primary_action": _text(agent_channel.get("primary_action"), limit=480),
            "must_attempt": bool(agent_channel.get("must_attempt")),
            "delivery_allowed": bool(agent_channel.get("delivery_allowed")),
            "quiet_noop_allowed": bool(agent_channel.get("quiet_noop_allowed")),
            "selected_todo": _selected_todo(payload),
        },
        "user": _user_channel(interaction, payload),
        "required_reads": _required_reads(interaction, payload),
        "boundary": _boundary(payload),
        "writeback": {
            "next_cli_actions": _text_list(
                cli_channel.get("next_cli_actions"),
                limit=5,
                item_limit=420,
            ),
            "spend_allowed_now": bool(cli_channel.get("spend_allowed_now")),
            "spend_after_validation": bool(cli_channel.get("spend_after_validation")),
            "spend_policy": _text(cli_channel.get("spend_policy"), limit=280),
        },
        "scheduler": _scheduler(payload),
        "detail_ref": _cold_path(payload, agent_id),
    }

    source_bytes = len(json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")))
    envelope["compaction"] = {
        "source_json_bytes": source_bytes,
        "envelope_json_bytes": 0,
        "byte_reduction_ratio": 0.0,
        "budget_bytes": TURN_ENVELOPE_BUDGET_BYTES,
        "within_budget": True,
    }
    for _ in range(3):
        envelope_bytes = len(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
        envelope["compaction"].update(
            {
                "envelope_json_bytes": envelope_bytes,
                "byte_reduction_ratio": (
                    round(1 - envelope_bytes / source_bytes, 4) if source_bytes else 0.0
                ),
                "within_budget": envelope_bytes <= TURN_ENVELOPE_BUDGET_BYTES,
            }
        )
    return envelope
