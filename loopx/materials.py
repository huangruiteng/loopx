from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .registry import registry_goals, resolve_state_file


MARKDOWN_SUFFIXES = {".md", ".markdown"}
MAX_REVIEW_MATERIAL_BYTES = 256_000
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+?\.(?:md|markdown)(?:#[^)]+)?)\)", re.I)
BACKTICK_MARKDOWN_PATTERN = re.compile(r"`([^`]+?\.(?:md|markdown)(?:#[^`]*)?)`", re.I)


def split_material_reference(raw: str) -> tuple[str, str | None]:
    text = unquote(raw.strip().strip("<>"))
    if "#" not in text:
        return text, None
    path, anchor = text.split("#", 1)
    return path, anchor or None


def is_markdown_path(raw_path: str) -> bool:
    parsed = urlparse(raw_path)
    if parsed.scheme and parsed.scheme not in {"file"}:
        return False
    path, _anchor = split_material_reference(parsed.path if parsed.scheme == "file" else raw_path)
    return Path(path).suffix.lower() in MARKDOWN_SUFFIXES


def find_registry_goal(registry: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    for goal in registry_goals(registry):
        if str(goal.get("id") or "") == goal_id:
            return goal
    return None


def goal_repo(goal: dict[str, Any]) -> Path | None:
    repo = goal.get("repo")
    return Path(str(repo)).expanduser() if repo else None


def goal_state_path(goal: dict[str, Any]) -> Path | None:
    repo = goal_repo(goal)
    if not repo:
        return None
    return resolve_state_file(repo, goal.get("state_file"))


def material_roots(goal: dict[str, Any], *, runtime_root: Path | None = None, state_path: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    repo = goal_repo(goal)
    if repo:
        roots.append(repo)
    resolved_state_path = state_path or goal_state_path(goal)
    if resolved_state_path:
        roots.append(resolved_state_path.parent)
    if runtime_root:
        goal_id = str(goal.get("id") or "")
        if goal_id:
            roots.append(runtime_root / "goals" / goal_id)

    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            deduped.append(resolved)
    return deduped


def path_is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_review_material_path(
    *,
    goal: dict[str, Any],
    raw_path: str,
    runtime_root: Path | None = None,
    state_path: Path | None = None,
) -> Path:
    parsed = urlparse(raw_path)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("review material must be a local Markdown path, not a URL")
    path_text, _anchor = split_material_reference(parsed.path if parsed.scheme == "file" else raw_path)
    if not is_markdown_path(path_text):
        raise ValueError("review material must end with .md or .markdown")

    roots = material_roots(goal, runtime_root=runtime_root, state_path=state_path)
    if not roots:
        raise ValueError("goal has no repo/state/runtime root for review material resolution")

    raw = Path(path_text).expanduser()
    if raw.is_absolute():
        candidate = raw.resolve()
        if any(path_is_under(candidate, root) for root in roots):
            return candidate
        raise ValueError("review material path is outside the goal repo/state/runtime roots")

    candidates = [(root, (root / raw).resolve()) for root in roots]
    safe_candidates = [(root, candidate) for root, candidate in candidates if path_is_under(candidate, root)]
    if not safe_candidates:
        raise ValueError("review material path is outside the goal repo/state/runtime roots")
    for _root, candidate in safe_candidates:
        if candidate.exists():
            return candidate
    return safe_candidates[0][1]


def extract_review_materials(
    text: str,
    *,
    goal: dict[str, Any],
    state_path: Path | None = None,
) -> list[dict[str, Any]]:
    matches: list[tuple[str, str]] = []
    for match in MARKDOWN_LINK_PATTERN.finditer(text):
        label, path = match.groups()
        matches.append((label.strip() or Path(path).name, path.strip()))
    for match in BACKTICK_MARKDOWN_PATTERN.finditer(text):
        path = match.group(1).strip()
        matches.append((Path(split_material_reference(path)[0]).name, path))

    materials: list[dict[str, Any]] = []
    seen: set[str] = set()
    for label, raw_path in matches:
        path_text, anchor = split_material_reference(raw_path)
        if not is_markdown_path(path_text):
            continue
        key = f"{path_text}#{anchor or ''}"
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved = resolve_review_material_path(goal=goal, raw_path=raw_path, state_path=state_path)
            exists = resolved.exists()
        except ValueError:
            resolved = None
            exists = False
        item: dict[str, Any] = {
            "label": label or Path(path_text).name,
            "path": raw_path,
            "exists": exists,
        }
        if anchor:
            item["anchor"] = anchor
        if resolved is not None:
            item["resolved_path"] = str(resolved)
        materials.append(item)
    return materials


def read_review_material(
    *,
    registry: dict[str, Any],
    runtime_root: Path | None,
    goal_id: str,
    raw_path: str,
) -> dict[str, Any]:
    goal = find_registry_goal(registry, goal_id)
    if goal is None:
        raise ValueError(f"goal {goal_id!r} is not present in the registry")
    resolved = resolve_review_material_path(goal=goal, raw_path=raw_path, runtime_root=runtime_root)
    if not resolved.exists():
        raise FileNotFoundError(f"review material does not exist: {raw_path}")
    if resolved.stat().st_size > MAX_REVIEW_MATERIAL_BYTES:
        raise ValueError(f"review material is too large; limit is {MAX_REVIEW_MATERIAL_BYTES} bytes")
    content = resolved.read_text(encoding="utf-8")
    return {
        "ok": True,
        "goal_id": goal_id,
        "path": raw_path,
        "resolved_path": str(resolved),
        "bytes": len(content.encode("utf-8")),
        "content": content,
    }
