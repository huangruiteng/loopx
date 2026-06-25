#!/usr/bin/env python3
"""Smoke-test the Feishu progress bridge with fake feishu-cli and loopx CLIs."""

from __future__ import annotations

import importlib.util
import json
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "feishu_loopx_progress_bridge.py"


def load_bridge_module():
    spec = importlib.util.spec_from_file_location("feishu_loopx_progress_bridge_smoke", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load Feishu bridge script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    bridge = load_bridge_module()
    commands: list[list[str]] = []
    cards: list[dict[str, Any]] = []

    def fake_run_text(args: list[str], *, cwd: Path = bridge.CONTROL_ROOT, timeout: float = 30) -> str:
        commands.append(list(args))
        if args[:4] == ["loopx", "--registry", ".loopx/registry.json", "todo"] and args[4] == "add":
            return "added todo_abc"
        if args[:3] == ["feishu-cli", "msg", "reply"]:
            if "--text" in args:
                return json.dumps({"message_id": "om_text_ack"})
            content_path = Path(args[args.index("--content-file") + 1])
            cards.append(json.loads(content_path.read_text(encoding="utf-8")))
            return json.dumps({"message_id": "om_progress_reply"})
        if args[:3] == ["feishu-cli", "msg", "update"]:
            content_path = Path(args[args.index("--content-file") + 1])
            cards.append(json.loads(content_path.read_text(encoding="utf-8")))
            return json.dumps({"message_id": args[3]})
        if args[:4] == ["loopx", "--registry", ".loopx/registry.json", "todo"]:
            return json.dumps({"ok": True})
        raise AssertionError(f"unexpected command: {args}")

    def fake_run_json(args: list[str], *, cwd: Path = bridge.CONTROL_ROOT, timeout: float = 45) -> dict[str, Any]:
        commands.append(list(args))
        if args[:5] == ["loopx", "--registry", ".loopx/registry.json", "scheduler", "plan"]:
            assert "--format" in args and "json" in args, args
            return {
                "schema_version": "scheduler_plan_v0",
                "goal_id": "default",
                "agent_id": "codex-devbox",
                "dispatch_plan": {
                    "action": "run_parallel_batch",
                    "parallelizable": True,
                    "runnable_todo_ids": ["todo_docs", "todo_read"],
                    "waiting_reason_counts": {"agent_lane_capacity": 1},
                },
            }
        if args[:5] == ["loopx", "--registry", ".loopx/registry.json", "scheduler", "next-batch"]:
            assert "--format" in args and "json" in args, args
            assert "--agent-id" not in args, args
            return {
                "schema_version": "scheduler_next_batch_v0",
                "goal_id": "default",
                "ready_to_dispatch": True,
                "dispatch_mode": "parallel_batch",
                "batch_size": 2,
                "worker_slots": [
                    {"todo_id": "todo_docs", "agent_lane": "codex-devbox-req-a"},
                    {"todo_id": "todo_view", "agent_lane": "codex-devbox-req-b"},
                ],
            }
        if args[:5] == ["loopx", "--registry", ".loopx/registry.json", "scheduler", "handoffs"]:
            assert "--format" in args and "json" in args, args
            assert "--todo-id" in args and args[args.index("--todo-id") + 1] == "todo_abc", args
            return {
                "schema_version": "scheduler_worker_handoffs_v0",
                "goal_id": "default",
                "todo_id": "todo_abc",
                "handoff_count": 1,
                "worker_handoffs": [
                    {
                        "todo_id": "todo_abc",
                        "agent_lane": "codex-devbox-req-a",
                        "start_steps": [{"kind": "quota_guard", "command": "loopx quota should-run ..."}],
                        "closeout_steps": [{"kind": "complete_todo", "command_template": "loopx todo complete ..."}],
                    }
                ],
            }
        if args[:4] == ["loopx", "--registry", ".loopx/registry.json", "status"]:
            agent_id = args[args.index("--agent-id") + 1]
            assert agent_id.startswith("codex-devbox-req-"), args
            return {"ok": True, "agent_id": agent_id, "attention_queue": {"items": []}}
        if args[:5] == ["loopx", "--registry", ".loopx/registry.json", "quota", "should-run"]:
            agent_id = args[args.index("--agent-id") + 1]
            assert agent_id.startswith("codex-devbox-req-"), args
            return {
                "goal_id": args[args.index("--goal-id") + 1],
                "agent_id": agent_id,
                "requires_user_action": True,
                "recommended_action": "approve protected write",
                "interaction_contract": {
                    "user_channel": {
                        "action_required": True,
                        "reason": "external write requires owner approval",
                    }
                },
                "user_todo_summary": {
                    "first_open_items": [
                        {
                            "todo_id": "todo_user_gate",
                            "text": "Approve external write.",
                            "task_class": "user_gate",
                            "decision_scope": {
                                "kind": "write_scope",
                                "granularity": "project",
                                "scope_key": "docs/**",
                                "reason_summary": "owner approves generated docs write",
                            },
                        }
                    ]
                },
            }
        raise AssertionError(f"unexpected json command: {args}")

    bridge.run_text = fake_run_text
    bridge.run_json = fake_run_json
    state = bridge.StateStore(Path(tempfile.mkdtemp()) / "state.json")
    plan_response = bridge.handle_text("/plan", "om_plan", state)
    assert plan_response and "Scheduler plan: run_parallel_batch" in plan_response, plan_response
    assert "Runnable: todo_docs, todo_read" in plan_response, plan_response
    next_response = bridge.handle_text("/next", "om_next", state)
    assert next_response and "Next batch: parallel_batch" in next_response, next_response
    assert "codex-devbox-req-a" in next_response, next_response
    bridge.handle_text("write the docs", "om_original", state)
    add_commands = [
        command
        for command in commands
        if command[:5] == ["loopx", "--registry", ".loopx/registry.json", "todo", "add"]
    ]
    assert add_commands, commands
    add_command = add_commands[-1]
    claimed_by = add_command[add_command.index("--claimed-by") + 1]
    assert claimed_by.startswith("codex-devbox-req-"), add_command
    assert claimed_by != "codex-devbox", add_command
    assert add_command[add_command.index("--safety-class") + 1] == "read_only", add_command
    tracked = state.todo("todo_abc")
    assert tracked["message_id"] == "om_original", tracked
    assert tracked["request_lane"] == claimed_by, tracked
    assert tracked["progress_message_id"] == "om_progress_reply", tracked
    assert cards and f"Progress lane: `{claimed_by}`" in cards[-1]["elements"][0]["text"]["content"], cards[-1]
    assert "Initial scheduler snapshot" in cards[-1]["elements"][0]["text"]["content"], cards[-1]
    assert "Next batch: parallel_batch" in cards[-1]["elements"][0]["text"]["content"], cards[-1]
    action_blocks = [element for element in cards[-1]["elements"] if element.get("tag") == "action"]
    assert action_blocks, cards[-1]
    action_ids = [button["value"]["action_id"] for button in action_blocks[0]["actions"]]
    assert "show_next_batch" in action_ids and "show_handoffs" in action_ids, action_ids

    bridge.handle_card_action(
        {
            "event": {
                "operator": {"open_id": "ou_operator"},
                "action": {
                    "value": {
                        "source": "loopx_feishu_progress_bridge",
                        "action_id": "show_handoffs",
                        "todo_id": "todo_abc",
                        "goal_id": "default",
                    }
                },
            }
        },
        state,
    )
    handoff_commands = [
        command
        for command in commands
        if command[:5] == ["loopx", "--registry", ".loopx/registry.json", "scheduler", "handoffs"]
    ]
    assert handoff_commands and "--todo-id" in handoff_commands[-1], commands
    handoff_replies = [command for command in commands if command[:3] == ["feishu-cli", "msg", "reply"] and "--text" in command]
    assert any("Worker handoffs: 1" in " ".join(command) for command in handoff_replies), handoff_replies

    sent = bridge.poll_progress_once(state)
    assert sent == 1, sent
    status_commands = [
        command
        for command in commands
        if command[:4] == ["loopx", "--registry", ".loopx/registry.json", "status"]
    ]
    quota_commands = [
        command
        for command in commands
        if command[:5] == ["loopx", "--registry", ".loopx/registry.json", "quota", "should-run"]
    ]
    assert status_commands, commands
    assert quota_commands, commands
    assert all("--agent-id" in command and claimed_by in command for command in status_commands), status_commands
    assert all("--agent-id" in command and claimed_by in command for command in quota_commands), quota_commands
    assert any(command[:3] == ["feishu-cli", "msg", "update"] for command in commands), commands
    assert any(command[:3] == ["feishu-cli", "msg", "reply"] for command in commands), commands

    bridge.handle_card_action(
        {
            "event": {
                "operator": {"open_id": "ou_operator"},
                "action": {
                    "value": {
                        "source": "loopx_feishu_progress_bridge",
                        "action_id": "approve_continue",
                        "todo_id": "todo_abc",
                        "goal_id": "default",
                        "user_todo_id": "todo_user_gate",
                        "decision_scope": {
                            "kind": "write_scope",
                            "granularity": "project",
                            "scope_key": "docs/**",
                        },
                    }
                },
            }
        },
        state,
    )
    complete_commands = [
        command
        for command in commands
        if command[:5] == ["loopx", "--registry", ".loopx/registry.json", "todo", "complete"]
    ]
    assert complete_commands, commands
    complete_command_text = " ".join(complete_commands[-1])
    assert "ou_operator" in complete_command_text, complete_command_text
    assert "write_scope/project/docs/**" in complete_command_text, complete_command_text
    audit = state.todo("todo_abc").get("action_audit")
    assert audit and audit[-1]["actor_id"] == "ou_operator", audit
    assert audit[-1]["decision_scope"]["scope_key"] == "docs/**", audit

    wrapper = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "feishu-bridge", "print-launch-agent"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    plist = plistlib.loads(wrapper.stdout)
    assert plist["Label"] == "dev.loopx.feishu-progress-bridge", plist
    assert plist["KeepAlive"]["SuccessfulExit"] is False, plist

    print("feishu progress bridge e2e smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
