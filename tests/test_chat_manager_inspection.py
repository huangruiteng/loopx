"""Manager reads retain Core truth, pagination and audience boundaries."""

import io
import json
import queue
from datetime import datetime, timezone

import pytest

from loopx.capabilities.manager_context.inspection import (
    ManagerInspection,
    TOOL_NAME,
    manager_index,
)
from loopx.chat_agent import CodexChatAgentSession, CodexChatAgentError
from loopx.chat_manager_history import read_manager_delivery_history
import loopx.chat_manager_details as details


def inspector(tmp_path, scope=lambda: True):
    records = []
    tool = ManagerInspection(
        context={"snapshot_id": "fixture", "goals": [{"goal_id": "alpha"}]},
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path,
        owner_scope=False,
        scope_valid=scope,
        record=records.append,
    )
    return tool, records


def test_todo_pages_reach_beyond_previous_cap_and_keep_revision(monkeypatch, tmp_path):
    monkeypatch.setattr(
        details,
        "list_goal_todos",
        lambda **_: {
            "ok": True,
            "source": "file_authority",
            "todos": [
                {"todo_id": f"todo_{i}", "text": f"Check result {i}", "status": "open"}
                for i in range(55)
            ],
        },
    )
    tool, records = inspector(tmp_path)
    offset, ids, revisions = 0, [], set()
    while offset is not None:
        page = tool.read(
            TOOL_NAME, {"view": "todos", "goal_id": "alpha", "offset": offset}
        )
        ids.extend(r["todo_id"] for r in page["rows"])
        revisions.add(page["source"]["source_revision"])
        offset = page["next_offset"]
    assert len(ids) == len(set(ids)) == 55
    assert len(revisions) == 1 and len(records) == 7
    assert records[-1]["matched"] == 55


@pytest.mark.parametrize(
    "args",
    [
        {"view": "todos", "goal_id": "outside"},
        {"view": "shell"},
        {"view": "portfolio", "path": "/unknown"},
        {"view": "portfolio", "offset": True},
        {"view": "portfolio", "limit": 13},
    ],
)
def test_invalid_or_out_of_scope_reads_do_not_touch_core(monkeypatch, tmp_path, args):
    def forbidden(**_):
        pytest.fail("Core must not be read")

    monkeypatch.setattr(details, "list_goal_todos", forbidden)
    tool, records = inspector(tmp_path)
    assert tool.read(TOOL_NAME, args)["ok"] is False
    assert not records


def test_revocation_during_read_suppresses_result(monkeypatch, tmp_path):
    grants = iter([True, False])
    monkeypatch.setattr(
        details, "list_goal_todos", lambda **_: {"ok": True, "todos": []}
    )
    tool, records = inspector(tmp_path, lambda: next(grants))
    assert tool.read(TOOL_NAME, {"view": "todos", "goal_id": "alpha"}) == {
        "ok": False,
        "error": "authorization_changed",
    }
    assert not records


def test_unavailable_is_unknown_and_large_portfolio_is_disclosed(tmp_path):
    tool, records = inspector(tmp_path)
    result = tool.read(TOOL_NAME, {"view": "deliveries", "goal_id": "alpha"})
    assert result["unknown"] and result["matched"] is None
    assert result["source"]["status"] == "unavailable"
    tool.context["goals"][0]["current_todos"] = {"body": "x" * 40000}
    index = manager_index(tool.context)
    assert len(json.dumps(index)) < 1000
    result = tool.read(TOOL_NAME, {"view": "portfolio"})
    assert result["oversized_rows"] == [0]
    assert len(json.dumps(result)) < 2000


def test_delivery_pages_cross_day_without_duplication(tmp_path):
    path = tmp_path / "goals" / "alpha" / "runs" / "index.jsonl"
    path.parent.mkdir(parents=True)
    rows = [
        {
            "generated_at": at,
            "delivery_outcome": "outcome_progress",
            "todo_id": f"todo_{i}",
        }
        for i, at in enumerate(
            [
                "2026-01-01T12:00:00+00:00",
                "2026-01-02T01:00:00+00:00",
                "2026-01-02T02:00:00+00:00",
            ]
        )
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows))
    pages = [
        read_manager_delivery_history(
            tmp_path,
            "alpha",
            limit=1,
            offset=i,
            now=datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    assert {p["deliveries"][0]["todo_id"] for p in pages} == {
        "todo_0",
        "todo_1",
        "todo_2",
    }


def test_dynamic_requests_are_not_mistaken_for_client_responses(tmp_path):
    class Process:
        stdin = io.StringIO()

    messages = queue.Queue()
    session = CodexChatAgentSession(
        process=Process(),
        messages=messages,
        thread_id="thread",
        work_dir=tmp_path,
        current_turn_id="turn",
    )
    reads = []
    session.read_tool_handler = lambda tool, args: (
        reads.append((tool, args)) or {"ok": True}
    )
    # JSON-RPC request IDs belong to separate peers and may collide.
    messages.put(
        {
            "id": 1,
            "method": "item/tool/call",
            "params": {
                "threadId": "thread",
                "turnId": "turn",
                "tool": TOOL_NAME,
                "arguments": {"view": "portfolio"},
            },
        }
    )
    messages.put({"id": 1, "result": {"receipt": "actual-response"}})
    assert session._request("fixture", {}, request_id=1) == {
        "receipt": "actual-response"
    }
    assert reads == [(TOOL_NAME, {"view": "portfolio"})]
    assert json.loads(Process.stdin.getvalue().splitlines()[-1])["result"]["success"]
    session._check_server_gate(
        {
            "id": 2,
            "method": "item/tool/call",
            "params": {
                "threadId": "other",
                "turnId": "turn",
                "tool": TOOL_NAME,
                "arguments": {},
            },
        }
    )
    assert len(reads) == 1
    assert not json.loads(Process.stdin.getvalue().splitlines()[-1])["result"][
        "success"
    ]
    with pytest.raises(CodexChatAgentError):
        session._check_server_gate(
            {"id": 3, "method": "item/commandExecution/requestApproval"}
        )


def test_manager_runtime_installs_tool_and_records_real_subprocess_read(
    monkeypatch, tmp_path
):
    from loopx.chat_runtime import ChatRuntimeController
    from loopx.chat_store import ChatSessionStore
    import loopx.chat_manager_context as context

    fake = tmp_path / "fake-codex"
    fake.write_text("""#!/usr/bin/env python3
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    m = r.get('method')
    if m == 'initialize':
        result = {}
    elif m == 'thread/start':
        assert r['params']['dynamicTools'][0]['name'] == 'loopx_manager_read'
        result = {'thread': {'id': 'fixture-thread'}}
    elif m == 'turn/start':
        text = json.dumps(r['params']['input'])
        assert 'manager_evidence_index_v1' in text
        print(json.dumps({'id':r['id'],'result':{'turn':{'id':'fixture-turn'}}}), flush=True)
        print(json.dumps({'id':900,'method':'item/tool/call','params':{
            'threadId':'fixture-thread','turnId':'fixture-turn','tool':'loopx_manager_read',
            'arguments':{'view':'todos','goal_id':'alpha'}}}), flush=True)
        continue
    elif r.get('id') == 900:
        assert r['result']['success']
        evidence = json.loads(r['result']['contentItems'][0]['text'])
        assert evidence['rows'][0]['title'] == 'Check the sample result'
        print(json.dumps({'method':'item/agentMessage/delta','params':{
            'threadId':'fixture-thread','turnId':'fixture-turn','delta':'Read the sample task.'}}), flush=True)
        print(json.dumps({'method':'turn/completed','params':{
            'threadId':'fixture-thread','turn':{'id':'fixture-turn','status':'completed'}}}), flush=True)
        continue
    else:
        continue
    print(json.dumps({'id':r['id'],'result':result}), flush=True)
""")
    fake.chmod(0o755)
    collected = []

    def collect(*args, **kwargs):
        collected.append(kwargs)
        return {"goals": [{"goal_id": "alpha"}], "snapshot_id": "fixture"}

    monkeypatch.setattr(context, "collect_manager_turn_context", collect)
    monkeypatch.setattr(
        details,
        "list_goal_todos",
        lambda **_: {
            "ok": True,
            "todos": [
                {
                    "todo_id": "todo_sample",
                    "text": "Check the sample result",
                    "status": "open",
                },
            ],
        },
    )
    store = ChatSessionStore(tmp_path / "runtime" / "chat")
    runtime = ChatRuntimeController(
        store=store, codex_bin=str(fake), registry_path=tmp_path / "registry.json"
    )
    monkeypatch.setattr(
        runtime,
        "capabilities",
        lambda: [
            {
                "agent_id": "codex",
                "available": True,
                "adapter_kind": "codex_app_server",
            },
        ],
    )
    try:
        session, _ = runtime.open_session(
            goal_id="loopx-manager",
            agent_id="codex",
            work_dir=tmp_path,
            objective="manager",
            mode="new",
            channel_id="manager",
        )
        turn, _ = runtime.submit_turn(
            session_id=session["session_id"],
            client_turn_id="fixture",
            message="Inspect sample task",
            work_dir=tmp_path,
            objective="manager",
        )
        done = runtime.wait_for_turn(
            session_id=session["session_id"], turn_id=turn["turn_id"], timeout_sec=10
        )
        assert done["status"] == "completed", done
        assert collected == [{"include_details": False}]
        events = store.events_after(session["session_id"], turn["turn_id"], None)
        reads = [e for e in events if e["kind"] == "manager.evidence_read"]
        assert (
            len(reads) == 1
            and reads[0]["payload"]["rows"][0]["todo_id"] == "todo_sample"
        )
    finally:
        runtime.close()


def test_stopped_goals_are_opt_in_but_stale_active_remains_visible(tmp_path):
    tool, _ = inspector(tmp_path)
    tool.context['goals'] = [
        {'goal_id': 'alpha', 'activation_state': 'active', 'quality': 'stale'},
        {'goal_id': 'old', 'activation_state': 'stopped', 'quality': 'omitted'},
        {'goal_id': 'unknown', 'activation_state': 'unknown', 'quality': 'unreadable'},
    ]
    index = manager_index(tool.context)
    assert [r['goal_id'] for r in index['goals']] == ['alpha', 'unknown']
    assert index['stopped_goals_excluded'] == 1
    current = tool.read(TOOL_NAME, {'view': 'portfolio'})
    assert current['matched'] == 2
    history = tool.read(TOOL_NAME, {'view': 'portfolio', 'include_stopped': True})
    assert history['matched'] == 3
    explicit = tool.read(TOOL_NAME, {'view': 'portfolio', 'goal_id': 'old'})
    assert explicit['rows'][0]['activation_state'] == 'stopped'
