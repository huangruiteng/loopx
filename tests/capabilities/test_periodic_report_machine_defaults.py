from __future__ import annotations

import json
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import pytest

from loopx.capabilities.machine_configuration.builtins import (
    build_builtin_machine_configuration_registry,
)
from loopx.capabilities.machine_configuration.store import (
    configure_machine_configuration,
)
from loopx.capabilities.periodic_report.machine_defaults import (
    PeriodicReportSubscriptionConfigurationError,
    build_goal_periodic_report_delivery_identity,
    build_goal_periodic_report_delivery_plan,
    normalize_loopx_machine_defaults,
    resolve_goal_periodic_report_subscription,
    select_goal_periodic_report_executor,
)
import loopx.capabilities.periodic_report.machine_defaults as machine_defaults_module
from loopx.capabilities.periodic_report.machine_store import (
    configure_periodic_report_machine_defaults,
)
from loopx.cli import main
from loopx.configure_goal import configure_goal


def _defaults(*, enabled: bool = True, route_ref: str = "loopx-concierge") -> dict:
    periodic_report = {
        "enabled": enabled,
        "inheritance": "live_machine_default",
        "timezone": "Asia/Shanghai",
    }
    if enabled:
        periodic_report.update(
            {
                "profile_preset": "weekly-progress",
                "route_ref": route_ref,
            }
        )
    return {
        "schema_version": "loopx_machine_configuration_v0",
        "namespaces": {
            "periodic_report": {
                "schema_version": "periodic_report_machine_defaults_v0",
                **periodic_report,
            }
        },
    }


def _goal(goal_id: str, *, status: str = "active") -> dict:
    return {
        "id": goal_id,
        "repo": f"/projects/{goal_id}",
        "state_file": "GOAL.md",
        "status": status,
    }


def _apply_defaults(runtime_root: Path, defaults: dict) -> None:
    preview = configure_periodic_report_machine_defaults(
        runtime_root=runtime_root,
        machine_defaults=defaults,
    )
    configure_periodic_report_machine_defaults(
        runtime_root=runtime_root,
        machine_defaults=defaults,
        execute=True,
        expected_plan_revision=preview["plan_revision"],
    )


def _remove_defaults(runtime_root: Path) -> None:
    registry = build_builtin_machine_configuration_registry()
    preview = configure_machine_configuration(
        runtime_root=runtime_root,
        configuration=None,
        registry=registry,
    )
    configure_machine_configuration(
        runtime_root=runtime_root,
        configuration=None,
        registry=registry,
        execute=True,
        expected_plan_revision=preview["plan_revision"],
    )


def test_machine_defaults_require_a_route_when_weekly_reports_are_enabled() -> None:
    payload = _defaults()
    payload["namespaces"]["periodic_report"].pop("route_ref")

    with pytest.raises(ValueError, match="route_ref is required"):
        normalize_loopx_machine_defaults(payload)


def test_utc_default_does_not_require_a_platform_timezone_database(monkeypatch) -> None:
    """Windows source installs must accept the built-in UTC default."""

    def missing_timezone(_name: str) -> None:
        raise ZoneInfoNotFoundError("test timezone database unavailable")

    monkeypatch.setattr(machine_defaults_module, "ZoneInfo", missing_timezone)
    payload = _defaults(enabled=False)
    payload["namespaces"]["periodic_report"]["timezone"] = "UTC"

    normalized = normalize_loopx_machine_defaults(payload)
    assert normalized["namespaces"]["periodic_report"]["timezone"] == "UTC"


def test_goal_override_beats_machine_default() -> None:
    goal = _goal("research")
    goal["control_plane"] = {
        "periodic_report": {
            "enabled": False,
            "profile_preset": "weekly-progress",
            "route_ref": "project-room",
            "timezone": "UTC",
        }
    }

    subscription = resolve_goal_periodic_report_subscription(goal, _defaults())

    assert subscription["enabled"] is False
    assert subscription["route_ref"] == "project-room"
    assert subscription["source"] == "goal_override"


def test_runtime_goal_subscription_does_not_fall_back_to_machine_defaults() -> None:
    goal = _goal("research")
    goal["control_plane"] = {"periodic_report": {"enabled": True}}
    original_goal = json.loads(json.dumps(goal))
    defaults = _defaults()
    original_defaults = json.loads(json.dumps(defaults))

    with pytest.raises(
        PeriodicReportSubscriptionConfigurationError,
        match="profile_preset",
    ) as caught:
        resolve_goal_periodic_report_subscription(goal, defaults)

    assert caught.value.goal_id == "research"
    assert caught.value.configuration_source == "goal_override"
    assert caught.value.invalid_fields == ("profile_preset", "route_ref")
    assert goal == original_goal
    assert defaults == original_defaults


def test_unconfigured_goal_is_not_subscribed_at_runtime() -> None:
    subscription = resolve_goal_periodic_report_subscription(_goal("research"), None)

    assert subscription == {
        "schema_version": "periodic_report_goal_subscription_v0",
        "goal_id": "research",
        "enabled": False,
        "source": "not_configured",
        "source_revision": None,
        "profile_preset": None,
        "route_ref": None,
        "timezone": "UTC",
        "effective_revision": subscription["effective_revision"],
    }
    assert "agent_id" not in subscription


def test_existing_goal_follows_live_machine_default_without_mutation() -> None:
    goal = _goal("research")
    original = json.loads(json.dumps(goal))

    first = resolve_goal_periodic_report_subscription(
        goal,
        _defaults(route_ref="project-room-a"),
    )
    second = resolve_goal_periodic_report_subscription(
        goal,
        _defaults(route_ref="project-room-b"),
    )

    assert first["source"] == "machine_default"
    assert first["route_ref"] == "project-room-a"
    assert second["source"] == "machine_default"
    assert second["route_ref"] == "project-room-b"
    assert first["source_revision"] != second["source_revision"]
    assert first["effective_revision"] != second["effective_revision"]
    assert goal == original


def test_clearing_goal_override_restores_live_machine_default(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"goals": [_goal("research")]}),
        encoding="utf-8",
    )
    explicit = {
        "enabled": True,
        "profile_preset": "goal-weekly",
        "route_ref": "existing-goal-binding",
        "timezone": "UTC",
    }

    configured = configure_goal(
        registry_path=registry,
        goal_id="research",
        periodic_report_configuration=explicit,
        execute=True,
    )
    configured_goal = json.loads(registry.read_text(encoding="utf-8"))["goals"][0]
    overridden = resolve_goal_periodic_report_subscription(
        configured_goal,
        _defaults(route_ref="machine-manager-binding"),
    )

    assert configured["after"]["periodic_report"] == explicit
    assert overridden["source"] == "goal_override"
    assert overridden["route_ref"] == "existing-goal-binding"

    cleared = configure_goal(
        registry_path=registry,
        goal_id="research",
        clear_periodic_report_configuration=True,
        execute=True,
    )
    cleared_goal = json.loads(registry.read_text(encoding="utf-8"))["goals"][0]
    inherited = resolve_goal_periodic_report_subscription(
        cleared_goal,
        _defaults(route_ref="machine-manager-binding"),
    )

    assert cleared["after"]["periodic_report"] is None
    assert "periodic_report" not in cleared_goal.get("control_plane", {})
    assert inherited["source"] == "machine_default"
    assert inherited["route_ref"] == "machine-manager-binding"


def test_periodic_report_provenance_ignores_unowned_machine_namespaces() -> None:
    goal = _goal("research")
    periodic_only = _defaults()
    with_sibling = json.loads(json.dumps(periodic_only))
    with_sibling["namespaces"]["search_defaults"] = {
        "schema_version": "search_defaults_v0",
        "provider": "example",
    }

    first = resolve_goal_periodic_report_subscription(goal, periodic_only)
    second = resolve_goal_periodic_report_subscription(goal, with_sibling)

    assert first == second


def test_machine_document_without_periodic_namespace_is_not_configured() -> None:
    subscription = resolve_goal_periodic_report_subscription(
        _goal("research"),
        {
            "schema_version": "loopx_machine_configuration_v0",
            "namespaces": {
                "search_defaults": {
                    "schema_version": "search_defaults_v0",
                }
            },
        },
    )

    assert subscription["source"] == "not_configured"
    assert subscription["source_revision"] is None


def test_delivery_identity_is_goal_period_route_owned_not_agent_owned() -> None:
    first = build_goal_periodic_report_delivery_identity(
        goal_id="research",
        period_start_at="2026-08-24T00:00:00+08:00",
        period_end_at="2026-08-31T00:00:00+08:00",
        route_id="loopx-concierge",
    )
    replay = build_goal_periodic_report_delivery_identity(
        goal_id="research",
        period_start_at="2026-08-24T00:00:00+08:00",
        period_end_at="2026-08-31T00:00:00+08:00",
        route_id="loopx-concierge",
    )

    assert first == replay
    assert set(first) == {
        "schema_version",
        "goal_id",
        "period_start_at",
        "period_end_at",
        "route_id",
        "idempotency_key",
    }
    assert "agent_id" not in first


def test_reporting_agent_is_preferred_but_failover_keeps_goal_identity() -> None:
    preferred = select_goal_periodic_report_executor(
        reporting_agent_id="agent-b",
        eligible_agent_ids=["agent-c", "agent-b", "agent-a"],
    )
    failover = select_goal_periodic_report_executor(
        reporting_agent_id="agent-b",
        eligible_agent_ids=["agent-c", "agent-a"],
    )

    assert preferred["selected_agent_id"] == "agent-b"
    assert preferred["selection_reason"] == "reporting_agent_preferred"
    assert failover["selected_agent_id"] == "agent-a"
    assert failover["selection_reason"] == "reporting_agent_unavailable_failover"


def test_goal_delivery_plan_prefers_the_candidate_reporting_agent() -> None:
    goal = _goal("research")
    result = build_goal_periodic_report_delivery_plan(
        {
            "schema_version": "periodic_report_goal_delivery_plan_request_v0",
            "goal": goal,
            "period_window": {
                "start_at": "2026-08-24T00:00:00+08:00",
                "end_at": "2026-08-31T00:00:00+08:00",
            },
            "reporting_agent_id": "agent-b",
            "eligible_agent_ids": ["agent-a", "agent-b"],
        },
        machine_defaults=_defaults(),
    )

    assert result["status"] == "ready"
    assert result["executor"]["selected_agent_id"] == "agent-b"
    assert "agent_id" not in result["delivery_identity"]


def test_goal_delivery_plan_does_not_activate_an_unconfigured_goal() -> None:
    result = build_goal_periodic_report_delivery_plan(
        {
            "schema_version": "periodic_report_goal_delivery_plan_request_v0",
            "goal": _goal("research"),
            "period_window": {
                "start_at": "2026-08-24T00:00:00+08:00",
                "end_at": "2026-08-31T00:00:00+08:00",
            },
            "reporting_agent_id": "agent-b",
            "eligible_agent_ids": ["agent-a", "agent-b"],
        }
    )

    assert result["status"] == "not_subscribed"
    assert result["subscription"]["source"] == "not_configured"
    assert result["delivery_identity"] is None
    assert result["executor"] is None


@pytest.mark.parametrize(
    "invalid_agent_id",
    [None, 1, True, {"id": "agent-a"}, ""],
)
def test_goal_delivery_executor_rejects_untyped_agent_ids(
    invalid_agent_id: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match=r"eligible_agent_ids\[0\]"):
        select_goal_periodic_report_executor(
            reporting_agent_id="agent-b",
            eligible_agent_ids=[invalid_agent_id],
        )


def test_goal_delivery_executor_reports_an_empty_eligible_set() -> None:
    result = select_goal_periodic_report_executor(
        reporting_agent_id="agent-b",
        eligible_agent_ids=[],
    )

    assert result["selected_agent_id"] is None
    assert result["selection_reason"] == "no_eligible_executor"


def test_delivery_identity_normalizes_equivalent_timestamp_offsets() -> None:
    local = build_goal_periodic_report_delivery_identity(
        goal_id="research",
        period_start_at="2026-08-24T08:00:00+08:00",
        period_end_at="2026-08-31T08:00:00+08:00",
        route_id="loopx-concierge",
    )
    utc = build_goal_periodic_report_delivery_identity(
        goal_id="research",
        period_start_at="2026-08-24T00:00:00Z",
        period_end_at="2026-08-31T00:00:00Z",
        route_id="loopx-concierge",
    )

    assert local == utc


def test_delivery_identity_rejects_an_invalid_period() -> None:
    with pytest.raises(ValueError, match="end must be after"):
        build_goal_periodic_report_delivery_identity(
            goal_id="research",
            period_start_at="2026-08-31T00:00:00Z",
            period_end_at="2026-08-24T00:00:00Z",
            route_id="loopx-concierge",
        )


def test_goal_delivery_plan_cli_reads_live_default_for_the_same_goal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"goals": []}', encoding="utf-8")
    runtime_root = tmp_path / "runtime"
    _apply_defaults(runtime_root, _defaults(route_ref="project-room-a"))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "periodic_report_goal_delivery_plan_request_v0",
                "goal": _goal("research"),
                "period_window": {
                    "start_at": "2026-08-24T00:00:00+08:00",
                    "end_at": "2026-08-31T00:00:00+08:00",
                },
                "reporting_agent_id": "agent-b",
                "eligible_agent_ids": ["agent-a", "agent-b"],
            }
        ),
        encoding="utf-8",
    )
    request_before = request_path.read_bytes()
    command = [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        "periodic-report",
        "plan-goal-delivery",
        "--request-json",
        str(request_path),
    ]

    assert main(command) == 0
    first = json.loads(capsys.readouterr().out)
    _apply_defaults(runtime_root, _defaults(route_ref="project-room-b"))
    assert main(command) == 0
    second = json.loads(capsys.readouterr().out)
    _remove_defaults(runtime_root)
    assert main(command) == 0
    removed = json.loads(capsys.readouterr().out)

    assert first["status"] == second["status"] == "ready"
    assert first["subscription"]["source"] == "machine_default"
    assert first["subscription"]["route_ref"] == "project-room-a"
    assert second["subscription"]["route_ref"] == "project-room-b"
    assert first["subscription"]["source_revision"] != second["subscription"][
        "source_revision"
    ]
    assert first["subscription"]["effective_revision"] != second["subscription"][
        "effective_revision"
    ]
    assert second["executor"]["reporting_agent_id"] == "agent-b"
    assert second["executor"]["selected_agent_id"] == "agent-b"
    assert second["executor"]["selection_reason"] == "reporting_agent_preferred"
    assert "agent_id" not in second["delivery_identity"]
    assert removed["status"] == "not_subscribed"
    assert removed["subscription"]["source"] == "not_configured"
    assert removed["subscription"]["source_revision"] is None
    assert request_path.read_bytes() == request_before


def test_goal_delivery_plan_cli_fails_closed_on_invalid_machine_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"goals": []}', encoding="utf-8")
    runtime_root = tmp_path / "runtime"
    store_path = runtime_root / "machine" / "configuration.json"
    store_path.parent.mkdir(parents=True)
    invalid = _defaults()
    invalid["namespaces"]["periodic_report"].pop("route_ref")
    store_path.write_text(json.dumps(invalid), encoding="utf-8")
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "periodic_report_goal_delivery_plan_request_v0",
                "goal": _goal("research"),
                "period_window": {
                    "start_at": "2026-08-24T00:00:00+08:00",
                    "end_at": "2026-08-31T00:00:00+08:00",
                },
                "reporting_agent_id": "agent-b",
                "eligible_agent_ids": ["agent-b"],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "periodic-report",
                "plan-goal-delivery",
                "--request-json",
                str(request_path),
            ]
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["command"] == "plan-goal-delivery"
    assert "route_ref is required" in payload["error"]


def test_goal_delivery_plan_cli_diagnoses_incomplete_explicit_override_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"goals": []}', encoding="utf-8")
    runtime_root = tmp_path / "runtime"
    _apply_defaults(runtime_root, _defaults())
    request_path = tmp_path / "request.json"
    goal = _goal("research")
    goal["control_plane"] = {
        "periodic_report": {
            "enabled": True,
            "profile_preset": "weekly-progress",
        }
    }
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "periodic_report_goal_delivery_plan_request_v0",
                "goal": goal,
                "period_window": {
                    "start_at": "2026-08-24T00:00:00+08:00",
                    "end_at": "2026-08-31T00:00:00+08:00",
                },
                "reporting_agent_id": "agent-b",
                "eligible_agent_ids": ["agent-b"],
            }
        ),
        encoding="utf-8",
    )
    store_path = runtime_root / "machine" / "configuration.json"
    before = {
        "registry": registry_path.read_bytes(),
        "request": request_path.read_bytes(),
        "machine_configuration": store_path.read_bytes(),
    }

    assert (
        main(
            [
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "periodic-report",
                "plan-goal-delivery",
                "--request-json",
                str(request_path),
            ]
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload == {
        "ok": False,
        "schema_version": "periodic_report_subscription_error_v0",
        "command": "plan-goal-delivery",
        "error_kind": "subscription_configuration_invalid",
        "goal_id": "research",
        "configuration_source": "goal_override",
        "invalid_fields": ["route_ref"],
        "error": "goal periodic_report.route_ref is required",
        "remediation": (
            "Provide a complete explicit periodic_report override, or clear the "
            "override to restore live machine-default inheritance."
        ),
        "mutation_performed": False,
    }
    assert (
        main(
            [
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "markdown",
                "periodic-report",
                "plan-goal-delivery",
                "--request-json",
                str(request_path),
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == (
        "# Periodic Report Configuration Error\n\n"
        "- error: goal periodic_report.route_ref is required\n"
        "- configuration_source: `goal_override`\n"
        "- invalid_fields: `route_ref`\n"
        "- mutation_performed: `False`\n\n"
        "## Remediation\n\n"
        "Provide a complete explicit periodic_report override, or clear the "
        "override to restore live machine-default inheritance.\n\n"
    )
    assert registry_path.read_bytes() == before["registry"]
    assert request_path.read_bytes() == before["request"]
    assert store_path.read_bytes() == before["machine_configuration"]
