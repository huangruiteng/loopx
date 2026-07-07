"""Public-safe SkillsBench task source classification helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _public_task_label(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    cleaned = [
        char.lower() if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in text
    ]
    label = "".join(cleaned).strip("-_.")
    while "--" in label:
        label = label.replace("--", "-")
    return label[:limit]


def _public_registry_path(value: Any, *, limit: int = 200) -> str:
    text = str(value or "").strip().replace("\\", "/")
    parts = [
        _public_task_label(part, limit=80)
        for part in text.split("/")
        if part.strip()
    ]
    return "/".join(part for part in parts if part)[:limit]


def _registry_source_metadata(
    *,
    skillsbench_root: Path,
    task_id: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "registry_task_present": False,
        "registry_task_path_recorded": False,
        "registry_task_path": "",
        "registry_excluded": False,
        "registry_source_kind": "none",
        "registry_source_status": "missing",
    }
    registry_path = (
        skillsbench_root.expanduser()
        / "website"
        / "src"
        / "data"
        / "tasks-registry.json"
    )
    if not registry_path.exists():
        return metadata
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["registry_source_status"] = "unreadable"
        return metadata
    entries = raw if isinstance(raw, list) else None
    if isinstance(raw, dict):
        entries = raw.get("tasks") or raw.get("entries") or raw.get("data")
    if not isinstance(entries, list):
        metadata["registry_source_status"] = "unsupported_shape"
        return metadata
    requested = _public_task_label(task_id)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        registry_path_text = _public_registry_path(entry.get("path"))
        candidates = {
            _public_task_label(entry.get(key))
            for key in ("id", "task_id", "name", "title", "slug")
        }
        if registry_path_text:
            candidates.add(Path(registry_path_text).name)
        if requested not in candidates:
            continue
        source_kind = "other"
        if registry_path_text.startswith("tasks/"):
            source_kind = "tasks"
        elif registry_path_text.startswith("tasks-extra/"):
            source_kind = "tasks_extra"
        elif registry_path_text.startswith("experiments/sanity-tasks/"):
            source_kind = "experiments_sanity_tasks"
        return {
            **metadata,
            "registry_task_present": True,
            "registry_task_path_recorded": bool(registry_path_text),
            "registry_task_path": registry_path_text,
            "registry_excluded": entry.get("excluded") is True,
            "registry_source_kind": source_kind,
            "registry_source_status": "matched",
        }
    metadata["registry_source_status"] = "not_found"
    return metadata


def classify_missing_task_source(
    *,
    skillsbench_root: Path,
    task_id: str,
    sanity_task_exists: bool,
    canonical_equivalent_status: str,
) -> dict[str, Any]:
    registry_source = _registry_source_metadata(
        skillsbench_root=skillsbench_root,
        task_id=task_id,
    )
    if sanity_task_exists:
        alternate_source_kind = "experiments_sanity_tasks"
    elif registry_source.get("registry_source_kind") == "tasks_extra":
        alternate_source_kind = "tasks_extra"
    else:
        alternate_source_kind = "none"
    source_is_excluded = (
        registry_source.get("registry_source_kind") == "tasks_extra"
        and registry_source.get("registry_excluded") is True
    )
    return {
        **registry_source,
        "status": (
            "task_excluded_from_formal_tasks"
            if source_is_excluded
            else "task_missing_from_canonical_tasks"
        ),
        "first_blocker": (
            "skillsbench_task_source_excluded"
            if source_is_excluded
            else "skillsbench_task_source_preflight_blocked"
        ),
        "alternate_source_kind": alternate_source_kind,
        "selection_recommendation": (
            "excluded_tasks_extra_requires_explicit_sanity_source_mode"
            if source_is_excluded
            else (
                "choose_nearest_canonical_task_candidate_or_use_explicit_sanity_source_runner"
                if canonical_equivalent_status == "close_canonical_match_found"
                else "no_close_canonical_task_match_choose_normal_tasks_candidate_or_explicit_sanity_source_runner"
            )
        ),
    }
