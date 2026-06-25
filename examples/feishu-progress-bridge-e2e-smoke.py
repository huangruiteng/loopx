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

    def fake_run_text(args: list[str], *, cwd: Path = bridge.CONTROL_ROOT, timeout: float = 30) -> str:
        commands.append(list(args))
        if args[:4] == ["loopx", "--registry", ".loopx/registry.json", "todo"] and args[4] == "add":
            return "added todo_abc"
        if args[:3] == ["feishu-cli", "msg", "reply"]:
            if "--text" in args:
                return json.dumps({"message_id": "om_text_ack"})
            return json.dumps({"message_id": "om_progress_reply"})
        if args[:3] == ["feishu-cli", "msg", "update"]:
            return json.dumps({"message_id": args[3]})
        if args[:4] == ["loopx", "--registry", ".loopx/registry.json", "todo"]:
            return json.dumps({"ok": True})
        raise AssertionError(f"unexpected command: {args}")

    bridge.run_text = fake_run_text
    bridge.loopx_status_payload = lambda: {}
    bridge.loopx_quota_payload = lambda goal_id: {
        "goal_id": goal_id,
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

    state = bridge.StateStore(Path(tempfile.mkdtemp()) / "state.json")
    bridge.handle_text("write the docs", "om_original", state)
    tracked = state.todo("todo_abc")
    assert tracked["message_id"] == "om_original", tracked
    assert tracked["progress_message_id"] == "om_progress_reply", tracked

    sent = bridge.poll_progress_once(state)
    assert sent == 1, sent
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
