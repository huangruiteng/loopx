from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .authority import authority_registry_summary
from .control_plane import compact_control_plane_policy, control_plane_policy_summary
from .execution_profile import compact_execution_profile, execution_profile_summary
from .orchestration import compact_orchestration_policy, orchestration_policy_summary
from .quota import goal_quota_config


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("registry root must be a JSON object")
    return payload


def resolve_state_file(repo: Path, state_file: str | None) -> Path | None:
    if not state_file:
        return None
    path = Path(state_file).expanduser()
    return path if path.is_absolute() else repo / path


def stable_path_key(path: Path) -> str:
    try:
        return str(path.expanduser().resolve())
    except OSError:
        return str(path.expanduser())


def registry_goals(registry: dict[str, Any]) -> list[dict[str, Any]]:
    goals = registry.get("goals")
    if not isinstance(goals, list):
        return []
    return [goal for goal in goals if isinstance(goal, dict) and goal.get("id")]


def inspect_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "registry": str(path),
            "error": "registry file does not exist",
        }

    payload = read_json(path)
    goals = payload.get("goals") or []
    if not isinstance(goals, list):
        raise ValueError("goals must be a list")

    inspected_goals: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    problems: list[str] = []
    seen_ids: set[str] = set()
    repo_goal_ids: dict[str, list[str]] = {}
    state_goal_ids: dict[str, list[str]] = {}

    for raw_goal in goals:
        if not isinstance(raw_goal, dict):
            continue
        goal_id = str(raw_goal.get("id") or "")
        if not goal_id:
            continue
        repo_text = str(raw_goal.get("repo") or "")
        repo = Path(repo_text).expanduser() if repo_text else None
        if repo:
            repo_goal_ids.setdefault(stable_path_key(repo), []).append(goal_id)
            state_file = resolve_state_file(repo, raw_goal.get("state_file"))
            if state_file:
                state_goal_ids.setdefault(stable_path_key(state_file), []).append(goal_id)

    for raw_goal in goals:
        if not isinstance(raw_goal, dict):
            problems.append("non-object goal entry")
            continue

        goal_id = str(raw_goal.get("id") or "")
        status = str(raw_goal.get("status") or "unknown")
        repo_text = str(raw_goal.get("repo") or "")
        repo = Path(repo_text).expanduser() if repo_text else None
        state_file = resolve_state_file(repo, raw_goal.get("state_file")) if repo else None
        repo_ids = repo_goal_ids.get(stable_path_key(repo), []) if repo else []
        adapter = raw_goal.get("adapter") if isinstance(raw_goal.get("adapter"), dict) else {}
        spawn_policy = raw_goal.get("spawn_policy") if isinstance(raw_goal.get("spawn_policy"), dict) else {}
        orchestration = compact_orchestration_policy(spawn_policy)
        execution_profile = compact_execution_profile(raw_goal.get("execution_profile"))
        control_plane = compact_control_plane_policy(raw_goal.get("control_plane"))
        authority_sources = raw_goal.get("authority_sources")
        if not isinstance(authority_sources, list):
            authority_sources = []
        authority_registry = authority_registry_summary(raw_goal)
        quota = goal_quota_config(raw_goal)

        status_counts[status] = status_counts.get(status, 0) + 1
        if not goal_id:
            problems.append("goal entry missing id")
        elif goal_id in seen_ids:
            problems.append(f"duplicate goal id: {goal_id}")
        seen_ids.add(goal_id)

        if not repo:
            problems.append(f"{goal_id or '<missing>'}: missing repo")
        if not raw_goal.get("domain"):
            problems.append(f"{goal_id or '<missing>'}: missing domain")
        if not raw_goal.get("state_file"):
            problems.append(f"{goal_id or '<missing>'}: missing state_file")
        if not adapter.get("kind"):
            problems.append(f"{goal_id or '<missing>'}: missing adapter.kind")

        inspected_goals.append(
            {
                "id": goal_id,
                "domain": raw_goal.get("domain"),
                "status": status,
                "role": raw_goal.get("role") or "controller",
                "parent_goal_id": raw_goal.get("parent_goal_id"),
                "repo": repo_text,
                "repo_exists": bool(repo and repo.exists()),
                "repo_goal_count": len(repo_ids),
                "repo_goal_ids": repo_ids,
                "state_file": raw_goal.get("state_file"),
                "state_file_abs": stable_path_key(state_file) if state_file else None,
                "state_file_exists": bool(state_file and state_file.exists()),
                "adapter_kind": adapter.get("kind"),
                "adapter_status": adapter.get("status"),
                "authority_sources": authority_sources,
                "authority_source_count": len(authority_sources),
                "authority_registry": authority_registry,
                "quota": quota,
                "execution_profile": execution_profile,
                "waiting_on": raw_goal.get("waiting_on"),
                "attention_status": raw_goal.get("attention_status"),
                "operator_question": raw_goal.get("operator_question"),
                "recommended_action": raw_goal.get("recommended_action"),
                "next_handoff_condition": raw_goal.get("next_handoff_condition"),
                "orchestration": orchestration,
                "orchestration_mode": orchestration.get("mode"),
                "spawn_allowed": spawn_policy.get("allowed"),
                "max_children": spawn_policy.get("max_children"),
                "control_plane": control_plane,
                "next_probe": raw_goal.get("next_probe"),
                "guards": raw_goal.get("guards") or [],
            }
        )

    for state_file, goal_ids in sorted(state_goal_ids.items()):
        unique_goal_ids = sorted(set(goal_ids))
        if len(unique_goal_ids) > 1:
            problems.append(
                "state_file shared by multiple goals: "
                f"{', '.join(unique_goal_ids)} -> {state_file}"
            )

    return {
        "ok": not problems,
        "registry": str(path),
        "schema_version": payload.get("schema_version"),
        "updated_at": payload.get("updated_at"),
        "common_runtime_root": payload.get("common_runtime_root"),
        "goal_count": len(inspected_goals),
        "status_counts": status_counts,
        "problems": problems,
        "goals": inspected_goals,
    }

def _registry_boundary_kind(path: Path) -> dict[str, Any]:
    parts = path.expanduser().parts
    name = path.name
    if ".goal-harness" in parts:
        return {
            "kind": "project_local_private_registry",
            "github_push_allowed": False,
            "should_be_gitignored": True,
        }
    if name == "registry.global.json" or (
        ".codex" in parts and "goal-harness" in parts
    ):
        return {
            "kind": "global_local_private_registry",
            "github_push_allowed": False,
            "should_be_gitignored": True,
        }
    if "examples" in parts or name.endswith(".example.json"):
        return {
            "kind": "public_fixture_registry_projection",
            "github_push_allowed": True,
            "should_be_gitignored": False,
        }
    return {
        "kind": "unknown_registry_boundary",
        "github_push_allowed": False,
        "should_be_gitignored": True,
    }


def _registry_git_probe(path: Path) -> dict[str, Any]:
    probe_dir = path if path.is_dir() else path.parent

    def run_git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=probe_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    root = run_git("rev-parse", "--show-toplevel")
    inside = root.returncode == 0
    tracked = False
    ignored = False
    if inside:
        root_path = Path(root.stdout.strip())
        try:
            rel_path = os.path.relpath(path.resolve(), root_path)
        except (OSError, ValueError):
            rel_path = path.name
        tracked = (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel_path],
                cwd=root_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            ).returncode
            == 0
        )
        ignored = (
            subprocess.run(
                ["git", "check-ignore", "-q", rel_path],
                cwd=root_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            ).returncode
            == 0
        )
    return {
        "inside_worktree": inside,
        "tracked": tracked,
        "ignored": ignored,
        "worktree_root_recorded": False,
    }


def inspect_registry_boundary(path: Path) -> dict[str, Any]:
    expanded = path.expanduser()
    classification = _registry_boundary_kind(expanded)
    git = _registry_git_probe(expanded)
    risks: list[str] = []
    if git.get("tracked") and not classification["github_push_allowed"]:
        risks.append("registry_tracked_but_not_push_allowed")
    if (
        classification["should_be_gitignored"]
        and git.get("inside_worktree")
        and not git.get("ignored")
        and not git.get("tracked")
    ):
        risks.append("registry_should_be_gitignored")
    return {
        "ok": not risks,
        "schema_version": "goal_harness_registry_boundary_v0",
        "path_label": expanded.name,
        "path_recorded": False,
        "boundary_kind": classification["kind"],
        "github_push_allowed": classification["github_push_allowed"],
        "should_be_gitignored": classification["should_be_gitignored"],
        "git": git,
        "risks": risks,
    }


def render_registry_boundary_markdown(payload: dict[str, Any]) -> str:
    git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
    lines = [
        "# Goal Harness Registry Boundary",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- path_label: `{payload.get('path_label')}`",
        f"- boundary_kind: `{payload.get('boundary_kind')}`",
        f"- github_push_allowed: `{payload.get('github_push_allowed')}`",
        f"- should_be_gitignored: `{payload.get('should_be_gitignored')}`",
        f"- git tracked/ignored: `{git.get('tracked')}`/`{git.get('ignored')}`",
        f"- path_recorded: `{payload.get('path_recorded')}`",
    ]
    risks = payload.get("risks") if isinstance(payload.get("risks"), list) else []
    if risks:
        lines.extend(["", "## Risks"])
        lines.extend(f"- `{risk}`" for risk in risks)
    return "\n".join(lines) + "\n"


def render_registry_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Registry",
        "",
        f"- registry: `{payload.get('registry')}`",
        f"- ok: `{payload.get('ok')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)

    lines.extend(
        [
            f"- schema_version: `{payload.get('schema_version')}`",
            f"- updated_at: `{payload.get('updated_at')}`",
            f"- common_runtime_root: `{payload.get('common_runtime_root')}`",
            f"- goals: `{payload.get('goal_count')}`",
            "",
            "| goal | role | parent | domain | status | repo_exists | repo_goals | state_exists | spawn | adapter | next_probe |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for goal in payload.get("goals") or []:
        adapter = f"{goal.get('adapter_kind')}:{goal.get('adapter_status')}"
        spawn = orchestration_policy_summary(
            goal.get("orchestration") if isinstance(goal.get("orchestration"), dict) else None
        )
        next_probe = str(goal.get("next_probe") or "").replace("|", "\\|")
        authority_suffix = ""
        if goal.get("authority_source_count"):
            authority_suffix = f" authorities={goal.get('authority_source_count')}"
        authority_registry = goal.get("authority_registry") if isinstance(goal.get("authority_registry"), dict) else {}
        if authority_registry.get("declared"):
            default_count = authority_registry.get("default_entry_count")
            topic_count = authority_registry.get("topic_authority_count")
            authority_suffix += f" authority_registry=defaults:{default_count},topics:{topic_count}"
        quota = goal.get("quota") if isinstance(goal.get("quota"), dict) else {}
        quota_suffix = f" quota={quota.get('compute')}" if quota else ""
        execution_profile = (
            goal.get("execution_profile")
            if isinstance(goal.get("execution_profile"), dict)
            else None
        )
        execution_suffix = (
            f" execution_profile={execution_profile_summary(execution_profile)}"
            if execution_profile
            else ""
        )
        control_plane = (
            goal.get("control_plane")
            if isinstance(goal.get("control_plane"), dict)
            else None
        )
        control_plane_suffix = (
            f" control_plane={control_plane_policy_summary(control_plane)}"
            if control_plane
            else ""
        )
        lines.append(
            "| "
            f"`{goal.get('id')}` | "
            f"{goal.get('role')} | "
            f"{goal.get('parent_goal_id') or ''} | "
            f"{goal.get('domain')} | "
            f"{goal.get('status')} | "
            f"{goal.get('repo_exists')} | "
            f"{goal.get('repo_goal_count')} | "
            f"{goal.get('state_file_exists')} | "
            f"{spawn} | "
            f"{adapter}{authority_suffix}{quota_suffix}{execution_suffix}{control_plane_suffix} | "
            f"{next_probe} |"
        )

    problems = payload.get("problems") or []
    if problems:
        lines.extend(["", "## Problems"])
        lines.extend(f"- {item}" for item in problems)
    return "\n".join(lines)
