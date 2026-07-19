from __future__ import annotations

from pathlib import Path

from examples.control_plane.quota_plan_fixtures import SCOPED_AGENT_ID, write_cli_fixture
from loopx.control_plane.testing.canary_harness import run_json_cli


GOAL_ID = "needs-operator"


def _write_heartbeat_rrule(codex_home: Path, rrule: str) -> None:
    automation_path = codex_home / "automations" / "fixture" / "automation.toml"
    automation_path.parent.mkdir(parents=True, exist_ok=True)
    automation_path.write_text(
        "\n".join(
            [
                "version = 1",
                'id = "fixture"',
                'kind = "heartbeat"',
                'name = "Scheduler ACK fixture"',
                (
                    'prompt = "Advance `needs-operator` from active state. '
                    'Agent: `codex-side-bypass`."'
                ),
                'status = "ACTIVE"',
                f'rrule = "{rrule}"',
                'target_thread_id = "fixture-thread"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _quota(
    registry_path: Path,
    runtime_root: Path,
    project: Path,
) -> dict:
    return run_json_cli(
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        SCOPED_AGENT_ID,
        "--codex-app",
        registry_path=registry_path,
        runtime_root=runtime_root,
        cwd=project,
    )


def test_scheduler_ack_current_replays_host_binding_after_update(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry_path, runtime_root, project = write_cli_fixture(
        tmp_path / "fixture",
        scoped_agents=True,
    )
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CODEX_THREAD_ID", "fixture-thread")
    _write_heartbeat_rrule(codex_home, "FREQ=MINUTELY;INTERVAL=3")

    first = _quota(registry_path, runtime_root, project)
    app = first["scheduler_hint"]["codex_app"]
    target_rrule = app["recommended_rrule"]
    ack_hint = app["ack_hint"]
    assert app["stateful_backoff"]["apply_needed"] is True
    assert ack_hint["after"] == "automation_update_rrule_success"
    assert ack_hint["args"]["host_match_observed"] is True

    # Simulate a successful host update before executing the original ACK hint.
    _write_heartbeat_rrule(codex_home, target_rrule)
    ack = run_json_cli(
        *ack_hint["cli_args"],
        registry_path=registry_path,
        runtime_root=runtime_root,
        cwd=project,
    )
    assert ack["scheduler_state_mutated"] is True
    assert ack["already_applied"] is False

    settled = _quota(registry_path, runtime_root, project)
    settled_app = settled["scheduler_hint"]["codex_app"]
    assert settled_app["stateful_backoff"]["apply_needed"] is False
    assert settled_app["stateful_backoff"]["ack_needed"] is False
    assert settled_app["host_action"] == "none"
