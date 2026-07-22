from __future__ import annotations

import re
from typing import Any, Callable, Optional, Pattern


PublicSafeText = Callable[..., Optional[str]]
AckRecorded = Callable[[dict[str, Any]], bool]
DeliveryOutcomeNormalizer = Callable[[Any], Any]
SectionParser = Callable[[str, tuple[str, ...]], dict[str, list[str]]]
SectionEntries = Callable[[list[str]], list[str]]


MAX_AUTONOMOUS_REPLAN_TRIGGERS = 3
AUTONOMOUS_REPLAN_STALL_THRESHOLD = 2
AUTONOMOUS_REPLAN_TRIGGER_PATTERNS = (
    (
        "periodic_review",
        re.compile(r"(?i)(?:periodic review|periodic replan|review cadence|规划复盘|周期复盘|每几十轮)"),
    ),
    (
        "no_progress_streak",
        re.compile(r"(?i)(?:no[- ]?progress|stalled?|stall streak|没有实质进展|停转|连续[^。；;]*无进展)"),
    ),
    (
        "repeated_action_loop",
        re.compile(r"(?i)(?:repeated[- ]?action|action loop|same action|looped|重复动作|循环观察|反复观察)"),
    ),
    (
        "phase_transition",
        re.compile(r"(?i)(?:phase transition|next phase|stage transition|readiness .*done|阶段切换|进入下一阶段)"),
    ),
    (
        "backlog_mismatch",
        re.compile(r"(?i)(?:backlog mismatch|todo mismatch|next action mismatch|todo.*淹没|待办.*不一致)"),
    ),
    (
        "evidence_contradiction",
        re.compile(r"(?i)(?:evidence contradiction|contradictory evidence|stale evidence|stale latest-run|证据矛盾|状态矛盾)"),
    ),
    (
        "explicit_replan",
        re.compile(r"(?i)(?:autonomous replan|replan obligation|planning[- ]?trigger|重新规划|重规划|规划触发)"),
    ),
)


def normalized_run_history_stall_signature(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _single_public_agent_id(items: list[dict[str, Any]]) -> str | None:
    agent_ids = {
        str(item.get("agent_id") or "").strip()
        for item in items
        if isinstance(item, dict) and str(item.get("agent_id") or "").strip()
    }
    return next(iter(agent_ids)) if len(agent_ids) == 1 else None


def run_history_agent_id(run: dict[str, Any]) -> str | None:
    agent_id = str(run.get("agent_id") or "").strip()
    if agent_id:
        return agent_id
    monitor_target = run_history_monitor_target(run)
    if isinstance(monitor_target, dict):
        return str(monitor_target.get("agent_id") or "").strip() or None
    return None


def _latest_agent_run_history(
    latest_runs: list[dict[str, Any]] | None,
    *,
    neutral_classifications: set[str],
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Keep the newest attributable agent lane while preserving goal-level runs."""

    accountable_agent_id = str(agent_id or "").strip() or None
    if accountable_agent_id is None:
        accountable_agent_id = next(
            (
                run_history_agent_id(run)
                for run in latest_runs or []
                if isinstance(run, dict)
                and str(run.get("classification") or "").strip()
                not in neutral_classifications
                and run_history_agent_id(run)
            ),
            None,
        )
    if not accountable_agent_id:
        return [run for run in latest_runs or [] if isinstance(run, dict)]
    return [
        run
        for run in latest_runs or []
        if isinstance(run, dict)
        and run_history_agent_id(run) in {None, accountable_agent_id}
    ]


def run_history_monitor_target(run: dict[str, Any]) -> dict[str, Any] | None:
    target = run.get("monitor_target")
    if isinstance(target, dict):
        return target
    event = run.get("monitor_event")
    if isinstance(event, dict) and isinstance(event.get("monitor_target"), dict):
        return event.get("monitor_target")
    return None


def run_history_stall_signal(
    run: dict[str, Any],
    *,
    autonomous_replan_ack_recorded: AckRecorded,
    neutral_classifications: set[str],
    progress_outcomes: set[Any],
    stall_pattern: Pattern[str],
    public_safe_compact_text: PublicSafeText,
    normalize_delivery_outcome: DeliveryOutcomeNormalizer,
) -> dict[str, Any] | None:
    if autonomous_replan_ack_recorded(run):
        return None
    classification = str(run.get("classification") or "").strip()
    if not classification or classification in neutral_classifications:
        return None
    delivery_outcome = normalize_delivery_outcome(run.get("delivery_outcome"))
    if delivery_outcome in progress_outcomes:
        return None
    recommended_action = public_safe_compact_text(run.get("recommended_action"), limit=140)
    health_check = public_safe_compact_text(run.get("health_check"), limit=140)
    combined = " ".join(
        value
        for value in (
            classification,
            recommended_action,
            health_check,
            delivery_outcome.value if delivery_outcome else "",
        )
        if value
    )
    if not combined or not stall_pattern.search(combined):
        return None
    action_or_classification = recommended_action or classification
    signal = {
        "classification": classification,
        "generated_at": str(run.get("generated_at") or ""),
        "agent_id": str(run.get("agent_id") or "").strip() or None,
        "recommended_action": recommended_action,
        "delivery_outcome": delivery_outcome.value if delivery_outcome else None,
        "signature": normalized_run_history_stall_signature(action_or_classification),
    }
    monitor_target = run_history_monitor_target(run)
    if monitor_target:
        signal["monitor_target_id"] = str(monitor_target.get("target_id") or "")
        signal["monitor_target"] = {
            key: monitor_target.get(key)
            for key in (
                "schema_version",
                "target_id",
                "monitor_mode",
                "effective_action",
                "agent_id",
                "frontier_identity",
            )
            if monitor_target.get(key)
        }
    return signal


def run_history_monitor_wait_already_acknowledged(
    latest_runs: list[dict[str, Any]] | None,
    *,
    signal_count: int,
    autonomous_replan_ack_recorded: AckRecorded,
    neutral_classifications: set[str],
) -> bool:
    """Return true when newer monitor-poll stalls already have a compact ack run behind them."""

    for run in (latest_runs or [])[signal_count:]:
        if not isinstance(run, dict):
            continue
        if autonomous_replan_ack_recorded(run):
            return True
        classification = str(run.get("classification") or "").strip()
        if not classification:
            continue
        if classification in neutral_classifications:
            continue
        if classification == "quota_monitor_poll":
            continue
        return False
    return False


def autonomous_replan_periodic_review_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
    autonomous_replan_ack_recorded: AckRecorded,
    neutral_classifications: set[str],
    periodic_run_threshold: int,
    build_autonomous_replan_obligation: Callable[..., dict[str, Any] | None],
) -> dict[str, Any] | None:
    durable_runs: list[dict[str, Any]] = []
    for run in latest_runs or []:
        if not isinstance(run, dict):
            continue
        if autonomous_replan_ack_recorded(run):
            break
        classification = str(run.get("classification") or "").strip()
        if not classification:
            continue
        if classification in neutral_classifications:
            continue
        durable_runs.append(run)
        if len(durable_runs) >= periodic_run_threshold:
            break

    if len(durable_runs) < periodic_run_threshold:
        return None

    evidence: list[dict[str, Any]] = [
        {
            "kind": "periodic_review_due",
            "section": "run_history",
            "text": (
                f"latest {len(durable_runs)} durable public run records since last autonomous "
                f"replan reached periodic review threshold {periodic_run_threshold}"
            ),
            "run_count": len(durable_runs),
            "threshold": periodic_run_threshold,
            "latest_generated_at": str(durable_runs[0].get("generated_at") or ""),
            "oldest_counted_generated_at": str(durable_runs[-1].get("generated_at") or ""),
            "agent_id": _single_public_agent_id(durable_runs),
        }
    ]
    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)


def autonomous_replan_obligation_from_state(
    state_text: str,
    *,
    agent_todos: dict[str, Any] | None,
    section_headings: tuple[str, ...],
    section_parser: SectionParser,
    section_entries: SectionEntries,
    public_safe_compact_text: PublicSafeText,
    build_autonomous_replan_obligation: Callable[..., dict[str, Any] | None],
    trigger_patterns: tuple[tuple[str, Pattern[str]], ...] = AUTONOMOUS_REPLAN_TRIGGER_PATTERNS,
    max_triggers: int = MAX_AUTONOMOUS_REPLAN_TRIGGERS,
) -> dict[str, Any] | None:
    evidence: list[dict[str, Any]] = []
    seen_kinds: set[str] = set()
    sections = section_parser(state_text, section_headings)
    for section, lines in sections.items():
        for entry in section_entries(lines):
            text = public_safe_compact_text(entry, limit=160)
            if not text:
                continue
            for kind, pattern in trigger_patterns:
                if kind in seen_kinds or not pattern.search(text):
                    continue
                evidence.append({"kind": kind, "section": section, "text": text})
                seen_kinds.add(kind)
                if len(evidence) >= max_triggers:
                    break
            if len(evidence) >= max_triggers:
                break
        if len(evidence) >= max_triggers:
            break

    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)


def _monitor_no_change_evidence(
    agent_todos: dict[str, Any] | None,
    *,
    threshold: int,
    schema_version: str,
) -> dict[str, Any] | None:
    if not isinstance(agent_todos, dict):
        return None
    raw_monitors = agent_todos.get("monitor_open_items")
    monitors = [item for item in raw_monitors or [] if isinstance(item, dict)]
    stalled: list[tuple[int, dict[str, Any]]] = []
    for item in monitors:
        try:
            no_change_count = int(str(item.get("consecutive_no_change") or "0"))
        except ValueError:
            continue
        if no_change_count >= threshold:
            stalled.append((no_change_count, item))
    if not stalled:
        return None

    stalled.sort(key=lambda pair: pair[0], reverse=True)
    no_change_count, monitor = stalled[0]
    agent_id = str(monitor.get("claimed_by") or "").strip() or None
    raw_advancements = agent_todos.get("executable_backlog_items")
    if not isinstance(raw_advancements, list):
        raw_advancements = agent_todos.get("items")
    for item in raw_advancements or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() != "open":
            continue
        if str(item.get("task_class") or "").strip() != "advancement_task":
            continue
        claimed_by = str(item.get("claimed_by") or "").strip() or None
        if not claimed_by or claimed_by == agent_id:
            return None

    monitor_target_id = str(
        monitor.get("target_key") or monitor.get("todo_id") or "monitor"
    ).strip()
    return {
        "kind": "monitor_no_change_streak",
        "schema_version": schema_version,
        "section": "agent_todos",
        "text": (
            f"monitor {monitor_target_id} recorded {no_change_count} "
            "consecutive unchanged polls without runnable advancement"
        ),
        "run_count": no_change_count,
        "threshold": threshold,
        "monitor_target_id": monitor_target_id,
        "agent_id": agent_id,
    }


def _has_runnable_agent_advancement(agent_todos: dict[str, Any] | None) -> bool:
    if not isinstance(agent_todos, dict):
        return False
    for key in (
        "first_executable_items",
        "executable_backlog_items",
        "first_open_items",
    ):
        items = agent_todos.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "open").strip().lower() not in {
                "",
                "open",
                "todo",
                "active",
                "pending",
            }:
                continue
            task_class = str(item.get("task_class") or "").strip()
            if task_class in {"", "advancement_task"}:
                return True
    return False


def build_autonomous_replan_obligation(
    evidence: list[dict[str, Any]],
    *,
    agent_todos: dict[str, Any] | None,
    public_safe_compact_text: PublicSafeText,
    autonomous_replan_schema_version: str,
    autonomous_replan_stall_threshold: int,
    dead_monitor_repeat_threshold: int,
    dead_monitor_repeat_schema_version: str,
) -> dict[str, Any] | None:
    if not evidence:
        monitor_evidence = _monitor_no_change_evidence(
            agent_todos,
            threshold=autonomous_replan_stall_threshold,
            schema_version=dead_monitor_repeat_schema_version,
        )
        if monitor_evidence:
            evidence = [monitor_evidence]
    if not evidence:
        return None

    dead_monitor_evidence = next(
        (
            item
            for item in evidence
            if item.get("kind") in {"dead_monitor_repeat", "monitor_no_change_streak"}
        ),
        None,
    )
    blocked_successor_evidence = next(
        (
            item
            for item in evidence
            if item.get("kind") == "blocked_successor_no_progress_repeat"
        ),
        None,
    )
    first_open: dict[str, Any] = {}
    if isinstance(agent_todos, dict):
        open_items = agent_todos.get("first_open_items")
        if isinstance(open_items, list) and open_items and isinstance(open_items[0], dict):
            first_open = open_items[0]

    evidence_has_agent_attribution = any("agent_id" in item for item in evidence)
    replan_agent_id = _single_public_agent_id(evidence)
    if replan_agent_id is None and not evidence_has_agent_attribution:
        replan_agent_id = str(first_open.get("claimed_by") or "").strip() or None

    todo_actions: list[dict[str, Any]] = []
    first_open_text = public_safe_compact_text(first_open.get("text"), limit=140)
    if first_open_text:
        action: dict[str, Any] = {
            "action": "split",
            "role": "agent",
            "text": first_open_text,
        }
        if first_open.get("priority"):
            action["priority"] = first_open.get("priority")
        todo_actions.append(action)
    if blocked_successor_evidence:
        todo_actions.append(
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "discover and promote one safe in-scope evidence-backed successor; "
                    "otherwise record watch-lane continuation for this frontier"
                ),
            }
        )
    elif dead_monitor_evidence:
        todo_actions.append(
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "resolve the repeated monitor target with watch-lane expiry, "
                    "a concrete blocker, todo supersede, or successor runnable todo"
                ),
            }
        )
    else:
        todo_actions.append(
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "write a compact replan record naming trigger, selected next slice, "
                    "validation command, and stop condition"
                ),
            }
        )
    if any(item.get("kind") in {"no_progress_streak", "repeated_action_loop"} for item in evidence):
        todo_actions.append(
            {
                "action": "retire",
                "role": "agent",
                "priority": "P2",
                "text": "retire or downgrade stale monitor-only next actions after the executable replan is selected",
            }
        )
    if any(item.get("kind") in {"periodic_review", "periodic_review_due"} for item in evidence):
        todo_actions.append(
            {
                "action": "ask_decision",
                "role": "user",
                "priority": "P2",
                "text": (
                    "ask the operator only if the review changes benchmark family, public claims, "
                    "resource budget, or protected scope"
                ),
            }
        )

    if blocked_successor_evidence:
        recommended_action = (
            "run a bounded autonomous replan for the exact blocked successor: "
            "promote one safe in-scope evidence-backed successor when available; "
            "otherwise record a no-spend wait continuation for this frontier"
        )
    elif dead_monitor_evidence:
        recommended_action = (
            "resolve a dead monitor loop: record watch-lane continuation with expiry, "
            "a concrete blocker, todo supersede, or successor runnable todo before "
            "another quiet monitor poll"
        )
    elif any(item.get("kind") in {"periodic_review", "periodic_review_due"} for item in evidence):
        recommended_action = (
            "run a bounded autonomous periodic review: keep, split, add, retire, or ask for "
            "a decision; then update todos and select the next validated slice"
        )
    else:
        recommended_action = (
            "run an autonomous replan after two consecutive stalled turns before another "
            "monitor-only or repeated action consumes the eligible turn"
        )

    extra_fields: dict[str, Any] = {}
    if (
        not _has_runnable_agent_advancement(agent_todos)
        and not dead_monitor_evidence
        and not blocked_successor_evidence
    ):
        extra_fields["agent_todo_writeback_required"] = True
    if (
        blocked_successor_evidence
        and blocked_successor_evidence.get("frontier_identity")
    ):
        extra_fields["frontier_identity"] = blocked_successor_evidence.get(
            "frontier_identity"
        )

    result = build_autonomous_replan_obligation_payload(
        schema_version=autonomous_replan_schema_version,
        stall_threshold=(
            int(dead_monitor_evidence.get("threshold") or dead_monitor_repeat_threshold)
            if dead_monitor_evidence
            else autonomous_replan_stall_threshold
        ),
        trigger_count=len(evidence),
        triggers=evidence,
        guidance_actions=(
            ["set_watch_expiry", "write_blocker", "supersede_monitor", "create_successor"]
            if dead_monitor_evidence
            else ["discover_safe_successor", "create_successor", "record_wait_continuation"]
            if blocked_successor_evidence
            else ["keep", "split", "add", "retire", "ask_decision"]
        ),
        todo_actions=todo_actions[:3],
        stop_condition=(
            "stop if the replan requires private material, credentials, destructive git, "
            "production actions, or owner-only decisions"
        ),
        recommended_action=recommended_action,
        agent_id=replan_agent_id,
        extra_fields=extra_fields,
    )
    if dead_monitor_evidence:
        result["dead_monitor_detector"] = {
            "schema_version": dead_monitor_repeat_schema_version,
            "monitor_target_id": dead_monitor_evidence.get("monitor_target_id"),
            "run_count": dead_monitor_evidence.get("run_count"),
            "threshold": dead_monitor_evidence.get("threshold"),
            "required_resolution": [
                "watch_lane_expiry",
                "blocker",
                "todo_supersede",
                "successor_runnable_todo",
            ],
        }
    return result


def build_autonomous_replan_obligation_payload(
    *,
    schema_version: str,
    stall_threshold: int,
    trigger_count: int,
    triggers: list[dict[str, Any]],
    guidance_actions: list[str],
    todo_actions: list[dict[str, Any]],
    stop_condition: str,
    recommended_action: str,
    agent_id: str | None = None,
    include_agent_id: bool = False,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "required": True,
        "stall_threshold": stall_threshold,
        "trigger_count": trigger_count,
        "triggers": triggers,
        "guidance_actions": guidance_actions,
        "todo_actions": todo_actions,
        "stop_condition": stop_condition,
        "recommended_action": recommended_action,
    }
    if include_agent_id or agent_id is not None:
        payload["agent_id"] = agent_id
    if extra_fields:
        payload.update(extra_fields)
    return payload


def autonomous_replan_obligation_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
    agent_id: str | None = None,
    autonomous_replan_ack_recorded: AckRecorded,
    neutral_classifications: set[str],
    progress_outcomes: set[Any],
    stall_pattern: Pattern[str],
    public_safe_compact_text: PublicSafeText,
    normalize_delivery_outcome: DeliveryOutcomeNormalizer,
    build_autonomous_replan_obligation: Callable[..., dict[str, Any] | None],
    autonomous_replan_stall_threshold: int,
    dead_monitor_repeat_threshold: int,
    dead_monitor_repeat_schema_version: str,
    periodic_run_threshold: int,
) -> dict[str, Any] | None:
    scoped_latest_runs = _latest_agent_run_history(
        latest_runs,
        neutral_classifications=neutral_classifications,
        agent_id=agent_id,
    )

    def periodic_review() -> dict[str, Any] | None:
        return autonomous_replan_periodic_review_from_runs(
            scoped_latest_runs,
            agent_todos=agent_todos,
            autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
            neutral_classifications=neutral_classifications,
            periodic_run_threshold=periodic_run_threshold,
            build_autonomous_replan_obligation=build_autonomous_replan_obligation,
        )

    signals: list[dict[str, Any]] = []
    signal_scan_limit = max(autonomous_replan_stall_threshold, dead_monitor_repeat_threshold)
    for run in scoped_latest_runs:
        if not isinstance(run, dict):
            continue
        classification = str(run.get("classification") or "").strip()
        if classification in neutral_classifications:
            continue
        signal = run_history_stall_signal(
            run,
            autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
            neutral_classifications=neutral_classifications,
            progress_outcomes=progress_outcomes,
            stall_pattern=stall_pattern,
            public_safe_compact_text=public_safe_compact_text,
            normalize_delivery_outcome=normalize_delivery_outcome,
        )
        if not signal:
            break
        signals.append(signal)
        if len(signals) >= signal_scan_limit:
            break

    stall_signals = signals[:autonomous_replan_stall_threshold]
    if len(stall_signals) < autonomous_replan_stall_threshold:
        return periodic_review()

    signatures = {str(signal.get("signature") or "") for signal in stall_signals if signal.get("signature")}
    classifications = {
        str(signal.get("classification") or "")
        for signal in stall_signals
        if signal.get("classification")
    }
    if len(signatures) > 1 and len(classifications) > 1:
        return periodic_review()
    if classifications == {"quota_monitor_poll"}:
        blocked_successor_signals = signals[:autonomous_replan_stall_threshold]
        blocked_successor_modes = {
            str((signal.get("monitor_target") or {}).get("monitor_mode") or "")
            for signal in blocked_successor_signals
        }
        if blocked_successor_modes == {
            "blocked_successor_wait_without_material_transition"
        }:
            monitor_target_ids = {
                str(signal.get("monitor_target_id") or "")
                for signal in blocked_successor_signals
                if signal.get("monitor_target_id")
            }
            frontier_identities = {
                str((signal.get("monitor_target") or {}).get("frontier_identity") or "")
                for signal in blocked_successor_signals
                if (signal.get("monitor_target") or {}).get("frontier_identity")
            }
            if len(monitor_target_ids) != 1 or len(frontier_identities) != 1:
                return periodic_review()
            monitor_target_id = next(iter(monitor_target_ids))
            frontier_identity = next(iter(frontier_identities))
            evidence = [
                {
                    "kind": "blocked_successor_no_progress_repeat",
                    "section": "run_history",
                    "text": (
                        f"latest {autonomous_replan_stall_threshold} exact blocked "
                        "successor waits repeated the same frontier without progress"
                    ),
                    "run_count": len(blocked_successor_signals),
                    "threshold": autonomous_replan_stall_threshold,
                    "monitor_target_id": monitor_target_id,
                    "frontier_identity": frontier_identity,
                    "latest_generated_at": signals[0].get("generated_at"),
                    "agent_id": _single_public_agent_id(blocked_successor_signals),
                }
            ]
            return build_autonomous_replan_obligation(
                evidence,
                agent_todos=agent_todos,
            )
        monitor_signals = signals[:dead_monitor_repeat_threshold]
        if len(monitor_signals) < dead_monitor_repeat_threshold:
            return periodic_review()
        monitor_classifications = {
            str(signal.get("classification") or "")
            for signal in monitor_signals
            if signal.get("classification")
        }
        if monitor_classifications != {"quota_monitor_poll"}:
            return periodic_review()
        if run_history_monitor_wait_already_acknowledged(
            scoped_latest_runs,
            signal_count=len(monitor_signals),
            autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
            neutral_classifications=neutral_classifications,
        ):
            return periodic_review()
        monitor_target_ids = {
            str(signal.get("monitor_target_id") or "")
            for signal in monitor_signals
            if signal.get("monitor_target_id")
        }
        if len(monitor_target_ids) != 1:
            return periodic_review()
        monitor_target_id = next(iter(monitor_target_ids))
        evidence = [
            {
                "kind": "dead_monitor_repeat",
                "schema_version": dead_monitor_repeat_schema_version,
                "section": "run_history",
                "text": (
                    f"latest {dead_monitor_repeat_threshold} monitor polls repeated "
                    "the same monitor target without a material transition"
                ),
                "run_count": len(monitor_signals),
                "threshold": dead_monitor_repeat_threshold,
                "monitor_target_id": monitor_target_id,
                "latest_generated_at": signals[0].get("generated_at"),
                "agent_id": _single_public_agent_id(monitor_signals),
            }
        ]
        return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)

    action = public_safe_compact_text(
        stall_signals[0].get("recommended_action") or stall_signals[0].get("classification"),
        limit=120,
    )
    evidence_text = (
        f"latest {autonomous_replan_stall_threshold} public run records repeated "
        f"{action or 'the same monitor/no-progress action'}"
    )
    evidence: list[dict[str, Any]] = [
        {
            "kind": "run_history_no_progress_repeat",
            "section": "run_history",
            "text": evidence_text,
            "run_count": len(stall_signals),
            "latest_generated_at": stall_signals[0].get("generated_at"),
            "agent_id": _single_public_agent_id(stall_signals),
        }
    ]
    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)
