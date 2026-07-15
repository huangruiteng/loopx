from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from ...repository_identity import normalize_repository_identity
from ..todos.contract import normalize_todo_claimed_by, normalize_todo_task_repository

AGENT_WORKSPACE_GUARD_SCHEMA_VERSION = "agent_workspace_guard_v1"
DELIVERY_WORKSPACE_SCHEMA_VERSION = "delivery_workspace_v0"
PEER_WRITE_ACTION_KINDS = {
    "fix",
    "implement",
    "rebuild",
    "repair",
    "writeback",
}


def _is_same_or_child_path(path: Path, root: Path) -> bool:
    try:
        current = path.expanduser().resolve()
        target = root.expanduser().resolve()
    except OSError:
        return False
    return current == target or target in current.parents


def _git_command_output(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def _git_worktree_root(path: Path) -> Path | None:
    output = _git_command_output(path, "rev-parse", "--show-toplevel")
    if not output:
        return None
    try:
        return Path(output).expanduser().resolve()
    except OSError:
        return None


def _git_common_dir(path: Path) -> Path | None:
    root = _git_worktree_root(path)
    if root is None:
        return None
    output = _git_command_output(root, "rev-parse", "--git-common-dir")
    if not output:
        return None
    common = Path(output).expanduser()
    if not common.is_absolute():
        common = root / common
    try:
        return common.resolve()
    except OSError:
        return None


def _git_dir(path: Path) -> Path | None:
    root = _git_worktree_root(path)
    if root is None:
        return None
    output = _git_command_output(root, "rev-parse", "--git-dir")
    if not output:
        return None
    git_dir = Path(output).expanduser()
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    try:
        return git_dir.resolve()
    except OSError:
        return None


def _git_repository_identity(path: Path) -> str | None:
    remote = _git_command_output(path, "config", "--get", "remote.origin.url")
    if not remote:
        return None
    try:
        return normalize_repository_identity(remote)
    except ValueError:
        return None


def capture_delivery_workspace(
    current_path: Path | None = None,
    *,
    peer_independent_worktree_required: bool = False,
) -> dict[str, Any] | None:
    """Capture a compact, credential-free delivery workspace identity.

    The snapshot intentionally excludes local paths and branch names.  It is
    safe to persist with an accountable run and later binds quota accounting
    to the repository where that delivery was actually written.
    """

    path = current_path or Path.cwd()
    current_root = _git_worktree_root(path)
    if current_root is None:
        return None
    current_common = _git_common_dir(path)
    current_git_dir = _git_dir(path)
    task_repository = _git_repository_identity(path)
    if not task_repository or current_common is None or current_git_dir is None:
        return None
    workspace_kind = (
        "independent_git_worktree"
        if current_git_dir != current_common
        else "canonical_checkout"
    )
    return {
        "schema_version": DELIVERY_WORKSPACE_SCHEMA_VERSION,
        "task_repository": task_repository,
        "repository_source": "current_git_origin",
        "workspace_kind": workspace_kind,
        "peer_independent_worktree_required": bool(
            peer_independent_worktree_required
        ),
    }


def delivery_workspace_repository(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != DELIVERY_WORKSPACE_SCHEMA_VERSION:
        return None
    if value.get("workspace_kind") not in {
        "canonical_checkout",
        "independent_git_worktree",
    }:
        return None
    if not isinstance(value.get("peer_independent_worktree_required"), bool):
        return None
    try:
        return normalize_todo_task_repository(value.get("task_repository"))
    except (TypeError, ValueError):
        return None


def build_delivery_workspace_guard(
    delivery_run: dict[str, Any],
    *,
    agent_id: str | None = None,
    current_path: Path | None = None,
) -> dict[str, Any] | None:
    """Validate quota accounting against its accountable delivery workspace.

    Legacy delivery runs without a snapshot return ``None`` so the existing
    selected-todo workspace guard remains the fail-closed fallback.
    """

    snapshot = (
        delivery_run.get("delivery_workspace")
        if isinstance(delivery_run.get("delivery_workspace"), dict)
        else {}
    )
    task_repository = delivery_workspace_repository(snapshot)
    if not task_repository:
        return None

    current = capture_delivery_workspace(current_path)
    current_repository = str((current or {}).get("task_repository") or "")
    current_workspace = str((current or {}).get("workspace_kind") or "")
    recorded_workspace = str(snapshot.get("workspace_kind") or "")
    peer_independent_worktree_required = bool(
        snapshot.get("peer_independent_worktree_required")
    )
    if not current:
        current_workspace = "not_git_worktree"
    elif current_repository != task_repository:
        current_workspace = "foreign_git_worktree"
    elif (
        recorded_workspace == "independent_git_worktree"
        and current_workspace != "independent_git_worktree"
    ):
        current_workspace = "canonical_checkout"
    elif (
        peer_independent_worktree_required
        and recorded_workspace != "independent_git_worktree"
    ):
        current_workspace = "delivery_not_recorded_from_independent_worktree"
    else:
        return None

    return {
        "schema_version": AGENT_WORKSPACE_GUARD_SCHEMA_VERSION,
        "source": "quota.spend_slot.delivery_workspace",
        "action": "return_to_delivery_worktree",
        "current_workspace": current_workspace,
        "required_workspace": (
            "accountable_delivery_independent_git_worktree"
            if recorded_workspace == "independent_git_worktree"
            or peer_independent_worktree_required
            else "accountable_delivery_git_checkout"
        ),
        "blocks_delivery": True,
        "agent_id": normalize_todo_claimed_by(agent_id),
        "repository_source": "delivery_run.delivery_workspace.task_repository",
        "task_repository": task_repository,
        "delivery_run_generated_at": delivery_run.get("generated_at"),
        "delivery_run_classification": delivery_run.get("classification"),
        "reason": (
            "quota spend workspace does not match the latest unspent accountable "
            "delivery workspace"
        ),
        "required_action": (
            "run quota spend-slot from the workspace that produced the latest "
            "unspent accountable delivery"
        ),
    }


def _peer_candidate_items(agent_todo_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(agent_todo_summary, dict):
        return []
    for key in (
        "active_next_action_executable_items",
        "executable_backlog_items",
        "first_executable_items",
    ):
        items = agent_todo_summary.get(key)
        if isinstance(items, list) and items:
            return [item for item in items if isinstance(item, dict)]
    return []


def _peer_work_requires_isolated_workspace(
    workspace_guard_policy: dict[str, Any],
    agent_todo_summary: dict[str, Any] | None,
) -> bool:
    explicit = workspace_guard_policy.get("peer_independent_worktree_required")
    if explicit is not None:
        return explicit is True
    candidates = _peer_candidate_items(agent_todo_summary)
    if not candidates:
        return False
    candidate = candidates[0]
    if candidate.get("required_write_scopes"):
        return True
    action_kind = str(candidate.get("action_kind") or "").strip().lower()
    return action_kind in PEER_WRITE_ACTION_KINDS or action_kind.startswith(
        tuple(f"{prefix}_" for prefix in PEER_WRITE_ACTION_KINDS)
    )


def build_agent_workspace_guard(
    goal: dict[str, Any],
    agent_identity: dict[str, Any] | None,
    *,
    agent_todo_summary: dict[str, Any] | None = None,
    current_path: Path | None = None,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict):
        return None
    workspace_guard_policy = (
        goal.get("workspace_guard_policy")
        if isinstance(goal.get("workspace_guard_policy"), dict)
        else {}
    )
    if len(agent_identity.get("registered_agents") or []) <= 1:
        return None
    if not _peer_work_requires_isolated_workspace(
        workspace_guard_policy,
        agent_todo_summary,
    ):
        return None
    current_path = current_path or Path.cwd()
    candidates = _peer_candidate_items(agent_todo_summary)
    candidate = candidates[0] if candidates else {}
    task_repository = normalize_todo_task_repository(candidate.get("task_repository"))
    current_workspace = ""
    repository_source = "goal.repo"
    if task_repository:
        repository_source = "selected_todo.task_repository"
        current_root = _git_worktree_root(current_path)
        current_common = _git_common_dir(current_path) if current_root else None
        current_git_dir = _git_dir(current_path) if current_root else None
        current_repository = (
            _git_repository_identity(current_path) if current_root else None
        )
        if current_root is None:
            current_workspace = "not_git_worktree"
        elif current_repository != task_repository:
            current_workspace = "foreign_git_worktree"
        elif (
            current_common is None
            or current_git_dir is None
            or current_git_dir == current_common
        ):
            current_workspace = "canonical_checkout"
    else:
        repo_value = goal.get("repo") or goal.get("project") or goal.get("root")
        if not repo_value:
            return None
        repo_path = Path(str(repo_value)).expanduser()
        if not repo_path.is_absolute():
            return None
        if _is_same_or_child_path(current_path, repo_path):
            current_workspace = "canonical_checkout"
        else:
            canonical_root = _git_worktree_root(repo_path) or repo_path
            current_root = _git_worktree_root(current_path)
            canonical_common = _git_common_dir(canonical_root)
            current_common = _git_common_dir(current_path) if current_root else None
            if current_root is None:
                current_workspace = "not_git_worktree"
            elif (
                canonical_common is None
                or current_common is None
                or current_common != canonical_common
            ):
                current_workspace = "foreign_git_worktree"
            elif current_root == canonical_root:
                current_workspace = "canonical_checkout"
    if not current_workspace:
        return None
    payload = {
        "schema_version": AGENT_WORKSPACE_GUARD_SCHEMA_VERSION,
        "source": "quota.should-run",
        "action": "move_to_independent_worktree",
        "current_workspace": current_workspace,
        "required_workspace": "independent_git_worktree",
        "blocks_delivery": True,
        "agent_id": agent_identity.get("agent_id"),
        "repository_source": repository_source,
        "reason": (
            "peer delivery with repository writes is not running from an independent "
            "worktree; normal delivery must move before repository edits"
        ),
        "required_action": (
            "create or switch to an independent git worktree/branch for this peer lane, "
            "then rerun quota should-run with the same --agent-id before editing files"
        ),
    }
    if task_repository:
        payload["task_repository"] = task_repository
    return payload
