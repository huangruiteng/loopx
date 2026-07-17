#!/usr/bin/env python3
"""Smoke-test read-only duplicate run-index inspection."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_index_fixture(root: Path, goal_id: str, duplicate_kind: str) -> None:
    runs_dir = root / "runtime" / "goals" / goal_id / "runs"
    runs_dir.mkdir(parents=True)
    json_path = runs_dir / "run.json"
    markdown_path = runs_dir / "run.md"
    json_path.write_text('{"ok": true}\n', encoding="utf-8")
    markdown_path.write_text("# Run\n", encoding="utf-8")
    base = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": goal_id,
        "classification": "state_refreshed",
        "recommended_action": "inspect public-safe duplicate fixture",
        "health_check": "state_file 1/1; registry_goal 1/1; authority_sources 0",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if duplicate_kind == "reward_overlay":
        rows = [
            base,
            {
                **base,
                "human_reward": {
                    "recorded_at": "2026-01-01T00:00:01+00:00",
                    "decision": "continue",
                    "reward": "positive",
                    "reason_summary": "operator accepted public-safe fixture",
                    "follow_up": "continue",
                },
            },
        ]
    elif duplicate_kind == "projected_reward_overlay":
        projected = {
            key: base[key]
            for key in (
                "generated_at",
                "goal_id",
                "classification",
                "recommended_action",
                "health_check",
                "json_path",
                "markdown_path",
            )
        }
        rows = [
            {
                **base,
                "agent_id": "fixture-agent",
                "progress_scope": "agent_lane",
                "delivery_batch_scale": "multi_surface",
                "delivery_outcome": "outcome_progress",
            },
            {
                **projected,
                "human_reward": {
                    "recorded_at": "2026-01-01T00:00:01+00:00",
                    "decision": "continue",
                    "reward": "positive",
                },
            },
            {
                **projected,
                "human_reward": {
                    "recorded_at": "2026-01-01T00:00:02+00:00",
                    "decision": "refine",
                    "reward": "mixed",
                },
            },
        ]
    elif duplicate_kind == "conflicting_projected_reward_overlay":
        rows = [
            base,
            {
                **base,
                "recommended_action": "conflicting compact projection must stay visible",
                "human_reward": {
                    "recorded_at": "2026-01-01T00:00:01+00:00",
                    "decision": "continue",
                    "reward": "positive",
                },
            },
        ]
    elif duplicate_kind == "plain_duplicate":
        rows = [base, dict(base)]
    elif duplicate_kind == "structured_artifact_collision":
        rows = [
            {
                **base,
                "classification": "benchmark_run_v0",
                "health_check": "benchmark_run_v0 compact event public-safe",
                "benchmark_run": {
                    "schema_version": "benchmark_run_v0",
                    "mode": "codex_loopx",
                    "official_task_score": {"kind": "fixture"},
                },
            },
            {
                **base,
                "classification": "benchmark_run_v0",
                "health_check": "state_file 1/1; registry_goal 1/1; authority_sources 0",
            },
        ]
    elif duplicate_kind == "structured_artifact_bundle":
        rows = [
            {
                **base,
                "classification": "benchmark_run_v0",
                "health_check": "benchmark_run_v0 compact event public-safe",
                "benchmark_run": {
                    "schema_version": "benchmark_run_v0",
                    "mode": "codex_loopx",
                    "job_name": "bundle_case_a",
                    "official_task_score": {"kind": "fixture", "value": 0.0},
                },
            },
            {
                **base,
                "classification": "benchmark_run_v0",
                "health_check": "benchmark_run_v0 compact event public-safe",
                "benchmark_run": {
                    "schema_version": "benchmark_run_v0",
                    "mode": "codex_loopx",
                    "job_name": "bundle_case_b",
                    "official_task_score": {"kind": "fixture", "value": 1.0},
                },
            },
        ]
    elif duplicate_kind == "artifact_identity_collision":
        rows = [
            {
                **base,
                "classification": "quota_monitor_poll",
                "todo_id": "todo_fixture_a",
                "target_key": "github-pr-101",
                "health_check": "due monitor observation unchanged",
            },
            {
                **base,
                "classification": "quota_monitor_poll",
                "todo_id": "todo_fixture_b",
                "target_key": "github-pr-102",
                "health_check": "due monitor observation unchanged",
            },
        ]
    else:
        raise ValueError(duplicate_kind)
    (runs_dir / "index.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_registry(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir()
    goals = []
    for goal_id, kind in (
        ("reward-overlay-goal", "reward_overlay"),
        ("projected-reward-overlay-goal", "projected_reward_overlay"),
        (
            "conflicting-projected-reward-overlay-goal",
            "conflicting_projected_reward_overlay",
        ),
        ("plain-duplicate-goal", "plain_duplicate"),
        ("structured-artifact-goal", "structured_artifact_collision"),
        ("structured-bundle-goal", "structured_artifact_bundle"),
        ("artifact-collision-goal", "artifact_identity_collision"),
    ):
        state_file = project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            "---\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n", encoding="utf-8"
        )
        write_index_fixture(root, goal_id, kind)
        goals.append(
            {
                "id": goal_id,
                "domain": "duplicate-inspection-fixture",
                "status": "active-read-only",
                "repo": str(project),
                "state_file": str(state_file.relative_to(project)),
                "adapter": {"kind": "fixture", "status": "connected-read-only"},
            }
        )
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(root / "runtime"),
                "goals": goals,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path


def run_cli(registry_path: Path, *args: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        registry_path = write_registry(Path(raw_tmp))
        payload = run_cli(
            registry_path, "history", "inspect-index-duplicates", "--limit", "10"
        )
        assert payload["ok"] is True, payload
        assert payload["duplicate_group_count"] == 7, payload
        assert payload["duplicate_row_count"] == 8, payload
        by_goal = {group["goal_id"]: group for group in payload["groups"]}
        assert by_goal["reward-overlay-goal"]["duplicate_kind"] == "reward_overlay", (
            payload
        )
        assert by_goal["reward-overlay-goal"]["severity"] == "info", payload
        assert (
            by_goal["projected-reward-overlay-goal"]["duplicate_kind"]
            == "reward_overlay"
        ), payload
        assert by_goal["projected-reward-overlay-goal"]["severity"] == "info", payload
        assert by_goal["projected-reward-overlay-goal"]["reward_overlay_rows"] == 2, (
            payload
        )
        assert (
            by_goal["conflicting-projected-reward-overlay-goal"]["duplicate_kind"]
            == "artifact_identity_collision"
        ), payload
        assert (
            by_goal["conflicting-projected-reward-overlay-goal"]["severity"]
            == "warning"
        ), payload
        assert by_goal["plain-duplicate-goal"]["duplicate_kind"] == "plain_duplicate", (
            payload
        )
        assert by_goal["plain-duplicate-goal"]["severity"] == "warning", payload
        assert (
            by_goal["structured-artifact-goal"]["duplicate_kind"]
            == "artifact_identity_collision"
        ), payload
        assert (
            by_goal["structured-bundle-goal"]["duplicate_kind"]
            == "structured_artifact_bundle"
        ), payload
        assert by_goal["structured-bundle-goal"]["severity"] == "info", payload
        assert (
            by_goal["artifact-collision-goal"]["duplicate_kind"]
            == "artifact_identity_collision"
        ), payload
        assert by_goal["artifact-collision-goal"]["classifications"] == [
            "quota_monitor_poll"
        ], payload
        assert payload["groups"][0]["severity"] == "warning", payload

        repair_preview = run_cli(
            registry_path, "history", "repair-index-duplicates", "--limit", "10"
        )
        assert repair_preview["ok"] is True, repair_preview
        assert repair_preview["dry_run"] is True, repair_preview
        assert repair_preview["repaired"] is False, repair_preview
        assert repair_preview["removed_row_count"] == 2, repair_preview
        assert repair_preview["preserved_reward_overlay_rows"] == 3, repair_preview
        assert repair_preview["preserved_structured_artifact_bundle_rows"] == 1, (
            repair_preview
        )
        assert repair_preview["unrepaired_group_count"] == 2, repair_preview
        repair_actions = {
            group["goal_id"]: group["action"] for group in repair_preview["groups"]
        }
        assert repair_actions["reward-overlay-goal"] == "preserve_reward_overlay", (
            repair_preview
        )
        assert (
            repair_actions["projected-reward-overlay-goal"] == "preserve_reward_overlay"
        ), repair_preview
        assert (
            repair_actions["conflicting-projected-reward-overlay-goal"]
            == "blocked_artifact_identity_collision"
        ), repair_preview
        assert repair_actions["plain-duplicate-goal"] == "drop_plain_duplicate_rows", (
            repair_preview
        )
        assert (
            repair_actions["structured-artifact-goal"] == "keep_structured_artifact_row"
        ), repair_preview
        assert (
            repair_actions["structured-bundle-goal"]
            == "preserve_structured_artifact_bundle"
        ), repair_preview
        assert (
            repair_actions["artifact-collision-goal"]
            == "blocked_artifact_identity_collision"
        ), repair_preview

        repair_execute = run_cli(
            registry_path,
            "history",
            "repair-index-duplicates",
            "--limit",
            "10",
            "--execute",
        )
        assert repair_execute["ok"] is True, repair_execute
        assert repair_execute["dry_run"] is False, repair_execute
        assert repair_execute["repaired"] is True, repair_execute
        assert repair_execute["removed_row_count"] == 2, repair_execute

        after_repair = run_cli(
            registry_path, "history", "inspect-index-duplicates", "--limit", "10"
        )
        assert after_repair["ok"] is True, after_repair
        assert after_repair["duplicate_group_count"] == 5, after_repair
        after_by_goal = {group["goal_id"]: group for group in after_repair["groups"]}
        assert "plain-duplicate-goal" not in after_by_goal, after_repair
        assert "structured-artifact-goal" not in after_by_goal, after_repair
        assert (
            after_by_goal["reward-overlay-goal"]["duplicate_kind"] == "reward_overlay"
        ), after_repair
        assert (
            after_by_goal["projected-reward-overlay-goal"]["duplicate_kind"]
            == "reward_overlay"
        ), after_repair
        assert (
            after_by_goal["conflicting-projected-reward-overlay-goal"]["duplicate_kind"]
            == "artifact_identity_collision"
        ), after_repair
        assert (
            after_by_goal["structured-bundle-goal"]["duplicate_kind"]
            == "structured_artifact_bundle"
        ), after_repair
        assert (
            after_by_goal["artifact-collision-goal"]["duplicate_kind"]
            == "artifact_identity_collision"
        ), after_repair

        filtered = run_cli(
            registry_path,
            "history",
            "inspect-index-duplicates",
            "--goal-id",
            "reward-overlay-goal",
        )
        assert filtered["duplicate_group_count"] == 1, filtered
        assert filtered["groups"][0]["duplicate_kind"] == "reward_overlay", filtered

        rebuild_preview = run_cli(
            registry_path,
            "history",
            "rebuild-index-collisions",
            "--goal-id",
            "artifact-collision-goal",
        )
        assert rebuild_preview["dry_run"] is True, rebuild_preview
        assert rebuild_preview["collision_group_count"] == 1, rebuild_preview
        assert rebuild_preview["total_collision_group_count"] == 1, rebuild_preview
        assert rebuild_preview["truncated"] is False, rebuild_preview
        assert rebuild_preview["review_required"] is True, rebuild_preview
        assert rebuild_preview["destructive_row_deletion"] is False, rebuild_preview
        review_plan = rebuild_preview["review_plan"]
        assert review_plan["destructive_row_deletion"] is False, review_plan
        assert review_plan["truncated"] is False, review_plan
        assert len(review_plan["groups"][0]["rows"]) == 2, review_plan
        assert {
            row["event_identity"]["todo_id"]
            for row in review_plan["groups"][0]["rows"]
        } == {"todo_fixture_a", "todo_fixture_b"}, review_plan
        plan_path = Path(raw_tmp) / "reviewed-collision-plan.json"
        plan_path.write_text(
            json.dumps(review_plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        rebuild_execute = run_cli(
            registry_path,
            "history",
            "rebuild-index-collisions",
            "--goal-id",
            "artifact-collision-goal",
            "--review-plan-json",
            str(plan_path),
            "--execute",
        )
        assert rebuild_execute["rebuilt"] is True, rebuild_execute
        assert rebuild_execute["destructive_row_deletion"] is False, rebuild_execute
        rebuilt_index = rebuild_execute["rebuilt_indexes"][0]
        assert rebuilt_index["preserved_row_count"] == 2, rebuild_execute
        assert Path(rebuilt_index["backup_path"]).exists(), rebuild_execute
        assert all(Path(path).exists() for path in rebuilt_index["recovery_paths"]), (
            rebuild_execute
        )

        after_rebuild = run_cli(
            registry_path,
            "history",
            "inspect-index-duplicates",
            "--goal-id",
            "artifact-collision-goal",
        )
        assert after_rebuild["duplicate_group_count"] == 0, after_rebuild
        rebuilt_rows = [
            json.loads(line)
            for line in (
                Path(rebuilt_index["index_path"]).read_text(encoding="utf-8").splitlines()
            )
            if line.strip()
        ]
        assert len(rebuilt_rows) == 2, rebuilt_rows
        assert {row["classification"] for row in rebuilt_rows} == {
            "quota_monitor_poll"
        }, rebuilt_rows
        assert {row["todo_id"] for row in rebuilt_rows} == {
            "todo_fixture_a",
            "todo_fixture_b",
        }, rebuilt_rows
        assert {row["target_key"] for row in rebuilt_rows} == {
            "github-pr-101",
            "github-pr-102",
        }, rebuilt_rows
        assert len({row["json_path"] for row in rebuilt_rows}) == 2, rebuilt_rows
        assert all(row["artifact_rebuild"]["ambiguous_legacy_artifact_claimed"] is False for row in rebuilt_rows)

    print("history-index-duplicate-inspection-smoke ok")


if __name__ == "__main__":
    main()
