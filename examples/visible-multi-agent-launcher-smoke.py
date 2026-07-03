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

from loopx.capabilities.multi_agent.runtime_scripts import (  # noqa: E402
    CODEX_TUI_EXEC_PY as _CODEX_TUI_EXEC_PY,
    SCOPED_LOOPX_WRAPPER_PY as _SCOPED_LOOPX_WRAPPER_PY,
)
from loopx.visible_multi_agent_launcher import (  # noqa: E402
    TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
    build_visible_multi_agent_payload,
    build_visible_multi_agent_payload_from_spec,
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
    contract_source = (ROOT / "loopx/capabilities/multi_agent/contract.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (ROOT / "loopx/capabilities/multi_agent/runtime_scripts.py").read_text(
        encoding="utf-8"
    )
    assert "from ...visible_multi_agent_launcher import" in auto_research_cli
    assert "execute_visible_multi_agent_launcher" in auto_research_cli
    forbidden_defs = [
        "def _launch_auto_research_with_tmux",
        "def _tmux_visible_launch_acceptance",
        "def _resolve_demo_workspace",
        "def _resolve_auto_research_launcher",
    ]
    leaked_defs = [name for name in forbidden_defs if name in auto_research_cli]
    assert not leaked_defs, leaked_defs
    assert "demo_local_wrapper" not in launcher_source
    assert "_SCOPED_LOOPX_WRAPPER_PY = r" not in launcher_source
    assert "_CODEX_TUI_EXEC_PY = r" not in launcher_source
    assert "SCOPED_LOOPX_WRAPPER_PY = r" in runtime_source
    assert "CODEX_TUI_EXEC_PY = r" in runtime_source
    assert "scoped_loopx_wrapper" in launcher_source
    assert "LOOPX_PANE_LOOPX_JSON" in launcher_source
    assert "LOOPX_PANE_ARTIFACT_DIR" in launcher_source
    assert "LOOPX_PANE_A2A_TICK" in launcher_source
    assert "loopx-pane-a2a-tick" in launcher_source
    assert "LOOPX_PANE_WORKER_TURN" in launcher_source
    assert "LOOPX_PANE_TICK_ROUNDS" in launcher_source
    assert "The launcher runs `$LOOPX_PANE_A2A_TICK` before this Codex TUI opens." in contract_source
    assert "LOOPX_VISIBLE_FORCE_MARKDOWN" in launcher_source
    assert "machine_json_command=$LOOPX_PANE_LOOPX_JSON artifact_dir=$LOOPX_PANE_ARTIFACT_DIR" in runtime_source
    assert "$LOOPX_PANE_LOOPX_JSON is a command path, not an output file." in runtime_source
    assert "It injects --format json unless you pass an explicit --format." in runtime_source
    assert "Never write output to `$LOOPX_PANE_LOOPX_JSON`" in contract_source
    assert "LoopX machine JSON hidden" in runtime_source
    assert "LOOPX_ALLOW_TTY_JSON" in runtime_source
    assert "stat.S_ISREG" in runtime_source
    assert "LOOPX_MACHINE_JSON=1 explicitly" in runtime_source
    assert "multi_agent_visible_interactive_tui_contract_v0" in contract_source
    assert TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION in contract_source
    assert "build_tui_multi_agent_runner_contract" in launcher_source
    assert "LOOPX_CODEX_TUI_MODE=interactive" in launcher_source
    assert "LOOPX_CODEX_TRUST_WORKSPACE" in launcher_source
    assert "LOOPX_CODEX_BIN" in launcher_source
    assert "LOOPX_CODEX_REASONING_EFFORT" in launcher_source
    assert "export BOOTSTRAP_PROMPT" in launcher_source
    assert "_persist_codex_workspace_trust" in launcher_source
    assert "rev-parse\", \"--show-toplevel" in runtime_source
    assert "trust_level=" in runtime_source and "trusted" in runtime_source
    assert "trust_prompt_blocked" in launcher_source
    assert "Do you trust the contents of this directory?" in launcher_source
    assert "pre_codex_character_stream" in launcher_source
    assert "build_visible_frontier_command" not in launcher_source
    assert 'FRONTIER_ARTIFACT_NAME="frontier.public.json"' not in launcher_source
    assert "_VISIBLE_CODEX_STREAM_FILTER_PY" not in launcher_source
    assert "_HUMAN_VIEW_PACKET_PY" not in launcher_source
    assert "worker-local skill block hidden" not in launcher_source
    assert "codex_stream_filter" not in launcher_source
    assert " codex exec " not in launcher_source

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
    runner_contract = dry_packet["runner_contract"]
    assert runner_contract["schema_version"] == TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION
    assert runner_contract["coordination_model"]["leader_required"] is False, runner_contract
    assert runner_contract["coordination_model"]["state_bus"] == (
        "loopx_registry_runtime_todo_quota_frontier"
    ), runner_contract
    assert runner_contract["tmux_lifecycle"]["one_window_per_role"] is True, runner_contract
    assert runner_contract["tmux_lifecycle"]["attach_command"] == dry_packet["commands"]["attach"]
    assert runner_contract["tmux_lifecycle"]["stop_command"] == dry_packet["commands"]["stop"]
    assert runner_contract["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK"
    assert runner_contract["pane_local_a2a"]["cadence_wakeup_command"] == (
        "loopx multi-agent wake --session-name <session>"
    )
    assert runner_contract["pane_local_a2a"]["cadence_wakeup_model"] == "fixed_prompt_broadcast"
    assert runner_contract["pane_local_a2a"]["cadence_broadcaster_decides_work"] is False
    driver = runner_contract["decentralized_a2a_driver"]
    assert driver["schema_version"] == "multi_agent_decentralized_a2a_driver_contract_v0", driver
    assert driver["owner_layer"] == "generic_multi_agent_kernel", driver
    assert driver["driver_model"] == "fixed_prompt_broadcast_plus_pane_local_state_tick", driver
    assert driver["broadcaster"]["reads_frontier"] is False, driver
    assert driver["broadcaster"]["selects_todo"] is False, driver
    assert driver["broadcaster"]["runs_worker_turn"] is False, driver
    assert driver["pane"]["decision_owner"] == "codex_tui_agent_via_loopx_state", driver
    assert driver["acceptance"]["each_pane_decides_from_state"] is True, driver
    assert runner_contract["pane_local_a2a"]["first_action"] == (
        "launcher runs $LOOPX_PANE_A2A_TICK before Codex TUI opens"
    )
    assert runner_contract["pane_local_a2a"]["bounded_rounds_env"] == (
        "LOOPX_PANE_TICK_ROUNDS"
    )
    assert "LOOPX_PANE_WORKER_TURN" in runner_contract["lane_runtime_env"]["pane_tools"]
    assert "LOOPX_PANE_ARTIFACT_DIR" in runner_contract["lane_runtime_env"]["pane_tools"]
    assert runner_contract["pane_local_a2a"]["machine_json_destination"] == (
        "$LOOPX_PANE_ARTIFACT_DIR/*.public.json"
    )
    assert runner_contract["pane_local_a2a"]["rounds_artifact"] == (
        "$LOOPX_PANE_ARTIFACT_DIR/pane-a2a-rounds.public.json"
    )
    assert runner_contract["role_prompt_and_skill"]["worker_local_skill_only"] is True
    assert runner_contract["debug_artifacts"]["machine_json"] == (
        "redirected_public_artifacts_only"
    )
    assert runner_contract["boundaries"]["domain_specific_research_logic"] is False
    assert (
        dry_packet["interactive_tui_contract"]["schema_version"]
        == "multi_agent_visible_interactive_tui_contract_v0"
    ), dry_packet
    assert dry_packet["interactive_tui_contract"]["runner_contract"] == (
        TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION
    )
    assert dry_packet["interactive_tui_contract"]["machine_json_policy"] == (
        "file_or_explicit_machine_channel_only"
    ), dry_packet
    assert dry_packet["interactive_tui_contract"]["codex_surface"] == "interactive_cli_tui", dry_packet
    assert dry_packet["acceptance"]["runner_contract"] == (
        TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION
    )
    assert dry_packet["acceptance"]["machine_json_file_bound"] is True, dry_packet
    assert dry_packet["acceptance"]["codex_tui_interactive"] is True, dry_packet
    assert dry_packet["boundary"]["hidden_prompt_injection"] is False, dry_packet
    assert dry_packet["boundary"]["spends_loopx_quota"] is False, dry_packet
    assert dry_packet["boundary"]["all_lane_workspace_isolation"] is False, dry_packet

    generic_packet = build_visible_multi_agent_payload_from_spec(
        {
            "goal_id": "loopx-meta",
            "roles": [
                {
                    "agent_id": "codex-side-bypass",
                    "role_id": "planner",
                    "scope": "plan one state-backed handoff",
                    "worker_turn_command": "printf 'turn streamed\\n'",
                    "tick_rounds": 2,
                    "tick_sleep_seconds": 1,
                }
            ],
        }
    )
    assert generic_packet["runner_contract"]["schema_version"] == (
        TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION
    )
    assert generic_packet["runner_contract"]["tmux_lifecycle"]["lane_count"] == 1
    generic_lane = generic_packet["lanes"][0]
    assert generic_lane["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", generic_lane
    assert generic_lane["pane_local_a2a"]["worker_turn_configured"] is True, generic_lane
    assert generic_lane["pane_local_a2a"]["auto_start"] is True, generic_lane
    assert generic_lane["pane_local_a2a"]["tick_rounds"] == 2, generic_lane
    assert "auto_start_pane_local_a2a_tick" in generic_lane["lane_timeline"], generic_lane
    assert "LOOPX_PANE_A2A_TICK" in generic_lane["visible_launch_command"], generic_lane
    assert "LOOPX_PANE_WORKER_TURN" in generic_lane["visible_launch_command"], generic_lane
    assert "LOOPX_PANE_ARTIFACT_DIR" in generic_lane["visible_launch_command"], generic_lane
    assert "$LOOPX_PANE_ARTIFACT_DIR/quota.public.json" in generic_lane["quota_guard"], generic_lane
    assert "LOOPX_PANE_TICK_ROUNDS=2" in generic_lane["visible_launch_command"], generic_lane
    assert "LOOPX_PANE_TICK_SLEEP_SECONDS=1" in generic_lane["visible_launch_command"], generic_lane
    assert "pane-a2a-tick.output.txt" in generic_lane["visible_launch_command"], generic_lane

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        workspace = temp / "workspace"
        tmux_log = temp / "tmux.jsonl"
        codex_home = temp / "codex-home"
        codex_argv_log = temp / "codex-argv.json"
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
        write_executable(
            fake_bin / "codex",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "path = os.environ.get('FAKE_CODEX_ARGV_LOG')",
                    "if path:",
                    "    with open(path, 'w', encoding='utf-8') as f:",
                    "        json.dump(sys.argv, f)",
                    "print('fake codex tui')",
                    "raise SystemExit(0)",
                    "",
                ]
            ),
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
                    "if len(sys.argv) > 1 and sys.argv[1] == 'list-windows':",
                    "    print('planner\\nreviewer')",
                    "    raise SystemExit(0)",
                    "if len(sys.argv) > 1 and sys.argv[1] == 'capture-pane':",
                    "    text = os.environ.get('FAKE_TMUX_CAPTURE_TEXT', '')",
                    "    if text:",
                    "        print(text)",
                    "    raise SystemExit(0)",
                    "raise SystemExit(0)",
                    "",
                ]
            ),
        )

        original_path = os.environ.get("PATH", "")
        original_codex_home = os.environ.get("CODEX_HOME")
        os.environ["PATH"] = f"{fake_bin}{os.pathsep}{original_path}"
        os.environ["CODEX_HOME"] = str(codex_home)
        os.environ["FAKE_TMUX_LOG"] = str(tmux_log)
        os.environ["FAKE_CODEX_ARGV_LOG"] = str(codex_argv_log)
        os.environ["WRAPPER_ARG_LOG"] = str(wrapper_arg_log)
        try:
            scoped_env = dict(os.environ)
            scoped_env.update(
                {
                    "LOOPX_PROJECT": str(workspace),
                    "LOOPX_REAL_CLI": str(fake_bin / "loopx"),
                    "LOOPX_REGISTRY": str(registry),
                    "LOOPX_RUNTIME_ROOT": str(runtime_root),
                    "LOOPX_PANE_ARTIFACT_DIR": str(workspace / ".local" / "pane-artifacts" / "reviewer"),
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
            machine_artifact = workspace / ".local" / "pane-artifacts" / "reviewer" / "status.public.json"
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
            implicit_machine_artifact = (
                workspace / ".local" / "pane-artifacts" / "reviewer" / "implicit-status.public.json"
            )
            with implicit_machine_artifact.open("w", encoding="utf-8") as handle:
                subprocess.run(
                    [str(workspace / ".local/bin/loopx-json"), "status"],
                    env=scoped_env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                )
            explicit_machine = subprocess.run(
                [str(workspace / ".local/bin/loopx-json"), "status"],
                env={**scoped_env, "LOOPX_MACHINE_JSON": "1"},
                check=True,
                capture_output=True,
                text=True,
            )
            tty_status, tty_output = run_with_pty(
                [str(workspace / ".local/bin/loopx-json"), "--format", "json", "status"],
                env=scoped_env,
            )
            tick = subprocess.run(
                [str(workspace / ".local/bin/loopx-pane-a2a-tick")],
                env={
                    **scoped_env,
                    "LOOPX_PANE_LOOPX": str(workspace / ".local/bin/loopx"),
                    "LOOPX_GOAL_ID": "loopx-meta",
                    "LOOPX_AGENT_ID": "codex-side-bypass",
                    "LOOPX_ROLE_ID": "planner",
                    "LOOPX_PANE_WORKER_TURN": "printf 'worker turn streamed\\n'",
                    "LOOPX_PANE_TICK_ROUNDS": "2",
                    "LOOPX_PANE_TICK_SLEEP_SECONDS": "1",
                },
                check=True,
                capture_output=True,
                text=True,
            )
            assert "machine_json_command=$LOOPX_PANE_LOOPX_JSON artifact_dir=$LOOPX_PANE_ARTIFACT_DIR" in human.stdout, human.stdout
            assert "--format markdown status" in human.stdout, human.stdout
            assert visible_pipe.returncode == 2, visible_pipe.stdout
            assert "LoopX machine JSON hidden" in visible_pipe.stdout, visible_pipe.stdout
            assert "LOOPX_PANE_ARTIFACT_DIR" in visible_pipe.stdout, visible_pipe.stdout
            assert "command path, not an output file" in visible_pipe.stdout, visible_pipe.stdout
            assert "injects --format json" in visible_pipe.stdout, visible_pipe.stdout
            assert "fake-loopx" not in visible_pipe.stdout, visible_pipe.stdout
            assert "--format json status" in machine_artifact.read_text(encoding="utf-8")
            assert "--format json status" in implicit_machine_artifact.read_text(encoding="utf-8")
            assert (workspace / ".local/bin/loopx-json").read_text(encoding="utf-8").startswith(
                "#!/usr/bin/env python3"
            )
            assert "--format json status" in explicit_machine.stdout, explicit_machine.stdout
            assert tty_status == 2, tty_output
            assert "LoopX machine JSON hidden" in tty_output, tty_output
            assert "fake-loopx" not in tty_output, tty_output
            assert "role=planner agent=codex-side-bypass" in tick.stdout, tick.stdout
            assert "round 1/2" in tick.stdout and "round 2/2" in tick.stdout, tick.stdout
            assert "quota should-run" in tick.stdout, tick.stdout
            assert "--format markdown" in tick.stdout, tick.stdout
            assert "worker turn streamed" in tick.stdout, tick.stdout
            rounds_artifact = (
                workspace
                / ".local"
                / "pane-artifacts"
                / "reviewer"
                / "pane-a2a-rounds.public.json"
            )
            rounds_payload = json.loads(rounds_artifact.read_text(encoding="utf-8"))
            assert rounds_payload["schema_version"] == "pane_local_a2a_tick_rounds_v0", rounds_payload
            assert rounds_payload["coordination_model"] == "decentralized_state_a2a", rounds_payload
            assert rounds_payload["workflow_driver"] is False, rounds_payload
            assert rounds_payload["rounds_requested"] == 2, rounds_payload
            assert rounds_payload["rounds_completed"] == 2, rounds_payload
            assert rounds_payload["worker_configured"] is True, rounds_payload
            assert [item["round_index"] for item in rounds_payload["rounds"]] == [1, 2], rounds_payload
            assert rounds_payload["public_boundary"]["raw_logs_recorded"] is False, rounds_payload
            assert "/" + "tmp/" not in json.dumps(rounds_payload, sort_keys=True), rounds_payload

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
                        {
                            "lane_id": "planner",
                            "frontier": "true",
                            "visible_launch_command": "exec codex -c model_reasoning_effort=high -C \"$LOOPX_PROJECT\" planner",
                        },
                        {
                            "lane_id": "reviewer",
                            "visible_launch_command": "exec codex -c model_reasoning_effort=high -C \"$LOOPX_PROJECT\" reviewer",
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
                codex_trust_workspace=True,
            )

            git_root_workspace = temp / "git-root" / "lanes" / "planner"
            git_root_workspace.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "init", str(temp / "git-root")],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "-c", _CODEX_TUI_EXEC_PY],
                env={
                    **os.environ,
                    "LOOPX_CODEX_BIN": str(fake_bin / "codex"),
                    "LOOPX_PROJECT": str(git_root_workspace),
                    "LOOPX_CODEX_REASONING_EFFORT": "high",
                    "BOOTSTRAP_PROMPT": "planner prompt",
                    "LOOPX_CODEX_TRUST_WORKSPACE": "1",
                },
                check=True,
                capture_output=True,
                text=True,
            )
            codex_args = json.loads(codex_argv_log.read_text(encoding="utf-8"))
            assert "-C" in codex_args and str(git_root_workspace) in codex_args, codex_args
            assert codex_args[-1] == "planner prompt", codex_args
            trust_args = [
                item
                for index, item in enumerate(codex_args)
                if index > 0 and codex_args[index - 1] == "-c" and ".trust_level=" in item
            ]
            assert any(str(git_root_workspace) in item for item in trust_args), codex_args
            assert any(str(temp / "git-root") in item for item in trust_args), codex_args

            os.environ["FAKE_TMUX_CAPTURE_TEXT"] = "Do you trust the contents of this directory?"
            blocked_launch, _, _ = execute_visible_multi_agent_launcher(
                payload={
                    "session_name": "loopx-visible-launcher-trust-block-smoke",
                    "lanes": [
                        {
                            "lane_id": "planner",
                            "visible_launch_command": "exec codex -c model_reasoning_effort=high -C \"$LOOPX_PROJECT\" planner",
                        }
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
                codex_trust_workspace=True,
            )
        finally:
            os.environ["PATH"] = original_path
            if original_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = original_codex_home
            os.environ.pop("FAKE_TMUX_LOG", None)
            os.environ.pop("FAKE_CODEX_ARGV_LOG", None)
            os.environ.pop("WRAPPER_ARG_LOG", None)
            os.environ.pop("FAKE_TMUX_CAPTURE_TEXT", None)

        assert chosen == "tmux", launch
        assert workspace_mode == "explicit_workspace", launch
        assert workspace.is_dir(), workspace
        assert launch["schema_version"] == "multi_agent_visible_launch_result_v0", launch
        assert launch["codex_trust_workspace"] is True, launch
        assert launch["codex_trust_scope"] == "persisted_selected_workspace_and_git_root", launch
        assert launch["codex_trust_config"]["trusted_path_count"] >= 1, launch
        config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
        assert str(workspace) in config_text, config_text
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
        assert launch["launcher_script_count"] == 2, launch
        acceptance = launch["visible_acceptance"]
        assert acceptance["schema_version"] == "multi_agent_visible_launch_acceptance_v0", acceptance
        assert acceptance["accepted"] is True, acceptance
        assert acceptance["missing_lanes"] == [], acceptance
        assert all(item["accepted"] for item in acceptance["pane_checks"]), acceptance
        assert all(item["interactive_codex_tui_script"] for item in acceptance["pane_checks"]), acceptance
        assert not any(item["trust_prompt_blocked"] for item in acceptance["pane_checks"]), acceptance

        blocked_acceptance = blocked_launch["visible_acceptance"]
        assert blocked_acceptance["accepted"] is False, blocked_acceptance
        assert blocked_acceptance["pane_checks"][0]["trust_prompt_blocked"] is True, blocked_acceptance

        log_entries = [json.loads(line) for line in tmux_log.read_text(encoding="utf-8").splitlines()]
        assert any(entry[:1] == ["new-session"] for entry in log_entries), log_entries
        assert sum(1 for entry in log_entries if entry[:1] == ["new-window"]) == 1, log_entries
        tmux_starts = [entry for entry in log_entries if entry[:1] in (["new-session"], ["new-window"])]
        assert all("-lc" not in entry for entry in tmux_starts), tmux_starts

    print("visible-multi-agent-launcher-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
