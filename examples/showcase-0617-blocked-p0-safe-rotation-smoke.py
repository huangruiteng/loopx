#!/usr/bin/env python3
"""Reproduce the 0617 blocked-P0/safe-fallback showcase with synthetic data."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402


GOAL_ID = "showcase-0617-blocked-p0-safe-rotation"


def todo(
    *,
    index: int,
    text: str,
    role: str,
    priority: str,
    task_class: str,
    action_kind: str,
) -> dict[str, object]:
    return {
        "index": index,
        "text": text,
        "role": role,
        "status": "open",
        "priority": priority,
        "task_class": task_class,
        "action_kind": action_kind,
    }


def todo_summary(*, source_section: str, items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "todo_summary_v0",
        "source_section": source_section,
        "total_count": len(items),
        "open_count": len(items),
        "done_count": 0,
        "first_open_items": items,
        "items": items,
    }


def status_payload() -> dict[str, object]:
    user_gate = todo(
        index=1,
        role="user",
        priority="P0",
        task_class="user_gate",
        action_kind="ale_image",
        text=(
            "[P0] Decide whether to acquire the large local image required by "
            "the ALE lane before any ALE execution."
        ),
    )
    blocked_agent_todo = todo(
        index=1,
        role="agent",
        priority="P0",
        task_class="advancement_task",
        action_kind="ale_image",
        text=(
            "[P0] Run the ALE lane only after the user approves the large local "
            "image acquisition."
        ),
    )
    safe_fallback_todo = todo(
        index=2,
        role="agent",
        priority="P1",
        task_class="advancement_task",
        action_kind="terminal_bench_no_upload",
        text=(
            "[P1] Continue the safe no-upload Terminal-Bench rotation and write "
            "back validation evidence."
        ),
    )
    attention_item = {
        "goal_id": GOAL_ID,
        "status": "benchmark_rotation_waiting_on_p0_gate",
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": "Surface the ALE gate, then continue the safe no-upload fallback.",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible synthetic showcase fixture",
        },
        "project_asset": {
            "next_action": "Surface the ALE gate, then continue the safe no-upload fallback.",
            "stop_condition": "stop before private materials, uploads, or unapproved image acquisition",
            "user_todos": todo_summary(
                source_section="User Todo / Owner Review Reading Queue",
                items=[user_gate],
            ),
            "agent_todos": todo_summary(
                source_section="Agent Todo",
                items=[blocked_agent_todo, safe_fallback_todo],
            ),
        },
    }
    return {
        "ok": True,
        "attention_queue": {"items": [attention_item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "domain": "showcase",
                    "status": "active",
                    "adapter_kind": "synthetic_showcase_fixture_v0",
                    "adapter_status": "connected-read-only",
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ]
        },
    }


def main() -> int:
    decision = build_quota_should_run(status_payload(), goal_id=GOAL_ID)
    markdown = render_quota_should_run_markdown(decision)
    fallback = decision.get("scoped_user_gate_fallback")
    obligation = decision.get("execution_obligation")

    assert decision["should_run"] is True, decision
    assert decision["requires_user_action"] is True, decision
    assert decision["safe_bypass_allowed"] is True, decision
    assert decision["safe_bypass_kind"] == "scoped_user_gate_fallback", decision
    assert isinstance(fallback, dict), decision
    assert fallback["blocked_user_gate"]["action_kind"] == "ale_image", fallback
    assert fallback["blocked_agent_items"][0]["action_kind"] == "ale_image", fallback
    assert fallback["selected_executable"]["action_kind"] == "terminal_bench_no_upload", fallback
    assert isinstance(obligation, dict) and obligation["must_attempt_work"] is True, obligation
    assert obligation["kind"] == "scoped_user_gate_fallback", obligation
    assert "scoped_user_gate_fallback" in markdown, markdown
    assert "safe no-upload Terminal-Bench rotation" in markdown, markdown

    print("showcase-0617-blocked-p0-safe-rotation-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
