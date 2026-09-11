"""Manager scope, restart migration and per-turn Core evidence contracts."""

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
        "reasoning_effort": "high",
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
        {"channel_id": "manager.external.fixture", "goal_id": "old-anchor"},
        tmp_path,
        authorized_goal_ids=["allowed"],
    )
    assert calls == [None, ["allowed"]]
    missing = context.manager_turn_context(None, {"channel_id": "manager"}, tmp_path)
    assert missing["coverage"]["discovered"] is None
    assert missing["warnings"] == ["registry_unavailable"]


class Adapter:
    upstream_thread_id = "fresh-upstream"

    def __init__(self):
        self.messages = []
        self.closed = False

    def healthcheck(self):
        return True

    def start_turn(self, message, sink):
        self.messages.append(message)
        return {"answer": "fixture response"}

    def close_session(self):
        self.closed = True


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

    def fresh(*args, **kwargs):
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


def test_external_session_anchor_never_supplies_read_authority(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        context,
        "build_goal_portfolio",
        lambda **kwargs: calls.append(kwargs) or {"goals": []},
    )
    result = context.collect_manager_turn_context(
        tmp_path / "registry.json",
        {"channel_id": "manager.external.fixture", "goal_id": "old-private-anchor"},
        tmp_path,
    )
    assert calls == []
    assert result["coverage"]["discovered"] is None
    assert result["warnings"] == ["external_authorization_unavailable"]


def test_external_authority_is_rechecked_after_collection(monkeypatch, tmp_path):
    def collect(**kwargs):
        assert kwargs["goal_ids"] == ["currently-authorized"]
        return {"goals": [{"goal_id": "currently-authorized", "quality": "verified"}]}

    monkeypatch.setattr(context, "build_goal_portfolio", collect)
    grants = iter([["currently-authorized"], []])
    result = context.collect_manager_turn_context(
        tmp_path / "registry.json",
        {"channel_id": "manager.external.fixture", "goal_id": "old-private-anchor"},
        tmp_path,
        lambda session: next(grants),
    )
    assert result["goals"] == []
    assert result["warnings"] == ["external_authorization_changed"]


def test_empty_external_authority_never_reaches_the_model(monkeypatch, tmp_path):
    store = ChatSessionStore(tmp_path / "runtime")
    runtime = ChatRuntimeController(
        store=store,
        codex_bin="codex",
        registry_path=tmp_path / "registry.json",
        manager_scope_resolver=lambda _session: [],
    )
    adapter = Adapter()
    session = store.create_session(
        goal_id="previously-authorized",
        agent_id="codex",
        adapter_kind="codex_app_server",
        upstream_thread_id="old-upstream",
        channel_id="manager.external.fixture",
        upstream_mode="chat",
        codex_home=str(runtime.codex_home),
    )
    runtime.adapters[session["session_id"]] = adapter
    try:
        turn, _ = runtime.submit_turn(
            session_id=session["session_id"],
            client_turn_id="revoked-scope",
            message="What changed?",
            work_dir=tmp_path,
            objective="manager",
        )
        done = runtime.wait_for_turn(
            session_id=session["session_id"], turn_id=turn["turn_id"], timeout_sec=5
        )
        assert done["status"] == "failed"
        assert done["error_code"] == "manager_authorization_unavailable"
        assert adapter.messages == []
    finally:
        runtime.close()


def test_changed_external_scope_rotates_upstream_before_model_call(
    monkeypatch, tmp_path
):
    store = ChatSessionStore(tmp_path / "runtime")
    runtime = ChatRuntimeController(store=store, codex_bin="codex")
    old_adapter = Adapter()
    replacement = Adapter()
    replacement.upstream_thread_id = "replacement-upstream"
    starts = []
    monkeypatch.setattr(
        context,
        "collect_manager_turn_context",
        lambda *_args: {
            "schema_version": "manager_turn_context_v1",
            "authorization_scope_id": context.manager_authorization_scope_id(
                ["newly-authorized"]
            ),
            "coverage": {"discovered": 1, "verified": 1, "complete": True},
            "goals": [{"goal_id": "newly-authorized"}],
        },
    )

    def start(**kwargs):
        starts.append(kwargs)
        return replacement

    monkeypatch.setattr(runtime, "_start_adapter", start)
    session = store.create_session(
        goal_id="previously-authorized",
        agent_id="codex",
        adapter_kind="codex_app_server",
        upstream_thread_id="old-upstream",
        channel_id="manager.external.fixture",
        upstream_mode="chat",
        codex_home=str(runtime.codex_home),
    )
    store.update_session(
        session["session_id"],
        manager_authorization_scope_id=context.manager_authorization_scope_id(
            ["previously-authorized"]
        ),
    )
    runtime.adapters[session["session_id"]] = old_adapter
    try:
        turn, _ = runtime.submit_turn(
            session_id=session["session_id"],
            client_turn_id="changed-scope",
            message="What changed?",
            work_dir=tmp_path,
            objective="manager",
        )
        done = runtime.wait_for_turn(
            session_id=session["session_id"], turn_id=turn["turn_id"], timeout_sec=5
        )
        assert done["status"] == "completed"
        assert old_adapter.closed
        assert len(starts) == 1
        assert starts[0]["resume_thread_id"] is None
        assert starts[0]["history"] is None
        assert "newly-authorized" in replacement.messages[0]
        persisted = store.load_session(session["session_id"])
        assert persisted["upstream_thread_id"] == "replacement-upstream"
        assert persisted["manager_authorization_scope_id"] == (
            context.manager_authorization_scope_id(["newly-authorized"])
        )
        retry, _ = runtime.submit_turn(
            session_id=session["session_id"],
            client_turn_id="same-scope-retry",
            message="And now?",
            work_dir=tmp_path,
            objective="manager",
        )
        retried = runtime.wait_for_turn(
            session_id=session["session_id"], turn_id=retry["turn_id"], timeout_sec=5
        )
        assert retried["status"] == "completed"
        assert len(starts) == 1
        assert len(replacement.messages) == 2
    finally:
        runtime.close()


def test_current_external_scope_is_fresh_and_excludes_other_labels(
    monkeypatch, tmp_path
):
    import json
    import loopx.goal_portfolio as portfolio

    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {"id": "old-private-anchor", "display_name": "PRIVATE-OLD-LABEL"},
                    {"id": "currently-authorized", "display_name": "Allowed label"},
                ]
            }
        )
    )
    reads = []

    def read(goal, **kwargs):
        reads.append(goal["id"])
        return {"goal_id": goal["id"], "quality": "verified", "warnings": []}

    monkeypatch.setattr(portfolio, "_read_goal", read)
    grant = ["currently-authorized"]
    session = {
        "channel_id": "manager.external.fixture",
        "goal_id": "old-private-anchor",
    }
    result = context.collect_manager_turn_context(
        registry, session, tmp_path, lambda _: grant
    )
    assert reads == ["currently-authorized"]
    assert [g["goal_id"] for g in result["goals"]] == grant
    assert "PRIVATE-OLD-LABEL" not in json.dumps(result)
    grant.clear()
    revoked = context.collect_manager_turn_context(
        registry, session, tmp_path, lambda _: grant
    )
    assert revoked["goals"] == []
    assert reads == ["currently-authorized"]
