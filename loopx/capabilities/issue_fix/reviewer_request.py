from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .metadata_preview import normalise_github_issue_reference
from .reviewer_notification import (
    NotificationSinkAdapter,
    build_issue_fix_reviewer_notification_sinks_result,
)
from .reward_memory import (
    run_issue_fix_reviewer_artifact_automatic_reward_memory,
    run_issue_fix_reviewer_notification_automatic_reward_memory,
)
from .reviewer_recommendation import build_issue_fix_reviewer_recommendation_packet


ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION = "issue_fix_reviewer_request_v0"
REVIEWER_BOT_HANDLE_PATTERN = re.compile(
    r"(?:^|[-_.])bot(?:$|[-_.])|\[bot\]$",
    re.IGNORECASE,
)
REVIEWER_COMMENT_MARKER_PATTERN = re.compile(
    r"<!--\s*loopx:\s*issue-fix-reviewer-notification\s+"
    r"reviewer=@?([A-Za-z0-9-]+(?:/[A-Za-z0-9_.-]+)?)\s*-->",
    re.IGNORECASE,
)
REVIEWER_COMMENT_MENTION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])@([A-Za-z0-9-]+(?:/[A-Za-z0-9_.-]+)?)",
    re.IGNORECASE,
)
REVIEWER_COMMENT_INTENT_PATTERNS = (
    re.compile(
        r"\b(?:could|can|would)\s+you(?:\s+please)?\s+"
        r"(?:review|take\s+a\s+look|look\s+over)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bplease\s+(?:review|take\s+a\s+look|look\s+over)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:请|麻烦|辛苦|帮忙|协助)[^\n]{0,32}"
        r"(?:review|code\s*review|\bcr\b|看一下|看下|审阅|评审)",
        re.IGNORECASE,
    ),
)
GITHUB_REVIEW_REQUEST_PERMISSION_PATTERN = re.compile(
    r"(?:HTTP\s+(?:403|404)|resource not accessible|"
    r"must have (?:push|triage|write) access|not found|"
    r"reviews? may only be requested from collaborators|not a collaborator)",
    re.IGNORECASE,
)

CommandRunner = Callable[[Sequence[str]], Mapping[str, Any]]


def _default_runner(args: Sequence[str]) -> Mapping[str, Any]:
    result = subprocess.run(
        list(args),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _normalise_login(value: Any) -> str | None:
    text = public_safe_compact_text(value, limit=100)
    if not text:
        return None
    text = text.strip().lstrip("@").lower()
    return f"@{text}" if text else None


def _is_automated_reviewer_handle(value: Any) -> bool:
    handle = _normalise_login(value)
    return bool(handle and REVIEWER_BOT_HANDLE_PATTERN.search(handle.lstrip("@")))


def _secondary_notification_targets(
    *,
    primary_handles: Sequence[str],
    candidates: Sequence[Any],
    sinks_input: Mapping[str, Any],
    allow_candidate_fallback: bool = True,
) -> tuple[list[str], list[str]]:
    """Choose sink-resolvable reviewers without changing GitHub coverage.

    The primary handles are reviewers already covered on GitHub or selected for
    a new GitHub request. Ranked recommendation candidates are fallback-only for
    a newly selected request. Existing GitHub coverage must stay bound to the
    same reviewer across secondary sinks; an unresolved mapping skips the sink
    instead of notifying another person. Sink adapters still perform the
    authoritative provider and membership verification before sending.
    """

    primary = list(
        dict.fromkeys(
            handle
            for value in primary_handles
            if (handle := _normalise_login(value)) is not None
        )
    )[:3]
    if not primary:
        return [], []

    pool = list(primary)
    for candidate in candidates:
        if (
            not isinstance(candidate, Mapping)
            or candidate.get("requestable") is not True
        ):
            continue
        handle = _normalise_login(candidate.get("reviewer_handle"))
        if handle and not _is_automated_reviewer_handle(handle) and handle not in pool:
            pool.append(handle)

    raw_sinks = sinks_input.get("sinks")
    sinks = raw_sinks if isinstance(raw_sinks, list) else []
    identity_maps: list[dict[str, Any]] = []
    for sink in sinks:
        if not isinstance(sink, Mapping):
            return primary, pool
        raw_identities = sink.get("reviewer_identities")
        if not isinstance(raw_identities, Mapping):
            return primary, pool
        identity_maps.append(
            {
                handle: value
                for raw_handle, value in raw_identities.items()
                if (handle := _normalise_login(raw_handle)) is not None
            }
        )
    if not identity_maps:
        return primary, pool

    target_count = len(primary)
    if not allow_candidate_fallback:
        return (
            [
                handle
                for handle in primary
                if all(
                    isinstance(identities.get(handle), Mapping)
                    for identities in identity_maps
                )
            ][:target_count],
            pool,
        )
    resolved = [
        handle
        for handle in pool
        if all(
            isinstance(identities.get(handle), Mapping) for identities in identity_maps
        )
    ][:target_count]
    return (resolved or primary), pool


def _is_mention_cluster_separator(value: str) -> bool:
    if "\n" in value or "\r" in value:
        return False
    remainder = re.sub(r"\b(?:and|or)\b|[和与及]", "", value, flags=re.IGNORECASE)
    return bool(re.fullmatch(r"[ \t,，、:：&+/]*", remainder))


def _semantic_review_request_mentions(body: str) -> list[str]:
    visible_body = re.sub(r"<!--.*?-->", " ", body, flags=re.DOTALL)
    visible_body = re.sub(r"```.*?```", " ", visible_body, flags=re.DOTALL)
    visible_body = "\n".join(
        line for line in visible_body.splitlines() if not line.lstrip().startswith(">")
    )
    handles: list[str] = []
    mentions = list(REVIEWER_COMMENT_MENTION_PATTERN.finditer(visible_body))
    for intent_pattern in REVIEWER_COMMENT_INTENT_PATTERNS:
        for intent in intent_pattern.finditer(visible_body):
            preceding = [
                mention
                for mention in mentions
                if mention.end() <= intent.start()
                and intent.start() - mention.end() <= 160
            ]
            if not preceding:
                continue
            cluster = [preceding[-1]]
            if not _is_mention_cluster_separator(
                visible_body[cluster[0].end() : intent.start()]
            ):
                continue
            for mention in reversed(preceding[:-1]):
                gap = visible_body[mention.end() : cluster[0].start()]
                if not _is_mention_cluster_separator(gap):
                    break
                cluster.insert(0, mention)
            for mention in cluster:
                handle = _normalise_login(mention.group(1))
                if handle and handle not in handles:
                    handles.append(handle)

    for index, mention in enumerate(mentions):
        next_mention_start = (
            mentions[index + 1].start()
            if index + 1 < len(mentions)
            else len(visible_body)
        )
        window = visible_body[
            mention.end() : min(next_mention_start, mention.end() + 160)
        ]
        if not any(
            pattern.search(window) for pattern in REVIEWER_COMMENT_INTENT_PATTERNS
        ):
            continue
        handle = _normalise_login(mention.group(1))
        if handle and handle not in handles:
            handles.append(handle)
    return handles


def _metadata_identities(
    payload: Mapping[str, Any],
    *,
    repo: str,
    number: int,
) -> dict[str, Any]:
    author = payload.get("author")
    author = author if isinstance(author, Mapping) else {}
    author_handle = _normalise_login(author.get("login"))
    pr_title = public_safe_compact_text(payload.get("title"), limit=180)
    linked_issue_refs: list[str] = []
    linked_issue_summaries: list[str] = []
    raw_issue_refs = payload.get("closingIssuesReferences") or payload.get(
        "closing_issues_references"
    )
    for item in raw_issue_refs or []:
        issue_number = item.get("number") if isinstance(item, Mapping) else None
        if isinstance(issue_number, int):
            issue_ref = f"#{issue_number}"
            if issue_ref not in linked_issue_refs:
                linked_issue_refs.append(issue_ref)
            issue_title = public_safe_compact_text(
                item.get("title") if isinstance(item, Mapping) else None,
                limit=140,
            )
            issue_summary = (
                f"{issue_ref}「{issue_title}」" if issue_title else issue_ref
            )
            if issue_summary not in linked_issue_summaries:
                linked_issue_summaries.append(issue_summary)

    requested: list[str] = []
    for item in payload.get("reviewRequests") or payload.get("review_requests") or []:
        if not isinstance(item, Mapping):
            continue
        handle = _normalise_login(item.get("login"))
        if not handle and item.get("slug"):
            owner = repo.partition("/")[0]
            handle = _normalise_login(f"{owner}/{item.get('slug')}")
        if handle and handle not in requested:
            requested.append(handle)

    reviewed: list[str] = []
    for item in payload.get("reviews") or []:
        if not isinstance(item, Mapping):
            continue
        review_author = item.get("author")
        review_author = review_author if isinstance(review_author, Mapping) else {}
        handle = _normalise_login(review_author.get("login"))
        if handle and handle not in reviewed:
            reviewed.append(handle)
    comment_notified: list[str] = []
    marker_comment_notified: list[str] = []
    semantic_comment_notified: list[str] = []
    comment_urls: dict[str, str] = {}
    for item in payload.get("comments") or []:
        if not isinstance(item, Mapping):
            continue
        body = str(item.get("body") or "")
        raw_url = public_safe_compact_text(item.get("url"), limit=300)
        url = (
            raw_url
            if re.fullmatch(
                rf"https://github\.com/{re.escape(repo)}/pull/{number}"
                r"#issuecomment-\d+",
                raw_url,
            )
            else ""
        )
        marker_handles: list[str] = []
        for login in REVIEWER_COMMENT_MARKER_PATTERN.findall(body):
            handle = _normalise_login(login)
            if handle and handle not in marker_handles:
                marker_handles.append(handle)
            if handle and handle not in marker_comment_notified:
                marker_comment_notified.append(handle)
            if handle and handle not in comment_notified:
                comment_notified.append(handle)
            if handle and url:
                comment_urls[handle] = url
        for handle in _semantic_review_request_mentions(body):
            if handle in marker_handles:
                continue
            if handle not in semantic_comment_notified:
                semantic_comment_notified.append(handle)
            if handle not in comment_notified:
                comment_notified.append(handle)
            if url:
                comment_urls[handle] = url
    return {
        "author_handle": author_handle,
        "pr_title": pr_title,
        "linked_issue_refs": linked_issue_refs[:3],
        "linked_issue_summaries": linked_issue_summaries[:3],
        "requested_reviewers": requested,
        "reviewed_by": reviewed,
        "comment_notified_reviewers": comment_notified,
        "marker_comment_notified_reviewers": marker_comment_notified,
        "semantic_comment_notified_reviewers": semantic_comment_notified,
        "reviewer_comment_urls": comment_urls,
        "state": str(payload.get("state") or "UNKNOWN").upper(),
        "is_draft": payload.get("isDraft") is True or payload.get("is_draft") is True,
    }


def _fetch_pr_metadata(
    *,
    repo: str,
    number: int,
    runner: CommandRunner,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = runner(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "author,closingIssuesReferences,comments,isDraft,reviewRequests,"
                "reviews,state,title,url",
            ]
        )
    except (OSError, subprocess.SubprocessError):
        return None, "github_pr_metadata_unavailable"
    if result.get("returncode") != 0:
        return None, "github_pr_metadata_unavailable"
    try:
        payload = json.loads(str(result.get("stdout") or "{}"))
    except json.JSONDecodeError:
        return None, "github_pr_metadata_invalid"
    return (
        (dict(payload), None)
        if isinstance(payload, Mapping)
        else (None, "github_pr_metadata_invalid")
    )


def _request_reviewers(
    *,
    repo: str,
    number: int,
    reviewer_handles: Sequence[str],
    runner: CommandRunner,
) -> tuple[str | None, bool]:
    args = ["gh", "pr", "edit", str(number), "--repo", repo]
    for handle in reviewer_handles:
        login = handle.lstrip("@")
        if "/" in login:
            args.extend(["--add-team-reviewer", login.partition("/")[2]])
        else:
            args.extend(["--add-reviewer", login])
    try:
        result = runner(args)
    except (OSError, subprocess.SubprocessError):
        return "github_review_request_failed", False
    if result.get("returncode") == 0:
        return None, False
    provider_error = " ".join(
        str(result.get(key) or "") for key in ("stderr", "stdout")
    )
    permission_denied = bool(
        GITHUB_REVIEW_REQUEST_PERMISSION_PATTERN.search(provider_error)
    )
    return (
        "github_review_request_permission_denied"
        if permission_denied
        else "github_review_request_failed",
        permission_denied,
    )


def _reviewer_comment_body(
    reviewer_handles: Sequence[str],
    *,
    pr_title: str | None,
    linked_issue_summaries: Sequence[str],
) -> str:
    review_requests = "；".join(
        f"{handle if handle.startswith('@') else f'@{handle}'} 请协助 review"
        for handle in reviewer_handles
    )
    issue_context = "、".join(linked_issue_summaries) or "关联 issue"
    change_context = public_safe_compact_text(pr_title, limit=180)
    change_summary = f"，改动是「{change_context}」" if change_context else ""
    return (
        f"{review_requests}：本 PR 修复 {issue_context}{change_summary}。"
        "必要性、验证与风险已写在 PR 描述中，谢谢！"
    )


def _comment_reviewer_notification(
    *,
    repo: str,
    number: int,
    reviewer_handles: Sequence[str],
    pr_title: str | None,
    linked_issue_summaries: Sequence[str],
    runner: CommandRunner,
) -> tuple[str | None, str | None, bool]:
    try:
        result = runner(
            [
                "gh",
                "pr",
                "comment",
                str(number),
                "--repo",
                repo,
                "--body",
                _reviewer_comment_body(
                    reviewer_handles,
                    pr_title=pr_title,
                    linked_issue_summaries=linked_issue_summaries,
                ),
            ]
        )
    except (OSError, subprocess.SubprocessError):
        return None, "github_reviewer_comment_fallback_failed", False
    if result.get("returncode") != 0:
        return None, "github_reviewer_comment_fallback_failed", False
    expected = re.compile(
        rf"https://github\.com/{re.escape(repo)}/pull/{number}#issuecomment-\d+"
    )
    match = expected.search(str(result.get("stdout") or ""))
    return (match.group(0) if match else None), None, True


def _transition(
    *,
    decision: str,
    action_kind: str,
    reason: str,
    material_change: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "issue_fix_reviewer_request_transition_v0",
        "decision": decision,
        "action_kind": action_kind,
        "reason": reason,
        "material_change": material_change,
        "external_write_gate_required": True,
    }


def build_issue_fix_reviewer_request_packet(
    *,
    repo_path: str | Path,
    url: str,
    changed_files: Sequence[str] = (),
    base_ref: str = "origin/main",
    history_limit: int = 40,
    max_candidates: int = 5,
    max_reviewers: int = 1,
    exclude_reviewers: Sequence[str] = (),
    exclude_author_names: Sequence[str] = (),
    resolved_identities: Mapping[str, Any] | None = None,
    reviewer_sources_input: Mapping[str, Any] | None = None,
    notification_sinks_input: Mapping[str, Any] | None = None,
    notification_sink_adapters: Mapping[str, NotificationSinkAdapter] | None = None,
    reviewer_artifact_reward_memory: Mapping[str, Any] | None = None,
    reviewer_notification_reward_memory: Mapping[str, Any] | None = None,
    reviewer_artifact_required: bool = False,
    provider_payload: Mapping[str, Any] | None = None,
    execute: bool = False,
    generated_at: str | None = "2026-07-10T00:00:00Z",
    notification_delivery_observed_at: str | None = None,
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    """Select and optionally notify the top repository-native reviewer."""

    if execute and provider_payload is not None:
        raise ValueError(
            "execute mode requires live GitHub PR metadata; metadata JSON is preview-only"
        )

    reference = normalise_github_issue_reference(
        repo="public_repo_fixture",
        issue_ref="pull_request_fixture",
        url=url,
    )
    if reference.get("kind") != "pull_request" or not isinstance(
        reference.get("number"), int
    ):
        raise ValueError("reviewer request requires a numeric GitHub pull request URL")
    repo = str(reference["repo"])
    number = int(reference["number"])
    max_reviewers = min(max(int(max_reviewers), 1), 3)

    external_reads = False
    metadata_error: str | None = None
    metadata = dict(provider_payload or {})
    if not metadata and execute:
        fetched, metadata_error = _fetch_pr_metadata(
            repo=repo,
            number=number,
            runner=runner,
        )
        external_reads = True
        metadata = fetched or {}
    identities = _metadata_identities(metadata, repo=repo, number=number)
    excluded = list(exclude_reviewers)
    if identities["author_handle"]:
        excluded.append(str(identities["author_handle"]))
    excluded.extend(identities["requested_reviewers"])
    excluded.extend(identities["reviewed_by"])
    excluded.extend(identities["comment_notified_reviewers"])

    recommendation = build_issue_fix_reviewer_recommendation_packet(
        repo_path=repo_path,
        repo=repo,
        changed_files=changed_files,
        base_ref=base_ref,
        history_limit=history_limit,
        max_candidates=max_candidates,
        exclude_reviewers=excluded,
        exclude_author_names=exclude_author_names,
        resolved_identities=resolved_identities,
        reviewer_sources_input=reviewer_sources_input,
        execute=True,
        generated_at=generated_at,
    )
    candidates = recommendation.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    existing_coverage = len(
        set(
            identities["requested_reviewers"]
            + identities["reviewed_by"]
            + identities["comment_notified_reviewers"]
        )
    )
    remaining_slots = max(0, max_reviewers - existing_coverage)
    selected = [
        str(candidate.get("reviewer_handle"))
        for candidate in candidates
        if isinstance(candidate, Mapping)
        and candidate.get("requestable") is True
        and candidate.get("reviewer_handle")
        and not _is_automated_reviewer_handle(candidate.get("reviewer_handle"))
    ][:remaining_slots]
    author_exclusion_verified = bool(identities["author_handle"])
    pr_state_verified = identities["state"] in {"OPEN", "CLOSED", "MERGED"}
    if not author_exclusion_verified or not pr_state_verified:
        selected = []

    existing_notified_reviewers = list(
        dict.fromkeys(
            identities["requested_reviewers"]
            + identities["reviewed_by"]
            + identities["comment_notified_reviewers"]
        )
    )
    existing_comment_url = next(
        iter(identities["reviewer_comment_urls"].values()),
        None,
    )
    existing_notification_mode = (
        "comment_fallback"
        if identities["marker_comment_notified_reviewers"]
        else "existing_review_comment"
        if identities["semantic_comment_notified_reviewers"]
        else (
            "formal_request"
            if identities["requested_reviewers"]
            else "existing_review"
            if identities["reviewed_by"]
            else "none"
        )
    )

    packet: dict[str, Any] = {
        "ok": metadata_error is None,
        "schema_version": ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION,
        "mode": "issue-fix-reviewer-request",
        "generated_at": generated_at,
        "repo": repo,
        "pr_ref": reference["issue_ref"],
        "number": number,
        "permalink": reference["permalink"],
        "execute": execute,
        "external_write_authority_asserted": execute,
        "selection_policy": "request_top_requestable_when_authorized",
        "max_reviewers": max_reviewers,
        "author_handle": identities["author_handle"],
        "pr_title": identities["pr_title"],
        "linked_issue_refs": identities["linked_issue_refs"],
        "linked_issue_summaries": identities["linked_issue_summaries"],
        "author_exclusion_verified": author_exclusion_verified,
        "pr_state_verified": pr_state_verified,
        "existing_requested_reviewers": identities["requested_reviewers"],
        "existing_reviewed_by": identities["reviewed_by"],
        "existing_comment_notified_reviewers": identities["comment_notified_reviewers"],
        "existing_marker_comment_notified_reviewers": identities[
            "marker_comment_notified_reviewers"
        ],
        "existing_semantic_comment_notified_reviewers": identities[
            "semantic_comment_notified_reviewers"
        ],
        "selected_reviewers": selected,
        "requested_reviewers": [],
        "notified_reviewers": existing_notified_reviewers,
        "recommendation_status": recommendation.get("recommendation_status"),
        "recommendation_candidates": candidates,
        "reviewer_source_count": recommendation.get("reviewer_source_count"),
        "reviewer_source_refs": recommendation.get("reviewer_source_refs"),
        "external_reads_performed": external_reads,
        "external_writes_performed": False,
        "review_request_performed": False,
        "review_request_verified": False,
        "reviewer_notification_mode": existing_notification_mode,
        "reviewer_notification_verified": bool(execute and existing_notified_reviewers),
        "comment_fallback_performed": False,
        "comment_fallback_verified": bool(
            execute and identities["marker_comment_notified_reviewers"]
        ),
        "existing_comment_notification_verified": bool(
            execute and identities["semantic_comment_notified_reviewers"]
        ),
        "reviewer_comment_url": existing_comment_url,
        "private_repo_state_read": True,
        "local_paths_captured": False,
        "raw_provider_payload_captured": False,
        "raw_git_output_captured": False,
        "commit_emails_captured": False,
    }
    if not execute and provider_payload is None:
        packet["ok"] = False
        packet["blocker"] = "github_pr_metadata_required_for_safe_preview"
        packet["transition"] = _transition(
            decision="blocker",
            action_kind="issue_fix_reviewer_request_metadata_blocker",
            reason=(
                "Provide compact PR metadata for preview, or execute with "
                "external-write authority so LoopX can exclude the live PR author."
            ),
            material_change=False,
        )
    elif metadata_error:
        packet["blocker"] = metadata_error
        packet["transition"] = _transition(
            decision="blocker",
            action_kind="issue_fix_reviewer_request_environment_blocker",
            reason=(
                "GitHub PR metadata is unavailable; do not request a reviewer "
                "without excluding the PR author."
            ),
            material_change=True,
        )
    elif not author_exclusion_verified:
        packet["ok"] = False
        packet["blocker"] = "github_pr_author_unavailable"
        packet["transition"] = _transition(
            decision="blocker",
            action_kind="issue_fix_reviewer_request_author_blocker",
            reason=(
                "PR author identity is unavailable; fail closed before reviewer "
                "selection or external write."
            ),
            material_change=False,
        )
    elif not pr_state_verified:
        packet["ok"] = False
        packet["blocker"] = "github_pr_state_unavailable"
        packet["transition"] = _transition(
            decision="blocker",
            action_kind="issue_fix_reviewer_request_state_blocker",
            reason=(
                "PR state is unavailable; fail closed before reviewer selection "
                "or external write."
            ),
            material_change=False,
        )
    elif identities["state"] != "OPEN":
        packet["transition"] = _transition(
            decision="no_followup",
            action_kind="issue_fix_reviewer_request_terminal_skip",
            reason="PR is not open; no reviewer request should be sent.",
            material_change=False,
        )
    elif not selected:
        already_covered = bool(
            identities["requested_reviewers"]
            or identities["reviewed_by"]
            or identities["comment_notified_reviewers"]
        )
        packet["transition"] = _transition(
            decision="monitor_continuation"
            if already_covered
            else "runnable_successor",
            action_kind=(
                "issue_fix_reviewer_request_already_covered"
                if already_covered
                else "issue_fix_reviewer_identity_resolution"
            ),
            reason=(
                "A reviewer is already requested, has reviewed, or is covered "
                "by an existing explicit review-request comment; keep lifecycle "
                "monitoring."
                if already_covered
                else (
                    "No requestable non-author reviewer identity is available; "
                    "resolve a candidate handle."
                )
            ),
            material_change=False,
        )
    elif not execute:
        packet["transition"] = _transition(
            decision="runnable_successor",
            action_kind="issue_fix_request_top_reviewer",
            reason=(
                "External-write authority may execute the top requestable "
                "reviewer request."
            ),
            material_change=False,
        )
    else:
        request_error, permission_denied = _request_reviewers(
            repo=repo,
            number=number,
            reviewer_handles=selected,
            runner=runner,
        )
        packet["external_writes_performed"] = request_error is None
        if request_error and permission_denied:
            packet["formal_request_error"] = request_error
            comment_url, comment_error, comment_performed = (
                _comment_reviewer_notification(
                    repo=repo,
                    number=number,
                    reviewer_handles=selected,
                    pr_title=identities["pr_title"],
                    linked_issue_summaries=identities["linked_issue_summaries"],
                    runner=runner,
                )
            )
            packet["reviewer_notification_mode"] = "comment_fallback"
            packet["reviewer_comment_url"] = comment_url
            packet["comment_fallback_performed"] = comment_performed
            packet["external_writes_performed"] = comment_performed
            if comment_error:
                packet["ok"] = False
                packet["blocker"] = comment_error
                packet["transition"] = _transition(
                    decision="blocker",
                    action_kind="issue_fix_reviewer_comment_fallback_blocker",
                    reason=(
                        "GitHub denied the formal reviewer request and the "
                        "fallback reviewer comment could not be published."
                    ),
                    material_change=True,
                )
            else:
                verified_payload, verify_error = _fetch_pr_metadata(
                    repo=repo,
                    number=number,
                    runner=runner,
                )
                packet["external_reads_performed"] = True
                verified = _metadata_identities(
                    verified_payload or {},
                    repo=repo,
                    number=number,
                )
                notified = [
                    handle
                    for handle in selected
                    if handle in verified["comment_notified_reviewers"]
                ]
                verified_urls = [
                    verified["reviewer_comment_urls"].get(handle)
                    for handle in selected
                    if verified["reviewer_comment_urls"].get(handle)
                ]
                readback_url = (
                    verified_urls[0]
                    if len(verified_urls) == len(selected)
                    and len(set(verified_urls)) == 1
                    else None
                )
                packet["reviewer_comment_url"] = readback_url or comment_url
                packet["notified_reviewers"] = notified
                packet["comment_fallback_verified"] = bool(
                    not verify_error
                    and readback_url
                    and len(notified) == len(selected)
                    and (not comment_url or readback_url == comment_url)
                )
                packet["reviewer_notification_verified"] = packet[
                    "comment_fallback_verified"
                ]
                if not packet["comment_fallback_verified"]:
                    packet["ok"] = False
                    packet["blocker"] = "github_reviewer_comment_not_verified"
                    packet["transition"] = _transition(
                        decision="blocker",
                        action_kind="issue_fix_reviewer_comment_verification_blocker",
                        reason=(
                            "Fallback comment command returned success but PR "
                            "readback did not confirm the semantic review request "
                            "and URL."
                        ),
                        material_change=True,
                    )
                else:
                    packet["transition"] = _transition(
                        decision="monitor_continuation",
                        action_kind="issue_fix_reviewer_comment_fallback_verified",
                        reason=(
                            "Formal reviewer request lacked permission; a verified "
                            "public comment notified the selected reviewer."
                        ),
                        material_change=True,
                    )
        elif request_error:
            packet["ok"] = False
            packet["blocker"] = request_error
            packet["transition"] = _transition(
                decision="blocker",
                action_kind="issue_fix_reviewer_request_provider_blocker",
                reason=(
                    "GitHub reviewer-request failure was not a confirmed permission "
                    "denial; do not post a fallback comment until the provider or "
                    "network error is classified."
                ),
                material_change=True,
            )
        else:
            verified_payload, verify_error = _fetch_pr_metadata(
                repo=repo,
                number=number,
                runner=runner,
            )
            packet["external_reads_performed"] = True
            verified = _metadata_identities(
                verified_payload or {},
                repo=repo,
                number=number,
            )
            requested = [
                handle
                for handle in selected
                if handle in verified["requested_reviewers"]
            ]
            packet["requested_reviewers"] = requested
            packet["review_request_performed"] = bool(requested)
            packet["review_request_verified"] = len(requested) == len(selected)
            packet["notified_reviewers"] = requested
            packet["reviewer_notification_mode"] = "formal_request"
            packet["reviewer_notification_verified"] = packet["review_request_verified"]
            if verify_error or not packet["review_request_verified"]:
                packet["ok"] = False
                packet["blocker"] = "github_review_request_not_verified"
                packet["transition"] = _transition(
                    decision="blocker",
                    action_kind="issue_fix_reviewer_request_verification_blocker",
                    reason=(
                        "Reviewer request command returned success but the PR "
                        "did not confirm every selected reviewer."
                    ),
                    material_change=True,
                )
            else:
                packet["transition"] = _transition(
                    decision="monitor_continuation",
                    action_kind="issue_fix_reviewer_request_verified",
                    reason=(
                        "Reviewer request is visible on the PR; continue lifecycle "
                        "monitoring."
                    ),
                    material_change=True,
                )

    packet["secondary_notification_configured"] = bool(notification_sinks_input)
    packet["secondary_notification_status"] = "not_configured"
    packet["secondary_notification_verified"] = False
    reviewer_artifact_application: dict[str, Any] | None = None
    reward_memory_error: str | None = None
    if reviewer_artifact_reward_memory and (
        packet.get("selected_reviewers") or packet.get("notified_reviewers")
    ):
        config = reviewer_artifact_reward_memory.get("config")
        config = config if isinstance(config, Mapping) else {}
        try:
            reviewer_artifact_application = (
                run_issue_fix_reviewer_artifact_automatic_reward_memory(
                    {
                        "repo": repo,
                        "pr_ref": f"#{number}",
                        "permalink": str(reference["permalink"]),
                        "source_title": identities["pr_title"],
                        "summary": "",
                    },
                    reviewer_summary=str(
                        reviewer_artifact_reward_memory.get("reviewer_summary") or ""
                    ),
                    reasoning_summary=str(
                        reviewer_artifact_reward_memory.get("reasoning_summary") or ""
                    ),
                    experiment_config=config,
                    revision_ref=f"pr:{number}:{identities['state'].lower()}",
                    observed_at=str(
                        reviewer_artifact_reward_memory.get("observed_at")
                        or generated_at
                    ),
                    freshness_context={
                        "source_truth_current": pr_state_verified,
                        "source_revision": (
                            f"pr:{number}:{identities['state'].lower()}"
                        ),
                    },
                    conflict_state="clear",
                    application_id=f"issue-fix:reviewer-artifact:{repo}:{number}",
                    artifact_ref=f"github:{repo}#pr-{number}",
                    provider=reviewer_artifact_reward_memory.get("provider"),
                )
            )
        except (OSError, RuntimeError, ValueError):
            reward_memory_error = "reward_memory_application_unavailable"
    packet["reviewer_artifact_reward_memory_required"] = reviewer_artifact_required
    packet["reviewer_artifact_reward_memory_status"] = (
        (reviewer_artifact_application or {}).get("notification_gate", {}).get("status")
        if reviewer_artifact_application
        else "unavailable"
        if reviewer_artifact_reward_memory
        else "not_configured"
    )
    if reviewer_artifact_application is not None:
        packet["reviewer_artifact_reward_memory_preview"] = (
            reviewer_artifact_application
        )
    if reward_memory_error:
        packet["reviewer_artifact_reward_memory_blocker"] = reward_memory_error
    if notification_sinks_input:
        notification_targets = list(packet.get("selected_reviewers") or [])
        if packet.get("notified_reviewers"):
            notification_targets = list(packet.get("notified_reviewers") or [])
        if execute:
            completed_reviewers = set(packet.get("existing_reviewed_by") or [])
            notification_targets = [
                handle
                for handle in notification_targets
                if handle not in completed_reviewers
            ]
        primary_notification_targets = list(notification_targets)
        notification_targets, notification_candidate_pool = (
            _secondary_notification_targets(
                primary_handles=primary_notification_targets,
                candidates=candidates,
                sinks_input=notification_sinks_input,
                allow_candidate_fallback=bool(packet.get("selected_reviewers")),
            )
        )
        packet["secondary_notification_primary_targets"] = primary_notification_targets
        packet["secondary_notification_candidate_pool"] = notification_candidate_pool
        packet["secondary_notification_targets"] = notification_targets
        packet["secondary_notification_fallback_used"] = bool(
            notification_targets
            and notification_targets != primary_notification_targets
        )
        if notification_targets:
            reviewer_notification_policy_application: dict[str, Any] | None = None
            if reviewer_notification_reward_memory:
                config = reviewer_notification_reward_memory.get("config")
                config = config if isinstance(config, Mapping) else {}
                try:
                    reviewer_notification_policy_application = (
                        run_issue_fix_reviewer_notification_automatic_reward_memory(
                            repo=repo,
                            pr_number=number,
                            pr_url=str(reference["permalink"]),
                            delivery_policy=(
                                notification_sinks_input.get("delivery_policy")
                                if isinstance(notification_sinks_input, Mapping)
                                else None
                            ),
                            experiment_config=config,
                            revision_ref=f"pr:{number}:{identities['state'].lower()}",
                            observed_at=str(
                                reviewer_notification_reward_memory.get("observed_at")
                                or generated_at
                            ),
                            freshness_context={
                                "source_truth_current": pr_state_verified,
                                "source_revision": (
                                    f"pr:{number}:{identities['state'].lower()}"
                                ),
                            },
                            conflict_state="clear",
                            application_id=(
                                f"issue-fix:reviewer-notification:{repo}:{number}"
                            ),
                            provider=reviewer_notification_reward_memory.get(
                                "provider"
                            ),
                        )
                    )
                except (OSError, RuntimeError, ValueError):
                    reviewer_notification_policy_application = None
            packet["reviewer_notification_reward_memory_status"] = (
                (
                    reviewer_notification_policy_application.get(
                        "before_send_gate", {}
                    )
                    if reviewer_notification_policy_application
                    else {}
                ).get("status", "unavailable")
                if reviewer_notification_reward_memory
                else "not_configured"
            )
            if reviewer_notification_policy_application is not None:
                packet["reviewer_notification_reward_memory_preview"] = (
                    reviewer_notification_policy_application
                )
            secondary = build_issue_fix_reviewer_notification_sinks_result(
                repo=repo,
                pr_number=number,
                pr_url=str(reference["permalink"]),
                pr_title=identities["pr_title"],
                linked_issue_refs=identities["linked_issue_refs"],
                author_handle=identities["author_handle"],
                reviewer_handles=notification_targets,
                sinks_input=notification_sinks_input,
                reviewer_artifact_application=reviewer_artifact_application,
                reviewer_notification_policy_application=(
                    reviewer_notification_policy_application
                ),
                reviewer_artifact_required=reviewer_artifact_required,
                execute=execute,
                delivery_observed_at=notification_delivery_observed_at,
                runner=runner,
                sink_adapters=notification_sink_adapters,
            )
            packet["secondary_notifications"] = secondary
            packet["secondary_notification_status"] = secondary.get("status")
            packet["secondary_notification_blocker"] = secondary.get("blocker")
            packet["secondary_notification_verified"] = bool(
                secondary.get("notification_verified")
            )
            packet["external_writes_performed"] = bool(
                packet["external_writes_performed"]
                or secondary.get("external_writes_performed")
            )
        else:
            packet["secondary_notification_status"] = (
                "skipped_reviewer_already_reviewed"
                if execute and packet.get("existing_reviewed_by")
                else "skipped_reviewer_unavailable"
            )

    validation = validate_issue_fix_reviewer_request_packet(packet)
    packet["ok"] = bool(packet["ok"] and validation["ok"])
    packet["validation"] = validation
    return packet


def validate_issue_fix_reviewer_request_packet(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION:
        errors.append("schema_version must be issue_fix_reviewer_request_v0")
    if packet.get("local_paths_captured") is not False:
        errors.append("local_paths_captured must be false")
    if packet.get("raw_provider_payload_captured") is not False:
        errors.append("raw_provider_payload_captured must be false")
    if packet.get("raw_git_output_captured") is not False:
        errors.append("raw_git_output_captured must be false")
    if packet.get("commit_emails_captured") is not False:
        errors.append("commit_emails_captured must be false")
    performed = packet.get("review_request_performed") is True
    verified = packet.get("review_request_verified") is True
    requested = packet.get("requested_reviewers")
    if not isinstance(requested, list):
        errors.append("requested_reviewers must be a list")
        requested = []
    if performed != bool(requested):
        errors.append(
            "review_request_performed must reflect verified requested_reviewers"
        )
    if performed and packet.get("external_writes_performed") is not True:
        errors.append(
            "verified reviewer requests require external_writes_performed=true"
        )
    if verified and not performed:
        errors.append("review_request_verified requires a performed request")
    selected = packet.get("selected_reviewers")
    if not isinstance(selected, list):
        errors.append("selected_reviewers must be a list")
        selected = []
    author = packet.get("author_handle")
    if selected and packet.get("author_exclusion_verified") is not True:
        errors.append("reviewer selection requires verified PR author exclusion")
    if selected and packet.get("pr_state_verified") is not True:
        errors.append("reviewer selection requires verified open PR state")
    if author and author in selected:
        errors.append("the PR author must not be selected as reviewer")
    if verified and set(requested) != set(selected):
        errors.append("verified reviewer requests must match selected_reviewers")
    fallback_performed = packet.get("comment_fallback_performed") is True
    fallback_verified = packet.get("comment_fallback_verified") is True
    comment_url = packet.get("reviewer_comment_url")
    notified = packet.get("notified_reviewers")
    if not isinstance(notified, list):
        errors.append("notified_reviewers must be a list")
        notified = []
    if fallback_performed and packet.get("external_writes_performed") is not True:
        errors.append("comment fallback requires external_writes_performed=true")
    if fallback_verified and not comment_url:
        errors.append("verified comment fallback requires reviewer_comment_url")
    if fallback_verified and set(notified) != set(selected):
        existing_comment_notified = packet.get("existing_comment_notified_reviewers")
        existing_comment_notified = (
            existing_comment_notified
            if isinstance(existing_comment_notified, list)
            else []
        )
        if set(notified) != set(existing_comment_notified):
            errors.append(
                "verified comment fallback must notify selected or existing reviewers"
            )
    notification_verified = packet.get("reviewer_notification_verified") is True
    existing_comment_verified = (
        packet.get("existing_comment_notification_verified") is True
    )
    existing_semantic_comment_notified = packet.get(
        "existing_semantic_comment_notified_reviewers"
    )
    existing_semantic_comment_notified = (
        existing_semantic_comment_notified
        if isinstance(existing_semantic_comment_notified, list)
        else []
    )
    if existing_comment_verified and not existing_semantic_comment_notified:
        errors.append(
            "existing comment verification requires semantic notified reviewers"
        )
    if existing_comment_verified and not comment_url:
        errors.append("existing comment verification requires reviewer_comment_url")
    existing_notification_verified = bool(
        packet.get("execute") is True
        and (
            packet.get("existing_requested_reviewers")
            or packet.get("existing_reviewed_by")
            or existing_comment_verified
        )
    )
    if notification_verified != bool(
        verified or fallback_verified or existing_notification_verified
    ):
        errors.append(
            "reviewer_notification_verified must reflect formal or comment verification"
        )
    secondary = packet.get("secondary_notifications")
    if secondary is not None:
        if not isinstance(secondary, Mapping):
            errors.append("secondary_notifications must be an object")
        else:
            secondary_validation = secondary.get("validation")
            if not isinstance(secondary_validation, Mapping) or (
                secondary_validation.get("ok") is not True
            ):
                errors.append("secondary notification contract validation must pass")
    return {
        "ok": not errors,
        "schema_version": "issue_fix_reviewer_request_validation_v0",
        "errors": errors,
    }


def render_issue_fix_reviewer_request_markdown(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "# LoopX Issue-Fix Reviewer Request",
            "",
            f"- ok: {payload.get('ok')}",
            f"- repo: {payload.get('repo')}",
            f"- pr_ref: {payload.get('pr_ref')}",
            f"- selected_reviewers: {','.join(payload.get('selected_reviewers') or [])}",
            f"- requested_reviewers: {','.join(payload.get('requested_reviewers') or [])}",
            f"- review_request_performed: {payload.get('review_request_performed')}",
            f"- review_request_verified: {payload.get('review_request_verified')}",
            f"- reviewer_notification_mode: {payload.get('reviewer_notification_mode')}",
            "- reviewer_notification_verified: "
            f"{payload.get('reviewer_notification_verified')}",
            f"- reviewer_comment_url: {payload.get('reviewer_comment_url')}",
            "- secondary_notification_status: "
            f"{payload.get('secondary_notification_status')}",
            "- secondary_notification_verified: "
            f"{payload.get('secondary_notification_verified')}",
            "- secondary_notification_blocker: "
            f"{payload.get('secondary_notification_blocker')}",
            f"- transition: {(payload.get('transition') or {}).get('decision')}",
            f"- next: {(payload.get('transition') or {}).get('reason')}",
        ]
    )
