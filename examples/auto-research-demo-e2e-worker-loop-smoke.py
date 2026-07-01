#!/usr/bin/env python3
"""Smoke-test the one-command demo-e2e path with a real LoopX worker loop."""

from __future__ import annotations

import json
import os
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
                "--run-worker-loop",
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
        assert payload["execution_kind"] == "loopx_worker_loop_plus_minimal_kernel", payload
        assert payload["result_source"] == "loopx_worker_loop_with_protected_eval", payload
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
        claim = payload["claim_summary"]
        assert claim["status"] == "loopx_worker_loop_positive", claim
        assert claim["can_claim"] == ["one_command_loopx_worker_loop_positive_result"], claim
        assert "visible_codex_tui_authored_result" in claim["cannot_claim"], claim
        assert_public_safe(payload)
    print("auto-research-demo-e2e-worker-loop-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
