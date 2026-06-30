#!/usr/bin/env python3
"""Smoke-test the one-command auto-research positive demo path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-auto-research-knn"
AGENT_ID = "codex-side-bypass"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_cli(args: list[str], *, registry: Path, runtime_root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_root),
            *args,
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def assert_e2e_payload(payload: dict[str, Any], *, executed: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "auto_research_demo_e2e_result_v0", payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["agent_id"] == AGENT_ID, payload
    assert payload["reasoning_effort"] == "high", payload
    assert payload["supervisor"]["lane_count"] == 3, payload
    assert payload["supervisor"]["reasoning_contract"]["default_reasoning_effort"] == "high", payload
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    assert payload["public_boundary"]["private_artifacts_recorded"] is False, payload
    assert payload["public_boundary"]["absolute_paths_recorded"] is False, payload
    assert payload["public_boundary"]["credentials_recorded"] is False, payload
    assert payload["public_boundary"]["local_workspace_path_redacted"] is True, payload
    replay = payload["replay_result"]
    assert replay["executed"] is executed, payload
    if executed:
        assert replay["status"] == "supported", payload
        assert replay["dev_metric"] == 4.0, payload
        assert replay["holdout_metric"] == 4.5, payload
        assert replay["dev_exact"] is True, payload
        assert replay["holdout_exact"] is True, payload
        assert replay["protected_scope_clean"] is True, payload
        assert payload["append"]["appended_count"] == 3, payload
        assert payload["append"]["counts_by_kind"] == {
            "research_evidence": 2,
            "research_hypothesis": 1,
        }, payload
        assert payload["board"]["rollout_backed"] is True, payload
        assert payload["board"]["promotion_candidate_count"] >= 1, payload
        assert payload["acceptance"]["ready_for_real_launch"] is True, payload
    else:
        assert replay["expected_positive_result"] == "dev=4.0x holdout=4.5x after --execute", payload
    assert_public_safe(payload)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )

        dry_run = run_cli(
            [
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
            ],
            registry=registry,
            runtime_root=runtime_root,
        )
        assert_e2e_payload(json.loads(dry_run.stdout), executed=False)

        executed = run_cli(
            [
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--execute",
            ],
            registry=registry,
            runtime_root=runtime_root,
        )
        assert_e2e_payload(json.loads(executed.stdout), executed=True)

        markdown = run_cli(
            [
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
            ],
            registry=registry,
            runtime_root=runtime_root,
        ).stdout
        assert "# LoopX Auto Research Demo E2E" in markdown, markdown
        assert "reasoning_effort: `high`" in markdown, markdown
        assert "positive replay:" in markdown, markdown
        assert_public_safe(markdown)

    print("auto-research-demo-e2e-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
