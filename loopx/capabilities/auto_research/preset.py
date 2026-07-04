from __future__ import annotations

import shlex
from collections.abc import Iterable

from .defaults import AUTO_RESEARCH_DEFAULT_GOAL_ID


AUTO_RESEARCH_PRESET_SCHEMA_VERSION = "auto_research_thin_preset_v0"
AUTO_RESEARCH_MINIMAL_A2A_RECIPE_SCHEMA_VERSION = "auto_research_minimal_a2a_recipe_v0"
AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION = "auto_research_role_profile_v0"
AUTO_RESEARCH_REQUIRED_SKILL = "loopx-auto-research"
AUTO_RESEARCH_WORKER_SKILL_SOURCE = (
    "loopx/capabilities/auto_research/worker_skill/SKILL.md"
)
AUTO_RESEARCH_DEMO_TICK_ROUNDS = 3
AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS = 3
AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Run held-out validation for the dev-supported "
    "hypothesis, append public-safe evidence, and summarize promotion readiness."
)
AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Summarize held-out validation, promotion readiness, "
    "and the public claim boundary for the supported hypothesis."
)
AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION = {
    "all": [
        {
            "path": "decision_summary.dev_promotion_candidate_count",
            "op": "gt",
            "value": 0,
            "fail_reason": "no_dev_promotion_candidate",
        },
        {
            "path": "decision_summary.validated_promotion_candidate_count",
            "op": "eq",
            "value": 0,
            "fail_reason": "holdout_already_validated",
        },
    ]
}
AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_CONDITION = {
    "all": [
        {
            "path": "decision_summary.validated_promotion_candidate_count",
            "op": "gt",
            "value": 0,
            "fail_reason": "no_validated_promotion_candidate",
        },
    ]
}
AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE = (
    "loopx todo add --goal-id {goal_id_shell} --role agent "
    "--text {text_shell} --task-class {task_class_shell} "
    "--action-kind {action_kind_shell} --claimed-by {target_agent_id_shell} "
    "--unblocks-todo-id {source_todo_id_shell}"
)

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
        "allowed_actions": ["run_dev_eval", "run_holdout_eval"],
        "write_scope": ["auto_research_evidence_packet_v0", "rollout_event_log"],
        "handoff": [
            "Append scored evidence, complete the selected todo, and create the declared successor todo when the role profile says another split is due."
        ],
        "successor_todos": [
            {
                "after_action": "run_dev_eval",
                "condition": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION,
                "target_agent_id": "codex-main-control",
                "target_role_id": "evidence_runner",
                "task_class": "advancement_task",
                "action_kind": "run_holdout_eval",
                "text": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "run_holdout_eval",
                "condition": AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_CONDITION,
                "target_agent_id": "codex-value-explorer",
                "target_role_id": "evidence_verifier",
                "task_class": "advancement_task",
                "action_kind": "write_evaluation_summary",
                "text": AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            }
        ],
    },
    "evidence_verifier": {
        "phase": "verify",
        "allowed_actions": ["summarize_evidence"],
        "write_scope": ["research_evidence_graph_v0", "todo_item_v0"],
        "handoff": ["Add a role-declared successor todo when evidence needs another bounded split."],
        "successor_todos": [
            {
                "after_action": "summarize_evidence",
                "condition": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION,
                "target_agent_id": "codex-main-control",
                "target_role_id": "evidence_runner",
                "task_class": "advancement_task",
                "action_kind": "run_holdout_eval",
                "text": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            }
        ],
    },
}

AUTO_RESEARCH_ACTION_ROLE_IDS = {
    "write_research_contract": "research_curator",
    "propose_hypothesis": "hypothesis_mapper",
    "run_dev_eval": "evidence_runner",
    "run_holdout_eval": "evidence_runner",
    "write_evidence": "evidence_runner",
    "classify_evidence": "evidence_verifier",
    "summarize_evidence": "evidence_verifier",
    "write_evaluation_summary": "evidence_verifier",
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


def _quoted_open_question(open_question: object | None) -> str:
    question = str(open_question or "").strip()
    if not question:
        return '"<open question>"'
    return shlex.quote(question)


def build_auto_research_minimal_a2a_recipe(
    *,
    open_question: object | None = None,
    output_language: str = "en",
    role_specs: Iterable[object] | None = None,
) -> dict[str, object]:
    """Return the public line-count claim for the thin auto-research preset.

    The count is deliberately about declarative recipe lines, not the shared
    LoopX kernel implementation. That keeps the public claim reusable and
    honest: other products can replace the four role specs without owning the
    runner, fixed wake prompt, pane-local tick, or state protocol.
    """

    language = str(output_language or "en").strip()
    language_flag = f" --language {shlex.quote(language)}" if language != "en" else ""
    user_line = (
        "loopx auto-research start "
        f"{_quoted_open_question(open_question)}{language_flag} --execute"
    )
    raw_role_specs = (
        role_specs if role_specs is not None else default_auto_research_agent_specs()
    )
    preset_lines = [str(spec).strip() for spec in raw_role_specs if str(spec).strip()]
    user_line_count = 1
    preset_line_count = len(preset_lines)
    return {
        "schema_version": AUTO_RESEARCH_MINIMAL_A2A_RECIPE_SCHEMA_VERSION,
        "claim": (
            "one user command plus the default four-line auto-research role spec "
            "starts decentralized A2A on the shared LoopX multi-agent kernel"
        ),
        "line_unit": "declarative_recipe_line",
        "user_line_count": user_line_count,
        "preset_role_spec_line_count": preset_line_count,
        "user_plus_preset_line_count": user_line_count + preset_line_count,
        "shared_kernel_counted_as_recipe_lines": False,
        "claim_boundary": (
            "line count covers user intent and auto-research preset defaults only; "
            "the reusable kernel owns visible process launch, fixed wake prompt, "
            "pane-local quota/frontier tick, todo/evidence/status protocol, "
            "and public artifact routing"
        ),
        "user_recipe_lines": [user_line],
        "preset_recipe_lines": preset_lines,
        "coordination_model": "decentralized_state_a2a",
        "a2a_proof_contract": {
            "broadcaster_selects_todo": False,
            "broadcaster_runs_worker_turn": False,
            "each_pane_reads_own_quota_frontier": True,
            "successor_todos_declared_by_role_profile": True,
            "leader_agent_required": False,
        },
        "kernel_reuse": [
            "generic visible multi-agent runner",
            "fixed prompt broadcast",
            "pane-local A2A tick",
            "LoopX todo/evidence/status protocol",
        ],
    }


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
        "worker_skill_scope": "role_specific_semantics_and_successor_todos_only",
        "default_kernel_skills_owner": "generic_multi_agent_kernel",
        "fixed_a2a_wake_prompt_owner": "generic_multi_agent_kernel",
        "stop_conditions": [
            "quota says should_run=false or user_action_required=true",
            "frontier has no selected todo for this agent",
            "selected action is outside this role profile",
            "work would require raw logs, credentials, protected scope, or private material",
        ],
        **base,
    }


def auto_research_role_id_for_action(action: str) -> str:
    return AUTO_RESEARCH_ACTION_ROLE_IDS.get(action, "")


def auto_research_successor_specs_for_action(*, role_id: str, action: str) -> list[dict[str, object]]:
    profile = AUTO_RESEARCH_ROLE_PROFILES.get(role_id) or {}
    specs = profile.get("successor_todos") if isinstance(profile, dict) else []
    if not isinstance(specs, list):
        return []
    return [
        dict(spec)
        for spec in specs
        if isinstance(spec, dict) and str(spec.get("after_action") or "") == action
    ]


def auto_research_worker_turn_command(
    *,
    goal_id: str,
    agent_id: str,
    objective: str,
    output_language: str = "en",
) -> str:
    return (
        f"LOOPX_AUTO_RESEARCH_OUTPUT_LANGUAGE={shlex.quote(output_language)} "
        '"${LOOPX_PANE_LOOPX_JSON:-$LOOPX_PANE_LOOPX}" auto-research worker-turn '
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
    output_language: str = "en",
) -> dict[str, object]:
    role_id = lane["role_id"]
    agent_id = lane["agent_id"]
    role_profile = auto_research_role_profile(
        role_id=role_id,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    role_profile["output_language"] = output_language
    return {
        "agent_id": agent_id,
        "lane_id": lane["lane_id"],
        "role_id": role_id,
        "scope": lane["scope"],
        "responsibility": lane["scope"],
        "output_language": output_language,
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
            output_language=output_language,
        ),
        "tick_rounds": AUTO_RESEARCH_DEMO_TICK_ROUNDS,
        "tick_sleep_seconds": AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS,
        "reasoning_effort": reasoning_effort,
    }


def build_auto_research_preset_summary(*, role_count: int) -> dict[str, object]:
    return {
        "schema_version": AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
        "minimal_a2a_recipe": build_auto_research_minimal_a2a_recipe(),
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
            "default_loopx_skill_bootstrap",
            "fixed_a2a_wake_prompt",
            "kernel_default_skill_prompting",
        ],
        "worker_skill_scope": "role_specific_semantics_and_successor_todos_only",
        "successor_routing": "role_profile_successor_todos_with_target_agent",
        "role_count": role_count,
        "default_agent_specs": default_auto_research_agent_specs(),
    }
