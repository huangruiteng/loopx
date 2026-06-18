from __future__ import annotations

from collections import Counter
from typing import Any

from .status import (
    DREAMING_ADVISORY_CLASSIFICATIONS,
    STATUS_NEUTRAL_CLASSIFICATIONS,
    public_safe_compact_text,
)


DREAMING_DRY_RUN_SCHEMA_VERSION = "dreaming_dry_run_proposal_v0"
DREAMING_PROPOSAL_SCHEMA_VERSION = "dreaming_proposal_v0"
MAX_DREAMING_EVIDENCE_ITEMS = 5


def _compact_run(run: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for field in ("generated_at", "classification"):
        value = public_safe_compact_text(run.get(field), limit=120)
        if value:
            compact[field] = value
    action = public_safe_compact_text(
        run.get("recommended_action") or run.get("summary") or run.get("health_check"),
        limit=220,
    )
    if action:
        compact["recommended_action"] = action
    outcome = public_safe_compact_text(run.get("delivery_outcome"), limit=80)
    if outcome:
        compact["delivery_outcome"] = outcome
    return compact


def _goal_record(history_payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    for goal in history_payload.get("goals") or []:
        if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
            return goal
    return None


def _signal_runs(goal: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
    signal_runs: list[dict[str, Any]] = []
    for run in latest_runs:
        if not isinstance(run, dict):
            continue
        classification = str(run.get("classification") or "")
        if not classification:
            continue
        if classification in STATUS_NEUTRAL_CLASSIFICATIONS:
            continue
        if classification in DREAMING_ADVISORY_CLASSIFICATIONS:
            continue
        signal_runs.append(run)
        if len(signal_runs) >= limit:
            break
    return signal_runs


def _proposal_type(runs: list[dict[str, Any]]) -> str:
    combined = " ".join(
        public_safe_compact_text(
            " ".join(
                str(run.get(field) or "")
                for field in (
                    "classification",
                    "recommended_action",
                    "health_check",
                    "delivery_outcome",
                )
            ),
            limit=500,
        )
        for run in runs
    ).lower()
    if any(token in combined for token in ("refactor", "duplicate", "bloat", "large", "monolith", "drift")):
        return "refactor_warning"
    if any(token in combined for token in ("lesson", "memory", "playbook", "skill", "docs", "documentation")):
        return "memory_consolidation"
    if any(token in combined for token in ("archive", "obsolete", "stale")):
        return "archive_suggestion"
    return "exploration"


def _classification_for_proposal_type(proposal_type: str) -> str:
    return {
        "refactor_warning": "dreaming_refactor_warning",
        "memory_consolidation": "dreaming_memory_consolidation",
        "archive_suggestion": "dreaming_archive_suggestion",
    }.get(proposal_type, "dreaming_exploration_proposal")


def _operator_question(goal_id: str, proposal_type: str) -> str:
    if proposal_type == "refactor_warning":
        return (
            f"Should {goal_id} open a reviewed delivery todo for the repeated "
            "refactor or state-drift warning found in recent run history?"
        )
    if proposal_type == "memory_consolidation":
        return (
            f"Should {goal_id} consolidate these repeated lessons into a "
            "project-local playbook, skill, or active-state update?"
        )
    if proposal_type == "archive_suggestion":
        return (
            f"Should {goal_id} review whether stale or obsolete work should be "
            "archived before the next delivery slice?"
        )
    return (
        f"Should {goal_id} promote this exploration proposal into a concrete "
        "delivery todo, defer it, or reject it?"
    )


def _proposal_summary(runs: list[dict[str, Any]], proposal_type: str) -> str:
    classifications = Counter(str(run.get("classification") or "unknown") for run in runs)
    top = ", ".join(f"{name} x{count}" for name, count in classifications.most_common(3))
    if not top:
        top = "no recent non-neutral run history"
    if proposal_type == "refactor_warning":
        return f"Recent run history suggests a possible refactor/state-drift warning: {top}."
    if proposal_type == "memory_consolidation":
        return f"Recent run history has repeated lessons worth consolidating: {top}."
    if proposal_type == "archive_suggestion":
        return f"Recent run history may contain stale work that needs archive review: {top}."
    return f"Recent run history suggests an exploration option for operator review: {top}."


def build_dreaming_dry_run_proposal(
    history_payload: dict[str, Any],
    *,
    goal_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    """Build a local-only dreaming proposal preview from compact run history.

    The returned payload is intentionally advisory: it does not append runtime
    history, mutate active project truth, grant an agent command, or spend quota.
    """

    safe_limit = max(1, min(int(limit), 50))
    goal = _goal_record(history_payload, goal_id)
    if not goal:
        return {
            "ok": False,
            "schema_version": DREAMING_DRY_RUN_SCHEMA_VERSION,
            "goal_id": goal_id,
            "dry_run": True,
            "error": f"goal_id not found in history payload: {goal_id}",
            "side_effects": {
                "project_files_mutated": False,
                "active_state_mutated": False,
                "runtime_history_appended": False,
                "quota_spent": False,
            },
        }

    runs = _signal_runs(goal, safe_limit)
    proposal_type = _proposal_type(runs)
    classification = _classification_for_proposal_type(proposal_type)
    evidence_window = f"last_{len(runs)}_non_neutral_runs" if runs else "no_recent_non_neutral_runs"
    question = _operator_question(goal_id, proposal_type)
    dreaming = {
        "schema_version": DREAMING_PROPOSAL_SCHEMA_VERSION,
        "lane": "exploration",
        "evidence_window": evidence_window,
        "proposal_type": proposal_type,
        "confidence": "medium" if len(runs) >= 3 else "low",
        "requires_project_controller": True,
        "advisory": True,
        "promoted_to_delivery": False,
        "execution_allowed": False,
        "delivery_spend_allowed": False,
    }
    preview = {
        "goal_id": goal_id,
        "classification": classification,
        "recommended_action": (
            "Review this advisory dreaming proposal; approve, defer, or reject "
            "it before converting it into active project truth."
        ),
        "operator_question": question,
        "agent_command": None,
        "dreaming": dreaming,
    }
    return {
        "ok": True,
        "schema_version": DREAMING_DRY_RUN_SCHEMA_VERSION,
        "goal_id": goal_id,
        "dry_run": True,
        "classification": classification,
        "proposal_type": proposal_type,
        "summary": _proposal_summary(runs, proposal_type),
        "operator_question": question,
        "recommended_action": preview["recommended_action"],
        "run_record_preview": preview,
        "recent_evidence": [_compact_run(run) for run in runs[:MAX_DREAMING_EVIDENCE_ITEMS]],
        "side_effects": {
            "project_files_mutated": False,
            "active_state_mutated": False,
            "runtime_history_appended": False,
            "quota_spent": False,
        },
        "write_policy": {
            "advisory": True,
            "append_runtime_history": False,
            "mutate_active_state": False,
            "grant_agent_command": False,
            "spend_quota": False,
        },
    }


def render_dreaming_dry_run_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Dreaming Dry-Run Proposal",
        "",
        f"- Goal: `{payload.get('goal_id')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
    ]
    if payload.get("error"):
        lines.append(f"- Error: {payload.get('error')}")
        return "\n".join(lines) + "\n"

    side_effects = payload.get("side_effects") if isinstance(payload.get("side_effects"), dict) else {}
    lines.extend(
        [
            f"- Classification: `{payload.get('classification')}`",
            f"- Proposal type: `{payload.get('proposal_type')}`",
            f"- Summary: {payload.get('summary')}",
            f"- Operator question: {payload.get('operator_question')}",
            f"- Runtime history appended: `{side_effects.get('runtime_history_appended')}`",
            f"- Active state mutated: `{side_effects.get('active_state_mutated')}`",
            f"- Quota spent: `{side_effects.get('quota_spent')}`",
            "",
            "## Recent Evidence",
            "",
        ]
    )
    evidence = payload.get("recent_evidence") if isinstance(payload.get("recent_evidence"), list) else []
    if not evidence:
        lines.append("- No recent non-neutral run evidence.")
    for item in evidence:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- "
            f"`{item.get('classification')}` "
            f"{item.get('generated_at') or ''}: "
            f"{item.get('recommended_action') or item.get('delivery_outcome') or ''}"
        )
    return "\n".join(lines) + "\n"
