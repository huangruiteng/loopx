#!/usr/bin/env python3
"""Regression for status/diagnose after consecutive status-neutral runs."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from goal_harness.diagnose import collect_diagnosis  # noqa: E402
from goal_harness.quota import QUOTA_MONITOR_POLL_CLASSIFICATION, build_quota_should_run  # noqa: E402
from goal_harness.status import collect_status  # noqa: E402


GOAL_ID = "neutral-window-connected-delivery"
REAL_CLASSIFICATION = "autonomous_replan_recorded_stable_monitor"
REAL_ACTION = "continue the stable monitor lane without asking the user"
AGENT_TODO = "[P1] Continue the stable monitor lane and write back compact evidence."


def write_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Neutral Window Fixture\n\n"
        "## Agent Todo\n\n"
        f"- [ ] {AGENT_TODO}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "status-neutral-window-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_delivery_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                        },
                        "coordination": {
                            "write_scope": ["docs/**"],
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path


def append_run(root: Path, *, generated_at: str, classification: str, action: str) -> None:
    run_dir = root / "runtime" / "goals" / GOAL_ID / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-{classification}.json"
    markdown_path = run_dir / f"{compact_time}-{classification}.md"
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": classification,
        "recommended_action": action,
        "health_check": "status-neutral-window fixture run",
        "delivery_batch_scale": "single_surface",
        "delivery_outcome": "outcome_progress",
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(f"# {classification}\n", encoding="utf-8")
    with (run_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    **record,
                    "json_path": str(json_path),
                    "markdown_path": str(markdown_path),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def write_runs(root: Path) -> None:
    append_run(
        root,
        generated_at="2026-01-01T00:00:00+00:00",
        classification=REAL_CLASSIFICATION,
        action=REAL_ACTION,
    )
    for index in range(1, 7):
        append_run(
            root,
            generated_at=f"2026-01-01T00:0{index}:00+00:00",
            classification=QUOTA_MONITOR_POLL_CLASSIFICATION,
            action="monitor poll only; no status transition",
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-status-neutral-window-") as tmp:
        root = Path(tmp)
        registry_path = write_registry(root)
        write_runs(root)

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[root / "project"],
            limit=5,
        )
        item = status["attention_queue"]["items"][0]
        assert item["goal_id"] == GOAL_ID, item
        assert item["status"] == REAL_CLASSIFICATION, item
        assert item["waiting_on"] == "codex", item
        assert item["source"] == "latest_run", item
        assert item["recommended_action"] == REAL_ACTION, item
        assert "connect an adapter" not in item["recommended_action"], item

        run_goal = status["run_history"]["goals"][0]
        assert run_goal["latest_status_run"]["classification"] == REAL_CLASSIFICATION, run_goal
        assert len(run_goal["latest_runs"]) == 5, run_goal
        assert {
            run["classification"]
            for run in run_goal["latest_runs"]
        } == {QUOTA_MONITOR_POLL_CLASSIFICATION}, run_goal

        readiness = item["handoff_readiness"]
        assert readiness["post_handoff_latest_run"]["classification"] == REAL_CLASSIFICATION, readiness

        quota = build_quota_should_run(status, goal_id=GOAL_ID)
        assert quota["state"] != "operator_gate", quota
        assert quota["requires_user_action"] is False, quota
        user_todo_summary = quota.get("user_todo_summary") if isinstance(quota.get("user_todo_summary"), dict) else {}
        assert user_todo_summary.get("open_count", 0) == 0, quota
        assert quota["status"] == REAL_CLASSIFICATION, quota
        assert "connect an adapter" not in quota["recommended_action"], quota
        assert (
            quota["handoff_readiness"]["post_handoff_latest_run"]["classification"]
            == REAL_CLASSIFICATION
        ), quota

        diagnosis = collect_diagnosis(
            registry_path=registry_path,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[root / "project"],
            limit=5,
            goal_id=GOAL_ID,
        )
        selected = diagnosis["selected"]
        assert selected["status"] == REAL_CLASSIFICATION, selected
        assert selected["waiting_on"] == "codex", selected
        assert selected["machine_signal"] in {
            "agent_work_attention",
            "no_immediate_agent_delivery_signal",
        }, selected
        assert selected["todo_evidence"]["user_open_count"] == 0, selected

    print("status-neutral-run-window-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
