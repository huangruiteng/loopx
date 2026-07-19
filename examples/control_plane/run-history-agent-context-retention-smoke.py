#!/usr/bin/env python3
"""Smoke-test per-agent vision/replan context survives latest-run truncation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loopx.control_plane.goals.goal_frontier import latest_agent_vision_from_status_payload
from loopx.control_plane.runtime.run_history import build_run_history
from loopx.history import collect_history


GOAL_ID = "agent-context-retention-goal"
COORDINATION_PEER = "codex-coordination-peer"
PRODUCT_PEER = "codex-product-peer"
TARGET_PEER = "codex-research-peer"


def project_run_history(history: dict, *, display_limit: int = 3) -> dict:
    return build_run_history(
        history,
        latest_run=lambda goal: goal.get("latest_status_run"),
        goal_lifecycle_fields=lambda goal, run: {
            "lifecycle_phase": "active",
            "lifecycle_flags": [],
        },
        subagent_activity_for_goal=lambda goal: None,
        compact_run=lambda run: dict(run),
        quota_status=lambda goal: {},
        display_limit=display_limit,
    )


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
                            "agent_model": "peer_v1",
                            "registered_agents": [
                                COORDINATION_PEER,
                                TARGET_PEER,
                                PRODUCT_PEER,
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
        ("2026-07-06T00:06:00+00:00", COORDINATION_PEER, "latest coordination"),
        ("2026-07-06T00:05:00+00:00", PRODUCT_PEER, "latest product"),
        ("2026-07-06T00:04:00+00:00", COORDINATION_PEER, "second coordination"),
        (
            "2026-07-06T00:03:00+00:00",
            TARGET_PEER,
            "target peer vision",
        ),
        ("2026-07-06T00:02:00+00:00", TARGET_PEER, "older target peer"),
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
            if action == "target peer vision":
                record["agent_vision"] = {
                    "schema_version": "goal_vision_replan_contract_v0",
                    "agent_id": TARGET_PEER,
                    "state": "active",
                    "vision_patch": {
                        "acceptance_summary": (
                            "Keep the research peer's multi-round work runnable."
                        ),
                        "replan_trigger_summary": (
                            "The research peer's vision would otherwise fall out of the "
                            "global run window."
                        ),
                    },
                }
                record["vision_checkpoint"] = {
                    "schema_version": "vision_checkpoint_v0",
                    "agent_id": TARGET_PEER,
                    "required": True,
                    "satisfied": True,
                    "decision": "patched",
                }
            if action == "older target peer":
                record["autonomous_replan_ack"] = {
                    "schema_version": "autonomous_replan_ack_v0",
                    "recorded": True,
                    "source": "fixture",
                    "delta_contract": {
                        "schema_version": "repair_delta_contract_v0",
                        "required": True,
                        "delta_present": True,
                        "delta_kinds": ["runnable_todo_set"],
                        "auto_evidence": [],
                        "accepted_without_delta": False,
                    },
                }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return registry_path, runtime


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-agent-context-retention-") as raw_tmp:
        registry_path, runtime = write_fixture(Path(raw_tmp))
        runs_dir = runtime / "goals" / GOAL_ID / "runs"
        with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "generated_at": "2026-07-06T00:07:00+00:00",
                        "goal_id": GOAL_ID,
                        "classification": "state_refreshed",
                        "agent_id": TARGET_PEER,
                        "recommended_action": "keep peer vision unchanged",
                        "json_path": str(runs_dir / "unchanged-peer-vision.json"),
                        "markdown_path": str(runs_dir / "unchanged-peer-vision.md"),
                        "vision_checkpoint": {
                            "schema_version": "vision_checkpoint_v0",
                            "agent_id": TARGET_PEER,
                            "required": True,
                            "satisfied": True,
                            "decision": "unchanged_with_reason",
                            "unchanged_reason": "The active peer vision still applies.",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        history = collect_history(
            registry_path=registry_path,
            runtime_root=runtime,
            goal_id=GOAL_ID,
            limit=3,
        )
        goal = history["goals"][0]
        latest_runs = goal["latest_runs"]
        assert [run["recommended_action"] for run in latest_runs[:3]] == [
            "keep peer vision unchanged",
            "latest coordination",
            "latest product",
        ], latest_runs
        assert any(
            run.get("agent_id") == TARGET_PEER and run.get("agent_vision")
            for run in latest_runs
        ), latest_runs
        assert any(
            run.get("agent_id") == TARGET_PEER and run.get("autonomous_replan_ack")
            for run in latest_runs
        ), latest_runs
        assert len(latest_runs) == 5, latest_runs
        projected_run_history = project_run_history(history)
        projected_runs = projected_run_history["goals"][0]["latest_runs"]
        assert any(
            run.get("agent_id") == TARGET_PEER and run.get("agent_vision")
            for run in projected_runs
        ), projected_runs
        assert any(
            run.get("agent_id") == TARGET_PEER and run.get("autonomous_replan_ack")
            for run in projected_runs
        ), projected_runs
        assert len(projected_runs) == 5, projected_runs
        vision = latest_agent_vision_from_status_payload(
            {"run_history": projected_run_history},
            goal_id=GOAL_ID,
            agent_id=TARGET_PEER,
        )
        assert vision and vision["agent_id"] == TARGET_PEER, vision
        assert "global run window" in vision["vision_patch"]["replan_trigger_summary"], vision

        zero_budget_history = collect_history(
            registry_path=registry_path,
            runtime_root=runtime,
            goal_id=GOAL_ID,
            limit=0,
        )
        assert zero_budget_history["goals"][0]["latest_runs"] == [], zero_budget_history
        zero_budget_projection = project_run_history(history, display_limit=0)
        assert zero_budget_projection["goals"][0]["latest_runs"] == [], (
            zero_budget_projection
        )
    with tempfile.TemporaryDirectory(prefix="loopx-agent-context-retired-") as raw_tmp:
        registry_path, runtime = write_fixture(Path(raw_tmp))
        runs_dir = runtime / "goals" / GOAL_ID / "runs"
        with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "generated_at": "2026-07-06T00:07:00+00:00",
                        "goal_id": GOAL_ID,
                        "classification": "state_refreshed",
                        "agent_id": TARGET_PEER,
                        "recommended_action": "retire peer vision",
                        "json_path": str(runs_dir / "retired-peer-vision.json"),
                        "markdown_path": str(runs_dir / "retired-peer-vision.md"),
                        "vision_checkpoint": {
                            "schema_version": "vision_checkpoint_v0",
                            "agent_id": TARGET_PEER,
                            "required": True,
                            "satisfied": True,
                            "decision": "retired_or_superseded",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        history = collect_history(
            registry_path=registry_path,
            runtime_root=runtime,
            goal_id=GOAL_ID,
            limit=3,
        )
        latest_runs = history["goals"][0]["latest_runs"]
        assert [run["recommended_action"] for run in latest_runs[:3]] == [
            "retire peer vision",
            "latest coordination",
            "latest product",
        ], latest_runs
        assert not any(
            run.get("agent_id") == TARGET_PEER and run.get("agent_vision")
            for run in latest_runs
        ), latest_runs
        projected_run_history = project_run_history(history)
        projected_runs = projected_run_history["goals"][0]["latest_runs"]
        assert not any(
            run.get("agent_id") == TARGET_PEER and run.get("agent_vision")
            for run in projected_runs
        ), projected_runs
        vision = latest_agent_vision_from_status_payload(
            {"run_history": projected_run_history},
            goal_id=GOAL_ID,
            agent_id=TARGET_PEER,
        )
        assert vision is None, vision
    print("run-history-agent-context-retention-smoke ok")


if __name__ == "__main__":
    main()
