from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .feedback import validate_public_safe_text
from .global_registry import sync_project_registry_to_global
from .history import load_registry
from .paths import resolve_runtime_root
from .registry import registry_goals, resolve_state_file
from .runtime import validate_goal_id_path_segment


DEFAULT_REFRESH_CLASSIFICATION = "state_refreshed"
DEFAULT_REFRESH_ACTION = "inspect refreshed active goal state and continue the next bounded progress segment"
BULLET_PREFIX_RE = re.compile(r"^(?:[-*]\s+|\d+[.)]\s+)")


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


def clean_action_line(line: str) -> str:
    return BULLET_PREFIX_RE.sub("", line.strip()).strip()


def is_bullet_line(line: str) -> bool:
    return bool(BULLET_PREFIX_RE.match(line.strip()))


def first_action_item(lines: list[str], start: int) -> str:
    first_line = lines[start]
    parts = [clean_action_line(first_line)]
    if is_bullet_line(first_line):
        for line in lines[start + 1 :]:
            if is_bullet_line(line):
                break
            cleaned = clean_action_line(line)
            if cleaned:
                parts.append(cleaned)
    return " ".join(part for part in parts if part).strip()


def derive_recommended_action(state_text: str) -> str:
    lines = extract_section_lines(state_text, "Next Action", limit=8)
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
) -> dict[str, Any]:
    frontmatter = parse_frontmatter(state_text)
    next_action = extract_section_lines(state_text, "Next Action")
    recent_feedback = extract_section_lines(state_text, "Recent User Feedback", limit=5)
    progress = extract_section_lines(state_text, "Progress Ledger", limit=5)
    digest = hashlib.sha256(state_text.encode("utf-8")).hexdigest()[:16]
    authority_sources = []
    if registry_goal and isinstance(registry_goal.get("authority_sources"), list):
        authority_sources = registry_goal.get("authority_sources") or []
    return {
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


def render_state_refresh_markdown(payload: dict[str, Any]) -> str:
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    frontmatter = state.get("frontmatter") if isinstance(state.get("frontmatter"), dict) else {}
    lines = [
        "# Goal Harness State Refresh",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- state_file: `{state.get('path')}`",
        f"- state_updated_at: `{frontmatter.get('updated_at')}`",
        f"- health_check: `{payload.get('health_check')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)

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
            lines.extend(f"- {clean_action_line(value)}" for value in values)
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
    dry_run: bool,
    sync_global: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    validate_public_safe_text("classification", classification)
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
    action = recommended_action or derive_recommended_action(state_text)
    validate_public_safe_text("recommended_action", action)
    generated_at = now_local()
    record = build_state_refresh_record(
        goal_id=safe_goal_id,
        state_file=resolved_state_file,
        state_text=state_text,
        classification=classification,
        recommended_action=action,
        generated_at=generated_at,
        registry_goal=registry_goal,
    )

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    stem = run_file_stem(generated_at)
    json_path = runs_dir / f"{stem}.json"
    markdown_path = runs_dir / f"{stem}.md"
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
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "project": str(resolved_project) if resolved_project else None,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "generated_at": generated_at,
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        **record,
    }
    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
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
