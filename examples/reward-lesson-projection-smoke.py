#!/usr/bin/env python3
"""Validate human_reward lesson projection into status/quota warnings."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.feedback import compact_reward
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown
from loopx.status import compact_human_reward


GOAL_ID = "reward-lesson-projection-smoke"


def status_payload(reward: dict) -> dict:
    action = "[P1] Run SkillsBench before fixing the reward lesson projection."
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": 1,
        "open_count": 1,
        "done_count": 0,
        "first_open_items": [
            {
                "index": 1,
                "text": action,
                "role": "agent",
                "status": "open",
                "priority": "P1",
                "task_class": "advancement_task",
                "action_kind": "run_skillsbench",
                "todo_id": "todo_reward_lesson_projection",
            }
        ],
    }
    item = {
        "goal_id": GOAL_ID,
        "status": "reward_lesson_projection_smoke",
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": action,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "next_action": action,
            "stop_condition": "stop on private material",
            "agent_todos": agent_todos,
        },
    }
    return {
        "ok": True,
        "attention_queue": {"items": [item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "reward_lesson_projection_smoke",
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "latest_runs": [
                        {
                            "generated_at": "2026-06-24T00:00:00+00:00",
                            "goal_id": GOAL_ID,
                            "classification": "human_reward_recorded",
                            "recommended_action": "Run SkillsBench before fixing the route.",
                            "human_reward": reward,
                        }
                    ],
                }
            ]
        },
    }


def main() -> int:
    reward = compact_reward(
        recorded_at="2026-06-24T00:00:00+00:00",
        decision="route_correction",
        reward="mixed",
        reason_summary="User corrected the route: fix durable lesson projection before running more cases.",
        follow_up="Update the affected todo and next action before benchmark expansion.",
        lesson={
            "kind": "route",
            "summary": "Do not expand benchmark cases before the lesson projection route is fixed.",
            "avoid": ["Run SkillsBench before fixing"],
            "prefer": ["fix reward lesson projection"],
        },
    )
    compact = compact_human_reward(reward)
    assert compact is not None, reward
    assert compact["lesson"]["schema_version"] == "human_reward_lesson_v0", compact
    assert compact["lesson"]["kind"] == "route", compact
    assert compact["lesson"]["avoid"] == ["Run SkillsBench before fixing"], compact

    guard = build_quota_should_run(status_payload(compact), goal_id=GOAL_ID)
    warning = guard.get("reward_lesson_projection_warning")
    assert isinstance(warning, dict), guard
    assert warning["schema_version"] == "reward_lesson_projection_warning_v0", warning
    assert warning["match_count"] == 1, warning
    assert "Run SkillsBench" in warning["matches"][0]["avoid"], warning
    markdown = render_quota_should_run_markdown(guard)
    assert "reward_lesson_projection_warning" in markdown, markdown
    assert "reward_lesson_action" in markdown, markdown

    zero_token_reward = compact_reward(
        recorded_at="2026-06-24T00:00:00+00:00",
        decision="route_correction",
        reward="mixed",
        reason_summary="User correction phrase should not warn when it has no scope tokens.",
        follow_up=None,
        lesson={
            "kind": "route",
            "summary": "A tokenless avoid phrase should not match every recommended action.",
            "avoid": ["P0"],
        },
    )
    zero_token_compact = compact_human_reward(zero_token_reward)
    assert zero_token_compact is not None, zero_token_reward
    zero_token_guard = build_quota_should_run(status_payload(zero_token_compact), goal_id=GOAL_ID)
    assert "reward_lesson_projection_warning" not in zero_token_guard, zero_token_guard
    print("reward-lesson-projection smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
