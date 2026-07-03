from __future__ import annotations

import shlex
from typing import Any


AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION = "auto_research_user_contract_v0"


def build_auto_research_user_contract(
    open_question: str,
    *,
    max_todos: int = 5,
) -> dict[str, Any]:
    question = " ".join(str(open_question or "").strip().split())
    if not question:
        raise ValueError('auto-research requires an open question, e.g. loopx auto-research "..."')
    todo_limit = min(max(1, int(max_todos)), 5)
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
            "todo": "Run a decentralized multi-agent pass: curator maps sources, mapper proposes claims, runner gathers evidence, verifier checks boundaries.",
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
    start_command = f"loopx auto-research start {shlex.quote(question)} --execute"
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_USER_CONTRACT_SCHEMA_VERSION,
        "mode": "user_contract",
        "product_id": "auto-research",
        "open_question": question,
        "layering": {
            "user_layer": "one open question",
            "auto_research_layer": "fixed output contract only",
            "kernel_layer": "multi-agent runner, Codex TUI panes, pane-local tick, todo/evidence/status protocol",
        },
        "command_contract": {
            "canonical_invocation": 'loopx auto-research "<open question>"',
            "explicit_invocation": 'loopx auto-research contract "<open question>"',
            "one_click_start_invocation": 'loopx auto-research start "<open question>" --execute',
            "user_required_inputs": ["open_question"],
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
            "preview_command_template": 'loopx auto-research start "<open question>"',
            "preview_command": f"loopx auto-research start {shlex.quote(question)}",
            "starts": "visible_codex_tui_lanes",
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
