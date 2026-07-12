from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REWARD_EVENT_SCHEMA_VERSION = "user_reward_event_v0"
REWARD_SOURCE_SCHEMA_VERSION = "user_reward_source_v0"
REWARD_SOURCE_KINDS = {"direct", "github", "lark", "operator", "other"}


def compact_reward_source(kind: str | None, raw_ref: str | None) -> dict[str, str] | None:
    source_kind = str(kind or "").strip().lower()
    source_ref = str(raw_ref or "").strip()
    if not source_kind and not source_ref:
        return None
    if source_kind not in REWARD_SOURCE_KINDS:
        raise ValueError(
            "reward source kind must be one of: "
            + ", ".join(sorted(REWARD_SOURCE_KINDS))
        )
    if not source_ref:
        raise ValueError("reward source ref is required when source kind is set")
    if len(source_ref) > 500:
        raise ValueError("reward source ref must stay within 500 characters")
    return {
        "schema_version": REWARD_SOURCE_SCHEMA_VERSION,
        "kind": source_kind,
        "digest": "sha256:"
        + hashlib.sha256(f"{source_kind}:{source_ref}".encode("utf-8")).hexdigest(),
    }


def reward_event_id(goal_id: str, reward: Mapping[str, Any]) -> str:
    source = reward.get("source") if isinstance(reward.get("source"), Mapping) else {}
    stable_source = str(source.get("digest") or "")
    identity = stable_source or json.dumps(
        {
            key: reward.get(key)
            for key in (
                "recorded_at",
                "decision",
                "reward",
                "reason_summary",
                "follow_up",
                "lesson",
            )
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(f"{goal_id}\n{identity}".encode("utf-8")).hexdigest()[:16]
    return f"reward_{digest}"


def load_reward_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("schema_version") != REWARD_EVENT_SCHEMA_VERSION:
                continue
            reward_id = str(item.get("reward_id") or "").strip()
            if reward_id:
                events.setdefault(reward_id, item)
    return sorted(
        events.values(),
        key=lambda item: (str(item.get("recorded_at") or ""), str(item.get("reward_id") or "")),
        reverse=True,
    )


def append_reward_event(
    path: Path,
    *,
    goal_id: str,
    run_generated_at: str,
    reward: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    payload = dict(reward)
    reward_id = str(payload.get("reward_id") or reward_event_id(goal_id, payload))
    payload["reward_id"] = reward_id
    existing = next(
        (item for item in load_reward_events(path) if item.get("reward_id") == reward_id),
        None,
    )
    if existing is not None:
        return {
            "path": str(path),
            "reward_id": reward_id,
            "record": existing,
            "appended": False,
            "already_exists": True,
            "dry_run": dry_run,
        }
    record = {
        "schema_version": REWARD_EVENT_SCHEMA_VERSION,
        "reward_id": reward_id,
        "goal_id": goal_id,
        "run_generated_at": run_generated_at,
        "recorded_at": payload.get("recorded_at"),
        "human_reward": payload,
    }
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {
        "path": str(path),
        "reward_id": reward_id,
        "record": record,
        "appended": not dry_run,
        "already_exists": False,
        "dry_run": dry_run,
    }


def active_reward_lessons(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded: set[str] = set()
    active: list[dict[str, Any]] = []
    for event in events:
        reward_id = str(event.get("reward_id") or "")
        reward = event.get("human_reward") if isinstance(event.get("human_reward"), dict) else {}
        lesson = reward.get("lesson") if isinstance(reward.get("lesson"), dict) else {}
        if not reward_id or not lesson or reward_id in superseded:
            continue
        active.append(
            {
                "reward_id": reward_id,
                "recorded_at": event.get("recorded_at"),
                "decision": reward.get("decision"),
                "reward": reward.get("reward"),
                "kind": lesson.get("kind"),
                "summary": lesson.get("summary"),
                "strength": lesson.get("strength") or "advisory",
                "scope": lesson.get("scope") or "goal",
                "scope_key": lesson.get("scope_key"),
                "avoid": lesson.get("avoid") if isinstance(lesson.get("avoid"), list) else [],
                "prefer": lesson.get("prefer") if isinstance(lesson.get("prefer"), list) else [],
            }
        )
        superseded.update(
            str(value)
            for value in (lesson.get("supersedes") or [])
            if str(value).startswith("reward_")
        )
    return active
