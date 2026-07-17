from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, time, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .reward_memory import (
    reviewer_artifact_notification_gate,
    reviewer_notification_before_send_gate,
)


ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_sinks_input_v0"
)
ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_RESULT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_sinks_result_v0"
)
ISSUE_FIX_REVIEWER_NOTIFICATION_SINK_RESULT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_sink_result_v0"
)
ISSUE_FIX_REVIEWER_NOTIFICATION_QUEUE_RECEIPT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_queue_receipt_v0"
)
LARK_PERMISSION_PATTERN = re.compile(
    r"(?:missing\s+scope|permission|not\s+in\s+(?:the\s+)?chat|"
    r"lacks?\s+authority|99991672|230027|232033)",
    re.IGNORECASE,
)
LARK_SEARCH_PERMISSION_PATTERN = re.compile(
    r"search:message|missing\s+scope[^\n]*(?:message|search)",
    re.IGNORECASE,
)
SAFE_LOCAL_KEY_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}")
LARK_DESTINATION_PATTERN = re.compile(r"oc_[A-Za-z0-9_-]+")
LARK_MEMBER_PATTERN = re.compile(r"ou_[A-Za-z0-9_-]+")
LARK_MESSAGE_PATTERN = re.compile(r"om_[A-Za-z0-9_-]+")
LOCAL_TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

CommandRunner = Callable[[Sequence[str]], Mapping[str, Any]]
NotificationSinkAdapter = Callable[..., dict[str, Any]]


def goal_reviewer_notification_config_path(
    *,
    goal: Mapping[str, Any],
    project: str | Path,
) -> Path | None:
    """Resolve a registered local-private sink config without exposing its path."""

    control_plane = (
        goal.get("control_plane")
        if isinstance(goal.get("control_plane"), Mapping)
        else {}
    )
    issue_fix = (
        control_plane.get("issue_fix")
        if isinstance(control_plane.get("issue_fix"), Mapping)
        else {}
    )
    policy = (
        issue_fix.get("reviewer_notification")
        if isinstance(issue_fix.get("reviewer_notification"), Mapping)
        else {}
    )
    if policy.get("enabled") is not True:
        return None
    raw_path = str(policy.get("config_path") or "").strip().replace("\\", "/")
    relative = PurePosixPath(raw_path)
    if (
        not raw_path
        or relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) < 3
        or relative.parts[:2] != (".loopx", "config")
        or relative.suffix != ".json"
    ):
        raise ValueError("goal reviewer notification config pointer is invalid")
    root = Path(project).expanduser().resolve()
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "goal reviewer notification config must stay inside the project"
        ) from exc
    return resolved


def load_goal_reviewer_notification_sinks_input(
    *,
    goal: Mapping[str, Any],
    project: str | Path,
) -> dict[str, Any] | None:
    """Load the goal-default sink config and require explicit profile bindings."""

    path = goal_reviewer_notification_config_path(goal=goal, project=project)
    if path is None:
        return None
    if not path.is_file():
        raise ValueError("goal reviewer notification config is registered but missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("goal reviewer notification config is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION
    ):
        raise ValueError("goal reviewer notification config schema is invalid")
    sinks = payload.get("sinks")
    if not isinstance(sinks, list) or not sinks:
        raise ValueError("goal reviewer notification config must define sinks")
    for sink in sinks:
        if not isinstance(sink, Mapping):
            raise ValueError("goal reviewer notification sinks must be objects")
        if sink.get("sink_kind") == "lark_chat" and not (
            SAFE_LOCAL_KEY_PATTERN.fullmatch(str(sink.get("reader_profile") or ""))
            and sink.get("reader_identity") == "user"
            and SAFE_LOCAL_KEY_PATTERN.fullmatch(
                str(sink.get("sender_profile") or "")
            )
            and sink.get("sender_identity") == "bot"
        ):
            raise ValueError(
                "goal lark reviewer notification requires explicit reader/user "
                "and sender/bot profile bindings"
            )
    return payload


def reviewer_notification_receipts_from_state(
    packet: Mapping[str, Any] | None,
) -> list[str]:
    values = packet.get("reviewer_notification_receipts") if packet else []
    return list(
        dict.fromkeys(
            str(value)
            for value in (values if isinstance(values, list) else [])
            if re.fullmatch(r"sha256:[a-f0-9]{64}", str(value))
        )
    )


def reviewer_notification_queue_from_state(
    packet: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    values = packet.get("reviewer_notification_queue") if packet else []
    queue: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, Mapping):
            continue
        key = str(value.get("idempotency_key") or "")
        if (
            value.get("schema_version")
            != ISSUE_FIX_REVIEWER_NOTIFICATION_QUEUE_RECEIPT_SCHEMA_VERSION
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", key)
            or key in seen
        ):
            continue
        queue.append(dict(value))
        seen.add(key)
    return queue


def with_reviewer_notification_state(
    sinks_input: Mapping[str, Any],
    receipts: Sequence[str],
    queued_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    merged_receipts = reviewer_notification_receipts_from_state(
        {"reviewer_notification_receipts": list(receipts)}
    )
    for value in sinks_input.get("receipts") or []:
        text = str(value)
        if (
            re.fullmatch(r"sha256:[a-f0-9]{64}", text)
            and text not in merged_receipts
        ):
            merged_receipts.append(text)

    queue = reviewer_notification_queue_from_state(
        {"reviewer_notification_queue": list(queued_receipts)}
    )
    for value in reviewer_notification_queue_from_state(
        {"reviewer_notification_queue": sinks_input.get("queued_receipts")}
    ):
        if not any(
            item["idempotency_key"] == value["idempotency_key"] for item in queue
        ):
            queue.append(value)
    verified = set(merged_receipts)
    queue = [item for item in queue if item["idempotency_key"] not in verified]
    return {
        **dict(sinks_input),
        "receipts": merged_receipts,
        "queued_receipts": queue,
    }


def with_reviewer_notification_receipts(
    sinks_input: Mapping[str, Any],
    receipts: Sequence[str],
) -> dict[str, Any]:
    return with_reviewer_notification_state(sinks_input, receipts, ())


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


def _normalise_handle(value: Any) -> str | None:
    text = public_safe_compact_text(value, limit=100).strip().lstrip("@").lower()
    return f"@{text}" if text else None


def _humanize_pr_title(value: Any) -> str:
    title = public_safe_compact_text(value, limit=180) or ""
    title = re.sub(
        r"^(?:fix|bugfix)(?:\([^)]*\))?!?\s*:\s*",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return title.rstrip(".。")


def _normalise_issue_refs(values: Sequence[Any]) -> list[str]:
    return list(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if re.fullmatch(r"#\d+", str(value).strip())
        )
    )[:3]


def _idempotency_key(
    *,
    repo: str,
    pr_number: int,
    sink_kind: str,
    sink_instance_key: str,
    reviewer_handles: Sequence[str],
) -> str:
    logical_effect = json.dumps(
        {
            "repo": repo,
            "pr_number": pr_number,
            "sink_kind": sink_kind,
            "sink_instance_key": sink_instance_key,
            "reviewer_handles": sorted(reviewer_handles),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(logical_effect.encode('utf-8')).hexdigest()}"


def _parse_delivery_observed_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    text = str(value).strip()
    if not text:
        raise ValueError("delivery_observed_at must not be empty")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("delivery_observed_at must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("delivery_observed_at must include a timezone")
    return parsed


def _delivery_window_decision(
    policy: Any,
    *,
    delivery_observed_at: str | None,
) -> dict[str, Any]:
    if policy is None:
        return {"configured": False, "allowed": True}
    if not isinstance(policy, Mapping):
        raise ValueError("delivery_policy must be an object")
    timezone_name = str(policy.get("timezone") or "").strip()
    allowed_local_time = policy.get("allowed_local_time")
    if not isinstance(allowed_local_time, Mapping):
        raise ValueError("delivery_policy.allowed_local_time must be an object")
    start_text = str(allowed_local_time.get("start") or "").strip()
    end_text = str(allowed_local_time.get("end") or "").strip()
    if (
        not LOCAL_TIME_PATTERN.fullmatch(start_text)
        or not LOCAL_TIME_PATTERN.fullmatch(end_text)
        or start_text == end_text
        or policy.get("outside_window") != "queue_without_send"
    ):
        raise ValueError("delivery_policy window is invalid")
    try:
        location = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("delivery_policy timezone is invalid") from exc

    observed = _parse_delivery_observed_at(delivery_observed_at)
    local = observed.astimezone(location)
    start = time.fromisoformat(start_text)
    end = time.fromisoformat(end_text)
    current = local.timetz().replace(tzinfo=None)
    allowed = (
        start <= current < end
        if start < end
        else current >= start or current < end
    )
    decision: dict[str, Any] = {
        "configured": True,
        "allowed": allowed,
        "timezone": timezone_name,
        "start": start_text,
        "end": end_text,
        "observed_at": observed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    if not allowed:
        next_start = datetime.combine(local.date(), start, tzinfo=location)
        if local >= next_start:
            next_start += timedelta(days=1)
        decision["not_before"] = (
            next_start.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return decision


def _queued_result(
    *,
    repo: str,
    pr_number: int,
    sink_kind: str,
    sink_instance_key: str,
    reviewer_handles: Sequence[str],
    execute: bool,
    window: Mapping[str, Any],
) -> dict[str, Any]:
    if not SAFE_LOCAL_KEY_PATTERN.fullmatch(sink_instance_key):
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=[],
            idempotency_key=None,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=execute,
            blocker="reviewer_notification_delivery_policy_invalid",
        )
    key = _idempotency_key(
        repo=repo,
        pr_number=pr_number,
        sink_kind=sink_kind,
        sink_instance_key=sink_instance_key,
        reviewer_handles=reviewer_handles,
    )
    result = _public_result(
        sink_kind=sink_kind,
        reviewer_handles=reviewer_handles,
        idempotency_key=key,
        status="queued_until_window",
        ok=True,
        external_write_authority_asserted=execute,
    )
    result["queue_receipt"] = {
        "schema_version": (
            ISSUE_FIX_REVIEWER_NOTIFICATION_QUEUE_RECEIPT_SCHEMA_VERSION
        ),
        "idempotency_key": key,
        "sink_kind": sink_kind,
        "reviewer_handles": list(reviewer_handles),
        "queued_at": window["observed_at"],
        "not_before": window["not_before"],
        "timezone": window["timezone"],
        "allowed_local_time": {
            "start": window["start"],
            "end": window["end"],
        },
        "status": "queued",
    }
    return result


def _find_message_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        candidate = value.get("message_id")
        if isinstance(candidate, str) and LARK_MESSAGE_PATTERN.fullmatch(candidate):
            return candidate
        for nested in value.values():
            found = _find_message_id(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_message_id(nested)
            if found:
                return found
    return None


def _parse_json_object(value: Any) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def _payload_contains_text(value: Any, text: str) -> bool:
    if isinstance(value, Mapping):
        return any(_payload_contains_text(child, text) for child in value.values())
    if isinstance(value, list):
        return any(_payload_contains_text(child, text) for child in value)
    return isinstance(value, str) and text in value


def _lark_member_ids(value: Any) -> set[str]:
    """Collect exact member ids from a provider response without retaining it."""

    member_ids: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key in {"member_id", "open_id"} and isinstance(child, str):
                    member_id = child.strip()
                    if LARK_MEMBER_PATTERN.fullmatch(member_id):
                        member_ids.add(member_id)
                else:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return member_ids


def _public_result(
    *,
    sink_kind: str,
    reviewer_handles: Sequence[str],
    idempotency_key: str | None,
    status: str,
    ok: bool,
    external_write_authority_asserted: bool,
    external_write_performed: bool = False,
    verification_performed: bool = False,
    notification_verified: bool = False,
    bot_identity_verified: bool = False,
    reader_identity_verified: bool = False,
    semantic_dedupe_status: str | None = None,
    blocker: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": ok,
        "schema_version": ISSUE_FIX_REVIEWER_NOTIFICATION_SINK_RESULT_SCHEMA_VERSION,
        "sink_kind": sink_kind,
        "status": status,
        "reviewer_handles": list(reviewer_handles),
        "resolved_reviewer_count": len(reviewer_handles),
        "idempotency_key": idempotency_key,
        "identity_scope": "project_dedicated",
        "external_write_authority_asserted": external_write_authority_asserted,
        "external_write_performed": external_write_performed,
        "verification_performed": verification_performed,
        "notification_verified": notification_verified,
        "bot_identity_verified": bot_identity_verified,
        "reader_identity_verified": reader_identity_verified,
        "private_destination_captured": False,
        "private_member_ids_captured": False,
        "private_bot_profile_captured": False,
        "raw_provider_payload_captured": False,
    }
    if blocker:
        result["blocker"] = blocker
    if semantic_dedupe_status:
        result["semantic_dedupe_status"] = semantic_dedupe_status
    return result


def _lark_result(
    *,
    repo: str,
    pr_number: int,
    pr_url: str,
    pr_title: str,
    linked_issue_refs: Sequence[str],
    reviewer_handles: Sequence[str],
    sink: Mapping[str, Any],
    receipts: set[str],
    execute: bool,
    runner: CommandRunner,
) -> dict[str, Any]:
    sink_kind = "lark_chat"
    if sink.get("identity_scope") != "project_dedicated":
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=[],
            idempotency_key=None,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=execute,
            blocker="dedicated_bot_identity_required",
        )

    explicit_profile_bindings = any(
        sink.get(field) is not None
        for field in (
            "reader_profile",
            "reader_identity",
            "sender_profile",
            "sender_identity",
        )
    )
    reader_profile = str(sink.get("reader_profile") or "").strip()
    reader_identity = str(sink.get("reader_identity") or "").strip()
    profile = str(
        sink.get("sender_profile") or sink.get("bot_profile") or ""
    ).strip()
    sender_identity = str(sink.get("sender_identity") or "bot").strip()
    expected_bot_name = public_safe_compact_text(
        sink.get("bot_display_name"),
        limit=100,
    )
    destination_id = str(sink.get("destination_id") or "").strip()
    instance_key = str(sink.get("sink_instance_key") or "").strip()
    if (
        not SAFE_LOCAL_KEY_PATTERN.fullmatch(profile)
        or profile.lower() == "default"
        or not SAFE_LOCAL_KEY_PATTERN.fullmatch(instance_key)
        or not expected_bot_name
        or sender_identity != "bot"
        or (
            explicit_profile_bindings
            and (
                not SAFE_LOCAL_KEY_PATTERN.fullmatch(reader_profile)
                or reader_identity != "user"
                or not sink.get("sender_profile")
            )
        )
    ):
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=[],
            idempotency_key=None,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=execute,
            blocker="dedicated_bot_identity_required",
        )
    if not LARK_DESTINATION_PATTERN.fullmatch(destination_id):
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=[],
            idempotency_key=None,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=execute,
            blocker="reviewer_notification_destination_unavailable",
        )

    raw_identities = sink.get("reviewer_identities")
    identities = {
        handle: value
        for raw_handle, value in (
            raw_identities.items() if isinstance(raw_identities, Mapping) else []
        )
        if (handle := _normalise_handle(raw_handle)) is not None
    }
    resolved: list[tuple[str, str, str]] = []
    for handle in reviewer_handles:
        value = identities.get(handle)
        identity = value if isinstance(value, Mapping) else {}
        member_id = str(identity.get("member_id") or "").strip()
        display_name = public_safe_compact_text(
            identity.get("display_name") or handle,
            limit=80,
        )
        if not LARK_MEMBER_PATTERN.fullmatch(member_id):
            return _public_result(
                sink_kind=sink_kind,
                reviewer_handles=[],
                idempotency_key=None,
                status="gate_required",
                ok=False,
                external_write_authority_asserted=execute,
                blocker="reviewer_notification_identity_unresolved",
            )
        resolved.append((handle, member_id, display_name or handle))

    key = _idempotency_key(
        repo=repo,
        pr_number=pr_number,
        sink_kind=sink_kind,
        sink_instance_key=instance_key,
        reviewer_handles=reviewer_handles,
    )
    if key in receipts:
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=reviewer_handles,
            idempotency_key=key,
            status="already_notified",
            ok=True,
            external_write_authority_asserted=execute,
            notification_verified=True,
            semantic_dedupe_status="persisted_evidence_match",
        )
    if not execute:
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=reviewer_handles,
            idempotency_key=key,
            status="preview_ready",
            ok=True,
            external_write_authority_asserted=False,
        )

    reader_verified = False
    semantic_dedupe_status = "not_configured"
    if explicit_profile_bindings:
        try:
            reader_status = runner(
                [
                    "lark-cli",
                    "--profile",
                    reader_profile,
                    "auth",
                    "status",
                    "--verify",
                    "--json",
                ]
            )
        except (OSError, subprocess.SubprocessError):
            reader_status = {"returncode": 1}
        reader_payload = _parse_json_object(reader_status.get("stdout"))
        reader = (
            (reader_payload.get("identities") or {}).get("user")
            if isinstance(reader_payload, Mapping)
            and isinstance(reader_payload.get("identities"), Mapping)
            else {}
        )
        reader = reader if isinstance(reader, Mapping) else {}
        reader_verified = bool(
            reader_status.get("returncode") == 0
            and reader.get("available") is True
            and reader.get("verified") is True
        )
        if not reader_verified:
            return _public_result(
                sink_kind=sink_kind,
                reviewer_handles=reviewer_handles,
                idempotency_key=key,
                status="gate_required",
                ok=False,
                external_write_authority_asserted=True,
                blocker="reviewer_notification_reader_identity_mismatch",
            )
        try:
            members = runner(
                [
                    "lark-cli",
                    "--profile",
                    reader_profile,
                    "im",
                    "chat.members",
                    "get",
                    "--chat-id",
                    destination_id,
                    "--member-id-type",
                    "open_id",
                    "--page-all",
                    "--as",
                    "user",
                    "--format",
                    "json",
                ]
            )
        except (OSError, subprocess.SubprocessError):
            members = {"returncode": 1}
        if members.get("returncode") != 0:
            provider_error = " ".join(
                str(members.get(field) or "") for field in ("stderr", "stdout")
            )
            return _public_result(
                sink_kind=sink_kind,
                reviewer_handles=reviewer_handles,
                idempotency_key=key,
                status="gate_required",
                ok=False,
                external_write_authority_asserted=True,
                reader_identity_verified=True,
                blocker=(
                    "lark_bot_group_access_required"
                    if LARK_PERMISSION_PATTERN.search(provider_error)
                    else "reviewer_notification_provider_failed"
                ),
            )

        try:
            semantic_search = runner(
                [
                    "lark-cli",
                    "--profile",
                    reader_profile,
                    "im",
                    "+messages-search",
                    "--chat-id",
                    destination_id,
                    "--query",
                    pr_url,
                    "--page-size",
                    "20",
                    "--as",
                    "user",
                    "--no-reactions",
                    "--format",
                    "json",
                ]
            )
        except (OSError, subprocess.SubprocessError):
            semantic_search = {"returncode": 1}
        semantic_payload = _parse_json_object(semantic_search.get("stdout"))
        if semantic_search.get("returncode") == 0:
            if semantic_payload is None:
                return _public_result(
                    sink_kind=sink_kind,
                    reviewer_handles=reviewer_handles,
                    idempotency_key=key,
                    status="gate_required",
                    ok=False,
                    external_write_authority_asserted=True,
                    reader_identity_verified=True,
                    semantic_dedupe_status="provider_failed",
                    blocker="reviewer_notification_dedupe_readback_failed",
                )
            if _payload_contains_text(semantic_payload, pr_url):
                return _public_result(
                    sink_kind=sink_kind,
                    reviewer_handles=reviewer_handles,
                    idempotency_key=key,
                    status="already_notified",
                    ok=True,
                    external_write_authority_asserted=True,
                    verification_performed=True,
                    notification_verified=True,
                    reader_identity_verified=True,
                    semantic_dedupe_status="configured_chat_match",
                )
            semantic_dedupe_status = "configured_chat_no_match"
        else:
            provider_error = " ".join(
                str(semantic_search.get(field) or "")
                for field in ("stderr", "stdout")
            )
            if LARK_SEARCH_PERMISSION_PATTERN.search(provider_error):
                semantic_dedupe_status = "permission_fallback"
            else:
                return _public_result(
                    sink_kind=sink_kind,
                    reviewer_handles=reviewer_handles,
                    idempotency_key=key,
                    status="gate_required",
                    ok=False,
                    external_write_authority_asserted=True,
                    reader_identity_verified=True,
                    semantic_dedupe_status="provider_failed",
                    blocker="reviewer_notification_dedupe_readback_failed",
                )

    try:
        identity_status = runner(
            [
                "lark-cli",
                "--profile",
                profile,
                "auth",
                "status",
                "--verify",
                "--json",
            ]
        )
    except (OSError, subprocess.SubprocessError):
        identity_status = {"returncode": 1}
    identity_payload = _parse_json_object(identity_status.get("stdout"))
    bot_identity = (
        (identity_payload.get("identities") or {}).get("bot")
        if isinstance(identity_payload, Mapping)
        and isinstance(identity_payload.get("identities"), Mapping)
        else {}
    )
    bot_identity = bot_identity if isinstance(bot_identity, Mapping) else {}
    if not (
        identity_status.get("returncode") == 0
        and bot_identity.get("available") is True
        and bot_identity.get("verified") is True
        and str(bot_identity.get("appName") or "") == expected_bot_name
    ):
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=reviewer_handles,
            idempotency_key=key,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=True,
            blocker="dedicated_bot_identity_mismatch",
            reader_identity_verified=reader_verified,
        )

    if explicit_profile_bindings:
        try:
            sender_members = runner(
                [
                    "lark-cli",
                    "--profile",
                    profile,
                    "im",
                    "chat.members",
                    "get",
                    "--chat-id",
                    destination_id,
                    "--member-id-type",
                    "open_id",
                    "--page-all",
                    "--as",
                    "bot",
                    "--format",
                    "json",
                ]
            )
        except (OSError, subprocess.SubprocessError):
            sender_members = {"returncode": 1}
        if sender_members.get("returncode") != 0:
            provider_error = " ".join(
                str(sender_members.get(field) or "")
                for field in ("stderr", "stdout")
            )
            return _public_result(
                sink_kind=sink_kind,
                reviewer_handles=reviewer_handles,
                idempotency_key=key,
                status="gate_required",
                ok=False,
                external_write_authority_asserted=True,
                bot_identity_verified=True,
                reader_identity_verified=reader_verified,
                blocker=(
                    "lark_bot_group_access_required"
                    if LARK_PERMISSION_PATTERN.search(provider_error)
                    else "reviewer_notification_provider_failed"
                ),
            )
        sender_member_ids = _lark_member_ids(
            _parse_json_object(sender_members.get("stdout"))
        )
        if any(member_id not in sender_member_ids for _, member_id, _ in resolved):
            return _public_result(
                sink_kind=sink_kind,
                reviewer_handles=reviewer_handles,
                idempotency_key=key,
                status="gate_required",
                ok=False,
                external_write_authority_asserted=True,
                bot_identity_verified=True,
                reader_identity_verified=reader_verified,
                blocker="reviewer_notification_identity_unresolved",
            )

    provider_idempotency_key = f"loopx-{key.partition(':')[2][:32]}"
    mentions = " ".join(
        f'<at user_id="{member_id}">{html.escape(display_name)}</at>'
        for _, member_id, display_name in resolved
    )
    issue_clause = (
        f"（修复 {', '.join(linked_issue_refs)}）" if linked_issue_refs else ""
    )
    summary = f"：{pr_title}" if pr_title else ""
    content = json.dumps(
        {"text": f"{mentions} 请帮忙 review PR #{pr_number}{issue_clause}{summary}。{pr_url}"},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    send_args = [
        "lark-cli",
        "--profile",
        profile,
        "im",
        "+messages-send",
        "--chat-id",
        destination_id,
        "--content",
        content,
        "--msg-type",
        "text",
        "--idempotency-key",
        provider_idempotency_key,
        "--as",
        "bot",
        "--format",
        "json",
    ]
    try:
        send = runner(send_args)
    except (OSError, subprocess.SubprocessError):
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=reviewer_handles,
            idempotency_key=key,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=True,
            blocker="reviewer_notification_provider_unavailable",
            bot_identity_verified=True,
            reader_identity_verified=reader_verified,
        )
    if send.get("returncode") != 0:
        provider_error = " ".join(
            str(send.get(field) or "") for field in ("stderr", "stdout")
        )
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=reviewer_handles,
            idempotency_key=key,
            status="gate_required",
            ok=False,
            external_write_authority_asserted=True,
            blocker=(
                "lark_bot_group_access_required"
                if LARK_PERMISSION_PATTERN.search(provider_error)
                else "reviewer_notification_provider_failed"
            ),
            bot_identity_verified=True,
            reader_identity_verified=reader_verified,
        )

    send_payload = _parse_json_object(send.get("stdout"))
    message_id = _find_message_id(send_payload)
    if not message_id:
        return _public_result(
            sink_kind=sink_kind,
            reviewer_handles=reviewer_handles,
            idempotency_key=key,
            status="sent_unverified",
            ok=False,
            external_write_authority_asserted=True,
            external_write_performed=True,
            blocker="lark_notification_not_verified",
            bot_identity_verified=True,
            reader_identity_verified=reader_verified,
        )
    try:
        readback = runner(
            [
                "lark-cli",
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
            ]
        )
    except (OSError, subprocess.SubprocessError):
        readback = {"returncode": 1}
    readback_payload = _parse_json_object(readback.get("stdout"))
    readback_text = (
        json.dumps(readback_payload, ensure_ascii=False, sort_keys=True)
        if readback_payload is not None
        else ""
    )
    verified = bool(
        readback.get("returncode") == 0
        and message_id in readback_text
        and pr_url in readback_text
    )
    return _public_result(
        sink_kind=sink_kind,
        reviewer_handles=reviewer_handles,
        idempotency_key=key,
        status="sent_verified" if verified else "sent_unverified",
        ok=verified,
        external_write_authority_asserted=True,
        external_write_performed=True,
        verification_performed=True,
        notification_verified=verified,
        bot_identity_verified=True,
        reader_identity_verified=reader_verified,
        semantic_dedupe_status=semantic_dedupe_status,
        blocker=None if verified else "lark_notification_not_verified",
    )


def validate_issue_fix_reviewer_notification_sinks_result(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != (
        ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_RESULT_SCHEMA_VERSION
    ):
        errors.append(
            "schema_version must be issue_fix_reviewer_notification_sinks_result_v0"
        )
    for field in (
        "private_destination_captured",
        "private_member_ids_captured",
        "private_bot_profile_captured",
        "raw_provider_payload_captured",
    ):
        if packet.get(field) is not False:
            errors.append(f"{field} must be false")
    results = packet.get("results")
    if not isinstance(results, list):
        errors.append("results must be a list")
        results = []
    for result in results:
        if not isinstance(result, Mapping):
            errors.append("each sink result must be an object")
            continue
        if result.get("schema_version") != (
            ISSUE_FIX_REVIEWER_NOTIFICATION_SINK_RESULT_SCHEMA_VERSION
        ):
            errors.append("sink result schema_version is invalid")
        for field in (
            "private_destination_captured",
            "private_member_ids_captured",
            "private_bot_profile_captured",
            "raw_provider_payload_captured",
        ):
            if result.get(field) is not False:
                errors.append(f"sink result {field} must be false")
    receipts = packet.get("receipts")
    if not isinstance(receipts, list) or any(
        not re.fullmatch(r"sha256:[a-f0-9]{64}", str(value))
        for value in (receipts if isinstance(receipts, list) else [])
    ):
        errors.append("receipts must contain only stable sha256 keys")
    queued_receipts = packet.get("queued_receipts")
    if not isinstance(queued_receipts, list):
        errors.append("queued_receipts must be a list")
        queued_receipts = []
    queued_keys: set[str] = set()
    for receipt in queued_receipts:
        if not isinstance(receipt, Mapping):
            errors.append("each queued receipt must be an object")
            continue
        key = str(receipt.get("idempotency_key") or "")
        window = receipt.get("allowed_local_time")
        if (
            receipt.get("schema_version")
            != ISSUE_FIX_REVIEWER_NOTIFICATION_QUEUE_RECEIPT_SCHEMA_VERSION
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", key)
            or key in queued_keys
            or receipt.get("status") != "queued"
            or not public_safe_compact_text(receipt.get("sink_kind"), limit=50)
            or not isinstance(receipt.get("reviewer_handles"), list)
            or not isinstance(window, Mapping)
            or not LOCAL_TIME_PATTERN.fullmatch(str(window.get("start") or ""))
            or not LOCAL_TIME_PATTERN.fullmatch(str(window.get("end") or ""))
        ):
            errors.append("queued receipt is invalid")
            continue
        queued_keys.add(key)
    if isinstance(receipts, list) and queued_keys.intersection(
        str(value) for value in receipts
    ):
        errors.append("verified receipts cannot remain queued")
    writes = packet.get("external_writes_performed") is True
    if writes != any(
        isinstance(result, Mapping) and result.get("external_write_performed") is True
        for result in results
    ):
        errors.append("external_writes_performed must reflect sink results")
    verified = packet.get("notification_verified") is True
    if results and verified != all(
        isinstance(result, Mapping) and result.get("notification_verified") is True
        for result in results
    ):
        errors.append("notification_verified must reflect every sink result")
    return {
        "ok": not errors,
        "schema_version": "issue_fix_reviewer_notification_sinks_validation_v0",
        "errors": errors,
    }


def _finalize_result(packet: dict[str, Any]) -> dict[str, Any]:
    validation = validate_issue_fix_reviewer_notification_sinks_result(packet)
    packet["ok"] = bool(packet.get("ok") and validation["ok"])
    packet["validation"] = validation
    return packet


def build_issue_fix_reviewer_notification_sinks_result(
    *,
    repo: str,
    pr_number: int,
    pr_url: str,
    pr_title: str | None = None,
    linked_issue_refs: Sequence[str] = (),
    author_handle: str | None,
    reviewer_handles: Sequence[str],
    sinks_input: Mapping[str, Any],
    reviewer_artifact_application: Mapping[str, Any] | None = None,
    reviewer_notification_policy_application: Mapping[str, Any] | None = None,
    reviewer_artifact_required: bool = False,
    execute: bool = False,
    delivery_observed_at: str | None = None,
    runner: CommandRunner = _default_runner,
    sink_adapters: Mapping[str, NotificationSinkAdapter] | None = None,
) -> dict[str, Any]:
    """Preview or execute private-configured secondary reviewer notifications."""

    author = _normalise_handle(author_handle)
    title = _humanize_pr_title(pr_title)
    artifact_gate = reviewer_artifact_notification_gate(
        reviewer_artifact_application
    )
    before_send_gate = reviewer_notification_before_send_gate(
        reviewer_notification_policy_application,
        repo=repo,
        pr_number=pr_number,
        pr_url=pr_url,
    )
    artifact = (
        reviewer_artifact_application.get("reviewer_artifact")
        if isinstance(reviewer_artifact_application, Mapping)
        else None
    )
    artifact = artifact if isinstance(artifact, Mapping) else {}
    if artifact_gate["passed"] is True and not (
        artifact.get("repo") == public_safe_compact_text(repo, limit=200)
        and artifact.get("pr_ref") == f"#{int(pr_number)}"
        and artifact.get("permalink")
        == public_safe_compact_text(pr_url, limit=300)
    ):
        artifact_gate = {
            **artifact_gate,
            "passed": False,
            "status": "blocked",
            "reason_codes": ["current_artifact_identity_mismatch"],
        }
    if artifact_gate["passed"] is True:
        title = str(artifact_gate["summary"])
    issue_refs = _normalise_issue_refs(linked_issue_refs)
    reviewers = list(
        dict.fromkeys(
            handle
            for value in reviewer_handles
            if (handle := _normalise_handle(value)) is not None
        )
    )[:3]
    base: dict[str, Any] = {
        "ok": False,
        "schema_version": ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_RESULT_SCHEMA_VERSION,
        "mode": "issue-fix-reviewer-notification-sinks",
        "repo": public_safe_compact_text(repo, limit=200),
        "pr_ref": f"#{int(pr_number)}",
        "permalink": public_safe_compact_text(pr_url, limit=300),
        "pr_title": title,
        "linked_issue_refs": issue_refs,
        "reviewer_handles": reviewers,
        "status": "gate_required",
        "results": [],
        "receipts": [],
        "queued_receipts": [],
        "external_write_authority_asserted": execute,
        "external_writes_performed": False,
        "notification_verified": False,
        "private_destination_captured": False,
        "private_member_ids_captured": False,
        "private_bot_profile_captured": False,
        "raw_provider_payload_captured": False,
        "reward_memory_reviewer_artifact_required": reviewer_artifact_required,
        "reward_memory_reviewer_artifact_gate": artifact_gate,
        "reward_memory_before_send_gate": before_send_gate,
        "reward_memory_before_send_status": before_send_gate["status"],
    }
    if reviewer_artifact_required and artifact_gate["passed"] is not True:
        base["blocker"] = "reward_memory_reviewer_artifact_unverified"
        return _finalize_result(base)
    if sinks_input.get("schema_version") != (
        ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION
    ):
        base["blocker"] = "reviewer_notification_sinks_input_invalid"
        return _finalize_result(base)
    if not author:
        base["blocker"] = "reviewer_notification_author_unavailable"
        return _finalize_result(base)
    if not reviewers:
        base["blocker"] = "reviewer_notification_reviewer_unavailable"
        return _finalize_result(base)
    if author in reviewers:
        base["blocker"] = "reviewer_notification_author_exclusion_failed"
        return _finalize_result(base)

    raw_sinks = sinks_input.get("sinks")
    sinks = raw_sinks if isinstance(raw_sinks, list) else []
    if (
        not sinks
        or len(sinks) > 3
        or not all(isinstance(sink, Mapping) for sink in sinks)
    ):
        base["blocker"] = "reviewer_notification_sinks_input_invalid"
        return _finalize_result(base)
    raw_receipts = sinks_input.get("receipts")
    receipts = {
        str(value)
        for value in (raw_receipts if isinstance(raw_receipts, list) else [])
        if re.fullmatch(r"sha256:[a-f0-9]{64}", str(value))
    }
    semantic_history_pr_refs = {
        public_safe_compact_text(value, limit=300)
        for value in (
            sinks_input.get("_semantic_history_pr_refs")
            if isinstance(sinks_input.get("_semantic_history_pr_refs"), list)
            else []
        )
        if public_safe_compact_text(value, limit=300)
    }
    queued_receipts_by_key = {
        str(value["idempotency_key"]): value
        for value in reviewer_notification_queue_from_state(
            {"reviewer_notification_queue": sinks_input.get("queued_receipts")}
        )
    }
    effective_delivery_policy = sinks_input.get("delivery_policy")
    if before_send_gate["passed"] is True:
        effective_delivery_policy = before_send_gate["delivery_policy"]
    try:
        delivery_window = _delivery_window_decision(
            effective_delivery_policy,
            delivery_observed_at=delivery_observed_at,
        )
    except ValueError:
        base["blocker"] = "reviewer_notification_delivery_policy_invalid"
        return _finalize_result(base)
    base["delivery_policy_configured"] = delivery_window["configured"]
    base["delivery_policy_source"] = (
        "reward_memory"
        if before_send_gate["passed"] is True
        else "sink_config"
        if sinks_input.get("delivery_policy") is not None
        else "default_unrestricted"
    )

    adapters: dict[str, NotificationSinkAdapter] = {"lark_chat": _lark_result}
    if sink_adapters:
        adapters.update(sink_adapters)
    results: list[dict[str, Any]] = []
    for sink in sinks:
        sink_kind = str(sink.get("sink_kind") or "").strip()
        if sink_kind == "lark_chat" and pr_url in semantic_history_pr_refs:
            sink_instance_key = str(sink.get("sink_instance_key") or "").strip()
            if SAFE_LOCAL_KEY_PATTERN.fullmatch(sink_instance_key):
                receipts.add(
                    _idempotency_key(
                        repo=repo,
                        pr_number=int(pr_number),
                        sink_kind=sink_kind,
                        sink_instance_key=sink_instance_key,
                        reviewer_handles=reviewers,
                    )
                )
        adapter = adapters.get(sink_kind)
        if adapter and execute and not delivery_window["allowed"]:
            sink_instance_key = str(sink.get("sink_instance_key") or "").strip()
            queued_key = (
                _idempotency_key(
                    repo=repo,
                    pr_number=int(pr_number),
                    sink_kind=sink_kind,
                    sink_instance_key=sink_instance_key,
                    reviewer_handles=reviewers,
                )
                if SAFE_LOCAL_KEY_PATTERN.fullmatch(sink_instance_key)
                else None
            )
            if queued_key and queued_key in receipts:
                result = _public_result(
                    sink_kind=sink_kind,
                    reviewer_handles=reviewers,
                    idempotency_key=queued_key,
                    status="already_notified",
                    ok=True,
                    external_write_authority_asserted=execute,
                    notification_verified=True,
                )
            elif queued_key and queued_key in queued_receipts_by_key:
                result = _public_result(
                    sink_kind=sink_kind,
                    reviewer_handles=reviewers,
                    idempotency_key=queued_key,
                    status="already_queued",
                    ok=True,
                    external_write_authority_asserted=execute,
                )
                result["queue_receipt"] = dict(queued_receipts_by_key[queued_key])
            else:
                result = _queued_result(
                    repo=repo,
                    pr_number=int(pr_number),
                    sink_kind=sink_kind,
                    sink_instance_key=sink_instance_key,
                    reviewer_handles=reviewers,
                    execute=execute,
                    window=delivery_window,
                )
        elif adapter:
            result = adapter(
                repo=repo,
                pr_number=int(pr_number),
                pr_url=pr_url,
                pr_title=title,
                linked_issue_refs=issue_refs,
                reviewer_handles=reviewers,
                sink=sink,
                receipts=receipts,
                execute=execute,
                runner=runner,
            )
        else:
            result = _public_result(
                sink_kind=public_safe_compact_text(sink_kind, limit=50) or "unknown",
                reviewer_handles=[],
                idempotency_key=None,
                status="gate_required",
                ok=False,
                external_write_authority_asserted=execute,
                blocker="reviewer_notification_sink_unsupported",
            )
        results.append(result)

    successful_receipts = list(
        dict.fromkeys(
            result["idempotency_key"]
            for result in results
            if result.get("notification_verified") is True
            and result.get("idempotency_key")
        )
    )
    queued_receipts = list(
        {
            str(receipt["idempotency_key"]): receipt
            for result in results
            if isinstance(result.get("queue_receipt"), Mapping)
            for receipt in [dict(result["queue_receipt"])]
        }.values()
    )
    queued_receipts_by_result_key = {
        str(receipt["idempotency_key"]): receipt for receipt in queued_receipts
    }
    for result in results:
        key = str(result.get("idempotency_key") or "")
        prior = queued_receipts_by_key.get(key)
        if (
            prior is not None
            and result.get("ok") is False
            and result.get("external_write_performed") is not True
            and key not in queued_receipts_by_result_key
        ):
            queued_receipts.append(dict(prior))
            queued_receipts_by_result_key[key] = dict(prior)
    statuses = {str(result.get("status")) for result in results}
    if len(statuses) == 1:
        status = statuses.pop()
    elif any(result.get("ok") is False for result in results):
        status = "partial_failure"
    elif queued_receipts:
        status = "partial_queued"
    elif execute:
        status = "sent_verified"
    else:
        status = "preview_ready"
    base.update(
        {
            "ok": all(result.get("ok") is True for result in results),
            "status": status,
            "results": results,
            "receipts": successful_receipts,
            "queued_receipts": queued_receipts,
            "external_writes_performed": any(
                result.get("external_write_performed") is True for result in results
            ),
            "notification_verified": all(
                result.get("notification_verified") is True for result in results
            ),
            "semantic_history_evidence_applied": bool(
                pr_url in semantic_history_pr_refs
            ),
        }
    )
    blockers = [
        str(result.get("blocker")) for result in results if result.get("blocker")
    ]
    if blockers:
        base["blocker"] = blockers[0] if len(set(blockers)) == 1 else "multiple"
    return _finalize_result(base)
