#!/usr/bin/env python3
"""Smoke-test that auto-research worker-turn does not fake research output."""

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
EXECUTOR_AGENT_ID = "research-executor"
EVALUATOR_AGENT_ID = "evaluator-promoter"
LANES = [
    "research-curator:research-curator:research_curator",
    "hypothesis-proposer:hypothesis-proposer:hypothesis_proposer",
    "research-executor:research-executor:research_executor",
    "evaluator-promoter:evaluator-promoter:evaluator_promoter",
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


def run_worker_turn(
    *,
    registry: Path,
    runtime_root: str | None,
    workspace: Path,
    agent_id: str,
    execute: bool,
    complete: bool = False,
) -> dict[str, Any]:
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
        "worker-turn",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        agent_id,
        "--lane-count",
        "4",
        "--visible-lanes-accepted",
    ]
    if execute:
        args.append("--execute")
    if complete:
        args.append("--complete-selected-todo")
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
            f"worker-turn failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def assert_manual_research_required(payload: dict[str, Any], *, action: str) -> None:
    assert payload["schema_version"] == "auto_research_worker_turn_v0", payload
    assert payload["mode"] == "manual_research_required", payload
    assert payload["selected_action"] == action, payload
    assert payload["executed"] is False, payload
    assert payload["manual_research_required"] is True, payload
    assert payload["completion"]["executed"] is False, payload
    assert payload["public_boundary"]["fake_metrics_recorded"] is False, payload
    assert "dev_metric" not in payload, payload
    assert "holdout_metric" not in payload, payload
    assert "live_evidence" not in payload, payload
    assert_public_safe(payload)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        supervisor = build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=LANES,
            session_name="loopx-auto-research-worker-turn-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
        )
        _visible_control, registry, runtime_root = _seed_visible_demo_control_plane(
            demo_root=temp,
            goal_id=GOAL_ID,
            objective="Verify visible auto-research requires real role-authored evidence.",
            supervisor=supervisor,
        )
        workspace = temp / "visible-workspace"
        workspace.mkdir()

        curator_preview = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=CURATOR_AGENT_ID,
            execute=False,
        )
        assert curator_preview["mode"] == "dry_run", curator_preview
        assert curator_preview["selected_action"] == "write_research_contract", curator_preview

        curator_execute = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=CURATOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert_manual_research_required(curator_execute, action="write_research_contract")

        executor_execute = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EXECUTOR_AGENT_ID,
            execute=True,
            complete=True,
        )
        assert_manual_research_required(executor_execute, action="run_dev_eval")

        evaluator_execute = run_worker_turn(
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            agent_id=EVALUATOR_AGENT_ID,
            execute=True,
            complete=False,
        )
        assert evaluator_execute["mode"] == "execute", evaluator_execute
        assert evaluator_execute["selected_action"] == "summarize_evidence", evaluator_execute
        assert evaluator_execute["summary_mode"] == "rollout_evidence_summary", evaluator_execute
        assert evaluator_execute["claim_allowed"] is False, evaluator_execute
        assert evaluator_execute["evaluation_summary"]["holdout_improvement_count"] == 0, evaluator_execute
        assert evaluator_execute["evaluation_summary"]["best_dev_metric"] is None, evaluator_execute
        assert evaluator_execute["evaluation_summary"]["best_holdout_metric"] is None, evaluator_execute
        assert "dev_metric" not in evaluator_execute, evaluator_execute
        assert "holdout_metric" not in evaluator_execute, evaluator_execute
        assert_public_safe(evaluator_execute)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
