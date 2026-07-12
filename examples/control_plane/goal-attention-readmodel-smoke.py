#!/usr/bin/env python3
"""Smoke-test goal attention routing read-model parity."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.work_items import attention_routing as routing_read_model  # noqa: E402
from loopx.session_runtime import SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION  # noqa: E402


def direct_goal_attention(goal: dict) -> dict | None:
    return routing_read_model.goal_attention(
        goal,
        latest_run=status_module.latest_run,
        readiness_attention_fields=status_module.readiness_attention_fields,
        operator_gate_attention_fields=status_module.operator_gate_attention_fields,
        dreaming_attention_fields=status_module.dreaming_attention_fields,
        goal_lifecycle_fields=status_module.goal_lifecycle_fields,
        legacy_runtime_goal_attention=status_module.legacy_runtime_goal_attention,
        compact_session_runtime_projection_from_run=status_module.compact_session_runtime_projection_from_run,
        public_safe_compact_text=status_module.public_safe_compact_text,
        attention_item=status_module.attention_item,
        run_has_external_evidence_watch_signal=status_module.run_has_external_evidence_watch_signal,
        default_operator_question=status_module.default_operator_question,
        normalize_operator_question=status_module.normalize_operator_question,
        monitor_signal_waiting_on=status_module.MONITOR_SIGNAL_WAITING_ON,
        default_operator_gate=status_module.DEFAULT_OPERATOR_GATE,
        planned_controller_opt_in_recommended_action=status_module.PLANNED_CONTROLLER_OPT_IN_RECOMMENDED_ACTION,
        connected_adapter_statuses=status_module.CONNECTED_ADAPTER_STATUSES,
        connected_delivery_adapter_statuses=status_module.CONNECTED_DELIVERY_ADAPTER_STATUSES,
        registry_waiting_on_overrides=status_module.REGISTRY_WAITING_ON_OVERRIDES,
        blocking_classifications=status_module.BLOCKING_CLASSIFICATIONS,
        user_or_controller_classifications=status_module.USER_OR_CONTROLLER_CLASSIFICATIONS,
        codex_ready_classifications=status_module.CODEX_READY_CLASSIFICATIONS,
    )


def assert_parity(goal: dict) -> dict | None:
    wrapper = status_module.goal_attention(goal)
    direct = direct_goal_attention(goal)
    assert wrapper == direct, (wrapper, direct)
    return wrapper


def run(
    classification: str,
    *,
    recommended_action: str = "continue bounded delivery",
    json_exists: bool = True,
    markdown_exists: bool = True,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "generated_at": "2026-07-04T00:00:00+00:00",
        "classification": classification,
        "recommended_action": recommended_action,
        "json_exists": json_exists,
        "markdown_exists": markdown_exists,
    }
    payload.update(extra)
    return payload


def goal(**extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "goal-attention-smoke",
        "status": "active",
        "registry_member": True,
    }
    payload.update(extra)
    return payload


def assert_routed(goal_payload: dict, *, status: str, waiting_on: str, severity: str) -> dict:
    item = assert_parity(goal_payload)
    assert item is not None, goal_payload
    assert item["status"] == status, item
    assert item["waiting_on"] == waiting_on, item
    assert item["severity"] == severity, item
    return item


def main() -> int:
    connected = assert_routed(
        goal(adapter_status="connected-read-only"),
        status="connected_without_run",
        waiting_on="codex",
        severity="action",
    )
    assert connected["source"] == "run_history", connected

    connected_delivery = assert_routed(
        goal(adapter_status="connected-delivery"),
        status="connected_without_run",
        waiting_on="codex",
        severity="action",
    )
    assert connected_delivery["source"] == "run_history", connected_delivery

    planned = assert_routed(
        goal(adapter_status="planned", adapter_kind="demo_read_only_map_v0"),
        status="active",
        waiting_on="user_or_controller",
        severity="action",
    )
    assert planned["agent_command"] == "loopx read-only-map --goal-id goal-attention-smoke --dry-run", planned

    missing_artifact = assert_routed(
        goal(latest_status_run=run("state_refreshed", markdown_exists=False)),
        status="run_artifact_missing",
        waiting_on="codex",
        severity="high",
    )
    assert missing_artifact["source"] == "run_history", missing_artifact

    registry_override = assert_routed(
        goal(
            waiting_on="external_evidence",
            attention_status="waiting_for_remote",
            recommended_action="observe remote public signal",
            operator_question="Proceed?",
            operator_gate="publish",
            next_handoff_condition="after external signal",
            latest_status_run=run("state_refreshed"),
        ),
        status="waiting_for_remote",
        waiting_on="external_evidence",
        severity="watch",
    )
    assert registry_override["source"] == "registry", registry_override
    assert registry_override["next_handoff_condition"] == "after external signal", registry_override

    assert_routed(
        goal(latest_status_run=run("blocked_by_safety")),
        status="blocked_by_safety",
        waiting_on="user_or_controller",
        severity="high",
    )

    assert_routed(
        goal(latest_status_run=run("ready_for_controller_opt_in")),
        status="ready_for_controller_opt_in",
        waiting_on="user_or_controller",
        severity="action",
    )

    assert_routed(
        goal(latest_status_run=run("state_refreshed")),
        status="state_refreshed",
        waiting_on="codex",
        severity="action",
    )

    external_signal = assert_routed(
        goal(
            latest_status_run=run(
                "runtime_result_pending",
                waiting_on="external_evidence",
            )
        ),
        status="runtime_result_pending",
        waiting_on="external_evidence",
        severity="watch",
    )
    assert external_signal["source"] == "latest_run", external_signal

    assert_routed(
        goal(adapter_status="connected-delivery", latest_status_run=run("custom_delivery")),
        status="custom_delivery",
        waiting_on="codex",
        severity="action",
    )

    session_runtime = assert_routed(
        goal(
            latest_status_run=run(
                "runtime_result_pending",
                session_runtime_projection={
                    "schema_version": SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION,
                    "goal_id": "goal-attention-smoke",
                    "first_screen": {
                        "recommended_action": "continue from session runtime",
                        "agent_can_continue": True,
                    },
                    "work_lane_contract": {
                        "lane": "advancement_task",
                        "must_attempt_work": True,
                    },
                },
            )
        ),
        status="session_runtime_advancement_task",
        waiting_on="codex",
        severity="action",
    )
    assert session_runtime["source"] == "session_runtime_projection", session_runtime

    assert assert_parity(goal(adapter_status="planned", latest_status_run=run("custom_idle"))) is None

    print("goal-attention-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
