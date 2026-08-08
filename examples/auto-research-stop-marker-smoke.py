#!/usr/bin/env python3
"""Smoke: stop marker lifecycle for auto-research worker-loop.

Covers:
  - Placing the stop marker causes ``operator_stop_requested`` before round 1.
  - The stop marker is checked before *each* round, not just at start.
  - Removing the marker lets the worker-loop resume.
"""

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
CURATOR_AGENT_ID = "research-curator"
HYPOTHESIS_AGENT_ID = "hypothesis-proposer"
EXECUTOR_AGENT_ID = "research-executor"
EVALUATOR_AGENT_ID = "evaluator-promoter"
AGENT_IDS = [CURATOR_AGENT_ID, HYPOTHESIS_AGENT_ID, EXECUTOR_AGENT_ID, EVALUATOR_AGENT_ID]
LANES = [
    "research-curator:research-curator:research_curator",
    "hypothesis-proposer:hypothesis-proposer:hypothesis_proposer",
    "research-executor:research-executor:research_executor",
    "evaluator-promoter:evaluator-promoter:evaluator_promoter",
]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return env


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


def _run_worker_loop(
    *, registry: Path, runtime_root: str | None, workspace: Path, max_rounds: int = 2
) -> dict[str, Any]:
    env = _env()
    args = [
        sys.executable, "-m", "loopx.cli", "--registry", str(registry),
        "--runtime-root", str(runtime_root), "--format", "json",
        "auto-research", "worker-loop", "--goal-id", GOAL_ID,
        "--lane-count", str(len(AGENT_IDS)), "--max-rounds", str(max_rounds),
        "--visible-lanes-accepted", "--complete-selected-todo", "--execute",
    ]
    for agent_id in AGENT_IDS:
        args.extend(["--agent-id", agent_id])
    result = subprocess.run(args, cwd=workspace, env=env, check=False,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(
            f"worker-loop failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _stop_marker(workspace: Path) -> Path:
    return workspace / ".loopx-auto-research-stop"


def test_stop_marker_halts_before_round_one() -> None:
    """Placing the stop marker causes the worker-loop to exit before any turns."""
    temp = Path(tempfile.mkdtemp(prefix="loopx-smoke-stop-marker-"))
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID, agent_specs=LANES,
        session_name="loopx-smoke-stop-marker",
        cli_bin="loopx", codex_bin="codex", tmux_bin="tmux", reasoning_effort="high",
    )
    _, registry, runtime_root = _seed_visible_demo_control_plane(
        demo_root=temp, goal_id=GOAL_ID,
        objective="Verify stop marker halts worker-loop before round 1.",
        supervisor=supervisor,
    )
    workspace = temp / "shared-research-workspace"
    workspace.mkdir()

    # Place stop marker before calling the loop.
    _stop_marker(workspace).write_text("stop", encoding="utf-8")

    payload = _run_worker_loop(
        registry=registry, runtime_root=runtime_root, workspace=workspace, max_rounds=3,
    )
    assert payload["ok"] is True, payload
    assert payload["stop_reason"] == "operator_stop_requested", payload["stop_reason"]
    assert payload["turn_count"] == 0, payload["turn_count"]
    assert_public_safe(payload)


def test_stop_marker_checked_before_each_round() -> None:
    """Stop marker is checked at the top of every round — not just at start."""
    temp = Path(tempfile.mkdtemp(prefix="loopx-smoke-stop-marker-mid-"))
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID, agent_specs=LANES,
        session_name="loopx-smoke-stop-marker-mid",
        cli_bin="loopx", codex_bin="codex", tmux_bin="tmux", reasoning_effort="high",
    )
    _, registry, runtime_root = _seed_visible_demo_control_plane(
        demo_root=temp, goal_id=GOAL_ID,
        objective="Verify stop marker is checked before each round.",
        supervisor=supervisor,
    )
    workspace = temp / "shared-research-workspace"
    workspace.mkdir()

    # Run one round without marker.
    round1 = _run_worker_loop(
        registry=registry, runtime_root=runtime_root, workspace=workspace, max_rounds=1,
    )
    assert round1["stop_reason"] in ("no_executed_turns", "no_runnable_frontier"), round1

    # Place marker — next loop call should stop immediately.
    _stop_marker(workspace).write_text("stop", encoding="utf-8")
    round2 = _run_worker_loop(
        registry=registry, runtime_root=runtime_root, workspace=workspace, max_rounds=1,
    )
    assert round2["stop_reason"] == "operator_stop_requested", round2["stop_reason"]
    assert round2["turn_count"] == 0, round2
    assert_public_safe(round2)

    # Remove marker — loop can run again.
    _stop_marker(workspace).unlink(missing_ok=True)
    round3 = _run_worker_loop(
        registry=registry, runtime_root=runtime_root, workspace=workspace, max_rounds=1,
    )
    assert round3["stop_reason"] != "operator_stop_requested", round3["stop_reason"]
    assert_public_safe(round3)


def main() -> int:
    test_stop_marker_halts_before_round_one()
    print("  ok  stop marker halts before round one")
    test_stop_marker_checked_before_each_round()
    print("  ok  stop marker checked before each round")
    print("auto-research-stop-marker-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
