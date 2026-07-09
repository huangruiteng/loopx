from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..domain_state import default_domain_state_file_path, upsert_domain_state_jsonl


ISSUE_FIX_DOMAIN_STATE_LEDGER_FILENAME = "pr-lifecycle.jsonl"
ISSUE_FIX_FEASIBILITY_LEDGER_FILENAME = "feasibility.jsonl"


def _upsert_issue_fix_payload(
    ledger_path: str | Path,
    payload: dict[str, Any],
    *,
    key: dict[str, Any],
    existing_key_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
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
        )
    except Exception:
        projection["write_performed"] = False
        raise
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
        "response_payloads_captured",
        "raw_check_logs_captured",
        "local_paths_captured",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"issue-fix domain-state payload must keep {key}=false")
    return _upsert_issue_fix_payload(
        ledger_path,
        payload,
        key=issue_fix_pr_lifecycle_ledger_key(payload),
        existing_key_fn=issue_fix_pr_lifecycle_ledger_key,
    )


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
