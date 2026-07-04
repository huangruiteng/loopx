#!/usr/bin/env python3
"""Smoke-test a minimal role-compatible auto-research worker loop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.demo_e2e import _seed_visible_demo_control_plane  # noqa: E402
from loopx.capabilities.auto_research.demo_supervisor import (  # noqa: E402
    build_auto_research_demo_supervisor_plan,
)


GOAL_ID = "loopx-auto-research-demo"
AGENT_IDS = [
    "codex-product-capability",
    "codex-side-bypass",
    "codex-main-control",
    "codex-value-explorer",
]
LANES = [
    "codex-product-capability:research-curator:research_curator",
    "codex-side-bypass:hypothesis-mapper:hypothesis_mapper",
    "codex-main-control:evidence-runner:evidence_runner",
    "codex-value-explorer:evidence-verifier:evidence_verifier",
]


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http" + "://",
        "https" + "://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        supervisor = build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=LANES,
            session_name="loopx-auto-research-worker-loop-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
        )
        _visible_control, registry, runtime_root = _seed_visible_demo_control_plane(
            demo_root=temp,
            goal_id=GOAL_ID,
            objective="Run a role-compatible live worker loop from LoopX queue to public-safe evidence.",
            supervisor=supervisor,
        )
        workspace = temp / "shared-research-workspace"
        workspace.mkdir()
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
        args = [
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
            "worker-loop",
            "--goal-id",
            GOAL_ID,
            "--lane-count",
            str(len(AGENT_IDS)),
            "--max-rounds",
            "3",
            "--visible-lanes-accepted",
            "--complete-selected-todo",
            "--execute",
        ]
        for agent_id in AGENT_IDS:
            args.extend(["--agent-id", agent_id])
        result = subprocess.run(
            args,
            cwd=workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"worker-loop failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["schema_version"] == "auto_research_worker_loop_v0", payload
        assert payload["mode"] == "execute", payload
        assert payload["executed_turn_count"] == 6, payload
        assert payload["completed_turn_count"] == 6, payload
        assert payload["stop_reason"] == "no_runnable_frontier", payload
        assert payload["selected_actions"] == [
            "write_research_contract",
            "propose_hypothesis",
            "run_dev_eval",
            "summarize_evidence",
            "run_holdout_eval",
            "write_evaluation_summary",
        ], payload
        evidence_turn = next(
            turn for turn in payload["turns"] if turn.get("selected_action") == "run_dev_eval"
        )
        assert evidence_turn["dev_metric"] == 4.0, evidence_turn
        assert evidence_turn["appended_count"] == 2, evidence_turn
        assert evidence_turn["live_evidence_written"] is True, evidence_turn
        verifier_turn = next(
            turn for turn in payload["turns"] if turn.get("selected_action") == "summarize_evidence"
        )
        assert verifier_turn["completion_status"] == "done", verifier_turn
        assert verifier_turn["claim_allowed"] is None, verifier_turn
        assert verifier_turn["appended_count"] is None, verifier_turn
        holdout_turn = next(
            turn for turn in payload["turns"] if turn.get("selected_action") == "run_holdout_eval"
        )
        assert holdout_turn["holdout_metric"] == 4.5, holdout_turn
        assert holdout_turn["completion_status"] == "done", holdout_turn
        summary_turn = next(
            turn for turn in payload["turns"] if turn.get("selected_action") == "write_evaluation_summary"
        )
        assert summary_turn["completion_status"] == "done", summary_turn
        assert summary_turn["selected_todo_id"], summary_turn
        final_round = [turn for turn in payload["turns"] if turn.get("round") == 3]
        assert final_round and all(turn["mode"] == "no_action" for turn in final_round), payload
        assert_public_safe(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
