from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


ONBOARDING_SCAN_SCHEMA_VERSION = "loopx_project_onboarding_v0"

PROJECT_SIGNAL_FILES = (
    "GOAL.md",
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "justfile",
)

VALIDATION_SIGNAL_FILES = {
    "pyproject.toml": "python",
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "Makefile": "make",
    "justfile": "just",
}


def _git(project: Path, *args: str, timeout_seconds: float = 1.5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(project), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_lines(project: Path, *args: str, timeout_seconds: float = 1.5) -> list[str]:
    result = _git(project, *args, timeout_seconds=timeout_seconds)
    if result is None or result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_git_repo(project: Path) -> bool:
    result = _git(project, "rev-parse", "--is-inside-work-tree", timeout_seconds=1)
    return bool(result and result.returncode == 0 and result.stdout.strip() == "true")


def _top_level_files(project: Path, *, limit: int) -> list[str]:
    names: list[str] = []
    try:
        for child in sorted(project.iterdir(), key=lambda path: path.name.lower()):
            if child.name.startswith(".git"):
                continue
            suffix = "/" if child.is_dir() else ""
            names.append(f"{child.name}{suffix}")
            if len(names) >= limit:
                break
    except OSError:
        return []
    return names


def _detected_signal_files(project: Path) -> list[str]:
    return [name for name in PROJECT_SIGNAL_FILES if (project / name).exists()]


def _recent_commits(project: Path, *, max_commits: int) -> list[dict[str, str]]:
    lines = _git_lines(project, "log", f"--max-count={max(0, max_commits)}", "--pretty=format:%h%x09%s")
    commits: list[dict[str, str]] = []
    for line in lines:
        if "\t" in line:
            short_hash, subject = line.split("\t", 1)
        else:
            short_hash, subject = line, ""
        commits.append({"hash": short_hash, "subject": subject})
    return commits


def _candidate(
    *,
    text: str,
    task_class: str = "advancement_task",
    action_kind: str = "analyze",
    reason: str,
) -> dict[str, str]:
    return {
        "text": " ".join(text.split()),
        "task_class": task_class,
        "action_kind": action_kind,
        "reason": " ".join(reason.split()),
    }


def build_onboarding_scan(
    project: Path,
    *,
    max_commits: int = 5,
    max_status_paths: int = 12,
    max_top_level_files: int = 24,
) -> dict[str, Any]:
    """Build a bounded, body-free scan for first-time project onboarding."""
    project = project.expanduser().resolve()
    is_git_repo = _is_git_repo(project)
    status_paths = (
        _git_lines(project, "status", "--short", "--untracked-files=normal", timeout_seconds=1.5)
        if is_git_repo
        else []
    )
    status_sample = status_paths[: max(0, max_status_paths)]
    commits = _recent_commits(project, max_commits=max_commits) if is_git_repo else []
    signal_files = _detected_signal_files(project)
    validation_signal_files = [
        {"path": path, "ecosystem": VALIDATION_SIGNAL_FILES[path]}
        for path in signal_files
        if path in VALIDATION_SIGNAL_FILES
    ]
    top_level_files = _top_level_files(project, limit=max(0, max_top_level_files))

    candidates: list[dict[str, str]] = []
    if status_sample:
        sample = ", ".join(status_sample[:5])
        candidates.append(
            _candidate(
                text=(
                    f"[P1] Inspect current uncommitted changes ({sample}) and decide what belongs "
                    "in the first LoopX segment before editing."
                ),
                action_kind="repo_status_review",
                reason="The repo already has local changes, so the first safe step is ownership and scope classification.",
            )
        )
    elif is_git_repo:
        candidates.append(
            _candidate(
                text="[P1] Confirm the clean git baseline and record the first safe bounded segment before editing.",
                action_kind="repo_status_review",
                reason="The repo appears clean, so the agent can establish a baseline before selecting delivery work.",
            )
        )

    if commits:
        count = len(commits)
        candidates.append(
            _candidate(
                text=f"[P1] Summarize the last {count} commits and extract the safest next bounded project follow-up.",
                action_kind="commit_summary",
                reason="Recent commits are a fast signal of current project direction without reading private bodies.",
            )
        )

    if validation_signal_files:
        files = ", ".join(item["path"] for item in validation_signal_files[:4])
        candidates.append(
            _candidate(
                text=f"[P1] Identify the fastest validation command from {files} and record whether it is safe to run now.",
                action_kind="validation_plan",
                reason="Validation entrypoints are visible from top-level project metadata.",
            )
        )

    if signal_files:
        files = ", ".join(signal_files[:5])
        candidates.append(
            _candidate(
                text=(
                    f"[P2] Build a compact read-only project map from {files} and note authority sources, "
                    "risks, and first useful handoff."
                ),
                action_kind="read_only_map",
                reason="Top-level project files can seed a useful map before any implementation work.",
            )
        )

    if not candidates:
        candidates.append(
            _candidate(
                text="[P1] Do a bounded read-only repo intake and ask the user to confirm the first concrete delivery target.",
                action_kind="repo_intake",
                reason="No common project signals were found, so the safest first step is a narrow intake.",
            )
        )

    return {
        "schema_version": ONBOARDING_SCAN_SCHEMA_VERSION,
        "project_label": project.name,
        "is_git_repo": is_git_repo,
        "status_path_count": len(status_paths),
        "status_paths_sample": status_sample,
        "recent_commits": commits,
        "signal_files": signal_files,
        "validation_signal_files": validation_signal_files,
        "top_level_files_sample": top_level_files,
        "agent_todo_candidates": candidates[:4],
        "user_acceptance_required": True,
        "scan_policy": {
            "fast": True,
            "max_commits": max_commits,
            "max_status_paths": max_status_paths,
            "max_top_level_files": max_top_level_files,
            "raw_file_bodies_read": False,
        },
    }
