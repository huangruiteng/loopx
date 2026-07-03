from __future__ import annotations

import shlex
from collections.abc import Iterable

from .defaults import AUTO_RESEARCH_DEFAULT_GOAL_ID


AUTO_RESEARCH_PRESET_SCHEMA_VERSION = "auto_research_thin_preset_v0"
AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION = "auto_research_role_profile_v0"
AUTO_RESEARCH_REQUIRED_SKILL = "loopx-auto-research"
AUTO_RESEARCH_WORKER_SKILL_SOURCE = (
    "loopx/capabilities/auto_research/worker_skill/SKILL.md"
)
AUTO_RESEARCH_DEMO_TICK_ROUNDS = 3
AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS = 3

AUTO_RESEARCH_DEFAULT_LANES = (
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

AUTO_RESEARCH_ROLE_PROFILES: dict[str, dict[str, object]] = {
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

AUTO_RESEARCH_SEED_TITLES = {
    "write_research_contract": (
        "Write the public-safe research contract for the shared demo hypothesis."
    ),
    "propose_hypothesis": (
        "Map the first shared idea into a todo-backed research hypothesis."
    ),
    "claim_attempt": "Claim one visible attempt boundary for the selected hypothesis.",
    "run_dev_eval": (
        "Run the selected hypothesis on the dev split, write public-safe evidence, append it, and capture live evidence."
    ),
    "run_holdout_eval": (
        "Run held-out validation for the dev-supported hypothesis, append public-safe evidence, and summarize promotion readiness."
    ),
    "write_evaluation_summary": (
        "Verify the evidence packet and open the next validation or promotion gate."
    ),
    "summarize_evidence": (
        "Summarize dev evidence and hand off holdout validation when the hypothesis is supported."
    ),
}


def default_auto_research_agent_specs() -> list[str]:
    return [
        f"{agent}:{lane}:{role}"
        for agent, lane, role, _scope in AUTO_RESEARCH_DEFAULT_LANES
    ]


def auto_research_role_id(raw_role: str, *, index: int) -> str:
    raw = raw_role.strip()
    role_id = AUTO_RESEARCH_ROLE_PROFILE_ALIASES.get(raw, raw)
    if role_id in AUTO_RESEARCH_ROLE_PROFILES:
        return role_id
    if raw:
        allowed = ", ".join(AUTO_RESEARCH_ROLE_PROFILE_ORDER)
        raise ValueError(f"unknown auto-research role_id {raw!r}; expected one of {allowed}")
    return AUTO_RESEARCH_ROLE_PROFILE_ORDER[(index - 1) % len(AUTO_RESEARCH_ROLE_PROFILE_ORDER)]


def auto_research_lane_specs(agent_specs: Iterable[str] | None) -> list[dict[str, str]]:
    parsed_specs = list(agent_specs or [])
    if not parsed_specs:
        parsed_specs = default_auto_research_agent_specs()

    lanes: list[dict[str, str]] = []
    default_scope = {
        lane: scope for _agent, lane, _role, scope in AUTO_RESEARCH_DEFAULT_LANES
    }
    for index, raw in enumerate(parsed_specs, start=1):
        parts = [part.strip() for part in str(raw).split(":")]
        if len(parts) not in {1, 2, 3, 4} or not parts[0]:
            raise ValueError("agent specs must be agent_id[:lane_id[:role_id[:scope]]]")
        agent_id = parts[0]
        lane_id = parts[1] if len(parts) >= 2 and parts[1] else f"lane-{index}"
        role_id = auto_research_role_id(parts[2] if len(parts) >= 3 else "", index=index)
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


def auto_research_role_profile(*, role_id: str, goal_id: str, agent_id: str) -> dict[str, object]:
    base = dict(AUTO_RESEARCH_ROLE_PROFILES[role_id])
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


def auto_research_worker_turn_command(*, goal_id: str, agent_id: str, objective: str) -> str:
    return (
        "$LOOPX_PANE_LOOPX auto-research worker-turn "
        f"--goal-id {shlex.quote(goal_id)} "
        f"--agent-id {shlex.quote(agent_id)} "
        f"--objective {shlex.quote(objective)} "
        '--lane-count "${LOOPX_VISIBLE_LANE_COUNT:-1}" '
        "--visible-lanes-accepted "
        '--live-evidence-output "$LOOPX_PANE_ARTIFACT_DIR/live-codex-e2e-evidence.public.json" '
        "--execute --complete-selected-todo"
    )


def auto_research_seed_action_for_role(role_id: str) -> str:
    profile = AUTO_RESEARCH_ROLE_PROFILES.get(role_id) or {}
    actions = profile.get("allowed_actions") if isinstance(profile, dict) else []
    action = str((actions or ["advance_todo"])[0])
    if role_id == "evidence_runner":
        return "run_dev_eval"
    return action


def auto_research_seed_title(*, action_kind: str, role_id: str, lane_id: str) -> str:
    return AUTO_RESEARCH_SEED_TITLES.get(
        action_kind,
        f"Run one role-compatible auto-research action for {role_id or lane_id}.",
    )


def build_auto_research_preset_role(
    *,
    lane: dict[str, str],
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    reasoning_effort: str = "high",
) -> dict[str, object]:
    role_id = lane["role_id"]
    agent_id = lane["agent_id"]
    role_profile = auto_research_role_profile(
        role_id=role_id,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    return {
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
        "worker_turn_command": auto_research_worker_turn_command(
            goal_id=goal_id,
            agent_id=agent_id,
            objective="Run the next bounded auto-research frontier item.",
        ),
        "tick_rounds": AUTO_RESEARCH_DEMO_TICK_ROUNDS,
        "tick_sleep_seconds": AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS,
        "reasoning_effort": reasoning_effort,
    }


def build_auto_research_preset_summary(*, role_count: int) -> dict[str, object]:
    return {
        "schema_version": AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
        "owns": [
            "research_roles",
            "handoff_hints",
            "metric_evidence_loop",
            "domain_defaults",
        ],
        "forbidden": [
            "multi_agent_runner",
            "real_codex_tui_panes",
            "workspace_and_trust_safe_launch",
            "decentralized_a2a_driver",
            "pane_local_a2a_tick",
            "todo_evidence_status_protocol",
            "compact_human_status",
        ],
        "role_count": role_count,
        "default_agent_specs": default_auto_research_agent_specs(),
    }
