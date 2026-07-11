from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from ..work_items.interaction_contract import (
    PROTOCOL_ACTION_PACKET_LLM_POLICY,
    protocol_action_packet_fields,
    render_protocol_action_packet_summary,
)
from ..work_items.primary_action import protocol_action_text


TURN_ENVELOPE_SCHEMA_VERSION = "loopx_turn_envelope_v0"
TURN_ENVELOPE_BUDGET_BYTES = 8_192
CONTRACT_CAPSULE_SCHEMA_VERSION = "loopx_contract_capsule_v0"
ACTION_SIGNATURE_SCHEMA_VERSION = "loopx_action_signature_v0"
ACTION_SIGNATURE_COVERAGE = "turn_envelope_action_dimensions_v0"
ACTIONABLE_WARNING_FIELDS = (
    "state_projection_gap",
    "boundary_projection_gap",
    "state_action_projection_warning",
    "next_action_projection_warning",
    "stale_latest_run_warning",
    "decision_freshness_warning",
)
CONTRACT_CAPSULE_FIELDS = {
    "interaction_contract": (
        "schema_version",
        "mode",
    ),
    "work_lane_contract": (
        "schema_version",
        "lane",
        "monitor_kind",
        "next_lane",
        "obligation",
        "must_attempt_work",
        "reason_codes",
        "monitor_policy",
        "selected_todo_id",
        "selected_next_due_at",
        "material_transition",
        "action",
    ),
    "execution_profile": (
        "cadence",
        "minimum_scale",
        "spend_rule",
        "must_include",
    ),
    "execution_obligation": (
        "kind",
        "contract",
        "contract_obligation",
        "must_attempt_work",
        "notify_is_execution_gate",
        "delivery_allowed",
        "reason",
    ),
    "goal_route_hint": (
        "schema_version",
        "kind",
        "route_decision",
        "preserves_goal_next_action",
        "goal_next_action_mutation",
    ),
    "autonomous_replan_scope": (
        "schema_version",
        "required",
        "applies",
        "scope",
        "owner_agent_ids",
        "selected_peer_agent",
    ),
    "agent_scope_frontier": (
        "schema_version",
        "action",
        "effective_action",
        "blocks_delivery",
        "quiet_noop_allowed",
        "requires_replan",
        "recommended_action",
        "spend_policy",
    ),
    "automation_liveness": (
        "schema_version",
        "keep_active",
        "pause_allowed",
        "pause_policy",
        "automation_action",
    ),
    "vision_continuation_audit": (
        "schema_version",
        "required",
        "decision",
        "selected_todo_is_goal_completion",
        "closeout_allowed_without_evidence",
        "required_before_closeout",
        "recommended_action",
    ),
    "handoff_readiness": (
        "ready",
        "codex_ready",
        "handoff_status",
        "post_handoff_run_seen",
    ),
    "capability_monitor_fallback": (
        "schema_version",
        "capability_gate_action",
        "blocked_advancement_count",
        "mode",
    ),
}
CONTRACT_CAPSULE_TEXT_LIMITS = {
    "work_lane_contract": {"action": 300, "material_transition": 240},
    "execution_obligation": {"reason": 240},
    "agent_scope_frontier": {"recommended_action": 320, "spend_policy": 220},
    "automation_liveness": {"pause_policy": 260},
    "vision_continuation_audit": {"recommended_action": 320},
}


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


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _compact_fields(
    value: Any,
    fields: tuple[str, ...],
    *,
    text_limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    source = _mapping(value)
    compact: dict[str, Any] = {}
    limits = dict(text_limits or {})
    for field in fields:
        raw = source.get(field)
        if raw is None:
            continue
        if field in limits:
            text = _text(raw, limit=limits[field])
            if text:
                compact[field] = text
        elif isinstance(raw, list):
            values = _text_list(raw, limit=6, item_limit=140)
            if values:
                compact[field] = values
        else:
            compact[field] = raw
    return compact


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


def _execution_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "normal_delivery_allowed",
        "recovery_delivery_allowed",
        "self_repair_allowed",
        "capability_repair_allowed",
        "workspace_repair_allowed",
        "safe_bypass_allowed",
        "safe_bypass_kind",
        "blocked_action_scope",
    )
    return {field: payload[field] for field in fields if payload.get(field) is not None}


def _derived_protocol_action_packet_fields(
    *,
    action: Mapping[str, Any],
    user: Mapping[str, Any],
    capsule: Mapping[str, Any],
    scheduler: Mapping[str, Any],
) -> dict[str, Any]:
    interaction = _mapping(capsule.get("interaction_contract"))
    work_lane = _mapping(capsule.get("work_lane_contract"))
    automation = _mapping(capsule.get("automation_liveness"))
    mode = str(interaction.get("mode") or "")
    user_required = bool(user.get("action_required"))
    agent_required = bool(action.get("must_attempt"))
    actor = (
        "agent_with_user_gate"
        if user_required
        and mode in {"scoped_user_gate_fallback", "bounded_delivery_with_user_notice"}
        else "user"
        if user_required
        else "agent"
    )
    fields: dict[str, Any] = {
        "actor": actor,
        "user_action_required": user_required,
        "agent_action_required": agent_required,
        "quiet_noop_allowed": bool(action.get("quiet_noop_allowed")),
    }
    if work_lane.get("lane"):
        fields["lane"] = work_lane.get("lane")
    if automation.get("automation_action"):
        fields["automation"] = automation.get("automation_action")
    if scheduler.get("action"):
        fields["scheduler"] = scheduler.get("action")
    if automation.get("pause_allowed") is False:
        fields["pause_allowed"] = False
    fields["llm"] = PROTOCOL_ACTION_PACKET_LLM_POLICY

    user_actions = user.get("actions") if isinstance(user.get("actions"), list) else []
    action_key = "agent_action" if agent_required or not user_required else "user_action"
    if user_actions and (not user_required or action_key != "user_action"):
        fields["user_action_pending"] = True
        user_action = _text(user_actions[0], limit=80)
        if user_action:
            fields["user_action"] = user_action

    if agent_required:
        action_value = action.get("primary_action")
    elif user_required and user_actions:
        action_value = user_actions[0]
    elif work_lane.get("obligation") == "quiet_until_material_monitor_transition":
        action_value = (
            "quiet until a material monitor transition, regression, or concrete blocker appears"
        )
    else:
        action_value = action.get("primary_action") or "quiet no-op; no material transition"
    text = _text(action_value, limit=80)
    if text:
        fields[action_key] = text
    return fields


def _contract_capsule(
    payload: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    user: Mapping[str, Any],
    scheduler: Mapping[str, Any],
) -> dict[str, Any]:
    capsule: dict[str, Any] = {
        "schema_version": CONTRACT_CAPSULE_SCHEMA_VERSION,
        "source": "full_quota_decision",
    }
    for source_key, fields in CONTRACT_CAPSULE_FIELDS.items():
        compact = _compact_fields(
            payload.get(source_key),
            fields,
            text_limits=CONTRACT_CAPSULE_TEXT_LIMITS.get(source_key),
        )
        if compact:
            capsule[source_key] = compact

    work_lane = _mapping(payload.get("work_lane_contract"))
    work_lane_compact = _mapping(capsule.get("work_lane_contract"))
    outcome_followthrough = _mapping(work_lane.get("outcome_followthrough"))
    if outcome_followthrough:
        work_lane_compact["outcome_followthrough"] = _compact_fields(
            outcome_followthrough,
            (
                "required",
                "obligation",
                "accepted_resolution_kinds",
                "spend_policy",
            ),
            text_limits={"spend_policy": 220},
        )
        capsule["work_lane_contract"] = work_lane_compact

    packet = _mapping(payload.get("protocol_action_packet"))
    if packet:
        summary = _text(packet.get("summary"), limit=2_000)
        source_fields = protocol_action_packet_fields(dict(payload))
        derived_fields = _derived_protocol_action_packet_fields(
            action=action,
            user=user,
            capsule=capsule,
            scheduler=scheduler,
        )
        residue = {
            key: value
            for key, value in source_fields.items()
            if derived_fields.get(key) != value
        }
        reconstructed_fields = {
            key: residue.get(key, derived_fields.get(key)) for key in source_fields
        }
        reconstructed_summary = render_protocol_action_packet_summary(reconstructed_fields)
        reconstruction_verified = bool(summary) and reconstructed_summary == summary
        packet_projection: dict[str, Any] = {
            "schema_version": packet.get("schema_version"),
            "present": True,
            "summary_hash": _canonical_hash(summary or ""),
            "derivation_status": (
                "verified_with_residue" if residue else "verified"
            )
            if reconstruction_verified
            else "unverified_retain_summary",
            "reconstruction_verified": reconstruction_verified,
            "llm_policy": PROTOCOL_ACTION_PACKET_LLM_POLICY,
            "candidate_derivation_inputs": [
                "action",
                "user",
                "work_lane_contract",
                "automation_liveness",
                "scheduler",
            ],
        }
        if residue:
            packet_projection["residue"] = residue
        if not reconstruction_verified:
            packet_projection["summary"] = summary
        capsule["protocol_action_packet"] = packet_projection

    warnings = [field for field in ACTIONABLE_WARNING_FIELDS if payload.get(field)]
    if warnings:
        capsule["actionable_warning_refs"] = warnings
    return capsule


def _action_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    interaction = _mapping(payload.get("interaction_contract"))
    agent_channel = _mapping(interaction.get("agent_channel"))
    cli_channel = _mapping(interaction.get("cli_channel"))
    action = {
        "recommended_action": _text(payload.get("recommended_action"), limit=480),
        "primary_action": _text(agent_channel.get("primary_action"), limit=480),
        "must_attempt": bool(agent_channel.get("must_attempt")),
        "delivery_allowed": bool(agent_channel.get("delivery_allowed")),
        "quiet_noop_allowed": bool(agent_channel.get("quiet_noop_allowed")),
        "selected_todo": _selected_todo(payload),
    }
    user = _user_channel(interaction, payload)
    scheduler = _scheduler(payload)
    return {
        "decision": payload.get("decision"),
        "should_run": bool(payload.get("should_run")),
        "effective_action": payload.get("effective_action"),
        "state": payload.get("state"),
        "action": action,
        "user": user,
        "required_reads": _required_reads(interaction, payload),
        "boundary": _boundary(payload),
        "execution_policy": _execution_policy(payload),
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
        "scheduler": scheduler,
        "contract_capsule": _contract_capsule(
            payload,
            action=action,
            user=user,
            scheduler=scheduler,
        ),
    }


def turn_envelope_action_signature_document(envelope: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "decision",
        "should_run",
        "effective_action",
        "state",
        "action",
        "user",
        "required_reads",
        "boundary",
        "execution_policy",
        "writeback",
        "scheduler",
        "contract_capsule",
    )
    return {
        "schema_version": ACTION_SIGNATURE_SCHEMA_VERSION,
        "coverage": ACTION_SIGNATURE_COVERAGE,
        **{field: envelope.get(field) for field in fields},
    }


def quota_action_signature_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    return turn_envelope_action_signature_document(_action_projection(payload))


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

    agent_identity = _mapping(payload.get("agent_identity"))
    agent_id = str(agent_identity.get("agent_id") or "").strip() or None

    envelope: dict[str, Any] = {
        "ok": bool(payload.get("ok")),
        "schema_version": TURN_ENVELOPE_SCHEMA_VERSION,
        "mode": "should-run",
        "view": "turn_envelope",
        "goal_id": payload.get("goal_id"),
        "agent_id": agent_id,
        "reason": _text(payload.get("reason"), limit=360),
        "action_required": bool(payload.get("action_required")),
        "open_count": int(payload.get("open_count") or 0),
        **_action_projection(payload),
        "detail_ref": _cold_path(payload, agent_id),
    }

    source_signature = quota_action_signature_document(payload)
    envelope_signature = turn_envelope_action_signature_document(envelope)
    envelope["action_signature"] = {
        "schema_version": ACTION_SIGNATURE_SCHEMA_VERSION,
        "coverage": ACTION_SIGNATURE_COVERAGE,
        "source_hash": _canonical_hash(source_signature),
        "envelope_hash": _canonical_hash(envelope_signature),
        "matches": source_signature == envelope_signature,
        "source_decision_hash": _canonical_hash(dict(payload)),
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
