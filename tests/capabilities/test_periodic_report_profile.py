from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.capabilities.periodic_report import build_periodic_report_activation
from loopx.cli import main


def _profile(*, enabled: bool = True) -> dict[str, object]:
    return {
        "schema_version": "periodic_report_profile_v0",
        "enabled": enabled,
        "profile_id": "release_summary",
        "profile_version": "v1",
        "trigger_policy": {
            "enabled_kinds": ["cadence_due", "primary_goal_outcome"],
            "minimum_interval_seconds": 3600,
        },
        "schedule": {
            "schema_version": "periodic_report_schedule_v0",
            "schedule_id": "weekly_window",
            "rrule": "FREQ=WEEKLY;BYDAY=MO;BYHOUR=9",
            "timezone": "Asia/Shanghai",
        },
        "source_bindings": [
            {
                "source_id": "release_state",
                "source_kind": "validated_outcomes",
                "adapter_id": "release_state_v0",
                "provider": {"kind": "builtin"},
            }
        ],
        "renderer_bindings": [
            {
                "renderer_id": "markdown",
                "renderer_kind": "markdown",
                "adapter_id": "markdown_v0",
                "provider": {"kind": "builtin"},
            }
        ],
        "sink_bindings": [
            {
                "schema_version": "periodic_report_sink_binding_v0",
                "sink_id": "project_archive",
                "sink_kind": "project_resource",
                "sink_role": "archive",
                "dependency_policy": "optional",
                "capability": {
                    "capability_id": "report.archive.write",
                    "capability_version": "v0",
                },
                "extension": {
                    "extension_id": "project_resource_report_archive",
                    "extension_version": "1.0.0",
                    "protocol": "periodic_report_sink_v0",
                },
            }
        ],
    }


def test_profile_is_default_off() -> None:
    activation = build_periodic_report_activation(
        {
            "schema_version": "periodic_report_profile_v0",
            "profile_id": "project_summary",
            "profile_version": "v1",
        }
    )

    assert activation["status"] == "disabled"
    assert activation["active"] is False
    assert activation["generation_allowed"] is False
    assert activation["boundary"]["default_enabled"] is False


def test_enabled_profile_is_domain_neutral_and_archive_is_optional() -> None:
    activation = build_periodic_report_activation(_profile())

    assert activation["status"] == "enabled"
    assert activation["extension_mode"] == "enhanced"
    assert activation["required_extension_count"] == 0
    assert activation["optional_extension_count"] == 1
    source = activation["profile"]["source_bindings"][0]
    assert source["source_kind"] == "validated_outcomes"
    assert "issue" not in json.dumps(activation).lower()
    assert activation["boundary"]["extension_effects_performed"] is False


def test_enabled_profile_requires_sources_and_renderers() -> None:
    profile = _profile()
    profile["source_bindings"] = []
    with pytest.raises(ValueError, match="at least one source"):
        build_periodic_report_activation(profile)

    profile = _profile()
    profile["renderer_bindings"] = []
    with pytest.raises(ValueError, match="at least one renderer"):
        build_periodic_report_activation(profile)


def test_builtin_adapter_rejects_extension_identity() -> None:
    profile = _profile()
    profile["source_bindings"][0]["provider"] = {
        "kind": "builtin",
        "provider_id": "unexpected_extension",
    }

    with pytest.raises(ValueError, match="must not declare extension identity"):
        build_periodic_report_activation(profile)


def test_profile_cli_returns_activation_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(_profile()), encoding="utf-8")

    assert (
        main(
            [
                "--format",
                "json",
                "periodic-report",
                "inspect-profile",
                "--profile-json",
                str(path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "periodic_report_activation_v0"
    assert payload["active"] is True
