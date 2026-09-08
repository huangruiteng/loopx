"""Split-root fence regressions for the monitor-poll and Turn writebacks.

Each writeback uses its effective runtime root and also respects the authority
of the registered source file. An override cannot bypass either source fence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from loopx.cli import main
from loopx.cli_commands.turn_todo_writeback import (
    write_turn_repair_update,
    write_turn_validated_completion,
)
from loopx.control_plane.coordination.legacy_writer_fence import (
    LegacyCoordinationWriterFenced,
    legacy_coordination_writer_fence_path,
)
from loopx.control_plane.coordination.local_authority import (
    LocalCoordinationAuthorityUnavailable,
)
from loopx.control_plane.quota import monitor_poll
from loopx.control_plane.scheduler.monitor_poll_writeback import (
    write_monitor_poll_todo_state,
)

GOAL_ID = "split-root-writeback-goal"
AGENT_ID = "turn-writeback-author"
ADVANCE_ID = "todo_splitroot_advance"
MONITOR_ID = "todo_splitroot_monitor"
OVERRIDE_POLL_HASH = "split-v2"
LEGACY_POLL_HASH = "split-v1"
REPOSITORY = Path(__file__).resolve().parents[2]


def _write_split_root_goal(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = repo / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "---\n"
        f"goal_id: {GOAL_ID}\n"
        "updated_at: 2026-09-04T00:00:00+00:00\n"
        "---\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Advance the fenced writeback slice.\n"
        "  <!-- loopx:todo "
        f"todo_id={ADVANCE_ID} status=open task_class=advancement_task "
        f"claimed_by={AGENT_ID} -->\n"
        "- [ ] [P2] Watch the fenced writeback channel.\n"
        "  <!-- loopx:todo "
        f"todo_id={MONITOR_ID} status=open task_class=continuous_monitor "
        f"claimed_by={AGENT_ID} target_key=splitroot-review cadence=30m "
        f"result_hash={LEGACY_POLL_HASH} material_change=false -->\n",
        encoding="utf-8",
    )
    runtime_registry = tmp_path / "registry-runtime"
    runtime_override = tmp_path / "override-runtime"
    runtime_registry.mkdir()
    runtime_override.mkdir()
    registry = tmp_path / "registry.global.json"
    registry.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime_registry),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "harness_self_improvement",
                        "status": "active",
                        "repo": str(repo),
                        "state_file": state.name,
                        "adapter": {"kind": "harness_self_improvement"},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry, state, runtime_registry, runtime_override


def _engage_fence_at(runtime_root: Path) -> None:
    fence = legacy_coordination_writer_fence_path(
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
    )
    fence.parent.mkdir(parents=True, exist_ok=True)
    fence.write_text(
        json.dumps({"state": "present", "engaged_by": "promotion"}),
        encoding="utf-8",
    )


def _fence_check_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.coordination.legacy_writer_fence."
        "effect_runtime_result",
        lambda *_args, **_kwargs: {
            "status": "blocked",
            "reason_code": "legacy_coordination_writer_fenced",
            "authority_mode": "file_v0",
        },
    )


def _poll_kwargs(
    registry: Path,
    runtime_root: Path,
    *,
    result_hash: str = OVERRIDE_POLL_HASH,
) -> dict[str, Any]:
    return {
        "registry_path": registry,
        "runtime_root": runtime_root,
        "goal_id": GOAL_ID,
        "generated_at": "2026-09-04T01:00:00+00:00",
        "execute": True,
        "todo_id": MONITOR_ID,
        "result_hash": result_hash,
        "material_change": False,
        "next_due_at": "2026-09-04T02:00:00+00:00",
        "agent_id": AGENT_ID,
    }


def test_monitor_poll_writeback_blocked_when_override_root_is_fenced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry, state, _runtime_registry, runtime_override = (
        _write_split_root_goal(tmp_path)
    )
    _engage_fence_at(runtime_override)
    _fence_check_blocks(monkeypatch)
    state_before = state.read_text(encoding="utf-8")

    with pytest.raises(LegacyCoordinationWriterFenced):
        write_monitor_poll_todo_state(**_poll_kwargs(registry, runtime_override))

    assert LEGACY_POLL_HASH in state.read_text(encoding="utf-8")
    assert OVERRIDE_POLL_HASH not in state.read_text(encoding="utf-8")
    assert state.read_text(encoding="utf-8") == state_before


def test_monitor_poll_writeback_blocks_when_the_registry_source_is_fenced(
    tmp_path: Path,
) -> None:
    """An override shares the source state, so its original fence still applies."""

    from loopx.control_plane.effect_runtime import effect_runtime_result

    registry, state, runtime_registry, runtime_override = (
        _write_split_root_goal(tmp_path)
    )
    before = state.read_bytes()
    engaged = effect_runtime_result("coordination.local_authority.legacy_writer_fence.engage", {
        "schema_version": "loopx_legacy_coordination_writer_fence_engage_request_v0",
        "runtime_root": str(runtime_registry), "goal_id": GOAL_ID, "state_path": str(state),
        "fence": {"schema_version": "loopx_legacy_coordination_writer_fence_v0", "state": "engaged",
            "goal_id": GOAL_ID, "fence_id": "original-source", "source_version": "source:1",
            "source_projection_sha256": "a" * 64, "expected_shadow_provider_revision": "file:1:aaaaaaaaaaaaaaaaaaaaaaaa"},
    })
    assert engaged["status"] == "applied", engaged
    with pytest.raises(LegacyCoordinationWriterFenced) as error:
        write_monitor_poll_todo_state(**_poll_kwargs(registry, runtime_override))
    assert error.value.code == "legacy_coordination_writer_fenced"
    assert state.read_bytes() == before


def test_monitor_poll_writeback_allows_an_unfenced_runtime_override(tmp_path: Path) -> None:
    registry, state, _runtime_registry, runtime_override = _write_split_root_goal(tmp_path)

    receipt = write_monitor_poll_todo_state(
        **_poll_kwargs(registry, runtime_override)
    )

    assert receipt is not None
    assert receipt["result_hash"] == OVERRIDE_POLL_HASH
    assert receipt["last_checked_at"] == "2026-09-04T01:00:00+00:00"
    active = state.read_text(encoding="utf-8")
    assert f"result_hash={OVERRIDE_POLL_HASH}" in active


def test_quota_monitor_poll_provider_writeback_blocked_under_override_fence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The record path must hand its effective root to the provider writeback."""

    registry, state, _runtime_registry, runtime_override = (
        _write_split_root_goal(tmp_path)
    )
    _engage_fence_at(runtime_override)
    _fence_check_blocks(monkeypatch)

    def native(_method: str, request: dict[str, Any]) -> dict[str, Any]:
        assert request["phase"] == "preflight"
        return {
            "schema_version": monitor_poll.QUOTA_MONITOR_POLL_COMMIT_RESULT_SCHEMA,
            "status": "provider_required",
            "provider_plan": {
                "goal_id": GOAL_ID,
                "generated_at": "2026-09-04T01:00:00+00:00",
                "execute": True,
                "todo_id": MONITOR_ID,
                "result_hash": OVERRIDE_POLL_HASH,
                "material_change": False,
                "next_due_at": "2026-09-04T02:00:00+00:00",
            },
        }

    monkeypatch.setattr(monitor_poll, "effect_runtime_result", native)
    before = {
        "goal_id": GOAL_ID,
        "should_run": False,
        "effective_action": "monitor_quiet_skip",
        "agent_identity": {"agent_id": AGENT_ID},
    }

    with pytest.raises(LegacyCoordinationWriterFenced):
        monitor_poll.record_quota_monitor_poll_for_decision(
            before,
            {"runtime_root": str(runtime_override)},
            goal_id=GOAL_ID,
            after_decision=lambda _status: before,
            render_markdown=lambda _record: "unused",
            registry_path=registry,
            execute=True,
            todo_id=MONITOR_ID,
            result_hash=OVERRIDE_POLL_HASH,
            agent_id=AGENT_ID,
        )

    assert OVERRIDE_POLL_HASH not in state.read_text(encoding="utf-8")


def test_quota_monitor_poll_cli_preserves_fence_rejection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry, state, _runtime_registry, runtime_override = (
        _write_split_root_goal(tmp_path)
    )
    _engage_fence_at(runtime_override)
    _fence_check_blocks(monkeypatch)
    before = state.read_bytes()

    def unexpected_collection(**_kwargs: Any) -> dict[str, Any]:
        pytest.fail("fenced monitor write must be rejected before status collection")

    monkeypatch.setattr("loopx.cli_commands.quota.collect_status", unexpected_collection)

    exit_code = main(
        [
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_override),
            "--format",
            "json",
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--todo-id",
            MONITOR_ID,
            "--target-key",
            "splitroot-review",
            "--result-hash",
            OVERRIDE_POLL_HASH,
            "--next-due-at",
            "2026-09-04T02:00:00+00:00",
            "--execute",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "legacy_coordination_writer_fenced"
    assert payload["reason"] == (
        "legacy coordination writer is fenced; use the promoted canonical "
        f"authority (file_v0) for goal {GOAL_ID}; fence unknown; "
        "the primary record was not changed"
    )
    assert payload["write_check"] == {
        "status": "blocked",
        "reason_code": "legacy_coordination_writer_fenced",
        "authority_mode": "file_v0",
    }
    assert state.read_bytes() == before


@pytest.mark.parametrize("command", ["should-run", "monitor-poll"])
def test_read_only_quota_still_collects_promoted_state(
    command: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from loopx.cli import build_parser
    from loopx.cli_commands.quota_context import prepare_quota_command_context

    registry, _state, _registered_root, runtime_override = _write_split_root_goal(tmp_path)
    _engage_fence_at(runtime_override)
    _fence_check_blocks(monkeypatch)
    args = build_parser().parse_args([
        "quota", command, "--goal-id", GOAL_ID, "--agent-id", AGENT_ID,
        *(["--todo-id", MONITOR_ID] if command == "monitor-poll" else []),
    ])
    collected: list[object] = []

    def collector(**kwargs: Any) -> dict[str, object]:
        collected.append(kwargs["runtime_root_override"])
        return {"runtime_root": str(runtime_override)}

    context = prepare_quota_command_context(
        args, registry_path=registry, runtime_root_arg=str(runtime_override),
        status_collector=collector,
        operator_inbox_urgency_projector_factory=lambda **_: lambda **__: {},
    )
    assert collected == [str(runtime_override)]
    assert context.status_payload["runtime_root"] == str(runtime_override)


def test_turn_repair_update_blocked_when_override_root_is_fenced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry, _state, _runtime_registry, runtime_override = (
        _write_split_root_goal(tmp_path)
    )
    _engage_fence_at(runtime_override)
    _fence_check_blocks(monkeypatch)

    with pytest.raises(LegacyCoordinationWriterFenced):
        write_turn_repair_update(
            registry_path=registry,
            runtime_root_arg=str(runtime_override),
            goal_id=GOAL_ID,
            todo_id=ADVANCE_ID,
            note="host repair reported a bounded retry",
            evidence="LoopX Turn repair_required: rerun the slice",
            agent_id=AGENT_ID,
        )


def test_turn_validated_completion_blocked_when_override_root_is_fenced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry, state, runtime_registry, runtime_override = (
        _write_split_root_goal(tmp_path)
    )
    _engage_fence_at(runtime_override)
    _fence_check_blocks(monkeypatch)
    before = state.read_bytes()

    with pytest.raises(LocalCoordinationAuthorityUnavailable) as error:
        write_turn_validated_completion(
            registry_path=registry,
            runtime_root_arg=str(runtime_override),
            goal_id=GOAL_ID,
            todo_id=ADVANCE_ID,
            completion_turn_key="turn_splitroot_0001",
            evidence="LoopX Turn validated completion: slice merged",
            note="advance to the next bounded slice",
            agent_id=AGENT_ID,
        )

    assert error.value.code == "local_authority_todo_list_unavailable"
    assert error.value.payload == {
        "schema_version": "loopx_local_coordination_todo_list_result_v0",
        "status": "missing",
        "source_authority": "file_v0",
        "decision_read_from_provider": True,
        "legacy_fallback_used": False,
        "recovery": {
            "action": "restore_canonical_authority",
            "runtime_root": str(runtime_override.resolve()),
            "goal_id": GOAL_ID,
            "legacy_markdown_fallback_allowed": False,
            "retry_after": "canonical_provider_readback_loaded",
        },
    }
    assert state.read_bytes() == before
    assert not (runtime_override / "authority").exists()
    assert not (runtime_registry / "authority").exists()

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.entrypoint",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_override),
            "--format",
            "json",
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            ADVANCE_ID,
            "--role",
            "agent",
            "--agent-id",
            AGENT_ID,
            "--evidence",
            "split-root provider recovery contract",
            "--next-agent-todo",
            "Resume only after canonical authority is restored.",
            "--next-task-class",
            "advancement_task",
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 1, process.stdout + process.stderr
    payload = json.loads(process.stdout)
    assert payload["error_code"] == "local_authority_todo_list_unavailable"
    assert payload["status"] == "missing"
    assert payload["source_authority"] == "file_v0"
    assert payload["decision_read_from_provider"] is True
    assert payload["legacy_fallback_used"] is False
    assert payload["recovery"] == error.value.payload["recovery"]
    assert state.read_bytes() == before
    assert not (runtime_override / "authority").exists()
    assert not (runtime_registry / "authority").exists()
