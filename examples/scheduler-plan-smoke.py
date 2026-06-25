#!/usr/bin/env python3
"""Smoke-test LoopX safe parallel scheduler planning."""

from __future__ import annotations

import sys
import json
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "scheduler-plan-smoke"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.scheduler import build_scheduler_plan  # noqa: E402


def agent_todo(
    todo_id: str,
    text: str,
    *,
    safety_class: str = "read_only",
    required_write_scopes: list[str] | None = None,
    required_decision_scopes: list[dict] | None = None,
    claimed_by: str | None = None,
) -> dict:
    item = {
        "todo_id": todo_id,
        "text": text,
        "status": "open",
        "done": False,
        "role": "agent",
        "task_class": "advancement_task",
        "safety_class": safety_class,
    }
    if required_write_scopes:
        item["required_write_scopes"] = required_write_scopes
    if required_decision_scopes:
        item["required_decision_scopes"] = required_decision_scopes
    if claimed_by:
        item["claimed_by"] = claimed_by
    return item


def user_gate(todo_id: str, scope_key: str) -> dict:
    return {
        "todo_id": todo_id,
        "text": f"Approve writes to {scope_key}.",
        "status": "open",
        "done": False,
        "role": "user",
        "task_class": "user_gate",
        "decision_scope": {
            "kind": "write_scope",
            "granularity": "project",
            "scope_key": scope_key,
        },
    }


def status_payload(agent_items: list[dict], user_items: list[dict] | None = None) -> dict:
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "open_count": len(agent_items),
        "first_open_items": agent_items,
        "first_executable_items": agent_items,
        "executable_backlog_items": agent_items,
        "items": agent_items,
    }
    user_todos = None
    if user_items:
        user_todos = {
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo / Owner Review Reading Queue",
            "open_count": len(user_items),
            "first_open_items": user_items,
            "items": user_items,
        }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "codex",
                    "severity": "info",
                    "agent_todos": agent_todos,
                    "project_asset": {"agent_todos": agent_todos},
                    "quota": {
                        "state": "eligible",
                        "reason": "eligible fixture",
                        "allowed_slots": 10,
                        "spent_slots": 0,
                    },
                }
            ]
        },
    } | (
        {}
        if not user_todos
        else {
            "attention_queue": {
                "items": [
                    {
                        "goal_id": GOAL_ID,
                        "status": "active",
                        "waiting_on": "codex",
                        "severity": "info",
                        "agent_todos": agent_todos,
                        "user_todos": user_todos,
                        "project_asset": {
                            "agent_todos": agent_todos,
                            "user_todos": user_todos,
                        },
                        "quota": {
                            "state": "eligible",
                            "reason": "eligible fixture",
                            "allowed_slots": 10,
                            "spent_slots": 0,
                        },
                    }
                ]
            }
        }
    )


def assert_disjoint_local_write_and_read_only_parallelize() -> None:
    plan = build_scheduler_plan(
        status_payload(
            [
                agent_todo("todo_docs", "Update docs.", safety_class="local_write", required_write_scopes=["docs/**"]),
                agent_todo("todo_src", "Update source.", safety_class="local_write", required_write_scopes=["loopx/scheduler.py"]),
                agent_todo("todo_read", "Inspect status.", safety_class="read_only"),
            ]
        ),
        goal_id=GOAL_ID,
        max_parallel=3,
    )
    assert plan["ok"] is True, plan
    assert [item["todo_id"] for item in plan["runnable_batch"]] == [
        "todo_docs",
        "todo_src",
        "todo_read",
    ], plan
    assert plan["blocked_candidates"] == [], plan


def assert_write_scope_conflict_waits_without_blocking_safe_read() -> None:
    plan = build_scheduler_plan(
        status_payload(
            [
                agent_todo("todo_docs", "Update docs.", safety_class="local_write", required_write_scopes=["docs/**"]),
                agent_todo("todo_api_doc", "Update API docs.", safety_class="local_write", required_write_scopes=["docs/api.md"]),
                agent_todo("todo_read", "Inspect status.", safety_class="read_only"),
            ]
        ),
        goal_id=GOAL_ID,
        max_parallel=3,
    )
    assert [item["todo_id"] for item in plan["runnable_batch"]] == ["todo_docs", "todo_read"], plan
    waiting = {item["todo_id"]: item for item in plan["waiting_candidates"]}
    assert waiting["todo_api_doc"]["reason_codes"] == ["write_scope_conflict"], waiting
    assert waiting["todo_api_doc"]["conflicts_with"] == ["todo_docs"], waiting


def assert_open_user_gate_blocks_matching_required_decision_scope() -> None:
    plan = build_scheduler_plan(
        status_payload(
            [
                agent_todo(
                    "todo_gated_docs",
                    "Write gated docs.",
                    safety_class="local_write",
                    required_write_scopes=["docs/**"],
                    required_decision_scopes=[
                        {"kind": "write_scope", "granularity": "project", "scope_key": "docs/**"}
                    ],
                ),
                agent_todo("todo_read", "Inspect status.", safety_class="read_only"),
            ],
            user_items=[user_gate("todo_user_docs", "docs/**")],
        ),
        goal_id=GOAL_ID,
        max_parallel=3,
    )
    assert [item["todo_id"] for item in plan["runnable_batch"]] == ["todo_read"], plan
    blocked = {item["todo_id"]: item for item in plan["blocked_candidates"]}
    assert blocked["todo_gated_docs"]["reason_codes"] == ["requires_user_decision"], blocked
    assert blocked["todo_gated_docs"]["blocked_by_user_todos"] == ["todo_user_docs"], blocked


def assert_high_risk_work_is_not_parallelized_by_default() -> None:
    plan = build_scheduler_plan(
        status_payload(
            [
                agent_todo("todo_ci_run", "Run hosted CI.", safety_class="external_run"),
                agent_todo("todo_prod", "Publish protected result.", safety_class="protected_write"),
                agent_todo("todo_read", "Inspect status.", safety_class="read_only"),
            ]
        ),
        goal_id=GOAL_ID,
        max_parallel=3,
    )
    assert [item["todo_id"] for item in plan["runnable_batch"]] == ["todo_read"], plan
    blocked = {item["todo_id"]: item for item in plan["blocked_candidates"]}
    assert blocked["todo_ci_run"]["reason_codes"] == ["external_run_requires_explicit_lane"], blocked
    assert blocked["todo_prod"]["reason_codes"] == ["protected_write_requires_user_gate"], blocked


def write_cli_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Scheduler Plan Smoke\n\n"
        "## Agent Todo\n\n"
        "- [ ] Update docs.\n"
        "  <!-- loopx:todo todo_id=todo_cli_docs status=open task_class=advancement_task "
        "required_write_scopes=docs/** safety_class=local_write -->\n"
        "- [ ] Inspect status.\n"
        "  <!-- loopx:todo todo_id=todo_cli_read status=open task_class=advancement_task "
        "safety_class=read_only -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {"kind": "harness_self_improvement"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry_path, runtime


def assert_cli_scheduler_plan_uses_status_collection() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-scheduler-plan-") as tmp:
        registry_path, runtime = write_cli_fixture(Path(tmp))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "scheduler",
                "plan",
                "--goal-id",
                GOAL_ID,
                "--max-parallel",
                "2",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == "scheduler_plan_v0", payload
        assert [item["todo_id"] for item in payload["runnable_batch"]] == [
            "todo_cli_docs",
            "todo_cli_read",
        ], payload


def assert_cli_scheduler_handoffs_render_copyable_worker_packets() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-scheduler-handoffs-") as tmp:
        registry_path, runtime = write_cli_fixture(Path(tmp))
        json_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "scheduler",
                "handoffs",
                "--goal-id",
                GOAL_ID,
                "--max-parallel",
                "2",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(json_result.stdout)
        assert payload["schema_version"] == "scheduler_worker_handoffs_v0", payload
        assert payload["handoff_count"] == 2, payload
        handoffs = {item["todo_id"]: item for item in payload["worker_handoffs"]}
        assert "Todo: todo_cli_docs" in handoffs["todo_cli_docs"]["handoff_text"], handoffs
        assert "Write scopes: docs/**" in handoffs["todo_cli_docs"]["handoff_text"], handoffs
        assert handoffs["todo_cli_docs"]["complete_command_template"] == (
            "loopx todo complete --goal-id scheduler-plan-smoke --role agent "
            "--todo-id todo_cli_docs --evidence '<public-safe evidence>'"
        ), handoffs
        assert handoffs["todo_cli_docs"]["blocked_command_template"] == (
            "loopx todo update --goal-id scheduler-plan-smoke --role agent "
            "--todo-id todo_cli_docs --status blocked --reason '<public-safe blocker>'"
        ), handoffs

        markdown_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "scheduler",
                "handoffs",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                "todo_cli_docs",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "# LoopX Scheduler Worker Handoffs" in markdown_result.stdout, markdown_result.stdout
        assert "Todo: todo_cli_docs" in markdown_result.stdout, markdown_result.stdout
        assert "complete:" in markdown_result.stdout, markdown_result.stdout
        assert "blocked:" in markdown_result.stdout, markdown_result.stdout
        assert "todo_cli_read" not in markdown_result.stdout, markdown_result.stdout


def main() -> int:
    assert_disjoint_local_write_and_read_only_parallelize()
    assert_write_scope_conflict_waits_without_blocking_safe_read()
    assert_open_user_gate_blocks_matching_required_decision_scope()
    assert_high_risk_work_is_not_parallelized_by_default()
    assert_cli_scheduler_plan_uses_status_collection()
    assert_cli_scheduler_handoffs_render_copyable_worker_packets()
    print("scheduler plan smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
