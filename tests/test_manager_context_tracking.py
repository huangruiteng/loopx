"""Handoff states, durable receipts and audience separation through real stores."""

import json
from argparse import Namespace

import pytest

import test_manager_context_handoff as handoff_tests
from loopx.capabilities.manager_context import (
    _hash,
    _root,
    _read,
    _write,
    deliver,
    acknowledge,
    pending,
    turn_start_hook,
    register_ingress,
    POLICY_SCHEMA,
)
from loopx.capabilities.manager_context.tracking import query, record_read, link
from loopx.capabilities.manager_context.inspection import ManagerInspection, TOOL_NAME
from loopx.cli_commands.manager_inbox import handle_manager_inbox


@pytest.fixture
def fixture(tmp_path):
    return handoff_tests.fixture.__wrapped__(tmp_path)


def test_delivery_read_decision_are_separate_and_restart_safe(fixture, capsys):
    root, registry, session, turn, target = fixture
    rid = deliver(root, registry, session=session, turn=turn, request=target)[
        "request_id"
    ]

    def status():
        return query(root, registry, goal_ids=["research"], owner_scope=True)["rows"][0]

    first = status()
    assert first["delivery"]["at"] and first["read"]["status"] == "not_recorded"
    turn_start_hook(root, registry, "research", "worker").producer()
    assert status()["read"]["status"] == "not_recorded"
    args = Namespace(manager_inbox_action="read", goal_id="research", agent_id="worker")
    assert handle_manager_inbox(args, registry, root) == 0
    assert json.loads(capsys.readouterr().out)["items"][0]["message"] == turn["message"]
    read_at = status()["read"]["at"]
    record_read(root, pending(root, "research", "worker")["items"])
    assert status()["read"]["at"] == read_at
    acknowledge(root, "research", "worker", rid, "adopt", "Investigate independently")
    at = status()["decision"]["at"]
    acknowledge(root, "research", "worker", rid, "adopt", "Investigate independently")
    assert status()["decision"]["at"] == at
    assert status()["decision"]["status"] == "adopt"
    assert status()["linked_todos"] == []
    assert deliver(root, registry, session=session, turn=turn, request=target)[
        "replayed"
    ]
    assert status()["delivery"]["at"] == first["delivery"]["at"]


def test_legacy_decision_is_not_a_fabricated_read(fixture):
    root, registry, session, turn, target = fixture
    rid = deliver(root, registry, session=session, turn=turn, request=target)[
        "request_id"
    ]
    path = _root(root) / "entries" / _hash(target) / (rid + ".json")
    old = _read(path)
    old.pop("delivered_at")
    old.pop("source_channel")
    _write(path, old)
    _write(
        _root(root) / "decisions" / (rid + ".json"),
        dict(request_id=rid, **target, decision="adopt", reason="Legacy"),
    )
    assert deliver(root, registry, session=session, turn=turn, request=target)[
        "replayed"
    ]
    row = query(root, registry, goal_ids=["research"], owner_scope=True)["rows"][0]
    assert row["delivery"]["at"] is None and row["decision"]["at"] is None
    assert row["read"]["status"] == "decision_exists_read_receipt_missing"
    assert row["read"]["at"] is None


def test_external_query_is_exact_audience_not_just_goal(fixture):
    root, registry, session, turn, target = fixture
    web = deliver(root, registry, session=session, turn=turn, request=target)[
        "request_id"
    ]
    ids = {}
    for channel in ["manager.external.one", "manager.external.two"]:
        external = dict(session, channel_id=channel)
        incoming = dict(turn, origin="lark", client_turn_id=channel)
        _write(
            _root(root) / "policy.json",
            {
                "schema_version": POLICY_SCHEMA,
                "sources": {channel: {"sender_ids": ["owner"], "targets": [target]}},
            },
        )
        register_ingress(
            root,
            session_id=external["session_id"],
            client_turn_id=channel,
            channel=channel,
            sender_id="owner",
            message=turn["message"],
            source_id="lark:" + channel,
        )
        rid = deliver(root, registry, session=external, turn=incoming, request=target)[
            "request_id"
        ]
        acknowledge(
            root, "research", "worker", rid, "adopt", "Private receiver rationale"
        )
        ids[channel] = rid

    def tool(scope=lambda: True):
        return ManagerInspection(
            context={"goals": [{"goal_id": "research"}]},
            registry_path=registry,
            runtime_root=root,
            owner_scope=False,
            scope_valid=scope,
            record=lambda _: None,
            channel_id="manager.external.one",
        )

    rows = tool().read(TOOL_NAME, {"view": "handoffs"})["rows"]
    assert [r["request_id"] for r in rows] == [ids["manager.external.one"]]
    assert "Private receiver rationale" not in json.dumps(rows)
    assert turn["message"] not in json.dumps(rows)
    assert tool().read(TOOL_NAME, {"view": "handoffs", "request_id": web})["rows"] == []
    revoked = iter([True, False])
    assert (
        tool(lambda: next(revoked)).read(TOOL_NAME, {"view": "handoffs"})["error"]
        == "authorization_changed"
    )
    # Legacy same-source provenance still resolves; changing audience is not inferred.
    path = (
        _root(root)
        / "entries"
        / _hash(target)
        / (ids["manager.external.one"] + ".json")
    )
    old = _read(path)
    old.pop("source_channel")
    _write(path, old)
    assert tool().read(TOOL_NAME, {"view": "handoffs"})["included"] == 1


def test_links_use_core_state_and_do_not_copy_progress(fixture, monkeypatch):
    import loopx.capabilities.manager_context.tracking as tracking

    root, registry, session, turn, target = fixture
    rid = deliver(root, registry, session=session, turn=turn, request=target)[
        "request_id"
    ]
    tid = "todo_123456789abc"
    core = {
        "ok": True,
        "todos": [
            {
                "todo_id": tid,
                "claimed_by": "worker",
                "text": "Evaluate hypothesis",
                "status": "open",
            }
        ],
    }
    monkeypatch.setattr(tracking, "list_goal_todos", lambda **_: core)
    ref = "sha256:" + "a" * 64
    link(root, registry, "research", "worker", rid, [tid], [ref])
    path = _root(root) / "links" / (rid + ".json")
    original = path.read_bytes()
    link(root, registry, "research", "worker", rid, [tid], [ref])
    assert path.read_bytes() == original
    core["todos"][0]["status"] = "done"
    row = query(root, registry, goal_ids=["research"], owner_scope=True)["rows"][0]
    assert row["linked_todos"][0]["status"] == "done"
    assert row["decision"]["status"] == "not_recorded"
    assert row["evidence_refs"] == [ref]
    with pytest.raises(ValueError):
        link(root, registry, "research", "worker", rid, ["todo_ffffffffffff"], [])
    with pytest.raises(ValueError):
        link(root, registry, "research", "worker", rid, [], ["/private/raw.txt"])
    assert "Evaluate hypothesis" not in path.read_text()


def test_pagination_and_conflicts_do_not_erase_gaps(fixture):
    root, registry, session, turn, target = fixture
    for i in range(14):
        deliver(
            root,
            registry,
            session=session,
            turn=dict(turn, client_turn_id=str(i)),
            request=target,
        )
    first = query(root, registry, goal_ids=["research"], owner_scope=True, limit=12)
    second = query(
        root, registry, goal_ids=["research"], owner_scope=True, offset=12, limit=12
    )
    assert first["matched"] == 14 and len(second["rows"]) == 2
    rid = first["rows"][0]["request_id"]
    _write(
        _root(root) / "decisions" / (rid + ".json"),
        dict(request_id=rid, goal_id="other", agent_id="peer", decision="adopt"),
    )
    row = query(
        root, registry, goal_ids=["research"], owner_scope=True, request_id=rid
    )["rows"][0]
    assert row["decision"]["status"] == "not_recorded"
    assert row["warnings"] == ["decisions_unreadable_or_conflicting"]
    links_path = _root(root) / "links" / (rid + ".json")
    _write(
        links_path,
        dict(request_id=rid, **target, todo_ids=[], evidence_ids=["/private/secret"]),
    )
    row = query(
        root, registry, goal_ids=["research"], owner_scope=True, request_id=rid
    )["rows"][0]
    assert row["evidence_refs"] == []
    assert "links_unreadable_or_conflicting" in row["warnings"]
    with pytest.raises(ValueError, match="links_unreadable_or_conflicting"):
        link(root, registry, "research", "worker", rid, [], ["sha256:" + "b" * 64])
    assert (
        query(root, registry, goal_ids=["research"], owner_scope=True, agent_id="peer")[
            "rows"
        ]
        == []
    )
