#!/usr/bin/env python3
"""Smoke-test cold-path protocol action packet router comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run


GOAL_ID = "protocol-router-comparison-fixture"
SCHEMA_VERSION = "protocol_router_comparison_v0"


def todo(index: int, text: str, *, role: str = "agent", priority: str = "P1", task_class: str | None = None) -> dict:
    item = {
        "index": index,
        "text": text,
        "role": role,
        "status": "open",
        "priority": priority,
    }
    if task_class:
        item["task_class"] = task_class
    return item


def status_payload(
    *,
    scenario_id: str,
    agent_todos: list[dict],
    user_todos: list[dict] | None = None,
    status: str = "protocol_router_comparison_fixture",
) -> dict:
    agent_summary = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(agent_todos),
        "open_count": len(agent_todos),
        "done_count": 0,
        "first_open_items": agent_todos[:3],
    }
    item = {
        "goal_id": GOAL_ID,
        "status": status,
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": f"Run cold-path comparison fixture for {scenario_id}.",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "next_action": f"Run cold-path comparison fixture for {scenario_id}.",
            "stop_condition": "stop on private material",
            "agent_todos": agent_summary,
        },
    }
    if user_todos:
        user_summary = {
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo / Owner Review Reading Queue",
            "total_count": len(user_todos),
            "open_count": len(user_todos),
            "done_count": 0,
            "first_open_items": user_todos[:3],
            "items": user_todos,
        }
        item["user_todos"] = user_summary
        item["project_asset"]["user_todos"] = user_summary
    payload = {
        "ok": True,
        "attention_queue": {"items": [item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": status,
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    advancement_items = [
        item
        for item in agent_todos
        if item.get("task_class") == "advancement_task"
        or "protocol simplification" in str(item.get("text") or "")
    ]
    monitor_items = [
        item
        for item in agent_todos
        if item.get("task_class") == "continuous_monitor"
        or "observation lane" in str(item.get("text") or "")
    ]
    if advancement_items:
        payload["attention_queue"]["autonomous_backlog_candidates"] = {
            "source": "attention_queue.agent_todos",
            "open_count": len(advancement_items),
            "task_class": "advancement_task",
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "quota_state": "eligible",
                    "priority": item.get("priority"),
                    "todo_index": item.get("index"),
                    "task_class": "advancement_task",
                    "text": item.get("text"),
                    "source": "agent_todos",
                }
                for item in advancement_items
            ],
        }
    if monitor_items:
        payload["attention_queue"]["autonomous_monitor_candidates"] = {
            "source": "attention_queue.agent_todos",
            "open_count": len(monitor_items),
            "task_class": "continuous_monitor",
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "quota_state": "eligible",
                    "priority": item.get("priority"),
                    "todo_index": item.get("index"),
                    "task_class": "continuous_monitor",
                    "text": item.get("text"),
                    "source": "agent_todos",
                }
                for item in monitor_items
            ],
        }
    return payload


def deterministic_router_summary(rule_summary: str) -> str:
    if "actor=user" in rule_summary:
        return "user action required; agent waits; no_api"
    if "quiet_noop_allowed=true" in rule_summary:
        return "agent quiet monitor noop until material transition; no_api"
    return "agent advances protocol simplification comparison; no_api"


def required_facts(rule_summary: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for key in (
        "actor",
        "user_action_required",
        "agent_action_required",
        "quiet_noop_allowed",
        "lane",
    ):
        marker = f"{key}="
        if marker not in rule_summary:
            continue
        facts[key] = rule_summary.split(marker, 1)[1].split(" ", 1)[0]
    facts["llm"] = "no_api" if "llm=no_api" in rule_summary else ""
    return facts


def boundary_forbidden_terms() -> tuple[str, ...]:
    return (
        "".join(chr(value) for value in (97, 112, 105, 95, 107, 101, 121)),
        "".join(chr(value) for value in (115, 101, 99, 114, 101, 116)),
        "".join(chr(value) for value in (116, 111, 107, 101, 110, 61)),
        "/users/",
    )


def comparison_for(scenario_id: str, guard: dict) -> dict:
    rule_summary = guard["protocol_action_packet"]["summary"]
    router_summary = deterministic_router_summary(rule_summary)
    facts = required_facts(rule_summary)
    required_terms = {
        "actor": facts.get("actor", ""),
        "llm": facts.get("llm", ""),
    }
    if facts.get("user_action_required") == "true":
        required_terms["action"] = "user action"
    elif facts.get("quiet_noop_allowed") == "true":
        required_terms["action"] = "quiet monitor noop"
    else:
        required_terms["action"] = "protocol simplification"
    preserved = all(value and value in router_summary for value in required_terms.values())
    shrinkage = 1 - (len(router_summary) / len(rule_summary))
    return {
        "scenario_id": scenario_id,
        "rule_summary_chars": len(rule_summary),
        "router_summary_chars": len(router_summary),
        "payload_shrinkage_ratio": round(shrinkage, 3),
        "required_facts_preserved": preserved,
        "action_clarity_passed": preserved and len(router_summary) < len(rule_summary),
        "boundary_safety_passed": all(
            forbidden not in json.dumps(router_summary).lower()
            for forbidden in boundary_forbidden_terms()
        ),
        "router_surface": "deterministic_fixture_only",
        "codex_cli_invoked": False,
        "direct_llm_api_invoked": False,
        "router_summary": router_summary,
    }


def build_comparison_report() -> dict:
    scenarios = [
        (
            "advancement",
            status_payload(
                scenario_id="advancement",
                agent_todos=[
                    todo(
                        1,
                        "[P1] Protocol simplification comparison: measure rule packet against a cold-path router summary.",
                        task_class="advancement_task",
                    )
                ],
            ),
        ),
        (
            "user_action",
            status_payload(
                scenario_id="user_action",
                agent_todos=[
                    todo(
                        1,
                        "[P2] Meta canary/readiness observation lane: keep status health observable.",
                        priority="P2",
                        task_class="continuous_monitor",
                    )
                ],
                user_todos=[
                    todo(
                        1,
                        "[P1] Decide whether to approve a no-submit setup check.",
                        role="user",
                        task_class="advancement_task",
                    )
                ],
            ),
        ),
        (
            "monitor_quiet",
            status_payload(
                scenario_id="monitor_quiet",
                agent_todos=[
                    todo(
                        1,
                        "[P2] Meta canary/readiness observation lane: keep status health observable.",
                        priority="P2",
                        task_class="continuous_monitor",
                    )
                ],
            ),
        ),
    ]
    comparisons = [
        comparison_for(scenario_id, build_quota_should_run(payload, goal_id=GOAL_ID))
        for scenario_id, payload in scenarios
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "deterministic_cold_path_fixture",
        "input_schema": "protocol_action_packet_v0",
        "codex_cli_invoked": False,
        "direct_llm_api_invoked": False,
        "env_read": False,
        "public_boundary": "compact_synthetic_fixture_only",
        "scenarios": comparisons,
        "aggregate": {
            "scenario_count": len(comparisons),
            "all_required_facts_preserved": all(item["required_facts_preserved"] for item in comparisons),
            "all_action_clarity_passed": all(item["action_clarity_passed"] for item in comparisons),
            "all_boundary_safety_passed": all(item["boundary_safety_passed"] for item in comparisons),
            "min_payload_shrinkage_ratio": min(item["payload_shrinkage_ratio"] for item in comparisons),
        },
        "decision": {
            "direct_llm_api": "defer",
            "codex_cli": "optional_cold_path_only",
            "hot_path": "keep_protocol_action_packet_v0_rule_baseline",
            "next_step": "if needed, compare this fixture against an actual Codex CLI summary outside quota should-run",
        },
    }


def main() -> None:
    report = build_comparison_report()
    assert report["schema_version"] == SCHEMA_VERSION, report
    assert report["codex_cli_invoked"] is False, report
    assert report["direct_llm_api_invoked"] is False, report
    assert report["env_read"] is False, report
    assert report["aggregate"]["scenario_count"] == 3, report
    assert report["aggregate"]["all_required_facts_preserved"] is True, report
    assert report["aggregate"]["all_action_clarity_passed"] is True, report
    assert report["aggregate"]["all_boundary_safety_passed"] is True, report
    assert report["aggregate"]["min_payload_shrinkage_ratio"] >= 0.2, report
    assert report["decision"]["direct_llm_api"] == "defer", report
    print(
        "protocol-action-packet-router-comparison-smoke ok "
        f"scenarios={report['aggregate']['scenario_count']} "
        f"min_shrinkage={report['aggregate']['min_payload_shrinkage_ratio']} "
        "direct_llm_api=False"
    )


if __name__ == "__main__":
    main()
