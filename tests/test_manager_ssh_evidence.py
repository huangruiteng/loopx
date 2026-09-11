"""Remote reports select real sources and preserve scoped Core evidence."""

import json
import subprocess
import shlex
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from loopx.capabilities.manager_context.ssh_evidence import configure, grants
from loopx.capabilities.manager_context.inspection import ManagerInspection, TOOL_NAME
from loopx.capabilities.manager_context.evidence_export import export_page
from loopx.chat_manager_context import manager_authorization_scope_id
from loopx.chat_manager_history import read_manager_delivery_history


@pytest.fixture
def remote(tmp_path):
    config = tmp_path / "ssh_config"
    config.write_text(
        "Host research-host\n  HostName example.invalid\nHost unrelated\n  HostName other.invalid\n"
    )
    channel = "manager.external." + "a" * 24
    configure(
        tmp_path,
        channel=channel,
        host="research-host",
        goal_ids=["remote-goal"],
        execute=True,
        config_path=config,
    )
    calls, records = [], []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "schema_version": "manager_evidence_page_v1",
                    "ok": True,
                    "rows": [{"goal_id": "remote-goal", "title": "Actual remote task"}],
                    "source": {"coverage": {"discovered": 1}},
                    "next_offset": None,
                }
            ),
        )

    inspection = ManagerInspection(
        context={"goals": [{"goal_id": "local-goal", "host_id": None}]},
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path,
        owner_scope=False,
        channel_id=channel,
        scope_valid=lambda: True,
        record=records.append,
        remote_runner=run,
        ssh_config_path=config,
    )
    return inspection, calls, records, channel, config


def test_remote_source_is_discovered_and_read_without_local_host_metadata(remote):
    tool, calls, records, _, _ = remote
    sources = tool.read(TOOL_NAME, {"view": "sources"})
    assert [r["source_id"] for r in sources["rows"]] == ["local", "ssh:research-host"]
    assert not calls
    result = tool.read(
        TOOL_NAME,
        {"view": "todos", "source_id": "ssh:research-host", "goal_id": "remote-goal"},
    )
    assert result["ok"] and result["rows"][0]["title"] == "Actual remote task"
    assert result["source_host"] == result["rows"][0]["source_host"] == "research-host"
    argv, opts = calls[0]
    assert (
        argv[-2] == "research-host"
        and '"$HOME/.codex/loopx/registry.global.json"' in argv[-1]
    )
    assert "--manager-view todos" in argv[-1] and "--goal-id remote-goal" in argv[-1]
    assert "BatchMode=yes" in argv and opts["timeout"] == 45
    assert records[-1] == result


@pytest.mark.parametrize(
    "query",
    [
        {"view": "todos", "source_id": "ssh:research-host", "goal_id": "local-goal"},
        {"view": "portfolio", "source_id": "ssh:unrelated"},
        {"view": "portfolio", "source_id": "ssh:unconfigured"},
        {"view": "handoffs", "source_id": "ssh:research-host"},
        {
            "view": "deliveries",
            "source_id": "ssh:research-host",
            "goal_id": "remote-goal",
            "days": 999,
        },
    ],
)
def test_invalid_or_unauthorized_queries_never_connect(remote, query):
    tool, calls, *_ = remote
    assert not tool.read(TOOL_NAME, query)["ok"]
    assert not calls


def test_remote_grant_revocation_discards_inflight_result_and_changes_context_identity(
    remote,
):
    tool, calls, _, channel, config = remote
    old = manager_authorization_scope_id(
        ["local-goal"], runtime_root=tool.runtime_root, channel_id=channel
    )
    original = tool.remote_runner

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        configure(
            tool.runtime_root,
            channel=channel,
            host="research-host",
            goal_ids=[],
            execute=True,
            config_path=config,
        )
        return result

    tool.remote_runner = revoke
    result = tool.read(
        TOOL_NAME, {"view": "portfolio", "source_id": "ssh:research-host"}
    )
    assert result == {"ok": False, "error": "authorization_changed"}
    assert not grants(tool.runtime_root, channel)
    assert old != manager_authorization_scope_id(
        ["local-goal"], runtime_root=tool.runtime_root, channel_id=channel
    )


def test_old_or_offline_remote_is_unknown_not_empty_healthy(remote):
    tool, *_ = remote

    def unavailable(*_, **__):
        raise subprocess.TimeoutExpired("ssh", 45)

    tool.remote_runner = unavailable
    result = tool.read(
        TOOL_NAME, {"view": "portfolio", "source_id": "ssh:research-host"}
    )
    assert not result["ok"] and result["coverage"] == {
        "discovered": None,
        "complete": False,
    }


def test_export_uses_canonical_todos_and_never_returns_owner_private_continuation(
    tmp_path, monkeypatch
):
    import loopx.chat_manager_details as details

    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"goals": [{"id": "remote-goal", "repo": str(tmp_path)}]})
    )
    monkeypatch.setattr(
        details,
        "list_goal_todos",
        lambda **_: {
            "ok": True,
            "source": "canonical",
            "todos": [
                {
                    "todo_id": "t1",
                    "text": "Validate delivery",
                    "status": "open",
                    "note": "Private deliberation",
                }
            ],
        },
    )
    args = SimpleNamespace(
        portfolio_goal_ids=["remote-goal"],
        manager_view="todos",
        limit=8,
        offset=0,
        days=1,
    )
    packet = export_page(registry, str(tmp_path), args)
    assert packet["schema_version"] == "manager_evidence_page_v1"
    assert packet["rows"][0]["goal_id"] == "remote-goal"
    assert packet["rows"][0]["title"] == "Validate delivery"
    assert "Private deliberation" not in json.dumps(packet)


def test_delivery_lookback_can_explain_stale_goals_without_redating_outcomes(tmp_path):
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=4)).isoformat()
    index = tmp_path / "goals" / "remote-goal" / "runs" / "index.jsonl"
    index.parent.mkdir(parents=True)
    index.write_text(
        json.dumps(
            {
                "generated_at": old,
                "goal_id": "remote-goal",
                "agent_id": "worker",
                "todo_id": "t1",
                "delivery_outcome": "outcome_progress",
                "classification": "validated_result",
            }
        )
        + "\n"
    )
    assert not read_manager_delivery_history(tmp_path, "remote-goal", now=now)[
        "deliveries"
    ]
    history = read_manager_delivery_history(
        tmp_path, "remote-goal", now=now, lookback_days=7
    )
    assert len(history["deliveries"]) == 1
    assert old in json.dumps(history["deliveries"])


def test_ssh_wire_arguments_execute_real_remote_cli_projection(remote, tmp_path):
    tool, _, _, _, _ = remote
    registry = tmp_path / "remote-registry.json"
    registry.write_text(
        json.dumps({"goals": [{"id": "remote-goal", "repo": str(tmp_path)}]})
    )

    def execute_cli(argv, **kwargs):
        arguments = shlex.split(argv[-1].split("--format json ", 1)[1])
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--runtime-root",
                str(tmp_path / "remote-runtime"),
                "--format",
                "json",
                *arguments,
            ],
            **kwargs,
        )

    tool.remote_runner = execute_cli
    result = tool.read(
        TOOL_NAME, {"view": "portfolio", "source_id": "ssh:research-host", "limit": 3}
    )
    assert result["ok"]
    assert result["rows"][0]["goal_id"] == "remote-goal"
    assert result["rows"][0]["source_host"] == "research-host"
    assert result["rows"][0]["quality"] != "verified"


def test_sources_paginate_and_malformed_remote_output_is_unknown(remote):
    tool, _, _, _, _ = remote
    tool.context["goals"].append({"goal_id": "remote-goal", "title": "Local namesake"})
    first = tool.read(TOOL_NAME, {"view": "sources", "limit": 1})
    assert first["next_offset"] == 1 and first["matched"] == 2
    assert (
        tool.read(TOOL_NAME, {"view": "sources", "offset": 1})["rows"][0]["source_id"]
        == "ssh:research-host"
    )
    assert (
        tool.read(
            TOOL_NAME,
            {
                "view": "todos",
                "source_id": "ssh:research-host",
                "goal_id": "remote-goal",
            },
        )["rows"][0]["title"]
        == "Actual remote task"
    )
    tool.remote_runner = lambda *_, **__: SimpleNamespace(returncode=0, stdout="[]")
    assert not tool.read(
        TOOL_NAME, {"view": "portfolio", "source_id": "ssh:research-host"}
    )["ok"]
