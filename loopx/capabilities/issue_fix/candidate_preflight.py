from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .metadata_preview import normalise_github_issue_reference


ISSUE_FIX_CANDIDATE_PREFLIGHT_INPUT_SCHEMA_VERSION = (
    "issue_fix_candidate_preflight_input_v0"
)
ISSUE_FIX_CANDIDATE_PREFLIGHT_SCHEMA_VERSION = "issue_fix_candidate_preflight_v0"

_TERMINAL_DOMAIN_STATES = {"closed", "done", "resolved", "superseded", "terminal"}
_IMPLEMENTATION_RELATIONS = {"implementation", "implements", "fix_candidate"}


def _safe_ref(value: object, *, field: str) -> str:
    compact = public_safe_compact_text(str(value or ""), limit=220)
    if not compact:
        raise ValueError(f"{field} must be a compact public-safe value")
    return compact


def _normalise_issue_ref(repo: str, value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return str(
            normalise_github_issue_reference(
                repo=repo,
                issue_ref=text,
                url=None,
            )["issue_ref"]
        )
    except ValueError:
        return None


def _matching_pr_rows(
    rows: object,
    *,
    repo: str,
    issue_ref: str,
    semantic: bool,
) -> list[dict[str, Any]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    matches: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        row_repo = str(raw.get("repo") or repo).strip()
        if row_repo.casefold() != repo.casefold():
            continue
        refs = raw.get("related_issue_refs") if semantic else raw.get(
            "closing_issue_refs"
        )
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
            continue
        normalised_refs = {
            ref
            for ref in (_normalise_issue_ref(repo, value) for value in refs)
            if ref
        }
        if issue_ref not in normalised_refs:
            continue
        if semantic:
            relation = str(raw.get("relation") or "").strip().casefold()
            if relation not in _IMPLEMENTATION_RELATIONS:
                continue
            if raw.get("current_revision_verified") is not True:
                continue
        matches.append(
            {
                "pr_ref": _safe_ref(raw.get("pr_ref"), field="pr_ref"),
                "state": str(raw.get("state") or "UNKNOWN").strip().upper(),
                "url": public_safe_compact_text(str(raw.get("url") or ""), limit=220),
                "evidence_kind": (
                    "semantic_implementation" if semantic else "numeric_closing_reference"
                ),
                "current_revision_verified": (
                    raw.get("current_revision_verified") is True if semantic else None
                ),
            }
        )
    return matches


def _domain_projection(
    raw: object,
    *,
    repo: str,
    issue_ref: str,
) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    row_repo = str(raw.get("repo") or repo).strip()
    row_issue = _normalise_issue_ref(repo, raw.get("issue_ref"))
    if row_repo.casefold() != repo.casefold() or row_issue != issue_ref:
        return None
    decision = raw.get("decision")
    route = (
        str(decision.get("route") or "").strip()
        if isinstance(decision, Mapping)
        else str(raw.get("route") or "").strip()
    )
    state = str(raw.get("status") or raw.get("state") or "").strip().casefold()
    return {
        "route": route,
        "terminal": raw.get("terminal") is True or state in _TERMINAL_DOMAIN_STATES,
        "state": state or None,
    }


def build_issue_fix_candidate_preflight_packet(
    *,
    repo: str,
    issue_ref: str,
    input_payload: Mapping[str, Any] | None,
    generated_at: str | None,
) -> dict[str, Any]:
    """Reconcile compact prior work before an issue becomes runnable.

    The caller owns provider queries. This seam performs no network, memory, or
    repository reads and treats semantic PR evidence as actionable only after
    current-revision verification.
    """

    reference = normalise_github_issue_reference(
        repo=repo,
        issue_ref=issue_ref,
        url=None,
    )
    canonical_repo = str(reference["repo"])
    canonical_issue_ref = str(reference["issue_ref"])
    configured = input_payload is not None
    payload = input_payload or {}
    if configured and payload.get("schema_version") != (
        ISSUE_FIX_CANDIDATE_PREFLIGHT_INPUT_SCHEMA_VERSION
    ):
        raise ValueError(
            "candidate preflight input schema_version must be "
            "issue_fix_candidate_preflight_input_v0"
        )

    domain = _domain_projection(
        payload.get("domain_state"),
        repo=canonical_repo,
        issue_ref=canonical_issue_ref,
    )
    numeric = _matching_pr_rows(
        payload.get("numeric_pr_evidence"),
        repo=canonical_repo,
        issue_ref=canonical_issue_ref,
        semantic=False,
    )
    semantic = _matching_pr_rows(
        payload.get("semantic_pr_evidence"),
        repo=canonical_repo,
        issue_ref=canonical_issue_ref,
        semantic=True,
    )
    existing_prs = numeric + [
        row for row in semantic if row["pr_ref"] not in {item["pr_ref"] for item in numeric}
    ]

    route = "proceed"
    reason_codes: list[str] = []
    if domain and domain["terminal"]:
        route = "skip"
        reason_codes.append("terminal_domain_state")
    else:
        open_prs = [row for row in existing_prs if row["state"] == "OPEN"]
        merged_prs = [row for row in existing_prs if row["state"] == "MERGED"]
        closed_prs = [row for row in existing_prs if row["state"] == "CLOSED"]
        if open_prs:
            route = "reuse_existing_pr"
            reason_codes.append("open_implementation_pr")
        elif merged_prs:
            route = "skip"
            reason_codes.append("merged_implementation_pr")
        elif closed_prs:
            route = "comment_only"
            reason_codes.append("closed_implementation_pr_requires_disposition")
        elif domain and domain["route"] == "comment_only":
            route = "comment_only"
            reason_codes.append("existing_comment_only_domain_route")
        elif domain and domain["route"] == "triage_only":
            route = "skip"
            reason_codes.append("existing_triage_only_domain_route")
        else:
            reason_codes.append("no_prior_work_conflict")

    recall = payload.get("agentic_recall_receipt")
    recall = recall if isinstance(recall, Mapping) else {}
    call_count = int(recall.get("call_count") or 0)
    max_calls = int(recall.get("max_calls") or 0)
    receipt_status = public_safe_compact_text(
        str(recall.get("status") or ""), limit=120
    )
    candidate_runnable = route == "proceed"
    return {
        "ok": True,
        "schema_version": ISSUE_FIX_CANDIDATE_PREFLIGHT_SCHEMA_VERSION,
        "configured": configured,
        "generated_at": generated_at,
        "repo": canonical_repo,
        "issue_ref": canonical_issue_ref,
        "decision": {
            "route": route,
            "candidate_runnable": candidate_runnable,
            "reason_codes": reason_codes,
            "existing_pr_refs": [row["pr_ref"] for row in existing_prs],
        },
        "evidence": {
            "domain_state_matched": domain is not None,
            "domain_route": domain.get("route") if domain else None,
            "numeric_pr_matches": numeric,
            "semantic_pr_matches": semantic,
            "all_state_numeric_checked": "numeric_pr_evidence" in payload,
            "semantic_implementation_checked": "semantic_pr_evidence" in payload,
        },
        "agentic_recall": {
            "receipt_status": receipt_status or None,
            "call_count": call_count,
            "max_calls": max_calls,
            "action": (
                "preserve_existing_receipt"
                if not candidate_runnable and receipt_status
                else "not_opened_by_preflight"
            ),
            "provider_calls_performed": 0,
            "raw_memory_captured": False,
        },
        "provider_neutral": True,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "raw_provider_payload_captured": False,
    }
