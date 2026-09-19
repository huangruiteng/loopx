from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.coordination.local_authority_shadow_observation import LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA, observe_local_authority_commit
from loopx.control_plane.todos.handoff_mode import set_goal_handoff_mode
from loopx.control_plane.work_items.task_lease import (
    acquire_task_lease,
    release_task_lease,
    renew_task_lease,
    transfer_task_lease,
)
from loopx.event_sourced_state import (
    TODO_ADDED,
    AppendOnlyStateEventStore,
    make_state_event,
)
from loopx.todos import (
    add_goal_todo,
    archive_completed_todos,
    complete_goal_todo,
    supersede_goal_todo,
    update_goal_todo,
)


GOAL_ID = "goal-shadow"
AGENT_A = "agent-a"
AGENT_B = "agent-b"


def _fixture(tmp_path: Path, *, enabled: bool) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = repo / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "---\n"
        f"goal_id: {GOAL_ID}\n"
        "handoff_mode: hard_lease\n"
        "updated_at: 2026-09-02T00:00:00+00:00\n"
        "---\n\n"
        "## Agent Todo\n\n",
        encoding="utf-8",
    )
    runtime_root = tmp_path / "runtime"
    coordination: dict[str, object] = {
        "agent_model": "peer_v1",
        "registered_agents": [AGENT_A, AGENT_B],
    }
    if enabled:
        coordination["authority_shadow"] = {
            "schema_version": "loopx_local_authority_shadow_config_v0",
            "mode": "file_one_way",
        }
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "harness_self_improvement",
                        "status": "active",
                        "repo": str(repo),
                        "state_file": state.name,
                        "adapter": {"kind": "harness_self_improvement"},
                        "coordination": coordination,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry, state, runtime_root


def _add(registry: Path) -> dict:
    return add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Exercise one-way local authority shadowing.",
        task_class="advancement_task",
    )


def _shadow_document(runtime_root: Path) -> dict:
    paths = list(
        (
            runtime_root
            / "authority-shadow"
            / "file"
            / GOAL_ID
        ).glob("authority-store-*.json")
    )
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8"))


def test_default_off_public_writers_never_call_shadow_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _state, runtime_root = _fixture(tmp_path, enabled=False)
    calls: list[object] = []

    def forbidden(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("default-off path constructed the shadow runtime")

    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority_shadow_observation.effect_runtime_result",
        forbidden,
    )

    result = _add(registry)
    lease_result = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=str(result["todo_id"]),
        owner=AGENT_A,
        idempotency_key="default-off",
        ttl_seconds=120,
    )

    assert result["ok"] is True
    assert lease_result["ok"] is True
    assert "authority_shadow" not in result
    assert "authority_shadow" not in lease_result
    assert calls == []
    assert not (runtime_root / "authority-shadow").exists()


def test_enabled_todo_public_facades_emit_post_commit_evidence(tmp_path: Path) -> None:
    registry, _state, runtime_root = _fixture(tmp_path, enabled=True)

    added = _add(registry)
    todo_id = str(added["todo_id"])
    acquired = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key="todo-terminal-a",
        ttl_seconds=120,
    )
    updated = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        note="A public-safe update.",
        agent_id=AGENT_A,
    )
    completed = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        role="agent",
        no_followup=True,
        agent_id=AGENT_A,
        task_lease_idempotency_key="todo-terminal-a",
        task_lease_expected_version=int(acquired["lease"]["version"]),
    )
    archived = archive_completed_todos(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        max_active_done=0,
        dry_run=False,
    )
    replacement = _add(registry)
    replacement_lease = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=str(replacement["todo_id"]),
        owner=AGENT_A,
        idempotency_key="todo-terminal-b",
        ttl_seconds=120,
    )
    superseded = supersede_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(replacement["todo_id"]),
        role="agent",
        reason="Replace obsolete work.",
        next_agent_todo="Carry the bounded work forward.",
        agent_id=AGENT_A,
        task_lease_idempotency_key="todo-terminal-b",
        task_lease_expected_version=int(replacement_lease["lease"]["version"]),
    )

    for result in (added, updated, completed, archived, replacement, superseded):
        assert result["ok"] is True
        assert result["authority_shadow"]["schema_version"] == (
            LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA
        )
        assert result["authority_shadow"]["primary_writeback_preserved"] is True
        assert result["authority_shadow"]["provider_to_local_writes"] is False
        assert result["authority_shadow"]["capture_kind"] == "post_commit_snapshot"
        assert result["authority_shadow"]["source_transaction_correlated"] is False
        assert result["authority_shadow"]["durable_source_outbox"] is False
        assert result["authority_shadow"]["source_candidate_compared"] is False
        assert result["authority_shadow"]["parity_verdict"] == "not_evaluated"


def test_enabled_task_lease_facades_shadow_only_committed_mutations(
    tmp_path: Path,
) -> None:
    registry, _state, runtime_root = _fixture(tmp_path, enabled=True)
    todo_id = str(_add(registry)["todo_id"])

    acquired = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key="lease-a",
        ttl_seconds=120,
    )
    replayed_acquire = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key="lease-a",
        ttl_seconds=120,
    )
    renewed = renew_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key="lease-a",
        expected_version=1,
        ttl_seconds=120,
    )
    transferred = transfer_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key="lease-a",
        new_owner=AGENT_B,
        new_idempotency_key="lease-b",
        expected_version=2,
        ttl_seconds=120,
    )
    released = release_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_B,
        idempotency_key="lease-b",
        expected_version=3,
    )

    for result in (acquired, renewed, transferred, released):
        assert result["authority_shadow"]["outcome"] in {
            "captured",
            "replayed",
            "ambiguous_reconciled",
        }
    assert replayed_acquire["idempotent"] is True
    assert "authority_shadow" not in replayed_acquire


def test_handoff_mode_and_todo_add_refresh_the_same_shadow(
    tmp_path: Path,
) -> None:
    registry, _state, runtime_root = _fixture(tmp_path, enabled=True)

    mode = set_goal_handoff_mode(
        registry_path=registry,
        goal_id=GOAL_ID,
        mode="legacy",
    )
    added = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Verify the migrated authority projection.",
        task_class="advancement_task",
    )

    assert mode["changed"] is True
    assert mode["authority_shadow"]["outcome"] == "captured"
    assert added["added"] is True
    assert added["authority_shadow"]["outcome"] == "captured"
    head = _shadow_document(runtime_root)["head"]
    assert head["handoff_mode"] == "legacy"
    assert [todo["todo_id"] for todo in head["todos"]] == [
        added["todo_id"]
    ]


def test_event_projected_completion_refreshes_shadow_after_releasing_lease(
    tmp_path: Path,
) -> None:
    registry, state, runtime_root = _fixture(tmp_path, enabled=True)
    todo_id = "todo_event_shadow"
    AppendOnlyStateEventStore(state.with_name("events.jsonl")).append(
        make_state_event(
            event_id="evt-event-shadow-parent",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": todo_id},
            payload={
                "role": "agent",
                "title": "Complete the event-projected shadow task.",
                "task_class": "advancement_task",
                "claimed_by": AGENT_A,
            },
            recorded_at="2026-09-02T00:00:00+00:00",
        )
    )
    lease_key = "event-shadow-instance"
    acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        owner=AGENT_A,
        idempotency_key=lease_key,
        ttl_seconds=120,
    )

    completed = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        claimed_by=AGENT_A,
        agent_id=AGENT_A,
        task_lease_idempotency_key=lease_key,
        task_lease_expected_version=1,
        evidence="validation://event-shadow-completion",
        no_followup=True,
    )

    assert completed["source"] == "event_log"
    assert completed["changed"] is True
    assert completed["authority_shadow"]["outcome"] == "captured"
    head = _shadow_document(runtime_root)["head"]
    assert len(head["leases"]) == 1
    assert head["leases"][0]["todo_id"] == todo_id
    assert head["leases"][0]["status"] == "released"
    projected = next(todo for todo in head["todos"] if todo["todo_id"] == todo_id)
    assert projected["status"] == "done"


def test_candidate_failure_never_changes_committed_todo_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state, _runtime_root = _fixture(tmp_path, enabled=True)

    def unavailable(
        _method: str,
        params: dict[str, object],
        **_kwargs: object,
    ) -> dict[str, object]:
        return {
            "schema_version": LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA,
            "outcome": "unavailable",
            "reason_code": "injected_outage",
            "goal_id": params["goal_id"],
            "observation_id": params["observation_id"],
            "source_digest": params["source_digest"],
            "primary_authority": "legacy_local",
            "candidate_provider": "file",
            "candidate_read_for_decision": False,
            "provider_to_local_writes": False,
            "primary_writeback_preserved": True,
            "capture_kind": "post_commit_snapshot",
            "source_transaction_correlated": False,
            "durable_source_outbox": False,
            "source_candidate_compared": False,
            "parity_verdict": "not_evaluated",
            "store_identity": None,
            "provider_revision": None,
            "cursor": None,
        }

    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority_shadow_observation.effect_runtime_result",
        unavailable,
    )

    result = _add(registry)

    assert result["ok"] is True
    assert result["added"] is True
    assert result["authority_shadow"]["outcome"] == "unavailable"
    assert str(result["todo_id"]) in state.read_text(encoding="utf-8")


def test_invalid_shadow_config_is_typed_but_preserves_primary_write(
    tmp_path: Path,
) -> None:
    registry, state, _runtime_root = _fixture(tmp_path, enabled=True)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["goals"][0]["coordination"]["authority_shadow"]["mode"] = "remote"
    registry.write_text(json.dumps(payload), encoding="utf-8")

    result = _add(registry)

    assert result["ok"] is True
    assert result["authority_shadow"]["outcome"] == "failed"
    assert result["authority_shadow"]["reason_code"] == "invalid_shadow_config"
    assert str(result["todo_id"]) in state.read_text(encoding="utf-8")


def test_observer_is_default_off_without_creating_lock_or_provider_directory(
    tmp_path: Path,
) -> None:
    registry, _state, runtime_root = _fixture(tmp_path, enabled=False)

    assert (
        observe_local_authority_commit(
            registry_path=registry,
            runtime_root=runtime_root,
            goal_id=GOAL_ID,
            observation_trigger="todo_update",
        )
        is None
    )
    assert not (runtime_root / "authority-shadow").exists()


def test_provider_revision_conflict_resamples_source_under_same_observation_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _state, runtime_root = _fixture(tmp_path, enabled=True)
    projections = iter(
        (
            {
                "schema_version": "loopx_local_authority_shadow_projection_v0",
                "goal_id": GOAL_ID,
                "handoff_mode": "hard_lease",
                "todos": [{"todo_id": "todo_old", "status": "open"}],
                "leases": [],
            },
            {
                "schema_version": "loopx_local_authority_shadow_projection_v0",
                "goal_id": GOAL_ID,
                "handoff_mode": "hard_lease",
                "todos": [{"todo_id": "todo_fresh", "status": "open"}],
                "leases": [],
            },
        )
    )
    requests: list[dict[str, object]] = []

    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority_shadow_observation._stable_projection",
        lambda **_kwargs: next(projections),
    )

    def conflict_then_advance(
        _method: str,
        params: dict[str, object],
        **_kwargs: object,
    ) -> dict[str, object]:
        requests.append(dict(params))
        outcome = "conflict_retry_required" if len(requests) == 1 else "captured"
        return {
            "schema_version": LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA,
            "outcome": outcome,
            "reason_code": (
                "provider_revision_mismatch" if len(requests) == 1 else None
            ),
            "goal_id": GOAL_ID,
            "observation_id": params["observation_id"],
            "source_digest": params["source_digest"],
            "primary_authority": "legacy_local",
            "candidate_provider": "file",
            "candidate_read_for_decision": False,
            "provider_to_local_writes": False,
            "primary_writeback_preserved": True,
            "capture_kind": "post_commit_snapshot",
            "source_transaction_correlated": False,
            "durable_source_outbox": False,
            "source_candidate_compared": False,
            "parity_verdict": "not_evaluated",
            "store_identity": "file:test",
            "provider_revision": "file:2:test",
            "cursor": "2",
        }

    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority_shadow_observation.effect_runtime_result",
        conflict_then_advance,
    )

    result = observe_local_authority_commit(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id=GOAL_ID,
        observation_trigger="todo_update:todo_a:now",
    )

    assert result is not None
    assert result["outcome"] == "captured"
    assert len(requests) == 2
    assert requests[0]["source_digest"] != requests[1]["source_digest"]
    assert requests[0]["observation_id"] != requests[1]["observation_id"]
    assert all(request["runtime_root"] == str(runtime_root) for request in requests)
    assert all("provider_directory" not in request for request in requests)


def test_relative_common_runtime_root_resolves_against_the_project_root_for_every_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from loopx.control_plane.work_items.task_lease import runtime_root_from_registry
    from loopx.paths import registry_project_root

    registry, _state, _absolute_runtime = _fixture(tmp_path, enabled=True)
    document = json.loads(registry.read_text(encoding="utf-8"))
    document["common_runtime_root"] = "runtime-relative"
    registry.write_text(json.dumps(document), encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    expected_root = registry_project_root(registry) / "runtime-relative"

    added = _add(registry)
    lease = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime_root_from_registry(registry, None),
        goal_id=GOAL_ID,
        todo_id=str(added["todo_id"]),
        owner=AGENT_A,
        idempotency_key="relative-root",
        ttl_seconds=120,
    )
    handoff = set_goal_handoff_mode(
        registry_path=registry,
        goal_id=GOAL_ID,
        mode="hard_lease",
    )

    assert added["authority_shadow"]["outcome"] == "captured"
    assert lease["authority_shadow"]["outcome"] == "captured"
    assert handoff["changed"] is False
    assert added["authority_shadow"]["store_identity"] == lease["authority_shadow"]["store_identity"]
    assert (expected_root / "authority-shadow" / "file" / GOAL_ID).is_dir()
    assert (expected_root / "goals" / GOAL_ID / "task-leases" / f"{added['todo_id']}.json").exists()
    assert not (elsewhere / "runtime-relative").exists()
    document = _shadow_document(expected_root)
    assert document["cursor"] == "2"
    assert len(document["head"]["leases"]) == 1
