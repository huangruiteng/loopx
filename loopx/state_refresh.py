from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .control_plane.runtime.time import now_local_iso
from .control_plane.work_items.delivery_batch_scale import (
    DELIVERY_BATCH_SCALE_CHOICES as DELIVERY_BATCH_SCALE_CHOICES,
    require_delivery_batch_scale,
)
from .control_plane.work_items.delivery_outcome import (
    ACCOUNTABLE_DELIVERY_OUTCOMES,
    DELIVERY_OUTCOME_CHOICES as DELIVERY_OUTCOME_CHOICES,
    require_delivery_outcome,
)
from .control_plane.agents.workspace_guard import capture_delivery_workspace
from .control_plane.work_items.repair_delta import (
    REPAIR_DELTA_KIND_CHOICES as REPAIR_DELTA_KIND_CHOICES,
    normalize_repair_delta_kinds,
)
from .control_plane.work_items.autonomous_replan_ack import (
    latest_blocked_successor_frontier_identity,
)
from .control_plane.runtime.shared_runtime_refresh_projection import (
    build_shared_runtime_projection,
    write_shared_runtime_projection,
)
from .control_plane.runtime.runtime_projection_route import (
    compact_runtime_projection_route,
    resolve_runtime_projection_route,
)
from .feedback import validate_local_control_text, validate_public_safe_text
from .file_lock import exclusive_file_lock
from .global_registry import sync_project_registry_to_global
from .history import (
    load_index,
    load_registry,
    reserve_unique_run_paths,
    unique_run_paths,
)
from .control_plane.runtime.local_state_write_correctness import build_local_state_write_correctness_dry_run_packet
from .paths import resolve_runtime_root
from .control_plane.goals.goal_vision import normalize_goal_vision_packet
from .control_plane.goals.goal_frontier import latest_agent_vision_from_runs
from .registry import registry_goals, resolve_state_file
from .runtime import validate_goal_id_path_segment
from .state_projection import state_projection_gap_warning
from .control_plane.todos.contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_BLOCKER,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    normalize_todo_claimed_by,
)


DEFAULT_REFRESH_CLASSIFICATION = "state_refreshed"
DEFAULT_REFRESH_ACTION = "inspect refreshed active goal state and continue the next bounded progress segment"
RECOMMENDED_ACTION_SOURCE_EXPLICIT = "explicit_arg"
RECOMMENDED_ACTION_SOURCE_ACTIVE_NEXT_ACTION = "active_state_next_action"
RECOMMENDED_ACTION_SOURCE_AGENT_TODO_FALLBACK = "agent_todo_fallback"
RECOMMENDED_ACTION_SOURCE_DEFAULT = "default_refresh_action"
GOAL_PROGRESS_SCOPE = "goal"
AGENT_LANE_PROGRESS_SCOPE = "agent_lane"
PROGRESS_SCOPE_CHOICES = (GOAL_PROGRESS_SCOPE, AGENT_LANE_PROGRESS_SCOPE)
RECOMMENDED_ACTION_SECTION_LINE_LIMIT = 16
BULLET_PREFIX_RE = re.compile(r"^(?:[-*]\s+|\d+[.)]\s+)")
CHECKBOX_PREFIX_RE = re.compile(r"^\[(?P<mark>[ xX])\]\s+")
ACTIVE_STATE_NEXT_ACTION_UPDATE_SCHEMA_VERSION = "active_state_next_action_update_v0"
REPAIR_DELTA_CONTRACT_SCHEMA_VERSION = "repair_delta_contract_v0"
REPAIR_NOOP_SCHEMA_VERSION = "repair_noop_v0"
VISION_CHECKPOINT_SCHEMA_VERSION = "vision_checkpoint_v0"
VISION_CHECKPOINT_MATERIAL_OUTCOMES = {
    "outcome_gap",
    "outcome_progress",
    "primary_goal_outcome",
}
VISION_UNCHANGED_REASON_LIMIT = 240


def now_local() -> str:
    return now_local_iso()


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
    validate_local_control_text("active_state_next_action", text)
    return text


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


def normalize_progress_scope(value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    validate_public_safe_text("progress_scope", normalized)
    if normalized not in PROGRESS_SCOPE_CHOICES:
        raise ValueError(
            "--progress-scope must be one of: " + ", ".join(PROGRESS_SCOPE_CHOICES)
        )
    return normalized


def _noop_classification_for(classification: str) -> str:
    normalized = str(classification or "").strip().lower()
    if "repair" in normalized and "replan" not in normalized:
        return "repair_noop"
    return "replan_noop"


def build_repair_delta_contract(
    *,
    requested_delta_kinds: list[str],
    active_state_next_action_update: dict[str, Any] | None,
    agent_vision: dict[str, Any] | None,
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
    if agent_vision:
        if "goal_vision_patch" not in delta_kinds:
            delta_kinds.append("goal_vision_patch")
        evidence.append(
            {
                "kind": "goal_vision_patch",
                "source": "refresh_state_agent_vision",
                "state": agent_vision.get("state"),
                "agent_id": agent_vision.get("agent_id"),
                "budget_status": (
                    agent_vision.get("vision_budget", {}).get("status")
                    if isinstance(agent_vision.get("vision_budget"), dict)
                    else None
                ),
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


def build_vision_checkpoint(
    *,
    agent_id: str | None,
    agent_vision: dict[str, Any] | None,
    existing_agent_vision: dict[str, Any] | None,
    vision_unchanged_reason: str | None,
    delivery_outcome: str | None,
    autonomous_replan_recorded: bool,
    active_state_next_action_update: dict[str, Any] | None,
    repair_delta_kinds: list[str] | None,
) -> dict[str, Any]:
    """Return the explicit vision closeout decision for this refresh run."""

    triggers: list[dict[str, Any]] = []
    if autonomous_replan_recorded:
        triggers.append({"kind": "autonomous_replan_recorded"})
    if delivery_outcome in VISION_CHECKPOINT_MATERIAL_OUTCOMES:
        triggers.append(
            {
                "kind": "material_delivery_outcome",
                "delivery_outcome": delivery_outcome,
            }
        )
    if active_state_next_action_update and active_state_next_action_update.get("would_update"):
        triggers.append({"kind": "durable_next_action_update"})

    delta_kinds = set(repair_delta_kinds or [])
    unchanged = normalize_vision_unchanged_reason(vision_unchanged_reason)

    required = bool(triggers or unchanged)
    if agent_vision:
        decision = "patched"
        satisfied = True
    elif unchanged and existing_agent_vision:
        decision = "unchanged_with_reason"
        satisfied = True
    elif unchanged:
        decision = "missing_required"
        satisfied = False
    elif delta_kinds & {"no_followup", "successor_or_supersede"}:
        decision = "retired_or_superseded"
        satisfied = True
    elif required:
        decision = "missing_required"
        satisfied = False
    else:
        decision = "not_required"
        satisfied = True

    checkpoint: dict[str, Any] = {
        "schema_version": VISION_CHECKPOINT_SCHEMA_VERSION,
        "agent_id": agent_id,
        "required": required,
        "satisfied": satisfied,
        "decision": decision,
        "triggers": triggers,
    }
    if agent_vision:
        checkpoint["agent_vision_state"] = agent_vision.get("state")
    if unchanged and existing_agent_vision:
        checkpoint["unchanged_reason"] = unchanged
        checkpoint["agent_vision_state"] = existing_agent_vision.get("state")
    elif unchanged:
        checkpoint["missing_baseline"] = True
        checkpoint["rejected_unchanged_reason"] = unchanged
    if delta_kinds:
        checkpoint["repair_delta_kinds"] = sorted(delta_kinds)
    if not satisfied:
        checkpoint["required_resolution"] = ["write_vision_patch"]
        if not checkpoint.get("missing_baseline"):
            checkpoint["required_resolution"].append("record_unchanged_reason")
        checkpoint["required_resolution"].extend(
            ["record_no_followup", "link_successor_or_supersede"]
        )
    return checkpoint


def normalize_vision_unchanged_reason(value: str | None) -> str:
    """Normalize and validate a vision closeout reason before state mutation."""

    unchanged = " ".join(str(value or "").strip().split())
    if not unchanged:
        return ""
    validate_public_safe_text("vision_unchanged_reason", unchanged)
    if len(unchanged) > VISION_UNCHANGED_REASON_LIMIT:
        raise ValueError(
            "vision_unchanged_reason exceeds "
            f"{VISION_UNCHANGED_REASON_LIMIT} chars"
        )
    return unchanged


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
            validate_local_control_text("derived agent_todo recommended_action", action)
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
            validate_local_control_text("derived recommended_action", action)
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
    progress_scope: str | None = None,
    agent_id: str | None = None,
    agent_lane: str | None = None,
    autonomous_replan_recorded: bool = False,
    repair_delta_contract: dict[str, Any] | None = None,
    autonomous_replan_frontier_identity: str | None = None,
    agent_vision: dict[str, Any] | None = None,
    vision_checkpoint: dict[str, Any] | None = None,
    delivery_workspace: dict[str, Any] | None = None,
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
    if delivery_workspace:
        record["delivery_workspace"] = delivery_workspace
    if autonomous_replan_recorded:
        record["autonomous_replan_ack"] = {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "refresh_state",
        }
        if repair_delta_contract:
            record["autonomous_replan_ack"]["delta_contract"] = repair_delta_contract
        if autonomous_replan_frontier_identity:
            record["autonomous_replan_ack"]["frontier_identity"] = (
                autonomous_replan_frontier_identity
            )
    if agent_vision:
        record["agent_vision"] = agent_vision
    if vision_checkpoint:
        record["vision_checkpoint"] = vision_checkpoint
    if progress_scope:
        record["progress_scope"] = progress_scope
    if agent_id:
        record["agent_id"] = agent_id
    if progress_scope == AGENT_LANE_PROGRESS_SCOPE and agent_id:
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
    if "external_sink_delivery_authorized" in payload:
        lines.append(
            "- external_sink_delivery_authorized: "
            f"`{payload.get('external_sink_delivery_authorized')}`"
        )
    delivery_workspace = (
        payload.get("delivery_workspace")
        if isinstance(payload.get("delivery_workspace"), dict)
        else {}
    )
    if delivery_workspace:
        lines.append(
            "- delivery_workspace: "
            f"repository={delivery_workspace.get('task_repository')} "
            f"kind={delivery_workspace.get('workspace_kind')}"
        )
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
    agent_vision = (
        payload.get("agent_vision")
        if isinstance(payload.get("agent_vision"), dict)
        else {}
    )
    if agent_vision:
        budget = (
            agent_vision.get("vision_budget")
            if isinstance(agent_vision.get("vision_budget"), dict)
            else {}
        )
        lines.append(
            "- agent_vision: "
            f"state={agent_vision.get('state')} "
            f"agent_id={agent_vision.get('agent_id')} "
            f"budget={budget.get('total_usage')}/{budget.get('total_limit')}"
        )
    vision_checkpoint = (
        payload.get("vision_checkpoint")
        if isinstance(payload.get("vision_checkpoint"), dict)
        else {}
    )
    if vision_checkpoint:
        lines.append(
            "- vision_checkpoint: "
            f"agent_id={vision_checkpoint.get('agent_id')} "
            f"required={vision_checkpoint.get('required')} "
            f"satisfied={vision_checkpoint.get('satisfied')} "
            f"decision={vision_checkpoint.get('decision')}"
        )
        if vision_checkpoint.get("unchanged_reason"):
            lines.append(
                f"- vision_unchanged_reason: {vision_checkpoint.get('unchanged_reason')}"
            )
        required_resolution = vision_checkpoint.get("required_resolution")
        if required_resolution:
            lines.append(
                "- vision_checkpoint_required_resolution: "
                f"{','.join(str(item) for item in required_resolution)}"
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

    write_correctness = (
        payload.get("local_state_write_correctness")
        if isinstance(payload.get("local_state_write_correctness"), dict)
        else {}
    )
    if write_correctness:
        intent = write_correctness.get("write_intent") if isinstance(write_correctness.get("write_intent"), dict) else {}
        preview = write_correctness.get("preview") if isinstance(write_correctness.get("preview"), dict) else {}
        apply_result = (
            write_correctness.get("apply_result")
            if isinstance(write_correctness.get("apply_result"), dict)
            else {}
        )
        lines.append(
            "- local_state_write_correctness: "
            f"schema={write_correctness.get('schema_version')} "
            f"write_class={intent.get('write_class')} "
            f"status={apply_result.get('status')} "
            f"non_destructive={preview.get('non_destructive')}"
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
    delivery_workspace_path: Path | None = None,
    agent_id: str | None = None,
    agent_lane: str | None = None,
    progress_scope: str | None = None,
    autonomous_replan_recorded: bool = False,
    repair_delta_kinds: list[str] | None = None,
    agent_vision_packet: dict[str, Any] | None = None,
    vision_unchanged_reason: str | None = None,
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
    normalized_progress_scope = normalize_progress_scope(progress_scope)
    normalized_delivery_batch_scale = (
        require_delivery_batch_scale(delivery_batch_scale).value if delivery_batch_scale else None
    )
    normalized_delivery_outcome = (
        require_delivery_outcome(delivery_outcome).value if delivery_outcome else None
    )
    if delivery_workspace_path is not None and (
        normalized_delivery_outcome not in ACCOUNTABLE_DELIVERY_OUTCOMES
    ):
        raise ValueError(
            "--delivery-workspace-path requires an accountable --delivery-outcome"
        )
    normalized_repair_delta_kinds = normalize_repair_delta_kinds(repair_delta_kinds)
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    runtime_projection_route = resolve_runtime_projection_route(
        registry_path=registry_path,
        goal_id=safe_goal_id,
        source_runtime_root=runtime_root,
    )
    route_status = str(runtime_projection_route.get("status") or "missing")
    route_target_text = str(
        runtime_projection_route.get("target_runtime_root") or ""
    ).strip()
    route_target_root = Path(route_target_text) if route_target_text else None
    shared_runtime_root = (
        route_target_root if sync_global and route_status == "resolved" else None
    )
    global_sync_runtime_root = (
        route_target_root
        if sync_global and route_status in {"resolved", "single_runtime"}
        else None
    )
    registry_goal, resolved_project, resolved_state_file = resolve_goal_state(
        registry=registry,
        goal_id=safe_goal_id,
        project_override=project,
        state_file_override=state_file,
    )
    if not resolved_state_file.exists():
        raise FileNotFoundError(f"state file does not exist: {resolved_state_file}")
    state_text = resolved_state_file.read_text(encoding="utf-8")
    expected_write_state_text = state_text
    normalized_next_action = normalize_next_action_text(next_action) if next_action else None
    registered_agents = registered_agents_for_goal(registry_goal)
    known_agents = {agent for agent in registered_agents if agent}
    multi_agent_goal = len(known_agents) > 1
    workspace_guard_policy = (
        registry_goal.get("workspace_guard_policy")
        if isinstance(registry_goal.get("workspace_guard_policy"), dict)
        else {}
    )
    explicit_peer_worktree_requirement = workspace_guard_policy.get(
        "peer_independent_worktree_required"
    )
    peer_independent_worktree_required = multi_agent_goal and (
        explicit_peer_worktree_requirement is None
        or explicit_peer_worktree_requirement is True
    )
    if normalized_agent_id and known_agents and normalized_agent_id not in known_agents:
        raise ValueError(
            f"agent_id {normalized_agent_id!r} is not registered for goal {safe_goal_id!r}"
        )
    if multi_agent_goal and not normalized_agent_id:
        raise ValueError(
            "multi-agent refresh-state requires --agent-id; text inference is disabled"
        )
    if not normalized_progress_scope:
        normalized_progress_scope = (
            AGENT_LANE_PROGRESS_SCOPE if normalized_agent_id else GOAL_PROGRESS_SCOPE
        )
    if normalized_progress_scope == AGENT_LANE_PROGRESS_SCOPE:
        if not normalized_agent_id:
            raise ValueError("--progress-scope agent_lane requires --agent-id")
        if normalized_next_action:
            raise ValueError(
                "agent-lane refresh-state cannot update the durable active-state Next Action; "
                "rerun without --next-action or use --progress-scope goal from a registered peer"
            )
    if normalized_progress_scope == GOAL_PROGRESS_SCOPE:
        if normalized_agent_lane:
            raise ValueError("--agent-lane requires --progress-scope agent_lane")
    agent_vision: dict[str, Any] | None = None
    if (agent_vision_packet is not None or vision_unchanged_reason) and not normalized_agent_id:
        raise ValueError("vision writeback requires --agent-id")
    if agent_vision_packet is not None:
        agent_vision = normalize_goal_vision_packet(
            agent_vision_packet,
            goal_id=safe_goal_id,
            agent_id=normalized_agent_id or None,
        )
    normalized_vision_unchanged_reason = normalize_vision_unchanged_reason(
        vision_unchanged_reason
    )
    existing_agent_vision: dict[str, Any] | None = None
    autonomous_replan_frontier_identity: str | None = None
    if normalized_agent_id and normalized_vision_unchanged_reason:
        existing_runs, _ = load_index(
            runtime_root / "goals" / safe_goal_id / "runs" / "index.jsonl"
        )
        newest_first_runs = [
            run
            for _, run in sorted(
                enumerate(existing_runs),
                key=lambda item: (str(item[1].get("generated_at") or ""), item[0]),
                reverse=True,
            )
        ]
        existing_agent_vision = latest_agent_vision_from_runs(
            newest_first_runs,
            goal_id=safe_goal_id,
            agent_id=normalized_agent_id,
        )
    if autonomous_replan_recorded:
        existing_runs, _ = load_index(
            runtime_root / "goals" / safe_goal_id / "runs" / "index.jsonl"
        )
        newest_first_runs = [
            run
            for _, run in sorted(
                enumerate(existing_runs),
                key=lambda item: (str(item[1].get("generated_at") or ""), item[0]),
                reverse=True,
            )
        ]
        autonomous_replan_frontier_identity = (
            latest_blocked_successor_frontier_identity(
                newest_first_runs,
                agent_id=normalized_agent_id or None,
            )
        )
    generated_at = now_local()
    active_state_next_action_update: dict[str, Any] | None = None
    if normalized_next_action:
        with exclusive_file_lock(resolved_state_file):
            locked_state_text = resolved_state_file.read_text(encoding="utf-8")
            expected_write_state_text = locked_state_text
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
    validate_local_control_text("recommended_action", action)
    repair_delta_contract: dict[str, Any] | None = None
    requested_classification = classification
    effective_autonomous_replan_recorded = bool(autonomous_replan_recorded)
    if autonomous_replan_recorded:
        repair_delta_contract = build_repair_delta_contract(
            requested_delta_kinds=normalized_repair_delta_kinds,
            active_state_next_action_update=active_state_next_action_update,
            agent_vision=agent_vision,
            dry_run=dry_run,
        )
        if not repair_delta_contract["delta_present"]:
            classification = _noop_classification_for(classification)
            effective_autonomous_replan_recorded = False
            if normalized_delivery_outcome in {"outcome_progress", "primary_goal_outcome"}:
                normalized_delivery_outcome = "outcome_gap"
    vision_checkpoint = build_vision_checkpoint(
        agent_id=normalized_agent_id or None,
        agent_vision=agent_vision,
        existing_agent_vision=existing_agent_vision,
        vision_unchanged_reason=normalized_vision_unchanged_reason,
        delivery_outcome=normalized_delivery_outcome,
        autonomous_replan_recorded=bool(autonomous_replan_recorded),
        active_state_next_action_update=active_state_next_action_update,
        repair_delta_kinds=normalized_repair_delta_kinds,
    )
    delivery_workspace = None
    if normalized_delivery_outcome in ACCOUNTABLE_DELIVERY_OUTCOMES:
        delivery_workspace = capture_delivery_workspace(
            current_path=delivery_workspace_path,
            peer_independent_worktree_required=peer_independent_worktree_required,
        )
        if delivery_workspace_path is not None:
            if delivery_workspace is None:
                raise ValueError(
                    "--delivery-workspace-path must identify a git checkout with "
                    "a credential-free origin repository"
                )
            if (
                peer_independent_worktree_required
                and delivery_workspace.get("workspace_kind")
                != "independent_git_worktree"
            ):
                raise ValueError(
                    "--delivery-workspace-path must identify the independent git "
                    "worktree that produced this peer delivery"
                )
            delivery_workspace["repository_source"] = (
                "refresh_state.delivery_workspace_path"
            )
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
        progress_scope=normalized_progress_scope,
        agent_id=normalized_agent_id or None,
        agent_lane=normalized_agent_lane or None,
        autonomous_replan_recorded=effective_autonomous_replan_recorded,
        repair_delta_contract=repair_delta_contract,
        autonomous_replan_frontier_identity=autonomous_replan_frontier_identity,
        agent_vision=agent_vision,
        vision_checkpoint=vision_checkpoint,
        delivery_workspace=delivery_workspace,
    )
    if autonomous_replan_recorded:
        if "autonomous_replan_ack" not in record:
            record["autonomous_replan_ack"] = {
                "schema_version": "autonomous_replan_ack_v0",
                "recorded": False,
                "source": "refresh_state",
                "delta_contract": repair_delta_contract,
            }
        record["autonomous_replan_ack"]["requested"] = True
        if autonomous_replan_frontier_identity:
            record["autonomous_replan_ack"]["frontier_identity"] = (
                autonomous_replan_frontier_identity
            )
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
    if agent_vision:
        record["agent_vision"] = agent_vision
    if vision_checkpoint:
        record["vision_checkpoint"] = vision_checkpoint
    compact_route = compact_runtime_projection_route(runtime_projection_route)
    compact_route["projection_enabled"] = bool(sync_global)
    compact_route["projection_marker_field"] = "shared_runtime_projection"
    record["runtime_projection_route"] = compact_route

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
    record_state = record.get("state") if isinstance(record.get("state"), dict) else {}
    record_frontmatter = (
        record_state.get("frontmatter")
        if isinstance(record_state.get("frontmatter"), dict)
        else {}
    )
    index_record["state"] = {
        "sha256_16": record_state.get("sha256_16"),
        "frontmatter": {
            "updated_at": record_frontmatter.get("updated_at"),
        },
    }
    index_record["runtime_projection_route"] = compact_route
    if normalized_delivery_batch_scale:
        index_record["delivery_batch_scale"] = normalized_delivery_batch_scale
    if normalized_delivery_outcome:
        index_record["delivery_outcome"] = normalized_delivery_outcome
    if delivery_workspace:
        index_record["delivery_workspace"] = delivery_workspace
    if autonomous_replan_recorded:
        index_record["autonomous_replan_ack"] = record["autonomous_replan_ack"]
        if requested_classification != classification:
            index_record["requested_classification"] = requested_classification
    if agent_vision:
        indexed_agent_vision = {
            "schema_version": agent_vision.get("schema_version"),
            "agent_id": agent_vision.get("agent_id"),
            "state": agent_vision.get("state"),
            "vision_patch": agent_vision.get("vision_patch")
            if isinstance(agent_vision.get("vision_patch"), dict)
            else {},
            "todo_delta": agent_vision.get("todo_delta")
            if isinstance(agent_vision.get("todo_delta"), list)
            else [],
            "vision_budget": agent_vision.get("vision_budget"),
        }
        if isinstance(agent_vision.get("path_delta"), dict):
            indexed_agent_vision["path_delta"] = agent_vision["path_delta"]
        index_record["agent_vision"] = indexed_agent_vision
    if vision_checkpoint:
        index_record["vision_checkpoint"] = vision_checkpoint
    if normalized_progress_scope:
        index_record["progress_scope"] = normalized_progress_scope
    if normalized_agent_id:
        index_record["agent_id"] = normalized_agent_id
    if normalized_progress_scope == AGENT_LANE_PROGRESS_SCOPE and normalized_agent_id:
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
        "agent_vision": agent_vision,
        "vision_checkpoint": vision_checkpoint,
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
    if dry_run:
        expected_write_scopes = ["runtime_history"]
        if active_state_next_action_update and active_state_next_action_update.get("would_update"):
            expected_write_scopes.insert(0, "active_state")
        if sync_global and route_status in {"resolved", "single_runtime"}:
            expected_write_scopes.append("global_registry")
        if shared_runtime_root:
            expected_write_scopes.append("shared_runtime_projection")
        patch_parts = [f"append refresh-state run classification={classification}"]
        if active_state_next_action_update:
            if active_state_next_action_update.get("would_update"):
                patch_parts.append("preview active-state Next Action update")
            else:
                patch_parts.append("preserve active-state Next Action")
        if sync_global and route_status in {"resolved", "single_runtime"}:
            patch_parts.append("sync public-safe registry projection")
        elif sync_global:
            patch_parts.append(f"block global sync on {route_status} runtime projection route")
        if shared_runtime_root:
            patch_parts.append("project compact refresh to registered shared runtime")
        payload["local_state_write_correctness"] = build_local_state_write_correctness_dry_run_packet(
            goal_id=safe_goal_id,
            writer_id=normalized_agent_id or "loopx.refresh-state",
            write_class="refresh_state",
            state_text=expected_write_state_text,
            target_refs={
                "state_file_ref": "registry.goal.state_file",
                "run_history_ref": "runtime.goal.runs",
                "index_ref": "runtime.goal.runs.index",
                "global_registry_ref": (
                    "runtime.registry.global"
                    if sync_global and route_status in {"resolved", "single_runtime"}
                    else None
                ),
                "shared_runtime_projection_ref": (
                    "shared_runtime.goal.runs.index" if shared_runtime_root else None
                ),
            },
            patch_summary="; ".join(patch_parts),
            expected_write_scopes=expected_write_scopes,
            lease_ref=None,
            projection_status_surface=f"refresh-state dry-run: {classification}",
        )
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
    if sync_global and route_status in {"missing", "ambiguous"}:
        payload["ok"] = False
        payload["partial_write"] = not dry_run
        payload["global_sync"] = {
            "ok": False,
            "enabled": False,
            "wrote": False,
            "reason": f"runtime projection route is {route_status}",
            "route_status": route_status,
        }
        payload["shared_runtime_projection"] = {
            "ok": False,
            "status": f"route_{route_status}",
            "dry_run": dry_run,
            "raw_artifacts_copied": False,
            "recommended_action_copied": False,
            "runtime_projection_route_id": compact_route.get("route_id"),
        }
    elif sync_global:
        payload["global_sync"] = sync_project_registry_to_global(
            registry_path=registry_path,
            runtime_root_override=str(global_sync_runtime_root or runtime_root),
            goal_id=safe_goal_id,
            dry_run=dry_run,
        )
        if shared_runtime_root and payload["global_sync"].get("ok"):
            projection_record, projection_index = build_shared_runtime_projection(
                record=record,
            )
            try:
                payload["shared_runtime_projection"] = write_shared_runtime_projection(
                    shared_runtime_root=shared_runtime_root,
                    goal_id=safe_goal_id,
                    record=projection_record,
                    index_record=projection_index,
                    dry_run=dry_run,
                )
            except OSError as exc:
                payload["ok"] = False
                payload["partial_write"] = not dry_run
                payload["shared_runtime_projection"] = {
                    "ok": False,
                    "status": "write_failed",
                    "dry_run": dry_run,
                    "shared_runtime_root": str(shared_runtime_root),
                    "raw_artifacts_copied": False,
                    "recommended_action_copied": False,
                    "error": str(exc),
                }
        elif shared_runtime_root:
            payload["ok"] = False
            payload["partial_write"] = not dry_run
            payload["shared_runtime_projection"] = {
                "ok": False,
                "status": "blocked_by_global_sync",
                "dry_run": dry_run,
                "shared_runtime_root": str(shared_runtime_root),
                "raw_artifacts_copied": False,
                "recommended_action_copied": False,
            }
        else:
            payload["shared_runtime_projection"] = {
                "ok": True,
                "status": "not_required",
                "dry_run": dry_run,
                "raw_artifacts_copied": False,
                "recommended_action_copied": False,
            }
    else:
        payload["global_sync"] = {
            "enabled": False,
            "global_registry": str(runtime_root / "registry.global.json"),
            "synced_goal_ids": [],
            "wrote": False,
        }
        payload["shared_runtime_projection"] = {
            "ok": True,
            "status": "disabled",
            "dry_run": dry_run,
            "raw_artifacts_copied": False,
            "recommended_action_copied": False,
        }
    return payload
