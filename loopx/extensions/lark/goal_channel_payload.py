from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...control_plane.todos.contract import normalize_todo_decision_scope
from ...todos import add_goal_todo, complete_goal_todo, list_goal_todos
from .goal_channel_contracts import operation_packet
from .goal_channel_delivery_contract import (
    goal_channel_binding_digest,
    goal_channel_delivery_route,
)
from .goal_channel_message_delivery import (
    GoalChannelMessageDeliverySession,
    resolve_bound_goal_channel,
)
from .outbound import normalize_lark_outbound_text
from .presentation.kanban import CommandRunner, default_subprocess_runner
from .presentation.message_card import build_lark_markdown_reply_card
from .private_json import write_private_json_atomic


FROZEN_PAYLOAD_REQUEST_SCHEMA = "goal_channel_frozen_payload_request_v0"
FROZEN_PAYLOAD_RECEIPT_SCHEMA = "goal_channel_frozen_payload_receipt_v0"
_RECEIPT_ID_RE = re.compile(r"^gcp_[0-9a-f]{24}$")
_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,127}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _required_text(value: object, label: str, *, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return text


def _token(value: object, label: str) -> str:
    token = str(value or "").strip().lower()
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError(f"{label} must be a public-safe opaque token")
    return token


def _decision_scope_text(scope: Mapping[str, Any]) -> str:
    return f"{scope['kind']}:{scope['granularity']}:{scope['scope_key']}"


def _normalized_request(request: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "capability_id",
        "payload_ref",
        "title",
        "markdown",
        "footer",
        "decision_scope",
        "public_safe",
    }
    extra = sorted(set(request) - allowed)
    if extra:
        raise ValueError(f"frozen payload request contains unsupported fields: {extra}")
    if request.get("schema_version") != FROZEN_PAYLOAD_REQUEST_SCHEMA:
        raise ValueError(f"request must use {FROZEN_PAYLOAD_REQUEST_SCHEMA}")
    if request.get("public_safe") is not True:
        raise ValueError(
            "producing capability must attest that the frozen payload is public-safe"
        )
    scope = normalize_todo_decision_scope(request.get("decision_scope"))
    if (
        scope is None
        or scope["kind"] != "public_claim"
        or scope["granularity"] != "action"
        or "*" in scope["scope_key"]
    ):
        raise ValueError(
            "frozen Goal Channel payload requires a public_claim:action decision scope"
        )
    title = _required_text(request.get("title"), "title", maximum=72)
    footer = _required_text(request.get("footer"), "footer", maximum=96)
    markdown = normalize_lark_outbound_text(
        request.get("markdown"), limit=3600, preserve_format=True
    )
    if re.search(r"<\s*at\b", markdown, re.IGNORECASE):
        raise ValueError("frozen Goal Channel payload must not contain mentions")
    card = build_lark_markdown_reply_card(
        markdown, title=title, footer=footer, max_markdown_chars=3600
    )
    return {
        "capability_id": _token(request.get("capability_id"), "capability_id"),
        "payload_ref": _token(request.get("payload_ref"), "payload_ref"),
        "title": title,
        "markdown": markdown,
        "footer": footer,
        "decision_scope": scope,
        "card": card,
        "payload_digest": _canonical_digest(card),
    }


def _receipt_identity(
    *,
    goal_id: str,
    request: Mapping[str, Any],
    binding_digest: str,
    agent_id: str,
) -> str:
    digest = _canonical_digest(
        {
            "goal_id": goal_id,
            "capability_id": request["capability_id"],
            "payload_ref": request["payload_ref"],
            "payload_digest": request["payload_digest"],
            "decision_scope": request["decision_scope"],
            "binding_digest": binding_digest,
            "agent_id": agent_id,
        }
    )
    return "gcp_" + digest.removeprefix("sha256:")[:24]


def _receipt_path(runtime_root: Path, goal_id: str, receipt_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", goal_id):
        raise ValueError("goal_id must be a stable LoopX Goal id")
    if not _RECEIPT_ID_RE.fullmatch(receipt_id):
        raise ValueError("receipt_id must be a Goal Channel frozen payload id")
    return (
        runtime_root
        / "goals"
        / goal_id
        / "goal_channel_payloads"
        / f"{receipt_id}.json"
    )


def _read_receipt(runtime_root: Path, goal_id: str, receipt_id: str) -> dict[str, Any]:
    path = _receipt_path(runtime_root, goal_id, receipt_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Goal Channel frozen payload receipt is unavailable") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != FROZEN_PAYLOAD_RECEIPT_SCHEMA
        or payload.get("receipt_id") != receipt_id
        or payload.get("goal_id") != goal_id
    ):
        raise ValueError("Goal Channel frozen payload receipt is invalid")
    card = payload.get("card")
    scope = normalize_todo_decision_scope(payload.get("decision_scope"))
    if (
        not isinstance(card, Mapping)
        or _canonical_digest(card) != payload.get("payload_digest")
        or not _DIGEST_RE.fullmatch(str(payload.get("payload_digest") or ""))
        or not _DIGEST_RE.fullmatch(str(payload.get("binding_digest") or ""))
        or scope is None
        or scope["kind"] != "public_claim"
        or scope["granularity"] != "action"
        or payload.get("status") not in {"approval_pending", "satisfied"}
        or _receipt_identity(
            goal_id=goal_id,
            request=payload,
            binding_digest=str(payload.get("binding_digest") or ""),
            agent_id=str(payload.get("agent_id") or ""),
        )
        != receipt_id
    ):
        raise ValueError("Goal Channel frozen payload receipt content drifted")
    return payload


def prepare_goal_channel_payload(
    request: Mapping[str, Any],
    *,
    registry_path: Path,
    runtime_root: Path,
    binding_path: Path,
    target_path: Path,
    goal_id: str,
    agent_id: str,
    execute: bool = False,
) -> dict[str, Any]:
    """Freeze one capability-owned public payload behind an exact user gate."""

    normalized = _normalized_request(request)
    binding = resolve_bound_goal_channel(
        binding_path=binding_path,
        target_path=target_path,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    binding_digest = goal_channel_binding_digest(binding)
    receipt_id = _receipt_identity(
        goal_id=goal_id,
        request=normalized,
        binding_digest=binding_digest,
        agent_id=agent_id,
    )
    receipt_path = _receipt_path(runtime_root, goal_id, receipt_id)
    if receipt_path.exists():
        receipt = _read_receipt(runtime_root, goal_id, receipt_id)
        return operation_packet(
            ok=True,
            goal_id=goal_id,
            operation="prepare_payload",
            execute=execute,
            status=str(receipt["status"]),
            public_summary="reused the exact frozen Goal Channel payload",
            idempotency_key=receipt_id,
            receipt_id=receipt_id,
            details={
                "capability_id": receipt["capability_id"],
                "payload_digest": receipt["payload_digest"],
                "decision_scope": _decision_scope_text(receipt["decision_scope"]),
                "delivery_todo_id": receipt["delivery_todo_id"],
                "approval_todo_id": receipt["approval_todo_id"],
                "already_prepared": True,
            },
        )

    scope_text = _decision_scope_text(normalized["decision_scope"])
    digest_suffix = normalized["payload_digest"].removeprefix("sha256:")[:16]
    delivery = add_goal_todo(
        registry_path=registry_path,
        goal_id=goal_id,
        role="agent",
        text=f"[P0] Deliver frozen Goal Channel payload {receipt_id}.",
        status="blocked",
        note=(
            "Use only the frozen private receipt and the unchanged project_bot "
            "Goal Channel binding; require exact provider-native readback."
        ),
        task_class="advancement_task",
        action_kind="deliver_goal_channel_payload",
        task_domain="provider_delivery",
        capability_binding_ref=f"goal-channel:g{digest_suffix}",
        required_write_scopes=["goal_channel/lark/messages"],
        required_capabilities=["network", "lark_bot_message_write"],
        target_capabilities=[normalized["capability_id"], "goal_channel"],
        required_decision_scopes=[scope_text],
        claimed_by=agent_id,
        agent_id=agent_id,
        runtime_root_arg=str(runtime_root),
        dry_run=not execute,
    )
    gate = add_goal_todo(
        registry_path=registry_path,
        goal_id=goal_id,
        role="user",
        text=(
            "Approve the exact frozen public payload "
            f"{receipt_id} ({normalized['payload_digest']}) for Goal Channel delivery."
        ),
        note=(
            "Approval covers only this frozen card digest and current Goal Channel "
            "binding; rejection or cancellation keeps delivery blocked."
        ),
        task_class="user_gate",
        action_kind="approve_goal_channel_payload",
        decision_scope=scope_text,
        bound_agent=agent_id,
        blocks_agent=agent_id,
        unblocks_todo_id=str(delivery["todo_id"]),
        agent_id=agent_id,
        runtime_root_arg=str(runtime_root),
        dry_run=not execute,
    )
    receipt = {
        "schema_version": FROZEN_PAYLOAD_RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "goal_id": goal_id,
        "capability_id": normalized["capability_id"],
        "payload_ref": normalized["payload_ref"],
        "payload_digest": normalized["payload_digest"],
        "decision_scope": normalized["decision_scope"],
        "binding_digest": binding_digest,
        "agent_id": agent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": normalized["title"],
        "markdown": normalized["markdown"],
        "footer": normalized["footer"],
        "card": normalized["card"],
        "delivery_todo_id": delivery["todo_id"],
        "approval_todo_id": gate["todo_id"],
        "status": "approval_pending",
        "delivery": None,
    }
    if execute:
        write_private_json_atomic(receipt_path, receipt)
    return operation_packet(
        ok=True,
        goal_id=goal_id,
        operation="prepare_payload",
        execute=execute,
        status="approval_pending" if execute else "pending_execution",
        public_summary=(
            "froze one Goal Channel payload and created its exact approval gate"
            if execute
            else "validated one Goal Channel payload preparation"
        ),
        idempotency_key=receipt_id,
        receipt_id=receipt_id,
        details={
            "capability_id": normalized["capability_id"],
            "payload_digest": normalized["payload_digest"],
            "decision_scope": scope_text,
            "delivery_todo_id": delivery["todo_id"],
            "approval_todo_id": gate["todo_id"],
            "already_prepared": False,
        },
    )


def _todo(
    *, registry_path: Path, runtime_root: Path, goal_id: str, todo_id: str
) -> dict[str, Any] | None:
    payload = list_goal_todos(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=todo_id,
        runtime_root_arg=str(runtime_root),
    )
    todo = payload.get("todo")
    return dict(todo) if isinstance(todo, Mapping) else None


def _approval_verified(
    *, receipt: Mapping[str, Any], registry_path: Path, runtime_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    goal_id = str(receipt["goal_id"])
    delivery = _todo(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=goal_id,
        todo_id=str(receipt["delivery_todo_id"]),
    )
    gate = _todo(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=goal_id,
        todo_id=str(receipt["approval_todo_id"]),
    )
    expected_scope = normalize_todo_decision_scope(receipt["decision_scope"])
    expected_binding_ref = (
        "goal-channel:g" + str(receipt["payload_digest"]).removeprefix("sha256:")[:16]
    )
    agent_id = str(receipt["agent_id"])
    if delivery is None or gate is None or expected_scope is None:
        raise ValueError("frozen Goal Channel approval lifecycle is unavailable")
    if (
        gate.get("status") != "done"
        or gate.get("decision_outcome") != "approve"
        or normalize_todo_decision_scope(gate.get("decision_scope")) != expected_scope
        or gate.get("unblocks_todo_id") != delivery.get("todo_id")
        or gate.get("action_kind") != "approve_goal_channel_payload"
        or gate.get("blocks_agent") != agent_id
        or gate.get("bound_agent") != agent_id
        or receipt["receipt_id"] not in str(gate.get("text") or "")
        or delivery.get("status") not in {"open", "done"}
        or delivery.get("required_decision_scopes")
        or delivery.get("action_kind") != "deliver_goal_channel_payload"
        or delivery.get("claimed_by") != agent_id
        or delivery.get("capability_binding_ref") != expected_binding_ref
        or receipt["receipt_id"] not in str(delivery.get("text") or "")
    ):
        raise ValueError("frozen Goal Channel payload lacks exact approval")
    return delivery, gate


def deliver_goal_channel_payload(
    *,
    receipt_id: str,
    registry_path: Path,
    runtime_root: Path,
    binding_path: Path,
    target_path: Path,
    goal_id: str,
    execute: bool = False,
    runner: CommandRunner = default_subprocess_runner,
) -> dict[str, Any]:
    """Deliver one approved frozen payload with exact dedupe and readback."""

    receipt = _read_receipt(runtime_root, goal_id, receipt_id)
    delivery_todo, _gate = _approval_verified(
        receipt=receipt, registry_path=registry_path, runtime_root=runtime_root
    )
    agent_id = str(receipt["agent_id"])
    binding = resolve_bound_goal_channel(
        binding_path=binding_path,
        target_path=target_path,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    if goal_channel_binding_digest(binding) != receipt["binding_digest"]:
        raise ValueError("Goal Channel binding drifted after payload approval")
    route = goal_channel_delivery_route(goal_id, lambda _goal_id: binding)
    idempotency_key = _canonical_digest(
        {
            "goal_id": goal_id,
            "payload_digest": receipt["payload_digest"],
            "binding_digest": receipt["binding_digest"],
        }
    )
    if not execute:
        return operation_packet(
            ok=True,
            goal_id=goal_id,
            operation="deliver_payload",
            execute=False,
            status="pending_execution",
            public_summary="validated one approved frozen Goal Channel payload",
            idempotency_key=idempotency_key,
            receipt_id=receipt_id,
            details={
                "capability_id": receipt["capability_id"],
                "payload_digest": receipt["payload_digest"],
                "approval_verified": True,
            },
        )

    def resolve_current() -> Mapping[str, Any]:
        return resolve_bound_goal_channel(
            binding_path=binding_path,
            target_path=target_path,
            goal_id=goal_id,
            agent_id=agent_id,
        )

    session = GoalChannelMessageDeliverySession(
        goal_id=goal_id,
        binding=binding,
        history_start_at=str(receipt["created_at"]),
        resolve_current_binding=resolve_current,
        runner=runner,
    )
    if session.verify(route) is not True:
        raise ValueError("Goal Channel sender identity could not be verified")
    sent = dict(session.send(receipt["card"], idempotency_key, route))
    message_id = str(sent.get("message_id") or "")
    observed = dict(session.readback(message_id))
    verified = bool(
        observed.get("verified") is True
        and observed.get("message_id") == message_id
        and observed.get("chat_id") == route["chat_id"]
        and observed.get("sender_app_id") == route["bot_app_id"]
        and observed.get("sender_identity") == "bot"
        and observed.get("sender_evidence_source") == "message_readback"
    )
    if not verified:
        return operation_packet(
            ok=False,
            goal_id=goal_id,
            operation="deliver_payload",
            execute=True,
            status="readback_unverified",
            public_summary="Goal Channel delivery did not satisfy exact native readback",
            external_write_performed=sent.get("external_write_performed") is True,
            readback_verified=False,
            idempotency_key=idempotency_key,
            receipt_id=receipt_id,
            blocker="readback_unverified",
        )
    if delivery_todo.get("status") != "done":
        completed = complete_goal_todo(
            registry_path=registry_path,
            goal_id=goal_id,
            runtime_root_arg=str(runtime_root),
            todo_id=str(delivery_todo["todo_id"]),
            role="agent",
            claimed_by=agent_id,
            agent_id=agent_id,
            no_followup=True,
            evidence=(
                "Exact frozen Goal Channel payload delivered with provider-native "
                f"sender, chat, and content readback ({receipt['payload_digest']})."
            ),
        )
        if completed.get("ok") is not True:
            raise ValueError("Goal Channel delivery Todo completion failed")
    receipt["status"] = "satisfied"
    receipt["delivery"] = {
        "message_id": message_id,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "readback_verified": True,
        "semantic_dedupe_status": sent.get("semantic_dedupe_status"),
    }
    write_private_json_atomic(_receipt_path(runtime_root, goal_id, receipt_id), receipt)
    return operation_packet(
        ok=True,
        goal_id=goal_id,
        operation="deliver_payload",
        execute=True,
        status="satisfied",
        public_summary="delivered one approved frozen Goal Channel payload with exact readback",
        external_write_performed=sent.get("external_write_performed") is True,
        readback_verified=True,
        idempotency_key=idempotency_key,
        receipt_id=receipt_id,
        details={
            "capability_id": receipt["capability_id"],
            "payload_digest": receipt["payload_digest"],
            "approval_verified": True,
            "delivery_todo_completed": True,
            "semantic_dedupe_status": sent.get("semantic_dedupe_status"),
        },
    )


__all__ = [
    "FROZEN_PAYLOAD_RECEIPT_SCHEMA",
    "FROZEN_PAYLOAD_REQUEST_SCHEMA",
    "deliver_goal_channel_payload",
    "prepare_goal_channel_payload",
]
