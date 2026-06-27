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
    normalize_todo_claimed_by,
    normalize_todo_id,
    parse_todo_metadata_line,
)


DEFAULT_REFRESH_CLASSIFICATION = "state_refreshed"
DEFAULT_REFRESH_ACTION = "inspect refreshed active goal state and continue the next bounded progress segment"
RECOMMENDED_ACTION_SOURCE_EXPLICIT = "explicit_arg"
RECOMMENDED_ACTION_SOURCE_ACTIVE_NEXT_ACTION = "active_state_next_action"
RECOMMENDED_ACTION_SOURCE_AGENT_TODO_FALLBACK = "agent_todo_fallback"
RECOMMENDED_ACTION_SOURCE_DEFAULT = "default_refresh_action"
AGENT_LANE_PROGRESS_SCOPE = "agent_lane"
RECOMMENDED_ACTION_SECTION_LINE_LIMIT = 16
BULLET_PREFIX_RE = re.compile(r"^(?:[-*]\s+|\d+[.)]\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[(?P<mark>[ xX])\]\s+")
ACTIVE_STATE_NEXT_ACTION_UPDATE_SCHEMA_VERSION = "active_state_next_action_update_v0"
REPAIR_DELTA_CONTRACT_SCHEMA_VERSION = "repair_delta_contract_v0"
REPAIR_NOOP_SCHEMA_VERSION = "repair_noop_v0"
TODO_ID_REFERENCE_RE = re.compile(r"\btodo_[a-z0-9_-]{3,64}\b", flags=re.IGNORECASE)
REPAIR_DELTA_KIND_CHOICES = (
    "effective_action",
    "interaction_contract",
    "runnable_todo_set",
    "user_gate",
    "blocker",
    "successor_or_supersede",
    "capability_gate",
    "monitor_target",
    "active_state_next_action",
    "goal_boundary_projection",
    "watch_lane_continuation",
)


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


def normalize_repair_delta_kinds(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    allowed = set(REPAIR_DELTA_KIND_CHOICES)
    for value in values or []:
        item = str(value or "").strip()
        if not item:
            continue
        if item not in allowed:
            raise ValueError(
                "repair_delta_kind must be one of: " + ", ".join(REPAIR_DELTA_KIND_CHOICES)
            )
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def registered_agents_for_goal(registry_goal: dict[str, Any] | None) -> list[str]:
    coordination = (
        registry_goal.get("coordination")
        if registry_goal and isinstance(registry_goal.get("coordination"), dict)
        else {}
    )
    registered_raw = coordination.get("registered_agents") if isinstance(coordination, dict) else []
    registered_values = registered_raw if isinstance(registered_raw, list) else []
    registered_agents: list[str] = []
    for value in registered_values:
        candidate = value.get("id") if isinstance(value, dict) else value
        normalized = normalize_todo_claimed_by(candidate)
        if normalized:
            registered_agents.append(normalized)
    return registered_agents


def primary_agent_for_goal(registry_goal: dict[str, Any] | None) -> str | None:
    coordination = (
        registry_goal.get("coordination")
        if registry_goal and isinstance(registry_goal.get("coordination"), dict)
        else {}
    )
    return normalize_todo_claimed_by(coordination.get("primary_agent") if coordination else None)


def todo_claims_by_id(state_text: str) -> dict[str, str]:
    claims: dict[str, str] = {}
    for line in state_text.splitlines():
        metadata = parse_todo_metadata_line(line)
        if not metadata:
            continue
        todo_id = normalize_todo_id(metadata.get("todo_id"))
        claimed_by = normalize_todo_claimed_by(metadata.get("claimed_by"))
        if todo_id and claimed_by:
            claims[todo_id] = claimed_by
    return claims


def normalize_action_match_text(value: str | None) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    text = BULLET_PREFIX_RE.sub("", text).strip()
    checkbox = CHECKBOX_PREFIX_RE.match(text)
    if checkbox:
        text = text[checkbox.end() :].strip()
    return text


def todo_claims_by_action_text(state_text: str) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    previous_todo_text: str | None = None
    for line in state_text.splitlines():
        stripped = line.strip()
        if BULLET_PREFIX_RE.match(stripped):
            bullet_text = BULLET_PREFIX_RE.sub("", stripped).strip()
            if CHECKBOX_PREFIX_RE.match(bullet_text):
                previous_todo_text = CHECKBOX_PREFIX_RE.sub("", bullet_text).strip()
            else:
                previous_todo_text = None
        metadata = parse_todo_metadata_line(line)
        if not metadata:
            continue
        todo_id = normalize_todo_id(metadata.get("todo_id"))
        claimed_by = normalize_todo_claimed_by(metadata.get("claimed_by"))
        status = str(metadata.get("status") or "").strip().lower()
        if (
            not todo_id
            or not claimed_by
            or not previous_todo_text
            or status in {"done", "deferred", "blocked"}
        ):
            continue
        normalized_text = normalize_action_match_text(previous_todo_text)
        if len(normalized_text) < 32:
            continue
        claims.append(
            {
                "todo_id": todo_id,
                "claimed_by": claimed_by,
                "action_text": normalized_text,
            }
        )
    return claims


def referenced_todo_ids(*values: str | None) -> list[str]:
    todo_ids: list[str] = []
    seen: set[str] = set()
    for value in values:
        for match in TODO_ID_REFERENCE_RE.findall(str(value or "")):
            todo_id = normalize_todo_id(match)
            if todo_id and todo_id not in seen:
                seen.add(todo_id)
                todo_ids.append(todo_id)
    return todo_ids


def referenced_non_primary_agent(
    *,
    registered_agents: list[str],
    primary_agent: str,
    values: list[str | None],
) -> str | None:
    for value in values:
        text = str(value or "")
        for agent_id in registered_agents:
            if agent_id == primary_agent:
                continue
            pattern = rf"(?<![a-z0-9_.:@-]){re.escape(agent_id)}(?![a-z0-9_.:@-])"
            if re.search(pattern, text):
                return agent_id
    return None


def infer_agent_lane_scope(
    *,
    registry_goal: dict[str, Any] | None,
    state_text: str,
    recommended_action: str | None,
    next_action: str | None,
) -> dict[str, Any] | None:
    registered_agents = registered_agents_for_goal(registry_goal)
    primary_agent = primary_agent_for_goal(registry_goal)
    if not registered_agents or not primary_agent:
        return None
    claims_by_id = todo_claims_by_id(state_text)
    for todo_id in referenced_todo_ids(recommended_action, next_action):
        claimed_by = claims_by_id.get(todo_id)
        if not claimed_by or claimed_by == primary_agent or claimed_by not in registered_agents:
            continue
        return {
            "schema_version": "refresh_state_agent_lane_scope_inference_v0",
            "inferred": True,
            "agent_id": claimed_by,
            "agent_lane": claimed_by,
            "todo_id": todo_id,
            "primary_agent": primary_agent,
            "source": "referenced_claimed_todo",
        }
    values = [recommended_action, next_action]
    normalized_values = [normalize_action_match_text(value) for value in values if value]
    for claim in todo_claims_by_action_text(state_text):
        claimed_by = claim["claimed_by"]
        if claimed_by == primary_agent or claimed_by not in registered_agents:
            continue
        todo_text = claim["action_text"]
        for value in normalized_values:
            if not value or len(value) < 32:
                continue
            if value == todo_text or value in todo_text or todo_text in value:
                return {
                    "schema_version": "refresh_state_agent_lane_scope_inference_v0",
                    "inferred": True,
                    "agent_id": claimed_by,
                    "agent_lane": claimed_by,
                    "todo_id": claim["todo_id"],
                    "primary_agent": primary_agent,
                    "source": "matched_claimed_todo_text",
                }
    agent_id = referenced_non_primary_agent(
        registered_agents=registered_agents,
        primary_agent=primary_agent,
        values=values,
    )
    if agent_id:
        return {
            "schema_version": "refresh_state_agent_lane_scope_inference_v0",
            "inferred": True,
            "agent_id": agent_id,
            "agent_lane": agent_id,
            "todo_id": None,
            "primary_agent": primary_agent,
            "source": "referenced_registered_non_primary_agent",
        }
    return None


def _noop_classification_for(classification: str) -> str:
    normalized = str(classification or "").strip().lower()
    if "repair" in normalized and "replan" not in normalized:
        return "repair_noop"
    return "replan_noop"


def build_repair_delta_contract(
    *,
    requested_delta_kinds: list[str],
    active_state_next_action_update: dict[str, Any] | None,
    dry_run: bool,
) -> dict[str, Any]:
    delta_kinds = list(requested_delta_kinds)
    evidence: list[dict[str, Any]] = []
    update = active_state_next_action_update or {}
    if update.get("updated") is True:
        if "active_state_next_action" not in delta_kinds:
            delta_kinds.append("active_state_next_action")
        evidence.append(
            {
                "kind": "active_state_next_action",
                "source": "refresh_state_next_action_update",
                "updated": True,
            }
        )
    elif update.get("would_update") is True:
        evidence.append(
            {
                "kind": "active_state_next_action",
                "source": "refresh_state_next_action_update",
                "would_update": True,
                "dry_run": bool(dry_run),
            }
        )

    return {
        "schema_version": REPAIR_DELTA_CONTRACT_SCHEMA_VERSION,
        "required": True,
        "delta_present": bool(delta_kinds),
        "delta_kinds": delta_kinds,
        "auto_evidence": evidence,
        "accepted_without_delta": False,
    }


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


def derive_recommended_action_with_source(state_text: str) -> tuple[str, str]:
    lines = extract_section_lines(state_text, "Next Action", limit=RECOMMENDED_ACTION_SECTION_LINE_LIMIT)
    for index, line in enumerate(lines):
        action = first_action_item(lines, index)
        if not action:
            continue
        try:
            validate_public_safe_text("derived recommended_action", action)
        except ValueError:
            continue
        return action, RECOMMENDED_ACTION_SOURCE_ACTIVE_NEXT_ACTION
    agent_todo_action = first_open_agent_todo_action(state_text)
    if agent_todo_action:
        return agent_todo_action, RECOMMENDED_ACTION_SOURCE_AGENT_TODO_FALLBACK
    return DEFAULT_REFRESH_ACTION, RECOMMENDED_ACTION_SOURCE_DEFAULT


def derive_recommended_action(state_text: str) -> str:
    return derive_recommended_action_with_source(state_text)[0]


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
    recommended_action_source: str,
    generated_at: str,
    registry_goal: dict[str, Any] | None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    agent_id: str | None = None,
    agent_lane: str | None = None,
    autonomous_replan_recorded: bool = False,
    repair_delta_contract: dict[str, Any] | None = None,
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
        "recommended_action_source": recommended_action_source,
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
        if repair_delta_contract:
            record["autonomous_replan_ack"]["delta_contract"] = repair_delta_contract
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
        f"- autonomous_replan_recorded_requested: `{payload.get('autonomous_replan_recorded_requested')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- state_file: `{state.get('path')}`",
        f"- state_updated_at: `{frontmatter.get('updated_at')}`",
        f"- health_check: `{payload.get('health_check')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)

    repair_delta = (
        payload.get("repair_delta_contract")
        if isinstance(payload.get("repair_delta_contract"), dict)
        else {}
    )
    if repair_delta:
        lines.append(
            "- repair_delta_contract: "
            f"delta_present={repair_delta.get('delta_present')} "
            f"kinds={','.join(repair_delta.get('delta_kinds') or [])}"
        )

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
            f"- source: `{payload.get('recommended_action_source')}`",
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
    repair_delta_kinds: list[str] | None = None,
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
    normalized_repair_delta_kinds = normalize_repair_delta_kinds(repair_delta_kinds)
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    registry_goal, resolved_project, resolved_state_file = resolve_goal_state(
        registry=registry,
        goal_id=safe_goal_id,
        project_override=project,
        state_file_override=state_file,
    )
    if not resolved_state_file.exists():
        raise FileNotFoundError(f"state file does not exist: {resolved_state_file}")
    state_text = resolved_state_file.read_text(encoding="utf-8")
    normalized_next_action = normalize_next_action_text(next_action) if next_action else None
    agent_lane_scope_inference: dict[str, Any] | None = None
    if not normalized_agent_id:
        inferred_scope = infer_agent_lane_scope(
            registry_goal=registry_goal,
            state_text=state_text,
            recommended_action=recommended_action,
            next_action=normalized_next_action,
        )
        if inferred_scope:
            if normalized_next_action:
                raise ValueError(
                    "unscoped refresh-state inferred non-primary agent-lane scope "
                    f"from todo_id={inferred_scope.get('todo_id')!r}; rerun with "
                    f"--agent-id {inferred_scope.get('agent_id')} without --next-action, "
                    "or have the primary agent update the durable active-state Next Action"
                )
            if inferred_scope.get("source") == "referenced_registered_non_primary_agent":
                raise ValueError(
                    "unscoped refresh-state mentions registered non-primary agent "
                    f"{inferred_scope.get('agent_id')!r}; rerun with explicit "
                    f"--agent-id {inferred_scope.get('agent_id')} because text-only "
                    "agent references are ambiguous"
                )
            normalized_agent_id = str(inferred_scope["agent_id"])
            normalized_agent_lane = str(inferred_scope["agent_lane"])
            agent_lane_scope_inference = inferred_scope
    if normalized_agent_id and registry_goal:
        registered_agents = registered_agents_for_goal(registry_goal)
        if registered_agents and normalized_agent_id not in registered_agents:
            raise ValueError(
                f"agent_id {normalized_agent_id!r} is not registered for goal {safe_goal_id!r}"
            )
        primary_agent = primary_agent_for_goal(registry_goal)
        if normalized_next_action and primary_agent and normalized_agent_id != primary_agent:
            raise ValueError(
                "non-primary agent "
                f"{normalized_agent_id!r} cannot update the durable active-state Next Action; "
                "rerun without --next-action or have the primary agent update the global Next Action"
            )
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

    if recommended_action:
        action = recommended_action
        recommended_action_source = RECOMMENDED_ACTION_SOURCE_EXPLICIT
    else:
        action, recommended_action_source = derive_recommended_action_with_source(state_text)
    validate_public_safe_text("recommended_action", action)
    repair_delta_contract: dict[str, Any] | None = None
    requested_classification = classification
    effective_autonomous_replan_recorded = bool(autonomous_replan_recorded)
    if autonomous_replan_recorded:
        repair_delta_contract = build_repair_delta_contract(
            requested_delta_kinds=normalized_repair_delta_kinds,
            active_state_next_action_update=active_state_next_action_update,
            dry_run=dry_run,
        )
        if not repair_delta_contract["delta_present"]:
            classification = _noop_classification_for(classification)
            effective_autonomous_replan_recorded = False
            if normalized_delivery_outcome in {"outcome_progress", "primary_goal_outcome"}:
                normalized_delivery_outcome = "outcome_gap"
    record = build_state_refresh_record(
        goal_id=safe_goal_id,
        state_file=resolved_state_file,
        state_text=state_text,
        classification=classification,
        recommended_action=action,
        recommended_action_source=recommended_action_source,
        generated_at=generated_at,
        registry_goal=registry_goal,
        delivery_batch_scale=normalized_delivery_batch_scale,
        delivery_outcome=normalized_delivery_outcome,
        agent_id=normalized_agent_id or None,
        agent_lane=normalized_agent_lane or None,
        autonomous_replan_recorded=effective_autonomous_replan_recorded,
        repair_delta_contract=repair_delta_contract,
    )
    if agent_lane_scope_inference:
        record["agent_lane_scope_inference"] = agent_lane_scope_inference
    if autonomous_replan_recorded:
        if "autonomous_replan_ack" not in record:
            record["autonomous_replan_ack"] = {
                "schema_version": "autonomous_replan_ack_v0",
                "recorded": False,
                "source": "refresh_state",
                "delta_contract": repair_delta_contract,
            }
        record["autonomous_replan_ack"]["requested"] = True
        if requested_classification != classification:
            record["autonomous_replan_ack"]["requested_classification"] = requested_classification
            record["autonomous_replan_noop"] = {
                "schema_version": REPAIR_NOOP_SCHEMA_VERSION,
                "classification": classification,
                "requested_classification": requested_classification,
                "reason": "autonomous replan ACK requested without a machine-visible repair delta",
            }
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
        "recommended_action_source": recommended_action_source,
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
        if requested_classification != classification:
            index_record["requested_classification"] = requested_classification
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
        "autonomous_replan_recorded": effective_autonomous_replan_recorded,
        "autonomous_replan_recorded_requested": bool(autonomous_replan_recorded),
        "repair_delta_contract": repair_delta_contract,
        "recommended_action": action,
        "recommended_action_source": recommended_action_source,
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
