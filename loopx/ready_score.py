from __future__ import annotations

from typing import Any
from urllib.parse import quote


READY_SCORE_SCHEMA_VERSION = "loopx_ready_score_report_v0"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _first_attention_item(status_payload: dict[str, Any], *, goal_id: str | None) -> dict[str, Any]:
    queue = _as_dict(status_payload.get("attention_queue"))
    for item in _as_list(queue.get("items")):
        if not isinstance(item, dict):
            continue
        if goal_id is None or str(item.get("goal_id") or "") == goal_id:
            return item
    return {}


def select_ready_score_goal_id(status_payload: dict[str, Any], requested_goal_id: str | None = None) -> str | None:
    if requested_goal_id:
        return requested_goal_id
    item = _first_attention_item(status_payload, goal_id=None)
    if item.get("goal_id"):
        return str(item.get("goal_id"))
    goal_filter = status_payload.get("goal_filter")
    return str(goal_filter) if goal_filter else None


def _todo_summary(item: dict[str, Any], key: str) -> dict[str, Any]:
    direct = _as_dict(item.get(key))
    project_asset = _as_dict(item.get("project_asset"))
    asset = _as_dict(project_asset.get(key))
    return direct or asset


def _first_executable_count(summary: dict[str, Any]) -> int:
    return len(_as_list(summary.get("first_executable_items")))


def _quota_scheduler_apply_needed(quota_payload: dict[str, Any]) -> bool | None:
    scheduler = _as_dict(quota_payload.get("scheduler_hint"))
    codex_app = _as_dict(scheduler.get("codex_app"))
    stateful = _as_dict(codex_app.get("stateful_backoff"))
    value = stateful.get("apply_needed")
    return value if isinstance(value, bool) else None


def _check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    label: str,
    points: int,
    max_points: int,
    status: str,
    detail: str,
    action: str | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "status": status,
            "points": max(0, min(points, max_points)),
            "max_points": max_points,
            "detail": detail,
            "action": action,
        }
    )


def _grade(score: int) -> tuple[str, str, str]:
    if score >= 90:
        return "ready", "green", "Ready for autonomous LoopX use"
    if score >= 75:
        return "mostly_ready", "yellowgreen", "Mostly ready; review the warnings"
    if score >= 60:
        return "partially_ready", "yellow", "Partially ready; fix the main gaps first"
    if score >= 40:
        return "needs_setup", "orange", "Needs setup before recurring automation"
    return "not_ready", "red", "Not ready for autonomous LoopX use"


def _badge(score: int, grade: str, color: str) -> dict[str, Any]:
    message = f"{grade}-{score}"
    url = f"https://img.shields.io/badge/{quote('LoopX ready')}-{quote(message)}-{quote(color)}"
    return {
        "label": "LoopX ready",
        "message": message,
        "color": color,
        "preview_url": url,
        "markdown": f"![LoopX ready]({url})",
        "writeback_policy": "preview_only; do not write README or badges from this command",
    }


def build_ready_score_report(
    *,
    doctor_payload: dict[str, Any],
    status_payload: dict[str, Any],
    quota_payload: dict[str, Any] | None = None,
    goal_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    selected_goal_id = select_ready_score_goal_id(status_payload, goal_id)
    item = _first_attention_item(status_payload, goal_id=selected_goal_id)
    quota = _as_dict(quota_payload)
    agent_todos = _todo_summary(item, "agent_todos")
    user_todos = _todo_summary(item, "user_todos")
    checks: list[dict[str, Any]] = []

    doctor_ok = bool(doctor_payload.get("ok"))
    _check(
        checks,
        check_id="install_core",
        label="CLI install and import health",
        points=12 if doctor_ok else 0,
        max_points=12,
        status="pass" if doctor_ok else "fail",
        detail="doctor required checks pass" if doctor_ok else "doctor required checks failed",
        action=None if doctor_ok else "run loopx doctor and repair PATH/install/global registry write access",
    )

    skills = _as_dict(doctor_payload.get("skills"))
    skill_values = [value for value in skills.values() if isinstance(value, dict)]
    skill_exists = bool(skill_values) and all(bool(value.get("exists")) for value in skill_values)
    skill_routes = bool(skill_values) and all(bool(value.get("required_phrases")) for value in skill_values)
    if skill_exists and skill_routes:
        skill_points, skill_status, skill_detail = 8, "pass", "installed LoopX skills and route phrases are current"
    elif skill_exists:
        skill_points, skill_status, skill_detail = 4, "warn", "skills exist but at least one route phrase is stale"
    else:
        skill_points, skill_status, skill_detail = 0, "fail", "one or more LoopX skills are missing"
    _check(
        checks,
        check_id="install_skills",
        label="Installed agent skills",
        points=skill_points,
        max_points=8,
        status=skill_status,
        detail=skill_detail,
        action=None if skill_status == "pass" else "refresh installed LoopX skills with loopx slash-commands --install",
    )

    freshness = _as_dict(doctor_payload.get("install_freshness"))
    freshness_status = str(freshness.get("status") or "unknown")
    if freshness_status in {"fresh", "live_checkout"}:
        freshness_points, freshness_state = 8, "pass"
    elif freshness_status == "unknown":
        freshness_points, freshness_state = 5, "warn"
    elif freshness_status in {"stale", "repair_recommended"}:
        freshness_points, freshness_state = 3, "warn"
    else:
        freshness_points, freshness_state = 0, "fail"
    _check(
        checks,
        check_id="release_freshness",
        label="Default release freshness",
        points=freshness_points,
        max_points=8,
        status=freshness_state,
        detail=str(freshness.get("reason") or freshness_status),
        action=None if freshness_state == "pass" else "upgrade or reinstall LoopX before relying on unattended runs",
    )

    contract = _as_dict(status_payload.get("contract"))
    contract_summary = _as_dict(status_payload.get("contract_summary") or contract.get("summary"))
    contract_ok = bool(status_payload.get("ok")) and bool(contract.get("ok", True))
    contract_errors = _int(contract_summary.get("errors"))
    _check(
        checks,
        check_id="status_contract",
        label="Status and contract projection",
        points=12 if contract_ok and contract_errors == 0 else 4 if status_payload.get("ok") else 0,
        max_points=12,
        status="pass" if contract_ok and contract_errors == 0 else "warn" if status_payload.get("ok") else "fail",
        detail=f"status ok={bool(status_payload.get('ok'))}, contract_errors={contract_errors}",
        action=None if contract_ok and contract_errors == 0 else "run loopx check and repair status/contract projection errors",
    )

    has_goal = bool(selected_goal_id and item)
    has_action = bool(item.get("active_state_next_action") or item.get("recommended_action"))
    _check(
        checks,
        check_id="goal_connection",
        label="Connected goal and next action",
        points=12 if has_goal and has_action else 6 if has_goal else 0,
        max_points=12,
        status="pass" if has_goal and has_action else "warn" if has_goal else "fail",
        detail=(
            f"goal_id={selected_goal_id}, next_action_projected={has_action}"
            if selected_goal_id
            else "no goal selected"
        ),
        action=None if has_goal and has_action else "connect a goal or refresh state so status projects a concrete next action",
    )

    agent_open = _int(agent_todos.get("open_count"))
    executable_open = _first_executable_count(agent_todos)
    user_open = _int(user_todos.get("open_count"))
    runway_points = 0
    if executable_open > 0:
        runway_points += 8
    elif agent_open > 0:
        runway_points += 4
    if user_open == 0:
        runway_points += 4
    todo_status = "pass" if runway_points >= 12 else "warn" if runway_points > 0 else "fail"
    _check(
        checks,
        check_id="todo_runway",
        label="Agent todo runway and user gates",
        points=runway_points,
        max_points=12,
        status=todo_status,
        detail=f"agent_open={agent_open}, executable_open={executable_open}, user_open={user_open}",
        action=None if todo_status == "pass" else "add/claim an executable agent todo or resolve open user gates",
    )

    quota_state = str(_as_dict(quota.get("quota")).get("state") or quota.get("state") or "unknown")
    should_run = bool(quota.get("should_run"))
    effective_action = str(quota.get("effective_action") or quota.get("decision") or "")
    normal_allowed = bool(quota.get("normal_delivery_allowed"))
    scheduler_apply_needed = _quota_scheduler_apply_needed(quota)
    quota_points = 0
    if should_run and quota_state == "eligible":
        quota_points += 8
    elif should_run:
        quota_points += 5
    if normal_allowed or effective_action == "normal_run":
        quota_points += 5
    if scheduler_apply_needed is False:
        quota_points += 4
    elif scheduler_apply_needed is None:
        quota_points += 2
    if quota.get("recommended_action") or _as_dict(quota.get("interaction_contract")).get("primary_action"):
        quota_points += 3
    quota_status = "pass" if quota_points >= 18 else "warn" if quota_points > 0 else "fail"
    _check(
        checks,
        check_id="quota_scheduler",
        label="Quota, identity, and scheduler readiness",
        points=quota_points,
        max_points=20,
        status=quota_status,
        detail=(
            f"should_run={should_run}, quota_state={quota_state}, "
            f"effective_action={effective_action or 'unknown'}, scheduler_apply_needed={scheduler_apply_needed}"
        ),
        action=None if quota_status == "pass" else "rerun quota should-run with the registered agent id and apply scheduler ack if requested",
    )

    run_count = _int(status_payload.get("run_count"))
    usage = _as_dict(status_payload.get("usage_summary"))
    usage_totals = _as_dict(usage.get("totals"))
    event = _as_dict(status_payload.get("event_ledger_summary"))
    event_totals = _as_dict(event.get("totals"))
    promotion = _as_dict(status_payload.get("promotion_readiness_summary"))
    evidence_points = 0
    if run_count > 0:
        evidence_points += 3
    if _int(usage_totals.get("progress_signal_run_count_24h")) > 0:
        evidence_points += 3
    if _int(event_totals.get("events_24h")) > 0:
        evidence_points += 2
    if promotion.get("is_fresh") is True:
        evidence_points += 2
    _check(
        checks,
        check_id="evidence_history",
        label="Evidence and progress history",
        points=evidence_points,
        max_points=10,
        status="pass" if evidence_points >= 8 else "warn" if evidence_points > 0 else "fail",
        detail=(
            f"runs={run_count}, progress_24h={_int(usage_totals.get('progress_signal_run_count_24h'))}, "
            f"events_24h={_int(event_totals.get('events_24h'))}, promotion_fresh={promotion.get('is_fresh')}"
        ),
        action=None if evidence_points >= 8 else "run one validated LoopX state refresh or smoke so readiness is grounded in fresh evidence",
    )

    global_registry = _as_dict(status_payload.get("global_registry"))
    global_summary = _as_dict(global_registry.get("summary"))
    high_findings = _int(global_summary.get("high"))
    action_findings = _int(global_summary.get("action"))
    global_points = 0
    if global_registry.get("ok") and high_findings == 0:
        global_points += 4
    if action_findings == 0:
        global_points += 2
    elif action_findings <= 5:
        global_points += 1
    _check(
        checks,
        check_id="registry_hygiene",
        label="Global registry hygiene",
        points=global_points,
        max_points=6,
        status="pass" if global_points >= 6 else "warn" if global_points > 0 else "fail",
        detail=f"global_ok={bool(global_registry.get('ok'))}, high={high_findings}, action={action_findings}",
        action=None if global_points >= 6 else "archive or reconnect obsolete global registry entries when convenient",
    )

    score = int(round(sum(check["points"] for check in checks) * 100 / sum(check["max_points"] for check in checks)))
    grade, badge_color, grade_summary = _grade(score)
    recommendations = [
        {
            "id": check["id"],
            "status": check["status"],
            "action": check["action"],
        }
        for check in checks
        if check.get("status") != "pass" and check.get("action")
    ]
    return {
        "ok": True,
        "schema_version": READY_SCORE_SCHEMA_VERSION,
        "score": score,
        "grade": grade,
        "summary": grade_summary,
        "mutation_policy": "read_only; computes a report only; does not write registry, state, automation, README, or badges",
        "goal_id": selected_goal_id,
        "agent_id": agent_id,
        "checks": checks,
        "recommendations": recommendations,
        "badge": _badge(score, grade, badge_color),
        "source_signals": {
            "doctor": bool(doctor_payload),
            "status": bool(status_payload),
            "quota": bool(quota_payload),
        },
    }


def render_ready_score_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Ready score",
        "",
        f"- score: `{payload.get('score')}/100`",
        f"- grade: `{payload.get('grade')}`",
        f"- summary: {payload.get('summary')}",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- mutation_policy: {payload.get('mutation_policy')}",
        "",
        "## Badge Preview",
        "",
        str(_as_dict(payload.get("badge")).get("markdown") or ""),
        "",
        "This is a preview only. The command does not edit README files or publish a badge.",
        "",
        "## Checks",
        "",
        "| Check | Status | Points | Detail |",
        "| --- | --- | ---: | --- |",
    ]
    for check in _as_list(payload.get("checks")):
        if not isinstance(check, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(check.get("label") or check.get("id") or ""),
                    f"`{check.get('status')}`",
                    f"{check.get('points')}/{check.get('max_points')}",
                    str(check.get("detail") or "").replace("|", "\\|"),
                ]
            )
            + " |"
        )
    recommendations = [item for item in _as_list(payload.get("recommendations")) if isinstance(item, dict)]
    if recommendations:
        lines.extend(["", "## Recommended Fixes", ""])
        for item in recommendations:
            lines.append(f"- `{item.get('id')}`: {item.get('action')}")
    return "\n".join(lines).rstrip() + "\n"
