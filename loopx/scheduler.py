from __future__ import annotations

import hashlib
import shlex
from typing import Any

from .notification_projection import compact_markdown
from .scheduler_handoffs import (
    build_scheduler_handoffs_payload,
    build_worker_handoffs,
    render_scheduler_handoffs_markdown,
)
from .todo_contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_STATUS_OPEN,
    normalize_decision_scope,
    normalize_required_decision_scopes,
    normalize_required_write_scopes,
    normalize_safety_class,
    normalize_todo_claimed_by,
    normalize_todo_id,
)


SCHEDULER_PLAN_SCHEMA_VERSION = "scheduler_plan_v0"
SCHEDULER_CANDIDATE_SCHEMA_VERSION = "scheduler_candidate_v0"
MAX_CANDIDATE_TEXT_CHARS = 240
DEFAULT_MAX_PARALLEL = 4

TODO_CANDIDATE_KEYS = (
    "active_next_action_executable_items",
    "first_executable_items",
    "executable_backlog_items",
    "unclaimed_priority_open_items",
    "claimed_advancement_open_items",
    "first_open_items",
    "items",
)

GRANULARITY_RANK = {
    "action": 0,
    "lane": 1,
    "goal": 2,
    "project": 3,
    "global": 4,
}


def build_scheduler_plan(
    status_payload: dict[str, Any],
    *,
    goal_id: str | None = None,
    agent_id: str | None = None,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    safe_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
    limit = max(1, int(max_parallel or DEFAULT_MAX_PARALLEL))
    queue_items = _attention_items(status_payload)
    if safe_goal_id:
        queue_items = [item for item in queue_items if str(item.get("goal_id") or "") == safe_goal_id]

    runnable_batch: list[dict[str, Any]] = []
    waiting_candidates: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []

    for queue_index, item in enumerate(queue_items):
        open_user_gates = _open_user_gates(item)
        for todo_index, candidate in enumerate(_agent_candidates(item, agent_id=safe_agent_id)):
            candidate["queue_index"] = queue_index
            candidate["candidate_index"] = todo_index
            all_candidates.append(candidate)
            block = _standalone_block(candidate, open_user_gates=open_user_gates, agent_id=safe_agent_id)
            if block:
                blocked_candidates.append({**candidate, **block})
                continue
            lane_conflicts = [
                selected
                for selected in runnable_batch
                if _agent_lane_conflict(candidate, selected)
            ]
            if lane_conflicts:
                waiting_candidates.append(
                    {
                        **candidate,
                        "runnable": False,
                        "reason_codes": ["agent_lane_capacity"],
                        "conflicts_with": _candidate_refs(lane_conflicts),
                    }
                )
                continue
            if len(runnable_batch) >= limit:
                waiting_candidates.append(
                    {
                        **candidate,
                        "runnable": False,
                        "reason_codes": ["parallel_limit_reached"],
                        "parallel_limit": limit,
                    }
                )
                continue
            conflicts = [
                selected
                for selected in runnable_batch
                if _write_scopes_conflict(
                    candidate.get("required_write_scopes"),
                    selected.get("required_write_scopes"),
                )
            ]
            if conflicts:
                waiting_candidates.append(
                    {
                        **candidate,
                        "runnable": False,
                        "reason_codes": ["write_scope_conflict"],
                        "conflicts_with": _candidate_refs(conflicts),
                    }
                )
                continue
            runnable_batch.append({**candidate, "runnable": True})

    public_runnable_batch = [_public_candidate(item) for item in runnable_batch]
    public_waiting_candidates = [_public_candidate(item) for item in waiting_candidates]
    public_blocked_candidates = [_public_candidate(item) for item in blocked_candidates]
    developer_commands = _developer_commands(
        goal_id=safe_goal_id,
        agent_id=safe_agent_id,
        max_parallel=limit,
        runnable_batch=public_runnable_batch,
    )
    return {
        "ok": True,
        "status_health_ok": bool(status_payload.get("ok", True)),
        "schema_version": SCHEDULER_PLAN_SCHEMA_VERSION,
        "mode": "plan",
        "goal_id": safe_goal_id or None,
        "agent_id": safe_agent_id,
        "max_parallel": limit,
        "candidate_count": len(all_candidates),
        "runnable_batch_count": len(runnable_batch),
        "waiting_count": len(waiting_candidates),
        "blocked_count": len(blocked_candidates),
        "runnable_batch": public_runnable_batch,
        "waiting_candidates": public_waiting_candidates,
        "blocked_candidates": public_blocked_candidates,
        "developer_commands": developer_commands,
        "dispatch_plan": _dispatch_plan(
            goal_id=safe_goal_id,
            agent_id=safe_agent_id,
            runnable_batch=public_runnable_batch,
            waiting_candidates=public_waiting_candidates,
            blocked_candidates=public_blocked_candidates,
            developer_commands=developer_commands,
        ),
        "policy": {
            "schema_version": "scheduler_parallel_policy_v0",
            "state_writes": "serialized_by_active_state_file_lock",
            "read_only": "parallelizable",
            "local_write": "parallelizable_only_with_disjoint_required_write_scopes",
            "agent_lane_capacity": "one_runnable_candidate_per_claimed_or_target_agent_lane",
            "external_run": "blocked_without_explicit_lane",
            "protected_write": "blocked_without_user_or_controller_gate",
            "claim_policy": (
                "current_agent_or_unclaimed_only"
                if safe_agent_id
                else "all_claims_visible_without_assignment"
            ),
        },
    }


def build_scheduler_handoffs(
    status_payload: dict[str, Any],
    *,
    goal_id: str | None = None,
    agent_id: str | None = None,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    todo_id: str | None = None,
) -> dict[str, Any]:
    plan = build_scheduler_plan(
        status_payload,
        goal_id=goal_id,
        agent_id=agent_id,
        max_parallel=max_parallel,
    )
    return build_scheduler_handoffs_payload(plan, todo_id=todo_id)


def render_scheduler_plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Scheduler Plan",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- status_health_ok: `{payload.get('status_health_ok')}`",
        f"- goal_id: `{payload.get('goal_id') or ''}`",
        f"- agent_id: `{payload.get('agent_id') or ''}`",
        f"- max_parallel: `{payload.get('max_parallel')}`",
        f"- runnable_batch_count: `{payload.get('runnable_batch_count')}`",
        f"- waiting_count: `{payload.get('waiting_count')}`",
        f"- blocked_count: `{payload.get('blocked_count')}`",
    ]
    _append_dispatch_plan_lines(lines, payload.get("dispatch_plan"))
    _append_candidate_lines(lines, "Runnable batch", payload.get("runnable_batch"))
    _append_candidate_lines(lines, "Waiting candidates", payload.get("waiting_candidates"))
    _append_candidate_lines(lines, "Blocked candidates", payload.get("blocked_candidates"))
    return "\n".join(lines).rstrip() + "\n"


def _append_dispatch_plan_lines(lines: list[str], dispatch_plan: Any) -> None:
    if not isinstance(dispatch_plan, dict):
        return
    lines.extend(
        [
            "",
            "## Dispatch plan",
            f"- action: `{dispatch_plan.get('action') or ''}`",
            f"- parallelizable: `{dispatch_plan.get('parallelizable')}`",
            "- runnable_todo_ids: `"
            + ",".join(str(item) for item in dispatch_plan.get("runnable_todo_ids") or [])
            + "`",
        ]
    )
    waiting_counts = dispatch_plan.get("waiting_reason_counts")
    if isinstance(waiting_counts, dict) and waiting_counts:
        lines.append(
            "- waiting_reason_counts: `"
            + ",".join(f"{key}={value}" for key, value in sorted(waiting_counts.items()))
            + "`"
        )
    steps = dispatch_plan.get("developer_steps")
    if isinstance(steps, list) and steps:
        lines.append("- developer_steps:")
        for step in steps[:8]:
            if not isinstance(step, dict):
                continue
            label = str(step.get("kind") or "").strip()
            todo_id = str(step.get("todo_id") or "").strip()
            command = str(step.get("command") or "").strip()
            suffix = f" todo_id={todo_id}" if todo_id else ""
            lines.append(f"  - {label}{suffix}: `{command}`")
    handoffs = dispatch_plan.get("worker_handoffs")
    if isinstance(handoffs, list) and handoffs:
        lines.append("- worker_handoffs:")
        for handoff in handoffs[:8]:
            if not isinstance(handoff, dict):
                continue
            todo_id = str(handoff.get("todo_id") or handoff.get("candidate_key") or "").strip()
            lane = str(handoff.get("agent_lane") or "").strip()
            suffix = f" lane={lane}" if lane else ""
            lines.append(f"  - {todo_id}{suffix}")


def _append_candidate_lines(lines: list[str], heading: str, items: Any) -> None:
    if not isinstance(items, list) or not items:
        return
    lines.extend(["", f"## {heading}"])
    for item in items[:10]:
        if not isinstance(item, dict):
            continue
        parts = [
            str(item.get("todo_id") or item.get("candidate_key") or ""),
            f"safety={item.get('safety_class') or 'missing'}",
        ]
        if item.get("claimed_by"):
            parts.append(f"claimed_by={item.get('claimed_by')}")
        if item.get("agent_lane"):
            parts.append(f"lane={item.get('agent_lane')}")
        if item.get("required_write_scopes"):
            parts.append(f"write={','.join(item.get('required_write_scopes') or [])}")
        if item.get("reason_codes"):
            parts.append(f"reason={','.join(item.get('reason_codes') or [])}")
        lines.append(f"- {' '.join(part for part in parts if part)}")
        text = str(item.get("text") or "").strip()
        if text:
            lines.append(f"  - {text}")
        claim_command = str(item.get("claim_command") or "").strip()
        if claim_command:
            lines.append(f"  - claim: `{claim_command}`")


def _attention_items(status_payload: dict[str, Any]) -> list[dict[str, Any]]:
    queue = status_payload.get("attention_queue") if isinstance(status_payload, dict) else None
    if not isinstance(queue, dict):
        return []
    return [item for item in queue.get("items") or [] if isinstance(item, dict)]


def _summary_from_item(item: dict[str, Any], key: str) -> dict[str, Any] | None:
    direct = item.get(key)
    if isinstance(direct, dict):
        return direct
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict) and isinstance(project_asset.get(key), dict):
        return project_asset.get(key)
    return None


def _summary_items(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for key in TODO_CANDIDATE_KEYS:
        raw_items = summary.get(key)
        if not isinstance(raw_items, list):
            continue
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            identity = (
                str(raw.get("todo_id") or raw.get("id") or "").strip(),
                str(raw.get("text") or "").strip(),
            )
            if not identity[0] and not identity[1]:
                continue
            if identity in seen:
                continue
            seen.add(identity)
            items.append(raw)
    return items


def _agent_candidates(item: dict[str, Any], *, agent_id: str | None) -> list[dict[str, Any]]:
    goal_id = str(item.get("goal_id") or "").strip()
    summary = _summary_from_item(item, "agent_todos")
    candidates: list[dict[str, Any]] = []
    for raw in _summary_items(summary):
        status = str(raw.get("status") or "").strip().lower() or TODO_STATUS_OPEN
        if status != TODO_STATUS_OPEN or raw.get("done") is True:
            continue
        if str(raw.get("task_class") or TODO_TASK_CLASS_ADVANCEMENT) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        candidate = _candidate_from_todo(goal_id, raw)
        if agent_id and candidate.get("claimed_by") and candidate.get("claimed_by") != agent_id:
            candidate["other_agent_claimed"] = True
        if agent_id and not candidate.get("claimed_by"):
            candidate["claim_required_before_work"] = True
            if candidate.get("todo_id"):
                candidate["claim_command"] = _claim_command(
                    goal_id=goal_id,
                    todo_id=str(candidate.get("todo_id") or ""),
                    agent_id=agent_id,
                )
        agent_lane = _agent_lane(candidate, agent_id=agent_id)
        if agent_lane:
            candidate["agent_lane"] = agent_lane
        candidates.append(candidate)
    return candidates


def _candidate_from_todo(goal_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    todo_id = normalize_todo_id(raw.get("todo_id") or raw.get("id"))
    text = compact_markdown(raw.get("text") or "", max_chars=MAX_CANDIDATE_TEXT_CHARS, suffix="...")
    safety_class = normalize_safety_class(raw.get("safety_class"))
    write_scopes = normalize_required_write_scopes(raw.get("required_write_scopes"))
    decision_scopes = normalize_required_decision_scopes(raw.get("required_decision_scopes"))
    claimed_by = normalize_todo_claimed_by(raw.get("claimed_by"))
    key_source = f"{goal_id}\n{text}"
    candidate_key = todo_id or f"{goal_id}:{hashlib.sha256(key_source.encode('utf-8')).hexdigest()[:12]}"
    payload: dict[str, Any] = {
        "schema_version": SCHEDULER_CANDIDATE_SCHEMA_VERSION,
        "candidate_key": candidate_key,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "text": text,
        "task_class": TODO_TASK_CLASS_ADVANCEMENT,
        "safety_class": safety_class,
        "required_write_scopes": write_scopes,
        "required_decision_scopes": decision_scopes,
        "parallel_group_key": _parallel_group_key(
            safety_class=safety_class,
            required_write_scopes=write_scopes,
        ),
    }
    if claimed_by:
        payload["claimed_by"] = claimed_by
    for key in ("action_kind", "priority", "title", "blocks_agent", "unblocks_todo_id", "resume_when"):
        if raw.get(key):
            payload[key] = raw.get(key)
    if isinstance(raw.get("resume_condition"), dict):
        payload["resume_condition"] = raw.get("resume_condition")
    return payload


def _public_candidate(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "candidate_key",
        "goal_id",
        "todo_id",
        "text",
        "task_class",
        "safety_class",
        "required_write_scopes",
        "required_decision_scopes",
        "parallel_group_key",
        "agent_lane",
        "claimed_by",
        "claim_required_before_work",
        "claim_command",
        "runnable",
        "reason_codes",
        "conflicts_with",
        "blocked_by_user_todos",
        "parallel_limit",
        "action_kind",
        "priority",
        "blocks_agent",
        "unblocks_todo_id",
        "resume_when",
    )
    return {key: item.get(key) for key in keys if item.get(key) is not None}


def _agent_lane(candidate: dict[str, Any], *, agent_id: str | None) -> str:
    claimed_by = normalize_todo_claimed_by(candidate.get("claimed_by"))
    if claimed_by:
        return claimed_by
    if agent_id and candidate.get("claim_required_before_work"):
        return agent_id
    return ""


def _agent_lane_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_lane = str(left.get("agent_lane") or "").strip()
    if not left_lane:
        return False
    return left_lane == str(right.get("agent_lane") or "").strip()


def _candidate_refs(items: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("todo_id") or item.get("candidate_key") or "")
        for item in items
        if item.get("todo_id") or item.get("candidate_key")
    ]


def _developer_commands(
    *,
    goal_id: str,
    agent_id: str | None,
    max_parallel: int,
    runnable_batch: list[dict[str, Any]],
) -> dict[str, Any]:
    scheduler_plan = ["loopx", "--format", "json", "scheduler", "plan"]
    if goal_id:
        scheduler_plan.extend(["--goal-id", goal_id])
    if agent_id:
        scheduler_plan.extend(["--agent-id", agent_id])
    scheduler_plan.extend(["--max-parallel", str(max_parallel)])

    status = ["loopx", "--format", "json", "status"]
    if agent_id:
        status.extend(["--agent-id", agent_id])

    commands: dict[str, Any] = {
        "scheduler_plan": _shell_join(scheduler_plan),
        "status": _shell_join(status),
    }
    if goal_id:
        quota_guard = ["loopx", "--format", "json", "quota", "should-run", "--goal-id", goal_id]
        if agent_id:
            quota_guard.extend(["--agent-id", agent_id])
        commands["quota_guard"] = _shell_join(quota_guard)
    claim_commands = [
        str(item.get("claim_command") or "").strip()
        for item in runnable_batch
        if str(item.get("claim_command") or "").strip()
    ]
    if claim_commands:
        commands["claim_runnable"] = claim_commands
    return commands


def _dispatch_plan(
    *,
    goal_id: str,
    agent_id: str | None,
    runnable_batch: list[dict[str, Any]],
    waiting_candidates: list[dict[str, Any]],
    blocked_candidates: list[dict[str, Any]],
    developer_commands: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "scheduler_dispatch_plan_v0",
        "mode": "manual_safe_parallel_plan",
        "goal_id": goal_id or None,
        "agent_id": agent_id,
        "action": _dispatch_action(
            runnable_batch=runnable_batch,
            waiting_candidates=waiting_candidates,
            blocked_candidates=blocked_candidates,
        ),
        "parallelizable": len(runnable_batch) > 1,
        "runnable_todo_ids": _candidate_refs(runnable_batch),
        "waiting_todo_ids": _candidate_refs(waiting_candidates),
        "blocked_todo_ids": _candidate_refs(blocked_candidates),
        "waiting_reason_counts": _reason_counts(waiting_candidates),
        "blocked_reason_counts": _reason_counts(blocked_candidates),
        "agent_lanes": _agent_lane_summaries(
            runnable_batch=runnable_batch,
            waiting_candidates=waiting_candidates,
            blocked_candidates=blocked_candidates,
        ),
        "worker_handoffs": build_worker_handoffs(goal_id=goal_id, runnable_batch=runnable_batch),
        "developer_steps": _developer_steps(
            developer_commands=developer_commands,
            runnable_batch=runnable_batch,
        ),
    }


def _dispatch_action(
    *,
    runnable_batch: list[dict[str, Any]],
    waiting_candidates: list[dict[str, Any]],
    blocked_candidates: list[dict[str, Any]],
) -> str:
    if len(runnable_batch) > 1:
        return "run_parallel_batch"
    if len(runnable_batch) == 1:
        return "run_single_candidate"
    blocked_counts = _reason_counts(blocked_candidates)
    if blocked_counts.get("requires_user_decision") or blocked_counts.get("protected_write_requires_user_gate"):
        return "wait_for_user"
    if waiting_candidates:
        return "wait_for_lane_or_limit"
    if blocked_candidates:
        return "blocked"
    return "idle"


def _reason_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reasons = item.get("reason_codes")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            key = str(reason or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _agent_lane_summaries(
    *,
    runnable_batch: list[dict[str, Any]],
    waiting_candidates: list[dict[str, Any]],
    blocked_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lanes: dict[str, dict[str, Any]] = {}

    def ensure_lane(item: dict[str, Any]) -> dict[str, Any]:
        lane = str(item.get("agent_lane") or "unassigned").strip() or "unassigned"
        return lanes.setdefault(
            lane,
            {
                "agent_lane": lane,
                "runnable_todo_ids": [],
                "waiting_todo_ids": [],
                "blocked_todo_ids": [],
            },
        )

    for item in runnable_batch:
        ensure_lane(item)["runnable_todo_ids"].extend(_candidate_refs([item]))
    for item in waiting_candidates:
        ensure_lane(item)["waiting_todo_ids"].extend(_candidate_refs([item]))
    for item in blocked_candidates:
        ensure_lane(item)["blocked_todo_ids"].extend(_candidate_refs([item]))
    return list(lanes.values())


def _developer_steps(
    *,
    developer_commands: dict[str, Any],
    runnable_batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    quota_guard = str(developer_commands.get("quota_guard") or "").strip()
    if quota_guard:
        steps.append({"kind": "quota_guard", "command": quota_guard, "required": True})
    for item in runnable_batch:
        claim_command = str(item.get("claim_command") or "").strip()
        if not claim_command:
            continue
        step: dict[str, Any] = {
            "kind": "claim_runnable",
            "command": claim_command,
            "required": True,
        }
        todo_id = str(item.get("todo_id") or item.get("candidate_key") or "").strip()
        if todo_id:
            step["todo_id"] = todo_id
        steps.append(step)
    status = str(developer_commands.get("status") or "").strip()
    if status:
        steps.append({"kind": "status", "command": status, "required": False})
    scheduler_plan = str(developer_commands.get("scheduler_plan") or "").strip()
    if scheduler_plan:
        steps.append({"kind": "scheduler_plan", "command": scheduler_plan, "required": False})
    return steps


def _claim_command(*, goal_id: str, todo_id: str, agent_id: str) -> str:
    return _shell_join(
        [
            "loopx",
            "todo",
            "claim",
            "--goal-id",
            goal_id,
            "--todo-id",
            todo_id,
            "--claimed-by",
            agent_id,
        ]
    )


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts if str(part))


def _standalone_block(
    candidate: dict[str, Any],
    *,
    open_user_gates: list[dict[str, Any]],
    agent_id: str | None,
) -> dict[str, Any] | None:
    if agent_id and candidate.get("other_agent_claimed"):
        return {
            "runnable": False,
            "reason_codes": ["claimed_by_other_agent"],
        }
    resume_condition = candidate.get("resume_condition")
    if isinstance(resume_condition, dict) and resume_condition.get("satisfied") is False:
        return {
            "runnable": False,
            "reason_codes": ["resume_condition_not_satisfied"],
        }
    safety_class = candidate.get("safety_class")
    if not safety_class:
        return {
            "runnable": False,
            "reason_codes": ["missing_safety_class"],
        }
    if safety_class == "protected_write":
        return {
            "runnable": False,
            "reason_codes": ["protected_write_requires_user_gate"],
        }
    if safety_class == "external_run":
        return {
            "runnable": False,
            "reason_codes": ["external_run_requires_explicit_lane"],
        }
    if safety_class == "local_write" and not candidate.get("required_write_scopes"):
        return {
            "runnable": False,
            "reason_codes": ["missing_required_write_scope"],
        }
    blocked_by = _blocking_user_todo_ids(candidate, open_user_gates=open_user_gates)
    if blocked_by:
        return {
            "runnable": False,
            "reason_codes": ["requires_user_decision"],
            "blocked_by_user_todos": blocked_by,
        }
    return None


def _open_user_gates(item: dict[str, Any]) -> list[dict[str, Any]]:
    summary = _summary_from_item(item, "user_todos")
    gates: list[dict[str, Any]] = []
    for raw in _summary_items(summary):
        if raw.get("done") is True:
            continue
        status = str(raw.get("status") or "").strip().lower() or TODO_STATUS_OPEN
        if status != TODO_STATUS_OPEN:
            continue
        scope = normalize_decision_scope(raw.get("decision_scope"))
        if not scope:
            continue
        gates.append(
            {
                "todo_id": normalize_todo_id(raw.get("todo_id") or raw.get("id")),
                "decision_scope": scope,
            }
        )
    return gates


def _blocking_user_todo_ids(candidate: dict[str, Any], *, open_user_gates: list[dict[str, Any]]) -> list[str]:
    required_scopes = candidate.get("required_decision_scopes")
    if not isinstance(required_scopes, list) or not required_scopes:
        return []
    blocked: list[str] = []
    for gate in open_user_gates:
        gate_scope = gate.get("decision_scope")
        if not isinstance(gate_scope, dict):
            continue
        for required in required_scopes:
            if _decision_scope_covers(gate_scope, required):
                todo_id = str(gate.get("todo_id") or "").strip()
                if todo_id and todo_id not in blocked:
                    blocked.append(todo_id)
    return blocked


def _decision_scope_covers(gate_scope: dict[str, Any], required_scope: dict[str, Any]) -> bool:
    gate = normalize_decision_scope(gate_scope)
    required = normalize_decision_scope(required_scope)
    if not gate or not required:
        return False
    if gate.get("kind") != required.get("kind"):
        return False
    gate_key = str(gate.get("scope_key") or "")
    required_key = str(required.get("scope_key") or "")
    if gate_key == "*":
        return True
    if gate_key == required_key:
        return _granularity_covers(
            str(gate.get("granularity") or ""),
            str(required.get("granularity") or ""),
        )
    if gate.get("kind") == "write_scope":
        return _single_write_scope_conflict(gate_key, required_key)
    return False


def _granularity_covers(gate_granularity: str, required_granularity: str) -> bool:
    return GRANULARITY_RANK.get(gate_granularity, -1) >= GRANULARITY_RANK.get(required_granularity, 999)


def _parallel_group_key(
    *,
    safety_class: str | None,
    required_write_scopes: list[str],
) -> str:
    if safety_class == "read_only":
        return "read_only"
    if safety_class == "local_write":
        return "write:" + ",".join(required_write_scopes or ["<missing>"])
    return f"safety:{safety_class or 'missing'}"


def _write_scopes_conflict(left: Any, right: Any) -> bool:
    left_scopes = normalize_required_write_scopes(left)
    right_scopes = normalize_required_write_scopes(right)
    if not left_scopes or not right_scopes:
        return False
    return any(_single_write_scope_conflict(left_scope, right_scope) for left_scope in left_scopes for right_scope in right_scopes)


def _single_write_scope_conflict(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == "*" or right == "*":
        return True
    if left == right:
        return True
    left_prefix = _scope_prefix(left)
    right_prefix = _scope_prefix(right)
    if left_prefix and _scope_contains(left_prefix, right):
        return True
    if right_prefix and _scope_contains(right_prefix, left):
        return True
    return False


def _scope_prefix(scope: str) -> str:
    for suffix in ("/**", "/*"):
        if scope.endswith(suffix):
            return scope[: -len(suffix)].rstrip("/")
    return ""


def _scope_contains(prefix: str, scope: str) -> bool:
    if not prefix:
        return False
    clean = scope.rstrip("/")
    return clean == prefix or clean.startswith(prefix.rstrip("/") + "/")
