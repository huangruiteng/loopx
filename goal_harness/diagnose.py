from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .quota import build_quota_should_run
from .status import collect_status


DIAGNOSIS_SCHEMA_VERSION = "goal_harness_agent_diagnosis_packet_v0"
PACKET_KIND = "agent_reasoning_evidence_packet"


USER_DIAGNOSE_PROMPT = (
    "请诊断这个项目的 Goal Harness 运转情况。不要让我手动跑 shell 命令；如果 "
    "`goal-harness` 不在 PATH，请先安装/修复。然后运行 `goal-harness diagnose` "
    "读取诊断证据包，结合项目上下文自己判断：它是否可以自主推进、当前卡在哪、"
    "需要我回答什么、以及你下一步会做什么。"
)


AGENT_REASONING_CHECKLIST = [
    "判断 Goal Harness 本身是否健康：registry/status/quota 是否能读，是否存在 stale projection 或 contract error。",
    "判断当前 goal 是否已连接：若没有 registry goal 或 attention item，先接入而不是猜任务。",
    "判断是否存在 user/controller gate：开放 user todo、operator_question、interaction_contract.user_channel 都要纳入判断。",
    "判断是否可自主推进：只有在用户 gate 不阻塞所选路径、quota 允许、goal_boundary 允许、且有明确 agent todo/recommended_action 时才推进。",
    "判断是否应先自修复：state_projection_gap、boundary_projection_gap、stale action、todo 投影缺口优先于普通 delivery。",
    "向用户汇报时给出自己的结论，不要把 machine_signals 当成最终裁决；引用具体 evidence 字段说明理由。",
]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_text(summary: dict[str, Any]) -> str | None:
    for key in ("first_open_items", "items", "backlog_items"):
        for item in _as_list(summary.get(key)):
            if isinstance(item, dict) and item.get("text"):
                return str(item.get("text"))
    if summary.get("next"):
        return str(summary.get("next"))
    return None


def _open_count(summary: dict[str, Any]) -> int:
    for key in ("open_count", "open"):
        value = summary.get(key)
        if isinstance(value, int):
            return value
    return len(_as_list(summary.get("first_open_items")) or _as_list(summary.get("items")))


def _attention_items(status_payload: dict[str, Any]) -> list[dict[str, Any]]:
    queue = _as_dict(status_payload.get("attention_queue"))
    return [item for item in _as_list(queue.get("items")) if isinstance(item, dict)]


def _select_attention_item(
    status_payload: dict[str, Any],
    *,
    goal_id: str | None,
) -> dict[str, Any] | None:
    items = _attention_items(status_payload)
    if goal_id:
        for item in items:
            if str(item.get("goal_id") or "") == goal_id:
                return item
        return None
    return items[0] if items else None


def _goal_ids_for_packet(status_payload: dict[str, Any], *, goal_id: str | None, limit: int) -> list[str]:
    if goal_id:
        return [goal_id]
    ids: list[str] = []
    for item in _attention_items(status_payload):
        candidate = str(item.get("goal_id") or "").strip()
        if candidate and candidate not in ids:
            ids.append(candidate)
        if len(ids) >= max(1, limit):
            break
    return ids


def _quota_for_goal(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any]:
    try:
        return build_quota_should_run(status_payload, goal_id=goal_id)
    except Exception as exc:  # noqa: BLE001 - diagnosis packets should preserve compact failure context.
        return {
            "ok": False,
            "goal_id": goal_id,
            "error": str(exc),
            "should_run": False,
            "state": "diagnosis_quota_failed",
            "reason": str(exc),
        }


def _todo_summary(quota: dict[str, Any], item: dict[str, Any], *, role: str) -> dict[str, Any]:
    key = f"{role}_todo_summary"
    fallback = f"{role}_todos"
    return _as_dict(quota.get(key)) or _as_dict(item.get(fallback))


def _interaction_user_required(quota: dict[str, Any]) -> bool:
    contract = _as_dict(quota.get("interaction_contract"))
    user_channel = _as_dict(contract.get("user_channel"))
    if user_channel.get("action_required") is not None:
        return bool(user_channel.get("action_required"))
    return bool(quota.get("requires_user_action") or quota.get("notify_user_on_gate"))


def _machine_signal(*, status_payload: dict[str, Any], item: dict[str, Any] | None, quota: dict[str, Any]) -> str:
    if not status_payload.get("ok"):
        return "status_health_attention"
    if item is None:
        return "not_connected_or_not_projected"
    if not quota.get("ok", True):
        return "quota_attention"
    user_summary = _todo_summary(quota, item, role="user")
    if _interaction_user_required(quota) or _open_count(user_summary) > 0:
        return "user_or_controller_attention"
    if quota.get("self_repair_allowed"):
        return "self_repair_attention"
    if quota.get("recovery_delivery_allowed"):
        return "recovery_attention"
    if quota.get("should_run") and quota.get("normal_delivery_allowed", True):
        return "agent_work_attention"
    if quota.get("safe_bypass_allowed"):
        return "safe_bypass_attention"
    if item.get("waiting_on") == "external_evidence":
        return "external_evidence_attention"
    return "no_immediate_agent_delivery_signal"


def _first_user_question(quota: dict[str, Any], item: dict[str, Any]) -> str | None:
    for key in ("operator_question", "gate_prompt"):
        if quota.get(key):
            return str(quota.get(key))
        if item.get(key):
            return str(item.get(key))
    return _first_text(_todo_summary(quota, item, role="user"))


def _agent_commands(*, goal_id: str | None, registry_path: Path, scan_roots: list[Path], limit: int) -> list[str]:
    registry_arg = shlex.quote(str(registry_path))
    scan_args = " ".join(f"--scan-path {shlex.quote(str(path))}" for path in scan_roots)
    diagnose = f"goal-harness --registry {registry_arg} diagnose"
    status = f"goal-harness --registry {registry_arg} status"
    if scan_args:
        diagnose = f"{diagnose} {scan_args}"
        status = f"{status} {scan_args}"
    commands = [
        f"{diagnose} --limit {max(1, limit)}",
        f"{status} --limit {max(1, limit)}",
    ]
    if goal_id:
        quoted_goal = shlex.quote(goal_id)
        commands.append(f"goal-harness --registry {registry_arg} --format json quota should-run --goal-id {quoted_goal}")
        commands.append(f"goal-harness --registry {registry_arg} history --goal-id {quoted_goal} --limit {max(1, limit)}")
    return commands


def _compact_quota_signals(quota: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ok",
        "decision",
        "should_run",
        "state",
        "effective_action",
        "actionable_by_codex",
        "normal_delivery_allowed",
        "recovery_delivery_allowed",
        "self_repair_allowed",
        "safe_bypass_allowed",
        "safe_bypass_kind",
        "requires_user_action",
        "recommended_action",
        "reason",
    )
    return {key: quota.get(key) for key in keys if key in quota}


def _build_goal_packet(
    *,
    status_payload: dict[str, Any],
    item: dict[str, Any] | None,
    quota: dict[str, Any],
    registry_path: Path,
    scan_roots: list[Path],
    limit: int,
) -> dict[str, Any]:
    goal_id = str((item or {}).get("goal_id") or quota.get("goal_id") or "")
    item = item or {}
    user_summary = _todo_summary(quota, item, role="user")
    agent_summary = _todo_summary(quota, item, role="agent")
    machine_signal = _machine_signal(status_payload=status_payload, item=item or None, quota=quota)
    return {
        "goal_id": goal_id or None,
        "packet_role": "evidence_for_agent_reasoning",
        "machine_signal": machine_signal,
        "machine_signals_are_not_final_verdict": True,
        "status": item.get("status"),
        "waiting_on": item.get("waiting_on"),
        "severity": item.get("severity"),
        "recommended_action": quota.get("recommended_action") or item.get("recommended_action"),
        "user_question": _first_user_question(quota, item),
        "todo_evidence": {
            "user_open_count": _open_count(user_summary),
            "agent_open_count": _open_count(agent_summary),
            "first_user_todo": _first_text(user_summary),
            "first_agent_todo": _first_text(agent_summary),
        },
        "quota_signals": _compact_quota_signals(quota),
        "interaction_contract": _as_dict(quota.get("interaction_contract")),
        "work_lane_contract": _as_dict(quota.get("work_lane_contract")),
        "goal_boundary": _as_dict(quota.get("goal_boundary")),
        "projection_warnings": {
            "state_projection_gap": _as_dict(quota.get("state_projection_gap")),
            "state_action_projection_warning": _as_dict(quota.get("state_action_projection_warning")),
            "backlog_hygiene_warning": _as_dict(quota.get("backlog_hygiene_warning")),
            "autonomous_replan_obligation": _as_dict(quota.get("autonomous_replan_obligation")),
        },
        "agent_reasoning_checklist": AGENT_REASONING_CHECKLIST,
        "agent_commands": _agent_commands(
            goal_id=goal_id or None,
            registry_path=registry_path,
            scan_roots=scan_roots,
            limit=limit,
        ),
    }


def collect_diagnosis(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
    goal_id: str | None = None,
) -> dict[str, Any]:
    limit = max(1, limit)
    registry_path = registry_path.expanduser()
    status_payload = collect_status(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        limit=limit,
    )
    goal_ids = _goal_ids_for_packet(status_payload, goal_id=goal_id, limit=limit)
    item_by_goal = {
        str(item.get("goal_id") or ""): item
        for item in _attention_items(status_payload)
        if item.get("goal_id")
    }
    goal_packets = []
    for current_goal_id in goal_ids:
        item = item_by_goal.get(current_goal_id)
        quota = _quota_for_goal(status_payload, current_goal_id)
        goal_packets.append(
            _build_goal_packet(
                status_payload=status_payload,
                item=item,
                quota=quota,
                registry_path=registry_path,
                scan_roots=scan_roots,
                limit=limit,
            )
        )
    selected_item = _select_attention_item(status_payload, goal_id=goal_id)
    selected_goal_id = str((selected_item or {}).get("goal_id") or (goal_ids[0] if goal_ids else ""))
    selected = next((item for item in goal_packets if item.get("goal_id") == selected_goal_id), None)
    if selected is None:
        selected = _build_goal_packet(
            status_payload=status_payload,
            item=selected_item,
            quota={"ok": True, "goal_id": selected_goal_id, "should_run": False},
            registry_path=registry_path,
            scan_roots=scan_roots,
            limit=limit,
        )
    return {
        "ok": bool(status_payload.get("ok")),
        "schema_version": DIAGNOSIS_SCHEMA_VERSION,
        "packet_kind": PACKET_KIND,
        "agent_must_reason": True,
        "registry": str(registry_path),
        "runtime_root": status_payload.get("runtime_root"),
        "goal_id": goal_id,
        "selected_goal_id": selected.get("goal_id"),
        "status_ok": status_payload.get("ok"),
        "goal_count": status_payload.get("goal_count"),
        "run_count": status_payload.get("run_count"),
        "attention_item_count": _as_dict(status_payload.get("attention_queue")).get("item_count"),
        "selected": selected,
        "goals": goal_packets,
        "status_summary": {
            "contract": _as_dict(status_payload.get("contract")).get("summary"),
            "global_registry": _as_dict(_as_dict(status_payload.get("global_registry")).get("summary")),
        },
        "user_prompt": USER_DIAGNOSE_PROMPT,
    }


def render_diagnosis_markdown(payload: dict[str, Any]) -> str:
    selected = _as_dict(payload.get("selected"))
    todo_evidence = _as_dict(selected.get("todo_evidence"))
    quota = _as_dict(selected.get("quota_signals"))
    lines = [
        "# Goal Harness Diagnosis Packet",
        "",
        "This packet is evidence for the user's agent. Goal Harness is not making the final diagnosis.",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- packet_kind: `{payload.get('packet_kind')}`",
        f"- agent_must_reason: `{payload.get('agent_must_reason')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- selected_goal_id: `{payload.get('selected_goal_id')}`",
        f"- goals: `{payload.get('goal_count')}`",
        f"- runs: `{payload.get('run_count')}`",
        "",
        "## Machine Signals",
        "",
        f"- machine_signal: `{selected.get('machine_signal')}`",
        f"- status: `{selected.get('status')}`",
        f"- waiting_on: `{selected.get('waiting_on')}`",
        f"- severity: `{selected.get('severity')}`",
        f"- recommended_action: {selected.get('recommended_action')}",
        f"- user_question: {selected.get('user_question')}",
        f"- user_todo_open_count: `{todo_evidence.get('user_open_count')}`",
        f"- agent_todo_open_count: `{todo_evidence.get('agent_open_count')}`",
    ]
    if todo_evidence.get("first_user_todo"):
        lines.append(f"- first_user_todo: {todo_evidence.get('first_user_todo')}")
    if todo_evidence.get("first_agent_todo"):
        lines.append(f"- first_agent_todo: {todo_evidence.get('first_agent_todo')}")
    if quota:
        lines.extend(
            [
                f"- quota_state: `{quota.get('state')}`",
                f"- quota_should_run: `{quota.get('should_run')}`",
                f"- effective_action: `{quota.get('effective_action')}`",
                f"- requires_user_action: `{quota.get('requires_user_action')}`",
                f"- normal_delivery_allowed: `{quota.get('normal_delivery_allowed')}`",
                f"- self_repair_allowed: `{quota.get('self_repair_allowed')}`",
                f"- safe_bypass_allowed: `{quota.get('safe_bypass_allowed')}`",
                f"- quota_reason: {quota.get('reason')}",
            ]
        )

    checklist = _as_list(selected.get("agent_reasoning_checklist"))
    if checklist:
        lines.extend(["", "## Agent Reasoning Checklist", ""])
        for item in checklist:
            lines.append(f"- {item}")

    commands = _as_list(selected.get("agent_commands"))
    if commands:
        lines.extend(["", "## Agent Commands", ""])
        lines.append("These are for the agent to run when it needs drill-down, not for the user to copy manually.")
        for command in commands:
            lines.append(f"- `{command}`")

    goals = _as_list(payload.get("goals"))
    if goals:
        lines.extend(["", "## Goal Packets", "", "| goal | machine signal | user todo | agent todo |", "| --- | --- | --- | --- |"])
        for goal in goals:
            if not isinstance(goal, dict):
                continue
            evidence = _as_dict(goal.get("todo_evidence"))
            lines.append(
                "| "
                f"`{goal.get('goal_id')}` | "
                f"`{goal.get('machine_signal')}` | "
                f"`{evidence.get('user_open_count')}` | "
                f"`{evidence.get('agent_open_count')}` |"
            )

    lines.extend(["", "## User Prompt", "", str(payload.get("user_prompt") or USER_DIAGNOSE_PROMPT)])
    return "\n".join(lines)
