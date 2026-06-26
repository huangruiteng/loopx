from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .history import collect_history, load_registry
from .paths import DEFAULT_RUNTIME_ROOT, rel_or_abs, resolve_runtime_root
from .registry import inspect_registry, inspect_registry_boundary


LEAK_PATTERNS = {
    "private_doc_url": re.compile(
        "|".join(["la" + "rk" + "office", "docs" + r"\." + "internal"]),
        re.I,
    ),
    "credential": re.compile(
        "|".join(
            [
                "Bear" + "er" + r"\s+[A-Za-z0-9._-]+",
                "AK" + "IA" + r"[0-9A-Z]{16}",
                "tok" + "en=",
                "pass" + "word=",
                "Author" + "ization:",
            ]
        ),
        re.I,
    ),
    "local_private_path": re.compile(
        "(" + "/" + "Users" + "/" + r"[^/\s]+/(?:Documents|code" + "-" + r"reading)|" + "/ext" + "_data/" + ")"
    ),
    "internal_task_id": re.compile(r"\bt-" + r"20\d{12}-[a-z0-9]+\b"),
    "private_ip": re.compile(r"\b10\.\d+\.\d+\.\d+\b|\b172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+\b|\b192\.168\.\d+\.\d+\b"),
}

DEFAULT_SCAN_SUFFIXES = {".md", ".py", ".toml", ".json", ".yaml", ".yml", ".sh"}
DEFAULT_SKIP_DIRS = {
    ".git",
    ".goal-harness",
    ".loopx",
    ".goal-wrapper.local",
    ".local",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "node_modules",
    "runtime",
}
LOCAL_PRIVATE_STATE_PARTS = {
    ".codex",
    ".goal-harness",
    ".goal-wrapper.local",
    ".local",
    ".loopx",
    "logs",
    "runtime",
}
LOCAL_PRIVATE_STATE_FILE_NAMES = {"ACTIVE_GOAL_STATE.md", "ACTIVE_GOAL_STATE.md.lock"}


def _git_probe(path: Path) -> dict[str, Any]:
    target = path if path.is_dir() else path.parent
    try:
        root = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"inside_worktree": False, "tracked": False, "ignored": False}

    repo_root = Path(root)
    try:
        rel_path = str(path.relative_to(repo_root))
    except ValueError:
        rel_path = str(path)
    tracked = (
        subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", rel_path],
            text=True,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    ignored = (
        subprocess.run(
            ["git", "-C", str(repo_root), "check-ignore", "-q", "--", rel_path],
            text=True,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    return {
        "inside_worktree": True,
        "root": str(repo_root),
        "tracked": tracked,
        "ignored": ignored,
    }


def _is_local_private_state_path(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & LOCAL_PRIVATE_STATE_PARTS) or path.name in LOCAL_PRIVATE_STATE_FILE_NAMES


def _public_boundary_policy(registry: dict[str, Any]) -> dict[str, str]:
    policy = registry.get("public_boundary") if isinstance(registry, dict) else None
    if not isinstance(policy, dict):
        policy = registry.get("privacy") if isinstance(registry, dict) else None
    if not isinstance(policy, dict):
        policy = {}

    tracked_private_doc_urls = "block"
    raw_mode = (
        policy.get("tracked_private_doc_urls")
        or policy.get("private_doc_urls_in_tracked_files")
    )
    if str(raw_mode).lower() == "allow" or policy.get("allow_tracked_private_doc_urls") is True:
        tracked_private_doc_urls = "allow"

    return {
        "schema_version": "loopx_public_boundary_policy_v0",
        "tracked_private_doc_urls": tracked_private_doc_urls,
    }


def _hit_allowed_by_policy(name: str, git: dict[str, Any], policy: dict[str, str]) -> bool:
    if name != "private_doc_url":
        return False
    if not git.get("tracked"):
        return False
    return policy.get("tracked_private_doc_urls") == "allow"


def _index_duplicate_summary(index_path: Path) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    if not index_path.exists():
        return {
            "duplicate_rows": 0,
            "reward_overlay_rows": 0,
            "unexpected_duplicate_rows": 0,
        }

    with index_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("generated_at") or ""),
                str(item.get("json_path") or ""),
                str(item.get("markdown_path") or ""),
            )
            groups.setdefault(key, []).append(item)

    reward_overlay_rows = 0
    unexpected_duplicate_rows = 0
    for records in groups.values():
        if len(records) <= 1:
            continue
        duplicate_rows = len(records) - 1
        normalized = []
        reward_records = 0
        for record in records:
            if isinstance(record.get("human_reward"), dict):
                reward_records += 1
            normalized.append({key: value for key, value in record.items() if key != "human_reward"})
        normalized_keys = {json.dumps(record, sort_keys=True, ensure_ascii=False) for record in normalized}
        if reward_records and len(normalized_keys) == 1:
            reward_overlay_rows += duplicate_rows
        else:
            unexpected_duplicate_rows += duplicate_rows

    return {
        "duplicate_rows": reward_overlay_rows + unexpected_duplicate_rows,
        "reward_overlay_rows": reward_overlay_rows,
        "unexpected_duplicate_rows": unexpected_duplicate_rows,
    }


def _index_duplicate_warning(goal_id: object, raw: int, unique: int) -> str:
    safe_goal_id = str(goal_id)
    return (
        f"{safe_goal_id}: duplicate index rows raw={raw} unique={unique}; "
        f"inspect with `loopx history inspect-index-duplicates --goal-id {safe_goal_id}`"
    )


def iter_scan_files(scan_root: Path) -> list[Path]:
    if scan_root.is_file():
        return [scan_root]
    files: list[Path] = []
    root_parts = set(scan_root.parts)
    if any(part in DEFAULT_SKIP_DIRS or part.endswith(".egg-info") for part in root_parts):
        return files

    for dir_path, dir_names, file_names in os.walk(scan_root):
        dir_names[:] = [
            name
            for name in dir_names
            if name not in DEFAULT_SKIP_DIRS and not name.endswith(".egg-info")
        ]
        current_dir = Path(dir_path)
        for file_name in file_names:
            path = current_dir / file_name
            if path.name.endswith(".local.json"):
                continue
            if path.suffix in DEFAULT_SCAN_SUFFIXES:
                files.append(path)
    return sorted(files)


def scan_public_boundary(
    scan_roots: list[Path], *, registry: dict[str, Any] | None = None
) -> dict[str, Any]:
    hits: list[str] = []
    allowed_hits: list[str] = []
    private_state_git_warnings: list[str] = []
    skipped_private_state_files: list[str] = []
    files: list[Path] = []
    file_roots: dict[Path, Path] = {}
    for scan_root in scan_roots:
        display_root = scan_root.parent if scan_root.is_file() else scan_root
        for file_path in iter_scan_files(scan_root):
            files.append(file_path)
            file_roots[file_path] = display_root
    files = sorted(set(files))
    policy = _public_boundary_policy(registry or {})

    for path in files:
        root = file_roots.get(path, path)
        git: dict[str, Any] | None = None
        if _is_local_private_state_path(path):
            git = _git_probe(path)
            if not git.get("tracked"):
                skipped_private_state_files.append(rel_or_abs(path, root))
                if git.get("inside_worktree") and not git.get("ignored"):
                    private_state_git_warnings.append(
                        f"{rel_or_abs(path, root)}: private state should be gitignored"
                    )
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in LEAK_PATTERNS.items():
                if pattern.search(line):
                    hit = f"{rel_or_abs(path, root)}:{line_no}: {name}"
                    if name == "private_doc_url":
                        git = git or _git_probe(path)
                    if git is not None and _hit_allowed_by_policy(name, git, policy):
                        allowed_hits.append(hit)
                    else:
                        hits.append(hit)
    return {
        "ok": not hits,
        "scan_roots": [str(path) for path in scan_roots],
        "files": len(files),
        "scanned_files": len(files) - len(skipped_private_state_files),
        "skipped_private_state_files": skipped_private_state_files,
        "allowed_hits": allowed_hits,
        "private_state_git_warnings": private_state_git_warnings,
        "policy": policy,
        "hits": hits,
    }


def check_contract(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
    allow_missing_registry: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    registry_payload = inspect_registry(registry_path)
    if registry_payload.get("ok"):
        checks.append(f"registry goals checked: {registry_payload.get('goal_count')}")
    else:
        if registry_payload.get("error"):
            error = str(registry_payload.get("error"))
            if allow_missing_registry and error == "registry file does not exist":
                warnings.append(f"{error}: {registry_path}")
            else:
                errors.append(error)
        errors.extend(str(item) for item in registry_payload.get("problems") or [])

    boundary_payload = inspect_registry_boundary(registry_path)
    if boundary_payload.get("ok"):
        git = boundary_payload.get("git") if isinstance(boundary_payload.get("git"), dict) else {}
        checks.append(
            "registry boundary: "
            f"{boundary_payload.get('classification')} "
            f"push_allowed={boundary_payload.get('github_push_allowed')} "
            f"tracked={git.get('tracked')} ignored={git.get('ignored')}"
        )
        if boundary_payload.get("should_be_gitignored") and git.get("inside_worktree"):
            if not git.get("ignored") and not git.get("tracked"):
                warnings.append(f"registry should be gitignored: {registry_path}")
    else:
        if boundary_payload.get("error"):
            warnings.append(f"registry boundary unavailable: {boundary_payload.get('error')}")
        for risk in boundary_payload.get("risks") or []:
            errors.append(f"registry boundary risk: {risk}")

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    if runtime_root == DEFAULT_RUNTIME_ROOT or runtime_root.exists():
        checks.append(f"runtime root resolved: {runtime_root}")
    else:
        warnings.append(f"runtime root does not exist yet: {runtime_root}")

    history = collect_history(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=None,
        limit=limit,
    )
    checks.append(f"run-history goals={history.get('goal_count')} runs={history.get('run_count')}")
    for item in history.get("goals") or []:
        raw = int(item.get("raw_index_records") or 0)
        unique = int(item.get("unique_runs") or 0)
        if item.get("legacy_runtime_goal") and raw > unique:
            checks.append(f"{item.get('id')}: legacy runtime goal has duplicate rows raw={raw} unique={unique}")
            continue
        if raw > unique:
            duplicate_summary = _index_duplicate_summary(Path(str(item.get("index_path") or "")))
            if duplicate_summary.get("unexpected_duplicate_rows"):
                warnings.append(_index_duplicate_warning(item.get("id"), raw, unique))
            elif duplicate_summary.get("reward_overlay_rows"):
                checks.append(
                    f"{item.get('id')}: reward overlay rows raw={raw} unique={unique} "
                    f"overlays={duplicate_summary.get('reward_overlay_rows')}"
                )
            else:
                warnings.append(_index_duplicate_warning(item.get("id"), raw, unique))

    boundary = scan_public_boundary(scan_roots, registry=registry)
    if boundary.get("ok"):
        checks.append(f"public boundary scan clean: {boundary.get('scanned_files')} files")
    else:
        errors.extend(str(item) for item in boundary.get("hits") or [])
    if boundary.get("skipped_private_state_files"):
        checks.append(
            "private state scan skipped: "
            f"{len(boundary.get('skipped_private_state_files') or [])} local-private files"
        )
    if boundary.get("allowed_hits"):
        checks.append(
            "public boundary policy allowed: "
            f"{len(boundary.get('allowed_hits') or [])} private_doc_url hits"
        )
    warnings.extend(str(item) for item in boundary.get("private_state_git_warnings") or [])

    return {
        "ok": not errors,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "scan_roots": [str(path) for path in scan_roots],
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "checks": len(checks),
        },
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def render_contract_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Contract Check",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- scan_roots: `{payload.get('scan_roots')}`",
    ]
    summary = payload.get("summary") or {}
    lines.append(
        f"- summary: errors={summary.get('errors')}, warnings={summary.get('warnings')}, checks={summary.get('checks')}"
    )
    for title, key in (("Errors", "errors"), ("Warnings", "warnings"), ("Checks", "checks")):
        items = payload.get(key) or []
        if items:
            lines.extend(["", f"## {title}"])
            lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)
