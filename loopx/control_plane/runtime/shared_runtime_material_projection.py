from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...global_registry import sync_project_registry_to_global
from .run_compaction import (
    compact_operator_gate,
    compact_operator_gate_resume_contract,
)
from .runtime_projection_route import (
    compact_runtime_projection_route,
    resolve_runtime_projection_route,
)
from .runtime_projection_writer import write_compact_runtime_projection


SHARED_RUNTIME_MATERIAL_PROJECTION_SCHEMA_VERSION = (
    "shared_runtime_material_projection_v0"
)
SHARED_RUNTIME_MATERIAL_PROJECTION_MARKER = "shared_runtime_material_projection"
MATERIAL_PROJECTION_KINDS = {
    "dreaming_decision",
    "operator_gate_decision",
    "read_only_project_map",
}


def prepare_material_projection_route(
    *,
    registry_path: Path,
    goal_id: str,
    source_runtime_root: Path,
    sync_global: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve and compact the route before the source event is appended."""

    route = resolve_runtime_projection_route(
        registry_path=registry_path,
        goal_id=goal_id,
        source_runtime_root=source_runtime_root,
    )
    compact = compact_runtime_projection_route(route)
    compact["projection_enabled"] = bool(sync_global)
    compact["projection_marker_field"] = SHARED_RUNTIME_MATERIAL_PROJECTION_MARKER
    return route, compact


def _compact_dreaming_decision(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {
        field: value[field]
        for field in (
            "schema_version",
            "proposal_id",
            "decision",
            "reason_summary",
            "promoted_to_delivery",
            "promoted_todo_id",
            "created_todo_id",
            "todo_added",
            "delivery_spend_allowed",
            "quota_spent",
        )
        if field in value
    }
    return compact or None


def _compact_source_dreaming_proposal(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {
        field: value[field]
        for field in (
            "generated_at",
            "classification",
            "proposal_id",
            "proposal_type",
            "evidence_window",
            "summary",
        )
        if field in value
    }
    return compact or None


def build_shared_runtime_material_projection(
    *,
    source_row: dict[str, Any],
    projection_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one compact, allowlisted shared-runtime event projection."""

    if projection_kind not in MATERIAL_PROJECTION_KINDS:
        raise ValueError(
            "projection_kind must be one of: "
            + ", ".join(sorted(MATERIAL_PROJECTION_KINDS))
        )

    route = (
        source_row.get("runtime_projection_route")
        if isinstance(source_row.get("runtime_projection_route"), dict)
        else {}
    )
    marker: dict[str, Any] = {
        "schema_version": SHARED_RUNTIME_MATERIAL_PROJECTION_SCHEMA_VERSION,
        "projection_kind": projection_kind,
        "source_generated_at": source_row.get("generated_at"),
        "raw_artifacts_copied": False,
        "recommended_action_copied": False,
    }
    if route.get("route_id"):
        marker["runtime_projection_route_id"] = route["route_id"]

    projection: dict[str, Any] = {
        field: source_row[field]
        for field in (
            "generated_at",
            "goal_id",
            "classification",
            "health_check",
            "delivery_batch_scale",
            "delivery_outcome",
        )
        if field in source_row
    }
    if projection_kind == "operator_gate_decision":
        operator_gate = compact_operator_gate(source_row.get("operator_gate"))
        if operator_gate:
            projection["operator_gate"] = operator_gate
        resume_contract = compact_operator_gate_resume_contract(
            source_row.get("operator_gate_resume_contract")
        )
        if resume_contract:
            resume_contract.pop("resulting_action", None)
            projection["operator_gate_resume_contract"] = resume_contract
    elif projection_kind == "read_only_project_map":
        project_map = source_row.get("project_map")
        if isinstance(project_map, dict):
            projection["project_map"] = dict(project_map)
    else:
        dreaming_decision = _compact_dreaming_decision(
            source_row.get("dreaming_decision")
        )
        if dreaming_decision:
            projection["dreaming_decision"] = dreaming_decision
        source_proposal = _compact_source_dreaming_proposal(
            source_row.get("source_dreaming_proposal")
        )
        if source_proposal:
            projection["source_dreaming_proposal"] = source_proposal

    projection[SHARED_RUNTIME_MATERIAL_PROJECTION_MARKER] = marker
    marker["source_projection_sha256_16"] = hashlib.sha256(
        json.dumps(projection, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    index_record = dict(projection)
    return projection, index_record


def _render_projection_markdown(record: dict[str, Any]) -> str:
    marker = record.get(SHARED_RUNTIME_MATERIAL_PROJECTION_MARKER) or {}
    return "\n".join(
        [
            "# LoopX Shared Runtime Material Projection",
            "",
            f"- goal_id: `{record.get('goal_id')}`",
            f"- classification: `{record.get('classification')}`",
            f"- generated_at: `{record.get('generated_at')}`",
            f"- projection_kind: `{marker.get('projection_kind')}`",
            f"- raw_artifacts_copied: `{marker.get('raw_artifacts_copied')}`",
            f"- recommended_action_copied: `{marker.get('recommended_action_copied')}`",
            f"- runtime_projection_route_id: `{marker.get('runtime_projection_route_id')}`",
        ]
    )


def write_shared_runtime_material_projection(
    *,
    shared_runtime_root: Path,
    goal_id: str,
    record: dict[str, Any],
    index_record: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    result = write_compact_runtime_projection(
        target_runtime_root=shared_runtime_root,
        goal_id=goal_id,
        record=record,
        index_record=index_record,
        marker_field=SHARED_RUNTIME_MATERIAL_PROJECTION_MARKER,
        identity_fields=(
            "source_generated_at",
            "source_projection_sha256_16",
        ),
        markdown_renderer=_render_projection_markdown,
        dry_run=dry_run,
    )
    marker = record[SHARED_RUNTIME_MATERIAL_PROJECTION_MARKER]
    result.update(
        {
            "shared_runtime_root": str(shared_runtime_root),
            "projection_kind": marker.get("projection_kind"),
            "raw_artifacts_copied": False,
            "recommended_action_copied": False,
            "source_generated_at": marker.get("source_generated_at"),
        }
    )
    return result


def finalize_material_projection(
    *,
    registry_path: Path,
    source_runtime_root: Path,
    goal_id: str,
    source_row: dict[str, Any],
    projection_kind: str,
    route: dict[str, Any],
    sync_global: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """Sync the registry and project a source-first material event."""

    disabled_sync = {
        "enabled": False,
        "global_registry": str(source_runtime_root / "registry.global.json"),
        "synced_goal_ids": [],
        "wrote": False,
    }
    projection_base = {
        "dry_run": dry_run,
        "projection_kind": projection_kind,
        "raw_artifacts_copied": False,
        "recommended_action_copied": False,
    }
    if not sync_global:
        return {
            "ok": True,
            "partial_write": False,
            "global_sync": disabled_sync,
            "shared_runtime_material_projection": {
                **projection_base,
                "ok": True,
                "status": "disabled",
            },
        }

    route_status = str(route.get("status") or "missing")
    if route_status in {"missing", "ambiguous"}:
        return {
            "ok": False,
            "partial_write": not dry_run,
            "global_sync": {
                "ok": False,
                "enabled": False,
                "wrote": False,
                "reason": f"runtime projection route is {route_status}",
                "route_status": route_status,
            },
            "shared_runtime_material_projection": {
                **projection_base,
                "ok": False,
                "status": f"route_{route_status}",
            },
        }

    target_text = str(route.get("target_runtime_root") or "").strip()
    target_runtime = Path(target_text) if target_text else source_runtime_root
    global_sync = sync_project_registry_to_global(
        registry_path=registry_path,
        runtime_root_override=str(target_runtime),
        goal_id=goal_id,
        dry_run=dry_run,
    )
    if route_status == "single_runtime":
        return {
            "ok": bool(global_sync.get("ok")),
            "partial_write": bool(not dry_run and not global_sync.get("ok")),
            "global_sync": global_sync,
            "shared_runtime_material_projection": {
                **projection_base,
                "ok": bool(global_sync.get("ok")),
                "status": (
                    "not_required" if global_sync.get("ok") else "blocked_by_global_sync"
                ),
            },
        }

    if not global_sync.get("ok"):
        return {
            "ok": False,
            "partial_write": not dry_run,
            "global_sync": global_sync,
            "shared_runtime_material_projection": {
                **projection_base,
                "ok": False,
                "status": "blocked_by_global_sync",
                "shared_runtime_root": str(target_runtime),
            },
        }

    record, index_record = build_shared_runtime_material_projection(
        source_row=source_row,
        projection_kind=projection_kind,
    )
    try:
        projection = write_shared_runtime_material_projection(
            shared_runtime_root=target_runtime,
            goal_id=goal_id,
            record=record,
            index_record=index_record,
            dry_run=dry_run,
        )
    except OSError as exc:
        projection = {
            **projection_base,
            "ok": False,
            "status": "write_failed",
            "shared_runtime_root": str(target_runtime),
            "error": str(exc),
        }
    return {
        "ok": bool(projection.get("ok")),
        "partial_write": bool(not dry_run and not projection.get("ok")),
        "global_sync": global_sync,
        "shared_runtime_material_projection": projection,
    }
