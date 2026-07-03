#!/usr/bin/env python3
"""Smoke-test the generic visible multi-agent one-command path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_CONTRACT_SCHEMA_VERSION = "tui_multi_agent_runner_contract_v0"

PRIVATE_MARKERS = [
    "byte" + "dance",
    "lark" + "office",
    "fei" + "shu.cn",
    "/" + "Users" + "/",
    "/" + "private" + "/",
    "/" + "tmp" + "/",
    "api" + "_key",
    "pass" + "word",
    "sec" + "ret",
]


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def run_launch_command(
    env: dict[str, str],
    *,
    spec_path: Path,
    registry: Path,
    runtime_root: Path,
    workspace: Path,
    execute: bool,
) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        "multi-agent",
        "launch",
        "--spec",
        str(spec_path),
        "--tmux-bin",
        "tmux",
        "--cli-bin",
        "loopx",
        "--codex-bin",
        "codex",
    ]
    if execute:
        command.extend(
            [
                "--execute",
                "--workspace",
                str(workspace),
                "--create-workspace",
                "--replace-existing",
            ]
        )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def run_wake_command(
    env: dict[str, str],
    *,
    registry: Path,
    runtime_root: Path,
    session_name: str,
    execute: bool,
    lanes: list[str] | None = None,
) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        "multi-agent",
        "wake",
        "--session-name",
        session_name,
        "--tmux-bin",
        "tmux",
    ]
    for lane in lanes or []:
        command.extend(["--lane", lane])
    if execute:
        command.append("--execute")
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def assert_public_safe(value: object, label: str) -> None:
    text = json.dumps(value, sort_keys=True).lower()
    leaked = [marker for marker in PRIVATE_MARKERS if marker.lower() in text]
    assert not leaked, f"{label} leaks private markers: {leaked}"


def fake_tmux_script() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env python3",
            "import json, os, sys",
            "record = {",
            "    'argv': sys.argv[1:],",
            "    'env': {",
            "        'LOOPX_PROJECT': os.environ.get('LOOPX_PROJECT'),",
            "        'LOOPX_REGISTRY': os.environ.get('LOOPX_REGISTRY'),",
            "        'LOOPX_RUNTIME_ROOT': os.environ.get('LOOPX_RUNTIME_ROOT'),",
            "    },",
            "}",
            "with open(os.environ['FAKE_TMUX_LOG'], 'a', encoding='utf-8') as f:",
            "    f.write(json.dumps(record, sort_keys=True) + '\\n')",
            "if len(sys.argv) > 1 and sys.argv[1] == 'has-session':",
            "    raise SystemExit(1)",
            "if len(sys.argv) > 1 and sys.argv[1] == 'list-windows':",
            "    print('planner\\ncritic')",
            "    raise SystemExit(0)",
            "raise SystemExit(0)",
            "",
        ]
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        workspace = temp / "workspace"
        tmux_log = temp / "tmux.jsonl"
        registry.write_text(json.dumps({"common_runtime_root": str(runtime_root)}), encoding="utf-8")
        runtime_root.mkdir()
        worker_skill = temp / "worker" / "SKILL.md"
        worker_skill.parent.mkdir()
        worker_skill.write_text(
            "# Planner Worker Skill\n\nUse LoopX todo/frontier state for handoff.\n",
            encoding="utf-8",
        )
        spec_path = temp / "multi-agent-spec.json"
        spec_path.write_text(
            json.dumps(
                {
                    "schema_version": "generic_multi_agent_launch_spec_v0",
                    "goal_id": "loopx-meta",
                    "session_name": "loopx-generic-multi-agent-smoke",
                    "default_reasoning_effort": "high",
                    "roles": [
                        {
                            "lane_id": "planner",
                            "agent_id": "codex-main-control",
                            "role_id": "planner",
                            "scope": "Plan the next bounded step from the shared goal surface.",
                            "skill": {
                                "name": "loopx-planner-worker",
                                "source": "worker/SKILL.md",
                            },
                            "handoff_hints": [
                                "Create or update a LoopX todo for critic when a plan needs review."
                            ],
                        },
                        {
                            "lane_id": "critic",
                            "agent_id": "codex-side-bypass",
                            "role_id": "critic",
                            "scope": "Review the bounded step against the same todo and quota projection.",
                            "handoff_hints": [
                                "Complete the review todo or hand a focused fix todo back to planner."
                            ],
                        },
                    ],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        write_executable(fake_bin / "loopx", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "codex", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "tmux", fake_tmux_script())

        env = dict(os.environ)
        env.update(
            {
                "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                "PYTHONPATH": f"{ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}",
                "FAKE_TMUX_LOG": str(tmux_log),
            }
        )

        dry_packet = run_launch_command(
            env,
            spec_path=spec_path,
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            execute=False,
        )
        assert dry_packet["mode"] == "dry_run", dry_packet
        assert dry_packet["product_spec"]["schema_version"] == "generic_multi_agent_launch_spec_v0", dry_packet
        assert dry_packet["product_spec"]["domain_specific"] is False, dry_packet
        assert dry_packet["reasoning_contract"]["default_reasoning_effort"] == "high", dry_packet
        assert dry_packet["shared_goal_surface"]["shared_state_route"] == "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT", dry_packet
        assert dry_packet["shared_goal_surface"]["all_lane_workspace_isolation"] is False, dry_packet
        assert dry_packet["runner_contract"]["schema_version"] == RUNNER_CONTRACT_SCHEMA_VERSION, dry_packet
        assert dry_packet["runner_contract"]["runner_surface"] == "tmux_codex_cli_tui", dry_packet
        assert dry_packet["runner_contract"]["coordination_model"]["leader_required"] is False, dry_packet
        assert dry_packet["runner_contract"]["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", dry_packet
        assert dry_packet["runner_contract"]["pane_local_a2a"]["cadence_wakeup_command"] == (
            "loopx multi-agent wake --session-name <session>"
        ), dry_packet
        assert dry_packet["runner_contract"]["pane_local_a2a"]["cadence_wakeup_model"] == (
            "fixed_prompt_broadcast"
        ), dry_packet
        assert dry_packet["runner_contract"]["pane_local_a2a"]["cadence_broadcaster_decides_work"] is False, dry_packet
        driver = dry_packet["runner_contract"]["decentralized_a2a_driver"]
        assert driver["schema_version"] == "multi_agent_decentralized_a2a_driver_contract_v0", driver
        assert driver["owner_layer"] == "generic_multi_agent_kernel", driver
        assert driver["driver_model"] == (
            "fixed_prompt_broadcast_plus_pane_local_state_tick"
        ), driver
        assert driver["broadcaster"]["decides_work"] is False, driver
        assert driver["pane"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", driver
        assert driver["acceptance"]["user_and_preset_do_not_own_tick_driver"] is True, driver
        assert dry_packet["runner_contract"]["pane_local_a2a"]["machine_json_destination"] == (
            "$LOOPX_PANE_ARTIFACT_DIR/*.public.json"
        ), dry_packet
        assert dry_packet["runner_contract"]["boundaries"]["domain_specific_research_logic"] is False, dry_packet
        compact = dry_packet["compact_human_status"]
        assert compact["schema_version"] == "generic_multi_agent_compact_status_v0", compact
        assert compact["role_count"] == 2, compact
        assert compact["first_action"] == "$LOOPX_PANE_A2A_TICK", compact
        assert compact["driver_model"] == (
            "fixed_prompt_broadcast_plus_pane_local_state_tick"
        ), compact
        assert compact["user_takeover"] == "attach to the session and type into any role pane", compact
        assert dry_packet["interactive_tui_contract"]["schema_version"] == "multi_agent_visible_interactive_tui_contract_v0", dry_packet
        assert dry_packet["interactive_tui_contract"]["runner_contract"] == RUNNER_CONTRACT_SCHEMA_VERSION, dry_packet
        assert dry_packet["interactive_tui_contract"]["machine_json_policy"] == "file_or_explicit_machine_channel_only", dry_packet
        assert dry_packet["interactive_tui_contract"]["codex_surface"] == "interactive_cli_tui", dry_packet
        assert dry_packet["acceptance"]["runner_contract"] == RUNNER_CONTRACT_SCHEMA_VERSION, dry_packet
        assert dry_packet["acceptance"]["machine_json_file_bound"] is True, dry_packet
        assert dry_packet["acceptance"]["codex_tui_interactive"] is True, dry_packet
        assert dry_packet["boundary"]["starts_visible_processes"] is False, dry_packet
        assert dry_packet["boundary"]["spends_loopx_quota"] is False, dry_packet
        assert all(lane["reasoning_effort"] == "high" for lane in dry_packet["lanes"]), dry_packet
        assert any(lane["role_profile"].get("required_skill") == "loopx-planner-worker" for lane in dry_packet["lanes"]), dry_packet
        assert_public_safe(dry_packet, "dry-run packet")

        exec_packet = run_launch_command(
            env,
            spec_path=spec_path,
            registry=registry,
            runtime_root=runtime_root,
            workspace=workspace,
            execute=True,
        )
        assert exec_packet["chosen_launcher"] == "tmux", exec_packet
        assert exec_packet["workspace_mode"] == "explicit_workspace", exec_packet
        launch = exec_packet["launch_result"]
        assert exec_packet["mode"] == "execute", exec_packet
        assert exec_packet["boundary"]["starts_visible_processes"] is True, exec_packet
        assert exec_packet["boundary"]["writes_loopx_state"] is False, exec_packet
        assert exec_packet["boundary"]["spends_loopx_quota"] is False, exec_packet
        assert launch["schema_version"] == "multi_agent_visible_launch_result_v0", launch
        assert launch["started_lanes"] == ["planner", "critic"], launch
        assert launch["visible_acceptance"]["accepted"] is True, launch
        assert launch["visible_acceptance"]["missing_lanes"] == [], launch
        assert all(
            item["interactive_codex_tui_script"] for item in launch["visible_acceptance"]["pane_checks"]
        ), launch
        skill_items = launch["worker_skill_materialization"]
        assert skill_items and skill_items[0]["materialized"] is True, launch
        assert (workspace / ".codex" / "skills" / "loopx-planner-worker" / "SKILL.md").is_file()
        dry_wake = run_wake_command(
            env,
            registry=registry,
            runtime_root=runtime_root,
            session_name="loopx-generic-multi-agent-smoke",
            execute=False,
            lanes=["planner"],
        )
        assert dry_wake["schema_version"] == "multi_agent_pane_a2a_wakeup_v0", dry_wake
        assert dry_wake["mode"] == "dry_run", dry_wake
        assert dry_wake["target_lanes"] == ["planner"], dry_wake
        assert dry_wake["coordination_model"] == "decentralized_state_a2a", dry_wake
        assert dry_wake["wakeup_model"] == "fixed_prompt_broadcast", dry_wake
        assert dry_wake["driver_contract"]["owner_layer"] == "generic_multi_agent_kernel", dry_wake
        assert dry_wake["driver_contract"]["broadcaster"]["selects_todo"] is False, dry_wake
        assert dry_wake["workflow_driver"] is False, dry_wake
        assert dry_wake["broadcaster_reads_frontier"] is False, dry_wake
        assert dry_wake["broadcaster_selects_todo"] is False, dry_wake
        assert "$LOOPX_PANE_A2A_TICK" in dry_wake["prompt"], dry_wake
        assert "\n" not in dry_wake["prompt"], dry_wake
        exec_wake = run_wake_command(
            env,
            registry=registry,
            runtime_root=runtime_root,
            session_name="loopx-generic-multi-agent-smoke",
            execute=True,
        )
        assert exec_wake["mode"] == "execute", exec_wake
        assert exec_wake["target_lanes"] == ["planner", "critic"], exec_wake
        assert exec_wake["boundary"]["writes_loopx_state"] is False, exec_wake
        assert exec_wake["boundary"]["runs_worker_turn_directly"] is False, exec_wake
        assert_public_safe(
            {
                "product_spec": exec_packet["product_spec"],
                "schema_version": launch["schema_version"],
                "launcher": launch["launcher"],
                "started_lanes": launch["started_lanes"],
                "workspace_mode": launch["workspace_mode"],
                "attach_requested": launch["attach_requested"],
            },
            "launch public summary",
        )

        log_entries = [json.loads(line) for line in tmux_log.read_text(encoding="utf-8").splitlines()]
        env_snapshots = [
            entry["env"]
            for entry in log_entries
            if entry["env"].get("LOOPX_REGISTRY")
        ]
        assert env_snapshots, log_entries
        for snapshot in env_snapshots:
            assert snapshot["LOOPX_REGISTRY"] == str(registry), snapshot
            assert snapshot["LOOPX_RUNTIME_ROOT"] == str(runtime_root), snapshot
            assert Path(snapshot["LOOPX_PROJECT"]).resolve() == workspace.resolve(), snapshot
        start_commands = [
            entry["argv"][-1]
            for entry in log_entries
            if entry["argv"][:1] in (["new-session"], ["new-window"])
        ]
        assert len(start_commands) == 2, log_entries
        start_payloads = []
        for command in start_commands:
            command_path = Path(command)
            start_payloads.append(
                command_path.read_text(encoding="utf-8") if command_path.is_file() else command
            )
        assert all("LOOPX_CODEX_BIN=codex" in command for command in start_payloads), start_payloads
        assert all("LOOPX_CODEX_REASONING_EFFORT=high" in command for command in start_payloads), start_payloads
        assert all("exec python3 -c" in command for command in start_payloads), start_payloads
        assert all("LOOPX_PANE_ARTIFACT_DIR" in command for command in start_payloads), start_payloads
        assert all("codex exec" not in command for command in start_payloads), start_payloads
        wake_entries = [entry["argv"] for entry in log_entries if entry["argv"][:1] in (["set-buffer"], ["paste-buffer"], ["send-keys"])]
        assert any(entry[:1] == ["set-buffer"] for entry in wake_entries), wake_entries
        assert sum(1 for entry in wake_entries if entry[:1] == ["paste-buffer"]) == 2, wake_entries
        assert sum(1 for entry in wake_entries if entry[:1] == ["send-keys"] and entry[-1] == "Enter") == 2, wake_entries
        assert any("$LOOPX_PANE_A2A_TICK" in " ".join(entry) for entry in wake_entries), wake_entries
        launcher_source = (ROOT / "loopx/visible_multi_agent_launcher.py").read_text(
            encoding="utf-8"
        )
        contract_source = (ROOT / "loopx/capabilities/multi_agent/contract.py").read_text(
            encoding="utf-8"
        )
        assert "scoped_loopx_wrapper" in launcher_source
        assert "build_tui_multi_agent_runner_contract" in contract_source
        assert "generic_multi_agent_compact_status_v0" in contract_source
        assert "demo_local_wrapper" not in launcher_source

    smoke_source = Path(__file__).read_text(encoding="utf-8").lower()
    domain_marker = "auto" + "-research"
    assert domain_marker not in smoke_source, "generic launcher smoke should not depend on a domain demo"

    print("generic-multi-agent-one-command-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
