from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.todos import provider_projection


SOURCE = """# Goal

Human-owned introduction.

## User Todo / Owner Review Reading Queue

## Agent Todo

## Completed Work Archive

## Next Action

Keep working.
"""


def _registry(tmp_path: Path) -> tuple[Path, Path, Path]:
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    state_file = project / ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(SOURCE, encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "schema_version": 1,
        "common_runtime_root": str(runtime_root),
        "goals": [{
            "id": "goal-a", "status": "active", "repo": str(project),
            "state_file": ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md",
        }],
    }), encoding="utf-8")
    return registry, runtime_root, state_file


def _authority_read() -> dict[str, object]:
    return {
        "status": "loaded",
        "source_authority": "file_v0",
        "provider_revision": "file:7:abc",
        "todos": [
            {
                "schema_version": "todo_domain_record_v0",
                "todo_id": "todo_active",
                "role": "agent",
                "status": "open",
                "done": False,
                "text": "Render native provider work.",
                "archive_state": "active",
                "task_class": "advancement_task",
            },
            {
                "schema_version": "todo_domain_record_v0",
                "todo_id": "todo_archive",
                "role": "user",
                "status": "done",
                "done": True,
                "text": "Preserve archived source ownership.",
                "archive_state": "archive",
                "task_class": "user_action",
            },
        ],
    }


def test_project_current_canonical_todos_is_durable_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry, runtime_root, state_file = _registry(tmp_path)
    monkeypatch.setattr(
        provider_projection,
        "read_canonical_todos_if_promoted",
        lambda **_kwargs: _authority_read(),
    )

    delivered = provider_projection.project_current_canonical_todos(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="goal-a",
    )
    rendered = state_file.read_text(encoding="utf-8")

    assert delivered["status"] == "delivered"
    assert delivered["source"] == "committed_authority_journal"
    assert "Render native provider work." in rendered
    assert "Preserve archived source ownership." in rendered
    assert "role=user" in rendered
    assert "Human-owned introduction." in rendered
    assert "Keep working." in rendered

    replay = provider_projection.project_current_canonical_todos(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="goal-a",
    )
    assert replay["status"] == "current"
    assert replay["changed"] is False
    assert state_file.read_text(encoding="utf-8") == rendered


def test_settlement_preserves_commit_and_replays_after_projection_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry, runtime_root, state_file = _registry(tmp_path)
    monkeypatch.setattr(
        provider_projection,
        "read_canonical_todos_if_promoted",
        lambda **_kwargs: _authority_read(),
    )
    real_write = provider_projection._atomic_write_text
    monkeypatch.setattr(
        provider_projection,
        "_atomic_write_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("crash")),
    )

    committed = provider_projection.settle_canonical_todo_projection(
        {"status": "applied", "changed": True},
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="goal-a",
    )

    assert committed["status"] == "applied"
    assert committed["changed"] is True
    assert committed["projection_delivery"] == "pending"
    assert committed["projection_outbox"] == {
        "schema_version": "loopx_todo_projection_delivery_v0",
        "status": "pending",
        "source": "committed_authority_journal",
        "reason_code": "todo_projection_write_unavailable",
        "error_class": "OSError",
        "retryable": True,
    }
    assert state_file.read_text(encoding="utf-8") == SOURCE

    monkeypatch.setattr(provider_projection, "_atomic_write_text", real_write)
    replay = provider_projection.settle_canonical_todo_projection(
        {"status": "replayed", "changed": False},
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="goal-a",
    )
    assert replay["projection_delivery"] == "delivered"
    assert "Render native provider work." in state_file.read_text(encoding="utf-8")


def test_explicit_projection_fences_requested_revision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry, runtime_root, state_file = _registry(tmp_path)
    monkeypatch.setattr(
        provider_projection,
        "read_canonical_todos_if_promoted",
        lambda **_kwargs: _authority_read(),
    )

    with pytest.raises(ValueError, match="does not match"):
        provider_projection.project_current_canonical_todos(
            registry_path=registry,
            runtime_root=runtime_root,
            goal_id="goal-a",
            expected_provider_revision="file:6:stale",
        )

    assert state_file.read_text(encoding="utf-8") == SOURCE
