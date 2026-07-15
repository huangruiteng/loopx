from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

from loopx.cli import main as cli_main
from loopx.control_plane.turn_driver import (
    LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
    LoopXTurnRoute,
    build_loopx_turn_plan,
)
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
    assert payload["session"] == {
        "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
        "action": "start_new",
    }
    assert payload["transaction"]["status"] == "planned"
    assert payload["transaction"]["phases"] == [
        "host_execute",
        "typed_result",
        "validation",
        "durable_writeback",
        "quota_spend",
        "scheduler_apply",
        "scheduler_ack",
    ]
    assert payload["transaction"]["receipt_seed"]["status"] == "not_executed"
    assert payload["transaction"]["receipt_seed"]["next_phase"] == "host_execute"
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


def test_turn_plan_resumes_only_a_matching_session_binding() -> None:
    payload = build_loopx_turn_plan(
        _envelope(),
        host="codex-cli",
        execution_mode="interactive-visible",
        session_binding={
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "goal_id": "fixture-goal",
            "agent_id": "codex-fixture",
            "todo_id": "todo_fixture0001",
        },
    )

    assert payload["ok"] is True
    assert payload["session"]["action"] == "resume"
    assert payload["boundary"]["opaque_session_handle_omitted"] is True


def test_turn_plan_rejects_session_binding_identity_drift() -> None:
    payload = build_loopx_turn_plan(
        _envelope(),
        host="codex-cli",
        execution_mode="interactive-visible",
        session_binding={
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "goal_id": "another-goal",
            "agent_id": "codex-fixture",
            "todo_id": "todo_fixture0001",
        },
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value
    assert payload["route"]["would_invoke_host"] is False
    assert payload["session"]["action"] == "reject"
    assert payload["session"]["binding_status"] == "identity_mismatch"
    assert payload["transaction"]["status"] == "not_applicable"
    assert payload["effects"]["host_invoked"] is False


def test_turn_plan_transaction_key_is_stable_and_todo_scoped() -> None:
    first = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    repeated = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    changed_envelope = _envelope()
    changed_envelope["action"]["selected_todo"]["todo_id"] = "todo_fixture0002"
    changed = build_loopx_turn_plan(
        changed_envelope,
        host="generic-cli",
        execution_mode="isolated-headless",
    )

    assert first["transaction"]["turn_key"] == repeated["transaction"]["turn_key"]
    assert first["transaction"]["turn_key"] != changed["transaction"]["turn_key"]


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
    assert payload["session"]["action"] == "none"
    assert payload["transaction"]["status"] == "not_applicable"
    assert payload["transaction"]["phases"] == []


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
            "codex_app": {"ack_hint": {"cli_args": ["quota", "scheduler-ack-current"]}}
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
                        "adapter": {
                            "kind": "fixture_v0",
                            "status": "connected-delivery",
                        },
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
                "--include-transaction-detail",
            ]
        )

    payload = json.loads(output.getvalue())
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert exit_code == 0
    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value
    assert payload["session"]["action"] == "start_new"
    assert payload["turn_envelope"]["action_signature"]["matches"] is True
    assert payload["effects"]["state_written"] is False
    assert before == after


def test_turn_cli_omits_transaction_detail_by_default(tmp_path: Path) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
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
    assert exit_code == 0
    assert "session" not in payload
    assert "transaction" not in payload
    assert "opaque_session_handle_omitted" not in payload["boundary"]


def test_turn_cli_requires_complete_resume_identity(tmp_path: Path) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
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
                "--resume-goal-id",
                "loopx-turn-fixture",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload["ok"] is False
    assert "requires --resume-goal-id" in payload["error"]


def test_turn_run_once_cli_commits_validated_result_and_one_quota_slot(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()
    host_script = """
import json
import pathlib
import sys
request = json.load(sys.stdin)
pathlib.Path("fixture-artifact.txt").write_text("validated", encoding="utf-8")
json.dump({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": request["turn_key"],
    "result_kind": "validated_progress",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "fixture_progress",
    "recommended_action": "Continue the public fixture",
    "next_action": "Run the next public fixture check",
    "delivery_batch_scale": "implementation",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The fixture objective remains unchanged.",
    "summary": "One public fixture advanced."
}, sys.stdout)
"""
    validation_script = """
import json
import pathlib
import sys
json.load(sys.stdin)
artifact = pathlib.Path("fixture-artifact.txt")
raise SystemExit(0 if artifact.read_text(encoding="utf-8") == "validated" else 7)
"""
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
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-adapter-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--validation-command-json",
                json.dumps([sys.executable, "-c", validation_script]),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0, payload
    assert payload["status"] == "scheduler_action_required"
    assert payload["receipt"]["status"] == "validated"
    assert payload["receipt"]["next_phase"] == "scheduler_apply"
    assert payload["validation"]["status"] == "passed"
    assert payload["validation"]["validator_kind"] == "command"
    assert payload["resume_turn_key"].startswith("sha256:")
    assert payload["effects"] == {
        "host_invoked": True,
        "state_written": True,
        "quota_spent": True,
        "scheduler_acknowledged": False,
    }
    state_path = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    )
    assert "Run the next public fixture check" in state_path.read_text(encoding="utf-8")
    index_path = runtime / "goals" / "loopx-turn-fixture" / "runs" / "index.jsonl"
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert [row["classification"] for row in rows] == [
        "fixture_progress",
        "quota_slot_spent",
    ]

    resumed_output = io.StringIO()
    with contextlib.redirect_stdout(resumed_output):
        resumed_exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--validation-command-json",
                json.dumps([sys.executable, "-c", validation_script]),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--resume-turn-key",
                payload["resume_turn_key"],
                "--execute",
            ]
        )

    resumed = json.loads(resumed_output.getvalue())
    assert resumed_exit_code == 0, resumed
    assert resumed["status"] == "scheduler_action_required"
    assert resumed["effects"] == {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    replayed_rows = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["classification"] for row in replayed_rows] == [
        "fixture_progress",
        "quota_slot_spent",
    ]


def test_turn_run_once_cli_rejects_unproven_host_claim_before_writeback(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()
    host_script = """
import json
import sys
request = json.load(sys.stdin)
json.dump({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": request["turn_key"],
    "result_kind": "validated_progress",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "unproven_fixture_progress",
    "recommended_action": "Continue the public fixture",
    "next_action": "Run the next public fixture check",
    "delivery_batch_scale": "implementation",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The fixture objective remains unchanged.",
    "summary": "The host claims a missing artifact."
}, sys.stdout)
"""
    validation_script = """
import json
import pathlib
import sys
json.load(sys.stdin)
raise SystemExit(0 if pathlib.Path("claimed-artifact.txt").is_file() else 9)
"""
    state_path = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    )
    before_state = state_path.read_text(encoding="utf-8")
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
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--validation-command-json",
                json.dumps([sys.executable, "-c", validation_script]),
                "--validation-failure-kind",
                "replan_required",
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1, payload
    assert payload["status"] == "failed"
    assert payload["result_kind"] == "validation_failed"
    assert payload["validation"]["status"] == "failed"
    assert payload["validation"]["recovery_kind"] == "replan_required"
    assert payload["validation"]["exit_code"] == 9
    assert payload["effects"]["host_invoked"] is True
    assert payload["effects"]["state_written"] is False
    assert payload["effects"]["quota_spent"] is False
    assert state_path.read_text(encoding="utf-8") == before_state
    assert not (runtime / "goals" / "loopx-turn-fixture" / "runs").exists()


@pytest.mark.parametrize(
    "result_kind", ["validated_progress", "repair_required", "replan_required"]
)
def test_turn_run_once_cli_uses_built_in_codex_host_and_typed_writeback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result_kind: str,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)

    def fake_codex_host(request: dict[str, object], **_kwargs: object) -> dict[str, object]:
        return {
            "schema_version": "loopx_turn_result_v0",
            "turn_key": request["turn_key"],
            "result_kind": result_kind,
            "completed_phases": ["host_execute", "typed_result"],
            "classification": f"fixture_{result_kind}",
            "recommended_action": "Apply the typed follow-up",
            "next_action": "Run one revised public fixture check",
            "delivery_batch_scale": "implementation",
            "delivery_outcome": "outcome_progress",
            "vision_unchanged_reason": "The fixture objective remains unchanged.",
            "summary": "One public fixture advanced.",
        }

    monkeypatch.setattr("loopx.cli_commands.turn.run_codex_cli_host", fake_codex_host)
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
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--host",
                "codex-cli",
                "--project",
                str(project),
                "--validation-command-json",
                json.dumps(
                    [
                        sys.executable,
                        "-c",
                        "import json, sys; json.load(sys.stdin)",
                    ]
                ),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0, payload
    assert payload["host"] == {"executable": "built-in", "kind": "codex-cli"}
    assert payload["effects"]["state_written"] is True
    assert payload["effects"]["quota_spent"] is True
    state = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    ).read_text(encoding="utf-8")
    assert "Run one revised public fixture check" in state
    if result_kind != "validated_progress":
        assert f"LoopX%20Turn%20{result_kind}" in state
