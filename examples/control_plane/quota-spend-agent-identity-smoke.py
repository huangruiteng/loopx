#!/usr/bin/env python3
"""Smoke-test quota agent identity on registered multi-agent goals."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "control_plane" / "quota_plan_fixtures.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.interaction_contract import interaction_next_cli_actions  # noqa: E402
from loopx.control_plane.quota.slot_accounting import (  # noqa: E402
    _latest_unspent_accountable_delivery_run,
)
from loopx.quota import build_quota_monitor_poll_event, build_quota_slot_spend_event  # noqa: E402


def load_quota_plan_fixture() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quota_plan_smoke_fixture", FIXTURE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_quota(root: Path, registry_path: Path, runtime: Path, *args: str) -> tuple[dict, int]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "quota",
            *args,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.stdout, result.stderr
    return json.loads(result.stdout), result.returncode


def assert_monitor_poll_event_carries_agent_id(agent_id: str) -> None:
    event = build_quota_monitor_poll_event(
        {
            "goal_id": "scoped-monitor-goal",
            "should_run": True,
            "effective_action": "monitor_quiet_skip",
            "recommended_action": "stay quiet until material transition",
            "reason": "unchanged monitor target",
            "heartbeat_recommendation": {
                "recommended_mode": "monitor_quiet_until_material_transition",
                "reason": "unchanged monitor target",
            },
            "agent_identity": {
                "agent_id": agent_id,
                "registered": True,
                "agent_model": "peer_v1",
                "registered_agents": ["codex-main-control", agent_id],
            },
        },
        source="heartbeat",
    )

    assert event["agent_id"] == agent_id, event
    assert event["monitor_event"]["agent_id"] == agent_id, event
    target = event["monitor_target"]
    assert target["schema_version"] == "quota_monitor_target_v0", target
    assert target["target_id"] == event["monitor_event"]["monitor_target"]["target_id"], event
    assert target["agent_id"] == agent_id, target
    assert target["effective_action"] == "monitor_quiet_skip", target


def assert_monitor_poll_next_cli_action_preserves_agent_id(agent_id: str) -> None:
    actions = interaction_next_cli_actions(
        {
            "goal_id": "scoped-monitor-goal",
            "agent_identity": {
                "agent_id": agent_id,
            },
        },
        mode="monitor_quiet_skip",
    )

    assert actions == [
        f"loopx quota monitor-poll --goal-id scoped-monitor-goal --agent-id {agent_id} --execute",
        f"loopx --format json quota should-run --goal-id scoped-monitor-goal --agent-id {agent_id}",
    ], actions


def assert_delivery_completion_spend_preserves_requested_agent_id(agent_id: str) -> None:
    before = {
        "goal_id": "delivery-completion-goal",
        "should_run": False,
        "normal_delivery_allowed": False,
        "recovery_delivery_allowed": False,
        "effective_action": "monitor_quiet_skip",
        "self_repair_allowed": False,
        "capability_repair_allowed": False,
        "workspace_repair_allowed": False,
        "state": "eligible",
        "safe_bypass_allowed": False,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "spent_slots": 0,
            "allowed_slots": 1440,
        },
    }
    after = {**before, "quota": {**before["quota"], "spent_slots": 1}}
    preview = {
        "ok": True,
        "mode": "spend-slot",
        "dry_run": True,
        "goal_id": "delivery-completion-goal",
        "slots": 1,
        "agent_id": agent_id,
        "before": before,
        "after": after,
        "delivery_completion_spend": True,
        "delivery_run_generated_at": "2026-01-01T00:00:00+00:00",
        "delivery_run_classification": "validated_delivery_fixture",
    }
    event = build_quota_slot_spend_event(preview, source="heartbeat")

    assert event["agent_id"] == agent_id, event
    assert event["quota_event"]["agent_id"] == agent_id, event
    assert event["quota_event"]["delivery_run_classification"] == "validated_delivery_fixture", event
    assert "validated delivery" in event["health_check"], event


def assert_quota_neutral_events_do_not_hide_same_agent_delivery(agent_id: str) -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-quota-spend-neutral-events-") as tmp:
        runtime = Path(tmp)
        goal_id = "neutral-events-goal"
        index_path = runtime / "goals" / goal_id / "runs" / "index.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        delivery = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "classification": "validated_delivery_fixture",
            "delivery_outcome": "outcome_progress",
            "agent_id": agent_id,
        }
        neutral_runs = [
            delivery,
            {
                "generated_at": "2026-01-01T00:01:00+00:00",
                "classification": "quota_monitor_poll",
                "delivery_outcome": "surface_only",
                "material_change": False,
                "agent_id": agent_id,
            },
            {
                "generated_at": "2026-01-01T00:02:00+00:00",
                "classification": "quota_scheduler_ack",
                "agent_id": agent_id,
            },
        ]
        index_path.write_text(
            "".join(json.dumps(row) + "\n" for row in neutral_runs),
            encoding="utf-8",
        )
        selected = _latest_unspent_accountable_delivery_run(
            runtime, goal_id, agent_id=agent_id
        )
        assert selected == delivery, selected

        material_monitor = {
            "generated_at": "2026-01-01T00:03:00+00:00",
            "classification": "quota_monitor_poll",
            "delivery_outcome": "outcome_progress",
            "material_change": True,
            "agent_id": agent_id,
        }
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(material_monitor) + "\n")
        selected = _latest_unspent_accountable_delivery_run(
            runtime, goal_id, agent_id=agent_id
        )
        assert selected == material_monitor, selected

        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "generated_at": "2026-01-01T00:04:00+00:00",
                        "classification": "quota_slot_spent",
                        "agent_id": agent_id,
                    }
                )
                + "\n"
            )
        assert (
            _latest_unspent_accountable_delivery_run(
                runtime, goal_id, agent_id=agent_id
            )
            is None
        )


def main() -> int:
    fixture = load_quota_plan_fixture()
    agent_id = fixture.SCOPED_AGENT_ID

    assert_monitor_poll_event_carries_agent_id(agent_id)
    assert_monitor_poll_next_cli_action_preserves_agent_id(agent_id)
    assert_delivery_completion_spend_preserves_requested_agent_id(agent_id)
    assert_quota_neutral_events_do_not_hide_same_agent_delivery(agent_id)

    with tempfile.TemporaryDirectory(prefix="loopx-quota-spend-agent-identity-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        index_path = runtime / "goals" / "near-limit-half" / "runs" / "index.jsonl"
        registry_before = registry_path.read_text(encoding="utf-8")
        index_before = index_path.read_text(encoding="utf-8")

        unscoped_payload, unscoped_code = run_quota(
            root,
            registry_path,
            runtime,
            "spend-slot",
            "--goal-id",
            "near-limit-half",
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
        )
        before = unscoped_payload["before"]
        assert unscoped_code == 1, unscoped_payload
        assert unscoped_payload["ok"] is False, unscoped_payload
        assert unscoped_payload["dry_run"] is True, unscoped_payload
        assert unscoped_payload["appended"] is False, unscoped_payload
        assert unscoped_payload["registry_mutated"] is False, unscoped_payload
        assert unscoped_payload["agent_id"] is None, unscoped_payload
        assert before["effective_action"] == "automation_prompt_upgrade_required", unscoped_payload
        assert before["should_run"] is False, unscoped_payload
        assert registry_path.read_text(encoding="utf-8") == registry_before
        assert index_path.read_text(encoding="utf-8") == index_before

        scoped_payload, scoped_code = run_quota(
            root,
            registry_path,
            runtime,
            "spend-slot",
            "--goal-id",
            "near-limit-half",
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--agent-id",
            agent_id,
            "--scan-path",
            str(project),
        )
        assert scoped_code == 0, scoped_payload
        assert scoped_payload["ok"] is True, scoped_payload
        assert scoped_payload["appended"] is True, scoped_payload
        assert scoped_payload["agent_id"] == agent_id, scoped_payload
        assert scoped_payload["before"] == scoped_payload["quota_event"]["before"], scoped_payload
        assert scoped_payload["after"] == scoped_payload["quota_event"]["after"], scoped_payload
        assert scoped_payload["after"]["spent_slots"] == scoped_payload["before"]["spent_slots"] + 1, scoped_payload
        assert "quota" not in scoped_payload["before"], scoped_payload

    print("quota-spend-agent-identity-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
