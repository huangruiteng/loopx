#!/usr/bin/env python3
"""Smoke-test per-agent vision/replan context survives latest-run truncation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loopx.control_plane.goals.goal_frontier import latest_agent_vision_from_status_payload
from loopx.history import collect_history


GOAL_ID = "agent-context-retention-goal"
SIDE_AGENT = "codex-side-bypass"


def write_fixture(root: Path) -> tuple[Path, Path]:
    runtime = root / "runtime"
    project = root / "project"
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True)
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": ".local/goals/fixture.md",
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                        "coordination": {
                            "primary_agent": "codex-main-control",
                            "registered_agents": [
                                "codex-main-control",
                                SIDE_AGENT,
                                "codex-product-capability",
                            ],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    runs = [
        ("2026-07-06T00:06:00+00:00", "codex-main-control", "latest main"),
        ("2026-07-06T00:05:00+00:00", "codex-product-capability", "latest product"),
        ("2026-07-06T00:04:00+00:00", "codex-main-control", "second main"),
        (
            "2026-07-06T00:03:00+00:00",
            SIDE_AGENT,
            "side vision",
        ),
        ("2026-07-06T00:02:00+00:00", SIDE_AGENT, "older side"),
    ]
    with (runs_dir / "index.jsonl").open("w", encoding="utf-8") as handle:
        for generated_at, agent_id, action in runs:
            record = {
                "generated_at": generated_at,
                "goal_id": GOAL_ID,
                "classification": "state_refreshed",
                "agent_id": agent_id,
                "recommended_action": action,
                "json_path": str(runs_dir / f"{generated_at}.json"),
                "markdown_path": str(runs_dir / f"{generated_at}.md"),
            }
            if action == "side vision":
                record["agent_vision"] = {
                    "schema_version": "goal_vision_replan_contract_v0",
                    "agent_id": SIDE_AGENT,
                    "state": "active",
                    "vision_patch": {
                        "acceptance_summary": (
                            "Keep side-lane auto-research multi-round work runnable."
                        ),
                        "replan_trigger_summary": (
                            "Side-lane vision would otherwise fall out of the "
                            "global run window."
                        ),
                    },
                }
                record["vision_checkpoint"] = {
                    "schema_version": "vision_checkpoint_v0",
                    "agent_id": SIDE_AGENT,
                    "required": True,
                    "satisfied": True,
                    "decision": "patched",
                }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return registry_path, runtime


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-agent-context-retention-") as raw_tmp:
        registry_path, runtime = write_fixture(Path(raw_tmp))
        history = collect_history(
            registry_path=registry_path,
            runtime_root=runtime,
            goal_id=GOAL_ID,
            limit=3,
        )
        goal = history["goals"][0]
        latest_runs = goal["latest_runs"]
        assert [run["recommended_action"] for run in latest_runs[:3]] == [
            "latest main",
            "latest product",
            "second main",
        ], latest_runs
        assert any(
            run.get("agent_id") == SIDE_AGENT and run.get("agent_vision")
            for run in latest_runs
        ), latest_runs
        vision = latest_agent_vision_from_status_payload(
            {"run_history": {"goals": history["goals"]}},
            goal_id=GOAL_ID,
            agent_id=SIDE_AGENT,
        )
        assert vision and vision["agent_id"] == SIDE_AGENT, vision
        assert "global run window" in vision["vision_patch"]["replan_trigger_summary"], vision
    print("run-history-agent-context-retention-smoke ok")


if __name__ == "__main__":
    main()
