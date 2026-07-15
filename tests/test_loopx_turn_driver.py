from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from loopx.cli import main as cli_main
from loopx.control_plane.turn_driver import LoopXTurnRoute, build_loopx_turn_plan
from loopx.control_plane.quota.live_decision import bind_scheduler_followup_cli_routes


def _envelope(
    *,
    should_run: bool = True,
    effective_action: str = "normal_run",
    action_required: bool = False,
    quiet_noop_allowed: bool = False,
) -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "loopx_turn_envelope_v0",
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "should_run": should_run,
        "effective_action": effective_action,
        "action": {
            "must_attempt": should_run,
            "delivery_allowed": should_run,
            "quiet_noop_allowed": quiet_noop_allowed,
            "selected_todo": {
                "todo_id": "todo_fixture0001",
                "text": "Advance one public fixture",
            },
        },
        "user": {
            "action_required": action_required,
            "open_count": 1 if action_required else 0,
            "notify": "NOTIFY" if action_required else "DONT_NOTIFY",
        },
        "writeback": {"spend_after_validation": should_run},
        "scheduler": {"action": "run_now" if should_run else "wait"},
        "action_signature": {
            "matches": True,
            "source_hash": "sha256:fixture",
            "envelope_hash": "sha256:fixture",
        },
        "compaction": {"within_budget": True},
    }


def test_turn_plan_projects_ready_route_without_side_effects() -> None:
    envelope = _envelope()

    payload = build_loopx_turn_plan(
        envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == "loopx_turn_plan_v0"
    assert payload["mode"] == "plan"
    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value
    assert payload["route"]["would_invoke_host"] is True
    assert payload["route"]["host_invocation_allowed"] is False
    assert payload["turn_envelope"] == envelope
    assert payload["effects"] == {
        "host_invoked": False,
        "state_written": False,
        "scheduler_acknowledged": False,
        "quota_spent": False,
    }
    assert payload["boundary"]["read_only"] is True


def test_turn_help_omits_legacy_agent_loop_entrypoint() -> None:
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(["--help"])

    assert exit_code == 0
    assert "agent-loop" not in output.getvalue()
    assert "turn" in output.getvalue()


@pytest.mark.parametrize(
    ("effective_action", "expected"),
    [
        ("capability_repair", LoopXTurnRoute.REPAIR_REQUIRED),
        ("autonomous_replan", LoopXTurnRoute.REPLAN_REQUIRED),
        ("successor_replan_required", LoopXTurnRoute.REPLAN_REQUIRED),
    ],
)
def test_turn_plan_projects_typed_recovery_routes(
    effective_action: str,
    expected: LoopXTurnRoute,
) -> None:
    payload = build_loopx_turn_plan(
        _envelope(effective_action=effective_action),
        host="generic-cli",
        execution_mode="isolated-headless",
    )

    assert payload["route"]["kind"] == expected.value
    assert payload["host"]["explicit_isolation"] is True


def test_turn_plan_preserves_safe_bypass_when_user_action_is_visible() -> None:
    payload = build_loopx_turn_plan(
        _envelope(action_required=True),
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value


@pytest.mark.parametrize(
    ("action_required", "quiet_noop_allowed", "expected"),
    [
        (True, False, LoopXTurnRoute.USER_ACTION_REQUIRED),
        (False, True, LoopXTurnRoute.WAIT),
        (False, False, LoopXTurnRoute.BLOCKED),
    ],
)
def test_turn_plan_projects_non_run_routes(
    action_required: bool,
    quiet_noop_allowed: bool,
    expected: LoopXTurnRoute,
) -> None:
    payload = build_loopx_turn_plan(
        _envelope(
            should_run=False,
            action_required=action_required,
            quiet_noop_allowed=quiet_noop_allowed,
        ),
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["route"]["kind"] == expected.value
    assert payload["route"]["would_invoke_host"] is False


def test_turn_plan_fails_closed_on_action_signature_drift() -> None:
    envelope = _envelope()
    envelope["action_signature"] = {"matches": False}

    payload = build_loopx_turn_plan(
        envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value
    assert payload["route"]["would_invoke_host"] is False


def test_turn_plan_fails_closed_on_oversized_turn_envelope() -> None:
    envelope = _envelope()
    envelope["compaction"] = {"within_budget": False}

    payload = build_loopx_turn_plan(
        envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value


def test_scheduler_followup_binding_preserves_turn_lineage(
    tmp_path: Path,
) -> None:
    payload = {
        "scheduler_hint": {
            "codex_app": {
                "ack_hint": {"cli_args": ["quota", "scheduler-ack-current"]}
            }
        }
    }

    bind_scheduler_followup_cli_routes(
        payload,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        source="loopx_turn_plan",
    )

    ack_hint = payload["scheduler_hint"]["codex_app"]["ack_hint"]
    assert ack_hint["cli_args"][:2] == ["--registry", str(tmp_path / "registry.json")]
    assert ack_hint["route_binding"]["source"] == "loopx_turn_plan"


def _write_live_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    runtime.mkdir(parents=True)
    state = project / ".codex" / "goals" / "loopx-turn-fixture" / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# LoopX Turn Fixture",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P0] Advance one public fixture.",
                "  <!-- loopx:todo todo_id=todo_fixture0001 status=open task_class=advancement_task action_kind=fixture claimed_by=codex-fixture priority=P0 -->",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": "loopx-turn-fixture",
                        "domain": "loopx-turn-public-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                        "adapter": {"kind": "fixture_v0", "status": "connected-delivery"},
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": ["codex-fixture"],
                            "agent_profiles": {
                                "codex-fixture": {
                                    "schema_version": "agent_profile_v1",
                                    "profile_role": "fixture",
                                    "scope": "public qualification",
                                }
                            },
                            "write_scope": ["docs/**"],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return project, runtime, registry


def test_turn_cli_consumes_live_state_without_writes(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "plan",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert exit_code == 0
    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value
    assert payload["turn_envelope"]["action_signature"]["matches"] is True
    assert payload["effects"]["state_written"] is False
    assert before == after
