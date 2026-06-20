#!/usr/bin/env python3
"""Materialize a SkillsBench BenchFlow agent runtime layer.

SkillsBench cases should not download Node.js or install the ACP agent inside
every task container.  This helper builds a host-side runtime directory that can
be mounted read-only at ``/opt/benchflow`` before a case starts.

The helper is intentionally offline by default.  Feed it cached sources from
the host, a local artifact cache, or an operator-provided archive.  Network
fetching belongs outside the case container and should be recorded separately as
host bootstrap evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "skillsbench_agent_runtime_layer_v0"
DEFAULT_OUTPUT = "~/goal-harness-bench/benchflow-agent-runtime"
MOUNT_TARGET = "/opt/benchflow"
DEFAULT_CODEX_ACP_PACKAGE = "@agentclientprotocol/codex-acp"
DEFAULT_CODEX_ACP_VERSION = "0.0.45"


def _copytree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=True)


def _safe_extract_tarball(tarball: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball) as archive:
        members = archive.getmembers()
        for member in members:
            destination = (target / member.name).resolve()
            if not str(destination).startswith(str(target.resolve())):
                raise ValueError(f"unsafe tar member: {member.name}")
        archive.extractall(target, members=members)
    dirs = [path for path in target.iterdir() if path.is_dir()]
    if len(dirs) == 1 and (dirs[0] / "bin" / "node").exists():
        return dirs[0]
    return target


def _write_layer_wrapper(path: Path, relative_executable: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "DIR=$(CDPATH= cd -- \"$(dirname -- \"$0\")/..\" && pwd)\n"
        f"if [ -x \"$DIR/{relative_executable}\" ]; then\n"
        f"  exec \"$DIR/{relative_executable}\" \"$@\"\n"
        "fi\n"
        f"exec \"{MOUNT_TARGET}/{relative_executable}\" \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _copy_executable(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(target.stat().st_mode | 0o111)


def _probe(bin_dir: Path, command: str, *args: str) -> dict[str, Any]:
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    try:
        completed = subprocess.run(
            [command, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"command": command, "ok": False, "version_line": ""}
    version_line = " ".join((completed.stdout or "").splitlines()[:1]).strip()
    return {
        "command": command,
        "ok": completed.returncode == 0,
        "version_line": version_line[:160],
    }


def _install_codex_acp_package(
    *,
    npm_bin: Path,
    package: str,
    target_prefix: Path,
) -> dict[str, Any]:
    target_prefix.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            str(npm_bin),
            "install",
            "--prefix",
            str(target_prefix),
            "--no-audit",
            "--no-fund",
            package,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=300,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "output_first_line": " ".join((completed.stdout or "").splitlines()[:1])[:160],
    }


def build_layer(
    *,
    output: Path,
    node_root: Path | None,
    node_tarball: Path | None,
    codex_acp_bin: Path | None,
    codex_acp_package: Path | str | None,
    verify: bool,
) -> dict[str, Any]:
    output = output.expanduser()
    bin_dir = output / "bin"
    node_target = output / "node"
    js_agents_target = output / "js-agents"

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ready": False,
        "first_blocker": "",
        "output": {
            "basename": output.name,
            "path_recorded": False,
            "mount_target": MOUNT_TARGET,
        },
        "inputs": {
            "node_root_found": node_root is not None and node_root.exists(),
            "node_tarball_found": node_tarball is not None and node_tarball.is_file(),
            "codex_acp_bin_found": (
                codex_acp_bin is not None and codex_acp_bin.is_file()
            ),
            "codex_acp_package": str(codex_acp_package)
            if codex_acp_package
            else "",
        },
        "required_tools": ["node", "npm", "codex-acp"],
        "files": [],
        "verification": [],
        "install": {
            "npm_install_attempted": False,
            "npm_install_ok": None,
            "npm_install_output_first_line": "",
        },
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_read": False,
            "private_paths_recorded": False,
        },
    }

    if node_root and node_root.exists():
        _copytree(node_root.expanduser(), node_target)
    elif node_tarball and node_tarball.is_file():
        extracted = _safe_extract_tarball(node_tarball.expanduser(), output / ".node-extract")
        _copytree(extracted, node_target)
        shutil.rmtree(output / ".node-extract", ignore_errors=True)
    else:
        payload["first_blocker"] = "missing_node_runtime_source"
        return payload

    node_bin = node_target / "bin" / "node"
    npm_bin = node_target / "bin" / "npm"
    if not node_bin.exists():
        payload["first_blocker"] = "missing_node_bin"
        return payload
    if not npm_bin.exists():
        payload["first_blocker"] = "missing_npm_bin"
        return payload

    _write_layer_wrapper(bin_dir / "node", "node/bin/node")
    _write_layer_wrapper(bin_dir / "npm", "node/bin/npm")

    if codex_acp_bin and codex_acp_bin.is_file():
        _copy_executable(codex_acp_bin.expanduser(), bin_dir / "codex-acp")
    else:
        package_spec = codex_acp_package
        if package_spec is None:
            payload["first_blocker"] = "missing_codex_acp_runtime_source"
            return payload
        if isinstance(package_spec, Path):
            package_spec = str(package_spec.expanduser())
        payload["install"]["npm_install_attempted"] = True
        install = _install_codex_acp_package(
            npm_bin=bin_dir / "npm",
            package=str(package_spec),
            target_prefix=js_agents_target,
        )
        payload["install"]["npm_install_ok"] = install["ok"]
        payload["install"]["npm_install_output_first_line"] = install[
            "output_first_line"
        ]
        if not install["ok"]:
            payload["first_blocker"] = "codex_acp_package_install_failed"
            return payload
        acp_bin = js_agents_target / "node_modules" / ".bin" / "codex-acp"
        if not acp_bin.exists():
            payload["first_blocker"] = "missing_codex_acp_bin_after_install"
            return payload
        _write_layer_wrapper(
            bin_dir / "codex-acp",
            "js-agents/node_modules/.bin/codex-acp",
        )

    payload["files"] = sorted(path.name for path in bin_dir.iterdir() if path.is_file())
    if verify:
        payload["verification"] = [
            _probe(bin_dir, "node", "--version"),
            _probe(bin_dir, "npm", "--version"),
            _probe(bin_dir, "codex-acp", "--version"),
        ]
        if not payload["verification"][-1]["ok"]:
            payload["verification"][-1] = _probe(bin_dir, "codex-acp", "--help")
        failed = [
            probe["command"]
            for probe in payload["verification"]
            if not probe.get("ok")
        ]
        if failed:
            payload["first_blocker"] = f"verification_failed:{failed[0]}"
            return payload

    payload["ready"] = True
    payload["first_blocker"] = ""
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a BenchFlow /opt/benchflow agent runtime layer for "
            "SkillsBench cases from cached host-side runtime sources."
        )
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--node-root")
    parser.add_argument("--node-tarball")
    parser.add_argument("--codex-acp-bin")
    parser.add_argument("--codex-acp-package")
    parser.add_argument(
        "--use-default-codex-acp-package",
        action="store_true",
        help=(
            "Install @agentclientprotocol/codex-acp from the host npm registry "
            "once into the layer. This may use network on the host, never "
            "inside the case container."
        ),
    )
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    codex_acp_package: Path | str | None = None
    if args.codex_acp_package:
        codex_acp_package = Path(args.codex_acp_package)
    elif args.use_default_codex_acp_package:
        codex_acp_package = (
            f"{DEFAULT_CODEX_ACP_PACKAGE}@{DEFAULT_CODEX_ACP_VERSION}"
        )

    payload = build_layer(
        output=Path(args.output),
        node_root=Path(args.node_root).expanduser() if args.node_root else None,
        node_tarball=Path(args.node_tarball).expanduser()
        if args.node_tarball
        else None,
        codex_acp_bin=Path(args.codex_acp_bin).expanduser()
        if args.codex_acp_bin
        else None,
        codex_acp_package=codex_acp_package,
        verify=not args.no_verify,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
