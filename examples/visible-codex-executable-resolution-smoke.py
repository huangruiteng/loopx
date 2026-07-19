#!/usr/bin/env python3
"""Smoke-test durable Codex executable selection for visible agents."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.control_plane.agents.multi_agent.codex_executable import (  # noqa: E402
    resolve_codex_executable,
    write_codex_compatibility_shim,
)


def write_codex(path: Path, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        f"if [ \"${{1:-}}\" = --version ]; then echo 'codex-cli {version}'; exit 0; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def version_order(version: str) -> tuple[int, int, int, int, str]:
    release, separator, prerelease = version.partition("-")
    major, minor, patch = (int(part) for part in release.split("."))
    return major, minor, patch, 1 if not separator else 0, prerelease


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-codex-resolution-smoke.") as tmp:
        temp = Path(tmp)
        path_bin = temp / "path-bin"
        home = temp / "home"
        old_codex = path_bin / "codex"
        new_codex = home / ".npm-global" / "bin" / "codex"
        explicit = temp / "explicit-codex"
        write_codex(old_codex, "0.142.0-alpha.7")
        write_codex(new_codex, "0.144.1")
        write_codex(explicit, "0.141.0")
        env = {
            "PATH": str(path_bin),
            "HOME": str(home),
        }

        selected, packet = resolve_codex_executable("codex", env=env)
        assert packet["selection_policy"] == (
            "newest_version_across_host_candidates"
        ), packet
        candidates = [
            item for item in packet["candidate_versions"] if item["version"]
        ]
        expected = max(candidates, key=lambda item: version_order(item["version"]))
        assert packet["selected_source"] == expected["source"], packet
        assert packet["selected_version"] == expected["version"], packet
        expected_paths = {
            "path": old_codex,
            "user_npm_global": new_codex,
            "chatgpt_app_bundle": Path(
                "/Applications/ChatGPT.app/Contents/Resources/codex"
            ),
        }
        assert Path(selected) == expected_paths[expected["source"]], (selected, packet)
        candidate_versions = {
            item["source"]: item["version"] for item in candidates
        }
        assert candidate_versions["path"] == "0.142.0-alpha.7", packet
        assert candidate_versions["user_npm_global"] == "0.144.1", packet
        assert packet["path_default_bypassed"] is True, packet
        assert packet["path_frozen"] is True, packet
        assert packet["candidate_count"] >= 2, packet

        selected_explicit, explicit_packet = resolve_codex_executable(
            str(explicit), env=env
        )
        assert Path(selected_explicit) == explicit, explicit_packet
        assert explicit_packet["selection_policy"] == "explicit_authoritative"
        assert explicit_packet["selected_version"] == "0.141.0"

        shim = write_codex_compatibility_shim(
            directory=temp / "shim-bin",
            executable=str(explicit),
        )
        assert shim.name == "codex" and os.access(shim, os.X_OK), shim
        assert str(explicit) in shim.read_text(encoding="utf-8"), shim

        public_packet = json.dumps(packet, sort_keys=True)
        assert str(temp) not in public_packet, public_packet
        assert not public_packet.startswith("/"), public_packet

    print("visible-codex-executable-resolution-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
