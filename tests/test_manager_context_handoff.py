import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from loopx.capabilities.manager_context import (
    POLICY_SCHEMA,
    _root,
    _write,
    acknowledge,
    authority,
    deliver,
    pending,
    register_ingress,
    turn_start_hook,
)
from loopx.control_plane.capability_hooks import dispatch_turn_start_hooks


@pytest.fixture
def fixture(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": "research",
                        "repo": str(tmp_path),
                        "coordination": {"registered_agents": ["worker"]},
                    },
                    {
                        "id": "other",
                        "repo": str(tmp_path),
                        "coordination": {"registered_agents": ["peer"]},
                    },
                ]
            }
        )
    )
    session = {"session_id": "manager-session", "channel_id": "manager"}
    turn = {
        "client_turn_id": "request-one",
        "origin": "web",
        "message": "Consider this new method against current evidence; replan only when justified.",
    }
    return (
        tmp_path,
        registry,
        session,
        turn,
        {"goal_id": "research", "agent_id": "worker"},
    )


def test_original_context_delivery_is_idempotent_without_priority_or_todo_writes(
    fixture,
):
    root, registry, session, turn, request = fixture
    with ThreadPoolExecutor(max_workers=4) as executor:
        receipts = list(
            executor.map(
                lambda _: deliver(
                    root, registry, session=session, turn=turn, request=request
                ),
                range(4),
            )
        )
    assert sum(not r["replayed"] for r in receipts) == 1
    assert len({r["request_id"] for r in receipts}) == 1
    assert all(
        not r["priority_changed"]
        and not r["todo_created"]
        and not r["execution_interrupted"]
        for r in receipts
    )
    assert pending(root, "research", "worker")["items"][0]["message"] == turn["message"]
    assert not pending(root, "other", "peer")["items"]
    files = list((root / ".local").rglob("*.json"))
    assert len(files) == 2  # original intent and its exact return route
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in files)
    with pytest.raises(ValueError, match="identity conflict"):
        deliver(
            root,
            registry,
            session=session,
            turn={**turn, "message": "changed"},
            request=request,
        )
    with pytest.raises(ValueError):
        deliver(
            root,
            registry,
            session=session,
            turn=turn,
            request={**request, "priority": "P0"},
        )


def test_external_authority_requires_exact_sender_source_and_recipient(fixture):
    root, registry, session, turn, request = fixture
    session["channel_id"] = "manager.external.group"
    turn["origin"] = "lark"
    _write(
        _root(root) / "policy.json",
        {
            "schema_version": POLICY_SCHEMA,
            "sources": {
                session["channel_id"]: {"sender_ids": ["owner"], "targets": [request]}
            },
        },
    )
    assert not authority(root, registry, session, turn)["targets"]
    register_ingress(
        root,
        session_id=session["session_id"],
        client_turn_id=turn["client_turn_id"],
        channel=session["channel_id"],
        sender_id="owner",
        message=turn["message"],
        source_id="lark:original",
    )
    assert authority(root, registry, session, turn)["targets"] == [request]
    assert not authority(root, registry, session, {**turn, "message": "forged"})[
        "targets"
    ]
    assert not authority(root, registry, session, {**turn, "origin": "web"})["targets"]
    with pytest.raises(ValueError):
        deliver(
            root,
            registry,
            session=session,
            turn=turn,
            request={"goal_id": "other", "agent_id": "peer"},
        )
    receipt = deliver(root, registry, session=session, turn=turn, request=request)
    # Revocation is checked before replay, not cached as a permanent grant.
    _write(
        _root(root) / "policy.json", {"schema_version": POLICY_SCHEMA, "sources": {}}
    )
    with pytest.raises(ValueError):
        deliver(root, registry, session=session, turn=turn, request=request)
    assert receipt["status"] == "delivered"


def test_hook_keeps_decided_requests_open_until_receiver_returns_conclusion(
    fixture,
):
    root, registry, session, turn, request = fixture
    receipt = deliver(root, registry, session=session, turn=turn, request=request)
    dispatch = dispatch_turn_start_hooks(
        [turn_start_hook(root, registry, "research", "worker")]
    )
    assert not dispatch["failures"]
    assert dispatch["required_reads"][0]["ordering"] == "before_work"
    assert "manager-inbox read" in dispatch["required_reads"][0]["command"]
    assert turn["message"] not in json.dumps(dispatch)
    assert dispatch["results"][0]["agent_read_required"]
    acknowledge(
        root,
        "research",
        "worker",
        receipt["request_id"],
        "no_change",
        "Current experiment still has stronger evidence; retain its order.",
    )
    assert pending(root, "research", "worker")["items"][0]["receiver_decision_recorded"]
    from loopx.capabilities.manager_context.roundtrip import report

    report(
        root,
        "research",
        "worker",
        receipt["request_id"],
        "conclusion",
        "Current evidence supports retaining the existing experiment; no plan change.",
    )
    assert not pending(root, "research", "worker")["items"]
    assert not dispatch_turn_start_hooks(
        [turn_start_hook(root, registry, "research", "worker")]
    )["required_reads"]
    assert deliver(root, registry, session=session, turn=turn, request=request)[
        "replayed"
    ]
    assert not pending(root, "research", "worker")["items"]
    with pytest.raises((ValueError, OSError)):
        acknowledge(
            root, "other", "peer", receipt["request_id"], "adopt", "Wrong target"
        )


def test_actual_manager_turn_delivers_and_reports_host_receipt(fixture, monkeypatch):
    from loopx.chat_runtime import ChatRuntimeController
    from loopx.chat_store import ChatSessionStore
    import loopx.chat_manager_context as manager_context

    root, registry, _session, turn, request = fixture
    original_registry = registry.read_bytes()
    store = ChatSessionStore(root)
    controller = ChatRuntimeController(
        store=store, codex_bin="codex", registry_path=registry
    )

    class Adapter:
        upstream_thread_id = "fixture-upstream"

        def healthcheck(self):
            return True

        def close_session(self):
            pass

        def start_turn(self, message, sink):
            assert "context_delegation" in message
            return {
                "message": "Preparing handoff",
                "context_handoff": request,
                "proposals": [],
                "gate": None,
            }

    monkeypatch.setattr(
        controller,
        "capabilities",
        lambda: [
            {"agent_id": "codex", "available": True, "adapter_kind": "codex_app_server"}
        ],
    )
    monkeypatch.setattr(controller, "_start_adapter", lambda **kw: Adapter())
    monkeypatch.setattr(
        manager_context,
        "collect_manager_turn_context",
        lambda *a: {"coverage": {}, "goals": []},
    )
    try:
        session, _ = controller.open_session(
            goal_id="loopx-manager",
            agent_id="codex",
            work_dir=root,
            objective="manager",
            mode="resume_latest",
            channel_id="manager",
        )
        accepted, created = controller.submit_turn(
            session_id=session["session_id"],
            client_turn_id=turn["client_turn_id"],
            message=turn["message"],
            work_dir=root,
            objective="manager",
        )
        completed = controller.wait_for_turn(
            session_id=session["session_id"], turn_id=accepted["turn_id"], timeout_sec=5
        )
        assert created and completed["status"] == "completed", completed
        response = completed["response"]
        assert response["context_handoff_receipt"]["status"] == "delivered"
        assert "已将原消息交给 worker" in response["message"]
        assert response["proposals"] == [] and response["gate"] is None
        assert len(pending(root, "research", "worker")["items"]) == 1
        assert registry.read_bytes() == original_registry
    finally:
        controller.close()


def test_provider_wrapper_is_not_forwarded_and_large_registry_is_supported(fixture):
    root, registry, session, turn, request = fixture
    data = json.loads(registry.read_text())
    data["unrelated_metadata"] = "x" * 180000
    registry.write_text(json.dumps(data))
    assert request in authority(root, registry, session, turn)["targets"]
    session["channel_id"] = "manager.external.group"
    turn["origin"] = "lark"
    _write(
        _root(root) / "policy.json",
        {
            "schema_version": POLICY_SCHEMA,
            "sources": {
                session["channel_id"]: {"sender_ids": ["owner"], "targets": [request]}
            },
        },
    )
    register_ingress(
        root,
        session_id=session["session_id"],
        client_turn_id=turn["client_turn_id"],
        channel=session["channel_id"],
        sender_id="owner",
        message=turn["message"],
        source_id="lark:original",
        source_message="Original user intent",
    )
    deliver(root, registry, session=session, turn=turn, request=request)
    assert (
        pending(root, "research", "worker")["items"][0]["message"]
        == "Original user intent"
    )


def test_lark_bridge_registers_provenance_before_queueing(fixture):
    from types import SimpleNamespace
    from loopx.extensions.lark.goal_topic_runtime import answer_lark_goal_topic

    root, registry, session, _turn, request = fixture
    session.update(channel_id="manager.external.group", agent_id="codex", status="open")
    _write(
        _root(root) / "policy.json",
        {
            "schema_version": POLICY_SCHEMA,
            "sources": {
                session["channel_id"]: {"sender_ids": ["owner"], "targets": [request]}
            },
        },
    )

    class Controller:
        store = SimpleNamespace(root=root / "chat", load_session=lambda _sid: session)

        def enqueue_turn(self, **kw):
            assert kw["origin"] == "lark"
            assert authority(root, registry, session, kw)["targets"] == [request]
            deliver(root, registry, session=session, turn=kw, request=request)
            return {"turn_id": "fixture-turn"}, True

        def wait_for_turn(self, **_kw):
            return {"status": "completed", "response": {"message": "Delivered"}}

    route = {
        "goal_id": "manager",
        "session_id": session["session_id"],
        "conversation_kind": "manager",
        "executor_endpoint_id": "codex",
        "manager_channel_id": session["channel_id"],
        "ingress_mode": "session_queue",
        "source_sender_id": "owner",
        "message_id": "provider-original",
        "topic_root_message_id": "topic",
    }
    assert (
        answer_lark_goal_topic(
            route=route,
            text="Original intent",
            work_dir=root,
            objective="manager",
            runtime_controller=Controller(),
        )
        == "Delivered"
    )
    assert (
        pending(root, "research", "worker")["items"][0]["message"] == "Original intent"
    )
