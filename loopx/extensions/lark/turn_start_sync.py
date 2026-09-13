"""Bounded incremental Lark history sync for the LoopX turn-start hook."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from bisect import bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ...file_lock import (
    LockAcquireTimeoutError,
    LockAcquisitionPolicy,
    exclusive_file_lock,
)
from .event_collector import _executable_prefix, load_lark_event_collector_config
from .event_collector_runtime import (
    _create_lark_event_received_reaction,
    _delete_lark_event_reaction,
    _profile_app_id,
    _sender_identity,
)
from .event_inbox import (
    MESSAGE_ID_PATTERN,
    ROUTE_KEY_PATTERN,
    load_lark_event_inbox_config,
)
from .goal_channel_contracts import LarkTopicEventDecisionReason
from .goal_topic_routing import decide_lark_topic_route_event
from .group_history import (
    _canonical_events,
    _page_digest,
    _provider_argv,
    _provider_failure,
    _provider_page,
    _verify_inbox_events,
)
from .group_history_cursor import group_history_source_fingerprint
from .inbox_reactions import (
    ensure_lark_event_inbox_received_reaction,
    lark_inbox_pending_turn_start_read_message_ids,
    record_lark_inbox_turn_start_read,
)
from .private_json import write_private_json_atomic
from .routed_inbox import ingest_routed_lark_event_inbox, lark_inbox_config_kind

CURSOR_SCHEMA_VERSION = "lark_turn_start_sync_cursor_v0"
DISPATCH_CURSOR_SCHEMA_VERSION = "lark_turn_start_dispatch_cursor_v0"
SYNC_SCHEMA_VERSION = "lark_turn_start_inbox_sync_v0"
Runner = Callable[..., subprocess.CompletedProcess[str]]
SOURCE_FINGERPRINT_PATTERN = re.compile(r"^sha256:([0-9a-f]{24})$")
TURN_START_REACTION_ATTEMPT_LIMIT = 3
DIRECT_INBOX_TURN_START_POLICY = {
    "enabled": True,
    "initial_lookback_seconds": 15 * 60,
    "overlap_seconds": 5,
    "page_size": 50,
}


@dataclass
class _ReactionAttemptBudget:
    remaining: int
    last_consuming_route_key: str | None = None

    def take(self, requested: int, *, route_key: str) -> int:
        granted = min(self.remaining, max(0, requested))
        self.remaining -= granted
        if granted:
            self.last_consuming_route_key = route_key
        return granted


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _cursor_path(project: Path, *, route_key: str, source_fingerprint: str) -> Path:
    if not ROUTE_KEY_PATTERN.fullmatch(route_key):
        raise ValueError("Lark turn-start sync route key is invalid")
    match = SOURCE_FINGERPRINT_PATTERN.fullmatch(source_fingerprint)
    if match is None:
        raise ValueError("Lark turn-start sync source fingerprint is invalid")
    trusted_root = (project / ".loopx" / "inbox" / ".turn-start").resolve()
    cursor_path = (trusted_root / route_key / f"{match.group(1)}.json").resolve()
    if not cursor_path.is_relative_to(trusted_root):
        raise ValueError("Lark turn-start sync cursor path escapes its private root")
    return cursor_path


def _dispatch_source_fingerprint(config: Mapping[str, Any]) -> str:
    identity = json.dumps(
        {
            "config_path": str(Path(config["config_path"]).resolve()),
            "profile": str(config["profile"]),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"sha256:{digest}"


def _turn_start_config(
    *, project: str | Path, config_path: str | Path
) -> dict[str, Any]:
    """Normalize a collector or one-click direct Inbox into one sync topology."""

    kind = lark_inbox_config_kind(project=project, config_path=config_path)
    if kind == "collector":
        collector_config: Mapping[str, Any] = load_lark_event_collector_config(
            project=project,
            config_path=config_path,
        )
        return dict(collector_config)

    root = Path(project).expanduser().resolve()
    path = Path(config_path).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    inbox = load_lark_event_inbox_config(project=root, config_path=path)
    if not inbox["enabled"]:
        return {
            "schema_version": "lark_turn_start_direct_inbox_v0",
            "enabled": False,
            "project": root,
            "config_path": path,
            "profile": "",
            "turn_start_sync": {**DIRECT_INBOX_TURN_START_POLICY, "enabled": False},
            "routes": [],
        }
    reply = inbox["reply"]
    if reply["enabled"] is not True:
        raise ValueError(
            "enabled direct Lark turn-start sync requires an explicit reply profile"
        )
    topic_root_message_id = str(inbox.get("topic_root_message_id") or "")
    if not MESSAGE_ID_PATTERN.fullmatch(topic_root_message_id):
        raise ValueError(
            "enabled direct Lark turn-start sync requires a Goal Topic root"
        )
    config_ref = path.relative_to(root).as_posix()
    return {
        "schema_version": "lark_turn_start_direct_inbox_v0",
        "enabled": True,
        "project": root,
        "config_path": path,
        "profile": str(reply["sender_profile"]),
        "turn_start_sync": dict(DIRECT_INBOX_TURN_START_POLICY),
        "routes": [
            {
                "route_key": "default",
                "chat_id": str(reply["chat_id"]),
                "topic_root_message_id": topic_root_message_id,
                "event_inbox_config_ref": config_ref,
                "inbox": inbox,
            }
        ],
    }


def _route_source_fingerprint(
    *, config: Mapping[str, Any], route: Mapping[str, Any]
) -> str:
    project_root = Path(config["project"])
    inbox_path_ref = Path(route["inbox"]["inbox_path"]).relative_to(
        project_root
    ).as_posix()
    return group_history_source_fingerprint(
        route_key=str(route["route_key"]),
        profile=str(config["profile"]),
        chat_id=str(route["chat_id"]),
        event_inbox_config_ref=str(route["event_inbox_config_ref"]),
        inbox_path_ref=inbox_path_ref,
        capture_scope=str(route["inbox"]["capture_scope"]),
        route_binding_ref=str(route.get("topic_root_message_id") or ""),
    )


def _events_for_route(
    events: list[dict[str, Any]], *, route: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Apply the Inbox's structural addressing boundary before persistence."""

    inbox = route["inbox"]
    if inbox["capture_scope"] == "configured_chat_all":
        return events
    return [
        event
        for event in events
        if decide_lark_topic_route_event(
            event=event,
            chat_id=str(route["chat_id"]),
            topic_root_message_id=str(route.get("topic_root_message_id") or ""),
            capture_scope=str(inbox["capture_scope"]),
            identity=inbox["reply"],
        )
        is LarkTopicEventDecisionReason.MATCHED
    ]


def _dispatch_cursor_path(project: Path, *, source_fingerprint: str) -> Path:
    match = SOURCE_FINGERPRINT_PATTERN.fullmatch(source_fingerprint)
    if match is None:
        raise ValueError("Lark turn-start dispatch fingerprint is invalid")
    trusted_root = (
        project / ".loopx" / "inbox" / ".turn-start" / ".dispatch"
    ).resolve()
    cursor_path = (trusted_root / f"{match.group(1)}.json").resolve()
    if not cursor_path.is_relative_to(trusted_root):
        raise ValueError("Lark turn-start dispatch cursor escapes its private root")
    return cursor_path


def _load_dispatch_cursor(
    path: Path, *, source_fingerprint: str
) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Lark turn-start dispatch cursor is unreadable") from exc
    last_route_key = (
        str(payload.get("last_route_key") or "")
        if isinstance(payload, Mapping)
        else ""
    )
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != DISPATCH_CURSOR_SCHEMA_VERSION
        or payload.get("source_fingerprint") != source_fingerprint
        or not ROUTE_KEY_PATTERN.fullmatch(last_route_key)
    ):
        raise ValueError("Lark turn-start dispatch cursor schema is invalid")
    return {
        "schema_version": DISPATCH_CURSOR_SCHEMA_VERSION,
        "source_fingerprint": source_fingerprint,
        "last_route_key": last_route_key,
    }


def _rotate_routes_after(
    routes: list[Mapping[str, Any]], *, last_route_key: str | None
) -> list[Mapping[str, Any]]:
    if not last_route_key:
        return routes
    route_keys = [str(route["route_key"]) for route in routes]
    if last_route_key not in route_keys:
        return routes
    start = route_keys.index(last_route_key) + 1
    return routes[start:] + routes[:start]


def _load_cursor(
    path: Path, *, route_key: str, source_fingerprint: str
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Lark turn-start sync cursor is unreadable") from exc
    if not isinstance(payload, Mapping) or payload.get("schema_version") != (
        CURSOR_SCHEMA_VERSION
    ):
        raise ValueError("Lark turn-start sync cursor schema is invalid")
    if payload.get("route_key") != route_key:
        raise ValueError("Lark turn-start sync cursor route binding changed")
    if payload.get("source_fingerprint") != source_fingerprint:
        raise ValueError("Lark turn-start sync cursor source binding changed")
    for field in ("window_start", "window_end"):
        value = payload.get(field)
        if not isinstance(value, str):
            raise TypeError("Lark turn-start sync cursor window is invalid")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Lark turn-start sync cursor window is invalid") from exc
        if parsed.tzinfo is None:
            raise ValueError("Lark turn-start sync cursor window is invalid")
    next_page_token = payload.get("next_page_token")
    if next_page_token is not None and (
        not isinstance(next_page_token, str) or not next_page_token.strip()
    ):
        raise ValueError("Lark turn-start sync cursor page token is invalid")
    reaction_cursor_message_id = payload.get("reaction_cursor_message_id")
    if reaction_cursor_message_id is not None and (
        not isinstance(reaction_cursor_message_id, str)
        or not MESSAGE_ID_PATTERN.fullmatch(reaction_cursor_message_id)
    ):
        raise ValueError("Lark turn-start sync reaction cursor is invalid")
    page_count = payload.get("page_count")
    message_count = payload.get("message_count")
    if (
        isinstance(page_count, bool)
        or not isinstance(page_count, int)
        or page_count < 1
        or isinstance(message_count, bool)
        or not isinstance(message_count, int)
        or message_count < 0
    ):
        raise ValueError("Lark turn-start sync cursor counters are invalid")
    return dict(payload)


def _write_cursor(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    write_private_json_atomic(path, state)


def _window_state(
    existing: Mapping[str, Any] | None,
    *,
    route_key: str,
    source_fingerprint: str,
    now: datetime,
    initial_lookback_seconds: int,
    overlap_seconds: int,
) -> tuple[dict[str, Any], str]:
    if existing and existing.get("next_page_token"):
        return dict(existing), "page_resumed"
    end = now.astimezone(UTC)
    if existing:
        prior_end = datetime.fromisoformat(str(existing["window_end"])).astimezone(UTC)
        if end <= prior_end:
            end = prior_end + timedelta(microseconds=1)
        start = prior_end - timedelta(seconds=overlap_seconds)
        transition = "tail_advanced"
    else:
        start = end - timedelta(seconds=initial_lookback_seconds)
        transition = "initialized"
    state = {
        "schema_version": CURSOR_SCHEMA_VERSION,
        "route_key": route_key,
        "source_fingerprint": source_fingerprint,
        "window_start": _timestamp(start),
        "window_end": _timestamp(end),
        "next_page_token": None,
        "page_count": 0,
        "message_count": 0,
        "last_page_digest": "",
    }
    if existing and existing.get("reaction_cursor_message_id"):
        state["reaction_cursor_message_id"] = str(
            existing["reaction_cursor_message_id"]
        )
    return state, transition


def _bounded_reaction_message_ids(
    message_ids: list[str],
    *,
    route_key: str,
    cursor_message_id: str | None,
    budget: _ReactionAttemptBudget,
) -> tuple[list[str], int]:
    """Select a bounded round-robin slice without exposing private ids."""

    if not message_ids:
        return [], 0
    limit = budget.take(len(message_ids), route_key=route_key)
    if limit == 0:
        return [], len(message_ids)
    start = bisect_right(message_ids, cursor_message_id or "")
    ordered = message_ids[start:] + message_ids[:start]
    selected = ordered[:limit]
    return selected, len(message_ids) - len(selected)


def _read_provider_events(
    *,
    runner: Runner,
    argv: list[str],
    route_key: str,
    chat_id: str,
    command_prefix: list[str],
    profile: str,
) -> tuple[dict[str, Any] | None, tuple[list[dict[str, Any]], bool, str | None, int, int]]:
    """Read and canonicalize one provider page behind a compact failure contract."""

    try:
        provider = runner(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return (
            {
                "ok": False,
                "status": "provider_unavailable",
                "error_code": "provider_unavailable",
                "external_read_performed": False,
                "local_private_state_mutated": False,
            },
            ([], False, None, 0, 0),
        )
    if provider.returncode != 0:
        failed = _provider_failure(provider, route_key=route_key)
        return (
            {
                "ok": False,
                "status": str(failed["status"]),
                "error_code": str(failed["status"]),
                "external_read_performed": bool(failed["external_read_performed"]),
                "local_private_state_mutated": False,
            },
            ([], False, None, 0, 0),
        )
    try:
        payload = json.loads(provider.stdout)
        messages, has_more, next_page_token = _provider_page(payload)
        profile_app_id = (
            _profile_app_id(
                runner=runner,
                command_prefix=command_prefix,
                profile=profile,
            )
            if any(_sender_identity(message)[0] == "app" for message in messages)
            else None
        )
        events, skipped_count, invalid_count, self_message_skipped_count = (
            _canonical_events(
                messages,
                chat_id=chat_id,
                profile_app_id=profile_app_id,
            )
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        invalid_count = 1
        events, has_more, next_page_token = [], False, None
        skipped_count = self_message_skipped_count = 0
    if invalid_count:
        return (
            {
                "ok": False,
                "status": "provider_contract_error",
                "error_code": "provider_contract_error",
                "external_read_performed": True,
                "local_private_state_mutated": False,
            },
            ([], False, None, 0, 0),
        )
    return (
        None,
        (
            events,
            has_more,
            next_page_token,
            skipped_count,
            self_message_skipped_count,
        ),
    )


def _route_receipt(
    *,
    config: Mapping[str, Any],
    route: Mapping[str, Any],
    source_fingerprint: str,
    now: datetime,
    initial_lookback_seconds: int,
    overlap_seconds: int,
    page_size: int,
    lark_cli_executable: str,
    runner: Runner,
    reaction_budget: _ReactionAttemptBudget,
    historical_context_only: bool,
    emit_received_reactions: bool,
) -> dict[str, Any]:
    route_key = str(route["route_key"])
    cursor_path = _cursor_path(
        Path(config["project"]),
        route_key=route_key,
        source_fingerprint=source_fingerprint,
    )
    try:
        lock = exclusive_file_lock(
            cursor_path,
            policy=LockAcquisitionPolicy.SINGLE_FLIGHT,
            operation="lark_turn_start_sync",
        )
        with lock:
            existing = _load_cursor(
                cursor_path,
                route_key=route_key,
                source_fingerprint=source_fingerprint,
            )
            state, _transition = _window_state(
                existing,
                route_key=route_key,
                source_fingerprint=source_fingerprint,
                now=now,
                initial_lookback_seconds=initial_lookback_seconds,
                overlap_seconds=overlap_seconds,
            )
            argv = _provider_argv(
                command_prefix=_executable_prefix(lark_cli_executable),
                profile=str(config["profile"]),
                chat_id=str(route["chat_id"]),
                state=state,
                page_size=page_size,
            )
            command_prefix = _executable_prefix(lark_cli_executable)
            failure, provider_page = _read_provider_events(
                runner=runner,
                argv=argv,
                route_key=route_key,
                chat_id=str(route["chat_id"]),
                command_prefix=command_prefix,
                profile=str(config["profile"]),
            )
            if failure is not None:
                return failure
            (
                events,
                has_more,
                next_page_token,
                skipped_count,
                self_message_skipped_count,
            ) = provider_page
            events = _events_for_route(events, route=route)
            newly_missing = [
                event
                for event in events
                if not (
                    route["inbox"]["inbox_path"] / f"{event['message_id']}.json"
                ).is_file()
            ]
            ingest = ingest_routed_lark_event_inbox(
                project=config["project"],
                config_path=config["config_path"],
                events=[
                    {
                        **event,
                        "route_key": route_key,
                        **(
                            {"historical_context_only": True}
                            if historical_context_only
                            else {}
                        ),
                    }
                    for event in events
                ],
                execute=True,
            )
            try:
                verified_count = _verify_inbox_events(route, newly_missing)
            except ValueError:
                return {
                    "ok": False,
                    "status": "inbox_readback_failed",
                    "error_code": "inbox_readback_failed",
                    "external_read_performed": True,
                    "local_private_state_mutated": bool(ingest["write_performed"]),
                }
            try:
                first_read_count = sum(
                    int(
                        record_lark_inbox_turn_start_read(
                            inbox=route["inbox"]["inbox_path"],
                            message_id=str(event["message_id"]),
                        )
                    )
                    for event in events
                )
                reaction_enabled = emit_received_reactions and bool(
                    route["inbox"]["reply"].get("received_reaction_emoji")
                )
                pending_reaction_message_ids = (
                    lark_inbox_pending_turn_start_read_message_ids(
                        inbox=route["inbox"]["inbox_path"]
                    )
                    if reaction_enabled
                    else []
                )
                reaction_message_ids, reaction_deferred_count = (
                    _bounded_reaction_message_ids(
                        pending_reaction_message_ids,
                        route_key=route_key,
                        cursor_message_id=(
                            str(state.get("reaction_cursor_message_id") or "") or None
                        ),
                        budget=reaction_budget,
                    )
                )
            except (OSError, TypeError, ValueError):
                return {
                    "ok": False,
                    "status": "turn_start_read_receipt_failed",
                    "error_code": "turn_start_read_receipt_failed",
                    "accepted_count": int(ingest["accepted_count"]),
                    "external_read_performed": True,
                    "local_private_state_mutated": bool(ingest["write_performed"]),
                }
            # Retry from the durable Agent-read set, not only the provider's
            # overlap page. A failed ACK therefore remains recoverable after
            # the history cursor advances beyond the message timestamp.
            reaction_results = [
                ensure_lark_event_inbox_received_reaction(
                    project=config["project"],
                    config_path=route["event_inbox_config_ref"],
                    event={"message_id": message_id},
                    create_reaction=lambda message_id, emoji_type: (
                        _create_lark_event_received_reaction(
                            {"message_id": message_id},
                            runner=runner,
                            command_prefix=command_prefix,
                            profile=str(config["profile"]),
                            emoji_type=emoji_type,
                        )
                    ),
                    delete_reaction=lambda message_id, reaction_id: (
                        _delete_lark_event_reaction(
                            runner=runner,
                            command_prefix=command_prefix,
                            profile=str(config["profile"]),
                            message_id=message_id,
                            reaction_id=reaction_id,
                        )
                    ),
                )
                for message_id in reaction_message_ids
            ]
            reaction_failures = [
                result for result in reaction_results if result["ok"] is not True
            ]
            updated = {
                **state,
                "next_page_token": next_page_token,
                "page_count": int(state["page_count"]) + 1,
                "message_count": int(state["message_count"]) + len(events),
                "last_page_digest": _page_digest(events, next_page_token),
            }
            if reaction_message_ids:
                updated["reaction_cursor_message_id"] = reaction_message_ids[-1]
            try:
                _write_cursor(cursor_path, updated)
                readback = _load_cursor(
                    cursor_path,
                    route_key=route_key,
                    source_fingerprint=source_fingerprint,
                )
                if readback != updated:
                    raise ValueError("Lark turn-start sync cursor readback mismatch")
            except (OSError, TypeError, ValueError):
                return {
                    "ok": False,
                    "status": "cursor_readback_failed",
                    "error_code": "cursor_readback_failed",
                    "accepted_count": int(ingest["accepted_count"]),
                    "external_read_performed": True,
                    "local_private_state_mutated": bool(ingest["write_performed"]),
                }
            return {
                "ok": not reaction_failures,
                "status": (
                    "received_reaction_failed"
                    if reaction_failures
                    else "page_pending"
                    if has_more
                    else "synced"
                ),
                "error_code": (
                    "received_reaction_failed" if reaction_failures else None
                ),
                "accepted_count": int(ingest["accepted_count"]),
                "first_read_count": first_read_count,
                "duplicate_count": int(ingest["duplicate_count"]),
                "skipped_count": skipped_count,
                "self_message_skipped_count": self_message_skipped_count,
                "verified_count": verified_count,
                "external_read_performed": True,
                "received_reaction_count": sum(
                    int(result["created_count"]) for result in reaction_results
                ),
                "received_reaction_failure_count": len(reaction_failures),
                "received_reaction_deferred_count": reaction_deferred_count,
                "read_ack_attempt_count": sum(
                    int(result["read_ack_attempted"] is True)
                    for result in reaction_results
                ),
                "external_writes_performed": any(
                    result["external_writes_performed"] is True
                    for result in reaction_results
                ),
                "local_private_state_mutated": True,
            }
    except LockAcquireTimeoutError:
        return {
            "ok": False,
            "status": "sync_already_running",
            "error_code": "sync_already_running",
            "external_read_performed": False,
            "local_private_state_mutated": False,
        }


def _dispatch_failure(
    status: str,
    *,
    external_read_performed: bool = False,
    local_private_state_mutated: bool = False,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error_code": status,
        "external_read_performed": external_read_performed,
        "local_private_state_mutated": local_private_state_mutated,
    }


def _dispatch_route_receipts(
    *,
    config: Mapping[str, Any],
    policy: Mapping[str, Any],
    observed_at: datetime,
    lark_cli_executable: str,
    runner: Runner,
    historical_context_only: bool,
    emit_received_reactions: bool,
) -> list[dict[str, Any]]:
    source_fingerprint = _dispatch_source_fingerprint(config)
    cursor_path = _dispatch_cursor_path(
        Path(config["project"]),
        source_fingerprint=source_fingerprint,
    )
    try:
        lock = exclusive_file_lock(
            cursor_path,
            policy=LockAcquisitionPolicy.SINGLE_FLIGHT,
            operation="lark_turn_start_dispatch",
        )
        with lock:
            try:
                cursor = _load_dispatch_cursor(
                    cursor_path,
                    source_fingerprint=source_fingerprint,
                )
            except (OSError, TypeError, ValueError):
                return [_dispatch_failure("dispatch_cursor_unreadable")]
            routes = _rotate_routes_after(
                list(config["routes"]),
                last_route_key=(cursor or {}).get("last_route_key"),
            )
            reaction_budget = _ReactionAttemptBudget(
                TURN_START_REACTION_ATTEMPT_LIMIT
            )
            receipts = [
                _route_receipt(
                    config=config,
                    route=route,
                    source_fingerprint=_route_source_fingerprint(
                        config=config,
                        route=route,
                    ),
                    now=observed_at,
                    initial_lookback_seconds=int(policy["initial_lookback_seconds"]),
                    overlap_seconds=int(policy["overlap_seconds"]),
                    page_size=int(policy["page_size"]),
                    lark_cli_executable=lark_cli_executable,
                    runner=runner,
                    reaction_budget=reaction_budget,
                    historical_context_only=historical_context_only,
                    emit_received_reactions=emit_received_reactions,
                )
                for route in routes
            ]
            last_route_key = reaction_budget.last_consuming_route_key
            if not last_route_key:
                return receipts
            updated = {
                "schema_version": DISPATCH_CURSOR_SCHEMA_VERSION,
                "source_fingerprint": source_fingerprint,
                "last_route_key": last_route_key,
            }
            try:
                _write_cursor(cursor_path, updated)
                readback = _load_dispatch_cursor(
                    cursor_path,
                    source_fingerprint=source_fingerprint,
                )
                if readback != updated:
                    raise ValueError(
                        "Lark turn-start dispatch cursor readback mismatch"
                    )
            except (OSError, TypeError, ValueError):
                receipts.append(
                    _dispatch_failure(
                        "dispatch_cursor_readback_failed",
                        external_read_performed=any(
                            receipt.get("external_read_performed") is True
                            for receipt in receipts
                        ),
                        local_private_state_mutated=any(
                            receipt.get("local_private_state_mutated") is True
                            for receipt in receipts
                        ),
                    )
                )
            return receipts
    except LockAcquireTimeoutError:
        return [_dispatch_failure("sync_already_running")]


def sync_lark_turn_start_inbox(
    *,
    project: str | Path,
    config_path: str | Path,
    lark_cli_executable: str = "lark-cli",
    runner: Runner = subprocess.run,
    now: datetime | None = None,
    historical_context_only: bool = False,
    emit_received_reactions: bool = True,
) -> dict[str, Any]:
    """Sync one bounded page per configured route and return a content-free receipt."""

    config = _turn_start_config(
        project=project,
        config_path=config_path,
    )
    policy = config["turn_start_sync"]
    if policy["enabled"] is not True:
        return {
            "ok": True,
            "schema_version": SYNC_SCHEMA_VERSION,
            "status": "not_applicable",
            "observation_count": 0,
            "agent_read_required": False,
            "external_reads_performed": False,
            "external_writes_performed": False,
            "self_message_skipped_count": 0,
            "local_private_state_mutated": False,
            "error_code": None,
            "private_content_returned": False,
            "provider_payload_returned": False,
        }
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    receipts = _dispatch_route_receipts(
        config=config,
        policy=policy,
        observed_at=observed_at,
        lark_cli_executable=lark_cli_executable,
        runner=runner,
        historical_context_only=historical_context_only,
        emit_received_reactions=emit_received_reactions,
    )
    failures = [receipt for receipt in receipts if receipt["ok"] is not True]
    # A realtime collector may have persisted a message before this hook sees
    # the same provider-history item. The owner-private read receipt is
    # independent of optional provider reactions, so it remains the sole
    # authority for whether this turn newly placed content in the Agent chain.
    observation_count = sum(
        int(receipt.get("first_read_count") or receipt.get("accepted_count") or 0)
        for receipt in receipts
    )
    agent_read_required = bool(observation_count)
    if failures and agent_read_required:
        status = "partial"
        error_code = "route_sync_partial"
    elif failures and len(failures) == len(receipts):
        status = "unavailable"
        error_code = str(failures[0]["error_code"])
    elif failures:
        status = "partial"
        error_code = "route_sync_partial"
    elif agent_read_required:
        status = "observed"
        error_code = None
    else:
        status = "empty"
        error_code = None
    return {
        "ok": not failures,
        "schema_version": SYNC_SCHEMA_VERSION,
        "status": status,
        "observation_count": observation_count,
        "agent_read_required": agent_read_required,
        "external_reads_performed": any(
            receipt.get("external_read_performed") is True for receipt in receipts
        ),
        "received_reaction_count": sum(
            int(receipt.get("received_reaction_count") or 0) for receipt in receipts
        ),
        "received_reaction_failure_count": sum(
            int(receipt.get("received_reaction_failure_count") or 0)
            for receipt in receipts
        ),
        "received_reaction_deferred_count": sum(
            int(receipt.get("received_reaction_deferred_count") or 0)
            for receipt in receipts
        ),
        "read_ack_attempt_count": sum(
            int(receipt.get("read_ack_attempt_count") or 0) for receipt in receipts
        ),
        "self_message_skipped_count": sum(
            int(receipt.get("self_message_skipped_count") or 0) for receipt in receipts
        ),
        "external_writes_performed": any(
            receipt.get("external_writes_performed") is True for receipt in receipts
        ),
        "local_private_state_mutated": any(
            receipt.get("local_private_state_mutated") is True for receipt in receipts
        ),
        "error_code": error_code,
        "private_content_returned": False,
        "provider_payload_returned": False,
    }
