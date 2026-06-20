#!/usr/bin/env python3
"""Smoke-test Harbor preinstalled agent-tools bundle materialization."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "harbor_agent_tools_bundle.py"


def _fake_executable(path: Path, output: str) -> None:
    path.write_text(f"#!/usr/bin/env sh\necho {output!r}\n", encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gh-harbor-agent-tools-") as tmp:
        root = Path(tmp)
        src = root / "src"
        out = root / "bundle"
        src.mkdir()
        codex = src / "codex-native"
        rg = src / "rg"
        curl = src / "curl"
        _fake_executable(codex, "codex-cli 0.test")
        _fake_executable(rg, "ripgrep 0.test")
        _fake_executable(curl, "curl 0.test")

        completed = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--output",
                str(out),
                "--codex-native-bin",
                str(codex),
                "--rg-bin",
                str(rg),
                "--curl-bin",
                str(curl),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = json.loads(completed.stdout)

        assert payload["ready"] is True, payload
        assert payload["first_blocker"] == "", payload
        assert payload["output"]["mount_target"] == "/opt/harbor-agent-tools", payload
        assert payload["output"]["path_recorded"] is False, payload
        assert payload["boundary"]["raw_task_text_read"] is False, payload
        assert payload["boundary"]["credential_values_read"] is False, payload
        assert set(payload["files"]) == {"codex", "codex-real", "curl", "rg"}, payload
        assert all(item["ok"] for item in payload["verification"]), payload

        wrapper = (out / "bin" / "codex").read_text(encoding="utf-8")
        assert "CODEX_OPENAI_PROXY" in wrapper, wrapper
        assert "127.0.0.1" not in wrapper, wrapper

    print("harbor-agent-tools-bundle smoke passed")


if __name__ == "__main__":
    main()
