from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .delivery_batch_scale import DELIVERY_BATCH_SCALE_CHOICES, require_delivery_batch_scale
from .delivery_outcome import DELIVERY_OUTCOME_CHOICES, require_delivery_outcome
from .feedback import validate_public_safe_text
from .file_lock import exclusive_file_lock
from .global_registry import sync_project_registry_to_global
from .history import load_registry, reserve_unique_run_paths, unique_run_paths
from .paths import resolve_runtime_root
from .registry import registry_goals, resolve_state_file
from .runtime import validate_goal_id_path_segment
from .state_projection import state_projection_gap_warning
from .todo_contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_BLOCKER,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
)


DEFAULT_REFRESH_CLASSIFICATION = "state_refreshed"
DEFAULT_REFRESH_ACTION = "inspect refreshed active goal state and continue the next bounded progress segment"
AGENT_LANE_PROGRESS_SCOPE = "agent_lane"
RECOMMENDED_ACTION_SECTION_LINE_LIMIT = 16
BULLET_PREFIX_RE = re.compile(r"^(?:[-*]\s+|\d+[.)]\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[(?P<mark>[ xX])\]\s+")
ACTIVE_STATE_NEXT_ACTION_UPDATE_SCHEMA_VERSION = "active_state_next_action_update_v0"


def now_local() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def run_file_stem(generated_at: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]+", "-", generated_at).strip("-")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    values: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        values[key.strip()] = value
    return values


def extract_section_lines(text: str, heading: str, limit: int = 8) -> list[str]:
    lines = text.splitlines()
    in_section = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line[3:].strip() == heading
            continue
        if in_section and line.strip():
            collected.append(line.strip())
            if len(collected) >= limit:
                break
    return collected


def replace_updated_at(text: str, updated_at: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    frontmatter = parts[1]
    body = parts[2]
    if re.search(r"(?m)^updated_at:\s*.+$", frontmatter):
        frontmatter = re.sub(
            r"(?m)^updated_at:\s*.+$",
            f"updated_at: {updated_at}",
            frontmatter,
            count=1,
        )
    else:
        frontmatter = frontmatter.rstrip("\n") + f"\nupdated_at: {updated_at}\n"
    return "---" + frontmatter + "---" + body


def normalize_next_action_text(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        raise ValueError("next_action must not be empty")
    validate_public_safe_text("active_state_next_action", text)
    return text


def next_action_section_bounds(lines: list[str]) -> tuple[int, int] | None:
    for index, line in enumerate(lines):
        if line.strip() != "## Next Action":
            continue
        end = len(lines)
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("## "):
                end = next_index
                break
        return index, end
    return None


def next_action_insert_anchor(lines: list[str]) -> int:
    preferred = {
        "## Recent User Feedback",
        "## Progress Ledger",
        "## Operating Lessons",
        "## Completed Work Archive",
    }
    for index, line in enumerate(lines):
        if line.strip() in preferred:
            return index
    return len(lines)


def replace_next_action_section(
    state_text: str,
    *,
    next_action: str,
    updated_at: str,
) -> tuple[str, bool]:
    lines = state_text.splitlines()
    section = ["## Next Action", "", f"- {next_action}", ""]
    bounds = next_action_section_bounds(lines)
    if bounds:
        start, end = bounds
        updated_lines = [*lines[:start], *section, *lines[end:]]
    else:
        anchor = next_action_insert_anchor(lines)
        insert = list(section)
        if anchor > 0 and lines[anchor - 1].strip():
            insert.insert(0, "")
        updated_lines = [*lines[:anchor], *insert, *lines[anchor:]]
    section_text = "\n".join(updated_lines).rstrip() + "\n"
    if section_text.rstrip("\n") == state_text.rstrip("\n"):
        return state_text, False
    return replace_updated_at(section_text, updated_at), True


def clean_action_line(line: str) -> str:
    text = BULLET_PREFIX_RE.sub("", line.strip()).strip()
    return CHECKBOX_PREFIX_RE.sub("", text).strip()


def is_bullet_line(line: str) -> bool:
    return bool(BULLET_PREFIX_RE.match(line.strip()))


def first_action_item(lines: list[str], start: int) -> str:
    first_line = lines[start]
    parts = [clean_action_line(first_line)]
    if is_bullet_line(first_line):
        for line in lines[start + 1 :]:
            if is_bullet_line(line):
                break
            if line.strip().startswith("<!--"):
                continue
            cleaned = clean_action_line(line)
            if cleaned:
                parts.append(cleaned)
    return " ".join(part for part in parts if part).strip()


def checkbox_mark(line: str) -> str | None:
    text = BULLET_PREFIX_RE.sub("", line.strip()).strip()
    match = CHECKBOX_PREFIX_RE.match(text)
    if not match:
        return None
    return match.group("mark")


def todo_metadata(lines: list[str], start: int) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if is_bullet_line(line):
            break
        text = line.strip()
        if not text.startswith("<!-- loopx:todo"):
            continue
        for key, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([^ >]+)", text):
            metadata[key] = value
        break
    return metadata


def todo_priority_rank(action: str) -> int:
    match = re.match(r"^\[P(?P<rank>\d+)\]\s+", action.strip(), flags=re.IGNORECASE)
    if not match:
        return 99
    return int(match.group("rank"))


def first_open_agent_todo_action(state_text: str) -> str | None:
    lines = extract_section_lines(state_text, "Agent Todo", limit=512)
    advancement_candidates: list[tuple[int, int, str]] = []
    fallback_candidates: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        mark = checkbox_mark(line)
        if mark is None or mark.lower() == "x":
            continue
        action = first_action_item(lines, index)
        if not action:
            continue
        try:
            validate_public_safe_text("derived agent_todo recommended_action", action)
        except ValueError:
            continue
        metadata = todo_metadata(lines, index)
        if metadata.get("task_class") == TODO_TASK_CLASS_ADVANCEMENT:
            advancement_candidates.append((todo_priority_rank(action), index, action))
            continue
        if metadata.get("task_class") in {
            TODO_TASK_CLASS_MONITOR,
            TODO_TASK_CLASS_USER_GATE,
            TODO_TASK_CLASS_BLOCKER,
        }:
            continue
        fallback_candidates.append((todo_priority_rank(action), index, action))
    if advancement_candidates:
        return sorted(advancement_candidates)[0][2]
    if fallback_candidates:
        return sorted(fallback_candidates)[0][2]
    return None


def section_list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if is_bullet_line(line):
            item = first_action_item(lines, index)
            if item:
                items.append(item)
            index += 1
            while index < len(lines) and not is_bullet_line(lines[index]):
                index += 1
            continue
        cleaned = clean_action_line(line)
        if cleaned:
            items.append(cleaned)
        index += 1
    return items


def derive_recommended_action(state_text: str) -> str:
    agent_todo_action = first_open_agent_todo_action(state_text)
    if agent_todo_action:
        return agent_todo_action
    lines = extract_section_lines(state_text, "Next Action", limit=RECOMMENDED_ACTION_SECTION_LINE_LIMIT)
    for index, line in enumerate(lines):
        action = first_action_item(lines, index)
        if not action:
            continue
        try:
            validate_public_safe_text("derived recommended_action", action)
        except ValueError:
            continue
        return action
    return DEFAULT_REFRESH_ACTION


def resolve_goal_state(
    *,
    registry: dict[str, Any],
    goal_id: str,
    project_override: Path | None,
    state_file_override: Path | None,
) -> tuple[dict[str, Any] | None, Path | None, Path]:
    goal = next((item for item in registry_goals(registry) if str(item.get("id")) == goal_id), None)
    project = project_override.expanduser().resolve() if project_override else None
    if project is None and goal and goal.get("repo"):
        project = Path(str(goal.get("repo"))).expanduser()

    state_file = state_file_override.expanduser() if state_file_override else None
    if state_file is None and goal:
        state_file = resolve_state_file(project, goal.get("state_file")) if project else None
    if state_file is None:
        raise ValueError("state file is required when the goal is not resolvable from registry")
    if not state_file.is_absolute():
        if project is None:
            raise ValueError("relative state file requires --project or registry repo")
        state_file = project / state_file
    return goal, project, state_file


def build_state_refresh_record(
    *,
    goal_id: str,
    state_file: Path,
    state_text: str,
    classification: str,
    recommended_action: str,
    generated_at: str,
    registry_goal: dict[str, Any] | None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    agent_id: str | None = None,
    agent_lane: str | None = None,
    autonomous_replan_recorded: bool = False,
) -> dict[str, Any]:
    frontmatter = parse_frontmatter(state_text)
    next_action = extract_section_lines(state_text, "Next Action")
    recent_feedback = extract_section_lines(state_text, "Recent User Feedback", limit=5)
    progress = extract_section_lines(state_text, "Progress Ledger", limit=5)
    digest = hashlib.sha256(state_text.encode("utf-8")).hexdigest()[:16]
    authority_sources = []
    if registry_goal and isinstance(registry_goal.get("authority_sources"), list):
        authority_sources = registry_goal.get("authority_sources") or []
    record = {
        "generated_at": generated_at,
        "goal_id": goal_id,
        "classification": classification,
        "recommended_action": recommended_action,
        "health_check": (
            f"state_file 1/1; registry_goal {1 if registry_goal else 0}/1; "
            f"authority_sources {len(authority_sources)}"
        ),
        "state": {
            "path": str(state_file),
            "sha256_16": digest,
            "frontmatter": frontmatter,
            "next_action": next_action,
            "recent_feedback": recent_feedback,
            "progress": progress,
        },
        "registry_goal": {
            "present": bool(registry_goal),
            "domain": registry_goal.get("domain") if registry_goal else None,
            "status": registry_goal.get("status") if registry_goal else None,
            "adapter": registry_goal.get("adapter") if registry_goal else None,
            "authority_source_count": len(authority_sources),
        },
    }
    projection_gap = state_projection_gap_warning(state_text)
    if projection_gap:
        record["state_projection_gap"] = projection_gap
    if delivery_batch_scale:
        record["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        record["delivery_outcome"] = delivery_outcome
    if autonomous_replan_recorded:
        record["autonomous_replan_ack"] = {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "refresh_state",
        }
    if agent_id:
        record["progress_scope"] = AGENT_LANE_PROGRESS_SCOPE
        record["agent_id"] = agent_id
        record["agent_lane"] = agent_lane or agent_id
    return record


def render_state_refresh_markdown(payload: dict[str, Any]) -> str:
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    frontmatter = state.get("frontmatter") if isinstance(state.get("frontmatter"), dict) else {}
    lines = [
        "# LoopX State Refresh",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- progress_scope: `{payload.get('progress_scope')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- agent_lane: `{payload.get('agent_lane')}`",
        f"- delivery_batch_scale: `{payload.get('delivery_batch_scale')}`",
        f"- delivery_outcome: `{payload.get('delivery_outcome')}`",
        f"- autonomous_replan_recorded: `{payload.get('autonomous_replan_recorded')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- state_file: `{state.get('path')}`",
        f"- state_updated_at: `{frontmatter.get('updated_at')}`",
        f"- health_check: `{payload.get('health_check')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)

    projection_gap = (
        payload.get("state_projection_gap")
        if isinstance(payload.get("state_projection_gap"), dict)
        else {}
    )
    if projection_gap:
        lines.append(
            "- state_projection_gap: "
            f"requires_todo_expansion={projection_gap.get('requires_todo_expansion')} "
            f"user_open={projection_gap.get('user_open_count')} "
            f"agent_open={projection_gap.get('agent_open_count')} "
            f"target_roles={','.join(projection_gap.get('target_roles') or [])}"
        )
        if projection_gap.get("recommended_action"):
            lines.append(f"- state_projection_gap_action: {projection_gap.get('recommended_action')}")

    next_action_update = (
        payload.get("active_state_next_action_update")
        if isinstance(payload.get("active_state_next_action_update"), dict)
        else {}
    )
    if next_action_update:
        lines.append(
            "- active_state_next_action_update: "
            f"updated={next_action_update.get('updated')} "
            f"would_update={next_action_update.get('would_update')} "
            f"dry_run={next_action_update.get('dry_run')}"
        )
        if next_action_update.get("next_action"):
            lines.append(
                f"- active_state_next_action: {next_action_update.get('next_action')}"
            )

    global_sync = payload.get("global_sync") if isinstance(payload.get("global_sync"), dict) else {}
    if global_sync:
        lines.extend(
            [
                f"- global_registry: `{global_sync.get('global_registry')}`",
                f"- global_sync_wrote: `{global_sync.get('wrote')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Recommended Action",
            str(payload.get("recommended_action") or ""),
        ]
    )
    for heading, key in (
        ("Next Action", "next_action"),
        ("Recent Feedback", "recent_feedback"),
        ("Progress", "progress"),
    ):
        values = state.get(key) if isinstance(state.get(key), list) else []
        if values:
            lines.extend(["", f"## {heading}"])
            lines.extend(f"- {value}" for value in section_list_items(values))
    return "\n".join(lines)


def refresh_state_run(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    project: Path | None,
    state_file: Path | None,
    classification: str,
    recommended_action: str | None,
    next_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    agent_id: str | None = None,
    agent_lane: str | None = None,
    autonomous_replan_recorded: bool = False,
    dry_run: bool,
    sync_global: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    validate_public_safe_text("classification", classification)
    normalized_agent_id = (agent_id or "").strip()
    normalized_agent_lane = (agent_lane or "").strip()
    if normalized_agent_id:
        validate_public_safe_text("agent_id", normalized_agent_id)
    if normalized_agent_lane:
        validate_public_safe_text("agent_lane", normalized_agent_lane)
    if normalized_agent_lane and not normalized_agent_id:
        raise ValueError("--agent-lane requires --agent-id so the lane has an owner")
    normalized_delivery_batch_scale = (
        require_delivery_batch_scale(delivery_batch_scale).value if delivery_batch_scale else None
    )
    normalized_delivery_outcome = (
        require_delivery_outcome(delivery_outcome).value if delivery_outcome else None
    )
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    registry_goal, resolved_project, resolved_state_file = resolve_goal_state(
        registry=registry,
        goal_id=safe_goal_id,
        project_override=project,
        state_file_override=state_file,
    )
    if normalized_agent_id and registry_goal:
        coordination = registry_goal.get("coordination") if isinstance(registry_goal.get("coordination"), dict) else {}
        registered_raw = coordination.get("registered_agents") if isinstance(coordination, dict) else []
        registered_agents = []
        registered_values = registered_raw if isinstance(registered_raw, list) else []
        for value in registered_values:
            if isinstance(value, dict):
                registered_agents.append(str(value.get("id") or ""))
            else:
                registered_agents.append(str(value or ""))
        registered_agents = [value for value in registered_agents if value]
        if registered_agents and normalized_agent_id not in registered_agents:
            raise ValueError(
                f"agent_id {normalized_agent_id!r} is not registered for goal {safe_goal_id!r}"
            )
    if not resolved_state_file.exists():
        raise FileNotFoundError(f"state file does not exist: {resolved_state_file}")
    state_text = resolved_state_file.read_text(encoding="utf-8")
    normalized_next_action = normalize_next_action_text(next_action) if next_action else None
    generated_at = now_local()
    active_state_next_action_update: dict[str, Any] | None = None
    if normalized_next_action:
        with exclusive_file_lock(resolved_state_file):
            locked_state_text = resolved_state_file.read_text(encoding="utf-8")
            updated_state_text, state_updated = replace_next_action_section(
                locked_state_text,
                next_action=normalized_next_action,
                updated_at=generated_at,
            )
            active_state_next_action_update = {
                "schema_version": ACTIVE_STATE_NEXT_ACTION_UPDATE_SCHEMA_VERSION,
                "source": "refresh_state",
                "next_action": normalized_next_action,
                "updated": bool(state_updated and not dry_run),
                "would_update": bool(state_updated),
                "dry_run": bool(dry_run),
                "updated_at": generated_at if state_updated else None,
            }
            if state_updated and not dry_run:
                resolved_state_file.write_text(updated_state_text, encoding="utf-8")
            state_text = updated_state_text if state_updated else locked_state_text

    action = recommended_action or derive_recommended_action(state_text)
    validate_public_safe_text("recommended_action", action)
    record = build_state_refresh_record(
        goal_id=safe_goal_id,
        state_file=resolved_state_file,
        state_text=state_text,
        classification=classification,
        recommended_action=action,
        generated_at=generated_at,
        registry_goal=registry_goal,
        delivery_batch_scale=normalized_delivery_batch_scale,
        delivery_outcome=normalized_delivery_outcome,
        agent_id=normalized_agent_id or None,
        agent_lane=normalized_agent_lane or None,
        autonomous_replan_recorded=autonomous_replan_recorded,
    )
    if active_state_next_action_update:
        record["active_state_next_action_update"] = active_state_next_action_update

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    json_path, markdown_path = unique_run_paths(runs_dir, generated_at)
    index_path = runs_dir / "index.jsonl"
    index_record = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if normalized_delivery_batch_scale:
        index_record["delivery_batch_scale"] = normalized_delivery_batch_scale
    if normalized_delivery_outcome:
        index_record["delivery_outcome"] = normalized_delivery_outcome
    if autonomous_replan_recorded:
        index_record["autonomous_replan_ack"] = record["autonomous_replan_ack"]
    if normalized_agent_id:
        index_record["progress_scope"] = AGENT_LANE_PROGRESS_SCOPE
        index_record["agent_id"] = normalized_agent_id
        index_record["agent_lane"] = normalized_agent_lane or normalized_agent_id
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "project": str(resolved_project) if resolved_project else None,
        "goal_id": safe_goal_id,
        "classification": classification,
        "progress_scope": record.get("progress_scope"),
        "agent_id": record.get("agent_id"),
        "agent_lane": record.get("agent_lane"),
        "autonomous_replan_recorded": autonomous_replan_recorded,
        "recommended_action": action,
        "active_state_next_action_update": active_state_next_action_update,
        "generated_at": generated_at,
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        **record,
    }
    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path, markdown_path = reserve_unique_run_paths(runs_dir, generated_at)
        index_record["json_path"] = str(json_path)
        index_record["markdown_path"] = str(markdown_path)
        payload["json_path"] = str(json_path)
        payload["markdown_path"] = str(markdown_path)
        json_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(render_state_refresh_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    if sync_global:
        payload["global_sync"] = sync_project_registry_to_global(
            registry_path=registry_path,
            runtime_root_override=str(runtime_root),
            goal_id=safe_goal_id,
            dry_run=dry_run,
        )
    else:
        payload["global_sync"] = {
            "enabled": False,
            "global_registry": str(runtime_root / "registry.global.json"),
            "synced_goal_ids": [],
            "wrote": False,
        }
    return payload
