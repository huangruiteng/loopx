"""Batch-level integrity guards for multi-role Explore visual delivery."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Mapping


def _configured_stage_tokens(role_sink: Mapping[str, Any]) -> list[tuple[int, str]]:
    stages = [
        (
            int(item.get("stage_index") or 0),
            str(item.get("whiteboard_token") or "").strip(),
        )
        for item in role_sink.get("stage_whiteboards") or []
        if isinstance(item, Mapping)
        and int(item.get("stage_index") or 0) > 0
        and str(item.get("whiteboard_token") or "").strip()
    ]
    fallback = str(role_sink.get("whiteboard_token") or "").strip()
    return stages or ([(1, fallback)] if fallback else [])


def cross_role_stage_token_conflict_delivery(
    *,
    bundle: Mapping[str, Any],
    visual_sinks: Mapping[str, Any],
    requested_roles: list[str],
    active_roles: list[str],
    execute: bool,
    schema_version: str,
) -> dict[str, Any] | None:
    """Fail before writes when distinct visual roles share a stage board."""

    token_refs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for role in active_roles:
        role_sink = visual_sinks.get(role)
        if not isinstance(role_sink, Mapping):
            continue
        for stage_index, token in _configured_stage_tokens(role_sink):
            token_refs[token].append({"view_role": role, "stage_index": stage_index})
    conflicts = [
        {
            "token_fingerprint": hashlib.sha256(token.encode("utf-8")).hexdigest()[:12],
            "stage_refs": refs,
        }
        for token, refs in token_refs.items()
        if len({str(ref["view_role"]) for ref in refs}) > 1
    ]
    if not conflicts:
        return None
    error = "each Explore visual role/stage must use a distinct whiteboard token"
    views = {
        role: {
            "ok": False,
            "status": "stage_whiteboard_token_conflict",
            "execute": execute,
            "published": False,
            "retryable": False,
            "view_role": role,
            "source_digest": bundle.get("source_digest"),
            "source_revision": bundle.get("source_revision"),
            "conflicts": conflicts,
            "error": error,
        }
        for role in requested_roles
        if role in active_roles
    }
    return {
        "ok": False,
        "status": "configuration_conflict",
        "published": False,
        "retryable": False,
        "required_action": error,
        "configured_roles": requested_roles,
        "missing_recommended_roles": [
            role for role in active_roles if role not in requested_roles
        ],
        "schema_version": schema_version,
        "execute": execute,
        "presentation_mode": bundle.get("presentation_mode"),
        "reason_codes": bundle.get("reason_codes") or [],
        "source_digest": bundle.get("source_digest"),
        "source_revision": bundle.get("source_revision"),
        "recommended_roles": active_roles,
        "conflicts": conflicts,
        "views": views,
        "error": error,
    }


def finalize_visual_role_results(
    results: Mapping[str, dict[str, Any]], *, execute: bool
) -> None:
    """Recompute role status only after the batch-wide marker postcondition."""

    for role, result in results.items():
        stages = result.get("stages")
        if not isinstance(stages, list):
            continue
        role_ok = all(bool(stage.get("ok")) for stage in stages)
        retryable = any(bool(stage.get("retryable")) for stage in stages)
        result.update(
            {
                "ok": role_ok,
                "status": (
                    "published"
                    if execute and role_ok
                    else "would_publish"
                    if role_ok
                    else "publish_failed"
                ),
                "published": bool(execute and role_ok),
                "retryable": retryable,
                "required_action": (
                    f"retry Explore visual sync for the {role} marker readback"
                    if retryable
                    else None
                ),
            }
        )
