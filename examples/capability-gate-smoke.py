#!/usr/bin/env python3
"""Smoke-test per-todo capability requirements in quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, build_quota_slot_preview  # noqa: E402


GOAL_ID = "capability-gate-goal"


def todo(index: int, priority: str, text: str, capabilities: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "todo_item_v0",
        "todo_id": f"todo_capability_{index}",
        "role": "agent",
        "status": "open",
        "done": False,
        "index": index,
        "priority": priority,
        "text": text,
        "title": text.removeprefix(f"[{priority}] "),
        "task_class": "advancement_task",
        "action_kind": "run_eval" if "benchmark" in text.lower() else "validate",
        "required_capabilities": capabilities,
    }


def status_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(items),
        "open_count": len(items),
        "done_count": 0,
        "first_open_items": items[:3],
        "first_executable_items": items[:3],
        "backlog_items": items[:8],
        "executable_backlog_items": items[:8],
        "monitor_open_items": [],
    }
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "allowed_slots": 1440,
        "spent_slots": 0,
        "state": "eligible",
        "reason": "fixture eligible quota",
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "codex",
                    "severity": "info",
                    "source": "project_asset",
                    "quota": quota,
                    "project_asset": {
                        "next_action": items[0]["text"] if items else "",
                        "agent_todos": summary,
                    },
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "quota": quota,
                    "latest_runs": [],
                }
            ]
        },
    }


def main() -> int:
    p0_benchmark = todo(
        1,
        "P0",
        "[P0] Run the benchmark runner once and write back compact result.",
        ["shell", "benchmark_runner"],
    )
    p0_validate = todo(
        2,
        "P0",
        "[P0] Validate the public control-plane docs.",
        ["shell", "filesystem_write"],
    )
    p0_network = todo(
        3,
        "P0",
        "[P0] Fetch external public data before drafting the packet.",
        ["shell", "network"],
    )
    p1_gpu = todo(
        4,
        "P1",
        "[P1] Rebuild the optional GPU-heavy visual fixture.",
        ["shell", "gpu_runner"],
    )
    p1_docs = todo(
        5,
        "P1",
        "[P1] Refresh the public docs fallback and validate it.",
        ["shell", "filesystem_write"],
    )

    p0_fallback = build_quota_should_run(
        status_payload([p0_benchmark, p0_validate, p1_docs]),
        goal_id=GOAL_ID,
        available_capabilities=["shell", "filesystem_write"],
    )
    assert p0_fallback["should_run"] is True, p0_fallback
    assert p0_fallback["normal_delivery_allowed"] is True, p0_fallback
    assert p0_fallback["capability_gate"]["action"] == "run", p0_fallback
    assert p0_fallback["capability_gate"]["decision_owner"] == "agent", p0_fallback
    assert [
        item["todo_id"]
        for item in p0_fallback["capability_gate"]["runnable_candidates"]
    ] == ["todo_capability_2", "todo_capability_5"], p0_fallback
    assert p0_fallback["capability_gate"]["blocked_candidates"][0]["todo_id"] == "todo_capability_1", p0_fallback
    assert "Run the benchmark runner once" in p0_fallback["recommended_action"], p0_fallback
    assert "choose one of 2 capability-runnable todo(s)" in p0_fallback["protocol_action_packet"]["summary"], p0_fallback

    fallback = build_quota_should_run(
        status_payload([p0_benchmark, p0_network, p1_gpu, p1_docs]),
        goal_id=GOAL_ID,
        available_capabilities=["shell", "filesystem_write"],
    )
    assert fallback["should_run"] is True, fallback
    assert fallback["normal_delivery_allowed"] is True, fallback
    assert fallback["capability_gate"]["action"] == "run", fallback
    assert [item["todo_id"] for item in fallback["capability_gate"]["runnable_candidates"]] == [
        "todo_capability_5",
    ], fallback
    assert [item["todo_id"] for item in fallback["capability_gate"]["blocked_candidates"]] == [
        "todo_capability_1",
        "todo_capability_3",
        "todo_capability_4",
    ], fallback
    assert fallback["capability_gate"]["blocked_candidates"][0]["missing_capabilities"] == ["benchmark_runner"], fallback
    assert fallback["capability_gate"]["blocked_candidates"][1]["missing_capabilities"] == ["network"], fallback
    assert fallback["capability_gate"]["blocked_candidates"][2]["missing_capabilities"] == ["gpu_runner"], fallback
    assert "Run the benchmark runner once" in fallback["recommended_action"], fallback
    assert "choose one of 1 capability-runnable todo(s)" in fallback["protocol_action_packet"]["summary"], fallback

    benchmark_ready = build_quota_should_run(
        status_payload([p0_benchmark, p0_validate, p1_docs]),
        goal_id=GOAL_ID,
        available_capabilities=["shell", "filesystem_write", "benchmark_runner"],
    )
    assert benchmark_ready["capability_gate"]["action"] == "run", benchmark_ready
    assert [
        item["todo_id"]
        for item in benchmark_ready["capability_gate"]["runnable_candidates"]
    ] == ["todo_capability_1", "todo_capability_2", "todo_capability_5"], benchmark_ready
    assert benchmark_ready["capability_gate"]["blocked_candidates"] == [], benchmark_ready

    spend_preview = build_quota_slot_preview(
        status_payload([p0_benchmark, p0_validate, p1_docs]),
        goal_id=GOAL_ID,
        available_capabilities=["shell", "filesystem_write", "benchmark_runner"],
    )
    assert spend_preview["ok"] is True, spend_preview
    assert spend_preview["before"]["normal_delivery_allowed"] is True, spend_preview
    assert spend_preview["before"]["capability_gate"]["runnable_candidates"][0]["todo_id"] == "todo_capability_1", spend_preview

    bridge_missing = build_quota_should_run(
        status_payload([p0_benchmark]),
        goal_id=GOAL_ID,
        available_capabilities=["shell", "filesystem_write"],
    )
    assert bridge_missing["should_run"] is True, bridge_missing
    assert bridge_missing["normal_delivery_allowed"] is False, bridge_missing
    assert bridge_missing["capability_repair_allowed"] is True, bridge_missing
    assert bridge_missing["effective_action"] == "capability_bridge_repair", bridge_missing
    assert bridge_missing["capability_gate"]["action"] == "repair_bridge", bridge_missing
    assert bridge_missing["interaction_contract"]["mode"] == "capability_bridge_repair", bridge_missing
    assert bridge_missing["execution_obligation"]["kind"] == "capability_bridge_repair", bridge_missing

    network_todo = todo(
        6,
        "P0",
        "[P0] Fetch external public data before drafting the packet.",
        ["shell", "network"],
    )
    owner_gate = build_quota_should_run(
        status_payload([network_todo]),
        goal_id=GOAL_ID,
        available_capabilities=["shell", "filesystem_write"],
    )
    assert owner_gate["should_run"] is False, owner_gate
    assert owner_gate["requires_user_action"] is True, owner_gate
    assert owner_gate["capability_gate"]["action"] == "ask_owner", owner_gate
    assert owner_gate["interaction_contract"]["user_channel"]["action_required"] is True, owner_gate
    assert owner_gate["heartbeat_recommendation"]["notify"] == "NOTIFY", owner_gate

    print("capability-gate-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
