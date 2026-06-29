#!/usr/bin/env python3
"""Smoke-test the visible auto-research demo launcher without starting real TUI processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

GOAL_ID = "loopx-auto-research-knn"
LANES = [
    "codex-product-capability:research-curator:research_curator",
    "codex-side-bypass:hypothesis-mapper:hypothesis_mapper",
    "codex-main-control:evidence-runner:evidence_runner",
    "codex-value-explorer:evidence-verifier:evidence_verifier",
]


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        tmux_log = temp / "tmux.jsonl"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        write_executable(
            fake_bin / "tmux",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "with open(os.environ['FAKE_TMUX_LOG'], 'a', encoding='utf-8') as f:",
                    "    f.write(json.dumps(sys.argv[1:]) + '\\n')",
                    "if len(sys.argv) > 1 and sys.argv[1] == 'has-session':",
                    "    raise SystemExit(1)",
                    "raise SystemExit(0)",
                    "",
                ]
            ),
        )
        write_executable(fake_bin / "loopx", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "codex", "#!/usr/bin/env sh\nexit 0\n")

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["FAKE_TMUX_LOG"] = str(tmux_log)
        workspace = temp / "visible-workspace"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "auto-research",
                "demo-supervisor",
                "--goal-id",
                GOAL_ID,
                "--session-name",
                "loopx-auto-research-smoke",
                "--agent",
                LANES[0],
                "--agent",
                LANES[1],
                "--agent",
                LANES[2],
                "--agent",
                LANES[3],
                "--execute",
                "--launcher",
                "tmux",
                "--workspace",
                str(workspace),
                "--create-workspace",
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["mode"] == "executed_visible_launch", payload
        assert payload["boundary"]["starts_tmux"] is True, payload
        assert payload["boundary"]["runs_codex"] is True, payload
        assert payload["boundary"]["writes_loopx_state"] is False, payload
        assert payload["boundary"]["spends_loopx_quota"] is False, payload
        assert payload["boundary"]["workspace_mode"] == "explicit_workspace", payload
        assert payload["boundary"]["workspace_write_scope"] == "user_selected_workspace_only", payload
        assert payload["boundary"]["shared_state_route"] == "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT", payload
        launch = payload["launch_result"]
        assert launch["launcher"] == "tmux", launch
        assert launch["started_lane_count"] == 4, launch
        assert launch["attach_command"] == "tmux attach -t loopx-auto-research-smoke", launch
        assert launch["stop_command"] == "tmux kill-session -t loopx-auto-research-smoke", launch
        assert launch["workspace_mode"] == "explicit_workspace", launch
        assert workspace.is_dir(), workspace

        for lane in payload["lanes"]:
            profile = lane["role_profile"]
            assert profile["schema_version"] == "auto_research_role_profile_v0", profile
            assert profile["role_id"] == lane["role_id"], profile
            assert profile["required_skill"] == "loopx-auto-research", profile
            assert profile["write_scope"], profile
            assert profile["protected_scope"], profile
            assert profile["stop_conditions"], profile
            command = lane["visible_launch_command"]
            assert profile["schema_version"] == "auto_research_role_profile_v0", profile
            assert profile["required_skill"] == "loopx-auto-research", profile
            assert profile["agent_id"] == lane["agent_id"], profile
            assert profile["lane_id"] == lane["lane_id"], profile
            assert profile["stop_conditions"], profile
            assert "[LoopX role profile]" in command, command
            assert "LOOPX_ROLE_PROFILE_JSON" in command, command
            assert "LOOPX_ROLE_ID" in command, command
            assert "LOOPX_ROLE_PROFILE_REF" in command, command
            assert "LOOPX_REQUIRED_SKILL" in command, command
            assert "quota should-run" in command, command
            assert "auto-research frontier" in command, command
            assert "codex-cli-bootstrap-message" in command, command
            assert 'exec codex "$BOOTSTRAP_PROMPT"' in command, command

        log_entries = [json.loads(line) for line in tmux_log.read_text(encoding="utf-8").splitlines()]
        assert log_entries[0][:1] == ["has-session"], log_entries
        assert any(entry[:1] == ["new-session"] for entry in log_entries), log_entries
        assert sum(1 for entry in log_entries if entry[:1] == ["new-window"]) == 4, log_entries
        assert_public_safe(payload)

    print("auto-research-visible-launcher-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
