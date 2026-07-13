from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..semantic_preference import application_receipt, recall


BUILD_SCHEMA = "issue_fix_pr_description_build_v0"
SURFACE = "issue_fix.pr_description"
ISSUE_REFERENCE_BLOCK_SCHEMA = "issue_fix_pr_issue_reference_block_v0"

_ISSUE_REFERENCE_PATTERN = re.compile(
    r"^(?:#[1-9][0-9]*|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*)$"
)
_CLOSING_LINE_PATTERN = re.compile(
    r"(?im)^\s*(?:-\s*)?(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)"
    r"\s*:?\s*(#[1-9][0-9]*|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*)\s*$"
)
_RELATED_LINE_PATTERN = re.compile(
    r"(?im)^\s*(?:-\s*)?related\s+to\s*:?\s*"
    r"(#[1-9][0-9]*|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*)\s*$"
)
_CANONICAL_CLOSING_KEYWORD = {
    "close": "Closes",
    "closes": "Closes",
    "closed": "Closes",
    "fix": "Fixes",
    "fixes": "Fixes",
    "fixed": "Fixes",
    "resolve": "Resolves",
    "resolves": "Resolves",
    "resolved": "Resolves",
}

PreferenceApplier = Callable[
    [str, Sequence[Mapping[str, Any]]],
    Mapping[str, Any],
]
Recall = Callable[..., dict[str, Any]]


def _normalise_issue_references(
    values: Sequence[str] | None, *, field: str
) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a list")
    references: list[str] = []
    for raw in values:
        reference = str(raw or "").strip()
        if not _ISSUE_REFERENCE_PATTERN.fullmatch(reference):
            raise ValueError(
                f"{field} entries must use #N or owner/repository#N syntax"
            )
        if reference not in references:
            references.append(reference)
    return references


def _issue_reference_policy(
    *,
    closing_issue_references: Sequence[str] | None,
    related_issue_references: Sequence[str] | None,
    closing_keyword: str,
    issue_reference_section_label: str,
    targets_default_branch: bool | None,
) -> dict[str, Any]:
    closing = _normalise_issue_references(
        closing_issue_references, field="closing_issue_references"
    )
    related = _normalise_issue_references(
        related_issue_references, field="related_issue_references"
    )
    overlap = sorted(set(closing).intersection(related))
    if overlap:
        raise ValueError(
            "an issue reference cannot be both closing and related: "
            + ", ".join(overlap)
        )
    keyword = _CANONICAL_CLOSING_KEYWORD.get(str(closing_keyword or "").lower())
    if keyword is None:
        raise ValueError("closing_keyword must be a GitHub closing keyword")
    label = str(issue_reference_section_label or "").strip()
    if not label or "\n" in label or "\r" in label:
        raise ValueError("issue_reference_section_label must be one line")
    if closing and targets_default_branch is not True:
        raise ValueError(
            "closing issue references require explicit default-branch targeting"
        )
    return {
        "schema_version": ISSUE_REFERENCE_BLOCK_SCHEMA,
        "configured": bool(closing or related),
        "section_label": label,
        "closing_keyword": keyword,
        "closing_references": closing,
        "related_references": related,
        "target_default_branch_verified": targets_default_branch is True,
        "applied_after_semantic_preferences": True,
    }


def _strip_conflicting_reference_lines(
    description: str,
    *,
    closing_references: set[str],
    related_references: set[str],
) -> str:
    lines: list[str] = []
    for line in description.splitlines():
        closing = _CLOSING_LINE_PATTERN.fullmatch(line)
        if closing and closing.group(1) in related_references:
            continue
        related = _RELATED_LINE_PATTERN.fullmatch(line)
        if related and related.group(1) in closing_references:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _apply_issue_reference_policy(
    description: str, policy: Mapping[str, Any]
) -> tuple[str, bool]:
    if not policy.get("configured"):
        return description, False
    closing_references = set(policy.get("closing_references") or [])
    related_references = set(policy.get("related_references") or [])
    cleaned = _strip_conflicting_reference_lines(
        description,
        closing_references=closing_references,
        related_references=related_references,
    )
    present_closing = {
        match.group(1) for match in _CLOSING_LINE_PATTERN.finditer(cleaned)
    }
    present_related = {
        match.group(1) for match in _RELATED_LINE_PATTERN.finditer(cleaned)
    }
    missing_lines = [
        f"{policy['closing_keyword']} {reference}"
        for reference in policy.get("closing_references") or []
        if reference not in present_closing
    ]
    missing_lines.extend(
        f"Related to {reference}"
        for reference in policy.get("related_references") or []
        if reference not in present_related
    )
    if missing_lines:
        block = f"## {policy['section_label']}\n\n" + "\n".join(missing_lines)
        cleaned = f"{cleaned}\n\n{block}".strip()
    return cleaned + (
        "\n" if description.endswith("\n") else ""
    ), cleaned != description.strip()


def _result(
    *,
    description: str,
    recall_status: str,
    application_status: str,
    recalled_item_count: int = 0,
    applied_preference_count: int = 0,
    receipt: Mapping[str, Any] | None = None,
    fail_open_preserved_base: bool = False,
    description_changed: bool = False,
    issue_reference_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = dict(issue_reference_policy or {})
    description, issue_reference_changed = _apply_issue_reference_policy(
        description, policy
    )
    return {
        "ok": True,
        "schema_version": BUILD_SCHEMA,
        "description": description,
        "description_changed": description_changed or issue_reference_changed,
        "semantic_preference": {
            "surface": SURFACE,
            "recall_status": recall_status,
            "application_status": application_status,
            "recalled_item_count": recalled_item_count,
            "applied_preference_count": applied_preference_count,
            "receipt": dict(receipt) if receipt is not None else None,
        },
        "raw_preference_content_returned": False,
        "fail_open_preserved_base": fail_open_preserved_base,
        "issue_reference_block": {
            "schema_version": policy.get("schema_version"),
            "configured": bool(policy.get("configured")),
            "applied": issue_reference_changed,
            "section_label": policy.get("section_label"),
            "closing_keyword": policy.get("closing_keyword"),
            "closing_reference_count": len(policy.get("closing_references") or []),
            "related_reference_count": len(policy.get("related_references") or []),
            "target_default_branch_verified": bool(
                policy.get("target_default_branch_verified")
            ),
            "applied_after_semantic_preferences": bool(
                policy.get("applied_after_semantic_preferences")
            ),
        },
    }


def _preference_refs(items: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(item.get("preference_ref") or "").strip()
        for item in items
        if str(item.get("preference_ref") or "").strip()
    }


def build_issue_fix_pr_description(
    base_description: str,
    *,
    project: str | Path,
    semantic_preference_config: str | Path | None = None,
    context: Sequence[str] | None = None,
    application_id: str | None = None,
    artifact_ref: str | None = None,
    apply_preferences: PreferenceApplier | None = None,
    recall_fn: Recall = recall,
    closing_issue_references: Sequence[str] | None = None,
    related_issue_references: Sequence[str] | None = None,
    closing_keyword: str = "Fixes",
    issue_reference_section_label: str = "关联 Issue",
    targets_default_branch: bool | None = None,
) -> dict[str, Any]:
    """Apply optional semantic preferences at the PR-description boundary.

    The caller owns prose generation through ``apply_preferences``. This wrapper
    owns one recall, fail-open preservation, preference-reference attribution,
    and the stateless compact receipt returned for existing evidence/state
    writeback. Functional issue references are applied after semantic prose so a
    preference rewrite cannot remove closing metadata. It never persists the
    description or recalled provider items.
    """

    if not isinstance(base_description, str) or not base_description.strip():
        raise ValueError("base_description must be a non-empty string")
    issue_reference_policy = _issue_reference_policy(
        closing_issue_references=closing_issue_references,
        related_issue_references=related_issue_references,
        closing_keyword=closing_keyword,
        issue_reference_section_label=issue_reference_section_label,
        targets_default_branch=targets_default_branch,
    )
    if semantic_preference_config is None:
        return _result(
            description=base_description,
            recall_status="not_configured",
            application_status="not_configured",
            issue_reference_policy=issue_reference_policy,
        )

    recalled = recall_fn(
        semantic_preference_config,
        project=project,
        surface=SURFACE,
        context=context,
        execute=True,
    )
    recall_status = str(recalled.get("status") or "invalid")
    raw_items = recalled.get("items")
    items = (
        [dict(item) for item in raw_items if isinstance(item, Mapping)]
        if isinstance(raw_items, list)
        else []
    )
    if recall_status != "completed" or not items:
        return _result(
            description=base_description,
            recall_status=recall_status,
            application_status=recall_status,
            fail_open_preserved_base=recall_status == "provider_unavailable",
            issue_reference_policy=issue_reference_policy,
        )
    if apply_preferences is None:
        return _result(
            description=base_description,
            recall_status=recall_status,
            application_status="available_not_applied",
            recalled_item_count=len(items),
            issue_reference_policy=issue_reference_policy,
        )
    if not application_id:
        raise ValueError("application_id is required when preferences are applied")

    available_refs = _preference_refs(items)
    try:
        application = apply_preferences(base_description, items)
        if not isinstance(application, Mapping):
            raise TypeError("preference application must return an object")
        description = application.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("preference application description must be non-empty")
        raw_applied_refs = application.get("applied_preference_refs") or []
        if not isinstance(raw_applied_refs, Sequence) or isinstance(
            raw_applied_refs, (str, bytes)
        ):
            raise ValueError("applied_preference_refs must be a list")
        applied_refs = [
            str(ref).strip() for ref in raw_applied_refs if str(ref).strip()
        ]
        if any(ref not in available_refs for ref in applied_refs):
            raise ValueError("applied_preference_refs must come from recalled items")
        if description != base_description and not applied_refs:
            raise ValueError("changed descriptions require preference attribution")
    except Exception:  # noqa: BLE001 - configured application is a fail-open boundary
        return _result(
            description=base_description,
            recall_status=recall_status,
            application_status="application_failed",
            recalled_item_count=len(items),
            receipt=application_receipt(
                surface=SURFACE,
                application_id=application_id,
                outcome="failed",
                artifact_ref=artifact_ref,
            ),
            fail_open_preserved_base=True,
            issue_reference_policy=issue_reference_policy,
        )

    outcome = "applied" if applied_refs else "ignored"
    return _result(
        description=description,
        recall_status=recall_status,
        application_status=outcome,
        recalled_item_count=len(items),
        applied_preference_count=len(set(applied_refs)),
        receipt=application_receipt(
            surface=SURFACE,
            application_id=application_id,
            outcome=outcome,
            preference_refs=applied_refs,
            artifact_ref=artifact_ref,
        ),
        description_changed=description != base_description,
        issue_reference_policy=issue_reference_policy,
    )
