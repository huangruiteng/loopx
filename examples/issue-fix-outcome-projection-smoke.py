#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.outcome_projection import (  # noqa: E402
    build_issue_fix_outcome_projection,
)
from loopx.presentation.sinks.lark.kanban import (  # noqa: E402
    LarkKanbanConfig,
    STATUS_DONE,
    sync_loopx_projection_to_lark_kanban,
)


def feasibility_packet(*, route: str = "fix_pr") -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "issue_fix_feasibility_v0",
        "observation": {
            "repo": "public-fixture/widgets",
            "issue_ref": "issues_42",
            "number": 42,
            "permalink": "https://github.com/public-fixture/widgets/issues/42",
            "reproduction_status": "confirmed",
            "reproduction_label": "focused parser contract repro",
            "validation_label": "focused parser tests",
            "repository_context": {
                "repository_revision": "abc1234def5678",
                "context_fingerprint": "context-fixture-42",
                "context_status": "grounded",
            },
        },
        "decision": {"route": route},
        "repository_context_effect": {
            "context_fingerprint": "context-fixture-42",
            "context_status": "grounded",
            "reproduction_evidence_refs": ["parser-test-42"],
            "validation_evidence_refs": ["parser-test-42"],
        },
        "transition": {
            "decision": "runnable_successor"
            if route != "triage_only"
            else "no_followup",
            "projected_todo": {
                "text": "Run the focused parser validation and prepare review evidence."
            }
            if route != "triage_only"
            else None,
        },
    }


def lifecycle_packet(
    *,
    state: str = "OPEN",
    checks: str = "PENDING",
    review: str = "REVIEW_REQUIRED",
) -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "issue_fix_pr_lifecycle_monitor_v0",
        "observation": {
            "repo": "public-fixture/widgets",
            "pr_ref": "pull_77",
            "number": 77,
            "permalink": "https://github.com/public-fixture/widgets/pull/77",
            "state": state,
            "is_draft": False,
            "checks": {
                "aggregate": checks,
                "failing_count": int(checks == "FAILING"),
                "pending_count": int(checks == "PENDING"),
                "passing_count": int(checks == "PASSING"),
            },
            "review_decision": review,
            "merge_state_status": "CLEAN",
            "merged_at": "2026-07-10T00:00:00Z" if state == "MERGED" else None,
            "closed_at": "2026-07-10T00:00:00Z"
            if state in {"MERGED", "CLOSED"}
            else None,
        },
        "transition": {
            "decision": "no_followup"
            if state in {"MERGED", "CLOSED"}
            else "monitor_continuation",
            "reason": (
                "PR is merged; close the monitor with no follow-up."
                if state == "MERGED"
                else "PR checks are pending; keep monitoring."
            ),
        },
    }


def delivery_evidence() -> dict[str, object]:
    return {
        "schema_version": "issue_fix_delivery_evidence_input_v0",
        "outcome_status": "in_progress",
        "validation_status": "passed",
        "validation_label": "12 focused parser tests and lint",
        "changed_files": ["src/parser.py", "tests/test_parser.py"],
        "commit_ref": "fix-parser-abc1234",
        "outputs": [
            {
                "kind": "review_packet",
                "url": "https://github.com/public-fixture/widgets/pull/77",
            }
        ],
        "risks": ["full integration suite remains outside focused validation"],
    }


def main() -> None:
    projection = build_issue_fix_outcome_projection(
        goal_id="issue-fix-fixture-goal",
        feasibility_packet=feasibility_packet(),
        pr_lifecycle_packet=lifecycle_packet(),
        delivery_evidence_input=delivery_evidence(),
        agent_id="codex-public-fixture",
        generated_at="2026-07-10T00:00:00Z",
    )
    assert projection["ok"] is True, projection
    outcome = projection["issue_fix_outcomes"][0]
    assert outcome["stage"] == "ci_pending", outcome
    assert outcome["route"] == "fix_pr", outcome
    assert outcome["repository_context"]["revision"] == "abc1234def5678", outcome
    assert outcome["validation"]["status"] == "passed", outcome
    assert outcome["delivery"]["changed_files"] == [
        "src/parser.py",
        "tests/test_parser.py",
    ], outcome
    assert outcome["pull_request"]["checks"]["aggregate"] == "PENDING", outcome
    assert outcome["result"]["kind"] == "fix_pr_open", outcome
    assert projection["source_contract"]["creates_parallel_state_machine"] is False

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-outcome-") as tmp:
        sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=projection,
            agent_id="codex-public-fixture",
            sink_visibility="shared",
            config_path=Path(tmp) / "lark-kanban.json",
            execute=False,
        )
    assert sync["ok"] is True, sync
    assert sync["row_count"] == 1, sync
    row = sync["records"][0]
    assert row["todo_id"] == (
        "projection:issue-fix-outcome:issue_fix_outcome:"
        "public-fixture-widgets:issues_42"
    ), row
    assert row["values"]["Action Kind"] == "issue_fix_outcome", row
    assert row["values"]["Work Item Type"] == "Issue Fix", row
    assert row["values"]["Repository"] == "public-fixture/widgets", row
    assert row["values"]["Issue"] == "https://github.com/public-fixture/widgets/issues/42", row
    assert row["values"]["Pull Request"] == "https://github.com/public-fixture/widgets/pull/77", row
    assert row["values"]["Route"] == "fix_pr", row
    assert row["values"]["Stage"] == "ci_pending", row
    assert row["values"]["Validation"].startswith("passed:"), row
    assert row["values"]["Outcome"] == "fix_pr_open", row
    assert "stage=ci_pending" in row["values"]["Evidence"], row
    assert "commit=fix-parser-abc1234" in row["values"]["Evidence"], row
    assert "risks=full integration suite" in row["values"]["Evidence"], row
    assert sync["public_safe_redaction"] is True, sync

    merged = build_issue_fix_outcome_projection(
        goal_id="issue-fix-fixture-goal",
        feasibility_packet=feasibility_packet(),
        pr_lifecycle_packet=lifecycle_packet(
            state="MERGED", checks="PASSING", review="APPROVED"
        ),
        delivery_evidence_input=delivery_evidence(),
        agent_id="codex-public-fixture",
    )
    merged_outcome = merged["issue_fix_outcomes"][0]
    assert merged_outcome["stage"] == "merged", merged_outcome
    assert merged_outcome["status"] == "done", merged_outcome
    assert merged_outcome["result"]["terminal"] is True, merged_outcome
    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-merged-") as tmp:
        merged_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=merged,
            agent_id="codex-public-fixture",
            config_path=Path(tmp) / "lark-kanban.json",
            execute=False,
        )
    assert merged_sync["row_count"] == 1, merged_sync
    assert merged_sync["records"][0]["values"]["Status"] == STATUS_DONE, merged_sync

    triage = build_issue_fix_outcome_projection(
        goal_id="issue-fix-fixture-goal",
        feasibility_packet=feasibility_packet(route="triage_only"),
    )
    assert triage["issue_fix_outcomes"][0]["stage"] == "triage_complete", triage

    comment_delivery = delivery_evidence()
    comment_delivery["outcome_status"] = "completed"
    comment_delivery["outputs"] = [
        {
            "kind": "issue_comment",
            "url": "https://github.com/public-fixture/widgets/issues/42#issuecomment-1",
        }
    ]
    comment = build_issue_fix_outcome_projection(
        goal_id="issue-fix-fixture-goal",
        feasibility_packet=feasibility_packet(route="comment_only"),
        delivery_evidence_input=comment_delivery,
    )
    comment_outcome = comment["issue_fix_outcomes"][0]
    assert comment_outcome["stage"] == "comment_published", comment_outcome
    assert comment_outcome["result"]["kind"] == "useful_comment_published", (
        comment_outcome
    )
    assert comment_outcome["result"]["terminal"] is True, comment_outcome

    blocked_delivery = delivery_evidence()
    blocked_delivery["outcome_status"] = "blocked"
    blocked_delivery["validation_status"] = "failed"
    blocked = build_issue_fix_outcome_projection(
        goal_id="issue-fix-fixture-goal",
        feasibility_packet=feasibility_packet(),
        pr_lifecycle_packet=lifecycle_packet(),
        delivery_evidence_input=blocked_delivery,
    )
    blocked_outcome = blocked["issue_fix_outcomes"][0]
    assert blocked_outcome["stage"] == "delivery_blocked", blocked_outcome
    assert blocked_outcome["status"] == "blocked", blocked_outcome

    unsafe = delivery_evidence()
    unsafe["changed_files"] = ["/Users/example/private.py"]
    try:
        build_issue_fix_outcome_projection(
            goal_id="issue-fix-fixture-goal",
            feasibility_packet=feasibility_packet(),
            delivery_evidence_input=unsafe,
        )
    except ValueError as exc:
        assert "repo-relative" in str(exc) or "public-safe" in str(exc), exc
    else:
        raise AssertionError("absolute changed file should be rejected")

    print("issue-fix-outcome-projection-smoke: ok")


if __name__ == "__main__":
    main()
