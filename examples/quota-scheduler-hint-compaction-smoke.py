#!/usr/bin/env python3
"""Smoke-test the compact quota scheduler_hint hot-path contract."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.policies.scheduler_hint import build_scheduler_hint  # noqa: E402
from loopx.quota import _scheduler_hint  # noqa: E402


def payload(*, should_run: bool, recommended_mode: str = "", user_required: bool = False) -> dict:
    return {
        "goal_id": "quota-scheduler-compaction",
        "should_run": should_run,
        "effective_action": "operator_gate_notify" if user_required else "normal_run",
        "recommended_action": "Keep scheduler hints compact on the hot path.",
        "heartbeat_recommendation": {
            "recommended_mode": recommended_mode,
            "notify": "NOTIFY" if user_required else "DONT_NOTIFY",
            "spend_policy": "spend only after validated writeback",
        },
        "execution_obligation": {
            "must_attempt_work": should_run,
            "spend_policy": "execution obligation spend policy",
        },
        "automation_liveness": {
            "automation_action": "",
            "spend_policy": "automation liveness spend policy",
        },
        "interaction_contract": {
            "mode": recommended_mode or "normal_run",
            "user_channel": {
                "action_required": user_required,
            },
        },
    }


def json_size(value: dict) -> int:
    return len(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def assert_compact_scheduler(name: str, source_payload: dict) -> None:
    compact = build_scheduler_hint(deepcopy(source_payload), user_action_required=False)
    wrapper = _scheduler_hint(deepcopy(source_payload))
    detailed = build_scheduler_hint(
        deepcopy(source_payload),
        user_action_required=False,
        include_detail=True,
    )

    assert compact == wrapper, (name, compact, wrapper)
    assert compact["schema_version"] == "scheduler_hint_v0", (name, compact)
    assert "local_scheduler" not in compact, (name, compact)
    assert "codex_cli_tui" not in compact, (name, compact)
    assert "claude_code_loop" not in compact, (name, compact)
    assert "cold_path_detail" not in compact, (name, compact)
    assert compact["detail_ref"]["omitted_by_default"] is True, (name, compact)
    assert compact["detail_ref"]["request"] == "loopx quota should-run --include-scheduler-detail", (name, compact)
    assert compact["reset_policy"]["reset_token"], (name, compact)
    assert compact["reset_policy"]["codex_app_initial_rrule"] == compact["codex_app"]["recommended_rrule"], (
        name,
        compact,
    )
    assert "identity_snapshot" not in compact["reset_policy"], (name, compact)
    assert "profile_snapshot" not in compact["reset_policy"], (name, compact)

    unchanged_poll = compact["unchanged_poll"]
    assert isinstance(unchanged_poll["limits"], dict), (name, compact)
    assert isinstance(unchanged_poll["after_limits"], dict), (name, compact)
    assert "final_quota_replan_check" not in unchanged_poll, (name, compact)

    cold_path = detailed["cold_path_detail"]
    assert cold_path["schema_version"] == "scheduler_hint_detail_v0", (name, detailed)
    assert cold_path["local_scheduler"]["recommended_interval_minutes"], (name, detailed)
    assert cold_path["codex_cli_tui"]["final_quota_replan_check"], (name, detailed)
    assert cold_path["claude_code_loop"]["after_limit"], (name, detailed)
    assert json_size(compact) < json_size(detailed), (name, json_size(compact), json_size(detailed))
    assert json_size(compact) <= 2_800, (name, json_size(compact))


def main() -> int:
    assert_compact_scheduler("active-work", payload(should_run=True))
    assert_compact_scheduler(
        "human-gate",
        payload(should_run=False, recommended_mode="ask_operator_gate", user_required=True),
    )
    print("quota-scheduler-hint-compaction-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
