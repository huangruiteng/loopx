#!/usr/bin/env python3
"""Smoke-test todo add/update dry-run write correctness packets."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.runtime.local_state_write_correctness import (  # noqa: E402
    shadow_validate_local_state_write_correctness_packet,
)
from loopx.control_plane.testing.canary_harness import (  # noqa: E402
    run_json_cli,
    write_fixture_registry,
)

GOAL_ID = "todo-write-correctness-goal"
AGENT_ID = "codex-product-capability"
TODO_TEXT = "Preview a todo write correctness packet before mutating state."


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Todo Write Correctness Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Existing todo for update preview.\n"
        "  <!-- loopx:todo todo_id=todo_existing status=open task_class=advancement_task -->\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="todo-write-correctness-fixture",
        adapter_kind="generic_project_goal_v0",
        registered_agents=("codex-main-control", AGENT_ID),
        quota_allowed_slots=None,
    )
    return registry_path, state_file, project


def run_cli(registry_path: Path, *args: str, as_json: bool = True) -> dict | str:
    if as_json:
        return run_json_cli(
            *args,
            registry_path=registry_path,
            include_returncode=False,
        )
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
    ]
    command.extend(args)
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def assert_packet(
    payload: dict,
    *,
    state_file: Path,
    project: Path,
    write_class: str,
    todo_id: str,
    claimed_by: str | None,
) -> dict:
    packet = payload.get("local_state_write_correctness")
    assert isinstance(packet, dict), payload
    assert packet["schema_version"] == "local_state_write_correctness_v0", packet
    assert str(project) not in json.dumps(packet, ensure_ascii=False), packet

    intent = packet["write_intent"]
    assert intent["goal_id"] == GOAL_ID, packet
    assert intent["writer_id"] == "loopx.todo", packet
    assert intent["write_class"] == write_class, packet
    assert intent["target_refs"]["state_file_ref"] == "registry.goal.state_file", packet
    assert intent["target_refs"]["todo_id"] == todo_id, packet
    assert intent["expected_revision"]["value"] == "sha256:" + hashlib.sha256(
        state_file.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest(), packet
    assert intent["idempotency_key"].startswith(f"{GOAL_ID}:{write_class}:"), packet

    assert packet["lock_boundary"] == {
        "kind": "per_goal",
        "lock_key": f"goal:{GOAL_ID}",
        "narrower_lock_allowed": "per_todo_when_patch_is_single_todo_and_order_independent",
    }, packet
    assert packet["preview"]["mode"] == "dry_run", packet
    assert packet["preview"]["non_destructive"] is True, packet
    assert packet["preview"]["expected_write_scopes"] == ["active_state"], packet
    assert packet["apply_result"]["status"] == "preview_only", packet
    boundary = packet["projection"]["public_boundary"]
    assert boundary == {
        "raw_logs_copied": False,
        "private_paths_copied": False,
        "credentials_copied": False,
        "production_action_authorized": False,
    }, packet

    if claimed_by:
        assert intent["lease_ref"]["todo_id"] == todo_id, packet
        assert intent["lease_ref"]["claimed_by"] == claimed_by, packet
        assert packet["projection"]["lease_projection"] == {
            "todo_id": todo_id,
            "claimed_by": claimed_by,
            "lease_state": "preview_only",
        }, packet
    else:
        assert intent["lease_ref"] is None, packet
        assert packet["projection"]["lease_projection"] is None, packet
    return packet


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-write-correctness-") as tmp:
        registry_path, state_file, project = write_fixture(Path(tmp))
        original = state_file.read_text(encoding="utf-8")

        add_dry_run = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
            "--claimed-by",
            AGENT_ID,
            "--dry-run",
        )
        add_dry_run_repeat = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
            "--claimed-by",
            AGENT_ID,
            "--dry-run",
        )
        assert add_dry_run["dry_run"] is True, add_dry_run
        assert add_dry_run["added"] is True, add_dry_run
        assert state_file.read_text(encoding="utf-8") == original
        add_packet = assert_packet(
            add_dry_run,
            state_file=state_file,
            project=project,
            write_class="todo_add",
            todo_id=add_dry_run["todo_id"],
            claimed_by=AGENT_ID,
        )
        clean_shadow = shadow_validate_local_state_write_correctness_packet(
            add_packet,
            current_state_text=state_file.read_text(encoding="utf-8"),
            observed_lease_ref=add_packet["write_intent"]["lease_ref"],
        )
        assert clean_shadow["apply_result"]["status"] == "preview_only", clean_shadow
        assert clean_shadow["apply_result"]["conflict"] is None, clean_shadow

        revision_conflict = shadow_validate_local_state_write_correctness_packet(
            add_packet,
            current_state_text=(
                state_file.read_text(encoding="utf-8")
                + "\n<!-- concurrent change -->\n"
            ),
        )
        assert (
            revision_conflict["apply_result"]["status"] == "revision_conflict"
        ), revision_conflict
        revision_conflict_detail = revision_conflict["apply_result"]["conflict"]
        assert revision_conflict_detail["kind"] == "revision_conflict", revision_conflict
        assert revision_conflict_detail["expected_revision"] == add_packet["write_intent"][
            "expected_revision"
        ], revision_conflict
        assert revision_conflict_detail["current_revision"] != add_packet["write_intent"][
            "expected_revision"
        ], revision_conflict
        assert state_file.read_text(encoding="utf-8") == original

        foreign_lease = dict(add_packet["write_intent"]["lease_ref"])
        foreign_lease["claimed_by"] = "codex-main-control"
        foreign_lease["lease_id"] = f"lease_{add_dry_run['todo_id']}_codex_main_control"
        lease_conflict = shadow_validate_local_state_write_correctness_packet(
            add_packet,
            current_state_text=state_file.read_text(encoding="utf-8"),
            observed_lease_ref=foreign_lease,
        )
        assert lease_conflict["apply_result"]["status"] == "lease_conflict", lease_conflict
        lease_conflict_detail = lease_conflict["apply_result"]["conflict"]
        assert lease_conflict_detail["kind"] == "lease_conflict", lease_conflict
        assert lease_conflict_detail["expected_lease_ref"] == add_packet["write_intent"][
            "lease_ref"
        ], lease_conflict
        assert lease_conflict_detail["observed_lease_ref"] == foreign_lease, lease_conflict
        assert state_file.read_text(encoding="utf-8") == original

        repeat_packet = add_dry_run_repeat["local_state_write_correctness"]
        assert (
            add_packet["write_intent"]["idempotency_key"]
            == repeat_packet["write_intent"]["idempotency_key"]
        )

        add_markdown = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
            "--dry-run",
            as_json=False,
        )
        assert "## Local State Write Correctness" in add_markdown, add_markdown
        assert "status: `preview_only`" in add_markdown, add_markdown

        real_add = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
        )
        assert real_add["dry_run"] is False, real_add
        assert "local_state_write_correctness" not in real_add, real_add

        update_dry_run = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            "todo_existing",
            "--agent-id",
            AGENT_ID,
            "--claimed-by",
            AGENT_ID,
            "--note",
            "Preview update without writing state.",
            "--dry-run",
        )
        assert update_dry_run["dry_run"] is True, update_dry_run
        assert update_dry_run["changed"] is True, update_dry_run
        assert_packet(
            update_dry_run,
            state_file=state_file,
            project=project,
            write_class="todo_update",
            todo_id="todo_existing",
            claimed_by=AGENT_ID,
        )
        assert "Preview update without writing state." not in state_file.read_text(
            encoding="utf-8"
        )

    print("todo-write-correctness-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
