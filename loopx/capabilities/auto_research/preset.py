from __future__ import annotations

import shlex
from collections.abc import Iterable

from .defaults import AUTO_RESEARCH_DEFAULT_GOAL_ID
from ..multi_agent.recipe import (
    build_minimal_decentralized_a2a_recipe,
    parse_multi_agent_role_spec_lines,
)


AUTO_RESEARCH_PRESET_SCHEMA_VERSION = "auto_research_thin_preset_v0"
AUTO_RESEARCH_MINIMAL_A2A_RECIPE_SCHEMA_VERSION = "auto_research_minimal_a2a_recipe_v0"
AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION = "auto_research_role_profile_v0"
AUTO_RESEARCH_REQUIRED_SKILL = "loopx-auto-research"
AUTO_RESEARCH_WORKER_SKILL_SOURCE = (
    "loopx/capabilities/auto_research/worker_skill/SKILL.md"
)
AUTO_RESEARCH_DEMO_TICK_ROUNDS = 8
AUTO_RESEARCH_DEMO_TICK_SLEEP_SECONDS = 1
AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Run held-out validation for the dev-supported "
    "hypothesis from {source_todo_id}, append public-safe evidence, and "
    "summarize promotion readiness."
)
AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Summarize held-out validation from {source_todo_id}, "
    "promotion readiness, and the public claim boundary for the supported hypothesis."
)
AUTO_RESEARCH_REFINED_HYPOTHESIS_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Grow the next evidence-backed hypothesis from the "
    "validated branch {source_todo_id} and route a second dev attempt."
)
AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Run the refined hypothesis from {source_todo_id} on "
    "the dev split, append public-safe evidence, and hand off the second holdout check."
)
AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Re-check the research contract and protected scope after "
    "{source_todo_id}, then keep the next collective round honest."
)
AUTO_RESEARCH_HYPOTHESIS_FRONTIER_REVIEW_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Review the current hypothesis frontier after "
    "{source_todo_id}, record whether another candidate is needed, and keep the "
    "round participation visible."
)
AUTO_RESEARCH_PROMOTION_READINESS_REVIEW_SUCCESSOR_TEXT = (
    "[P0-auto-research-live] Review promotion readiness after {source_todo_id}, "
    "record the current evidence gap, and wait for the holdout handoff."
)
AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION = {
    "all": [
        {
            "path": "decision_summary.dev_candidate_pending_holdout_count",
            "op": "gt",
            "value": 0,
            "fail_reason": "no_dev_promotion_candidate",
        }
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
AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION = {
    "all": [
        {
            "path": "decision_summary.validated_promotion_candidate_count",
            "op": "gt",
            "value": 0,
            "fail_reason": "no_validated_promotion_candidate",
        },
        {
            "path": "decision_summary.holdout_improvement_count",
            "op": "lt",
            "value": 2,
            "fail_reason": "target_holdout_improvements_reached",
        },
    ]
}
AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_CONDITION = {
    "all": [
        {
            "path": "decision_summary.holdout_improvement_count",
            "op": "gt",
            "value": 0,
            "fail_reason": "initial_seed_dev_already_exists",
        },
        {
            "path": "decision_summary.holdout_improvement_count",
            "op": "lt",
            "value": 2,
            "fail_reason": "target_holdout_improvements_reached",
        },
        {
            "path": "decision_summary.dev_candidate_pending_holdout_count",
            "op": "eq",
            "value": 0,
            "fail_reason": "dev_candidate_already_pending_holdout",
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
        "research-curator",
        "research-curator",
        "research_curator",
        "Frame the question, metric, protected boundary, and first research todo.",
    ),
    (
        "hypothesis-proposer",
        "hypothesis-proposer",
        "hypothesis_proposer",
        "Grow the hypothesis frontier and route the next bounded research attempt.",
    ),
    (
        "research-executor",
        "research-executor",
        "research_executor",
        "Run dev/holdout evidence for selected hypotheses and append public-safe evidence.",
    ),
    (
        "evaluator-promoter",
        "evaluator-promoter",
        "evaluator_promoter",
        "Prune or promote claims, summarize validation, and trigger the next research round.",
    ),
)

AUTO_RESEARCH_ROLE_PROFILE_ORDER = (
    "research_curator",
    "hypothesis_proposer",
    "research_executor",
    "evaluator_promoter",
)

AUTO_RESEARCH_ROLE_PROFILE_ALIASES = {
    "research-curator": "research_curator",
    "curator": "research_curator",
    "codex-product-capability": "research_curator",
    "hypothesis-proposer": "hypothesis_proposer",
    "hypothesis_mapper": "hypothesis_proposer",
    "hypothesis-mapper": "hypothesis_proposer",
    "mapper": "hypothesis_proposer",
    "hypothesis-runner": "hypothesis_proposer",
    "codex-side-bypass": "hypothesis_proposer",
    "research-executor": "research_executor",
    "research_executor": "research_executor",
    "evidence_runner": "research_executor",
    "evidence-runner": "research_executor",
    "runner": "research_executor",
    "codex-main-control": "research_executor",
    "evaluator-promoter": "evaluator_promoter",
    "evaluator_promoter": "evaluator_promoter",
    "evidence_verifier": "evaluator_promoter",
    "evidence-verifier": "evaluator_promoter",
    "verifier": "evaluator_promoter",
    "evidence-promoter": "evaluator_promoter",
    "codex-value-explorer": "evaluator_promoter",
}

AUTO_RESEARCH_ROLE_PROFILES: dict[str, dict[str, object]] = {
    "research_curator": {
        "phase": "contract",
        "allowed_actions": ["write_research_contract", "review_research_contract"],
        "write_scope": ["research_contract_v0", "todo_item_v0"],
        "handoff": ["Create the first hypothesis-proposer todo."],
    },
    "hypothesis_proposer": {
        "phase": "hypothesis",
        "allowed_actions": ["propose_hypothesis", "review_hypothesis_frontier"],
        "write_scope": ["research_hypothesis_v0", "todo_item_v0"],
        "handoff": ["Create or unblock a research-executor todo."],
        "successor_todos": [
            {
                "after_action": "propose_hypothesis",
                "condition": AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_CONDITION,
                "target_agent_id": "research-executor",
                "target_role_id": "research_executor",
                "task_class": "advancement_task",
                "action_kind": "run_dev_eval",
                "text": AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "propose_hypothesis",
                "condition": AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_CONDITION,
                "target_agent_id": "evaluator-promoter",
                "target_role_id": "evaluator_promoter",
                "task_class": "advancement_task",
                "action_kind": "review_promotion_readiness",
                "text": AUTO_RESEARCH_PROMOTION_READINESS_REVIEW_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            }
        ],
    },
    "research_executor": {
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
                "target_agent_id": "research-executor",
                "target_role_id": "research_executor",
                "task_class": "advancement_task",
                "action_kind": "run_holdout_eval",
                "text": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "run_holdout_eval",
                "condition": AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_CONDITION,
                "target_agent_id": "evaluator-promoter",
                "target_role_id": "evaluator_promoter",
                "task_class": "advancement_task",
                "action_kind": "write_evaluation_summary",
                "text": AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            }
        ],
    },
    "evaluator_promoter": {
        "phase": "verify",
        "allowed_actions": [
            "summarize_evidence",
            "write_evaluation_summary",
            "classify_evidence",
            "review_promotion_readiness",
        ],
        "write_scope": ["research_evidence_graph_v0", "todo_item_v0"],
        "handoff": ["Add a role-declared successor todo when evidence needs another bounded split."],
        "successor_todos": [
            {
                "after_action": "summarize_evidence",
                "condition": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION,
                "target_agent_id": "research-curator",
                "target_role_id": "research_curator",
                "task_class": "advancement_task",
                "action_kind": "review_research_contract",
                "text": AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "summarize_evidence",
                "condition": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION,
                "target_agent_id": "hypothesis-proposer",
                "target_role_id": "hypothesis_proposer",
                "task_class": "advancement_task",
                "action_kind": "review_hypothesis_frontier",
                "text": AUTO_RESEARCH_HYPOTHESIS_FRONTIER_REVIEW_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "write_evaluation_summary",
                "condition": AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION,
                "target_agent_id": "hypothesis-proposer",
                "target_role_id": "hypothesis_proposer",
                "task_class": "advancement_task",
                "action_kind": "propose_hypothesis",
                "text": AUTO_RESEARCH_REFINED_HYPOTHESIS_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "write_evaluation_summary",
                "condition": AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION,
                "target_agent_id": "research-curator",
                "target_role_id": "research_curator",
                "task_class": "advancement_task",
                "action_kind": "review_research_contract",
                "text": AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "review_promotion_readiness",
                "condition": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION,
                "target_agent_id": "research-curator",
                "target_role_id": "research_curator",
                "task_class": "advancement_task",
                "action_kind": "review_research_contract",
                "text": AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
            {
                "after_action": "review_promotion_readiness",
                "condition": AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION,
                "target_agent_id": "hypothesis-proposer",
                "target_role_id": "hypothesis_proposer",
                "task_class": "advancement_task",
                "action_kind": "review_hypothesis_frontier",
                "text": AUTO_RESEARCH_HYPOTHESIS_FRONTIER_REVIEW_SUCCESSOR_TEXT,
                "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
            },
        ],
    },
}

AUTO_RESEARCH_ACTION_ROLE_IDS = {
    "write_research_contract": "research_curator",
    "review_research_contract": "research_curator",
    "propose_hypothesis": "hypothesis_proposer",
    "review_hypothesis_frontier": "hypothesis_proposer",
    "run_dev_eval": "research_executor",
    "run_holdout_eval": "research_executor",
    "write_evidence": "research_executor",
    "classify_evidence": "evaluator_promoter",
    "summarize_evidence": "evaluator_promoter",
    "write_evaluation_summary": "evaluator_promoter",
    "review_promotion_readiness": "evaluator_promoter",
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
    "review_research_contract": (
        "Re-check the research contract and protected scope for the next collective round."
    ),
    "review_hypothesis_frontier": (
        "Review the hypothesis frontier and record whether another bounded candidate is needed."
    ),
    "review_promotion_readiness": (
        "Review promotion readiness and record the current evidence gap."
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
    raw_role_specs = role_specs or default_auto_research_agent_specs()
    return build_minimal_decentralized_a2a_recipe(
        schema_version=AUTO_RESEARCH_MINIMAL_A2A_RECIPE_SCHEMA_VERSION,
        product_id="auto-research",
        claim=(
            "one user command plus the default four-line auto-research role spec "
            "starts decentralized A2A on the shared LoopX multi-agent kernel"
        ),
        claim_boundary=(
            "line count covers user intent and auto-research preset defaults only; "
            "the reusable kernel owns visible process launch, fixed wake prompt, "
            "pane-local quota/frontier tick, todo/evidence/status protocol, "
            "and public artifact routing"
        ),
        user_recipe_lines=[user_line],
        preset_recipe_lines=raw_role_specs,
    )


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
    default_scope = {
        lane: scope for _agent, lane, _role, scope in AUTO_RESEARCH_DEFAULT_LANES
    }
    return parse_multi_agent_role_spec_lines(
        agent_specs=agent_specs,
        default_agent_specs=default_auto_research_agent_specs(),
        resolve_role_id=lambda raw_role, index: auto_research_role_id(
            raw_role,
            index=index,
        ),
        default_scope_by_lane=default_scope,
    )


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
    if role_id == "research_executor":
        return "run_dev_eval"
    if role_id == "evaluator_promoter":
        return "summarize_evidence"
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
