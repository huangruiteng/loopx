from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .time import parse_scheduler_timestamp


SCHEDULER_STATE_SCHEMA_VERSION = "loopx_scheduler_state_v0"
SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION = "scheduler_host_update_failure_v0"
SCHEDULER_HOST_UPDATE_FAILURE_CACHE_LIMIT = 4
SCHEDULER_HOST_UPDATE_FAILURE_TTL = timedelta(hours=24)
CODEX_APP_STATEFUL_BACKOFF_STATE_KEY = "scheduler_hint.codex_app.stateful_backoff"
CODEX_APP_SURFACE = "codex_app"


def rrule_for_minutes(minutes: int) -> str:
    return f"FREQ=MINUTELY;INTERVAL={max(1, int(minutes))}"


def normalize_scheduler_rrule(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if text.upper().startswith("RRULE:"):
        text = text[6:].strip()
    return text


def _safe_segment(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", str(value or "").strip()).strip("-._")
    return safe or "default"


def _positive_int_list(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    result: list[int] = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            return None
        if number <= 0:
            return None
        result.append(number)
    return result or None


def normalize_scheduler_host_update_failure(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if str(value.get("schema_version") or "") != SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION:
        return None
    target_rrule = normalize_scheduler_rrule(value.get("target_rrule"))
    observed_host_rrule = normalize_scheduler_rrule(value.get("observed_host_rrule"))
    failure_kind = str(value.get("failure_kind") or "").strip()
    failed_at = str(value.get("failed_at") or "").strip()
    try:
        failure_count = int(value.get("failure_count"))
    except (TypeError, ValueError):
        return None
    if not target_rrule or not failure_kind or not failed_at or failure_count < 1:
        return None
    return {
        "schema_version": SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
        "target_rrule": target_rrule,
        "observed_host_rrule": observed_host_rrule,
        "failure_kind": failure_kind,
        "failure_count": failure_count,
        "failed_at": failed_at,
    }


def _scheduler_host_update_failure_pair(value: dict[str, Any]) -> tuple[str, str]:
    return (
        normalize_scheduler_rrule(value.get("target_rrule")),
        normalize_scheduler_rrule(value.get("observed_host_rrule")),
    )


def normalize_scheduler_host_update_failures(
    value: Any,
    *,
    legacy_failure: Any = None,
) -> list[dict[str, Any]]:
    candidates = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    for candidate in [*candidates, legacy_failure]:
        failure = normalize_scheduler_host_update_failure(candidate)
        if failure is None:
            continue
        pair = _scheduler_host_update_failure_pair(failure)
        normalized = [
            item
            for item in normalized
            if _scheduler_host_update_failure_pair(item) != pair
        ]
        normalized.append(failure)
    return normalized[-SCHEDULER_HOST_UPDATE_FAILURE_CACHE_LIMIT:]


def retained_scheduler_host_update_failures(
    value: Any,
    *,
    reference_time: datetime | str | None = None,
    observed_host_rrule: Any = None,
) -> list[dict[str, Any]]:
    failures = normalize_scheduler_host_update_failures(value)
    if isinstance(reference_time, datetime):
        current_time = reference_time
    else:
        current_time = parse_scheduler_timestamp(reference_time)
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    elif current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    cutoff = current_time - SCHEDULER_HOST_UPDATE_FAILURE_TTL
    expected_host_rrule = normalize_scheduler_rrule(observed_host_rrule)
    retained: list[dict[str, Any]] = []
    for failure in failures:
        failed_at = parse_scheduler_timestamp(failure.get("failed_at"))
        if failed_at is None or failed_at < cutoff:
            continue
        if (
            expected_host_rrule
            and normalize_scheduler_rrule(failure.get("observed_host_rrule"))
            != expected_host_rrule
        ):
            continue
        retained.append(failure)
    return retained


def merge_scheduler_host_update_failure(
    value: Any,
    failure: dict[str, Any],
    *,
    reference_time: datetime | str | None = None,
) -> list[dict[str, Any]]:
    normalized_failure = normalize_scheduler_host_update_failure(failure)
    if normalized_failure is None:
        raise ValueError("scheduler host update failure is invalid")
    retained = retained_scheduler_host_update_failures(
        value,
        reference_time=reference_time,
        observed_host_rrule=normalized_failure.get("observed_host_rrule"),
    )
    return normalize_scheduler_host_update_failures([*retained, normalized_failure])


def normalize_scheduler_state(
    state: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    expected = {
        "schema_version": SCHEDULER_STATE_SCHEMA_VERSION,
        "goal_id": str(goal_id or "").strip(),
        "agent_id": str(agent_id or "").strip(),
        "surface": str(surface or CODEX_APP_SURFACE).strip() or CODEX_APP_SURFACE,
        "state_key": str(state_key or CODEX_APP_STATEFUL_BACKOFF_STATE_KEY).strip(),
    }
    for key, expected_value in expected.items():
        if str(state.get(key) or "").strip() != expected_value:
            return None
    reset_token = str(state.get("reset_token") or "").strip()
    identity_signature = str(state.get("identity_signature") or "").strip()
    last_applied_rrule = str(state.get("last_applied_rrule") or "").strip()
    host_update_failures = normalize_scheduler_host_update_failures(
        state.get("host_update_failures"),
        legacy_failure=state.get("host_update_failure"),
    )
    if not reset_token or not identity_signature:
        return None
    if not last_applied_rrule and not host_update_failures:
        return None
    try:
        progression_index = int(state.get("progression_index"))
    except (TypeError, ValueError):
        return None
    if progression_index < 0:
        return None
    progression_minutes = _positive_int_list(state.get("progression_minutes"))
    if progression_minutes is None:
        return None
    normalized = dict(state)
    normalized.update(expected)
    normalized["reset_token"] = reset_token
    normalized["identity_signature"] = identity_signature
    normalized["progression_index"] = progression_index
    normalized["progression_minutes"] = progression_minutes
    normalized["last_applied_rrule"] = last_applied_rrule
    if host_update_failures:
        normalized["host_update_failures"] = host_update_failures
        normalized["host_update_failure"] = host_update_failures[-1]
    else:
        normalized.pop("host_update_failures", None)
        normalized.pop("host_update_failure", None)
    return normalized


def build_scheduler_state(
    *,
    goal_id: Any,
    agent_id: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    reset_token: Any,
    identity_signature: Any,
    progression_index: int,
    progression_minutes: list[Any],
    last_applied_rrule: Any,
    updated_at: str,
    source: str | None = None,
    host_update_failure: dict[str, Any] | None = None,
    host_update_failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = {
        "schema_version": SCHEDULER_STATE_SCHEMA_VERSION,
        "goal_id": str(goal_id or "").strip(),
        "agent_id": str(agent_id or "").strip(),
        "surface": str(surface or CODEX_APP_SURFACE).strip() or CODEX_APP_SURFACE,
        "state_key": str(state_key or CODEX_APP_STATEFUL_BACKOFF_STATE_KEY).strip(),
        "reset_token": reset_token,
        "identity_signature": identity_signature,
        "progression_index": progression_index,
        "progression_minutes": progression_minutes,
        "last_applied_rrule": last_applied_rrule,
        "updated_at": str(updated_at or ""),
    }
    if host_update_failure is not None:
        state["host_update_failure"] = host_update_failure
    if host_update_failures is not None:
        state["host_update_failures"] = host_update_failures
    if source:
        state["source"] = str(source)
    normalized = normalize_scheduler_state(
        state,
        goal_id=state["goal_id"],
        agent_id=state["agent_id"],
        surface=state["surface"],
        state_key=state["state_key"],
    )
    if normalized is None:
        raise ValueError("scheduler state is missing required persisted-state fields")
    return normalized


def scheduler_state_path(
    runtime_root: Path,
    *,
    goal_id: str,
    agent_id: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
) -> Path:
    state_hash = hashlib.sha256(state_key.encode("utf-8")).hexdigest()[:16]
    return (
        runtime_root.expanduser()
        / "goals"
        / _safe_segment(goal_id)
        / "scheduler-state"
        / _safe_segment(agent_id)
        / _safe_segment(surface)
        / f"{state_hash}.json"
    )


def load_scheduler_state(
    runtime_root: Path,
    *,
    goal_id: str,
    agent_id: str | None,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
) -> dict[str, Any] | None:
    if not agent_id:
        return None
    path = scheduler_state_path(
        runtime_root,
        goal_id=goal_id,
        agent_id=agent_id,
        surface=surface,
        state_key=state_key,
    )
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return normalize_scheduler_state(
        parsed,
        goal_id=goal_id,
        agent_id=agent_id,
        surface=surface,
        state_key=state_key,
    )


def write_scheduler_state(
    runtime_root: Path,
    state: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
) -> Path:
    normalized = normalize_scheduler_state(
        state,
        goal_id=goal_id,
        agent_id=agent_id,
        surface=surface,
        state_key=state_key,
    )
    if normalized is None:
        raise ValueError("scheduler state does not match target scope or schema")
    path = scheduler_state_path(
        runtime_root,
        goal_id=goal_id,
        agent_id=agent_id,
        surface=surface,
        state_key=state_key,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path
