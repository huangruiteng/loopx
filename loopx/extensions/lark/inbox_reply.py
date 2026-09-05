from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .event_inbox import (
    MESSAGE_ID_PATTERN,
    _event_from_file,
    load_lark_event_inbox_config,
)
from .inbox_reactions import complete_lark_event_inbox_reactions
from .outbound import (
    expected_lark_mention_identities,
    lark_member_identities,
    lark_provider_preview_matches_outbound,
    lark_readback_matches_outbound,
    normalize_lark_outbound_text,
)

CommandRunner = Callable[[Sequence[str]], Mapping[str, Any]]


def _default_runner(args: Sequence[str]) -> Mapping[str, Any]:
    result = subprocess.run(
        list(args),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _call(runner: CommandRunner, args: Sequence[str]) -> Mapping[str, Any]:
    try:
        return runner(args)
    except (OSError, subprocess.SubprocessError):
        return {"returncode": 1}


def _json_object(value: Any) -> Mapping[str, Any]:
    try:
        payload = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _message_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        candidate = value.get("message_id")
        if isinstance(candidate, str) and MESSAGE_ID_PATTERN.fullmatch(candidate):
            return candidate
        return next(
            (found for child in value.values() if (found := _message_id(child))),
            None,
        )
    if isinstance(value, list):
        return next(
            (found for child in value if (found := _message_id(child))),
            None,
        )
    return None


def _message(value: Any, message_id: str) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        if str(value.get("message_id") or "") == message_id:
            return value
        return next(
            (
                found
                for child in value.values()
                if (found := _message(child, message_id))
            ),
            None,
        )
    if isinstance(value, list):
        return next(
            (found for child in value if (found := _message(child, message_id))),
            None,
        )
    return None


def _result(
    *,
    status: str,
    ok: bool,
    execute: bool,
    receipt: str | None,
    identity_verified: bool = False,
    membership_verified: bool = False,
    write_performed: bool = False,
    readback_performed: bool = False,
    reply_verified: bool = False,
    reaction_cleanup_verified: bool = False,
    placement: str | None = None,
    blocker: str | None = None,
    format_preflight_passed: bool = False,
    provider_preview_performed: bool = False,
    provider_preview_verified: bool = False,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "ok": ok,
        "schema_version": "lark_event_inbox_reply_v0",
        "status": status,
        "execute": execute,
        "idempotency_key": receipt,
        "external_write_authority_asserted": execute,
        "external_write_performed": write_performed,
        "verification_performed": readback_performed,
        "reply_verified": reply_verified,
        "reaction_cleanup_verified": reaction_cleanup_verified,
        "sender_identity_verified": identity_verified,
        "sender_chat_membership_verified": membership_verified,
        "format_preflight_passed": format_preflight_passed,
        "provider_preview_performed": provider_preview_performed,
        "provider_preview_verified": provider_preview_verified,
        "private_sender_profile_captured": False,
        "private_chat_id_captured": False,
        "private_message_id_captured": False,
        "private_reply_content_captured": False,
        "raw_provider_payload_captured": False,
    }
    if blocker:
        packet["blocker"] = blocker
    if placement:
        packet["placement"] = placement
    return packet


def _deliver_lark_inbox_outbound(
    *,
    project: str | Path,
    config_path: str | Path,
    message_id: str | None,
    text: str,
    execute: bool = False,
    provider_preflight: bool = False,
    runner: CommandRunner = _default_runner,
    before_send: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deliver through one inbox-configured bot with exact provider readback."""

    config = load_lark_event_inbox_config(project=project, config_path=config_path)
    if not config["enabled"]:
        raise ValueError("lark event inbox is not enabled")
    source_message_id = str(message_id or "").strip()
    if source_message_id and not MESSAGE_ID_PATTERN.fullmatch(source_message_id):
        raise ValueError("lark inbox reply requires a valid message id")
    inbox = config["inbox_path"]
    source_event = (
        next(
            (
                event
                for path in (inbox.glob("*.json") if inbox.is_dir() else [])
                if path.name != "processed.json"
                if (event := _event_from_file(path)) is not None
                if event.get("message_id") == source_message_id
            ),
            None,
        )
        if source_message_id
        else None
    )
    if source_message_id and source_event is None:
        raise ValueError(
            "lark inbox reply source message is not captured by this inbox"
        )
    reply_text = normalize_lark_outbound_text(text)
    if not reply_text:
        raise ValueError("lark inbox reply requires non-empty text")

    reply_config = config["reply"]
    if reply_config.get("enabled") is not True:
        return _result(
            status="gate_required",
            ok=False,
            execute=execute,
            receipt=None,
            blocker="lark_inbox_reply_sender_unconfigured",
        )

    profile = str(reply_config["sender_profile"])
    chat_id = str(reply_config["chat_id"])
    source_is_threaded = bool(
        source_event and (source_event.get("parent_id") or source_event.get("root_id"))
    )
    placement = (
        "chat_root"
        if source_event is None
        or (
            reply_config["placement_policy"] == "source_context"
            and not source_is_threaded
        )
        else "source_thread"
    )
    digest = hashlib.sha256(
        json.dumps(
            {
                "message_id": source_message_id,
                "placement": placement,
                "text": reply_text,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    receipt = f"sha256:{digest}"
    if not execute and not provider_preflight:
        return _result(
            status="preview_ready",
            ok=True,
            execute=False,
            receipt=receipt,
            placement=placement,
            format_preflight_passed=True,
        )

    base = ["lark-cli", "--profile", profile]
    auth = _call(runner, base + ["auth", "status", "--verify", "--json"])
    identities = _json_object(auth.get("stdout")).get("identities")
    identity = identities.get("bot", {}) if isinstance(identities, Mapping) else {}
    identity_verified = bool(
        auth.get("returncode") == 0
        and isinstance(identity, Mapping)
        and identity.get("available") is True
        and identity.get("verified") is True
        and str(identity.get("appName") or "") == reply_config["bot_display_name"]
    )
    if not identity_verified:
        return _result(
            status="gate_required",
            ok=False,
            execute=execute,
            receipt=receipt,
            blocker="lark_inbox_reply_sender_identity_mismatch",
            format_preflight_passed=True,
        )

    membership = _call(
        runner,
        base
        + [
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
    )
    if membership.get("returncode") != 0:
        return _result(
            status="gate_required",
            ok=False,
            execute=execute,
            receipt=receipt,
            identity_verified=True,
            blocker="lark_inbox_reply_sender_not_in_configured_chat",
            format_preflight_passed=True,
        )

    expected_mentions = expected_lark_mention_identities(reply_text)
    if expected_mentions:
        member_identity_sets: dict[str, set[str]] = {}
        membership_failed = False
        for identity_kind in sorted(set(expected_mentions.values())):
            members = _call(
                runner,
                base
                + [
                    "im",
                    "chat.members",
                    "get",
                    "--chat-id",
                    chat_id,
                    "--member-id-type",
                    identity_kind,
                    "--page-all",
                    "--as",
                    "bot",
                    "--format",
                    "json",
                ],
            )
            if members.get("returncode") != 0:
                membership_failed = True
                break
            member_identity_sets[identity_kind] = lark_member_identities(
                _json_object(members.get("stdout"))
            )
        if membership_failed or any(
            identity not in member_identity_sets.get(identity_kind, set())
            for identity, identity_kind in expected_mentions.items()
        ):
            return _result(
                status="gate_required",
                ok=False,
                execute=execute,
                receipt=receipt,
                identity_verified=True,
                membership_verified=True,
                placement=placement,
                blocker="lark_inbox_reply_mention_identity_unresolved",
                format_preflight_passed=True,
            )

    destination = (
        [
            "im",
            "+messages-send",
            "--chat-id",
            chat_id,
            "--text",
            reply_text,
        ]
        if placement == "chat_root"
        else [
            "im",
            "+messages-reply",
            "--message-id",
            source_message_id,
            "--text",
            reply_text,
            "--reply-in-thread",
        ]
    )
    provider_args = (
        base
        + destination
        + [
            "--idempotency-key",
            f"loopx-{digest[:32]}",
            "--as",
            "bot",
            "--format",
            "json",
        ]
    )
    preview = _call(runner, provider_args + ["--dry-run"])
    provider_preview_verified = bool(
        preview.get("returncode") == 0
        and lark_provider_preview_matches_outbound(
            outbound_text=reply_text,
            payload=_json_object(preview.get("stdout")),
        )
    )
    if not provider_preview_verified:
        return _result(
            status="gate_required",
            ok=False,
            execute=execute,
            receipt=receipt,
            identity_verified=True,
            membership_verified=True,
            placement=placement,
            blocker="lark_inbox_reply_provider_preview_mismatch",
            format_preflight_passed=True,
            provider_preview_performed=True,
        )
    guidance = None
    if before_send is not None:
        # Bind review to destination/profile as well as content and placement.
        # None of these private values are supplied to the memory provider.
        intent_digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps([profile, chat_id, receipt]).encode("utf-8")
            ).hexdigest()
        )
        guidance = before_send(intent_digest)
        if guidance.get("continue_delivery") is not True or not execute:
            return _result(
                status="agent_review_required"
                if guidance.get("agent_review_required")
                else "preview_ready",
                ok=True,
                execute=execute,
                receipt=receipt,
                identity_verified=True,
                membership_verified=True,
                placement=placement,
                format_preflight_passed=True,
                provider_preview_performed=True,
                provider_preview_verified=True,
            ) | {"outbound_guidance": dict(guidance)}
    if not execute:
        return _result(
            status="preview_ready",
            ok=True,
            execute=False,
            receipt=receipt,
            identity_verified=True,
            membership_verified=True,
            placement=placement,
            format_preflight_passed=True,
            provider_preview_performed=True,
            provider_preview_verified=True,
        )

    send = _call(
        runner,
        provider_args,
    )
    if send.get("returncode") != 0:
        return _result(
            status="gate_required",
            ok=False,
            execute=True,
            receipt=receipt,
            identity_verified=True,
            membership_verified=True,
            placement=placement,
            blocker="lark_inbox_reply_provider_failed",
            format_preflight_passed=True,
            provider_preview_performed=True,
            provider_preview_verified=True,
        )

    reply_message_id = _message_id(_json_object(send.get("stdout")))
    if not reply_message_id:
        return _result(
            status="sent_unverified",
            ok=False,
            execute=True,
            receipt=receipt,
            identity_verified=True,
            membership_verified=True,
            write_performed=True,
            placement=placement,
            blocker="lark_inbox_reply_not_verified",
            format_preflight_passed=True,
            provider_preview_performed=True,
            provider_preview_verified=True,
        )
    readback = _call(
        runner,
        base
        + [
            "im",
            "+messages-mget",
            "--message-ids",
            reply_message_id,
            "--as",
            "bot",
            "--no-reactions",
            "--format",
            "json",
        ],
    )
    readback_payload = _json_object(readback.get("stdout"))
    readback_message = _message(readback_payload, reply_message_id)
    verified = bool(
        readback.get("returncode") == 0
        and readback_message is not None
        and lark_readback_matches_outbound(
            outbound_text=reply_text,
            message=readback_message,
        )
    )
    reaction_cleanup = (
        complete_lark_event_inbox_reactions(
            project=project,
            config_path=config_path,
            message_id=source_message_id,
            execute=True,
            runner=runner,
        )
        if verified and source_message_id
        else {"ok": True}
        if verified
        else None
    )
    reaction_cleanup_verified = bool(
        reaction_cleanup is not None and reaction_cleanup.get("ok") is True
    )
    completed = bool(verified and reaction_cleanup_verified)
    result = _result(
        status=(
            "sent_verified"
            if completed
            else "sent_verified_cleanup_pending"
            if verified
            else "sent_unverified"
        ),
        ok=completed,
        execute=True,
        receipt=receipt,
        identity_verified=True,
        membership_verified=True,
        write_performed=True,
        readback_performed=True,
        reply_verified=verified,
        reaction_cleanup_verified=reaction_cleanup_verified,
        placement=placement,
        blocker=(
            None
            if completed
            else "lark_inbox_reply_reaction_cleanup_pending"
            if verified
            else "lark_inbox_reply_not_verified"
        ),
        format_preflight_passed=True,
        provider_preview_performed=True,
        provider_preview_verified=True,
    )
    if guidance is not None:
        result["outbound_guidance"] = dict(guidance)
    return result


def reply_lark_event_inbox(
    *,
    project: str | Path,
    config_path: str | Path,
    message_id: str,
    text: str,
    execute: bool = False,
    provider_preflight: bool = False,
    runner: CommandRunner = _default_runner,
    before_send: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reply with the explicit inbox-configured bot and placement policy."""

    return _deliver_lark_inbox_outbound(
        project=project,
        config_path=config_path,
        message_id=message_id,
        text=text,
        execute=execute,
        provider_preflight=provider_preflight,
        runner=runner,
        before_send=before_send,
    )


def send_lark_inbox_message(
    *,
    project: str | Path,
    config_path: str | Path,
    text: str,
    execute: bool = False,
    provider_preflight: bool = False,
    runner: CommandRunner = _default_runner,
    before_send: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send one verified chat-root message through the configured inbox bot."""

    result = _deliver_lark_inbox_outbound(
        project=project,
        config_path=config_path,
        message_id=None,
        text=text,
        execute=execute,
        provider_preflight=provider_preflight,
        runner=runner,
        before_send=before_send,
    )
    result["schema_version"] = "lark_outbound_message_v0"
    blocker = result.get("blocker")
    if isinstance(blocker, str):
        result["blocker"] = blocker.replace(
            "lark_inbox_reply_", "lark_outbound_message_"
        )
    return result
