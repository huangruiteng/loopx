#!/usr/bin/env python3
"""Smoke-test the explicit visible auto-research worker-turn hook path."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e  # noqa: E402
from loopx.capabilities.auto_research.demo_supervisor import (  # noqa: E402
    build_auto_research_demo_supervisor_plan,
    build_visible_worker_turn_command,
)
from loopx.capabilities.auto_research.user_contract import (  # noqa: E402
    build_auto_research_preset_context,
)


GOAL_ID = "loopx-auto-research-visible-worker-hook-smoke"
AGENT_ID = "auto-research-operator"
QUESTION = "如何提升 KNN 精确近邻检索速度？"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
        "raw transcript",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def assert_worker_turn_command_shape() -> None:
    command = build_visible_worker_turn_command(objective=QUESTION)
    assert '"$LOOPX_PANE_LOOPX" --format json auto-research worker-turn' in command
    assert '--goal-id "$LOOPX_GOAL_ID"' in command
    assert '--agent-id "$LOOPX_AGENT_ID"' in command
    assert '--lane-count "${LOOPX_VISIBLE_LANE_COUNT:-1}"' in command
    assert "--visible-lanes-accepted" in command
    assert "--complete-selected-todo" in command
    assert "--execute" in command
    assert_public_safe(command)


def assert_supervisor_can_configure_worker_turn() -> None:
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID,
        open_question=QUESTION,
        preset_context=build_auto_research_preset_context("knn-demo"),
        output_language="zh",
        configure_visible_worker_turn=True,
    )
    assert supervisor["auto_research"]["visible_worker_turn_configured"] is True
    assert supervisor["auto_research"]["worker_turn_owner"] == "generic_multi_agent_kernel"
    assert supervisor["runner_contract"]["decentralized_a2a_driver"]["broadcaster"][
        "runs_worker_turn"
    ] is False
    for lane in supervisor["lanes"]:
        assert lane["pane_local_a2a"]["worker_turn_configured"] is True, lane
        assert lane["pane_local_a2a"]["worker_loop_configured"] is False, lane
        assert lane["pane_local_a2a"]["status_check_only"] is True, lane
        assert lane["pane_local_a2a"]["counts_as_research_round"] is False, lane
        assert "LOOPX_PANE_WORKER_TURN" in lane["visible_launch_command"], lane
        assert "auto-research worker-turn" in lane["visible_launch_command"], lane
        assert "--visible-lanes-accepted" in lane["visible_launch_command"], lane
        assert "--complete-selected-todo" in lane["visible_launch_command"], lane
        profile = lane["role_profile"]
        assert profile["visible_worker_turn_configured"] is True, profile
    assert_public_safe(supervisor)


def assert_demo_e2e_exposes_validation_path() -> None:
    captured: dict[str, object] = {}

    def fake_visible_launcher(
        supervisor: dict[str, object],
        _registry_path: Path,
        _runtime_root: str | None,
        _demo_root: Path,
    ) -> dict[str, object]:
        captured["supervisor"] = supervisor
        return {
            "mode": "execute",
            "launch_result": {
                "session_name": "loopx-ar-visible-worker-hook-smoke",
                "started_lanes": [
                    str(lane.get("lane_id") or "")
                    for lane in supervisor.get("lanes", [])
                    if isinstance(lane, dict)
                ],
                "visible_acceptance": {"accepted": True},
            },
            "boundary": {
                "starts_visible_processes": False,
                "writes_loopx_state": False,
                "public_safe_redaction": True,
            },
        }

    with tempfile.TemporaryDirectory(prefix="loopx-ar-visible-worker-hook.") as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        payload = run_auto_research_demo_e2e(
            agent_id=AGENT_ID,
            goal_id=GOAL_ID,
            tracking_goal_id=None,
            preset_id="knn-demo",
            objective=QUESTION,
            output_dir="auto_research_lightweight_kernel",
            execute=True,
            run_worker_loop=False,
            worker_loop_rounds=1,
            configure_visible_worker_turn=True,
            launch_visible=True,
            keep_workspace=False,
            registry_path=registry,
            runtime_root_arg=str(runtime_root),
            session_name="loopx-ar-visible-worker-hook-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
            output_language="zh",
            live_evidence_path=None,
            append_evidence=lambda _path: {"ok": True, "appended_count": 0},
            visible_launcher=fake_visible_launcher,
            visible_wake=None,
            visible_live_evidence_wait_seconds=0.0,
        )
    validation = payload["visible_worker_turn_validation"]
    assert validation["configured"] is True, validation
    assert validation["counts_as_research_evidence_without_role_output"] is False, validation
    assert validation["manual_research_required_is_blocker_not_progress"] is True, validation
    assert payload["visible_worker_proof"]["visible_lanes_accepted"] is True, payload
    assert payload["visible_readiness"]["ready"] is False, payload["visible_readiness"]
    assert "lane_authored_evidence_loaded" in payload["visible_readiness"]["missing_requirements"]
    captured_supervisor = captured["supervisor"]
    for lane in captured_supervisor["lanes"]:
        assert lane["pane_local_a2a"]["worker_turn_configured"] is True, lane
    assert_public_safe(payload)


def main() -> None:
    assert_worker_turn_command_shape()
    assert_supervisor_can_configure_worker_turn()
    assert_demo_e2e_exposes_validation_path()
    print("auto-research-visible-worker-hook-smoke ok")


if __name__ == "__main__":
    main()
