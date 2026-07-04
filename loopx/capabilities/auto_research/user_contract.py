from __future__ import annotations

import shlex
from typing import Any

from .preset import build_auto_research_minimal_a2a_recipe


AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION = "auto_research_user_contract_v0"


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


def _language_flag(question: str, *, output_language: str) -> str:
    resolved = infer_auto_research_output_language(
        question,
        output_language=output_language,
    )
    return f" --language {shlex.quote(resolved)}" if resolved != "en" else ""


def build_auto_research_user_contract(
    open_question: str,
    *,
    max_todos: int = 5,
    output_language: str = "auto",
) -> dict[str, Any]:
    question = " ".join(str(open_question or "").strip().split())
    if not question:
        raise ValueError('auto-research requires an open question, e.g. loopx auto-research "..."')
    todo_limit = min(max(1, int(max_todos)), 5)
    resolved_language = infer_auto_research_output_language(
        question,
        output_language=output_language,
    )
    action_plan = [
        {
            "priority": "P0",
            "todo": "Define the research brief and claim boundary before making factual claims.",
            "owner_layer": "auto_research_preset",
        },
        {
            "priority": "P0",
            "todo": "Collect evidence refs from allowed code, docs, benchmarks, issues, and PRs.",
            "owner_layer": "generic_kernel_agents",
        },
        {
            "priority": "P1",
            "todo": "Run a decentralized multi-agent pass: research-curator frames the boundary, hypothesis-proposer grows claims, research-executor gathers evidence, and evaluator-promoter checks promotion readiness.",
            "owner_layer": "generic_kernel_runner",
        },
        {
            "priority": "P1",
            "todo": "Produce the next executable step and say whether it can run automatically.",
            "owner_layer": "auto_research_preset",
        },
        {
            "priority": "P2",
            "todo": "Summarize gates and unresolved evidence gaps without expanding the user contract.",
            "owner_layer": "auto_research_preset",
        },
    ][:todo_limit]
    language_flag = _language_flag(question, output_language=resolved_language)
    start_command = (
        f"loopx auto-research start {shlex.quote(question)}{language_flag} --execute"
    )
    takeover_command = f"{start_command} --attach"
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
        "minimal_a2a_recipe": build_auto_research_minimal_a2a_recipe(
            open_question=question,
            output_language=resolved_language,
        ),
        "command_contract": {
            "canonical_invocation": 'loopx auto-research "<open question>"',
            "explicit_invocation": 'loopx auto-research contract "<open question>"',
            "one_click_start_invocation": 'loopx auto-research start "<open question>" --execute',
            "user_required_inputs": ["open_question"],
            "user_optional_inputs": ["output_language"],
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
            "command_template": 'loopx auto-research start "<open question>" --execute',
            "command": start_command,
            "operator_takeover_command_template": (
                'loopx auto-research start "<open question>" --execute --attach'
            ),
            "operator_takeover_command": takeover_command,
            "preview_command_template": 'loopx auto-research start "<open question>"',
            "preview_command": (
                f"loopx auto-research start {shlex.quote(question)}{language_flag}"
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
