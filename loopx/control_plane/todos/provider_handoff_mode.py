"""Transport and readback for the canonical mode owner; no local authority fallback."""
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..coordination.local_authority import (
    LOCAL_AUTHORITY_SOURCES, LocalCoordinationAuthorityRejection,
    LocalCoordinationAuthorityUnavailable,
    local_authority_is_promoted, read_canonical_todos_if_promoted,
)
from ..effect_runtime import effect_runtime_result
from ..runtime.time import now_local_iso


def read_canonical_handoff_mode(*, runtime_root: Path, goal_id: str) -> dict[str, Any] | None:
    source = read_canonical_todos_if_promoted(runtime_root=runtime_root, goal_id=goal_id, include_leases=True)
    if source is None:
        return None
    return {key: source[key] for key in ("handoff_mode", "source_authority", "provider_revision",
                                        "decision_read_from_provider", "legacy_fallback_used")}


def set_canonical_handoff_mode(*, runtime_root: Path, goal_id: str, mode: str,
                               operation_id: str | None, dry_run: bool) -> dict[str, Any] | None:
    if not local_authority_is_promoted(runtime_root=runtime_root, goal_id=goal_id):
        return None
    result = effect_runtime_result("coordination.local_authority.handoff_mode_set", {
        "schema_version": "loopx_coordination_handoff_mode_set_request_v0",
        "runtime_root": str(runtime_root.expanduser().resolve()), "goal_id": goal_id,
        "operation_id": (operation_id if operation_id is not None else f"handoff-mode:{goal_id}:{uuid4().hex}"),
        "requested_mode": mode, "observed_at": now_local_iso(), "dry_run": dry_run,
    })
    if (not isinstance(result, dict) or result.get("status") not in {"applied", "replayed", "recovered", "planned"}
        or result.get("source_authority") not in LOCAL_AUTHORITY_SOURCES
        or result.get("decision_read_from_provider") is not True or result.get("legacy_fallback_used") is not False):
        payload = result if isinstance(result, dict) else {}
        if payload.get("status") == "failed" and payload.get("failure_kind") == "decision_rejection":
            raise LocalCoordinationAuthorityRejection(
                str(payload.get("reason") or "canonical handoff mode request was rejected"),
                code=str(payload.get("reason_code") or "handoff_mode_rejected"),
                payload=payload,
            )
        raise LocalCoordinationAuthorityUnavailable(str(payload.get("reason") or "canonical mode unavailable"),
            code=str(payload.get("reason_code") or "handoff_mode_unavailable"), payload=payload)
    return {**result, "ok": True, "schema_version": "goal_handoff_mode_v0", "action": "set",
            "source": "canonical_provider", "dry_run": dry_run}
