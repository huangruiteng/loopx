#!/usr/bin/env python3
"""Smoke-test active-state Next Action vs Todo projection consistency."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from goal_harness.state_projection import state_projection_gap_warning  # noqa: E402
from goal_harness.state_refresh import refresh_state_run, render_state_refresh_markdown  # noqa: E402


GOAL_ID = "state-projection-gap-fixture"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_registry(root: Path, state_text: str) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = Path(".codex/goals") / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    (project / state_file).parent.mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(state_text, encoding="utf-8")
    registry_path = project / ".goal-harness" / "registry.json"
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "projection-fixture",
                    "status": "active",
                    "repo": str(project),
                    "state_file": str(state_file),
                    "adapter": {"kind": "harness_self_improvement", "status": "connected"},
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ],
        },
    )
    return registry_path, runtime


def executable_gap_state() -> str:
    return (
        "---\n"
        "status: active\n"
        "updated_at: 2026-06-16T00:00:00+00:00\n"
        "---\n\n"
        "# Projection Gap Fixture\n\n"
        "## Agent Todo\n\n"
        "- [x] Finish the previous bounded implementation slice.\n\n"
        "## Next Action\n\n"
        "- Run the trace reducer backfill and validate the benchmark compact output.\n"
    )


def test_projection_gap_warning() -> dict:
    gap = state_projection_gap_warning(executable_gap_state())
    assert gap is not None, gap
    assert gap["kind"] == "state_projection_gap", gap
    assert gap["requires_todo_expansion"] is True, gap
    assert gap["agent_open_count"] == 0, gap
    assert gap["user_open_count"] == 0, gap
    assert gap["target_roles"] == ["agent"], gap

    user_gap = state_projection_gap_warning(
        "## Next Action\n\n- Wait for owner approval before uploading anything.\n"
    )
    assert user_gap is not None, user_gap
    assert user_gap["target_roles"] == ["user"], user_gap

    no_gap = state_projection_gap_warning(
        "## Agent Todo\n\n"
        "- [ ] Run the trace reducer backfill.\n\n"
        "## Next Action\n\n"
        "- Run the trace reducer backfill.\n"
    )
    assert no_gap is None, no_gap

    technical_gate_no_gap = state_projection_gap_warning(
        "## Agent Todo\n\n"
        "- [ ] Advance ALE split-control provider/task-data readiness.\n\n"
        "## Next Action\n\n"
        "- Agent: choose exactly one compact no-upload next gate among "
        "baked-task-input scan, task-material readiness, or remote Docker "
        "capacity proof. Keep credentials local; avoid submit and leaderboard "
        "paths.\n"
    )
    assert technical_gate_no_gap is None, technical_gate_no_gap
    return gap


def test_refresh_state_warns() -> None:
    with tempfile.TemporaryDirectory(prefix="state-projection-gap-refresh-") as tmp:
        registry_path, _runtime = write_registry(Path(tmp), executable_gap_state())
        payload = refresh_state_run(
            registry_path=registry_path,
            runtime_root_override=None,
            goal_id=GOAL_ID,
            project=None,
            state_file=None,
            classification="state_refreshed",
            recommended_action=None,
            dry_run=True,
            sync_global=False,
        )
        gap = payload.get("state_projection_gap")
        assert isinstance(gap, dict), payload
        assert gap["target_roles"] == ["agent"], payload
        markdown = render_state_refresh_markdown(payload)
        assert "state_projection_gap" in markdown, markdown
        assert "requires_todo_expansion=True" in markdown, markdown


def test_quota_routes_gap_to_projection_repair(gap: dict) -> None:
    status_payload = {
        "ok": True,
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected",
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [
                        {
                            "generated_at": "2026-06-16T00:00:00+00:00",
                            "classification": "state_refreshed",
                            "recommended_action": (
                                "Run the trace reducer backfill and validate the benchmark compact output."
                            ),
                        }
                    ],
                }
            ]
        },
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "state_refreshed",
                    "waiting_on": "codex",
                    "severity": "action",
                    "source": "latest_run",
                    "recommended_action": (
                        "Run the trace reducer backfill and validate the benchmark compact output."
                    ),
                    "quota": {
                        "compute": 1.0,
                        "slot_minutes": 1,
                        "allowed_slots": 1440,
                        "spent_slots": 0,
                        "state": "eligible",
                        "reason": "eligible fixture",
                    },
                    "project_asset": {
                        "owner": "codex",
                        "next_action": (
                            "Run the trace reducer backfill and validate the benchmark compact output."
                        ),
                        "stop_condition": "stop on fixture boundary",
                        "state_projection_gap": gap,
                        "quota": {
                            "compute": 1.0,
                            "slot_minutes": 1,
                            "allowed_slots": 1440,
                            "spent_slots": 0,
                            "state": "eligible",
                            "reason": "eligible fixture",
                        },
                    },
                    "state_projection_gap": gap,
                }
            ]
        },
    }
    decision = build_quota_should_run(status_payload, goal_id=GOAL_ID)
    assert decision["should_run"] is True, decision
    assert decision["normal_delivery_allowed"] is False, decision
    assert decision["self_repair_allowed"] is True, decision
    assert decision["effective_action"] == "state_projection_gap_repair", decision
    assert decision["heartbeat_recommendation"]["recommended_mode"] == (
        "repair_state_projection_gap"
    ), decision
    assert decision["execution_obligation"]["kind"] == "state_projection_gap_repair", decision
    assert decision["execution_obligation"]["delivery_allowed"] is False, decision
    markdown = render_quota_should_run_markdown(decision)
    assert "state_projection_gap" in markdown, markdown
    assert "effective_action: `state_projection_gap_repair`" in markdown, markdown


def main() -> int:
    gap = test_projection_gap_warning()
    test_refresh_state_warns()
    test_quota_routes_gap_to_projection_repair(gap)
    print("state-projection-gap-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
