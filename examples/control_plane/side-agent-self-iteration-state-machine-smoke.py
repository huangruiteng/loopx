#!/usr/bin/env python3
"""Canary a side-agent self-iteration state machine end to end."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.canary_harness import (  # noqa: E402
    run_json_cli,
    run_json_cli_result,
    write_fixture_registry,
)


GOAL_ID = "side-agent-self-iteration-fixture"
AGENT_ID = "codex-product-capability"
PRIMARY_AGENT_ID = "codex-main-control"
START_TODO_ID = "todo_self_iter_start"
START_TODO_TEXT = "Build the first side-agent self-iteration canary slice."
NEXT_TODO_TEXT = (
    "Continue the side-agent self-iteration canary with scheduler and quota coverage."
)
GOAL_NEXT_ACTION = "Keep the primary goal route stable while the side-agent lane advances."
CAPABILITY_BLOCKED_TODO_ID = "todo_self_iter_network_only"
CAPABILITY_FALLBACK_TODO_ID = "todo_self_iter_filesystem_fallback"
CAPABILITY_FALLBACK_TEXT = (
    "Run the public-safe filesystem fallback while network capability is unavailable."
)
EXISTING_SUCCESSOR_START_TODO_ID = "todo_self_iter_existing_start"
EXISTING_SUCCESSOR_HANDOFF_TODO_ID = "todo_self_iter_existing_handoff"
EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID = "todo_self_iter_existing_same_agent"
EXISTING_SUCCESSOR_START_TEXT = "Finish a side-agent slice with an already-created handoff successor."
EXISTING_SUCCESSOR_HANDOFF_TEXT = "Review and merge the completed side-agent slice."


def run_cli(
    *args: str,
    registry_path: Path,
    runtime: Path,
) -> dict:
    return run_json_cli(
        *args,
        registry_path=registry_path,
        runtime_root=runtime,
        cwd=REPO_ROOT,
    )


def run_cli_result(
    *args: str,
    registry_path: Path,
    runtime: Path,
) -> tuple[int, dict]:
    return run_json_cli_result(
        *args,
        registry_path=registry_path,
        runtime_root=runtime,
        cwd=REPO_ROOT,
    )


def write_registry(
    *,
    project: Path,
    runtime: Path,
    registry_path: Path,
    adapter_kind: str,
) -> None:
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="side-agent-self-iteration-fixture",
        adapter_kind=adapter_kind,
        adapter_status="connected-read-only",
        registered_agents=[PRIMARY_AGENT_ID, AGENT_ID],
        primary_agent=PRIMARY_AGENT_ID,
        quota_allowed_slots=5,
        side_agent_independent_worktree_required=False,
    )


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "owner_mode: goal\n"
        'objective: "Exercise side-agent self-iteration."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Side-Agent Self-Iteration Fixture\n\n"
        "## Objective\n\n"
        "Exercise side-agent self-iteration.\n\n"
        "## Next Action\n\n"
        f"- {GOAL_NEXT_ACTION}\n\n"
        "## Agent Todo\n\n"
        f"- [ ] [P1] {START_TODO_TEXT}\n"
        f"  <!-- loopx:todo todo_id={START_TODO_ID} status=open "
        "task_class=advancement_task action_kind=state_machine_canary_refactor "
        f"claimed_by={AGENT_ID} -->\n",
        encoding="utf-8",
    )
    write_registry(
        project=project,
        runtime=runtime,
        registry_path=registry_path,
        adapter_kind="side_agent_self_iteration_fixture_v0",
    )
    return project, runtime, registry_path


def write_existing_successor_fixture(
    root: Path,
    *,
    successor_todo_id: str,
    successor_claimed_by: str,
    source_action_kind: str = "state_machine_canary_refactor",
    source_blocks_agent: str | None = None,
    source_required_write_scope: str | None = None,
    successor_action_kind: str = "primary_review",
    handoff_agent: str | None = None,
) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True)
    source_metadata = (
        f"todo_id={EXISTING_SUCCESSOR_START_TODO_ID} status=open "
        f"task_class=advancement_task action_kind={source_action_kind} "
        f"claimed_by={AGENT_ID}"
    )
    if source_blocks_agent:
        source_metadata += f" blocks_agent={source_blocks_agent}"
    if source_required_write_scope:
        source_metadata += f" required_write_scopes={source_required_write_scope}"
    state_path.write_text(
        "---\n"
        "status: active\n"
        "owner_mode: goal\n"
        'objective: "Exercise existing successor completion."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Existing Successor Completion Fixture\n\n"
        "## Objective\n\n"
        "Exercise existing successor completion.\n\n"
        "## Next Action\n\n"
        f"- {GOAL_NEXT_ACTION}\n\n"
        "## Agent Todo\n\n"
        f"- [ ] [P1] {EXISTING_SUCCESSOR_START_TEXT}\n"
        f"  <!-- loopx:todo {source_metadata} -->\n"
        f"- [ ] [P1] {EXISTING_SUCCESSOR_HANDOFF_TEXT}\n"
        f"  <!-- loopx:todo todo_id={successor_todo_id} status=open "
        f"task_class=advancement_task action_kind={successor_action_kind} "
        f"claimed_by={successor_claimed_by} -->\n",
        encoding="utf-8",
    )
    write_registry(
        project=project,
        runtime=runtime,
        registry_path=registry_path,
        adapter_kind="side_agent_existing_successor_fixture_v0",
    )
    if handoff_agent:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["goals"][0]["coordination"]["side_agent_handoff_agent"] = handoff_agent
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return project, runtime, registry_path


def write_capability_fallback_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "owner_mode: goal\n"
        'objective: "Exercise side-agent capability fallback routing."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Side-Agent Capability Fallback Fixture\n\n"
        "## Objective\n\n"
        "Exercise side-agent capability fallback routing.\n\n"
        "## Next Action\n\n"
        f"- Run {CAPABILITY_BLOCKED_TODO_ID} before fallback work.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] Run the network-only side-agent canary path.\n"
        f"  <!-- loopx:todo todo_id={CAPABILITY_BLOCKED_TODO_ID} status=open "
        "task_class=advancement_task action_kind=state_machine_canary_refactor "
        f"required_capabilities=network claimed_by={AGENT_ID} -->\n"
        f"- [ ] [P1] {CAPABILITY_FALLBACK_TEXT}\n"
        f"  <!-- loopx:todo todo_id={CAPABILITY_FALLBACK_TODO_ID} status=open "
        "task_class=advancement_task action_kind=state_machine_canary_refactor "
        f"required_capabilities=shell claimed_by={AGENT_ID} -->\n",
        encoding="utf-8",
    )
    write_registry(
        project=project,
        runtime=runtime,
        registry_path=registry_path,
        adapter_kind="side_agent_capability_fallback_fixture_v0",
    )
    return project, runtime, registry_path


def should_run(registry_path: Path, runtime: Path, project: Path) -> dict:
    return run_cli(
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--scan-path",
        str(project),
        registry_path=registry_path,
        runtime=runtime,
    )


def assert_initial_side_agent_lane(
    guard: dict,
    *,
    expected_todo_id: str,
) -> None:
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert guard["interaction_contract"]["mode"] == "bounded_delivery", guard
    assert guard["interaction_contract"]["user_channel"]["action_required"] is False, guard
    assert guard["interaction_contract"]["agent_channel"]["delivery_allowed"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard["agent_identity"]["role"] == "side-agent", guard
    assert guard["agent_identity"]["primary_agent"] == PRIMARY_AGENT_ID, guard
    next_action = guard["agent_lane_next_action"]
    assert next_action["todo_id"] == expected_todo_id, guard
    assert next_action["claimed_by"] == AGENT_ID, guard
    assert next_action["preserves_goal_next_action"] is True, guard
    assert guard["active_state_next_action"] == GOAL_NEXT_ACTION, guard
    assert guard["goal_route_hint"]["route_decision"] == "run_current_agent_lane", guard


def assert_scheduler_ack_round_trip(
    *,
    registry_path: Path,
    runtime: Path,
    project: Path,
    guard: dict,
) -> None:
    codex_app = guard["scheduler_hint"]["codex_app"]
    stateful = codex_app["stateful_backoff"]
    assert stateful["apply_needed"] is True, guard
    rrule = codex_app["recommended_rrule"]
    ack = run_cli(
        "quota",
        "scheduler-ack",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--applied-rrule",
        rrule,
        "--execute",
        "--scan-path",
        str(project),
        registry_path=registry_path,
        runtime=runtime,
    )
    assert ack["ok"] is True, ack
    assert ack["scheduler_state_mutated"] is True, ack
    assert ack["scheduler_ack_event"]["scheduler_state"]["last_applied_rrule"] == rrule, ack

    steady = should_run(registry_path, runtime, project)
    steady_app = steady["scheduler_hint"]["codex_app"]
    assert steady_app["stateful_backoff"]["apply_needed"] is False, steady
    assert steady_app["host_action"] == "none", steady
    assert "recommended_rrule" not in steady_app, steady


def assert_self_iteration_flow() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-self-iteration-") as tmp:
        project, runtime, registry_path = write_fixture(Path(tmp))

        first = should_run(registry_path, runtime, project)
        assert_initial_side_agent_lane(first, expected_todo_id=START_TODO_ID)

        completed = run_cli(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            START_TODO_ID,
            "--claimed-by",
            AGENT_ID,
            "--side-agent-self-merged",
            "--evidence",
            "fixture public validation passed",
            "--next-agent-todo",
            NEXT_TODO_TEXT,
            "--next-claimed-by",
            AGENT_ID,
            "--next-task-class",
            "advancement_task",
            "--next-action-kind",
            "state_machine_canary_refactor",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert completed["ok"] is True, completed
        assert completed["side_agent_self_merged"] is True, completed
        assert completed["status"] == "done", completed
        successor = completed["next_todos"][0]
        successor_id = successor["todo_id"]
        assert successor["claimed_by"] == AGENT_ID, completed
        assert successor["action_kind"] == "state_machine_canary_refactor", completed

        refresh = run_cli(
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--agent-lane",
            "product_capability",
            "--progress-scope",
            "agent_lane",
            "--classification",
            "side_agent_self_iteration_fixture",
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "outcome_progress",
            "--recommended-action",
            f"Continue {successor_id}: {NEXT_TODO_TEXT}",
            "--no-global-sync",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert refresh["ok"] is True, refresh
        assert refresh["appended"] is True, refresh
        assert refresh["progress_scope"] == "agent_lane", refresh
        assert refresh["active_state_next_action_update"] is None, refresh
        assert refresh["state"]["next_action"] == [f"- {GOAL_NEXT_ACTION}"], refresh

        second = should_run(registry_path, runtime, project)
        assert_initial_side_agent_lane(second, expected_todo_id=successor_id)
        assert second["agent_lane_next_action"]["title"] == NEXT_TODO_TEXT, second
        assert second["quota"]["spent_slots"] == 0, second

        assert_scheduler_ack_round_trip(
            registry_path=registry_path,
            runtime=runtime,
            project=project,
            guard=second,
        )

        spend = run_cli(
            "quota",
            "spend-slot",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert spend["ok"] is True, spend
        assert spend["appended"] is True, spend
        assert spend["quota_event"]["before"]["spent_slots"] == 0, spend
        assert spend["quota_event"]["after"]["spent_slots"] == 1, spend

        third = should_run(registry_path, runtime, project)
        assert_initial_side_agent_lane(third, expected_todo_id=successor_id)
        assert third["quota"]["spent_slots"] == 1, third
        assert third["active_state_next_action"] == GOAL_NEXT_ACTION, third


def assert_existing_handoff_successor_flow() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-existing-successor-") as tmp:
        project, runtime, registry_path = write_existing_successor_fixture(
            Path(tmp),
            successor_todo_id=EXISTING_SUCCESSOR_HANDOFF_TODO_ID,
            successor_claimed_by=PRIMARY_AGENT_ID,
        )

        first = should_run(registry_path, runtime, project)
        assert_initial_side_agent_lane(first, expected_todo_id=EXISTING_SUCCESSOR_START_TODO_ID)

        completed = run_cli(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            EXISTING_SUCCESSOR_START_TODO_ID,
            "--claimed-by",
            AGENT_ID,
            "--evidence",
            "fixture linked an existing public handoff successor",
            "--successor-todo-id",
            EXISTING_SUCCESSOR_HANDOFF_TODO_ID,
            registry_path=registry_path,
            runtime=runtime,
        )
        assert completed["ok"] is True, completed
        assert completed["status"] == "done", completed
        assert completed["side_agent_self_merged"] is False, completed
        assert completed["linked_handoff_successor_id"] == EXISTING_SUCCESSOR_HANDOFF_TODO_ID, completed
        assert completed["successor_todo_ids"] == [EXISTING_SUCCESSOR_HANDOFF_TODO_ID], completed
        assert completed["next_todos"] == [], completed

        successor_lookup = run_cli(
            "todo",
            "list",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            EXISTING_SUCCESSOR_HANDOFF_TODO_ID,
            registry_path=registry_path,
            runtime=runtime,
        )
        assert successor_lookup["matched"] is True, successor_lookup
        assert successor_lookup["todo"]["status"] == "open", successor_lookup
        assert successor_lookup["todo"]["claimed_by"] == PRIMARY_AGENT_ID, successor_lookup

        primary_guard = run_cli(
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            PRIMARY_AGENT_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert primary_guard["decision"] == "run", primary_guard
        assert primary_guard["effective_action"] == "normal_run", primary_guard
        assert primary_guard["agent_identity"]["role"] == "primary-agent", primary_guard
        primary_next_action = primary_guard["agent_lane_next_action"]
        assert primary_next_action["todo_id"] == EXISTING_SUCCESSOR_HANDOFF_TODO_ID, primary_guard
        assert primary_next_action["claimed_by"] == PRIMARY_AGENT_ID, primary_guard


def assert_same_agent_existing_successor_still_requires_self_merge_or_handoff() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-same-successor-") as tmp:
        _project, runtime, registry_path = write_existing_successor_fixture(
            Path(tmp),
            successor_todo_id=EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID,
            successor_claimed_by=AGENT_ID,
            successor_action_kind="state_machine_followup",
            handoff_agent=AGENT_ID,
        )

        returncode, rejected = run_cli_result(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            EXISTING_SUCCESSOR_START_TODO_ID,
            "--claimed-by",
            AGENT_ID,
            "--evidence",
            "fixture attempted same-agent successor link",
            "--successor-todo-id",
            EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID,
            registry_path=registry_path,
            runtime=runtime,
        )
        assert returncode != 0, rejected
        assert "handoff_agent='codex-product-capability'" in rejected["error"], rejected
        assert "--side-agent-self-merged" in rejected["error"], rejected


def assert_review_only_gate_can_continue_with_same_agent_successor() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-review-continuation-") as tmp:
        _project, runtime, registry_path = write_existing_successor_fixture(
            Path(tmp),
            successor_todo_id=EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID,
            successor_claimed_by=AGENT_ID,
            source_action_kind="pilot_readiness_review",
            source_blocks_agent=PRIMARY_AGENT_ID,
            successor_action_kind="pilot_followup",
            handoff_agent=AGENT_ID,
        )

        returncode, rejected = run_cli_result(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            EXISTING_SUCCESSOR_START_TODO_ID,
            "--claimed-by",
            AGENT_ID,
            "--evidence",
            "independent read-only readiness review passed",
            "--next-agent-todo",
            "Generate an unlinked same-agent continuation.",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert returncode != 0, rejected
        assert "--successor-todo-id" in rejected["error"], rejected

        completed = run_cli(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            EXISTING_SUCCESSOR_START_TODO_ID,
            "--claimed-by",
            AGENT_ID,
            "--evidence",
            "independent read-only readiness review passed",
            "--successor-todo-id",
            EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID,
            registry_path=registry_path,
            runtime=runtime,
        )
        assert completed["ok"] is True, completed
        assert completed["side_agent_self_merged"] is False, completed
        assert completed["linked_handoff_successor_id"] == EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID, (
            completed
        )

    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-review-write-scope-") as tmp:
        _project, runtime, registry_path = write_existing_successor_fixture(
            Path(tmp),
            successor_todo_id=EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID,
            successor_claimed_by=AGENT_ID,
            source_action_kind="pilot_readiness_review",
            source_blocks_agent=PRIMARY_AGENT_ID,
            source_required_write_scope="loopx/**",
            successor_action_kind="pilot_followup",
            handoff_agent=AGENT_ID,
        )
        returncode, rejected = run_cli_result(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            EXISTING_SUCCESSOR_START_TODO_ID,
            "--claimed-by",
            AGENT_ID,
            "--evidence",
            "review included repository delivery",
            "--successor-todo-id",
            EXISTING_SUCCESSOR_SAME_AGENT_TODO_ID,
            registry_path=registry_path,
            runtime=runtime,
        )
        assert returncode != 0, rejected
        assert "--side-agent-self-merged" in rejected["error"], rejected


def assert_capability_fallback_preserves_frontier_and_scheduler() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-capability-fallback-") as tmp:
        project, runtime, registry_path = write_capability_fallback_fixture(Path(tmp))

        guard = should_run(registry_path, runtime, project)
        assert guard["decision"] == "run", guard
        assert guard["normal_delivery_allowed"] is True, guard
        assert guard["active_state_next_action"] == (
            f"Run {CAPABILITY_BLOCKED_TODO_ID} before fallback work."
        ), guard

        capability = guard["capability_gate"]
        assert capability["action"] == "run", guard
        assert capability["runnable_count"] == 1, capability
        assert capability["runnable_candidates"][0]["todo_id"] == CAPABILITY_FALLBACK_TODO_ID, capability
        assert capability["blocked_candidates"][0]["todo_id"] == CAPABILITY_BLOCKED_TODO_ID, capability
        assert capability["blocked_missing"] == ["network"], capability

        lane = guard["agent_lane_next_action"]
        assert lane["todo_id"] == CAPABILITY_FALLBACK_TODO_ID, guard
        assert lane["source"] == "capability_gate.runnable_candidates", guard
        assert lane["selected_by"] == "current_agent_claimed_todo", guard
        assert lane["required_capabilities"] == ["shell"], guard
        assert lane["preserves_goal_next_action"] is True, guard
        assert guard["recommended_action"].endswith(CAPABILITY_FALLBACK_TEXT), guard

        frontier = guard["goal_frontier_projection"]
        assert frontier["remaining_advancement_frontier"] == {
            "current_agent_claimed_advancement_count": 2,
            "unclaimed_advancement_count": 0,
            "other_agent_claimed_advancement_count": 0,
        }, frontier
        assert frontier["replan_required"] is False, frontier

        scheduler = guard["scheduler_hint"]
        assert scheduler["action"] == "run_now", guard
        assert scheduler["cadence_class"] == "active_work", guard
        assert scheduler["codex_app"]["stateful_backoff"]["apply_needed"] is True, guard

        assert_scheduler_ack_round_trip(
            registry_path=registry_path,
            runtime=runtime,
            project=project,
            guard=guard,
        )


def main() -> int:
    assert_self_iteration_flow()
    assert_existing_handoff_successor_flow()
    assert_same_agent_existing_successor_still_requires_self_merge_or_handoff()
    assert_review_only_gate_can_continue_with_same_agent_successor()
    assert_capability_fallback_preserves_frontier_and_scheduler()
    print("side-agent-self-iteration-state-machine-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
