from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEDULER_STATE_SCHEMA_VERSION = "loopx_scheduler_state_v0"
CODEX_APP_STATEFUL_BACKOFF_STATE_KEY = "scheduler_hint.codex_app.stateful_backoff"
CODEX_APP_SURFACE = "codex_app"


def rrule_for_minutes(minutes: int) -> str:
    return f"FREQ=MINUTELY;INTERVAL={max(1, int(minutes))}"


def _safe_segment(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", str(value or "").strip()).strip("-._")
    return safe or "default"


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
    if parsed.get("schema_version") != SCHEDULER_STATE_SCHEMA_VERSION:
        return None
    return parsed


def write_scheduler_state(
    runtime_root: Path,
    state: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
) -> Path:
    path = scheduler_state_path(
        runtime_root,
        goal_id=goal_id,
        agent_id=agent_id,
        surface=surface,
        state_key=state_key,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path
