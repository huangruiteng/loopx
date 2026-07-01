#!/usr/bin/env python3
"""Smoke-test durable interaction-pattern documentation coverage."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "docs" / "interaction-pattern-catalog.md"
STATE_MODEL = REPO_ROOT / "docs" / "state-interaction-model.md"
SELF_REPAIR_PATTERNS = (
    REPO_ROOT
    / "skills"
    / "loopx-self-repair"
    / "references"
    / "repair-patterns.md"
)


def require(text: str, snippets: list[str], *, source: Path) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    catalog = CATALOG.read_text(encoding="utf-8")
    state_model = STATE_MODEL.read_text(encoding="utf-8")
    repair_patterns = SELF_REPAIR_PATTERNS.read_text(encoding="utf-8")

    require(
        catalog,
        [
            "## Pattern Families",
            "| Work Routing |",
            "| Human Decision |",
            "| State And Boundary |",
            "| Evidence Lifecycle |",
            "| Planning Governance |",
            "## Optional OM/HITL Overlay Schemas",
            "human_ai_role_contract_v0",
            "ops_metric_overlay_v0",
            "escalation_failure_type_v0",
            "These overlays are descriptive and analytic.",
            "The overlays should stay optional until a UI or controller path consumes them.",
            "IP-027 | Deferred Gate Resume",
            "Deferred todos represent parked work behind a resume gate.",
            "Ready deferred work is not a no-candidate state.",
            "Human Decision / gate-resume pattern, not a no-todo pattern.",
            "IP-029 | Handoff Todo Gate State",
            "`blocks_agent` todos are not only backlog rows.",
            "`todo_handoff_gate_v0`",
            "`cleared_without_successor`",
            "a current-agent\n`blocking` handoff wins over stale done handoffs",
            "state-machine bugs, not prompt wording bugs",
            "examples/quota-cleared-blocker-successor-gate-smoke.py",
            "When a user gate carries `blocks_agent=<agent-id>`",
            "agent-scoped user gate overreach",
            "not IP-026 scope exhaustion",
            "examples/quota-agent-scoped-user-gate-smoke.py",
            "docs/archive/incidents/agent-scoped-user-gate-overreach-incident-20260624.md",
            "IP-017 | User Reward Lesson Promotion",
            "IP-018 | Plan To Todo Writeback",
            "promote correction into durable lesson",
            "User-facing plans are not durable control-plane state by themselves",
            "writeback target",
            "IP-022 | Claimed Todo Visibility And Agent-Lane Next Action",
            "The same scoped identity must be carried through the whole successful turn",
            "refresh/spend with same --agent-id",
            "spends without `--agent-id`",
            "Todo projection has two jobs that should not collapse into one list",
            "`current_agent_claimed_advancement_items`",
            "The default agent-facing lane cap should remain modest",
            "IP-026 | Agent-Scoped No-Candidate Gap",
            "Agent-scoped quota must distinguish \"the goal has runnable work\" from \"this\nagent has runnable work.\"",
            "no current-agent or unclaimed deferred resume candidate is ready",
            "after IP-029 has found no current-agent handoff\ngate state",
            "If the only apparent blocker is a user todo with `blocks_agent` pointing at a\ndifferent agent, IP-003 owns the case before IP-026",
            "IP-029 handoff gate state?",
            "`scope_exhausted`",
            "`agent_scope_wait`",
            "an empty\n  current-agent frontier cannot produce `delivery_allowed=true`",
            "IP-023 | Status Neutral Run Window",
            "IP-025 | Experimental Diagnostic Sidecar Boundary",
            "Experimental proof/debug verdicts are sidecar diagnostics first.",
            "not in `protocol_action_packet_v0` or the routine quota/status packet shape",
            "Promotion from sidecar to stable schema needs an explicit schema decision",
            "`same_tui_visible_attach_accepted` or\n`visible_session_proof_required` directly to a generic runtime packet",
            "IP-028 | Connector Runtime Boundary",
            "Connector packets must carry a machine-readable runtime policy before the first\nbrowser/API run.",
            "content_ops_connector_runtime_policy_v0",
            "browser_open_allowed_before_gate: false",
            "message-list or\nmessage-detail APIs",
            "UI display limit must not become the control-plane reasoning window",
            "## Catalog Maintenance And Validation Design",
            "Do not add\na new IP merely because a maintainer needs a validation technique",
            "Those are uses of the\ncatalog, not catalog patterns by themselves.",
            "if the behavior is already covered by an IP, add the new smoke, fixture,\n  protocol doc, or visual explanation",
            "Canary and readiness groups should therefore be catalog-informed rather than\ncatalog-expanding by default.",
            "it should not become a standalone IP unless the canary behavior itself is a\nruntime/state interaction",
            "fixture-level `loopx canary run`\nchecks as the first evidence layer",
            "`loopx canary run` must stay no-write by\ndefault",
            "not write promotion evidence, create runtime contracts, poll external targets,\nor run deep/browser checks",
            "Replan closeout is explicit",
            "--autonomous-replan-recorded",
            "--repair-delta-kind",
            "autonomous_replan_ack_v0",
            "repair_delta_contract_v0",
            "Classification remains a human-readable history\nlabel",
            "IP-024 | Repair Delta Contract",
            "A successful repair/replan must change the machine-visible frontier",
            "remote development\nmachine, but Codex stays local",
            "future `user_reward_lesson_projection_gap`",
        ],
        source=CATALOG,
    )
    require(
        state_model,
        [
            "candidate operating lesson",
            "Codex stays local; the remote host is\nonly the execution substrate",
            "gate-resume mode, not an agent-scoped no-candidate wait",
            "Chat memory alone is not a replayable\n  control-plane signal.",
        ],
        source=STATE_MODEL,
    )
    require(
        repair_patterns,
        [
            "user_reward_lesson_projection_gap",
            "status_projection_history_neutral_gap",
            "monitor_replan_noop_loop",
            "agent_scoped_user_gate_overreach",
            "agent_scoped_no_candidate_gap",
            "deferred_gate_resume_misclassified",
            "handoff_gate_state_projection_gap",
            "plan_todo_writeback_gap",
            "connector_runtime_boundary_gap",
            "shell_pr_comment_command_substitution",
            "The correction stayed in chat/model belief",
            "Agent-scoped quota does not distinguish \"goal has runnable work\" from \"this agent has runnable work\"",
            "Deferred work was modeled as absence of todo instead of a gate-resume lifecycle condition",
            "Handoff lifecycle was inferred from open todo lanes instead of a small state machine",
            "`todo_handoff_gate_v0`",
            "Agent used chat as memory after understanding the plan",
            "Connector safety lived in prose or posthoc packet fields",
            "Markdown backticks were passed through a double-quoted `gh ... --body",
            "Use a single-quoted body when safe, stdin or `--body-file`",
            "User-gate projection treated agent-scoped routing metadata as diagnostic text",
            "refresh state so `quota should-run` selects the corrected rule",
        ],
        source=SELF_REPAIR_PATTERNS,
    )

    print("interaction-pattern-catalog-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
