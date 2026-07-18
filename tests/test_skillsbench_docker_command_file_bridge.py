from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path

import scripts.skillsbench_docker_command_file_bridge as bridge_module
from loopx.benchmark_adapters.skillsbench_bridge_guard import (
    LOOPX_COMMAND_INSTRUMENTATION_SOURCE,
)
from loopx.benchmark_core.container_exec import parse_container_exit_status
from scripts.skillsbench_docker_command_file_bridge import (
    MARKER_CONTENT,
    DockerCommandFileBridge,
)


def _bridge() -> DockerCommandFileBridge:
    return DockerCommandFileBridge(
        project_name="demo-project",
        project_dir="/tmp/demo-project",
        compose_files=["/tmp/demo-project/compose.yaml"],
        service="main",
    )


def _loopx_subcommands(command: str) -> list[str]:
    namespace = {"re": re, "shlex": shlex}
    exec(LOOPX_COMMAND_INSTRUMENTATION_SOURCE, namespace)
    return namespace["loopx_subcommands"](command)


def test_loopx_subcommands_skip_compact_and_custom_scheduler_bindings() -> None:
    compact = (
        "loopx --format json quota should-run --goal-id g "
        "--available-capability network --runtime-profile outer_controller"
    )
    custom = (
        "loopx --format json quota should-run --goal-id g "
        "-H codex_cli -O agent_cli_loop -M isolated_headless"
    )

    assert _loopx_subcommands(compact) == ["quota", "should-run"]
    assert _loopx_subcommands(custom) == ["quota", "should-run"]


def test_container_exit_status_parser_fails_closed() -> None:
    assert parse_container_exit_status(b"0\n") == 0
    assert parse_container_exit_status("255") == 255
    assert parse_container_exit_status(b"") is None
    assert parse_container_exit_status(b"256") is None
    assert parse_container_exit_status(b"not-a-status") is None


def test_resolve_container_id_uses_compose_labels(monkeypatch) -> None:
    bridge = _bridge()
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/docker.sock")

    def fake_run(command, **_kwargs):
        assert command[:6] == [
            "curl",
            "--silent",
            "--show-error",
            "--fail",
            "--unix-socket",
            "/tmp/docker.sock",
        ]
        payload = [
            {
                "Id": "private-container-id",
                "Labels": {
                    "com.docker.compose.project": "demo-project",
                    "com.docker.compose.service": "main",
                },
            }
        ]
        return subprocess.CompletedProcess(command, 0, json.dumps(payload).encode(), b"")

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)
    assert bridge._resolve_container_id(timeout_seconds=5) == "private-container-id"


def test_read_file_uses_bounded_docker_copy(monkeypatch, capsys) -> None:
    bridge = _bridge()
    compose_commands: list[str] = []

    def fake_compose_exec(shell_command, **_kwargs):
        compose_commands.append(shell_command)
        return subprocess.CompletedProcess([], 0, b"", b"")

    def fake_docker_cp(command, **_kwargs):
        assert command[:2] == ["docker", "cp"]
        assert command[2].startswith("private-container-id:")
        Path(command[3]).write_bytes(b"abcde")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(bridge, "_compose_exec", fake_compose_exec)
    monkeypatch.setattr(
        bridge, "_resolve_container_id", lambda **_kwargs: "private-container-id"
    )
    monkeypatch.setattr(bridge_module.subprocess, "run", fake_docker_cp)

    assert bridge._run_read_file({"path": "/app/result.txt", "max_bytes": 4}, 5) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["ok"] is True
    assert response["content"] == "abcd"
    assert response["content_truncated"] is True
    assert any("bs=5 count=1" in command for command in compose_commands)
    assert any(command.startswith("rm -f -- ") for command in compose_commands)


def test_exec_and_probe_do_not_depend_on_attached_stdout(monkeypatch, capsys) -> None:
    bridge = _bridge()
    exit_codes = iter((b"0", b"7"))

    def fake_compose_exec(_shell_command, **_kwargs):
        return subprocess.CompletedProcess([], 0, b"", b"")

    def fake_read(path, **_kwargs):
        if path.endswith("/stdout"):
            return 0, b"visible output\n", b""
        if path.endswith("/stderr"):
            return 0, b"", b""
        if path.endswith("/exit_code"):
            return 0, next(exit_codes), b""
        return 0, MARKER_CONTENT.encode(), b""

    monkeypatch.setattr(bridge, "_compose_exec", fake_compose_exec)
    monkeypatch.setattr(bridge, "_read_container_file_via_copy", fake_read)

    assert bridge._run_exec({"cwd": "/app", "command": "pwd"}, 5) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["ok"] is True
    assert response["stdout"] == "visible output\n"

    operations, blocker = bridge.probe(5)
    assert blocker is None
    assert all(operation["status"] == "ok" for operation in operations)


def test_exec_recovers_container_exit_code_when_compose_reports_zero(
    monkeypatch, capsys
) -> None:
    bridge = _bridge()
    compose_commands: list[str] = []

    def fake_compose_exec(shell_command, **_kwargs):
        compose_commands.append(shell_command)
        return subprocess.CompletedProcess([], 0, b"", b"")

    def fake_read(path, **_kwargs):
        if path.endswith("/stdout"):
            return 0, b"", b""
        if path.endswith("/stderr"):
            return 0, b"command failed\n", b""
        if path.endswith("/exit_code"):
            return 0, b"7\n", b""
        raise AssertionError(path)

    monkeypatch.setattr(bridge, "_compose_exec", fake_compose_exec)
    monkeypatch.setattr(bridge, "_read_container_file_via_copy", fake_read)
    completion_times = iter((0.0, 20.0))
    monkeypatch.setattr(
        bridge_module.time,
        "monotonic",
        lambda: next(completion_times),
    )

    assert bridge._run_exec({"cwd": "/app", "command": "exit 7"}, 5) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["ok"] is False
    assert response["first_blocker"] == "exec_failed"
    assert response["exit_code"] == 7
    assert "loopx_command_rc=$?" in compose_commands[0]
    assert "/exit_code" in compose_commands[0]


def test_exec_waits_for_delayed_container_exit_status(monkeypatch, capsys) -> None:
    bridge = _bridge()
    status_reads = 0

    def fake_compose_exec(_shell_command, **_kwargs):
        return subprocess.CompletedProcess([], 0, b"", b"")

    def fake_read(path, **_kwargs):
        nonlocal status_reads
        if path.endswith("/exit_code"):
            status_reads += 1
            if status_reads < 3:
                return 1, b"", b"status pending"
            return 0, b"7\n", b""
        if path.endswith("/stdout"):
            return 0, b"", b""
        if path.endswith("/stderr"):
            return 0, b"late failure\n", b""
        raise AssertionError(path)

    monkeypatch.setattr(bridge, "_compose_exec", fake_compose_exec)
    monkeypatch.setattr(bridge, "_read_container_file_via_copy", fake_read)
    monkeypatch.setattr(bridge_module.time, "sleep", lambda _seconds: None)

    assert bridge._run_exec({"cwd": "/app", "command": "exit 7"}, 5) == 0
    response = json.loads(capsys.readouterr().out)
    assert status_reads == 3
    assert response["ok"] is False
    assert response["first_blocker"] == "exec_failed"
    assert response["exit_code"] == 7
    assert response["stderr"] == "late failure\n"
