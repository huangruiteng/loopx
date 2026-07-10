from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .metadata_preview import normalise_github_issue_reference
from .reviewer_recommendation import build_issue_fix_reviewer_recommendation_packet


ISSUE_FIX_REVIEWER_REQUEST_SCHEMA_VERSION = "issue_fix_reviewer_request_v0"
REVIEWER_BOT_HANDLE_PATTERN = re.compile(
    r"(?:^|[-_.])bot(?:$|[-_.])|\[bot\]$",
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


def _metadata_identities(
    payload: Mapping[str, Any],
    *,
    repo: str,
) -> dict[str, Any]:
    author = payload.get("author")
    author = author if isinstance(author, Mapping) else {}
    author_handle = _normalise_login(author.get("login"))

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
    return {
        "author_handle": author_handle,
        "requested_reviewers": requested,
        "reviewed_by": reviewed,
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
                "author,isDraft,reviewRequests,reviews,state,url",
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
) -> str | None:
    args = ["gh", "pr", "edit", str(number), "--repo", repo]
    for handle in reviewer_handles:
        args.extend(["--add-reviewer", handle.lstrip("@")])
    try:
        result = runner(args)
    except (OSError, subprocess.SubprocessError):
        return "github_review_request_failed"
    return (
        None
        if result.get("returncode") == 0
        else "github_review_request_failed"
    )


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
    provider_payload: Mapping[str, Any] | None = None,
    execute: bool = False,
    generated_at: str | None = "2026-07-10T00:00:00Z",
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    """Select and optionally request the top repository-native reviewer."""

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
    identities = _metadata_identities(metadata, repo=repo)
    excluded = list(exclude_reviewers)
    if identities["author_handle"]:
        excluded.append(str(identities["author_handle"]))
    excluded.extend(identities["requested_reviewers"])
    excluded.extend(identities["reviewed_by"])

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
        execute=True,
        generated_at=generated_at,
    )
    candidates = recommendation.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    existing_coverage = len(
        set(identities["requested_reviewers"] + identities["reviewed_by"])
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
        "author_exclusion_verified": author_exclusion_verified,
        "pr_state_verified": pr_state_verified,
        "existing_requested_reviewers": identities["requested_reviewers"],
        "existing_reviewed_by": identities["reviewed_by"],
        "selected_reviewers": selected,
        "requested_reviewers": [],
        "recommendation_status": recommendation.get("recommendation_status"),
        "recommendation_candidates": candidates,
        "external_reads_performed": external_reads,
        "external_writes_performed": False,
        "review_request_performed": False,
        "review_request_verified": False,
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
            identities["requested_reviewers"] or identities["reviewed_by"]
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
                "A reviewer is already requested or has reviewed; keep lifecycle monitoring."
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
        request_error = _request_reviewers(
            repo=repo,
            number=number,
            reviewer_handles=selected,
            runner=runner,
        )
        packet["external_writes_performed"] = request_error is None
        if request_error:
            packet["ok"] = False
            packet["blocker"] = request_error
            packet["transition"] = _transition(
                decision="blocker",
                action_kind="issue_fix_reviewer_request_permission_or_network_blocker",
                reason=(
                    "GitHub rejected the reviewer request; preserve the selected "
                    "candidate and retry after permission or network repair."
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
            verified = _metadata_identities(verified_payload or {}, repo=repo)
            requested = [
                handle
                for handle in selected
                if handle in verified["requested_reviewers"]
            ]
            packet["requested_reviewers"] = requested
            packet["review_request_performed"] = bool(requested)
            packet["review_request_verified"] = len(requested) == len(selected)
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
            f"- transition: {(payload.get('transition') or {}).get('decision')}",
            f"- next: {(payload.get('transition') or {}).get('reason')}",
        ]
    )
