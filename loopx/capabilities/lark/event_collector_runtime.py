from __future__ import annotations

import json
import re
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .event_collector import (
    _executable_prefix,
    _jq_projection,
    load_lark_event_collector_config,
)
from .event_inbox import (
    MESSAGE_ID_PATTERN,
    _event_attention_kind,
    ingest_lark_event_inbox,
)


APP_ID_PATTERN = re.compile(r"cli_[A-Za-z0-9_-]+")
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]


def _run_json(runner: CommandRunner, argv: Sequence[str]) -> object:
    result = runner(
        list(argv),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {}


def _find_string_by_key(value: object, keys: set[str]) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in keys and isinstance(child, str) and child.strip():
                return child.strip()
        for child in value.values():
            if found := _find_string_by_key(child, keys):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := _find_string_by_key(child, keys):
                return found
    return None


def _profile_app_id(
    *,
    runner: CommandRunner,
    command_prefix: Sequence[str],
    profile: str,
) -> str | None:
    payload = _run_json(
        runner,
        [*command_prefix, "--profile", profile, "whoami", "--as", "bot"],
    )
    app_id = _find_string_by_key(payload, {"appId", "app_id"})
    return app_id if app_id and APP_ID_PATTERN.fullmatch(app_id) else None


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


def _read_message(
    *,
    runner: CommandRunner,
    command_prefix: Sequence[str],
    profile: str,
    message_id: str,
    attempts: int,
    sleeper: Sleeper,
) -> Mapping[str, Any] | None:
    for attempt in range(max(1, attempts)):
        payload = _run_json(
            runner,
            [
                *command_prefix,
                "--profile",
                profile,
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
        )
        if message := _find_message(payload, message_id):
            return message
        if attempt + 1 < max(1, attempts):
            sleeper(0.5 * (attempt + 1))
    return None


def _sender_identity(message: Mapping[str, Any]) -> tuple[str, str]:
    sender = message.get("sender")
    sender = sender if isinstance(sender, Mapping) else {}
    sender_type = str(
        sender.get("sender_type") or message.get("sender_type") or ""
    ).strip()
    sender_id = str(
        sender.get("id")
        or sender.get("sender_id")
        or message.get("sender_id")
        or ""
    ).strip()
    return sender_type, sender_id


def enrich_lark_event_reply_context(
    event: Mapping[str, Any],
    *,
    runner: CommandRunner,
    command_prefix: Sequence[str],
    profile: str,
    profile_app_id: str,
    configured_chat_id: str,
    attempts: int = 3,
    sleeper: Sleeper = time.sleep,
) -> dict[str, Any]:
    """Verify whether an event structurally replies to this profile's bot."""

    enriched = dict(event)
    enriched["reply_context_verified"] = False
    enriched["reply_to_bot"] = False
    message_id = str(event.get("message_id") or "").strip()
    if not MESSAGE_ID_PATTERN.fullmatch(message_id):
        return enriched
    current = _read_message(
        runner=runner,
        command_prefix=command_prefix,
        profile=profile,
        message_id=message_id,
        attempts=attempts,
        sleeper=sleeper,
    )
    if current is None or str(current.get("chat_id") or "") != configured_chat_id:
        return enriched

    parent_id = str(current.get("parent_id") or "").strip()
    root_id = str(current.get("root_id") or "").strip()
    if MESSAGE_ID_PATTERN.fullmatch(root_id):
        enriched["root_id"] = root_id
    if not MESSAGE_ID_PATTERN.fullmatch(parent_id):
        enriched["reply_context_verified"] = True
        return enriched
    enriched["parent_id"] = parent_id

    parent = _read_message(
        runner=runner,
        command_prefix=command_prefix,
        profile=profile,
        message_id=parent_id,
        attempts=attempts,
        sleeper=sleeper,
    )
    if parent is None or str(parent.get("chat_id") or "") != configured_chat_id:
        return enriched
    current_sender_type, _ = _sender_identity(current)
    parent_sender_type, parent_sender_id = _sender_identity(parent)
    enriched["reply_context_verified"] = True
    enriched["reply_to_bot"] = bool(
        current_sender_type == "user"
        and parent_sender_type == "app"
        and parent_sender_id == profile_app_id
    )
    return enriched


def _consume_argv(
    config: Mapping[str, Any], command_prefix: Sequence[str]
) -> list[str]:
    return [
        *command_prefix,
        "--profile",
        str(config["profile"]),
        "event",
        "consume",
        str(config["event_key"]),
        "--as",
        str(config["identity"]),
        "--timeout",
        str(config["consume_timeout"]),
        "--jq",
        _jq_projection(str(config["chat_id"])),
        "--quiet",
    ]


def lark_event_requires_reply_context_lookup(
    event: Mapping[str, Any], *, bot_display_name: str
) -> bool:
    """Direct mentions are actionable without a provider readback."""

    direct_attention = _event_attention_kind(
        event,
        bot_display_name=bot_display_name,
        capture_scope="configured_chat_all",
    )
    return direct_attention not in {"direct_question", "direct_mention"}


def run_lark_event_collector(
    *,
    project: str | Path,
    config_path: str | Path,
    lark_cli_executable: str,
    node_executable: str | None = None,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    config = load_lark_event_collector_config(
        project=project,
        config_path=config_path,
    )
    command_prefix = (
        [node_executable, lark_cli_executable]
        if node_executable
        else _executable_prefix(lark_cli_executable)
    )
    process = subprocess.Popen(
        _consume_argv(config, command_prefix),
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    previous_handlers: dict[signal.Signals, Any] = {}

    def forward_signal(signum: int, _: object) -> None:
        if process.poll() is None:
            process.send_signal(signum)

    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, forward_signal)
    captured_count = 0
    verified_count = 0
    reply_to_bot_count = 0
    profile_app_id: str | None = None
    profile_identity_checked = False
    try:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, Mapping):
                continue
            needs_reply_lookup = lark_event_requires_reply_context_lookup(
                payload,
                bot_display_name=str(
                    config["inbox"]["reply"].get("bot_display_name") or ""
                ),
            )
            if not needs_reply_lookup:
                enriched = {
                    **payload,
                    "reply_context_verified": False,
                    "reply_to_bot": False,
                }
            else:
                if not profile_identity_checked:
                    profile_app_id = _profile_app_id(
                        runner=runner,
                        command_prefix=command_prefix,
                        profile=str(config["profile"]),
                    )
                    profile_identity_checked = True
                enriched = (
                    enrich_lark_event_reply_context(
                        payload,
                        runner=runner,
                        command_prefix=command_prefix,
                        profile=str(config["profile"]),
                        profile_app_id=profile_app_id,
                        configured_chat_id=str(config["chat_id"]),
                    )
                    if profile_app_id is not None
                    else {
                        **payload,
                        "reply_context_verified": False,
                        "reply_to_bot": False,
                    }
                )
            result = ingest_lark_event_inbox(
                project=config["project"],
                config_path=config["event_inbox_config_ref"],
                events=[{"schema_version": "lark_event_inbox_event_v0", **enriched}],
                execute=True,
            )
            if int(result.get("accepted_count") or 0) == 0:
                continue
            captured_count += 1
            verified_count += int(enriched.get("reply_context_verified") is True)
            reply_to_bot_count += int(enriched.get("reply_to_bot") is True)
        returncode = process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return {
        "ok": returncode == 0,
        "schema_version": "lark_event_collector_run_v0",
        "status": "completed" if returncode == 0 else "consumer_failed",
        "captured_count": captured_count,
        "reply_context_verified_count": verified_count,
        "reply_to_bot_count": reply_to_bot_count,
        "profile_identity_checked": profile_identity_checked,
        "profile_identity_verified": profile_app_id is not None,
        "private_content_returned": False,
    }
