#!/usr/bin/env python3
"""Smoke-test authority-gated, verified issue-fix reviewer notification."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.reviewer_request import (  # noqa: E402
    ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION,
    build_issue_fix_reviewer_request_packet,
)
from loopx.capabilities.issue_fix.reviewer_recommendation import (  # noqa: E402
    ISSUE_FIX_REVIEWER_SOURCES_INPUT_SCHEMA_VERSION,
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


def reviewer_comment(
    login: str = "service-owner",
    *,
    url: str = "https://github.com/owner/repo/pull/42#issuecomment-1001",
) -> dict[str, Any]:
    return {
        "author": {"login": "current-author"},
        "body": (
            f"@{login} could you please review?\n\n"
            "<!-- loopx: issue-fix-reviewer-notification "
            f"reviewer=@{login} -->"
        ),
        "url": url,
    }


def metadata(
    *,
    requested: list[str] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "author": {"login": "current-author"},
        "comments": comments or [],
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
        edit_stderr: str = "",
        comment_returncode: int = 0,
        comment_stdout: str = "",
    ) -> None:
        self.before = before
        self.after = after if after is not None else before
        self.edit_returncode = edit_returncode
        self.edit_stderr = edit_stderr
        self.comment_returncode = comment_returncode
        self.comment_stdout = comment_stdout
        self.calls: list[list[str]] = []
        self.edits = 0
        self.comments = 0

    def __call__(self, args: list[str]) -> dict[str, Any]:
        command = list(args)
        self.calls.append(command)
        if command[:3] == ["gh", "pr", "view"]:
            payload = self.after if self.edits or self.comments else self.before
            return {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""}
        if command[:3] == ["gh", "pr", "edit"]:
            self.edits += 1
            return {
                "returncode": self.edit_returncode,
                "stdout": "",
                "stderr": self.edit_stderr,
            }
        if command[:3] == ["gh", "pr", "comment"]:
            self.comments += 1
            return {
                "returncode": self.comment_returncode,
                "stdout": self.comment_stdout,
                "stderr": (
                    "comment provider failure" if self.comment_returncode else ""
                ),
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
        assert packet["notified_reviewers"] == ["@service-owner"]
        assert packet["reviewer_notification_mode"] == "formal_request"
        assert packet["reviewer_notification_verified"] is True
        assert packet["external_writes_performed"] is True
        assert packet["transition"]["decision"] == "monitor_continuation"
        assert runner.edits == 1
        assert ["--add-reviewer", "service-owner"] == runner.calls[1][-2:]
        assert_public_safe(packet)

        already_runner = FakeGitHubRunner(before=metadata(requested=["service-owner"]))
        already = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=already_runner,
        )
        assert already["ok"] is True, already
        assert already["selected_reviewers"] == []
        assert already["notified_reviewers"] == ["@service-owner"]
        assert already["reviewer_notification_mode"] == "formal_request"
        assert already["reviewer_notification_verified"] is True
        assert already["external_writes_performed"] is False
        assert already["transition"]["action_kind"].endswith("already_covered")
        assert already_runner.edits == 0
        assert_public_safe(already)

        fallback_url = "https://github.com/owner/repo/pull/42#issuecomment-1001"
        permission_runner = FakeGitHubRunner(
            before=metadata(),
            after=metadata(comments=[reviewer_comment(url=fallback_url)]),
            edit_returncode=1,
            edit_stderr="HTTP 404: Not Found",
        )
        fallback = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=permission_runner,
        )
        assert fallback["ok"] is True, fallback
        assert fallback["selected_reviewers"] == ["@service-owner"]
        assert fallback["requested_reviewers"] == []
        assert fallback["notified_reviewers"] == ["@service-owner"]
        assert fallback["review_request_performed"] is False
        assert fallback["review_request_verified"] is False
        assert fallback["reviewer_notification_mode"] == "comment_fallback"
        assert fallback["reviewer_notification_verified"] is True
        assert fallback["comment_fallback_performed"] is True
        assert fallback["comment_fallback_verified"] is True
        assert fallback["reviewer_comment_url"] == fallback_url
        assert fallback["external_writes_performed"] is True
        assert fallback["transition"]["action_kind"].endswith(
            "comment_fallback_verified"
        )
        assert permission_runner.edits == 1
        assert permission_runner.comments == 1
        comment_call = permission_runner.calls[2]
        comment_body = comment_call[comment_call.index("--body") + 1]
        assert "@service-owner" in comment_body
        assert "issue-fix-reviewer-notification" in comment_body
        assert_public_safe(fallback)

        fallback_retry_runner = FakeGitHubRunner(
            before=metadata(comments=[reviewer_comment(url=fallback_url)])
        )
        fallback_retry = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=fallback_retry_runner,
        )
        assert fallback_retry["ok"] is True, fallback_retry
        assert fallback_retry["selected_reviewers"] == []
        assert fallback_retry["existing_comment_notified_reviewers"] == [
            "@service-owner"
        ]
        assert fallback_retry["notified_reviewers"] == ["@service-owner"]
        assert fallback_retry["reviewer_notification_mode"] == "comment_fallback"
        assert fallback_retry["reviewer_notification_verified"] is True
        assert fallback_retry["comment_fallback_performed"] is False
        assert fallback_retry["comment_fallback_verified"] is True
        assert fallback_retry["reviewer_comment_url"] == fallback_url
        assert fallback_retry["external_writes_performed"] is False
        assert fallback_retry["transition"]["action_kind"].endswith("already_covered")
        assert fallback_retry_runner.edits == 0
        assert fallback_retry_runner.comments == 0
        assert_public_safe(fallback_retry)

        comment_blocked_runner = FakeGitHubRunner(
            before=metadata(),
            edit_returncode=1,
            edit_stderr="HTTP 403: Resource not accessible by integration",
            comment_returncode=1,
        )
        comment_blocked = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=comment_blocked_runner,
        )
        assert comment_blocked["ok"] is False
        assert comment_blocked["blocker"] == "github_reviewer_comment_fallback_failed"
        assert comment_blocked["comment_fallback_performed"] is False
        assert comment_blocked["external_writes_performed"] is False
        assert comment_blocked_runner.edits == 1
        assert comment_blocked_runner.comments == 1
        assert_public_safe(comment_blocked)

        failed_runner = FakeGitHubRunner(
            before=metadata(),
            edit_returncode=1,
            edit_stderr="provider failure",
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
        assert failed_runner.comments == 0
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

        reviewer_sources = {
            "schema_version": ISSUE_FIX_REVIEWER_SOURCES_INPUT_SCHEMA_VERSION,
            "sources": [
                {
                    "source_id": "public-maintainer-map",
                    "source_kind": "maintainer_map",
                    "reference": "https://github.com/owner/repo/issues/10",
                    "trust": "verified",
                    "freshness": "current",
                    "observed_at": "2026-07-10T00:00:00Z",
                    "routes": [
                        {
                            "route_id": "map-only-module",
                            "match_kind": "path_prefix",
                            "pattern": "src/map_only.py",
                            "primary_reviewers": ["@map-owner"],
                            "fallback_reviewers": ["@map-backup"],
                        }
                    ],
                }
            ],
        }
        source_preview = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            changed_files=["src/map_only.py"],
            base_ref="main",
            exclude_reviewers=["@fallback-owner"],
            reviewer_sources_input=reviewer_sources,
            provider_payload=metadata(),
        )
        assert source_preview["ok"] is True, source_preview
        assert source_preview["selected_reviewers"] == ["@map-owner"]
        assert source_preview["reviewer_source_count"] == 1
        assert source_preview["reviewer_source_refs"] == [
            "https://github.com/owner/repo/issues/10"
        ]
        source_candidate = source_preview["recommendation_candidates"][0]
        assert source_candidate["reviewer_handle"] == "@map-owner"
        assert "repository_declared_primary_contact" in source_candidate["reason_codes"]
        assert_public_safe(source_preview)

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
        reviewer_sources_path = path / "reviewer-sources.json"
        write(reviewer_sources_path, json.dumps(reviewer_sources))
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
                "--changed-file",
                "src/map_only.py",
                "--exclude-reviewer",
                "@fallback-owner",
                "--reviewer-sources-json",
                str(reviewer_sources_path),
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
        assert cli_packet["selected_reviewers"] == ["@map-owner"]
        assert cli_packet["reviewer_source_count"] == 1
        assert cli_packet["external_writes_performed"] is False
        assert_public_safe(cli_packet)
    finally:
        for attempt in range(10):
            try:
                shutil.rmtree(path)
                break
            except FileNotFoundError:
                break
            except OSError as exc:
                if exc.errno != errno.ENOTEMPTY or attempt == 9:
                    raise
                time.sleep(0.05)

    print("issue-fix-reviewer-request-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
