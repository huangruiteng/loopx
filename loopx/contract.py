from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .agent_registry import registered_agent_ids_for_goal
from .control_plane.runtime.run_index_duplicates import (
    classify_index_duplicate_records,
    index_identity,
)
from .control_plane.todos.active_state_editing import COMPLETED_WORK_ARCHIVE_HEADING
from .history import collect_history, load_registry
from .paths import DEFAULT_RUNTIME_ROOT, rel_or_abs, resolve_runtime_root
from .registry import inspect_registry, inspect_registry_boundary, registry_goals, resolve_state_file
from .state_projection import state_projection_gap_warning
from .control_plane.todos.contract import (
    TODO_STATUS_DEFERRED,
    TODO_STATUS_DONE,
    TODO_METADATA_PATTERN,
    TODO_TASK_CLASS_USER_ACTION,
    TODO_TASK_CLASS_USER_GATE,
    TODO_TASK_PATTERN,
    decode_metadata_value,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_excluded_agents,
    normalize_todo_goal_bound,
    normalize_removed_todo_continuation_policy,
    normalize_todo_status,
    parse_todo_metadata_line,
    parse_todo_metadata_tokens,
    require_todo_excluded_agents,
    todo_status_from_marker,
)


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
                r"(?<![A-Za-z0-9_])" + "tok" + "en=",
                r"(?<![A-Za-z0-9_])" + "pass" + "word=",
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
TERMINAL_TODO_STATUSES = {TODO_STATUS_DONE, TODO_STATUS_DEFERRED, "completed", "closed", "archived"}


def _git_probe(path: Path) -> dict[str, Any]:
    path = path.resolve()
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

    repo_root = Path(root).resolve()
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
            "structured_artifact_bundle_rows": 0,
            "unexpected_duplicate_rows": 0,
            "repairable_duplicate_rows": 0,
            "artifact_identity_collision_rows": 0,
            "artifact_identity_collision_groups": 0,
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
            groups.setdefault(index_identity(item), []).append(item)

    reward_overlay_rows = 0
    structured_artifact_bundle_rows = 0
    unexpected_duplicate_rows = 0
    repairable_duplicate_rows = 0
    artifact_identity_collision_rows = 0
    artifact_identity_collision_groups = 0
    for records in groups.values():
        if len(records) <= 1:
            continue
        duplicate_rows = len(records) - 1
        duplicate_classification = classify_index_duplicate_records(records)
        duplicate_kind = duplicate_classification.get("duplicate_kind")
        if duplicate_kind == "reward_overlay":
            reward_overlay_rows += duplicate_rows
        elif duplicate_kind == "structured_artifact_bundle":
            structured_artifact_bundle_rows += duplicate_rows
        elif duplicate_classification.get("repairable"):
            unexpected_duplicate_rows += duplicate_rows
            repairable_duplicate_rows += duplicate_rows
        else:
            unexpected_duplicate_rows += duplicate_rows
            artifact_identity_collision_rows += duplicate_rows
            artifact_identity_collision_groups += 1

    return {
        "duplicate_rows": reward_overlay_rows + structured_artifact_bundle_rows + unexpected_duplicate_rows,
        "reward_overlay_rows": reward_overlay_rows,
        "structured_artifact_bundle_rows": structured_artifact_bundle_rows,
        "unexpected_duplicate_rows": unexpected_duplicate_rows,
        "repairable_duplicate_rows": repairable_duplicate_rows,
        "artifact_identity_collision_rows": artifact_identity_collision_rows,
        "artifact_identity_collision_groups": artifact_identity_collision_groups,
    }


def _index_duplicate_warning(
    goal_id: object,
    raw: int,
    unique: int,
    duplicate_summary: dict[str, Any] | None = None,
) -> str:
    safe_goal_id = str(goal_id)
    duplicate_summary = duplicate_summary or {}
    detail_parts = []
    unexpected_rows = int(duplicate_summary.get("unexpected_duplicate_rows") or 0)
    repairable_rows = int(duplicate_summary.get("repairable_duplicate_rows") or 0)
    artifact_collision_rows = int(duplicate_summary.get("artifact_identity_collision_rows") or 0)
    artifact_collision_groups = int(duplicate_summary.get("artifact_identity_collision_groups") or 0)
    reward_overlay_rows = int(duplicate_summary.get("reward_overlay_rows") or 0)
    structured_artifact_bundle_rows = int(duplicate_summary.get("structured_artifact_bundle_rows") or 0)
    if unexpected_rows:
        detail_parts.append(f"unexpected={unexpected_rows}")
    if repairable_rows:
        detail_parts.append(f"auto_repairable={repairable_rows}")
    if artifact_collision_groups:
        detail_parts.append(f"artifact_identity_collisions={artifact_collision_groups}")
    if artifact_collision_rows:
        detail_parts.append(f"artifact_collision_rows={artifact_collision_rows}")
    if reward_overlay_rows:
        detail_parts.append(f"reward_overlays={reward_overlay_rows}")
    if structured_artifact_bundle_rows:
        detail_parts.append(f"structured_artifact_bundles={structured_artifact_bundle_rows}")
    if not detail_parts and raw > unique:
        detail_parts.append(f"duplicates={raw - unique}")
    detail = f" {' '.join(detail_parts)}" if detail_parts else ""
    inspect_command = f"`loopx history --goal-id {safe_goal_id} inspect-index-duplicates`"
    repair_command = f"`loopx history --goal-id {safe_goal_id} repair-index-duplicates`"
    if artifact_collision_rows:
        action = (
            f"inspect with {inspect_command}; artifact identity collisions need reviewed merge semantics"
        )
        if repairable_rows:
            action += f"; preview safe repair for auto-repairable rows with {repair_command}"
    else:
        action = f"inspect with {inspect_command}; preview repair with {repair_command}"
    return f"{safe_goal_id}: duplicate index rows raw={raw} unique={unique}{detail}; {action}"


def _active_state_user_gate_scope_errors(registry: dict[str, Any]) -> tuple[list[str], int]:
    errors: list[str] = []
    checked = 0
    for goal in registry_goals(registry):
        goal_id = str(goal.get("id") or "")
        registered_agents = registered_agent_ids_for_goal(goal)
        repo_text = str(goal.get("repo") or "").strip()
        if not repo_text:
            continue
        state_file = resolve_state_file(Path(repo_text).expanduser(), goal.get("state_file"))
        if not state_file or not state_file.exists():
            continue
        try:
            lines = state_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{goal_id}: cannot read active state for user-gate scope check: {exc}")
            continue

        role: str | None = None
        in_completed_work_archive = False
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.startswith("## "):
                heading_text = line.lstrip("#").strip()
                heading = heading_text.lower()
                in_completed_work_archive = (
                    heading_text.casefold() == COMPLETED_WORK_ARCHIVE_HEADING.casefold()
                )
                if "user todo" in heading or "owner review" in heading:
                    role = "user"
                elif "agent todo" in heading:
                    role = "agent"
                else:
                    role = None
                index += 1
                continue
            match = TODO_TASK_PATTERN.match(line)
            if not match:
                index += 1
                continue
            marker, text = match.groups()
            metadata: dict[str, Any] = {}
            malformed_excluded_agents = False
            malformed_status = False
            next_index = index + 1
            while next_index < len(lines):
                if lines[next_index].startswith("## ") or TODO_TASK_PATTERN.match(lines[next_index]):
                    break
                raw_line = lines[next_index]
                raw_metadata = parse_todo_metadata_tokens(raw_line)
                metadata_match = TODO_METADATA_PATTERN.match(raw_line)
                if metadata_match:
                    for raw_field in metadata_match.group("body").split():
                        if not raw_field.startswith("status="):
                            continue
                        raw_status = decode_metadata_value(raw_field.split("=", 1)[1])
                        if normalize_todo_status(raw_status) is None:
                            malformed_status = True
                for key, value in raw_metadata or []:
                    if key == "status" and normalize_todo_status(value) is None:
                        malformed_status = True
                    if key not in {"excluded_agent", "excluded_agents"}:
                        continue
                    try:
                        require_todo_excluded_agents(value)
                    except ValueError:
                        malformed_excluded_agents = True
                parsed = parse_todo_metadata_line(raw_line)
                if parsed:
                    metadata.update(parsed)
                next_index += 1
            removed_continuation_policy = normalize_removed_todo_continuation_policy(
                metadata.get("removed_continuation_policy")
            )
            status = str(metadata.get("status") or todo_status_from_marker(marker) or "").lower()
            task_class = str(metadata.get("task_class") or "")
            todo_id = metadata.get("todo_id") or f"line:{index + 1}"
            if malformed_excluded_agents:
                errors.append(
                    f"{goal_id}: todo {todo_id} has malformed excluded_agents metadata; "
                    "replace it with --excluded-agent <registered-agent> or remove it "
                    "with --clear-excluded-agents"
                )
            if malformed_status:
                errors.append(
                    f"{goal_id}: todo {todo_id} has malformed status metadata; "
                    "replace it with status=open, status=done, status=blocked, or "
                    "status=deferred"
                )
            if role == "agent" and removed_continuation_policy:
                errors.append(
                    f"{goal_id}: agent todo {todo_id} uses removed continuation_policy="
                    f"{removed_continuation_policy}; use continuation_policy=independent_handoff "
                    "with an explicit review action_kind and excluded_agents=<author> only when "
                    "executor separation is required"
                )
            blocks_agent = metadata.get("blocks_agent")
            if role == "agent" and blocks_agent:
                errors.append(
                    f"{goal_id}: agent todo {todo_id} uses removed blocks_agent routing; "
                    "blocks_agent is reserved for user gates, while agent executor "
                    "constraints use excluded_agents"
                )
            excluded_agents = normalize_todo_excluded_agents(
                metadata.get("excluded_agents")
            )
            claimed_by = normalize_todo_claimed_by(metadata.get("claimed_by"))
            if claimed_by and claimed_by in excluded_agents:
                errors.append(
                    f"{goal_id}: agent todo {todo_id} has claimed_by={claimed_by!r} "
                    "also listed in excluded_agents"
                )
            archived_terminal_todo = (
                in_completed_work_archive
                and todo_status_from_marker(marker) in TERMINAL_TODO_STATUSES
                and status in TERMINAL_TODO_STATUSES
            )
            if role != "agent" and excluded_agents and not archived_terminal_todo:
                errors.append(
                    f"{goal_id}: {role or 'unscoped'} todo {todo_id} uses excluded_agents; "
                    "executor exclusions are only valid for agent todos"
                )
            unknown_excluded_agents = [
                agent_id
                for agent_id in excluded_agents
                if registered_agents and agent_id not in registered_agents
            ]
            if role == "agent" and unknown_excluded_agents:
                errors.append(
                    f"{goal_id}: agent todo {todo_id} excludes unregistered agents: "
                    + ", ".join(unknown_excluded_agents)
                )
            if role == "user" and status not in TERMINAL_TODO_STATUSES:
                checked += 1
                global_gate = metadata.get("global_gate") is True
                bound_agent = normalize_todo_bound_agent(metadata.get("bound_agent"))
                goal_bound = normalize_todo_goal_bound(metadata.get("goal_bound")) is True
                effective_bound_agent = (
                    bound_agent
                    or (
                        blocks_agent
                        if task_class == TODO_TASK_CLASS_USER_GATE
                        else None
                    )
                    or claimed_by
                )
                effective_goal_bound = bool(
                    goal_bound
                    or (
                        global_gate
                        and task_class == TODO_TASK_CLASS_USER_GATE
                    )
                )
                if task_class not in {TODO_TASK_CLASS_USER_ACTION, TODO_TASK_CLASS_USER_GATE}:
                    errors.append(
                        f"{goal_id}: open user todo {todo_id} requires task_class=user_gate "
                        "or task_class=user_action "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif task_class == TODO_TASK_CLASS_USER_ACTION and (blocks_agent or global_gate):
                    errors.append(
                        f"{goal_id}: open user_action todo {todo_id} is non-blocking and "
                        "cannot set blocks_agent or global_gate=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif task_class == TODO_TASK_CLASS_USER_GATE and blocks_agent and global_gate:
                    errors.append(
                        f"{goal_id}: open user_gate todo {todo_id} in multi-agent goal "
                        "cannot set both blocks_agent and global_gate=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif bound_agent and goal_bound:
                    errors.append(
                        f"{goal_id}: open user todo {todo_id} cannot set both "
                        "bound_agent and goal_bound=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif (
                    task_class == TODO_TASK_CLASS_USER_GATE
                    and global_gate
                    and bound_agent
                ):
                    errors.append(
                        f"{goal_id}: goal-wide user_gate todo {todo_id} cannot set "
                        "bound_agent; its response binding is goal_bound=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif (
                    task_class == TODO_TASK_CLASS_USER_GATE
                    and blocks_agent
                    and goal_bound
                ):
                    errors.append(
                        f"{goal_id}: agent-scoped user_gate todo {todo_id} cannot set "
                        "goal_bound=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif (
                    task_class == TODO_TASK_CLASS_USER_GATE
                    and blocks_agent
                    and bound_agent
                    and bound_agent != blocks_agent
                ):
                    errors.append(
                        f"{goal_id}: agent-scoped user_gate todo {todo_id} must bind "
                        f"to blocks_agent={blocks_agent!r}, not bound_agent="
                        f"{bound_agent!r} (state_file={state_file}, line={index + 1}, "
                        f"text={text})"
                    )
                elif bound_agent and registered_agents and bound_agent not in registered_agents:
                    errors.append(
                        f"{goal_id}: open user todo {todo_id} has bound_agent="
                        f"{bound_agent!r}, which is not registered for this goal "
                        f"(registered_agents={', '.join(registered_agents)}, "
                        f"state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif (
                    len(registered_agents) > 1
                    and not effective_bound_agent
                    and not effective_goal_bound
                ):
                    errors.append(
                        f"{goal_id}: open user todo {todo_id} in multi-agent goal "
                        "requires bound_agent=<registered-agent> or goal_bound=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif (
                    task_class == TODO_TASK_CLASS_USER_GATE
                    and blocks_agent
                    and registered_agents
                    and blocks_agent not in registered_agents
                ):
                    errors.append(
                        f"{goal_id}: open user_gate todo {todo_id} has blocks_agent="
                        f"{blocks_agent!r}, which is not registered for this goal "
                        f"(registered_agents={', '.join(registered_agents)}, "
                        f"state_file={state_file}, line={index + 1}, text={text})"
                    )
                elif (
                    task_class == TODO_TASK_CLASS_USER_GATE
                    and len(registered_agents) > 1
                    and not blocks_agent
                    and not global_gate
                ):
                    errors.append(
                        f"{goal_id}: open user_gate todo {todo_id} in multi-agent goal "
                        "requires blocks_agent=<registered-agent> or global_gate=true "
                        f"(state_file={state_file}, line={index + 1}, text={text})"
                    )
            index = next_index
    return errors, checked


def _active_state_projection_gap_warnings(registry: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for goal in registry_goals(registry):
        goal_id = str(goal.get("id") or "")
        repo_text = str(goal.get("repo") or "").strip()
        if not repo_text:
            continue
        state_file = resolve_state_file(Path(repo_text).expanduser(), goal.get("state_file"))
        if not state_file or not state_file.exists():
            continue
        try:
            state_text = state_file.read_text(encoding="utf-8")
        except OSError:
            continue
        projection_gap = state_projection_gap_warning(state_text)
        if not projection_gap:
            continue
        target_roles = ",".join(str(role) for role in projection_gap.get("target_roles") or [])
        warnings.append(
            f"{goal_id}: active state has a state_projection_gap for {target_roles or 'todo'}; "
            "expand executable Next Action work into an open Agent Todo or user wait into an open User Todo"
        )
    return warnings


def _tracked_scan_files(scan_root: Path) -> list[Path]:
    scan_root = scan_root.resolve()
    target = scan_root if scan_root.is_dir() else scan_root.parent
    try:
        root = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    repo_root = Path(root).resolve()
    try:
        rel_root = str(scan_root.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return []
    if not rel_root:
        rel_root = "."

    tracked = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", rel_root],
        text=True,
        capture_output=True,
        check=False,
    )
    if tracked.returncode != 0:
        return []

    files: list[Path] = []
    for rel_path in tracked.stdout.split("\0"):
        if not rel_path:
            continue
        path = (repo_root / rel_path).resolve()
        if path.name.endswith(".local.json"):
            continue
        if path.is_file() and path.suffix in DEFAULT_SCAN_SUFFIXES:
            files.append(path)
    return files


def iter_scan_files(scan_root: Path) -> list[Path]:
    scan_root = scan_root.resolve()
    if scan_root.is_file():
        return [scan_root]
    files: list[Path] = []
    tracked_files = _tracked_scan_files(scan_root)
    root_parts = set(scan_root.parts)
    if any(part in DEFAULT_SKIP_DIRS or part.endswith(".egg-info") for part in root_parts):
        return sorted(tracked_files)

    for dir_path, dir_names, file_names in os.walk(scan_root):
        dir_names[:] = [
            name
            for name in dir_names
            if name not in DEFAULT_SKIP_DIRS and not name.endswith(".egg-info")
        ]
        current_dir = Path(dir_path)
        for file_name in file_names:
            path = (current_dir / file_name).resolve()
            if path.name.endswith(".local.json"):
                continue
            if path.suffix in DEFAULT_SCAN_SUFFIXES:
                files.append(path)
    return sorted(set(files + tracked_files))


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
        resolved_scan_root = scan_root.resolve()
        display_root = resolved_scan_root.parent if resolved_scan_root.is_file() else resolved_scan_root
        for file_path in iter_scan_files(resolved_scan_root):
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
    user_gate_scope_errors, checked_user_gates = _active_state_user_gate_scope_errors(registry)
    if checked_user_gates:
        checks.append(f"user-gate scopes checked: {checked_user_gates} open multi-agent gates")
    errors.extend(user_gate_scope_errors)
    warnings.extend(_active_state_projection_gap_warnings(registry))

    runtime_root = resolve_runtime_root(
        registry,
        runtime_root_override,
        registry_path=registry_path,
    )
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
                warnings.append(_index_duplicate_warning(item.get("id"), raw, unique, duplicate_summary))
            else:
                emitted_check = False
                if duplicate_summary.get("reward_overlay_rows"):
                    emitted_check = True
                    checks.append(
                        f"{item.get('id')}: reward overlay rows raw={raw} unique={unique} "
                        f"overlays={duplicate_summary.get('reward_overlay_rows')}"
                    )
                if duplicate_summary.get("structured_artifact_bundle_rows"):
                    emitted_check = True
                    checks.append(
                        f"{item.get('id')}: structured artifact bundle rows raw={raw} unique={unique} "
                        f"bundles={duplicate_summary.get('structured_artifact_bundle_rows')}"
                    )
                if not emitted_check:
                    warnings.append(_index_duplicate_warning(item.get("id"), raw, unique, duplicate_summary))

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
