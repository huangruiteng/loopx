from __future__ import annotations

import re
from typing import Any, Callable, Optional, Pattern


PublicSafeText = Callable[..., Optional[str]]
AckRecorded = Callable[[dict[str, Any]], bool]
DeliveryOutcomeNormalizer = Callable[[Any], Any]


def normalized_run_history_stall_signature(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


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
        "recommended_action": recommended_action,
        "delivery_outcome": delivery_outcome.value if delivery_outcome else None,
        "signature": normalized_run_history_stall_signature(action_or_classification),
    }
    monitor_target = run_history_monitor_target(run)
    if monitor_target:
        signal["monitor_target_id"] = str(monitor_target.get("target_id") or "")
        signal["monitor_target"] = {
            key: monitor_target.get(key)
            for key in ("schema_version", "target_id", "monitor_mode", "effective_action", "agent_id")
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
        }
    ]
    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)


def autonomous_replan_obligation_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
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
    def periodic_review() -> dict[str, Any] | None:
        return autonomous_replan_periodic_review_from_runs(
            latest_runs,
            agent_todos=agent_todos,
            autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
            neutral_classifications=neutral_classifications,
            periodic_run_threshold=periodic_run_threshold,
            build_autonomous_replan_obligation=build_autonomous_replan_obligation,
        )

    signals: list[dict[str, Any]] = []
    signal_scan_limit = max(autonomous_replan_stall_threshold, dead_monitor_repeat_threshold)
    for run in latest_runs or []:
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
            latest_runs,
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
        }
    ]
    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)
