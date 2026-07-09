from __future__ import annotations

import shlex
from collections.abc import Iterable

from .defaults import AUTO_RESEARCH_DEFAULT_GOAL_ID
from .role_profiles import (
    AUTO_RESEARCH_DEFAULT_LANES,
    AUTO_RESEARCH_REQUIRED_HOLDOUT_IMPROVEMENTS,
    AUTO_RESEARCH_REQUIRED_SKILL,
    AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION,
    AUTO_RESEARCH_WORKER_SKILL_SOURCE,
    auto_research_role_id,
    auto_research_role_id_for_action,
    auto_research_role_profile,
    auto_research_seed_action_for_role,
    auto_research_seed_title,
    auto_research_successor_specs_for_action,
    knn_demo_visible_first_steps,
)
from ..multi_agent.recipe import (
    build_minimal_decentralized_a2a_recipe,
    parse_multi_agent_role_spec_lines,
)


AUTO_RESEARCH_PRESET_SCHEMA_VERSION = "auto_research_thin_preset_v0"
AUTO_RESEARCH_MINIMAL_A2A_RECIPE_SCHEMA_VERSION = "auto_research_minimal_a2a_recipe_v0"


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


def build_auto_research_preset_role(
    *,
    lane: dict[str, str],
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    reasoning_effort: str = "high",
    output_language: str = "en",
    open_question: object | None = None,
    preset_context: dict[str, object] | None = None,
) -> dict[str, object]:
    role_id = lane["role_id"]
    agent_id = lane["agent_id"]
    role_profile = auto_research_role_profile(
        role_id=role_id,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    role_profile["output_language"] = output_language
    if str(open_question or "").strip():
        role_profile["open_question"] = str(open_question).strip()
    if preset_context:
        role_profile["preset_context"] = dict(preset_context)
        if str(preset_context.get("preset_id") or "") == "knn-demo":
            role_profile["visible_first_steps"] = knn_demo_visible_first_steps(role_id)
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
        "reasoning_effort": reasoning_effort,
    }


def build_auto_research_preset_summary(
    *,
    role_count: int,
    open_question: object | None = None,
    output_language: str = "en",
    role_specs: Iterable[object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
        "minimal_a2a_recipe": build_auto_research_minimal_a2a_recipe(
            open_question=open_question,
            output_language=output_language,
            role_specs=role_specs,
        ),
        "owns": [
            "research_roles",
            "handoff_hints",
            "metric_contract_hints",
            "domain_defaults",
        ],
        "forbidden": [
            "multi_agent_runner",
            "real_codex_tui_panes",
            "workspace_and_trust_safe_launch",
            "decentralized_a2a_driver",
            "pane_local_a2a_status_check",
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
