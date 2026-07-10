#!/usr/bin/env python3
"""Smoke-test authority-gated, verified issue-fix reviewer requests."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.reviewer_request import (  # noqa: E402
    ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION,
    build_issue_fix_reviewer_request_packet,
)


PRIVATE_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"/tmp/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
)


def run_git(repo: Path, *args: str, author: str = "Fixture Author") -> None:
    login = author.lower().replace(" ", "-")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": author,
        "GIT_AUTHOR_EMAIL": f"{login}@users.noreply.github.com",
        "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": f"{login}@users.noreply.github.com",
    }
    subprocess.run(
        ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit(repo: Path, message: str, *, author: str) -> None:
    run_git(repo, "add", "-A", author=author)
    run_git(repo, "commit", "-m", message, author=author)


def metadata(*, requested: list[str] | None = None) -> dict[str, Any]:
    return {
        "author": {"login": "current-author"},
        "isDraft": False,
        "reviewRequests": [{"login": login} for login in (requested or [])],
        "reviews": [],
        "state": "OPEN",
        "url": "https://github.com/owner/repo/pull/42",
    }


class FakeGitHubRunner:
    def __init__(
        self,
        *,
        before: dict[str, Any],
        after: dict[str, Any] | None = None,
        edit_returncode: int = 0,
    ) -> None:
        self.before = before
        self.after = after if after is not None else before
        self.edit_returncode = edit_returncode
        self.calls: list[list[str]] = []
        self.edits = 0

    def __call__(self, args: list[str]) -> dict[str, Any]:
        command = list(args)
        self.calls.append(command)
        if command[:3] == ["gh", "pr", "view"]:
            payload = self.after if self.edits else self.before
            return {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""}
        if command[:3] == ["gh", "pr", "edit"]:
            self.edits += 1
            return {
                "returncode": self.edit_returncode,
                "stdout": "",
                "stderr": "provider failure" if self.edit_returncode else "",
            }
        raise AssertionError(command)


def assert_public_safe(packet: dict[str, Any]) -> None:
    text = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for pattern in PRIVATE_PATTERNS:
        assert not pattern.search(text), pattern.pattern
    assert "@users.noreply.github.com" not in text
    assert "provider failure" not in text
    assert packet["local_paths_captured"] is False
    assert packet["raw_provider_payload_captured"] is False
    assert packet["raw_git_output_captured"] is False
    assert packet["commit_emails_captured"] is False


def main() -> int:
    path = Path(tempfile.mkdtemp(prefix="loopx-reviewer-request-"))
    try:
        run_git(path, "init", "-b", "main")
        write(
            path / ".github/CODEOWNERS",
            (
                "* @fallback-owner\n"
                "/src/service.py @current-author @release-bot @service-owner\n"
            ),
        )
        write(path / "src/service.py", "VALUE = 1\n")
        commit(path, "Add service", author="History Owner")
        run_git(path, "checkout", "-b", "feature/reviewer-request")
        write(path / "src/service.py", "VALUE = 2\n")
        commit(path, "Fix service", author="Current Author")

        runner = FakeGitHubRunner(
            before=metadata(),
            after=metadata(requested=["service-owner"]),
        )
        packet = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=runner,
        )
        assert packet["schema_version"] == ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION
        assert packet["ok"] is True, packet
        assert packet["author_handle"] == "@current-author"
        assert packet["author_exclusion_verified"] is True
        assert packet["selected_reviewers"] == ["@service-owner"], packet
        assert "@release-bot" not in packet["selected_reviewers"]
        assert packet["requested_reviewers"] == ["@service-owner"], packet
        assert packet["review_request_performed"] is True
        assert packet["review_request_verified"] is True
        assert packet["external_writes_performed"] is True
        assert packet["transition"]["decision"] == "monitor_continuation"
        assert runner.edits == 1
        assert ["--add-reviewer", "service-owner"] == runner.calls[1][-2:]
        assert_public_safe(packet)

        already_runner = FakeGitHubRunner(
            before=metadata(requested=["service-owner"])
        )
        already = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=already_runner,
        )
        assert already["ok"] is True, already
        assert already["selected_reviewers"] == []
        assert already["external_writes_performed"] is False
        assert already["transition"]["action_kind"].endswith("already_covered")
        assert already_runner.edits == 0
        assert_public_safe(already)

        failed_runner = FakeGitHubRunner(
            before=metadata(),
            edit_returncode=1,
        )
        failed = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=failed_runner,
        )
        assert failed["ok"] is False
        assert failed["blocker"] == "github_review_request_failed"
        assert failed["selected_reviewers"] == ["@service-owner"]
        assert failed["external_writes_performed"] is False
        assert failed["transition"]["decision"] == "blocker"
        assert_public_safe(failed)

        preview = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            provider_payload=metadata(),
        )
        assert preview["ok"] is True, preview
        assert preview["selected_reviewers"] == ["@service-owner"]
        assert preview["external_write_authority_asserted"] is False
        assert preview["external_writes_performed"] is False
        assert preview["transition"]["action_kind"] == "issue_fix_request_top_reviewer"
        assert_public_safe(preview)

        try:
            build_issue_fix_reviewer_request_packet(
                repo_path=path,
                url="https://github.com/owner/repo/pull/42",
                base_ref="main",
                provider_payload=metadata(),
                execute=True,
                runner=FakeGitHubRunner(before=metadata()),
            )
        except ValueError as exc:
            assert "preview-only" in str(exc), exc
        else:
            raise AssertionError("execute mode must not trust supplied PR metadata")

        unsafe_preview = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
        )
        assert unsafe_preview["ok"] is False
        assert unsafe_preview["blocker"].endswith("required_for_safe_preview")
        assert unsafe_preview["selected_reviewers"] == [], unsafe_preview
        assert unsafe_preview["external_writes_performed"] is False
        assert_public_safe(unsafe_preview)

        incomplete_preview = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            provider_payload={},
        )
        assert incomplete_preview["ok"] is False
        assert incomplete_preview["blocker"] == "github_pr_author_unavailable"
        assert incomplete_preview["selected_reviewers"] == []
        assert_public_safe(incomplete_preview)

        author_only_preview = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            provider_payload={"author": {"login": "current-author"}},
        )
        assert author_only_preview["ok"] is False
        assert author_only_preview["blocker"] == "github_pr_state_unavailable"
        assert author_only_preview["selected_reviewers"] == []
        assert_public_safe(author_only_preview)

        metadata_path = path / "pr-metadata.json"
        write(metadata_path, json.dumps(metadata()))
        cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "issue-fix",
                "reviewer-request",
                "--url",
                "https://github.com/owner/repo/pull/42",
                "--repo-path",
                str(path),
                "--base-ref",
                "main",
                "--metadata-json",
                str(metadata_path),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        cli_packet = json.loads(cli.stdout)
        assert cli_packet["selected_reviewers"] == ["@service-owner"]
        assert cli_packet["external_writes_performed"] is False
        assert_public_safe(cli_packet)
    finally:
        shutil.rmtree(path)

    print("issue-fix-reviewer-request-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
