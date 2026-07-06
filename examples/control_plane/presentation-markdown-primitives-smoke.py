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
from loopx.history import render_history_markdown  # noqa: E402
from loopx.presentation.markdown import as_dict, as_list, markdown_scalar  # noqa: E402
from loopx.presentation.renderers.status_markdown import (  # noqa: E402
    append_attention_queue_item_header_markdown,
)
from loopx.slash_commands import render_slash_command_catalog_markdown  # noqa: E402


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
            "registry": "/tmp/registry.json",
            "runtime_root": "/tmp/runtime",
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
            "registry": "/tmp/registry.json",
            "runtime_root": "/tmp/runtime",
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
            "runtime_root": "/tmp/runtime",
            "registry": "/tmp/registry.json",
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


def main() -> int:
    assert as_dict({"ok": True}) == {"ok": True}
    assert as_dict(["not", "a", "dict"]) == {}
    assert as_list(["item"]) == ["item"]
    assert as_list({"not": "a list"}) == []
    assert markdown_scalar(RAW_TEXT) == ESCAPED_TEXT

    surfaces = {
        "status": status_markdown(),
        "quota_plan": quota_plan_markdown(),
        "quota_should_run": quota_should_run_markdown(),
        "diagnose": diagnosis_markdown(),
        "history": history_markdown(),
        "slash_commands": slash_command_markdown(),
    }
    for label, markdown in surfaces.items():
        assert_escaped(label, markdown)
    print("presentation-markdown-primitives-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
