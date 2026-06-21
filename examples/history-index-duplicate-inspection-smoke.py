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
    elif duplicate_kind == "artifact_identity_collision":
        rows = [
            {**base, "classification": "benchmark_run_v0", "health_check": "benchmark_run_v0 compact event public-safe"},
            {**base, "classification": "state_refreshed"},
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
        ("plain-duplicate-goal", "plain_duplicate"),
        ("structured-artifact-goal", "structured_artifact_collision"),
        ("artifact-collision-goal", "artifact_identity_collision"),
    ):
        state_file = project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("---\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n", encoding="utf-8")
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
        payload = run_cli(registry_path, "history", "inspect-index-duplicates", "--limit", "10")
        assert payload["ok"] is True, payload
        assert payload["duplicate_group_count"] == 4, payload
        assert payload["duplicate_row_count"] == 4, payload
        by_goal = {group["goal_id"]: group for group in payload["groups"]}
        assert by_goal["reward-overlay-goal"]["duplicate_kind"] == "reward_overlay", payload
        assert by_goal["reward-overlay-goal"]["severity"] == "info", payload
        assert by_goal["plain-duplicate-goal"]["duplicate_kind"] == "plain_duplicate", payload
        assert by_goal["plain-duplicate-goal"]["severity"] == "warning", payload
        assert by_goal["structured-artifact-goal"]["duplicate_kind"] == "artifact_identity_collision", payload
        assert by_goal["artifact-collision-goal"]["duplicate_kind"] == "artifact_identity_collision", payload
        assert by_goal["artifact-collision-goal"]["classifications"] == ["benchmark_run_v0", "state_refreshed"], payload
        assert payload["groups"][0]["severity"] == "warning", payload

        repair_preview = run_cli(registry_path, "history", "repair-index-duplicates", "--limit", "10")
        assert repair_preview["ok"] is True, repair_preview
        assert repair_preview["dry_run"] is True, repair_preview
        assert repair_preview["repaired"] is False, repair_preview
        assert repair_preview["removed_row_count"] == 2, repair_preview
        assert repair_preview["preserved_reward_overlay_rows"] == 1, repair_preview
        assert repair_preview["unrepaired_group_count"] == 1, repair_preview
        repair_actions = {group["goal_id"]: group["action"] for group in repair_preview["groups"]}
        assert repair_actions["reward-overlay-goal"] == "preserve_reward_overlay", repair_preview
        assert repair_actions["plain-duplicate-goal"] == "drop_plain_duplicate_rows", repair_preview
        assert repair_actions["structured-artifact-goal"] == "keep_structured_artifact_row", repair_preview
        assert repair_actions["artifact-collision-goal"] == "blocked_artifact_identity_collision", repair_preview

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

        after_repair = run_cli(registry_path, "history", "inspect-index-duplicates", "--limit", "10")
        assert after_repair["ok"] is True, after_repair
        assert after_repair["duplicate_group_count"] == 2, after_repair
        after_by_goal = {group["goal_id"]: group for group in after_repair["groups"]}
        assert "plain-duplicate-goal" not in after_by_goal, after_repair
        assert "structured-artifact-goal" not in after_by_goal, after_repair
        assert after_by_goal["reward-overlay-goal"]["duplicate_kind"] == "reward_overlay", after_repair
        assert after_by_goal["artifact-collision-goal"]["duplicate_kind"] == "artifact_identity_collision", after_repair

        filtered = run_cli(
            registry_path,
            "history",
            "inspect-index-duplicates",
            "--goal-id",
            "reward-overlay-goal",
        )
        assert filtered["duplicate_group_count"] == 1, filtered
        assert filtered["groups"][0]["duplicate_kind"] == "reward_overlay", filtered

    print("history-index-duplicate-inspection-smoke ok")


if __name__ == "__main__":
    main()
