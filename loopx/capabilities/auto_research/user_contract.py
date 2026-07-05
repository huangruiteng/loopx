from __future__ import annotations

import shlex

from .defaults import (
    AUTO_RESEARCH_KNN_DEMO_CONTEXT,
    AUTO_RESEARCH_KNN_DEMO_PRESET_ID,
    AUTO_RESEARCH_SUPPORTED_PRESET_IDS,
)

AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION = "auto_research_user_contract_v0"


def normalize_auto_research_preset_id(preset_id: str | None) -> str | None:
    text = str(preset_id or "").strip()
    if not text:
        return None
    if text not in AUTO_RESEARCH_SUPPORTED_PRESET_IDS:
        supported = ", ".join(AUTO_RESEARCH_SUPPORTED_PRESET_IDS)
        raise ValueError(f"unsupported auto-research preset {text!r}; supported: {supported}")
    return text


def build_auto_research_preset_context(preset_id: str | None) -> dict[str, object] | None:
    normalized = normalize_auto_research_preset_id(preset_id)
    if normalized == AUTO_RESEARCH_KNN_DEMO_PRESET_ID:
        return dict(AUTO_RESEARCH_KNN_DEMO_CONTEXT)
    return None


def infer_auto_research_output_language(
    open_question: str,
    *,
    output_language: str = "auto",
) -> str:
    requested = str(output_language or "auto").strip().lower()
    if requested in {"zh", "en"}:
        return requested
    question = str(open_question or "")
    return "zh" if any("\u4e00" <= char <= "\u9fff" for char in question) else "en"


def build_auto_research_user_contract(
    open_question: str,
    *,
    max_todos: int = 5,
    output_language: str = "auto",
    preset_id: str | None = None,
) -> dict[str, object]:
    question = " ".join(str(open_question or "").strip().split())
    if not question:
        raise ValueError('auto-research requires an open question, e.g. loopx auto-research "..."')
    preset_context = build_auto_research_preset_context(preset_id)
    normalized_preset_id = (
        str(preset_context.get("preset_id")) if preset_context else None
    )
    todo_limit = min(max(1, int(max_todos)), 5)
    resolved_language = infer_auto_research_output_language(
        question,
        output_language=output_language,
    )
    action_plan = [
        {"priority": priority, "todo": todo, "owner_layer": owner}
        for priority, todo, owner in [
            ("P0", "Define the research brief and claim boundary before making factual claims.", "auto_research_preset"),
            ("P0", "Collect evidence refs from allowed code, docs, benchmarks, issues, and PRs.", "generic_kernel_agents"),
            ("P1", "Run a decentralized multi-agent pass: research-curator frames the boundary, hypothesis-proposer grows claims, research-executor gathers evidence, and evaluator-promoter checks promotion readiness.", "generic_kernel_runner"),
            ("P1", "Produce the next executable step and say whether it can run automatically.", "auto_research_preset"),
            ("P2", "Summarize gates and unresolved evidence gaps without expanding the user contract.", "auto_research_preset"),
        ][:todo_limit]
    ]
    preset_flag = (
        f" --preset {shlex.quote(normalized_preset_id)}"
        if normalized_preset_id
        else ""
    )
    language_flag = f" --language {shlex.quote(resolved_language)}" if resolved_language != "en" else ""
    start_command = (
        f"loopx auto-research start {shlex.quote(question)}{preset_flag}{language_flag} --execute"
    )
    takeover_command = f"{start_command} --attach"
    command_template = (
        f'loopx auto-research start "<open question>"{preset_flag} --execute'
    )
    preview_template = f'loopx auto-research start "<open question>"{preset_flag}'
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION,
        "mode": "user_contract",
        "product_id": "auto-research",
        "open_question": question,
        "output_language": {
            "requested": str(output_language or "auto"),
            "resolved": resolved_language,
            "human_process_language": "Chinese" if resolved_language == "zh" else "English",
            "machine_schema_language": "English",
        },
        "layering": {
            "user_layer": "one open question",
            "auto_research_layer": "fixed output contract only",
            "kernel_layer": "multi-agent runner, Codex TUI panes, pane-local tick, todo/evidence/status protocol",
        },
        "command_contract": {
            "canonical_invocation": 'loopx auto-research "<open question>"',
            "explicit_invocation": 'loopx auto-research contract "<open question>"',
            "one_click_start_invocation": command_template,
            "user_required_inputs": ["open_question"],
            "user_optional_inputs": ["output_language", "preset"],
            "auto_research_required_outputs": [
                "research_brief",
                "action_plan",
                "evidence_refs",
                "next_executable_step",
                "gate",
            ],
            "max_action_plan_todos": 5,
        },
        "one_click_start": {
            "schema_version": "auto_research_one_click_start_v0",
            "command_template": command_template,
            "command": start_command,
            "operator_takeover_command_template": (
                f"{command_template} --attach"
            ),
            "operator_takeover_command": takeover_command,
            "preview_command_template": preview_template,
            "preview_command": (
                f"loopx auto-research start {shlex.quote(question)}{preset_flag}{language_flag}"
            ),
            "starts": "visible_codex_tui_lanes",
            "attach_semantics": (
                "--attach means operator takeover first; it skips the default evidence-first wake."
            ),
            "uses_generic_kernel": True,
            "coordination_model": "decentralized_state_a2a",
            "user_does_not_choose": [
                "agent_ids",
                "tmux_layout",
                "pane_tick_command",
                "evidence_packet_schema",
                "frontier_protocol",
            ],
        },
        **({"preset_context": preset_context} if preset_context else {}),
        "research_brief": {
            "read": [],
            "not_read": [
                "source code",
                "docs",
                "benchmarks",
                "issues",
                "pull requests",
            ],
            "claim_boundary": (
                "Initial contract only: no factual claim is accepted until it is backed "
                "by an evidence ref and checked by the verifier lane."
            ),
        },
        "action_plan": action_plan,
        "evidence_refs": {
            "code": [],
            "docs": [],
            "benchmarks": [],
            "issues": [],
            "pull_requests": [],
        },
        "next_executable_step": {
            "can_run_automatically": True,
            "step": (
                "Start with read-only evidence discovery and claim-boundary drafting. "
                "Escalate to the user only when private material, credentials, production "
                "actions, or destructive git operations are required."
            ),
        },
        "gate": {
            "user_judgment_needed": [
                "Which private or restricted sources, if any, are allowed.",
                "Whether production actions, credentialed connectors, or destructive git are allowed.",
                "Whether unresolved evidence gaps are acceptable for the final claim.",
            ],
            "default_without_user_gate": "public/read-only discovery plus local evidence draft",
        },
        "public_boundary": {
            "raw_logs": False,
            "private_material": False,
            "credentials": False,
            "destructive_git": False,
            "production_actions": False,
        },
    }
