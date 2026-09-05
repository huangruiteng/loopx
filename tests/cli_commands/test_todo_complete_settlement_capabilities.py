from __future__ import annotations

from pathlib import Path

from settlement_capability_dispatch_fixture import (
    AGENT_ID,
    COMPLETED_TODO,
    GATED_TODO,
    PLAIN_TODO,
    complete_todo_via_cli,
)


def _write_stage_state(project: Path) -> None:
    project.joinpath("goal.md").write_text(
        f"""# Goal

## User Todo

## Agent Todo

- [ ] Ship the localized weekly report slice.
  <!-- loopx:todo todo_id={COMPLETED_TODO} status=open task_class=advancement_task claimed_by={AGENT_ID} continuation_policy=same_agent_non_delivery -->
- [ ] Retry the outbound channel sync once network capacity returns.
  <!-- loopx:todo todo_id={GATED_TODO} status=open task_class=advancement_task claimed_by={AGENT_ID} action_kind=gated_work resume_when=capacity_available:network -->
- [ ] Draft the follow-up frontier analysis.
  <!-- loopx:todo todo_id={PLAIN_TODO} status=open task_class=advancement_task claimed_by={AGENT_ID} -->
""",
        encoding="utf-8",
    )


def _dispatched_next_action_source(captured: dict[str, object]) -> str:
    intents = captured["post_writeback_hooks"]["intents"]
    assert isinstance(intents, list) and len(intents) == 1
    items = intents[0]["payload"]["project_progress"]["items"]
    matched = [
        item["source_ref"]
        for item in items
        if item.get("content_kind") == "next_action"
    ]
    assert len(matched) == 1
    return matched[0]


def test_todo_complete_dispatch_selects_gated_successor_with_settlement_evidence(
    tmp_path: Path,
) -> None:
    captured, _registry, _runtime = complete_todo_via_cli(
        tmp_path,
        journal_capabilities=["network"],
        write_state=_write_stage_state,
    )

    assert captured["available_capabilities"] == ["network"]
    assert _dispatched_next_action_source(captured) == f"todo:{GATED_TODO}"


def test_todo_complete_dispatch_fails_closed_without_capability_evidence(
    tmp_path: Path,
) -> None:
    captured, _registry, _runtime = complete_todo_via_cli(
        tmp_path,
        journal_capabilities=[],
        write_state=_write_stage_state,
    )

    assert "available_capabilities" not in captured
    assert _dispatched_next_action_source(captured) == f"todo:{PLAIN_TODO}"
