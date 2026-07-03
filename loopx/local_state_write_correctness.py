from __future__ import annotations

import hashlib
import json
import re
from typing import Any


LOCAL_STATE_WRITE_CORRECTNESS_SCHEMA_VERSION = "local_state_write_correctness_v0"


def active_state_revision(state_text: str) -> dict[str, str]:
    return {
        "kind": "active_state_revision",
        "value": "sha256:" + hashlib.sha256(state_text.encode("utf-8")).hexdigest(),
    }


def stable_write_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_local_state_write_correctness_dry_run_packet(
    *,
    goal_id: str,
    writer_id: str,
    write_class: str,
    state_text: str,
    target_refs: dict[str, Any],
    patch_summary: str,
    expected_write_scopes: list[str],
    lease_ref: dict[str, Any] | None = None,
    lease_projection: dict[str, Any] | None = None,
    narrower_lock_allowed: str | None = None,
    projection_status_surface: str | None = None,
) -> dict[str, Any]:
    """Build the dry-run correctness envelope for a local state writer.

    The packet uses logical refs rather than local absolute paths so it can be
    safely projected by status/review surfaces. Callers remain responsible for
    the actual lock, write, and rollout-event behavior.
    """

    intent_seed = {
        "goal_id": goal_id,
        "writer_id": writer_id,
        "write_class": write_class,
        "target_refs": target_refs,
        "patch_summary": patch_summary,
        "expected_write_scopes": expected_write_scopes,
        "lease_ref": lease_ref,
    }
    digest = stable_write_digest(intent_seed)
    write_id = f"write_{write_class}_{digest[:16]}"
    return {
        "schema_version": LOCAL_STATE_WRITE_CORRECTNESS_SCHEMA_VERSION,
        "write_intent": {
            "write_id": write_id,
            "goal_id": goal_id,
            "writer_id": writer_id,
            "write_class": write_class,
            "target_refs": target_refs,
            "idempotency_key": f"{goal_id}:{write_class}:{digest}",
            "expected_revision": active_state_revision(state_text),
            "lease_ref": lease_ref,
        },
        "lock_boundary": {
            "kind": "per_goal",
            "lock_key": f"goal:{goal_id}",
            "narrower_lock_allowed": narrower_lock_allowed or "not_for_refresh_state",
        },
        "preview": {
            "mode": "dry_run",
            "patch_summary": patch_summary,
            "non_destructive": True,
            "expected_write_scopes": expected_write_scopes,
        },
        "apply_result": {
            "status": "preview_only",
            "applied_revision": None,
            "duplicate_of": None,
            "conflict": None,
        },
        "projection": {
            "status_surface": projection_status_surface or patch_summary,
            "lease_projection": lease_projection,
            "public_boundary": {
                "raw_logs_copied": False,
                "private_paths_copied": False,
                "credentials_copied": False,
                "production_action_authorized": False,
            },
        },
    }


def shadow_validate_local_state_write_correctness_packet(
    packet: dict[str, Any],
    *,
    current_state_text: str,
    observed_lease_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview revision and lease conflicts without changing write behavior."""

    validated = json.loads(json.dumps(packet, ensure_ascii=False))
    intent = validated.get("write_intent") if isinstance(validated, dict) else {}
    if not isinstance(intent, dict):
        return validated
    apply_result = validated.setdefault("apply_result", {})
    if not isinstance(apply_result, dict):
        apply_result = {}
        validated["apply_result"] = apply_result
    apply_result.setdefault("status", "preview_only")
    apply_result.setdefault("applied_revision", None)
    apply_result.setdefault("duplicate_of", None)
    apply_result.setdefault("conflict", None)

    expected_revision = intent.get("expected_revision")
    current_revision = active_state_revision(current_state_text)
    if (
        isinstance(expected_revision, dict)
        and expected_revision.get("value")
        and expected_revision.get("value") != current_revision["value"]
    ):
        apply_result.update(
            {
                "status": "revision_conflict",
                "applied_revision": None,
                "duplicate_of": None,
                "conflict": {
                    "kind": "revision_conflict",
                    "expected_revision": expected_revision,
                    "current_revision": current_revision,
                },
            }
        )
        return validated

    expected_lease_ref = intent.get("lease_ref")
    if _lease_refs_conflict(expected_lease_ref, observed_lease_ref):
        apply_result.update(
            {
                "status": "lease_conflict",
                "applied_revision": None,
                "duplicate_of": None,
                "conflict": {
                    "kind": "lease_conflict",
                    "expected_lease_ref": expected_lease_ref,
                    "observed_lease_ref": observed_lease_ref,
                },
            }
        )
    return validated


def _lease_refs_conflict(expected: Any, observed: Any) -> bool:
    if not isinstance(expected, dict) or not isinstance(observed, dict):
        return False
    if str(expected.get("kind") or "") != str(observed.get("kind") or ""):
        return False
    if str(expected.get("goal_id") or "") != str(observed.get("goal_id") or ""):
        return False
    if str(expected.get("todo_id") or "") != str(observed.get("todo_id") or ""):
        return False
    expected_holder = str(expected.get("claimed_by") or "")
    observed_holder = str(observed.get("claimed_by") or "")
    return bool(expected_holder and observed_holder and expected_holder != observed_holder)


def _todo_lease_ref(
    *,
    goal_id: str,
    todo_id: str | None,
    claimed_by: str | None,
) -> dict[str, str] | None:
    if not todo_id or not claimed_by:
        return None
    safe_todo_id = re.sub(r"[^A-Za-z0-9_]+", "_", todo_id).strip("_") or "todo"
    safe_claimed_by = re.sub(r"[^A-Za-z0-9_]+", "_", claimed_by).strip("_") or "agent"
    return {
        "kind": "todo_claim",
        "goal_id": goal_id,
        "todo_id": todo_id,
        "claimed_by": claimed_by,
        "lease_id": f"lease_{safe_todo_id}_{safe_claimed_by}",
    }


def _todo_lease_projection(lease_ref: dict[str, str] | None) -> dict[str, str] | None:
    if not lease_ref:
        return None
    return {
        "todo_id": lease_ref["todo_id"],
        "claimed_by": lease_ref["claimed_by"],
        "lease_state": "preview_only",
    }


def build_todo_write_correctness_dry_run_packet(
    *,
    goal_id: str,
    write_class: str,
    state_text: str,
    todo_id: str | None,
    role: str | None,
    section: str | None,
    claimed_by: str | None,
    changed: bool,
) -> dict[str, Any]:
    target = todo_id or "new_todo"
    role_text = role or "unknown_role"
    effect = "would change active state" if changed else "would leave active state unchanged"
    patch_summary = f"preview {write_class} for {role_text} todo {target}: {effect}"
    lease_ref = _todo_lease_ref(
        goal_id=goal_id,
        todo_id=todo_id,
        claimed_by=claimed_by,
    )
    return build_local_state_write_correctness_dry_run_packet(
        goal_id=goal_id,
        writer_id="loopx.todo",
        write_class=write_class,
        state_text=state_text,
        target_refs={
            "state_file_ref": "registry.goal.state_file",
            "todo_id": todo_id,
            "role": role,
            "section": section,
        },
        patch_summary=patch_summary,
        expected_write_scopes=["active_state"],
        lease_ref=lease_ref,
        lease_projection=_todo_lease_projection(lease_ref),
        narrower_lock_allowed="per_todo_when_patch_is_single_todo_and_order_independent",
        projection_status_surface=patch_summary,
    )
