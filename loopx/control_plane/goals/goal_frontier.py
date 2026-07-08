from __future__ import annotations

from typing import Any

from ..agents.agent_scope import (
    agent_scope_blocking_handoff_gates,
    agent_scope_count_advancement_items,
    agent_scope_item_claimed_by,
    agent_scope_item_claimed_by_agent_or_unclaimed,
)
from ..work_items.autonomous_replan_ack import (
    autonomous_replan_ack_matches_agent,
    latest_autonomous_replan_ack_for_projection,
)
from ..work_items.autonomous_replan_obligation import (
    build_autonomous_replan_obligation_payload,
)
from ..work_items.repair_delta import repair_delta_kinds_have_frontier_delta


GOAL_FRONTIER_PROJECTION_SCHEMA_VERSION = "goal_frontier_projection_v0"
VISION_CONTINUATION_AUDIT_SCHEMA_VERSION = "vision_continuation_audit_v0"
VISION_GAP_JUDGE_SCHEMA_VERSION = "vision_gap_judge_v0"
AUTONOMOUS_REPLAN_DECISION_SCHEMA_VERSION = "autonomous_replan_decision_v0"
AUTONOMOUS_REPLAN_SCOPE_SCHEMA_VERSION = "autonomous_replan_scope_v0"
AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION = "autonomous_replan_obligation_v0"
AUTONOMOUS_REPLAN_REQUIRED_MODE = "autonomous_replan_required"
FRONTIER_EXHAUSTED_MONITOR_TRIGGER = "frontier_exhausted_monitor_lane"
LONG_TODO_CHAIN_TRIGGER = "long_todo_chain"
VISION_ACCEPTANCE_GAP_TRIGGER = "vision_acceptance_gap"
VISION_CHECKPOINT_MISSING_TRIGGER = "vision_checkpoint_missing"
TODO_SUCCESSION_GAP_TRIGGER = "completed_advancement_without_successor"
TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
TODO_TASK_CLASS_MONITOR = "continuous_monitor"
LONG_TODO_CHAIN_ADVANCEMENT_THRESHOLD = 15
LONG_TODO_CHAIN_OPEN_THRESHOLD = 20
AGENT_VISION_CLOSED_STATES = {
    "closed",
    "satisfied",
    "vision_closed",
    "retired",
    "retired_or_superseded",
    "superseded",
    "no_followup",
    "no-followup",
}
VISION_CHECKPOINT_SATISFIED_DECISIONS = {
    "patched",
    "retired_or_superseded",
    "unchanged_with_reason",
}


def safe_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def select_autonomous_replan_obligation(
    item: dict[str, Any],
    project_asset: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    project_asset = project_asset if isinstance(project_asset, dict) else {}
    value = item.get("autonomous_replan_obligation")
    if isinstance(value, dict):
        return value
    value = project_asset.get("autonomous_replan_obligation")
    if isinstance(value, dict):
        return value
    return None


def autonomous_replan_is_required(replan_obligation: dict[str, Any] | None) -> bool:
    return bool(replan_obligation and replan_obligation.get("required"))


def autonomous_replan_ack_has_frontier_delta(ack: dict[str, Any] | None) -> bool:
    if not isinstance(ack, dict) or ack.get("recorded") is not True:
        return False
    delta_contract = ack.get("delta_contract")
    if not isinstance(delta_contract, dict) or delta_contract.get("delta_present") is not True:
        return False
    return repair_delta_kinds_have_frontier_delta(delta_contract.get("delta_kinds"))


def autonomous_replan_decision_allowed(
    *,
    replan_obligation: dict[str, Any] | None,
    plan_ok: bool,
    workspace_blocked: bool,
    automation_prompt_upgrade_required: bool,
    agent_id: str | None = None,
    primary_agent_id: str | None = None,
) -> bool:
    return bool(
        autonomous_replan_is_required(replan_obligation)
        and autonomous_replan_scope_decision(
            replan_obligation,
            agent_id=agent_id,
            primary_agent_id=primary_agent_id,
        ).get("applies")
        and plan_ok
        and not workspace_blocked
        and not automation_prompt_upgrade_required
    )


def _normalize_replan_agent_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _autonomous_replan_owner_agent_ids(
    replan_obligation: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(replan_obligation, dict):
        return []
    owner_keys = (
        "agent_id",
        "claimed_by",
        "owner_agent",
        "target_agent",
        "blocks_agent",
    )
    owners: list[str] = []

    def append_owner(value: Any) -> None:
        owner = _normalize_replan_agent_id(value)
        if owner and owner not in owners:
            owners.append(owner)

    for key in owner_keys:
        append_owner(replan_obligation.get(key))
    triggers = (
        replan_obligation.get("triggers")
        if isinstance(replan_obligation.get("triggers"), list)
        else []
    )
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        for key in owner_keys:
            append_owner(trigger.get(key))
    return owners


def autonomous_replan_scope_decision(
    replan_obligation: dict[str, Any] | None,
    *,
    agent_id: str | None,
    primary_agent_id: str | None,
) -> dict[str, Any]:
    """Return whether a replan obligation belongs to this agent lane.

    Explicit agent-owned replans are consumed only by that agent. Unscoped
    goal-level replans default to the primary/controller lane so side agents do
    not repeatedly consume another lane's stalled Next Action.
    """

    normalized_agent_id = _normalize_replan_agent_id(agent_id)
    normalized_primary_agent_id = _normalize_replan_agent_id(primary_agent_id)
    owners = _autonomous_replan_owner_agent_ids(replan_obligation)
    required = autonomous_replan_is_required(replan_obligation)
    if not required:
        applies = False
        scope = "not_required"
    elif not normalized_agent_id:
        applies = True
        scope = "unscoped_quota_call"
    elif owners:
        applies = normalized_agent_id in owners
        scope = "explicit_agent_owner"
    elif normalized_primary_agent_id:
        applies = normalized_agent_id == normalized_primary_agent_id
        scope = "default_primary_agent"
    else:
        applies = True
        scope = "single_agent_or_unknown_primary"
    return {
        "schema_version": AUTONOMOUS_REPLAN_SCOPE_SCHEMA_VERSION,
        "required": required,
        "applies": applies,
        "scope": scope,
        "agent_id": normalized_agent_id,
        "primary_agent_id": normalized_primary_agent_id,
        "owner_agent_ids": owners,
    }


def _compact_projection_text(value: Any, *, limit: int = 360) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    return text[:limit]


def _latest_runs_for_goal(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
) -> list[dict[str, Any]]:
    run_history = (
        status_payload.get("run_history")
        if isinstance(status_payload.get("run_history"), dict)
        else {}
    )
    goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    goal = next(
        (
            item
            for item in goals
            if isinstance(item, dict) and str(item.get("id") or "") == goal_id
        ),
        None,
    )
    latest_runs = goal.get("latest_runs") if isinstance(goal, dict) else None
    return [item for item in latest_runs if isinstance(item, dict)] if isinstance(latest_runs, list) else []


def _run_agent_id_matches(run: dict[str, Any], *, agent_id: str | None) -> bool:
    if not agent_id:
        return True
    run_agent_id = str(run.get("agent_id") or "").strip()
    return not run_agent_id or run_agent_id == agent_id


def _run_retires_prior_agent_vision(
    run: dict[str, Any],
    *,
    agent_id: str | None,
) -> bool:
    if not _run_agent_id_matches(run, agent_id=agent_id):
        return False
    checkpoint = (
        run.get("vision_checkpoint")
        if isinstance(run.get("vision_checkpoint"), dict)
        else {}
    )
    if isinstance(checkpoint, dict) and checkpoint:
        checkpoint_agent_id = str(
            checkpoint.get("agent_id") or run.get("agent_id") or ""
        ).strip()
        if agent_id and checkpoint_agent_id and checkpoint_agent_id != agent_id:
            return False
        if (
            checkpoint.get("satisfied") is True
            and str(checkpoint.get("decision") or "").strip() == "retired_or_superseded"
        ):
            return True
    return False


def latest_agent_vision_from_status_payload(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None,
) -> dict[str, Any] | None:
    """Return the newest compact agent vision packet visible in run history."""

    for run in _latest_runs_for_goal(status_payload, goal_id=goal_id):
        vision = run.get("agent_vision")
        if not isinstance(vision, dict):
            if _run_retires_prior_agent_vision(run, agent_id=agent_id):
                return None
            continue
        vision_agent_id = str(vision.get("agent_id") or run.get("agent_id") or "").strip()
        if agent_id and vision_agent_id and vision_agent_id != agent_id:
            continue
        patch = vision.get("vision_patch") if isinstance(vision.get("vision_patch"), dict) else {}
        if not patch:
            continue
        return {
            "schema_version": vision.get("schema_version"),
            "goal_id": goal_id,
            "agent_id": vision_agent_id or agent_id,
            "state": vision.get("state"),
            "vision_patch": patch,
            "todo_delta": vision.get("todo_delta")
            if isinstance(vision.get("todo_delta"), list)
            else [],
            "vision_budget": vision.get("vision_budget")
            if isinstance(vision.get("vision_budget"), dict)
            else None,
            "generated_at": run.get("generated_at"),
        }
    return None


def latest_missing_vision_checkpoint_from_status_payload(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None,
) -> dict[str, Any] | None:
    """Return the newest unsatisfied per-agent vision checkpoint in run history."""

    for run in _latest_runs_for_goal(status_payload, goal_id=goal_id):
        checkpoint = run.get("vision_checkpoint")
        if not isinstance(checkpoint, dict):
            continue
        checkpoint_agent_id = str(
            checkpoint.get("agent_id") or run.get("agent_id") or ""
        ).strip()
        if agent_id and checkpoint_agent_id != agent_id:
            continue
        if not agent_id and checkpoint_agent_id:
            continue
        decision = str(checkpoint.get("decision") or "").strip()
        if (
            checkpoint.get("satisfied") is True
            and decision in VISION_CHECKPOINT_SATISFIED_DECISIONS
        ):
            return None
        if checkpoint.get("required") is not True:
            continue
        if checkpoint.get("satisfied") is not False:
            continue
        if decision != "missing_required":
            continue
        return {
            "schema_version": checkpoint.get("schema_version"),
            "goal_id": goal_id,
            "agent_id": checkpoint_agent_id or agent_id,
            "decision": checkpoint.get("decision"),
            "triggers": checkpoint.get("triggers")
            if isinstance(checkpoint.get("triggers"), list)
            else [],
            "required_resolution": checkpoint.get("required_resolution")
            if isinstance(checkpoint.get("required_resolution"), list)
            else [],
            "generated_at": run.get("generated_at"),
        }
    return None


def latest_autonomous_replan_ack_from_status_payload(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None,
    neutral_classifications: set[str],
) -> dict[str, Any] | None:
    """Return the newest agent-scoped durable replan ACK visible in run history."""

    if not agent_id:
        return None
    latest_runs = [
        run
        for run in _latest_runs_for_goal(status_payload, goal_id=goal_id)
        if _run_agent_id_matches(run, agent_id=agent_id)
    ]
    return latest_autonomous_replan_ack_for_projection(
        latest_runs,
        neutral_classifications=neutral_classifications,
    )


def projected_autonomous_replan_ack_for_agent(
    item: dict[str, Any],
    project_asset: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> dict[str, Any] | None:
    """Return the current projected replan ACK when it belongs to this agent."""

    project_asset = project_asset if isinstance(project_asset, dict) else {}
    for candidate in (
        item.get("autonomous_replan_ack"),
        project_asset.get("autonomous_replan_ack"),
    ):
        if autonomous_replan_ack_matches_agent(candidate, agent_id=agent_id):
            return candidate
    return None


def acceptance_gaps_from_agent_vision(
    agent_vision: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Convert bounded vision replan triggers into goal-frontier gap records."""

    if not isinstance(agent_vision, dict):
        return []
    patch = agent_vision.get("vision_patch") if isinstance(agent_vision.get("vision_patch"), dict) else {}
    state = str(agent_vision.get("state") or "").strip().lower()
    if state in AGENT_VISION_CLOSED_STATES:
        return []
    acceptance = _compact_projection_text(patch.get("acceptance_summary"), limit=420)
    trigger = _compact_projection_text(patch.get("replan_trigger_summary"), limit=240)
    if not trigger and acceptance:
        trigger = "active agent vision remains open with acceptance evidence still required"
    if not trigger:
        return []
    gap: dict[str, Any] = {
        "kind": VISION_ACCEPTANCE_GAP_TRIGGER,
        "source": "latest_agent_vision",
        "agent_id": agent_vision.get("agent_id"),
        "state": agent_vision.get("state"),
        "replan_trigger_summary": trigger,
    }
    if acceptance:
        gap["acceptance_summary"] = acceptance
    generated_at = _compact_projection_text(agent_vision.get("generated_at"), limit=80)
    if generated_at:
        gap["generated_at"] = generated_at
    return [gap]


def acceptance_gaps_from_vision_checkpoint(
    checkpoint: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Convert a missing per-agent vision checkpoint into a frontier gap."""

    if not isinstance(checkpoint, dict):
        return []
    trigger_kinds = [
        str(trigger.get("kind") or "").strip()
        for trigger in (checkpoint.get("triggers") or [])
        if isinstance(trigger, dict) and str(trigger.get("kind") or "").strip()
    ]
    trigger_text = ", ".join(trigger_kinds[:3]) or "required vision checkpoint"
    gap: dict[str, Any] = {
        "kind": VISION_CHECKPOINT_MISSING_TRIGGER,
        "source": "latest_vision_checkpoint",
        "agent_id": checkpoint.get("agent_id"),
        "decision": checkpoint.get("decision"),
        "replan_trigger_summary": (
            "refresh-state closed a material segment without a per-agent vision "
            f"decision; triggers={trigger_text}"
        ),
        "acceptance_summary": (
            "Write a bounded agent vision patch, record an unchanged reason, "
            "or retire/supersede the frontier with an explicit rationale."
        ),
    }
    generated_at = _compact_projection_text(checkpoint.get("generated_at"), limit=80)
    if generated_at:
        gap["generated_at"] = generated_at
    return [gap]


def build_vision_continuation_audit(
    *,
    goal_id: str | None = None,
    agent_id: str | None,
    acceptance_gaps: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return the closeout audit contract for an open per-agent vision gap.

    This is a read-path contract: quota/status can tell an agent that the
    selected todo is only a step toward the active vision. Writeback still goes
    through normal todo, evidence, and refresh-state commands.
    """

    compact_acceptance_gaps = [
        gap for gap in (acceptance_gaps or []) if isinstance(gap, dict)
    ]
    if not compact_acceptance_gaps:
        return None
    vision_gap_judge = build_vision_gap_judge(
        goal_id=goal_id,
        agent_id=agent_id,
        acceptance_gaps=compact_acceptance_gaps,
    )
    acceptance_requirements = [
        text
        for text in (
            _compact_projection_text(gap.get("acceptance_summary"), limit=180)
            for gap in compact_acceptance_gaps
        )
        if text
    ]
    audit: dict[str, Any] = {
        "schema_version": VISION_CONTINUATION_AUDIT_SCHEMA_VERSION,
        "required": True,
        "agent_id": agent_id,
        "decision": "acceptance_gap_open",
        "selected_todo_is_goal_completion": False,
        "closeout_allowed_without_evidence": False,
        "trigger_count": len(compact_acceptance_gaps),
        "acceptance_gaps": compact_acceptance_gaps[:5],
        "vision_gap_judge": vision_gap_judge,
        "authoritative_evidence_kinds": [
            "changed_files",
            "public_safe_evidence_records",
            "public_web_research_findings",
            "evaluation_outputs",
            "successor_state",
            "blocker_state",
            "superseding_agent_vision",
        ],
        "not_satisfied_by": [
            "todo_completion_alone",
            "autonomous_replan_ack_alone",
            "vision_checkpoint_alone",
            "no_followup_without_acceptance_evidence",
        ],
        "required_before_closeout": [
            "derive_requirements_from_active_vision_and_current_todo",
            "name_authoritative_evidence_for_each_requirement",
            "run_bounded_public_research_when_local_evidence_is_missing",
            "create_successor_or_write_vision_replan_trigger_when_unproven",
        ],
        "recommended_action": (
            "audit active per-agent vision acceptance before todo closeout; "
            "if evidence is weak or missing, use bounded public research when "
            "the claim depends on public facts, then keep the vision active with "
            "a successor todo or --vision-replan-trigger"
        ),
    }
    if acceptance_requirements:
        audit["acceptance_requirements"] = acceptance_requirements[:5]
    return audit


def build_vision_gap_judge(
    *,
    goal_id: str | None = None,
    agent_id: str | None,
    acceptance_gaps: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Return the strict done/continue judge for active per-agent vision gaps.

    The read model keeps the prompt essence compact: unless current evidence
    satisfies, blocks, or supersedes the active vision, the agent should judge
    the vision as still CONTINUE.
    """

    compact_acceptance_gaps = [
        gap for gap in (acceptance_gaps or []) if isinstance(gap, dict)
    ]
    first_gap = compact_acceptance_gaps[0] if compact_acceptance_gaps else {}
    reason = _compact_projection_text(
        first_gap.get("replan_trigger_summary")
        or "active per-agent vision still has an open acceptance gap",
        limit=220,
    )
    evidence_command = None
    if goal_id and agent_id:
        evidence_command = (
            f"loopx evidence-log --goal-id {goal_id} "
            f"--agent-id {agent_id} --thin"
        )
    evidence_read_instruction = (
        "Before judging, read any projected required_reads; then read the "
        "agent-scoped evidence log"
    )
    if evidence_command:
        evidence_read_instruction = f"{evidence_read_instruction}: `{evidence_command}`."
    else:
        evidence_read_instruction = (
            f"{evidence_read_instruction} when goal_id and agent_id are available."
        )
    public_research_instruction = (
        "If the evidence log is missing, stale, or too weak and the acceptance "
        "question depends on public facts, run bounded public web research using "
        "primary or authoritative sources; record confirmed/refuted findings as "
        "public-safe evidence or a compact vision replan trigger before judging."
    )
    return {
        "schema_version": VISION_GAP_JUDGE_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": agent_id,
        "done": False,
        "decision": "continue",
        "reason": (
            reason
            or "active per-agent vision still has an open acceptance gap"
        ),
        "agent_judge_instruction": (
            "Judge vision closure: compare active vision acceptance_summary "
            "with projected evidence and agent-scoped evidence-log reads. "
            "Use bounded public web research when local evidence is insufficient "
            "and the gap depends on public facts. "
            "Mark done only when evidence proves completion, a blocker/user "
            "gate, or superseding/no-follow-up closure; otherwise continue."
        ),
        "evidence_read_instruction": evidence_read_instruction,
        "external_research_instruction": public_research_instruction,
        "research_writeback_required_when_used": [
            "source_url_or_public_reference",
            "confirmed_or_refuted_finding",
            "supports_or_refutes_acceptance_gap",
            "successor_todo_or_vision_replan_trigger",
        ],
        "done_only_when": [
            "authoritative_evidence_satisfies_acceptance",
            "final_deliverable_or_eval_output_satisfies_acceptance",
            "blocker_or_user_gate_is_projected",
            "superseding_vision_or_no_followup_closes_the_frontier",
        ],
        "continue_when": [
            "evidence_is_missing_weak_or_stale",
            "todo_lifecycle_or_protocol_status_is_the_only_proof",
            "acceptance_gap_is_still_projected",
        ],
        "otherwise": "continue",
    }


def _open_todo_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    return safe_non_negative_int(summary.get("open_count"))


def _todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    if item.get("done") is True:
        return False
    status = str(item.get("status") or "open").strip().lower()
    return status in {"", "open", "todo", "active", "pending"}


def _todo_task_class(item: dict[str, Any]) -> str:
    return str(item.get("task_class") or "").strip()


def _count_advancement_items(items: Any, *, claimed_by: str | None = None) -> int:
    return agent_scope_count_advancement_items(items, claimed_by=claimed_by)


def _summary_task_counts(summary: dict[str, Any] | None) -> dict[str, int]:
    open_count = _open_todo_count(summary)
    if not isinstance(summary, dict):
        return {"open": open_count, "advancement": 0, "monitor": 0, "monitor_due": 0}
    executable = summary.get("executable_backlog_items")
    monitor_open = summary.get("monitor_open_items")
    advancement_count = (
        _count_advancement_items(executable)
        if isinstance(executable, list)
        else safe_non_negative_int(summary.get("claimed_advancement_open_count"))
        + len(
            [
                item
                for item in (summary.get("unclaimed_priority_open_items") or [])
                if isinstance(item, dict)
                and _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
            ]
        )
    )
    monitor_count = (
        len(
            [
                item
                for item in monitor_open
                if isinstance(item, dict)
                and _todo_item_is_actionable_open(item)
                and _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
            ]
        )
        if isinstance(monitor_open, list)
        else safe_non_negative_int(summary.get("claimed_monitor_open_count"))
    )
    return {
        "open": open_count,
        "advancement": advancement_count,
        "monitor": monitor_count,
        "monitor_due": safe_non_negative_int(summary.get("monitor_due_count")),
    }


def _frontier_advancement_counts(
    *,
    agent_todo_summary: dict[str, Any] | None,
    agent_id: str | None,
) -> dict[str, int]:
    current_agent_advancement_count = (
        safe_non_negative_int(agent_todo_summary.get("current_agent_claimed_advancement_count"))
        if isinstance(agent_todo_summary, dict)
        else 0
    )
    unclaimed_advancement_count = (
        _count_advancement_items(
            agent_todo_summary.get("unclaimed_priority_open_items"),
            claimed_by="__unclaimed__",
        )
        if isinstance(agent_todo_summary, dict)
        else 0
    )
    other_agent_claimed_items: Any = None
    if isinstance(agent_todo_summary, dict):
        executable_items = agent_todo_summary.get("executable_backlog_items")
        if isinstance(executable_items, list):
            if agent_id:
                current_agent_advancement_count = max(
                    current_agent_advancement_count,
                    _count_advancement_items(executable_items, claimed_by=agent_id),
                )
            unclaimed_advancement_count = max(
                unclaimed_advancement_count,
                _count_advancement_items(executable_items, claimed_by="__unclaimed__"),
            )
        claim_scope = (
            agent_todo_summary.get("claim_scope")
            if isinstance(agent_todo_summary.get("claim_scope"), dict)
            else {}
        )
        other_agent_claimed_items = claim_scope.get("other_agent_claimed_items")
    return {
        "current_agent_claimed_advancement_count": current_agent_advancement_count,
        "unclaimed_advancement_count": unclaimed_advancement_count,
        "other_agent_claimed_advancement_count": _count_advancement_items(
            other_agent_claimed_items
        ),
    }


def _long_todo_chain_trigger(
    *,
    agent_todo_summary: dict[str, Any] | None,
    agent_counts: dict[str, int],
    frontier_counts: dict[str, int],
    agent_id: str | None,
) -> dict[str, Any] | None:
    """Return a trigger when one lane is long enough to need vision replan.

    The trigger is scoped to the current agent plus unclaimed selectable work.
    Other-agent claimed todos stay out of this count so one role cannot replan
    another role's backlog.
    """

    current_advancement = frontier_counts.get("current_agent_claimed_advancement_count", 0)
    unclaimed_advancement = frontier_counts.get("unclaimed_advancement_count", 0)
    selectable_advancement = current_advancement + unclaimed_advancement
    if isinstance(agent_todo_summary, dict):
        current_open = safe_non_negative_int(
            agent_todo_summary.get("current_agent_claimed_open_count")
        )
        unclaimed_open = safe_non_negative_int(agent_todo_summary.get("unclaimed_open_count"))
        selectable_open = max(current_open + unclaimed_open, selectable_advancement)
    else:
        selectable_open = max(agent_counts.get("open", 0), selectable_advancement)
    if selectable_advancement >= LONG_TODO_CHAIN_ADVANCEMENT_THRESHOLD:
        return {
            "trigger_count": selectable_advancement,
            "count_kind": "selectable_advancement_todos",
            "selectable_open_count": selectable_open,
            "selectable_advancement_count": selectable_advancement,
            "current_agent_claimed_advancement_count": current_advancement,
            "unclaimed_advancement_count": unclaimed_advancement,
            "threshold": LONG_TODO_CHAIN_ADVANCEMENT_THRESHOLD,
            "agent_id": agent_id,
        }
    if (
        selectable_open >= LONG_TODO_CHAIN_OPEN_THRESHOLD
        and selectable_advancement > 0
    ):
        return {
            "trigger_count": selectable_open,
            "count_kind": "selectable_open_todos",
            "selectable_open_count": selectable_open,
            "selectable_advancement_count": selectable_advancement,
            "current_agent_claimed_advancement_count": current_advancement,
            "unclaimed_advancement_count": unclaimed_advancement,
            "threshold": LONG_TODO_CHAIN_OPEN_THRESHOLD,
            "agent_id": agent_id,
        }
    return None


def _compact_todo_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    todo_id = str(item.get("todo_id") or "").strip()
    return todo_id or None


def _deferred_successors(
    summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {
            "ready_count": 0,
            "blocked_count": 0,
            "current_agent_ready_count": 0,
            "ready_todo_ids": [],
        }

    ready_items = [
        item
        for item in (summary.get("deferred_resume_candidates") or [])
        if isinstance(item, dict)
    ]
    deferred_items = [
        item for item in (summary.get("deferred_items") or []) if isinstance(item, dict)
    ]
    deferred_count = max(
        safe_non_negative_int(summary.get("deferred_count")),
        len(deferred_items),
        len(ready_items),
    )
    current_agent_ready_items = [
        item
        for item in ready_items
        if agent_id and agent_scope_item_claimed_by(item) == agent_id
    ]
    ready_todo_ids = [
        todo_id for todo_id in (_compact_todo_id(item) for item in ready_items[:5]) if todo_id
    ]
    projection = {
        "ready_count": len(ready_items),
        "blocked_count": max(0, deferred_count - len(ready_items)),
        "current_agent_ready_count": len(current_agent_ready_items),
        "ready_todo_ids": ready_todo_ids,
    }
    if ready_todo_ids:
        projection["top_ready_todo_id"] = ready_todo_ids[0]
    return projection


def _is_monitor_only_lane(
    work_lane_contract: dict[str, Any] | None,
) -> bool:
    return bool(
        work_lane_contract
        and work_lane_contract.get("lane") == TODO_TASK_CLASS_MONITOR
        and work_lane_contract.get("must_attempt_work") is False
    )


def _monitor_only_lane_has_future_schedule(
    agent_todo_summary: dict[str, Any] | None,
) -> bool:
    if not isinstance(agent_todo_summary, dict):
        return False
    if "monitor_due_count" not in agent_todo_summary:
        return False
    if "monitor_schedule_gap_count" not in agent_todo_summary:
        return False
    if safe_non_negative_int(agent_todo_summary.get("monitor_due_count")) > 0:
        return False
    if safe_non_negative_int(agent_todo_summary.get("monitor_schedule_gap_count")) > 0:
        return False
    monitor_items = agent_todo_summary.get("monitor_open_items")
    return isinstance(monitor_items, list) and len(monitor_items) > 0


def _blocking_handoff_gate_count(
    agent_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> int:
    if not agent_id or not isinstance(agent_todo_summary, dict):
        return 0
    return len(agent_scope_blocking_handoff_gates(agent_todo_summary, agent_id=agent_id))


def _ready_deferred_successor_count(
    agent_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> int:
    if not isinstance(agent_todo_summary, dict):
        return 0
    current_count = safe_non_negative_int(
        agent_todo_summary.get("current_agent_deferred_resume_count")
    )
    unclaimed_count = safe_non_negative_int(
        agent_todo_summary.get("unclaimed_deferred_resume_count")
    )
    if current_count or unclaimed_count:
        return current_count + unclaimed_count
    candidates = (
        agent_todo_summary.get("deferred_resume_candidates")
        if isinstance(agent_todo_summary.get("deferred_resume_candidates"), list)
        else []
    )
    return len(
        [
            item
            for item in candidates
            if isinstance(item, dict)
            and agent_scope_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
        ]
    )


def _succession_gap_items(
    agent_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(agent_todo_summary, dict):
        return []
    warning = (
        agent_todo_summary.get("todo_succession_warning")
        if isinstance(agent_todo_summary.get("todo_succession_warning"), dict)
        else {}
    )
    source_items = (
        warning.get("items")
        if isinstance(warning.get("items"), list)
        else agent_todo_summary.get("completed_without_successor_items")
        if isinstance(agent_todo_summary.get("completed_without_successor_items"), list)
        else []
    )
    items = [item for item in source_items if isinstance(item, dict)]
    if not agent_id:
        return items
    return [
        item
        for item in items
        if agent_scope_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
    ]


def derive_goal_frontier_replan_obligation_from_summaries(
    *,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    agent_id: str | None,
    existing_replan_obligation: dict[str, Any] | None,
    latest_replan_ack: dict[str, Any] | None = None,
    acceptance_gaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return a compact replan obligation when the goal frontier has no advancement.

    This keeps the per-goal completion/replan rule in the goal-frontier policy
    seam. Quota should consume the resulting obligation instead of embedding
    monitor/vision semantics in its scheduler path.
    """

    if autonomous_replan_is_required(existing_replan_obligation):
        return None
    if _blocking_handoff_gate_count(agent_todo_summary, agent_id=agent_id) > 0:
        return None
    if _ready_deferred_successor_count(agent_todo_summary, agent_id=agent_id) > 0:
        return None

    user_counts = _summary_task_counts(user_todo_summary)
    agent_counts = _summary_task_counts(agent_todo_summary)
    frontier_counts = _frontier_advancement_counts(
        agent_todo_summary=agent_todo_summary,
        agent_id=agent_id,
    )
    total_frontier_advancement = sum(frontier_counts.values())
    compact_acceptance_gaps = [
        item for item in (acceptance_gaps or []) if isinstance(item, dict)
    ]
    if user_counts.get("open", 0) > 0:
        return None
    succession_gap_items = _succession_gap_items(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if (
        succession_gap_items
        and agent_counts.get("advancement", 0) == 0
        and total_frontier_advancement == 0
    ):
        triggers = [
            {
                "kind": TODO_SUCCESSION_GAP_TRIGGER,
                "section": "agent_todo_summary.todo_succession_warning",
                "todo_id": item.get("todo_id"),
                "text": item.get("text")
                or item.get("title")
                or "completed advancement needs a successor or no-followup rationale",
                "agent_id": agent_id,
                "claimed_by": item.get("claimed_by"),
            }
            for item in succession_gap_items[:3]
        ]
        return build_autonomous_replan_obligation_payload(
            schema_version=AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
            agent_id=agent_id,
            include_agent_id=True,
            stall_threshold=1,
            trigger_count=len(succession_gap_items),
            triggers=triggers,
            guidance_actions=[
                "create_successor",
                "link_successor",
                "record_no_followup",
            ],
            todo_actions=[
                {
                    "action": "add",
                    "role": "agent",
                    "priority": "P0",
                    "text": (
                        "run a bounded successor replan: create or link the next "
                        "runnable advancement todo, or record an explicit "
                        "no-follow-up rationale"
                    ),
                }
            ],
            stop_condition=(
                "stop if the successor decision requires private material, "
                "credentials, destructive git, production actions, or owner-only decisions"
            ),
            recommended_action=(
                "run a bounded successor replan before another quiet poll: add/link "
                "the next advancement todo, or record explicit no-follow-up"
            ),
        )
    if (
        compact_acceptance_gaps
        and agent_counts.get("advancement", 0) == 0
        and total_frontier_advancement == 0
    ):
        return build_autonomous_replan_obligation_payload(
            schema_version=AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
            agent_id=agent_id,
            include_agent_id=True,
            stall_threshold=1,
            trigger_count=len(compact_acceptance_gaps),
            triggers=[
                {
                    "kind": gap.get("kind") or VISION_ACCEPTANCE_GAP_TRIGGER,
                    "section": "goal_frontier_projection.acceptance_gaps",
                    "text": gap.get("replan_trigger_summary")
                    or "bounded agent vision reports an open acceptance gap",
                    "agent_id": agent_id,
                    "acceptance_summary": gap.get("acceptance_summary"),
                }
                for gap in compact_acceptance_gaps[:3]
            ],
            guidance_actions=[
                "create_successor",
                "update_agent_vision",
                "record_evidence_gap",
                "record_no_followup",
            ],
            todo_actions=[
                {
                    "action": "add",
                    "role": "agent",
                    "priority": "P0",
                    "text": (
                        "run a bounded vision-gap replan: create the next runnable "
                        "advancement todo or record an explicit no-follow-up rationale"
                    ),
                }
            ],
            stop_condition=(
                "stop if the gap requires private material, credentials, destructive git, "
                "production actions, or owner-only decisions"
            ),
            recommended_action=(
                "run a bounded vision-gap replan before another quiet poll: create "
                "successor work, update the agent vision, record evidence gap, or "
                "record no-follow-up"
            ),
        )
    long_chain_trigger = _long_todo_chain_trigger(
        agent_todo_summary=agent_todo_summary,
        agent_counts=agent_counts,
        frontier_counts=frontier_counts,
        agent_id=agent_id,
    )
    if long_chain_trigger and not autonomous_replan_ack_has_frontier_delta(
        latest_replan_ack
    ):
        return build_autonomous_replan_obligation_payload(
            schema_version=AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
            agent_id=agent_id,
            include_agent_id=True,
            stall_threshold=long_chain_trigger.get("threshold"),
            trigger_count=long_chain_trigger.get("trigger_count"),
            triggers=[
                {
                    "kind": LONG_TODO_CHAIN_TRIGGER,
                    "section": "agent_todo_summary",
                    "text": (
                        "current agent lane has a long selectable todo chain; "
                        "run a vision checkpoint/replan before continuing linearly"
                    ),
                    **long_chain_trigger,
                }
            ],
            guidance_actions=[
                "read_evidence_log",
                "run_bounded_public_research_if_local_evidence_is_missing",
                "group_or_prune_todo_chain",
                "update_agent_vision",
                "create_successor",
            ],
            todo_actions=[
                {
                    "action": "add",
                    "role": "agent",
                    "priority": "P1",
                    "text": (
                        "run a bounded long-chain vision replan: compare evidence "
                        "with the active vision, group or prune the todo chain, "
                        "and select the next high-value runnable slice"
                    ),
                }
            ],
            stop_condition=(
                "stop if pruning or external research requires private material, "
                "credentials, destructive git, production actions, or owner-only decisions"
            ),
            recommended_action=(
                "run a bounded long-chain vision replan before continuing a 15+ "
                "todo lane: read evidence, use public research if local evidence "
                "is weak, group/prune work, and write a concrete todo or vision delta"
            ),
        )
    if autonomous_replan_ack_has_frontier_delta(latest_replan_ack):
        return None
    if not _is_monitor_only_lane(work_lane_contract):
        return None
    if agent_counts.get("monitor", 0) <= 0:
        return None
    if agent_counts.get("advancement", 0) > 0 or total_frontier_advancement > 0:
        return None
    future_schedule_present = _monitor_only_lane_has_future_schedule(agent_todo_summary)

    return build_autonomous_replan_obligation_payload(
        schema_version=AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
        stall_threshold=1,
        trigger_count=1,
        triggers=[
            {
                "kind": FRONTIER_EXHAUSTED_MONITOR_TRIGGER,
                "section": "goal_frontier_projection",
                "text": (
                    "current goal frontier has no current, unclaimed, or other-agent "
                    "advancement todo while only monitor work remains"
                ),
                "agent_id": agent_id,
                "agent_open_count": agent_counts.get("open", 0),
                "agent_monitor_open_count": agent_counts.get("monitor", 0),
                "future_monitor_schedule_present": future_schedule_present,
            }
        ],
        guidance_actions=[
            "create_successor",
            "supersede_monitor",
            "set_watch_expiry",
            "record_no_followup",
        ],
        todo_actions=[
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "run a compact goal-frontier replan: create a successor runnable "
                    "todo, supersede stale monitor work, set watch-lane expiry, or "
                    "record an explicit no-follow-up rationale"
                ),
            }
        ],
        stop_condition=(
            "stop if the replan requires private material, credentials, destructive git, "
            "production actions, or owner-only decisions"
        ),
        recommended_action=(
            "run a bounded goal-frontier replan before another monitor-only quiet "
            "poll: create successor work, supersede the monitor lane, set an expiry, "
            "record watch-lane continuation, or record no-follow-up"
        ),
    )


def build_goal_frontier_projection_from_summaries(
    *,
    goal_id: str,
    agent_id: str | None,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    replan_obligation: dict[str, Any] | None,
    acceptance_gaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    user_counts = _summary_task_counts(user_todo_summary)
    agent_counts = _summary_task_counts(agent_todo_summary)
    frontier_counts = _frontier_advancement_counts(
        agent_todo_summary=agent_todo_summary,
        agent_id=agent_id,
    )
    monitor_only_lane = _is_monitor_only_lane(work_lane_contract)
    return build_goal_frontier_projection(
        goal_id=goal_id,
        agent_id=agent_id,
        user_counts=user_counts,
        agent_counts=agent_counts,
        current_agent_claimed_advancement_count=frontier_counts[
            "current_agent_claimed_advancement_count"
        ],
        unclaimed_advancement_count=frontier_counts["unclaimed_advancement_count"],
        other_agent_claimed_advancement_count=frontier_counts[
            "other_agent_claimed_advancement_count"
        ],
        monitor_only_lane=monitor_only_lane,
        replan_obligation=replan_obligation,
        acceptance_gaps=acceptance_gaps,
        deferred_successors=_deferred_successors(
            agent_todo_summary,
            agent_id=agent_id,
        ),
    )


def build_goal_frontier_projection_context_from_status(
    *,
    goal_id: str,
    agent_id: str | None,
    primary_agent_id: str | None,
    status_payload: dict[str, Any],
    item: dict[str, Any],
    project_asset: dict[str, Any] | None,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    neutral_replan_ack_classifications: set[str],
) -> dict[str, Any]:
    """Build the quota-facing goal-frontier read model.

    Quota decides delivery permission, but this helper owns the goal-frontier
    state reduction: existing obligation scope, latest replan ACK, open
    per-agent vision gaps, derived replan obligation, and final projection.
    """

    replan_obligation = select_autonomous_replan_obligation(item, project_asset)
    replan_scope = autonomous_replan_scope_decision(
        replan_obligation,
        agent_id=agent_id,
        primary_agent_id=primary_agent_id,
    )
    if replan_scope.get("required") and not replan_scope.get("applies"):
        replan_obligation = None

    latest_agent_replan_ack = latest_autonomous_replan_ack_from_status_payload(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
        neutral_classifications=neutral_replan_ack_classifications,
    )
    latest_agent_vision = latest_agent_vision_from_status_payload(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    latest_missing_vision_checkpoint = latest_missing_vision_checkpoint_from_status_payload(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
    )
    acceptance_gaps = (
        acceptance_gaps_from_agent_vision(latest_agent_vision)
        + acceptance_gaps_from_vision_checkpoint(latest_missing_vision_checkpoint)
    )
    projected_replan_ack = projected_autonomous_replan_ack_for_agent(
        item,
        project_asset,
        agent_id=agent_id,
    )
    frontier_replan_obligation = derive_goal_frontier_replan_obligation_from_summaries(
        user_todo_summary=user_todo_summary,
        agent_todo_summary=agent_todo_summary,
        work_lane_contract=work_lane_contract,
        agent_id=agent_id,
        existing_replan_obligation=replan_obligation,
        latest_replan_ack=latest_agent_replan_ack or projected_replan_ack,
        acceptance_gaps=acceptance_gaps,
    )
    if frontier_replan_obligation:
        replan_obligation = frontier_replan_obligation
        replan_scope = autonomous_replan_scope_decision(
            replan_obligation,
            agent_id=agent_id,
            primary_agent_id=primary_agent_id,
        )

    goal_frontier_projection = build_goal_frontier_projection_from_summaries(
        goal_id=goal_id,
        agent_id=agent_id,
        user_todo_summary=user_todo_summary,
        agent_todo_summary=agent_todo_summary,
        work_lane_contract=work_lane_contract,
        replan_obligation=replan_obligation,
        acceptance_gaps=acceptance_gaps,
    )
    return {
        "schema_version": "goal_frontier_projection_context_v0",
        "replan_obligation": replan_obligation,
        "replan_scope": replan_scope,
        "goal_frontier_projection": goal_frontier_projection,
        "acceptance_gaps": acceptance_gaps,
        "latest_replan_ack": latest_agent_replan_ack,
        "projected_replan_ack": projected_replan_ack,
    }


def compact_replan_obligation(replan_obligation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": replan_obligation.get("schema_version"),
        "stall_threshold": replan_obligation.get("stall_threshold"),
        "trigger_count": replan_obligation.get("trigger_count"),
        "triggers": replan_obligation.get("triggers") or [],
        "stop_condition": replan_obligation.get("stop_condition"),
    }


def build_autonomous_replan_recommendation(
    replan_obligation: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "recommended_mode": AUTONOMOUS_REPLAN_REQUIRED_MODE,
        "notify": "DONT_NOTIFY",
        "replan_obligation": compact_replan_obligation(replan_obligation),
        "spend_policy": (
            "append exactly one heartbeat spend only after executing the selected "
            "replan slice, validating it, and writing back todo split/add/retire state"
        ),
        "reason": reason
        or (
            "status exposes an autonomous replan obligation; advance the goal-level "
            "planning-trigger slice before monitor-only or agent-scope wait classification"
        ),
    }


def build_autonomous_replan_decision(replan_obligation: dict[str, Any]) -> dict[str, Any]:
    triggers = (
        replan_obligation.get("triggers")
        if isinstance(replan_obligation.get("triggers"), list)
        else []
    )
    return {
        "schema_version": AUTONOMOUS_REPLAN_DECISION_SCHEMA_VERSION,
        "required": True,
        "decision": AUTONOMOUS_REPLAN_REQUIRED_MODE,
        "decision_plane": "goal_frontier_before_lane_quiet_or_agent_scope_wait",
        "not_disturbed_by": [
            "monitor_quiet_skip",
            "agent_scope_wait",
            "agent_scope_exhausted",
        ],
        "trigger_count": safe_non_negative_int(replan_obligation.get("trigger_count")),
        "triggers": [
            trigger.get("kind")
            for trigger in triggers
            if isinstance(trigger, dict) and trigger.get("kind")
        ],
    }


def build_goal_frontier_projection(
    *,
    goal_id: str,
    agent_id: str | None,
    user_counts: dict[str, int],
    agent_counts: dict[str, int],
    current_agent_claimed_advancement_count: int,
    unclaimed_advancement_count: int,
    other_agent_claimed_advancement_count: int,
    monitor_only_lane: bool,
    replan_obligation: dict[str, Any] | None,
    acceptance_gaps: list[dict[str, Any]] | None = None,
    deferred_successors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    replan_required = autonomous_replan_is_required(replan_obligation)
    blockers: list[str] = []
    if monitor_only_lane:
        blockers.append("monitor_only_lane")
    if (
        current_agent_claimed_advancement_count == 0
        and unclaimed_advancement_count == 0
        and other_agent_claimed_advancement_count > 0
    ):
        blockers.append("other_agent_claimed_advancement")
    if replan_required:
        blockers.append("autonomous_replan_obligation")

    compact_acceptance_gaps = [
        item for item in (acceptance_gaps or []) if isinstance(item, dict)
    ]
    vision_continuation_audit = build_vision_continuation_audit(
        goal_id=goal_id,
        agent_id=agent_id,
        acceptance_gaps=compact_acceptance_gaps,
    )
    projection: dict[str, Any] = {
        "schema_version": GOAL_FRONTIER_PROJECTION_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": agent_id,
        "source": "quota_should_run",
        "normalized_progress": {
            "user_open_count": user_counts.get("open", 0),
            "agent_open_count": agent_counts.get("open", 0),
            "agent_advancement_open_count": agent_counts.get("advancement", 0),
            "agent_monitor_open_count": agent_counts.get("monitor", 0),
            "agent_monitor_due_count": agent_counts.get("monitor_due", 0),
        },
        "remaining_advancement_frontier": {
            "current_agent_claimed_advancement_count": current_agent_claimed_advancement_count,
            "unclaimed_advancement_count": unclaimed_advancement_count,
            "other_agent_claimed_advancement_count": other_agent_claimed_advancement_count,
        },
        "monitor_only_lanes": {
            "present": monitor_only_lane,
            "quiet_until_material_transition": monitor_only_lane,
        },
        "deferred_successors": deferred_successors
        if isinstance(deferred_successors, dict)
        else {
            "ready_count": 0,
            "blocked_count": 0,
            "current_agent_ready_count": 0,
            "ready_todo_ids": [],
        },
        "acceptance_gaps": compact_acceptance_gaps[:5],
        "autonomy_blockers": blockers,
        "replan_required": replan_required,
    }
    if vision_continuation_audit:
        projection["vision_continuation_audit"] = vision_continuation_audit
    if replan_required and isinstance(replan_obligation, dict):
        projection["autonomous_replan_decision"] = build_autonomous_replan_decision(
            replan_obligation
        )
    return projection
