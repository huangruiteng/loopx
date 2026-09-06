from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from loopx.control_plane.coordination.local_authority import (
    LocalCoordinationAuthorityRejection,
    LocalCoordinationAuthorityUnavailable,
    claim_canonical_todo_if_promoted,
    read_canonical_todos_if_promoted,
)
from loopx.control_plane.coordination.runtime_shadow import (
    build_todo_runtime_shadow_projection,
)
from loopx.control_plane.effect_runtime import effect_runtime_result
from loopx.control_plane.todos.active_state_editing import TODO_SECTION_HEADINGS
from loopx.control_plane.coordination.legacy_writer_fence import (
    legacy_coordination_writer_fence_path,
)
from loopx.todos import add_goal_todo, list_goal_todos


def _engage_fence(runtime_root: Path, goal_id: str = "goal-a") -> None:
    path = legacy_coordination_writer_fence_path(
        runtime_root=runtime_root,
        goal_id=goal_id,
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"state": "engaged"}), encoding="utf-8")


def _todo_read_model(todo_count: int) -> dict[str, object]:
    return {
        "schema_version": "loopx_todo_canonical_read_record_v0",
        "todo_count": todo_count,
    }


def test_absent_fence_preserves_legacy_path_without_starting_typescript(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        lambda *_args, **_kwargs: pytest.fail("pre-cutover read must stay legacy"),
    )
    assert read_canonical_todos_if_promoted(
        runtime_root=tmp_path,
        goal_id="goal-a",
    ) is None


def test_engaged_fence_reads_typescript_provider_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engage_fence(tmp_path)
    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        lambda method, params: {
            "status": "loaded",
            "todos": [{"todo_id": "todo_a", "role": "agent", "status": "open"}],
            "todo_read_model": _todo_read_model(1),
            "provider_revision": "file:1",
            "cursor": "1",
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        },
    )
    result = read_canonical_todos_if_promoted(
        runtime_root=tmp_path,
        goal_id="goal-a",
    )
    assert result is not None
    assert result["todos"][0]["todo_id"] == "todo_a"


def test_promoted_claim_adapter_invokes_typescript_without_markdown_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goals": [
                    {
                        "id": "goal-a",
                        "coordination": {
                            "registered_agents": ["agent-a", "agent-b"]
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _engage_fence(tmp_path)
    calls: list[tuple[str, dict[str, object]]] = []

    def _claim(method: str, params: dict[str, object]) -> dict[str, object]:
        calls.append((method, params))
        return {
            "status": "applied",
            "changed": True,
            "todo_id": "todo_a",
            "claimed_by": "agent-a",
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        }

    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        _claim,
    )
    result = claim_canonical_todo_if_promoted(
        registry_path=registry,
        runtime_root=tmp_path,
        goal_id="goal-a",
        todo_id="todo_a",
        role="agent",
        claimed_by="agent-a",
        actor_agent_id="agent-a",
        dry_run=False,
    )

    assert result is not None and result["changed"] is True
    assert calls[0][0] == "coordination.local_authority.todo_claim"
    assert calls[0][1]["registered_agents"] == ["agent-a", "agent-b"]
    assert str(calls[0][1]["operation_id"]).startswith(
        "todo-claim:goal-a:todo_a:"
    )
    assert isinstance(calls[0][1]["observed_at"], str)


def test_promoted_add_invokes_native_create_without_markdown_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "schema_version": 1,
        "common_runtime_root": str(tmp_path / "runtime"),
        "goals": [{
            "id": "goal-a",
            "coordination": {"registered_agents": ["agent-a", "agent-b"]},
        }],
    }), encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "loopx.control_plane.todos.provider_create.read_canonical_todos_if_promoted",
        lambda **_kwargs: {"todos": []},
    )

    def _create(method: str, params: dict[str, object]) -> dict[str, object]:
        calls.append((method, params))
        return {
            "status": "applied", "changed": True,
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        }

    monkeypatch.setattr(
        "loopx.control_plane.todos.provider_create.effect_runtime_result", _create
    )
    result = add_goal_todo(
        registry_path=registry, goal_id="goal-a", role="agent",
        text="Create natively", claimed_by="agent-a", agent_id="agent-a",
        task_class="advancement_task", action_kind="implement",
        validation_command_json='["python", "-c", "pass"]',
    )

    assert result["added"] is True
    assert calls[0][0] == "coordination.local_authority.todo_create"
    assert calls[0][1]["todo"]["schema_version"] == "todo_domain_record_v0"
    assert calls[0][1]["todo"]["claimed_by"] == "agent-a"
    assert calls[0][1]["todo"]["validation_command_argv"] == [
        "python", "-c", "pass"
    ]
    assert calls[0][1]["registered_agents"] == ["agent-a", "agent-b"]


def test_promoted_add_delegates_semantic_duplicate_to_typescript(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.todos.provider_create.read_canonical_todos_if_promoted",
        lambda **_kwargs: {"todos": [{
            "todo_id": "todo_existing", "role": "agent", "status": "open",
            "archive_state": "active", "text": "Already native",
        }]},
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def _create(method: str, params: dict[str, object]) -> dict[str, object]:
        calls.append((method, params))
        return {
            "status": "no_change", "changed": False,
            "todo_id": "todo_existing", "source_authority": "file_v0",
            "decision_read_from_provider": True, "legacy_fallback_used": False,
        }

    monkeypatch.setattr(
        "loopx.control_plane.todos.provider_create.effect_runtime_result", _create,
    )
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "schema_version": 1,
        "goals": [{"id": "goal-a", "coordination": {
            "registered_agents": ["agent-a"]
        }}],
    }), encoding="utf-8")

    result = add_goal_todo(
        registry_path=registry, goal_id="goal-a", role="agent",
        text="Already native", claimed_by="agent-a", agent_id="agent-a",
    )

    assert result["already_exists"] is True
    assert result["todo_id"] == "todo_existing"
    assert calls[0][0] == "coordination.local_authority.todo_create"


def test_engaged_fence_never_falls_back_when_provider_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engage_fence(tmp_path)
    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        lambda method, params: {
            "status": "missing",
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        },
    )
    with pytest.raises(LocalCoordinationAuthorityUnavailable) as exc_info:
        read_canonical_todos_if_promoted(runtime_root=tmp_path, goal_id="goal-a")
    assert exc_info.value.code == "local_authority_todo_list_unavailable"


def _claim_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goals": [
                    {
                        "id": "goal-a",
                        "coordination": {"registered_agents": ["agent-a"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry


def _seed_promoted_store(runtime_root: Path) -> None:
    """Promote one open agent Todo through the real TypeScript runtime."""

    projection = build_todo_runtime_shadow_projection(
        goal_id="goal-a",
        todos=[
            {
                "schema_version": "todo_item_v0",
                "index": 1,
                "done": False,
                "text": "Claim through the promoted provider head",
                "todo_id": "todo_a",
                "role": "agent",
                "status": "open",
                "archive_state": "active",
                "source_section": TODO_SECTION_HEADINGS["agent"],
            }
        ],
    )
    canonical_bytes = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    projection_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
    bootstrap = effect_runtime_result(
        "coordination.runtime_shadow.bootstrap",
        {
            "schema_version": "loopx_coordination_runtime_shadow_bootstrap_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "operation_id": "bootstrap:goal-a:f34",
            "source_version": "state:f34:0",
            "projection": projection,
        },
    )
    assert bootstrap["status"] == "applied"
    mirrored = effect_runtime_result(
        "coordination.runtime_shadow.commit",
        {
            "schema_version": "loopx_coordination_runtime_shadow_commit_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "operation_id": "todo:goal-a:f34:qualify",
            "event_kind": "todo_update",
            "source_version": "state:f34:1",
            "projection": projection,
        },
    )
    assert mirrored["status"] == "applied"
    provider_revision = str(mirrored["provider_revision"])
    fence = {
        "schema_version": "loopx_legacy_coordination_writer_fence_v0",
        "state": "engaged",
        "goal_id": "goal-a",
        "fence_id": "legacy-writer-fence:goal-a:f34",
        "source_version": "state:f34:1",
        "source_projection_sha256": projection_sha256,
        "expected_shadow_provider_revision": provider_revision,
    }
    engaged = effect_runtime_result(
        "coordination.local_authority.legacy_writer_fence.engage",
        {
            "schema_version": "loopx_legacy_coordination_writer_fence_engage_request_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "fence": fence,
        },
    )
    assert engaged["status"] == "applied"
    promoted = effect_runtime_result(
        "coordination.local_authority.promote",
        {
            "schema_version": "loopx_local_coordination_promotion_request_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "operation_id": "promote:goal-a:f34",
            "expected_shadow_provider_revision": provider_revision,
            "expected_shadow_projection_sha256": projection_sha256,
            "minimum_operations": 1,
            "required_event_kinds": ["todo_update"],
            "writer_fence": fence,
        },
    )
    assert promoted["status"] == "applied"


def test_promoted_claim_rejection_preserves_legacy_valueerror_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Promoted claim rejections must stay catchable via ``except ValueError``.

    The legacy kernel raised ValueError for decision rejections such as
    todo_not_open; external Python API callers rely on that contract.
    """
    _engage_fence(tmp_path)
    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        lambda method, params: {
            "status": "failed",
            "reason_code": "todo_not_open",
            "reason": "todo claim requires status=open",
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        },
    )
    with pytest.raises(ValueError) as exc_info:
        claim_canonical_todo_if_promoted(
            registry_path=_claim_registry(tmp_path),
            runtime_root=tmp_path,
            goal_id="goal-a",
            todo_id="todo_a",
            role="agent",
            claimed_by="agent-a",
            actor_agent_id="agent-a",
            dry_run=False,
        )
    rejection = exc_info.value
    assert isinstance(rejection, LocalCoordinationAuthorityRejection)
    # Callers that already migrated to the authority-unavailable handling of
    # promoted claims keep working: the rejection is still its subclass.
    assert isinstance(rejection, LocalCoordinationAuthorityUnavailable)
    assert rejection.code == "todo_not_open"
    assert str(rejection) == "todo claim requires status=open"


def test_promoted_claim_protocol_failure_stays_infrastructure_outage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Protocol-level request failures must not masquerade as ValueErrors."""
    _engage_fence(tmp_path)
    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        lambda method, params: {
            "status": "failed",
            "reason_code": "invalid_local_coordination_todo_claim_request",
            "reason": "registered_agents must be a JSON array",
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        },
    )
    with pytest.raises(LocalCoordinationAuthorityUnavailable) as exc_info:
        claim_canonical_todo_if_promoted(
            registry_path=_claim_registry(tmp_path),
            runtime_root=tmp_path,
            goal_id="goal-a",
            todo_id="todo_a",
            role="agent",
            claimed_by="agent-a",
            actor_agent_id="agent-a",
            dry_run=False,
        )
    assert exc_info.value.code == "invalid_local_coordination_todo_claim_request"
    assert not isinstance(exc_info.value, ValueError)
    assert not isinstance(exc_info.value, LocalCoordinationAuthorityRejection)


def test_promoted_claim_folds_agent_id_whitespace_like_legacy(tmp_path: Path) -> None:
    """Tabs in claimed_by must fold to "-" before and after promotion alike.

    Legacy normalize_todo_claimed_by collapses any whitespace run (Python
    compact_todo_text) to a single "-"; the TypeScript owner now folds the
    same way, so the identical claim command keeps succeeding post-cutover.
    """
    _seed_promoted_store(tmp_path)
    result = claim_canonical_todo_if_promoted(
        registry_path=_claim_registry(tmp_path),
        runtime_root=tmp_path,
        goal_id="goal-a",
        todo_id="todo_a",
        role="agent",
        claimed_by="Agent\tA",
        actor_agent_id=None,
        dry_run=False,
    )
    assert result is not None and result["ok"] is True
    assert result["status"] == "applied"
    assert result["claimed_by"] == "agent-a"


def test_promoted_claim_missing_todo_rejection_is_valueerror(tmp_path: Path) -> None:
    """End-to-end: a real TypeScript decision rejection raises ValueError."""
    _seed_promoted_store(tmp_path)
    with pytest.raises(ValueError) as exc_info:
        claim_canonical_todo_if_promoted(
            registry_path=_claim_registry(tmp_path),
            runtime_root=tmp_path,
            goal_id="goal-a",
            todo_id="todo_missing",
            role="agent",
            claimed_by="agent-a",
            actor_agent_id="agent-a",
            dry_run=False,
        )
    assert isinstance(exc_info.value, LocalCoordinationAuthorityRejection)
    assert exc_info.value.code == "todo_not_found"


def test_todo_list_uses_provider_after_cutover_even_when_markdown_disagrees(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    state_file = project / ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "# Goal\n\n## Agent Todos\n\n- [ ] stale Markdown Todo <!-- loopx:todo todo_id=todo_stale status=open -->\n",
        encoding="utf-8",
    )
    runtime_root = tmp_path / "runtime"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": "goal-a",
                        "status": "active",
                        "repo": str(project),
                        "state_file": ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md",
                        "coordination": {
                            "registered_agents": ["agent-a", "agent-b"]
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _engage_fence(runtime_root)
    state_file.unlink()
    monkeypatch.setattr(
        "loopx.control_plane.coordination.local_authority.effect_runtime_result",
        lambda method, params: {
            "status": "loaded",
            "todos": [
                {
                    "todo_id": "todo_provider",
                    "role": "agent",
                    "status": "open",
                    "text": "provider Todo",
                }
            ],
            "todo_read_model": _todo_read_model(1),
            "provider_revision": "file:2",
            "cursor": "2",
            "source_authority": "file_v0",
            "decision_read_from_provider": True,
            "legacy_fallback_used": False,
        },
    )

    result = list_goal_todos(registry_path=registry_path, goal_id="goal-a")

    assert result["source"] == "file_authority"
    assert [item["todo_id"] for item in result["todos"]] == ["todo_provider"]
    assert result["authority_read"]["legacy_fallback_used"] is False


def test_real_shadow_projection_promotes_complete_complex_todo_semantics(
    tmp_path: Path,
) -> None:
    """Exercise builder -> shadow -> promotion -> production Todo list."""

    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    state_file = project / ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("# Goal\n", encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": "goal-a",
                        "status": "active",
                        "repo": str(project),
                        "state_file": ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md",
                        "coordination": {
                            "registered_agents": ["agent-a", "agent-b"]
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    complex_todo = {
        "schema_version": "todo_item_v0",
        "index": 7,
        "done": False,
        "text": "Qualify provider cutover on a complex Goal",
        "title": "Provider semantic parity",
        "todo_id": "todo_complex",
        "role": "agent",
        "status": "deferred",
        "priority": "P0",
        "archive_state": "active",
        "source_section": TODO_SECTION_HEADINGS["agent"],
        "task_class": "continuous_monitor",
        "action_kind": "monitor",
        "task_domain": "control_plane",
        "task_repository": "loopx",
        "continuation_policy": "continue_goal",
        "claimed_by": "agent-a",
        "excluded_agents": ["agent-b"],
        "resume_when": "material_change",
        "resume_ready": False,
        "cadence": "weekly",
        "next_due_at": "2026-09-07T09:00:00+08:00",
        "expires_at": "2026-10-01T00:00:00+08:00",
        "watch_only": True,
        "material_change": False,
        "material_change_generation": 4,
        "consecutive_no_change": 2,
        "max_no_change_before_replan": 3,
        "successor_todo_ids": ["todo_successor"],
        "note": "keep operator context",
        "evidence": "semantic fixture evidence",
        "updated_at": "2026-09-04T10:00:00+08:00",
    }
    successor = {
        "schema_version": "todo_item_v0",
        "index": 8,
        "done": True,
        "text": "Preserve completion semantics",
        "title": "Completion evidence",
        "todo_id": "todo_successor",
        "role": "agent",
        "status": "done",
        "priority": "P1",
        "archive_state": "active",
        "source_section": TODO_SECTION_HEADINGS["agent"],
        "completion_continuation": "no_followup",
        "completed_at": "2026-09-03T18:00:00+08:00",
        "completion_turn_key": "turn-complete",
    }
    claimable = {
        "schema_version": "todo_item_v0",
        "index": 9,
        "done": False,
        "text": "Claim directly against the promoted provider head",
        "todo_id": "todo_claimable",
        "role": "agent",
        "status": "open",
        "archive_state": "active",
        "source_section": TODO_SECTION_HEADINGS["agent"],
        "priority": "P0",
        "action_kind": "implement",
        "note": "this complete record must survive the claim",
    }
    projection = build_todo_runtime_shadow_projection(
        goal_id="goal-a",
        todos=[complex_todo, successor, claimable],
    )
    canonical_bytes = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    projection_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    bootstrap = effect_runtime_result(
        "coordination.runtime_shadow.bootstrap",
        {
            "schema_version": "loopx_coordination_runtime_shadow_bootstrap_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "operation_id": "bootstrap:goal-a:complex",
            "source_version": "state:complex:0",
            "projection": projection,
        },
    )
    assert bootstrap["status"] == "applied"
    mirrored = effect_runtime_result(
        "coordination.runtime_shadow.commit",
        {
            "schema_version": "loopx_coordination_runtime_shadow_commit_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "operation_id": "todo:goal-a:complex:qualify",
            "event_kind": "todo_update",
            "source_version": "state:complex:1",
            "projection": projection,
        },
    )
    assert mirrored["status"] == "applied"
    provider_revision = str(mirrored["provider_revision"])
    fence = {
        "schema_version": "loopx_legacy_coordination_writer_fence_v0",
        "state": "engaged",
        "goal_id": "goal-a",
        "fence_id": "legacy-writer-fence:goal-a:complex",
        "source_version": "state:complex:1",
        "source_projection_sha256": projection_sha256,
        "expected_shadow_provider_revision": provider_revision,
    }
    engaged = effect_runtime_result(
        "coordination.local_authority.legacy_writer_fence.engage",
        {
            "schema_version": "loopx_legacy_coordination_writer_fence_engage_request_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "fence": fence,
        },
    )
    assert engaged["status"] == "applied"
    promoted = effect_runtime_result(
        "coordination.local_authority.promote",
        {
            "schema_version": "loopx_local_coordination_promotion_request_v0",
            "runtime_root": str(runtime_root),
            "goal_id": "goal-a",
            "operation_id": "promote:goal-a:complex",
            "expected_shadow_provider_revision": provider_revision,
            "expected_shadow_projection_sha256": projection_sha256,
            "minimum_operations": 1,
            "required_event_kinds": ["todo_update"],
            "writer_fence": fence,
        },
    )
    assert promoted["status"] == "applied"

    state_file.unlink()
    result = list_goal_todos(registry_path=registry_path, goal_id="goal-a")
    by_id = {item["todo_id"]: item for item in result["todos"]}
    for field in (
        "text",
        "title",
        "priority",
        "source_section",
        "archive_state",
        "continuation_policy",
        "resume_when",
        "cadence",
        "next_due_at",
        "expires_at",
        "watch_only",
        "material_change_generation",
        "successor_todo_ids",
        "note",
        "evidence",
    ):
        assert by_id["todo_complex"][field] == complex_todo[field]
    assert by_id["todo_successor"]["completed_at"] == successor["completed_at"]
    assert by_id["todo_successor"]["completion_continuation"] == "no_followup"
    assert result["authority_read"]["todo_read_model"]["todo_count"] == 3

    # The public compatibility CLI must retain claim-neutral text correction
    # after promotion; it must not reconstruct or write the Markdown source.
    correction_command = [
        sys.executable, "-m", "loopx.cli", "--format", "json",
        "--registry", str(registry_path), "todo", "update", "--goal-id", "goal-a",
        "--todo-id", "todo_claimable", "--agent-id", "agent-b",
        "--text", "Corrected before claiming",
    ]
    correction = subprocess.run(correction_command, capture_output=True, text=True,
                                check=True, timeout=30)
    assert json.loads(correction.stdout)["ok"] is True
    corrected = list_goal_todos(registry_path=registry_path, goal_id="goal-a")
    corrected_item = next(item for item in corrected["todos"]
                          if item["todo_id"] == "todo_claimable")
    assert corrected_item["text"] == "Corrected before claiming"
    assert not corrected_item.get("claimed_by")
    assert corrected_item["last_actor_agent_id"] == "agent-b"
    assert not state_file.exists()

    # A note-only CLI edit must survive an independent provider readback too;
    # accepting the option or exercising the text branch cannot prove this.
    note_command = [*correction_command[:-2], "--note", "Correction context"]
    note_result = subprocess.run(
        note_command, capture_output=True, text=True, check=True, timeout=30
    )
    assert json.loads(note_result.stdout)["ok"] is True
    noted = list_goal_todos(registry_path=registry_path, goal_id="goal-a")
    noted_item = next(
        item for item in noted["todos"] if item["todo_id"] == "todo_claimable"
    )
    assert noted_item["note"] == "Correction context"
    assert noted_item["text"] == "Corrected before claiming"
    assert not noted_item.get("claimed_by")
    assert not state_file.exists()

    claim_command = [
        sys.executable, "-m", "loopx.cli", "--format", "json",
        "--registry", str(registry_path), "todo", "claim", "--goal-id", "goal-a",
        "--todo-id", "todo_claimable", "--claimed-by", "agent-a", "--agent-id", "agent-a",
        "--claim-operation-id", "initial-cli-claim",
    ]
    # Duplicate callers race from separate processes, but one operation must
    # produce exactly one accepted claim and the same durable receipt.
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(subprocess.run, claim_command,
            capture_output=True, text=True, check=True, timeout=30) for _ in range(2)]
        claims = [json.loads(attempt.result().stdout) for attempt in attempts]
    assert sum(item["status"] == "applied" for item in claims) == 1
    assert all(item["status"] in {"applied", "recovered", "replayed"} for item in claims)
    assert claims[0]["original_receipt"] == claims[1]["original_receipt"]
    assert claims[0]["provider_revision"] == claims[1]["provider_revision"]
    claimed = next(item for item in claims if item["status"] == "applied")
    assert claimed["ok"] is True
    assert claimed["source_authority"] == "file_v0"
    assert claimed["legacy_fallback_used"] is False
    assert claimed["mutation_authority"]["mode"] == "registered_peer_actor"

    after_claim = list_goal_todos(registry_path=registry_path, goal_id="goal-a")
    claimed_item = next(
        item for item in after_claim["todos"] if item["todo_id"] == "todo_claimable"
    )
    assert claimed_item["claimed_by"] == "agent-a"

    # Separate CLI processes must replay one durable operation, not mint a
    # fresh receipt for every retry. Preview does not consume that identity.
    claim_command = [*claim_command[:-1], "retryable-cli-claim"]
    preview = json.loads(subprocess.run(
        [*claim_command, "--dry-run"], capture_output=True, text=True, check=True,
    ).stdout)
    assert preview["dry_run"] is True
    original = json.loads(subprocess.run(
        claim_command, capture_output=True, text=True, check=True,
    ).stdout)
    replay = json.loads(subprocess.run(
        claim_command, capture_output=True, text=True, check=True,
    ).stdout)
    assert original["status"] == "no_change"
    assert replay["status"] == "replayed"
    assert replay["original_receipt"] == original["original_receipt"]
    assert replay["provider_revision"] == original["provider_revision"]
    changed_intent = ["agent-b" if part == "agent-a" else part for part in claim_command]
    rejected = subprocess.run(changed_intent, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert json.loads(rejected.stdout)["error"] == "operation id already names a different coordination request"
    for invalid_key in ("", " padded-operation "):
        invalid = subprocess.run([*claim_command[:-1], invalid_key], capture_output=True, text=True)
        assert invalid.returncode != 0
    assert not state_file.exists()

    create_command = [
        sys.executable, "-m", "loopx.cli", "--format", "json",
        "--registry", str(registry_path), "todo", "add", "--goal-id", "goal-a",
        "--role", "agent", "--text", "Create directly against promoted provider",
        "--claimed-by", "agent-a",
        "--task-class", "advancement_task", "--action-kind", "implement",
    ]
    create_preview = subprocess.run(
        [*create_command, "--dry-run"], capture_output=True, text=True, check=True,
    )
    assert json.loads(create_preview.stdout)["status"] == "planned"
    assert not state_file.exists()
    created = json.loads(subprocess.run(
        create_command, capture_output=True, text=True, check=True,
    ).stdout)
    assert created["ok"] is True
    assert created["source_authority"] == "file_v0"
    assert created["legacy_fallback_used"] is False
    assert not state_file.exists()

    after_create = list_goal_todos(registry_path=registry_path, goal_id="goal-a")
    created_item = next(
        item for item in after_create["todos"] if item["todo_id"] == created["todo_id"]
    )
    assert created_item["text"] == "Create directly against promoted provider"
    assert created_item["claimed_by"] == "agent-a"
    assert after_create["authority_read"]["todo_read_model"]["todo_count"] == 4
    assert claimed_item["note"] == "Correction context"

    # Real CLI, no Markdown file: provider data feeds an in-memory editor and
    # only requested fields return through TS CAS. Complex sibling fields do
    # not round-trip through the lossy Markdown representation.
    command = [sys.executable, "-m", "loopx.cli", "--format", "json",
               "--registry", str(registry_path), "todo", "update", "--goal-id", "goal-a",
               "--todo-id", "todo_claimable", "--agent-id", "agent-a",
               "--text", "Edit provider-owned work", "--note", "compatibility edit"]
    preview = subprocess.run([*command, "--dry-run"], capture_output=True, text=True, check=True)
    assert json.loads(preview.stdout)["status"] == "planned"
    assert list_goal_todos(registry_path=registry_path, goal_id="goal-a")["todos"] == after_create["todos"]
    edited = subprocess.run(command, capture_output=True, text=True, check=True)
    edit_result = json.loads(edited.stdout)
    assert edit_result["status"] == "applied"
    assert edit_result["projection_delivery"] == "pending"
    assert not state_file.exists()
    after_edit = list_goal_todos(registry_path=registry_path, goal_id="goal-a")
    edited_by_id = {item["todo_id"]: item for item in after_edit["todos"]}
    assert edited_by_id["todo_claimable"] == {
        **claimed_item, "text": "Edit provider-owned work", "note": "compatibility edit",
        "last_actor_agent_id": "agent-a",
        "updated_at": edited_by_id["todo_claimable"]["updated_at"],
    }
    assert edited_by_id["todo_claimable"]["updated_at"] != claimed_item["updated_at"]
    assert edited_by_id["todo_complex"] == by_id["todo_complex"]
    assert edited_by_id["todo_successor"] == by_id["todo_successor"]
