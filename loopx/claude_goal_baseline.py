"""Claude Code goal-mode baseline — the honest counterpart of
``codex_goal_baseline``.

Codex exposes a NATIVE goal feature: an app-server JSON-RPC surface
(``thread/goal/set`` / ``thread/goal/get``) plus a ``/goal`` slash command. The
Codex baseline (``codex_goal_baseline.py``) speaks that protocol directly.

Claude Code has no equivalent native goal OBJECT, but it DOES have native
scheduling: ``/loop`` re-runs a prompt each iteration. So the supported loopx
surface on Claude Code is:

- **the run loop** = Claude Code's native ``/loop``, driven by a project
  ``.claude/loop.md`` that encodes the loopx tick protocol;
- **the control plane** = the loopx MCP tools (``should_run`` / ``claim_task`` /
  ``complete_task``), where ``should_run`` is the deterministic per-tick gate;
- ``/loopx`` writes the loop.md and registers the goal/agent;
- an OPTIONAL ``PreToolUse`` should_run gate (opt-in) adds per-tool enforcement.

This module makes that contract explicit and machine-checkable, mirroring the
shape of the Codex baseline so dashboards/regressions can treat both backends
uniformly. It does NOT pretend a native goal API exists.
"""
from __future__ import annotations

import hashlib
from typing import Any

CLAUDE_CODE_GOAL_BASELINE_SCHEMA_VERSION = "claude_code_goal_baseline_v0"
CLAUDE_CODE_GOAL_BASELINE_PROOF_SCHEMA_VERSION = "claude_code_goal_baseline_proof_v0"

# Claude Code seams loopx uses (vs Codex's native goal API).
CLAUDE_CODE_GOAL_SEAMS = (
    "native_loop_runtime",             # Claude Code /loop is the scheduler/executor
    "loop_md_tick_protocol",           # .claude/loop.md encodes the loopx tick
    "mcp_should_run_control_plane",    # should_run/claim/complete (should_run = the gate)
    "slash_command_loopx_setup",       # /loopx writes loop.md + registers goal/agent
    "optional_pretooluse_hardening",   # opt-in per-tool should_run gate
)


def stable_text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_claude_code_goal_baseline_plan(
    *,
    objective: str,
    status: str = "active",
    write_scope: list[str] | None = None,
    token_budget: int | None = None,
) -> dict[str, Any]:
    """Describe the supported Claude-Code goal-mode contract (no native API).

    Unlike Codex, there is no ``thread/goal/set`` to persist a goal inside the
    agent. Persistence + quota + gating live in loopx state, and the agent
    is gated/driven from outside.
    """
    objective_text = str(objective or "").strip()
    if not objective_text:
        raise ValueError("objective must be non-empty")
    if status not in {"active", "paused", "budgetLimited", "complete"}:
        raise ValueError(f"unsupported goal status: {status}")

    return {
        "schema_version": CLAUDE_CODE_GOAL_BASELINE_SCHEMA_VERSION,
        "surface": "claude_code",
        "baseline_mode": "claude_code_goal_mode",
        "native_goal_api_present": False,
        "native_api_note": (
            "Claude Code has no thread/goal/set equivalent; loopx uses native /loop as the "
            "runtime and the MCP should_run protocol as the per-tick gate (the PreToolUse "
            "hook is optional hardening)."
        ),
        "seams": list(CLAUDE_CODE_GOAL_SEAMS),
        "permission_model": "mcp_should_run_per_tick_gate_optional_pretooluse_hook",
        "loop_model": "native_loop_runtime",
        "persistence_owner": "loopx_state",  # registry + active state + run history
        "objective_sha256": stable_text_digest(objective_text),
        "objective_chars": len(objective_text),
        "status": status,
        "write_scope": list(write_scope or []),
        "token_budget_present": token_budget is not None,
        "claim_boundary": {
            "permission_decision_is_deterministic": True,
            "slash_goal_toggle_is_supported": True,
            "must_not_include_loopx_state_in_agent_prompt_secrets": True,
        },
    }


def build_claude_code_goal_baseline_proof(
    *,
    expected_objective: str,
    expected_status: str = "active",
    hook_installed: bool,
    hook_denied_out_of_scope: bool,
    hook_allowed_in_scope: bool,
    should_run_consulted: bool,
    todo_completed_via_cli_or_mcp: bool,
    used_unverified_prompt_only_loop: bool = False,
    included_loopx_state_in_prompt: bool = False,
) -> dict[str, Any]:
    """Reduce a goal-mode run into public-safe baseline evidence.

    A Claude-Code goal-mode baseline is credible only if the deterministic hook
    actually gated tools (allow in-scope, deny out-of-scope), the loop consulted
    ``should_run``, and a todo was advanced through the CLI/MCP (not via an
    unverified prompt-only loop).
    """
    deterministic_gate_evidence = bool(
        hook_installed and hook_denied_out_of_scope and hook_allowed_in_scope
    )
    loop_evidence = bool(should_run_consulted and todo_completed_via_cli_or_mcp)
    boundary_clean = not any([used_unverified_prompt_only_loop, included_loopx_state_in_prompt])
    baseline_claim_allowed = bool(deterministic_gate_evidence and loop_evidence and boundary_clean)

    return {
        "schema_version": CLAUDE_CODE_GOAL_BASELINE_PROOF_SCHEMA_VERSION,
        "surface": "claude_code",
        "baseline_mode": "claude_code_goal_mode",
        "native_goal_api_present": False,
        "deterministic_gate_evidence": deterministic_gate_evidence,
        "loop_evidence": loop_evidence,
        "baseline_claim_allowed": baseline_claim_allowed,
        "expected_objective_sha256": stable_text_digest(str(expected_objective or "")),
        "expected_status": expected_status,
        "checks": {
            "hook_installed": bool(hook_installed),
            "hook_denied_out_of_scope": bool(hook_denied_out_of_scope),
            "hook_allowed_in_scope": bool(hook_allowed_in_scope),
            "should_run_consulted": bool(should_run_consulted),
            "todo_completed_via_cli_or_mcp": bool(todo_completed_via_cli_or_mcp),
        },
        "negative_controls": {
            "prompt_only_loop": bool(used_unverified_prompt_only_loop),
            "included_loopx_state_in_prompt": bool(included_loopx_state_in_prompt),
        },
    }
