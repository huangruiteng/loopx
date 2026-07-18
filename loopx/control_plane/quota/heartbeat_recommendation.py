from __future__ import annotations

from typing import Any

from .. import compact_control_plane_policy
from ..goals.goal_frontier import (
    build_autonomous_replan_recommendation,
    select_autonomous_replan_obligation,
)
from ..work_items.delivery_outcome import DeliveryOutcome, normalize_delivery_outcome
from ..work_items.work_lane_context import (
    build_work_lane_context_contract,
    latest_run_progress_scope,
)
from ..todos.user_gate import open_todo_count as _open_todo_count


HEARTBEAT_READ_ONLY_MAP_ADAPTER_SUFFIX = "_read_only_map_v0"
HEARTBEAT_HANDOFF_READINESS_COMPACT_FIELDS = (
    "ready",
    "codex_ready",
    "source",
    "quota_state",
    "handoff_status",
    "post_handoff_run_seen",
    "post_handoff_small_scale_streak",
    "post_handoff_outcome_gap_streak",
    "handoff_interface_budget",
)
HEARTBEAT_POST_HANDOFF_RUN_COMPACT_FIELDS = (
    "generated_at",
    "classification",
    "progress_scope",
    "delivery_batch_scale",
    "delivery_outcome",
    "delivery_turn_kind",
    "health_check",
    "json_exists",
    "markdown_exists",
)


def open_todo_notify_reason(*, state: str, waiting_on: str) -> str:
    if state == "focus_wait":
        return "open user todo can unblock focus_wait after owner evidence, external eval, or a clean baseline changes"
    if waiting_on == "external_evidence":
        return "open user todo can provide or defer the external-evidence checkpoint"
    if waiting_on in {"user_or_controller", "controller"}:
        return "open user todo can resolve the user/controller blocker"
    return "open user todo can resolve the current waiting lane"


def _supports_read_only_project_map(adapter_kind: Any) -> bool:
    kind = str(adapter_kind or "").strip()
    return kind == "read_only_project_map_v0" or kind.endswith(
        HEARTBEAT_READ_ONLY_MAP_ADAPTER_SUFFIX
    )


def _text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return [str(value)]


def _has_lifecycle_marker(*values: Any, marker: str) -> bool:
    target = marker.strip().lower()
    for value in values:
        for text in _text_values(value):
            if text.strip().lower() == target:
                return True
    return False


def _compact_latest_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run.get(key)
        for key in HEARTBEAT_POST_HANDOFF_RUN_COMPACT_FIELDS
        if run.get(key) is not None
    }


def _control_plane_post_handoff_observation_hint(item: dict[str, Any]) -> dict[str, Any] | None:
    control_plane = compact_control_plane_policy(item.get("control_plane"))
    self_repair = (
        control_plane.get("self_repair")
        if isinstance(control_plane.get("self_repair"), dict)
        else {}
    )
    if self_repair.get("enabled") is not True:
        return None
    if str(item.get("adapter_kind") or "") != "harness_self_improvement":
        return None
    if item.get("agent_command"):
        return None

    handoff_readiness = (
        item.get("handoff_readiness")
        if isinstance(item.get("handoff_readiness"), dict)
        else {}
    )
    latest_run = (
        handoff_readiness.get("post_handoff_latest_run")
        if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
        else {}
    )
    if handoff_readiness.get("post_handoff_run_seen") is not True:
        return None
    if str(handoff_readiness.get("handoff_status") or "") != "post_handoff_run_seen":
        return None
    if normalize_delivery_outcome(latest_run.get("delivery_outcome")) != DeliveryOutcome.PRIMARY_GOAL_OUTCOME:
        return None

    return {
        "source": "quota.should-run",
        "recommended_mode": "post_handoff_observe_if_unchanged",
        "stop_if_unchanged": True,
        "notify": "DONT_NOTIFY",
        "reason": (
            "control-plane self-repair is enabled and the latest post-handoff "
            "implementation run already reached the primary outcome; inspect "
            "registry/status/run history/repo state, then stay quiet if no new "
            "evidence or concrete safe work is found"
        ),
        "spend_policy": (
            "do not append quota spend for an unchanged post-handoff observation; "
            "spend only after a new validated artifact, repair, or durable state "
            "writeback advances the control-plane contract"
        ),
        "latest_run": _compact_latest_run(latest_run),
    }


def build_heartbeat_recommendation(
    item: dict[str, Any],
    *,
    goal_id: str,
    state: str,
    should_run: bool,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None = None,
    stall_self_repair: dict[str, Any] | None = None,
    replan_obligation: dict[str, Any] | None = None,
    select_replan_obligation: bool = True,
    monitor_due_item_limit: int = 1,
) -> dict[str, Any]:
    status = str(item.get("status") or "")
    waiting_on = str(item.get("waiting_on") or "")
    adapter_kind = str(item.get("adapter_kind") or "")
    lifecycle_phase = item.get("lifecycle_phase")
    lifecycle_flags = item.get("lifecycle_flags")
    quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    replan_obligation = (
        replan_obligation
        if isinstance(replan_obligation, dict)
        else select_autonomous_replan_obligation(item, project_asset)
        if select_replan_obligation
        else None
    )
    has_user_todos = _open_todo_count(user_todo_summary) > 0
    has_agent_todos = _open_todo_count(agent_todo_summary) > 0
    work_lane_contract = work_lane_contract or build_work_lane_context_contract(
        item,
        agent_todo_summary=agent_todo_summary,
        monitor_due_item_limit=monitor_due_item_limit,
    )

    base: dict[str, Any] = {
        "source": "quota.should-run",
        "recommended_mode": "skip",
        "notify": "DONT_NOTIFY",
        "spend_policy": "do not append quota spend unless a completed bounded progress segment produced substantive progress",
    }

    if (
        stall_self_repair
        and stall_self_repair.get("allowed")
        and (
            state != "operator_gate"
            or stall_self_repair.get("trigger") == "user_gate_scope_projection_drift"
        )
    ):
        return {
            **base,
            "recommended_mode": stall_self_repair.get("recommended_mode") or "repair_control_plane_stall",
            "notify": stall_self_repair.get("notify") or "DONT_NOTIFY",
            "spend_policy": stall_self_repair.get("spend_policy") or base["spend_policy"],
            "reason": stall_self_repair.get("reason") or "control-plane stall requires bounded repair",
            "repair_focus": stall_self_repair.get("repair_focus"),
        }
    if state == "operator_gate":
        return {
            **base,
            "recommended_mode": "ask_operator_gate",
            "notify": "NOTIFY",
            "spend_policy": "do not append quota spend while asking the operator gate",
            "reason": "operator gate blocks the gated delivery path",
        }
    if should_run and replan_obligation and replan_obligation.get("required"):
        return {
            **base,
            **build_autonomous_replan_recommendation(replan_obligation),
        }
    if state in {"focus_wait", "waiting"} and has_user_todos:
        return {
            **base,
            "recommended_mode": "blocker_push_notify",
            "notify": "NOTIFY",
            "repeat_notification_required": True,
            "spend_policy": "do not append quota spend for the blocker-push turn",
            "reason": open_todo_notify_reason(state=state, waiting_on=waiting_on),
        }
    if state == "focus_wait" and quota.get("handoff_outcome_floor_block"):
        if quota.get("outcome_floor_blocker_projected"):
            return {
                **base,
                "recommended_mode": "outcome_floor_blocker_projected_noop",
                "notify": "DONT_NOTIFY",
                "spend_policy": (
                    "do not append quota spend while the same concrete outcome-floor "
                    "blocker is already projected and no executable agent todo exists"
                ),
                "reason": str(
                    quota.get("reason")
                    or "outcome-floor blocker is already projected; wait for fresh outcome evidence"
                ),
            }
        if quota.get("safe_bypass_allowed"):
            return {
                **base,
                "recommended_mode": "outcome_floor_recovery",
                "notify": "DONT_NOTIFY",
                "spend_policy": (
                    "append exactly one quota spend only after a validated "
                    "ranker/cross-domain evidence artifact or concrete blocker writeback; "
                    "do not spend for another surface-only report"
                ),
                "reason": str(quota.get("reason") or "handoff outcome floor is not met"),
            }
        return {
            **base,
            "recommended_mode": "report_handoff_outcome_blocker",
            "notify": "NOTIFY",
            "spend_policy": "do not append quota spend while reporting the handoff outcome-floor blocker",
            "reason": str(quota.get("reason") or "handoff outcome floor is not met"),
        }
    if not should_run:
        return {
            **base,
            "recommended_mode": "quota_skip",
            "reason": f"quota state is {state}; skip delivery compute",
        }

    if item.get("agent_command"):
        return {
            **base,
            "recommended_mode": "run_agent_command",
            "command": str(item.get("agent_command")),
            "notify": "DONT_NOTIFY",
            "spend_policy": "append exactly one heartbeat spend after the command completes and validation/writeback are saved",
            "reason": "current status exposes an approved project-agent command",
        }

    if (
        work_lane_contract
        and work_lane_contract.get("lane") == "continuous_monitor"
        and work_lane_contract.get("must_attempt_work") is False
        and has_user_todos
    ):
        return {
            **base,
            "recommended_mode": "monitor_quiet_until_material_transition",
            "spend_policy": (
                "do not append quota spend or repeat a blocker notification for a "
                "monitor-only poll; keep the open user todo visible in the payload and "
                "wait for a material monitor transition"
            ),
            "reason": (
                "monitor-only polling has no material transition to write back; the "
                "current open user todo is already part of the durable active state"
            ),
        }

    if (
        work_lane_contract
        and work_lane_contract.get("lane") == "continuous_monitor"
        and work_lane_contract.get("must_attempt_work") is False
        and not has_user_todos
    ):
        return {
            **base,
            "recommended_mode": "monitor_quiet_until_material_transition",
            "spend_policy": (
                "do not append quota spend until a material monitor transition, regression, "
                "or concrete blocker is validated and written back"
            ),
            "reason": "all visible open agent todos are monitor-class work with no material transition to record",
        }

    if (
        work_lane_contract
        and work_lane_contract.get("lane") == "continuous_monitor"
        and work_lane_contract.get("must_attempt_work") is True
        and not has_user_todos
    ):
        latest_run: dict[str, Any] = {}
        handoff_readiness = (
            item.get("handoff_readiness")
            if isinstance(item.get("handoff_readiness"), dict)
            else {}
        )
        latest_handoff_run = (
            handoff_readiness.get("post_handoff_latest_run")
            if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
            else {}
        )
        if latest_handoff_run:
            latest_run = _compact_latest_run(latest_handoff_run)
            latest_run["progress_scope"] = latest_run_progress_scope(latest_handoff_run)
        payload = {
            **base,
            "recommended_mode": "follow_work_lane_contract",
            "spend_policy": (
                "follow work_lane_contract.obligation; spend only after validated "
                "advancement, concrete blocker writeback, or a material monitor transition"
            ),
            "reason": (
                "work_lane_contract is the machine contract for monitor-vs-advancement routing"
            ),
        }
        if latest_run:
            payload["latest_run"] = latest_run
        return payload

    if status == "connected_without_run" and _supports_read_only_project_map(adapter_kind):
        return {
            **base,
            "recommended_mode": "run_first_read_only_map",
            "command": f"loopx read-only-map --goal-id {goal_id}",
            "notify": "NOTIFY",
            "spend_policy": "append exactly one heartbeat spend after the read-only map run is saved and validated",
            "reason": "connected read-only project has no saved compact run yet",
        }

    mapped = (
        status == "read_only_project_map"
        or _has_lifecycle_marker(lifecycle_phase, lifecycle_flags, marker="mapped")
    )
    if mapped and not any([has_user_todos, has_agent_todos, item.get("agent_command")]):
        return {
            **base,
            "recommended_mode": "mapped_noop_if_unchanged",
            "stop_if_unchanged": True,
            "spend_policy": (
                "do not run another dry-run or append quota spend when the latest read-only map is still current "
                "and there is no new user instruction, owner evidence, agent todo, stale source, or safe handoff"
            ),
            "reason": "latest compact read-only map already exists; wait for new evidence or a concrete safe action",
        }

    post_handoff_observation = _control_plane_post_handoff_observation_hint(item)
    if post_handoff_observation and not has_user_todos:
        latest_observed_run = (
            post_handoff_observation.get("latest_run")
            if isinstance(post_handoff_observation.get("latest_run"), dict)
            else {}
        )
        progress_scope = latest_run_progress_scope(latest_observed_run)
        if isinstance(latest_observed_run, dict) and latest_observed_run:
            latest_observed_run.setdefault("progress_scope", progress_scope)
        if has_agent_todos and progress_scope == "dependency_observation":
            return {
                **base,
                **{
                    key: value
                    for key, value in post_handoff_observation.items()
                    if key != "stop_if_unchanged"
                },
                "recommended_mode": "follow_work_lane_contract",
                "spend_policy": (
                    "follow work_lane_contract.obligation; spend only after validated "
                    "advancement, concrete blocker writeback, or a material monitor transition"
                ),
                "reason": (
                    "latest post-handoff run was dependency observation; the work lane "
                    "contract decides whether to advance backlog or record a material transition"
                ),
            }
        if has_agent_todos:
            active_observation = {
                key: value
                for key, value in post_handoff_observation.items()
                if key != "stop_if_unchanged"
            }
            return {
                **base,
                **active_observation,
                "recommended_mode": "post_handoff_observe_then_backlog_step",
                "spend_policy": (
                    "observe registry/status/run history/repo state first; if unchanged, "
                    "advance exactly one bounded agent-todo backlog segment and append quota "
                    "spend only after validation and durable writeback"
                ),
                "reason": (
                    "latest post-handoff implementation reached the primary outcome, but "
                    "an open agent todo remains; observe for new blockers first, then "
                    "advance one bounded backlog step instead of quiet idling"
                ),
            }
        return {
            **base,
            **post_handoff_observation,
        }

    return {
        **base,
        "recommended_mode": "steering_audit_then_one_step",
        "spend_policy": "append exactly one heartbeat spend only after a bounded progress segment is validated and written back",
        "reason": "eligible Codex-ready goal requires the standard steering audit before delivery",
    }
