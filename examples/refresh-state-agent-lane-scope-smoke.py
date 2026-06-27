#!/usr/bin/env python3
"""Smoke-test agent-lane refreshes without stealing goal-level next action."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import loopx.state_refresh as state_refresh
from loopx.history import collect_history
from loopx.status import collect_status


GOAL_ID = "refresh-state-agent-lane-goal"
PRIMARY_ACTION = "Run the primary benchmark bootstrap hardening slice."
SIDE_ACTION = "Polish the hosted frontstage showcase for external developers."


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        "---\n"
        "status: primary_bootstrap_ready\n"
        "owner_mode: goal\n"
        'objective: "Keep primary and side-agent lanes distinct."\n'
        "updated_at: 2026-06-20T00:00:00+00:00\n"
        "---\n\n"
        "# Agent Lane Refresh Fixture\n\n"
        "## Agent Todo\n\n"
        f"- [ ] [P0] {PRIMARY_ACTION}\n"
        "  <!-- loopx:todo todo_id=todo_primary status=open "
        "task_class=advancement_task claimed_by=codex-main-control -->\n"
        f"- [ ] [P1] {SIDE_ACTION}\n"
        "  <!-- loopx:todo todo_id=todo_side status=open "
        "task_class=advancement_task claimed_by=codex-side-bypass -->\n\n"
        "## Next Action\n\n"
        f"- {PRIMARY_ACTION}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-06-20T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "refresh-state-agent-lane-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                        "coordination": {
                            "primary_agent": "codex-main-control",
                            "registered_agents": ["codex-main-control", "codex-side-bypass"],
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime, project


def main() -> None:
    original_now_local = state_refresh.now_local
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-agent-lane-refresh-") as raw_tmp:
            registry_path, runtime, project = write_fixture(Path(raw_tmp))

            state_refresh.now_local = lambda: "2026-06-20T00:00:00+00:00"
            state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="terminal_bench_primary_ready",
                recommended_action=PRIMARY_ACTION,
                delivery_batch_scale="multi_surface",
                delivery_outcome="outcome_progress",
                dry_run=False,
                sync_global=False,
            )

            state_refresh.now_local = lambda: "2026-06-20T00:01:00+00:00"
            side_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="frontstage_side_lane_next",
                recommended_action=SIDE_ACTION,
                delivery_batch_scale="single_surface",
                delivery_outcome="outcome_progress",
                agent_id="codex-side-bypass",
                agent_lane="productization_frontstage",
                dry_run=False,
                sync_global=False,
            )
            assert side_payload["progress_scope"] == "agent_lane", side_payload
            assert side_payload["agent_id"] == "codex-side-bypass", side_payload

            unscoped_side_action = f"Continue todo_side: {SIDE_ACTION}"
            blocked_next_action_error = None
            try:
                state_refresh.refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=str(runtime),
                    goal_id=GOAL_ID,
                    project=project,
                    state_file=None,
                    classification="frontstage_side_lane_next_action_write",
                    recommended_action=unscoped_side_action,
                    next_action=unscoped_side_action,
                    delivery_batch_scale="single_surface",
                    delivery_outcome="outcome_progress",
                    dry_run=True,
                    sync_global=False,
                )
            except ValueError as exc:
                blocked_next_action_error = str(exc)
            assert blocked_next_action_error and (
                "inferred non-primary agent-lane scope" in blocked_next_action_error
            )

            state_refresh.now_local = lambda: "2026-06-20T00:02:00+00:00"
            unscoped_side_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="frontstage_side_lane_next_unscoped",
                recommended_action=unscoped_side_action,
                delivery_batch_scale="single_surface",
                delivery_outcome="outcome_progress",
                dry_run=False,
                sync_global=False,
            )
            assert unscoped_side_payload["progress_scope"] == "agent_lane", unscoped_side_payload
            assert unscoped_side_payload["agent_id"] == "codex-side-bypass", unscoped_side_payload
            assert unscoped_side_payload["agent_lane_scope_inference"]["todo_id"] == "todo_side"

            primary_review_handoff = (
                "Primary review todo_primary should inspect the refactor before deeper splits; "
                "codex-side-bypass should switch to another eligible product todo."
            )
            state_refresh.now_local = lambda: "2026-06-20T00:03:00+00:00"
            handoff_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="side_lane_review_handoff",
                recommended_action=primary_review_handoff,
                delivery_batch_scale="single_surface",
                delivery_outcome="outcome_progress",
                dry_run=False,
                sync_global=False,
            )
            assert handoff_payload["progress_scope"] == "agent_lane", handoff_payload
            assert handoff_payload["agent_id"] == "codex-side-bypass", handoff_payload
            assert handoff_payload["agent_lane_scope_inference"]["source"] == (
                "referenced_registered_non_primary_agent"
            )

            history = collect_history(
                registry_path=registry_path,
                runtime_root=runtime,
                goal_id=GOAL_ID,
                limit=5,
            )
            goal = history["goals"][0]
            assert goal["latest_runs"][0]["classification"] == "side_lane_review_handoff", goal
            assert goal["latest_status_run"]["classification"] == "terminal_bench_primary_ready", goal

            status = collect_status(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                scan_roots=[project],
                limit=5,
            )
            items = status["attention_queue"]["items"]
            item = next(item for item in items if item["goal_id"] == GOAL_ID)
            assert item["status"] == "terminal_bench_primary_ready", item
            assert item["recommended_action"] == PRIMARY_ACTION, item
            lane = item["agent_lane_recommendation"]
            assert lane["progress_scope"] == "agent_lane", lane
            assert lane["agent_id"] == "codex-side-bypass", lane
            assert lane["agent_lane"] == "codex-side-bypass", lane
            assert lane["recommended_action"] == primary_review_handoff, lane
            assert item["project_asset"]["agent_lane_recommendation"] == lane, item
    finally:
        state_refresh.now_local = original_now_local

    print("refresh-state-agent-lane-scope-smoke ok")


if __name__ == "__main__":
    main()
