from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text


ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_sinks_input_v0"
)
ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_RESULT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_sinks_result_v0"
)
ISSUE_FIX_REVIEWER_NOTIFICATION_SINK_RESULT_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_sink_result_v0"
)
LARK_PERMISSION_PATTERN = re.compile(
    r"(?:missing\s+scope|permission|not\s+in\s+(?:the\s+)?chat|"
    r"lacks?\s+authority|99991672|230027|232033)",
    re.IGNORECASE,
)
SAFE_LOCAL_KEY_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}")
LARK_DESTINATION_PATTERN = re.compile(r"oc_[A-Za-z0-9_-]+")
LARK_MEMBER_PATTERN = re.compile(r"ou_[A-Za-z0-9_-]+")
LARK_MESSAGE_PATTERN = re.compile(r"om_[A-Za-z0-9_-]+")

CommandRunner = Callable[[Sequence[str]], Mapping[str, Any]]
NotificationSinkAdapter = Callable[..., dict[str, Any]]


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
        "private_destination_captured": False,
        "private_member_ids_captured": False,
        "private_bot_profile_captured": False,
        "raw_provider_payload_captured": False,
    }
    if blocker:
        result["blocker"] = blocker
    return result


def _lark_result(
    *,
    repo: str,
    pr_number: int,
    pr_url: str,
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

    profile = str(sink.get("bot_profile") or "").strip()
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
        )

    marker = f"loopx-reviewer-notification:{key.partition(':')[2][:16]}"
    mentions = " ".join(
        f'<at user_id="{member_id}">{html.escape(display_name)}</at>'
        for _, member_id, display_name in resolved
    )
    content = json.dumps(
        {
            "text": (
                f"{mentions} 请协助 review 这个 focused issue-fix PR：{pr_url}\n\n"
                f"[{marker}]"
            )
        },
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
        key,
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
        and marker in readback_text
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
    author_handle: str | None,
    reviewer_handles: Sequence[str],
    sinks_input: Mapping[str, Any],
    execute: bool = False,
    runner: CommandRunner = _default_runner,
    sink_adapters: Mapping[str, NotificationSinkAdapter] | None = None,
) -> dict[str, Any]:
    """Preview or execute private-configured secondary reviewer notifications."""

    author = _normalise_handle(author_handle)
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
        "reviewer_handles": reviewers,
        "status": "gate_required",
        "results": [],
        "receipts": [],
        "external_write_authority_asserted": execute,
        "external_writes_performed": False,
        "notification_verified": False,
        "private_destination_captured": False,
        "private_member_ids_captured": False,
        "private_bot_profile_captured": False,
        "raw_provider_payload_captured": False,
    }
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

    adapters: dict[str, NotificationSinkAdapter] = {"lark_chat": _lark_result}
    if sink_adapters:
        adapters.update(sink_adapters)
    results: list[dict[str, Any]] = []
    for sink in sinks:
        sink_kind = str(sink.get("sink_kind") or "").strip()
        adapter = adapters.get(sink_kind)
        if adapter:
            result = adapter(
                repo=repo,
                pr_number=int(pr_number),
                pr_url=pr_url,
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
    statuses = {str(result.get("status")) for result in results}
    if len(statuses) == 1:
        status = statuses.pop()
    elif any(result.get("ok") is False for result in results):
        status = "partial_failure"
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
            "external_writes_performed": any(
                result.get("external_write_performed") is True for result in results
            ),
            "notification_verified": all(
                result.get("notification_verified") is True for result in results
            ),
        }
    )
    blockers = [
        str(result.get("blocker")) for result in results if result.get("blocker")
    ]
    if blockers:
        base["blocker"] = blockers[0] if len(set(blockers)) == 1 else "multiple"
    return _finalize_result(base)
