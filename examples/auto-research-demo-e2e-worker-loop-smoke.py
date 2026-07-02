#!/usr/bin/env python3
"""Smoke-test the one-command demo-e2e path with a real LoopX worker loop."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
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
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.legacy_core import render_auto_research_markdown

    bootstrap_source = (
        REPO_ROOT / "loopx/capabilities/auto_research/legacy_core.py"
    ).read_text(encoding="utf-8")
    assert "--format json auto-research worker-turn" not in bootstrap_source
    assert "--format json auto-research worker-loop" not in bootstrap_source
    assert "auto-research worker-turn --format markdown" in bootstrap_source
    assert "Do not call bare `loopx`" in bootstrap_source
    assert "Use loopx-project" not in bootstrap_source
    assert "read that local JSON profile" not in bootstrap_source
    assert "Do not print, cat, or sed `$LOOPX_ROLE_PROFILE_PATH`" in bootstrap_source
    assert "Do not run `--help`" in bootstrap_source
    assert "worker-turn preview/execute as the human-facing polling command" in bootstrap_source
    assert "rewrites accidental visible `--format json` to markdown" in bootstrap_source
    assert "$LOOPX_PANE_LOOPX_JSON ... --format json > .local/<role>/<name>.public.json" in bootstrap_source

    worker_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_turn_v0",
            "mode": "dry_run",
            "goal_id": GOAL_ID,
            "agent_id": AGENT_ID,
            "selected_todo_id": "todo_worker_smoke",
            "selected_action": "run_dev_eval",
            "would_execute": "run_dev_eval",
            "executed": False,
            "completion": {"requested": False, "executed": False},
            "frontier": {
                "quota": {
                    "should_run": True,
                    "state": "eligible",
                    "user_action_required": False,
                },
                "frontier": {
                    "selected": {
                        "todo_id": "todo_worker_smoke",
                        "allowed_action": "run_dev_eval",
                        "title": "Run dev evidence.",
                    }
                },
            },
        }
    )
    assert "# LoopX Auto Research Worker Turn" in worker_markdown
    assert "- selected_action: `run_dev_eval`" in worker_markdown
    assert '"schema_version"' not in worker_markdown

    blocked_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_turn_v0",
            "mode": "blocked",
            "goal_id": GOAL_ID,
            "agent_id": "codex-value-explorer",
            "selected_todo_id": "todo_holdout_smoke",
            "selected_action": "run_holdout_eval",
            "executed": False,
            "blocker": "waiting_for_dev_evidence",
            "blocker_detail": "no dev-supported auto-research hypothesis is ready for holdout validation",
            "completion": {"requested": True, "executed": False},
            "frontier": {
                "quota": {
                    "should_run": True,
                    "state": "eligible",
                    "user_action_required": False,
                },
                "frontier": {
                    "selected": {
                        "todo_id": "todo_holdout_smoke",
                        "allowed_action": "run_holdout_eval",
                        "title": "Run held-out validation.",
                    }
                },
            },
        }
    )
    assert "- mode: `blocked`" in blocked_markdown
    assert "- blocker: `waiting_for_dev_evidence`" in blocked_markdown
    assert "Traceback" not in blocked_markdown

    loop_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_loop_v0",
            "mode": "execute",
            "goal_id": GOAL_ID,
            "round_count": 1,
            "max_rounds": 2,
            "stop_reason": "no_runnable_frontier",
            "turn_count": 1,
            "executed_turn_count": 1,
            "completed_turn_count": 1,
            "selected_actions": ["run_dev_eval"],
            "turns": [
                {
                    "round": 1,
                    "agent_id": AGENT_ID,
                    "mode": "execute",
                    "selected_action": "run_dev_eval",
                    "executed": True,
                    "completion_status": "done",
                    "dev_metric": 4.0,
                    "holdout_metric": None,
                }
            ],
        }
    )
    assert "# LoopX Auto Research Worker Loop" in loop_markdown
    assert "agent `codex-side-bypass`" in loop_markdown
    assert '"turns"' not in loop_markdown

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        workspace = temp / "workspace"
        workspace.mkdir()
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        fake_codex = fake_bin / "fake-codex-tui"
        codex_invocations = temp / "codex-invocations.txt"
        fake_codex.write_text(
            "#!/usr/bin/env sh\n"
            f"{{ printf 'PWD=%s\\n' \"$PWD\"; printf 'ARGS=%s\\n' \"$*\"; }} >> {shlex.quote(str(codex_invocations))}\n"
            "printf 'Fake Codex TUI ready\\n'\n"
            "sleep 8\n",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
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
        assert "--run-worker-loop" in tonight["one_command"], tonight
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
        if shutil.which("tmux"):
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
                        "--codex-bin",
                        "fake-codex-tui",
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
                assert visible_payload["execution_kind"] == "visible_worker_launch", visible_payload
                assert visible_payload["result_source"] == "visible_worker_launcher", visible_payload
                assert "worker_loop" not in visible_payload, visible_payload
                assert "tonight_experience" not in visible_payload, visible_payload
                visible_claim = visible_payload["claim_summary"]
                assert visible_claim["status"] == "visible_worker_queue_started", visible_claim
                assert visible_claim["dev_metric"] is None, visible_claim
                assert visible_claim["holdout_metric"] is None, visible_claim
                launch = visible_payload["visible_launch"]["launch_result"]
                assert launch["started_lane_count"] == 4, visible_payload
                assert "frontier" not in launch["started_lanes"], visible_payload
                assert launch["attach_requested"] is False, visible_payload
                assert launch["workspace_mode"] == "current_directory", visible_payload
                workspace_route = visible_payload["visible_control_plane"]["workspace_route"]
                assert workspace_route["side_lane_worktree_count"] == 0, workspace_route
                assert workspace_route["primary_workspace"] == "visible_codex_tui_workspace", workspace_route
                assert (
                    workspace_route["trust_prompt_avoidance"]
                    == "do_not_start_codex_tui_in_demo_local_git_worktrees"
                ), workspace_route
                acceptance = launch["visible_acceptance"]
                assert acceptance["accepted"] is True, visible_payload
                assert all(not item["blocked_before_bootstrap"] for item in acceptance["pane_checks"]), acceptance
                assert all(item["interactive_codex_tui_script"] for item in acceptance["pane_checks"]), acceptance
                skill_items = launch["worker_skill_materialization"]
                assert skill_items, visible_payload
                assert {item["source_resolution"] for item in skill_items} == {"package_root"}, skill_items
                assert all(item["materialized"] is True for item in skill_items), skill_items
                for _attempt in range(40):
                    if codex_invocations.exists() and codex_invocations.read_text(
                        encoding="utf-8"
                    ).count("PWD=") >= 4:
                        break
                    time.sleep(0.25)
                invocation_text = codex_invocations.read_text(encoding="utf-8")
                assert invocation_text.count("Fake Codex TUI") == 0, invocation_text
                assert invocation_text.count("PWD=") == 4, invocation_text
                assert invocation_text.count(f"PWD={workspace.resolve()}") == 4, invocation_text
                assert invocation_text.count(f'-C {workspace.resolve()}') == 4, invocation_text
                assert "visible-lane-worktrees" not in invocation_text, invocation_text
                assert "visible-control-plane" not in invocation_text, invocation_text
                for lane in launch["started_lanes"]:
                    capture = subprocess.run(
                        ["tmux", "capture-pane", "-pt", f"{session_name}:{lane}", "-S", "-300"],
                        check=False,
                        capture_output=True,
                        text=True,
                    ).stdout
                    assert "state_projection_gap" not in capture, (lane, capture)
                    assert "stopped_before_frontier" not in capture, (lane, capture)
                    assert "quota_wait_timeout" not in capture, (lane, capture)
                    assert "frontier_wait_timeout" not in capture, (lane, capture)
                    assert '"schema_version"' not in capture, (lane, capture)
                    assert "LOOPX_ROLE_PROFILE_JSON" not in capture, (lane, capture)
                    assert "/" + "private/" not in capture, (lane, capture)
                    assert "/" + "tmp/" not in capture, (lane, capture)
                    assert "role_profile_path=" not in capture, (lane, capture)
                    assert "[Codex bootstrap prompt]" not in capture, (lane, capture)
                    assert "codex_output=streaming_below" not in capture, (lane, capture)
                    assert "codex_stream_filter=public_safe" not in capture, (lane, capture)
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
