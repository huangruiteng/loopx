#!/usr/bin/env python3
"""Smoke-test LoopX progress notification projection for Feishu/Lark bridges."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark.message_card import build_lark_markdown_reply_card  # noqa: E402
from loopx.capabilities.lark.progress_reporter import (  # noqa: E402
    build_acceptance_notification,
    build_bridge_error_notification,
    build_progress_notification,
    should_emit_notification,
)


def main() -> int:
    accepted = build_acceptance_notification(
        todo_id="todo_abc",
        goal_id="goal",
        request_text="ship a bounded change",
        agent_id="agent",
    )
    assert accepted.stage == "accepted", accepted
    assert should_emit_notification(accepted, previous_fingerprint=None)
    assert not should_emit_notification(accepted, previous_fingerprint=accepted.fingerprint)

    user_gate = build_progress_notification(
        todo_id="todo_abc",
        goal_id="goal",
        request_text="ship a bounded change",
        status_payload={},
        quota_payload={
            "goal_id": "goal",
            "requires_user_action": True,
            "recommended_action": "wait for approval",
            "interaction_contract": {
                "user_channel": {
                    "action_required": True,
                    "notify": "NOTIFY",
                    "reason": "exact external write approval is required",
                }
            },
            "user_todo_summary": {
                "first_open_items": [
                    {
                        "todo_id": "todo_gate",
                        "text": "Approve the exact external write.",
                    }
                ]
            },
        },
    )
    assert user_gate.stage == "user_action", user_gate
    assert user_gate.template == "red", user_gate
    assert "Approve the exact external write" in user_gate.markdown, user_gate.markdown

    running = build_progress_notification(
        todo_id="todo_abc",
        goal_id="goal",
        request_text="ship a bounded change",
        status_payload={},
        quota_payload={
            "goal_id": "goal",
            "should_run": True,
            "decision": "run",
            "effective_action": "bounded_delivery",
            "recommended_action": "execute one validated implementation segment",
            "heartbeat_recommendation": {"recommended_mode": "steering_audit_then_one_step"},
            "execution_obligation": {"contract_obligation": "validate and write back before spend"},
            "interaction_contract": {
                "agent_channel": {
                    "must_attempt": True,
                    "primary_action": "bounded_delivery",
                }
            },
        },
    )
    assert running.stage == "running", running
    assert "bounded_delivery" in running.markdown, running.markdown

    progress = build_progress_notification(
        todo_id="todo_abc",
        goal_id="goal",
        request_text="ship a bounded change",
        status_payload={
            "run_history": {
                "goals": [
                    {
                        "goal_id": "goal",
                        "latest_runs": [
                            {
                                "generated_at": "2026-06-25T00:00:00Z",
                                "classification": "validated_progress",
                                "summary": "Implemented the bridge poller.",
                            }
                        ],
                    }
                ]
            }
        },
        quota_payload={},
    )
    assert progress.stage == "progress", progress
    assert "Implemented the bridge poller" in progress.markdown, progress.markdown

    done = build_progress_notification(
        todo_id="todo_abc",
        goal_id="goal",
        request_text="ship a bounded change",
        status_payload={"todo_index": {"items": [{"todo_id": "todo_abc", "done": True}]}},
        quota_payload={},
    )
    assert done.stage == "done", done
    assert done.done is True, done

    error = build_bridge_error_notification(
        todo_id="todo_abc",
        goal_id="goal",
        source="quota",
        error="quota command timed out",
    )
    assert error.stage == "bridge_error:quota", error
    assert error.template == "red", error

    card = build_lark_markdown_reply_card(progress.markdown, title=progress.title, template=progress.template)
    assert card["header"]["template"] == "blue", card
    assert card["elements"][0]["text"]["tag"] == "lark_md", card

    print("lark progress reporter smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
