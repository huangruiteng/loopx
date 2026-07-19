from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path
from typing import Any

import loopx.benchmark_core.container_exec as container_exec_module
from scripts.skillsbench_automation_loop import (
    install_benchflow_docker_exec_output_capture,
    install_benchflow_verifier_prep_timeout_override,
)


def test_host_local_docker_exec_recovers_output_and_status_from_compose_copy() -> None:
    class FakeDockerEnv:
        def __init__(self) -> None:
            self.exec_calls: list[tuple[str, dict[str, Any]]] = []
            self.compose_calls: list[tuple[list[str], dict[str, Any]]] = []

        async def exec(self, command: str, **kwargs: Any) -> Any:
            self.exec_calls.append((command, dict(kwargs)))
            return types.SimpleNamespace(stdout="", stderr="", return_code=0)

        async def _run_docker_compose_command(
            self, command: list[str], **kwargs: Any
        ) -> Any:
            self.compose_calls.append((command, dict(kwargs)))
            source = command[1].split(":", 1)[1]
            if source.endswith("/status"):
                payload = b"7\n"
            elif source.endswith("/stdout"):
                payload = b"captured stdout"
            elif source.endswith("/stderr"):
                payload = b"captured stderr"
            else:
                raise AssertionError(source)
            Path(command[-1]).write_bytes(payload)
            return types.SimpleNamespace(stdout="", stderr="", return_code=0)

    env = FakeDockerEnv()
    plan = {"runner_prerequisites": {}}
    original_exec = install_benchflow_docker_exec_output_capture(env, plan=plan)
    assert original_exec is not None

    result = asyncio.run(env.exec("printf ignored", timeout_sec=2))

    assert result.return_code == 7
    assert result.stdout == "captured stdout"
    assert result.stderr == "captured stderr"
    assert "loopx-benchmark-exec-capture" in env.exec_calls[0][0]
    assert "printf ignored" in env.exec_calls[0][0]
    assert env.exec_calls[-1][0].startswith("rm -rf ")
    assert len(env.compose_calls) == 3
    prereqs = plan["runner_prerequisites"]
    assert prereqs["host_local_acp_docker_exec_capture_status"] == "installed"
    assert prereqs["host_local_acp_docker_exec_capture_required"] is True
    assert prereqs["host_local_acp_docker_exec_capture_compose_copy"] is True
    assert prereqs["host_local_acp_docker_exec_capture_raw_output_recorded"] is False


def test_final_verifier_waits_for_container_completion_marker(monkeypatch) -> None:
    class FakeDockerEnv:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []
            self.compose_calls: list[tuple[list[str], dict[str, Any]]] = []

        async def _run_docker_compose_command(
            self, command: list[str], **kwargs: Any
        ) -> Any:
            self.compose_calls.append((command, dict(kwargs)))
            Path(command[-1]).write_text("7\n")
            return types.SimpleNamespace(stdout=None, return_code=0)

        async def exec(self, command: str, **kwargs: Any) -> Any:
            self.calls.append((command, dict(kwargs)))
            return types.SimpleNamespace(stdout=None, return_code=0)

    class FakeRollout:
        def __init__(self) -> None:
            self._env = FakeDockerEnv()

        async def verify(self) -> Any:
            return await self._env.exec("/verifier/test.sh", timeout_sec=9999)

        async def soft_verify(self) -> None:
            return None

    rollout = FakeRollout()
    completion_times = iter((0.0, 0.1))
    monkeypatch.setattr(
        container_exec_module,
        "time",
        types.SimpleNamespace(monotonic=lambda: next(completion_times)),
    )
    plan = {"runner_prerequisites": {}}
    trace: dict[str, Any] = {}
    original_verify, original_soft_verify = (
        install_benchflow_verifier_prep_timeout_override(
            FakeRollout,
            timeout_sec=120,
            final_verifier_timeout_sec=2,
            plan=plan,
            trace=trace,
        )
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
    assert rollout._env.compose_calls[0][0][0] == "cp"
    assert rollout._env.compose_calls[0][0][1].startswith(
        "main:/tmp/loopx-benchmark-exec-status/"
    )
    assert rollout._env.calls[-1][0].startswith("rm -f ")
    prereqs = plan["runner_prerequisites"]
    assert prereqs["benchflow_verifier_completion_poll_enabled"] is True
    assert prereqs["benchflow_verifier_completion_poll_reader"] == "compose_copy"
    assert prereqs["benchflow_verifier_completion_poll_raw_command_recorded"] is False
    assert prereqs["benchflow_verifier_completion_poll_raw_output_recorded"] is False
    assert "test.sh" not in json.dumps(prereqs)


def test_container_completion_falls_back_to_exec_stdout(monkeypatch) -> None:
    calls: list[str] = []

    async def exec_fn(command: str, **_: Any) -> Any:
        calls.append(command)
        stdout = "3\n" if command.startswith("cat ") else None
        return types.SimpleNamespace(stdout=stdout, return_code=0)

    completion_times = iter((0.0, 0.1))
    monkeypatch.setattr(
        container_exec_module,
        "time",
        types.SimpleNamespace(monotonic=lambda: next(completion_times)),
    )
    result = asyncio.run(
        container_exec_module.run_container_command_with_exit_status(
            exec_fn,
            "true",
            timeout_sec=2,
        )
    )

    assert result.return_code == 3
    assert calls[1].startswith("cat ")
