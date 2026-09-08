"""Recover the display through the public CLI without repairing authority."""
from __future__ import annotations

import json
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from canonical_authority_fixture import initialize_canonical_authority
from loopx.control_plane.coordination.local_authority import read_canonical_todos_if_promoted
from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection
from loopx.control_plane.coordination.coordination_state_contract import (
    TODO_DOMAIN_READ_RECORD_SCHEMA_VERSION, TODO_DOMAIN_RECORD_FIELDS,
)
from loopx.control_plane.coordination.local_authority_shadow_projection import canonical_bytes
from loopx.control_plane.todos import provider_projection
from loopx.control_plane.todos.completion_validation_store import (
    persist_completion_validation_declaration,
)


@pytest.fixture
def canonical_display(tmp_path):
    state = tmp_path / "state.md"
    state.write_text("# Goal\n\nAgent-generated acceptance is not in the Todo store.\n\n## Agent Todo\n")
    runtime = tmp_path / "runtime"
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "common_runtime_root": str(runtime),
        "goals": [{"id": "goal-a", "repo": str(tmp_path), "state_file": state.name,
                   "coordination": {"registered_agents": ["agent-a"]}}],
    }))
    records = [
        {"schema_version": "todo_item_v0", "todo_id": "todo_active", "role": "agent",
         "status": "open", "done": False, "text": "Retain the current claim.",
         "task_class": "advancement_task",
         "archive_state": "active", "source_section": "Agent Todo", "index": 1,
         "claimed_by": "agent-a"},
        {"schema_version": "todo_item_v0", "todo_id": "todo_archived", "role": "user",
         "status": "done", "done": True, "text": "Retain the historical decision.",
         "archive_state": "archive", "source_section": "Completed Work Archive", "index": 1},
    ]
    projection = build_todo_runtime_shadow_projection(goal_id="goal-a", todos=records, handoff_mode="soft_claim")
    for record in projection["todos"]:
        record["schema_version"] = "todo_domain_record_v0"
        record.pop("index")
        record.pop("source_section")
    projection["todo_read_model"] = {
        "schema_version": TODO_DOMAIN_READ_RECORD_SCHEMA_VERSION,
        "contract_fields": list(TODO_DOMAIN_RECORD_FIELDS),
        "todo_count": len(records),
        "records_sha256": hashlib.sha256(canonical_bytes(projection["todos"])).hexdigest(),
    }
    initialize_canonical_authority(runtime, "goal-a", projection, state_path=state)
    return registry, runtime, state


def _read(runtime):
    return read_canonical_todos_if_promoted(runtime_root=runtime, goal_id="goal-a")


def _cli(registry: Path, *options: str):
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--registry", str(registry), "--format", "json",
         "todo", *options],
        capture_output=True, text=True, timeout=60, check=False,
    )
    return result.returncode, json.loads(result.stdout) if result.stdout else result.stderr


def _run(registry: Path, revision: str, *options: str):
    return _cli(registry, "project-markdown", "--goal-id", "goal-a",
                "--provider-revision", revision, *options)


def test_public_rebuild_missing_preview_execute_and_replay(canonical_display):
    registry, runtime, state = canonical_display
    before = _read(runtime)
    state.unlink()
    revision = before["provider_revision"]
    code, preview = _run(registry, revision)
    assert code == 0, preview
    assert preview["dry_run"] is True
    assert preview["narrative_preserved"] is False
    assert preview["recovery_scope"] == "todo_sections_only"
    assert not state.exists()
    code, delivered = _run(registry, revision, "--execute")
    assert code == 0, delivered
    assert delivered["status"] == "delivered"
    assert delivered["narrative_preserved"] is False
    text = state.read_text()
    assert "todo_active" in text and "todo_archived" in text
    assert "claimed_by=agent-a" in text
    assert "Agent-generated acceptance is not in the Todo store." not in text
    assert "not recovered" in text
    if os.name == "posix":
        assert stat.S_IMODE(state.stat().st_mode) == 0o600
    code, replay = _run(registry, revision, "--execute")
    assert code == 0 and replay["status"] == "current", replay
    assert state.read_text() == text
    assert _read(runtime) == before


def test_committed_update_automatically_recovers_missing_display(canonical_display):
    registry, runtime, state = canonical_display
    state.unlink()
    code, result = _cli(
        registry, "update", "--goal-id", "goal-a", "--role", "agent",
        "--todo-id", "todo_active", "--agent-id", "agent-a", "--text", "Committed without a display.",
    )
    assert code == 0, json.dumps(result)
    assert result["projection_delivery"] == "delivered"
    assert result["projection_outbox"]["recovery_scope"] == "todo_sections_only"
    committed = _read(runtime)
    assert committed["todos"][0]["text"] == "Committed without a display."
    code, repaired = _run(registry, committed["provider_revision"], "--execute")
    assert code == 0, repaired
    assert "Committed without a display." in state.read_text()
    assert _read(runtime) == committed  # Recovery did not repeat the business transaction.


@pytest.mark.parametrize("case", ["stale_revision", "no_provider"])
def test_rebuild_requires_exact_available_authority(canonical_display, case):
    registry, runtime, state = canonical_display
    before = _read(runtime)
    state.unlink()
    revision = "stale-revision" if case == "stale_revision" else before["provider_revision"]
    if case == "no_provider":
        (runtime / "authority" / "file-v0").rename(runtime / "unavailable")
    code, result = _run(registry, revision, "--execute")
    assert code == 1, result
    assert not state.exists()
    if case == "stale_revision":
        assert "does not match" in result["error"]
    else:
        (runtime / "unavailable").rename(runtime / "authority" / "file-v0")
    assert _read(runtime) == before


@pytest.mark.parametrize("source", [
    b"\xffgenerated document",
    b"## Agent Todo\n<!-- loopx:todo-region-v0 role=agent begin -->\nUnstructured content\n",
])
def test_rebuild_never_discards_an_existing_damaged_document(canonical_display, source):
    registry, runtime, state = canonical_display
    before = _read(runtime)
    state.write_bytes(source)
    code, result = _run(registry, before["provider_revision"], "--execute")
    assert code == 1, result
    assert state.read_bytes() == source
    assert _read(runtime) == before


def test_recovery_preserves_existing_generated_non_todo_sections(canonical_display):
    registry, runtime, state = canonical_display
    source = state.read_bytes()
    revision = _read(runtime)["provider_revision"]
    code, result = _run(registry, revision, "--execute")
    assert code == 0, result
    assert result["narrative_preserved"] is True
    assert "recovery_scope" not in result
    assert state.read_bytes().startswith(source.split(b"## Agent Todo")[0])


def test_concurrent_document_restoration_is_not_overwritten(canonical_display, monkeypatch):
    registry, runtime, state = canonical_display
    before = _read(runtime)
    state.unlink()
    real_link = os.link

    def restore_before_publish(source, destination):
        Path(destination).write_text("Another writer concurrently restored the generated document.\n")
        return real_link(source, destination)

    monkeypatch.setattr(provider_projection.os, "link", restore_before_publish)
    with pytest.raises(FileExistsError):
        provider_projection.project_current_canonical_todos(
            registry_path=registry, runtime_root=runtime, goal_id="goal-a",
            expected_provider_revision=before["provider_revision"],
        )
    assert state.read_text() == "Another writer concurrently restored the generated document.\n"
    assert not list(state.parent.glob(".state.md.*.tmp"))
    assert _read(runtime) == before


@pytest.mark.parametrize("failure_point", ["fsync", "link", "directory_fsync"])
def test_interrupted_rebuild_is_safe_and_retryable(canonical_display, monkeypatch, failure_point):
    registry, runtime, state = canonical_display
    before = _read(runtime)
    state.unlink()

    def fail(*_args):
        raise OSError("injected publication failure")

    with monkeypatch.context() as patch:
        if failure_point == "directory_fsync":
            patch.setattr(provider_projection, "_fsync_parent_directory", fail)
        else:
            patch.setattr(provider_projection.os, failure_point, fail)
        with pytest.raises(OSError, match="injected publication failure"):
            provider_projection.project_current_canonical_todos(
                registry_path=registry, runtime_root=runtime, goal_id="goal-a",
                expected_provider_revision=before["provider_revision"],
            )
    assert not list(state.parent.glob(".state.md.*.tmp"))
    assert state.exists() is (failure_point == "directory_fsync")
    code, repaired = _run(registry, before["provider_revision"], "--execute")
    assert code == 0, repaired
    assert "todo_active" in state.read_text() and "todo_archived" in state.read_text()
    assert _read(runtime) == before


def test_todo_read_does_not_write_a_missing_display(canonical_display):
    registry, runtime, state = canonical_display
    before = _read(runtime)
    state.unlink()
    code, result = _cli(registry, "list", "--goal-id", "goal-a")
    assert code == 0, result
    assert not state.exists()
    assert _read(runtime) == before


def test_unpromoted_missing_document_is_not_regenerated(canonical_display):
    from loopx.control_plane.coordination.legacy_writer_fence import legacy_coordination_writer_fence_path

    registry, runtime, state = canonical_display
    revision = _read(runtime)["provider_revision"]
    state.unlink()
    legacy_coordination_writer_fence_path(runtime_root=runtime, goal_id="goal-a").unlink()
    code, result = _run(registry, revision, "--execute")
    assert code == 1 and "requires promoted canonical authority" in result["error"]
    assert not state.exists()


def test_production_scale_rebuild_retains_order_and_requires_private_declaration(tmp_path):
    # Reuse the shared RFC envelope, not a second large fixture or live data.
    script = (
        "import {productionScaleCoordinationFixture, PRODUCTION_SCALE_VALIDATION_DECLARATION} "
        "from './tests/control_plane_ts/production_scale_coordination_fixture.ts';"
        "process.stdout.write(JSON.stringify({fixture:productionScaleCoordinationFixture('goal-a'),"
        "declaration:PRODUCTION_SCALE_VALIDATION_DECLARATION}));"
    )
    generated = subprocess.run(
        ["node", "--no-warnings", "--experimental-strip-types", "--input-type=module", "-e", script],
        capture_output=True, text=True, check=True, timeout=30,
    )
    data = json.loads(generated.stdout)
    projection = data["fixture"]["projection"]
    runtime, state, registry = tmp_path / "runtime", tmp_path / "state.md", tmp_path / "registry.json"
    state.write_text("## Agent Todo\n")
    registry.write_text(json.dumps({"common_runtime_root": str(runtime), "goals": [
        {"id": "goal-a", "repo": str(tmp_path), "state_file": state.name},
    ]}))
    initialize_canonical_authority(runtime, "goal-a", projection, state_path=state)
    before = _read(runtime)
    state.unlink()
    code, rejected = _run(registry, before["provider_revision"], "--execute")
    assert code == 1 and "private validation declaration" in rejected["error"]
    assert not state.exists()  # Do not erase a validation obligation to make recovery pass.
    persist_completion_validation_declaration(
        runtime_root=runtime, goal_id="goal-a", todo_id=data["fixture"]["completion_todo_id"],
        declaration=data["declaration"],
    )
    code, result = _run(registry, before["provider_revision"], "--execute")
    assert code == 0, result
    assert result["todo_count"] == 464
    rendered = state.read_text()
    for role, count in (("agent", 256), ("user", 208)):
        positions = [rendered.index(f"todo_id=todo_fixture_{role}_{index:03d} ") for index in range(count)]
        assert positions == sorted(positions)
    assert _read(runtime) == before
    code, replay = _run(registry, before["provider_revision"], "--execute")
    assert code == 0 and replay["changed"] is False
