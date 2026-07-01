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

ONE_COMMAND = r'''
import json
import os
from pathlib import Path

from loopx.visible_multi_agent_launcher import execute_visible_multi_agent_launcher


goal_id = "loopx-meta"
session_name = "loopx-generic-multi-agent-smoke"
registry = Path(os.environ["SMOKE_REGISTRY"])
runtime_root = Path(os.environ["SMOKE_RUNTIME_ROOT"])
workspace = Path(os.environ["SMOKE_WORKSPACE"])
cwd = Path(os.environ["SMOKE_CWD"])

lanes = [
    {
        "lane_id": "planner",
        "agent_id": "codex-main-control",
        "role_id": "planner",
        "responsibility": "Plan the next bounded step from the shared goal surface.",
        "role_profile": {"schema_version": "generic_multi_agent_role_profile_v0", "role_id": "planner"},
        "quota_guard": "loopx --format json --registry \"$LOOPX_REGISTRY\" --runtime-root \"$LOOPX_RUNTIME_ROOT\" quota should-run --goal-id loopx-meta --agent-id codex-main-control",
        "frontier": "printf '[LoopX frontier]\\nfrontier_or_blocked_reason=printed\\n'",
        "bootstrap_message": "printf '[bootstrap-or-stop]\\nmodel_reasoning_effort=high\\n'",
        "visible_launch_command": "printf '[LoopX visible acceptance]\\n[LoopX role profile]\\n[LoopX quota guard]\\n[LoopX frontier]\\n[bootstrap-or-stop]\\nloopx_agent_handshake=role_profile_quota_frontier_bootstrap\\nloopx_polling_prompt=visible_bootstrap_prompt\\nhuman_stream_contract=role_todo_progress_codex_stream\\nmachine_json_policy=file_or_explicit_machine_channel_only\\nreasoning_effort=high\\nmodel_reasoning_effort=high\\n'; exec /bin/sh -i",
        "reasoning_effort": "high",
        "lane_timeline": ["role_profile", "quota_guard", "frontier", "bootstrap"],
    },
    {
        "lane_id": "critic",
        "agent_id": "codex-side-bypass",
        "role_id": "critic",
        "responsibility": "Review the bounded step against the same todo and quota projection.",
        "role_profile": {"schema_version": "generic_multi_agent_role_profile_v0", "role_id": "critic"},
        "quota_guard": "loopx --format json --registry \"$LOOPX_REGISTRY\" --runtime-root \"$LOOPX_RUNTIME_ROOT\" quota should-run --goal-id loopx-meta --agent-id codex-side-bypass",
        "frontier": "printf '[LoopX frontier]\\nfrontier_or_blocked_reason=printed\\n'",
        "bootstrap_message": "printf '[bootstrap-or-stop]\\nmodel_reasoning_effort=high\\n'",
        "visible_launch_command": "printf '[LoopX visible acceptance]\\n[LoopX role profile]\\n[LoopX quota guard]\\n[LoopX frontier]\\n[bootstrap-or-stop]\\nloopx_agent_handshake=role_profile_quota_frontier_bootstrap\\nloopx_polling_prompt=visible_bootstrap_prompt\\nhuman_stream_contract=role_todo_progress_codex_stream\\nmachine_json_policy=file_or_explicit_machine_channel_only\\nreasoning_effort=high\\nmodel_reasoning_effort=high\\n'; exec /bin/sh -i",
        "reasoning_effort": "high",
        "lane_timeline": ["role_profile", "quota_guard", "frontier", "bootstrap"],
    },
]

packet = {
    "schema_version": "multi_agent_visible_launcher_v0",
    "mode": "dry_run",
    "goal_id": goal_id,
    "session_name": session_name,
    "reasoning_contract": {
        "default_reasoning_effort": "high",
        "codex_cli_config_key": "model_reasoning_effort",
    },
    "shared_goal_surface": {
        "shared_goal_id": goal_id,
        "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
        "shared_frontier": True,
        "lane_identity_source": "role_profile_plus_agent_scoped_quota",
        "all_lane_workspace_isolation": False,
        "mutation_isolation_policy": "only mutating attempts require a claimed worktree or equivalent execution boundary",
    },
    "lanes": lanes,
    "human_stream_contract": {
        "schema_version": "multi_agent_visible_human_stream_contract_v0",
        "human_pane": [
            "role_profile_summary",
            "quota_summary",
            "frontier_or_blocked_summary",
            "bootstrap_artifact_ref",
            "codex_stream",
            "compact_exit_summary",
            "takeover_controls",
        ],
        "machine_artifacts": [
            "quota.public.json",
            "frontier.public.json",
            "bootstrap-prompt.public.txt",
            "role_local_public_artifacts",
        ],
        "machine_json_policy": "file_or_explicit_machine_channel_only",
        "visible_json_policy": "markdown_or_compact_summary_only",
        "codex_stream": "stdout_stderr_visible_below_bootstrap",
    },
    "commands": {
        "start_script": ["python -c <generic visible multi-agent launcher command>"],
        "attach": f"tmux attach -t {session_name}",
        "stop": f"tmux kill-session -t {session_name}",
        "retry": "rerun the same packet after quota/frontier refresh",
    },
    "acceptance": {
        "requires_visible_markers": [
            "[LoopX role profile]",
            "[LoopX quota guard]",
            "[LoopX frontier]",
            "[bootstrap-or-stop]",
            "loopx_agent_handshake=role_profile_quota_frontier_bootstrap",
            "loopx_polling_prompt=visible_bootstrap_prompt",
            "human_stream_contract=role_todo_progress_codex_stream",
            "machine_json_policy=file_or_explicit_machine_channel_only",
        ],
        "machine_json_file_bound": True,
        "codex_stream_visible": True,
    },
    "boundary": {
        "starts_visible_processes": False,
        "runs_agent_processes": False,
        "writes_loopx_state": False,
        "spends_loopx_quota": False,
        "reads_raw_transcripts": False,
        "reads_session_files": False,
        "reads_credentials": False,
        "hidden_prompt_injection": False,
        "shared_goal_surface": True,
        "all_lane_workspace_isolation": False,
        "public_safe_redaction": True,
    },
}

launch_result = None
if os.environ.get("SMOKE_EXECUTE") == "1":
    launch_result, chosen, workspace_mode = execute_visible_multi_agent_launcher(
        payload=packet,
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
        cwd=cwd,
    )
    packet["mode"] = "execute"
    packet["boundary"] = {
        **packet["boundary"],
        "starts_visible_processes": True,
        "runs_agent_processes": True,
    }
else:
    chosen = "dry_run_only"
    workspace_mode = "not_created"

print(json.dumps({
    "schema_version": "generic_multi_agent_one_command_smoke_v0",
    "chosen_launcher": chosen,
    "workspace_mode": workspace_mode,
    "packet": packet,
    "launch_result": launch_result,
}, sort_keys=True))
'''


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def run_one_command(env: dict[str, str], *, execute: bool) -> dict[str, object]:
    run_env = dict(env)
    if execute:
        run_env["SMOKE_EXECUTE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", ONE_COMMAND],
        check=True,
        capture_output=True,
        text=True,
        env=run_env,
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
            "if len(sys.argv) > 1 and sys.argv[1] == 'capture-pane':",
            "    print('[LoopX visible acceptance]')",
            "    print('[LoopX role profile]')",
            "    print('[LoopX quota guard]')",
            "    print('[LoopX frontier]')",
            "    print('[bootstrap-or-stop]')",
            "    print('frontier_or_blocked_reason=printed')",
            "    print('loopx_agent_handshake=role_profile_quota_frontier_bootstrap')",
            "    print('loopx_polling_prompt=visible_bootstrap_prompt')",
            "    print('human_stream_contract=role_todo_progress_codex_stream')",
            "    print('machine_json_policy=file_or_explicit_machine_channel_only')",
            "    print('reasoning_effort=high')",
            "    print('model_reasoning_effort=high')",
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

        write_executable(fake_bin / "loopx", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "codex", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "tmux", fake_tmux_script())

        env = dict(os.environ)
        env.update(
            {
                "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                "PYTHONPATH": f"{ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}",
                "FAKE_TMUX_LOG": str(tmux_log),
                "SMOKE_CWD": str(temp),
                "SMOKE_REGISTRY": str(registry),
                "SMOKE_RUNTIME_ROOT": str(runtime_root),
                "SMOKE_WORKSPACE": str(workspace),
            }
        )

        dry_run = run_one_command(env, execute=False)
        assert dry_run["schema_version"] == "generic_multi_agent_one_command_smoke_v0", dry_run
        assert dry_run["chosen_launcher"] == "dry_run_only", dry_run
        dry_packet = dry_run["packet"]
        assert dry_packet["mode"] == "dry_run", dry_packet
        assert dry_packet["reasoning_contract"]["default_reasoning_effort"] == "high", dry_packet
        assert dry_packet["shared_goal_surface"]["shared_state_route"] == "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT", dry_packet
        assert dry_packet["shared_goal_surface"]["all_lane_workspace_isolation"] is False, dry_packet
        assert dry_packet["human_stream_contract"]["schema_version"] == "multi_agent_visible_human_stream_contract_v0", dry_packet
        assert dry_packet["human_stream_contract"]["machine_json_policy"] == "file_or_explicit_machine_channel_only", dry_packet
        assert dry_packet["human_stream_contract"]["codex_stream"] == "stdout_stderr_visible_below_bootstrap", dry_packet
        assert dry_packet["acceptance"]["machine_json_file_bound"] is True, dry_packet
        assert dry_packet["acceptance"]["codex_stream_visible"] is True, dry_packet
        assert dry_packet["boundary"]["starts_visible_processes"] is False, dry_packet
        assert dry_packet["boundary"]["spends_loopx_quota"] is False, dry_packet
        assert all(lane["reasoning_effort"] == "high" for lane in dry_packet["lanes"]), dry_packet
        assert dry_run["launch_result"] is None, dry_run
        assert_public_safe(dry_packet, "dry-run packet")

        executed = run_one_command(env, execute=True)
        assert executed["chosen_launcher"] == "tmux", executed
        assert executed["workspace_mode"] == "explicit_workspace", executed
        exec_packet = executed["packet"]
        launch = executed["launch_result"]
        assert exec_packet["mode"] == "execute", exec_packet
        assert exec_packet["boundary"]["starts_visible_processes"] is True, exec_packet
        assert exec_packet["boundary"]["writes_loopx_state"] is False, exec_packet
        assert exec_packet["boundary"]["spends_loopx_quota"] is False, exec_packet
        assert launch["schema_version"] == "multi_agent_visible_launch_result_v0", launch
        assert launch["started_lanes"] == ["planner", "critic"], launch
        assert launch["visible_acceptance"]["accepted"] is True, launch
        assert launch["visible_acceptance"]["missing_lanes"] == [], launch
        assert_public_safe(exec_packet, "execute packet")
        assert_public_safe(
            {
                "schema_version": launch["schema_version"],
                "launcher": launch["launcher"],
                "started_lanes": launch["started_lanes"],
                "workspace_mode": launch["workspace_mode"],
                "attach_requested": launch["attach_requested"],
            },
            "launch public summary",
        )

        log_entries = [json.loads(line) for line in tmux_log.read_text(encoding="utf-8").splitlines()]
        env_snapshots = [entry["env"] for entry in log_entries]
        assert env_snapshots, log_entries
        for snapshot in env_snapshots:
            assert snapshot["LOOPX_REGISTRY"] == str(registry), snapshot
            assert snapshot["LOOPX_RUNTIME_ROOT"] == str(runtime_root), snapshot
            assert Path(snapshot["LOOPX_PROJECT"]).resolve() == workspace.resolve(), snapshot
        new_window_commands = [
            entry["argv"][-1]
            for entry in log_entries
            if entry["argv"][:1] == ["new-window"]
        ]
        assert len(new_window_commands) == 2, log_entries
        new_window_payloads = []
        for command in new_window_commands:
            command_path = Path(command)
            new_window_payloads.append(
                command_path.read_text(encoding="utf-8") if command_path.is_file() else command
            )
        assert all("reasoning_effort=high" in command for command in new_window_payloads), new_window_payloads
        assert all("model_reasoning_effort=high" in command for command in new_window_payloads), new_window_payloads
        launcher_source = (ROOT / "loopx/visible_multi_agent_launcher.py").read_text(
            encoding="utf-8"
        )
        assert "loopx_cli_scope=scoped_loopx_wrapper" in launcher_source
        assert "demo_local_wrapper" not in launcher_source

    smoke_source = Path(__file__).read_text(encoding="utf-8").lower()
    domain_marker = "auto" + "-research"
    assert domain_marker not in smoke_source, "generic launcher smoke should not depend on a domain demo"

    print("generic-multi-agent-one-command-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
