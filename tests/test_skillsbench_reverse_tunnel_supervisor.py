from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_PATH = REPO_ROOT / "scripts" / "skillsbench_reverse_tunnel_supervisor.py"


def _load_supervisor_module():
    spec = importlib.util.spec_from_file_location(
        "skillsbench_reverse_tunnel_supervisor_test",
        SUPERVISOR_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fake_ssh(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import sys
import time

if "loopx_reverse_tunnel_keepalive" in sys.argv[-1]:
    time.sleep(10)
elif "# LOOPX_REVERSE_TUNNEL_PROBE" in sys.argv[-1]:
    print("HTTP/1.1 200 OK")
elif sys.argv[-1] == "run-benchmark":
    time.sleep(0.2)
elif sys.argv[-1] == "fail-arguments":
    print("usage: runner [--known]", file=sys.stderr)
    print("runner: error: unrecognized arguments: --private-value", file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(0)
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_fake_codex(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
exit 0
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_supervisor_writes_starting_periodic_and_terminal_public_liveness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    supervisor = _load_supervisor_module()
    supervisor.PUBLIC_LIVENESS_INTERVAL_SEC = 0.05
    checkpoint_states: list[str] = []
    write_checkpoint = supervisor._write_public_checkpoint

    def record_checkpoint(*args, **kwargs) -> None:
        checkpoint_states.append(kwargs["state"])
        write_checkpoint(*args, **kwargs)

    monkeypatch.setattr(supervisor, "_write_public_checkpoint", record_checkpoint)
    fake_ssh = tmp_path / "fake-ssh"
    public_output = tmp_path / "public" / "supervisor.public.json"
    _write_fake_ssh(fake_ssh)

    args = supervisor.parse_args(
        [
            "--ssh-bin",
            str(fake_ssh),
            "--ssh-destination",
            "runner.example",
            "--remote-command",
            "run-benchmark",
            "--public-output-path",
            str(public_output),
            "--probe-interval-sec",
            "0.01",
            "--probe-timeout-sec",
            "1",
            "--tunnel-ready-timeout-sec",
            "1",
            "--tunnel-health-interval-sec",
            "0",
            "--run-timeout-sec",
            "2",
        ]
    )

    returncode, payload = supervisor.run_supervisor(args)
    persisted = json.loads(public_output.read_text(encoding="utf-8"))

    assert returncode == 0
    assert payload["ok"] is True
    assert persisted == payload
    assert checkpoint_states[0] == "starting"
    assert checkpoint_states.count("running") >= 2
    assert checkpoint_states[-1] == "succeeded"
    assert persisted["public_liveness"]["state"] == "succeeded"
    assert persisted["public_liveness"]["terminal"] is True
    assert persisted["public_liveness"]["process_alive"] is False
    assert persisted["public_liveness"]["heartbeat_count"] >= 4
    assert persisted["public_liveness"]["elapsed_sec"] >= 0.2
    assert persisted["public_liveness"]["raw_task_text_recorded"] is False
    assert persisted["public_liveness"]["raw_logs_recorded"] is False
    assert persisted["public_liveness"]["raw_trajectory_recorded"] is False
    assert persisted["public_liveness"]["raw_verifier_output_recorded"] is False
    assert persisted["public_liveness"]["local_paths_recorded"] is False


def test_supervisor_finalizes_public_liveness_on_early_launch_failure(
    tmp_path: Path,
) -> None:
    supervisor = _load_supervisor_module()
    public_output = tmp_path / "public" / "supervisor.public.json"
    args = supervisor.parse_args(
        [
            "--ssh-bin",
            str(tmp_path / "missing-ssh"),
            "--ssh-destination",
            "runner.example",
            "--remote-command",
            "run-benchmark",
            "--public-output-path",
            str(public_output),
        ]
    )

    returncode, payload = supervisor.run_supervisor(args)
    persisted = json.loads(public_output.read_text(encoding="utf-8"))

    assert returncode == 2
    assert payload["first_blocker"] == "reverse_tunnel_launch_failed"
    assert persisted == payload
    assert persisted["public_liveness"]["state"] == "failed"
    assert persisted["public_liveness"]["terminal"] is True
    assert persisted["public_liveness"]["process_alive"] is False
    assert persisted["public_liveness"]["heartbeat_count"] == 2


def test_remote_command_failure_subtype_uses_public_allowlist() -> None:
    supervisor = _load_supervisor_module()

    assert supervisor._remote_command_failure_subtype(
        "RuntimeError: loopx_runner_source_git_head_mismatch"
    ) == "runner_source_git_head_mismatch"
    assert supervisor._remote_command_failure_subtype(
        "runner: error: unrecognized arguments: --private-value"
    ) == "cli_argument_incompatible"
    assert supervisor._remote_command_failure_subtype(
        "usage: runner [--mode MODE]\nrunner: error: "
        "argument --mode: invalid choice"
    ) == "cli_argument_error"
    assert supervisor._remote_command_failure_subtype(
        "python3: can't open file 'opaque-runner.py': "
        "[Errno 2] No such file or directory"
    ) == "remote_entrypoint_missing"
    assert supervisor._remote_command_failure_subtype(
        "SkillsBenchSetupPreflightBlocked: private setup detail"
    ) == "setup_preflight_blocked"
    assert supervisor._remote_command_failure_subtype(
        "secret-host.example failed with private-token"
    ) == "unclassified"


def test_supervisor_projects_only_allowlisted_remote_failure_subtype(
    tmp_path: Path,
) -> None:
    supervisor = _load_supervisor_module()
    fake_ssh = tmp_path / "fake-ssh"
    public_output = tmp_path / "public" / "supervisor.public.json"
    _write_fake_ssh(fake_ssh)
    args = supervisor.parse_args(
        [
            "--ssh-bin",
            str(fake_ssh),
            "--ssh-destination",
            "runner.example",
            "--remote-command",
            "fail-arguments",
            "--public-output-path",
            str(public_output),
            "--probe-interval-sec",
            "0.01",
            "--probe-timeout-sec",
            "1",
            "--tunnel-ready-timeout-sec",
            "1",
            "--tunnel-health-interval-sec",
            "0",
            "--run-timeout-sec",
            "2",
        ]
    )

    returncode, payload = supervisor.run_supervisor(args)
    persisted = json.loads(public_output.read_text(encoding="utf-8"))
    public_text = json.dumps(persisted, sort_keys=True)

    assert returncode == 2
    assert payload["first_blocker"] == "remote_command_exit_nonzero"
    assert payload["remote_command_failure_subtype"] == (
        "cli_argument_incompatible"
    )
    assert persisted == payload
    assert "--private-value" not in public_text
    assert "usage: runner" not in public_text
    assert persisted["raw_remote_output_recorded"] is False


def test_supervisor_codex_bridge_preflight_is_task_free_and_public_safe(
    tmp_path: Path,
) -> None:
    supervisor = _load_supervisor_module()
    fake_ssh = tmp_path / "fake-ssh"
    fake_codex = tmp_path / "fake-codex"
    public_output = tmp_path / "public" / "supervisor.public.json"
    _write_fake_ssh(fake_ssh)
    _write_fake_codex(fake_codex)
    private_socket = "/tmp/private-codex-socket"
    private_client = "/tmp/private-codex-client"
    private_prompt_bridge = "private-prompt-bridge sentinel-bridge"
    args = supervisor.parse_args(
        [
            "--ssh-bin",
            str(fake_ssh),
            "--ssh-destination",
            "runner.example",
            "--codex-bridge",
            "--codex-bin",
            str(fake_codex),
            "--codex-remote-socket",
            private_socket,
            "--codex-remote-client-path",
            private_client,
            "--codex-prompt-bridge-command",
            private_prompt_bridge,
            "--codex-participant-sandbox",
            "workspace-write",
            "--preflight-only",
            "--public-output-path",
            str(public_output),
            "--probe-interval-sec",
            "0.01",
            "--probe-timeout-sec",
            "1",
            "--tunnel-ready-timeout-sec",
            "1",
            "--codex-socket-ready-timeout-sec",
            "1",
            "--codex-participant-probe-timeout-sec",
            "1",
        ]
    )

    returncode, payload = supervisor.run_supervisor(args)
    persisted = json.loads(public_output.read_text(encoding="utf-8"))
    public_text = json.dumps(persisted, sort_keys=True)

    assert returncode == 0
    assert payload["ok"] is True
    assert persisted == payload
    assert persisted["remote_command_requested"] is False
    assert persisted["codex_bridge"]["enabled"] is True
    assert persisted["codex_bridge"]["server_started"] is True
    assert persisted["codex_bridge"]["local_socket_ready"] is True
    assert persisted["codex_bridge"]["remote_socket_ready"] is True
    assert persisted["codex_bridge"]["remote_client_materialized"] is True
    assert persisted["codex_bridge"]["participant_probe_passed"] is True
    assert persisted["codex_bridge"]["participant_probe"]["sandbox"] == (
        "workspace-write"
    )
    assert persisted["codex_bridge"]["participant_probe"]["raw_output_recorded"] is (
        False
    )
    assert private_socket not in public_text
    assert private_client not in public_text
    assert private_prompt_bridge not in public_text
    assert "runner.example" not in public_text
    assert "sentinel-bridge" not in public_text
