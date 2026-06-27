from __future__ import annotations

import hashlib
import json
from collections.abc import Collection
from typing import Any


SCHEDULER_HINT_SCHEMA_VERSION = "scheduler_hint_v0"
SCHEDULER_RESET_POLICY_SCHEMA_VERSION = "scheduler_reset_policy_v0"
SCHEDULER_HINT_DETAIL_SCHEMA_VERSION = "scheduler_hint_detail_v0"


def build_scheduler_hint(
    payload: dict[str, Any],
    *,
    user_action_required: bool = False,
    agent_scope_frontier_actions: Collection[str] = (),
    include_detail: bool = False,
) -> dict[str, Any]:
    """Project host-runtime cadence/backoff policy from a quota decision.

    This helper is intentionally pure: callers provide the few quota-local
    classification facts it needs, and it returns the public scheduler contract
    without reading files, mutating state, or depending on the full quota module.
    """

    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    automation_liveness = (
        payload.get("automation_liveness")
        if isinstance(payload.get("automation_liveness"), dict)
        else {}
    )
    interaction_contract = (
        payload.get("interaction_contract")
        if isinstance(payload.get("interaction_contract"), dict)
        else {}
    )
    user_channel = (
        interaction_contract.get("user_channel")
        if isinstance(interaction_contract.get("user_channel"), dict)
        else {}
    )
    effective_action = str(payload.get("effective_action") or "")
    recommended_mode = str(heartbeat_recommendation.get("recommended_mode") or "")
    must_attempt_work = bool(execution_obligation.get("must_attempt_work"))
    user_required = user_action_required or bool(user_channel.get("action_required"))
    automation_action = str(automation_liveness.get("automation_action") or "")
    spend_policy = (
        automation_liveness.get("spend_policy")
        or execution_obligation.get("spend_policy")
        or heartbeat_recommendation.get("spend_policy")
    )
    identity_keys = [
        "goal_id",
        "agent_identity.agent_id",
        "effective_action",
        "heartbeat_recommendation.recommended_mode",
        "interaction_contract.mode",
        "recommended_action",
    ]
    agent_scope_action_set = {str(value) for value in agent_scope_frontier_actions}

    def identity_value(path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def hint(
        *,
        action: str,
        cadence_class: str,
        reason: str,
        codex_interval: int,
        codex_max: int,
        cli_limit: int | None,
        claude_limit: int | None,
        multiplier: int = 2,
        cadence_progression_override: list[int] | None = None,
    ) -> dict[str, Any]:
        cadence_progression = cadence_progression_override or [
            min(codex_interval * (multiplier**step), codex_max)
            for step in range(3)
        ]
        final_replan_check = {
            "enabled": cli_limit is not None or claude_limit is not None,
            "trigger": "before_unchanged_poll_after_limit",
            "action": "rerun_quota_should_run_once",
            "if_changed": "follow_new_scheduler_hint",
            "if_run_now": "execute_new_quota_contract",
            "if_unchanged": "apply_after_limit_without_spend",
            "spend_policy": "no quota spend for final replan check or loop stop",
        }
        identity_snapshot = {key: identity_value(key) for key in identity_keys}
        codex_rrule = f"FREQ=MINUTELY;INTERVAL={codex_interval}"
        profile_snapshot = {
            "cadence_class": cadence_class,
            "codex_app_initial_interval_minutes": codex_interval,
            "codex_app_initial_rrule": codex_rrule,
            "codex_app_max_interval_minutes": codex_max,
            "unchanged_poll_backoff_multiplier": multiplier,
            "local_scheduler_unchanged_poll_limit": cli_limit,
            "claude_code_loop_unchanged_poll_limit": claude_limit,
        }
        reset_token_payload = {
            "action": action,
            "identity_snapshot": identity_snapshot,
            "profile_snapshot": profile_snapshot,
        }
        reset_token = hashlib.sha256(
            json.dumps(
                reset_token_payload,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        identity_signature = hashlib.sha256(
            json.dumps(
                identity_snapshot,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:12]
        profile_signature = hashlib.sha256(
            json.dumps(
                profile_snapshot,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:12]
        reset_policy = {
            "schema_version": SCHEDULER_RESET_POLICY_SCHEMA_VERSION,
            "source": "quota.should-run",
            "reset_to": "profile_initial_interval",
            "profile_action": action,
            "reset_token": reset_token,
            "host_state_key": "scheduler_hint.reset_policy.reset_token",
            "codex_app_initial_interval_minutes": codex_interval,
            "codex_app_initial_rrule": codex_rrule,
            "local_scheduler_initial_interval_minutes": codex_interval,
            "clear_unchanged_poll_state": True,
            "identity_key_count": len(identity_keys),
            "identity_signature": identity_signature,
            "profile_signature": profile_signature,
            "reset_condition_summary": "token_changed|user_feedback|new_or_reassigned_todo|gate_or_material_transition|active_work_projected",
            "after_reset": "apply_initial_interval_before_backoff",
            "codex_app_apply": "update_rrule_to_initial_and_clear_unchanged_state_on_token_change",
            "no_spend_for_reset": True,
        }
        local_scheduler = {
            "recommended_interval_minutes": codex_interval,
            "max_interval_minutes": codex_max,
            "unchanged_poll_backoff_multiplier": multiplier,
            "example_progression_minutes": cadence_progression,
            "unchanged_poll_limit": cli_limit,
            "after_limit": "stop_tick_loop" if cli_limit is not None else "continue",
            "final_quota_replan_check": final_replan_check,
            "no_spend_for_cadence_change": True,
        }
        codex_cli_tui = {
            "unchanged_poll_limit": cli_limit,
            "after_limit": "exit_goal_loop" if cli_limit is not None else "continue",
            "final_quota_replan_check": final_replan_check,
            "no_spend_for_exit": True,
        }
        claude_code_loop = {
            "unchanged_poll_limit": claude_limit,
            "after_limit": "stop_loop" if claude_limit is not None else "continue",
            "final_quota_replan_check": final_replan_check,
            "no_spend_for_stop": True,
        }
        scheduler_hint = {
            "schema_version": SCHEDULER_HINT_SCHEMA_VERSION,
            "source": "quota.should-run",
            "action": action,
            "cadence_class": cadence_class,
            "reason": reason,
            "spend_policy": spend_policy,
            "codex_app": {
                "recommended_interval_minutes": codex_interval,
                "recommended_rrule": codex_rrule,
                "max_interval_minutes": codex_max,
                "unchanged_poll_backoff_multiplier": multiplier,
                "example_progression_minutes": cadence_progression,
                "apply": "update_automation_cadence_if_possible",
                "no_spend_for_cadence_change": True,
            },
            "unchanged_poll": {
                "limits": {
                    "local_scheduler": cli_limit,
                    "codex_cli_tui": cli_limit,
                    "claude_code_loop": claude_limit,
                },
                "after_limits": {
                    "local_scheduler": local_scheduler["after_limit"],
                    "codex_cli_tui": codex_cli_tui["after_limit"],
                    "claude_code_loop": claude_code_loop["after_limit"],
                },
                "final_quota_replan_check_enabled": final_replan_check["enabled"],
                "final_quota_replan_check_action": (
                    final_replan_check["action"] if final_replan_check["enabled"] else None
                ),
                "spend_policy": final_replan_check["spend_policy"],
            },
            "unchanged_identity_keys": identity_keys,
            "reset_policy": reset_policy,
            "detail_ref": {
                "schema_version": SCHEDULER_HINT_DETAIL_SCHEMA_VERSION,
                "omitted_by_default": True,
                "request": "loopx quota should-run --include-scheduler-detail",
                "contains": [
                    "local_scheduler",
                    "codex_cli_tui",
                    "claude_code_loop",
                    "final_quota_replan_check",
                ],
            },
        }
        if include_detail:
            scheduler_hint["cold_path_detail"] = {
                "schema_version": SCHEDULER_HINT_DETAIL_SCHEMA_VERSION,
                "source": "quota.should-run",
                "local_scheduler": local_scheduler,
                "codex_cli_tui": codex_cli_tui,
                "claude_code_loop": claude_code_loop,
                "final_quota_replan_check": final_replan_check,
            }
        return scheduler_hint

    if (
        recommended_mode in {"mapped_noop_if_unchanged", "post_handoff_observe_if_unchanged"}
        or heartbeat_recommendation.get("stop_if_unchanged")
        or automation_action == "keep_active_noop_if_unchanged"
    ):
        return hint(
            action="backoff_until_fresh_evidence",
            cadence_class="unchanged_noop",
            reason=(
                "the current mapped or post-handoff source is unchanged; do not "
                "keep a tight loop while waiting for fresh evidence or a concrete handoff"
            ),
            codex_interval=60,
            codex_max=240,
            cli_limit=3,
            claude_limit=3,
        )

    if (
        payload.get("should_run") is True
        or must_attempt_work
        or automation_action
        in {
            "execute_bounded_work",
            "repair_automation_prompt_identity",
        }
    ):
        return hint(
            action="run_now",
            cadence_class="active_work",
            reason=(
                "quota projects runnable work or a required repair; keep the active "
                "scheduler cadence until the turn validates or blocks"
            ),
            codex_interval=3,
            codex_max=10,
            cli_limit=None,
            claude_limit=None,
        )

    if user_required or recommended_mode in {"ask_operator_gate", "blocker_push_notify"}:
        return hint(
            action="backoff_waiting_for_user",
            cadence_class="human_gate",
            reason=(
                "user/controller action is the next unlock; after surfacing the "
                "concrete todo or gate, external loops should stop repeating the "
                "same quiet poll"
            ),
            codex_interval=30,
            codex_max=120,
            cli_limit=3,
            claude_limit=3,
        )

    if effective_action in agent_scope_action_set:
        return hint(
            action="backoff_until_reassigned",
            cadence_class="agent_scope_wait",
            reason=(
                "this registered agent has no in-scope advancement candidate; "
                "agent-to-agent handoffs may change quickly, so stay closer to "
                "the prior scheduler cadence while waiting for handoff owner "
                "progress, reassignment, or a current-agent todo"
            ),
            codex_interval=10,
            codex_max=60,
            cli_limit=3,
            claude_limit=3,
            cadence_progression_override=[10, 20, 30, 60],
        )

    if (
        effective_action == "monitor_quiet_skip"
        or recommended_mode == "monitor_quiet_until_material_transition"
    ):
        return hint(
            action="backoff_until_material_transition",
            cadence_class="monitor_wait",
            reason=(
                "monitor-only quiet polls should remain alive but use a slower "
                "cadence until material evidence, a blocker, or replan obligation appears"
            ),
            codex_interval=15,
            codex_max=60,
            cli_limit=3,
            claude_limit=3,
        )

    if payload.get("should_run") is False:
        return hint(
            action="backoff_until_state_change",
            cadence_class="quiet_wait",
            reason=(
                "quota blocks delivery and no immediate user/monitor-specific path "
                "is projected; poll at a slower cadence until the status changes"
            ),
            codex_interval=30,
            codex_max=120,
            cli_limit=3,
            claude_limit=3,
        )

    return hint(
        action="keep_default_cadence",
        cadence_class="default",
        reason="no scheduler backoff condition is projected",
        codex_interval=3,
        codex_max=30,
        cli_limit=None,
        claude_limit=None,
    )
