from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def build_runner_source_fingerprint(
    *,
    repo_root: Path,
    expected_git_head: str = "",
) -> dict[str, Any]:
    expected = str(expected_git_head or "").strip()
    head = ""
    error_kind = ""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0:
            head = proc.stdout.strip().splitlines()[0][:40]
        else:
            error_kind = "git_rev_parse_failed"
    except Exception as exc:
        error_kind = type(exc).__name__

    matches_expected = bool(expected and head and head.startswith(expected))
    status = "observed"
    first_blocker = ""
    if expected:
        if matches_expected:
            status = "matched_expected"
        elif head:
            status = "mismatched_expected"
            first_blocker = "loopx_runner_source_git_head_mismatch"
        else:
            status = "unknown_expected"
            first_blocker = "loopx_runner_source_git_head_unknown"
    elif not head:
        status = "unknown"

    return {
        "schema_version": "skillsbench_runner_source_fingerprint_v0",
        "status": status,
        "git_head": head,
        "expected_git_head": expected[:40],
        "matches_expected": matches_expected,
        "first_blocker": first_blocker,
        "error_kind": error_kind[:80],
        "git_head_recorded": bool(head),
        "expected_git_head_recorded": bool(expected),
        "source_path_recorded": False,
        "raw_git_output_recorded": False,
    }


def runner_source_prerequisite_fields(
    fingerprint: dict[str, Any],
) -> dict[str, Any]:
    return {
        "loopx_runner_source_fingerprint_status": str(
            fingerprint.get("status") or ""
        ),
        "loopx_runner_source_first_blocker": str(
            fingerprint.get("first_blocker") or ""
        ),
        "loopx_runner_source_git_head": str(fingerprint.get("git_head") or ""),
        "loopx_runner_source_expected_git_head": str(
            fingerprint.get("expected_git_head") or ""
        ),
        "loopx_runner_source_error_kind": str(fingerprint.get("error_kind") or ""),
        "loopx_runner_source_git_head_recorded": bool(
            fingerprint.get("git_head_recorded")
        ),
        "loopx_runner_source_expected_git_head_recorded": bool(
            fingerprint.get("expected_git_head_recorded")
        ),
        "loopx_runner_source_matches_expected": bool(
            fingerprint.get("matches_expected")
        ),
        "loopx_runner_source_path_recorded": False,
        "loopx_runner_source_raw_git_output_recorded": False,
    }


def compact_runner_source_public_fields(value: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, raw in value.items():
        if not key.startswith("loopx_runner_source_"):
            continue
        if isinstance(raw, str) and raw:
            compact[key] = raw[:180]
        elif isinstance(raw, bool):
            compact[key] = raw
    return compact
