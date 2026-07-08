#!/usr/bin/env python3
"""Smoke-test run history read-model parity."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.boundary_authority import (  # noqa: E402
    CHECKPOINTED_BOUNDARY_AUTHORITY_SCHEMA_VERSION,
    checkpointed_boundary_authority_summary,
)
from loopx.control_plane.runtime import run_history as run_history_read_model  # noqa: E402


def direct_latest_run(goal: dict) -> dict | None:
    return run_history_read_model.latest_run(
        goal,
        is_status_neutral_run=status_module.is_status_neutral_run,
    )


def direct_history(history: dict, *, display_limit: int | None = None) -> dict:
    return run_history_read_model.build_run_history(
        history,
        latest_run=status_module.latest_run,
        goal_lifecycle_fields=status_module.goal_lifecycle_fields,
        subagent_activity_for_goal=status_module.subagent_activity_for_goal,
        compact_run=status_module.compact_run,
        quota_status=status_module.quota_status,
        display_limit=display_limit,
    )


def assert_parity(history: dict, *, display_limit: int | None = None) -> dict:
    effective_display_limit = 999 if display_limit is None else display_limit
    wrapper = status_module.build_status_runtime_summaries(
        history=history,
        queue={},
        runtime_root=REPO_ROOT,
        goal_id_filter=None,
        display_limit=effective_display_limit,
        todo_index_limit=5,
    )["run_history"]
    direct = direct_history(history, display_limit=effective_display_limit)
    assert direct == wrapper, (direct, wrapper)
    return wrapper


def main() -> None:
    active_run = {"run_id": "active", "classification": "implementation_batch"}
    neutral_status_run = {"run_id": "status-only", "classification": "quota_slot_spent"}
    neutral_latest_run = {"run_id": "neutral", "classification": "quota_slot_spent"}
    latest_run_goal = {
        "latest_status_run": neutral_status_run,
        "latest_runs": [
            "invalid",
            neutral_latest_run,
            active_run,
        ],
    }
    assert status_module.latest_run(latest_run_goal) == direct_latest_run(latest_run_goal) == active_run
    assert status_module.latest_run({"latest_status_run": active_run}) == direct_latest_run(
        {"latest_status_run": active_run}
    ) == active_run
    assert status_module.latest_run({"latest_runs": [neutral_latest_run]}) == direct_latest_run(
        {"latest_runs": [neutral_latest_run]}
    ) is None

    history = {
        "goal_count": 2,
        "run_count": 4,
        "goals": [
            {
                "id": "loopx-meta",
                "domain": "loopx-platform",
                "status": "active-read-only",
                "registry_member": True,
                "legacy_runtime_goal": False,
                "adapter_kind": "harness_self_improvement",
                "adapter_status": "connected-read-only",
                "coordination": {
                    "primary_agent": "codex-main-control",
                    "registered_agents": ["codex-main-control", "codex-product-capability"],
                    "side_agent_handoff_agent": "codex-product-capability",
                    "checkpointed_boundary_authority": [
                        {
                            "status": "active",
                            "decision": "approve",
                            "write_scope": ["loopx/**"],
                            "source": "operator-approved product capability lane",
                            "decision_id": "gate-approved",
                            "recorded_at": "2026-07-04T00:04:00+00:00",
                        },
                        {
                            "status": "inactive",
                            "decision": "defer",
                            "write_scope": ["docs/**"],
                            "source": "deferred docs lane",
                            "decision_id": "gate-deferred",
                            "recorded_at": "2026-07-04T00:04:30+00:00",
                        },
                    ],
                },
                "guards": [{"kind": "private_boundary"}],
                "next_probe": "continue",
                "authority_registry": {"present": True},
                "index_exists": True,
                "raw_index_records": 3,
                "unique_runs": 2,
                "latest_status_run": {
                    "goal_id": "loopx-meta",
                    "generated_at": "2026-07-04T00:05:00+00:00",
                    "classification": "implementation_batch",
                    "recommended_action": "continue",
                    "human_reward": {
                        "recorded_at": "2026-07-04T00:06:00+00:00",
                        "decision": "continue",
                        "reward": 1,
                        "lesson": {
                            "schema_version": "lesson_v0",
                            "kind": "process",
                            "summary": "preserve parity",
                            "private_note": "must not surface",
                        },
                    },
                    "ignored_field": "not compacted",
                },
                "latest_runs": [
                    {
                        "goal_id": "loopx-meta",
                        "run_id": "run-2",
                        "generated_at": "2026-07-04T00:05:00+00:00",
                        "classification": "implementation_batch",
                        "operator_gate": {
                            "recorded_at": "2026-07-04T00:04:00+00:00",
                            "decision": "approved",
                            "private_note": "must not surface",
                        },
                        "subagents": [
                            {
                                "run_id": "child-1",
                                "agent_role": "product-capability",
                                "classification": "completed",
                                "quota_slots": 1,
                            }
                        ],
                    },
                    "invalid-run",
                    {
                        "goal_id": "loopx-meta",
                        "run_id": "run-1",
                        "generated_at": "2026-07-04T00:00:00+00:00",
                        "classification": "state_refreshed",
                    },
                ],
            },
            "invalid-goal",
            {
                "id": "local-only",
                "domain": "local",
                "status": "inactive",
                "registry_member": False,
                "coordination": "not-a-dict",
                "guards": "not-a-list",
                "latest_runs": [
                    {
                        "goal_id": "local-only",
                        "run_id": "local-run",
                        "generated_at": "2026-07-04T00:01:00+00:00",
                        "classification": "state_refreshed",
                    }
                ],
            },
        ],
        "runs": [
            {
                "goal_id": "loopx-meta",
                "run_id": "recent-1",
                "generated_at": "2026-07-04T00:05:00+00:00",
                "classification": "implementation_batch",
            },
            "invalid-run",
            {
                "goal_id": "local-only",
                "run_id": "recent-2",
                "generated_at": "2026-07-04T00:01:00+00:00",
                "classification": "state_refreshed",
            },
        ],
    }

    full = assert_parity(history)
    assert full["available"] is True, full
    assert full["goal_count"] == 2, full
    assert full["run_count"] == 4, full
    assert [goal["id"] for goal in full["goals"]] == ["loopx-meta", "local-only"], full
    assert len(full["recent_runs"]) == 2, full

    meta = full["goals"][0]
    assert meta["quota"] is not None, meta
    assert meta["coordination"]["primary_agent"] == "codex-main-control", meta
    assert meta["coordination"]["registered_agents"] == [
        "codex-main-control",
        "codex-product-capability",
    ], meta
    boundary_authority = meta["coordination"]["checkpointed_boundary_authority"]
    assert boundary_authority == {
        "schema_version": CHECKPOINTED_BOUNDARY_AUTHORITY_SCHEMA_VERSION,
        "active_count": 1,
        "inactive_count": 1,
        "active_write_scope": ["loopx/**"],
    }, meta
    assert checkpointed_boundary_authority_summary(meta["coordination"]) == boundary_authority, meta
    assert "entries" not in boundary_authority, meta
    assert "gate-approved" not in str(meta["coordination"]), meta
    assert meta["guards"] == [{"kind": "private_boundary"}], meta
    assert meta["latest_status_run"]["human_reward"]["lesson"] == {
        "schema_version": "lesson_v0",
        "kind": "process",
        "summary": "preserve parity",
    }, meta
    assert "private_note" not in str(meta), meta
    assert len(meta["latest_runs"]) == 2, meta
    assert meta["subagent_activity"]["child_count"] == 1, meta
    assert meta["subagent_activity"]["items"][0]["agent_role"] == "product-capability", meta
    assert meta["subagent_activity"]["quota_spend_slots"] == 1, meta

    local = full["goals"][1]
    assert local["quota"] is None, local
    assert local["coordination"] is None, local
    assert local["guards"] == [], local

    limited = assert_parity(history, display_limit=1)
    assert len(limited["recent_runs"]) == 1, limited
    assert len(limited["goals"][0]["latest_runs"]) == 1, limited

    empty_limit = assert_parity(history, display_limit=-5)
    assert empty_limit["recent_runs"] == [], empty_limit
    assert empty_limit["goals"][0]["latest_runs"] == [], empty_limit

    print("run-history-readmodel-smoke ok")


if __name__ == "__main__":
    main()
