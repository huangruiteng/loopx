#!/usr/bin/env python3
"""Build a Terminal-Bench task image with runner-required utilities."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "terminal_bench_task_image_bootstrap_v0"
DEFAULT_APT_MIRROR = "https://mirrors.tuna.tsinghua.edu.cn/debian"
DEFAULT_SECURITY_MIRROR = "https://mirrors.tuna.tsinghua.edu.cn/debian-security"


def _dockerfile(
    *,
    source_image: str,
    apt_packages: list[str],
    apt_mirror: str,
    security_mirror: str,
) -> str:
    packages = " ".join(apt_packages)
    return f"""FROM {source_image}
RUN sed -i \\
      -e "s|URIs: http://deb.debian.org/debian-security|URIs: {security_mirror}|" \\
      -e "s|URIs: http://deb.debian.org/debian|URIs: {apt_mirror}|" \\
      /etc/apt/sources.list.d/debian.sources \\
 && apt-get -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \\
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends {packages} \\
 && rm -rf /var/lib/apt/lists/*
"""


def _run(command: list[str], *, timeout_sec: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_sec,
    )


def build_plan(
    *,
    source_image: str,
    target_image: str,
    work_dir: Path,
    apt_packages: list[str],
    required_commands: list[str],
    apt_mirror: str,
    security_mirror: str,
    execute: bool,
    timeout_sec: int,
    use_host_network: bool,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    dockerfile = _dockerfile(
        source_image=source_image,
        apt_packages=apt_packages,
        apt_mirror=apt_mirror,
        security_mirror=security_mirror,
    )
    dockerfile_path = work_dir / "Dockerfile"
    dockerfile_path.write_text(dockerfile, encoding="utf-8")

    build_command = ["docker", "build"]
    if use_host_network:
        build_command.extend(["--network", "host"])
    build_command.extend(["-t", target_image, str(work_dir)])

    first_blocker = ""
    build_returncode: int | None = None
    command_checks: dict[str, bool] = {}
    if execute:
        try:
            build_result = _run(build_command, timeout_sec=timeout_sec)
            build_returncode = build_result.returncode
        except subprocess.TimeoutExpired:
            first_blocker = "terminal_bench_task_image_bootstrap_timeout"
        except subprocess.CalledProcessError as exc:
            build_returncode = exc.returncode
            first_blocker = "terminal_bench_task_image_bootstrap_failed"
        if not first_blocker:
            for command in required_commands:
                check = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        target_image,
                        "sh",
                        "-lc",
                        f"command -v {command} >/dev/null",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                command_checks[command] = check.returncode == 0
            if not all(command_checks.values()):
                first_blocker = "terminal_bench_task_image_required_command_missing"

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not first_blocker,
        "first_blocker": first_blocker,
        "execute": execute,
        "source_image": source_image,
        "target_image": target_image,
        "work_dir_basename": work_dir.name,
        "private_work_dir_recorded": False,
        "apt_packages": apt_packages,
        "required_commands": required_commands,
        "apt_mirror_host": apt_mirror.split("/")[2] if "://" in apt_mirror else apt_mirror,
        "security_mirror_host": (
            security_mirror.split("/")[2] if "://" in security_mirror else security_mirror
        ),
        "use_host_network": use_host_network,
        "timeout_sec": timeout_sec,
        "build_returncode": build_returncode,
        "command_checks": command_checks,
        "contract": {
            "score_or_task_behavior_changed": False,
            "runner_surface_changed": "task_image_startup_prerequisites_only",
            "case_runtime_agent_install_forbidden": True,
        },
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "private_paths_recorded": False,
            "credential_values_read": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap a Terminal-Bench task image with runner utilities."
    )
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--target-image", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument(
        "--apt-package",
        action="append",
        default=None,
        help=(
            "A package to install into the derived task image. May be repeated; "
            "defaults to tmux and asciinema when omitted."
        ),
    )
    parser.add_argument(
        "--required-command",
        action="append",
        default=None,
        help=(
            "A command that must be present after the build. May be repeated; "
            "defaults to tmux and asciinema when omitted."
        ),
    )
    parser.add_argument("--apt-mirror", default=DEFAULT_APT_MIRROR)
    parser.add_argument("--security-mirror", default=DEFAULT_SECURITY_MIRROR)
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument("--network-host", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_plan(
        source_image=args.source_image,
        target_image=args.target_image,
        work_dir=Path(args.work_dir),
        apt_packages=args.apt_package or ["tmux", "asciinema"],
        required_commands=args.required_command or ["tmux", "asciinema"],
        apt_mirror=args.apt_mirror,
        security_mirror=args.security_mirror,
        execute=args.execute,
        timeout_sec=args.timeout_sec,
        use_host_network=args.network_host,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
