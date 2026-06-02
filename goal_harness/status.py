from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .contract import check_contract
from .history import collect_history, load_registry
from .operator_gate import DEFAULT_OPERATOR_GATE, default_operator_question, normalize_operator_question
from .paths import global_registry_path, resolve_runtime_root
from .quota import quota_status
from .registry import registry_goals


CODEX_READY_CLASSIFICATIONS = {
    "controller_opted_in_waiting_for_run",
    "design_next_experiment",
    "inspect_eval_result",
    "inspect_result",
    "needs_more_read_only_evidence",
    "needs_validation",
    "public_harness_healthy",
    "read_only_project_map",
    "run_validation",
    "state_refreshed",
    "operator_gate_approved",
    "quota_slot_spent",
}
USER_OR_CONTROLLER_CLASSIFICATIONS = {
    "needs_human_reward",
    "needs_controller_opt_in",
    "needs_user_relay",
    "ready_for_controller_opt_in",
    "ready_for_user_relay",
    "operator_gate_deferred",
    "operator_gate_rejected",
}
WATCH_CLASSIFICATION_PREFIXES = ("await_", "monitor_")
BLOCKING_CLASSIFICATIONS = {
    "blocked_by_safety",
}
CONNECTED_ADAPTER_STATUSES = {
    "connected",
    "connected-read-only",
    "pre-tick-runnable",
}
PLANNED_CONTROLLER_OPT_IN_RECOMMENDED_ACTION = (
    "先在 Goal Harness 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run"
)
RUN_COMPACT_FIELDS = (
    "generated_at",
    "goal_id",
    "classification",
    "lifecycle_phase",
    "lifecycle_flags",
    "recommended_action",
    "health_check",
    "active_task_count",
    "active_priorities",
    "cache_check",
    "project_map",
    "json_exists",
    "markdown_exists",
)
HUMAN_REWARD_COMPACT_FIELDS = (
    "recorded_at",
    "decision",
    "reward",
    "reason_summary",
    "follow_up",
)
OPERATOR_GATE_COMPACT_FIELDS = (
    "recorded_at",
    "gate",
    "decision",
    "operator_question",
    "reason_summary",
    "follow_up",
    "agent_command",
)
CONTROLLER_READINESS_COMPACT_FIELDS = (
    "classification",
    "read_only_observer_ready",
    "decision_advisor_ready",
    "write_controller_ready",
    "missing_gates",
    "review_judgment",
    "next_handoff_condition",
)
CONTROLLER_READINESS_GATE_FIELDS = (
    "id",
    "ok",
    "review",
)
LIFECYCLE_PRIORITY = (
    "controller_ready",
    "reward_judged",
    "operator_approved",
    "controller_gated",
    "operator_gated",
    "adapter_inspected",
    "mapped",
    "refreshed",
    "connected",
    "registered",
    "planned",
    "run_recorded",
)


def attention_item(
    *,
    goal_id: str,
    status: str,
    waiting_on: str,
    severity: str,
    recommended_action: str,
    source: str,
    operator_question: str | None = None,
    agent_command: str | None = None,
    controller_stage: str | None = None,
    missing_gates: list[str] | None = None,
    next_handoff_condition: str | None = None,
    lifecycle_phase: str | None = None,
    lifecycle_flags: list[str] | None = None,
) -> dict[str, Any]:
    item = {
        "goal_id": goal_id,
        "status": status,
        "waiting_on": waiting_on,
        "severity": severity,
        "recommended_action": recommended_action,
        "source": source,
    }
    if operator_question:
        item["operator_question"] = operator_question
    if agent_command:
        item["agent_command"] = agent_command
    if controller_stage:
        item["controller_stage"] = controller_stage
    if missing_gates:
        item["missing_gates"] = missing_gates
    if next_handoff_condition:
        item["next_handoff_condition"] = next_handoff_condition
    if lifecycle_phase:
        item["lifecycle_phase"] = lifecycle_phase
    if lifecycle_flags:
        item["lifecycle_flags"] = lifecycle_flags
    return item


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def resolve_goal_local_path(raw: Any, goal: dict[str, Any], *, fallback_base: Path) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path
    repo = goal.get("repo")
    if repo:
        return Path(str(repo)).expanduser() / path
    return fallback_base / path


def global_registry_finding(
    *,
    kind: str,
    severity: str,
    message: str,
    recommended_action: str,
    goal_id: str | None = None,
    path: Path | None = None,
    goal_ids: list[str] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "kind": kind,
        "severity": severity,
        "message": message,
        "recommended_action": recommended_action,
    }
    if goal_id:
        finding["goal_id"] = goal_id
    if path:
        finding["path"] = str(path)
    if goal_ids:
        finding["goal_ids"] = goal_ids
    return finding


def collect_global_registry_health(
    *,
    registry_path: Path,
    runtime_root: Path,
    current_registry: dict[str, Any],
) -> dict[str, Any]:
    global_path = global_registry_path(runtime_root)
    if not global_path.exists():
        return {
            "available": False,
            "ok": True,
            "registry": str(global_path),
            "current_registry": str(registry_path),
            "current_registry_is_global": False,
            "summary": {"high": 0, "action": 0, "info": 0, "checks": 0, "findings": 0},
            "findings": [],
            "checks": [],
        }

    global_registry = load_registry(global_path)
    global_goals = registry_goals(global_registry)
    current_goals = registry_goals(current_registry)
    current_ids = {str(goal.get("id")) for goal in current_goals if goal.get("id")}
    global_ids = [str(goal.get("id")) for goal in global_goals if goal.get("id")]
    global_id_set = set(global_ids)
    source_registries: set[str] = set()
    findings: list[dict[str, Any]] = []
    checks: list[str] = []

    current_is_global = same_path(registry_path, global_path)
    id_counts = Counter(global_ids)
    for goal_id, count in sorted(id_counts.items()):
        if count <= 1:
            continue
        findings.append(
            global_registry_finding(
                kind="duplicate_goal_id",
                severity="high",
                goal_id=goal_id,
                message=f"global registry contains {count} entries for `{goal_id}`",
                recommended_action="deduplicate the global registry before trusting multi-project routing",
            )
        )

    for goal in global_goals:
        goal_id = str(goal.get("id") or "unknown-goal")
        source_path = resolve_goal_local_path(goal.get("source_registry"), goal, fallback_base=global_path.parent)
        if source_path:
            source_registries.add(str(source_path))
            if not source_path.exists():
                findings.append(
                    global_registry_finding(
                        kind="source_registry_missing",
                        severity="action",
                        goal_id=goal_id,
                        path=source_path,
                        message=f"`{goal_id}` source registry is missing",
                        recommended_action=f"reconnect `{goal_id}` from its project or archive it if the project is obsolete",
                    )
                )
            else:
                synced_at = parse_timestamp(goal.get("synced_at"))
                if synced_at:
                    source_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)
                    if source_mtime > synced_at.astimezone(timezone.utc) + timedelta(seconds=5):
                        findings.append(
                            global_registry_finding(
                                kind="stale_source_registry",
                                severity="action",
                                goal_id=goal_id,
                                path=source_path,
                                message=f"`{goal_id}` source registry changed after its last global sync",
                                recommended_action=(
                                    f"run `goal-harness sync-global --goal-id {goal_id}` from the source project"
                                ),
                            )
                        )

        state_path = resolve_goal_local_path(goal.get("state_file"), goal, fallback_base=global_path.parent)
        if state_path and not state_path.exists():
            findings.append(
                global_registry_finding(
                    kind="state_file_missing",
                    severity="action",
                    goal_id=goal_id,
                    path=state_path,
                    message=f"`{goal_id}` active state file is missing",
                    recommended_action=f"repair `{goal_id}` state_file or reconnect the project",
                )
            )
        if not state_path:
            findings.append(
                global_registry_finding(
                    kind="state_file_not_declared",
                    severity="action",
                    goal_id=goal_id,
                    message=f"`{goal_id}` does not declare a state_file",
                    recommended_action=f"reconnect `{goal_id}` with a durable active goal state file",
                )
            )

    missing_from_current = sorted(global_id_set - current_ids)
    if not current_is_global and missing_from_current:
        shown = missing_from_current[:8]
        findings.append(
            global_registry_finding(
                kind="current_registry_scope_excludes_global_goals",
                severity="info",
                message=f"current registry excludes {len(missing_from_current)} global goal(s)",
                recommended_action=(
                    "for multi-project dashboard/controller status, run `goal-harness status` "
                    "without `--registry` or pass the global registry"
                ),
                goal_ids=shown,
            )
        )

    checks.append(f"global registry goals checked: {len(global_goals)}")
    checks.append(f"global source registries checked: {len(source_registries)}")
    severity_counts = Counter(str(finding.get("severity") or "info") for finding in findings)
    return {
        "available": True,
        "ok": severity_counts.get("high", 0) == 0,
        "registry": str(global_path),
        "current_registry": str(registry_path),
        "current_registry_is_global": current_is_global,
        "global_goal_count": len(global_goals),
        "current_goal_count": len(current_goals),
        "source_registry_count": len(source_registries),
        "summary": {
            "high": severity_counts.get("high", 0),
            "action": severity_counts.get("action", 0),
            "info": severity_counts.get("info", 0),
            "checks": len(checks),
            "findings": len(findings),
        },
        "findings": findings,
        "checks": checks,
    }


def latest_run(goal: dict[str, Any]) -> dict[str, Any] | None:
    runs = goal.get("latest_runs")
    if not isinstance(runs, list) or not runs:
        return None
    run = runs[0]
    return run if isinstance(run, dict) else None


def ordered_lifecycle_flags(flags: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped = [flag for flag in flags if flag and not (flag in seen or seen.add(flag))]
    priority = {phase: index for index, phase in enumerate(LIFECYCLE_PRIORITY)}
    return sorted(deduped, key=lambda phase: priority.get(phase, len(priority)))


def primary_lifecycle_phase(flags: list[str], fallback: str = "registered") -> str:
    ordered = ordered_lifecycle_flags(flags)
    return ordered[0] if ordered else fallback


def run_lifecycle_flags(run: dict[str, Any] | None) -> list[str]:
    if not isinstance(run, dict):
        return []

    flags: list[str] = []
    classification = str(run.get("classification") or "")
    if classification == "state_refreshed":
        flags.append("refreshed")
    elif classification == "read_only_project_map" or isinstance(run.get("project_map"), dict):
        flags.append("mapped")
    elif classification:
        flags.append("adapter_inspected")
    else:
        flags.append("run_recorded")

    if compact_human_reward(run.get("human_reward")):
        flags.append("reward_judged")

    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if operator_gate:
        if operator_gate.get("decision") == "approve":
            flags.append("operator_approved")
        else:
            flags.append("operator_gated")

    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if readiness:
        if readiness.get("decision_advisor_ready") or readiness.get("write_controller_ready"):
            flags.append("controller_ready")
        elif readiness.get("read_only_observer_ready") or readiness.get("classification"):
            flags.append("controller_gated")

    return ordered_lifecycle_flags(flags)


def run_lifecycle_phase(run: dict[str, Any] | None) -> str:
    return primary_lifecycle_phase(run_lifecycle_flags(run), fallback="run_recorded")


def goal_lifecycle_fields(goal: dict[str, Any], current_run: dict[str, Any] | None) -> dict[str, Any]:
    if current_run:
        flags = run_lifecycle_flags(current_run)
        return {
            "lifecycle_phase": primary_lifecycle_phase(flags),
            "lifecycle_flags": flags,
        }

    adapter_status = str(goal.get("adapter_status") or "")
    status = str(goal.get("status") or "")
    flags: list[str]
    if adapter_status in CONNECTED_ADAPTER_STATUSES:
        flags = ["connected"]
    elif "planned" in status or adapter_status == "planned":
        flags = ["planned"]
    else:
        flags = ["registered"]
    flags = ordered_lifecycle_flags(flags)
    return {
        "lifecycle_phase": primary_lifecycle_phase(flags),
        "lifecycle_flags": flags,
    }


def readiness_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if not readiness:
        return {}
    fields: dict[str, Any] = {}
    if readiness.get("classification"):
        fields["controller_stage"] = readiness.get("classification")
    missing = readiness.get("missing_gates")
    if isinstance(missing, list):
        public_missing = [str(gate) for gate in missing if gate]
        if public_missing:
            fields["missing_gates"] = public_missing
    if readiness.get("next_handoff_condition"):
        fields["next_handoff_condition"] = readiness.get("next_handoff_condition")
    return fields


def operator_gate_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if not operator_gate:
        return {}
    fields: dict[str, Any] = {}
    if operator_gate.get("decision") != "approve" and operator_gate.get("operator_question"):
        fields["operator_question"] = normalize_operator_question(
            str(operator_gate.get("operator_question") or ""),
            goal_id=str(run.get("goal_id") or ""),
            gate=str(operator_gate.get("gate") or DEFAULT_OPERATOR_GATE),
        )
    if operator_gate.get("decision") == "approve" and operator_gate.get("agent_command"):
        fields["agent_command"] = operator_gate.get("agent_command")
    if operator_gate.get("follow_up"):
        fields["next_handoff_condition"] = operator_gate.get("follow_up")
    return fields


def legacy_runtime_goal_attention(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    readiness_fields: dict[str, Any],
) -> dict[str, Any] | None:
    if not goal.get("legacy_runtime_goal") or not current_run:
        return None

    goal_id = str(goal.get("id") or "unknown-goal")
    json_exists = bool(current_run.get("json_exists"))
    markdown_exists = bool(current_run.get("markdown_exists"))
    classification = str(current_run.get("classification") or "unknown")
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)

    actionable_classification = (
        classification in BLOCKING_CLASSIFICATIONS
        or classification in USER_OR_CONTROLLER_CLASSIFICATIONS
        or classification in CODEX_READY_CLASSIFICATIONS
    )
    if not actionable_classification and json_exists and markdown_exists:
        return None

    if not json_exists or not markdown_exists:
        severity = "high"
        action = (
            "repair this unregistered runtime goal or preview cleanup with "
            f"`goal-harness archive-runtime --goal-id {goal_id}` before trusting multi-project status"
        )
    elif classification in BLOCKING_CLASSIFICATIONS:
        severity = "high"
        action = (
            f"latest classification is {classification}; add this runtime goal to the registry "
            f"or preview cleanup with `goal-harness archive-runtime --goal-id {goal_id}` "
            "so multi-project status stays authoritative"
        )
    else:
        severity = "action"
        action = (
            f"latest classification is {classification}; add this runtime goal to the registry "
            f"or preview cleanup with `goal-harness archive-runtime --goal-id {goal_id}` "
            "so multi-project status stays authoritative"
        )

    return attention_item(
        goal_id=goal_id,
        status="unregistered_runtime_goal",
        waiting_on="controller",
        severity=severity,
        recommended_action=action,
        source="run_history",
        **readiness_fields,
        **lifecycle_fields,
    )


def goal_attention(goal: dict[str, Any]) -> dict[str, Any] | None:
    goal_id = str(goal.get("id") or "unknown-goal")
    adapter_status = str(goal.get("adapter_status") or "")
    adapter_kind = str(goal.get("adapter_kind") or "")
    current_run = latest_run(goal)
    readiness_fields = readiness_attention_fields(current_run)
    operator_gate_fields = operator_gate_attention_fields(current_run)
    attention_fields = {**readiness_fields, **operator_gate_fields}
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)

    if goal.get("legacy_runtime_goal"):
        return legacy_runtime_goal_attention(goal, current_run, readiness_fields)

    if not current_run:
        if adapter_status in CONNECTED_ADAPTER_STATUSES:
            return attention_item(
                goal_id=goal_id,
                status="connected_without_run",
                waiting_on="codex",
                severity="action",
                recommended_action="run the first read-only adapter tick and save a compact run record",
                source="run_history",
                **lifecycle_fields,
            )
        if adapter_status == "planned" and adapter_kind.endswith("_read_only_map_v0"):
            command = f"goal-harness read-only-map --goal-id {goal_id} --dry-run"
            return attention_item(
                goal_id=goal_id,
                status=str(goal.get("status") or "planned"),
                waiting_on="user_or_controller",
                severity="action",
                recommended_action=PLANNED_CONTROLLER_OPT_IN_RECOMMENDED_ACTION,
                operator_question=default_operator_question(goal_id, DEFAULT_OPERATOR_GATE),
                agent_command=command,
                source="registry",
                **lifecycle_fields,
            )
        return attention_item(
            goal_id=goal_id,
            status=str(goal.get("status") or "no_run"),
            waiting_on="controller",
            severity="action",
            recommended_action="connect an adapter or run a read-only map before expecting runtime status",
            source="registry",
            **lifecycle_fields,
        )

    json_exists = bool(current_run.get("json_exists"))
    markdown_exists = bool(current_run.get("markdown_exists"))
    if not json_exists or not markdown_exists:
        return attention_item(
            goal_id=goal_id,
            status="run_artifact_missing",
            waiting_on="codex",
            severity="high",
            recommended_action="repair or regenerate the latest run artifacts before trusting status",
            source="run_history",
            **attention_fields,
            **lifecycle_fields,
        )

    classification = str(current_run.get("classification") or "unknown")
    action = str(current_run.get("recommended_action") or "inspect the latest run and choose one next action")
    if classification in BLOCKING_CLASSIFICATIONS:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="user_or_controller",
            severity="high",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if classification in USER_OR_CONTROLLER_CLASSIFICATIONS:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="user_or_controller",
            severity="action",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if classification in CODEX_READY_CLASSIFICATIONS:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="codex",
            severity="action",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if classification.startswith(WATCH_CLASSIFICATION_PREFIXES):
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="external_evidence",
            severity="watch",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    return None


def build_attention_queue(
    *,
    contract: dict[str, Any],
    history: dict[str, Any],
    global_registry: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if contract.get("ok") is False:
        items.append(
            attention_item(
                goal_id="goal-harness-contract",
                status="contract_check_failed",
                waiting_on="codex",
                severity="high",
                recommended_action="fix contract errors before advancing goal adapters",
                source="contract",
            )
        )
    for finding in global_registry.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        if finding.get("severity") not in {"high", "action"}:
            continue
        goal_id = str(finding.get("goal_id") or "global-registry")
        items.append(
            attention_item(
                goal_id=goal_id,
                status=str(finding.get("kind") or "global_registry_finding"),
                waiting_on="codex",
                severity=str(finding.get("severity") or "action"),
                recommended_action=str(finding.get("recommended_action") or "inspect global registry health"),
                source="global_registry",
            )
        )

    for goal in history.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        item = goal_attention(goal)
        if item:
            if goal.get("registry_member"):
                item["quota"] = quota_status(
                    goal,
                    waiting_on=str(item.get("waiting_on") or ""),
                    severity=str(item.get("severity") or ""),
                )
            items.append(item)

    return {
        "available": True,
        "item_count": len(items),
        "needs_user_or_controller": sum(
            1 for item in items if item["waiting_on"] in {"user_or_controller", "controller"}
        ),
        "needs_controller": sum(1 for item in items if item["waiting_on"] == "controller"),
        "needs_codex": sum(1 for item in items if item["waiting_on"] == "codex"),
        "watching_external_evidence": sum(1 for item in items if item["waiting_on"] == "external_evidence"),
        "items": items,
    }


def compact_human_reward(reward: Any) -> dict[str, Any] | None:
    if not isinstance(reward, dict):
        return None
    compact = {field: reward[field] for field in HUMAN_REWARD_COMPACT_FIELDS if field in reward}
    return compact or None


def compact_operator_gate(operator_gate: Any) -> dict[str, Any] | None:
    if not isinstance(operator_gate, dict):
        return None
    compact = {field: operator_gate[field] for field in OPERATOR_GATE_COMPACT_FIELDS if field in operator_gate}
    return compact or None


def compact_controller_readiness(readiness: Any) -> dict[str, Any] | None:
    if not isinstance(readiness, dict):
        return None
    compact = {
        field: readiness[field]
        for field in CONTROLLER_READINESS_COMPACT_FIELDS
        if field in readiness
    }
    gates = []
    for gate in readiness.get("gates") or []:
        if not isinstance(gate, dict):
            continue
        gates.append({field: gate[field] for field in CONTROLLER_READINESS_GATE_FIELDS if field in gate})
    if gates:
        compact["gates"] = gates
    return compact or None


def _markdown_scalar(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def _append_human_reward_markdown(lines: list[str], goal_id: Any, reward: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("recorded_at", "decision", "reward"):
        value = reward.get(field)
        if value:
            headline_parts.append(f"{field}={_markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - human_reward: {' '.join(headline_parts)}")
    reason = reward.get("reason_summary")
    if reason:
        lines.append(f"      - reason_summary: {_markdown_scalar(reason)}")
    follow_up = reward.get("follow_up")
    if follow_up:
        lines.append(f"      - follow_up: {_markdown_scalar(follow_up)}")
    if goal_id:
        lines.append(
            "      - project_agent_visibility: "
            f"`goal-harness history --goal-id {_markdown_scalar(goal_id)} --limit 3`"
        )


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    compact = {field: run[field] for field in RUN_COMPACT_FIELDS if field in run}
    flags = run_lifecycle_flags(run)
    compact.setdefault("lifecycle_phase", primary_lifecycle_phase(flags, fallback="run_recorded"))
    compact.setdefault("lifecycle_flags", flags)
    reward = compact_human_reward(run.get("human_reward"))
    if reward:
        compact["human_reward"] = reward
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if operator_gate:
        compact["operator_gate"] = operator_gate
    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if readiness:
        compact["controller_readiness"] = readiness
    return compact


def build_run_history(history: dict[str, Any]) -> dict[str, Any]:
    goals: list[dict[str, Any]] = []
    for goal in history.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        current_run = latest_run(goal)
        lifecycle_fields = goal_lifecycle_fields(goal, current_run)
        goals.append(
            {
                "id": goal.get("id"),
                "domain": goal.get("domain"),
                "status": goal.get("status"),
                "lifecycle_phase": lifecycle_fields["lifecycle_phase"],
                "lifecycle_flags": lifecycle_fields["lifecycle_flags"],
                "registry_member": goal.get("registry_member"),
                "legacy_runtime_goal": goal.get("legacy_runtime_goal"),
                "adapter_kind": goal.get("adapter_kind"),
                "adapter_status": goal.get("adapter_status"),
                "authority_registry": goal.get("authority_registry"),
                "quota": quota_status(goal) if goal.get("registry_member") else None,
                "index_exists": goal.get("index_exists"),
                "raw_index_records": goal.get("raw_index_records"),
                "unique_runs": goal.get("unique_runs"),
                "latest_runs": [
                    compact_run(run)
                    for run in goal.get("latest_runs") or []
                    if isinstance(run, dict)
                ],
            }
        )

    recent_runs = [
        compact_run(run)
        for run in history.get("runs") or []
        if isinstance(run, dict)
    ]
    return {
        "available": True,
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "goals": goals,
        "recent_runs": recent_runs,
    }


def collect_status(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    global_registry = collect_global_registry_health(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=registry,
    )
    history = collect_history(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=None,
        limit=limit,
    )
    contract = check_contract(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        limit=limit,
    )
    queue = build_attention_queue(contract=contract, history=history, global_registry=global_registry)
    run_history = build_run_history(history)
    return {
        "ok": bool(contract.get("ok")) and bool(global_registry.get("ok", True)),
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "contract": {
            "ok": contract.get("ok"),
            "summary": contract.get("summary"),
            "errors": contract.get("errors") or [],
            "warnings": contract.get("warnings") or [],
            "checks": contract.get("checks") or [],
        },
        "global_registry": global_registry,
        "attention_queue": queue,
        "run_history": run_history,
    }


def render_status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Status",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- goals: `{payload.get('goal_count')}`",
        f"- runs: `{payload.get('run_count')}`",
    ]

    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    summary = contract.get("summary") if isinstance(contract.get("summary"), dict) else {}
    lines.append(
        "- contract: "
        f"ok={contract.get('ok')}, "
        f"errors={summary.get('errors')}, "
        f"warnings={summary.get('warnings')}, "
        f"checks={summary.get('checks')}"
    )

    global_registry = payload.get("global_registry") if isinstance(payload.get("global_registry"), dict) else {}
    global_summary = (
        global_registry.get("summary")
        if isinstance(global_registry.get("summary"), dict)
        else {}
    )
    lines.extend(
        [
            "- global_registry: "
            f"available={global_registry.get('available')}, "
            f"ok={global_registry.get('ok')}, "
            f"findings={global_summary.get('findings')}, "
            f"high={global_summary.get('high')}, "
            f"action={global_summary.get('action')}, "
            f"info={global_summary.get('info')}",
        ]
    )

    queue = payload.get("attention_queue") if isinstance(payload.get("attention_queue"), dict) else {}
    lines.extend(
        [
            "",
            "## Attention Queue",
            "- summary: "
            f"items={queue.get('item_count')}, "
            f"needs_user_or_controller={queue.get('needs_user_or_controller')}, "
            f"needs_controller={queue.get('needs_controller')}, "
            f"needs_codex={queue.get('needs_codex')}, "
            f"watching_external_evidence={queue.get('watching_external_evidence')}",
        ]
    )
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    if not items:
        lines.append("- none")
    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get("recommended_action") or "").replace("|", "\\|")
        lines.append(
            "- "
            f"`{item.get('goal_id')}`: "
            f"status={item.get('status')} "
            f"phase={item.get('lifecycle_phase')} "
            f"waiting_on={item.get('waiting_on')} "
            f"severity={item.get('severity')} "
            f"source={item.get('source')}"
        )
        if action:
            lines.append(f"  - action: {action}")
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        if quota:
            lines.append(
                "  - quota: "
                f"compute={quota.get('compute')} "
                f"state={quota.get('state')} "
                f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')} "
                f"reason={quota.get('reason')}"
            )
        operator_question = item.get("operator_question")
        agent_command = item.get("agent_command")
        if operator_question:
            lines.append(f"  - operator_question: {operator_question}")
            if agent_command:
                goal_id = item.get("goal_id")
                lines.append(
                    "  - operator_gate_dry_run: "
                    f"`goal-harness operator-gate --goal-id {goal_id} --decision approve "
                    '--reason-summary "<public-safe reason>" --dry-run`'
                )
        if agent_command:
            lines.append(f"  - agent_command: `{agent_command}`")
        gates = item.get("missing_gates") if isinstance(item.get("missing_gates"), list) else []
        gate_text = ", ".join(str(gate) for gate in gates if gate)
        controller_stage = item.get("controller_stage")
        next_condition = item.get("next_handoff_condition")
        if controller_stage or gate_text:
            lines.append(
                "  - gates: "
                f"stage={controller_stage or 'none'} "
                f"missing={gate_text or 'none'}"
            )
        if next_condition:
            lines.append(f"  - next_handoff_condition: {next_condition}")

    run_history = payload.get("run_history") if isinstance(payload.get("run_history"), dict) else {}
    run_goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    lines.extend(
        [
            "",
            "## Run History",
            "- summary: "
            f"goals={run_history.get('goal_count')}, "
            f"runs={run_history.get('run_count')}",
        ]
    )
    if not run_goals:
        lines.append("- none")
    for goal in run_goals:
        if not isinstance(goal, dict):
            continue
        lines.append(
            "- "
            f"`{goal.get('id')}`: "
            f"status={goal.get('status')} "
            f"phase={goal.get('lifecycle_phase')} "
            f"adapter={goal.get('adapter_kind')}:{goal.get('adapter_status')} "
            f"records={goal.get('raw_index_records')} "
            f"unique_runs={goal.get('unique_runs')}"
        )
        quota = goal.get("quota") if isinstance(goal.get("quota"), dict) else {}
        if quota:
            lines.append(
                "  - quota: "
                f"compute={quota.get('compute')} "
                f"state={quota.get('state')} "
                f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')}"
            )
        latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
        if latest_runs:
            latest = latest_runs[0]
            if isinstance(latest, dict):
                reward = latest.get("human_reward") if isinstance(latest.get("human_reward"), dict) else {}
                reward_text = (
                    f" reward={reward.get('decision')}:{reward.get('reward')}"
                    if reward
                    else ""
                )
                operator_gate = (
                    latest.get("operator_gate")
                    if isinstance(latest.get("operator_gate"), dict)
                    else {}
                )
                operator_gate_text = (
                    f" operator_gate={operator_gate.get('gate')}:{operator_gate.get('decision')}"
                    if operator_gate
                    else ""
                )
                readiness = (
                    latest.get("controller_readiness")
                    if isinstance(latest.get("controller_readiness"), dict)
                    else {}
                )
                readiness_text = (
                    f" readiness={readiness.get('classification')}"
                    if readiness
                    else ""
                )
                lines.append(
                    "  - latest: "
                    f"{latest.get('generated_at')} "
                    f"classification={latest.get('classification')} "
                    f"phase={latest.get('lifecycle_phase')} "
                    f"artifacts={latest.get('json_exists')}/{latest.get('markdown_exists')}"
                    f"{reward_text}"
                    f"{operator_gate_text}"
                    f"{readiness_text}"
                )
                if reward:
                    _append_human_reward_markdown(lines, goal.get("id"), reward)

    for title, key in (("Errors", "errors"), ("Warnings", "warnings"), ("Checks", "checks")):
        entries = contract.get(key) if isinstance(contract.get(key), list) else []
        if entries:
            lines.extend(["", f"## {title}"])
            lines.extend(f"- {entry}" for entry in entries)

    findings = (
        global_registry.get("findings")
        if isinstance(global_registry.get("findings"), list)
        else []
    )
    if findings:
        lines.extend(["", "## Global Registry Findings"])
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.append(
                "- "
                f"{finding.get('severity')} "
                f"{finding.get('kind')} "
                f"goal={finding.get('goal_id') or finding.get('goal_ids') or 'global'}: "
                f"{finding.get('message')}"
            )
            if finding.get("recommended_action"):
                lines.append(f"  - action: {finding.get('recommended_action')}")

    return "\n".join(lines)
