from __future__ import annotations

import argparse
import json
from datetime import datetime

import pytest

from loopx.capabilities.reward_memory import outbound
from loopx.capabilities.reward_memory.experiment import (
    load_reward_memory_experiment_config,
)
from tests.capabilities import test_agent_turn_recall as turn
from tests.extensions.test_lark_inbox_reactions import _fixture, ReplyRunner
from loopx.extensions.lark.inbox_reply import (
    send_lark_inbox_message,
    reply_lark_event_inbox,
)


def configure(tmp_path, monkeypatch, *, unavailable=False):
    raw = turn.raw_config()
    raw["corpora"][0]["corpus"]["scope"]["surface_ids"] = [outbound.SURFACE]
    raw["surfaces"][0]["surface_id"] = outbound.SURFACE
    path = tmp_path / "memory.json"
    path.write_text(json.dumps(raw))
    config = load_reward_memory_experiment_config(
        project=tmp_path, config_path="memory.json"
    )
    corpus = config["corpora"]["agent_turn_preferences"]["corpus"]
    record = json.dumps(
        {
            "schema_version": "reward_memory_active_record_v0",
            "corpus_id": corpus["corpus_id"],
            "candidate_ref": "candidate:guidance",
            "target_class": "soft_preference",
            "content_summary": "Try safe alternatives before requesting help.",
            "scope": corpus["scope"],
            "lifecycle": {"state": "active"},
        }
    )
    provider = turn.RecallProvider(record, unavailable=unavailable)
    monkeypatch.setattr(
        outbound, "resolve_reward_memory_experiment", lambda **kw: ({}, config)
    )
    from loopx.capabilities.reward_memory import application

    monkeypatch.setattr(application, "build_context_provider", lambda value: provider)
    return config, provider


@pytest.mark.parametrize("purpose", ["help", "progress", "unspecified"])
def test_real_recall_review_is_intent_bound(tmp_path, monkeypatch, purpose):
    _, provider = configure(tmp_path, monkeypatch)
    kwargs = dict(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        purpose=purpose,
    )
    first = outbound.outbound_guidance_hook(**kwargs)("sha256:first")
    assert first["status"] == "applied"
    assert first["agent_review_required"] and not first["continue_delivery"]
    assert first["application"]["receipt"]["result_readback_verified"]
    reviewed = outbound.outbound_guidance_hook(
        **kwargs, reviewed_digest=first["review_digest"]
    )
    assert reviewed("sha256:first")["continue_delivery"]
    assert not reviewed("sha256:changed")["continue_delivery"]
    assert provider.calls == 3
    assert all("sha256:first" not in query for query in provider.queries)


def test_disabled_urgent_failure_and_wrong_peer(tmp_path, monkeypatch):
    config, _ = configure(tmp_path, monkeypatch)
    kwargs = dict(
        registry_path=tmp_path / "registry.json", goal_id="goal", agent_id="pilot"
    )
    assert outbound.outbound_guidance_hook(**kwargs, purpose="urgent")("intent")[
        "continue_delivery"
    ]
    with pytest.raises(ValueError, match="agent scope"):
        outbound.outbound_guidance_hook(**(kwargs | {"agent_id": "other"}))
    config["automation"]["automatic_recall"] = False
    assert outbound.outbound_guidance_hook(**kwargs) is None
    configure(tmp_path, monkeypatch, unavailable=True)
    failed = outbound.outbound_guidance_hook(**kwargs)("intent")
    assert failed["status"] == "provider_unavailable"
    assert failed["continue_delivery"] and not failed["provider_failure_is_user_gate"]


def test_unconfigured_surface_preserves_existing_sender(tmp_path, monkeypatch):
    config, _ = configure(tmp_path, monkeypatch)
    del config["surfaces"][outbound.SURFACE]
    assert (
        outbound.outbound_guidance_hook(
            registry_path=tmp_path / "registry.json",
            goal_id="goal",
            agent_id="pilot",
        )
        is None
    )


@pytest.mark.parametrize("reply", [False, True])
def test_sender_stops_before_write_then_preserves_readback(
    tmp_path, monkeypatch, reply
):
    configure(tmp_path, monkeypatch)
    config, _, project = _fixture(tmp_path, lifecycle=False)
    kwargs = dict(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        purpose="help",
    )
    sender = reply_lark_event_inbox if reply else send_lark_inbox_message
    send_args = dict(project=project, config_path=config, text="done", execute=True)
    if reply:
        send_args["message_id"] = "om_reaction_fixture"
    runner = ReplyRunner(readback_text="done")
    first = sender(
        **send_args,
        runner=runner,
        before_send=outbound.outbound_guidance_hook(**kwargs),
    )
    assert first["status"] == "agent_review_required"
    assert not first["external_write_performed"]
    assert not any(
        ("+messages-send" in c or "+messages-reply" in c) and "--dry-run" not in c
        for c in runner.calls
    )
    hook = outbound.outbound_guidance_hook(
        **kwargs, reviewed_digest=first["outbound_guidance"]["review_digest"]
    )
    sent = sender(**send_args, runner=runner, before_send=hook)
    assert sent["reply_verified"] and sent["external_write_performed"]
    assert not sent["outbound_guidance"]["grants_new_action_authority"]


def test_cli_opaque_turn_uses_real_timestamp(tmp_path, monkeypatch):
    from loopx.capabilities.agent_turn_recall import cli

    config = turn.normalized_config(tmp_path)
    quota = turn.quota_decision() | {
        "mode": "should-run",
        "goal_id": "goal",
        "agent_identity": {"agent_id": "pilot"},
        "heartbeat_receipt": {"turn_instance_id": "opaque-turn", "status": "committed"},
    }
    monkeypatch.setattr(cli, "_goal_repo", lambda *a: tmp_path)
    monkeypatch.setattr(
        cli, "resolve_reward_memory_experiment", lambda **kw: ({}, config)
    )
    monkeypatch.setattr(cli, "_quota_decision", lambda path: quota)
    observed = []

    def run(config, situation, **kw):
        observed.append(datetime.fromisoformat(kw["observed_at"]))
        return {"ok": True, "status": "empty"}

    monkeypatch.setattr(cli, "run_agent_turn_recall", run)
    args = argparse.Namespace(
        command="agent-turn-recall",
        goal_id="goal",
        agent_id="pilot",
        turn_instance_id="opaque-turn",
        quota_decision_json="unused",
        session_ref=None,
        force_refresh=True,
        execute=True,
    )
    assert (
        cli.handle_agent_turn_recall_command(
            args,
            registry_path=tmp_path / "registry.json",
            output_format=lambda *a: "json",
            print_payload=lambda *a: None,
        )
        == 0
    )
    assert len(observed) == 1 and observed[0].tzinfo is not None


@pytest.mark.parametrize("command", ["send", "reply"])
def test_cli_installs_hook_at_real_sender(tmp_path, monkeypatch, command):
    from loopx.cli_commands import lark_inbox as cli

    configure(tmp_path, monkeypatch)
    config, _, project = _fixture(tmp_path, lifecycle=False)
    monkeypatch.setattr(cli, "_inbox_context", lambda *a: (project, config))
    monkeypatch.setattr(cli, "_resolve_lark_activation", lambda *a, **kw: {})
    monkeypatch.setattr(cli, "resolve_routed_lark_inbox_config", lambda **kw: config)
    monkeypatch.setattr(cli, "resolve_routed_lark_inbox_route", lambda **kw: config)
    runner = ReplyRunner(readback_text="done")
    sender = reply_lark_event_inbox if command == "reply" else send_lark_inbox_message
    monkeypatch.setattr(
        cli,
        "reply_lark_event_inbox" if command == "reply" else "send_lark_inbox_message",
        lambda **kw: sender(**kw, runner=runner),
    )
    args = argparse.Namespace(
        command="lark-inbox",
        lark_inbox_command=command,
        goal_id="goal",
        agent_id="pilot",
        message_id="om_reaction_fixture",
        route_key="example",
        text="done",
        execute=True,
        provider_preflight=False,
        message_purpose="help",
        reviewed_guidance_digest=None,
    )
    results = []
    cli.handle_lark_inbox_command(
        args,
        registry_path=tmp_path / "registry.json",
        runtime_root_arg=None,
        output_format=lambda *a: "json",
        print_payload=lambda payload, *a: results.append(payload),
    )
    assert results[0]["status"] == "agent_review_required"
    assert results[0]["external_write_performed"] is False
    assert "not a request for user approval" in cli._render(results[0])
