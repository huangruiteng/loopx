from __future__ import annotations

import hashlib
import json
import shlex

import pytest

from loopx.capabilities.reward_memory.feedback_hint import build_feedback_review_hint
from loopx.cli import main
from loopx.cli_commands import lark_inbox
from tests.capabilities.test_agent_turn_recall import raw_config
from tests.extensions.test_lark_inbox_reactions import _fixture


def experiment(tmp_path):
    project = tmp_path / "project"
    config = project / ".loopx/config/reward-memory/experiment.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(raw_config(goal_id="reward-memory-goal")))
    config_digest = f"sha256:{hashlib.sha256(config.read_bytes()).hexdigest()}"
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goals": [
                    {
                        "id": "reward-memory-goal",
                        "repo": str(project),
                        "coordination": {"registered_agents": ["pilot", "meta"]},
                        "control_plane": {
                            "reward_memory": {
                                "enabled": True,
                                "experimental": True,
                                "enabled_agents": ["pilot"],
                                "config_path": ".loopx/config/reward-memory/experiment.json",
                                "config_digest": config_digest,
                                "enablement_receipts": {
                                    "pilot": {
                                        "schema_version": (
                                            "reward_memory_enablement_receipt_v0"
                                        ),
                                        "status": "verified",
                                        "goal_id": "reward-memory-goal",
                                        "agent_id": "pilot",
                                        "config_digest": config_digest,
                                        "provider_id": "openviking",
                                        "isolation_mode": ("goal_scoped_agent_private"),
                                        "actor_binding_verified": True,
                                        "writability_verified": True,
                                        "exact_readback_verified": True,
                                    }
                                },
                            }
                        },
                    }
                ],
            }
        )
    )
    return registry, project, config


def _refresh_binding(registry, config):
    payload = json.loads(registry.read_text())
    digest = f"sha256:{hashlib.sha256(config.read_bytes()).hexdigest()}"
    binding = payload["goals"][0]["control_plane"]["reward_memory"]
    binding["config_digest"] = digest
    binding["enablement_receipts"]["pilot"]["config_digest"] = digest
    registry.write_text(json.dumps(payload))


def hint(registry, **overrides):
    return build_feedback_review_hint(
        **{
            "registry_path": registry,
            "goal_id": "reward-memory-goal",
            "agent_id": "pilot",
            **overrides,
        }
    )


@pytest.mark.parametrize("automatic", [False, True])
def test_hint_reuses_explicit_route_without_automation_or_provider(
    tmp_path, monkeypatch, automatic
):
    registry, _, config = experiment(tmp_path)
    raw = raw_config(goal_id="reward-memory-goal")
    raw["automation"] = {
        "automatic_recall": automatic,
        "automatic_ingest": automatic,
        "fail_open": True,
    }
    config.write_text(json.dumps(raw))
    _refresh_binding(registry, config)

    def forbidden(*a, **kw):
        pytest.fail("a hint must not construct a memory provider")

    monkeypatch.setattr(
        "loopx.capabilities.reward_memory.application.build_context_provider", forbidden
    )
    result = hint(registry)
    assert result["automatic_ingest"] is automatic
    assert not result["automatic_ingest_required"]
    assert result["advisory_only"]
    assert not result["grants_new_action_authority"]
    assert not result["blocks_inbox_settlement"]
    assert not result["provider_calls_performed"]
    assert result["routes"][0]["target_class"] == "soft_preference"
    assert result["routes"][0]["scope"]["peer_ref"] == "agent:pilot"
    argv = shlex.split(result["preview_command"])
    assert argv == [
        "loopx",
        "--format",
        "json",
        "--registry",
        str(registry),
        "reward-memory",
        "ingest-event",
        "--goal-id",
        "reward-memory-goal",
        "--agent-id",
        "pilot",
        "--input",
        "<compact-event.json>",
    ]
    assert (
        "authority" in result["instruction"]
        and "exact readback" in result["instruction"]
    )
    assert "viking://" not in json.dumps(result)


@pytest.mark.parametrize(
    "condition",
    [
        "disabled",
        "other_agent",
        "unregistered",
        "missing_agent",
        "missing_goal",
        "invalid_config",
        "wrong_peer",
        "unsupported_adapter",
        "policy_disabled",
        "read_only",
        "missing_registry",
    ],
)
def test_ineligible_routes_produce_no_hint(tmp_path, condition):
    registry, _, config = experiment(tmp_path)
    overrides = {}
    raw = raw_config(goal_id="reward-memory-goal")
    if condition == "disabled":
        payload = json.loads(registry.read_text())
        payload["goals"][0]["control_plane"]["reward_memory"]["enabled"] = False
        registry.write_text(json.dumps(payload))
    elif condition in {"other_agent", "unregistered", "missing_agent"}:
        overrides["agent_id"] = {
            "other_agent": "meta",
            "unregistered": "stranger",
            "missing_agent": None,
        }[condition]
    elif condition == "missing_goal":
        overrides["goal_id"] = None
    elif condition == "missing_registry":
        registry = tmp_path / "absent.json"
    elif condition == "invalid_config":
        raw = {}
    elif condition == "wrong_peer":
        raw = raw_config(
            peer_ref="agent:meta",
            goal_id="reward-memory-goal",
        )
    elif condition == "unsupported_adapter":
        raw["surfaces"][0]["adapter"] = "issue_fix_maintainer_feedback"
    elif condition == "policy_disabled":
        raw["corpora"][0]["standing_policy"]["enabled"] = False
    elif condition == "read_only":
        raw["corpora"][0]["corpus"]["write_authority"] = "read_only"
    config.write_text(json.dumps(raw))
    assert hint(registry, **overrides) is None


def test_generated_command_previews_reviewed_event_and_rejects_scope_expansion(
    tmp_path, capsys
):
    registry, _, _ = experiment(tmp_path)
    result = hint(registry)
    route = result["routes"][0]
    event = {
        **{k: v for k, v in route["scope"].items() if k != "surface_ids"},
        "schema_version": "scoped_feedback_reward_memory_event_v0",
        "feedback_ref": "feedback:example:summary",
        "surface_id": route["surface_id"],
        "revision_ref": "revision:example",
        "target_class": "soft_preference",
        "content_summary": "Use a concise summary followed by complete handoff details.",
        "source": {
            "source_kind": "explicit_user_instruction",
            "source_ref": "feedback:example:summary",
            "actor_ref": "user:example",
            "actor_role": "verified_project_owner_or_operator",
        },
        "reasoning": {
            "summary": "Confirmed scoped formatting feedback.",
            "confidence": "high",
        },
        "guard_context": {
            "source_freshness": "current",
            "conflict_state": "clear",
            "current_artifact_verified": True,
        },
        "requested_action_scopes": [],
        "raw_content_captured": False,
    }
    path = tmp_path / "compact-event.json"
    command = shlex.split(result["preview_command"])[1:]
    command[-1] = str(path)
    for peer, expected in [
        ("agent:pilot", "unavailable"),
        ("agent:meta", "guard_blocked"),
    ]:
        event["peer_ref"] = peer
        path.write_text(
            json.dumps(
                {
                    "adapter": "scoped_feedback",
                    "event": event,
                    "observed_at": "2026-08-01T00:00:00Z",
                }
            )
        )
        assert main(command) == 0
        receipt = json.loads(capsys.readouterr().out)
        assert receipt["status"] == expected, receipt["guard"]
        assert receipt["experiment"]["automatic_ingest"] is False
        assert not receipt["external_writes_performed"]
        assert not receipt["exact_readback_verified"]


@pytest.mark.parametrize(
    "condition",
    [
        "enabled",
        "empty",
        "disabled",
        "explicit_config",
        "project_override",
        "memory_disabled",
    ],
)
def test_real_drain_entrypoint_preserves_inbox_and_disabled_parity(
    tmp_path, monkeypatch, capsys, condition
):
    inbox_config, _, inbox_project = _fixture(tmp_path / "project", lifecycle=False)
    registry, project, _ = experiment(tmp_path)
    # Bind the synthetic project's existing local inbox through its registry.
    payload = json.loads(registry.read_text())
    payload["goals"][0]["control_plane"]["lark_event_inbox"] = {
        "enabled": True,
        "config_path": str(inbox_config),
    }
    registry.write_text(json.dumps(payload))
    monkeypatch.setattr(lark_inbox, "_resolve_lark_activation", lambda *a, **kw: {})
    original = lark_inbox.inspect_routed_lark_event_inbox(
        project=inbox_project,
        config_path=inbox_config,
        limit=20,
    )
    if condition in {"empty", "disabled"}:
        observed = dict(original)
        if condition == "empty":
            observed["items"] = []
        else:
            observed["enabled"] = False
        monkeypatch.setattr(
            lark_inbox, "inspect_routed_lark_event_inbox", lambda **kw: dict(observed)
        )
        original = observed
    extra = []
    if condition == "explicit_config":
        extra = ["--config", str(inbox_config), "--project", str(project)]
    if condition == "project_override":
        extra = ["--project", str(project)]
    if condition == "memory_disabled":
        payload["goals"][0]["control_plane"]["reward_memory"]["enabled"] = False
        registry.write_text(json.dumps(payload))
    assert (
        main(
            [
                "--format",
                "json",
                "--registry",
                str(registry),
                "lark-inbox",
                "drain",
                "--goal-id",
                "reward-memory-goal",
                "--agent-id",
                "pilot",
                *extra,
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    review = result.pop("reward_memory_feedback_review", None)
    result.pop("extension_activation", None)
    assert result == original
    assert bool(review) is (condition == "enabled")
    if review:
        rendered = lark_inbox._render({"reward_memory_feedback_review": review})
        assert review["preview_command"] in rendered
        assert "advisory" in rendered
