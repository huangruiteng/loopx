#!/usr/bin/env python3
"""Smoke-test CLI-owned scheduler RRULE ack state."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.policies.scheduler_hint import build_scheduler_hint  # noqa: E402
from loopx.quota import AgentScopeFrontierAction  # noqa: E402
from loopx.scheduler_state import SCHEDULER_STATE_SCHEMA_VERSION  # noqa: E402


AGENT_SCOPE_ACTIONS = [action.value for action in AgentScopeFrontierAction]


def _load_quota_plan_fixture_module():
    module_path = REPO_ROOT / "examples" / "quota-plan-smoke.py"
    spec = importlib.util.spec_from_file_location("quota_plan_smoke_fixture", module_path)
    assert spec and spec.loader, module_path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(*, recommended_action: str = "Wait for reassignment.") -> dict:
    return {
        "goal_id": "scheduler-state-ack-smoke",
        "agent_identity": {"agent_id": "codex-side-agent"},
        "should_run": False,
        "effective_action": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
        "recommended_action": recommended_action,
        "heartbeat_recommendation": {
            "recommended_mode": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "notify": "DONT_NOTIFY",
            "spend_policy": "no spend while waiting for reassignment",
        },
        "execution_obligation": {
            "must_attempt_work": False,
            "spend_policy": "do not spend",
        },
        "automation_liveness": {
            "automation_action": "",
            "spend_policy": "automation liveness spend policy",
        },
        "interaction_contract": {
            "mode": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "user_channel": {"action_required": False},
        },
    }


def state_from(hint: dict) -> dict:
    stateful = hint["codex_app"]["stateful_backoff"]
    return {
        "schema_version": SCHEDULER_STATE_SCHEMA_VERSION,
        "goal_id": "scheduler-state-ack-smoke",
        "agent_id": "codex-side-agent",
        "surface": "codex_app",
        "state_key": stateful["state_key"],
        "reset_token": stateful["reset_token"],
        "identity_signature": stateful["identity_signature"],
        "progression_index": stateful["progression_index"],
        "progression_minutes": stateful["progression_minutes"],
        "last_applied_rrule": hint["codex_app"]["recommended_rrule"],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def assert_policy_state_progression() -> None:
    base = payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    first_backoff = first["codex_app"]["stateful_backoff"]
    assert first["action"] == "backoff_until_reassigned", first
    assert first["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=10", first
    assert first_backoff["apply_needed"] is True, first
    assert first_backoff["state_status"] == "missing", first

    second = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(first),
    )
    assert second["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=20", second
    assert second["codex_app"]["stateful_backoff"]["progression_index"] == 1, second
    assert second["codex_app"]["stateful_backoff"]["state_status"] == "same_identity", second

    third = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(second),
    )
    assert third["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", third

    fourth = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(third),
    )
    assert fourth["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=60", fourth

    quiet = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(fourth),
    )
    assert quiet["codex_app"]["stateful_backoff"]["apply_needed"] is False, quiet
    assert quiet["codex_app"]["host_action"] == "none", quiet
    assert quiet["codex_app"]["rrule_source"] is None, quiet
    assert "recommended_rrule" not in quiet["codex_app"], quiet

    reset = build_scheduler_hint(
        payload(recommended_action="A new reassignment candidate appeared."),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(fourth),
    )
    assert reset["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=10", reset
    assert reset["codex_app"]["stateful_backoff"]["state_status"] == "reset_required", reset


def run_cli(root: Path, *args: str, registry_path: Path, runtime: Path, project: Path) -> dict:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        *args,
        "--scan-path",
        str(project),
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def assert_cli_scheduler_ack_progression() -> None:
    fixture = _load_quota_plan_fixture_module()
    with tempfile.TemporaryDirectory(prefix="loopx-quota-scheduler-ack-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        agent_id = fixture.SCOPED_AGENT_ID
        first = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        first_rrule = first["scheduler_hint"]["codex_app"]["recommended_rrule"]
        assert first["scheduler_hint"]["codex_app"]["stateful_backoff"]["apply_needed"] is True, first

        ack = run_cli(
            root,
            "quota",
            "scheduler-ack",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--applied-rrule",
            first_rrule,
            "--execute",
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        assert ack["ok"] is True, ack
        assert ack["appended"] is False, ack
        assert ack["scheduler_state_mutated"] is True, ack
        assert ack["scheduler_ack_event"]["scheduler_state"]["last_applied_rrule"] == first_rrule, ack
        assert Path(ack["scheduler_state_path"]).exists(), ack
        assert ack["after"] is None, ack
        assert ack["post_ack_contract"]["do_not_apply_successor_rrule_from_ack_response"] is True, ack

        second = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        second_app = second["scheduler_hint"]["codex_app"]
        assert second_app["stateful_backoff"]["state_status"] == "same_identity", second
        assert second_app["recommended_rrule"] != first_rrule, second
        assert second_app["stateful_backoff"]["apply_needed"] is True, second

        current = second
        while current["scheduler_hint"]["codex_app"]["stateful_backoff"]["apply_needed"]:
            current_rrule = current["scheduler_hint"]["codex_app"]["recommended_rrule"]
            ack = run_cli(
                root,
                "quota",
                "scheduler-ack",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                "--applied-rrule",
                current_rrule,
                "--execute",
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert ack["ok"] is True, ack
            current = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )

        final_app = current["scheduler_hint"]["codex_app"]
        assert final_app["stateful_backoff"]["apply_needed"] is False, current
        assert final_app["host_action"] == "none", current
        assert "recommended_rrule" not in final_app, current


def main() -> int:
    assert_policy_state_progression()
    assert_cli_scheduler_ack_progression()
    print("quota-scheduler-state-ack-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
