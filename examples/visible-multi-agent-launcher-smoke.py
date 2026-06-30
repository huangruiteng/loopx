#!/usr/bin/env python3
"""Smoke-test the reusable visible multi-agent launcher seam."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.visible_multi_agent_launcher import execute_visible_multi_agent_launcher  # noqa: E402


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def main() -> int:
    auto_research_cli = (ROOT / "loopx/capabilities/auto_research/cli.py").read_text(
        encoding="utf-8"
    )
    assert "from ...visible_multi_agent_launcher import execute_visible_multi_agent_launcher" in auto_research_cli
    forbidden_defs = [
        "def _launch_auto_research_with_tmux",
        "def _tmux_visible_launch_acceptance",
        "def _resolve_demo_workspace",
        "def _resolve_auto_research_launcher",
    ]
    leaked_defs = [name for name in forbidden_defs if name in auto_research_cli]
    assert not leaked_defs, leaked_defs

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        workspace = temp / "workspace"
        tmux_log = temp / "tmux.jsonl"
        worker_skill = temp / "worker" / "SKILL.md"
        worker_skill.parent.mkdir(parents=True)
        worker_skill.write_text("# Worker-local playbook\n", encoding="utf-8")
        registry.write_text(json.dumps({"common_runtime_root": str(runtime_root)}), encoding="utf-8")
        write_executable(fake_bin / "loopx", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "codex", "#!/usr/bin/env sh\nexit 0\n")
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
                    "if len(sys.argv) > 1 and sys.argv[1] == 'list-windows':",
                    "    print('planner\\nreviewer')",
                    "    raise SystemExit(0)",
                    "if len(sys.argv) > 1 and sys.argv[1] == 'capture-pane':",
                    "    print('[LoopX visible acceptance]')",
                    "    print('[LoopX role profile]')",
                    "    print('[LoopX quota guard]')",
                    "    print('[LoopX frontier]')",
                    "    print('[bootstrap-or-stop]')",
                    "    print('loopx_agent_handshake=role_profile_quota_frontier_bootstrap')",
                    "    raise SystemExit(0)",
                    "raise SystemExit(0)",
                    "",
                ]
            ),
        )

        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_bin}{os.pathsep}{original_path}"
        os.environ["FAKE_TMUX_LOG"] = str(tmux_log)
        try:
            launch, chosen, workspace_mode = execute_visible_multi_agent_launcher(
                payload={
                    "session_name": "loopx-visible-launcher-smoke",
                    "lanes": [
                        {"lane_id": "planner", "frontier": "true", "visible_launch_command": "true"},
                        {
                            "lane_id": "reviewer",
                            "visible_launch_command": "true",
                            "role_profile": {
                                "required_skill": "loopx-auto-research",
                                "worker_skill_source": "worker/SKILL.md",
                            },
                        },
                    ],
                },
                registry=registry,
                runtime_root=runtime_root,
                requested_launcher="tmux",
                tmux_bin="tmux",
                cli_bin="loopx",
                codex_bin="codex",
                attach=False,
                replace_existing=False,
                workspace=str(workspace),
                create_workspace=True,
                cwd=temp,
            )
        finally:
            os.environ["PATH"] = original_path
            os.environ.pop("FAKE_TMUX_LOG", None)

        assert chosen == "tmux", launch
        assert workspace_mode == "explicit_workspace", launch
        assert workspace.is_dir(), workspace
        assert launch["schema_version"] == "multi_agent_visible_launch_result_v0", launch
        skills = launch["worker_skill_materialization"]
        assert skills == [
            {
                "skill": "loopx-auto-research",
                "source": "worker/SKILL.md",
                "destination": ".codex/skills/loopx-auto-research/SKILL.md",
                "materialized": True,
                "workspace_count": 1,
            }
        ], skills
        assert (workspace / ".codex/skills/loopx-auto-research/SKILL.md").read_text(
            encoding="utf-8"
        ) == "# Worker-local playbook\n"
        assert launch["started_lanes"] == ["planner", "reviewer"], launch
        assert launch["surviving_lanes"] == ["planner", "reviewer"], launch
        assert launch["script_mode"] == "runtime_local_files", launch
        assert launch["launcher_script_count"] == 3, launch
        acceptance = launch["visible_acceptance"]
        assert acceptance["schema_version"] == "multi_agent_visible_launch_acceptance_v0", acceptance
        assert acceptance["accepted"] is True, acceptance
        assert acceptance["missing_lanes"] == [], acceptance
        assert all(item["accepted"] for item in acceptance["pane_checks"]), acceptance
        log_entries = [json.loads(line) for line in tmux_log.read_text(encoding="utf-8").splitlines()]
        assert any(entry[:1] == ["new-session"] for entry in log_entries), log_entries
        assert sum(1 for entry in log_entries if entry[:1] == ["new-window"]) == 2, log_entries
        tmux_starts = [entry for entry in log_entries if entry[:1] in (["new-session"], ["new-window"])]
        assert all("-lc" not in entry for entry in tmux_starts), tmux_starts

    print("visible-multi-agent-launcher-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
