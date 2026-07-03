#!/usr/bin/env python3
"""Smoke-test explicit refresh-state goal/agent-lane scoping."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import loopx.state_refresh as state_refresh
from loopx.history import collect_history
from loopx.status import collect_status


GOAL_ID = "refresh-state-agent-lane-goal"
PRIMARY_ACTION = "Run the primary benchmark bootstrap hardening slice."
PRIMARY_AGENT_LANE_ACTION = "Continue the primary adapter lifecycle rollout repair."
SIDE_ACTION = "Polish the hosted frontstage showcase for external developers."
SIDE_HANDOFF_ACTION = (
    "Primary should inspect todo_primary while side lane switches to the next product todo."
)
LOCAL_CONTROL_ACTION = (
    "Review standing authorization for todo_local_control before changing the runtime lane."
)
AUTO_RESEARCH_ACTION = (
    "[P0-auto-research] Use rollout-backed research_evidence_graph_v0 to generate "
    "live promotion and retirement candidates."
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
        f"- [ ] {AUTO_RESEARCH_ACTION}\n"
        "  <!-- loopx:todo todo_id=todo_auto_research status=open "
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
                            "registered_agents": [
                                "codex-main-control",
                                "codex-side-bypass",
                            ],
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


def expect_value_error(message: str, callback) -> None:
    error = None
    try:
        callback()
    except ValueError as exc:
        error = str(exc)
    assert error and message in error, error


def main() -> None:
    original_now_local = state_refresh.now_local
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-agent-lane-refresh-") as raw_tmp:
            registry_path, runtime, project = write_fixture(Path(raw_tmp))
            state_path = project / f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"

            state_refresh.now_local = lambda: "2026-06-20T00:00:00+00:00"
            primary_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="terminal_bench_primary_ready",
                recommended_action=PRIMARY_ACTION,
                delivery_batch_scale="multi_surface",
                delivery_outcome="outcome_progress",
                agent_id="codex-main-control",
                progress_scope="goal",
                dry_run=False,
                sync_global=False,
            )
            assert primary_payload["progress_scope"] == "goal", primary_payload
            assert primary_payload["agent_id"] == "codex-main-control", primary_payload
            assert primary_payload.get("agent_lane") is None, primary_payload

            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace(
                    "updated_at: 2026-06-20T00:00:00+00:00",
                    "updated_at: 2026-06-20T00:00:30+00:00",
                    1,
                ),
                encoding="utf-8",
            )

            expect_value_error(
                "multi-agent refresh-state requires --agent-id",
                lambda: state_refresh.refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=str(runtime),
                    goal_id=GOAL_ID,
                    project=project,
                    state_file=None,
                    classification="frontstage_side_lane_unscoped",
                    recommended_action=f"Continue todo_side: {SIDE_ACTION}",
                    delivery_batch_scale="single_surface",
                    delivery_outcome="outcome_progress",
                    dry_run=True,
                    sync_global=False,
                ),
            )

            expect_value_error(
                "agent-lane refresh-state cannot update the durable active-state Next Action",
                lambda: state_refresh.refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=str(runtime),
                    goal_id=GOAL_ID,
                    project=project,
                    state_file=None,
                    classification="frontstage_side_lane_next_action_write",
                    recommended_action=SIDE_ACTION,
                    next_action=SIDE_ACTION,
                    delivery_batch_scale="single_surface",
                    delivery_outcome="outcome_progress",
                    agent_id="codex-side-bypass",
                    dry_run=True,
                    sync_global=False,
                ),
            )

            expect_value_error(
                "goal-scope refresh-state requires the primary agent",
                lambda: state_refresh.refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=str(runtime),
                    goal_id=GOAL_ID,
                    project=project,
                    state_file=None,
                    classification="frontstage_side_goal_scope",
                    recommended_action=SIDE_ACTION,
                    delivery_batch_scale="single_surface",
                    delivery_outcome="outcome_progress",
                    agent_id="codex-side-bypass",
                    progress_scope="goal",
                    dry_run=True,
                    sync_global=False,
                ),
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
            assert side_payload["agent_lane"] == "productization_frontstage", side_payload
            assert "agent_lane_scope_inference" not in side_payload, side_payload

            state_refresh.now_local = lambda: "2026-06-20T00:03:00+00:00"
            handoff_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="side_lane_review_handoff",
                recommended_action=SIDE_HANDOFF_ACTION,
                delivery_batch_scale="single_surface",
                delivery_outcome="outcome_progress",
                agent_id="codex-side-bypass",
                dry_run=False,
                sync_global=False,
            )
            assert handoff_payload["progress_scope"] == "agent_lane", handoff_payload
            assert handoff_payload["agent_id"] == "codex-side-bypass", handoff_payload
            assert handoff_payload["agent_lane"] == "codex-side-bypass", handoff_payload
            assert "agent_lane_scope_inference" not in handoff_payload, handoff_payload

            history = collect_history(
                registry_path=registry_path,
                runtime_root=runtime,
                goal_id=GOAL_ID,
                limit=5,
            )
            goal = history["goals"][0]
            latest_run = goal["latest_runs"][0]
            assert latest_run["classification"] == "side_lane_review_handoff", goal
            assert latest_run["progress_scope"] == "agent_lane", latest_run
            assert latest_run["agent_id"] == "codex-side-bypass", latest_run
            assert latest_run["agent_lane"] == "codex-side-bypass", latest_run
            assert latest_run["delivery_batch_scale"] == "single_surface", latest_run
            assert latest_run["delivery_outcome"] == "outcome_progress", latest_run
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
            assert item["latest_run_recommended_action"] == PRIMARY_ACTION, item
            assert item["latest_run_recommended_action_source"] == "latest_status_run", item
            assert "stale_latest_run_warning" not in item, item
            assert "stale_latest_run_warning" not in item["project_asset"], item
            lane = item["agent_lane_recommendation"]
            assert lane["progress_scope"] == "agent_lane", lane
            assert lane["agent_id"] == "codex-side-bypass", lane
            assert lane["agent_lane"] == "codex-side-bypass", lane
            assert lane["recommended_action"] == SIDE_HANDOFF_ACTION, lane
            assert item["project_asset"]["agent_lane_recommendation"] == lane, item

            state_refresh.now_local = lambda: "2026-06-20T00:03:30+00:00"
            local_control_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="side_lane_local_control_reference",
                recommended_action=LOCAL_CONTROL_ACTION,
                delivery_batch_scale="single_surface",
                delivery_outcome="outcome_progress",
                agent_id="codex-side-bypass",
                dry_run=False,
                sync_global=False,
            )
            assert (
                local_control_payload["recommended_action"] == LOCAL_CONTROL_ACTION
            ), local_control_payload

            expect_value_error(
                "recommended_action contains a secret-looking value",
                lambda: state_refresh.refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=str(runtime),
                    goal_id=GOAL_ID,
                    project=project,
                    state_file=None,
                    classification="side_lane_auth_header_blocked",
                    recommended_action=(
                        "Do not store "
                        + "Author"
                        + "ization: "
                        + "Bear"
                        + "er fake-token in control-plane action text."
                    ),
                    delivery_batch_scale="single_surface",
                    delivery_outcome="outcome_progress",
                    agent_id="codex-side-bypass",
                    dry_run=True,
                    sync_global=False,
                ),
            )

            expect_value_error(
                "agent-lane refresh-state cannot update the durable active-state Next Action",
                lambda: state_refresh.refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=str(runtime),
                    goal_id=GOAL_ID,
                    project=project,
                    state_file=None,
                    classification="adapter_lifecycle_primary_default_lane_next",
                    recommended_action=PRIMARY_AGENT_LANE_ACTION,
                    next_action=PRIMARY_AGENT_LANE_ACTION,
                    delivery_batch_scale="single_surface",
                    delivery_outcome="outcome_progress",
                    agent_id="codex-main-control",
                    dry_run=True,
                    sync_global=False,
                ),
            )

            state_refresh.now_local = lambda: "2026-06-20T00:04:00+00:00"
            primary_next_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="adapter_lifecycle_primary_goal_next",
                recommended_action=PRIMARY_AGENT_LANE_ACTION,
                next_action=PRIMARY_AGENT_LANE_ACTION,
                delivery_batch_scale="single_surface",
                delivery_outcome="outcome_progress",
                agent_id="codex-main-control",
                progress_scope="goal",
                dry_run=False,
                sync_global=False,
            )
            assert primary_next_payload["progress_scope"] == "goal", primary_next_payload
            assert primary_next_payload["agent_id"] == "codex-main-control", primary_next_payload
            assert primary_next_payload.get("agent_lane") is None, primary_next_payload
            assert primary_next_payload["active_state_next_action_update"]["updated"] is True

            primary_goal_status = collect_status(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                scan_roots=[project],
                limit=5,
            )
            primary_goal_item = next(
                item
                for item in primary_goal_status["attention_queue"]["items"]
                if item["goal_id"] == GOAL_ID
            )
            assert primary_goal_item["status"] == "adapter_lifecycle_primary_goal_next"
            assert primary_goal_item["recommended_action"] == PRIMARY_AGENT_LANE_ACTION
            assert primary_goal_item["active_state_next_action"] == PRIMARY_AGENT_LANE_ACTION
            assert (
                primary_goal_item["latest_run_recommended_action"]
                == PRIMARY_AGENT_LANE_ACTION
            ), primary_goal_item
            assert (
                primary_goal_item["latest_run_recommended_action_source"]
                == "latest_status_run"
            ), primary_goal_item
            assert "next_action_projection_warning" not in primary_goal_item, primary_goal_item
    finally:
        state_refresh.now_local = original_now_local

    print("refresh-state-agent-lane-scope-smoke ok")


if __name__ == "__main__":
    main()
