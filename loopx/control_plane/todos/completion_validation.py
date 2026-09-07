from __future__ import annotations

import subprocess
from json import loads as json_loads
from pathlib import Path
from typing import Any, Mapping

from ...history import load_registry
from ...materials import find_registry_goal, goal_repo
from ..runtime.validation_command import (
    CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
    run_caller_validation,
)
from .active_state_editing import find_todo_block
from .contract import TODO_STATUS_DONE, normalize_todo_status
from .event_writeback import event_projection_source_authority, event_projection_todo_context
from .completion_transaction import (
    reduce_todo_completion_transaction,
    todo_completion_source_snapshot,
)
from .completion_policy import (
    build_completion_policy_request,
    linked_successors_from_state,
)


# Kept safely under the 30s outer CLI/MCP subprocess budget so a timed-out
# validation still produces a typed receipt before the outer call is killed.
_COMPLETION_VALIDATION_TIMEOUT_SECONDS = 20
# Per-todo overrides (declared on `todo add`) must also stay under that outer
# budget for the same reason; the writer-side range check enforces this.
COMPLETION_VALIDATION_TIMEOUT_MAX_SECONDS = 29


def normalize_validation_command_json(raw: str | None) -> list[str] | None:
    """Decode the run-once argv form used by Todo completion validation."""

    if raw is None:
        return None
    try:
        argv = json_loads(raw)
    except ValueError as exc:
        raise ValueError(
            "--validation-command-json must be a JSON string array"
        ) from exc
    if not isinstance(argv, list) or not argv or not all(
        isinstance(item, str) and item for item in argv
    ):
        raise ValueError("--validation-command-json must be a JSON string array")
    return argv


def _resolve_goal_repo_workspace(registry_path: Path, goal_id: str) -> Path | None:
    """Resolve the goal's repository directory to use as the validation workspace."""
    goal = find_registry_goal(load_registry(registry_path), goal_id)
    if goal is None:
        return None
    repo = goal_repo(goal)
    if repo is None or not repo.is_dir():
        return None
    return repo


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
    requested_has_successor: bool = False,
    completion_policy_facts: Mapping[str, Any] | None = None,
    requested_successor_todo_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run the caller-approved completion validation gate, OUTSIDE the mutation lock.

    Returns one envelope containing the source snapshot and typed transaction.
    ``failure`` is a ``validation_blocked_completion`` payload when a declared
    command does not pass, otherwise ``None``. The caller returns failures
    unchanged so durable writeback and quota spend are skipped. Dry runs and
    terminal replays do not execute validation. This function is read-only
    w.r.t. the state file and safe to call before acquiring the mutation lock,
    so a multi-second validation command does not block concurrent Todo writes.
    """
    projection_source = "materialized"
    source_authority: dict[str, Any] | None = None
    event_context: dict[str, Any] | None = None
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
            return {
                "failure": None,
                "source_authority": None,
                "source_snapshot": None,
                "transaction": None,
            }
        projection_source = "event_log"
        todo = dict(event_context.get("raw_item") or event_context["item"])
        todo["role"] = event_context["role"]
        source_authority = event_projection_source_authority(event_context)
    source_snapshot = todo_completion_source_snapshot(todo)
    completion_policy_source = None
    if completion_policy_facts is not None:
        try:
            lines = state_file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            lines = []
        completion_policy_source = completion_policy_source_from_state(
            registry_path=registry_path,
            goal_id=goal_id,
            lines=lines,
            successor_todo_ids=requested_successor_todo_ids or [],
            event_fields=(
                event_context.get("fields") if event_context is not None else None
            ),
            facts=completion_policy_facts,
        )
    transaction = reduce_todo_completion_transaction(
        todo=todo,
        projection_source=projection_source,
        completion_turn_key=completion_turn_key,
        no_followup=no_followup,
        dry_run=dry_run,
        completion_identity_source=completion_identity_source,
        goal_id=goal_id,
        todo_id=todo_id,
        requested_has_successor=requested_has_successor,
        validation_receipt=None,
        completion_policy_request=completion_policy_source,
    )
    completion_validation = None
    if transaction["decision"] == "execute_validation":
        effect = transaction["validation_effect"]
        validation_argv = effect.get("validation_argv")
        completion_validation = _run_declared_completion_validation(
            validation_command=(
                str(effect["validation_command"])
                if effect.get("validation_command") is not None
                else None
            ),
            validation_argv=(
                list(validation_argv)
                if isinstance(validation_argv, list)
                else None
            ),
            validation_label=(
                str(effect["validation_label"])
                if effect.get("validation_label") is not None
                else None
            ),
            validation_timeout_seconds=(
                int(effect["validation_timeout_seconds"])
                if effect.get("validation_timeout_seconds") is not None
                else None
            ),
            registry_path=registry_path,
            goal_id=goal_id,
        )
        if completion_validation is None:
            raise RuntimeError("Todo completion validation effect produced no receipt")
        transaction = reduce_todo_completion_transaction(
            todo=todo,
            projection_source=projection_source,
            completion_turn_key=completion_turn_key,
            no_followup=no_followup,
            dry_run=dry_run,
            completion_identity_source=completion_identity_source,
            goal_id=goal_id,
            todo_id=todo_id,
            requested_has_successor=requested_has_successor,
            validation_receipt=completion_validation,
            completion_policy_request=completion_policy_source,
        )
    if transaction["decision"] != "reject":
        return {
            "failure": None,
            "source_authority": source_authority,
            "source_snapshot": source_snapshot,
            "completion_policy_source": completion_policy_source,
            "transaction": transaction,
        }
    failure_payload = transaction["failure"]
    completion_validation = dict(failure_payload["validation_receipt"])
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
    return {
        "failure": failure,
        "source_authority": source_authority,
        "source_snapshot": source_snapshot,
        "completion_policy_source": completion_policy_source,
        "transaction": transaction,
    }


def completion_policy_source_from_state(
    *,
    registry_path: Path,
    goal_id: str,
    lines: list[str],
    successor_todo_ids: list[str],
    event_fields: Mapping[str, Any] | None,
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Project lock-comparable facts for the TS completion policy."""

    return build_completion_policy_request(
        registry_path=registry_path,
        goal_id=goal_id,
        claimed_by=facts.get("claimed_by"),
        next_claimed_by=facts.get("next_claimed_by"),
        next_agent_todo=facts.get("next_agent_todo"),
        next_action_kind=facts.get("next_action_kind"),
        next_continuation_policy=facts.get("next_continuation_policy"),
        next_excluded_agents=facts.get("next_excluded_agents") or [],
        self_merged=bool(facts.get("self_merged")),
        evidence=facts.get("evidence"),
        linked_successors=linked_successors_from_state(
            lines=lines,
            successor_todo_ids=successor_todo_ids,
            event_fields=event_fields,
        ),
    )
def prepare_user_todo_update_completion(
    *,
    status: str | None,
    state_file: Path,
    todo_id: str,
    role: str | None,
    registry_path: Path,
    goal_id: str,
    dry_run: bool,
    no_followup: bool,
    requested_has_successor: bool,
) -> dict[str, Any] | None:
    """Prepare the coarse transaction for a direct user-Todo completion."""

    if normalize_todo_status(status) != TODO_STATUS_DONE:
        return None
    match = find_todo_block(
        state_file.read_text(encoding="utf-8").splitlines(),
        todo_id=todo_id,
        role=role,
    )
    if match is None or (role or match[0]) == "agent":
        return None
    return run_completion_validation_gate_with_source(
        state_file=state_file,
        todo_id=todo_id,
        role=role,
        registry_path=registry_path,
        goal_id=goal_id,
        dry_run=dry_run,
        no_followup=no_followup,
        requested_has_successor=requested_has_successor,
    )


def locked_todo_completion_source(
    *,
    lines: list[str],
    state_file: Path,
    project: Path | None,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    role: str | None,
) -> tuple[Any, dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve the materialized or event-projected Todo under the write lock."""

    match = find_todo_block(lines, todo_id=todo_id, role=role)
    if match:
        item_role, _section, _start, _end, block = match
        todo = dict(block)
        todo["role"] = item_role
        return match, todo, None
    event_context = event_projection_todo_context(
        registry_path=registry_path,
        goal_id=goal_id,
        state_path=state_file,
        todo_id=todo_id,
        role=role,
    )
    if event_context is None:
        return None, None, None
    event_context["state_file"] = state_file
    event_context["project"] = project
    todo = dict(event_context["item"])
    todo["role"] = event_context["role"]
    return None, todo, event_context
