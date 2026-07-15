from __future__ import annotations

from typing import Any


CONTROL_PLANE_QUALIFICATION_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "control-plane-state-machine",
        "title": "Control-plane state-machine composition",
        "purpose": (
            "Run a bounded cross-state-machine canary when interaction, work-lane, "
            "scheduler, frontier, writeback, or quota-spend transitions change together."
        ),
        "catalog_families": ["Work Routing", "State And Boundary", "Planning Governance"],
        "trigger_hints": (
            "state-machine",
            "state machine",
            "interaction_contract",
            "work_lane_contract",
            "scheduler_hint",
            "goal_frontier",
            "automation_liveness",
            "spend-slot",
            "scheduler-ack",
            "monitor_target",
            "monitor_poll_writeback",
            "interaction_contract.py",
            "loopx/control_plane/scheduler/monitor_poll_writeback.py",
            "loopx/control_plane/scheduler/monitor_target.py",
            "loopx/control_plane/work_items/interaction_contract.py",
            "loopx/control_plane/work_items/execution_obligation.py",
            "loopx/control_plane/work_items/goal_route_hint.py",
            "loopx/control_plane/work_items/outcome_followthrough.py",
            "loopx/control_plane/work_items/work_lane.py",
            "loopx/control_plane/runtime/event_store_migration_bridge.py",
            "control-plane-integrated-canary-smoke.py",
            "interaction-contract-state-machine-smoke.py",
            "docs/product/core-control-plane/state-machine.md",
        ),
        "checks": [
            {
                "command": "python3 examples/control_plane/control-plane-integrated-canary-smoke.py",
                "tier": "deep",
                "reason": (
                    "samples the full event-sourced todo projection, status, quota interaction contract, "
                    "work-lane contract, scheduler ack, refresh-state, spend-slot, and review-packet handoff path; "
                    "kept deep because it is a slow end-to-end fixture"
                ),
            },
            {
                "command": "python3 examples/control_plane/peer-agent-continuation-state-machine-smoke.py",
                "tier": "default",
                "reason": (
                    "guards peer self-merge continuation through successor todo selection, "
                    "agent-lane refresh, scheduler ack, quota spend, and preserved goal next action"
                ),
            },
            {
                "command": "python3 examples/control_plane/interaction-contract-state-machine-smoke.py",
                "tier": "default",
                "reason": (
                    "guards interaction/protocol state-machine modes across active work, user notice, "
                    "monitor quiet, autonomous replan, agent-scope wait, and successor replan"
                ),
            },
            {
                "command": "python3 examples/control_plane/heartbeat-quota-flow-smoke.py",
                "tier": "default",
                "reason": "guards the heartbeat writeback then spend lifecycle that the composition canary executes",
            },
            {
                "command": "python3 examples/control_plane/quota-scheduler-state-ack-smoke.py",
                "tier": "default",
                "reason": "guards scheduler_hint stateful ack progression and no-spend cadence transitions",
            },
            {
                "command": "python3 examples/control_plane/work-lane-contract-smoke.py",
                "tier": "deep",
                "reason": "covers additional work-lane policy branches outside the integrated active-work path",
            },
        ],
    },
    {
        "id": "agent-facing-cli-output-budget",
        "title": "Agent-facing CLI output qualification",
        "purpose": (
            "Run exact stdout budgets and fail-closed command classification when "
            "recurring agent-facing CLI surfaces or their qualification contract change."
        ),
        "catalog_families": ["Work Routing", "State And Boundary", "Planning Governance"],
        "trigger_hints": (
            "agent-facing cli",
            "cli output budget",
            "cli output qualification",
            "loopx/cli.py",
            "loopx/help_surface.py",
            "loopx/cli_commands/",
            "loopx/project_prompt.py",
            "loopx/quota.py",
            "loopx/status.py",
            "loopx/review_packet.py",
            "loopx/heartbeat_prompt.py",
            "loopx/todos.py",
            "loopx/run_history.py",
            "loopx/evidence_log.py",
            "loopx/control_plane/testing/cli_output_budget.py",
            "tests/control_plane/test_cli_output_budget.py",
            "examples/control_plane/cli-output-budget-regression-smoke.py",
            ".github/workflows/python-tests.yml",
            "docs/interface-budget-contract.md",
        ),
        "checks": [
            {
                "command": "python3 examples/control_plane/cli-output-budget-regression-smoke.py",
                "tier": "default",
                "reason": (
                    "invokes the real CLI across declared JSON/Markdown surfaces, modes, "
                    "fixture scales, semantic anchors, and command classifications"
                ),
            },
            {
                "command": "python3 examples/control_plane/hot-path-interface-budget-smoke.py",
                "tier": "deep",
                "reason": "pairs emitted stdout qualification with compact in-memory hot-path budgets",
            },
        ],
    },
)
