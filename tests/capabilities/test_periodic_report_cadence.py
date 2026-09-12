from datetime import datetime

import pytest

from loopx.capabilities.periodic_report.cadence import (
    normalize_report_cadence,
    report_cadence_window,
)


def schedule(rule="FREQ=WEEKLY;BYDAY=FR;BYHOUR=18", zone="Asia/Shanghai"):
    return {"schema_version": "periodic_report_schedule_v0",
            "schedule_id": "weekly-report", "rrule": rule, "timezone": zone}


def at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_boundary_is_inclusive_and_repeat_wake_is_stable():
    before = report_cadence_window(schedule(), now=at("2026-09-11T09:59:59Z"))
    due = report_cadence_window(schedule(), now=at("2026-09-11T10:00:00Z"))
    repeated = report_cadence_window(schedule(), now=at("2026-09-11T10:15:00Z"))
    assert before["due_at"] == "2026-09-04T10:00:00Z"
    assert due == repeated
    assert due["start_at"] == "2026-09-04T10:00:00Z"
    assert due["due_at"] == "2026-09-11T10:00:00Z"
    assert due["next_due_at"] == "2026-09-18T10:00:00Z"


def test_daily_and_offset_equivalence():
    rule = schedule("FREQ=DAILY;BYHOUR=9;BYMINUTE=30", "America/New_York")
    result = report_cadence_window(rule, now=at("2026-09-12T09:30:00-04:00"))
    assert result == report_cadence_window(rule, now=at("2026-09-12T13:30:00Z"))
    assert result["due_at"] == "2026-09-12T13:30:00Z"


def test_dst_gap_skips_nonexistent_wall_time():
    rule = schedule("FREQ=DAILY;BYHOUR=2;BYMINUTE=30", "America/New_York")
    result = report_cadence_window(rule, now=at("2026-03-08T08:00:00Z"))
    assert result["due_at"] == "2026-03-07T07:30:00Z"
    assert result["next_due_at"] == "2026-03-09T06:30:00Z"


def test_dst_fold_is_not_a_second_report():
    rule = schedule("FREQ=DAILY;BYHOUR=1;BYMINUTE=30", "America/New_York")
    first = report_cadence_window(rule, now=at("2026-11-01T05:30:00Z"))
    second = report_cadence_window(rule, now=at("2026-11-01T06:30:00Z"))
    assert first == second
    assert first["due_at"] == "2026-11-01T05:30:00Z"


@pytest.mark.parametrize("rule", [
    "FREQ=HOURLY;BYHOUR=1", "FREQ=WEEKLY;BYHOUR=1",
    "FREQ=WEEKLY;BYDAY=MO,TU;BYHOUR=1", "FREQ=DAILY;BYDAY=MO;BYHOUR=1",
    "FREQ=DAILY;BYHOUR=24", "FREQ=DAILY;BYHOUR=1;BYMINUTE=60",
    "FREQ=DAILY;BYHOUR=1;BYHOUR=2", "FREQ=DAILY;BYHOUR=1;INTERVAL=2",
    "FREQ=DAILY;BYHOUR=1;COUNT=2", "FREQ=DAILY;BYHOUR=1;",
])
def test_unsupported_rules_fail_instead_of_approximating(rule):
    with pytest.raises(ValueError):
        normalize_report_cadence(schedule(rule))


def test_disabled_schedule_and_input_validation():
    assert normalize_report_cadence(None) is None
    assert report_cadence_window(None, now=at("2026-09-11T10:00:00Z")) is None
    with pytest.raises(ValueError, match="timezone"):
        normalize_report_cadence(schedule(zone="Invalid/Zone"))
    with pytest.raises(ValueError, match="offset"):
        report_cadence_window(schedule(), now=datetime(2026, 9, 11))


def test_equivalent_rules_have_one_normalized_identity():
    assert normalize_report_cadence(schedule()) == normalize_report_cadence(
        schedule("FREQ=WEEKLY;BYMINUTE=00;BYHOUR=18;BYDAY=FR;INTERVAL=1"))


def test_schedule_roundtrip_and_scope_precedence():
    from loopx.capabilities.periodic_report.goal_configuration import normalize_configuration
    from loopx.capabilities.periodic_report.machine_defaults import (
        normalize_loopx_machine_defaults,
        resolve_goal_periodic_report_subscription,
    )
    config = {"enabled": True, "profile_preset": "weekly-progress",
              "route_ref": "report-channel", "timezone": "Asia/Shanghai"}
    machine = normalize_loopx_machine_defaults({
        "schema_version": "loopx_machine_configuration_v0",
        "namespaces": {"periodic_report": {
            "schema_version": "periodic_report_machine_defaults_v0",
            **config, "schedule": schedule(),
        }},
    })
    inherited = resolve_goal_periodic_report_subscription({"id": "example"}, machine)
    assert inherited["schedule"] == normalize_report_cadence(schedule())
    assert inherited["source"] == "machine_default"
    goal_config = normalize_configuration(config)
    explicit = resolve_goal_periodic_report_subscription(
        {"id": "example", "control_plane": {"periodic_report": goal_config}}, machine)
    assert explicit["source"] == "goal_override"
    assert "schedule" not in explicit
    assert explicit["effective_revision"] != inherited["effective_revision"]
    assert normalize_configuration({**config, "schedule": schedule()})["schedule"] == inherited["schedule"]
    assert normalize_configuration({**config, "schedule": None}) == goal_config


def test_timezone_conflict_is_not_silently_reinterpreted():
    from loopx.capabilities.periodic_report.goal_configuration import normalize_configuration
    with pytest.raises(ValueError, match="must match"):
        normalize_configuration({"enabled": False, "timezone": "UTC", "schedule": schedule()})


def test_configure_goal_persists_and_clears_schedule(tmp_path):
    import json
    from loopx.configure_goal import configure_goal
    from loopx.chat_goal_configuration_api import _goal_capability_options
    from loopx.capabilities.periodic_report.machine_defaults import resolve_goal_periodic_report_subscription
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"goals": [{"id": "example", "repo": str(tmp_path),
        "state_file": "GOAL.md", "status": "active"}]}))
    config = {"enabled": True, "profile_preset": "weekly-progress",
              "route_ref": "report-channel", "timezone": "Asia/Shanghai", "schedule": schedule()}
    configure_goal(registry_path=registry, goal_id="example",
                   **_goal_capability_options("periodic_report", config), execute=True)
    stored = json.loads(registry.read_text())["goals"][0]
    assert resolve_goal_periodic_report_subscription(stored)["schedule"] == normalize_report_cadence(schedule())
    configure_goal(registry_path=registry, goal_id="example",
                   **_goal_capability_options("periodic_report", {**config, "schedule": None}), execute=True)
    stored = json.loads(registry.read_text())["goals"][0]
    assert "schedule" not in resolve_goal_periodic_report_subscription(stored)
