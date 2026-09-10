"""Manager scope, restart migration and per-turn Core evidence contracts."""

import json
from pathlib import Path

import pytest

import loopx.chat_manager_context as context
from loopx.chat_manager import (
    MANAGER_CONTEXT_VERSION,
    manager_model_config,
    manager_workspace,
)
from loopx.chat_runtime import ChatRuntimeController
from loopx.chat_store import ChatSessionStore


def test_manager_defaults_are_independent_of_worker_configuration(monkeypatch):
    monkeypatch.delenv("LOOPX_MANAGER_MODEL", raising=False)
    monkeypatch.delenv("LOOPX_MANAGER_REASONING_EFFORT", raising=False)
    assert manager_model_config() == {
        "model": "gpt-6-astra",
        "reasoning_effort": "medium",
    }
    monkeypatch.setenv("LOOPX_MANAGER_MODEL", "fixture-model")
    monkeypatch.setenv("LOOPX_MANAGER_REASONING_EFFORT", "low")
    assert manager_model_config() == {
        "model": "fixture-model",
        "reasoning_effort": "low",
    }
    monkeypatch.setenv("LOOPX_MANAGER_REASONING_EFFORT", "typo")
    with pytest.raises(ValueError):
        manager_model_config()


def test_context_scopes_before_read_and_missing_registry_is_unknown(
    monkeypatch, tmp_path
):
    calls = []

    def collect(**kwargs):
        calls.append(kwargs["goal_ids"])
        return {"goals": [], "coverage": {"discovered": 0, "complete": False}}

    monkeypatch.setattr(context, "build_goal_portfolio", collect)
    context.manager_turn_context(
        tmp_path / "registry.json",
        {"channel_id": "manager", "goal_id": "anchor"},
        tmp_path,
    )
    context.manager_turn_context(
        tmp_path / "registry.json",
        {"channel_id": "manager.external.fixture", "goal_id": "allowed"},
        tmp_path,
    )
    assert calls == [None, ["allowed"]]
    missing = context.manager_turn_context(None, {"channel_id": "manager"}, tmp_path)
    assert missing["coverage"]["discovered"] is None
    assert missing["warnings"] == ["registry_unavailable"]


class Adapter:
    upstream_thread_id = "fresh-upstream"

    def __init__(self):
        self.messages = []

    def healthcheck(self):
        return True

    def start_turn(self, message, sink):
        self.messages.append(message)
        return {"answer": "fixture response"}

    def close_session(self):
        pass


def test_legacy_manager_migrates_without_project_and_refreshes_each_turn(
    monkeypatch, tmp_path
):
    store = ChatSessionStore(tmp_path / "runtime" / "chat")
    runtime = ChatRuntimeController(
        store=store, codex_bin="codex", registry_path=tmp_path / "registry.json"
    )
    monkeypatch.setattr(
        runtime,
        "capabilities",
        lambda: [
            {"agent_id": "codex", "available": True, "adapter_kind": "codex_app_server"}
        ],
    )
    adapter = Adapter()
    starts = []

    def start(**kwargs):
        starts.append(kwargs)
        return adapter

    monkeypatch.setattr(runtime, "_start_adapter", start)
    legacy = store.create_session(
        goal_id="old-project",
        agent_id="codex",
        adapter_kind="codex_app_server",
        upstream_thread_id="old-project-thread",
        channel_id="manager",
        upstream_mode="chat",
        codex_home=str(runtime.codex_home),
    )
    session, resumed = runtime.open_session(
        goal_id="different-project",
        agent_id="codex",
        work_dir=tmp_path / "project",
        objective="old project instructions",
        mode="resume_latest",
        channel_id="manager",
    )
    assert resumed and session["session_id"] == legacy["session_id"]
    assert session["goal_id"] == "loopx-manager"
    assert session["manager_context_version"] == MANAGER_CONTEXT_VERSION
    assert starts[0]["resume_thread_id"] is None
    assert starts[0]["work_dir"] == manager_workspace(store.root)
    assert "global LoopX manager" in starts[0]["objective"]
    snapshots = []

    def fresh(*args):
        snapshot = {
            "snapshot_id": f"evidence-{len(snapshots)}",
            "coverage": {"discovered": len(snapshots) + 1},
        }
        snapshots.append(snapshot)
        return snapshot

    monkeypatch.setattr(context, "manager_turn_context", fresh)
    try:
        for index in range(2):
            turn, created = runtime.submit_turn(
                session_id=session["session_id"],
                client_turn_id=f"request-{index}",
                message="Which Goals?",
                work_dir=tmp_path / "project",
                objective="wrong project",
            )
            assert created
            done = runtime.wait_for_turn(
                session_id=session["session_id"], turn_id=turn["turn_id"], timeout_sec=5
            )
            assert done["status"] == "completed", done
            events = store.events_after(session["session_id"], turn["turn_id"], None)
            assert any(
                e["kind"] == "manager.context"
                and e["payload"]["snapshot_id"] == f"evidence-{index}"
                for e in events
            )
        assert "evidence-0" in adapter.messages[0]
        assert "evidence-1" in adapter.messages[1]
        assert len(starts) == 1
        # Stored requests remain original; the derived evidence is a separate receipt.
        assert all(
            m.get("text") == "Which Goals?"
            for m in store.messages(session["session_id"])
            if m["role"] == "user"
        )
    finally:
        runtime.close()
