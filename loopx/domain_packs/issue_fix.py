from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain_state import default_domain_state_file_path, upsert_domain_state_jsonl


ISSUE_FIX_DOMAIN_STATE_LEDGER_FILENAME = "pr-lifecycle.jsonl"


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
    return upsert_domain_state_jsonl(
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
