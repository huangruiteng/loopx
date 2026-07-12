from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from loopx.control_plane.runtime.trajectory_hygiene import (
    build_trajectory_hygiene_summary,
    compact_history_event_channel,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _runs() -> list[dict[str, object]]:
    return [
        {
            "classification": "quota_monitor_poll",
            "recommended_action": "wait for evidence",
            "material_change": False,
        },
        {
            "classification": "quota_slot_spent",
            "delivery_outcome": "surface_only",
        },
        {
            "classification": "patch_validated",
            "agent_id": "codex-test",
            "recommended_action": "open the reviewed pull request",
            "delivery_outcome": "outcome_progress",
        },
        {
            "classification": "patch_rechecked",
            "agent_id": "codex-test",
            "recommended_action": "open the reviewed pull request",
            "delivery_outcome": "outcome_progress",
        },
        {
            "classification": "owner_feedback",
            "human_reward": {"decision": "continue", "reason_summary": "fixture accepted"},
        },
    ]


def test_trajectory_hygiene_summary_separates_controller_rows() -> None:
    payload = build_trajectory_hygiene_summary(
        {"goal_filter": "fixture", "goal_count": 1, "runs": _runs()}
    )

    assert payload["schema_version"] == "trajectory_hygiene_summary_v0"
    assert payload["channel_counts"] == {
        "controller": 2,
        "human_decision": 1,
        "outcome": 2,
    }
    assert payload["metrics"]["controller_event_ratio"] == 0.4
    assert payload["metrics"]["non_material_event_ratio"] == 0.4
    assert payload["metrics"]["learning_candidate_count"] == 3
    assert payload["metrics"]["learning_action_coverage"] == 0.6667
    assert payload["metrics"]["learning_outcome_coverage"] == 0.6667
    assert payload["metrics"]["decision_anchor_coverage"] == 0.6667
    assert payload["metrics"]["duplicate_learning_action_ratio"] == 0.5
    assert 0 < payload["metrics"]["compact_controller_char_ratio"] < 1
    assert payload["training_boundary"] == {
        "raw_session_read": False,
        "raw_trajectory_read": False,
        "run_artifact_read": False,
        "compact_index_only": True,
        "seed_model_training_eligible": False,
        "reason": (
            "compact history is an audit baseline, not a learning trajectory; "
            "export model-visible task turns separately and link controller events by stable ids"
        ),
    }


def test_trajectory_hygiene_channel_precedence_keeps_human_decisions() -> None:
    assert compact_history_event_channel(
        {"classification": "quota_monitor_poll", "operator_gate": {"decision": "approve"}}
    ) == "human_decision"
    assert compact_history_event_channel({"classification": "state_refreshed"}) == "controller"
    assert compact_history_event_channel(
        {"classification": "implementation", "delivery_outcome": "primary_goal_outcome"}
    ) == "outcome"
    assert compact_history_event_channel(
        {"classification": "blocked_writeback", "delivery_outcome": "outcome_gap"}
    ) == "outcome"


def test_history_trajectory_hygiene_cli_reads_compact_index_only(tmp_path: Path) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    goal_id = "trajectory-hygiene-fixture"
    state_file = project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("---\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n", encoding="utf-8")

    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": goal_id,
                        "domain": "fixture",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": str(state_file.relative_to(project)),
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    runs_dir = runtime / "goals" / goal_id / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "index.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    **run,
                    "goal_id": goal_id,
                    "generated_at": f"2026-01-01T00:00:0{index}+00:00",
                }
            )
            + "\n"
            for index, run in enumerate(_runs())
        ),
        encoding="utf-8",
    )
    # The command must not need or inspect a raw trajectory artifact.
    (runs_dir / "trajectory.json").write_text("not-json-private-fixture", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            "history",
            "trajectory-hygiene",
            "--goal-id",
            goal_id,
            "--limit",
            "10",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["sample"]["compact_history_row_count"] == 5
    assert payload["training_boundary"]["raw_trajectory_read"] is False
    assert payload["training_boundary"]["seed_model_training_eligible"] is False
