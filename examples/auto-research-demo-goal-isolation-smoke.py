#!/usr/bin/env python3
"""Smoke-test isolated goal defaults for the one-command auto-research demo."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOAL_ID = "loopx-auto-research-demo"
FRESH_GOAL_ID = "loopx-auto-research-demo-smoke-001"
EXPLICIT_GOAL_ID = "loopx-auto-research-demo-explicit"
AGENT_ID = "codex-side-bypass"


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


def run_cli(
    args: list[str],
    *,
    registry: Path,
    runtime_root: Path,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
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
            *args,
        ],
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def read_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    payload = json.loads(result.stdout)
    assert_public_safe(payload)
    return payload


def assert_route(
    payload: dict[str, Any],
    *,
    goal_id: str,
    mode: str,
    reuses_default: bool,
) -> None:
    assert payload["ok"] is True, payload
    assert payload["goal_id"] == goal_id, payload
    route = payload["route_contract"]
    assert route["frontier_goal_id"] == goal_id, route
    assert route["visible_lanes_read_goal_id"] == goal_id, route
    assert route["goal_surface_mode"] == mode, route
    assert route["reuses_default_internal_goal"] is reuses_default, route
    assert route["default_internal_goal_id"] == DEFAULT_GOAL_ID, route
    assert route["dedicated_positive_demo_frontier"] is (not reuses_default), route
    if mode == "fresh_demo_goal":
        assert route["fresh_goal_default"] is True, route
        assert route["inherits_default_goal"] is False, route
        assert goal_id.startswith("loopx-auto-research-demo-"), route
    if mode == "inherited_default_goal":
        assert route["fresh_goal_default"] is False, route
        assert route["inherits_default_goal"] is True, route
    assert "--goal-id " + goal_id in payload["commands"]["one_command_worker_loop"], payload


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

        fresh = read_json(
            run_cli(
                [
                    "auto-research",
                    "demo-e2e",
                    "--agent-id",
                    AGENT_ID,
                    "--demo-run-id",
                    "smoke-001",
                ],
                registry=registry,
                runtime_root=runtime_root,
                cwd=workspace,
            )
        )
        assert_route(
            fresh,
            goal_id=FRESH_GOAL_ID,
            mode="fresh_demo_goal",
            reuses_default=False,
        )

        inherited = read_json(
            run_cli(
                [
                    "auto-research",
                    "demo-e2e",
                    "--agent-id",
                    AGENT_ID,
                    "--inherit-default-goal",
                ],
                registry=registry,
                runtime_root=runtime_root,
                cwd=workspace,
            )
        )
        assert_route(
            inherited,
            goal_id=DEFAULT_GOAL_ID,
            mode="inherited_default_goal",
            reuses_default=True,
        )

        explicit = read_json(
            run_cli(
                [
                    "auto-research",
                    "demo-e2e",
                    "--agent-id",
                    AGENT_ID,
                    "--goal-id",
                    EXPLICIT_GOAL_ID,
                ],
                registry=registry,
                runtime_root=runtime_root,
                cwd=workspace,
            )
        )
        assert_route(
            explicit,
            goal_id=EXPLICIT_GOAL_ID,
            mode="explicit_goal",
            reuses_default=False,
        )

        supervisor = read_json(
            run_cli(
                [
                    "auto-research",
                    "demo-supervisor",
                    "--demo-run-id",
                    "smoke-001",
                ],
                registry=registry,
                runtime_root=runtime_root,
                cwd=workspace,
            )
        )
        assert supervisor["goal_id"] == FRESH_GOAL_ID, supervisor
        surface = supervisor["goal_surface_route"]
        assert surface["mode"] == "fresh_demo_goal", surface
        assert surface["fresh_by_default"] is True, surface
        assert surface["reuses_default_internal_goal"] is False, surface

        conflict = read_json(
            run_cli(
                [
                    "auto-research",
                    "demo-e2e",
                    "--agent-id",
                    AGENT_ID,
                    "--goal-id",
                    EXPLICIT_GOAL_ID,
                    "--inherit-default-goal",
                ],
                registry=registry,
                runtime_root=runtime_root,
                cwd=workspace,
                check=False,
            )
        )
        assert conflict["ok"] is False, conflict
        assert "--inherit-default-goal cannot be combined with --goal-id" in conflict["error"], conflict

    print("auto-research demo goal isolation smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
