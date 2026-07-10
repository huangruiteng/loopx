#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.outcome_projection import (  # noqa: E402
    build_issue_fix_outcome_collection_from_domain_state,
    build_issue_fix_outcome_projection,
)
from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    default_issue_fix_domain_state_ledger_path,
    default_issue_fix_feasibility_ledger_path,
    upsert_issue_fix_feasibility_ledger_jsonl,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)
from loopx.presentation.sinks.lark.kanban import (  # noqa: E402
    LarkKanbanConfig,
    STATUS_DONE,
    sync_loopx_projection_to_lark_kanban,
    sync_loopx_todos_to_lark_kanban,
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


def assert_default_goal_sync_composes_outcomes() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-closeout-") as tmp:
        project = Path(tmp)
        goal_id = "public-issue-fix-closeout"
        registry = project / "registry.json"
        state = project / "active-state.md"
        state.write_text(
            "\n".join(
                [
                    "## User Todo / Owner Review Reading Queue",
                    "",
                    "## Agent Todo",
                    "",
                    "- [ ] [P2] Continue public fixture monitor",
                    "  <!-- loopx: todo_id=todo_monitor status=open task_class=continuous_monitor action_kind=monitor claimed_by=codex-public-fixture -->",
                ]
            ),
            encoding="utf-8",
        )
        registry.write_text(
            json.dumps(
                {
                    "goals": [
                        {
                            "id": goal_id,
                            "repo": str(project),
                            "state_file": state.name,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        feasibility_ledger = default_issue_fix_feasibility_ledger_path(
            project=project,
            goal_id=goal_id,
        )
        for number in (42, 43):
            packet = build_issue_fix_feasibility_packet(
                url=f"https://github.com/public-fixture/widgets/issues/{number}",
                reproduction_status="confirmed",
                scope_class="bounded",
                reproduction_label=f"focused fixture repro {number}",
                validation_label=f"focused fixture validation {number}",
            )
            upsert_issue_fix_feasibility_ledger_jsonl(feasibility_ledger, packet)

        lifecycle_ledger = default_issue_fix_domain_state_ledger_path(
            project=project,
            goal_id=goal_id,
        )
        linked = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/public-fixture/widgets/pull/77",
            issue_ref="issues_42",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {"name": "focused", "conclusion": "SUCCESS"}
                ],
            },
        )
        assert linked["observation"]["issue_ref"] == "issues_42", linked
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(lifecycle_ledger, linked)
        unlinked = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/public-fixture/widgets/pull/78",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(lifecycle_ledger, unlinked)

        collection = build_issue_fix_outcome_collection_from_domain_state(
            goal_id=goal_id,
            project=project,
            agent_id="codex-public-fixture",
        )
        assert collection["ok"] is True, collection
        assert collection["validation"]["ok"] is True, collection
        assert collection["source_counts"] == {
            "feasibility": 2,
            "pr_lifecycle": 2,
            "outcomes": 2,
            "unlinked_pr_lifecycle": 1,
        }, collection
        collection_by_issue = {
            item["issue_ref"]: item for item in collection["issue_fix_outcomes"]
        }
        assert collection_by_issue["issues_42"]["pull_request"]["number"] == 77
        assert collection_by_issue["issues_43"]["pull_request"] is None
        assert collection_by_issue["issues_42"]["validation"]["status"] == "declared"
        assert collection["source_contract"]["creates_parallel_state_machine"] is False

        delivery_path = project / "delivery-evidence.json"
        delivery_path.write_text(
            json.dumps(delivery_evidence(), ensure_ascii=False),
            encoding="utf-8",
        )
        outcome_command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--format",
            "json",
            "issue-fix",
            "outcome",
            "--goal-id",
            goal_id,
            "--project",
            str(project),
            "--repo",
            "public-fixture/widgets",
            "--issue-ref",
            "issues_42",
            "--pr-ref",
            "pull_77",
            "--delivery-evidence-json",
            str(delivery_path),
        ]
        ledger_before_preview = feasibility_ledger.read_text(encoding="utf-8")
        preview = subprocess.run(
            outcome_command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        preview_packet = json.loads(preview.stdout)
        assert preview_packet["issue_fix_outcomes"][0]["validation"]["status"] == "passed"
        assert preview_packet["source_contract"]["writes_source_state"] is False
        assert feasibility_ledger.read_text(encoding="utf-8") == ledger_before_preview

        persisted = subprocess.run(
            [*outcome_command, "--write-delivery-evidence"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        persisted_packet = json.loads(persisted.stdout)
        assert persisted_packet["source_contract"]["writes_source_state"] is True
        assert persisted_packet["domain_state_write"]["write_performed"] is True
        feasibility_rows = [
            json.loads(line)
            for line in feasibility_ledger.read_text(encoding="utf-8").splitlines()
        ]
        assert len(feasibility_rows) == 2, feasibility_rows
        stored = next(
            row
            for row in feasibility_rows
            if row["observation"]["issue_ref"] == "issues_42"
        )
        assert stored["delivery_evidence"]["validation_status"] == "passed"
        assert set(stored["delivery_evidence"]) == {
            "schema_version",
            "outcome_status",
            "validation_status",
            "validation_label",
            "changed_files",
            "commit_ref",
            "outputs",
            "risks",
            "recorded_at",
        }
        assert not list(feasibility_ledger.parent.glob("*outcome*"))

        ledger_after_write = feasibility_ledger.read_text(encoding="utf-8")
        repeated = subprocess.run(
            [*outcome_command, "--write-delivery-evidence"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        repeated_packet = json.loads(repeated.stdout)
        assert repeated_packet["domain_state_write"]["status"] == "unchanged"
        assert repeated_packet["domain_state_write"]["write_performed"] is False
        assert feasibility_ledger.read_text(encoding="utf-8") == ledger_after_write

        retained = build_issue_fix_outcome_collection_from_domain_state(
            goal_id=goal_id,
            project=project,
            agent_id="codex-public-fixture",
        )
        retained_by_issue = {
            item["issue_ref"]: item for item in retained["issue_fix_outcomes"]
        }
        assert retained_by_issue["issues_42"]["validation"]["status"] == "passed"
        assert retained_by_issue["issues_42"]["delivery"]["evidence_provided"] is True
        assert retained_by_issue["issues_43"]["validation"]["status"] == "declared"

        sync = sync_loopx_todos_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            registry_path=registry,
            goal_id=goal_id,
            agent_id="codex-public-fixture",
            execute=False,
        )
        assert sync["ok"] is True, sync
        assert sync["todo_count"] == 1, sync
        assert sync["issue_fix_outcome_count"] == 2, sync
        outcome_records = [
            item
            for item in sync["records"]
            if item["values"].get("Work Item Type") == "Issue Fix"
        ]
        assert len(outcome_records) == 2, sync
        linked_record = next(
            item
            for item in outcome_records
            if item["values"]["Issue"].endswith("/issues/42")
        )
        assert linked_record["values"]["Pull Request"].endswith("/pull/77")
        assert linked_record["values"]["Validation"].startswith("passed:")
        unlinked_record = next(
            item
            for item in outcome_records
            if item["values"]["Issue"].endswith("/issues/43")
        )
        assert unlinked_record["values"]["Pull Request"] == ""
        assert str(project) not in json.dumps(sync["records"], ensure_ascii=False)


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

    assert_default_goal_sync_composes_outcomes()

    print("issue-fix-outcome-projection-smoke: ok")


if __name__ == "__main__":
    main()
