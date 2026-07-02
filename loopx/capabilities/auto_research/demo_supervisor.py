"""Thin auto-research visible-lane plan built on the generic TUI runner."""

from __future__ import annotations

import shlex
from collections.abc import Iterable
from typing import Any

from .quickstart_seed import AUTO_RESEARCH_DEFAULT_GOAL_ID
from ...visible_multi_agent_launcher import build_visible_multi_agent_payload_from_spec


AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION = "auto_research_demo_supervisor_plan_v0"
AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION = "auto_research_role_profile_v0"
AUTO_RESEARCH_REQUIRED_SKILL = "loopx-auto-research"
AUTO_RESEARCH_WORKER_SKILL_SOURCE = (
    "loopx/capabilities/auto_research/worker_skill/SKILL.md"
)
AUTO_RESEARCH_DEMO_TICK_ROUNDS = 3
AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS = 3

AUTO_RESEARCH_DEMO_DEFAULT_LANES = (
    (
        "codex-product-capability",
        "research-curator",
        "research_curator",
        "Define the research contract, protected boundary, metric, and first todo.",
    ),
    (
        "codex-side-bypass",
        "hypothesis-mapper",
        "hypothesis_mapper",
        "Turn the current idea into a todo-backed hypothesis and successor handoff.",
    ),
    (
        "codex-main-control",
        "evidence-runner",
        "evidence_runner",
        "Run one selected hypothesis and append public-safe evidence.",
    ),
    (
        "codex-value-explorer",
        "evidence-verifier",
        "evidence_verifier",
        "Read appended evidence and decide whether another round is needed.",
    ),
)

AUTO_RESEARCH_ROLE_PROFILE_ORDER = (
    "research_curator",
    "hypothesis_mapper",
    "evidence_runner",
    "evidence_verifier",
)

AUTO_RESEARCH_ROLE_PROFILE_ALIASES = {
    "research-curator": "research_curator",
    "curator": "research_curator",
    "hypothesis-mapper": "hypothesis_mapper",
    "mapper": "hypothesis_mapper",
    "hypothesis-runner": "hypothesis_mapper",
    "evidence-runner": "evidence_runner",
    "runner": "evidence_runner",
    "evidence-verifier": "evidence_verifier",
    "verifier": "evidence_verifier",
    "evidence-promoter": "evidence_verifier",
}

_ROLE_PROFILES: dict[str, dict[str, object]] = {
    "research_curator": {
        "phase": "contract",
        "allowed_actions": ["write_research_contract"],
        "write_scope": ["research_contract_v0", "todo_item_v0"],
        "handoff": ["Create the first hypothesis-mapper todo."],
    },
    "hypothesis_mapper": {
        "phase": "hypothesis",
        "allowed_actions": ["propose_hypothesis"],
        "write_scope": ["research_hypothesis_v0", "todo_item_v0"],
        "handoff": ["Create or unblock an evidence-runner todo."],
    },
    "evidence_runner": {
        "phase": "evidence",
        "allowed_actions": ["run_dev_eval"],
        "write_scope": ["auto_research_evidence_packet_v0", "rollout_event_log"],
        "handoff": ["Append scored evidence, complete the selected todo, and leave verifier context."],
    },
    "evidence_verifier": {
        "phase": "verify",
        "allowed_actions": ["summarize_evidence"],
        "write_scope": ["research_evidence_graph_v0", "todo_item_v0"],
        "handoff": ["Add a next-round hypothesis todo when evidence is incomplete."],
    },
}


def _role_id_for_lane(raw_role: str, *, index: int) -> str:
    raw = raw_role.strip()
    role_id = AUTO_RESEARCH_ROLE_PROFILE_ALIASES.get(raw, raw)
    if role_id in _ROLE_PROFILES:
        return role_id
    if raw:
        allowed = ", ".join(AUTO_RESEARCH_ROLE_PROFILE_ORDER)
        raise ValueError(f"unknown auto-research role_id {raw!r}; expected one of {allowed}")
    return AUTO_RESEARCH_ROLE_PROFILE_ORDER[(index - 1) % len(AUTO_RESEARCH_ROLE_PROFILE_ORDER)]


def _lane_specs(agent_specs: Iterable[str] | None) -> list[dict[str, str]]:
    parsed_specs = list(agent_specs or [])
    if not parsed_specs:
        parsed_specs = [
            f"{agent}:{lane}:{role}" for agent, lane, role, _scope in AUTO_RESEARCH_DEMO_DEFAULT_LANES
        ]

    lanes: list[dict[str, str]] = []
    default_scope = {
        lane: scope for _agent, lane, _role, scope in AUTO_RESEARCH_DEMO_DEFAULT_LANES
    }
    for index, raw in enumerate(parsed_specs, start=1):
        parts = [part.strip() for part in str(raw).split(":")]
        if len(parts) not in {1, 2, 3, 4} or not parts[0]:
            raise ValueError("agent specs must be agent_id[:lane_id[:role_id[:scope]]]")
        agent_id = parts[0]
        lane_id = parts[1] if len(parts) >= 2 and parts[1] else f"lane-{index}"
        role_id = _role_id_for_lane(parts[2] if len(parts) >= 3 else "", index=index)
        scope = parts[3] if len(parts) >= 4 and parts[3] else default_scope.get(lane_id, role_id)
        lanes.append(
            {
                "agent_id": agent_id,
                "lane_id": lane_id,
                "role_id": role_id,
                "scope": scope,
            }
        )
    return lanes


def _profile(role_id: str, *, goal_id: str, agent_id: str) -> dict[str, object]:
    base = dict(_ROLE_PROFILES[role_id])
    return {
        "schema_version": AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": agent_id,
        "role_id": role_id,
        "required_skill": AUTO_RESEARCH_REQUIRED_SKILL,
        "worker_skill_source": AUTO_RESEARCH_WORKER_SKILL_SOURCE,
        "skill_distribution": "worker_local",
        "stop_conditions": [
            "quota says should_run=false or user_action_required=true",
            "frontier has no selected todo for this agent",
            "selected action is outside this role profile",
            "work would require raw logs, credentials, protected scope, or private material",
        ],
        **base,
    }


def _worker_turn_command(*, goal_id: str, agent_id: str, objective: str) -> str:
    return (
        "$LOOPX_PANE_LOOPX auto-research worker-turn "
        f"--goal-id {shlex.quote(goal_id)} "
        f"--agent-id {shlex.quote(agent_id)} "
        f"--objective {shlex.quote(objective)} "
        "--execute --complete-selected-todo"
    )


def build_auto_research_demo_supervisor_plan(
    *,
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    agent_specs: Iterable[str] | None = None,
    session_name: str = "loopx-auto-research",
    cli_bin: str = "loopx",
    codex_bin: str = "codex",
    tmux_bin: str = "tmux",
    reasoning_effort: str = "high",
) -> dict[str, Any]:
    """Build the auto-research visible TUI plan from a small role spec.

    This is intentionally only a launcher/spec packet. Research truth flows
    through each pane's LoopX quota/frontier/todo/evidence commands. The packet
    keeps presentation-specific reporting out of the auto-research kernel.
    """

    goal = str(goal_id).strip() or AUTO_RESEARCH_DEFAULT_GOAL_ID
    lanes = _lane_specs(agent_specs)
    roles = []
    for lane in lanes:
        role_id = lane["role_id"]
        agent_id = lane["agent_id"]
        role_profile = _profile(role_id, goal_id=goal, agent_id=agent_id)
        roles.append(
            {
                "agent_id": agent_id,
                "lane_id": lane["lane_id"],
                "role_id": role_id,
                "scope": lane["scope"],
                "responsibility": lane["scope"],
                "role_profile_ref": f"{AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION}:{role_id}",
                "role_profile": role_profile,
                "skill": {
                    "name": AUTO_RESEARCH_REQUIRED_SKILL,
                    "source": AUTO_RESEARCH_WORKER_SKILL_SOURCE,
                },
                "handoff_hints": role_profile.get("handoff") or [],
                "worker_turn_command": _worker_turn_command(
                    goal_id=goal,
                    agent_id=agent_id,
                    objective="Run the next bounded auto-research frontier item.",
                ),
                "tick_rounds": AUTO_RESEARCH_DEMO_TICK_ROUNDS,
                "tick_sleep_seconds": AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS,
                "reasoning_effort": reasoning_effort,
            }
        )

    payload = build_visible_multi_agent_payload_from_spec(
        {
            "goal_id": goal,
            "session_name": session_name,
            "reasoning_effort": reasoning_effort,
            "roles": roles,
        },
        tmux_bin=tmux_bin,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
    )
    launch_checks = payload.pop("acceptance", None)
    payload.update(
        {
            "schema_version": AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
            "mode": "dry_run",
            "auto_research": {
                "schema_version": "auto_research_visible_demo_kernel_v0",
                "uses_generic_runner": True,
                "surface_count": len(roles),
                "state_bus": "loopx_registry_runtime_todo_quota_frontier",
                "worker_turn": "pane_local_a2a_tick",
                "presentation_layers_in_kernel": False,
            },
            "coordination_model": {
                "leader_agent_required": False,
                "source_of_truth": [
                    "quota_should_run",
                    "agent_scoped_frontier",
                    "todo_claims",
                    "rollout_event_log",
                ],
                "pattern": "decentralized_state_a2a",
            },
            "launch_checks": launch_checks,
            "one_click_demo": {
                "schema_version": "auto_research_one_click_demo_v1",
                "mode": "visible_codex_tui_lanes",
                "default_safe": True,
                "expected_visible_result": [
                    "one tmux window per role",
                    "each window starts a real interactive Codex CLI TUI",
                    "each pane starts by running $LOOPX_PANE_A2A_TICK against its own frontier",
                    "each pane performs bounded role-local polling so successor todos can flow across lanes",
                ],
            },
        }
    )
    return payload
