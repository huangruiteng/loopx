#!/usr/bin/env python3
"""Smoke-test local default upgrade propagation planning."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.upgrade import build_upgrade_plan, render_upgrade_plan_markdown  # noqa: E402


GOAL_ID = "upgrade-plan-goal"


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "## Next Action\n\n"
        "- Keep the fixture heartbeat prompt current.\n",
        encoding="utf-8",
    )
    registry_path = project / ".goal-harness" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "quota": {"compute": 1.0, "window_hours": 24},
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, root / "installed-heartbeats.json"


def assert_unknown_manifest_blocks_promotion(registry_path: Path) -> dict:
    payload = build_upgrade_plan(registry_path=registry_path, modes=["brief"], cli_bin="goal-harness")
    assert payload["ok"] is True, payload
    assert payload["summary"]["managed_goal_count"] == 1, payload
    assert payload["summary"]["unknown_prompt_count"] == 1, payload
    assert payload["summary"]["ready_for_default_promotion"] is False, payload
    goal = payload["managed_heartbeats"][0]
    assert goal["state_file_exists"] is True, payload
    assert goal["installed_prompts"]["brief"]["status"] == "unknown", payload
    markdown = render_upgrade_plan_markdown(payload)
    assert "ready_for_default_promotion: `False`" in markdown, markdown
    return payload


def assert_matching_manifest_is_ready(registry_path: Path, manifest_path: Path, first_payload: dict) -> None:
    goal = first_payload["managed_heartbeats"][0]
    prompt_sha = goal["generated_prompts"]["brief"]["sha256"]
    manifest_path.write_text(
        json.dumps(
            {
                "automations": [
                    {
                        "automation_id": "fixture-heartbeat",
                        "goal_id": GOAL_ID,
                        "mode": "brief",
                        "prompt_sha256": prompt_sha,
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    payload = build_upgrade_plan(
        registry_path=registry_path,
        installed_manifest=manifest_path,
        modes=["brief"],
        cli_bin="goal-harness",
    )
    assert payload["summary"]["unknown_prompt_count"] == 0, payload
    assert payload["summary"]["stale_prompt_count"] == 0, payload
    assert payload["summary"]["current_prompt_count"] == 1, payload
    assert payload["summary"]["ready_for_default_promotion"] is True, payload
    assert payload["managed_heartbeats"][0]["installed_prompts"]["brief"]["status"] == "current", payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-upgrade-plan-smoke-") as raw_tmp:
        registry_path, manifest_path = write_fixture(Path(raw_tmp))
        first_payload = assert_unknown_manifest_blocks_promotion(registry_path)
        assert_matching_manifest_is_ready(registry_path, manifest_path, first_payload)
    print("upgrade-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
