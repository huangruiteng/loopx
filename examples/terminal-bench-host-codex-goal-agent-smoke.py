#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench host Codex Goal custom agent helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "terminal_bench_host_codex_goal_agent.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tb_host_codex_goal_agent", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_module()

    command = module.build_codex_tui_command(
        codex_bin="codex",
        model_name="gpt-5.5",
    )
    assert command == [
        "codex",
        "--no-alt-screen",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "danger-full-access",
        "--model",
        "gpt-5.5",
    ], command

    marker = Path("/tmp/goal-harness-terminal-bench/done.marker")
    prompt = module.build_host_goal_prompt(
        container_name="example-container",
        instruction="Synthetic instruction placeholder.",
        marker_path=marker,
        task_workdir="/app",
    )
    assert "native Codex Goal mode" in prompt
    assert "docker exec example-container" in prompt
    assert "cd /app" in prompt
    assert "first verify container command execution" in prompt
    assert "docker exec example-container bash -lc 'cd /app && pwd'" in prompt
    assert "Synthetic instruction placeholder." in prompt
    assert str(marker) in prompt
    assert "/Users/" not in prompt
    assert "/data/goal-harness-bench" not in prompt
    assert "/root/goal-harness-bench" not in prompt

    agent = module.HostCodexGoalAgent(
        goal_timeout_sec="7",
        startup_delay_sec="0",
        poll_interval_sec="0.5",
        goal_surface="app_server",
        app_server_response_timeout_sec="4",
    )
    assert agent.name() == "host-codex-goal"
    assert agent.goal_timeout_sec == 7.0
    assert agent.poll_interval_sec == 0.5
    assert agent.goal_surface == "app_server"
    assert agent.reasoning_effort == "high"
    assert agent.app_server_wait_for_completion is True
    assert agent.app_server_response_timeout_sec == 4.0
    assert str(agent.work_root) == "/tmp/goal-harness-terminal-bench"
    assert agent.network_bootstrap_script is None

    no_wait_agent = module.HostCodexGoalAgent(
        goal_surface="app_server",
        app_server_wait_for_completion="false",
    )
    assert no_wait_agent.app_server_wait_for_completion is False

    print("terminal-bench host Codex Goal agent smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
