from __future__ import annotations

import hashlib
import json
from importlib.resources import files

from loopx.capabilities.reward_memory.scoped_feedback import (
    build_scoped_feedback_reward_memory_candidate,
)
from loopx.capabilities.content_ops.social_browser_x import (
    CONTENT_OPS_SOCIAL_BROWSER_X_PROVIDER_SCHEMA_VERSION,
    SOCIAL_BROWSER_X_PROVIDER_MODULE,
    build_social_browser_x_provider_packet,
)
from loopx.capabilities.content_ops.surface import build_content_ops_preview_packet
from loopx.capabilities.catalog import BUILTIN_CAPABILITIES
from loopx.capabilities.value_connectors.install_check import (
    build_value_connector_install_check_packet,
    render_value_connector_install_check_markdown,
)
from loopx.capabilities.value_connectors.source_map import (
    build_value_connector_source_map_packet,
    render_value_connector_source_map_markdown,
)


def test_social_browser_x_provider_owns_the_shared_contract() -> None:
    provider = build_social_browser_x_provider_packet()

    assert provider["ok"] is True
    assert (
        provider["schema_version"]
        == CONTENT_OPS_SOCIAL_BROWSER_X_PROVIDER_SCHEMA_VERSION
    )
    assert provider["connector_id"] == "social_browser_x"
    assert provider["outcome_capability_id"] == "content-ops"
    assert provider["provider_module"] == SOCIAL_BROWSER_X_PROVIDER_MODULE
    assert provider["truth_contract"] == {
        "compatibility_facade_may_delegate": True,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "autopublish_allowed": False,
        "raw_platform_data_recorded": False,
    }


def test_value_connector_facade_delegates_social_profile_contract() -> None:
    provider = build_social_browser_x_provider_packet()
    source_map = build_value_connector_source_map_packet(connector="social_browser_x")
    install = build_value_connector_install_check_packet(connector="social_browser_x")

    assert source_map["source_profiles"][0] == {
        "schema_version": "value_connector_source_profile_v0",
        **provider["source_profile"],
        "external_reads_allowed": True,
        "external_writes_allowed": False,
        "outcome_capability_id": "content-ops",
        "provider_binding_state": "migrated",
        "provider_module": SOCIAL_BROWSER_X_PROVIDER_MODULE,
    }
    assert source_map["projection"]["migrated_profile_count"] == 1
    assert install["checks"] == [provider["install_check"]]


def test_content_ops_preview_uses_owned_social_connector_trial() -> None:
    provider = build_social_browser_x_provider_packet()
    preview = build_content_ops_preview_packet()
    trials = {item["trial_id"]: item for item in preview["surface"]["connector_trials"]}

    assert trials["trial_x_ego_lite_browser"] == provider["connector_trial"]


def test_content_ops_catalog_declares_social_provider() -> None:
    content_ops = next(
        capability
        for capability in BUILTIN_CAPABILITIES
        if capability["id"] == "content-ops"
    )
    protocols = {
        item["schema_version"]: item for item in content_ops["implemented_protocols"]
    }

    assert protocols[CONTENT_OPS_SOCIAL_BROWSER_X_PROVIDER_SCHEMA_VERSION] == {
        "schema_version": CONTENT_OPS_SOCIAL_BROWSER_X_PROVIDER_SCHEMA_VERSION,
        "module": SOCIAL_BROWSER_X_PROVIDER_MODULE,
        "doc": "loopx/capabilities/content_ops/README.md",
    }


def test_new_agent_discovers_packaged_advisory_seed_without_memory() -> None:
    raw = (
        files("loopx.capabilities.content_ops")
        .joinpath("experiences/x-composer-preflight-v1.json")
        .read_bytes()
    )
    seed = json.loads(raw)
    source = build_value_connector_source_map_packet(connector="social_browser_x")
    install = build_value_connector_install_check_packet(connector="social_browser_x")
    surfaced = source["source_profiles"][0]["operating_experience"]
    assert surfaced == seed | {
        "content_digest": "sha256:" + hashlib.sha256(raw).hexdigest()
    }
    assert install["checks"][0]["operating_experience"] == surfaced
    assert seed["authority"] == "advisory"
    assert seed["target_class"] == "procedural_experience"
    assert seed["version"] >= 1
    assert 0 < len(seed["content_summary"]) <= 500
    assert seed["applicability"] and seed["limits"] and seed["procedure"]
    init = seed["memory_initialization"]
    assert init["automatic_import"] is False
    assert init["provider_calls_performed"] is False
    assert init["grants_publish_authority"] is False
    for packet, render in (
        (source, render_value_connector_source_map_markdown),
        (install, render_value_connector_install_check_markdown),
    ):
        assert seed["content_summary"] in render(packet)
    assert source["external_writes_performed"] is False
    assert source["source_profiles"][0]["external_writes_allowed"] is False
    # Non-social entry points retain their existing shape; no global hook.
    for profile in build_value_connector_source_map_packet()["source_profiles"]:
        if profile["connector_id"] != "social_browser_x":
            assert "operating_experience" not in profile
    surfaced["procedure"].clear()
    assert build_social_browser_x_provider_packet()["source_profile"][
        "operating_experience"
    ]["procedure"]


def test_seed_reuses_scoped_memory_guard_not_an_import_permission() -> None:
    seed = build_social_browser_x_provider_packet()["source_profile"][
        "operating_experience"
    ]
    source_ref = (
        f"seed:{seed['seed_id']}:v{seed['version']}:{seed['content_digest'][-16:]}"
    )
    event = {
        "schema_version": "scoped_feedback_reward_memory_event_v0",
        "feedback_ref": source_ref,
        "workspace_ref": "workspace:synthetic",
        "project_ref": "project:synthetic",
        "peer_ref": "agent:synthetic",
        "surface_id": seed["memory_initialization"]["recall_surface_id"],
        "revision_ref": "revision:synthetic-verification",
        "target_class": seed["target_class"],
        "content_summary": seed["content_summary"],
        "source": {
            "source_kind": "reviewed_learning_card",
            "source_ref": source_ref,
            "actor_ref": "agent:synthetic",
            "actor_role": "corpus_reviewer",
        },
        "reasoning": {
            "summary": "Synthetic current-artifact review fixture",
            "confidence": "high",
        },
        "guard_context": {
            "source_freshness": "current",
            "conflict_state": "clear",
            "current_artifact_verified": False,
        },
        "requested_action_scopes": [],
        "raw_content_captured": False,
    }
    candidate = build_scoped_feedback_reward_memory_candidate(event)["shared_candidate"]
    assert candidate["status"] == "guard_blocked"
    event["guard_context"]["current_artifact_verified"] = True
    candidate = build_scoped_feedback_reward_memory_candidate(event)["shared_candidate"]
    assert candidate["status"] == "review_ready"
    assert candidate["candidate"]["content_summary"] == seed["content_summary"]
    assert candidate["provider_write_performed"] is False
    assert candidate["external_writes_performed"] is False
    assert (
        candidate
        == build_scoped_feedback_reward_memory_candidate(event)["shared_candidate"]
    )
    event["requested_action_scopes"] = ["publish"]
    assert (
        build_scoped_feedback_reward_memory_candidate(event)["shared_candidate"][
            "status"
        ]
        == "guard_blocked"
    )
