#!/usr/bin/env python3
"""Smoke-test the one-command demo-e2e path with a real LoopX worker loop."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ID = "codex-side-bypass"
GOAL_ID = "loopx-auto-research-demo-worker-loop-smoke"


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
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    bootstrap_source = (
        REPO_ROOT / "loopx/capabilities/auto_research/legacy_core.py"
    ).read_text(encoding="utf-8")
    assert "--format json auto-research worker-turn" not in bootstrap_source
    assert "--format json auto-research worker-loop" not in bootstrap_source
    assert "auto-research worker-turn --format markdown" in bootstrap_source
    assert "Do not call bare `loopx`" in bootstrap_source

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        workspace = temp / "workspace"
        workspace.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--agent-id",
                AGENT_ID,
                "--demo-run-id",
                "worker-loop-smoke",
                "--execute",
                "--headless",
            ],
            cwd=workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"demo-e2e worker-loop failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["goal_id"] == GOAL_ID, payload
        assert payload["execution_kind"] == "loopx_worker_loop", payload
        assert payload["result_source"] == "loopx_worker_loop_public_evidence", payload
        assert "protected_eval_result" not in payload, payload
        assert "research_loop" not in payload, payload
        assert "multiround_gain_acceptance" not in payload, payload
        assert payload["route_contract"]["goal_surface_mode"] == "fresh_demo_goal", payload
        assert payload["supervisor"]["lane_count"] == 4, payload
        worker_loop = payload["worker_loop"]
        assert worker_loop["schema_version"] == "auto_research_worker_loop_v0", payload
        assert worker_loop["mode"] == "execute", payload
        assert worker_loop["executed_turn_count"] == 4, payload
        assert worker_loop["completed_turn_count"] == 4, payload
        assert worker_loop["selected_actions"] == [
            "write_research_contract",
            "propose_hypothesis",
            "run_dev_eval",
            "run_holdout_eval",
        ], payload
        assert worker_loop["stop_reason"] == "no_runnable_frontier", payload
        tonight = payload["tonight_experience"]
        assert tonight["ready"] is True, tonight
        assert tonight["positive_result"] is True, tonight
        assert tonight["coordination_pattern"] == "decentralized_state_a2a", tonight
        assert tonight["workflow_model"] == "state_projected_frontier_not_dynamic_workflow", tonight
        assert tonight["leader_agent_required"] is False, tonight
        assert tonight["dev_metric"] == 4.0, tonight
        assert tonight["holdout_metric"] == 4.5, tonight
        assert "--run-worker-loop" not in tonight["one_command"], tonight
        assert "--headless" not in tonight["one_command"], tonight
        assert "--headless" in payload["commands"]["headless_worker_loop"], payload
        assert "--no-attach" in payload["commands"]["start_visible_lanes_without_attach"], payload
        claim = payload["claim_summary"]
        assert claim["status"] == "loopx_worker_loop_positive", claim
        assert claim["can_claim"] == ["one_command_loopx_worker_loop_positive_result"], claim
        assert "visible_codex_tui_authored_result" in claim["cannot_claim"], claim
        removed_replay_source = "deterministic_" + "protected_eval_kernel"
        assert removed_replay_source not in json.dumps(payload, sort_keys=True), payload
        assert_public_safe(payload)
        if shutil.which("tmux") and shutil.which("true"):
            session_name = "loopx-auto-research-worker-skill-smoke"
            try:
                visible = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "loopx.cli",
                        "--registry",
                        str(registry),
                        "--runtime-root",
                        str(runtime_root),
                        "--format",
                        "json",
                        "auto-research",
                        "demo-e2e",
                        "--agent-id",
                        AGENT_ID,
                        "--demo-run-id",
                        "worker-skill-visible-smoke",
                        "--execute",
                        "--no-attach",
                        "--replace-existing",
                        "--session-name",
                        session_name,
                        "--workspace",
                        str(workspace),
                        "--create-workspace",
                        "--codex-bin",
                        "true",
                    ],
                    cwd=workspace,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if visible.returncode != 0:
                    raise AssertionError(
                        f"visible demo-e2e failed rc={visible.returncode}\nstdout={visible.stdout}\nstderr={visible.stderr}"
                    )
                visible_payload = json.loads(visible.stdout)
                launch = visible_payload["visible_launch"]["launch_result"]
                assert launch["started_lane_count"] == 4, visible_payload
                assert launch["attach_requested"] is False, visible_payload
                acceptance = launch["visible_acceptance"]
                assert acceptance["accepted"] is True, visible_payload
                assert all(not item["blocked_before_bootstrap"] for item in acceptance["pane_checks"]), acceptance
                skill_items = launch["worker_skill_materialization"]
                assert skill_items, visible_payload
                assert {item["source_resolution"] for item in skill_items} == {"package_root"}, skill_items
                assert all(item["materialized"] is True for item in skill_items), skill_items
                for lane in launch["started_lanes"]:
                    capture = subprocess.run(
                        ["tmux", "capture-pane", "-pt", f"{session_name}:{lane}", "-S", "-300"],
                        check=False,
                        capture_output=True,
                        text=True,
                    ).stdout
                    assert "continuing_to_visible_bootstrap" in capture, (lane, capture)
                    assert "state_projection_gap" not in capture, (lane, capture)
                    assert "stopped_before_frontier" not in capture, (lane, capture)
                    assert "quota_wait_timeout" not in capture, (lane, capture)
                    assert "frontier_wait_timeout" not in capture, (lane, capture)
                    assert '"schema_version"' not in capture, (lane, capture)
                    assert "role_profile_path=" not in capture, (lane, capture)
                    assert "[Codex bootstrap prompt]" not in capture, (lane, capture)
                    assert "codex_output=streaming_below" in capture, (lane, capture)
                    assert f"goal={visible_payload['goal_id']}" in capture, (lane, capture)
                assert_public_safe(visible_payload)
            finally:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
    print("auto-research-demo-e2e-worker-loop-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
