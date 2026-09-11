"""One delegation automatically returns a conclusion without a second question."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from loopx.capabilities.manager_context import (
    _root,
    _write,
    acknowledge,
    deliver,
    pending,
    register_ingress,
    POLICY_SCHEMA,
)
from loopx.capabilities.manager_context.roundtrip import (
    ReturnService,
    drain,
    report,
    reply_status,
)
from loopx.chat_store import ChatSessionStore


@pytest.fixture
def flow(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": "research",
                        "repo": str(tmp_path),
                        "coordination": {"registered_agents": ["worker"]},
                    }
                ]
            }
        )
    )
    store = ChatSessionStore(tmp_path)

    def create(external=False):
        session = store.create_session(
            goal_id="loopx-manager",
            agent_id="codex",
            adapter_kind="codex_app_server",
            upstream_thread_id="test",
            channel_id="manager.external.test" if external else "manager",
        )
        turn, _ = store.create_turn(
            session["session_id"],
            client_turn_id="question",
            message="Investigate this new constraint",
            origin="lark" if external else "web",
        )
        target = {"goal_id": "research", "agent_id": "worker"}
        if external:
            _write(
                _root(tmp_path) / "policy.json",
                {
                    "schema_version": POLICY_SCHEMA,
                    "sources": {
                        session["channel_id"]: {
                            "sender_ids": ["owner"],
                            "targets": [target],
                        }
                    },
                },
            )
            register_ingress(
                tmp_path,
                session_id=session["session_id"],
                client_turn_id="question",
                channel=session["channel_id"],
                sender_id="owner",
                message=turn["message"],
                source_id="lark:om_fixture_source",
            )
        receipt = deliver(
            tmp_path, registry, session=session, turn=turn, request=target
        )
        store.update_turn(
            session["session_id"],
            turn["turn_id"],
            status="completing",
            response={
                "message": "Delivered; a conclusion will return here.",
                "context_handoff_receipt": receipt,
            },
        )
        store.finalize_managed_turn_completion(session["session_id"], turn["turn_id"])
        return session, turn, receipt

    return tmp_path, registry, store, create


def test_single_request_returns_to_original_transcript_without_second_model_turn(flow):
    root, registry, store, create = flow
    session, turn, receipt = create()
    rid = receipt["request_id"]
    acknowledge(root, "research", "worker", rid, "adopt", "Private deliberation")
    assert pending(root, "research", "worker")["items"]
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "Checked the constraint, updated the existing plan, and recorded the validation result.",
    )
    assert not pending(root, "research", "worker")["items"]
    before_turns = list(
        (store.root / "sessions" / session["session_id"] / "turns").glob("*.json")
    )

    def unexpected(*_):
        raise AssertionError("owner conversation must not send external messages")

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: drain(root, registry, store, unexpected), range(2)))
    # A new store models restart: no in-memory dedupe or new user prompt needed.
    drain(root, registry, ChatSessionStore(root), unexpected)
    rows = store.messages(session["session_id"])
    returned = [x for x in rows if x.get("origin") == "manager_followup"]
    assert len(returned) == 1 and returned[0]["turn_id"] == turn["turn_id"]
    assert "updated the existing plan" in returned[0]["text"]
    assert "Private deliberation" not in returned[0]["text"]
    assert len(
        list((store.root / "sessions" / session["session_id"] / "turns").glob("*.json"))
    ) == len(before_turns)
    assert reply_status(root, receipt)[0]["status"] == "delivered"


def test_conclusion_coalesces_unsent_intermediate_decision_and_is_immutable(flow):
    root, registry, store, create = flow
    session, _, r = create()
    rid = r["request_id"]
    with pytest.raises(ValueError, match="receiver decision"):
        report(root, "research", "worker", rid, "conclusion", "No change required.")
    acknowledge(root, "research", "worker", rid, "no_change", "Evidence unchanged")
    report(
        root,
        "research",
        "worker",
        rid,
        "decision",
        "Reviewing the original constraint.",
    )
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "The existing plan already covers this constraint. No priority changed.",
    )
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "The existing plan already covers this constraint. No priority changed.",
    )
    with pytest.raises(ValueError, match="conflicting"):
        report(root, "research", "worker", rid, "conclusion", "Different text")
    drain(root, registry, store, lambda *_: None)
    assert (
        len(
            [
                x
                for x in store.messages(session["session_id"])
                if x.get("origin") == "manager_followup"
            ]
        )
        == 1
    )
    assert {x["status"] for x in reply_status(root, r)} == {"superseded", "delivered"}


def test_external_failure_retries_same_reply_after_restart_without_duplicate_transcript(
    flow,
):
    root, registry, store, create = flow
    session, turn, r = create(True)
    rid = r["request_id"]
    acknowledge(root, "research", "worker", rid, "adopt", "Private rationale")
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "Validation completed; the revised plan preserves the existing priorities.",
    )
    calls = []

    def offline(route, s, t, text):
        calls.append((route, s, t, text))
        return {"ok": False, "external_write_performed": False}

    now = datetime.now(timezone.utc)
    drain(root, registry, store, offline, now=now)
    assert reply_status(root, r)[0]["status"] == "retry_pending"
    drain(root, registry, store, offline, now=now)
    assert len(calls) == 1

    def online(*args):
        assert args == calls[0]
        return {"ok": True, "reply_verified": True}

    drain(
        root, registry, ChatSessionStore(root), online, now=now + timedelta(minutes=10)
    )
    assert reply_status(root, r)[0]["status"] == "delivered"
    assert (
        len(
            [
                x
                for x in store.messages(session["session_id"])
                if x.get("origin") == "manager_followup"
            ]
        )
        == 1
    )


def test_revocation_and_closed_conversation_never_retarget(flow):
    root, registry, store, create = flow
    session, _, r = create(True)
    rid = r["request_id"]
    acknowledge(root, "research", "worker", rid, "reject", "Unsupported")
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "The request was assessed and declined because the required evidence is absent.",
    )
    _write(
        _root(root) / "policy.json", {"schema_version": POLICY_SCHEMA, "sources": {}}
    )

    def unexpected(*_):
        raise AssertionError("revoked request must not be sent")

    drain(root, registry, store, unexpected)
    assert not [
        x
        for x in store.messages(session["session_id"])
        if x.get("origin") == "manager_followup"
    ]
    store.update_session(session["session_id"], status="closed")
    drain(
        root,
        registry,
        store,
        unexpected,
        now=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    assert reply_status(root, r)[0]["status"] == "retry_pending"


def test_legacy_route_is_recovered_only_from_exact_persisted_chat_receipt(flow):
    root, registry, store, create = flow
    session, _, r = create()
    rid = r["request_id"]
    (_root(root) / "roundtrips" / (rid + ".json")).unlink()
    acknowledge(root, "research", "worker", rid, "defer", "Dependent data unavailable")
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "Deferred until the named dependency is available; no work result is claimed.",
    )
    drain(root, registry, store, lambda *_: None)
    assert (
        len(
            [
                x
                for x in store.messages(session["session_id"])
                if x.get("origin") == "manager_followup"
            ]
        )
        == 1
    )


def test_ambiguous_provider_write_is_not_blindly_resent(flow):
    root, registry, store, create = flow
    _, _, r = create(True)
    rid = r["request_id"]
    acknowledge(root, "research", "worker", rid, "adopt", "Checked")
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "Processed with a recorded validation result.",
    )
    calls = []

    def ambiguous(*args):
        calls.append(args)
        return {"ok": False, "external_write_performed": True, "reply_verified": False}

    drain(root, registry, store, ambiguous)
    drain(
        root,
        registry,
        store,
        ambiguous,
        now=datetime.now(timezone.utc) + timedelta(days=2),
    )
    assert len(calls) == 1
    assert reply_status(root, r)[0]["status"] == "verification_required"


def test_background_service_delivers_without_another_agent_or_query(flow):
    root, registry, store, create = flow
    _, _, receipt = create(True)
    rid = receipt["request_id"]
    acknowledge(root, "research", "worker", rid, "no_change", "Reviewed")
    report(
        root,
        "research",
        "worker",
        rid,
        "conclusion",
        "No change is needed after checking the existing plan.",
    )
    sent = threading.Event()

    def transport(*_):
        sent.set()
        return {"reply_verified": True, "idempotency_key": "sha256:provider-proof"}

    service = ReturnService(root, registry, store, transport)
    service.start()
    try:
        assert sent.wait(timeout=5)
    finally:
        service.close()
    state = json.loads(
        (_root(root) / "replies" / rid / "conclusion.delivery.json").read_text()
    )
    assert state["status"] == "delivered"
    assert state["provider_receipt"] == "sha256:provider-proof"
    assert not service.thread.is_alive()
