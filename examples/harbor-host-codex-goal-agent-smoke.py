#!/usr/bin/env python3
"""Smoke-test the Harbor host Codex Goal custom agent helpers."""

from __future__ import annotations

import importlib.util
import py_compile
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "harbor_host_codex_goal_agent.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("harbor_host_codex_goal", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_module()

    command = module.build_codex_tui_command(model_name="gpt-5.5")
    assert command[:5] == [
        "codex",
        "--no-alt-screen",
        "--ask-for-approval",
        "never",
        "--sandbox",
    ], command
    assert command[-2:] == ["--model", "gpt-5.5"], command

    prompt = module.build_host_goal_prompt(
        instruction="Synthetic Harbor instruction placeholder.",
        bridge_command=Path("/tmp/gh-harbor/bin/harbor-env-exec"),
        marker_path=Path("/tmp/gh-harbor/done.marker"),
        task_workdir="/workspace",
    )
    assert "native Codex Goal mode" in prompt
    assert "harbor-env-exec" in prompt
    assert "--cwd /workspace -- <command>" in prompt
    assert "first verify the bridge" in prompt
    assert "--cwd /workspace -- pwd" in prompt
    assert "Synthetic Harbor instruction placeholder." in prompt
    assert "/Users/" not in prompt
    assert "/data/goal-harness-bench" not in prompt
    assert "/root/goal-harness-bench" not in prompt

    with tempfile.TemporaryDirectory(prefix="gh-harbor-host-agent-") as tmp:
        request_dir = Path(tmp) / "requests"
        request_dir.mkdir()
        bridge = Path(tmp) / "harbor-env-exec"
        module.HarborHostCodexGoalAgent._write_bridge_script(bridge, request_dir)
        text = bridge.read_text(encoding="utf-8")
        assert "environment.exec" in text
        assert str(request_dir) in text
        assert bridge.stat().st_mode & 0o111
        py_compile.compile(str(bridge), doraise=True)

        agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "logs",
            goal_timeout_sec="9",
            startup_delay_sec="0",
            poll_interval_sec="0.5",
            task_workdir="/workspace",
            goal_surface="app_server",
            app_server_response_timeout_sec="4",
        )
        assert agent.name() == "harbor-host-codex-goal"
        assert agent.version() == "0.3.0"
        assert agent.goal_timeout_sec == 9.0
        assert agent.poll_interval_sec == 0.5
        assert agent.task_workdir == "/workspace"
        assert agent.goal_surface == "app_server"
        assert agent.reasoning_effort == "high"
        assert agent.app_server_wait_for_completion is True
        assert agent.app_server_response_timeout_sec == 4.0

        no_wait_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "no-wait-logs",
            goal_surface="app_server",
            app_server_wait_for_completion="false",
        )
        assert no_wait_agent.app_server_wait_for_completion is False

    print("harbor host Codex Goal agent smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
