from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ...history import load_registry
from ...materials import find_registry_goal, goal_repo
from ..runtime.validation_command import (
    CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
    run_caller_validation,
)
from .active_state_editing import find_todo_block
from .event_writeback import event_projection_source_authority, event_projection_todo_context


TODO_COMPLETION_VALIDATION_PLAN_REQUEST_SCHEMA = (
    "loopx_todo_completion_validation_plan_request_v0"
)
TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA = (
    "loopx_todo_completion_validation_plan_result_v0"
)

# Kept safely under the 30s outer CLI/MCP subprocess budget so a timed-out
# validation still produces a typed receipt before the outer call is killed.
_COMPLETION_VALIDATION_TIMEOUT_SECONDS = 20
# Per-todo overrides (declared on `todo add`) must also stay under that outer
# budget for the same reason; the writer-side range check enforces this.
COMPLETION_VALIDATION_TIMEOUT_MAX_SECONDS = 29


def _resolve_goal_repo_workspace(registry_path: Path, goal_id: str) -> Path | None:
    """Resolve the goal's repository directory to use as the validation workspace."""
    goal = find_registry_goal(load_registry(registry_path), goal_id)
    if goal is None:
        return None
    repo = goal_repo(goal)
    if repo is None or not repo.is_dir():
        return None
    return repo


def _json_successor_value(value: Any) -> Any:
    if isinstance(value, (tuple, set)):
        return list(value)
    return value


def _materialized_todo_item(
    *, state_file: Path, todo_id: str, role: str | None
) -> dict[str, Any] | None:
    try:
        lines = state_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    match = find_todo_block(lines, todo_id=todo_id, role=role)
    if not match:
        return None
    item_role, _section, _start, _end, block = match
    item = dict(block)
    item["role"] = item_role
    return item


def evaluate_todo_completion_validation_plan(
    *,
    todo: Mapping[str, Any],
    projection_source: str,
    completion_turn_key: str | None,
    no_followup: bool,
    dry_run: bool,
    completion_identity_source: str | None = None,
    goal_id: str | None = None,
    todo_id: str | None = None,
) -> dict[str, Any]:
    """Ask the TypeScript Todo owner for the validation decision/effect plan."""
    try:
        result = effect_runtime_result(
            "todo.completion_validation.plan",
            {
                "schema_version": TODO_COMPLETION_VALIDATION_PLAN_REQUEST_SCHEMA,
                "projection_source": projection_source,
                "todo": {
                    "status": str(todo.get("status") or "open"),
                    "no_followup": todo.get("no_followup"),
                    "completion_continuation": todo.get("completion_continuation"),
                    "completion_turn_key": todo.get("completion_turn_key"),
                    "successor_todo_ids": _json_successor_value(
                        todo.get("successor_todo_ids")
                    ),
                    "validation_command": todo.get("validation_command"),
                    "validation_command_argv": todo.get("validation_command_argv"),
                    "validation_label": todo.get("validation_label"),
                    "validation_timeout_seconds": todo.get(
                        "validation_timeout_seconds"
                    ),
                },
                "requested_no_followup": no_followup,
                "requested_completion_turn_key": completion_turn_key,
                "requested_completion_identity_source": completion_identity_source,
                "goal_id": goal_id,
                "todo_id": todo_id,
                "dry_run": dry_run,
            },
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, Mapping):
        raise RuntimeError(
            "TypeScript Todo completion validation plan result must be an object"
        )
    effect = result.get("effect")
    if (
        result.get("schema_version")
        != TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA
        or effect not in {"skip", "run", "reject"}
        or not isinstance(result.get("reason"), str)
    ):
        raise RuntimeError(
            "TypeScript Todo completion validation plan result shape mismatch"
        )
    if effect == "run":
        argv = result.get("validation_argv")
        if not (
            result.get("validation_command") is None
            or isinstance(result.get("validation_command"), str)
        ):
            raise RuntimeError(
                "TypeScript Todo completion validation run command shape mismatch"
            )
        if not (
            argv is None
            or (
                isinstance(argv, list)
                and argv
                and all(isinstance(item, str) and item for item in argv)
            )
        ):
            raise RuntimeError(
                "TypeScript Todo completion validation run argv shape mismatch"
            )
        timeout_seconds = result.get("validation_timeout_seconds")
        if not (
            timeout_seconds is None
            or (
                isinstance(timeout_seconds, int)
                and 1 <= timeout_seconds <= COMPLETION_VALIDATION_TIMEOUT_MAX_SECONDS
            )
        ):
            raise RuntimeError(
                "TypeScript Todo completion validation timeout shape mismatch"
            )
        if not (
            result.get("validation_label") is None
            or isinstance(result.get("validation_label"), str)
        ):
            raise RuntimeError(
                "TypeScript Todo completion validation label shape mismatch"
            )
    if effect == "reject" and (
        result.get("status") != "declaration_invalid"
        or not isinstance(result.get("summary"), str)
        or not (
            result.get("validation_label") is None
            or isinstance(result.get("validation_label"), str)
        )
    ):
        raise RuntimeError(
            "TypeScript Todo completion validation reject shape mismatch"
        )
    return dict(result)


def _validation_declaration_receipt(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
        "command_label": plan.get("validation_label")
        or "todo completion validation",
        "exit_code": None,
        "passed": False,
        "status": plan.get("status") or "declaration_invalid",
        "summary": str(plan.get("summary") or "validation declaration is invalid"),
        "stdout_captured": False,
        "stderr_captured": False,
        "local_path_captured": False,
    }


def _run_declared_completion_validation(
    *,
    validation_command: str | None,
    validation_argv: list[str] | None,
    validation_label: str | None,
    validation_timeout_seconds: int | None,
    registry_path: Path,
    goal_id: str,
) -> dict[str, Any] | None:
    """Run a todo's declared caller-approved validation command.

    Returns ``None`` when no command form is declared (the unchanged fast
    path). ``validation_argv`` (the JSON argv form declared on ``todo add``)
    takes the run-once no-shell path; ``validation_command`` keeps the
    legacy shlex form. ``validation_timeout_seconds`` overrides the module
    default when declared on ``todo add``; ``None`` keeps the default.
    Otherwise always returns a privacy-safe receipt whose ``passed`` is True
    only when the command ran and exited zero; setup failures (no repository
    workspace), timeouts, missing executables, and malformed commands are all
    reported as ``passed=False`` receipts rather than raised, so completion
    can surface a typed failure without committing.
    """
    if not validation_command and validation_argv is None:
        return None
    timeout_seconds = (
        validation_timeout_seconds
        if validation_timeout_seconds is not None
        else _COMPLETION_VALIDATION_TIMEOUT_SECONDS
    )
    label = validation_label or "todo completion validation"
    workspace = _resolve_goal_repo_workspace(registry_path, goal_id)
    if workspace is None:
        return {
            "schema_version": CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
            "command_label": label,
            "exit_code": None,
            "passed": False,
            "status": "workspace_unavailable",
            "summary": (
                "validation_command is declared but the goal has no "
                "repository workspace to run it in"
            ),
            "stdout_captured": False,
            "stderr_captured": False,
            "local_path_captured": False,
        }
    try:
        if validation_argv is not None:
            return run_caller_validation(
                workspace,
                validation_argv=validation_argv,
                validation_label=label,
                timeout_seconds=timeout_seconds,
            )
        return run_caller_validation(
            workspace,
            validation_command=str(validation_command),
            validation_label=label,
            timeout_seconds=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "schema_version": CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
            "command_label": label,
            "exit_code": None,
            "passed": False,
            "status": "timeout",
            "summary": (
                f"validation command timed out after {timeout_seconds}s"
            ),
            "stdout_captured": False,
            "stderr_captured": False,
            "local_path_captured": False,
        }
    except (FileNotFoundError, PermissionError) as exc:
        return {
            "schema_version": CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
            "command_label": label,
            "exit_code": None,
            "passed": False,
            "status": "command_not_run",
            "summary": f"validation command could not be launched: {exc}",
            "stdout_captured": False,
            "stderr_captured": False,
            "local_path_captured": False,
        }
    except ValueError as exc:
        # shlex.split rejects malformed (e.g. unbalanced-quote) commands, and
        # an argv form that collapsed to [] (corrupted stored declaration)
        # fails the runner's own empty-command check.
        return {
            "schema_version": CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
            "command_label": label,
            "exit_code": None,
            "passed": False,
            "status": "command_malformed",
            "summary": f"validation command could not be parsed: {exc}",
            "stdout_captured": False,
            "stderr_captured": False,
            "local_path_captured": False,
        }


def run_completion_validation_gate(
    *,
    state_file: Path,
    todo_id: str,
    role: str | None,
    registry_path: Path,
    goal_id: str,
    dry_run: bool,
    no_followup: bool = False,
    completion_turn_key: str | None = None,
    completion_identity_source: str | None = None,
) -> dict[str, Any] | None:
    return run_completion_validation_gate_with_source(
        state_file=state_file,
        todo_id=todo_id,
        role=role,
        registry_path=registry_path,
        goal_id=goal_id,
        dry_run=dry_run,
        no_followup=no_followup,
        completion_turn_key=completion_turn_key,
        completion_identity_source=completion_identity_source,
    ).get("failure")


def run_completion_validation_gate_with_source(
    *,
    state_file: Path,
    todo_id: str,
    role: str | None,
    registry_path: Path,
    goal_id: str,
    dry_run: bool,
    no_followup: bool = False,
    completion_turn_key: str | None = None,
    completion_identity_source: str | None = None,
) -> dict[str, Any]:
    """Run the caller-approved completion validation gate, OUTSIDE the mutation lock.

    Returns a ``validation_blocked_completion`` failure payload when a declared
    validation command does not pass (the caller returns it unchanged so the
    durable writeback and quota spend are both skipped), or ``None`` when there
    is no declared command, the command passes, or the completion is a dry_run
    or a terminal replay (no gate). Read-only w.r.t. the state file; safe to
    call before acquiring the mutation lock so a multi-second validation command
    does not block concurrent todo operations on the same goal.
    """
    projection_source = "materialized"
    source_authority: dict[str, Any] | None = None
    todo = _materialized_todo_item(state_file=state_file, todo_id=todo_id, role=role)
    if todo is None:
        event_context = event_projection_todo_context(
            registry_path=registry_path,
            goal_id=goal_id,
            state_path=state_file,
            todo_id=todo_id,
            role=role,
        )
        if event_context is None:
            return {"failure": None, "source_authority": None}
        projection_source = "event_log"
        todo = dict(event_context.get("raw_item") or event_context["item"])
        todo["role"] = event_context["role"]
        source_authority = event_projection_source_authority(event_context)
    plan = evaluate_todo_completion_validation_plan(
        todo=todo,
        projection_source=projection_source,
        completion_turn_key=completion_turn_key,
        no_followup=no_followup,
        dry_run=dry_run,
        completion_identity_source=completion_identity_source,
        goal_id=goal_id,
        todo_id=todo_id,
    )
    completion_validation = None
    if plan["effect"] == "reject":
        completion_validation = _validation_declaration_receipt(plan)
    elif plan["effect"] == "run":
        validation_argv = plan.get("validation_argv")
        completion_validation = _run_declared_completion_validation(
            validation_command=(
                str(plan["validation_command"])
                if plan.get("validation_command") is not None
                else None
            ),
            validation_argv=(
                list(validation_argv)
                if isinstance(validation_argv, list)
                else None
            ),
            validation_label=(
                str(plan["validation_label"])
                if plan.get("validation_label") is not None
                else None
            ),
            validation_timeout_seconds=(
                int(plan["validation_timeout_seconds"])
                if plan.get("validation_timeout_seconds") is not None
                else None
            ),
            registry_path=registry_path,
            goal_id=goal_id,
        )
    if completion_validation is None or completion_validation.get("passed") is True:
        return {"failure": None, "source_authority": source_authority}
    failure = {
        "ok": False,
        "dry_run": dry_run,
        "completed": False,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "changed": False,
        "validation": completion_validation,
        "validation_blocked_completion": True,
    }
    return {"failure": failure, "source_authority": source_authority}
