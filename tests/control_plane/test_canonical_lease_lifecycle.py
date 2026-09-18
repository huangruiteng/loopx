"""Public lease handover and cleanup must stay on the selected authority."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from canonical_authority_fixture import initialize_canonical_authority, isolate_sqlite_runtime

from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("provider", ["file", "sqlite"])
def test_public_lease_handover_replay_and_cleanup(tmp_path, monkeypatch, provider):
    isolate_sqlite_runtime(tmp_path, monkeypatch)
    runtime, state, registry = tmp_path / "runtime", tmp_path / "state.md", tmp_path / "registry.json"
    goal = "lease-lifecycle"
    state.write_text("# Synthetic lease lifecycle\n\n## Agent Todo\n")
    registry.write_text(json.dumps({"common_runtime_root": str(runtime), "goals": [{
        "id": goal, "repo": str(tmp_path), "state_file": state.name,
        "coordination": {"registered_agents": ["agent-a", "agent-b"]},
    }]}))
    now = datetime.now(UTC).replace(microsecond=0)
    lease = {"schema_version": "task_lease_v0", "goal_id": goal, "todo_id": "todo_handover",
             "owner": "agent-a", "idempotency_key": "execution-a", "version": 3, "lease_epoch": 7,
             "status": "active", "write_scopes": ["src/**"], "acquire_ttl_seconds": 600,
             "acquired_at": now.isoformat(), "updated_at": now.isoformat(),
             "expires_at": (now + timedelta(minutes=10)).isoformat()}
    retired_lease = {**lease, "todo_id": "todo_retired", "idempotency_key": "execution-retired",
                     "version": 11, "status": "released", "released_at": now.isoformat()}
    projection = build_todo_runtime_shadow_projection(goal_id=goal, handoff_mode="hard_lease", leases=[lease, retired_lease], todos=[{
        "schema_version": "todo_item_v0", "todo_id": "todo_handover", "role": "agent", "status": "open", "done": False,
        "text": "Hand over an existing execution lease", "archive_state": "active", "source_section": "Agent Todo", "index": 1,
        "task_class": "advancement_task",
    }, {
        "schema_version": "todo_item_v0", "todo_id": "todo_retired", "role": "agent", "status": "open", "done": False,
        "text": "Clean up an imported released lease", "archive_state": "active", "source_section": "Agent Todo", "index": 2,
        "task_class": "advancement_task",
    }])
    initialize_canonical_authority(runtime, goal, projection, state_path=state, provider=provider)
    state.unlink()
    # This file deliberately contradicts the provider. No command may use it.
    legacy_path = runtime / "goals" / goal / "task-leases" / "todo_handover.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_bytes = json.dumps({**lease, "version": 99, "owner": "stale-agent"}).encode()
    legacy_path.write_bytes(legacy_bytes)
    cli_repo = Path(os.environ.get("LOOPX_LEASE_REPLAY_REPO", REPO))

    def cli(operation, *args, expected_exit=0, todo_id="todo_handover"):
        child = subprocess.run([sys.executable, "-m", "loopx.cli", "--registry", str(registry), "--format", "json",
            "task-lease", operation, "--goal-id", goal, "--todo-id", todo_id, *args],
            cwd=cli_repo, capture_output=True, text=True, timeout=60, check=False)
        assert child.returncode == expected_exit, child.stdout + child.stderr
        return json.loads(child.stdout)

    def proof(owner="agent-a", key="execution-a", version=3):
        return ["--owner", owner, "--idempotency-key", key, "--expected-version", str(version)]

    def head():
        module = (REPO / "loopx/control_plane/coordination/local_authority_provider.ts").as_uri()
        script = f"import {{openLocalAuthorityStore}} from {json.dumps(module)};const s=await openLocalAuthorityStore(process.argv[1],process.argv[2]);console.log(JSON.stringify(await s.loadAuthority()));"
        child = subprocess.run(["node", "--no-warnings", "--experimental-strip-types", "--input-type=module", "-e", script,
                                str(runtime), goal], capture_output=True, text=True, timeout=30, check=True)
        return json.loads(child.stdout)

    transfer_args = [*proof(), "--new-owner", "agent-b", "--new-idempotency-key", "execution-b", "--ttl-seconds", "600"]
    try:
        transferred = cli("transfer", *transfer_args)
        assert transferred["ok"] and transferred["transferred"]
        assert transferred["source_authority"] == provider + "_v0"
        assert transferred["decision_read_from_provider"] is True and transferred["legacy_fallback_used"] is False
        assert transferred["lease"]["owner"] == "agent-b"
        assert transferred["lease"]["version"] == 4 and transferred["lease"]["lease_epoch"] == 8
        assert transferred["lease"]["write_scopes"] == lease["write_scopes"]
        after_transfer = head()
        stale = cli("release", *proof(), expected_exit=1)
        assert stale["error_code"] == "version_mismatch"
        assert head() == after_transfer
        renewed = cli("renew", *proof("agent-b", "execution-b", 4), "--ttl-seconds", "600")
        assert renewed["lease"]["version"] == 5 and renewed["lease"]["lease_epoch"] == 8
        released = cli("release", *proof("agent-b", "execution-b", 5))
        assert released["released"] and released["lease"]["status"] == "released"
        assert released["lease"]["version"] == 5 and released["lease"]["lease_epoch"] == 8
        before_no_change = head()
        no_change = cli("release", *proof("agent-a", "execution-retired", 11), todo_id="todo_retired")
        assert no_change["status"] == "no_change" and no_change["released"] is True
        assert no_change["idempotent"] is True
        final = head()
        assert final["head"] == before_no_change["head"]
        for operation, args, original in [
            ("transfer", transfer_args, transferred),
            ("renew", [*proof("agent-b", "execution-b", 4), "--ttl-seconds", "600"], renewed),
            ("release", proof("agent-b", "execution-b", 5), released),
        ]:
            replay = cli(operation, *args)
            assert replay["status"] == "replayed" and replay["idempotent"] is True
            assert replay["original_receipt"] == original["original_receipt"]
            assert replay["lease"] == original["lease"]
            assert "lease_path" not in replay
            assert head() == final
        inspected = cli("inspect")
        assert inspected["active"] is False and inspected["lease"] == released["lease"]
        assert inspected["source_authority"] == provider + "_v0"
        assert final["head"]["todos"] == projection["todos"]
        assert final["cursor"] == "5"
        assert legacy_path.read_bytes() == legacy_bytes and not state.exists()
    finally:
        subprocess.run([sys.executable, "-c", "from loopx.control_plane.effect_runtime import effect_runtime_result; effect_runtime_result('runtime.shutdown',{},retry_safe=False)"],
                       cwd=cli_repo, capture_output=True, text=True, timeout=30, check=True)
