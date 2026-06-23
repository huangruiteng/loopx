from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .issue_fix_intake_surface import build_content_ops_issue_fix_metadata_preview_packet


ISSUE_FIX_ACCEPTANCE_LOOP_SCHEMA_VERSION = "issue_fix_acceptance_loop_v0"
ISSUE_FIX_VALIDATED_FIX_ARTIFACT_SCHEMA_VERSION = "issue_fix_validated_fix_artifact_v0"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_fixture_smoke(workspace: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "test_calculator.py"],
        cwd=workspace,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    return {
        "schema_version": "issue_fix_validation_command_v0",
        "command_label": "python test_calculator.py",
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout_captured": False,
        "stderr_captured": False,
        "local_path_captured": False,
    }


def _run_git_step(
    workspace: Path,
    args: list[str],
    label: str | None = None,
    *,
    expected_exit_codes: tuple[int, ...] = (0,),
) -> dict[str, Any]:
    result = subprocess.run(
        ["git", *args],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    return {
        "schema_version": "issue_fix_git_step_v0",
        "command_label": label or "git " + " ".join(args),
        "exit_code": result.returncode,
        "expected_exit_codes": list(expected_exit_codes),
        "passed": result.returncode in expected_exit_codes,
        "stdout_captured": False,
        "stderr_captured": False,
        "local_path_captured": False,
    }


def _require_passed(step: Mapping[str, Any]) -> None:
    if step.get("passed") is not True:
        raise RuntimeError(f"{step.get('command_label')} failed with exit code {step.get('exit_code')}")


def _write_fixture_workspace(workspace: Path) -> None:
    (workspace / "calculator.py").write_text(
        "\n".join(
            [
                "def add(left, right):",
                "    return left - right",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "test_calculator.py").write_text(
        "\n".join(
            [
                "from calculator import add",
                "",
                "",
                "def main():",
                "    assert add(2, 3) == 5, 'add should sum two integers'",
                "",
                "",
                "if __name__ == '__main__':",
                "    main()",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _apply_fixture_patch(workspace: Path) -> dict[str, Any]:
    target = workspace / "calculator.py"
    before = target.read_text(encoding="utf-8")
    broken = "return left - right"
    fixed = "return left + right"
    if broken not in before:
        raise ValueError("fixture patch expected the known subtraction bug")
    after = before.replace(broken, fixed, 1)
    target.write_text(after, encoding="utf-8")
    shutil.rmtree(workspace / "__pycache__", ignore_errors=True)
    return {
        "schema_version": "issue_fix_patch_step_v0",
        "patch_applied": True,
        "file": "calculator.py",
        "change_summary": "replace subtraction with addition in add()",
        "before_hash": _sha256_text(before),
        "after_hash": _sha256_text(after),
        "local_path_captured": False,
        "destructive_git_used": False,
    }


def _build_metadata_packet(
    *,
    repo: str,
    issue_ref: str,
    url: str | None,
    generated_at: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata_packet = build_content_ops_issue_fix_metadata_preview_packet(
        repo=repo,
        issue_ref=issue_ref,
        url=url,
        provider_payload={
            "state": "open",
            "title": "add() returns the wrong arithmetic result",
            "labels": [{"name": "bug"}, {"name": "has-repro"}],
            "comments_count": 0,
        },
        generated_at=generated_at,
    )
    return metadata_packet, dict(metadata_packet["github_metadata_preview"])


def build_issue_fix_acceptance_fixture_packet(
    *,
    repo: str = "public_repo_fixture",
    issue_ref: str = "issue_123_public_metadata_fixture",
    url: str | None = None,
    generated_at: str | None = "2026-06-23T00:00:00Z",
) -> dict[str, Any]:
    """Run a deterministic issue-fix acceptance loop against a temp fixture."""

    metadata_packet, metadata = _build_metadata_packet(
        repo=repo,
        issue_ref=issue_ref,
        url=url,
        generated_at=generated_at,
    )

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-") as tmpdir:
        workspace = Path(tmpdir)
        _write_fixture_workspace(workspace)
        repro_before = _run_fixture_smoke(workspace)
        route = {
            "schema_version": "issue_fix_code_route_v0",
            "route_id": "fixture_calculator_add_route",
            "selected": True,
            "source": "public issue labels plus failing repro smoke",
            "files_examined": ["calculator.py", "test_calculator.py"],
            "requires_private_repo_state": False,
            "reads_private_material": False,
        }
        patch_step = _apply_fixture_patch(workspace)
        validation_after = _run_fixture_smoke(workspace)

    artifact = {
        "schema_version": ISSUE_FIX_VALIDATED_FIX_ARTIFACT_SCHEMA_VERSION,
        "fix_artifact_ready": validation_after["passed"],
        "pr_review_packet_ready": validation_after["passed"],
        "issue_signal": {
            "repo": metadata["repo"],
            "issue_ref": metadata["issue_ref"],
            "kind": metadata["kind"],
            "labels": metadata["labels"],
            "body_captured": False,
            "comment_bodies_captured": False,
        },
        "repro_before": repro_before,
        "code_route": route,
        "patch": patch_step,
        "validation_after": validation_after,
        "review_packet": {
            "schema_version": "issue_fix_pr_review_packet_v0",
            "ready": validation_after["passed"],
            "summary": "Focused fixture repro failed, minimal patch applied, focused validation passed.",
            "files_changed": ["calculator.py"],
            "validation_commands": ["python test_calculator.py"],
            "external_issue_comment_performed": False,
            "external_pr_created": False,
            "merge_performed": False,
        },
    }
    steps = [
        {
            "step": "metadata_intake",
            "result": "public metadata preview built without issue body or comments",
        },
        {
            "step": "repro_smoke",
            "result": "failed before patch" if not repro_before["passed"] else "unexpected pass",
        },
        {"step": "code_route", "result": "fixture calculator route selected"},
        {
            "step": "patch",
            "result": "minimal patch applied" if patch_step["patch_applied"] else "not applied",
        },
        {
            "step": "validation",
            "result": "passed after patch" if validation_after["passed"] else "failed after patch",
        },
    ]
    packet: dict[str, Any] = {
        "ok": bool(
            not repro_before["passed"]
            and patch_step["patch_applied"]
            and validation_after["passed"]
        ),
        "schema_version": ISSUE_FIX_ACCEPTANCE_LOOP_SCHEMA_VERSION,
        "mode": "issue-fix-acceptance-fixture",
        "generated_at": generated_at,
        "workspace_mode": "temporary_fixture",
        "metadata_preview_schema_version": metadata_packet["schema_version"],
        "validated_fix_artifact": artifact,
        "steps": steps,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "issue_body_captured": False,
        "comment_bodies_captured": False,
        "local_paths_captured": False,
        "private_repo_state_read": False,
        "destructive_git_used": False,
        "next_safe_action": (
            "promote this acceptance loop from deterministic fixture to a real "
            "repo-local issue branch only after a focused repro can be run safely"
        ),
    }
    validation = validate_issue_fix_acceptance_loop_packet(packet)
    packet["ok"] = bool(packet["ok"] and validation["ok"])
    packet["validation"] = validation
    return packet


def build_issue_fix_repo_branch_fixture_packet(
    *,
    repo: str = "public_repo_fixture",
    issue_ref: str = "issue_123_public_metadata_fixture",
    url: str | None = None,
    generated_at: str | None = "2026-06-23T00:00:00Z",
) -> dict[str, Any]:
    """Run the issue-fix loop through a real temporary git branch lifecycle."""

    metadata_packet, metadata = _build_metadata_packet(
        repo=repo,
        issue_ref=issue_ref,
        url=url,
        generated_at=generated_at,
    )
    branch_name = "codex/issue-123-public-metadata-fixture"

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-git-") as tmpdir:
        workspace = Path(tmpdir)
        git_steps: list[dict[str, Any]] = []
        for args, label in (
            (["init", "-b", "main"], "git init fixture repo"),
            (["config", "user.name", "LoopX Fixture"], "git config fixture user.name"),
            (["config", "user.email", "loopx-fixture@example.invalid"], "git config fixture user.email"),
        ):
            step = _run_git_step(workspace, args, label)
            git_steps.append(step)
            _require_passed(step)

        _write_fixture_workspace(workspace)
        for args, label in (
            (["add", "calculator.py", "test_calculator.py"], "git add fixture files"),
            (["commit", "-m", "Add failing calculator fixture"], "git commit baseline fixture"),
            (["checkout", "-b", branch_name], "git create issue fix branch"),
        ):
            step = _run_git_step(workspace, args, label)
            git_steps.append(step)
            _require_passed(step)

        repro_before = _run_fixture_smoke(workspace)
        route = {
            "schema_version": "issue_fix_code_route_v0",
            "route_id": "fixture_git_calculator_add_route",
            "selected": True,
            "source": "public issue labels plus local branch repro smoke",
            "files_examined": ["calculator.py", "test_calculator.py"],
            "requires_private_repo_state": False,
            "reads_private_material": False,
        }
        patch_step = _apply_fixture_patch(workspace)
        validation_after = _run_fixture_smoke(workspace)
        diff_step = _run_git_step(
            workspace,
            ["diff", "--quiet", "--", "calculator.py"],
            "git diff confirms branch patch",
            expected_exit_codes=(1,),
        )
        git_steps.append(diff_step)
        _require_passed(diff_step)

    artifact = {
        "schema_version": ISSUE_FIX_VALIDATED_FIX_ARTIFACT_SCHEMA_VERSION,
        "fix_artifact_ready": validation_after["passed"],
        "pr_review_packet_ready": validation_after["passed"],
        "issue_signal": {
            "repo": metadata["repo"],
            "issue_ref": metadata["issue_ref"],
            "kind": metadata["kind"],
            "labels": metadata["labels"],
            "body_captured": False,
            "comment_bodies_captured": False,
        },
        "repo_branch": {
            "schema_version": "issue_fix_repo_branch_artifact_v0",
            "repo_mode": "temporary_git_repo",
            "base_branch": "main",
            "issue_branch": branch_name,
            "branch_created": all(step.get("passed") for step in git_steps),
            "external_remote_used": False,
            "local_path_captured": False,
        },
        "git_steps": git_steps,
        "repro_before": repro_before,
        "code_route": route,
        "patch": patch_step,
        "validation_after": validation_after,
        "review_packet": {
            "schema_version": "issue_fix_pr_review_packet_v0",
            "ready": validation_after["passed"],
            "summary": (
                "Temporary git repo issue branch created, focused repro failed, "
                "minimal patch applied, focused validation passed."
            ),
            "files_changed": ["calculator.py"],
            "validation_commands": ["python test_calculator.py"],
            "external_issue_comment_performed": False,
            "external_pr_created": False,
            "merge_performed": False,
        },
    }
    packet: dict[str, Any] = {
        "ok": bool(
            artifact["repo_branch"]["branch_created"]
            and not repro_before["passed"]
            and patch_step["patch_applied"]
            and validation_after["passed"]
        ),
        "schema_version": ISSUE_FIX_ACCEPTANCE_LOOP_SCHEMA_VERSION,
        "mode": "issue-fix-repo-branch-fixture",
        "generated_at": generated_at,
        "workspace_mode": "temporary_git_repo",
        "metadata_preview_schema_version": metadata_packet["schema_version"],
        "validated_fix_artifact": artifact,
        "steps": [
            {"step": "metadata_intake", "result": "public metadata preview built"},
            {"step": "repo_branch", "result": f"created {branch_name} in a temporary git repo"},
            {"step": "repro_smoke", "result": "failed before patch" if not repro_before["passed"] else "unexpected pass"},
            {"step": "patch", "result": "minimal patch applied"},
            {"step": "validation", "result": "passed after patch" if validation_after["passed"] else "failed after patch"},
        ],
        "external_reads_performed": False,
        "external_writes_performed": False,
        "issue_body_captured": False,
        "comment_bodies_captured": False,
        "local_paths_captured": False,
        "private_repo_state_read": False,
        "destructive_git_used": False,
        "next_safe_action": (
            "promote from the temporary git fixture to an approved caller-provided "
            "local repo path with explicit branch and validation controls"
        ),
    }
    validation = validate_issue_fix_acceptance_loop_packet(packet)
    packet["ok"] = bool(packet["ok"] and validation["ok"])
    packet["validation"] = validation
    return packet


def validate_issue_fix_acceptance_loop_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != ISSUE_FIX_ACCEPTANCE_LOOP_SCHEMA_VERSION:
        errors.append("packet schema_version must be issue_fix_acceptance_loop_v0")
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "issue_body_captured",
        "comment_bodies_captured",
        "local_paths_captured",
        "private_repo_state_read",
        "destructive_git_used",
    ):
        if packet.get(key) is not False:
            errors.append(f"packet {key} must be false")

    artifact = (
        packet.get("validated_fix_artifact")
        if isinstance(packet.get("validated_fix_artifact"), Mapping)
        else {}
    )
    if artifact.get("schema_version") != ISSUE_FIX_VALIDATED_FIX_ARTIFACT_SCHEMA_VERSION:
        errors.append("validated fix artifact has wrong schema")
    if artifact.get("fix_artifact_ready") is not True:
        errors.append("validated fix artifact must be ready")
    repro = artifact.get("repro_before") if isinstance(artifact.get("repro_before"), Mapping) else {}
    after = (
        artifact.get("validation_after")
        if isinstance(artifact.get("validation_after"), Mapping)
        else {}
    )
    patch = artifact.get("patch") if isinstance(artifact.get("patch"), Mapping) else {}
    if repro.get("passed") is not False:
        errors.append("repro must fail before patch")
    if patch.get("patch_applied") is not True:
        errors.append("patch must be applied")
    if after.get("passed") is not True:
        errors.append("validation must pass after patch")
    for command in (repro, after):
        if command.get("stdout_captured") is not False:
            errors.append("validation stdout must not be captured")
        if command.get("stderr_captured") is not False:
            errors.append("validation stderr must not be captured")
        if command.get("local_path_captured") is not False:
            errors.append("validation local path must not be captured")
    if patch.get("file") != "calculator.py":
        errors.append("patch file must be repo-relative")
    if patch.get("local_path_captured") is not False:
        errors.append("patch local path must not be captured")

    repo_branch = artifact.get("repo_branch")
    if isinstance(repo_branch, Mapping):
        if repo_branch.get("branch_created") is not True:
            errors.append("repo branch must be created")
        if repo_branch.get("external_remote_used") is not False:
            errors.append("repo branch fixture must not use an external remote")
        if repo_branch.get("local_path_captured") is not False:
            errors.append("repo branch local path must not be captured")
    git_steps = artifact.get("git_steps")
    if isinstance(git_steps, list):
        for step in git_steps:
            if not isinstance(step, Mapping):
                errors.append("git_steps must contain objects")
                continue
            if step.get("passed") is not True:
                errors.append(f"git step failed: {step.get('command_label')}")
            if step.get("stdout_captured") is not False:
                errors.append("git stdout must not be captured")
            if step.get("stderr_captured") is not False:
                errors.append("git stderr must not be captured")
            if step.get("local_path_captured") is not False:
                errors.append("git local path must not be captured")

    review = (
        artifact.get("review_packet")
        if isinstance(artifact.get("review_packet"), Mapping)
        else {}
    )
    if review.get("ready") is not True:
        errors.append("review packet must be ready")
    for key in ("external_issue_comment_performed", "external_pr_created", "merge_performed"):
        if review.get(key) is not False:
            errors.append(f"review packet {key} must be false")

    return {
        "schema_version": "issue_fix_acceptance_loop_validation_v0",
        "ok": not errors,
        "errors": errors,
        "steps_count": len(packet.get("steps") or []),
        "validated_fix_artifact_ready": artifact.get("fix_artifact_ready") is True,
    }


def render_issue_fix_acceptance_loop_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Issue Fix Acceptance Loop",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- workspace_mode: `{payload.get('workspace_mode')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- local_paths_captured: `{payload.get('local_paths_captured')}`",
        f"- destructive_git_used: `{payload.get('destructive_git_used')}`",
    ]
    artifact = payload.get("validated_fix_artifact")
    if isinstance(artifact, Mapping):
        lines.extend(
            [
                "",
                "## Validated Fix Artifact",
                "",
                f"- fix_artifact_ready: `{artifact.get('fix_artifact_ready')}`",
                f"- pr_review_packet_ready: `{artifact.get('pr_review_packet_ready')}`",
            ]
        )
        repo_branch = artifact.get("repo_branch")
        if isinstance(repo_branch, Mapping):
            lines.extend(
                [
                    f"- repo_mode: `{repo_branch.get('repo_mode')}`",
                    f"- issue_branch: `{repo_branch.get('issue_branch')}`",
                    f"- branch_created: `{repo_branch.get('branch_created')}`",
                ]
            )
        repro = artifact.get("repro_before")
        after = artifact.get("validation_after")
        patch = artifact.get("patch")
        if isinstance(repro, Mapping) and isinstance(after, Mapping):
            lines.extend(
                [
                    f"- repro_before_passed: `{repro.get('passed')}`",
                    f"- validation_after_passed: `{after.get('passed')}`",
                ]
            )
        if isinstance(patch, Mapping):
            lines.append(f"- patch_file: `{patch.get('file')}`")
    steps = payload.get("steps")
    if isinstance(steps, list):
        lines.extend(["", "## Steps", ""])
        for step in steps:
            if isinstance(step, Mapping):
                lines.append(f"- `{step.get('step')}`: {step.get('result')}")
    validation = payload.get("validation")
    if isinstance(validation, Mapping):
        errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
        lines.extend(
            [
                "",
                "## Validation",
                "",
                f"- validation_ok: `{validation.get('ok')}`",
                f"- validated_fix_artifact_ready: `{validation.get('validated_fix_artifact_ready')}`",
                f"- error_count: `{len(errors)}`",
            ]
        )
    if payload.get("error"):
        lines.extend(["", "## Error", "", str(payload.get("error"))])
    return "\n".join(lines) + "\n"
