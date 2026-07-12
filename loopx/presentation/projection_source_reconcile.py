from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA_VERSION = "projection_source_reconcile_plan_v0"


def validate_projection_source_reconcile_request(
    *,
    requested: bool,
    source_snapshot_complete: bool,
    agent_id: str | None,
    include_done: bool,
    namespace_warnings: Sequence[str],
    selected_row_count: int,
    complete_row_count: int,
    complete_warnings: Sequence[str],
) -> None:
    if not requested:
        return
    if not source_snapshot_complete:
        raise ValueError(
            "source reconcile requires an explicit complete source snapshot"
        )
    if agent_id:
        raise ValueError("source reconcile refuses an agent-filtered projection")
    if not include_done:
        raise ValueError("source reconcile requires include_done=true")
    warnings = [*namespace_warnings, *complete_warnings]
    if warnings:
        raise ValueError(str(warnings[0]))
    if selected_row_count != complete_row_count:
        raise ValueError(
            "source reconcile row limit truncates the complete source snapshot"
        )


def projection_source_key_prefix(*, goal_id: str, source_id: str) -> str:
    resolved_goal = str(goal_id or "").strip()
    resolved_source = str(source_id or "").strip()
    if not resolved_goal:
        raise ValueError("projection source reconcile requires goal_id")
    if not resolved_source:
        raise ValueError("projection source reconcile requires source_id")
    return f"{resolved_goal}:projection:{resolved_source}:"


def plan_projection_source_reconcile(
    *,
    goal_id: str,
    source_id: str,
    desired_keys: Sequence[str],
    local_record_map: Mapping[str, str],
    remote_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Plan exact orphan cleanup inside one complete projection namespace."""

    prefix = projection_source_key_prefix(goal_id=goal_id, source_id=source_id)
    desired = {str(key).strip() for key in desired_keys if str(key).strip()}
    outside = sorted(key for key in desired if not key.startswith(prefix))
    if outside:
        raise ValueError(
            "desired projection keys must stay inside the reconciled source namespace"
        )

    local_source_keys = {
        str(key).strip()
        for key in local_record_map
        if str(key).strip().startswith(prefix)
    }
    remote_source_records: list[dict[str, str]] = []
    for item in remote_records:
        key = str(item.get("key") or "").strip()
        record_id = str(item.get("record_id") or "").strip()
        if key.startswith(prefix) and record_id:
            remote_source_records.append({"key": key, "record_id": record_id})

    remote_orphans = sorted(
        (item for item in remote_source_records if item["key"] not in desired),
        key=lambda item: (item["key"], item["record_id"]),
    )
    local_mapping_keys_to_remove = sorted(local_source_keys - desired)
    return {
        "schema_version": SCHEMA_VERSION,
        "goal_id": str(goal_id).strip(),
        "source_id": str(source_id).strip(),
        "namespace_prefix": prefix,
        "desired_key_count": len(desired),
        "remote_source_record_count": len(remote_source_records),
        "local_source_mapping_count": len(local_source_keys),
        "remote_orphans": remote_orphans,
        "remote_orphan_record_ids": [item["record_id"] for item in remote_orphans],
        "local_mapping_keys_to_remove": local_mapping_keys_to_remove,
        "remote_delete_count": len(remote_orphans),
        "local_mapping_delete_count": len(local_mapping_keys_to_remove),
    }
