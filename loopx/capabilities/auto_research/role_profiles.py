from __future__ import annotations

AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION = "auto_research_role_profile_v0"
AUTO_RESEARCH_REQUIRED_HOLDOUT_IMPROVEMENTS = 2
AUTO_RESEARCH_REQUIRED_SKILL = "loopx-auto-research"
AUTO_RESEARCH_WORKER_SKILL_SOURCE = (
    "loopx/capabilities/auto_research/worker_skill/SKILL.md"
)
AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT = "[P0-auto-research-live] Run held-out validation for the dev-supported hypothesis from {source_todo_id}, append public-safe evidence, and summarize promotion readiness."
AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_TEXT = "[P0-auto-research-live] Summarize held-out validation from {source_todo_id}, promotion readiness, and the public claim boundary for the supported hypothesis."
AUTO_RESEARCH_REFINED_HYPOTHESIS_SUCCESSOR_TEXT = "[P0-auto-research-live] Grow the next evidence-backed hypothesis from the validated branch {source_todo_id} and route a second dev attempt."
AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_TEXT = "[P0-auto-research-live] Run the refined hypothesis from {source_todo_id} on the dev split, append public-safe evidence, and hand off the second holdout check."
AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT = "[P0-auto-research-live] Re-check the research contract and protected scope after {source_todo_id}, then keep the next collective round honest."
AUTO_RESEARCH_HYPOTHESIS_FRONTIER_REVIEW_SUCCESSOR_TEXT = "[P0-auto-research-live] Review the current hypothesis frontier after {source_todo_id}, record whether another candidate is needed, and keep the round participation visible."
AUTO_RESEARCH_PROMOTION_READINESS_REVIEW_SUCCESSOR_TEXT = "[P0-auto-research-live] Review promotion readiness after {source_todo_id}, record the current evidence gap, and wait for the holdout handoff."
AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE = (
    "loopx todo add --goal-id {goal_id_shell} --role agent "
    "--text {text_shell} --task-class {task_class_shell} "
    "--action-kind {action_kind_shell} --claimed-by {target_agent_id_shell} "
    "--unblocks-todo-id {source_todo_id_shell}"
)


def _condition(path: str, op: str, value: object, fail_reason: str) -> dict[str, object]:
    return {"path": path, "op": op, "value": value, "fail_reason": fail_reason}


def _all(*conditions: dict[str, object]) -> dict[str, object]:
    return {"all": list(conditions)}


AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION = _all(
    _condition("decision_summary.dev_candidate_pending_holdout_count", "gt", 0, "no_dev_promotion_candidate")
)
AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_CONDITION = _all(
    _condition("decision_summary.validated_promotion_candidate_count", "gt", 0, "no_validated_promotion_candidate")
)
AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION = _all(
    _condition("decision_summary.validated_promotion_candidate_count", "gt", 0, "no_validated_promotion_candidate"),
    _condition(
        "decision_summary.holdout_improvement_count",
        "lt",
        AUTO_RESEARCH_REQUIRED_HOLDOUT_IMPROVEMENTS,
        "target_holdout_improvements_reached",
    ),
)
AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_CONDITION = _all(
    _condition("decision_summary.holdout_improvement_count", "gt", 0, "initial_seed_dev_already_exists"),
    _condition(
        "decision_summary.holdout_improvement_count",
        "lt",
        AUTO_RESEARCH_REQUIRED_HOLDOUT_IMPROVEMENTS,
        "target_holdout_improvements_reached",
    ),
    _condition("decision_summary.dev_candidate_pending_holdout_count", "eq", 0, "dev_candidate_already_pending_holdout"),
)

AUTO_RESEARCH_CONTINUATION_POLICY = {
    "schema_version": "auto_research_continuation_policy_v0",
    "successor_source": "role_profile.successor_todos",
    "required_holdout_improvement_count": AUTO_RESEARCH_REQUIRED_HOLDOUT_IMPROVEMENTS,
    "unmet_target_rule": (
        "if validated_promotion_candidate_count>0 and holdout_improvement_count is below "
        "required_holdout_improvement_count, create or link the role-declared successor"
    ),
    "no_followup_rule": (
        "no-follow-up is valid only after the target is reached, a blocker/user gate is "
        "projected, or evidence-backed retirement closes the frontier"
    ),
}


def _successor(
    after_action: str,
    condition: dict[str, object],
    target_agent_id: str,
    target_role_id: str,
    action_kind: str,
    text: str,
) -> dict[str, object]:
    return {
        "after_action": after_action,
        "condition": condition,
        "target_agent_id": target_agent_id,
        "target_role_id": target_role_id,
        "task_class": "advancement_task",
        "action_kind": action_kind,
        "text": text,
        "todo_command_template": AUTO_RESEARCH_SUCCESSOR_TODO_COMMAND_TEMPLATE,
    }


AUTO_RESEARCH_DEFAULT_LANES = (
    ("research-curator", "research-curator", "research_curator", "Frame the question, metric, protected boundary, and first research todo."),
    ("hypothesis-proposer", "hypothesis-proposer", "hypothesis_proposer", "Grow the hypothesis frontier and route the next bounded research attempt."),
    ("research-executor", "research-executor", "research_executor", "Run dev/holdout evidence for selected hypotheses and append public-safe evidence."),
    ("evaluator-promoter", "evaluator-promoter", "evaluator_promoter", "Prune or promote claims, summarize validation, and trigger the next research round."),
)

AUTO_RESEARCH_ROLE_PROFILE_ORDER = ("research_curator", "hypothesis_proposer", "research_executor", "evaluator_promoter")

AUTO_RESEARCH_ROLE_PROFILE_ALIASES = {
    "research-curator": "research_curator",
    "curator": "research_curator",
    "hypothesis-proposer": "hypothesis_proposer",
    "hypothesis_mapper": "hypothesis_proposer",
    "hypothesis-mapper": "hypothesis_proposer",
    "mapper": "hypothesis_proposer",
    "hypothesis-runner": "hypothesis_proposer",
    "research-executor": "research_executor",
    "research_executor": "research_executor",
    "evidence_runner": "research_executor",
    "evidence-runner": "research_executor",
    "runner": "research_executor",
    "evaluator-promoter": "evaluator_promoter",
    "evaluator_promoter": "evaluator_promoter",
    "evidence_verifier": "evaluator_promoter",
    "evidence-verifier": "evaluator_promoter",
    "verifier": "evaluator_promoter",
    "evidence-promoter": "evaluator_promoter",
}

AUTO_RESEARCH_ROLE_PROFILES: dict[str, dict[str, object]] = {
    "research_curator": {
        "phase": "contract",
        "allowed_actions": ["write_research_contract", "review_research_contract"],
        "write_scope": ["research_contract_v0", "todo_item_v0"],
        "handoff": ["Create the first hypothesis-proposer todo."],
        "successor_todos": [
            _successor("review_research_contract", AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION, "hypothesis-proposer", "hypothesis_proposer", "propose_hypothesis", AUTO_RESEARCH_REFINED_HYPOTHESIS_SUCCESSOR_TEXT),
        ],
    },
    "hypothesis_proposer": {
        "phase": "hypothesis",
        "allowed_actions": ["propose_hypothesis", "review_hypothesis_frontier"],
        "write_scope": ["research_hypothesis_v0", "todo_item_v0"],
        "handoff": ["Create or unblock a research-executor todo."],
        "successor_todos": [
            _successor("propose_hypothesis", AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_CONDITION, "research-executor", "research_executor", "run_dev_eval", AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_TEXT),
            _successor("propose_hypothesis", AUTO_RESEARCH_REFINED_DEV_SUCCESSOR_CONDITION, "evaluator-promoter", "evaluator_promoter", "review_promotion_readiness", AUTO_RESEARCH_PROMOTION_READINESS_REVIEW_SUCCESSOR_TEXT),
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
            _successor("run_dev_eval", AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION, "research-executor", "research_executor", "run_holdout_eval", AUTO_RESEARCH_HOLDOUT_SUCCESSOR_TEXT),
            _successor("run_holdout_eval", AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_CONDITION, "evaluator-promoter", "evaluator_promoter", "write_evaluation_summary", AUTO_RESEARCH_VALIDATED_SUMMARY_SUCCESSOR_TEXT),
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
            _successor("summarize_evidence", AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION, "research-curator", "research_curator", "review_research_contract", AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT),
            _successor("summarize_evidence", AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION, "hypothesis-proposer", "hypothesis_proposer", "review_hypothesis_frontier", AUTO_RESEARCH_HYPOTHESIS_FRONTIER_REVIEW_SUCCESSOR_TEXT),
            _successor("summarize_evidence", AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION, "research-curator", "research_curator", "review_research_contract", AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT),
            _successor("write_evaluation_summary", AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION, "research-curator", "research_curator", "review_research_contract", AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT),
            _successor("review_promotion_readiness", AUTO_RESEARCH_NEXT_HYPOTHESIS_SUCCESSOR_CONDITION, "research-curator", "research_curator", "review_research_contract", AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT),
            _successor("review_promotion_readiness", AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION, "research-curator", "research_curator", "review_research_contract", AUTO_RESEARCH_CURATOR_REVIEW_SUCCESSOR_TEXT),
            _successor("review_promotion_readiness", AUTO_RESEARCH_HOLDOUT_SUCCESSOR_CONDITION, "hypothesis-proposer", "hypothesis_proposer", "review_hypothesis_frontier", AUTO_RESEARCH_HYPOTHESIS_FRONTIER_REVIEW_SUCCESSOR_TEXT),
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
    "write_research_contract": "Write the public-safe research contract for the shared demo hypothesis.",
    "propose_hypothesis": "Map the first shared idea into a todo-backed research hypothesis.",
    "claim_attempt": "Claim one visible attempt boundary for the selected hypothesis.",
    "run_dev_eval": "Run the selected hypothesis on the dev split, write public-safe evidence, append it, and capture live evidence.",
    "run_holdout_eval": "Run held-out validation for the dev-supported hypothesis, append public-safe evidence, and summarize promotion readiness.",
    "write_evaluation_summary": "Verify the evidence packet and open the next validation or promotion gate.",
    "summarize_evidence": "Summarize dev evidence and hand off holdout validation when the hypothesis is supported.",
    "review_research_contract": "Re-check the research contract and protected scope for the next collective round.",
    "review_hypothesis_frontier": "Review the hypothesis frontier and record whether another bounded candidate is needed.",
    "review_promotion_readiness": "Review promotion readiness and record the current evidence gap.",
}

KNN_DEMO_VISIBLE_FIRST_STEP_COMMON = (
    "Read research_contract.public.json before claiming scope or metric facts.",
    "Do not treat $LOOPX_PANE_A2A_TICK output as research evidence.",
    (
        "Before claiming progress, leave one role-specific public-safe artifact, "
        "todo update, or evidence packet that another pane can use."
    ),
)

KNN_DEMO_VISIBLE_FIRST_STEPS_BY_ROLE = {
    "research_curator": (
        (
            "Write a compact contract note: metric direction, editable file, "
            "protected files, dev/test gates, and promotion rule."
        ),
        (
            "If the first hypothesis todo is missing, add a hypothesis-proposer "
            "todo for two exact-KNN speedup hypotheses and cite the contract note."
        ),
    ),
    "hypothesis_proposer": (
        (
            "Inspect solution.py, task.py, and eval.py; produce a two-row "
            "hypothesis table with mechanism, expected speed source, correctness "
            "risk, and eval command."
        ),
        (
            "Route exactly one dev-attempt todo to research-executor and keep "
            "the rejected/backup hypothesis visible as a retry candidate."
        ),
    ),
    "research_executor": (
        (
            "Run `bash eval.sh dev` before editing and save the last JSON line "
            "as baseline dev evidence."
        ),
        (
            "Edit only solution.py for one exact-KNN optimization, rerun "
            "`bash eval.sh dev`, and record the command, score, and diff summary."
        ),
        (
            "After a dev improvement, run `bash eval.sh test`, save both JSON "
            "outputs, and feed the real evaluator JSON to `loopx auto-research evidence`."
        ),
    ),
    "evaluator_promoter": (
        (
            "Only when your own evaluator todo is runnable, read executor evidence "
            "and classify it; if no todo is selected, wait for research-executor "
            "evidence instead of closing the evaluator todo."
        ),
        (
            "Write a verdict with split label, metric direction, protected-scope "
            "cleanliness, and next successor/retry todo; do not promote without "
            "`bash eval.sh test` output."
        ),
    ),
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
        "continuation_policy": dict(AUTO_RESEARCH_CONTINUATION_POLICY),
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


def knn_demo_visible_first_steps(role_id: str) -> list[str]:
    """Return compact KNN-demo role hints; execution stays in visible panes."""

    return [
        *KNN_DEMO_VISIBLE_FIRST_STEP_COMMON,
        *KNN_DEMO_VISIBLE_FIRST_STEPS_BY_ROLE.get(role_id, ()),
    ]
