#!/usr/bin/env python3
"""Render a static frontstage fixture for goal_channel_projection_v0."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.frontstage import (  # noqa: E402
    build_goal_channel_projection,
    render_goal_channel_projection_html,
)


REDACTED_LOCAL_PATH = "/" + "Users/example/private-control-plane.md"
REDACTED_RAW_NOTE = "raw internal note" + " body"


def build_sample_projection() -> dict[str, object]:
    """Build a public-safe synthetic projection for dashboard/frontstage work."""

    return build_goal_channel_projection(
        goal_id="demo-goal-channel",
        status_item={
            "goal_id": "demo-goal-channel",
            "domain": "product-control-plane",
            "status": "safe_side_path_running",
            "waiting_on": "codex",
            "project_asset": {
                "display_name": "Demo Goal Channel",
                "state_updated_at": "2026-06-20T08:00:00Z",
                "next_action": (
                    "Render the read-only channel projection and keep the "
                    "event ledger as truth."
                ),
                "user_todos": {
                    "open_count": 1,
                    "first_open_items": [
                        {
                            "todo_id": "todo_user_decision",
                            "priority": "P0",
                            "status": "open",
                            "title": "Decide whether the gated delivery route may continue.",
                        }
                    ],
                },
                "agent_todos": {
                    "open_count": 2,
                    "first_open_items": [
                        {
                            "todo_id": "todo_primary_route",
                            "priority": "P0",
                            "status": "open",
                            "claimed_by": "codex-main-control",
                            "task_class": "advancement_task",
                            "title": "Keep the primary delivery route visible while it waits.",
                        },
                        {
                            "todo_id": "todo_side_fixture",
                            "priority": "P2",
                            "status": "open",
                            "claimed_by": "codex-side-bypass",
                            "task_class": "advancement_task",
                            "title": "Render the productization frontstage fixture.",
                        },
                    ],
                },
            },
        },
        status_payload={"generated_at": "2026-06-20T08:01:00Z"},
        quota_payload={
            "status": "eligible",
            "waiting_on": "codex",
            "recommended_action": "Continue only the safe side path.",
            "quota": {
                "state": "eligible",
                "reason": "synthetic fixture has quota",
                "spend_policy": "spend after validated writeback",
                "spent_slots": 2,
                "allowed_slots": 10,
            },
            "interaction_contract": {
                "user_channel": {"action_required": True, "notify": "NOTIFY"},
                "agent_channel": {
                    "must_attempt": True,
                    "delivery_allowed": True,
                    "quiet_noop_allowed": False,
                },
            },
        },
        run_history_goal={
            "id": "demo-goal-channel",
            "latest_runs": [
                {
                    "generated_at": "2026-06-20T08:02:00Z",
                    "classification": "validated_progress",
                    "health_check": "frontstage fixture rendered from compact projection",
                },
                {
                    "generated_at": "2026-06-20T07:50:00Z",
                    "classification": "operator_gate_recorded",
                    "health_check": "human decision stayed explicit",
                    "raw_internal_note": REDACTED_RAW_NOTE,
                },
            ],
        },
        review_packet={"generated_at": "2026-06-20T08:03:00Z"},
        artifacts=[
            {
                "kind": "doc",
                "label": "frontstage roadmap",
                "path": "docs/frontstage-channel-lease-roadmap.md",
            },
            {
                "kind": "local_state",
                "label": "omitted private control-plane source",
                "path": REDACTED_LOCAL_PATH,
            },
        ],
        generated_at="2026-06-20T08:04:00Z",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("html", "json"), default="html")
    args = parser.parse_args()

    projection = build_sample_projection()
    if args.format == "json":
        print(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(render_goal_channel_projection_html(projection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
