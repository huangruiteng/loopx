from __future__ import annotations

import asyncio
import json
import types
from typing import Any

import loopx.benchmark_core.container_exec as container_exec_module
from scripts.skillsbench_automation_loop import (
    install_benchflow_verifier_prep_timeout_override,
)


def test_final_verifier_waits_for_container_completion_marker(monkeypatch) -> None:
    class FakeDockerEnv:
        _run_docker_compose_command = object()

        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []

        async def exec(self, command: str, **kwargs: Any) -> Any:
            self.calls.append((command, dict(kwargs)))
            if command.startswith("cat "):
                return types.SimpleNamespace(stdout="7\n", return_code=0)
            return types.SimpleNamespace(stdout=None, return_code=0)

    class FakeRollout:
        def __init__(self) -> None:
            self._env = FakeDockerEnv()

        async def verify(self) -> Any:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

        async def soft_verify(self) -> None:
            return None

    rollout = FakeRollout()
    completion_times = iter((0.0, 3.0))
    monkeypatch.setattr(
        container_exec_module,
        "time",
        types.SimpleNamespace(monotonic=lambda: next(completion_times)),
    )
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = install_benchflow_verifier_prep_timeout_override(
        FakeRollout,
        timeout_sec=120,
        final_verifier_timeout_sec=2,
        plan=plan,
        trace=trace,
    )
    try:
        result = asyncio.run(rollout.verify())
    finally:
        FakeRollout.verify = original_verify
        FakeRollout.soft_verify = original_soft_verify

    assert result.return_code == 7
    assert "/verifier/test.sh" in rollout._env.calls[0][0]
    assert "loopx_command_rc=$?" in rollout._env.calls[0][0]
    assert rollout._env.calls[0][1]["timeout_sec"] == 2
    assert rollout._env.calls[1][0].startswith("cat ")
    assert rollout._env.calls[-1][0].startswith("rm -f ")
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_verifier_completion_poll_enabled"] is True
    assert prereqs["benchflow_verifier_completion_poll_raw_command_recorded"] is False
    assert prereqs["benchflow_verifier_completion_poll_raw_output_recorded"] is False
    assert "test.sh" not in json.dumps(prereqs)
