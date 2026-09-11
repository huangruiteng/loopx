from __future__ import annotations

import pytest

from loopx.capabilities.configuration_ui import (
    build_capability_configuration_catalog,
    capability_configuration_editor,
    resolve_capability_configuration,
)
from loopx.configuration_catalog import build_goal_configuration_catalog


def test_periodic_report_editor_is_shared_across_machine_and_goal_scopes() -> None:
    editor = capability_configuration_editor("periodic_report")

    assert editor["schema_version"] == "capability_configuration_editor_v0"
    assert editor["editable"] is True
    assert editor["supported_scopes"] == ["machine", "goal"]
    assert [field["key"] for field in editor["fields"]] == [
        "enabled",
        "profile_preset",
        "route_ref",
        "timezone",
    ]


def test_catalog_merges_machine_and_goal_descriptors_without_losing_scope() -> None:
    catalog = build_capability_configuration_catalog(
        machine_namespaces=[
            {
                "namespace": "periodic_report",
                "title": "Periodic reports",
                "description": "Machine default.",
            },
            {
                "namespace": "search_defaults",
                "title": "Search defaults",
            },
        ],
        goal_features=[
            {
                "feature_id": "periodic_report",
                "display_name": "Periodic reports",
                "availability": "supported_opt_in",
                "default": {"enabled": False},
                "current": {"enabled": True},
            },
            {
                "feature_id": "explore_graph",
                "display_name": "Explore Graph",
                "current": {"enabled": False},
            },
        ],
    )

    assert catalog["schema_version"] == "capability_configuration_catalog_v0"
    entries = {item["capability_id"]: item for item in catalog["capabilities"]}
    assert entries["periodic_report"]["available_scopes"] == ["machine", "goal"]
    assert (
        entries["periodic_report"]["effective_value_policy"]
        == "goal_override_over_live_machine_default"
    )
    assert entries["explore_graph"]["available_scopes"] == ["goal"]
    assert entries["search_defaults"]["available_scopes"] == ["machine"]
    assert entries["search_defaults"]["configuration_editor"]["editable"] is False


@pytest.mark.parametrize(
    ("machine_namespaces", "goal_features", "message"),
    [
        ([{}], [], "requires a namespace"),
        ([], [{}], "requires a feature_id"),
        (
            [{"namespace": "same"}, {"namespace": "same"}],
            [],
            "duplicate machine capability",
        ),
        (
            [],
            [{"feature_id": "same"}, {"feature_id": "same"}],
            "duplicate Goal capability",
        ),
    ],
)
def test_catalog_fails_closed_on_incomplete_or_duplicate_descriptors(
    machine_namespaces: list[dict[str, object]],
    goal_features: list[dict[str, object]],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_capability_configuration_catalog(
            machine_namespaces=machine_namespaces,
            goal_features=goal_features,
        )


def test_goal_configuration_uses_the_shared_capability_catalog() -> None:
    catalog = build_goal_configuration_catalog(
        goal_id="goal-example",
        settings={},
        feature_summary={},
        default_multi_subagent_max_children=3,
        explore_harness_profiles=("generic",),
    )

    shared = catalog["capability_catalog"]
    assert shared["schema_version"] == "capability_configuration_catalog_v0"
    assert {item["capability_id"] for item in shared["capabilities"]} == {
        item["feature_id"] for item in catalog["features"]
    }
    assert all(item["available_scopes"] == ["goal"] for item in shared["capabilities"])
    multi_subagent = next(
        item
        for item in shared["capabilities"]
        if item["capability_id"] == "multi_subagent"
    )
    assert multi_subagent["context_contribution"] == {
        "supported_phases": ["before_plan", "before_delegate", "after_delegate_result"],
        "target": "coordinator", "activation": "with_capability", "receipt_required": True,
    }
    assert "context_contribution" not in multi_subagent["current"]
    assert multi_subagent["default"] == {
        "enabled": False,
        "max_children": 3,
        "allowed_domains": [],
    }


def test_goal_override_wins_atomically_without_rebinding_machine_fields() -> None:
    machine_default = {
        "enabled": True,
        "profile_preset": "weekly-progress",
        "route_ref": "loopx-manager-group",
        "timezone": "Asia/Shanghai",
    }
    existing_goal_override = {
        "enabled": True,
        "profile_preset": "ark-4.0-weekly",
        "route_ref": "existing-goal-binding",
        "timezone": "Asia/Shanghai",
    }

    resolved = resolve_capability_configuration(
        "periodic_report",
        goal_override=existing_goal_override,
        machine_default=machine_default,
    )

    assert resolved["schema_version"] == "capability_configuration_resolution_v0"
    assert resolved["source"] == "goal_override"
    assert resolved["configuration"] == existing_goal_override
    assert resolved["configuration"]["route_ref"] == "existing-goal-binding"
    assert resolved["inherited"] is False
    assert resolved["goal_override_present"] is True
    assert resolved["machine_default_present"] is True
    assert resolved["effective_revision"].startswith("sha256:")


def test_unconfigured_goal_inherits_live_machine_default_without_mutation() -> None:
    machine_default = {
        "enabled": True,
        "profile_preset": "weekly-progress",
        "route_ref": "loopx-manager-group",
        "timezone": "Asia/Shanghai",
    }

    resolved = resolve_capability_configuration(
        "periodic_report",
        machine_default=machine_default,
        capability_default={"enabled": False},
    )

    assert resolved["source"] == "machine_default"
    assert resolved["configuration"] == machine_default
    assert resolved["inherited"] is True
    assert resolved["goal_override_present"] is False


def test_resolution_rejects_values_for_unsupported_scopes() -> None:
    with pytest.raises(ValueError, match="does not support machine configuration"):
        resolve_capability_configuration(
            "explore_graph",
            machine_default={"enabled": True},
        )

    with pytest.raises(TypeError, match="goal_override must be an object or null"):
        resolve_capability_configuration(  # type: ignore[arg-type]
            "periodic_report",
            goal_override=True,
        )
