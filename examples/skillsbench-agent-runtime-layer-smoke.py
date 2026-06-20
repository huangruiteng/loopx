#!/usr/bin/env python3
"""Smoke-test SkillsBench BenchFlow agent runtime layer materialization."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "skillsbench_agent_runtime_layer.py"


def _fake_executable(path: Path, output: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env sh\necho {output!r}\n", encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-runtime-") as tmp:
        root = Path(tmp)
        node_root = root / "node-v22.test-linux-x64"
        _fake_executable(node_root / "bin" / "node", "v22.20.0")
        _fake_executable(node_root / "bin" / "npm", "10.9.0")
        codex_acp = root / "src" / "codex-acp"
        _fake_executable(codex_acp, "codex-acp 0.test")

        output = root / "benchflow-agent-runtime"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(output),
                "--node-root",
                str(node_root),
                "--codex-acp-bin",
                str(codex_acp),
                "--pretty",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = json.loads(completed.stdout)

        assert payload["schema_version"] == "skillsbench_agent_runtime_layer_v0"
        assert payload["ready"] is True, payload
        assert payload["first_blocker"] == "", payload
        assert payload["output"]["mount_target"] == "/opt/benchflow", payload
        assert payload["output"]["path_recorded"] is False, payload
        assert payload["required_tools"] == ["node", "npm", "codex-acp"], payload
        assert set(payload["files"]) == {"codex-acp", "node", "npm"}, payload
        assert all(item["ok"] for item in payload["verification"]), payload
        assert payload["install"]["npm_install_attempted"] is False, payload
        assert payload["boundary"]["raw_logs_read"] is False, payload
        assert payload["boundary"]["credential_values_read"] is False, payload
        node_wrapper = (output / "bin" / "node").read_text(encoding="utf-8")
        assert str(root) not in node_wrapper, node_wrapper
        assert "/opt/benchflow/node/bin/node" in node_wrapper, node_wrapper

        missing = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(root / "missing"),
                "--codex-acp-bin",
                str(codex_acp),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert missing.returncode == 1, missing.stdout
        missing_payload = json.loads(missing.stdout)
        assert (
            missing_payload["first_blocker"] == "missing_node_runtime_source"
        ), missing_payload

    print("skillsbench-agent-runtime-layer smoke passed")


if __name__ == "__main__":
    main()
