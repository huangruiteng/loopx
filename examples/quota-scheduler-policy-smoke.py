#!/usr/bin/env python3
"""Smoke-test the extracted quota scheduler policy helper."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.policies.scheduler_hint import build_scheduler_hint  # noqa: E402
from loopx.quota import AgentScopeFrontierAction, _scheduler_hint  # noqa: E402


AGENT_SCOPE_ACTIONS = [action.value for action in AgentScopeFrontierAction]


def payload(
    *,
    should_run: bool,
    effective_action: str,
    recommended_mode: str = "",
    automation_action: str = "",
    user_required: bool = False,
    stop_if_unchanged: bool = False,
) -> dict:
    return {
        "goal_id": "scheduler-policy-smoke",
        "should_run": should_run,
        "effective_action": effective_action,
        "recommended_action": "Run the scheduler policy smoke.",
        "heartbeat_recommendation": {
            "recommended_mode": recommended_mode,
            "notify": "DONT_NOTIFY",
            "spend_policy": "spend only after validated writeback",
            "stop_if_unchanged": stop_if_unchanged,
        },
        "execution_obligation": {
            "must_attempt_work": should_run,
            "spend_policy": "execution obligation spend policy",
        },
        "automation_liveness": {
            "automation_action": automation_action,
            "spend_policy": "automation liveness spend policy",
        },
        "interaction_contract": {
            "mode": recommended_mode or effective_action,
            "user_channel": {
                "action_required": user_required,
            },
        },
    }


def assert_policy_case(name: str, base_payload: dict, *, expected_action: str, expected_rrule: str) -> None:
    quota_wrapper = _scheduler_hint(deepcopy(base_payload))
    extracted = build_scheduler_hint(
        deepcopy(base_payload),
        user_action_required=bool(
            base_payload.get("interaction_contract", {})
            .get("user_channel", {})
            .get("action_required")
        ),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    detailed = build_scheduler_hint(
        deepcopy(base_payload),
        user_action_required=bool(
            base_payload.get("interaction_contract", {})
            .get("user_channel", {})
            .get("action_required")
        ),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        include_detail=True,
    )
    assert extracted == quota_wrapper, (name, extracted, quota_wrapper)
    assert extracted["schema_version"] == "scheduler_hint_v0", (name, extracted)
    assert extracted["source"] == "quota.should-run", (name, extracted)
    assert extracted["action"] == expected_action, (name, extracted)
    assert extracted["codex_app"]["recommended_rrule"] == expected_rrule, (name, extracted)
    assert extracted["codex_app"]["host_tool"] == "automation_update", (name, extracted)
    assert extracted["codex_app"]["host_action"] == "update_current_heartbeat_rrule", (name, extracted)
    assert extracted["codex_app"]["rrule_source"] == "scheduler_hint.codex_app.recommended_rrule", (
        name,
        extracted,
    )
    assert "local_scheduler" not in extracted, (name, extracted)
    assert "codex_cli_tui" not in extracted, (name, extracted)
    assert "claude_code_loop" not in extracted, (name, extracted)
    assert "cold_path_detail" not in extracted, (name, extracted)
    assert extracted["detail_ref"]["request"] == "loopx quota should-run --include-scheduler-detail", (name, extracted)
    assert detailed["cold_path_detail"]["local_scheduler"]["recommended_interval_minutes"], (name, detailed)
    assert detailed["cold_path_detail"]["codex_cli_tui"]["final_quota_replan_check"], (name, detailed)
    assert detailed["cold_path_detail"]["claude_code_loop"]["after_limit"], (name, detailed)
    reset = extracted["reset_policy"]
    assert reset["schema_version"] == "scheduler_reset_policy_v0", (name, reset)
    assert reset["codex_app_tool"] == "automation_update", (name, reset)
    assert "automation_update" in reset["codex_app_apply"], (name, reset)
    assert isinstance(reset["reset_token"], str) and len(reset["reset_token"]) == 16, (name, reset)
    assert len(reset["identity_signature"]) == 12, (name, reset)
    assert len(reset["profile_signature"]) == 12, (name, reset)
    assert "identity_snapshot" not in reset, (name, reset)
    assert "profile_snapshot" not in reset, (name, reset)


def main() -> int:
    assert_policy_case(
        "active-work",
        payload(should_run=True, effective_action="normal_run"),
        expected_action="run_now",
        expected_rrule="FREQ=MINUTELY;INTERVAL=3",
    )
    assert_policy_case(
        "mapped-noop",
        payload(
            should_run=True,
            effective_action="normal_run",
            recommended_mode="mapped_noop_if_unchanged",
            stop_if_unchanged=True,
        ),
        expected_action="backoff_until_fresh_evidence",
        expected_rrule="FREQ=MINUTELY;INTERVAL=60",
    )
    assert_policy_case(
        "human-gate",
        payload(
            should_run=False,
            effective_action="operator_gate_notify",
            recommended_mode="ask_operator_gate",
            user_required=True,
        ),
        expected_action="backoff_waiting_for_user",
        expected_rrule="FREQ=MINUTELY;INTERVAL=30",
    )
    assert_policy_case(
        "agent-scope-wait",
        payload(
            should_run=False,
            effective_action=AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
        ),
        expected_action="backoff_until_reassigned",
        expected_rrule="FREQ=MINUTELY;INTERVAL=10",
    )
    assert_policy_case(
        "monitor-wait",
        payload(
            should_run=False,
            effective_action="monitor_quiet_skip",
            recommended_mode="monitor_quiet_until_material_transition",
        ),
        expected_action="backoff_until_material_transition",
        expected_rrule="FREQ=MINUTELY;INTERVAL=15",
    )
    assert_policy_case(
        "quiet-wait",
        payload(should_run=False, effective_action="quota_skip"),
        expected_action="backoff_until_state_change",
        expected_rrule="FREQ=MINUTELY;INTERVAL=30",
    )
    print("ok: quota scheduler policy helper matches quota wrapper")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
