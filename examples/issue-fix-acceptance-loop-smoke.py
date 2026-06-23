#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _run_json_command(command: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "issue-fix",
            command,
            "--format",
            "json",
            "--url",
            "https://github.com/huangruiteng/loopx/issues/123",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if result.stderr.strip():
        raise AssertionError(f"unexpected stderr: {result.stderr}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise AssertionError("issue-fix acceptance fixture must emit a JSON object")
    return payload


def _walk_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_walk_values(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(_walk_values(child))
        return strings
    return []


def _assert_no_local_paths(payload: dict[str, Any]) -> None:
    joined = "\n".join(_walk_values(payload))
    blocked_markers = ("/tmp/", "/private/", str(ROOT))
    found = [marker for marker in blocked_markers if marker and marker in joined]
    if found:
        raise AssertionError(f"fixture artifact exposed local path markers: {found}")


def _assert_validated_fixture_payload(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True
    assert payload["schema_version"] == "issue_fix_acceptance_loop_v0"
    assert payload["external_reads_performed"] is False
    assert payload["external_writes_performed"] is False
    assert payload["local_paths_captured"] is False
    assert payload["destructive_git_used"] is False

    artifact = payload["validated_fix_artifact"]
    assert artifact["schema_version"] == "issue_fix_validated_fix_artifact_v0"
    assert artifact["fix_artifact_ready"] is True
    assert artifact["pr_review_packet_ready"] is True
    assert artifact["issue_signal"]["body_captured"] is False
    assert artifact["issue_signal"]["comment_bodies_captured"] is False

    repro_before = artifact["repro_before"]
    validation_after = artifact["validation_after"]
    patch = artifact["patch"]
    assert repro_before["passed"] is False
    assert repro_before["stdout_captured"] is False
    assert repro_before["stderr_captured"] is False
    assert validation_after["passed"] is True
    assert validation_after["stdout_captured"] is False
    assert validation_after["stderr_captured"] is False
    assert patch["patch_applied"] is True
    assert patch["file"] == "calculator.py"
    assert patch["local_path_captured"] is False
    assert patch["destructive_git_used"] is False

    review = artifact["review_packet"]
    assert review["ready"] is True
    assert review["external_issue_comment_performed"] is False
    assert review["external_pr_created"] is False
    assert review["merge_performed"] is False
    assert payload["validation"]["ok"] is True
    _assert_no_local_paths(payload)


def main() -> int:
    payload = _run_json_command("acceptance-fixture")
    _assert_validated_fixture_payload(payload)

    branch_payload = _run_json_command("repo-branch-fixture")
    _assert_validated_fixture_payload(branch_payload)
    branch_artifact = branch_payload["validated_fix_artifact"]["repo_branch"]
    assert branch_payload["mode"] == "issue-fix-repo-branch-fixture"
    assert branch_payload["workspace_mode"] == "temporary_git_repo"
    assert branch_artifact["repo_mode"] == "temporary_git_repo"
    assert branch_artifact["issue_branch"] == "codex/issue-123-public-metadata-fixture"
    assert branch_artifact["branch_created"] is True
    assert branch_artifact["external_remote_used"] is False
    assert branch_artifact["local_path_captured"] is False
    diff_steps = [
        step
        for step in branch_payload["validated_fix_artifact"]["git_steps"]
        if step["command_label"] == "git diff confirms branch patch"
    ]
    assert len(diff_steps) == 1
    assert diff_steps[0]["exit_code"] == 1
    assert diff_steps[0]["expected_exit_codes"] == [1]
    for step in branch_payload["validated_fix_artifact"]["git_steps"]:
        assert step["passed"] is True
        assert step["stdout_captured"] is False
        assert step["stderr_captured"] is False
        assert step["local_path_captured"] is False

    markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "issue-fix",
            "repo-branch-fixture",
            "--format",
            "markdown",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    assert "LoopX Issue Fix Acceptance Loop" in markdown
    assert "Validated Fix Artifact" in markdown
    assert "issue_branch: `codex/issue-123-public-metadata-fixture`" in markdown
    assert "validation_after_passed: `True`" in markdown
    print("issue-fix-acceptance-loop-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
