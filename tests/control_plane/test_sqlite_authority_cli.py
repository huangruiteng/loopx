"""Real CLI consumers with SQLite authority and no Markdown source."""
import hashlib
import os
import json
import subprocess
import sys

from canonical_authority_fixture import initialize_canonical_authority
from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection
from loopx.control_plane.coordination.coordination_state_contract import TODO_DOMAIN_READ_RECORD_SCHEMA_VERSION, TODO_DOMAIN_RECORD_FIELDS
from loopx.control_plane.coordination.local_authority_shadow_projection import canonical_bytes


def test_sqlite_cli_reopens_updates_and_recovers_missing_markdown(tmp_path, monkeypatch):
    monkeypatch.setenv("NODE_OPTIONS", os.environ.get("NODE_OPTIONS", "") + " --experimental-sqlite")
    # Do not reuse an Effect runtime started by the minimum-Node CI step.
    # Each CLI subprocess resolves its own tempfile root from this environment.
    for variable in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(variable, str(tmp_path))
    runtime, state, registry = tmp_path / "runtime", tmp_path / "state.md", tmp_path / "registry.json"
    state.write_text("# Synthetic goal\n\n## Agent Todo\n")
    registry.write_text(json.dumps({"common_runtime_root": str(runtime), "goals": [{
        "id": "sqlite-goal", "repo": str(tmp_path), "state_file": state.name,
        "coordination": {"registered_agents": ["agent-a"]},
    }]}))
    projection = build_todo_runtime_shadow_projection(goal_id="sqlite-goal", handoff_mode="soft_claim", todos=[{
        "schema_version": "todo_item_v0", "todo_id": "todo_sqlite", "role": "agent",
        "status": "open", "done": False, "text": "Original task", "archive_state": "active",
        "source_section": "Agent Todo", "index": 1, "claimed_by": "agent-a", "task_class": "advancement_task",
    }])
    for record in projection["todos"]:
        record["schema_version"] = "todo_domain_record_v0"
        record.pop("index")
        record.pop("source_section")
    projection["todo_read_model"] = {
        "schema_version": TODO_DOMAIN_READ_RECORD_SCHEMA_VERSION,
        "contract_fields": list(TODO_DOMAIN_RECORD_FIELDS),
        "todo_count": 1,
        "records_sha256": hashlib.sha256(canonical_bytes(projection["todos"])).hexdigest(),
    }
    initialize_canonical_authority(runtime, "sqlite-goal", projection, state_path=state, provider="sqlite")
    state.unlink()

    def cli(*args, expected_code=0):
        process = subprocess.run([sys.executable, "-m", "loopx.cli", "--registry", str(registry),
            "--format", "json", "todo", *args, "--goal-id", "sqlite-goal"],
            capture_output=True, text=True, timeout=60)
        assert process.returncode == expected_code, process.stdout + process.stderr
        return json.loads(process.stdout)

    assert "Original task" in json.dumps(cli("list"))
    assert not state.exists()
    updated = cli("update", "--role", "agent", "--todo-id", "todo_sqlite", "--agent-id", "agent-a",
        "--text", "Updated through SQLite")
    assert updated["source_authority"] == "sqlite_v0"
    assert updated["projection_delivery"] == "delivered", json.dumps(updated, indent=2)
    assert "Updated through SQLite" in state.read_text()
    state.unlink()
    assert "Updated through SQLite" in json.dumps(cli("list"))
    assert not state.exists()
    assert not list((runtime / "authority" / "file-v0").glob("authority-store-*.json"))
    # Native planning updates must preserve the selected provider through the
    # Python adapter, including dry-run, receipt replay and reopening a wait.
    planning = ("update", "--role", "agent", "--todo-id", "todo_sqlite", "--agent-id", "agent-a",
        "--status", "deferred", "--resume-when", "pr_merged:#123", "--reason", "Await upstream",
        "--update-operation-id", "sqlite-planning")
    assert cli(*planning, "--dry-run")["status"] == "planned"
    assert not state.exists()
    assert cli(*planning)["source_authority"] == "sqlite_v0"
    assert cli(*planning)["status"] == "replayed"
    resumed = cli("update", "--role", "agent", "--todo-id", "todo_sqlite", "--agent-id", "agent-a",
        "--status", "open", "--clear-resume-when")
    assert resumed["source_authority"] == "sqlite_v0"
    state.unlink()
    databases = list((runtime / "authority" / "sqlite-v0").glob("*.sqlite"))
    assert len(databases) == 1
    databases[0].rename(databases[0].with_suffix(".saved"))
    for result in (
        cli("list", expected_code=1),
        cli("update", "--role", "agent", "--todo-id", "todo_sqlite", "--agent-id", "agent-a",
            "--text", "Must not commit", expected_code=1),
    ):
        assert result["source_authority"] == "sqlite_v0"
        assert result["error_code"] == "local_authority_provider_missing"
        assert result["legacy_fallback_used"] is False
        assert result["decision_read_from_provider"] is False
    assert not state.exists()
    assert not databases[0].exists()
