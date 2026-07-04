#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import handoff_runs as handoff_run_read_model  # noqa: E402


def _projection_is_handoff_ready(run: dict[str, object]) -> bool:
    return handoff_run_read_model.is_handoff_ready_run(
        run,
        handoff_ready_classifications=status_module.HANDOFF_READY_CLASSIFICATIONS,
        compact_operator_gate=status_module.compact_operator_gate,
    )


def _projection_has_external_evidence(run: dict[str, object]) -> bool:
    return handoff_run_read_model.run_has_external_evidence_watch_signal(
        run,
        legacy_external_evidence_classification_prefixes=(
            status_module.LEGACY_EXTERNAL_EVIDENCE_CLASSIFICATION_PREFIXES
        ),
    )


def _projection_is_custom_post_handoff(run: dict[str, object]) -> bool:
    return handoff_run_read_model.is_custom_post_handoff_work_run(
        run,
        is_status_neutral_run=status_module.is_status_neutral_run,
        is_handoff_ready_run=status_module.is_handoff_ready_run,
        run_has_external_evidence_watch_signal=status_module.run_has_external_evidence_watch_signal,
        codex_ready_classifications=status_module.CODEX_READY_CLASSIFICATIONS,
        user_or_controller_classifications=status_module.USER_OR_CONTROLLER_CLASSIFICATIONS,
        blocking_classifications=status_module.BLOCKING_CLASSIFICATIONS,
    )


def assert_handoff_run_wrapper_parity() -> None:
    cases = [
        {"classification": next(iter(status_module.HANDOFF_READY_CLASSIFICATIONS))},
        {
            "classification": "operator_gate_approved",
            "operator_gate": {"decision": "approve", "agent_command": "continue"},
        },
        {"classification": "feature_monitoring_not_external"},
        {"classification": "research_progress_written"},
        {"classification": next(iter(status_module.CODEX_READY_CLASSIFICATIONS))},
        {"classification": next(iter(status_module.USER_OR_CONTROLLER_CLASSIFICATIONS))},
        {"classification": next(iter(status_module.BLOCKING_CLASSIFICATIONS))},
        {"classification": "custom_delivery", "waiting_on": "external_evidence"},
        {
            "classification": "custom_delivery",
            "monitor_event": {"monitor_mode": "external_signal_watch"},
        },
        {
            "classification": (
                f"{status_module.LEGACY_EXTERNAL_EVIDENCE_CLASSIFICATION_PREFIXES[0]}fixture"
            ),
        },
        {"classification": "quota_monitor_poll"},
        {},
    ]

    for run in cases:
        assert status_module.is_handoff_ready_run(run) == _projection_is_handoff_ready(run), run
        assert status_module.run_has_external_evidence_watch_signal(run) == _projection_has_external_evidence(
            run
        ), run
        assert status_module.is_custom_post_handoff_work_run(run) == _projection_is_custom_post_handoff(run), run


def main() -> None:
    assert_handoff_run_wrapper_parity()


if __name__ == "__main__":
    main()
