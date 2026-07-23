from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from ...file_lock import exclusive_file_lock
from ...turn_identity import normalize_turn_instance_id
from .decision_summary import compact_quota_decision, quota_decision_agent_id
from .spend_sources import DEFAULT_SLOT_SPEND_SOURCE, VALID_SLOT_SPEND_SOURCES
from ..runtime.time import now_local_iso
from ..runtime.run_artifacts import (
    next_run_artifact_paths,
    reserve_run_artifact_paths,
    run_file_stem,
)
from ..scheduler.monitor_poll_policy import (
    allows_no_spend_blocked_successor_wait_poll,
    allows_due_monitor_poll,
    allows_no_spend_external_monitor_poll,
    work_lane_reason_codes,
)
from ..scheduler.monitor_todo import monitor_todo_is_due
from ..scheduler.monitor_poll_writeback import (
    resolve_monitor_todo_item,
    write_monitor_poll_todo_state,
)
from ..scheduler.monitor_target import build_quota_monitor_target
from ..todos.contract import normalize_todo_claimed_by, normalize_todo_id
from ..work_items.delivery_outcome import DeliveryOutcome


QUOTA_MONITOR_POLL_CLASSIFICATION = "quota_monitor_poll"


def _now_local() -> str:
    return now_local_iso()


def build_quota_monitor_poll_event(
    before: dict[str, Any],
    *,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    generated_at: str | None = None,
    reason_summary: str | None = None,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
    authorized_due_monitor_poll: bool | None = None,
    turn_instance_id: str | None = None,
) -> dict[str, Any]:
    normalized_turn_instance_id = normalize_turn_instance_id(turn_instance_id)
    safe_source = str(source or DEFAULT_SLOT_SPEND_SOURCE).strip()
    if safe_source not in VALID_SLOT_SPEND_SOURCES:
        raise ValueError(f"quota monitor-poll source must be one of: {', '.join(sorted(VALID_SLOT_SPEND_SOURCES))}")
    external_monitor_poll = allows_no_spend_external_monitor_poll(before)
    blocked_successor_wait_poll = allows_no_spend_blocked_successor_wait_poll(before)
    due_monitor_poll = (
        allows_due_monitor_poll(
            before,
            todo_id=todo_id,
            target_key=target_key,
        )
        if authorized_due_monitor_poll is None
        else authorized_due_monitor_poll
    )
    if (
        before.get("effective_action") != "monitor_quiet_skip"
        and not external_monitor_poll
        and not due_monitor_poll
        and not blocked_successor_wait_poll
    ):
        raise ValueError(
            "quota monitor-poll requires a monitor_quiet_skip, due monitor todo, "
            "external monitor observation, or exact blocked successor wait decision"
        )
    recommendation = (
        before.get("heartbeat_recommendation")
        if isinstance(before.get("heartbeat_recommendation"), dict)
        else {}
    )
    if (
        recommendation.get("recommended_mode") != "monitor_quiet_until_material_transition"
        and not external_monitor_poll
        and not due_monitor_poll
        and not blocked_successor_wait_poll
    ):
        raise ValueError(
            "quota monitor-poll requires monitor_quiet_until_material_transition "
            "or exact blocked successor wait mode"
        )
    if blocked_successor_wait_poll:
        monitor_kind = "blocked successor wait"
        monitor_mode_prefix = "blocked_successor_wait"
    elif external_monitor_poll:
        monitor_kind = "external monitor"
        monitor_mode_prefix = "external_monitor"
    elif due_monitor_poll:
        monitor_kind = "due monitor"
        monitor_mode_prefix = "due_monitor"
    else:
        monitor_kind = "monitor"
        monitor_mode_prefix = "monitor"
    if material_change:
        monitor_mode = f"{monitor_mode_prefix}_material_transition"
        default_reason_summary = f"{monitor_kind} observation produced a material transition"
        health_check = (
            f"{monitor_kind} material transition observed; follow-up state updated; "
            "no quota spend by monitor-poll"
        )
    elif blocked_successor_wait_poll:
        monitor_mode = "blocked_successor_wait_without_material_transition"
        default_reason_summary = (
            recommendation.get("reason")
            or before.get("reason")
            or "exact blocked successor wait produced no material transition"
        )
        health_check = (
            "exact blocked successor wait unchanged; no quota spend; "
            "bounded replan after two identical frontier observations"
        )
    elif external_monitor_poll:
        monitor_mode = "external_monitor_observed_without_material_transition"
        default_reason_summary = "external monitor observation produced no material transition"
        health_check = "external monitor observation unchanged; no quota spend; no material transition"
    elif due_monitor_poll:
        monitor_mode = "due_monitor_observed_without_material_transition"
        default_reason_summary = (
            recommendation.get("reason")
            or before.get("reason")
            or "due monitor poll had no material transition"
        )
        health_check = "due monitor observation unchanged; no quota spend; next due updated"
    else:
        monitor_mode = "monitor_quiet_until_material_transition"
        default_reason_summary = (
            recommendation.get("reason")
            or before.get("reason")
            or "monitor-only poll had no material transition"
        )
        health_check = "monitor-only poll unchanged; no quota spend; no material transition"
    monitor_target = build_quota_monitor_target(before, monitor_mode=monitor_mode)
    safe_reason_summary = str(reason_summary or "").strip() or default_reason_summary
    safe_agent_id = quota_decision_agent_id(before)

    record = {
        "generated_at": generated_at or _now_local(),
        "goal_id": before.get("goal_id"),
        "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
        "recommended_action": before.get("recommended_action") or recommendation.get("reason") or before.get("reason"),
        "health_check": health_check,
        "delivery_outcome": (
            DeliveryOutcome.OUTCOME_PROGRESS.value
            if material_change
            else DeliveryOutcome.SURFACE_ONLY.value
        ),
        "monitor_target": monitor_target,
        "monitor_event": {
            "event_type": QUOTA_MONITOR_POLL_CLASSIFICATION,
            "source": safe_source,
            "monitor_mode": monitor_mode,
            "monitor_target": monitor_target,
            "reason_summary": safe_reason_summary,
            "material_change": material_change,
            "todo_id": normalize_todo_id(todo_id) if todo_id else None,
            "target_key": str(target_key or "").strip() or None,
            "result_hash": str(result_hash or "").strip() or None,
            "before": compact_quota_decision(before),
        },
    }
    if safe_agent_id:
        record["agent_id"] = safe_agent_id
        record["monitor_event"]["agent_id"] = safe_agent_id
    if normalized_turn_instance_id:
        record["turn_instance_id"] = normalized_turn_instance_id
        record["monitor_event"]["turn_instance_id"] = normalized_turn_instance_id
    return record


def _find_monitor_poll_turn(
    index_path: Path,
    *,
    goal_id: str,
    agent_id: str,
    turn_instance_id: str,
) -> dict[str, Any] | None:
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if (
            row.get("classification") == QUOTA_MONITOR_POLL_CLASSIFICATION
            and str(row.get("goal_id") or "") == goal_id
            and str(row.get("agent_id") or "") == agent_id
            and str(row.get("turn_instance_id") or "") == turn_instance_id
        ):
            return row
    return None


def find_quota_monitor_poll_turn(
    runtime_root: Path,
    *,
    goal_id: str,
    agent_id: str,
    turn_instance_id: str,
) -> dict[str, Any] | None:
    """Return the persisted stall observation for one heartbeat turn, if any."""

    normalized_turn_instance_id = normalize_turn_instance_id(turn_instance_id)
    if not normalized_turn_instance_id:
        return None
    return _find_monitor_poll_turn(
        runtime_root / "goals" / goal_id / "runs" / "index.jsonl",
        goal_id=goal_id,
        agent_id=agent_id,
        turn_instance_id=normalized_turn_instance_id,
    )


def _status_with_monitor_poll(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    index_record: dict[str, Any],
) -> dict[str, Any]:
    after_status = deepcopy(status_payload)
    run_history = (
        after_status.get("run_history")
        if isinstance(after_status.get("run_history"), dict)
        else {}
    )
    for goal in run_history.get("goals") if isinstance(run_history.get("goals"), list) else []:
        if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
            latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
            if index_record not in latest_runs:
                goal["latest_runs"] = [index_record, *latest_runs]
            runs = goal.get("runs") if isinstance(goal.get("runs"), list) else []
            if index_record not in runs:
                goal["runs"] = [index_record, *runs]
    recent_runs = run_history.get("recent_runs") if isinstance(run_history.get("recent_runs"), list) else []
    if index_record not in recent_runs:
        run_history["recent_runs"] = [index_record, *recent_runs]
    after_status["run_history"] = run_history
    return after_status


def _load_monitor_poll_artifact(index_record: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(index_record.get("json_path") or "").strip()
    if not raw_path:
        return {}
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _allows_registry_due_monitor_poll(
    before: dict[str, Any],
    *,
    registry_path: Path | None,
    goal_id: str,
    todo_id: str | None,
    target_key: str | None,
) -> bool:
    """Authorize an auxiliary due monitor omitted from the compact quota packet."""

    if registry_path is None or not (todo_id or target_key):
        return False
    contract = (
        before.get("work_lane_contract")
        if isinstance(before.get("work_lane_contract"), dict)
        else {}
    )
    if contract.get("must_attempt_work") is not True:
        return False
    if contract.get("obligation") == "attempt_due_monitor":
        return False
    if "due_monitor_context" not in work_lane_reason_codes(contract):
        return False
    try:
        item = resolve_monitor_todo_item(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            target_key=target_key,
        )
    except ValueError:
        return False
    if not monitor_todo_is_due(item):
        return False
    decision_agent_id = quota_decision_agent_id(before)
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    return bool(decision_agent_id and claimed_by == decision_agent_id)


def _monitor_poll_failure(
    *,
    goal_id: str,
    execute: bool,
    source: str,
    agent_id: str | None,
    todo_id: str | None,
    target_key: str | None,
    result_hash: str | None,
    material_change: bool,
    reason: str,
    before: dict[str, Any],
    turn_instance_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "mode": "monitor-poll",
        "dry_run": not execute,
        "goal_id": goal_id,
        "appended": False,
        "registry_mutated": False,
        "source": str(source or DEFAULT_SLOT_SPEND_SOURCE).strip() or DEFAULT_SLOT_SPEND_SOURCE,
        "agent_id": normalize_todo_claimed_by(agent_id),
        "todo_id": todo_id,
        "target_key": target_key,
        "result_hash": result_hash,
        "material_change": material_change,
        "reason": reason,
        "decision_summary": {
            "before": compact_quota_decision(before),
            "after": None,
        },
        "before": before,
        "after": None,
    }
    if turn_instance_id:
        payload["turn_instance_id"] = turn_instance_id
        payload["replayed"] = False
    return payload


def _capability_declaration_retry(before: dict[str, Any]) -> dict[str, Any] | None:
    gate = (
        before.get("capability_gate")
        if isinstance(before.get("capability_gate"), dict)
        else {}
    )
    raw_missing = gate.get("missing") if isinstance(gate.get("missing"), list) else []
    missing = [str(item).strip() for item in raw_missing if str(item).strip()]
    if not missing:
        return None
    cli_args = [arg for capability in missing for arg in ("--available-capability", capability)]
    return {
        "schema_version": "monitor_poll_capability_retry_v0",
        "command": "quota monitor-poll",
        "missing": missing,
        "cli_args": cli_args,
        "reason": (
            "monitor-poll recomputes should-run; if these capabilities are present "
            "in the current agent environment, repeat the runtime capability declarations"
        ),
    }


def record_quota_monitor_poll_for_decision(
    before: dict[str, Any],
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    after_decision: Callable[[dict[str, Any]], dict[str, Any]],
    render_markdown: Callable[[dict[str, Any]], str],
    registry_path: Path | None = None,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    agent_id: str | None = None,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
    cadence: str | None = None,
    next_due_at: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
    turn_instance_id: str | None = None,
    _index_lock_held: bool = False,
) -> dict[str, Any]:
    normalized_turn_instance_id = normalize_turn_instance_id(turn_instance_id)
    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    safe_target_key = str(target_key or "").strip() or None
    safe_result_hash = str(result_hash or "").strip() or None

    def failure(reason: str, *, include_capability_retry: bool = False) -> dict[str, Any]:
        payload = _monitor_poll_failure(
            goal_id=goal_id,
            execute=execute,
            source=source,
            agent_id=agent_id,
            todo_id=normalized_todo_id,
            target_key=safe_target_key,
            result_hash=safe_result_hash,
            material_change=material_change,
            reason=reason,
            before=before,
            turn_instance_id=normalized_turn_instance_id,
        )
        retry = _capability_declaration_retry(before) if include_capability_retry else None
        if retry:
            payload["capability_retry"] = retry
            payload["reason"] = (
                f"{reason}; {retry['reason']}: {', '.join(retry['missing'])}"
            )
        return payload

    if material_change and not (normalized_todo_id or safe_target_key):
        return failure("`quota monitor-poll --material-change` requires --todo-id or --target-key")
    if (next_agent_todo or next_user_todo) and not material_change:
        return failure("`--next-agent-todo` and `--next-user-todo` require --material-change")
    decision_agent_id = quota_decision_agent_id(before)
    if normalized_turn_instance_id and not decision_agent_id:
        return failure("turn-scoped monitor-poll requires a registered --agent-id")

    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    runs_dir = runtime_root / "goals" / goal_id / "runs"
    index_path = runs_dir / "index.jsonl"

    if execute and normalized_turn_instance_id and not _index_lock_held:
        with exclusive_file_lock(index_path):
            existing = _find_monitor_poll_turn(
                index_path,
                goal_id=goal_id,
                agent_id=str(decision_agent_id),
                turn_instance_id=normalized_turn_instance_id,
            )
            if existing:
                artifact = _load_monitor_poll_artifact(existing)
                after = after_decision(
                    _status_with_monitor_poll(
                        status_payload,
                        goal_id=goal_id,
                        index_record=existing,
                    )
                )
                monitor_event = (
                    artifact.get("monitor_event")
                    if isinstance(artifact.get("monitor_event"), dict)
                    else {}
                )
                return {
                    "ok": True,
                    "mode": "monitor-poll",
                    "dry_run": False,
                    "goal_id": goal_id,
                    "appended": False,
                    "replayed": True,
                    "registry_mutated": False,
                    "source": monitor_event.get("source") or source,
                    "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
                    "generated_at": existing.get("generated_at"),
                    "agent_id": existing.get("agent_id"),
                    "todo_id": existing.get("todo_id"),
                    "target_key": existing.get("target_key"),
                    "material_change": bool(existing.get("material_change")),
                    "turn_instance_id": normalized_turn_instance_id,
                    "monitor_event": monitor_event,
                    "todo_writeback": None,
                    "health_check": existing.get("health_check"),
                    "delivery_outcome": existing.get("delivery_outcome"),
                    "json_path": existing.get("json_path"),
                    "markdown_path": existing.get("markdown_path"),
                    "index_path": str(index_path),
                    "decision_summary": {
                        "before": compact_quota_decision(before),
                        "after": compact_quota_decision(after),
                    },
                    "before": before,
                    "after": after,
                    "reason": (
                        "replayed existing monitor poll event for heartbeat turn "
                        f"{normalized_turn_instance_id}"
                    ),
                }
            return record_quota_monitor_poll_for_decision(
                before,
                status_payload,
                goal_id=goal_id,
                after_decision=after_decision,
                render_markdown=render_markdown,
                registry_path=registry_path,
                execute=execute,
                source=source,
                reason_summary=reason_summary,
                agent_id=agent_id,
                todo_id=todo_id,
                target_key=target_key,
                result_hash=result_hash,
                material_change=material_change,
                cadence=cadence,
                next_due_at=next_due_at,
                next_agent_todo=next_agent_todo,
                next_user_todo=next_user_todo,
                next_claimed_by=next_claimed_by,
                turn_instance_id=normalized_turn_instance_id,
                _index_lock_held=True,
            )
    due_monitor_poll = allows_due_monitor_poll(
        before,
        todo_id=normalized_todo_id,
        target_key=safe_target_key,
    ) or _allows_registry_due_monitor_poll(
        before,
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=normalized_todo_id,
        target_key=safe_target_key,
    )
    if (
        before.get("effective_action") != "monitor_quiet_skip"
        and not allows_no_spend_external_monitor_poll(before)
        and not due_monitor_poll
        and not allows_no_spend_blocked_successor_wait_poll(before)
    ):
        return failure(
            "monitor-poll requires monitor_quiet_skip, due monitor todo, "
            "external monitor observation, or exact blocked successor wait",
            include_capability_retry=True,
        )

    generated_at = _now_local()
    todo_writeback = None
    if normalized_todo_id or safe_target_key:
        if registry_path is None:
            raise ValueError("monitor todo writeback requires registry_path")
        todo_writeback = write_monitor_poll_todo_state(
            registry_path=registry_path,
            goal_id=goal_id,
            generated_at=generated_at,
            execute=execute,
            todo_id=normalized_todo_id,
            target_key=safe_target_key,
            result_hash=result_hash,
            material_change=material_change,
            cadence=cadence,
            next_due_at=next_due_at,
            reason_summary=reason_summary,
            next_agent_todo=next_agent_todo,
            next_user_todo=next_user_todo,
            next_claimed_by=next_claimed_by,
            agent_id=agent_id,
        )
    record = build_quota_monitor_poll_event(
        before,
        source=source,
        generated_at=generated_at,
        reason_summary=reason_summary,
        todo_id=(todo_writeback or {}).get("todo_id") or normalized_todo_id,
        target_key=(todo_writeback or {}).get("target_key") or safe_target_key,
        result_hash=(todo_writeback or {}).get("result_hash") or result_hash,
        material_change=material_change,
        authorized_due_monitor_poll=due_monitor_poll,
        turn_instance_id=normalized_turn_instance_id,
    )
    if todo_writeback:
        record["monitor_event"]["todo_writeback"] = {
            key: value
            for key, value in todo_writeback.items()
            if key
            in {
                "schema_version",
                "dry_run",
                "goal_id",
                "todo_id",
                "target_key",
                "result_hash",
                "material_change",
                "consecutive_no_change",
                "last_checked_at",
                "next_due_at",
                "cadence",
            }
        }
    stem = run_file_stem(generated_at)
    path_allocator = reserve_run_artifact_paths if execute else next_run_artifact_paths
    json_path, markdown_path = path_allocator(runs_dir, stem, "quota-monitor-poll")
    index_record = {
        "generated_at": generated_at,
        "goal_id": goal_id,
        "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
        "recommended_action": record["recommended_action"],
        "health_check": record["health_check"],
        "delivery_outcome": record["delivery_outcome"],
        "monitor_target": record["monitor_target"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if record.get("agent_id"):
        index_record["agent_id"] = record["agent_id"]
    if normalized_turn_instance_id:
        index_record["turn_instance_id"] = normalized_turn_instance_id
    if record["monitor_event"].get("todo_id"):
        index_record["todo_id"] = record["monitor_event"]["todo_id"]
    if record["monitor_event"].get("target_key"):
        index_record["target_key"] = record["monitor_event"]["target_key"]
    if record["monitor_event"].get("material_change"):
        index_record["material_change"] = record["monitor_event"]["material_change"]

    after_status = deepcopy(status_payload)
    if execute:
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(record) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
        after_status = _status_with_monitor_poll(
            status_payload,
            goal_id=goal_id,
            index_record=index_record,
        )

    after = after_decision(after_status)
    decision_summary = {
        "before": record["monitor_event"]["before"],
        "after": compact_quota_decision(after),
    }
    result = {
        "ok": True,
        "mode": "monitor-poll",
        "dry_run": not execute,
        "goal_id": goal_id,
        "appended": execute,
        "registry_mutated": False,
        "source": record["monitor_event"]["source"],
        "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
        "generated_at": generated_at,
        "agent_id": record.get("agent_id"),
        "todo_id": record["monitor_event"].get("todo_id"),
        "target_key": record["monitor_event"].get("target_key"),
        "material_change": record["monitor_event"].get("material_change"),
        "monitor_event": record["monitor_event"],
        "todo_writeback": todo_writeback,
        "health_check": record["health_check"],
        "delivery_outcome": record["delivery_outcome"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "decision_summary": decision_summary,
        # Monitor-poll callers may need the full follow-up guard to decide whether
        # to stay quiet, replan, or continue work after recording the observation.
        "before": before,
        "after": after,
        "reason": (
            f"{'appended' if execute else 'dry-run preview'} monitor poll event: "
            f"{goal_id} effective_action={before.get('effective_action')}"
        ),
    }
    if normalized_turn_instance_id:
        result["turn_instance_id"] = normalized_turn_instance_id
        result["replayed"] = False
    return result
