from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from loopx.attached_session import (
    bind_attached_agent_session,
    claim_attached_agent_turn,
    complete_attached_agent_turn,
)
from loopx.chat_agent import CodexChatAgentError
from loopx.chat_runtime import ChatRuntimeController
from loopx.chat_server import ChatRequestHandler
from loopx.chat_store import CHAT_SESSION_MODE_ATTACHED, ChatSessionStore
from loopx.extensions.lark.goal_topic_runtime import answer_lark_goal_topic

GOAL_ID = "sample-goal"
AGENT_ID = "codex-sample-worker"
HOST_SURFACE = "codex-app-ssh"
HOST_SESSION_ID = "opaque-host-session"


def _registry() -> dict[str, object]:
    return {
        "goals": [
            {
                "id": GOAL_ID,
                "coordination": {
                    "registered_agents": [AGENT_ID],
                    "thread_agent_bindings": [
                        {
                            "host_surface": HOST_SURFACE,
                            "thread_id": HOST_SESSION_ID,
                            "agent_id": AGENT_ID,
                        }
                    ],
                },
            }
        ]
    }


def _bind(store: ChatSessionStore) -> dict[str, object]:
    packet = bind_attached_agent_session(
        store=store,
        registry=_registry(),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        executor_endpoint_id="codex",
        execute=True,
    )
    assert packet["created"] is True
    return packet


def _delete_session(
    runtime: ChatRuntimeController,
    session_id: str,
) -> list[dict[str, object]]:
    responses: list[dict[str, object]] = []

    class Handler:
        path = f"/api/chat/sessions/{session_id}"
        server = SimpleNamespace(runtime_controller=runtime)

        def _require_loopback_origin(self) -> bool:
            return True

        def _send_error(self, message: str, **kwargs: object) -> None:
            responses.append({"ok": False, "error": message, **kwargs})

        def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
            responses.append({**payload, "status": status})

        def _close_session(self, target_session_id: str) -> None:
            ChatRequestHandler._close_session(self, target_session_id)  # type: ignore[arg-type]

    ChatRequestHandler.do_DELETE(Handler())  # type: ignore[arg-type]
    return responses


def test_bind_requires_exact_registered_thread_and_is_idempotent(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    preview = bind_attached_agent_session(
        store=store,
        registry=_registry(),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        executor_endpoint_id="codex",
        execute=False,
    )
    assert preview["changed"] is True
    assert not list(store.sessions_root.glob("*/session.json"))

    created = _bind(store)
    session = created["session"]
    assert session["agent_id"] == AGENT_ID
    assert session["executor_endpoint_id"] == "codex"
    assert session["session_mode"] == CHAT_SESSION_MODE_ATTACHED
    assert session["attached_capabilities"] == {
        "live_steering": False,
        "session_queue": True,
        "claim_wait": True,
        "reply_readback": True,
    }

    duplicate = bind_attached_agent_session(
        store=store,
        registry=_registry(),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        executor_endpoint_id="codex",
        execute=True,
    )
    assert duplicate["created"] is False
    assert duplicate["session"]["session_id"] == session["session_id"]

    with pytest.raises(ValueError, match="exact registered Agent"):
        bind_attached_agent_session(
            store=store,
            registry=_registry(),
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
            host_surface=HOST_SURFACE,
            host_session_id="different-host-session",
            executor_endpoint_id="codex",
            execute=True,
        )


def test_concurrent_bind_and_completion_are_duplicate_safe(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        packets = list(executor.map(lambda _index: _bind_or_reuse(store), range(2)))
    assert sorted(packet["created"] for packet in packets) == [False, True]
    session_id = str(packets[0]["session"]["session_id"])

    queued, created = store.create_queued_turn(
        session_id,
        client_turn_id="concurrent-completion",
        message="complete once",
        origin="web",
    )
    assert created
    claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="shared-claim",
    )

    def complete(_index: int) -> dict[str, object]:
        return complete_attached_agent_turn(
            store=store,
            session_id=session_id,
            turn_id=str(queued["turn_id"]),
            host_surface=HOST_SURFACE,
            host_session_id=HOST_SESSION_ID,
            claim_id="shared-claim",
            completion_id="shared-completion",
            response={"message": "one durable response"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        completions = list(executor.map(complete, range(2)))
    assert sorted(packet["created"] for packet in completions) == [False, True]
    agent_messages = [item for item in store.messages(session_id) if item["role"] == "agent"]
    assert len(agent_messages) == 1


def test_attached_host_can_wait_for_queue_wakeup(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])

    def queue_message() -> None:
        time.sleep(0.02)
        store.create_queued_turn(
            session_id,
            client_turn_id="wake-host",
            message="wake the attached host",
            origin="lark",
        )

    producer = threading.Thread(target=queue_message)
    producer.start()
    claimed = claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="wake-claim",
        wait_seconds=1,
    )
    producer.join(timeout=1)

    assert claimed["claimed"] is True
    assert claimed["waited"] is True
    assert claimed["turn"]["message"] == "wake the attached host"


def test_attached_host_claim_wait_is_bounded(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])

    with pytest.raises(ValueError, match="between 0 and 1800"):
        claim_attached_agent_turn(
            store=store,
            session_id=session_id,
            host_surface=HOST_SURFACE,
            host_session_id=HOST_SESSION_ID,
            claim_id="unbounded-claim",
            wait_seconds=1_801,
        )


def test_loopback_attach_api_binds_without_exposing_host_session(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    responses: list[dict[str, object]] = []

    class Handler:
        server = SimpleNamespace(chat_store=store)

        def _read_json(self) -> dict[str, str]:
            return {
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "host_surface": HOST_SURFACE,
                "host_session_id": HOST_SESSION_ID,
                "executor_endpoint_id": "codex",
            }

        def _registry_and_goal(
            self,
            goal_id: str,
        ) -> tuple[dict[str, object], dict[str, object]]:
            assert goal_id == GOAL_ID
            return _registry(), {"id": GOAL_ID}

        def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
            responses.append({**payload, "http_status": status})

        def _send_error(self, message: str, **_kwargs: object) -> None:
            responses.append({"ok": False, "error": message})

    ChatRequestHandler._attach_session(Handler())  # type: ignore[arg-type]

    assert responses[0]["http_status"] == 201
    session = responses[0]["session"]
    assert isinstance(session, dict)
    assert session["session_mode"] == CHAT_SESSION_MODE_ATTACHED
    assert "upstream_thread_id" not in session


def _bind_or_reuse(store: ChatSessionStore) -> dict[str, object]:
    return bind_attached_agent_session(
        store=store,
        registry=_registry(),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        executor_endpoint_id="codex",
        execute=True,
    )


def test_web_and_lark_share_ordered_attached_session_without_spawning(
    tmp_path: Path,
) -> None:
    store = ChatSessionStore(tmp_path)
    session = _bind(store)["session"]
    session_id = str(session["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")

    web_turn, web_created = runtime.submit_turn(
        session_id=session_id,
        client_turn_id="web-1",
        message="web question",
        work_dir=tmp_path,
        objective="sample objective",
    )
    lark_turn, lark_created = runtime.enqueue_turn(
        session_id=session_id,
        client_turn_id="lark-1",
        message="lark question",
        work_dir=tmp_path,
        objective="sample objective",
        origin="lark",
    )
    assert web_created and lark_created
    assert not runtime.adapters

    first = claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-web-1",
    )
    assert first["turn"]["turn_id"] == web_turn["turn_id"]
    assert first["turn"]["origin"] == "web"
    duplicate_claim = claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-web-1",
    )
    assert duplicate_claim["turn"]["turn_id"] == web_turn["turn_id"]

    completed = complete_attached_agent_turn(
        store=store,
        session_id=session_id,
        turn_id=str(web_turn["turn_id"]),
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-web-1",
        completion_id="complete-web-1",
        response={"message": "web answer"},
    )
    assert completed["created"] is True
    duplicate_completion = complete_attached_agent_turn(
        store=store,
        session_id=session_id,
        turn_id=str(web_turn["turn_id"]),
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-web-1",
        completion_id="complete-web-1",
        response={"message": "different retry payload"},
    )
    assert duplicate_completion["created"] is False
    assert [
        item["text"] for item in store.messages(session_id) if item["role"] == "agent"
    ] == ["web answer"]

    second = claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-lark-1",
    )
    assert second["turn"]["turn_id"] == lark_turn["turn_id"]
    assert second["turn"]["origin"] == "lark"
    messages = store.messages(session_id)
    assert [item.get("origin") for item in messages[:3]] == [
        "web",
        "lark",
        "attached_host",
    ]


def test_resume_latest_reuses_attached_session_without_local_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ChatSessionStore(tmp_path)
    session = _bind(store)["session"]
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    monkeypatch.setattr(
        runtime,
        "_start_adapter",
        lambda **_kwargs: pytest.fail("attached Session must not start a local adapter"),
    )

    resumed, reused = runtime.open_session(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        work_dir=tmp_path,
        objective="sample objective",
        mode="resume_latest",
    )

    assert reused is True
    assert resumed["session_id"] == session["session_id"]
    assert runtime.adapters == {}


def test_attached_claimed_turn_interrupt_fails_closed(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    turn, _created = store.create_queued_turn(
        session_id,
        client_turn_id="claimed-interrupt",
        message="keep host ownership",
    )
    claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claimed-interrupt",
    )

    with pytest.raises(CodexChatAgentError) as raised:
        runtime.interrupt_turn(session_id=session_id, turn_id=str(turn["turn_id"]))

    assert raised.value.error_code == "attached_session_interrupt_unavailable"
    current_turn = store.load_turn(session_id, str(turn["turn_id"]))
    current_session = store.load_session(session_id)
    assert current_turn is not None and current_turn["status"] == "running"
    assert current_session is not None and current_session["status"] == "busy"
    assert current_session["active_turn_id"] == turn["turn_id"]
    assert (
        claim_attached_agent_turn(
            store=store,
            session_id=session_id,
            host_surface=HOST_SURFACE,
            host_session_id=HOST_SESSION_ID,
            claim_id="next-claim",
        )["claimed"]
        is False
    )


def test_attached_interrupt_endpoint_preserves_typed_failure(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    turn, _created = store.create_queued_turn(
        session_id,
        client_turn_id="endpoint-interrupt",
        message="keep host ownership",
    )
    turn_id = str(turn["turn_id"])
    claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="endpoint-interrupt",
    )
    responses: list[dict[str, object]] = []

    class Handler:
        server = SimpleNamespace(runtime_controller=runtime)

        def _send_error(self, message: str, **kwargs: object) -> None:
            responses.append({"error": message, **kwargs})

        def _send_json(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("interrupt should fail closed")

    ChatRequestHandler._interrupt_turn(Handler(), session_id, turn_id)  # type: ignore[arg-type]

    assert responses == [
        {
            "error": "The attached host does not expose interrupt control to LoopX Chat.",
            "status": 424,
            "error_code": "attached_session_interrupt_unavailable",
            "gate": {
                "kind": "host_tool_gate",
                "summary": "The active Turn is owned by the attached host.",
                "next_action": "Stop the Turn in the attached host, then retry.",
            },
        }
    ]
    assert store.load_turn(session_id, turn_id)["status"] == "running"  # type: ignore[index]
    session = store.load_session(session_id)
    assert session is not None and session["status"] == "busy"
    assert session["active_turn_id"] == turn_id


def test_attached_completion_uses_canonical_response_and_terminal_events(
    tmp_path: Path,
) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    turn, _created = store.create_queued_turn(
        session_id,
        client_turn_id="web-response-contract",
        message="return structured response",
        origin="web",
    )
    turn_id = str(turn["turn_id"])
    claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="response-contract-claim",
    )

    complete_attached_agent_turn(
        store=store,
        session_id=session_id,
        turn_id=turn_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="response-contract-claim",
        completion_id="response-contract-completion",
        response={
            "message": "structured answer",
            "proposals": [
                "not-a-proposal",
                {
                    "kind": "todo",
                    "text": "Follow the durable contract",
                    "priority": "invalid",
                    "rationale": "Keep the next action bounded.",
                },
            ],
            "gate": {
                "kind": "approval_gate",
                "message": "Approval is required.",
                "required_action": "Review the bounded proposal.",
            },
        },
    )

    completed = store.load_turn(session_id, turn_id)
    assert completed is not None
    response = completed["response"]
    assert response["proposals"] == [
        {
            "kind": "todo",
            "text": "Follow the durable contract",
            "priority": "P1",
            "rationale": "Keep the next action bounded.",
        }
    ]
    events = store.events_after(session_id, turn_id, None)
    assert [event["kind"] for event in events[-3:]] == [
        "proposal.ready",
        "gate.ready",
        "turn.completed",
    ]
    assert events[-1]["payload"]["response"] == response


def test_attached_completion_replays_closeout_after_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    turn, _created = store.create_queued_turn(
        session_id,
        client_turn_id="attached-completion-recovery",
        message="survive completion restart",
        origin="web",
    )
    turn_id = str(turn["turn_id"])
    claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="attached-recovery-claim",
    )
    append_events = store.append_completed_response_events

    def crash_after_events(*args: object, **kwargs: object) -> None:
        append_events(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("crash after attached completion events")

    monkeypatch.setattr(store, "append_completed_response_events", crash_after_events)
    with pytest.raises(RuntimeError, match="crash after attached completion events"):
        complete_attached_agent_turn(
            store=store,
            session_id=session_id,
            turn_id=turn_id,
            host_surface=HOST_SURFACE,
            host_session_id=HOST_SESSION_ID,
            claim_id="attached-recovery-claim",
            completion_id="attached-recovery-completion",
            response={"message": "durable attached response"},
        )

    assert store.load_turn(session_id, turn_id)["status"] == "completing"  # type: ignore[index]
    assert store.load_session(session_id)["status"] == "busy"  # type: ignore[index]

    restarted = ChatSessionStore(tmp_path)

    assert restarted.load_turn(session_id, turn_id)["status"] == "completed"  # type: ignore[index]
    assert restarted.load_session(session_id)["status"] == "ready"  # type: ignore[index]
    assert [
        message["text"]
        for message in restarted.messages(session_id)
        if message.get("role") == "agent"
    ] == ["durable attached response"]
    assert [
        event["kind"]
        for event in restarted.events_after(session_id, turn_id, None)
        if event.get("kind") == "turn.completed"
    ] == ["turn.completed"]


def test_chat_events_reconcile_writes_from_another_store_instance(tmp_path: Path) -> None:
    server_store = ChatSessionStore(tmp_path)
    session_id = str(_bind(server_store)["session"]["session_id"])
    turn, _created = server_store.create_queued_turn(
        session_id,
        client_turn_id="cross-process-events",
        message="observe worker events",
        origin="web",
    )
    turn_id = str(turn["turn_id"])
    assert [
        event["sequence"]
        for event in server_store.events_after(session_id, turn_id, None)
    ] == [1]

    worker_store = ChatSessionStore(tmp_path)
    worker_store.append_event(
        session_id,
        turn_id,
        kind="turn.claimed_by_attached_host",
        payload={},
    )
    worker_store.append_event(
        session_id,
        turn_id,
        kind="turn.completed",
        payload={"response": {"message": "worker answer"}},
    )

    assert [
        event["kind"]
        for event in server_store.events_after(session_id, turn_id, "1")
    ] == ["turn.claimed_by_attached_host", "turn.completed"]
    server_store.append_event(
        session_id,
        turn_id,
        kind="turn.observed",
        payload={},
    )
    persisted = ChatSessionStore(tmp_path).events_after(session_id, turn_id, None)
    assert [event["sequence"] for event in persisted] == [1, 2, 3, 4]

    server_event = server_store.append_event(
        session_id,
        turn_id,
        kind="turn.server_buffered",
        payload={},
        buffered=True,
    )
    worker_event = worker_store.append_event(
        session_id,
        turn_id,
        kind="turn.worker_buffered",
        payload={},
        buffered=True,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(
            executor.map(
                lambda store: store.flush_events(session_id, turn_id),
                (server_store, worker_store),
            )
        )
    persisted = ChatSessionStore(tmp_path).events_after(session_id, turn_id, None)
    assert [event["sequence"] for event in persisted] == [1, 2, 3, 4, 5, 6]
    assert {server_event["sequence"], worker_event["sequence"]} == {5, 6}


def test_attached_close_rejects_active_claim_and_preserves_completion(
    tmp_path: Path,
) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    turn, _created = runtime.submit_turn(
        session_id=session_id,
        client_turn_id="close-active-claim",
        message="finish before close",
        work_dir=tmp_path,
        objective="sample objective",
    )
    turn_id = str(turn["turn_id"])
    claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="close-active-claim",
    )

    responses = _delete_session(runtime, session_id)
    assert responses == [
        {
            "ok": False,
            "error": "complete the active attached Agent turn before closing the session",
            "status": 409,
            "error_code": "attached_session_turn_active",
        }
    ]

    session = store.load_session(session_id)
    active_turn = store.load_turn(session_id, turn_id)
    assert session is not None
    assert session["status"] == "busy"
    assert session["active_turn_id"] == turn_id
    assert active_turn is not None
    assert active_turn["status"] == "running"

    complete_attached_agent_turn(
        store=store,
        session_id=session_id,
        turn_id=turn_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="close-active-claim",
        completion_id="close-active-completion",
        response={"message": "completed before close"},
    )
    assert runtime.wait_for_turn(session_id=session_id, turn_id=turn_id)["status"] == "completed"
    assert runtime.close_session(session_id) is True
    assert store.load_session(session_id)["status"] == "closed"  # type: ignore[index]
    with pytest.raises(KeyError, match="attached Agent session was not found"):
        claim_attached_agent_turn(
            store=store,
            session_id=session_id,
            host_surface=HOST_SURFACE,
            host_session_id=HOST_SESSION_ID,
            claim_id="claim-after-close",
        )

    replay = complete_attached_agent_turn(
        store=store,
        session_id=session_id,
        turn_id=turn_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="close-active-claim",
        completion_id="close-active-completion",
        response={"message": "retry payload"},
    )

    assert replay["created"] is False
    assert [
        message["text"]
        for message in store.messages(session_id)
        if message["role"] == "agent"
    ] == ["completed before close"]
    with pytest.raises(ValueError, match="already completed by another receipt"):
        complete_attached_agent_turn(
            store=store,
            session_id=session_id,
            turn_id=turn_id,
            host_surface=HOST_SURFACE,
            host_session_id=HOST_SESSION_ID,
            claim_id="close-active-claim",
            completion_id="different-receipt",
            response={"message": "conflicting retry"},
        )


def test_attached_close_rejects_pending_queue_and_preserves_claimability(
    tmp_path: Path,
) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    queued, _created = store.create_queued_turn(
        session_id,
        client_turn_id="close-pending-queue",
        message="do not strand this turn",
        origin="web",
    )
    responses = _delete_session(runtime, session_id)

    assert responses == [
        {
            "ok": False,
            "error": "complete queued attached Agent turns before closing the session",
            "status": 409,
            "error_code": "attached_session_queue_pending",
        }
    ]
    session = store.load_session(session_id)
    assert session is not None
    assert session["status"] == "ready"
    claimed = store.claim_next_queued_turn(session_id, host_claim_id="pending-claim")
    assert claimed is not None
    assert claimed["turn_id"] == queued["turn_id"]


def test_attached_close_settles_expired_queue_before_closing(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    queued, _created = store.create_queued_turn(
        session_id,
        client_turn_id="close-expired-queue",
        message="expire before dispatch",
        origin="web",
    )
    turn_id = str(queued["turn_id"])
    store.update_turn(session_id, turn_id, expires_at="2000-01-01T00:00:00Z")

    responses = _delete_session(runtime, session_id)

    assert responses == [
        {"ok": True, "session_id": session_id, "closed": True, "status": 200}
    ]
    session = store.load_session(session_id)
    assert session is not None
    assert session["status"] == "closed"
    expired = store.load_turn(session_id, turn_id)
    assert expired is not None
    assert expired["status"] == "timed_out"
    assert expired["error_code"] == "session_queue_expired"
    events = store.events_after(session_id, turn_id, None)
    assert [event["kind"] for event in events] == ["turn.queued", "turn.failed"]
    assert events[-1]["payload"] == {"error_code": "session_queue_expired"}


def test_managed_close_reports_active_turn_instead_of_stranding_it(
    tmp_path: Path,
) -> None:
    store = ChatSessionStore(tmp_path)
    session = store.create_session(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        adapter_kind="managed-test",
        upstream_thread_id="managed-thread",
    )
    turn, _created = store.create_turn(
        str(session["session_id"]),
        client_turn_id="managed-active-close",
        message="active managed turn",
    )
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")

    responses = _delete_session(runtime, str(session["session_id"]))

    assert responses == [
        {
            "ok": False,
            "error": "interrupt the active Agent turn before closing the session",
            "status": 409,
            "error_code": "managed_session_turn_active",
        }
    ]
    current = store.load_session(str(session["session_id"]))
    assert current is not None
    assert current["status"] == "busy"
    assert current["active_turn_id"] == turn["turn_id"]


def test_managed_close_reports_pending_queue_instead_of_stranding_it(
    tmp_path: Path,
) -> None:
    store = ChatSessionStore(tmp_path)
    session = store.create_session(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        adapter_kind="managed-test",
        upstream_thread_id="managed-thread",
    )
    queued, _created = store.create_queued_turn(
        str(session["session_id"]),
        client_turn_id="managed-queued-close",
        message="queued managed turn",
    )
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")

    responses = _delete_session(runtime, str(session["session_id"]))

    assert responses == [
        {
            "ok": False,
            "error": "complete queued Agent turns before closing the session",
            "status": 409,
            "error_code": "managed_session_queue_pending",
        }
    ]
    current = store.load_session(str(session["session_id"]))
    assert current is not None
    assert current["status"] == "ready"
    assert store.load_turn(
        str(session["session_id"]), str(queued["turn_id"])
    )["status"] == "queued"  # type: ignore[index]


def test_attached_live_steering_fails_closed_with_durable_receipt(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")

    with pytest.raises(RuntimeError, match="attached_session_live_steering_unavailable"):
        runtime.steer_active_turn(
            session_id=session_id,
            client_ingress_id="lark-steer-1",
            message="steer now",
        )
    receipt = store.create_ingress_receipt(
        session_id,
        client_ingress_id="lark-steer-1",
        mode="live_steering",
        message="steer now",
    )[0]
    assert receipt["status"] == "failed"
    assert receipt["error_code"] == "attached_session_live_steering_unavailable"


def test_lark_session_queue_waits_for_attached_host_reply_readback(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_id = str(_bind(store)["session"]["session_id"])
    runtime = ChatRuntimeController(store=store, codex_bin="missing-codex")
    result: dict[str, str] = {}

    def answer() -> None:
        result["reply"] = answer_lark_goal_topic(
            route={
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "session_id": session_id,
                "ingress_mode": "session_queue",
                "message_id": "om_synthetic_message",
                "topic_root_message_id": "om_synthetic_root",
            },
            text="question from lark",
            work_dir=tmp_path,
            objective="sample objective",
            runtime_controller=runtime,
        )

    waiter = threading.Thread(target=answer)
    waiter.start()
    deadline = time.monotonic() + 2
    while not store.queued_turns(session_id) and time.monotonic() < deadline:
        time.sleep(0.01)
    claimed = claim_attached_agent_turn(
        store=store,
        session_id=session_id,
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-lark-reply",
    )
    assert claimed["turn"]["origin"] == "lark"
    complete_attached_agent_turn(
        store=store,
        session_id=session_id,
        turn_id=claimed["turn"]["turn_id"],
        host_surface=HOST_SURFACE,
        host_session_id=HOST_SESSION_ID,
        claim_id="claim-lark-reply",
        completion_id="complete-lark-reply",
        response={"message": "reply from attached host"},
    )
    waiter.join(timeout=2)
    assert not waiter.is_alive()
    assert result["reply"] == "reply from attached host"
