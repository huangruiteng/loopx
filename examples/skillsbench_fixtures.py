#!/usr/bin/env python3
"""Public-safe SkillsBench fixture builders for benchmark smokes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_official_skillsbench_result(
    root: Path,
    *,
    reward: float = 0.0,
    task_id: str = "sample-task",
) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-00" / f"{task_id}__abc123"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": task_id,
            "rollout_name": f"{task_id}__abc123",
            "rewards": {"reward": reward},
            "agent": "codex-acp",
            "agent_name": "codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 7,
            "n_prompts": 1,
            "error": None,
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": "acp",
        },
    )
    write_json(
        run_dir / "timing.json",
        {
            "environment_setup": 2.0,
            "agent_setup": 1.0,
            "agent_execution": 3.0,
            "verifier": 4.0,
            "total": 10.0,
        },
    )
    return result_path


def write_official_skillsbench_reward_artifact_recovery_result(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-00" / "sample-task__abc123"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "sample-task",
            "rollout_name": "sample-task__abc123",
            "agent": "codex-acp",
            "agent_name": "codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 7,
            "n_prompts": 1,
            "error": None,
            "verifier_error": "reward missing from compact result",
            "partial_trajectory": False,
            "trajectory_source": "acp",
        },
    )
    reward_path = run_dir / "verifier" / "reward.txt"
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("1\n", encoding="utf-8")
    return result_path


def write_official_skillsbench_runner_error_zero_reward_result(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-20__06-38-51" / "travel-planning__raw"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "travel-planning",
            "rollout_name": "travel-planning__raw",
            "agent": "codex-acp",
            "agent_name": "codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": "agent process ended after verifier wrote reward",
            "verifier_error": "reward missing from compact result",
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    reward_path = run_dir / "verifier" / "reward.txt"
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("0\n", encoding="utf-8")
    return result_path


def write_official_skillsbench_oracle_reward_artifact_recovery_result(
    root: Path,
) -> Path:
    run_dir = root / "official" / "2026-06-19__09-28-56" / "sample-task__oracle"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "sample-task",
            "rollout_name": "sample-task__oracle",
            "agent": "oracle",
            "agent_name": "oracle",
            "model": None,
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": None,
            "verifier_error": "verifier crashed: No reward file found",
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    reward_path = run_dir / "verifier" / "reward.txt"
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("1\n", encoding="utf-8")
    return result_path


def write_official_skillsbench_app_mount_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-00" / "citation-check__abc123"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "citation-check",
            "rollout_name": "citation-check__abc123",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment citation-check. "
                "Command: docker compose cp tasks/citation-check/environment/skills/. "
                "main:/app/skills. Error response from daemon: Could not find "
                "the file /app in container abc123."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 50.0, "total": 50.0})
    return result_path


def write_official_skillsbench_app_skills_mount_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-01" / "audit__def456"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "audit",
            "rollout_name": "audit__def456",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": (
                "Docker compose command failed while copying task skills to "
                "the /app/skills target in the running container."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 50.0, "total": 50.0})
    return result_path


def write_official_skillsbench_app_skills_permission_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-03" / "audit__perm"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "audit",
            "rollout_name": "audit__perm",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment audit. "
                "Command: docker compose build. Return code: 1. "
                "Dockerfile:45 RUN mkdir -p /app /app/skills. "
                "mkdir: cannot create directory '/app': Permission denied. "
                "failed to solve: process did not complete successfully"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 12.0, "total": 12.0})
    return result_path


def write_official_skillsbench_docker_port_conflict_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "setup-fuzzing-py__port"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__port",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment setup-fuzzing-py. "
                "Error response from daemon: driver failed programming external "
                "connectivity: Bind for 0.0.0.0:8080 failed: port is already allocated."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 10.0, "total": 10.0})
    return result_path


def write_official_skillsbench_docker_apt_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "setup-fuzzing-py__apt"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__apt",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment setup-fuzzing-py. "
                "The Dockerfile apt-get update step reported a GPG error and "
                "Hash Sum mismatch before agent execution."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 10.0, "total": 10.0})
    return result_path


def write_official_skillsbench_docker_daemon_unavailable_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "paratransit__daemon"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "paratransit-routing",
            "rollout_name": "paratransit-routing__daemon",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment paratransit-routing. "
                "Cannot connect to the Docker daemon at "
                "unix:///Users/example/.colima/default/docker.sock. "
                "Is the docker daemon running?"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 3.0, "total": 3.0})
    return result_path


def write_official_skillsbench_unclassified_compose_failure(root: Path) -> Path:
    run_dir = (
        root
        / "official"
        / "2026-06-15__00-00-03"
        / "paratransit-routing__compose"
    )
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "paratransit-routing",
            "rollout_name": "paratransit-routing__compose",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": (
                "Docker compose command failed for environment "
                "paratransit-routing under /Users/example/private/job/root. "
                "The underlying compose failure did not include a known "
                "setup-category marker."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"total": 10.0})
    return result_path


def write_official_skillsbench_volume_mount_failure(root: Path) -> Path:
    run_dir = (
        root
        / "official"
        / "2026-06-15__00-00-06"
        / "suricata-custom-exfil__volume"
    )
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "suricata-custom-exfil",
            "rollout_name": "suricata-custom-exfil__volume",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment "
                "suricata-custom-exfil under /Users/example/private/job/root. "
                "Error response from daemon: invalid mount config for type "
                "bind: bind source path does not exist."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"total": 10.0})
    return result_path


def write_official_skillsbench_codex_acp_libssl_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "setup-fuzzing-py__ghi789"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__ghi789",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Process closed stdout (rc=127): Local subprocess exited with "
                "rc=127 before stdout closed.\nstderr: codex-acp: error while "
                "loading shared libraries: libssl.so.3: cannot open shared "
                "object file: No such file or directory"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 60.0, "total": 70.0})
    return result_path


def write_official_skillsbench_codex_acp_glibc_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-03" / "setup-fuzzing-py__jkl012"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__jkl012",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "codex-acp runtime unsupported: glibc >=2.34 required by "
                "@zed-industries/codex-acp-linux-x64; found glibc 2.31"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 60.0, "total": 70.0})
    return result_path


def write_official_skillsbench_codex_acp_launch_preflight_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-04" / "ada-bathroom-plan-repair__mno345"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "ada-bathroom-plan-repair",
            "rollout_name": "ada-bathroom-plan-repair__mno345",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "codex-acp runtime launch preflight failed: "
                "codex-acp did not start or expose --version/--help rc=127"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 60.0, "total": 70.0})
    return result_path


def write_official_skillsbench_codex_acp_internal_error(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-05" / "llm-prefix-cache-replay__pqr678"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "llm-prefix-cache-replay",
            "rollout_name": "llm-prefix-cache-replay__pqr678",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": "ACP error -32603: Internal error",
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"agent_execution": 5.0, "total": 10.0})
    return result_path


def write_official_skillsbench_codex_acp_provider_zero_activity(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-23__06-23-26" / "powerlifting__zero"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "powerlifting-coef-calc",
            "rollout_name": "powerlifting-coef-calc__loopx_product_mode",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "@agentclientprotocol/codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": (
                "suspected provider api error: agent ended with zero tokens "
                "and zero tool calls (no scoreable model activity)"
            ),
            "error_category": "suspected_api_error",
            "verifier_error": "verifier timed out after 600.0s",
            "partial_trajectory": False,
            "trajectory_source": "acp",
        },
    )
    write_json(run_dir / "timing.json", {"agent_execution": 5.0, "total": 600.0})
    return result_path


