from __future__ import annotations

from collections.abc import Callable
from typing import Any


def is_handoff_ready_run(
    run: dict[str, Any],
    *,
    handoff_ready_classifications: set[str],
    compact_operator_gate: Callable[[Any], dict[str, Any] | None],
) -> bool:
    classification = str(run.get("classification") or "")
    if classification in handoff_ready_classifications:
        return True
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    return bool(
        operator_gate
        and operator_gate.get("decision") == "approve"
        and operator_gate.get("agent_command")
    )


def run_has_external_evidence_watch_signal(
    run: dict[str, Any],
    *,
    legacy_external_evidence_classification_prefixes: tuple[str, ...],
) -> bool:
    """Return true only for explicit external-evidence watch state."""

    waiting_on = str(run.get("waiting_on") or "").strip()
    execution_waiting_on = str(run.get("execution_waiting_on") or "").strip()
    if waiting_on == "external_evidence" or execution_waiting_on == "external_evidence":
        return True
    if isinstance(run.get("external_evidence_observation"), dict):
        return True
    monitor_event = run.get("monitor_event")
    if isinstance(monitor_event, dict):
        event_waiting_on = str(monitor_event.get("waiting_on") or "").strip()
        monitor_mode = str(monitor_event.get("monitor_mode") or "").strip()
        monitor_kind = str(monitor_event.get("monitor_kind") or "").strip()
        if event_waiting_on == "external_evidence":
            return True
        if monitor_mode.startswith("external_") or monitor_kind == "external_evidence":
            return True
    classification = str(run.get("classification") or "")
    return classification.startswith(legacy_external_evidence_classification_prefixes)


def is_custom_post_handoff_work_run(
    run: dict[str, Any],
    *,
    is_status_neutral_run: Callable[[dict[str, Any]], bool],
    is_handoff_ready_run: Callable[[dict[str, Any]], bool],
    run_has_external_evidence_watch_signal: Callable[[dict[str, Any]], bool],
    codex_ready_classifications: set[str],
    user_or_controller_classifications: set[str],
    blocking_classifications: set[str],
) -> bool:
    classification = str(run.get("classification") or "")
    if not classification:
        return False
    if is_status_neutral_run(run) or is_handoff_ready_run(run):
        return False
    if classification in codex_ready_classifications:
        return False
    if classification in user_or_controller_classifications or classification in blocking_classifications:
        return False
    if run_has_external_evidence_watch_signal(run):
        return False
    return True
