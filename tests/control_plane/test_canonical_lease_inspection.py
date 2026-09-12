"""A public lease read must not mix promoted authority with obsolete files."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from canonical_authority_fixture import initialize_canonical_authority, isolate_sqlite_runtime
from loopx.control_plane.coordination.local_authority import (
    LocalCoordinationAuthorityUnavailable,
    read_canonical_todos_if_promoted,
)
from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection
from loopx.control_plane.work_items.task_lease import inspect_task_lease

GOAL = "goal-lease-reader"
TODO = "todo_current"


def _fixture(root: Path, provider: str, *, retained: bool = True, excluded: bool = False):
    runtime = root / "runtime"
    state = root / "ACTIVE_GOAL_STATE.md"
    state.write_text("---\nhandoff_mode: soft_claim\n---\n# Obsolete display\n")
    registry = root / "registry.json"
    registry.write_text(json.dumps({"schema_version": 1, "common_runtime_root": str(runtime), "goals": [{
        "id": GOAL, "repo": str(root), "state_file": str(state),
        "coordination": {"registered_agents": ["agent-a", "agent-b"]}}]}))
    todo = {"schema_version": "todo_item_v0", "source_section": "Agent Todo",
            "todo_id": TODO, "role": "agent", "text": "Verify canonical ownership",
            "status": "open", "done": False, "archive_state": "active", "task_class": "advancement_task",
            "excluded_agents": ["agent-a"] if excluded else []}
    lease = {"schema_version": "task_lease_v0", "goal_id": GOAL, "todo_id": TODO,
             "status": "active", "owner": "agent-a", "idempotency_key": "lease-first",
             "expires_at": "2099-01-01T00:00:00Z", "lease_epoch": 3, "version": 2}
    projection = build_todo_runtime_shadow_projection(goal_id=GOAL, todos=[todo],
        leases=[lease] if retained else [], handoff_mode="hard_lease")
    initialize_canonical_authority(runtime, GOAL, projection, state_path=state, provider=provider)
    obsolete = runtime / "goals" / GOAL / "task-leases" / f"{TODO}.json"
    obsolete.parent.mkdir(parents=True, exist_ok=True)
    obsolete.write_text(json.dumps({**lease, "owner": "agent-b", "version": 999}))
    return registry, runtime, state, obsolete


def _inspect(registry, runtime):
    return inspect_task_lease(registry_path=registry, runtime_root=runtime, goal_id=GOAL, todo_id=TODO)


@pytest.mark.parametrize("provider", ["file", "sqlite"])
@pytest.mark.parametrize("display", ["stale", "missing", "malformed"])
@pytest.mark.parametrize("retained", [False, True])
def test_public_inspect_uses_one_revision_and_never_revives_obsolete_files(tmp_path, monkeypatch, provider, display, retained):
    isolate_sqlite_runtime(tmp_path, monkeypatch)
    registry, runtime, state, obsolete = _fixture(tmp_path, provider, retained=retained)
    if display == "missing":
        state.unlink()
    elif display == "malformed":
        state.write_text("invalid display")
        obsolete.write_text("invalid obsolete lease")
    before = read_canonical_todos_if_promoted(runtime_root=runtime, goal_id=GOAL, include_leases=True)
    obsolete_before = obsolete.read_bytes()
    result = _inspect(registry, runtime)
    assert result["ok"] is True
    assert result["active"] is retained
    assert result["handoff_mode"] == "hard_lease"
    assert result["lease_path"] is None
    assert result["legacy_fallback_used"] is False
    assert result["provider_revision"] == before["provider_revision"]
    if retained:
        assert result["lease"]["owner"] == "agent-a"
        assert result["lease"]["version"] == 2
    else:
        assert result["lease"] is None
    process = subprocess.run([sys.executable, "-m", "loopx.cli", "--registry", str(registry),
        "--format", "json", "task-lease", "inspect", "--goal-id", GOAL, "--todo-id", TODO],
        capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr + process.stdout
    assert json.loads(process.stdout) == result
    assert read_canonical_todos_if_promoted(runtime_root=runtime, goal_id=GOAL, include_leases=True) == before
    assert obsolete.read_bytes() == obsolete_before
    assert state.exists() is (display != "missing")


@pytest.mark.parametrize("provider", ["file", "sqlite"])
def test_active_but_excluded_owner_is_not_effective(tmp_path, monkeypatch, provider):
    isolate_sqlite_runtime(tmp_path, monkeypatch)
    registry, runtime, _, _ = _fixture(tmp_path, provider, excluded=True)
    result = _inspect(registry, runtime)
    assert result["active"] is False
    assert result["lease"]["status"] == "active"
    assert result["executor_constraint"]["reason"] == "owner_excluded_from_todo"


def test_unavailable_provider_fails_instead_of_reading_legacy_lease(tmp_path):
    registry, runtime, _, obsolete = _fixture(tmp_path, "file")
    authority = runtime / "authority" / "file-v0"
    authority.rename(authority.with_name("offline-fixture"))
    with pytest.raises(LocalCoordinationAuthorityUnavailable) as error:
        _inspect(registry, runtime)
    assert getattr(error.value, "code", "").startswith("local_authority_")
    assert json.loads(obsolete.read_text())["owner"] == "agent-b"
