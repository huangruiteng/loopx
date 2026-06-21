from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROLLOUT_EVENT_SCHEMA_VERSION = "loopx_rollout_event_v0"
ROLLOUT_EVENT_SUMMARY_SCHEMA_VERSION = "loopx_rollout_event_summary_v0"
DEFAULT_ROLLOUT_EVENT_LOG_NAME = "rollout-event-log.jsonl"

ROLLOUT_EVENT_KINDS = {
    "benchmark_launch",
    "benchmark_status",
    "codex_session_observed",
    "compact_blocker",
    "compact_case_result",
    "failure_attribution",
    "pr_merge",
    "quota_monitor_poll",
    "quota_should_run",
    "quota_spend",
    "quota_void",
    "refresh_state",
    "todo_add",
    "todo_archive_completed",
    "todo_claim",
    "todo_complete",
    "todo_supersede",
    "todo_update",
    "validation",
}

PRIVATE_SOURCE_KINDS = {
    "benchmark_run_dir",
    "codex_sessions_jsonl",
    "local_runtime_state",
    "private_runner_artifact",
    "unknown_private_source",
}

FORBIDDEN_TEXT_MARKERS = (
    "/" + "Users/",
    "/" + "root/",
    "/" + "home/",
    "/" + "private/",
    ".local/" + "private",
    "Auth" + "orization:",
    "api" + "_key",
    "api" + "key",
    "pass" + "word",
    "sec" + "ret=",
    "tok" + "en=",
    "loopx-" + "ecs",
    "115." + "190.",
)

RAW_KEY_HINTS = (
    "credential",
    "local_path",
    "log",
    "path",
    "raw",
    "secret",
    "stderr",
    "stdout",
    "task_text",
    "token",
    "trace",
    "trajectory",
    "transcript",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _compact_text(value: Any, *, limit: int = 500, field: str = "value") -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    lowered = text.lower()
    for marker in FORBIDDEN_TEXT_MARKERS:
        if marker.lower() in lowered:
            raise ValueError(f"{field} contains private or credential-like material")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _safe_key(key: str, *, field: str) -> str:
    text = str(key).strip()
    if not text:
        raise ValueError(f"{field} key is empty")
    lowered = text.lower()
    if any(hint in lowered for hint in RAW_KEY_HINTS):
        raise ValueError(f"{field} key {text!r} looks like raw/private material")
    return text


def _safe_scalar(value: Any, *, field: str) -> bool | int | float | str | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    return _compact_text(value, limit=240, field=field)


def _safe_public_ref(value: Any, *, field: str) -> str | None:
    text = _compact_text(value, limit=240, field=field)
    if text is None:
        return None
    path = Path(text)
    if text.startswith(("~", "/", "\\")) or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a public relative ref or opaque id")
    return text


def _safe_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (details or {}).items():
        safe_key = _safe_key(str(key), field="details")
        safe[safe_key] = _safe_scalar(value, field=f"details.{safe_key}")
    return safe


def _safe_source_refs(
    source_refs: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    safe_refs: list[dict[str, Any]] = []
    for index, ref in enumerate(source_refs or []):
        item: dict[str, Any] = {}
        for key, value in ref.items():
            safe_key = _safe_key(str(key), field=f"source_refs[{index}]")
            item[safe_key] = _safe_scalar(
                value, field=f"source_refs[{index}].{safe_key}"
            )
        if item:
            safe_refs.append(item)
    return safe_refs


def _normalized_event_kind(event_kind: str) -> str:
    text = str(event_kind).strip().lower().replace("-", "_")
    if text not in ROLLOUT_EVENT_KINDS:
        choices = ", ".join(sorted(ROLLOUT_EVENT_KINDS))
        raise ValueError(f"unsupported rollout event kind {event_kind!r}; choose {choices}")
    return text


def _event_id(payload: Mapping[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in {"event_id", "recorded_at"}
    }
    encoded = json.dumps(stable, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def rollout_event_log_path(runtime_root: Path, goal_id: str) -> Path:
    return (
        runtime_root.expanduser()
        / "goals"
        / str(goal_id)
        / DEFAULT_ROLLOUT_EVENT_LOG_NAME
    )


def build_rollout_event(
    *,
    goal_id: str,
    event_kind: str,
    agent_id: str | None = None,
    todo_id: str | None = None,
    benchmark_id: str | None = None,
    case_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    classification: str | None = None,
    delivery_outcome: str | None = None,
    labels: Sequence[str] | None = None,
    summary: str | None = None,
    artifact_refs: Sequence[str] | None = None,
    source_refs: Sequence[Mapping[str, Any]] | None = None,
    details: Mapping[str, Any] | None = None,
    private_source_kind: str | None = None,
    private_source_count: int | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build a public-safe append-only LoopX rollout event.

    The event records lifecycle metadata only. It intentionally keeps raw Codex
    sessions, benchmark logs, task text, trajectories, credentials, and absolute
    local paths out of the payload.
    """

    if not str(goal_id).strip():
        raise ValueError("goal_id is required")
    private_kind = (
        str(private_source_kind).strip()
        if private_source_kind
        else None
    )
    if private_kind and private_kind not in PRIVATE_SOURCE_KINDS:
        choices = ", ".join(sorted(PRIVATE_SOURCE_KINDS))
        raise ValueError(f"unsupported private source kind {private_kind!r}; choose {choices}")
    safe_artifact_refs = [
        ref
        for ref in (
            _safe_public_ref(value, field="artifact_refs") for value in artifact_refs or []
        )
        if ref
    ]
    safe_labels = [
        text
        for text in (_compact_text(value, limit=80, field="labels") for value in labels or [])
        if text
    ]
    payload: dict[str, Any] = {
        "schema_version": ROLLOUT_EVENT_SCHEMA_VERSION,
        "goal_id": str(goal_id).strip(),
        "event_kind": _normalized_event_kind(event_kind),
        "recorded_at": recorded_at or _now_iso(),
        "boundary": {
            "raw_task_text_recorded": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "raw_session_transcript_recorded": False,
            "credential_values_recorded": False,
            "absolute_paths_recorded": False,
        },
    }
    optional_scalars = {
        "agent_id": agent_id,
        "todo_id": todo_id,
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "run_id": run_id,
        "status": status,
        "classification": classification,
        "delivery_outcome": delivery_outcome,
        "summary": summary,
    }
    for key, value in optional_scalars.items():
        safe = _compact_text(value, limit=500 if key == "summary" else 180, field=key)
        if safe:
            payload[key] = safe
    if safe_labels:
        payload["labels"] = safe_labels
    if safe_artifact_refs:
        payload["artifact_refs"] = safe_artifact_refs
    safe_source_refs = _safe_source_refs(source_refs)
    if safe_source_refs:
        payload["source_refs"] = safe_source_refs
    safe_details = _safe_details(details)
    if safe_details:
        payload["details"] = safe_details
    if private_kind:
        payload["private_source"] = {
            "kind": private_kind,
            "raw_values_recorded": False,
        }
        if private_source_count is not None:
            if private_source_count < 0:
                raise ValueError("private_source_count must be non-negative")
            payload["private_source"]["count"] = int(private_source_count)
    payload["event_id"] = _event_id(payload)
    return payload


def append_rollout_event(log_path: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(event)
    if payload.get("schema_version") != ROLLOUT_EVENT_SCHEMA_VERSION:
        raise ValueError("unsupported rollout event schema")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
    return payload


def load_rollout_events(log_path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if limit is not None:
        lines = lines[-max(0, limit) :]
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("schema_version") == ROLLOUT_EVENT_SCHEMA_VERSION:
            events.append(parsed)
    return events


def _safe_event_view(event: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "event_id",
        "recorded_at",
        "event_kind",
        "status",
        "agent_id",
        "todo_id",
        "benchmark_id",
        "case_id",
        "run_id",
        "classification",
        "delivery_outcome",
        "summary",
    )
    return {key: event[key] for key in keys if key in event}


def summarize_rollout_events(
    events: Iterable[Mapping[str, Any]], *, limit: int = 12
) -> dict[str, Any]:
    event_list = [dict(event) for event in events]
    counts_by_kind = Counter(str(event.get("event_kind") or "") for event in event_list)
    counts_by_status = Counter(str(event.get("status") or "") for event in event_list if event.get("status"))
    latest = event_list[-1] if event_list else None
    return {
        "schema_version": ROLLOUT_EVENT_SUMMARY_SCHEMA_VERSION,
        "event_count": len(event_list),
        "counts_by_kind": dict(sorted(counts_by_kind.items())),
        "counts_by_status": dict(sorted(counts_by_status.items())),
        "latest_event": _safe_event_view(latest) if latest else None,
        "recent_events": [_safe_event_view(event) for event in event_list[-max(0, limit) :]],
        "boundary": {
            "raw_task_text_recorded": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "raw_session_transcript_recorded": False,
            "credential_values_recorded": False,
            "absolute_paths_recorded": False,
        },
    }
