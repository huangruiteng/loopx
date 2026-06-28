from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMAND = "/loopx-pr-review"
SCHEMA_VERSION = "loopx_pr_review_command_response_v0"

BOUNDARY = {
    "raw_logs_recorded": False,
    "raw_transcripts_recorded": False,
    "raw_connector_payloads_recorded": False,
    "credential_values_recorded": False,
    "absolute_paths_recorded": False,
    "private_source_bodies_recorded": False,
}

SOURCE_SURFACES = [
    "GitHub pull request metadata",
    "GitHub pull request body summary",
    "GitHub pull request changed-file list",
    "GitHub pull request commit headlines",
    "GitHub pull request status check rollup",
]

LOCAL_PATH_PATTERNS = (
    re.compile(r"/(?:Users|home|private|tmp|var)/[^\s`|,)]+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\s`|,)]+"),
)

RUNTIME_OR_CLI_PREFIXES = (
    "src/",
    "lib/",
    "pkg/",
    "packages/",
    "cmd/",
    "internal/",
    "server/",
    "backend/",
    "app/",
    "apps/",
    "loopx/",
    "scripts/",
    "bin/",
    "tools/",
)

UI_PREFIXES = (
    "apps/dashboard/",
    "apps/web/",
    "apps/frontend/",
    "apps/site/",
    "web/",
    "frontend/",
    "ui/",
    "components/",
    "pages/",
    "views/",
    "public/",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_text(value: object, *, limit: int = 320) -> str:
    text = str(value or "").strip()
    for pattern in LOCAL_PATH_PATTERNS:
        text = pattern.sub("<local-path-redacted>", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "..."
    return text


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _run_gh_json(args: list[str], *, cwd: Path | None = None) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(proc.stdout or "null")


def resolve_current_github_repository(*, cwd: Path | None = None) -> str | None:
    try:
        payload = _run_gh_json(["repo", "view", "--json", "nameWithOwner"], cwd=cwd)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return str(payload.get("nameWithOwner") or "") or None


def _parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _github_search_date(value: object) -> str | None:
    parsed = _parse_timestamp(value)
    if parsed:
        return parsed.astimezone(timezone.utc).date().isoformat()
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def _pr_window_timestamp(pr: dict[str, Any]) -> datetime | None:
    return (
        _parse_timestamp(pr.get("mergedAt") or pr.get("merged_at"))
        or _parse_timestamp(pr.get("closedAt") or pr.get("closed_at"))
        or _parse_timestamp(pr.get("updatedAt") or pr.get("updated_at"))
    )


def _include_pr_in_window(pr: dict[str, Any], *, since: object | None) -> bool:
    since_dt = _parse_timestamp(since)
    if since_dt is None:
        return True
    activity_dt = _pr_window_timestamp(pr)
    return bool(activity_dt and activity_dt >= since_dt)


def normalize_pr_state_filter(value: object) -> str:
    state = str(value or "all").strip().lower()
    return state if state in {"open", "merged", "all"} else "all"


def fetch_github_pull_requests(
    *,
    repo: str | None,
    limit: int,
    cwd: Path | None = None,
    state_filter: str = "all",
    since: str | None = None,
) -> list[dict[str, Any]]:
    repo_args = ["--repo", repo] if repo else []
    normalized_state = normalize_pr_state_filter(state_filter)
    search_args: list[str] = []
    search_date = _github_search_date(since)
    if search_date:
        search_args = ["--search", f"updated:>={search_date}"]
    list_fields = [
        "number",
        "title",
        "url",
        "state",
        "isDraft",
        "reviewDecision",
        "mergeStateStatus",
        "headRefName",
        "baseRefName",
        "author",
        "updatedAt",
        "closedAt",
        "mergedAt",
    ]
    fetch_limit = max(1, limit)
    if since:
        fetch_limit = max(fetch_limit, min(100, fetch_limit * 3))
    rows = _run_gh_json(
        [
            "pr",
            "list",
            "--state",
            normalized_state,
            "--limit",
            str(fetch_limit),
            "--json",
            ",".join(list_fields),
            *search_args,
            *repo_args,
        ],
        cwd=cwd,
    )
    if not isinstance(rows, list):
        return []

    view_fields = [
        "number",
        "title",
        "url",
        "state",
        "isDraft",
        "reviewDecision",
        "mergeStateStatus",
        "mergeable",
        "headRefName",
        "baseRefName",
        "author",
        "updatedAt",
        "closedAt",
        "mergedAt",
        "mergeCommit",
        "body",
        "files",
        "commits",
        "changedFiles",
        "additions",
        "deletions",
        "statusCheckRollup",
    ]
    detailed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        number = row.get("number")
        if not number:
            continue
        try:
            view = _run_gh_json(
                [
                    "pr",
                    "view",
                    str(number),
                    "--json",
                    ",".join(view_fields),
                    *repo_args,
                ],
                cwd=cwd,
            )
            if isinstance(view, dict):
                merged = {**row, **view}
                if _include_pr_in_window(merged, since=since):
                    detailed.append(merged)
                continue
        except Exception:
            pass
        if _include_pr_in_window(row, since=since):
            detailed.append(row)
    return detailed


def load_pr_fixture(path: Path) -> tuple[str | None, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return None, [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return None, []
    items = payload.get("pull_requests") or payload.get("prs") or []
    return (
        str(payload.get("repository") or "") or None,
        [item for item in _as_list(items) if isinstance(item, dict)],
    )


def _clean_body_lines(body: object) -> list[str]:
    lines: list[str] = []
    for raw in str(body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("<!--") or line.startswith("-->"):
            continue
        if line.startswith("#"):
            continue
        if line.startswith("- [") or line.startswith("* ["):
            continue
        if line.lower() in {"summary", "motivation", "changes", "testing"}:
            continue
        lines.append(line.strip("-* "))
    return lines


def _motivation(pr: dict[str, Any]) -> str:
    lines = _clean_body_lines(pr.get("body"))
    if lines:
        return _redact_text(" ".join(lines[:2]), limit=380)
    title = pr.get("title") or f"PR #{pr.get('number')}"
    return _redact_text(f"Review the intent described by the title: {title}", limit=220)


def _commit_headlines(pr: dict[str, Any], *, limit: int = 5) -> list[str]:
    commits: list[str] = []
    for item in _as_list(pr.get("commits")):
        if not isinstance(item, dict):
            continue
        headline = item.get("messageHeadline") or _as_dict(item.get("commit")).get("messageHeadline")
        if headline:
            commits.append(_redact_text(headline, limit=140))
        if len(commits) >= limit:
            break
    return commits


def _file_area(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    lowered = path.lower()
    if path in {
        "README.md",
        "README.zh-CN.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "LICENSE",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
    }:
        return "public_entry_or_policy"
    if path.startswith(".github/workflows/"):
        return "ci_or_release"
    if path.startswith("docs/"):
        return "public_docs"
    if path.startswith(("examples/", "fixtures/", "test/", "tests/", "spec/", "smoke/")):
        return "test_or_example"
    if path.startswith(UI_PREFIXES):
        return "app_or_ui_surface"
    if path.startswith(RUNTIME_OR_CLI_PREFIXES):
        return "product_runtime"
    if path.endswith((".toml", ".yaml", ".yml", ".json", ".ini")) or name in {
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "Makefile",
    }:
        return "build_or_config"
    if lowered.endswith((".md", ".mdx", ".rst")):
        return "public_docs"
    return "other"


def _files(pr: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for item in _as_list(pr.get("files")):
        if isinstance(item, str):
            path = item
            additions = None
            deletions = None
        elif isinstance(item, dict):
            path = str(item.get("path") or item.get("filename") or "")
            additions = item.get("additions")
            deletions = item.get("deletions")
        else:
            continue
        if not path:
            continue
        files.append(
            {
                "path": _redact_text(path, limit=180),
                "area": _file_area(path),
                "additions": additions,
                "deletions": deletions,
            }
        )
    return files


def _area_counts(files: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in files:
        area = str(item.get("area") or "other")
        counts[area] = counts.get(area, 0) + 1
    return counts


def _check_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("context") or item.get("workflowName") or "check")


def _check_state(item: dict[str, Any]) -> str:
    conclusion = str(item.get("conclusion") or "").upper()
    status = str(item.get("status") or "").upper()
    if conclusion in {"SUCCESS", "PASSED", "NEUTRAL", "SKIPPED"}:
        return "success"
    if conclusion in {"FAILURE", "FAILED", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "failure"
    if status in {"COMPLETED"} and conclusion:
        return conclusion.lower()
    if status in {"QUEUED", "IN_PROGRESS", "PENDING", "WAITING"}:
        return "pending"
    return "unknown"


def _checks(pr: dict[str, Any]) -> dict[str, Any]:
    items = [item for item in _as_list(pr.get("statusCheckRollup")) if isinstance(item, dict)]
    counts: dict[str, int] = {}
    failures: list[str] = []
    pending: list[str] = []
    for item in items:
        state = _check_state(item)
        counts[state] = counts.get(state, 0) + 1
        if state == "failure":
            failures.append(_redact_text(_check_name(item), limit=120))
        elif state == "pending":
            pending.append(_redact_text(_check_name(item), limit=120))
    if not items:
        return {
            "total": 0,
            "counts": {},
            "summary": "No status-check rollup was available from the source.",
            "failures": [],
            "pending": [],
        }
    if failures:
        summary = f"{len(failures)} failing check(s)."
    elif pending:
        summary = f"{len(pending)} pending check(s)."
    else:
        summary = f"{counts.get('success', 0)} successful check(s)."
    return {
        "total": len(items),
        "counts": counts,
        "summary": summary,
        "failures": failures[:5],
        "pending": pending[:5],
    }


def _risk_notes(pr: dict[str, Any], files: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    state = str(pr.get("state") or "").upper()
    if state == "MERGED" or pr.get("mergedAt") or pr.get("merged_at"):
        notes.append("Already merged: review for post-merge quality, regression risk, and follow-up work.")
    elif state in {"CLOSED"}:
        notes.append("Closed without a merge signal; review only if it still informs a replacement path.")
    if pr.get("isDraft"):
        notes.append("Draft PR: review may be advisory until it is marked ready.")
    if state != "MERGED" and str(pr.get("mergeStateStatus") or "").upper() not in {"", "CLEAN", "HAS_HOOKS", "UNKNOWN"}:
        notes.append(f"Merge state is {pr.get('mergeStateStatus')}; check conflict or branch-protection details.")
    if any(str(item.get("path") or "").startswith(RUNTIME_OR_CLI_PREFIXES) for item in files):
        notes.append("Touches runtime, app, CLI, or automation paths; review behavior and compatibility before merge.")
    changed = int(pr.get("changedFiles") or len(files) or 0)
    additions = int(pr.get("additions") or 0)
    deletions = int(pr.get("deletions") or 0)
    if changed >= 12 or additions + deletions >= 800:
        notes.append("Large review surface; split the review by area before approving.")
    checks = _checks(pr)
    if checks.get("failures"):
        notes.append("Failing status checks block a clean merge decision.")
    return notes


def _review_depth(files: list[dict[str, Any]]) -> str:
    areas = {str(item.get("area") or "") for item in files}
    if "product_runtime" in areas:
        return "runtime_behavior_review"
    if "app_or_ui_surface" in areas or "public_entry_or_policy" in areas:
        return "presentation_or_policy_review"
    if areas <= {"public_docs", "test_or_example"}:
        return "docs_and_smoke_review"
    return "standard_review"


def _parse_updated_epoch(value: object) -> float:
    parsed = _parse_timestamp(value)
    return parsed.timestamp() if parsed else 0.0


def _review_priority(pr: dict[str, Any], files: list[dict[str, Any]]) -> tuple[int, float]:
    is_draft = bool(pr.get("isDraft") or pr.get("is_draft"))
    review_decision = str(pr.get("reviewDecision") or pr.get("review_decision") or "").upper()
    state = str(pr.get("state") or "").upper()
    activity_at = (
        pr.get("mergedAt")
        or pr.get("merged_at")
        or pr.get("closedAt")
        or pr.get("closed_at")
        or pr.get("updatedAt")
        or pr.get("updated_at")
    )
    if is_draft:
        bucket = 4
    elif state == "MERGED":
        bucket = 3
    elif state == "CLOSED":
        bucket = 5
    elif review_decision in {"", "REVIEW_REQUIRED", "CHANGES_REQUESTED", "UNKNOWN"}:
        bucket = 0
    elif _review_depth(files) == "runtime_behavior_review":
        bucket = 1
    else:
        bucket = 2
    return (bucket, -_parse_updated_epoch(activity_at))


def _normalize_pr(pr: dict[str, Any]) -> dict[str, Any]:
    files = _files(pr)
    checks = _checks(pr)
    number = pr.get("number")
    url = pr.get("url") or (f"https://github.com/pull/{number}" if number else "")
    raw_state = str(pr.get("state") or "").upper()
    if not raw_state:
        raw_state = "MERGED" if pr.get("mergedAt") or pr.get("merged_at") else "OPEN"
    merge_commit = pr.get("mergeCommit") or pr.get("merge_commit")
    merge_commit_oid = _as_dict(merge_commit).get("oid") if isinstance(merge_commit, dict) else None
    item: dict[str, Any] = {
        "number": number,
        "title": _redact_text(pr.get("title"), limit=180),
        "url": _redact_text(url, limit=220),
        "state": raw_state,
        "author": _redact_text(_as_dict(pr.get("author")).get("login") or pr.get("author"), limit=80),
        "updated_at": pr.get("updatedAt"),
        "closed_at": pr.get("closedAt"),
        "merged_at": pr.get("mergedAt"),
        "merge_commit": _redact_text(merge_commit_oid, limit=80) if merge_commit_oid else None,
        "base_ref": _redact_text(pr.get("baseRefName"), limit=80),
        "head_ref": _redact_text(pr.get("headRefName"), limit=120),
        "is_draft": bool(pr.get("isDraft")),
        "review_decision": str(pr.get("reviewDecision") or "UNKNOWN"),
        "merge_state": str(pr.get("mergeStateStatus") or pr.get("mergeable") or "UNKNOWN"),
        "motivation": _motivation(pr),
        "scale": {
            "changed_files": int(pr.get("changedFiles") or len(files) or 0),
            "additions": int(pr.get("additions") or 0),
            "deletions": int(pr.get("deletions") or 0),
        },
        "areas": _area_counts(files),
        "key_files": files[:10],
        "commit_headlines": _commit_headlines(pr),
        "checks": checks,
        "review_depth": _review_depth(files),
        "risk_notes": _risk_notes(pr, files),
        "review_prompts": [
            "What user or maintainer value does this PR unlock now?",
            "Do the touched files match that stated scope?",
            "Are validation evidence and risk boundaries strong enough for merge?",
        ],
        "evidence_commands": [
            f"gh pr view {number} --json title,body,files,commits,statusCheckRollup",
            f"gh pr diff {number} --stat",
        ]
        if number
        else [],
    }
    return item


def build_pr_review_packet(
    *,
    pull_requests: list[dict[str, Any]],
    repository: str | None,
    limit: int,
    source: str,
    state_filter: str = "all",
    since: str | None = None,
) -> dict[str, Any]:
    normalized_state_filter = normalize_pr_state_filter(state_filter)
    normalized_all = [_normalize_pr(item) for item in pull_requests]
    normalized_all = [
        item
        for item in normalized_all
        if (normalized_state_filter == "all" or str(item.get("state") or "").lower() == normalized_state_filter)
        and _include_pr_in_window(item, since=since)
    ]
    normalized_all.sort(key=lambda item: _review_priority(item, item.get("key_files") or []))
    normalized = normalized_all[: max(1, limit)]
    review_sequence = [
        {
            "rank": index,
            "number": item.get("number"),
            "title": item.get("title"),
            "url": item.get("url"),
            "state": item.get("state"),
            "review_depth": item.get("review_depth"),
            "why_now": _review_why_now(item),
        }
        for index, item in enumerate(normalized, start=1)
    ]
    open_review_required = [
        item
        for item in normalized
        if str(item.get("state") or "").upper() == "OPEN"
        and not item.get("is_draft")
        and str(item.get("review_decision") or "").upper() in {"", "REVIEW_REQUIRED", "CHANGES_REQUESTED", "UNKNOWN"}
    ]
    merged_items = [item for item in normalized if str(item.get("state") or "").upper() == "MERGED"]
    closed_items = [item for item in normalized if str(item.get("state") or "").upper() == "CLOSED"]
    first = review_sequence[0] if review_sequence else None
    review_attention_count = len(open_review_required) + len(merged_items)
    open_items = [item for item in normalized if str(item.get("state") or "").upper() == "OPEN"]
    headline = (
        (
            f"{len(normalized)} PR(s) in review window: "
            f"{len(open_items)} open, "
            f"{len(merged_items)} merged; {review_attention_count} need review attention."
        )
        if normalized
        else "No pull requests found for the requested review window."
    )
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "request": {
            "schema_version": "loopx_pr_review_command_request_v0",
            "command": COMMAND,
            "cli_command": "loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]",
            "repository": repository,
            "limit": max(1, limit),
            "state_filter": normalized_state_filter,
            "since": since,
            "window": {
                "since": since,
                "state_filter": normalized_state_filter,
            },
            "source": source,
            "include": ["motivation", "change_scope", "checks", "risk_notes", "review_sequence"],
            "privacy_mode": "public_safe_github_metadata",
            "dry_run": True,
        },
        "generated_at": _now_iso(),
        "summary": {
            "headline": headline,
            "total_pr_count": len(normalized),
            "open_pr_count": len(open_items),
            "merged_pr_count": len(merged_items),
            "closed_pr_count": len(closed_items),
            "review_attention_count": review_attention_count,
            "open_review_attention_count": len(open_review_required),
            "post_merge_review_count": len(merged_items),
            "draft_count": sum(1 for item in normalized if item.get("is_draft")),
            "source_surfaces": SOURCE_SURFACES,
            "recommended_first_pr": first,
        },
        "review_sequence": review_sequence,
        "pull_requests": normalized,
        "actions": [
            {
                "action_id": "act_review_next_pr",
                "kind": "review",
                "requires_user_approval": False,
                "requires_primary_agent": False,
                "preview": "Start with the first PR in review_sequence, read its motivation, inspect key files, then decide approve/request changes/defer.",
            },
            {
                "action_id": "act_merge_after_review",
                "kind": "merge_or_publish",
                "requires_user_approval": False,
                "requires_primary_agent": True,
                "preview": "Merge only after repository policy, validation, and public/private boundary checks pass.",
            },
        ],
        "omissions": [
            "Raw logs, private connector payloads, credentials, local paths, and private source bodies were intentionally omitted.",
            "The command summarizes public PR metadata and does not post review comments, approve, merge, or spend quota.",
        ],
        "boundary": BOUNDARY,
    }


def _review_why_now(item: dict[str, Any]) -> str:
    state = str(item.get("state") or "").upper()
    if state == "MERGED":
        return "Merged in the review window; audit outcome, validation, and follow-up quality."
    if state == "CLOSED":
        return "Closed without a merge signal; check whether a replacement or cleanup is needed."
    if item.get("is_draft"):
        return "Draft PR; skim for early direction but do not treat as merge-ready."
    decision = str(item.get("review_decision") or "").upper()
    if decision in {"REVIEW_REQUIRED", "UNKNOWN", ""}:
        return "Open and awaiting reviewer decision."
    if decision == "CHANGES_REQUESTED":
        return "Changes were requested; verify whether the latest diff addresses them."
    if decision == "APPROVED":
        return "Approved but still open; check merge state and final validation."
    return "Open PR; confirm current merge readiness."


def render_pr_review_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "# Project PR Review Queue\n\n- ok: `False`\n- error: " + _redact_text(payload.get("error"))

    summary = _as_dict(payload.get("summary"))
    request = _as_dict(payload.get("request"))
    lines = [
        "# Project PR Review Queue",
        "",
        f"- command: `{request.get('command')}`",
        f"- repository: `{request.get('repository') or 'current gh repository'}`",
        f"- state_filter: `{request.get('state_filter') or 'all'}`",
        f"- since: `{request.get('since') or 'not set'}`",
        f"- headline: {summary.get('headline')}",
        f"- counts: total=`{summary.get('total_pr_count')}`, open=`{summary.get('open_pr_count')}`, merged=`{summary.get('merged_pr_count')}`, review_attention=`{summary.get('review_attention_count')}`, draft=`{summary.get('draft_count')}`",
        "",
        "## Review Sequence",
    ]
    sequence = [item for item in _as_list(payload.get("review_sequence")) if isinstance(item, dict)]
    if not sequence:
        lines.append("- none")
    for item in sequence:
        lines.append(
            f"{item.get('rank')}. [#{item.get('number')} {item.get('title')}]({item.get('url')}) "
            f"[{item.get('state')}] - "
            f"{item.get('review_depth')}: {item.get('why_now')}"
        )

    for pr in [item for item in _as_list(payload.get("pull_requests")) if isinstance(item, dict)]:
        lines.extend(
            [
                "",
                f"## PR #{pr.get('number')}: {pr.get('title')}",
                "",
                f"- url: {pr.get('url')}",
                f"- state: `{pr.get('state')}`",
                f"- merged_at: `{pr.get('merged_at') or 'n/a'}`",
                f"- branch: `{pr.get('head_ref')}` -> `{pr.get('base_ref')}`",
                f"- status: review=`{pr.get('review_decision')}`, merge=`{pr.get('merge_state')}`, draft=`{pr.get('is_draft')}`",
                f"- motivation: {pr.get('motivation')}",
                f"- scale: files=`{_as_dict(pr.get('scale')).get('changed_files')}`, +`{_as_dict(pr.get('scale')).get('additions')}`, -`{_as_dict(pr.get('scale')).get('deletions')}`",
                f"- areas: `{json.dumps(pr.get('areas') or {}, ensure_ascii=False)}`",
                f"- checks: {_as_dict(pr.get('checks')).get('summary')}",
            ]
        )
        commits = [item for item in _as_list(pr.get("commit_headlines")) if item]
        if commits:
            lines.append("- commits: " + "; ".join(f"`{item}`" for item in commits))
        key_files = [item for item in _as_list(pr.get("key_files")) if isinstance(item, dict)]
        if key_files:
            lines.append("- key files:")
            for item in key_files[:8]:
                lines.append(f"  - `{item.get('path')}` ({item.get('area')})")
        risks = [item for item in _as_list(pr.get("risk_notes")) if item]
        lines.append("- risk notes: " + ("; ".join(str(item) for item in risks) if risks else "none"))
        prompts = [item for item in _as_list(pr.get("review_prompts")) if item]
        if prompts:
            lines.append("- review prompts: " + " / ".join(str(item) for item in prompts))

    lines.extend(["", "## Boundary", "- Public PR metadata only; raw/private material is omitted."])
    return "\n".join(lines)
