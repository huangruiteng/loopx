"""Bounded GitHub reads for the pull-request review queue."""

from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

GitHubJsonRunner = Callable[..., Any]

DETAIL_FIELDS = (
    "body",
    "files",
    "reviewDecision",
    "mergeStateStatus",
    "createdAt",
    "commits",
    "reviews",
)


def run_gh_json(args: list[str], *, cwd: Path | None = None) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(proc.stdout or "null")


def _fetch_complete_pr_files(
    *,
    repository: str,
    number: str,
    expected_count: int,
    cwd: Path | None,
    run_gh_json: GitHubJsonRunner,
) -> list[dict[str, Any]] | None:
    try:
        payload = run_gh_json(
            [
                "api",
                "--paginate",
                "--slurp",
                f"repos/{repository}/pulls/{number}/files?per_page=100",
            ],
            cwd=cwd,
        )
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    pages = payload if all(isinstance(page, list) for page in payload) else [payload]
    files: list[dict[str, Any]] = []
    try:
        for page in pages:
            for item in page:
                if not isinstance(item, dict):
                    return None
                path = str(item.get("filename") or item.get("path") or "").strip()
                if not path:
                    return None
                additions = int(item.get("additions") or 0)
                deletions = int(item.get("deletions") or 0)
                if additions < 0 or deletions < 0:
                    return None
                files.append(
                    {
                        "path": path,
                        "additions": additions,
                        "deletions": deletions,
                    }
                )
    except (TypeError, ValueError):
        return None
    return files if len(files) == expected_count else None


def attach_pr_review_details(
    row: dict[str, Any],
    *,
    repository: str | None,
    cwd: Path | None = None,
    run_gh_json: GitHubJsonRunner = run_gh_json,
    wait_for_ci: bool = True,
) -> bool:
    """Attach complete per-PR details after the lightweight list scan."""

    detail_fields = DETAIL_FIELDS + (("statusCheckRollup",) if wait_for_ci else ())
    number = str(row.get("number") or "").strip()
    if not number or not repository:
        return False
    try:
        details = run_gh_json(
            [
                "pr",
                "view",
                number,
                "--json",
                ",".join(detail_fields),
                "--repo",
                repository,
            ],
            cwd=cwd,
        )
    except Exception:
        return False
    try:
        expected_file_count = int(row["changedFiles"])
    except (KeyError, TypeError, ValueError):
        return False
    if not isinstance(details, dict) or any(
        key not in details for key in detail_fields
    ):
        return False
    detail_files = details["files"]
    if not isinstance(detail_files, list):
        return False
    if len(detail_files) != expected_file_count:
        detail_files = _fetch_complete_pr_files(
            repository=repository,
            number=number,
            expected_count=expected_file_count,
            cwd=cwd,
            run_gh_json=run_gh_json,
        )
        if detail_files is None:
            return False
        details["files"] = detail_files
    for key in detail_fields:
        row[key] = details[key]
    return True


PR_REVIEW_DETAIL_MAX_WORKERS = 8


def attach_pr_review_details_concurrently(
    rows: Sequence[dict[str, Any]],
    *,
    repository: str | None,
    cwd: Path | None = None,
    attach: Callable[..., bool] = attach_pr_review_details,
    run_gh_json: GitHubJsonRunner = run_gh_json,
    wait_for_ci: bool = True,
) -> list[bool]:
    """Read per-PR details concurrently while preserving queue order."""

    if not rows:
        return []
    worker_count = min(PR_REVIEW_DETAIL_MAX_WORKERS, len(rows))

    def read(row: dict[str, Any]) -> bool:
        return attach(
            row,
            repository=repository,
            cwd=cwd,
            run_gh_json=run_gh_json,
            **({"wait_for_ci": False} if not wait_for_ci else {}),
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(read, rows))
