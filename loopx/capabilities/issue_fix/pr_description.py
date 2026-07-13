from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..semantic_preference import application_receipt, recall


BUILD_SCHEMA = "issue_fix_pr_description_build_v0"
SURFACE = "issue_fix.pr_description"

PreferenceApplier = Callable[
    [str, Sequence[Mapping[str, Any]]],
    Mapping[str, Any],
]
Recall = Callable[..., dict[str, Any]]


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
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": BUILD_SCHEMA,
        "description": description,
        "description_changed": description_changed,
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
) -> dict[str, Any]:
    """Apply optional semantic preferences at the PR-description boundary.

    The caller owns prose generation through ``apply_preferences``. This wrapper
    owns one recall, fail-open preservation, preference-reference attribution,
    and the stateless compact receipt returned for existing evidence/state
    writeback. It never persists the description or recalled provider items.
    """

    if not isinstance(base_description, str) or not base_description.strip():
        raise ValueError("base_description must be a non-empty string")
    if semantic_preference_config is None:
        return _result(
            description=base_description,
            recall_status="not_configured",
            application_status="not_configured",
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
        )
    if apply_preferences is None:
        return _result(
            description=base_description,
            recall_status=recall_status,
            application_status="available_not_applied",
            recalled_item_count=len(items),
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
    )
