from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..domain_state import default_domain_state_file_path, upsert_domain_state_jsonl


ISSUE_FIX_DOMAIN_STATE_LEDGER_FILENAME = "pr-lifecycle.jsonl"
ISSUE_FIX_FEASIBILITY_LEDGER_FILENAME = "feasibility.jsonl"
REVIEWER_NOTIFICATION_RECEIPT_PATTERN = re.compile(r"sha256:[a-f0-9]{64}")


def _upsert_issue_fix_payload(
    ledger_path: str | Path,
    payload: dict[str, Any],
    *,
    key: dict[str, Any],
    existing_key_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
    unchanged_fn: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
    merge_existing_fn: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any]
    ]
    | None = None,
) -> dict[str, Any]:
    projection = payload.get("domain_state_projection")
    if not isinstance(projection, dict):
        raise ValueError("issue-fix payload must include domain_state_projection")

    projection.pop("write_result", None)
    projection.pop("write_skipped_reason", None)
    projection["write_performed"] = True
    try:
        result = upsert_domain_state_jsonl(
            ledger_path,
            payload,
            key=key,
            existing_key_fn=existing_key_fn,
            unchanged_fn=unchanged_fn,
            merge_existing_fn=merge_existing_fn,
        )
    except Exception:
        projection["write_performed"] = False
        raise
    if result.get("write_performed") is False:
        projection["write_performed"] = False
        projection["write_skipped_reason"] = "observation_fingerprint_unchanged"
    projection["write_result"] = result
    return result


def issue_fix_feasibility_ledger_key(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("issue-fix feasibility payload must include observation")
    repo = str(observation.get("repo") or "").strip()
    issue_ref = str(observation.get("issue_ref") or "").strip()
    if not repo or not issue_ref:
        raise ValueError("issue-fix feasibility payload must include repo and issue_ref")
    return {
        "repo": repo,
        "issue_ref": issue_ref,
    }


def upsert_issue_fix_feasibility_ledger_jsonl(
    ledger_path: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Upsert one compact issue-fix feasibility decision into domain state."""

    if payload.get("ok") is not True:
        raise ValueError("only successful issue-fix feasibility payloads can be written")
    for key in (
        "issue_body_captured",
        "comment_bodies_captured",
        "response_payloads_captured",
        "raw_logs_captured",
        "local_paths_captured",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"issue-fix domain-state payload must keep {key}=false")
    return _upsert_issue_fix_payload(
        ledger_path,
        payload,
        key=issue_fix_feasibility_ledger_key(payload),
        existing_key_fn=issue_fix_feasibility_ledger_key,
    )


def issue_fix_pr_lifecycle_ledger_key(payload: dict[str, Any]) -> dict[str, Any]:
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("issue-fix PR lifecycle payload must include observation")
    repo = str(observation.get("repo") or "").strip()
    pr_ref = str(observation.get("pr_ref") or "").strip()
    if not repo or not pr_ref:
        raise ValueError("issue-fix PR lifecycle payload must include repo and pr_ref")
    return {
        "repo": repo,
        "pr_ref": pr_ref,
    }


def upsert_issue_fix_pr_lifecycle_ledger_jsonl(
    ledger_path: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Upsert a compact issue-fix PR lifecycle packet into domain state."""

    if payload.get("ok") is not True:
        raise ValueError("only successful issue-fix PR lifecycle payloads can be written")
    for key in (
        "issue_body_captured",
        "comment_bodies_captured",
        "maintainer_correction_body_captured",
        "response_payloads_captured",
        "raw_check_logs_captured",
        "local_paths_captured",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"issue-fix domain-state payload must keep {key}=false")
    def unchanged_quiet_observation(
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> bool:
        existing_fingerprint = str(existing.get("observation_fingerprint") or "")
        incoming_fingerprint = str(incoming.get("observation_fingerprint") or "")
        existing_correction_fingerprint = str(
            existing.get("maintainer_correction_fingerprint") or ""
        )
        incoming_correction_fingerprint = str(
            incoming.get("maintainer_correction_fingerprint") or ""
        )
        existing_receipts = existing.get("reviewer_notification_receipts")
        incoming_receipts = incoming.get("reviewer_notification_receipts")
        return bool(
            existing_fingerprint
            and existing_fingerprint == incoming_fingerprint
            and existing_correction_fingerprint == incoming_correction_fingerprint
            and existing_receipts == incoming_receipts
        )

    def preserve_reviewer_notification_receipts(
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> dict[str, Any]:
        if "reviewer_notification_receipts" in incoming:
            return incoming
        receipts = existing.get("reviewer_notification_receipts")
        if not isinstance(receipts, list) or not receipts:
            return incoming
        return {**incoming, "reviewer_notification_receipts": list(receipts)}

    return _upsert_issue_fix_payload(
        ledger_path,
        payload,
        key=issue_fix_pr_lifecycle_ledger_key(payload),
        existing_key_fn=issue_fix_pr_lifecycle_ledger_key,
        unchanged_fn=unchanged_quiet_observation,
        merge_existing_fn=preserve_reviewer_notification_receipts,
    )


def persist_issue_fix_reviewer_notification_receipts(
    ledger_path: str | Path,
    payload: dict[str, Any],
    receipts: list[str],
) -> dict[str, Any]:
    """Persist only verified hashed reviewer-notification receipts in PR state."""

    # Rows written before a capture-boundary field was introduced may omit it.
    # Receipt persistence is a metadata-only migration, so make that historical
    # absence explicit without weakening the guard for any truthy value.
    for key in (
        "issue_body_captured",
        "comment_bodies_captured",
        "maintainer_correction_body_captured",
        "response_payloads_captured",
        "raw_check_logs_captured",
        "local_paths_captured",
    ):
        payload.setdefault(key, False)

    existing = payload.get("reviewer_notification_receipts")
    merged = [
        str(value)
        for value in (existing if isinstance(existing, list) else [])
        if REVIEWER_NOTIFICATION_RECEIPT_PATTERN.fullmatch(str(value))
    ]
    for receipt in receipts:
        text = str(receipt)
        if not REVIEWER_NOTIFICATION_RECEIPT_PATTERN.fullmatch(text):
            raise ValueError("reviewer notification receipts must be sha256 keys")
        if text not in merged:
            merged.append(text)
    if merged == (existing if isinstance(existing, list) else []):
        return {
            "status": "unchanged",
            "write_performed": False,
            "row_count": None,
            "path_recorded": False,
        }
    payload["reviewer_notification_receipts"] = merged
    return upsert_issue_fix_pr_lifecycle_ledger_jsonl(ledger_path, payload)


def default_issue_fix_domain_state_ledger_path(
    *,
    project: str | Path = ".",
    goal_id: str,
) -> Path:
    """Return the project-local domain-state ledger path for issue-fix PRs."""

    return default_domain_state_file_path(
        project=project,
        goal_id=goal_id,
        domain_pack="issue_fix",
        filename=ISSUE_FIX_DOMAIN_STATE_LEDGER_FILENAME,
    )


def default_issue_fix_feasibility_ledger_path(
    *,
    project: str | Path = ".",
    goal_id: str,
) -> Path:
    """Return the project-local issue-fix feasibility ledger path."""

    return default_domain_state_file_path(
        project=project,
        goal_id=goal_id,
        domain_pack="issue_fix",
        filename=ISSUE_FIX_FEASIBILITY_LEDGER_FILENAME,
    )
