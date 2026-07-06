#!/usr/bin/env python3
"""Smoke-test shared Markdown presentation primitives across CLI surfaces."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.quota.markdown import (  # noqa: E402
    render_quota_markdown,
    render_quota_should_run_markdown,
)
from loopx.diagnose import render_diagnosis_markdown  # noqa: E402
from loopx.history import (  # noqa: E402
    render_history_markdown,
    render_index_duplicate_inspection_markdown,
    render_index_duplicate_repair_markdown,
)
from loopx.presentation.markdown import (  # noqa: E402
    as_dict,
    as_list,
    markdown_code,
    markdown_scalar,
    markdown_table_row,
    markdown_table_separator,
)
from loopx.presentation.renderers.status_markdown import (  # noqa: E402
    append_attention_queue_item_header_markdown,
)
from loopx.pr_review import render_pr_review_markdown  # noqa: E402
from loopx.registry import render_registry_markdown  # noqa: E402
from loopx.slash_commands import render_slash_command_catalog_markdown  # noqa: E402
from loopx.summary_all import render_summary_all_markdown  # noqa: E402


RAW_TEXT = "alpha|beta\nnext"
ESCAPED_TEXT = "alpha\\|beta next"


def assert_escaped(label: str, markdown: str) -> None:
    assert ESCAPED_TEXT in markdown, (label, markdown)
    assert "alpha|beta" not in markdown, (label, markdown)
    assert "alpha|beta\nnext" not in markdown, (label, markdown)


def status_markdown() -> str:
    lines: list[str] = []
    append_attention_queue_item_header_markdown(
        lines,
        {
            "goal_id": "presentation-fixture",
            "status": "active",
            "lifecycle_phase": "running",
            "waiting_on": "codex",
            "severity": "normal",
            "source": "fixture",
            "recommended_action": RAW_TEXT,
        },
    )
    return "\n".join(lines)


def quota_plan_markdown() -> str:
    return render_quota_markdown(
        {
            "ok": True,
            "registry": "./fixtures/registry.json",
            "runtime_root": "./fixtures/runtime",
            "goal_count": 1,
            "run_count": 0,
            "mode": "plan",
            "summary": {
                "registered_goals": 1,
                "health_blockers": 0,
                "states": {},
            },
            "groups": {
                "eligible": [
                    {
                        "goal_id": "presentation-fixture",
                        "waiting_on": "codex",
                        "status": "active",
                        "lifecycle_phase": "running",
                        "quota": {},
                        "recommended_action": RAW_TEXT,
                    }
                ]
            },
        }
    )


def quota_should_run_markdown() -> str:
    return render_quota_should_run_markdown(
        {
            "ok": True,
            "goal_id": "presentation-fixture",
            "decision": "run",
            "should_run": True,
            "normal_delivery_allowed": True,
            "recovery_delivery_allowed": False,
            "self_repair_allowed": False,
            "effective_action": "normal_run",
            "actionable_by_codex": True,
            "state": "eligible",
            "waiting_on": "codex",
            "status": "active",
            "agent_lane_next_action": {
                "todo_id": "todo_alpha",
                "selected_by": "current_agent_claimed_todo",
                "confidence": 1.0,
                "text": RAW_TEXT,
            },
        }
    )


def diagnosis_markdown() -> str:
    return render_diagnosis_markdown(
        {
            "ok": True,
            "packet_kind": "agent_reasoning_evidence_packet",
            "agent_must_reason": True,
            "registry": "./fixtures/registry.json",
            "runtime_root": "./fixtures/runtime",
            "selected_goal_id": "presentation-fixture",
            "goal_count": 1,
            "goal_packet_count": 1,
            "run_count": 0,
            "selected": {
                "machine_signal": "agent_work_attention",
                "status": "active",
                "waiting_on": "codex",
                "severity": "normal",
                "recommended_action": RAW_TEXT,
                "user_question": RAW_TEXT,
                "todo_evidence": {
                    "user_open_count": 0,
                    "agent_open_count": 1,
                    "first_agent_todo": RAW_TEXT,
                },
            },
            "status_summary": {},
            "goals": [],
        }
    )


def history_markdown() -> str:
    return render_history_markdown(
        {
            "ok": True,
            "runtime_root": "./fixtures/runtime",
            "registry": "./fixtures/registry.json",
            "goal_filter": "presentation-fixture",
            "goal_count": 1,
            "run_count": 1,
            "runs": [
                {
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "goal_id": "presentation-fixture",
                    "classification": "fixture",
                    "json_exists": True,
                    "markdown_exists": True,
                    "recommended_action": RAW_TEXT,
                }
            ],
            "goals": [],
        }
    )


def history_duplicate_repair_markdown() -> str:
    return render_index_duplicate_repair_markdown(
        {
            "ok": True,
            "dry_run": True,
            "repaired": False,
            "runtime_root": "./fixtures/runtime",
            "registry": "./fixtures/registry.json",
            "goal_filter": "presentation-fixture",
            "checked_goal_count": 1,
            "raw_index_records": 2,
            "removed_row_count": 0,
            "preserved_reward_overlay_rows": 0,
            "preserved_structured_artifact_bundle_rows": 0,
            "unrepaired_group_count": 1,
            "truncated": False,
            "groups": [
                {
                    "goal_id": "presentation-fixture",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "action": "inspect",
                    "repairable": True,
                    "kept_line_numbers": [1],
                    "removed_line_numbers": [],
                    "reason": RAW_TEXT,
                }
            ],
        }
    )


def history_duplicate_inspection_markdown() -> str:
    return render_index_duplicate_inspection_markdown(
        {
            "ok": True,
            "runtime_root": "./fixtures/runtime",
            "registry": "./fixtures/registry.json",
            "goal_filter": "presentation-fixture",
            "checked_goal_count": 1,
            "raw_index_records": 2,
            "duplicate_group_count": 1,
            "duplicate_row_count": 2,
            "truncated": False,
            "groups": [
                {
                    "goal_id": "presentation-fixture",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "duplicate_kind": "same_action",
                    "severity": "warning",
                    "line_numbers": [1, 2],
                    "classifications": ["fixture"],
                    "repair_hint": RAW_TEXT,
                }
            ],
        }
    )


def registry_markdown() -> str:
    return render_registry_markdown(
        {
            "ok": True,
            "registry": "./fixtures/registry.json",
            "schema_version": "fixture",
            "updated_at": "2026-01-01T00:00:00Z",
            "common_runtime_root": "./fixtures/runtime",
            "goal_count": 1,
            "goals": [
                {
                    "id": "presentation-fixture",
                    "role": "project",
                    "parent_goal_id": "",
                    "domain": "fixture",
                    "status": "active",
                    "repo_exists": True,
                    "repo_goal_count": 1,
                    "state_file_exists": True,
                    "adapter_kind": "local",
                    "adapter_status": "ok",
                    "next_probe": RAW_TEXT,
                }
            ],
        }
    )


def slash_command_markdown() -> str:
    return render_slash_command_catalog_markdown(
        {
            "ok": True,
            "onboarding": {"suggested_user_note": ""},
            "commands": [
                {
                    "command": "/loopx-fixture",
                    "scope": "project",
                    "intent": RAW_TEXT,
                    "mutation_policy": "read-only",
                    "cli_reference": "loopx fixture",
                }
            ],
        }
    )


def assert_malformed_payloads_use_shared_coercion() -> None:
    pr_markdown = render_pr_review_markdown(
        {
            "ok": True,
            "summary": {"headline": "fixture"},
            "request": "not-a-dict",
            "review_groups": "not-a-dict",
            "review_sequence": "not-a-list",
            "pull_requests": "not-a-list",
        }
    )
    assert "## Unmerged PRs\n- none" in pr_markdown, pr_markdown
    assert "## Combined Review Sequence\n- none" in pr_markdown, pr_markdown

    summary_markdown = render_summary_all_markdown(
        {
            "ok": True,
            "summary": {"headline": "fixture"},
            "request": "not-a-dict",
            "lanes": "not-a-list",
            "gates": "not-a-list",
            "recent_progress": "not-a-list",
        }
    )
    assert "## Gates\n- none" in summary_markdown, summary_markdown


def main() -> int:
    assert as_dict({"ok": True}) == {"ok": True}
    assert as_dict(["not", "a", "dict"]) == {}
    assert as_list(["item"]) == ["item"]
    assert as_list({"not": "a list"}) == []
    assert markdown_scalar(RAW_TEXT) == ESCAPED_TEXT
    assert markdown_code(RAW_TEXT) == f"`{ESCAPED_TEXT}`"
    assert markdown_code(None) == "``"
    assert markdown_table_row([RAW_TEXT, markdown_code(RAW_TEXT)]) == f"| {ESCAPED_TEXT} | `{ESCAPED_TEXT}` |"
    assert markdown_table_separator(2) == "| --- | --- |"
    try:
        markdown_table_separator(0)
    except ValueError:
        pass
    else:
        raise AssertionError("markdown_table_separator should reject zero columns")
    assert_malformed_payloads_use_shared_coercion()

    surfaces = {
        "status": status_markdown(),
        "quota_plan": quota_plan_markdown(),
        "quota_should_run": quota_should_run_markdown(),
        "diagnose": diagnosis_markdown(),
        "history": history_markdown(),
        "history_duplicate_repair": history_duplicate_repair_markdown(),
        "history_duplicate_inspection": history_duplicate_inspection_markdown(),
        "registry": registry_markdown(),
        "slash_commands": slash_command_markdown(),
    }
    for label, markdown in surfaces.items():
        assert_escaped(label, markdown)
    print("presentation-markdown-primitives-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
