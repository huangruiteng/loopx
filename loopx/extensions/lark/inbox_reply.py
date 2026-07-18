from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .event_inbox import (
    MESSAGE_ID_PATTERN,
    _event_from_file,
    load_lark_event_inbox_config,
)


CommandRunner = Callable[[Sequence[str]], Mapping[str, Any]]

AT_MENTION_PATTERN = re.compile(
    r'<at\s+(?P<kind>user_id|open_id|union_id)="(?P<identity>[^"<>]+)">'
    r"(?P<name>.*?)</at>",
    re.IGNORECASE,
)
MENTION_ID_KEYS = ("open_id", "user_id", "union_id")


def _default_runner(args: Sequence[str]) -> Mapping[str, Any]:
    result = subprocess.run(
        list(args),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
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
            (found for child in value.values() if (found := _message(child, message_id))),
            None,
        )
    if isinstance(value, list):
        return next(
            (found for child in value if (found := _message(child, message_id))),
            None,
        )
    return None


def _content_text(value: Any) -> str:
    if isinstance(value, Mapping):
        text = value.get("text")
        if isinstance(text, str):
            return text
        content = value.get("content")
        if content is not None:
            return _content_text(content)
        return ""
    if not isinstance(value, str):
        return ""
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return value
    return _content_text(decoded) if isinstance(decoded, Mapping) else value


def _message_text(message: Mapping[str, Any]) -> str:
    body = message.get("body")
    if isinstance(body, Mapping):
        text = _content_text(body)
        if text:
            return text
    return _content_text(message.get("content"))


def _mention_identities(mention: Mapping[str, Any]) -> set[str]:
    identities = {
        str(mention.get(key) or "").strip()
        for key in MENTION_ID_KEYS
        if str(mention.get(key) or "").strip()
    }
    mention_id = mention.get("id")
    if isinstance(mention_id, Mapping):
        identities.update(
            str(mention_id.get(key) or "").strip()
            for key in MENTION_ID_KEYS
            if str(mention_id.get(key) or "").strip()
        )
    elif isinstance(mention_id, str) and mention_id.strip():
        identities.add(mention_id.strip())
    return identities


def _canonical_expected_text(text: str) -> tuple[str, dict[str, str]]:
    identity_tokens: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        identity = match.group("identity").strip()
        token = identity_tokens.setdefault(
            identity, f"\x1fmention:{len(identity_tokens)}\x1f"
        )
        return token

    return " ".join(AT_MENTION_PATTERN.sub(replace, text).split()), identity_tokens


def _readback_matches_reply(
    *, reply_text: str, message: Mapping[str, Any]
) -> bool:
    expected_text, identity_tokens = _canonical_expected_text(reply_text)
    actual_text = _message_text(message)
    if not actual_text:
        return False
    if not identity_tokens:
        return " ".join(actual_text.split()) == expected_text

    mentions = message.get("mentions")
    if not isinstance(mentions, list):
        return False
    matched_identities: set[str] = set()
    for mention in mentions:
        if not isinstance(mention, Mapping):
            return False
        key = str(mention.get("key") or "")
        matches = _mention_identities(mention).intersection(identity_tokens)
        if not key or len(matches) != 1:
            return False
        identity = next(iter(matches))
        actual_text = actual_text.replace(key, identity_tokens[identity])
        matched_identities.add(identity)
    return (
        matched_identities == set(identity_tokens)
        and " ".join(actual_text.split()) == expected_text
    )


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
    blocker: str | None = None,
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
        "sender_identity_verified": identity_verified,
        "sender_chat_membership_verified": membership_verified,
        "private_sender_profile_captured": False,
        "private_chat_id_captured": False,
        "private_message_id_captured": False,
        "private_reply_content_captured": False,
        "raw_provider_payload_captured": False,
    }
    if blocker:
        packet["blocker"] = blocker
    return packet


def reply_lark_event_inbox(
    *,
    project: str | Path,
    config_path: str | Path,
    message_id: str,
    text: str,
    execute: bool = False,
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    """Reply in the source thread with the explicit inbox-configured bot."""

    config = load_lark_event_inbox_config(project=project, config_path=config_path)
    if not config["enabled"]:
        raise ValueError("lark event inbox is not enabled")
    source_message_id = str(message_id or "").strip()
    if not MESSAGE_ID_PATTERN.fullmatch(source_message_id):
        raise ValueError("lark inbox reply requires a valid message id")
    inbox = config["inbox_path"]
    source_captured = any(
        event.get("message_id") == source_message_id
        for path in (inbox.glob("*.json") if inbox.is_dir() else [])
        if path.name != "processed.json"
        if (event := _event_from_file(path)) is not None
    )
    if not source_captured:
        raise ValueError(
            "lark inbox reply source message is not captured by this inbox"
        )
    reply_text = " ".join(str(text or "").split())[:1200]
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
    digest = hashlib.sha256(
        json.dumps(
            {"message_id": source_message_id, "text": reply_text},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    receipt = f"sha256:{digest}"
    if not execute:
        return _result(
            status="preview_ready",
            ok=True,
            execute=False,
            receipt=receipt,
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
            execute=True,
            receipt=receipt,
            blocker="lark_inbox_reply_sender_identity_mismatch",
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
            execute=True,
            receipt=receipt,
            identity_verified=True,
            blocker="lark_inbox_reply_sender_not_in_configured_chat",
        )

    send = _call(
        runner,
        base
        + [
            "im",
            "+messages-reply",
            "--message-id",
            source_message_id,
            "--text",
            reply_text,
            "--reply-in-thread",
            "--idempotency-key",
            f"loopx-{digest[:32]}",
            "--as",
            "bot",
            "--format",
            "json",
        ],
    )
    if send.get("returncode") != 0:
        return _result(
            status="gate_required",
            ok=False,
            execute=True,
            receipt=receipt,
            identity_verified=True,
            membership_verified=True,
            blocker="lark_inbox_reply_provider_failed",
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
            blocker="lark_inbox_reply_not_verified",
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
        and _readback_matches_reply(
            reply_text=reply_text,
            message=readback_message,
        )
    )
    return _result(
        status="sent_verified" if verified else "sent_unverified",
        ok=verified,
        execute=True,
        receipt=receipt,
        identity_verified=True,
        membership_verified=True,
        write_performed=True,
        readback_performed=True,
        reply_verified=verified,
        blocker=None if verified else "lark_inbox_reply_not_verified",
    )
