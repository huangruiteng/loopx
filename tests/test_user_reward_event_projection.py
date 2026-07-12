from __future__ import annotations

import json
from pathlib import Path

from loopx.capabilities.lark.event_inbox import (
    inspect_lark_event_inbox,
    project_lark_event_inbox_reward,
)
from loopx.feedback import compact_reward
from loopx.control_plane.runtime.reward_events import (
    active_reward_lessons,
    append_reward_event,
    load_reward_events,
)
from loopx.history import collect_history
from loopx.quota import build_quota_should_run


GOAL_ID = "user-reward-projection-goal"
RUN_AT = "2026-07-12T00:00:00+00:00"


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    inbox = project / ".loopx" / "inbox" / "feedback"
    config = project / ".loopx" / "config" / "lark-inbox.json"
    inbox.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "schema_version": "lark_event_inbox_config_v0",
                "enabled": True,
                "inbox_dir": ".loopx/inbox/feedback",
                "capture_scope": "configured_chat_all",
            }
        ),
        encoding="utf-8",
    )
    (inbox / "feedback.json").write_text(
        json.dumps(
            {
                "schema_version": "lark_event_inbox_event_v0",
                "event_id": "event-feedback-1",
                "message_id": "om_feedback_1",
                "create_time": "2026-07-12T00:01:00Z",
                "content": "raw source content must not enter reward state",
            }
        ),
        encoding="utf-8",
    )
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text("# Goal\n\n## Progress Ledger\n\n", encoding="utf-8")
    run_dir = runtime / "goals" / GOAL_ID / "runs"
    run_dir.mkdir(parents=True)
    run_json = run_dir / "run.json"
    run_md = run_dir / "run.md"
    run_json.write_text("{}\n", encoding="utf-8")
    run_md.write_text("# run\n", encoding="utf-8")
    (run_dir / "index.jsonl").write_text(
        json.dumps(
            {
                "generated_at": RUN_AT,
                "goal_id": GOAL_ID,
                "classification": "fixture_run",
                "recommended_action": "Publish a ready pull request before memory acceptance.",
                "json_path": str(run_json),
                "markdown_path": str(run_md),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": "ACTIVE_GOAL_STATE.md",
                        "status": "eligible",
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return project, runtime, registry, config


def _status_payload(history: dict) -> dict:
    action = "Publish a ready pull request before memory acceptance."
    todo = {
        "todo_id": "todo_reward_projection",
        "text": action,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
    }
    summary = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": 1,
        "open_count": 1,
        "done_count": 0,
        "first_open_items": [todo],
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "eligible",
                    "waiting_on": "codex",
                    "source": "project_asset",
                    "recommended_action": action,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                        "spent_slots": 0,
                        "state": "eligible",
                    },
                    "project_asset": {"next_action": action, "agent_todos": summary},
                }
            ]
        },
        "run_history": history,
    }


def test_lark_reward_projection_is_idempotent_and_quota_visible(tmp_path: Path) -> None:
    project, runtime, registry, config = _fixture(tmp_path)
    reward = compact_reward(
        recorded_at="2026-07-12T00:02:00+00:00",
        decision="owner_constraint",
        reward="negative",
        reason_summary="Publication must wait for the memory acceptance gate.",
        follow_up="Keep new pull requests in draft state.",
        lesson={
            "kind": "safety_boundary",
            "summary": "New pull requests must remain drafts until memory acceptance closes.",
            "strength": "required",
            "scope": "workspace",
            "scope_key": "example-project",
            "avoid": ["Publish a ready pull request"],
            "prefer": ["Create a draft pull request"],
        },
    )
    first = project_lark_event_inbox_reward(
        project=project,
        config_path=config,
        registry_path=registry,
        runtime_root_override=str(runtime),
        goal_id=GOAL_ID,
        message_id="om_feedback_1",
        reward=reward,
        execute=True,
    )
    assert first["reward_event_appended"] is True
    assert first["acknowledged"] is True
    assert inspect_lark_event_inbox(project=project, config_path=config)["pending_count"] == 0

    second = project_lark_event_inbox_reward(
        project=project,
        config_path=config,
        registry_path=registry,
        runtime_root_override=str(runtime),
        goal_id=GOAL_ID,
        message_id="om_feedback_1",
        reward=reward,
        execute=True,
    )
    assert second["reward_event_already_exists"] is True
    ledger = runtime / "goals" / GOAL_ID / "reward-events" / "index.jsonl"
    text = ledger.read_text(encoding="utf-8")
    assert len(text.splitlines()) == 1
    assert "om_feedback_1" not in text
    assert "raw source content" not in text

    history = collect_history(
        registry_path=registry,
        runtime_root=runtime,
        goal_id=GOAL_ID,
        limit=10,
    )
    goal = history["goals"][0]
    assert goal["reward_event_count"] == 1
    assert goal["active_reward_lessons"][0]["strength"] == "required"

    quota = build_quota_should_run(_status_payload(history), goal_id=GOAL_ID)
    projection = quota["reward_lesson_projection"]
    assert projection["required_count"] == 1
    assert quota["reward_lesson_projection_warning"]["match_count"] == 1
    lessons = quota["interaction_contract"]["agent_channel"]["operating_lessons"]
    assert lessons[0]["strength"] == "required"


def test_new_reward_can_supersede_an_older_lesson(tmp_path: Path) -> None:
    ledger = tmp_path / "reward-events.jsonl"
    first_reward = compact_reward(
        recorded_at="2026-07-12T00:00:00+00:00",
        decision="initial_preference",
        reward="positive",
        reason_summary="Initial preference.",
        follow_up=None,
        lesson={
            "kind": "operating_rule",
            "summary": "Use the initial delivery format.",
            "strength": "advisory",
            "scope": "workspace",
        },
        source_kind="direct",
        source_event_ref="initial-preference",
    )
    first = append_reward_event(
        ledger,
        goal_id=GOAL_ID,
        run_generated_at=RUN_AT,
        reward=first_reward,
        dry_run=False,
    )
    correction = compact_reward(
        recorded_at="2026-07-12T00:01:00+00:00",
        decision="corrected_preference",
        reward="mixed",
        reason_summary="The owner replaced the initial format.",
        follow_up=None,
        lesson={
            "kind": "operating_rule",
            "summary": "Use the corrected delivery format.",
            "strength": "required",
            "scope": "workspace",
            "supersedes": [first["reward_id"]],
        },
        source_kind="direct",
        source_event_ref="corrected-preference",
    )
    append_reward_event(
        ledger,
        goal_id=GOAL_ID,
        run_generated_at=RUN_AT,
        reward=correction,
        dry_run=False,
    )
    active = active_reward_lessons(load_reward_events(ledger))
    assert len(active) == 1
    assert active[0]["summary"] == "Use the corrected delivery format."
    assert active[0]["strength"] == "required"
