#!/usr/bin/env python3
"""Smoke-test the reusable visible multi-agent launcher seam."""

from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.visible_multi_agent_launcher import (  # noqa: E402
    _SCOPED_LOOPX_WRAPPER_PY,
    _VISIBLE_CODEX_STREAM_FILTER_PY,
    build_visible_multi_agent_payload,
    execute_visible_multi_agent_launcher,
)


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def run_with_pty(command: list[str], *, env: dict[str, str]) -> tuple[int, str]:
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        chunks: list[bytes] = []
        while True:
            ready, _, _ = select.select([master], [], [], 0.2)
            if master in ready:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    data = b""
                if data:
                    chunks.append(data)
            if proc.poll() is not None:
                while True:
                    try:
                        data = os.read(master, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                return proc.returncode or 0, b"".join(chunks).decode(errors="replace")
    finally:
        try:
            os.close(master)
        except OSError:
            pass


def main() -> int:
    auto_research_cli = (ROOT / "loopx/capabilities/auto_research/cli.py").read_text(
        encoding="utf-8"
    )
    launcher_source = (ROOT / "loopx/visible_multi_agent_launcher.py").read_text(
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
    assert "demo_local_wrapper" not in launcher_source
    assert "loopx_cli_scope=scoped_loopx_wrapper" in launcher_source
    assert "LOOPX_PANE_LOOPX_JSON" in launcher_source
    assert "LOOPX_VISIBLE_FORCE_MARKDOWN" in launcher_source
    assert "format=markdown; machine_json_wrapper=$LOOPX_PANE_LOOPX_JSON" in launcher_source
    assert "LoopX machine JSON hidden" in launcher_source
    assert "LOOPX_ALLOW_TTY_JSON" in launcher_source
    assert "stat.S_ISREG" in launcher_source
    assert "LOOPX_MACHINE_JSON=1 explicitly" in launcher_source
    assert "human_stream_contract=role_todo_progress_codex_stream" in launcher_source
    assert "machine_json_policy=file_or_explicit_machine_channel_only" in launcher_source
    assert 'FRONTIER_ARTIFACT_NAME="frontier.public.json"' in launcher_source
    assert 'artifact=%s\\\\n" "$FRONTIER_STATUS" "$FRONTIER_ARTIFACT_NAME"' in launcher_source
    assert 'artifact=%s\\\\n" "$FRONTIER_STATUS" "$FRONTIER_ARTIFACT"' not in launcher_source
    assert "_VISIBLE_CODEX_STREAM_FILTER_PY" in launcher_source
    assert "worker-local skill block hidden" in launcher_source
    assert " WARN codex_core_" in launcher_source

    slash = "/"
    private_tmp = slash + "private" + slash + "tmp"
    var_folders = slash + "var" + slash + "folders"
    filtered = subprocess.run(
        [sys.executable, "-u", "-c", _VISIBLE_CODEX_STREAM_FILTER_PY],
        input=(
            "OpenAI Codex v0\n"
            "user\n"
            "hidden bootstrap prompt\n"
            "codex\n"
            "codex says hello\n"
            "2026-01-01T00:00:00Z  WARN codex_core_plugins::manifest: noisy\n"
            f"exec in {private_tmp}/loopx-demo/path\n"
            "BEGIN_SKILL\nhidden skill body\nEND_SKILL\n"
            f"result saved under {var_folders}/demo/file\n"
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "codex says hello" in filtered, filtered
    assert "hidden bootstrap prompt" not in filtered, filtered
    assert "WARN codex_core" not in filtered, filtered
    assert "hidden skill body" not in filtered, filtered
    assert private_tmp not in filtered, filtered
    assert var_folders not in filtered, filtered
    assert "<local-path>" in filtered, filtered

    dry_packet = build_visible_multi_agent_payload(
        goal_id="loopx-meta",
        session_name="loopx-visible-launcher-contract-smoke",
        lanes=[
            {
                "lane_id": "planner",
                "frontier": "true",
                "visible_launch_command": "true",
            }
        ],
    )
    assert dry_packet["commands"]["attach"] == "tmux attach -t loopx-visible-launcher-contract-smoke"
    assert dry_packet["commands"]["stop"] == "tmux kill-session -t loopx-visible-launcher-contract-smoke"
    assert "retry" in dry_packet["commands"], dry_packet
    assert (
        dry_packet["human_stream_contract"]["schema_version"]
        == "multi_agent_visible_human_stream_contract_v0"
    ), dry_packet
    assert dry_packet["human_stream_contract"]["machine_json_policy"] == (
        "file_or_explicit_machine_channel_only"
    ), dry_packet
    assert dry_packet["human_stream_contract"]["codex_stream"] == (
        "public_filtered_stdout_stderr_visible_below_bootstrap"
    ), dry_packet
    assert dry_packet["acceptance"]["machine_json_file_bound"] is True, dry_packet
    assert dry_packet["acceptance"]["codex_stream_visible"] is True, dry_packet
    assert dry_packet["acceptance"]["codex_stream_public_filter"] is True, dry_packet
    assert dry_packet["boundary"]["hidden_prompt_injection"] is False, dry_packet
    assert dry_packet["boundary"]["spends_loopx_quota"] is False, dry_packet

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        workspace = temp / "workspace"
        tmux_log = temp / "tmux.jsonl"
        worker_skill = temp / "worker" / "SKILL.md"
        wrapper_arg_log = temp / "wrapper-args.jsonl"
        worker_skill.parent.mkdir(parents=True)
        worker_skill.write_text("# Worker-local playbook\n", encoding="utf-8")
        registry.write_text(json.dumps({"common_runtime_root": str(runtime_root)}), encoding="utf-8")
        write_executable(
            fake_bin / "loopx",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "path = os.environ.get('WRAPPER_ARG_LOG')",
                    "if path:",
                    "    with open(path, 'a', encoding='utf-8') as f:",
                    "        f.write(json.dumps(sys.argv[1:]) + '\\n')",
                    "print('fake-loopx ' + ' '.join(sys.argv[1:]))",
                    "",
                ]
            ),
        )
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
                    "    print('loopx_cli_scope=scoped_loopx_wrapper')",
                    "    print('human_stream_contract=role_todo_progress_codex_stream')",
                    "    print('machine_json_policy=file_or_explicit_machine_channel_only')",
                    "    raise SystemExit(0)",
                    "raise SystemExit(0)",
                    "",
                ]
            ),
        )

        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_bin}{os.pathsep}{original_path}"
        os.environ["FAKE_TMUX_LOG"] = str(tmux_log)
        os.environ["WRAPPER_ARG_LOG"] = str(wrapper_arg_log)
        try:
            scoped_env = dict(os.environ)
            scoped_env.update(
                {
                    "LOOPX_PROJECT": str(workspace),
                    "LOOPX_REAL_CLI": str(fake_bin / "loopx"),
                    "LOOPX_REGISTRY": str(registry),
                    "LOOPX_RUNTIME_ROOT": str(runtime_root),
                }
            )
            workspace.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [sys.executable, "-c", _SCOPED_LOOPX_WRAPPER_PY],
                env=scoped_env,
                check=True,
                capture_output=True,
                text=True,
            )
            human = subprocess.run(
                [str(workspace / ".local/bin/loopx"), "--format", "json", "status"],
                env=scoped_env,
                check=True,
                capture_output=True,
                text=True,
            )
            visible_pipe = subprocess.run(
                [str(workspace / ".local/bin/loopx-json"), "--format", "json", "status"],
                env=scoped_env,
                capture_output=True,
                text=True,
            )
            machine_artifact = workspace / ".local" / "reviewer" / "status.public.json"
            machine_artifact.parent.mkdir(parents=True, exist_ok=True)
            with machine_artifact.open("w", encoding="utf-8") as handle:
                subprocess.run(
                    [str(workspace / ".local/bin/loopx-json"), "--format", "json", "status"],
                    env=scoped_env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                )
            explicit_machine = subprocess.run(
                [str(workspace / ".local/bin/loopx-json"), "--format", "json", "status"],
                env={**scoped_env, "LOOPX_MACHINE_JSON": "1"},
                check=True,
                capture_output=True,
                text=True,
            )
            tty_status, tty_output = run_with_pty(
                [str(workspace / ".local/bin/loopx-json"), "--format", "json", "status"],
                env=scoped_env,
            )
            assert "format=markdown; machine_json_wrapper=$LOOPX_PANE_LOOPX_JSON" in human.stdout, human.stdout
            assert "--format markdown status" in human.stdout, human.stdout
            assert visible_pipe.returncode == 2, visible_pipe.stdout
            assert "LoopX machine JSON hidden" in visible_pipe.stdout, visible_pipe.stdout
            assert "fake-loopx" not in visible_pipe.stdout, visible_pipe.stdout
            assert "--format json status" in machine_artifact.read_text(encoding="utf-8")
            assert "--format json status" in explicit_machine.stdout, explicit_machine.stdout
            assert tty_status == 2, tty_output
            assert "LoopX machine JSON hidden" in tty_output, tty_output
            assert "fake-loopx" not in tty_output, tty_output

            try:
                execute_visible_multi_agent_launcher(
                    payload={
                        "session_name": "loopx-visible-launcher-missing-skill-smoke",
                        "lanes": [
                            {
                                "lane_id": "reviewer",
                                "visible_launch_command": "true",
                                "role_profile": {
                                    "required_skill": "loopx-auto-research",
                                    "worker_skill_source": "worker/MISSING.md",
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
                    workspace=str(temp / "missing-skill-workspace"),
                    create_workspace=True,
                    cwd=temp,
                )
                raise AssertionError("missing worker-local skill source should fail closed")
            except ValueError as exc:
                assert "worker-local skill materialization failed" in str(exc), exc
                assert "worker/MISSING.md" in str(exc), exc
            assert not tmux_log.exists(), tmux_log

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
            os.environ.pop("WRAPPER_ARG_LOG", None)

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
                "source_resolution": "source_root",
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
