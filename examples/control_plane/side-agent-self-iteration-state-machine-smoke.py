#!/usr/bin/env python3
"""Canary a side-agent self-iteration state machine end to end."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
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


def run_cli(
    *args: str,
    registry_path: Path,
    runtime: Path,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    if not result.stdout.strip():
        raise AssertionError(f"empty CLI output for {command!r}: {result.stderr}")
    payload = json.loads(result.stdout)
    payload["_returncode"] = result.returncode
    return payload


def write_registry(
    *,
    project: Path,
    runtime: Path,
    registry_path: Path,
    adapter_kind: str,
) -> None:
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "side-agent-self-iteration-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {
                            "kind": adapter_kind,
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                        "coordination": {
                            "registered_agents": [PRIMARY_AGENT_ID, AGENT_ID],
                            "primary_agent": PRIMARY_AGENT_ID,
                        },
                        "workspace_guard_policy": {
                            "side_agent_independent_worktree_required": False,
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
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
    assert_capability_fallback_preserves_frontier_and_scheduler()
    print("side-agent-self-iteration-state-machine-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
