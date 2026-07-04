#!/usr/bin/env python3
"""Smoke-test global registry health read-model parity."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import global_registry_health as health_read_model  # noqa: E402


def direct_collect(
    *,
    registry_path: Path,
    runtime_root: Path,
    current_registry: dict[str, Any],
) -> dict[str, Any]:
    return health_read_model.collect_global_registry_health(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=current_registry,
        global_registry_path=status_module.global_registry_path,
        load_registry=status_module.load_registry,
        registry_goals=status_module.registry_goals,
        same_path=status_module.same_path,
        resolve_goal_local_path=status_module.resolve_goal_local_path,
        parse_timestamp=status_module.parse_timestamp,
    )


def assert_parity(
    *,
    registry_path: Path,
    runtime_root: Path,
    current_registry: dict[str, Any],
) -> dict[str, Any]:
    wrapper = status_module.collect_global_registry_health(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=current_registry,
    )
    direct = direct_collect(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=current_registry,
    )
    assert wrapper == direct, (wrapper, direct)
    return wrapper


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-global-registry-health-") as raw_tmp:
        root = Path(raw_tmp)
        runtime = root / "runtime"
        current_registry_path = root / "project" / ".loopx" / "registry.json"
        missing = assert_parity(
            registry_path=current_registry_path,
            runtime_root=runtime,
            current_registry={"goals": []},
        )
        assert missing["available"] is False, missing
        assert missing["summary"] == {
            "high": 0,
            "action": 0,
            "info": 0,
            "checks": 0,
            "findings": 0,
        }, missing

        source_registry = root / "source" / ".loopx" / "registry.json"
        source_registry.parent.mkdir(parents=True)
        source_registry.write_text("{}\n", encoding="utf-8")
        state_file = root / "source" / ".codex" / "goals" / "fresh" / "ACTIVE_GOAL_STATE.md"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("---\nupdated_at: 2026-07-04T00:00:00+00:00\n---\n", encoding="utf-8")

        current_registry = {
            "goals": [
                {
                    "id": "fresh",
                    "repo": str(root / "source"),
                    "state_file": ".codex/goals/fresh/ACTIVE_GOAL_STATE.md",
                }
            ]
        }
        global_registry = {
            "goals": [
                {
                    "id": "fresh",
                    "repo": str(root / "source"),
                    "source_registry": ".loopx/registry.json",
                    "state_file": ".codex/goals/fresh/ACTIVE_GOAL_STATE.md",
                    "synced_at": "2026-07-04T00:00:00+00:00",
                },
                {
                    "id": "duplicate",
                    "repo": str(root / "missing-a"),
                    "state_file": ".codex/goals/duplicate/ACTIVE_GOAL_STATE.md",
                },
                {
                    "id": "duplicate",
                    "repo": str(root / "missing-b"),
                    "source_registry": ".loopx/registry.json",
                },
                {
                    "id": "global-only",
                    "repo": str(root / "missing-c"),
                    "source_registry": ".loopx/registry.json",
                    "state_file": ".codex/goals/global-only/ACTIVE_GOAL_STATE.md",
                },
            ]
        }
        write_json(status_module.global_registry_path(runtime), global_registry)

        health = assert_parity(
            registry_path=current_registry_path,
            runtime_root=runtime,
            current_registry=current_registry,
        )
        kinds = {str(finding.get("kind")) for finding in health["findings"]}
        assert health["available"] is True, health
        assert health["ok"] is False, health
        assert health["summary"]["high"] == 1, health
        assert "duplicate_goal_id" in kinds, health
        assert "source_registry_missing" in kinds, health
        assert "state_file_missing" in kinds, health
        assert "state_file_not_declared" in kinds, health
        assert "current_registry_scope_excludes_global_goals" in kinds, health
        assert health["source_registry_count"] == 3, health

        finding = status_module.global_registry_finding(
            kind="fixture",
            severity="info",
            message="fixture finding",
            recommended_action="keep parity",
            goal_id="fresh",
            path=state_file,
            goal_ids=["fresh"],
        )
        assert finding == health_read_model.global_registry_finding(
            kind="fixture",
            severity="info",
            message="fixture finding",
            recommended_action="keep parity",
            goal_id="fresh",
            path=state_file,
            goal_ids=["fresh"],
        )

    print("global-registry-health-readmodel-smoke ok")


if __name__ == "__main__":
    main()
