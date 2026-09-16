#!/usr/bin/env python3
"""Smoke-test durable interaction-pattern documentation coverage."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.machine_configuration.builtins import (  # noqa: E402
    build_builtin_machine_configuration_registry,
)

CATALOG = REPO_ROOT / "docs" / "concepts" / "interaction-pattern-catalog.md"
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


def require_catalog_structure(text: str, *, source: Path) -> None:
    table_ids = re.findall(r"^\| P\d \| (IP-\d{3}) \| ", text, re.MULTILINE)
    duplicated = sorted({pid for pid in table_ids if table_ids.count(pid) > 1})
    assert not duplicated, f"{source}: pattern ids own more than one table row: {duplicated}"

    detail_ids = re.findall(r"^#### (IP-\d{3}) ", text, re.MULTILINE)
    missing_detail = sorted(set(table_ids) - set(detail_ids))
    assert not missing_detail, f"{source}: pattern rows without a detail heading: {missing_detail}"
    orphan_detail = sorted(set(detail_ids) - set(table_ids))
    assert not orphan_detail, f"{source}: detail headings without a pattern row: {orphan_detail}"

    matrix_block = re.search(
        r"^\| Family \| P0/P1 Pattern Coverage \|[^\n]*\n\|[^\n]*\|\n(.*?)\n\n",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert matrix_block, f"{source}: Pattern-To-Canary matrix block not found"
    family_cells = re.findall(
        r"^\| [^|]+ \| ((?:IP-\d{3}, )*IP-\d{3}) \|",
        matrix_block.group(1),
        re.MULTILINE,
    )
    family_ids = [pid for cell in family_cells for pid in cell.split(", ")]
    split_families = sorted({pid for pid in family_ids if family_ids.count(pid) > 1})
    assert not split_families, (
        f"{source}: pattern ids listed under more than one family: {split_families}"
    )
    unknown_matrix_ids = sorted(set(family_ids) - set(table_ids))
    assert not unknown_matrix_ids, (
        f"{source}: family matrix lists ids without a pattern row: {unknown_matrix_ids}"
    )


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
            "examples/control_plane/quota-cleared-blocker-successor-gate-smoke.py",
            "When a user gate carries `blocks_agent=<agent-id>`",
            "agent-scoped user gate overreach",
            "not IP-026 scope exhaustion",
            "examples/control_plane/quota-agent-scoped-user-gate-smoke.py",
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
            "The 2026-06-21 monitor-only replan stall is the canonical public-safe bad case",
            "agent todo lane contains only monitor-style work",
            "no runnable todo, blocker, successor, supersede, or watch-lane expiry changed",
            "A watch lane may\nremain visible",
            "must not\nrender as immediate Codex delivery or as a user/controller approval gate",
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
            "IP-032 | Completed Work Archive With Durable Decision Retention",
            "Archive is a storage move, not a decision loss.",
            "retained_standing_decision_count",
            "The role defaults to `agent`",
            "examples/control_plane/todo-archive-completed-smoke.py",
            "IP-033 | Recorded Rejection Is Not Absent Authority",
            "A recorded rejection is a decision, not the absence of one.",
            "`inactive_count`",
            "## Catalog Maintenance And Validation Design",
            "Do not add\na new IP merely because a maintainer needs a validation technique",
            "Those are uses of the\ncatalog, not catalog patterns by themselves.",
            "if the behavior is already covered by an IP, add the new smoke, fixture,\n  protocol doc, or visual explanation",
            "Canary and readiness groups should therefore be catalog-informed rather than\ncatalog-expanding by default.",
            "it should not become a standalone IP unless the canary behavior itself is a\nruntime/state interaction",
            "fixture-level `loopx canary run`\nchecks as the first evidence layer",
            "`loopx canary run` must stay no-write by\ndefault",
            "not write promotion evidence, create runtime contracts, poll external targets,\nor run deep/browser checks",
            "Replan closeout is semantic and causally bound",
            "--replan-obligation-id",
            "host_action=end_current_heartbeat",
            "semantic receipt bound to the exact current\nobligation",
            "Classification prose, an evidence read receipt",
            "same full goal-frontier context as quota",
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
            "Agent-scoped quota does not distinguish \"goal has runnable work\" from \"this peer has runnable work\"",
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

    require_catalog_structure(catalog, source=CATALOG)

    # Every registered built-in machine-configuration namespace must be
    # discoverable from the catalog, so a new capability cannot land as a
    # silent omission in the IP-030 inventory.
    registered_namespaces = sorted(
        build_builtin_machine_configuration_registry().namespace_ids
    )
    undocumented = [ns for ns in registered_namespaces if ns not in catalog]
    assert not undocumented, (
        f"{CATALOG}: built-in machine-configuration namespaces missing from the "
        f"catalog: {undocumented}; document them in IP-030 or record an explicit "
        "intentional omission"
    )

    print("interaction-pattern-catalog-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
