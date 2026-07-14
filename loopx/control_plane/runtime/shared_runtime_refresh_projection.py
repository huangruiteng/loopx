from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from ...file_lock import exclusive_file_lock
from ...history import load_index, load_registry, reserve_unique_run_paths
from ...paths import DEFAULT_RUNTIME_ROOT, global_registry_path
from ...registry import registry_goals
from ..goals.goal_vision import compact_goal_vision_packet
from .time import now_local_iso


SHARED_RUNTIME_PROJECTION_SCHEMA_VERSION = "shared_runtime_refresh_projection_v0"
ISO_LIKE_TIMESTAMP_RE = re.compile(r"[0-9TZ:+.\-]{10,64}")


def registered_shared_runtime_root(
    *,
    registry_path: Path,
    goal_id: str,
    source_runtime_root: Path,
) -> Path | None:
    """Find the shared runtime that registered this exact source registry route."""

    candidate_roots: list[Path] = []
    configured_root = str(os.environ.get("LOOPX_RUNTIME_ROOT") or "").strip()
    if configured_root:
        candidate_roots.append(Path(configured_root).expanduser())
    candidate_roots.append(DEFAULT_RUNTIME_ROOT)

    source_path = registry_path.expanduser().resolve()
    seen: set[Path] = set()
    for candidate_root in candidate_roots:
        resolved_root = candidate_root.resolve()
        if resolved_root in seen or resolved_root == source_runtime_root.resolve():
            continue
        seen.add(resolved_root)
        candidate_registry = global_registry_path(resolved_root)
        if not candidate_registry.exists() or candidate_registry.resolve() == source_path:
            continue
        shared_registry = load_registry(candidate_registry)
        for goal in registry_goals(shared_registry):
            if str(goal.get("id") or "") != goal_id:
                continue
            registered_source = str(goal.get("source_registry") or "").strip()
            if not registered_source:
                continue
            registered_path = Path(registered_source).expanduser()
            if not registered_path.is_absolute():
                registered_path = candidate_registry.parent / registered_path
            if registered_path.resolve() == source_path:
                return resolved_root
    return None


def build_shared_runtime_projection(
    *,
    record: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the compact allowlisted record consumed by shared status/quota."""

    state = record.get("state") if isinstance(record.get("state"), dict) else {}
    frontmatter = (
        state.get("frontmatter") if isinstance(state.get("frontmatter"), dict) else {}
    )
    updated_at = str(frontmatter.get("updated_at") or "").strip()
    if not ISO_LIKE_TIMESTAMP_RE.fullmatch(updated_at):
        updated_at = ""
    marker = {
        "schema_version": SHARED_RUNTIME_PROJECTION_SCHEMA_VERSION,
        "source": "refresh_state",
        "source_generated_at": record.get("generated_at"),
        "raw_artifacts_copied": False,
        "recommended_action_copied": False,
    }
    projection: dict[str, Any] = {
        "generated_at": record.get("generated_at"),
        "goal_id": record.get("goal_id"),
        "classification": record.get("classification"),
        "health_check": "project-local refresh projected to registered shared runtime",
        "state": {
            "sha256_16": state.get("sha256_16"),
            "frontmatter": {"updated_at": updated_at or None},
        },
        "shared_runtime_projection": marker,
    }
    compact_vision = compact_goal_vision_packet(record.get("agent_vision"))
    if compact_vision:
        projection["agent_vision"] = compact_vision
    for field in (
        "delivery_batch_scale",
        "delivery_outcome",
        "progress_scope",
        "agent_id",
        "agent_lane",
        "vision_checkpoint",
    ):
        if field in record:
            projection[field] = record[field]

    ack = (
        record.get("autonomous_replan_ack")
        if isinstance(record.get("autonomous_replan_ack"), dict)
        else {}
    )
    if ack:
        compact_ack = {
            field: ack[field]
            for field in ("schema_version", "recorded", "source", "requested")
            if field in ack
        }
        delta = ack.get("delta_contract") if isinstance(ack.get("delta_contract"), dict) else {}
        if delta:
            compact_ack["delta_contract"] = {
                field: delta[field]
                for field in (
                    "schema_version",
                    "required",
                    "delta_present",
                    "delta_kinds",
                    "accepted_without_delta",
                )
                if field in delta
            }
        projection["autonomous_replan_ack"] = compact_ack

    marker["source_projection_sha256_16"] = hashlib.sha256(
        json.dumps(projection, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    projected_index = {
        key: projection[key]
        for key in (
            "generated_at",
            "goal_id",
            "classification",
            "health_check",
            "state",
            "delivery_batch_scale",
            "delivery_outcome",
            "progress_scope",
            "agent_id",
            "agent_lane",
            "autonomous_replan_ack",
            "agent_vision",
            "vision_checkpoint",
            "shared_runtime_projection",
        )
        if key in projection
    }
    return projection, projected_index


def _render_projection_markdown(record: dict[str, Any]) -> str:
    marker = record.get("shared_runtime_projection") or {}
    return "\n".join(
        [
            "# LoopX Shared Runtime Refresh Projection",
            "",
            f"- goal_id: `{record.get('goal_id')}`",
            f"- classification: `{record.get('classification')}`",
            f"- generated_at: `{record.get('generated_at')}`",
            f"- agent_id: `{record.get('agent_id')}`",
            f"- raw_artifacts_copied: `{marker.get('raw_artifacts_copied')}`",
            f"- recommended_action_copied: `{marker.get('recommended_action_copied')}`",
        ]
    )


def write_shared_runtime_projection(
    *,
    shared_runtime_root: Path,
    goal_id: str,
    record: dict[str, Any],
    index_record: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    marker = record["shared_runtime_projection"]
    result: dict[str, Any] = {
        "ok": True,
        "status": "would_project" if dry_run else "projected",
        "dry_run": dry_run,
        "shared_runtime_root": str(shared_runtime_root),
        "raw_artifacts_copied": False,
        "recommended_action_copied": False,
        "source_generated_at": marker.get("source_generated_at"),
    }
    if dry_run:
        return result

    runs_dir = shared_runtime_root / "goals" / goal_id / "runs"
    index_path = runs_dir / "index.jsonl"
    with exclusive_file_lock(index_path):
        existing, _ = load_index(index_path)
        if any(
            isinstance(item.get("shared_runtime_projection"), dict)
            and item["shared_runtime_projection"].get("source_generated_at")
            == marker.get("source_generated_at")
            and item["shared_runtime_projection"].get("source_projection_sha256_16")
            == marker.get("source_projection_sha256_16")
            for item in existing
        ):
            result["status"] = "already_current"
            result["index_path"] = str(index_path)
            return result
        json_path, markdown_path = reserve_unique_run_paths(
            runs_dir, str(record.get("generated_at") or now_local_iso())
        )
        index_record["json_path"] = str(json_path)
        index_record["markdown_path"] = str(markdown_path)
        json_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(
            _render_projection_markdown(record) + "\n",
            encoding="utf-8",
        )
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    result.update(
        {
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "index_path": str(index_path),
        }
    )
    return result
