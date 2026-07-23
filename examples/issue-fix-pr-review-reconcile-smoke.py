#!/usr/bin/env python3
"""Prove revision-aware, host-neutral PR review reconciliation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.pr_gate_reconcile import (  # noqa: E402
    reconcile_issue_fix_pr_review,
)
from loopx.capabilities.issue_fix.pr_review_ack import (  # noqa: E402
    record_issue_fix_pr_review_ack,
)
from loopx.status import parse_active_state_todos  # noqa: E402
from loopx.todos import update_goal_todo  # noqa: E402


PR_URL = "https://github.com/huangruiteng/loopx/pull/1716"


def record_ack(
    *,
    registry_path: Path,
    runtime_root: Path,
    project: Path,
    generated_at: str,
) -> dict[str, Any]:
    return record_issue_fix_pr_review_ack(
        registry_path=registry_path,
        runtime_root_arg=str(runtime_root),
        goal_id="example-goal",
        todo_id="todo_github_review",
        agent_id="codex-test",
        project=project,
        url=PR_URL,
        owner_acknowledged=True,
        generated_at=generated_at,
    )


def todo(state_file: Path, todo_id: str) -> dict[str, Any]:
    projection = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
    return next(
        item
        for item in projection["user_todos"]["items"]
        if item["todo_id"] == todo_id
    )


def reconcile_without_provider(
    *,
    registry_path: Path,
    runtime_root: Path,
    project: Path,
    todo_id: str,
    ack_receipt: dict[str, Any] | None,
    url: str = PR_URL,
) -> dict[str, Any]:
    with patch(
        "loopx.capabilities.issue_fix.pr_gate_reconcile."
        "build_issue_fix_pr_lifecycle_monitor_packet",
        side_effect=AssertionError("invalid acknowledgement must not read provider"),
    ):
        return reconcile_issue_fix_pr_review(
            registry_path=registry_path,
            runtime_root_arg=str(runtime_root),
            goal_id="example-goal",
            todo_id=todo_id,
            agent_id="codex-test",
            project=project,
            url=url,
            ack_receipt=ack_receipt,
            fetch_metadata=True,
            execute=True,
        )


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="loopx-issue-fix-pr-review-reconcile-"
    ) as tmpdir:
        project = Path(tmpdir)
        runtime_root = project / "runtime"
        registry_path = project / ".loopx" / "registry.json"
        state_file = (
            project / ".codex" / "goals" / "example-goal" / "ACTIVE_GOAL_STATE.md"
        )
        registry_path.parent.mkdir(parents=True)
        state_file.parent.mkdir(parents=True)
        registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "common_runtime_root": str(runtime_root),
                    "goals": [
                        {
                            "id": "example-goal",
                            "status": "active",
                            "repo": str(project),
                            "state_file": (
                                ".codex/goals/example-goal/ACTIVE_GOAL_STATE.md"
                            ),
                            "adapter": {
                                "kind": "read_only_project_map_v0",
                                "status": "connected-read-only",
                            },
                            "coordination": {
                                "agent_model": "peer_v1",
                                "registered_agents": ["codex-test"],
                            },
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        state_file.write_text(
            "# Active Goal State\n\n"
            "## User Todo / Owner Review Reading Queue\n\n"
            "- [ ] Review the exact GitHub PR.\n"
            "  <!-- loopx:todo todo_id=todo_github_review status=open "
            "task_class=user_action bound_agent=codex-test -->\n\n"
            "- [ ] Review a non-GitHub change.\n"
            "  <!-- loopx:todo todo_id=todo_other_provider status=open "
            "task_class=user_action bound_agent=codex-test -->\n\n"
            "## Agent Todo\n\n",
            encoding="utf-8",
        )

        missing = reconcile_without_provider(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            todo_id="todo_github_review",
            ack_receipt=None,
        )
        assert missing["skip_reason"] == "ack_receipt_missing", missing
        assert missing["external_read_performed"] is False, missing
        unsupported = reconcile_without_provider(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            todo_id="todo_other_provider",
            ack_receipt=None,
            url="https://gitlab.com/group/project/-/merge_requests/12",
        )
        assert unsupported["skip_reason"] == "provider_unsupported", unsupported
        assert unsupported["external_read_performed"] is False, unsupported

        first_ack = record_ack(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            generated_at="2026-07-24T01:00:00Z",
        )
        replayed_ack = record_ack(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            generated_at="2026-07-24T01:00:00Z",
        )
        assert first_ack["write_performed"] is True, first_ack
        assert replayed_ack["replayed"] is True, replayed_ack
        assert first_ack["binding"]["todo_revision"], first_ack
        assert (
            first_ack["ack_receipt"]["receipt_id"]
            == replayed_ack["ack_receipt"]["receipt_id"]
        )

        updated = update_goal_todo(
            registry_path=registry_path,
            goal_id="example-goal",
            todo_id="todo_github_review",
            role="user",
            text="Review the exact GitHub PR after its latest push.",
            agent_id="codex-test",
            project=project,
        )
        assert updated["changed"] is True, updated
        stale = reconcile_without_provider(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            todo_id="todo_github_review",
            ack_receipt=first_ack["ack_receipt"],
        )
        assert stale["skip_reason"] == "stale_ack_receipt", stale
        assert todo(state_file, "todo_github_review")["status"] == "open"

        current_ack = record_ack(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            generated_at="2026-07-24T01:01:00Z",
        )
        assert current_ack["binding"]["todo_revision"] != (
            first_ack["binding"]["todo_revision"]
        )
        reconciled = reconcile_issue_fix_pr_review(
            registry_path=registry_path,
            runtime_root_arg=str(runtime_root),
            goal_id="example-goal",
            todo_id="todo_github_review",
            agent_id="codex-test",
            project=project,
            url=PR_URL,
            ack_receipt=current_ack["ack_receipt"],
            provider_payload={
                "state": "MERGED",
                "mergedAt": "2026-07-24T01:02:00Z",
            },
            execute=True,
        )
        assert reconciled["reconciled"] is True, reconciled
        assert reconciled["write_performed"] is True, reconciled
        assert todo(state_file, "todo_github_review")["status"] == "done"

        repeated = reconcile_without_provider(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            todo_id="todo_github_review",
            ack_receipt=current_ack["ack_receipt"],
        )
        assert repeated["already_reconciled"] is True, repeated
        assert repeated["external_read_performed"] is False, repeated

        assert todo(state_file, "todo_other_provider")["status"] == "open"

    print("issue-fix-pr-review-reconcile-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
