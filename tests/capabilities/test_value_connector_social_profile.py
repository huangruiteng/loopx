from __future__ import annotations

from loopx.capabilities.content_ops.social_browser_x import (
    CONTENT_OPS_SOCIAL_BROWSER_X_PROVIDER_SCHEMA_VERSION,
    SOCIAL_BROWSER_X_PROVIDER_MODULE,
    build_social_browser_x_provider_packet,
)
from loopx.capabilities.content_ops.surface import build_content_ops_preview_packet
from loopx.capabilities.catalog import BUILTIN_CAPABILITIES
from loopx.capabilities.value_connectors.install_check import (
    build_value_connector_install_check_packet,
)
from loopx.capabilities.value_connectors.source_map import (
    build_value_connector_source_map_packet,
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
        "doc": "docs/capabilities/content-ops/README.md",
    }
