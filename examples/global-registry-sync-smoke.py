#!/usr/bin/env python3
"""Smoke-test global registry sync across multiple local sources."""

from __future__ import annotations

import json
import multiprocessing
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.global_registry import sync_project_registry_to_global  # noqa: E402
from loopx.paths import global_registry_path  # noqa: E402


GOAL_ID = "multi-source-main-control"
OVERRIDE_ACTION = "先完成 owner/SOP 判断并记录结论"


def write_registry(path: Path, *, runtime: Path, repo: Path, override: bool) -> None:
    goal = {
        "id": GOAL_ID,
        "domain": "multi-source-sync",
        "status": "active-read-only",
        "repo": str(repo),
        "state_file": "ACTIVE_GOAL_STATE.md",
        "adapter": {
            "kind": "read_only_project_map_v0",
            "status": "connected-read-only",
        },
        "authority_sources": [],
    }
    if override:
        goal.update(
            {
                "waiting_on": "user_or_controller",
                "attention_status": "owner_sop_review_pending",
                "recommended_action": OVERRIDE_ACTION,
                "operator_question": "是否同意继续？",
                "next_handoff_condition": "owner/SOP decision recorded",
            }
        )
    payload = {
        "schema_version": 1,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "common_runtime_root": str(runtime),
        "goals": [goal],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_goal(global_registry: Path) -> dict:
    payload = json.loads(global_registry.read_text(encoding="utf-8"))
    for goal in payload.get("goals") or []:
        if goal.get("id") == GOAL_ID:
            return goal
    raise AssertionError(f"{GOAL_ID} not found in global registry")


def assert_no_write_temps(global_registry: Path) -> None:
    leftovers = sorted(global_registry.parent.glob(f".{global_registry.name}.*.tmp"))
    assert not leftovers, [str(path) for path in leftovers]


def sync_worker(registry_path: str) -> None:
    sync_project_registry_to_global(
        registry_path=Path(registry_path),
        runtime_root_override=None,
        dry_run=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-global-sync-smoke-") as tmp:
        root = Path(tmp)
        runtime = root / "runtime"
        global_registry = global_registry_path(runtime)
        controller_repo = root / "controller"
        project_repo = root / "project"
        controller_repo.mkdir()
        project_repo.mkdir()
        (controller_repo / "ACTIVE_GOAL_STATE.md").write_text("# Controller state\n", encoding="utf-8")
        (project_repo / "ACTIVE_GOAL_STATE.md").write_text("# Project state\n", encoding="utf-8")

        controller_registry = controller_repo / ".loopx" / "registry.json"
        project_registry = project_repo / ".loopx" / "registry.json"
        write_registry(controller_registry, runtime=runtime, repo=controller_repo, override=True)
        write_registry(project_registry, runtime=runtime, repo=project_repo, override=False)

        sync_project_registry_to_global(
            registry_path=controller_registry,
            runtime_root_override=None,
            dry_run=False,
        )
        sync_project_registry_to_global(
            registry_path=project_registry,
            runtime_root_override=None,
            dry_run=False,
        )

        assert_no_write_temps(global_registry)
        goal = find_goal(global_registry)
        assert goal["waiting_on"] == "user_or_controller", goal
        assert goal["attention_status"] == "owner_sop_review_pending", goal
        assert goal["recommended_action"] == OVERRIDE_ACTION, goal
        assert goal["operator_question"] == "是否同意继续？", goal
        assert goal["next_handoff_condition"] == "owner/SOP decision recorded", goal
        assert goal["source_registry"] == str(project_registry.resolve()), goal

        sync_project_registry_to_global(
            registry_path=project_registry,
            runtime_root_override=None,
            dry_run=False,
        )
        assert_no_write_temps(global_registry)
        goal = find_goal(global_registry)
        assert "waiting_on" not in goal, goal
        assert "attention_status" not in goal, goal
        assert "recommended_action" not in goal, goal
        assert "operator_question" not in goal, goal
        assert "next_handoff_condition" not in goal, goal
        assert goal["source_registry"] == str(project_registry.resolve()), goal

        processes = [
            multiprocessing.Process(target=sync_worker, args=(str(controller_registry),)),
            multiprocessing.Process(target=sync_worker, args=(str(project_registry),)),
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0, process.exitcode
        assert_no_write_temps(global_registry)
        find_goal(global_registry)

    print("global-registry-sync-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
