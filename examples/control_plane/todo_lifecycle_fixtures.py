"""Fixtures for the todo lifecycle CLI smoke."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.canary_harness import (  # noqa: E402
    run_json_cli,
    run_json_cli_result,
    runtime_root_from_registry,
    write_fixture_registry,
)
from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "todo-lifecycle-goal"
RUN_TODO = "Run a fresh-seed full PR3-r8 treatment repeat after the support-blocked seed failed."
REBUILD_TODO = "Rebuild labels and scorer after the fresh repeat."
VALIDATE_TODO = "Validate scorer labels and write back the compact result."
SIDE_TODO = "Refine todo ownership contract from a side worktree."
SIDE_CONTINUATION_TODO = "Continue the small side-agent productization lane after self-merge."
SIDE_REVIEW_TODO = "Refine todo ownership contract with primary review required."
REVIEW_TODO = "Primary agent review, verify, and merge the side-agent ownership contract work."
SIDE_HANDOFF_SOURCE_TODO = "Refine todo ownership contract with configured side-agent handoff."
SIDE_HANDOFF_TODO = "Review, verify, and continue the side-agent handoff work."
HANDOFF_SOURCE_TODO = "Prepare successor handoff routing from the primary agent."
HANDOFF_SUCCESSOR_TODO = "Continue successor handoff routing from the side agent."
UNCLAIMED_SOURCE_TODO = "Prepare an unclaimed successor routing check."
UNCLAIMED_SUCCESSOR_TODO = "Continue the unclaimed successor routing check."


def write_fixture(root: Path) -> tuple[Path, Path]:
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
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Exercise todo lifecycle transitions.\n\n"
        "## Agent Todo\n\n"
        "- [ ] Legacy monitor-only placeholder.\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="todo-lifecycle-fixture",
        adapter_kind="generic_project_goal_v0",
        registered_agents=["codex-main-control", "codex-side-bypass"],
        primary_agent="codex-main-control",
        quota_allowed_slots=None,
    )
    return registry_path, state_file


def run_cli(registry_path: Path, *args: str) -> dict:
    return run_json_cli(
        *args,
        registry_path=registry_path,
        runtime_root=runtime_root_from_registry(registry_path),
        cwd=REPO_ROOT,
        include_returncode=False,
    )


def run_cli_error(registry_path: Path, *args: str) -> dict:
    returncode, payload = run_json_cli_result(
        *args,
        registry_path=registry_path,
        runtime_root=runtime_root_from_registry(registry_path),
        cwd=REPO_ROOT,
    )
    assert returncode == 1, payload
    return payload


def parsed_items(state_file: Path) -> list[dict]:
    fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
    return fields["agent_todos"]["items"]


def parsed_agent_summary(state_file: Path) -> dict:
    fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
    return fields["agent_todos"]


def assert_configured_side_agent_handoff() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-handoff-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        coordination = registry["goals"][0]["coordination"]
        coordination["registered_agents"].append("codex-side-reviewer")
        coordination["side_agent_handoff_agent"] = "codex-side-reviewer"
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        side_handoff_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_HANDOFF_SOURCE_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        side_handoff_completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_handoff_added["todo_id"],
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
            "--next-agent-todo",
            SIDE_HANDOFF_TODO,
            "--next-claimed-by",
            "codex-side-reviewer",
        )
        assert side_handoff_completed["changed"] is True, side_handoff_completed
        side_handoff_successor_id = side_handoff_completed["next_todos"][0]["todo_id"]
        assert side_handoff_completed["next_todos"][0]["claimed_by"] == "codex-side-reviewer", (
            side_handoff_completed
        )
        assert side_handoff_completed["next_todos"][0]["blocks_agent"] == "codex-side-bypass", (
            side_handoff_completed
        )
        assert side_handoff_completed["next_todos"][0]["unblocks_todo_id"] == side_handoff_added["todo_id"], (
            side_handoff_completed
        )
        side_handoff_successor = next(
            item for item in parsed_items(state_file) if item["todo_id"] == side_handoff_successor_id
        )
        assert not side_handoff_successor.get("action_kind"), side_handoff_successor
        assert side_handoff_successor["claimed_by"] == "codex-side-reviewer", side_handoff_successor

    with tempfile.TemporaryDirectory(prefix="loopx-explicit-primary-review-handoff-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        coordination = registry["goals"][0]["coordination"]
        coordination["registered_agents"].append("codex-side-reviewer")
        coordination["side_agent_handoff_agent"] = "codex-side-reviewer"
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        review_source_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_HANDOFF_SOURCE_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        explicit_primary_review = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            review_source_added["todo_id"],
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
            "--next-agent-todo",
            REVIEW_TODO,
            "--next-claimed-by",
            "codex-main-control",
            "--next-action-kind",
            "primary_review_merge",
        )
        assert explicit_primary_review["changed"] is True, explicit_primary_review
        review_successor = explicit_primary_review["next_todos"][0]
        assert review_successor["claimed_by"] == "codex-main-control", explicit_primary_review
        assert review_successor["action_kind"] == "primary_review_merge", explicit_primary_review
        assert review_successor["blocks_agent"] == "codex-side-bypass", explicit_primary_review
        assert review_successor["unblocks_todo_id"] == review_source_added["todo_id"], explicit_primary_review
        review_successor_item = next(
            item for item in parsed_items(state_file) if item["todo_id"] == review_successor["todo_id"]
        )
        assert review_successor_item["claimed_by"] == "codex-main-control", review_successor_item
        assert review_successor_item["action_kind"] == "primary_review_merge", review_successor_item

    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-handoff-self-smoke-") as tmp:
        root = Path(tmp)
        registry_path, _state_file = write_fixture(root)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["goals"][0]["coordination"]["side_agent_handoff_agent"] = "codex-side-bypass"
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        side_handoff_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_HANDOFF_SOURCE_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        same_agent_handoff = run_cli_error(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_handoff_added["todo_id"],
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
            "--next-agent-todo",
            SIDE_HANDOFF_TODO,
        )
        assert "side-agent handoff todo cannot be claimed by the completing side agent" in (
            same_agent_handoff["error"]
        ), same_agent_handoff

    with tempfile.TemporaryDirectory(prefix="loopx-ignored-side-agent-review-smoke-") as tmp:
        root = Path(tmp)
        registry_path, _state_file = write_fixture(root)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        coordination = registry["goals"][0]["coordination"]
        coordination["registered_agents"].append("codex-side-reviewer")
        coordination["side_agent_review_agent"] = "codex-side-reviewer"
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ignored_review_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_HANDOFF_SOURCE_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        ignored_review_handoff = run_cli_error(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            ignored_review_added["todo_id"],
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
            "--next-agent-todo",
            SIDE_HANDOFF_TODO,
            "--next-claimed-by",
            "codex-side-reviewer",
        )
        assert "handoff_agent='codex-main-control'" in ignored_review_handoff["error"], ignored_review_handoff

    with tempfile.TemporaryDirectory(prefix="loopx-profile-side-agent-handoff-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        coordination = registry["goals"][0]["coordination"]
        coordination["registered_agents"].append("codex-product-capability")
        coordination["side_agent_handoff_agent"] = "codex-side-bypass"
        coordination["agent_profiles"] = {
            "codex-product-capability": {
                "schema_version": "agent_profile_v0",
                "review_policy": {"handoff_agent": "codex-main-control"},
            }
        }
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        profile_handoff_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_HANDOFF_SOURCE_TODO,
            "--claimed-by",
            "codex-product-capability",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        profile_handoff_completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            profile_handoff_added["todo_id"],
            "--claimed-by",
            "codex-product-capability",
            "--evidence",
            "product-capability-runtime-contract-diff",
            "--next-agent-todo",
            SIDE_HANDOFF_TODO,
            "--next-claimed-by",
            "codex-main-control",
        )
        assert profile_handoff_completed["changed"] is True, profile_handoff_completed
        assert profile_handoff_completed["next_todos"][0]["claimed_by"] == "codex-main-control", (
            profile_handoff_completed
        )
        assert profile_handoff_completed["next_todos"][0]["blocks_agent"] == "codex-product-capability", (
            profile_handoff_completed
        )
        assert profile_handoff_completed["next_todos"][0]["unblocks_todo_id"] == profile_handoff_added["todo_id"], (
            profile_handoff_completed
        )
        profile_handoff_successor = next(
            item
            for item in parsed_items(state_file)
            if item["todo_id"] == profile_handoff_completed["next_todos"][0]["todo_id"]
        )
        assert profile_handoff_successor["claimed_by"] == "codex-main-control", profile_handoff_successor


def assert_no_followup_cli_metadata() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-no-followup-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Review completed work that intentionally needs no successor.",
            "--claimed-by",
            "codex-main-control",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "review",
        )
        missing_rationale = run_cli_error(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            added["todo_id"],
            "--no-follow-up",
        )
        assert "--no-follow-up requires" in missing_rationale["error"], missing_rationale
        updated = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            added["todo_id"],
            "--status",
            "done",
            "--no-follow-up",
            "--note",
            "No rollout or follow-up is needed after validation.",
        )
        assert updated["changed"] is True, updated
        item = next(item for item in parsed_items(state_file) if item["todo_id"] == added["todo_id"])
        assert item["status"] == "done", item
        assert item["no_followup"] is True, item


def assert_complete_links_existing_successor() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-existing-successor-complete-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        source = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Ship a side-agent slice that already has its next lane todo.",
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        successor = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_CONTINUATION_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        source_id = source["todo_id"]
        successor_id = successor["todo_id"]

        mixed_successor_modes = run_cli_error(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            source_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "self-merged commit ghi789 after focused validation",
            "--side-agent-self-merged",
            "--successor-todo-id",
            successor_id,
            "--next-agent-todo",
            "Duplicate successor should be rejected.",
        )
        assert "--successor-todo-id links existing work" in mixed_successor_modes["error"], (
            mixed_successor_modes
        )

        completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            source_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "self-merged commit ghi789 after focused validation",
            "--side-agent-self-merged",
            "--successor-todo-id",
            successor_id,
        )
        assert completed["changed"] is True, completed
        assert completed["side_agent_self_merged"] is True, completed
        assert completed["next_todos"] == [], completed
        assert completed["successor_todo_ids"] == [successor_id], completed

        source_item = next(item for item in parsed_items(state_file) if item["todo_id"] == source_id)
        assert source_item["status"] == "done", source_item
        assert source_item["successor_todo_ids"] == [successor_id], source_item
        successor_item = next(item for item in parsed_items(state_file) if item["todo_id"] == successor_id)
        assert successor_item["status"] == "open", successor_item
        assert successor_item["claimed_by"] == "codex-side-bypass", successor_item

        summary = parsed_agent_summary(state_file)
        assert summary.get("completed_without_successor_count", 0) == 0, summary
        assert "todo_succession_warning" not in summary, summary


def assert_same_title_completion_creates_fresh_successor() -> None:
    title = "[P1] Continue the next non-benchmark LoopX state-machine canary/refactor slice."
    with tempfile.TemporaryDirectory(prefix="loopx-same-title-successor-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            title,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "state_machine_canary_refactor",
        )
        completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            added["todo_id"],
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "self-merged commit same-title after focused validation",
            "--side-agent-self-merged",
            "--next-agent-todo",
            title,
            "--next-claimed-by",
            "codex-side-bypass",
            "--next-action-kind",
            "state_machine_canary_refactor",
        )
        assert completed["changed"] is True, completed
        assert completed["next_todos"][0]["added"] is True, completed
        successor_id = completed["next_todos"][0]["todo_id"]
        assert successor_id != added["todo_id"], completed
        assert completed["next_todos"][0]["unblocks_todo_id"] == added["todo_id"], completed

        items = parsed_items(state_file)
        source_item = next(item for item in items if item["todo_id"] == added["todo_id"])
        successor_item = next(item for item in items if item["todo_id"] == successor_id)
        assert source_item["status"] == "done", source_item
        assert successor_item["status"] == "open", successor_item
        assert successor_item["text"] == title, successor_item
        assert successor_item["unblocks_todo_id"] == added["todo_id"], successor_item

        summary = parsed_agent_summary(state_file)
        assert summary.get("completed_without_successor_count", 0) == 0, summary
        assert "todo_succession_warning" not in summary, summary
