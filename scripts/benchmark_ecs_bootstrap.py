#!/usr/bin/env python3
"""Public-safe readiness probe for a dedicated benchmark ECS host."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_COMMANDS = ("git", "python3", "uv", "docker", "codex")
DEFAULT_OPTIONAL_COMMANDS = ("node", "npm")
WORKSPACE_SUBDIRS = (
    "sources",
    "runs",
    "cache",
    "artifacts/public",
    "artifacts/private",
)


def _probe_version(command: str) -> dict[str, Any]:
    binary = shutil.which(command)
    payload: dict[str, Any] = {
        "command": command,
        "present": bool(binary),
        "version_probe_ok": False,
        "version_line": "",
    }
    if not binary:
        return payload

    version_args = [command, "--version"]
    try:
        completed = subprocess.run(
            version_args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return payload

    first_line = " ".join((completed.stdout or "").splitlines()[:1]).strip()
    payload["version_probe_ok"] = completed.returncode == 0
    payload["version_line"] = first_line[:160]
    return payload


def _probe_docker_server() -> dict[str, Any]:
    if not shutil.which("docker"):
        return {
            "command_present": False,
            "server_reachable": False,
            "server_version_present": False,
        }
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{json .ServerVersion}}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "command_present": True,
            "server_reachable": False,
            "server_version_present": False,
        }
    server_version = (completed.stdout or "").strip().strip('"')
    return {
        "command_present": True,
        "server_reachable": completed.returncode == 0,
        "server_version_present": bool(server_version),
    }


def _disk_probe(path: Path, min_free_gib: float) -> dict[str, Any]:
    probe_path = path
    while not probe_path.exists() and probe_path != probe_path.parent:
        probe_path = probe_path.parent
    usage = shutil.disk_usage(probe_path)
    free_gib = usage.free / (1024**3)
    total_gib = usage.total / (1024**3)
    return {
        "checked": True,
        "workspace_basename": path.name,
        "workspace_path_recorded": False,
        "free_gib": round(free_gib, 3),
        "total_gib": round(total_gib, 3),
        "min_free_gib": float(min_free_gib),
        "enough_free_disk": free_gib >= min_free_gib,
    }


def build_payload(
    *,
    workspace: Path,
    min_free_gib: float,
    required: list[str],
    optional: list[str],
    create_dirs: bool,
) -> dict[str, Any]:
    workspace = workspace.expanduser()
    if create_dirs:
        for subdir in WORKSPACE_SUBDIRS:
            (workspace / subdir).mkdir(parents=True, exist_ok=True)

    command_probes = {
        command: _probe_version(command) for command in required + optional
    }
    missing_required = [
        command
        for command in required
        if not command_probes.get(command, {}).get("present")
    ]
    docker_server = _probe_docker_server()
    disk = _disk_probe(workspace, min_free_gib)

    first_blocker = ""
    if missing_required:
        first_blocker = f"missing_required_command:{missing_required[0]}"
    elif not disk["enough_free_disk"]:
        first_blocker = "insufficient_free_disk"
    elif "docker" in required and not docker_server["server_reachable"]:
        first_blocker = "docker_server_unreachable"

    ready = not first_blocker
    return {
        "schema_version": "benchmark_ecs_bootstrap_probe_v0",
        "ready": ready,
        "first_blocker": first_blocker,
        "workspace": {
            "basename": workspace.name,
            "path_recorded": False,
            "created_dirs": bool(create_dirs),
            "layout": list(WORKSPACE_SUBDIRS),
        },
        "required_commands": required,
        "optional_commands": optional,
        "missing_required_commands": missing_required,
        "commands": command_probes,
        "docker_server": docker_server,
        "disk": disk,
        "operator_substrate": {
            "docker_registry_or_mirror_documented": "unknown",
            "network_proxy_or_tunnel_documented": "unknown",
            "source_materialization_policy_documented": "unknown",
            "dependency_prewarm_documented": "unknown",
        },
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_read": False,
            "private_paths_recorded": False,
            "network_proxy_values_recorded": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe cloud ECS benchmark-host readiness without recording private host details."
    )
    parser.add_argument(
        "--workspace",
        default="~/loopx-bench",
        help="Benchmark workspace root on the host. Only its basename is emitted.",
    )
    parser.add_argument("--min-free-gib", type=float, default=80.0)
    parser.add_argument(
        "--require",
        action="append",
        help="Required command. May be repeated; overrides the default required set.",
    )
    parser.add_argument(
        "--optional",
        action="append",
        help="Optional command. May be repeated; overrides the default optional set.",
    )
    parser.add_argument("--create-dirs", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    required = (
        args.require if args.require is not None else list(DEFAULT_REQUIRED_COMMANDS)
    )
    optional = (
        args.optional if args.optional is not None else list(DEFAULT_OPTIONAL_COMMANDS)
    )
    payload = build_payload(
        workspace=Path(args.workspace),
        min_free_gib=args.min_free_gib,
        required=required,
        optional=optional,
        create_dirs=args.create_dirs,
    )
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 1 if args.strict and not payload["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
