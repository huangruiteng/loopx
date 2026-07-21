from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "skillsbench-launch-goal-xhigh.sh"


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("SKILLSBENCH_RUNNER_PROFILE", None)
    env.update(
        {
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "SKILLSBENCH_SSH_DESTINATION": "example.invalid",
            "SKILLSBENCH_REMOTE_ROOT": "/remote/loopx",
            "SKILLSBENCH_ROOT": "/remote/skillsbench",
            "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD": "abc1234",
            "SKILLSBENCH_DOCKER_PROXY_HOST": "host.docker.internal",
            "SKILLSBENCH_DOCKER_API_VERSION": "1.43",
            "SKILLSBENCH_RUN_STAMP": "20260716T000000CST",
        }
    )
    return env


def test_turn_launcher_wires_private_commands_without_echoing_values(
    tmp_path: Path,
) -> None:
    env = _base_env(tmp_path)
    private_values = {
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_COMMAND": (
            "private-probe-command sentinel-probe"
        ),
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_SOLVER_COMMAND": (
            "private-solver-command sentinel-solver"
        ),
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND": (
            "private-agent-command sentinel-agent"
        ),
        "SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND": (
            "private-validator-command sentinel-validator"
        ),
    }
    env.update(private_values)
    env.update(
        {
            "SKILLSBENCH_ROUTE": "loopx-turn-agent-cli",
            "SKILLSBENCH_LOOPX_TURN_MAX_TURNS": "4",
            "SKILLSBENCH_LOOPX_TURN_PROGRESS_EXIT_CODE": "10",
            "SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICY": "fixed-n",
            "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED": (
                "1"
            ),
        }
    )

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "turn-wiring"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    output = proc.stdout
    assert "remote_command_file_bridge_probe_command_configured=1" in output
    assert "remote_command_file_bridge_solver_command_configured=1" in output
    assert "remote_command_file_bridge_agent_command_configured=1" in output
    assert "remote_command_file_bridge_agent_command_instrumented=1" in output
    assert "loopx_turn_validation_command_configured=1" in output
    assert "loopx_turn_max_turns=4" in output
    assert "loopx_turn_progress_exit_code=10" in output
    assert "loopx_turn_terminal_policy=fixed-n" in output
    assert "docker_proxy_host_recorded=false" in output
    assert "docker_proxy_host=" not in output
    assert env["SKILLSBENCH_DOCKER_PROXY_HOST"] not in output
    assert "private_runner_command_values_redacted=true" in output
    for arg_name in (
        "--remote-command-file-bridge-probe-command",
        "--remote-command-file-bridge-solver-command",
        "--remote-command-file-bridge-agent-command",
        "--remote-command-file-bridge-agent-command-instrumented",
        "--loopx-turn-validation-command",
        "--loopx-turn-max-turns",
        "--loopx-turn-progress-exit-code",
        "--loopx-turn-terminal-policy",
    ):
        assert arg_name in output
    for private_value in private_values.values():
        assert private_value not in output
    assert "sentinel-" not in output


def test_turn_launcher_accepts_stability_policy(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    validator = "private-validator-command sentinel-validator"
    env.update(
        {
            "SKILLSBENCH_ROUTE": "loopx-turn-agent-cli",
            "SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND": validator,
            "SKILLSBENCH_LOOPX_TURN_MAX_TURNS": "4",
            "SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICY": "stability",
        }
    )

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "stability-wiring"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    assert "loopx_turn_max_turns=4" in proc.stdout
    assert "loopx_turn_terminal_policy=stability" in proc.stdout
    assert validator not in proc.stdout


def test_instrumented_agent_bridge_requires_an_explicit_agent_command(
    tmp_path: Path,
) -> None:
    env = _base_env(tmp_path)
    env["SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED"] = "1"

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "turn-wiring"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert (
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED requires "
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND"
    ) in proc.stderr


def test_turn_launcher_requires_an_independent_validator(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    env["SKILLSBENCH_ROUTE"] = "loopx-turn-agent-cli"

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "turn-wiring"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert (
        "SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND is required for "
        "loopx-turn-agent-cli"
    ) in proc.stderr


def test_launcher_allows_explicit_direct_benchmark_egress(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    env["SKILLSBENCH_BENCHMARK_EGRESS_PROXY_MODE"] = "off"

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "direct-egress"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    assert "benchmark_egress_proxy_mode=off" in proc.stdout
    assert "--benchmark-egress-proxy-mode off" in proc.stdout


def test_launcher_rejects_invalid_benchmark_egress_mode(tmp_path: Path) -> None:
    env = _base_env(tmp_path)
    env["SKILLSBENCH_BENCHMARK_EGRESS_PROXY_MODE"] = "sometimes"

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "direct-egress"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert (
        "SKILLSBENCH_BENCHMARK_EGRESS_PROXY_MODE must be require, auto, or off"
        in proc.stderr
    )


def test_setup_only_launcher_enables_incremental_public_artifact_sync(
    tmp_path: Path,
) -> None:
    env = _base_env(tmp_path)
    env["SKILLSBENCH_SETUP_ONLY_PUBLIC_PREFLIGHT"] = "1"

    proc = subprocess.run(
        [str(LAUNCHER), "--dry-run", "public-smoke-case", "setup-progress"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    assert "public_artifact_sync_interval_sec=30" in proc.stdout
    assert "--public-artifact-sync-interval-sec 30" in proc.stdout
