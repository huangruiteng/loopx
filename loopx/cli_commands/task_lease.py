from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from ..control_plane.turn_effect import normalize_turn_effect_key
from ..control_plane.work_items.task_lease import (
    TaskLeaseError,
    inspect_task_lease,
    hold_task_lease_fence,
    release_task_lease,
    renew_task_lease,
    runtime_root_from_registry,
    task_lease_path,
    transfer_task_lease,
)
from ..control_plane.work_items.task_lease_settlement import (
    execute_task_lease_settlement,
)
from ..file_lock import LockAcquireTimeoutError
from ..presentation.markdown import append_operator_action_markdown


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def add_turn_effect_fence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--turn-effect-key", help=argparse.SUPPRESS)
    parser.add_argument("--turn-fence-todo-id", help=argparse.SUPPRESS)
    parser.add_argument("--turn-fence-idempotency-key", help=argparse.SUPPRESS)
    parser.add_argument("--turn-fencing-token", help=argparse.SUPPRESS)


def turn_effect_key_from_args(args: argparse.Namespace) -> str | None:
    return normalize_turn_effect_key(getattr(args, "turn_effect_key", None))


def turn_effect_fence_requested(args: argparse.Namespace) -> bool:
    return any(
        str(getattr(args, attr, None) or "").strip()
        for attr in (
            "turn_effect_key",
            "turn_fence_todo_id",
            "turn_fence_idempotency_key",
            "turn_fencing_token",
        )
    )


@contextmanager
def hold_cli_turn_effect_fence(
    args: argparse.Namespace,
    *,
    runtime_root: Path,
    goal_id: str,
    owner: str | None,
) -> Iterator[None]:
    values = {
        "--turn-effect-key": getattr(args, "turn_effect_key", None),
        "--turn-fence-todo-id": getattr(args, "turn_fence_todo_id", None),
        "--turn-fence-idempotency-key": getattr(
            args,
            "turn_fence_idempotency_key",
            None,
        ),
        "--turn-fencing-token": getattr(args, "turn_fencing_token", None),
    }
    supplied = {flag for flag, value in values.items() if str(value or "").strip()}
    if not supplied:
        yield
        return
    missing = sorted(set(values) - supplied)
    if missing:
        raise ValueError(
            "Turn effect fencing requires all internal fence arguments; missing: "
            + ", ".join(missing)
        )
    if not str(owner or "").strip():
        raise ValueError("Turn effect fencing requires --agent-id")
    turn_effect_key_from_args(args)
    with hold_task_lease_fence(
        runtime_root=runtime_root,
        goal_id=goal_id,
        todo_id=str(values["--turn-fence-todo-id"]),
        owner=str(owner),
        idempotency_key=str(values["--turn-fence-idempotency-key"]),
        fencing_token=str(values["--turn-fencing-token"]),
        operation="cli_turn_effect",
    ):
        yield


def render_task_lease_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# LoopX Task Lease",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- action: `{payload.get('action')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    if payload.get("error_code"):
        lines.append(f"- error_code: `{payload.get('error_code')}`")
    lease = payload.get("lease")
    if isinstance(lease, dict):
        lines.extend(
            [
                f"- goal_id: `{lease.get('goal_id')}`",
                f"- todo_id: `{lease.get('todo_id')}`",
                f"- owner: `{lease.get('owner')}`",
                f"- version: `{lease.get('version')}`",
                f"- expires_at: `{lease.get('expires_at')}`",
                f"- write_scopes: `{', '.join(lease.get('write_scopes') or [])}`",
            ]
        )
    if payload.get("lease_path"):
        lines.append(f"- lease_path: `{payload.get('lease_path')}`")
    conflicts = payload.get("conflicts")
    if isinstance(conflicts, list) and conflicts:
        lines.append("- conflicts:")
        for conflict in conflicts:
            if not isinstance(conflict, dict):
                continue
            lines.append(
                f"  - `{conflict.get('todo_id')}` owner=`{conflict.get('owner')}` "
                f"expires_at=`{conflict.get('expires_at')}` "
                f"write_scopes=`{', '.join(conflict.get('write_scopes') or [])}`"
            )
    append_operator_action_markdown(lines, payload)
    return "\n".join(lines)


def register_task_lease_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "task-lease",
        help="Acquire, renew, transfer, release, or inspect a per-(goal_id,todo_id) hard task lease.",
    )
    add_subcommand_format(parser)
    parser.add_argument(
        "task_lease_command",
        choices=["acquire", "renew", "transfer", "release", "inspect"],
        help="Lease lifecycle action.",
    )
    parser.add_argument("--goal-id", required=True, help="Goal id that owns the todo.")
    parser.add_argument("--todo-id", required=True, help="Structured todo id such as todo_ab12cd34ef56.")
    parser.add_argument("--owner", help="Registered public-safe agent id that owns the lease.")
    parser.add_argument("--idempotency-key", help="Public-safe token used for idempotent retries and CAS.")
    parser.add_argument("--new-owner", help="For transfer, target registered public-safe agent id.")
    parser.add_argument("--new-idempotency-key", help="For transfer, target idempotency key.")
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        help="Lease TTL in seconds. Defaults to 45 minutes and is capped at 24 hours.",
    )
    parser.add_argument(
        "--write-scope",
        dest="write_scopes",
        action="append",
        help="Relative write scope protected by this lease, such as loopx/**. Repeatable.",
    )
    parser.add_argument(
        "--expected-version",
        type=int,
        help="Optional CAS version that must match the current lease version.",
    )


def _requires_owner(args: argparse.Namespace) -> bool:
    return args.task_lease_command in {"acquire", "renew", "transfer", "release"}


def handle_task_lease_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: Callable[..., str],
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "task-lease":
        return None
    try:
        if _requires_owner(args) and not args.owner:
            raise ValueError("task-lease action requires --owner")
        if _requires_owner(args) and not args.idempotency_key:
            raise ValueError("task-lease action requires --idempotency-key")
        runtime_root = runtime_root_from_registry(registry_path, runtime_root_arg)
        if args.task_lease_command == "acquire":
            result = execute_task_lease_settlement(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                owner=args.owner,
                todo_id=args.todo_id,
                idempotency_key=args.idempotency_key,
                write_scopes=args.write_scopes,
                ttl_seconds=args.ttl_seconds,
                expected_version=args.expected_version,
                acquire=True,
            )
            lease_path = task_lease_path(
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
            )
            if result.failure is not None:
                failure_details = result.failure.details
                original_code = (
                    str(failure_details.get("task_lease_error_code"))
                    if isinstance(failure_details, dict)
                    and failure_details.get("task_lease_error_code")
                    else result.failure.kind.value
                )
                payload = {
                    "ok": False,
                    "schema_version": "task_lease_v0",
                    "action": "acquire",
                    "error": str(result.failure.reason),
                    "error_code": original_code,
                    "lease_path": str(lease_path),
                    "settlement": {
                        "effect_id": (
                            result.receipts[-1].effect_id if result.receipts else None
                        ),
                        "receipts": [
                            {
                                "step": receipt.step_kind.value,
                                "status": receipt.status,
                                "effect_id": receipt.effect_id,
                            }
                            for receipt in result.receipts
                        ],
                        "failure": {
                            "step": result.failure.step_kind.value,
                            "kind": result.failure.kind.value,
                            "code": original_code,
                        },
                    },
                }
                if isinstance(failure_details, dict):
                    if failure_details.get("conflicts") is not None:
                        payload["conflicts"] = failure_details["conflicts"]
                    if failure_details.get("lease") is not None:
                        payload["lease"] = failure_details["lease"]
            else:
                lease = result.value if isinstance(result.value, dict) else {}
                idempotent = any(
                    receipt.status == "idempotent" for receipt in result.receipts
                )
                payload = {
                    "ok": True,
                    "schema_version": "task_lease_v0",
                    "action": "acquire",
                    "acquired": not idempotent,
                    "idempotent": idempotent,
                    "lease": lease,
                    "lease_path": str(lease_path),
                    "settlement": {
                        "effect_id": (
                            result.receipts[-1].effect_id if result.receipts else None
                        ),
                        "receipts": [
                            {
                                "step": receipt.step_kind.value,
                                "status": receipt.status,
                                "effect_id": receipt.effect_id,
                            }
                            for receipt in result.receipts
                        ],
                    },
                }
        elif args.task_lease_command == "renew":
            if args.write_scopes:
                raise ValueError("task-lease renew does not accept --write-scope")
            payload = renew_task_lease(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                owner=args.owner,
                idempotency_key=args.idempotency_key,
                ttl_seconds=args.ttl_seconds,
                expected_version=args.expected_version,
            )
        elif args.task_lease_command == "transfer":
            if args.write_scopes:
                raise ValueError("task-lease transfer does not accept --write-scope")
            if not args.new_owner or not args.new_idempotency_key:
                raise ValueError("task-lease transfer requires --new-owner and --new-idempotency-key")
            payload = transfer_task_lease(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                owner=args.owner,
                idempotency_key=args.idempotency_key,
                new_owner=args.new_owner,
                new_idempotency_key=args.new_idempotency_key,
                ttl_seconds=args.ttl_seconds,
                expected_version=args.expected_version,
            )
        elif args.task_lease_command == "release":
            if args.write_scopes:
                raise ValueError("task-lease release does not accept --write-scope")
            if args.ttl_seconds is not None:
                raise ValueError("task-lease release does not accept --ttl-seconds")
            payload = release_task_lease(
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                owner=args.owner,
                idempotency_key=args.idempotency_key,
                expected_version=args.expected_version,
            )
        else:
            unsupported = [
                flag
                for flag, value in (
                    ("--owner", args.owner),
                    ("--idempotency-key", args.idempotency_key),
                    ("--new-owner", args.new_owner),
                    ("--new-idempotency-key", args.new_idempotency_key),
                    ("--ttl-seconds", args.ttl_seconds),
                    ("--write-scope", args.write_scopes),
                    ("--expected-version", args.expected_version),
                )
                if value
            ]
            if unsupported:
                raise ValueError("task-lease inspect only accepts --goal-id and --todo-id; unsupported: " + ", ".join(unsupported))
            payload = inspect_task_lease(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
            )
    except TaskLeaseError as exc:
        payload = {
            "ok": False,
            "schema_version": "task_lease_v0",
            "action": getattr(args, "task_lease_command", None),
            "error": str(exc),
            "error_code": exc.code,
            **exc.payload,
        }
    except LockAcquireTimeoutError as exc:
        payload = {
            "ok": False,
            "schema_version": "task_lease_v0",
            "action": getattr(args, "task_lease_command", None),
            "error": str(exc),
            **exc.to_payload(),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "task_lease_v0",
            "action": getattr(args, "task_lease_command", None),
            "error": str(exc),
            "error_code": exc.__class__.__name__,
        }
    print_payload(payload, output_format(args), render_task_lease_markdown)
    return 0 if payload.get("ok") else 1
