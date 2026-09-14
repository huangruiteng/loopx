from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ...chat_action_store import ActionConflictError, ChatActionStore
from ...control_plane.effect_runtime import effect_runtime_result
from ...file_lock import exclusive_file_lock
from ...extensions.runtime import (
    default_extension_state_file,
    execute_extension_runtime_binding,
    resolve_extension_binding,
)
from .goal_channel_contracts import operation_packet
from .goal_channel_delivery_contract import (
    goal_channel_binding_digest,
    goal_channel_delivery_route,
)
from .goal_channel_message_delivery import (
    GoalChannelMessageDeliverySession,
    resolve_bound_goal_channel,
)
from .goal_channel_transport import call, json_payload, lark_args
from .presentation.kanban import CommandRunner, default_subprocess_runner


OPERATION_CARD_ACTION_SCHEMA_VERSION = "loopx_operation_card_action_v0"
OPERATION_CALLBACK_RECEIPT_SCHEMA_VERSION = "lark_operation_callback_receipt_v0"
OPERATION_EXECUTOR_CAPABILITY_ID = "human-confirmed-operation-executor"
_EVENT_ID = re.compile(r"^[A-Za-z0-9._:-]{1,240}$")
_MESSAGE_ID = re.compile(r"^om_[A-Za-z0-9_-]+$")
_CHAT_ID = re.compile(r"^oc_[A-Za-z0-9_-]+$")
_OPEN_ID = re.compile(r"^ou_[A-Za-z0-9_-]+$")


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _card_text(value: object) -> str:
    text = html.escape(str(value or "").strip(), quote=True)
    for character, entity in {
        "*": "&#42;",
        "~": "&#126;",
        "[": "&#91;",
        "]": "&#93;",
        "(": "&#40;",
        ")": "&#41;",
        "#": "&#35;",
        "_": "&#95;",
    }.items():
        text = text.replace(character, entity)
    return text


def _proposal_operation(
    proposal: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    parameters = proposal.get("normalized_parameters")
    operation = proposal.get("operation")
    if (
        proposal.get("action_kind") != "operation.execute"
        or not isinstance(parameters, dict)
        or not isinstance(operation, dict)
    ):
        raise ValueError("typed operation proposal is unavailable")
    return parameters, operation


def _field_markdown(fields: list[Mapping[str, Any]]) -> str:
    return "\n".join(
        f"**{_card_text(field.get('label'))}**\n{_card_text(field.get('value'))}"
        for field in fields
    )


def _operation_review_frame(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Read provider-neutral operation presentation semantics from TypeScript."""

    plan = effect_runtime_result(
        "presentation.action_review_plan.compile",
        {"proposal": proposal},
    )
    if not isinstance(plan, Mapping):
        raise ValueError("operation review plan is unavailable")
    frame = plan.get("operationFrame")
    if (
        not isinstance(frame, Mapping)
        or frame.get("schemaVersion") != "operation_review_frame_v0"
        or frame.get("operationId") != proposal.get("proposal_id")
    ):
        raise ValueError("operation review frame is unavailable")
    return dict(frame)


def build_goal_channel_operation_card(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    frame = _operation_review_frame(proposal)
    if frame.get("kind") != "confirmation":
        raise ActionConflictError("operation is not awaiting confirmation")
    projection = frame.get("content")
    if not isinstance(projection, Mapping):
        raise ValueError("operation projection is unavailable")
    fields = projection.get("fields")
    if not isinstance(fields, list) or not all(
        isinstance(item, Mapping) for item in fields
    ):
        raise ValueError("operation projection fields are unavailable")
    action_base = {
        "schema_version": OPERATION_CARD_ACTION_SCHEMA_VERSION,
        "operation_id": frame["operationId"],
        "confirmation_digest": frame["confirmationDigest"],
    }
    simulated = frame.get("simulated") is True
    return {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "width_mode": "default",
            "enable_forward": False,
            "summary": {"content": str(projection["title"])},
        },
        "header": {
            "title": {"tag": "plain_text", "content": str(projection["title"])},
            "subtitle": {
                "tag": "plain_text",
                "content": str(projection["subtitle"]),
            },
            "template": "orange",
            "icon": {"tag": "standard_icon", "token": "approval_colorful"},
            "text_tag_list": [
                {
                    "tag": "text_tag",
                    "text": {
                        "tag": "plain_text",
                        "content": "SIMULATION" if simulated else "待确认",
                    },
                    "color": "yellow" if simulated else "orange",
                }
            ],
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 20px 12px",
            "vertical_spacing": "12px",
            "elements": [
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "background_style": "orange-50",
                            "corner_radius": "8px",
                            "padding": "12px",
                            "vertical_spacing": "2px",
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": (
                                        "**请求摘要**\n"
                                        f"{_card_text(projection['focus'])}"
                                    ),
                                }
                            ],
                        }
                    ],
                },
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "background_style": "grey-50",
                            "corner_radius": "8px",
                            "padding": "12px",
                            "vertical_spacing": "4px",
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": _field_markdown(fields),
                                }
                            ],
                        }
                    ],
                },
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "background_style": "red-50",
                            "corner_radius": "8px",
                            "padding": "12px",
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": (
                                        "**确认边界**\n"
                                        f"{_card_text(projection['warning'])}"
                                    ),
                                }
                            ],
                        }
                    ],
                },
                {
                    "tag": "column_set",
                    "flex_mode": "bisect",
                    "horizontal_spacing": "12px",
                    "columns": [
                        {
                            "tag": "column",
                            "elements": [
                                {
                                    "tag": "button",
                                    "text": {
                                        "tag": "plain_text",
                                        "content": "确认模拟执行"
                                        if simulated
                                        else "确认执行",
                                    },
                                    "type": "primary_filled",
                                    "width": "fill",
                                    "behaviors": [
                                        {
                                            "type": "callback",
                                            "value": {
                                                **action_base,
                                                "decision": "confirm",
                                            },
                                        }
                                    ],
                                    "confirm": {
                                        "title": {
                                            "tag": "plain_text",
                                            "content": "确认这个精确请求？",
                                        },
                                        "text": {
                                            "tag": "plain_text",
                                            "content": "修改任何条款都需要创建新请求。",
                                        },
                                    },
                                }
                            ],
                        },
                        {
                            "tag": "column",
                            "elements": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "拒绝"},
                                    "type": "danger",
                                    "width": "fill",
                                    "behaviors": [
                                        {
                                            "type": "callback",
                                            "value": {
                                                **action_base,
                                                "decision": "reject",
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            ],
        },
    }


def build_goal_channel_operation_result_card(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    frame = _operation_review_frame(proposal)
    if frame.get("kind") != "result":
        raise ActionConflictError("operation outcome is not available")
    projection = frame.get("content")
    if not isinstance(projection, Mapping):
        raise ValueError("operation result projection is unavailable")
    result_kind = frame.get("resultKind")
    rejected = result_kind == "rejected"
    simulated = result_kind == "simulation_completed"
    template = "red" if rejected else "green"
    result_label = "已拒绝" if rejected else "模拟完成" if simulated else "已完成"
    summary = str(frame.get("summary") or result_label)
    return {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "width_mode": "default",
            "enable_forward": False,
            "summary": {"content": f"{projection['title']} · {result_label}"},
        },
        "header": {
            "title": {"tag": "plain_text", "content": str(projection["title"])},
            "subtitle": {
                "tag": "plain_text",
                "content": str(projection["subtitle"]),
            },
            "template": template,
            "icon": {"tag": "standard_icon", "token": "approval_colorful"},
            "text_tag_list": [
                {
                    "tag": "text_tag",
                    "text": {"tag": "plain_text", "content": result_label},
                    "color": "red" if rejected else "green",
                }
            ],
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 20px 12px",
            "vertical_spacing": "12px",
            "elements": [
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "background_style": f"{template}-50",
                            "corner_radius": "8px",
                            "padding": "12px",
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": f"**{result_label}**\n{_card_text(summary)}",
                                }
                            ],
                        }
                    ],
                },
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "background_style": "grey-50",
                            "corner_radius": "8px",
                            "padding": "12px",
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": (
                                        f"**Operation**\n{frame['operationId']}\n"
                                        f"**Digest**\n{frame['confirmationDigest'][:16]}…"
                                    ),
                                    "text_size": "notation",
                                }
                            ],
                        }
                    ],
                },
            ],
        },
    }


def deliver_goal_channel_operation_card(
    *,
    proposal_id: str,
    action_store_root: Path,
    runtime_root: Path,
    binding_path: Path,
    target_path: Path,
    expected_goal_id: str | None = None,
    execute: bool = False,
    runner: CommandRunner = default_subprocess_runner,
    executor_binding_resolver: (
        Callable[[Mapping[str, Any], Path], Mapping[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    store = ChatActionStore(action_store_root)
    proposal = store.load(proposal_id)
    if proposal is None:
        raise ValueError("typed operation proposal was not found")
    parameters, operation = _proposal_operation(proposal)
    if operation.get("lifecycle_state") != "awaiting_confirmation":
        raise ActionConflictError("operation is not awaiting confirmation")
    goal_id = str(parameters["goal_id"])
    if expected_goal_id is not None and goal_id != expected_goal_id:
        raise ActionConflictError("operation proposal belongs to another goal")
    resolved_executor = dict(
        executor_binding_resolver(parameters, runtime_root)
        if executor_binding_resolver is not None
        else _resolve_operation_executor_binding(parameters, runtime_root=runtime_root)
    )
    if resolved_executor.get("revision") != parameters["executor"]["revision"]:
        raise ActionConflictError("operation executor revision is not ready")
    agent_id = str(parameters["agent_id"])
    binding = resolve_bound_goal_channel(
        binding_path=binding_path,
        target_path=target_path,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    route = goal_channel_delivery_route(goal_id, lambda _goal_id: binding)
    card = build_goal_channel_operation_card(proposal)
    card_digest = _digest(card)
    key = str(operation["confirmation_digest"])
    if not execute:
        return operation_packet(
            ok=True,
            goal_id=goal_id,
            operation="deliver_operation_card",
            execute=False,
            status="pending_execution",
            public_summary="validated one exact operation card for Goal Channel delivery",
            idempotency_key=key,
            receipt_id=proposal_id,
            details={
                "operation_id": proposal_id,
                "confirmation_digest": key,
                "card_digest": card_digest,
                "simulation": parameters["projection"]["simulated"] is True,
                "executor_preflight_verified": True,
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
        binding_lock_path=binding_path,
        target_lock_path=target_path,
        history_start_at=str(proposal["created_at"]),
        resolve_current_binding=resolve_current,
        runner=runner,
    )
    if session.verify(route) is not True:
        raise ValueError("Goal Channel sender identity could not be verified")
    sent = dict(session.send(card, key, route))
    message_id = str(sent.get("message_id") or "")
    observed = dict(session.readback(message_id))
    if not (
        observed.get("verified") is True
        and observed.get("message_id") == message_id
        and observed.get("chat_id") == route["chat_id"]
        and observed.get("sender_app_id") == route["bot_app_id"]
    ):
        return operation_packet(
            ok=False,
            goal_id=goal_id,
            operation="deliver_operation_card",
            execute=True,
            status="readback_unverified",
            public_summary="operation card delivery lacked exact native readback",
            external_write_performed=sent.get("external_write_performed") is True,
            readback_verified=False,
            idempotency_key=key,
            receipt_id=proposal_id,
            blocker="readback_unverified",
        )
    store.record_operation_delivery(
        proposal_id,
        delivery={
            "provider": "lark",
            "message_id": message_id,
            "chat_id": route["chat_id"],
            "app_id": route["bot_app_id"],
            "binding_digest": goal_channel_binding_digest(binding),
            "card_digest": card_digest,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return operation_packet(
        ok=True,
        goal_id=goal_id,
        operation="deliver_operation_card",
        execute=True,
        status="awaiting_confirmation",
        public_summary="delivered one exact operation card with native readback",
        external_write_performed=sent.get("external_write_performed") is True,
        readback_verified=True,
        idempotency_key=key,
        receipt_id=proposal_id,
        details={
            "operation_id": proposal_id,
            "confirmation_digest": key,
            "card_digest": card_digest,
            "semantic_dedupe_status": sent.get("semantic_dedupe_status"),
            "executor_preflight_verified": True,
        },
    )


def _callback_action(event: Mapping[str, Any]) -> dict[str, str]:
    if event.get("type") != "card.action.trigger":
        raise ValueError("operation callback event type is unsupported")
    if event.get("action_tag") != "button":
        raise ValueError("operation callback must come from a button")
    raw = event.get("action_value")
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError("operation callback action_value is invalid") from exc
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "operation_id",
        "confirmation_digest",
        "decision",
    }:
        raise ValueError("operation callback action is incomplete")
    if value.get("schema_version") != OPERATION_CARD_ACTION_SCHEMA_VERSION:
        raise ValueError("operation callback action schema is unsupported")
    decision = str(value.get("decision") or "")
    if decision not in {"confirm", "reject"}:
        raise ValueError("operation callback decision is unsupported")
    return {key: str(value[key]) for key in value}


def _callback_timestamp(value: object) -> str:
    token = str(value or "").strip()
    if not token.isdigit() or len(token) > 16:
        raise ValueError("operation callback timestamp is invalid")
    return (
        datetime.fromtimestamp(
            int(token) / 1000,
            tz=timezone.utc,
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def _operator_membership_verified(
    *,
    runner: CommandRunner,
    cli_bin: str,
    profile: str,
    chat_id: str,
    operator_id: str,
) -> bool:
    chat_result = call(
        runner,
        lark_args(
            cli_bin=cli_bin,
            profile=profile,
            tail=[
                "im",
                "chats",
                "get",
                "--chat-id",
                chat_id,
                "--as",
                "bot",
                "--format",
                "json",
            ],
        ),
    )
    member_result = call(
        runner,
        lark_args(
            cli_bin=cli_bin,
            profile=profile,
            tail=[
                "im",
                "+chat-members-list",
                "--chat-id",
                chat_id,
                "--member-types",
                "user",
                "--member-id-type",
                "open_id",
                "--page-all",
                "--as",
                "bot",
                "--format",
                "json",
            ],
        ),
    )
    if chat_result.get("returncode") != 0 or member_result.get("returncode") != 0:
        return False
    chat_payload = json_payload(chat_result)
    member_payload = json_payload(member_result)
    chat_tenant = _first_tenant_key(chat_payload)
    member_tenant = _member_tenant_key(member_payload, operator_id)
    return bool(chat_tenant and member_tenant and chat_tenant == member_tenant)


def _first_tenant_key(value: object) -> str | None:
    if isinstance(value, Mapping):
        candidate = value.get("tenant_key")
        if isinstance(candidate, str) and candidate:
            return candidate
        for child in value.values():
            if found := _first_tenant_key(child):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := _first_tenant_key(child):
                return found
    return None


def _member_tenant_key(value: object, operator_id: str) -> str | None:
    if isinstance(value, Mapping):
        identities = {
            str(value.get(key) or "")
            for key in ("member_id", "open_id", "operator_id", "id")
        }
        tenant_key = value.get("tenant_key")
        if operator_id in identities and isinstance(tenant_key, str) and tenant_key:
            return tenant_key
        for child in value.values():
            if found := _member_tenant_key(child, operator_id):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := _member_tenant_key(child, operator_id):
                return found
    return None


def _resolve_operation_executor_binding(
    parameters: Mapping[str, Any], *, runtime_root: Path
) -> dict[str, Any]:
    executor = parameters.get("executor")
    if not isinstance(executor, Mapping):
        raise ValueError("operation executor binding is unavailable")
    return resolve_extension_binding(
        str(executor["extension_id"]),
        state_file=default_extension_state_file(runtime_root),
        capability_id=OPERATION_EXECUTOR_CAPABILITY_ID,
        protocol=str(executor["protocol"]),
        permission=str(executor["permission"]),
    )


def _execute_claimed_operation(
    proposal: Mapping[str, Any], *, runtime_root: Path
) -> dict[str, Any]:
    parameters, operation = _proposal_operation(proposal)
    claim = operation.get("claim")
    executor = parameters.get("executor")
    if not isinstance(claim, Mapping) or not isinstance(executor, Mapping):
        raise ValueError("claimed operation executor binding is unavailable")
    binding = _resolve_operation_executor_binding(
        parameters,
        runtime_root=runtime_root,
    )
    if binding.get("revision") != executor.get("revision"):
        raise ActionConflictError(
            "operation executor revision changed after confirmation"
        )
    result = execute_extension_runtime_binding(
        binding,
        request={
            "schema_version": "finance_operation_execute_request_v0",
            "protocol": executor["protocol"],
            "permission": executor["permission"],
            "operation_id": operation["operation_id"],
            "operation_kind": parameters["operation_kind"],
            "operation_schema": parameters["operation_schema"],
            "payload": parameters["payload"],
            "payload_digest": operation["payload_digest"],
            "confirmation_digest": operation["confirmation_digest"],
            "claim_id": claim["claim_id"],
            "executor_revision": executor["revision"],
            "destination_account_ref": operation["destination_account_ref"],
        },
    )
    if (
        result.get("schema_version") != "loopx_operation_outcome_v0"
        or result.get("operation_id") != operation["operation_id"]
        or result.get("payload_digest") != operation["payload_digest"]
        or result.get("claim_id") != claim["claim_id"]
        or result.get("executor_revision") != executor["revision"]
        or result.get("simulation") is not True
        or result.get("external_write_performed") is not False
    ):
        raise ValueError("operation executor outcome does not match the consumed claim")
    return result


def _find_message(value: object, message_id: str) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        if str(value.get("message_id") or "") == message_id:
            return value
        for child in value.values():
            if found := _find_message(child, message_id):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := _find_message(child, message_id):
                return found
    return None


def _message_card(value: Mapping[str, Any]) -> Mapping[str, Any] | None:
    body = value.get("body")
    raw = body.get("content") if isinstance(body, Mapping) else value.get("content")
    try:
        card = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None
    return card if isinstance(card, Mapping) else None


def _result_card_readback_verified(
    payload: Mapping[str, Any],
    *,
    message_id: str,
    chat_id: str,
    app_id: str,
    card: Mapping[str, Any],
) -> bool:
    message = _find_message(payload, message_id)
    sender = message.get("sender") if isinstance(message, Mapping) else None
    observed_card = _message_card(message) if isinstance(message, Mapping) else None
    return bool(
        payload.get("ok") is True
        and isinstance(message, Mapping)
        and str(message.get("chat_id") or "") == chat_id
        and isinstance(sender, Mapping)
        and sender.get("sender_type") == "app"
        and sender.get("id") == app_id
        and isinstance(observed_card, Mapping)
        and _digest(observed_card) == _digest(card)
    )


def _read_result_card(
    *,
    runner: CommandRunner,
    cli_bin: str,
    profile: str,
    message_id: str,
) -> tuple[Mapping[str, Any], bool]:
    readback = call(
        runner,
        lark_args(
            cli_bin=cli_bin,
            profile=profile,
            tail=[
                "im",
                "+messages-mget",
                "--message-ids",
                message_id,
                "--as",
                "bot",
                "--no-reactions",
                "--format",
                "json",
            ],
        ),
    )
    return json_payload(readback), readback.get("returncode") == 0


def _update_callback_card(
    *,
    runner: CommandRunner,
    cli_bin: str,
    profile: str,
    token: str,
    card: Mapping[str, Any],
    message_id: str,
    chat_id: str,
    app_id: str,
) -> dict[str, bool]:
    result = call(
        runner,
        lark_args(
            cli_bin=cli_bin,
            profile=profile,
            tail=[
                "api",
                "POST",
                "/open-apis/interactive/v1/card/update",
                "--as",
                "bot",
                "--data",
                json.dumps(
                    {"token": token, "card": dict(card)},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ],
        ),
    )
    payload = json_payload(result)
    write_performed = result.get("returncode") == 0 and payload.get("ok") is True
    if not write_performed:
        return {"external_write_performed": False, "readback_verified": False}
    readback_payload, readback_ok = _read_result_card(
        runner=runner,
        cli_bin=cli_bin,
        profile=profile,
        message_id=message_id,
    )
    verified = bool(
        readback_ok
        and _result_card_readback_verified(
            readback_payload,
            message_id=message_id,
            chat_id=chat_id,
            app_id=app_id,
            card=card,
        )
    )
    return {
        "external_write_performed": True,
        "readback_verified": verified,
    }


def _patch_operation_result_card(
    *,
    runner: CommandRunner,
    cli_bin: str,
    profile: str,
    card: Mapping[str, Any],
    message_id: str,
    chat_id: str,
    app_id: str,
) -> dict[str, bool]:
    result = call(
        runner,
        lark_args(
            cli_bin=cli_bin,
            profile=profile,
            tail=[
                "im",
                "messages",
                "patch",
                "--message-id",
                message_id,
                "--data",
                json.dumps(
                    {
                        "content": json.dumps(
                            dict(card),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "--as",
                "bot",
                "--format",
                "json",
            ],
        ),
    )
    payload = json_payload(result)
    write_performed = result.get("returncode") == 0 and payload.get("ok") is True
    if not write_performed:
        return {"external_write_performed": False, "readback_verified": False}
    readback_payload, readback_ok = _read_result_card(
        runner=runner,
        cli_bin=cli_bin,
        profile=profile,
        message_id=message_id,
    )
    verified = readback_ok and _result_card_readback_verified(
        readback_payload,
        message_id=message_id,
        chat_id=chat_id,
        app_id=app_id,
        card=card,
    )
    return {
        "external_write_performed": True,
        "readback_verified": verified,
    }


def recover_goal_channel_operation_results(
    *,
    action_store_root: Path,
    profile_app_id: str,
    allowed_chat_ids: set[str],
    cli_bin: str,
    profile: str,
    runner: CommandRunner = default_subprocess_runner,
    limit: int = 20,
) -> dict[str, int]:
    """Retry only result-card delivery; never repeat a domain execution."""

    store = ChatActionStore(action_store_root)
    attempted = 0
    delivered = 0
    failed = 0
    for proposal in store.list():
        if attempted >= max(1, min(limit, 100)):
            break
        if proposal.get("action_kind") != "operation.execute":
            continue
        _parameters, operation = _proposal_operation(proposal)
        delivery = operation.get("delivery")
        if (
            operation.get("lifecycle_state") != "outcome_observed"
            or isinstance(operation.get("result_delivery"), Mapping)
            or not isinstance(delivery, Mapping)
            or delivery.get("provider") != "lark"
            or delivery.get("app_id") != profile_app_id
            or delivery.get("chat_id") not in allowed_chat_ids
        ):
            continue
        attempted += 1
        result_lock = store.root / f"{proposal['proposal_id']}.result-delivery.lock"
        with exclusive_file_lock(
            result_lock,
            agent_id="loopx-lark-operation",
            operation="recover_operation_result_delivery",
        ):
            current = store.load(str(proposal["proposal_id"]))
            if current is None:
                failed += 1
                continue
            _current_parameters, current_operation = _proposal_operation(current)
            if isinstance(current_operation.get("result_delivery"), Mapping):
                continue
            current_delivery = current_operation.get("delivery")
            if not isinstance(current_delivery, Mapping):
                failed += 1
                continue
            result_card = build_goal_channel_operation_result_card(current)
            result = _patch_operation_result_card(
                runner=runner,
                cli_bin=cli_bin,
                profile=profile,
                card=result_card,
                message_id=str(current_delivery["message_id"]),
                chat_id=str(current_delivery["chat_id"]),
                app_id=str(current_delivery["app_id"]),
            )
            if result["readback_verified"] is not True:
                failed += 1
                continue
            store.record_operation_result_delivery(
                str(proposal["proposal_id"]),
                delivery={
                    "provider": "lark",
                    "message_id": str(current_delivery["message_id"]),
                    "chat_id": str(current_delivery["chat_id"]),
                    "app_id": str(current_delivery["app_id"]),
                    "card_digest": _digest(result_card),
                    "transport": "message_patch",
                    "delivered_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            delivered += 1
    return {"attempted": attempted, "delivered": delivered, "failed": failed}


def recover_goal_channel_simulation_claims(
    *,
    action_store_root: Path,
    runtime_root: Path,
    limit: int = 20,
) -> dict[str, int]:
    """Resume only explicitly non-effectful M1 simulation claims after restart."""

    store = ChatActionStore(action_store_root)
    attempted = 0
    observed = 0
    failed = 0
    for proposal in store.list(status="applying"):
        if attempted >= max(1, min(limit, 100)):
            break
        if proposal.get("action_kind") != "operation.execute":
            continue
        parameters, operation = _proposal_operation(proposal)
        executor = parameters.get("executor")
        if (
            operation.get("lifecycle_state") != "claimed"
            or not isinstance(executor, Mapping)
            or executor.get("permission") != "finance.operation.simulate"
            or parameters.get("operation_kind") != "finance.order.simulate"
            or operation.get("destination_account_ref") != "account:simulation"
        ):
            continue
        attempted += 1
        dispatch_lock = store.root / f"{proposal['proposal_id']}.dispatch.lock"
        with exclusive_file_lock(
            dispatch_lock,
            agent_id="loopx-lark-operation",
            operation="recover_claimed_simulation",
        ):
            current = store.load(str(proposal["proposal_id"]))
            if current is None:
                failed += 1
                continue
            _current_parameters, current_operation = _proposal_operation(current)
            if current_operation.get("lifecycle_state") != "claimed":
                continue
            try:
                outcome = _execute_claimed_operation(
                    current,
                    runtime_root=runtime_root,
                )
                store.observe_operation_outcome(
                    str(proposal["proposal_id"]), outcome=outcome
                )
            except (ActionConflictError, OSError, RuntimeError, ValueError):
                failed += 1
                continue
            observed += 1
    return {"attempted": attempted, "observed": observed, "failed": failed}


def handle_goal_channel_operation_callback(
    event: Mapping[str, Any],
    *,
    runtime_root: Path,
    action_store_root: Path,
    profile_app_id: str,
    cli_bin: str,
    profile: str,
    runner: CommandRunner = default_subprocess_runner,
    executor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    action = _callback_action(event)
    callback_token = str(event.get("token") or "").strip()
    if (
        not callback_token
        or len(callback_token) > 2048
        or any(ord(character) < 32 for character in callback_token)
    ):
        raise ValueError("operation callback update token is invalid")
    for field, pattern in (
        ("event_id", _EVENT_ID),
        ("message_id", _MESSAGE_ID),
        ("chat_id", _CHAT_ID),
        ("operator_id", _OPEN_ID),
    ):
        if not pattern.fullmatch(str(event.get(field) or "")):
            raise ValueError(f"operation callback {field} is invalid")
    if str(event.get("host") or "") != "im_message":
        raise ValueError("operation callback host is unsupported")
    card_content = event.get("card_content")
    try:
        card = json.loads(card_content) if isinstance(card_content, str) else None
    except json.JSONDecodeError as exc:
        raise ValueError("operation callback card_content is invalid") from exc
    if not isinstance(card, Mapping):
        raise ValueError("operation callback requires exact card_content")
    store = ChatActionStore(action_store_root)
    proposal = store.load(action["operation_id"])
    if proposal is None:
        raise ValueError("operation callback proposal was not found")
    parameters, operation = _proposal_operation(proposal)
    delivery = operation.get("delivery")
    if not isinstance(delivery, Mapping):
        raise ActionConflictError("operation card delivery was not recorded")
    if action["confirmation_digest"] != operation.get("confirmation_digest"):
        raise ActionConflictError("operation callback digest drifted")
    if _digest(card) != delivery.get("card_digest"):
        raise ActionConflictError("operation callback card content drifted")
    if profile_app_id != delivery.get("app_id"):
        raise ActionConflictError("operation callback app identity drifted")
    operator_id = str(event["operator_id"])
    operator_principal = f"lark:{operator_id}"
    chat_id = str(event["chat_id"])
    if operator_principal not in set(parameters.get("authorized_principals") or []):
        raise ActionConflictError("principal is not authorized for this operation")
    if not _operator_membership_verified(
        runner=runner,
        cli_bin=cli_bin,
        profile=profile,
        chat_id=chat_id,
        operator_id=operator_id,
    ):
        raise ActionConflictError("operation callback tenant membership is unverified")
    decided = store.decide_operation(
        action["operation_id"],
        decision=action["decision"],
        confirmation={
            "provider": "lark",
            "event_id": str(event["event_id"]),
            "principal": operator_principal,
            "message_id": str(event["message_id"]),
            "chat_id": chat_id,
            "app_id": profile_app_id,
            "surface_kind": "group_message_card",
            "interaction_kind": "button_callback",
            "confirmation_digest": action["confirmation_digest"],
            "card_digest": str(delivery["card_digest"]),
            "confirmed_at": _callback_timestamp(event.get("timestamp")),
        },
    )
    dispatch_lock = store.root / f"{action['operation_id']}.dispatch.lock"
    with exclusive_file_lock(
        dispatch_lock,
        agent_id="loopx-lark-operation",
        operation="dispatch_claimed_operation",
    ):
        current = store.load(action["operation_id"])
        if current is None:
            raise ValueError("claimed operation disappeared before dispatch")
        _parameters, current_operation = _proposal_operation(current)
        if current_operation.get("lifecycle_state") == "claimed":
            outcome = dict(
                executor(current)
                if executor is not None
                else _execute_claimed_operation(current, runtime_root=runtime_root)
            )
            current = store.observe_operation_outcome(
                action["operation_id"], outcome=outcome
            )
        decided = current
    result_lock = store.root / f"{action['operation_id']}.result-delivery.lock"
    with exclusive_file_lock(
        result_lock,
        agent_id="loopx-lark-operation",
        operation="deliver_operation_callback_result",
    ):
        current = store.load(action["operation_id"])
        if current is None:
            raise ValueError("operation disappeared before result delivery")
        decided = current
        result_card = build_goal_channel_operation_result_card(decided)
        if isinstance(decided["operation"].get("result_delivery"), Mapping):
            update = {"external_write_performed": False, "readback_verified": True}
        else:
            update = _update_callback_card(
                runner=runner,
                cli_bin=cli_bin,
                profile=profile,
                token=callback_token,
                card=result_card,
                message_id=str(delivery["message_id"]),
                chat_id=str(delivery["chat_id"]),
                app_id=str(delivery["app_id"]),
            )
            if update["readback_verified"] is True:
                decided = store.record_operation_result_delivery(
                    action["operation_id"],
                    delivery={
                        "provider": "lark",
                        "message_id": str(delivery["message_id"]),
                        "chat_id": str(delivery["chat_id"]),
                        "app_id": str(delivery["app_id"]),
                        "card_digest": _digest(result_card),
                        "transport": "callback_update",
                        "delivered_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
    update_verified = update["readback_verified"]
    return {
        "ok": update_verified,
        "schema_version": OPERATION_CALLBACK_RECEIPT_SCHEMA_VERSION,
        "operation_id": action["operation_id"],
        "decision": action["decision"],
        "lifecycle_state": decided["operation"]["lifecycle_state"],
        "outcome": decided["operation"]["outcome"]["outcome"],
        "claim_id": (
            decided["operation"]["claim"]["claim_id"]
            if isinstance(decided["operation"].get("claim"), Mapping)
            else None
        ),
        "callback_ack_is_execution_receipt": False,
        "card_update_verified": update_verified,
        "status": "outcome_observed" if update_verified else "result_delivery_pending",
        "domain_external_write_performed": bool(
            decided["operation"]["outcome"].get("external_write_performed") is True
        ),
        "external_write_performed": update["external_write_performed"],
    }


__all__ = [
    "build_goal_channel_operation_card",
    "build_goal_channel_operation_result_card",
    "deliver_goal_channel_operation_card",
    "handle_goal_channel_operation_callback",
    "recover_goal_channel_operation_results",
    "recover_goal_channel_simulation_claims",
]
