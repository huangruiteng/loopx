#!/usr/bin/env python3
"""Smoke-test direct Lark inbox questions preempting ordinary quota work."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark.event_inbox import (  # noqa: E402
    acknowledge_lark_event_inbox,
)
from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
)
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402


GOAL_ID = "lark-inbox-priority-fixture"


def status_payload(project: Path) -> dict:
    next_action = "Advance the ordinary implementation todo."
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="ordinary_advancement_ready",
        recommended_action=next_action,
        next_action=next_action,
        agent_todo_items=[
            quota_todo_item(
                todo_id="todo_ordinary_advancement",
                title="Advance the ordinary implementation todo.",
                priority="P1",
            )
        ],
        goal_extra={
            "repo": str(project),
            "control_plane": {
                "lark_event_inbox": {
                    "enabled": True,
                    "config_path": ".loopx/config/lark/event-inbox.json",
                }
            },
        },
    )
    registry = project / ".loopx/registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "control_plane": {
                            "lark_event_inbox": {
                                "enabled": True,
                                "config_path": ".loopx/config/lark/event-inbox.json",
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    payload["registry"] = str(registry)
    return payload


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        project = Path(raw)
        config = project / ".loopx/config/lark/event-inbox.json"
        inbox = project / ".loopx/inbox/team-feedback"
        config.parent.mkdir(parents=True)
        inbox.mkdir(parents=True)
        config.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": ".loopx/inbox/team-feedback",
                    "capture_scope": "configured_chat_all",
                    "reply": {
                        "enabled": True,
                        "sender_profile": "project-review-bot",
                        "sender_identity": "bot",
                        "bot_display_name": "Project Review Bot",
                        "chat_id": "oc_project_review",
                    },
                }
            ),
            encoding="utf-8",
        )
        (inbox / "om_direct_question.json").write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_event_v0",
                    "event_id": "evt-direct-question",
                    "message_id": "om_direct_question",
                    "create_time": "2026-07-15T00:00:00Z",
                    "content": "@Project Review Bot 这个结论呢？",
                }
            ),
            encoding="utf-8",
        )

        decision = build_quota_should_run(status_payload(project), goal_id=GOAL_ID)
        assert decision["should_run"] is True, decision
        assert decision["effective_action"] == "lark_inbox_reply_due", decision
        lane = decision["work_lane_contract"]
        assert lane["lane"] == "lark_event_inbox", lane
        assert lane["next_lane"] == "advancement_task", lane
        assert lane["obligation"] == "drain_lark_inbox_reply_due", lane
        assert lane["priority_preemption"] is True, lane
        assert lane["direct_question_count"] == 1, lane
        assert lane["pending_count"] == 1, lane
        assert decision["execution_obligation"]["contract_obligation"] == lane["obligation"]
        assert "durable effect" in decision["recommended_action"], decision
        urgency = decision["goal_boundary"]["capabilities"]["lark_event_inbox"]["urgency"]
        assert urgency["reply_due"] is True, urgency
        assert urgency["local_private_content_returned"] is False, urgency
        assert "items" not in urgency and "message_id" not in json.dumps(urgency), urgency
        markdown = render_quota_should_run_markdown(decision)
        assert "lane=lark_event_inbox" in markdown, markdown
        assert "questions=1" in markdown, markdown

        acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_direct_question"],
            execute=True,
        )
        after_ack = build_quota_should_run(status_payload(project), goal_id=GOAL_ID)
        assert after_ack["work_lane_contract"]["lane"] == "advancement_task", after_ack
        assert after_ack["effective_action"] == "normal_run", after_ack

    print("lark-inbox-priority-smoke: ok")


if __name__ == "__main__":
    main()
