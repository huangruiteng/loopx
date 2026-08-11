from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from ...file_lock import exclusive_file_lock
from ..agents.workspace_guard import (
    build_delivery_workspace_guard,
    delivery_workspace_repository,
)
from ..turn_effect import (
    find_turn_effect_record,
    normalize_turn_effect_key,
    require_matching_turn_effect,
    turn_effect_input_hash,
)
from ..runtime.run_artifacts import (
    next_run_artifact_paths,
    reserve_run_artifact_paths,
    run_file_stem,
)
from ..runtime.time import now_local_iso
from ..todos.contract import normalize_todo_claimed_by, normalize_todo_id
from ..work_items.delivery_outcome import (
    ACCOUNTABLE_DELIVERY_OUTCOMES,
    normalize_delivery_outcome,
)
from .decision_summary import compact_quota_decision, quota_decision_agent_id
from .monitor_poll import QUOTA_MONITOR_POLL_CLASSIFICATION
from .scheduler_ack import QUOTA_SCHEDULER_ACK_CLASSIFICATION
from .settlement import (
    SettlementIdentity,
    infer_persisted_heartbeat_settlement_identity,
    require_settlement_writeback,
    resolve_heartbeat_settlement_identity,
    resolve_settlement_delivery_workspace_causality,
    settlement_result_payload,
)
from .settlement_workspace_causality import completed_todo_workspace_causality
from .spend_sources import DEFAULT_SLOT_SPEND_SOURCE, VALID_SLOT_SPEND_SOURCES

QUOTA_SLOT_SPENT_CLASSIFICATION = "quota_slot_spent"
QUOTA_SLOT_VOIDED_CLASSIFICATION = "quota_slot_voided"

QuotaDecisionBuilder = Callable[[dict[str, Any]], dict[str, Any]]
QuotaStatusBuilder = Callable[..., dict[str, Any]]


def _todo_binding_error(
    *,
    source: str,
    before: dict[str, Any],
    requested_todo_id: str | None,
    settlement_identity: SettlementIdentity | None = None,
) -> str | None:
    if settlement_identity is not None:
        if requested_todo_id != settlement_identity.todo_id:
            return (
                "quota spend Todo does not match the original settlement identity: "
                f"expected {settlement_identity.todo_id} but received "
                f"{requested_todo_id or 'missing'}"
            )
        return None
    selected = before.get("selected_todo") if isinstance(before.get("selected_todo"), dict) else {}
    selected_todo_id = normalize_todo_id(selected.get("todo_id"))
    if requested_todo_id and selected_todo_id and requested_todo_id != selected_todo_id:
        return (
            f"quota spend todo binding mismatch: selected todo is "
            f"{selected_todo_id} but --todo-id is {requested_todo_id}; "
            "complete or update the selected todo first, or record a replan"
        )
    if (
        source == DEFAULT_SLOT_SPEND_SOURCE
        and before.get("normal_delivery_allowed") is True
        and selected_todo_id
        and not requested_todo_id
    ):
        return (
            f"quota spend requires --todo-id {selected_todo_id} for heartbeat "
            "delivery so the accounted turn is bound to the selected todo"
        )
    return None


def _resolve_preview_settlement(
    *,
    raw_runtime_root: Any,
    source: str,
    goal_id: str,
    agent_id: str | None,
    todo_id: str | None,
    turn_instance_id: str | None,
) -> dict[str, Any]:
    if turn_instance_id and source != DEFAULT_SLOT_SPEND_SOURCE:
        return {"reason": "turn-scoped settlement is valid only for heartbeat spend"}
    if turn_instance_id and not raw_runtime_root:
        return {"reason": "status payload does not include runtime_root"}
    if source != DEFAULT_SLOT_SPEND_SOURCE or not raw_runtime_root:
        return {}

    runtime_root = Path(str(raw_runtime_root)).expanduser()
    result = (
        resolve_heartbeat_settlement_identity(
            runtime_root,
            goal_id=goal_id,
            agent_id=agent_id,
            todo_id=todo_id,
            turn_instance_id=turn_instance_id,
        )
        if turn_instance_id
        else infer_persisted_heartbeat_settlement_identity(
            runtime_root,
            goal_id=goal_id,
            agent_id=agent_id,
            todo_id=todo_id,
        )
    )
    if result is None:
        return {}
    identity = result.value if result.failure is None else None
    delivery_workspace_causality = (
        resolve_settlement_delivery_workspace_causality(runtime_root, identity)
        if identity is not None
        else None
    )
    if identity is not None:
        result = result.bind(
            lambda resolved: require_settlement_writeback(
                runtime_root,
                resolved,
            )
        )
    return {
        "identity": identity,
        "result": result,
        "delivery_run": result.value if result.failure is None else None,
        "delivery_workspace_causality": delivery_workspace_causality,
        "reason": result.failure.reason if result.failure is not None else None,
    }


def _now_local() -> str:
    return now_local_iso()


def _validate_goal_id_path_segment(goal_id: str) -> str:
    value = goal_id.strip()
    if not value:
        raise ValueError("goal id is required")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("goal id must be a single path segment")
    if Path(value).name != value:
        raise ValueError("goal id must not include path traversal")
    return value


def _int_number(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return default
    return default


def _queue_item_for_goal(status_payload: dict[str, Any], *, goal_id: str) -> dict[str, Any]:
    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    return next(
        (
            item
            for item in queue_items
            if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id
        ),
        {},
    )


def _set_quota_for_goal(status_payload: dict[str, Any], *, goal_id: str, quota: dict[str, Any]) -> None:
    run_history = status_payload.get("run_history") if isinstance(status_payload.get("run_history"), dict) else {}
    run_goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    for goal in run_goals:
        if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
            goal["quota"] = dict(quota)

    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in queue_items:
        if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id:
            item["quota"] = dict(quota)
            project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
            if project_asset:
                project_asset["quota"] = dict(quota)


def _load_goal_run_index_records(runtime_root: Path, goal_id: str) -> list[dict[str, Any]]:
    index_path = runtime_root / "goals" / goal_id / "runs" / "index.jsonl"
    if not index_path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _is_quota_neutral_state_refresh(run: dict[str, Any]) -> bool:
    """Recognize refresh-state provenance without relying on its classification."""

    if str(run.get("delivery_outcome") or "").strip():
        return False
    if str(run.get("classification") or "").strip() == "state_refreshed":
        return True
    return (
        isinstance(run.get("state"), dict)
        and isinstance(run.get("runtime_projection_route"), dict)
        and bool(str(run.get("recommended_action_source") or "").strip())
    )


def _latest_unspent_accountable_delivery_run(
    runtime_root: Path,
    goal_id: str,
    *,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the latest same-agent delivery that still needs accounting.

    Unchanged monitor polls, scheduler acknowledgements, and plain state
    refreshes are quota-neutral. They may occur after validation and before
    accounting, so they must not hide the accountable run. A state refresh
    with an explicit non-accountable delivery outcome and other non-delivery
    events remain fail closed.
    """

    safe_agent_id = normalize_todo_claimed_by(agent_id)
    for run in reversed(_load_goal_run_index_records(runtime_root, goal_id)):
        run_agent_id = normalize_todo_claimed_by(run.get("agent_id"))
        if safe_agent_id and run_agent_id and safe_agent_id != run_agent_id:
            continue
        classification = str(run.get("classification") or "").strip()
        if classification == QUOTA_SLOT_VOIDED_CLASSIFICATION:
            continue
        if classification == QUOTA_SLOT_SPENT_CLASSIFICATION:
            return None
        if (
            classification == QUOTA_MONITOR_POLL_CLASSIFICATION
            and run.get("material_change") is not True
        ):
            continue
        if classification == QUOTA_SCHEDULER_ACK_CLASSIFICATION:
            continue
        if _is_quota_neutral_state_refresh(run):
            continue
        delivery_outcome = normalize_delivery_outcome(run.get("delivery_outcome"))
        if delivery_outcome in ACCOUNTABLE_DELIVERY_OUTCOMES:
            return run
        return None
    return None


def _missing_delivery_workspace_preview(
    *,
    delivery_workspace_causality: dict[str, Any] | None,
    delivery_workspace: dict[str, Any] | None,
    goal_id: str,
    slots: int,
    agent_id: str | None,
    before: dict[str, Any],
) -> dict[str, Any] | None:
    requirement = str(
        (delivery_workspace_causality or {}).get("requirement") or ""
    )
    if (
        not delivery_workspace_causality
        or requirement == "not_required"
        or delivery_workspace_repository(delivery_workspace)
    ):
        return None
    return {
        "ok": False,
        "mode": "spend-slot",
        "dry_run": True,
        "goal_id": goal_id,
        "slots": slots,
        "agent_id": agent_id,
        "appended": False,
        "registry_mutated": False,
        "reason": (
            "quota spend requires a valid delivery workspace snapshot for "
            f"settlement causality requirement {requirement}"
        ),
        "delivery_workspace": delivery_workspace,
        "delivery_workspace_causality": delivery_workspace_causality,
        "delivery_workspace_validated": False,
        "before": before,
        "after": None,
    }


def build_quota_slot_preview_for_decision(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    before: dict[str, Any],
    after_decision: QuotaDecisionBuilder,
    quota_status_builder: QuotaStatusBuilder,
    self_repair_spend_actions: set[str] | frozenset[str],
    slots: int = 1,
    agent_id: str | None = None,
    workspace_path: Path | None = None,
    todo_id: str | None = None,
    turn_instance_id: str | None = None,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    safe_slots = max(1, _int_number(slots, default=1))
    safe_requested_agent_id = normalize_todo_claimed_by(agent_id)
    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    raw_runtime_root = status_payload.get("runtime_root")
    settlement_identity = None
    settlement_result = None
    delivery_completion_run = None
    delivery_workspace_causality = None
    settlement = _resolve_preview_settlement(
        raw_runtime_root=raw_runtime_root,
        source=source,
        goal_id=safe_goal_id,
        agent_id=safe_requested_agent_id,
        todo_id=normalized_todo_id,
        turn_instance_id=turn_instance_id,
    )
    settlement_identity = settlement.get("identity")
    settlement_result = settlement.get("result")
    delivery_completion_run = settlement.get("delivery_run")
    delivery_workspace_causality = settlement.get(
        "delivery_workspace_causality"
    )
    if settlement.get("reason"):
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "reason": settlement["reason"],
            "settlement_result": (
                settlement_result_payload(settlement_result)
                if settlement_result is not None
                else None
            ),
            "before": before,
            "after": None,
        }
    binding_error = _todo_binding_error(
        source=source,
        before=before,
        requested_todo_id=normalized_todo_id,
        settlement_identity=settlement_identity,
    )
    if binding_error:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "reason": binding_error,
            "before": before,
            "after": None,
        }
    safe_bypass_requested = (
        (
            before.get("state") == "operator_gate"
            or before.get("recovery_delivery_allowed") is True
            or before.get("effective_action") == "outcome_floor_recovery"
        )
        and before.get("safe_bypass_allowed") is True
    )
    self_repair_spend = before.get("effective_action") in self_repair_spend_actions
    capability_repair_spend = (
        before.get("effective_action") == "capability_bridge_repair"
        and before.get("capability_repair_allowed") is True
    )
    delivery_completion_run = delivery_completion_run or (
        _latest_unspent_accountable_delivery_run(
            Path(str(raw_runtime_root)).expanduser(),
            safe_goal_id,
            agent_id=safe_requested_agent_id,
        )
        if raw_runtime_root
        else None
    )
    if settlement_identity is not None and not delivery_workspace_causality:
        delivery_workspace_causality = completed_todo_workspace_causality(
            status_payload,
            goal_id=safe_goal_id,
            todo_id=settlement_identity.todo_id,
        )
    safe_bypass_without_delivery = (
        safe_bypass_requested and delivery_completion_run is None
    )
    if safe_bypass_without_delivery:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "reason": (
                "safe-bypass quota spend requires a latest "
                "unspent accountable delivery writeback"
            ),
            "before": before,
            "after": None,
        }
    safe_bypass_spend = safe_bypass_requested
    raw_delivery_workspace = (
        delivery_completion_run.get("delivery_workspace")
        if isinstance(delivery_completion_run, dict)
        and isinstance(delivery_completion_run.get("delivery_workspace"), dict)
        else None
    )
    missing_delivery_workspace_preview = _missing_delivery_workspace_preview(
        delivery_workspace_causality=delivery_workspace_causality,
        delivery_workspace=raw_delivery_workspace,
        goal_id=safe_goal_id,
        slots=safe_slots,
        agent_id=safe_requested_agent_id,
        before=before,
    )
    if missing_delivery_workspace_preview:
        return missing_delivery_workspace_preview
    workspace_requirement = str(
        (delivery_workspace_causality or {}).get("requirement") or ""
    )
    raw_delivery_workspace_repository = delivery_workspace_repository(
        raw_delivery_workspace
    )
    delivery_workspace = (
        raw_delivery_workspace
        if raw_delivery_workspace_repository
        and workspace_requirement != "not_required"
        else None
    )
    delivery_workspace_guard = (
        build_delivery_workspace_guard(
            delivery_completion_run,
            agent_id=safe_requested_agent_id,
            current_path=workspace_path,
        )
        if delivery_completion_run and delivery_workspace
        else None
    )
    if delivery_workspace_guard:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "reason": delivery_workspace_guard["reason"],
            "workspace_guard": delivery_workspace_guard,
            "delivery_workspace": delivery_workspace,
            "delivery_workspace_causality": delivery_workspace_causality,
            "delivery_workspace_validated": False,
            "before": before,
            "after": None,
        }
    delivery_workspace_validated = bool(delivery_workspace)
    workspace_repair_no_spend = (
        before.get("effective_action") == "agent_workspace_repair"
        and before.get("workspace_repair_allowed") is True
        and not delivery_workspace_validated
    )
    if workspace_repair_no_spend:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "delivery_workspace": delivery_workspace,
            "delivery_workspace_causality": delivery_workspace_causality,
            "delivery_workspace_validated": False,
            "reason": (
                "agent workspace guard requires moving to an independent "
                "worktree and rerunning quota should-run before quota spend"
            ),
            "before": before,
            "after": None,
        }
    delivery_completion_spend = (
        delivery_completion_run is not None
        and before.get("ok")
        and (
            settlement_identity is not None
            or not before.get("should_run")
            or before.get("effective_action") == "external_evidence_observe"
            or (
                before.get("effective_action") == "agent_workspace_repair"
                and delivery_workspace_validated
            )
        )
        and before.get("effective_action") != "automation_prompt_upgrade_required"
        and not safe_bypass_spend
        and str(before.get("state") or "") in {"waiting", "focus_wait", "operator_gate", "eligible"}
    )
    if not before.get("ok") or (
        not before.get("should_run")
        and not safe_bypass_spend
        and not capability_repair_spend
        and not delivery_completion_spend
    ):
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "reason": before.get("reason") or "goal is not eligible for quota accounting preview",
            "before": before,
            "after": None,
        }
    before_quota = before.get("quota") if isinstance(before.get("quota"), dict) else {}
    if not before_quota:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "agent_id": safe_requested_agent_id,
            "appended": False,
            "registry_mutated": False,
            "reason": "goal has no quota payload to preview",
            "before": before,
            "after": None,
        }

    queue_item = _queue_item_for_goal(status_payload, goal_id=safe_goal_id)
    after_status = deepcopy(status_payload)
    after_goal = {
        "quota": {
            **before_quota,
            "spent_slots": _int_number(before_quota.get("spent_slots"), default=0) + safe_slots,
        }
    }
    after_quota = quota_status_builder(
        after_goal,
        waiting_on=str(before.get("waiting_on") or ""),
        severity=str(queue_item.get("severity") or ""),
        lifecycle_phase=before.get("lifecycle_phase") or queue_item.get("lifecycle_phase"),
        lifecycle_flags=before.get("lifecycle_flags") or queue_item.get("lifecycle_flags"),
        status=before.get("status") or queue_item.get("status"),
    )
    _set_quota_for_goal(after_status, goal_id=safe_goal_id, quota=after_quota)
    after = after_decision(after_status)

    return {
        "ok": True,
        "mode": "spend-slot",
        "dry_run": True,
        "goal_id": safe_goal_id,
        "slots": safe_slots,
        "agent_id": safe_requested_agent_id,
        "appended": False,
        "registry_mutated": False,
        "before": before,
        "after": after,
        "would_throttle": after.get("state") == "throttled",
        "reason": (
            f"dry-run preview: spending {safe_slots} slot(s) accounts for latest "
            f"validated delivery {delivery_completion_run.get('classification')} "
            f"after current {before.get('state')} guard"
            if delivery_completion_spend and delivery_completion_run
            else (
                f"dry-run preview: spending {safe_slots} slot(s) would move "
                f"{safe_goal_id} from {before.get('state')} to {after.get('state')}"
            )
        ),
        "rolling_window_note": (
            "before -> after is a same-status-payload projection. Later quota status "
            "recomputes spent_slots from quota_slot_spent events still inside window_hours, "
            "so the visible total can stay flat if an older spend expires."
        ),
        "todo_id": normalized_todo_id,
        "turn_instance_id": (
            settlement_identity.turn_instance_id
            if settlement_identity is not None
            else None
        ),
        "settlement_identity": (
            settlement_identity.as_dict()
            if settlement_identity is not None
            else None
        ),
        "settlement_result": (
            settlement_result_payload(settlement_result)
            if settlement_result is not None
            else None
        ),
        "safe_bypass_spend": safe_bypass_spend,
        "self_repair_spend": self_repair_spend,
        "capability_repair_spend": capability_repair_spend,
        "delivery_completion_spend": delivery_completion_spend,
        "delivery_run_generated_at": delivery_completion_run.get("generated_at")
        if delivery_completion_run
        else None,
        "delivery_run_classification": delivery_completion_run.get("classification")
        if delivery_completion_run
        else None,
        "delivery_run_agent_id": normalize_todo_claimed_by(delivery_completion_run.get("agent_id"))
        if delivery_completion_run
        else None,
        "delivery_run_recommended_action": delivery_completion_run.get("recommended_action")
        if delivery_completion_run
        else None,
        "delivery_workspace": delivery_workspace,
        "delivery_workspace_causality": delivery_workspace_causality,
        "delivery_workspace_validated": delivery_workspace_validated,
    }


def build_quota_slot_spend_event(
    preview: dict[str, Any],
    *,
    self_repair_spend_actions: set[str] | frozenset[str],
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not preview.get("ok"):
        raise ValueError(preview.get("reason") or "quota slot spend requires an eligible preview")
    safe_source = str(source or DEFAULT_SLOT_SPEND_SOURCE).strip()
    if safe_source not in VALID_SLOT_SPEND_SOURCES:
        raise ValueError(f"quota slot spend source must be one of: {', '.join(sorted(VALID_SLOT_SPEND_SOURCES))}")
    before = preview.get("before") if isinstance(preview.get("before"), dict) else {}
    after = preview.get("after") if isinstance(preview.get("after"), dict) else {}
    safe_agent_id = normalize_todo_claimed_by(preview.get("agent_id")) or quota_decision_agent_id(before)
    slots = max(1, _int_number(preview.get("slots"), default=1))
    before_compact = compact_quota_decision(before)
    after_compact = compact_quota_decision(after)
    if _int_number(after_compact.get("spent_slots"), default=0) != _int_number(
        before_compact.get("spent_slots"), default=0
    ) + slots:
        raise ValueError("after.spent_slots must equal before.spent_slots + slots")
    self_repair_spend = (
        before_compact["should_run"] is True
        and before_compact["effective_action"] in self_repair_spend_actions
        and before_compact["self_repair_allowed"] is True
    )
    capability_repair_spend = (
        before_compact["should_run"] is True
        and before_compact["effective_action"] == "capability_bridge_repair"
        and before_compact["capability_repair_allowed"] is True
    )
    delivery_completion_spend = bool(preview.get("delivery_completion_spend"))
    eligible_spend = (
        before_compact["should_run"] is True
        and before_compact["state"] == "eligible"
        and before_compact["effective_action"] != "external_evidence_observe"
        and not self_repair_spend
        and not capability_repair_spend
        and before_compact["workspace_repair_allowed"] is not True
        and not delivery_completion_spend
    )
    safe_bypass_spend = bool(preview.get("safe_bypass_spend")) and (
        (
            before_compact["state"] == "operator_gate"
            or before_compact["recovery_delivery_allowed"] is True
            or before_compact["effective_action"] == "outcome_floor_recovery"
        )
        and before_compact["safe_bypass_allowed"] is True
    )
    if (
        not eligible_spend
        and not safe_bypass_spend
        and not self_repair_spend
        and not capability_repair_spend
        and not delivery_completion_spend
    ):
        raise ValueError(
            "quota slot spend requires an eligible, safe-bypass, control-plane self-repair, "
            "capability bridge repair, or latest validated delivery-completion quota should-run decision"
        )

    delivery_run_action = str(preview.get("delivery_run_recommended_action") or "").strip()
    record = {
        "generated_at": generated_at or _now_local(),
        "goal_id": preview.get("goal_id"),
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "recommended_action": (
            delivery_run_action
            if delivery_completion_spend and delivery_run_action
            else after.get("recommended_action") or "inspect next quota should-run decision"
        ),
        "health_check": (
            "quota should-run eligible; quota slot spend event public-safe"
            if eligible_spend
            else (
                "quota outcome-floor recovery safe-bypass; quota slot spend event public-safe"
                if before_compact.get("effective_action") == "outcome_floor_recovery"
                else (
                    "quota control-plane self-repair; quota slot spend event public-safe"
                    if self_repair_spend
                    else (
                        "quota capability bridge repair; quota slot spend event public-safe"
                        if capability_repair_spend
                        else (
                            "quota validated delivery completion; quota slot spend event public-safe"
                            if delivery_completion_spend
                            else "quota safe-bypass delivery; quota slot spend event public-safe"
                        )
                    )
                )
            )
        ),
        "quota_event": {
            "event_type": QUOTA_SLOT_SPENT_CLASSIFICATION,
            "source": safe_source,
            "todo_id": preview.get("todo_id"),
            "turn_instance_id": preview.get("turn_instance_id"),
            "settlement_identity": preview.get("settlement_identity"),
            "slots": slots,
            "reason_summary": (
                f"{slots} automatic agent slot(s) completed under an eligible quota guard"
                if eligible_spend
                else (
                    f"{slots} automatic agent slot(s) completed as outcome-floor recovery safe-bypass work"
                    if before_compact.get("effective_action") == "outcome_floor_recovery"
                    else (
                        f"{slots} automatic agent slot(s) completed as control-plane self-repair work"
                        if self_repair_spend
                        else (
                            f"{slots} automatic agent slot(s) completed as capability bridge repair work"
                            if capability_repair_spend
                            else (
                                f"{slots} automatic agent slot(s) accounted after validated delivery "
                                f"{preview.get('delivery_run_classification')}"
                                if delivery_completion_spend
                                else f"{slots} automatic agent slot(s) completed as safe-bypass work"
                            )
                        )
                    )
                )
            ),
            "delivery_run_generated_at": preview.get("delivery_run_generated_at"),
            "delivery_run_classification": preview.get("delivery_run_classification"),
            "delivery_run_agent_id": preview.get("delivery_run_agent_id"),
            "delivery_run_recommended_action": delivery_run_action or None,
            "delivery_workspace": preview.get("delivery_workspace"),
            "delivery_workspace_causality": preview.get(
                "delivery_workspace_causality"
            ),
            "delivery_workspace_validated": bool(
                preview.get("delivery_workspace_validated")
            ),
            "before": before_compact,
            "after": after_compact,
        },
    }
    if safe_agent_id:
        record["agent_id"] = safe_agent_id
        record["quota_event"]["agent_id"] = safe_agent_id
    if preview.get("turn_instance_id"):
        record["turn_instance_id"] = preview["turn_instance_id"]
        record["todo_id"] = preview.get("todo_id")
        record["settlement_identity"] = preview.get("settlement_identity")
    return record


def _find_quota_spend_run(
    runtime_root: Path,
    *,
    goal_id: str,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for run in reversed(_load_goal_run_index_records(runtime_root, goal_id)):
        if str(run.get("goal_id") or goal_id) != goal_id:
            continue
        if str(run.get("generated_at") or "") != generated_at:
            continue
        if str(run.get("classification") or "") != QUOTA_SLOT_SPENT_CLASSIFICATION:
            continue
        event = load_quota_event_from_run(run)
        if not event or str(event.get("event_type") or "") != QUOTA_SLOT_SPENT_CLASSIFICATION:
            continue
        return run, event
    return None


def load_quota_event_from_run(run: dict[str, Any]) -> dict[str, Any] | None:
    if str(run.get("classification") or "") not in {
        QUOTA_SLOT_SPENT_CLASSIFICATION,
        QUOTA_SLOT_VOIDED_CLASSIFICATION,
    }:
        return None
    event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else None
    if event:
        return event

    raw_json_path = str(run.get("json_path") or "")
    if not raw_json_path:
        return None
    json_path = Path(raw_json_path).expanduser()
    if not json_path.exists():
        return None
    try:
        record = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    event = record.get("quota_event") if isinstance(record.get("quota_event"), dict) else None
    return event


def build_quota_slot_void_preview_for_decision(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    voided_run_generated_at: str,
    before: dict[str, Any],
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    safe_voided_at = str(voided_run_generated_at or "").strip()
    if not safe_voided_at:
        return {
            "ok": False,
            "mode": "void-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "appended": False,
            "registry_mutated": False,
            "reason": "`quota void-slot` requires --void-generated-at",
        }

    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    target = _find_quota_spend_run(runtime_root, goal_id=safe_goal_id, generated_at=safe_voided_at)
    if target is None:
        return {
            "ok": False,
            "mode": "void-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "voided_run_generated_at": safe_voided_at,
            "appended": False,
            "registry_mutated": False,
            "reason": "target quota_slot_spent run was not found in the goal runtime index",
        }
    target_run, target_event = target
    slots = max(1, _int_number(target_event.get("slots"), default=1))
    before_quota = before.get("quota") if isinstance(before.get("quota"), dict) else {}
    after = deepcopy(before)
    after_quota = deepcopy(before_quota)
    after_quota["spent_slots"] = max(0, _int_number(before_quota.get("spent_slots"), default=0) - slots)
    after["quota"] = after_quota
    return {
        "ok": True,
        "mode": "void-slot",
        "dry_run": True,
        "goal_id": safe_goal_id,
        "slots": slots,
        "voided_run_generated_at": safe_voided_at,
        "voided_run_classification": target_run.get("classification"),
        "voided_run_json_path": target_run.get("json_path"),
        "appended": False,
        "registry_mutated": False,
        "before": before,
        "after": after,
        "would_throttle": False,
        "reason": (
            f"dry-run preview: voiding {slots} slot(s) from {safe_goal_id} "
            f"quota spend run {safe_voided_at}"
        ),
        "rolling_window_note": (
            "quota void-slot appends a quota_slot_voided accounting event. It does not delete the "
            "original spend event; rolling-window ledgers subtract the void only when the target "
            "spend event is inside the same accounting window."
        ),
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
    }


def build_quota_slot_void_event(
    preview: dict[str, Any],
    *,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not preview.get("ok"):
        raise ValueError(preview.get("reason") or "quota slot void requires a valid preview")
    safe_source = str(source or DEFAULT_SLOT_SPEND_SOURCE).strip()
    if safe_source not in VALID_SLOT_SPEND_SOURCES:
        raise ValueError(f"quota slot void source must be one of: {', '.join(sorted(VALID_SLOT_SPEND_SOURCES))}")
    safe_reason = str(reason_summary or "").strip() or "void duplicate or invalid quota slot spend event"
    before = preview.get("before") if isinstance(preview.get("before"), dict) else {}
    after = preview.get("after") if isinstance(preview.get("after"), dict) else {}
    safe_agent_id = quota_decision_agent_id(before)
    record = {
        "generated_at": generated_at or _now_local(),
        "goal_id": preview.get("goal_id"),
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
        "recommended_action": safe_reason,
        "health_check": "quota slot void event public-safe; original spend preserved for audit",
        "quota_event": {
            "event_type": QUOTA_SLOT_VOIDED_CLASSIFICATION,
            "source": safe_source,
            "slots": max(1, _int_number(preview.get("slots"), default=1)),
            "reason_summary": safe_reason,
            "voided_run_generated_at": preview.get("voided_run_generated_at"),
            "voided_run_classification": preview.get("voided_run_classification"),
            "before": compact_quota_decision(before) if before else {},
            "after": compact_quota_decision(after) if after else {},
        },
    }
    if safe_agent_id:
        record["agent_id"] = safe_agent_id
        record["quota_event"]["agent_id"] = safe_agent_id
    return record


def record_quota_slot_void_from_preview(
    preview: dict[str, Any],
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    render_markdown: Callable[[dict[str, Any]], str],
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    if not preview.get("ok"):
        return preview

    generated_at = _now_local()
    record = build_quota_slot_void_event(
        preview,
        source=source,
        reason_summary=reason_summary,
        generated_at=generated_at,
    )
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    stem = run_file_stem(generated_at)
    path_allocator = reserve_run_artifact_paths if execute else next_run_artifact_paths
    json_path, markdown_path = path_allocator(runs_dir, stem, "quota-slot-voided")
    index_path = runs_dir / "index.jsonl"
    index_record = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
        "recommended_action": record["recommended_action"],
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if record.get("agent_id"):
        index_record["agent_id"] = record["agent_id"]
    payload = {
        **preview,
        "dry_run": not execute,
        "appended": execute,
        "registry_mutated": False,
        "source": record["quota_event"]["source"],
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
        "generated_at": generated_at,
        "agent_id": record.get("agent_id"),
        "quota_event": record["quota_event"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "reason": (
            f"{'appended' if execute else 'dry-run preview'} quota slot void event: "
            f"{safe_goal_id} voided {record['quota_event']['slots']} slot(s) from "
            f"{record['quota_event']['voided_run_generated_at']}"
        ),
    }
    if execute:
        payload["before"] = record["quota_event"]["before"]
        payload["after"] = record["quota_event"]["after"]
    if execute:
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def _record_quota_slot_spend_from_preview(
    preview: dict[str, Any],
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    self_repair_spend_actions: set[str] | frozenset[str],
    render_markdown: Callable[[dict[str, Any]], str],
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    _turn_effect_key: str | None = None,
    _effect_input_hash: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    if not preview.get("ok"):
        return preview

    generated_at = _now_local()
    record = build_quota_slot_spend_event(
        preview,
        self_repair_spend_actions=self_repair_spend_actions,
        source=source,
        generated_at=generated_at,
    )
    if _turn_effect_key is not None:
        if _effect_input_hash is None:
            raise ValueError("turn effect input hash is required")
        record["turn_effect_key"] = _turn_effect_key
        record["effect_input_hash"] = _effect_input_hash
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    stem = run_file_stem(generated_at)
    path_allocator = reserve_run_artifact_paths if execute else next_run_artifact_paths
    json_path, markdown_path = path_allocator(runs_dir, stem, "quota-slot-spent")
    index_path = runs_dir / "index.jsonl"
    index_record = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "recommended_action": record["recommended_action"],
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if _turn_effect_key is not None:
        index_record["turn_effect_key"] = _turn_effect_key
        index_record["effect_input_hash"] = _effect_input_hash
    if record.get("agent_id"):
        index_record["agent_id"] = record["agent_id"]
    for field in ("turn_instance_id", "todo_id", "settlement_identity"):
        if record.get(field):
            index_record[field] = record[field]

    payload = {
        **preview,
        "dry_run": not execute,
        "appended": execute,
        "registry_mutated": False,
        "source": record["quota_event"]["source"],
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "generated_at": generated_at,
        "agent_id": record.get("agent_id"),
        "quota_event": record["quota_event"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "reason": (
            f"{'appended' if execute else 'dry-run preview'} quota slot spend event: "
            f"{safe_goal_id} {record['quota_event']['before']['spent_slots']}->"
            f"{record['quota_event']['after']['spent_slots']} slots"
        ),
    }
    if _turn_effect_key is not None:
        payload["turn_effect_key"] = _turn_effect_key
        payload["effect_input_hash"] = _effect_input_hash
        payload["idempotent"] = False
    if execute:
        payload["before"] = record["quota_event"]["before"]
        payload["after"] = record["quota_event"]["after"]
    if execute:
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def record_quota_slot_spend_from_preview(
    preview: dict[str, Any],
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    self_repair_spend_actions: set[str] | frozenset[str],
    render_markdown: Callable[[dict[str, Any]], str],
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    turn_effect_key: str | None = None,
) -> dict[str, Any]:
    normalized_effect_key = normalize_turn_effect_key(turn_effect_key)
    effect_input_hash = (
        turn_effect_input_hash(
            {
                "preview": preview,
                "goal_id": goal_id,
                "source": source,
                "self_repair_spend_actions": sorted(self_repair_spend_actions),
                "execute": execute,
            }
        )
        if normalized_effect_key is not None
        else None
    )
    def write_once() -> dict[str, Any]:
        return _record_quota_slot_spend_from_preview(
            preview,
            status_payload,
            goal_id=goal_id,
            self_repair_spend_actions=self_repair_spend_actions,
            render_markdown=render_markdown,
            execute=execute,
            source=source,
            _turn_effect_key=normalized_effect_key,
            _effect_input_hash=effect_input_hash,
        )

    if normalized_effect_key is None or not execute:
        return write_once()
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    index_path = runtime_root / "goals" / safe_goal_id / "runs" / "index.jsonl"
    with exclusive_file_lock(
        index_path,
        agent_id=preview.get("agent_id"),
        operation="quota_spend_turn_effect",
    ):
        existing = find_turn_effect_record(index_path, normalized_effect_key)
        if existing is not None:
            assert effect_input_hash is not None
            require_matching_turn_effect(existing, effect_input_hash)
            quota_event = load_quota_event_from_run(existing)
            if quota_event is None:
                raise ValueError("turn effect durable record is missing quota_event")
            before = quota_event.get("before")
            after = quota_event.get("after")
            if not isinstance(before, dict) or not isinstance(after, dict):
                raise ValueError("turn effect durable quota_event is incomplete")
            return {
                **preview,
                "ok": True,
                "dry_run": False,
                "appended": False,
                "idempotent": True,
                "idempotent_replay": True,
                "registry_mutated": False,
                "source": quota_event.get("source"),
                "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
                "generated_at": existing.get("generated_at"),
                "agent_id": existing.get("agent_id"),
                "quota_event": quota_event,
                "before": before,
                "after": after,
                "json_path": existing.get("json_path"),
                "markdown_path": existing.get("markdown_path"),
                "index_path": str(index_path),
                "turn_effect_key": normalized_effect_key,
                "effect_input_hash": effect_input_hash,
                "reason": "quota slot spend replayed for the same Turn effect",
            }
        return write_once()
