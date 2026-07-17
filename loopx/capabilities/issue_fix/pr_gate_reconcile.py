from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ...control_plane.todos.contract import normalize_todo_decision_scope
from ...control_plane.todos.projection import todo_item_task_class
from ...todos import complete_goal_todo, list_goal_todos
from .pr_lifecycle import build_issue_fix_pr_lifecycle_monitor_packet
from .pr_lifecycle_rollout import append_pr_merge_rollout_event


PR_GATE_RECONCILIATION_SCHEMA_VERSION = "issue_fix_pr_gate_reconciliation_v0"
TERMINAL_PR_STATES = {"MERGED", "CLOSED"}


def _validate_merge_gate(todo: Mapping[str, Any], *, pr_number: int) -> None:
    if str(todo.get("role") or "") != "user":
        raise ValueError("PR gate reconciliation requires a user todo")
    if todo_item_task_class(dict(todo)) != "user_gate":
        raise ValueError("PR gate reconciliation requires task_class=user_gate")
    decision_scope = normalize_todo_decision_scope(todo.get("decision_scope"))
    expected_scope_key = f"merge_pr_{pr_number}"
    if not decision_scope or decision_scope.get("scope_key") != expected_scope_key:
        raise ValueError(
            "PR gate decision_scope must match "
            f"direction:action:{expected_scope_key}"
        )


def reconcile_issue_fix_pr_gate(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str,
    todo_id: str,
    project: Path,
    url: str,
    provider_payload: Mapping[str, Any] | None = None,
    fetch_metadata: bool = False,
    fetch_timeout_seconds: int = 10,
    execute: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    lifecycle = build_issue_fix_pr_lifecycle_monitor_packet(
        url=url,
        provider_payload=provider_payload,
        fetch_metadata=fetch_metadata,
        fetch_timeout_seconds=fetch_timeout_seconds,
        generated_at=generated_at,
    )
    observation = lifecycle.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("PR lifecycle observation is missing")
    number = observation.get("number")
    if not isinstance(number, int) or number <= 0:
        raise ValueError("PR lifecycle observation requires a numeric PR")

    todo_payload = list_goal_todos(
        registry_path=registry_path,
        goal_id=goal_id,
        role="user",
        todo_id=todo_id,
        project=project,
    )
    todo = todo_payload.get("todo")
    if not isinstance(todo, dict):
        raise ValueError(f"user todo {todo_id!r} was not found")
    _validate_merge_gate(todo, pr_number=number)

    state = str(observation.get("state") or "UNKNOWN").upper()
    terminal = state in TERMINAL_PR_STATES
    already_reconciled = bool(todo.get("done")) or str(todo.get("status") or "") == "done"
    receipt: dict[str, Any] = {
        "ok": True,
        "schema_version": PR_GATE_RECONCILIATION_SCHEMA_VERSION,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "pr": {
            "repo": observation.get("repo"),
            "number": number,
            "url": observation.get("permalink"),
            "state": state,
            "merged_at": observation.get("merged_at"),
            "closed_at": observation.get("closed_at"),
        },
        "terminal": terminal,
        "execute": execute,
        "would_reconcile": terminal and not already_reconciled,
        "write_performed": False,
        "already_reconciled": already_reconciled,
        "external_read_performed": lifecycle.get("external_reads_performed") is True,
        "external_write_performed": False,
        "private_material_read": False,
        "raw_provider_payload_recorded": False,
    }
    if not terminal:
        receipt["skip_reason"] = "pr_not_terminal"
        return receipt
    if not execute:
        receipt["skip_reason"] = "execute_required"
        return receipt

    if not already_reconciled:
        permalink = str(observation.get("permalink") or url)
        terminal_at = str(
            observation.get("merged_at")
            or observation.get("closed_at")
            or generated_at
            or ""
        ).strip()
        completion = complete_goal_todo(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            role="user",
            decision_outcome="approve" if state == "MERGED" else "cancel",
            note=(
                f"Public PR lifecycle reached terminal state {state}; "
                "the merge approval gate is obsolete."
            ),
            evidence=(
                f"{permalink} state={state}"
                + (f" terminal_at={terminal_at}" if terminal_at else "")
            ),
            no_followup=True,
            project=project,
        )
        receipt["write_performed"] = bool(completion.get("changed"))
        receipt["todo_completion"] = {
            "completed": completion.get("completed"),
            "status": completion.get("status"),
            "status_changed": completion.get("status_changed"),
            "metadata_updated": completion.get("metadata_updated"),
        }
    if state == "MERGED":
        receipt["rollout_event"] = append_pr_merge_rollout_event(
            payload=lifecycle,
            goal_id=goal_id,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
        )
    receipt["reconciled"] = True
    return receipt


def render_issue_fix_pr_gate_reconciliation_markdown(payload: dict[str, Any]) -> str:
    pr = payload.get("pr") if isinstance(payload.get("pr"), dict) else {}
    return "\n".join(
        [
            "# LoopX Issue Fix PR Gate Reconciliation",
            "",
            f"- ok: `{payload.get('ok')}`",
            f"- todo_id: `{payload.get('todo_id')}`",
            f"- pr: `{pr.get('repo')}#{pr.get('number')}`",
            f"- state: `{pr.get('state')}`",
            f"- terminal: `{payload.get('terminal')}`",
            f"- write_performed: `{payload.get('write_performed')}`",
            f"- already_reconciled: `{payload.get('already_reconciled')}`",
            f"- skip_reason: `{payload.get('skip_reason')}`",
        ]
    )
