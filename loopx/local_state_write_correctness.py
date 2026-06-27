from __future__ import annotations

import hashlib
import json
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
            "narrower_lock_allowed": "not_for_refresh_state",
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
            "lease_projection": None,
            "public_boundary": {
                "raw_logs_copied": False,
                "private_paths_copied": False,
                "credentials_copied": False,
                "production_action_authorized": False,
            },
        },
    }
