#!/usr/bin/env python3
"""Prove generic-host Turn transaction and terminal-routing contracts."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.turn_driver import (  # noqa: E402
    TurnEffectEnvelope,
    TurnLeaseController,
    build_loopx_turn_command_validator,
    build_loopx_turn_plan,
    load_turn_events,
    load_loopx_turn_plan_from_journal,
    run_loopx_turn_once,
)


def _envelope(*, action_hash: str, should_run: bool = True) -> dict[str, Any]:
    terminal = not should_run
    return {
        "ok": True,
        "schema_version": "loopx_turn_envelope_v0",
        "goal_id": "fake-host-walkthrough",
        "agent_id": "generic-fixture-host",
        "should_run": should_run,
        "effective_action": "normal_run" if should_run else "terminal_no_followup",
        "action": {
            "must_attempt": should_run,
            "delivery_allowed": should_run,
            "quiet_noop_allowed": terminal,
            **(
                {
                    "selected_todo": {
                        "todo_id": "todo_fakehost0001",
                        "text": "Advance one synthetic public fixture.",
                        "required_write_scopes": ["synthetic/**"],
                    }
                }
                if should_run
                else {}
            ),
        },
        "user": {"action_required": False, "open_count": 0, "notify": "DONT_NOTIFY"},
        "writeback": {"spend_after_validation": should_run},
        "scheduler": {"action": "run_now" if should_run else "wait"},
        "action_signature": {
            "matches": True,
            "source_hash": action_hash,
            "envelope_hash": action_hash,
        },
        "compaction": {"within_budget": True},
    }


def _plan(*, action_hash: str) -> dict[str, Any]:
    return build_loopx_turn_plan(
        _envelope(action_hash=action_hash),
        host="generic-cli",
        execution_mode="isolated-headless",
    )


def _host_argv(effect_path: Path, count_path: Path) -> list[str]:
    script = """
import json
import pathlib
import sys

request = json.load(sys.stdin)
contract = request["result_contract"]
assert contract["schema_version"] == "loopx_turn_result_v0"
assert contract["completed_phases"] == ["host_execute", "typed_result"]
effect_path = pathlib.Path(sys.argv[1])
effect_path.parent.mkdir(parents=True, exist_ok=True)
effect_path.write_text(
    json.dumps(
        {
            "task": "synthetic_public_fixture",
            "turn_key": request["turn_key"],
            "result_schema_version": contract["schema_version"],
        }
    ),
    encoding="utf-8",
)
count_path = pathlib.Path(sys.argv[2])
count_path.write_text(
    str(int(count_path.read_text()) + 1 if count_path.exists() else 1),
    encoding="utf-8",
)
json.dump(
    {
        "schema_version": contract["schema_version"],
        "turn_key": request["turn_key"],
        "result_kind": "validated_progress",
        "completed_phases": contract["completed_phases"],
        "classification": "fake_host_fixture_progress",
        "recommended_action": "Validate the synthetic fixture.",
        "next_action": "Stop after the independently validated fixture.",
        "delivery_batch_scale": "single_surface",
        "delivery_outcome": "outcome_progress",
        "vision_unchanged_reason": "The public fixture objective is unchanged.",
        "summary": "The generic fake host advanced one fixture.",
    },
    sys.stdout,
)
"""
    program = effect_path.parent.parent / "synthetic-generic-host.py"
    program.write_text(script, encoding="utf-8")
    return [sys.executable, str(program), str(effect_path), str(count_path)]


def _validator_argv(effect_path: Path) -> list[str]:
    script = """
import json
import pathlib
import sys

result = json.load(sys.stdin)
effect = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
valid = (
    effect.get("task") == "synthetic_public_fixture"
    and effect.get("turn_key") == result.get("turn_key")
    and effect.get("result_schema_version") == result.get("schema_version")
)
raise SystemExit(0 if valid else 9)
"""
    program = effect_path.parent.parent / "synthetic-task-validator.py"
    program.write_text(script, encoding="utf-8")
    return [sys.executable, str(program), str(effect_path)]


def _callbacks(calls: dict[str, int], phases: list[str]):
    def writeback(
        _effect: TurnEffectEnvelope,
        _result: dict[str, Any],
    ) -> dict[str, Any]:
        calls["writeback"] += 1
        phases.append("writeback")
        return {"ok": True, "appended": True, "classification": "fixture_progress"}

    def spend(_effect: TurnEffectEnvelope) -> dict[str, Any]:
        calls["spend"] += 1
        phases.append("spend")
        return {"ok": True, "appended": True, "slots": 1}

    def scheduler(
        _effect: TurnEffectEnvelope,
        _spend: dict[str, Any],
    ) -> dict[str, Any]:
        calls["scheduler"] += 1
        phases.append("scheduler")
        return {
            "completed": True,
            "acknowledged": True,
            "disposition": "applied_and_acknowledged",
        }

    return writeback, spend, scheduler


def _common(
    *,
    root: Path,
    plan: dict[str, Any],
    calls: dict[str, int],
    phases: list[str],
) -> tuple[dict[str, Any], Path, Path]:
    project = root / "project"
    project.mkdir(parents=True)
    effect_path = project / "synthetic-task.json"
    count_path = root / "host-count"
    state_path = project / "ACTIVE_GOAL_STATE.md"
    state_path.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "---",
                "",
                "# Fake Host Walkthrough",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P0] Advance one synthetic public fixture.",
                "  <!-- loopx:todo todo_id=todo_fakehost0001 status=open "
                "claimed_by=generic-fixture-host "
                "required_write_scopes=synthetic%2F%2A%2A priority=P0 -->",
                "",
            ]
        ),
        encoding="utf-8",
    )
    runtime_root = root / "runtime"
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": "fake-host-walkthrough",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_path.name,
                        "coordination": {
                            "registered_agents": ["generic-fixture-host"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    transaction = plan.get("transaction")
    assert isinstance(transaction, dict)
    turn_key = str(transaction["turn_key"])
    writeback, spend, scheduler = _callbacks(calls, phases)
    return {
        "host_argv": _host_argv(effect_path, count_path),
        "project": project,
        "runtime_root": runtime_root,
        "goal_id": "fake-host-walkthrough",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": build_loopx_turn_command_validator(
            _validator_argv(effect_path),
            project=project,
            timeout_seconds=5,
        ),
        "writeback": writeback,
        "spend": spend,
        "scheduler": scheduler,
        "lease_controller": TurnLeaseController(
            registry_path=registry_path,
            runtime_root=runtime_root,
            goal_id="fake-host-walkthrough",
            todo_id="todo_fakehost0001",
            owner="generic-fixture-host",
            idempotency_key=f"turn:{turn_key}",
            write_scopes=["synthetic/**"],
        ),
    }, effect_path, count_path


def _commit_replay_and_boundary(root: Path) -> dict[str, Any]:
    plan = _plan(action_hash="sha256:fake-host-commit")
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    phases: list[str] = []
    kwargs, effect_path, count_path = _common(
        root=root,
        plan=plan,
        calls=calls,
        phases=phases,
    )

    preview = run_loopx_turn_once(plan, **{**kwargs, "execute": False})
    committed = run_loopx_turn_once(plan, **kwargs)
    replay = run_loopx_turn_once(plan, **kwargs)

    assert preview["status"] == "preview"
    assert not any(preview["effects"].values())
    assert committed["status"] == "committed"
    assert committed["receipt"]["status"] == "committed"
    assert committed["effects"] == {
        "host_invoked": True,
        "state_written": True,
        "quota_spent": True,
        "scheduler_acknowledged": True,
    }
    assert replay["replayed"] is True
    assert not any(replay["effects"].values())
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}
    assert phases == ["writeback", "spend", "scheduler"]
    assert count_path.read_text(encoding="utf-8") == "1"
    assert json.loads(effect_path.read_text(encoding="utf-8"))["task"] == (
        "synthetic_public_fixture"
    )

    events = load_turn_events(
        root / "runtime",
        "fake-host-walkthrough",
        committed["resume_turn_key"],
    )
    states = [
        event["payload"]["state"]
        for event in events
        if isinstance(event.get("payload"), dict)
        and isinstance(event["payload"].get("state"), dict)
    ]
    assert states
    journal_payload = states[-1]
    assert journal_payload["host"] == {
        "executable": Path(sys.executable).name,
        "argv_count": 4,
    }
    assert set(journal_payload["host_result"]) == {
        "classification",
        "completed_phases",
        "delivery_batch_scale",
        "delivery_outcome",
        "next_action",
        "path_delta_mode",
        "recommended_action",
        "result_kind",
        "schema_version",
        "summary",
        "turn_key",
        "vision_unchanged_reason",
    }
    assert str(root) not in json.dumps(journal_payload, sort_keys=True)

    return {
        "generic_host_process_boundary_proven": True,
        "independent_task_effect_validated": True,
        "preview_has_no_effects": True,
        "committed_once": True,
        "replay_has_no_effects": True,
        "ordered_effects": phases,
        "public_boundary_preserved": True,
    }


def _recover_after_writeback(root: Path) -> dict[str, Any]:
    plan = _plan(action_hash="sha256:fake-host-recovery")
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    phases: list[str] = []
    kwargs, effect_path, count_path = _common(
        root=root,
        plan=plan,
        calls=calls,
        phases=phases,
    )
    healthy_spend = kwargs["spend"]

    def interrupted_spend(_effect: TurnEffectEnvelope) -> dict[str, Any]:
        calls["spend"] += 1
        phases.append("spend-interrupted")
        raise SystemExit(8)

    try:
        run_loopx_turn_once(plan, **{**kwargs, "spend": interrupted_spend})
    except SystemExit as exc:
        assert exc.code == 8
    else:
        raise AssertionError("the synthetic spend interruption must escape")

    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    resumed_plan = load_loopx_turn_plan_from_journal(
        root / "runtime",
        goal_id="fake-host-walkthrough",
        turn_key=str(transaction["turn_key"]),
    )
    recovered = run_loopx_turn_once(
        resumed_plan,
        **{**kwargs, "spend": healthy_spend},
    )

    assert recovered["status"] == "committed"
    assert calls == {"writeback": 1, "spend": 2, "scheduler": 1}
    assert phases == ["writeback", "spend-interrupted", "spend", "scheduler"]
    assert count_path.read_text(encoding="utf-8") == "1"
    assert json.loads(effect_path.read_text(encoding="utf-8"))["task"] == (
        "synthetic_public_fixture"
    )
    return {
        "resumed_after_writeback": True,
        "host_not_repeated": True,
        "writeback_not_repeated": True,
        "task_effect_not_repeated": True,
        "remaining_effects": ["spend", "scheduler"],
    }


def _terminal_envelope_blocks_host() -> dict[str, Any]:
    """The lifecycle owner supplies terminal state; Turn must honor it."""
    plan = build_loopx_turn_plan(
        _envelope(action_hash="sha256:fake-host-terminal", should_run=False),
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    assert plan["route"]["kind"] == "wait"
    assert plan["route"]["would_invoke_host"] is False
    assert plan["route"]["host_invocation_allowed"] is False
    assert plan["transaction"]["status"] == "not_applicable"
    assert not any(plan["effects"].values())
    return {"host_followup_eligible": False, "effects": plan["effects"]}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-turn-fake-host-") as directory:
        root = Path(directory)
        summary = {
            "schema_version": "loopx_turn_fake_host_walkthrough_v1",
            "host": "generic-cli",
            "commit_and_replay": _commit_replay_and_boundary(root / "commit"),
            "recovery": _recover_after_writeback(root / "recovery"),
            "terminal_envelope_routing": _terminal_envelope_blocks_host(),
        }

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
