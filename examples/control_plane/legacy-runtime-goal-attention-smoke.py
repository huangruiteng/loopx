#!/usr/bin/env python3
"""Smoke-test legacy runtime goal attention projection."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import build_attention_queue  # noqa: E402


def build_queue(*, classification: str, json_exists: bool = True, markdown_exists: bool = True) -> dict:
    run = {
        "generated_at": "2026-01-01T00:00:00Z",
        "goal_id": "legacy-demo",
        "classification": classification,
        "json_exists": json_exists,
        "markdown_exists": markdown_exists,
    }
    history = {
        "goal_count": 1,
        "run_count": 1,
        "goals": [
            {
                "id": "legacy-demo",
                "status": "active",
                "registry_member": False,
                "legacy_runtime_goal": True,
                "latest_runs": [run],
            }
        ],
        "runs": [run],
    }
    return build_attention_queue(
        contract={"ok": True},
        history=history,
        global_registry={"ok": True, "findings": []},
    )


def test_missing_artifact_projects_high_attention() -> None:
    queue = build_queue(classification="state_refreshed", markdown_exists=False)
    item = queue["items"][0]
    assert item["status"] == "unregistered_runtime_goal", item
    assert item["waiting_on"] == "controller", item
    assert item["severity"] == "high", item
    assert "archive-runtime" in item["recommended_action"], item


def test_blocking_classification_projects_high_attention() -> None:
    queue = build_queue(classification="blocked_by_safety")
    item = queue["items"][0]
    assert item["status"] == "unregistered_runtime_goal", item
    assert item["severity"] == "high", item
    assert "blocked_by_safety" in item["recommended_action"], item


def test_neutral_complete_legacy_runtime_goal_stays_quiet() -> None:
    queue = build_queue(classification="neutral_complete")
    assert queue["items"] == [], queue


def main() -> int:
    test_missing_artifact_projects_high_attention()
    test_blocking_classification_projects_high_attention()
    test_neutral_complete_legacy_runtime_goal_stays_quiet()
    print("legacy-runtime-goal-attention-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
