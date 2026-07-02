#!/usr/bin/env python3
"""Smoke-test the Codex app-server Goal turn driver with a fake codex binary."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "codex_app_server_goal_driver.py"


FAKE_CODEX = """#!/usr/bin/env python3
import json
import time
import sys

for line in sys.stdin:
    msg = json.loads(line)
    mid = msg.get("id")
    method = msg.get("method")
    if method == "initialized":
        continue
    if method == "initialize":
        result = {"serverInfo": {"name": "fake-codex"}}
    elif method == "thread/start":
        result = {"thread": {"id": "thread-smoke"}}
    elif method == "thread/goal/set":
        result = {"goal": {"threadId": "thread-smoke", "status": "active"}}
    elif method == "thread/goal/get":
        result = {"goal": {"threadId": "thread-smoke", "status": "active"}}
    elif method == "turn/start":
        if msg.get("params", {}).get("effort") not in {"high", "xhigh"}:
            print(json.dumps({
                "id": mid,
                "error": {"code": -32602, "message": "missing supported effort"},
            }), flush=True)
            continue
        prompt_text = msg.get("params", {}).get("input", [{}])[0].get("text", "")
        if "event-style completion" in prompt_text:
            result = {"turn": {"id": "turn-event-msg-smoke", "status": "running"}}
            print(json.dumps({"id": mid, "result": result}), flush=True)
            print(json.dumps({
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "call-event-style-smoke",
                },
            }), flush=True)
            print(json.dumps({
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-event-style-smoke",
                },
            }), flush=True)
            print(json.dumps({
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Event style final answer."}
                    ],
                },
            }), flush=True)
            print(json.dumps({
                "type": "event_msg",
                "payload": {"type": "task_complete"},
            }), flush=True)
            continue
        if "session-file completion" in prompt_text:
            result = {"turn": {"id": "turn-session-file-smoke", "status": "running"}}
            print(json.dumps({"id": mid, "result": result}), flush=True)
            with open("rollout-fake-session-smoke.jsonl", "a", encoding="utf-8") as session:
                session.write(json.dumps({
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Session file final answer."}
                        ],
                    },
                }) + "\\n")
                session.write(json.dumps({
                    "type": "event_msg",
                    "payload": {"type": "task_complete"},
                }) + "\\n")
                session.flush()
                time.sleep(30)
            continue
        print(json.dumps({
            "method": "turn/started",
            "params": {
                "threadId": "thread-smoke",
                "turn": {"id": "turn-event-smoke", "status": "inProgress"},
            },
        }), flush=True)
        print(json.dumps({
            "method": "item/started",
            "params": {
                "threadId": "thread-smoke",
                "turnId": "turn-event-smoke",
                "item": {
                    "id": "user-item-smoke",
                    "type": "userMessage",
                    "content": [{"type": "text", "text": prompt_text}],
                },
            },
        }), flush=True)
        print(json.dumps({
            "method": "item/completed",
            "params": {
                "threadId": "thread-smoke",
                "turnId": "turn-event-smoke",
                "item": {
                    "id": "user-item-smoke",
                    "type": "userMessage",
                    "content": [{"type": "text", "text": prompt_text}],
                },
            },
        }), flush=True)
        result = {"turn": {"id": "turn-response-smoke", "status": "running"}}
        print(json.dumps({"id": mid, "result": result}), flush=True)
        print(json.dumps({
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thread-smoke",
                "turnId": "turn-event-smoke",
                "itemId": "item-smoke",
                "delta": "Synthetic final answer.",
            },
        }), flush=True)
        print(json.dumps({
            "method": "turn/completed",
            "params": {
                "threadId": "thread-smoke",
                "turn": {"id": "turn-event-smoke", "status": "completed"},
            },
        }), flush=True)
        continue
    else:
        result = {}
    print(json.dumps({"id": mid, "result": result}), flush=True)
"""


def _load_module():
    spec = importlib.util.spec_from_file_location("codex_app_server_goal_driver", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_module()
    with tempfile.TemporaryDirectory(prefix="gh-codex-app-server-smoke-") as tmp:
        root = Path(tmp)
        fake = root / "codex"
        fake.write_text(FAKE_CODEX, encoding="utf-8")
        fake.chmod(0o755)
        turn = module.start_codex_app_server_goal_turn(
            codex_bin=str(fake),
            work_dir=root / "work",
            objective="Synthetic objective.",
            prompt="Synthetic prompt.",
            model_name="gpt-5.5",
            reasoning_effort="high",
            response_timeout_sec=5,
        )
        try:
            assert turn.thread_id == "thread-smoke"
            assert turn.turn_id == "turn-event-smoke"
            compact = module.compact_turn_metadata(turn)
            assert compact["schema_version"] == "codex_app_server_goal_turn_driver_v0"
            assert compact["thread_id_present"] is True
            assert compact["goal_get_present"] is True
            assert compact["goal_status"] == "active"
            assert compact["turn_id_present"] is True
            assert compact["turn_id_source"] == "event_stream", compact
            assert compact["turn_start_response_turn_id_present"] is True, compact
            assert compact["turn_event_stream_turn_id_present"] is True, compact
            assert compact["turn_completed_observed"] is False
            assert compact["user_message_item_count"] == 1, compact
            assert compact["agent_message_item_count"] == 0, compact
            assert compact["raw_transcript_recorded"] is False
            assert "Synthetic prompt" not in json.dumps(compact)
            observed = module.observe_codex_app_server_goal_turn(
                turn,
                timeout_sec=5,
                until_completed=True,
            )
            assert observed is True
            compact = module.compact_turn_metadata(turn)
            assert compact["turn_completed_observed"] is True, compact
            assert compact["assistant_message_present"] is True, compact
            assert compact["user_message_item_count"] == 1, compact
            assert compact["agent_message_item_count"] == 0, compact
            assert "Synthetic final answer." not in json.dumps(compact), compact
        finally:
            turn.terminate()

        completed_turn = module.start_codex_app_server_goal_turn(
            codex_bin=str(fake),
            work_dir=root / "work-completed",
            objective="Synthetic objective.",
            prompt="Synthetic prompt.",
            model_name="gpt-5.5",
            reasoning_effort="high",
            response_timeout_sec=5,
            wait_for_completion=True,
            turn_timeout_sec=5,
        )
        try:
            assert completed_turn.assistant_message == "Synthetic final answer."
            compact = module.compact_turn_metadata(completed_turn)
            assert compact["turn_completed_observed"] is True, compact
            assert compact["turn_status"] == "completed", compact
            assert compact["assistant_message_present"] is True, compact
            assert compact["assistant_message_chars"] == len("Synthetic final answer.")
            assert compact["assistant_message_sha256"], compact
            assert compact["raw_assistant_message_recorded"] is False, compact
            assert "Synthetic final answer." not in json.dumps(compact), compact
        finally:
            completed_turn.terminate()

        xhigh_turn = module.start_codex_app_server_goal_turn(
            codex_bin=str(fake),
            work_dir=root / "work-xhigh",
            objective="Synthetic objective.",
            prompt="Synthetic prompt.",
            model_name="gpt-5.5",
            reasoning_effort="xhigh",
            response_timeout_sec=5,
            wait_for_completion=True,
            turn_timeout_sec=5,
        )
        try:
            assert xhigh_turn.assistant_message == "Synthetic final answer."
            compact = module.compact_turn_metadata(xhigh_turn)
            assert compact["turn_completed_observed"] is True, compact
            assert compact["assistant_message_present"] is True, compact
        finally:
            xhigh_turn.terminate()

        event_completed_turn = module.start_codex_app_server_goal_turn(
            codex_bin=str(fake),
            work_dir=root / "work-event-completed",
            objective="Synthetic objective.",
            prompt="Synthetic event-style completion prompt.",
            model_name="gpt-5.5",
            reasoning_effort="high",
            response_timeout_sec=5,
            wait_for_completion=True,
            turn_timeout_sec=5,
        )
        try:
            compact = module.compact_turn_metadata(event_completed_turn)
            assert compact["turn_id_present"] is True, compact
            assert compact["turn_completed_observed"] is True, compact
            assert compact["turn_status"] == "completed", compact
            assert compact["assistant_message_present"] is True, compact
            assert compact["assistant_message_chars"] == len(
                "Event style final answer."
            )
            assert compact["non_user_item_completed_count"] >= 3, compact
            assert "event_msg:task_complete" in compact["notifications"], compact
            assert "response_item:function_call" in compact["notifications"], compact
            assert "Event style final answer." not in json.dumps(compact), compact
        finally:
            event_completed_turn.terminate()

        session_completed_turn = module.start_codex_app_server_goal_turn(
            codex_bin=str(fake),
            work_dir=root / "work-session-completed",
            objective="Synthetic objective.",
            prompt="Synthetic session-file completion prompt.",
            model_name="gpt-5.5",
            reasoning_effort="high",
            response_timeout_sec=5,
            wait_for_completion=True,
            turn_timeout_sec=5,
        )
        try:
            compact = module.compact_turn_metadata(session_completed_turn)
            assert compact["turn_id_present"] is True, compact
            assert compact["turn_completed_observed"] is True, compact
            assert compact["turn_status"] == "completed", compact
            assert compact["session_log_observed"] is True, compact
            assert compact["session_event_count"] >= 2, compact
            assert compact["session_task_complete_observed"] is True, compact
            assert compact["assistant_message_present"] is True, compact
            assert compact["assistant_message_chars"] == len(
                "Session file final answer."
            )
            assert "event_msg:task_complete" in compact["notifications"], compact
            assert "Session file final answer." not in json.dumps(compact), compact
        finally:
            session_completed_turn.terminate()

    print("codex app-server goal driver smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
