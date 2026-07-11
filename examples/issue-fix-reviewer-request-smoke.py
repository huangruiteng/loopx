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
from loopx.capabilities.issue_fix.cli import (  # noqa: E402
    _materialize_goal_reviewer_notification_lifecycle,
)
from loopx.capabilities.issue_fix.reviewer_notification import (  # noqa: E402
    reviewer_notification_receipts_from_state,
    with_reviewer_notification_receipts,
)
from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.capabilities.issue_fix.reviewer_recommendation import (  # noqa: E402
    ISSUE_FIX_REVIEWER_SOURCES_INPUT_SCHEMA_VERSION,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    default_issue_fix_domain_state_ledger_path,
    persist_issue_fix_reviewer_notification_receipts,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)


PRIVATE_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"/tmp/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"oc_[A-Za-z0-9_-]+"),
    re.compile(r"ou_[A-Za-z0-9_-]+"),
    re.compile(r"private-lark-profile"),
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


def semantic_reviewer_comment(
    login: str = "Service-Owner",
    *,
    body: str | None = None,
    url: str = "https://github.com/owner/repo/pull/42#issuecomment-1002",
) -> dict[str, Any]:
    return {
        "author": {"login": "current-author"},
        "body": body
        or (
            f"@{login} could you please take a look when convenient? Thanks! "
            "@fallback-owner FYI."
        ),
        "url": url,
    }


def metadata(
    *,
    requested: list[str] | None = None,
    comments: list[dict[str, Any]] | None = None,
    reviewed: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "author": {"login": "current-author"},
        "closingIssuesReferences": [
            {
                "number": 40,
                "title": "Consistency check accepts unsupported file URIs",
            }
        ],
        "comments": comments or [],
        "isDraft": False,
        "reviewRequests": [{"login": login} for login in (requested or [])],
        "reviews": [
            {"author": {"login": login}} for login in (reviewed or [])
        ],
        "state": "OPEN",
        "title": "fix: reject file URI for consistency check",
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


class FakeCombinedRunner:
    def __init__(self, github: FakeGitHubRunner) -> None:
        self.github = github
        self.lark_calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> dict[str, Any]:
        command = list(args)
        if command[0] == "gh":
            return self.github(command)
        if command[-4:] == ["auth", "status", "--verify", "--json"]:
            self.lark_calls.append(command)
            if command[2] == "fixture-reader-profile":
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "identities": {
                                "user": {"available": True, "verified": True}
                            }
                        }
                    ),
                    "stderr": "",
                }
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "identities": {
                            "bot": {
                                "available": True,
                                "verified": True,
                                "appName": "Project Review Bot",
                            }
                        }
                    }
                ),
                "stderr": "",
            }
        if "chat.members" in command and "get" in command:
            self.lark_calls.append(command)
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {"items": [{"member_id": "ou_private_member"}]}
                ),
                "stderr": "",
            }
        if "+messages-send" in command:
            self.lark_calls.append(command)
            return {
                "returncode": 0,
                "stdout": json.dumps({"data": {"message_id": "om_fixture"}}),
                "stderr": "",
            }
        if "+messages-mget" in command:
            self.lark_calls.append(command)
            send_call = next(
                call for call in self.lark_calls if "+messages-send" in call
            )
            content = send_call[send_call.index("--content") + 1]
            assert "请帮忙 review PR #42（修复 #40）" in content, content
            assert "reject file URI for consistency check" in content, content
            assert "loopx-reviewer-notification" not in content, content
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "items": [
                            {
                                "message_id": "om_fixture",
                                "body": {"content": content},
                            }
                        ]
                    }
                ),
                "stderr": "",
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

        sinks_input = {
            "schema_version": "issue_fix_reviewer_notification_sinks_input_v0",
            "receipts": [],
            "sinks": [
                {
                    "sink_kind": "lark_chat",
                    "sink_instance_key": "fixture-review-lane",
                    "identity_scope": "project_dedicated",
                    "bot_profile": "private-lark-profile",
                    "bot_display_name": "Project Review Bot",
                    "destination_id": "oc_private_destination",
                    "reviewer_identities": {
                        "@service-owner": {
                            "member_id": "ou_private_member",
                            "display_name": "Service Owner",
                        }
                    },
                }
            ],
        }
        combined = FakeCombinedRunner(
            FakeGitHubRunner(
                before=metadata(),
                after=metadata(requested=["service-owner"]),
            )
        )
        with_secondary = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            notification_sinks_input=sinks_input,
            execute=True,
            runner=combined,
        )
        assert with_secondary["ok"] is True, with_secondary
        assert with_secondary["reviewer_notification_verified"] is True
        assert with_secondary["secondary_notification_status"] == "sent_verified"
        assert with_secondary["secondary_notification_verified"] is True
        assert with_secondary["secondary_notifications"]["receipts"]
        assert len(combined.lark_calls) == 3
        assert_public_safe(with_secondary)

        reviewed_combined = FakeCombinedRunner(
            FakeGitHubRunner(before=metadata(reviewed=["service-owner"]))
        )
        already_reviewed = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            notification_sinks_input=sinks_input,
            execute=True,
            runner=reviewed_combined,
        )
        assert already_reviewed["ok"] is True, already_reviewed
        assert already_reviewed["reviewer_notification_verified"] is True
        assert already_reviewed["secondary_notification_status"] == (
            "skipped_reviewer_already_reviewed"
        )
        assert already_reviewed["secondary_notification_verified"] is False
        assert reviewed_combined.lark_calls == []
        assert_public_safe(already_reviewed)

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
            after=metadata(
                comments=[
                    semantic_reviewer_comment(
                        url=fallback_url,
                        body=(
                            "@service-owner 请协助 review：本 PR 修复 "
                            "#40「Consistency check accepts unsupported file URIs」，"
                            "改动是「fix: reject file URI for consistency check」。"
                            "必要性、验证与风险已写在 PR 描述中，谢谢！"
                        ),
                    )
                ]
            ),
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
        assert "#40" in comment_body
        assert "Consistency check accepts unsupported file URIs" in comment_body
        assert "fix: reject file URI for consistency check" in comment_body
        assert "必要性、验证与风险已写在 PR 描述中" in comment_body
        assert "issue-fix-reviewer-notification" not in comment_body
        assert_public_safe(fallback)

        fallback_retry_runner = FakeGitHubRunner(
            before=permission_runner.after
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
        assert fallback_retry["reviewer_notification_mode"] == (
            "existing_review_comment"
        )
        assert fallback_retry["reviewer_notification_verified"] is True
        assert fallback_retry["comment_fallback_performed"] is False
        assert fallback_retry["comment_fallback_verified"] is False
        assert fallback_retry["existing_comment_notification_verified"] is True
        assert fallback_retry["reviewer_comment_url"] == fallback_url
        assert fallback_retry["external_writes_performed"] is False
        assert fallback_retry["transition"]["action_kind"].endswith("already_covered")
        assert fallback_retry_runner.edits == 0
        assert fallback_retry_runner.comments == 0
        assert_public_safe(fallback_retry)

        semantic_url = "https://github.com/owner/repo/pull/42#issuecomment-1002"
        semantic_retry_runner = FakeGitHubRunner(
            before=metadata(
                comments=[semantic_reviewer_comment(url=semantic_url)]
            )
        )
        semantic_retry = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=semantic_retry_runner,
        )
        assert semantic_retry["ok"] is True, semantic_retry
        assert semantic_retry["selected_reviewers"] == []
        assert semantic_retry["existing_marker_comment_notified_reviewers"] == []
        assert semantic_retry["existing_semantic_comment_notified_reviewers"] == [
            "@service-owner"
        ]
        assert semantic_retry["existing_comment_notified_reviewers"] == [
            "@service-owner"
        ]
        assert semantic_retry["notified_reviewers"] == ["@service-owner"]
        assert semantic_retry["reviewer_notification_mode"] == (
            "existing_review_comment"
        )
        assert semantic_retry["reviewer_notification_verified"] is True
        assert semantic_retry["existing_comment_notification_verified"] is True
        assert semantic_retry["comment_fallback_performed"] is False
        assert semantic_retry["comment_fallback_verified"] is False
        assert semantic_retry["reviewer_comment_url"] == semantic_url
        assert semantic_retry["external_writes_performed"] is False
        assert semantic_retry["transition"]["action_kind"].endswith(
            "already_covered"
        )
        assert "existing explicit review-request comment" in semantic_retry[
            "transition"
        ]["reason"]
        assert semantic_retry_runner.edits == 0
        assert semantic_retry_runner.comments == 0
        assert_public_safe(semantic_retry)

        discussion_comment = semantic_reviewer_comment(
            login="service-owner",
            body=(
                "@service-owner thanks for the context. The release owner will "
                "decide who should review this later."
            ),
        )
        discussion_runner = FakeGitHubRunner(
            before=metadata(comments=[discussion_comment]),
            after=metadata(
                requested=["service-owner"], comments=[discussion_comment]
            ),
        )
        discussion = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            base_ref="main",
            execute=True,
            runner=discussion_runner,
        )
        assert discussion["ok"] is True, discussion
        assert discussion["existing_semantic_comment_notified_reviewers"] == []
        assert discussion["selected_reviewers"] == ["@service-owner"]
        assert discussion["review_request_verified"] is True
        assert discussion_runner.edits == 1
        assert discussion_runner.comments == 0
        assert_public_safe(discussion)

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
        cli_sinks_input = json.loads(json.dumps(sinks_input))
        cli_sinks_input["sinks"][0]["reviewer_identities"] = {
            "@map-owner": {
                "member_id": "ou_private_member",
                "display_name": "Map Owner",
            }
        }
        notification_sinks_path = path / "notification-sinks.json"
        write(notification_sinks_path, json.dumps(cli_sinks_input))
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
                "--notification-sinks-json",
                str(notification_sinks_path),
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
        assert cli_packet["secondary_notification_status"] == "preview_ready"
        assert cli_packet["secondary_notifications"]["results"][0][
            "private_destination_captured"
        ] is False
        assert_public_safe(cli_packet)

        goal_id = "reviewer-request-default-fixture"
        goal_config = json.loads(json.dumps(cli_sinks_input))
        goal_sink = goal_config["sinks"][0]
        goal_sink.pop("bot_profile")
        goal_sink.update(
            {
                "reader_profile": "fixture-reader-profile",
                "reader_identity": "user",
                "sender_profile": "fixture-sender-profile",
                "sender_identity": "bot",
            }
        )
        goal_config_path = (
            path
            / ".loopx/config/issue-fix/reviewer-notification-sinks.json"
        )
        write(goal_config_path, json.dumps(goal_config))
        registry = path / ".loopx/registry.json"
        write(
            registry,
            json.dumps(
                {
                    "schema_version": 1,
                    "goals": [
                        {
                            "id": goal_id,
                            "repo": str(path),
                            "control_plane": {
                                "issue_fix": {
                                    "reviewer_notification": {
                                        "enabled": True,
                                        "config_path": (
                                            ".loopx/config/issue-fix/"
                                            "reviewer-notification-sinks.json"
                                        ),
                                    }
                                }
                            },
                        }
                    ],
                }
            ),
        )
        goal_default_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
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
                "--goal-id",
                goal_id,
                "--project",
                str(path),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        goal_default_packet = json.loads(goal_default_cli.stdout)
        assert goal_default_packet["secondary_notification_source"] == "goal_default"
        assert goal_default_packet["secondary_notification_status"] == "preview_ready"
        assert_public_safe(goal_default_packet)

        lifecycle_path = default_issue_fix_domain_state_ledger_path(
            project=path,
            goal_id=goal_id,
        )
        invalid_execute_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--format",
                "json",
                "issue-fix",
                "reviewer-request",
                "--url",
                "https://github.com/owner/repo/pull/42",
                "--repo-path",
                str(path),
                "--changed-file",
                "src/map_only.py",
                "--metadata-json",
                str(metadata_path),
                "--goal-id",
                goal_id,
                "--project",
                str(path),
                "--execute",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert invalid_execute_cli.returncode != 0
        assert "preview-only" in invalid_execute_cli.stdout
        assert not lifecycle_path.exists()

        unrelated_cwd = path / "unrelated-control-plane"
        write(
            unrelated_cwd / ".loopx/registry.json",
            json.dumps({"schema_version": 1, "goals": []}),
        )
        project_registry_cli = subprocess.run(
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
                "--goal-id",
                goal_id,
                "--project",
                str(path),
            ],
            cwd=unrelated_cwd,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert project_registry_cli.returncode == 0, project_registry_cli.stdout
        project_registry_packet = json.loads(project_registry_cli.stdout)
        assert (
            project_registry_packet["secondary_notification_source"] == "goal_default"
        )
        assert (
            project_registry_packet["secondary_notification_status"] == "preview_ready"
        )
        assert_public_safe(project_registry_packet)

        lifecycle = _materialize_goal_reviewer_notification_lifecycle(
            ledger_path=lifecycle_path,
            url="https://github.com/owner/repo/pull/42",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [],
                "closingIssuesReferences": [{"number": 40}],
            },
        )
        assert lifecycle["observation"]["issue_ref"] == "issues_40"
        assert lifecycle["domain_state_projection"]["write_performed"] is True
        repeated_materialize = _materialize_goal_reviewer_notification_lifecycle(
            ledger_path=lifecycle_path,
            url="https://github.com/owner/repo/pull/42",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [],
                "closingIssuesReferences": [{"number": 40}],
            },
        )
        assert repeated_materialize["domain_state_projection"][
            "write_performed"
        ] is False
        legacy_lifecycle = json.loads(
            lifecycle_path.read_text(encoding="utf-8").splitlines()[0]
        )
        legacy_lifecycle.pop("maintainer_correction_body_captured")
        lifecycle_path.write_text(
            json.dumps(legacy_lifecycle, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        goal_execute_runner = FakeCombinedRunner(
            FakeGitHubRunner(
                before=metadata(),
                after=metadata(requested=["map-owner"]),
            )
        )
        goal_execute = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            changed_files=["src/map_only.py"],
            base_ref="main",
            exclude_reviewers=["@fallback-owner"],
            reviewer_sources_input=reviewer_sources,
            notification_sinks_input=goal_config,
            execute=True,
            runner=goal_execute_runner,
        )
        assert goal_execute["secondary_notification_status"] == "sent_verified"
        assert len(goal_execute_runner.lark_calls) == 6
        receipt = goal_execute["secondary_notifications"]["receipts"][0]
        receipt_write = persist_issue_fix_reviewer_notification_receipts(
            lifecycle_path,
            legacy_lifecycle,
            [receipt],
        )
        assert receipt_write["write_performed"] is True, receipt_write
        stored_lifecycle = json.loads(
            lifecycle_path.read_text(encoding="utf-8").splitlines()[0]
        )
        assert stored_lifecycle["reviewer_notification_receipts"] == [receipt]
        assert stored_lifecycle["maintainer_correction_body_captured"] is False
        unsafe_lifecycle = json.loads(json.dumps(stored_lifecycle))
        unsafe_lifecycle["maintainer_correction_body_captured"] = True
        try:
            persist_issue_fix_reviewer_notification_receipts(
                lifecycle_path,
                unsafe_lifecycle,
                ["sha256:" + "f" * 64],
            )
        except ValueError as exc:
            assert "maintainer_correction_body_captured=false" in str(exc)
        else:
            raise AssertionError("truthy legacy capture flag must remain blocked")
        later_monitor = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/42",
            issue_ref="issues_40",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [
                    {"name": "focused", "conclusion": "SUCCESS"}
                ],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(lifecycle_path, later_monitor)
        stored_lifecycle = json.loads(
            lifecycle_path.read_text(encoding="utf-8").splitlines()[0]
        )
        assert stored_lifecycle["reviewer_notification_receipts"] == [receipt]
        retry_config = with_reviewer_notification_receipts(
            goal_config,
            reviewer_notification_receipts_from_state(stored_lifecycle),
        )
        restarted_runner = FakeCombinedRunner(
            FakeGitHubRunner(before=metadata(requested=["map-owner"]))
        )
        restarted = build_issue_fix_reviewer_request_packet(
            repo_path=path,
            url="https://github.com/owner/repo/pull/42",
            changed_files=["src/map_only.py"],
            base_ref="main",
            exclude_reviewers=["@fallback-owner"],
            reviewer_sources_input=reviewer_sources,
            notification_sinks_input=retry_config,
            execute=True,
            runner=restarted_runner,
        )
        assert restarted["secondary_notification_status"] == "already_notified"
        assert restarted["secondary_notification_verified"] is True
        assert restarted_runner.lark_calls == []
        repeated_receipt_write = persist_issue_fix_reviewer_notification_receipts(
            lifecycle_path,
            stored_lifecycle,
            [receipt],
        )
        assert repeated_receipt_write["status"] == "unchanged"
        assert repeated_receipt_write["write_performed"] is False
        assert_public_safe(restarted)
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
