from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from .content_ops_surface import _normalise_exploration_label


GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION = "github_issue_metadata_preview_v0"

GITHUB_BODY_OR_COMMENT_KEYS = {
    "body",
    "body_text",
    "comments",
    "comment_bodies",
    "timeline",
    "events",
    "raw",
    "response_payload",
}

ALLOWED_ISSUE_FIX_INTAKE_STATES = {"open", "closed", "unknown"}


def normalise_github_issue_reference(
    *,
    repo: str | None = None,
    issue_ref: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    if url:
        parsed = urlsplit(str(url).strip())
        if parsed.scheme != "https":
            raise ValueError("GitHub issue URL must use https")
        if parsed.username or parsed.password:
            raise ValueError("GitHub issue URL must not include credentials")
        host = (parsed.hostname or "").lower().rstrip(".")
        if host != "github.com":
            raise ValueError("GitHub issue URL must use github.com")
        if parsed.query or parsed.fragment:
            raise ValueError("GitHub issue URL must not include query or fragment data")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 4 or parts[2] not in {"issues", "pull"}:
            raise ValueError("GitHub issue URL must look like /owner/repo/issues/123")
        if not parts[3].isdigit():
            raise ValueError("GitHub issue or PR number must be numeric")
        repo_label = _normalise_exploration_label(f"{parts[0]}/{parts[1]}", "repo")
        issue_label = f"{parts[2]}_{parts[3]}"
        permalink = urlunsplit(("https", "github.com", "/" + "/".join(parts), "", ""))
        return {
            "repo": repo_label,
            "issue_ref": issue_label,
            "kind": "pull_request" if parts[2] == "pull" else "issue",
            "number": int(parts[3]),
            "permalink": permalink,
        }

    repo_label = _normalise_exploration_label(repo, "repo")
    issue_label = _normalise_exploration_label(issue_ref, "issue_ref")
    number = None
    digits = "".join(ch for ch in issue_label if ch.isdigit())
    if digits:
        number = int(digits)
    return {
        "repo": repo_label,
        "issue_ref": issue_label,
        "kind": "issue",
        "number": number,
        "permalink": None,
    }


def _provider_payload_labels(payload: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    raw_labels = payload.get("labels")
    if not isinstance(raw_labels, Sequence) or isinstance(raw_labels, (str, bytes)):
        return labels
    for item in raw_labels:
        if isinstance(item, Mapping):
            label = _normalise_exploration_label(item.get("name"), "label")
        else:
            label = _normalise_exploration_label(item, "label")
        if label and label not in labels:
            labels.append(label)
    return labels[:12]


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def github_metadata_from_provider_payload(
    *,
    reference: Mapping[str, Any],
    provider_payload: Mapping[str, Any] | None,
    provider_mode: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    payload = provider_payload or {}
    gated_keys = sorted(
        str(key) for key in payload if str(key).lower() in GITHUB_BODY_OR_COMMENT_KEYS
    )
    labels = _provider_payload_labels(payload) or ["needs-triage"]
    state = str(payload.get("state") or "unknown").strip().lower()
    if state not in ALLOWED_ISSUE_FIX_INTAKE_STATES:
        state = "unknown"
    number = _safe_int(payload.get("number"))
    if number is None:
        number = reference.get("number") if isinstance(reference.get("number"), int) else None
    comments_count = _safe_int(payload.get("comments_count"))
    if comments_count is None:
        comments_count = _safe_int(payload.get("comments"))
    mode = provider_mode or ("mocked_metadata" if provider_payload else "reference_only")
    metadata = {
        "schema_version": GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION,
        "provider": "github",
        "provider_mode": mode,
        "repo": reference["repo"],
        "issue_ref": reference["issue_ref"],
        "kind": payload.get("kind") or reference["kind"],
        "number": number,
        "state": state,
        "title_summary": (
            _normalise_exploration_label(payload.get("title"), "title")
            if payload.get("title")
            else "public GitHub issue metadata preview"
        ),
        "labels": labels,
        "updated_at": _normalise_exploration_label(payload.get("updated_at"), "updated_at")
        if payload.get("updated_at")
        else None,
        "author_association": _normalise_exploration_label(
            payload.get("author_association"),
            "author_association",
        )
        if payload.get("author_association")
        else "unknown",
        "comments_count": comments_count,
        "permalink": reference.get("permalink"),
        "body_captured": False,
        "comment_bodies_captured": False,
        "response_payload_captured": False,
        "local_path_captured": False,
        "private_repo_state_read": False,
        "gated_provider_fields_present": gated_keys,
    }
    return metadata, gated_keys


def fetch_github_issue_metadata_payload(
    reference: Mapping[str, Any],
    *,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    repo = str(reference.get("repo") or "")
    number = reference.get("number")
    if "/" not in repo or not isinstance(number, int):
        raise ValueError("--fetch-metadata requires a numeric GitHub issue or PR URL")
    owner, repo_name = repo.split("/", 1)
    endpoint = f"repos/{quote(owner, safe='')}/{quote(repo_name, safe='')}/issues/{number}"
    jq_filter = (
        "{"
        "number: .number, "
        "state: .state, "
        "title: .title, "
        "labels: [.labels[]?.name], "
        "updated_at: .updated_at, "
        "author_association: .author_association, "
        "comments_count: .comments, "
        "kind: (if .pull_request then \"pull_request\" else \"issue\" end)"
        "}"
    )
    result = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            endpoint,
            "--jq",
            jq_filter,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "GitHub metadata fetch failed; install/authenticate gh or use --metadata-json"
        )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("GitHub metadata fetch must return a JSON object")
    return payload
