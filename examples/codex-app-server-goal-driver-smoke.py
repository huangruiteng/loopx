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
        if msg.get("params", {}).get("effort") != "high":
            print(json.dumps({
                "id": mid,
                "error": {"code": -32602, "message": "missing high effort"},
            }), flush=True)
            continue
        result = {"turn": {"id": "turn-smoke", "status": "running"}}
        print(json.dumps({"id": mid, "result": result}), flush=True)
        print(json.dumps({
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thread-smoke",
                "turnId": "turn-smoke",
                "itemId": "item-smoke",
                "delta": "Synthetic final answer.",
            },
        }), flush=True)
        print(json.dumps({
            "method": "turn/completed",
            "params": {
                "threadId": "thread-smoke",
                "turn": {"id": "turn-smoke", "status": "completed"},
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
            assert turn.turn_id == "turn-smoke"
            compact = module.compact_turn_metadata(turn)
            assert compact["schema_version"] == "codex_app_server_goal_turn_driver_v0"
            assert compact["thread_id_present"] is True
            assert compact["goal_get_present"] is True
            assert compact["goal_status"] == "active"
            assert compact["turn_id_present"] is True
            assert compact["turn_completed_observed"] is False
            assert compact["raw_transcript_recorded"] is False
            assert "Synthetic prompt" not in json.dumps(compact)
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

    print("codex app-server goal driver smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
