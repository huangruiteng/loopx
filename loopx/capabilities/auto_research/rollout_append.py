from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Mapping

from .evidence_packet import (
    AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
    build_auto_research_rollout_events,
    load_auto_research_evidence_packet,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...rollout_event_log import (
    append_rollout_event,
    load_rollout_events,
    rollout_event_log_path,
)


def _event_content_key(event: Mapping[str, object]) -> str:
    """Identify the durable research content, not this append observation."""

    content = {
        key: value
        for key, value in event.items()
        if key not in {"event_id", "recorded_at"}
    }
    return json.dumps(content, sort_keys=True, ensure_ascii=True)


def append_auto_research_rollout_events(
    *,
    packet_path: str,
    registry_path: Path,
    runtime_root_arg: str | None,
    dry_run: bool,
) -> dict[str, object]:
    packet = load_auto_research_evidence_packet(packet_path)
    goal_id = packet["research_contract"]["goal_id"]
    events = build_auto_research_rollout_events(packet)
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    log_path = rollout_event_log_path(runtime_root, goal_id)
    existing_events = load_rollout_events(log_path)
    existing_ids = {
        str(event.get("event_id")) for event in existing_events if event.get("event_id")
    }
    existing_content_ids = {
        _event_content_key(event): str(event["event_id"])
        for event in existing_events
        if event.get("event_id")
    }
    appended_ids: list[str] = []
    skipped_ids: list[str] = []
    effective_ids: list[str] = []
    for event in events:
        event_id = str(event["event_id"])
        content_key = _event_content_key(event)
        existing_content_id = existing_content_ids.get(content_key)
        if existing_content_id:
            skipped_ids.append(existing_content_id)
            effective_ids.append(existing_content_id)
            continue
        if event_id in existing_ids:
            skipped_ids.append(event_id)
            effective_ids.append(event_id)
            continue
        if not dry_run:
            append_rollout_event(log_path, event)
            existing_ids.add(event_id)
            existing_content_ids[content_key] = event_id
        appended_ids.append(event_id)
        effective_ids.append(event_id)
    counts_by_kind = Counter(str(event.get("event_kind") or "") for event in events)
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
        "goal_id": goal_id,
        "dry_run": dry_run,
        "event_count": len(events),
        "appended_count": 0 if dry_run else len(appended_ids),
        "would_append_count": len(appended_ids),
        "skipped_existing_count": len(skipped_ids),
        "event_ids": effective_ids,
        "appended_event_ids": [] if dry_run else appended_ids,
        "skipped_existing_event_ids": skipped_ids,
        "counts_by_kind": dict(sorted(counts_by_kind.items())),
        "packet_summary": packet["summary"],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "source": "loopx_rollout_event_log",
        },
    }
