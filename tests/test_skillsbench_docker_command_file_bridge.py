from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.skillsbench_docker_command_file_bridge as bridge_module
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

    def fake_compose_exec(_shell_command, **_kwargs):
        return subprocess.CompletedProcess([], 0, b"", b"")

    def fake_read(path, **_kwargs):
        if path.endswith("/stdout"):
            return 0, b"visible output\n", b""
        if path.endswith("/stderr"):
            return 0, b"", b""
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
