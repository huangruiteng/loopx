from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION = "tui_multi_agent_runner_contract_v0"
INTERACTIVE_TUI_CONTRACT_SCHEMA_VERSION = "multi_agent_visible_interactive_tui_contract_v0"
VISIBLE_LAUNCHER_ACCEPTANCE_CONTRACT_SCHEMA_VERSION = (
    "multi_agent_visible_launcher_acceptance_contract_v0"
)
DECENTRALIZED_A2A_DRIVER_CONTRACT_SCHEMA_VERSION = (
    "multi_agent_decentralized_a2a_driver_contract_v0"
)
GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION = "generic_multi_agent_role_profile_v0"
GENERIC_MULTI_AGENT_COMPACT_STATUS_SCHEMA_VERSION = "generic_multi_agent_compact_status_v0"
THREE_LAYER_MINIMALITY_CONTRACT_SCHEMA_VERSION = (
    "multi_agent_three_layer_minimality_contract_v0"
)
GENERIC_MULTI_AGENT_DEFAULT_KERNEL_SKILLS = ("loopx-project", "loopx-doc-registry")

PANE_LOCAL_A2A_WAKEUP_PROMPT = (
    "LoopX pane-local A2A wakeup: read $LOOPX_CODEX_TUI_PROMPT_ARTIFACT for role/scope if needed. "
    "Treat this fixed wake as a fresh decentralized round. "
    "Inspect $LOOPX_PANE_TICK_SUMMARY only as your own prior pane-local tick evidence, then read your own LoopX quota/frontier. "
    "Run the bounded $LOOPX_PANE_A2A_TICK once when your own state shows runnable work or the user asked for another round. "
    "Use only your own LOOPX_GOAL_ID/LOOPX_AGENT_ID quota/frontier; "
    "if no runnable frontier remains, stay quiet with a brief no-action note; "
    "if advanced, summarize public evidence and next handoff. "
    "Honor the role prompt's human output language for summaries while keeping machine artifact schema keys unchanged. "
    "Do not ask the broadcaster for direction; LoopX state is the source of truth."
)

GENERIC_MULTI_AGENT_KERNEL_MECHANICS = (
    "multi_agent_runner",
    "real_codex_tui_panes",
    "workspace_and_trust_safe_launch",
    "decentralized_a2a_driver",
    "pane_local_a2a_tick",
    "todo_evidence_status_protocol",
    "compact_human_status",
    "default_role_prompt_scaffolding",
)


def positive_int_value(value: object, *, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        return default
    return parsed if parsed > 0 else default


def as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def role_skill_profile(skill: object) -> dict[str, str]:
    if not skill:
        return {}
    if isinstance(skill, str):
        source = skill.strip()
        if not source:
            return {}
        name = Path(source).parent.name or Path(source).stem or "worker-skill"
        return {"required_skill": name, "worker_skill_source": source}
    if not isinstance(skill, dict):
        return {}
    name = str(skill.get("name") or skill.get("skill_name") or "").strip()
    source = str(skill.get("source") or skill.get("path") or "").strip()
    if not name and source:
        name = Path(source).parent.name or Path(source).stem
    if not name or not source:
        return {}
    return {"required_skill": name, "worker_skill_source": source}


def build_generic_role_profile(
    *,
    role_id: str,
    agent_id: str,
    scope: str,
    responsibility: str,
    handoff_hints: list[str],
    skill_profile: dict[str, str],
    extra_profile: object = None,
) -> dict[str, object]:
    role_profile: dict[str, object] = {
        "schema_version": GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION,
        "role_id": role_id,
        "agent_id": agent_id,
        "agent_scope": scope,
        "responsibility": responsibility,
        "handoff_hints": handoff_hints,
        "default_kernel_skills": list(GENERIC_MULTI_AGENT_DEFAULT_KERNEL_SKILLS),
    }
    if isinstance(extra_profile, dict):
        role_profile.update(extra_profile)
    role_profile.update(skill_profile)
    return role_profile


def generic_role_prompt(
    *,
    goal_id: str,
    agent_id: str,
    role_id: str,
    scope: str,
    handoff_hints: list[str],
    skill_name: str | None,
    output_language: str | None = None,
) -> str:
    lines = [
        "LoopX multi-agent role",
        f"Goal: {goal_id}",
        f"Agent: {agent_id}",
        f"Role: {role_id}",
    ]
    if scope:
        lines.extend(["", "Scope:", scope])
    if skill_name:
        lines.extend(["", "Local skill:", f"Use ${skill_name} when it applies to this role."])
    if output_language:
        language_label = "Chinese" if output_language == "zh" else "English"
        lines.extend(
            [
                "",
                "Human output language:",
                (
                    f"- Use {language_label} for human-readable progress, summaries, "
                    "and blockers in this pane."
                ),
                "- Keep LoopX commands, schema keys, todo ids, and artifact filenames unchanged.",
            ]
        )
    lines.extend(
        [
            "",
            "Default LoopX skills:",
            "- Use $loopx-project for LoopX state, quota/frontier, todo, rationale, and repo-goal coordination.",
            "- Use $loopx-doc-registry when durable project material, wiki/doc authority, or source registration matters.",
            "- Keep worker-local skills focused on role semantics; generic LoopX mechanics belong to the kernel prompt and state.",
        ]
    )
    lines.extend(
        [
            "",
            "How to work:",
            "- Treat LoopX state as the shared A2A surface.",
            "- This Codex TUI owns the first visible tick; run `$LOOPX_PANE_A2A_TICK` once before summarizing when runnable work remains.",
            "- Treat `$LOOPX_PANE_TICK_SUMMARY` as previous pane-local evidence; it is not a gate that cancels later fixed wakes.",
            "- On each fixed wake, read your own LoopX quota/frontier and run the bounded `$LOOPX_PANE_A2A_TICK` once when runnable work remains or the user asks for another round.",
            "- If no runnable frontier remains, stay quiet with a brief no-action note.",
            "- The tick reads your quota/frontier and then runs this role's worker-turn when configured.",
            "- When the tick completes, summarize what changed, what remains blocked, and stay interactive for user takeover.",
            "- For machine reads, run `$LOOPX_PANE_LOOPX_JSON` as the command and redirect output into `$LOOPX_PANE_ARTIFACT_DIR/<name>.public.json`; it defaults to `--format json`.",
            "- Never write output to `$LOOPX_PANE_LOOPX_JSON`; it is the executable wrapper, not an artifact path.",
            "- Write compact public-safe evidence before completing or handing off a todo.",
            "- The user may type into this pane; respond like a normal Codex CLI agent.",
        ]
    )
    if handoff_hints:
        lines.append("")
        lines.append("Handoff hints:")
        lines.extend(f"- {hint}" for hint in handoff_hints)
    return "\n".join(lines)


def build_decentralized_a2a_driver_contract(
    *,
    wake_command: str = "loopx multi-agent wake --session-name <session>",
) -> dict[str, object]:
    """Describe the reusable fixed-prompt driver for live Codex TUI agents."""

    return {
        "schema_version": DECENTRALIZED_A2A_DRIVER_CONTRACT_SCHEMA_VERSION,
        "owner_layer": "generic_multi_agent_kernel",
        "driver_model": "fixed_prompt_broadcast_plus_pane_local_state_tick",
        "coordination_pattern": "decentralized_state_a2a",
        "prompt": {
            "owner_layer": "generic_multi_agent_kernel",
            "trigger": PANE_LOCAL_A2A_WAKEUP_PROMPT,
            "instruction_only": True,
            "frontier_embedded": False,
            "todo_embedded": False,
            "target_role_embedded": False,
            "target_role_artifact_ref": "$LOOPX_CODEX_TUI_PROMPT_ARTIFACT",
            "tick_summary_ref": "$LOOPX_PANE_TICK_SUMMARY",
            "wake_round": "fresh_agent_scoped_quota_frontier_check",
            "tick_summary_semantics": "prior_pane_tick_evidence_not_a_tick_skip_gate",
        },
        "broadcaster": {
            "command": wake_command,
            "model": "fixed_prompt_broadcast",
            "reads_frontier": False,
            "selects_todo": False,
            "runs_worker_turn": False,
            "writes_loopx_state": False,
            "spends_quota": False,
            "decides_work": False,
        },
        "pane": {
            "decision_owner": "codex_tui_agent_via_loopx_state",
            "tick_command": "$LOOPX_PANE_A2A_TICK",
            "first_action": "codex_tui_first_turn_tick",
            "cadence_action": "fixed_prompt_wakeup_then_own_quota_frontier_tick_when_runnable",
            "reads": [
                "own_LOOPX_GOAL_ID",
                "own_LOOPX_AGENT_ID",
                "own_quota_should_run",
                "own_agent_scoped_frontier",
                "own_prior_tick_summary_evidence",
            ],
            "may_run": ["LOOPX_PANE_WORKER_TURN", "LOOPX_PANE_WORKER_LOOP"],
            "writes": ["public_safe_evidence", "todo_completion_when_worker_turn_configured"],
            "rounds_env": "LOOPX_PANE_TICK_ROUNDS",
            "rounds_artifact": "$LOOPX_PANE_ARTIFACT_DIR/pane-a2a-rounds.public.json",
        },
        "layer_budget": {
            "user_layer": ["goal_id", "roles", "optional_overrides"],
            "preset_layer": ["domain_roles", "handoff_hints", "worker_turn_command"],
            "kernel_layer": [
                "tmux_codex_tui_lifecycle",
                "fixed_prompt_wakeup",
                "pane_local_tick_runtime",
                "loopx_state_protocol",
            ],
        },
        "acceptance": {
            "broadcaster_is_not_workflow": True,
            "no_leader_frontier_scan": True,
            "each_pane_decides_from_state": True,
            "tick_summary_does_not_gate_wake_tick": True,
            "tui_first_turn_owns_tick": True,
            "user_and_preset_do_not_own_tick_driver": True,
        },
    }


def build_tui_multi_agent_runner_contract(
    *,
    session_name: str,
    lane_count: int,
    attach_command: str,
    stop_command: str,
    retry_command: str,
    all_lane_workspace_isolation: bool,
) -> dict[str, object]:
    """Describe the reusable visible-TUI runner without domain-specific steps."""

    driver_contract = build_decentralized_a2a_driver_contract()
    return {
        "schema_version": TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
        "runner_surface": "tmux_codex_cli_tui",
        "coordination_model": {
            "leader_required": False,
            "state_bus": "loopx_registry_runtime_todo_quota_frontier",
            "selection": "agent_scoped_quota_should_run_frontier",
            "handoff": "todo_and_public_safe_evidence",
        },
        "tmux_lifecycle": {
            "session_name": session_name,
            "lane_count": lane_count,
            "one_window_per_role": False,
            "single_window_tiled_role_panes": True,
            "remain_on_exit": True,
            "replace_existing": "execute_flag_only",
            "attach_command": attach_command,
            "stop_command": stop_command,
            "retry_command": retry_command,
        },
        "lane_runtime_env": {
            "shared": [
                "LOOPX_PROJECT",
                "LOOPX_REGISTRY",
                "LOOPX_RUNTIME_ROOT",
                "LOOPX_VISIBLE_SESSION",
                "LOOPX_VISIBLE_ARTIFACT_DIR",
            ],
            "role_identity": [
                "LOOPX_ROLE_ID",
                "LOOPX_ROLE_PROFILE_REF",
                "LOOPX_ROLE_PROFILE_ARTIFACT",
                "LOOPX_GOAL_ID",
                "LOOPX_AGENT_ID",
            ],
            "pane_tools": [
                "LOOPX_PANE_LOOPX",
                "LOOPX_PANE_LOOPX_JSON",
                "LOOPX_PANE_ARTIFACT_DIR",
                "LOOPX_PANE_A2A_TICK",
                "LOOPX_PANE_BOOTSTRAP_PROMPT",
                "LOOPX_PANE_TICK_SUMMARY",
                "LOOPX_PANE_TICK_OUTPUT_ARTIFACT",
                "LOOPX_PANE_WORKER_TURN",
                "LOOPX_PANE_WORKER_LOOP",
            ],
            "workspace_policy": (
                "shared_goal_surface_by_default; mutating lanes may opt into lane workspaces"
            ),
            "all_lane_workspace_isolation": all_lane_workspace_isolation,
        },
        "role_prompt_and_skill": {
            "bootstrap_prompt": "written_to_public_artifact_for_fixed_wake_context",
            "role_profile": "role-local public json artifact",
            "default_kernel_skills": list(GENERIC_MULTI_AGENT_DEFAULT_KERNEL_SKILLS),
            "default_kernel_skill_policy": {
                "owner_layer": "generic_multi_agent_kernel",
                "injected_via": "generic_role_prompt",
                "preset_should_not_repeat_skill_playbooks": True,
                "worker_skill_scope": "role_specific_semantics_and_successor_declarations",
            },
            "fixed_wake_prompt_owner": "generic_multi_agent_kernel",
            "skill_materialization": ".codex/skills/<skill>/SKILL.md",
            "worker_local_skill_scope": "role_specific_semantics_only",
        },
        "decentralized_a2a_driver": driver_contract,
        "pane_local_a2a": {
            "tick_command": driver_contract["pane"]["tick_command"],
            "first_action": (
                "Codex TUI first turn runs $LOOPX_PANE_A2A_TICK; "
                "later live wakes check own quota/frontier and tick when runnable"
            ),
            "cadence_wakeup_command": driver_contract["broadcaster"]["command"],
            "cadence_wakeup_model": driver_contract["broadcaster"]["model"],
            "cadence_broadcaster_decides_work": driver_contract["broadcaster"]["decides_work"],
            "reads": ["own prior tick evidence", "own quota should-run", "own agent-scoped frontier"],
            "runs": driver_contract["pane"]["may_run"],
            "bounded_rounds_env": driver_contract["pane"]["rounds_env"],
            "rounds_artifact": driver_contract["pane"]["rounds_artifact"],
            "tick_summary": "$LOOPX_PANE_TICK_SUMMARY",
            "tick_output": "$LOOPX_PANE_TICK_OUTPUT_ARTIFACT",
            "machine_json_policy": "file_or_explicit_machine_channel_only",
            "machine_json_destination": "$LOOPX_PANE_ARTIFACT_DIR/*.public.json",
            "human_default": "markdown_status_inside_codex_tui",
        },
        "user_takeover": {
            "interactive_codex_tui": True,
            "may_type_into_each_role": True,
            "attach": attach_command,
            "stop": stop_command,
        },
        "debug_artifacts": {
            "machine_json": "redirected_public_artifacts_only",
            "launcher_scripts": "runtime_local_debug_files",
            "raw_transcripts": False,
            "credentials": False,
        },
        "boundaries": {
            "domain_specific_research_logic": False,
            "runs_agent_processes_in_dry_run": False,
            "writes_loopx_state_in_dry_run": False,
            "spends_quota_in_dry_run": False,
        },
    }


def build_three_layer_minimality_contract(
    *,
    product_id: str,
    preset_id: str,
    user_intent_fields: Iterable[object] | None = None,
    preset_responsibilities: Iterable[object] | None = None,
    preset_forbidden_mechanics: Iterable[object] | None = None,
    kernel_mechanics: Iterable[object] | None = None,
    extension_points: Iterable[object] | None = None,
) -> dict[str, object]:
    """Describe how a product preset stays thin on the generic kernel.

    The contract is intentionally product-agnostic: callers supply the preset's
    domain responsibilities, while this module records the shared mechanics that
    must remain in the reusable multi-agent kernel.
    """

    intent_fields = as_string_list(user_intent_fields) or ["objective"]
    preset_owns = as_string_list(preset_responsibilities)
    kernel_owns = as_string_list(kernel_mechanics) or list(GENERIC_MULTI_AGENT_KERNEL_MECHANICS)
    forbidden = as_string_list(preset_forbidden_mechanics) or kernel_owns
    extensions = as_string_list(extension_points)
    return {
        "schema_version": THREE_LAYER_MINIMALITY_CONTRACT_SCHEMA_VERSION,
        "product_id": product_id,
        "preset_id": preset_id,
        "principle": "user_and_preset_stay_thin_kernel_owns_reusable_mechanics",
        "line_budget_goal": {
            "user_layer": "few_field_intent_or_config",
            "preset_layer": "small_domain_defaults_and_handoff_contract",
            "kernel_layer": "shared_multi_agent_runtime_and_state_protocol",
        },
        "user_layer": {
            "owns": "intent",
            "fields": intent_fields,
            "forbidden": [
                "tmux_or_process_lifecycle",
                "quota_frontier_protocol_details",
                "pane_local_tick_commands",
                "raw_worker_or_status_plumbing",
            ],
        },
        "preset_layer": {
            "owns": preset_owns,
            "forbidden": forbidden,
            "role_skill_limit": "role_specific_semantics_and_successor_declarations_only",
            "must_remain_reusable": True,
        },
        "kernel_layer": {
            "owns": kernel_owns,
            "default_skills": list(GENERIC_MULTI_AGENT_DEFAULT_KERNEL_SKILLS),
            "fixed_wake_prompt": "PANE_LOCAL_A2A_WAKEUP_PROMPT",
            "cross_product_reuse_required": True,
        },
        "extension_points": extensions,
        "acceptance": {
            "user_can_copy_small_recipe": True,
            "preset_has_no_runner_process_logic": True,
            "kernel_contract_is_domain_agnostic": True,
            "other_multi_agent_products_can_reuse_kernel": True,
        },
    }


def build_compact_human_status(payload: dict[str, object]) -> dict[str, object]:
    """Return the small status shape a product surface can show before attach."""

    lanes = [lane for lane in payload.get("lanes", []) if isinstance(lane, dict)]
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    runner = payload.get("runner_contract") if isinstance(payload.get("runner_contract"), dict) else {}
    driver = (
        runner.get("decentralized_a2a_driver")
        if isinstance(runner.get("decentralized_a2a_driver"), dict)
        else {}
    )
    session = str(payload.get("session_name") or "")
    role_summaries = []
    for lane in lanes:
        pane = lane.get("pane_local_a2a") if isinstance(lane.get("pane_local_a2a"), dict) else {}
        role_summaries.append(
            {
                "lane_id": lane.get("lane_id"),
                "role_id": lane.get("role_id"),
                "agent_id": lane.get("agent_id"),
                "scope": lane.get("agent_scope"),
                "tick": pane.get("tick_command") or "$LOOPX_PANE_A2A_TICK",
                "worker_turn_configured": bool(pane.get("worker_turn_configured")),
                "worker_loop_configured": bool(pane.get("worker_loop_configured")),
            }
        )
    return {
        "schema_version": GENERIC_MULTI_AGENT_COMPACT_STATUS_SCHEMA_VERSION,
        "summary": (
            f"{len(role_summaries)} interactive Codex TUI role(s)"
            + (f" in tmux session {session}" if session else "")
        ),
        "goal_id": payload.get("goal_id"),
        "mode": payload.get("mode"),
        "session_name": session,
        "role_count": len(role_summaries),
        "roles": role_summaries,
        "attach": commands.get("attach"),
        "stop": commands.get("stop"),
        "first_action": "$LOOPX_PANE_A2A_TICK",
        "driver_model": driver.get("driver_model")
        or "fixed_prompt_broadcast_plus_pane_local_state_tick",
        "coordination_pattern": driver.get("coordination_pattern")
        or "decentralized_state_a2a",
        "machine_json_policy": "artifact_only_in_visible_panes",
        "user_takeover": "attach to the session and type into any role pane",
    }
