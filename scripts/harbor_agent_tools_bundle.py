#!/usr/bin/env python3
"""Build a public-safe Harbor preinstalled agent-tools bundle.

The bundle is intended to be mounted read-only into Harbor task containers at
``/opt/harbor-agent-tools``. Harbor's preinstalled Codex agent variants then
find ``codex`` and ``rg`` on PATH without downloading nvm, npm packages, or
Codex inside each benchmark container. ``curl`` is optional because dynamic
host curl binaries are often not portable across task images.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "~/loopx-bench/harbor-agent-tools"
CODEX_VENDOR_CANDIDATES = (
    "/usr/local/lib/node_modules/@openai/codex/node_modules/"
    "@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex",
)
RG_VENDOR_CANDIDATES = (
    "/usr/local/lib/node_modules/@openai/codex/node_modules/"
    "@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex-path/rg",
    "/usr/local/lib/node_modules/@openai/codex/node_modules/"
    "@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/path/rg",
)


def _first_existing(paths: list[str] | tuple[str, ...]) -> Path | None:
    for path in paths:
        candidate = Path(path).expanduser()
        if candidate.is_file():
            return candidate
    return None


def _which(command: str) -> Path | None:
    resolved = shutil.which(command)
    return Path(resolved) if resolved else None


def _discover_codex_native(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    return _first_existing(CODEX_VENDOR_CANDIDATES)


def _discover_rg(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    return _which("rg") or _first_existing(RG_VENDOR_CANDIDATES)


def _copy_executable(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(target.stat().st_mode | 0o111)


def _write_codex_wrapper(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${CODEX_OPENAI_PROXY:-}" ] \\
  && [ -z "${HTTPS_PROXY:-}${https_proxy:-}${ALL_PROXY:-}${all_proxy:-}" ]; then
  export HTTP_PROXY="${CODEX_OPENAI_PROXY}"
  export HTTPS_PROXY="${CODEX_OPENAI_PROXY}"
  export ALL_PROXY="${CODEX_OPENAI_PROXY}"
  export http_proxy="${CODEX_OPENAI_PROXY}"
  export https_proxy="${CODEX_OPENAI_PROXY}"
  export all_proxy="${CODEX_OPENAI_PROXY}"
fi
exec "$DIR/codex-real" "$@"
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _probe_command(bin_dir: Path, command: str) -> dict[str, Any]:
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    try:
        completed = subprocess.run(
            [command, "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=8,
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


def build_bundle(
    *,
    output: Path,
    codex_native: Path | None,
    rg: Path | None,
    curl: Path | None,
    include_curl: bool,
    verify: bool,
) -> dict[str, Any]:
    output = output.expanduser()
    bin_dir = output / "bin"
    missing: list[str] = []
    for name, path in (
        ("codex_native", codex_native),
        ("rg", rg),
    ):
        if path is None or not path.is_file():
            missing.append(name)
    if include_curl and (curl is None or not curl.is_file()):
        missing.append("curl")

    payload: dict[str, Any] = {
        "schema_version": "harbor_agent_tools_bundle_v0",
        "ready": False,
        "first_blocker": f"missing_{missing[0]}" if missing else "",
        "output": {
            "basename": output.name,
            "path_recorded": False,
            "mount_target": "/opt/harbor-agent-tools",
        },
        "inputs": {
            "codex_native_found": codex_native is not None and codex_native.is_file(),
            "rg_found": rg is not None and rg.is_file(),
            "curl_found": curl is not None and curl.is_file(),
            "include_curl": include_curl,
        },
        "required_tools": ["codex", "rg"],
        "optional_tools": ["curl"],
        "files": [],
        "verification": [],
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_read": False,
            "private_paths_recorded": False,
        },
    }
    if missing:
        return payload

    assert codex_native is not None
    assert rg is not None
    _copy_executable(codex_native, bin_dir / "codex-real")
    _copy_executable(rg, bin_dir / "rg")
    if include_curl:
        assert curl is not None
        _copy_executable(curl, bin_dir / "curl")
    _write_codex_wrapper(bin_dir / "codex")

    payload["files"] = sorted(path.name for path in bin_dir.iterdir() if path.is_file())
    if verify:
        payload["verification"] = [
            _probe_command(bin_dir, "codex"),
            _probe_command(bin_dir, "rg"),
        ]
        if include_curl:
            payload["verification"].append(_probe_command(bin_dir, "curl"))
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
            "Create a Harbor /opt/harbor-agent-tools bundle so benchmark "
            "containers can use preinstalled Codex tools without per-case "
            "nvm/npm downloads."
        )
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--codex-native-bin")
    parser.add_argument("--rg-bin")
    parser.add_argument("--curl-bin")
    parser.add_argument(
        "--include-curl",
        action="store_true",
        help=(
            "Also copy curl into the bundle. By default curl is optional "
            "because host dynamic curl binaries are often not portable across "
            "benchmark task images."
        ),
    )
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_bundle(
        output=Path(args.output),
        codex_native=_discover_codex_native(args.codex_native_bin),
        rg=_discover_rg(args.rg_bin),
        curl=Path(args.curl_bin).expanduser()
        if args.curl_bin
        else _which("curl"),
        include_curl=args.include_curl,
        verify=not args.no_verify,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
