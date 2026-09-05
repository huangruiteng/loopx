"""Convert private TraeX JSONL into ATIF and a public-safe route receipt."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import ExitStack
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...file_lock import (
    ExclusiveFileLockLease,
    exclusive_file_lock,
    lock_timeout_error_fields,
)
from ...registry import atomic_write_json as _registry_atomic_write_json
from .route_receipt import (
    BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION,
    PublicIdentityKind,
    normalize_benchmark_model_route_receipt_v1,
    normalize_public_identity_token,
    normalize_public_route_label,
    normalize_sensitive_values,
    public_identity_digest,
)

TRAE_BENCHMARK_EVIDENCE_SCHEMA_VERSION = "benchmark_trae_evidence_capture_v0"
BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION = "benchmark_model_route_receipt_v0"
ATIF_SCHEMA_VERSION = "ATIF-v1.7"
TRAE_EVIDENCE_PAIR_PUBLICATION_CONTRACT = {
    "isolation": "ordered_per_output_lock_leases",
    "failure_recovery": "ownership_checked_rollback",
    "crash_atomic": False,
}

_SHA256_LENGTH = 64


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_route_binding(
    *,
    run_id: str | None,
    arm_id: str | None,
    launch_binding_digest: str | None,
    authority: str | None,
    sensitive_values: Iterable[str],
) -> dict[str, str] | None:
    values = (run_id, arm_id, launch_binding_digest, authority)
    if not any(value is not None for value in values):
        return None
    if not all(value is not None for value in values):
        raise ValueError("benchmark_model_route_binding_incomplete")
    if not isinstance(launch_binding_digest, str):
        raise TypeError("benchmark_model_route_launch_binding_digest_invalid")
    digest = launch_binding_digest.strip()
    if len(digest) != _SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError("benchmark_model_route_launch_binding_digest_invalid")
    return {
        "run_id": normalize_public_identity_token(
            run_id,
            field="run_id",
            kind=PublicIdentityKind.RUN,
            sensitive_values=sensitive_values,
        ),
        "arm_id": normalize_public_identity_token(
            arm_id,
            field="arm_id",
            kind=PublicIdentityKind.ARM,
            sensitive_values=sensitive_values,
        ),
        "launch_binding_digest": digest,
        "authority": normalize_public_identity_token(
            authority,
            field="authority",
            kind=PublicIdentityKind.AUTHORITY,
            sensitive_values=sensitive_values,
        ),
    }


def _text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, Mapping) and isinstance(item.get("text"), str):
            parts.append(str(item["text"]))
    return "\n".join(parts)


def _tool_arguments(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _runtime_route(events: Iterable[Mapping[str, Any]]) -> list[tuple[str, str, str]]:
    routes: list[tuple[str, str, str]] = []
    for event in events:
        if event.get("type") != "event_msg":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping) or payload.get("type") != "token_count":
            continue
        context = payload.get("context")
        if not isinstance(context, Mapping):
            info = payload.get("info")
            context = info.get("context") if isinstance(info, Mapping) else None
        if not isinstance(context, Mapping):
            continue
        raw_model = context.get("model")
        raw_provider = context.get("modelProviderId")
        raw_variant = context.get("modelBackendVariant")
        if raw_model is not None and not isinstance(raw_model, str):
            raise TypeError("traex_runtime_route_model_invalid")
        if raw_provider is not None and not isinstance(raw_provider, str):
            raise TypeError("traex_runtime_route_provider_invalid")
        if raw_variant is not None and not isinstance(raw_variant, str):
            raise TypeError("traex_runtime_route_backend_variant_invalid")
        model = (raw_model or "").strip()
        provider = (raw_provider or "").strip()
        variant = (raw_variant or "").strip()
        if model and provider:
            route = (model, provider, variant)
            if route not in routes:
                routes.append(route)
    return routes


def build_traex_model_route_receipt(
    events: Iterable[Mapping[str, Any]],
    *,
    requested_model: str,
    requested_provider: str = "trae",
    run_id: str | None = None,
    arm_id: str | None = None,
    launch_binding_digest: str | None = None,
    authority: str | None = None,
    sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Reduce runtime route observations without copying prompts or paths."""

    secrets = normalize_sensitive_values(sensitive_values)
    model = normalize_public_route_label(
        requested_model, field="requested_model", sensitive_values=secrets
    )
    provider = normalize_public_route_label(
        requested_provider, field="requested_provider", sensitive_values=secrets
    )
    binding = _normalize_route_binding(
        run_id=run_id,
        arm_id=arm_id,
        launch_binding_digest=launch_binding_digest,
        authority=authority,
        sensitive_values=secrets,
    )
    routes = _runtime_route(events)
    if not routes:
        status = "route_requested_not_runtime_audited"
        matched = False
    elif len(routes) != 1:
        status = "runtime_route_ambiguous"
        matched = False
    else:
        observed_model, observed_provider, _variant = routes[0]
        matched = (
            observed_model.casefold() == model.casefold()
            and observed_provider.casefold() == provider.casefold()
        )
        status = "runtime_route_verified" if matched else "runtime_route_mismatch"

    receipt: dict[str, Any] = {
        "schema_version": (
            BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
            if binding is not None
            else BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION
        ),
        "runtime": "traex",
        "requested_model": model,
        "requested_provider": provider,
        "status": status,
        "runtime_audited": bool(routes),
        "matched": matched,
        "observed_route_count": len(routes),
        "raw_content_recorded": False,
        "input_path_recorded": False,
    }
    if binding is not None:
        receipt.update(binding)
    if len(routes) == 1:
        observed_model, observed_provider, observed_variant = routes[0]
        receipt["observed_model"] = normalize_public_route_label(
            observed_model, field="observed_model", sensitive_values=secrets
        )
        receipt["observed_provider"] = normalize_public_route_label(
            observed_provider,
            field="observed_provider",
            sensitive_values=secrets,
        )
        if observed_variant:
            receipt["observed_backend_variant"] = public_identity_digest(
                observed_variant, kind=PublicIdentityKind.BACKEND_VARIANT
            )
    return receipt


def _archived_items(events: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    response_items: list[Mapping[str, Any]] = []
    for event in events:
        if event.get("type") != "response_item":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("traex_archive_response_item_invalid")
        response_items.append(payload)
    if response_items:
        return response_items

    items: list[Mapping[str, Any]] = []
    for event in events:
        if event.get("type") != "history_mutation":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        operation = payload.get("operation")
        if operation not in {"append", "replace"}:
            raise ValueError("traex_history_mutation_operation_unsupported")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("traex_history_mutation_items_invalid")
        if not all(isinstance(item, Mapping) for item in raw_items):
            raise ValueError("traex_history_mutation_item_invalid")
        if operation == "replace":
            items = list(raw_items)
        else:
            items.extend(raw_items)
    return items


def _append_archived_steps(
    items: Iterable[Mapping[str, Any]],
    steps: list[dict[str, Any]],
) -> None:
    pending: dict[str, dict[str, Any]] = {}
    for item in items:
        item_type = item.get("type")
        if item_type in {"function_call", "custom_tool_call"}:
            call_id = str(item.get("call_id") or item.get("id") or "")
            if not call_id or call_id in pending:
                raise ValueError("traex_function_call_identity_invalid")
            arguments_field = (
                "input" if item_type == "custom_tool_call" else "arguments"
            )
            step: dict[str, Any] = {
                "step_id": str(len(steps) + 1),
                "source": "agent",
                "message": "",
                "tool_calls": [
                    {
                        "function_name": str(item.get("name") or "unknown"),
                        "arguments": _tool_arguments(item.get(arguments_field) or {}),
                    }
                ],
            }
            steps.append(step)
            pending[call_id] = step
        elif item_type in {"function_call_output", "custom_tool_call_output"}:
            call_id = str(item.get("call_id") or "")
            if call_id not in pending:
                raise ValueError("traex_function_call_output_unmatched")
            step = pending.pop(call_id)
            step["observation"] = item.get("output")
        elif item_type == "message":
            role = item.get("role")
            if role not in {"assistant", "developer", "system", "user"}:
                raise ValueError("traex_archive_message_role_unsupported")
            if role == "assistant":
                message = _text_content(item.get("content"))
                if message:
                    steps.append(
                        {
                            "step_id": str(len(steps) + 1),
                            "source": "agent",
                            "message": message,
                            "tool_calls": [],
                        }
                    )
        elif item_type != "reasoning":
            raise ValueError("traex_archive_action_unsupported")
    if pending:
        raise ValueError("traex_function_call_output_missing")


def _append_stdout_steps(
    events: Iterable[Mapping[str, Any]],
    steps: list[dict[str, Any]],
) -> None:
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, Mapping):
            raise ValueError("traex_stdout_item_invalid")
        item_type = item.get("type")
        if item_type == "command_execution":
            command = str(item.get("command") or "")
            if not command:
                raise ValueError("traex_stdout_command_missing")
            steps.append(
                {
                    "step_id": str(len(steps) + 1),
                    "source": "agent",
                    "message": "",
                    "tool_calls": [
                        {
                            "function_name": "exec_command",
                            "arguments": {"cmd": command},
                        }
                    ],
                    "observation": {
                        "output": item.get("aggregated_output"),
                        "exit_code": item.get("exit_code"),
                    },
                }
            )
        elif item_type == "file_change":
            changes = item.get("changes")
            if not isinstance(changes, list) or not all(
                isinstance(change, Mapping) for change in changes
            ):
                raise ValueError("traex_stdout_file_changes_invalid")
            steps.append(
                {
                    "step_id": str(len(steps) + 1),
                    "source": "agent",
                    "message": "",
                    "tool_calls": [
                        {
                            "function_name": "apply_patch",
                            "arguments": {"changes": changes},
                        }
                    ],
                    "observation": {"status": item.get("status")},
                }
            )
        elif item_type == "agent_message":
            message = str(item.get("text") or "")
            if message:
                steps.append(
                    {
                        "step_id": str(len(steps) + 1),
                        "source": "agent",
                        "message": message,
                        "tool_calls": [],
                    }
                )
        elif item_type not in {"error", "reasoning"}:
            raise ValueError("traex_stdout_action_unsupported")


def convert_traex_events_to_atif(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Convert TraeX stdout or archived events into a private ATIF trajectory."""

    event_list = list(events)
    steps: list[dict[str, Any]] = []
    archived_items = _archived_items(event_list)
    if archived_items:
        _append_archived_steps(archived_items, steps)
    else:
        _append_stdout_steps(event_list, steps)
    if not steps:
        raise ValueError("traex_trajectory_steps_missing")
    return {
        "schema_version": ATIF_SCHEMA_VERSION,
        "steps": steps,
    }


def _read_jsonl(source: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with source.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"traex_jsonl_line_invalid:{line_number}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"traex_jsonl_event_invalid:{line_number}")
            events.append(event)
    if not events:
        raise ValueError("traex_jsonl_empty")
    return events


def _thread_identities(events: Iterable[Mapping[str, Any]]) -> set[str]:
    identities: set[str] = set()
    for event in events:
        if event.get("type") == "thread.started":
            identity = str(event.get("thread_id") or "").strip()
        elif event.get("type") == "session_meta":
            payload = event.get("payload")
            identity = (
                str(payload.get("id") or "").strip()
                if isinstance(payload, Mapping)
                else ""
            )
        else:
            continue
        if identity:
            identities.add(identity)
    return identities


def _verify_route_source_binding(
    source_events: Iterable[Mapping[str, Any]],
    route_events: Iterable[Mapping[str, Any]],
) -> None:
    source_identities = _thread_identities(source_events)
    route_identities = _thread_identities(route_events)
    if (
        len(source_identities) != 1
        or len(route_identities) != 1
        or source_identities != route_identities
    ):
        raise ValueError("traex_route_source_identity_mismatch")


@dataclass(frozen=True, slots=True)
class _EvidenceFileSnapshot:
    content: bytes | None
    mode: int | None
    generation: tuple[int, int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class _PinnedEvidenceOutput:
    identity: str
    parent_fd: int
    parent_device: int
    parent_inode: int
    filename: str
    path: Path


_ACTIVE_PINNED_OUTPUTS: ContextVar[dict[str, _PinnedEvidenceOutput] | None] = (
    ContextVar("active_traex_evidence_outputs", default=None)
)


def _evidence_file_generation(
    info: os.stat_result,
) -> tuple[int, int, int, int]:
    """Return an identity that changes when an atomic writer replaces a file."""

    return (
        int(getattr(info, "st_dev", 0)),
        int(getattr(info, "st_ino", 0)),
        int(getattr(info, "st_birthtime_ns", 0)),
        int(getattr(info, "st_ctime_ns", 0)),
    )


class TraexEvidencePairPublishError(OSError):
    """Public-safe failure state for the serialized evidence-pair writer."""

    def __init__(
        self,
        *,
        classification: str = "publish_failed",
        write_state: str,
        rollback_verified: bool | None,
        failure_metadata: Mapping[str, object] | None = None,
    ) -> None:
        if classification not in {
            "lock_failed",
            "output_ancestor_symlink_rejected",
            "output_symlink_rejected",
            "snapshot_failed",
            "publish_failed",
        }:
            raise ValueError("traex_evidence_pair_classification_invalid")
        if write_state not in {
            "no_write_lock_failed",
            "no_write_output_ancestor_symlink_rejected",
            "no_write_output_symlink_rejected",
            "no_write_snapshot_failed",
            "rolled_back_verified",
            "unknown",
        }:
            raise ValueError("traex_evidence_pair_write_state_invalid")
        if write_state.startswith("no_write_") and rollback_verified is not None:
            raise ValueError("traex_evidence_pair_rollback_state_invalid")
        if write_state == "rolled_back_verified" and rollback_verified is not True:
            raise ValueError("traex_evidence_pair_rollback_state_invalid")
        self.classification = classification
        self.write_state = write_state
        self.rollback_verified = rollback_verified
        self.failure_metadata = dict(failure_metadata or {})
        super().__init__("traex_evidence_pair_publish_failed")


class _EvidenceOutputSymlinkState(Enum):
    FINAL_COMPONENT = (
        "output_symlink_rejected",
        "no_write_output_symlink_rejected",
    )
    ANCESTOR_COMPONENT = (
        "output_ancestor_symlink_rejected",
        "no_write_output_ancestor_symlink_rejected",
    )

    @property
    def classification(self) -> str:
        return self.value[0]

    @property
    def write_state(self) -> str:
        return self.value[1]


def _lexical_absolute_output(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _unresolved_absolute_output(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    # Joining, unlike abspath(), preserves ``..`` components so a symlink
    # hidden before one cannot disappear from the admission walk.
    return Path.cwd() / expanded


def _output_symlink_state(path: Path) -> _EvidenceOutputSymlinkState | None:
    """Inspect the lexical output chain without resolving symlink targets."""

    output = _unresolved_absolute_output(path)
    current = Path(output.anchor)
    components = output.parts[1:]
    for index, component in enumerate(components):
        if component == "..":
            current = current.parent
            continue
        current /= component
        try:
            mode = current.lstat().st_mode
        except (FileNotFoundError, NotADirectoryError):
            # Continue the lexical walk: a later ``..`` may return to an
            # existing component that still has to be inspected.
            continue
        if stat.S_ISLNK(mode):
            return (
                _EvidenceOutputSymlinkState.FINAL_COMPONENT
                if index == len(components) - 1
                else _EvidenceOutputSymlinkState.ANCESTOR_COMPONENT
            )
    return None


def _reject_symlink_outputs(paths: Iterable[Path]) -> None:
    """Reject final or ancestor symlinks before publication creates state."""

    for path in paths:
        state = _output_symlink_state(path)
        if state is not None:
            raise TraexEvidencePairPublishError(
                classification=state.classification,
                write_state=state.write_state,
                rollback_verified=None,
            )


def _directory_supports_case_insensitive_aliases(path: Path) -> bool:
    probe = Path(os.fspath(path).swapcase())
    if probe == path:
        return False
    try:
        return probe.exists() and probe.samefile(path)
    except OSError:
        return False


def _canonical_output_identity_path(path: Path) -> Path:
    lexical_output = _lexical_absolute_output(path)
    if _output_symlink_state(path) is not None:
        return lexical_output
    try:
        parent = lexical_output.parent.resolve(strict=False)
    except OSError:
        parent = lexical_output.parent
    filename = (
        lexical_output.name.casefold()
        if _directory_supports_case_insensitive_aliases(parent)
        else lexical_output.name
    )
    return parent / filename


def _evidence_output_identity(path: Path) -> str:
    canonical = _canonical_output_identity_path(path)
    rendered = os.fspath(canonical)
    if _directory_supports_case_insensitive_aliases(canonical.parent):
        return rendered.casefold()
    return os.path.normcase(rendered)


def _evidence_output_lock_target(identity: str) -> Path:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return Path(tempfile.gettempdir()) / "loopx-traex-evidence-outputs" / digest


def _ordered_evidence_lock_targets(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Return opaque per-output locks in one process-independent order.

    Locking each output serializes transactions whose path sets overlap. Sorting
    before acquisition prevents AB/BA deadlocks when writers request paths in a
    different order.
    """

    return tuple(
        _evidence_output_lock_target(identity)
        for identity in sorted({_evidence_output_identity(path) for path in paths})
    )


def _public_lock_failure_metadata(error: BaseException) -> dict[str, object]:
    fields = lock_timeout_error_fields(error)
    incident = fields.get("lock_timeout")
    incident = incident if isinstance(incident, Mapping) else {}
    action = incident.get("operator_action")
    action = action if isinstance(action, Mapping) else {}
    metadata = {
        "error_code": fields.get("error_code"),
        "incident_recorded": fields.get("incident_recorded"),
        "incident_channel": fields.get("incident_channel"),
        "lock_id": incident.get("lock_id"),
        "lock_policy": incident.get("policy"),
        "retry_mode": action.get("retry_mode"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _symlink_publish_error(
    state: _EvidenceOutputSymlinkState,
) -> TraexEvidencePairPublishError:
    return TraexEvidencePairPublishError(
        classification=state.classification,
        write_state=state.write_state,
        rollback_verified=None,
    )


def _directory_open_flags() -> int:
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    dir_fd_operations = (os.open, os.mkdir, os.stat, os.rename, os.unlink)
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required)
        or any(operation not in os.supports_dir_fd for operation in dir_fd_operations)
    ):
        raise OSError("secure_output_directory_handles_unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _open_directory_component(parent_fd: int, component: str, *, create: bool) -> int:
    flags = _directory_open_flags()
    try:
        return os.open(component, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(component, dir_fd=parent_fd)
        except FileExistsError:
            pass
        try:
            return os.open(component, flags, dir_fd=parent_fd)
        except OSError as error:
            try:
                mode = os.stat(
                    component, dir_fd=parent_fd, follow_symlinks=False
                ).st_mode
            except OSError:
                raise error
            if stat.S_ISLNK(mode):
                raise _symlink_publish_error(
                    _EvidenceOutputSymlinkState.ANCESTOR_COMPONENT
                ) from error
            raise
    except OSError as error:
        try:
            mode = os.stat(component, dir_fd=parent_fd, follow_symlinks=False).st_mode
        except OSError:
            raise error
        if stat.S_ISLNK(mode):
            raise _symlink_publish_error(
                _EvidenceOutputSymlinkState.ANCESTOR_COMPONENT
            ) from error
        raise


def _open_output_parent(path: Path, *, create: bool) -> int:
    output = _lexical_absolute_output(path)
    if not output.name or output.name in {".", ".."}:
        raise OSError("evidence_output_filename_invalid")
    current_fd = os.open(output.anchor, _directory_open_flags())
    try:
        for component in output.parent.parts[1:]:
            if component == ".":
                continue
            next_fd = _open_directory_component(
                current_fd, component, create=create and component != ".."
            )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _pin_evidence_output(path: Path) -> _PinnedEvidenceOutput:
    lexical_output = _lexical_absolute_output(path)
    parent_fd = _open_output_parent(path, create=True)
    try:
        parent_stat = os.fstat(parent_fd)
        return _PinnedEvidenceOutput(
            identity=_evidence_output_identity(path),
            parent_fd=parent_fd,
            parent_device=parent_stat.st_dev,
            parent_inode=parent_stat.st_ino,
            filename=lexical_output.name,
            path=path,
        )
    except BaseException:
        os.close(parent_fd)
        raise


def _assert_pinned_parent_current(output: _PinnedEvidenceOutput) -> None:
    try:
        current_fd = _open_output_parent(output.path, create=False)
    except TraexEvidencePairPublishError:
        raise
    except OSError as error:
        state = _output_symlink_state(output.path)
        if state is not None:
            raise _symlink_publish_error(state) from error
        raise
    try:
        current_stat = os.fstat(current_fd)
    finally:
        os.close(current_fd)
    if (current_stat.st_dev, current_stat.st_ino) != (
        output.parent_device,
        output.parent_inode,
    ):
        raise OSError("evidence_output_parent_replaced")


def _assert_pinned_outputs_current(
    outputs: Iterable[_PinnedEvidenceOutput],
) -> None:
    for output in outputs:
        _assert_pinned_parent_current(output)


def _active_pinned_output(path: Path) -> _PinnedEvidenceOutput | None:
    outputs = _ACTIVE_PINNED_OUTPUTS.get()
    if outputs is None:
        return None
    return outputs.get(_evidence_output_identity(path))


def _paths_overlap(left: Path, right: Path) -> bool:
    if _evidence_output_identity(left) == _evidence_output_identity(right):
        return True
    try:
        return left.samefile(right)
    except OSError:
        return False


def _open_pinned_output(
    output: _PinnedEvidenceOutput, *, flags: int, mode: int = 0o600
) -> int:
    try:
        return os.open(
            output.filename,
            flags | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=output.parent_fd,
        )
    except OSError as error:
        try:
            current_mode = os.stat(
                output.filename,
                dir_fd=output.parent_fd,
                follow_symlinks=False,
            ).st_mode
        except OSError:
            raise error
        if stat.S_ISLNK(current_mode):
            raise _symlink_publish_error(
                _EvidenceOutputSymlinkState.FINAL_COMPONENT
            ) from error
        raise


def _reject_pinned_final_symlink(output: _PinnedEvidenceOutput) -> None:
    try:
        mode = os.stat(
            output.filename,
            dir_fd=output.parent_fd,
            follow_symlinks=False,
        ).st_mode
    except FileNotFoundError:
        return
    if stat.S_ISLNK(mode):
        raise _symlink_publish_error(_EvidenceOutputSymlinkState.FINAL_COMPONENT)


def _read_opened_regular_file(descriptor: int) -> tuple[bytes, os.stat_result]:
    try:
        initial_stat = os.fstat(descriptor)
        if not stat.S_ISREG(initial_stat.st_mode):
            raise OSError("traex_evidence_output_not_regular")
        try:
            stream = os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            descriptor = -1
            raise
        descriptor = -1
        with stream:
            content = stream.read()
            current_stat = os.fstat(stream.fileno())
        if not stat.S_ISREG(current_stat.st_mode):
            raise OSError("traex_evidence_output_not_regular")
        return content, current_stat
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _assert_pinned_output_descriptor_current(
    output: _PinnedEvidenceOutput,
    descriptor_stat: os.stat_result,
) -> None:
    current_stat = os.stat(
        output.filename,
        dir_fd=output.parent_fd,
        follow_symlinks=False,
    )
    if stat.S_ISLNK(current_stat.st_mode):
        raise _symlink_publish_error(_EvidenceOutputSymlinkState.FINAL_COMPONENT)
    if not stat.S_ISREG(current_stat.st_mode):
        raise OSError("traex_evidence_output_not_regular")
    if (current_stat.st_dev, current_stat.st_ino) != (
        descriptor_stat.st_dev,
        descriptor_stat.st_ino,
    ):
        raise OSError("traex_evidence_output_replaced_during_readback")


def _read_pinned_evidence_file(path: Path) -> _EvidenceFileSnapshot:
    output = _active_pinned_output(path)
    if output is None:  # pragma: no cover - caller bug
        raise ValueError("traex_evidence_output_not_pinned")
    _assert_pinned_parent_current(output)
    try:
        descriptor = _open_pinned_output(
            output,
            flags=os.O_RDONLY | getattr(os, "O_NONBLOCK", 0),
        )
    except FileNotFoundError:
        _assert_pinned_parent_current(output)
        return _EvidenceFileSnapshot(content=None, mode=None)
    content, current_stat = _read_opened_regular_file(descriptor)
    _assert_pinned_parent_current(output)
    _assert_pinned_output_descriptor_current(output, current_stat)
    return _EvidenceFileSnapshot(
        content=content,
        mode=current_stat.st_mode & 0o777,
        generation=_evidence_file_generation(current_stat),
    )


def _snapshot_evidence_file(path: Path) -> _EvidenceFileSnapshot:
    output = _active_pinned_output(path)
    if output is not None:
        return _read_pinned_evidence_file(path)
    try:
        descriptor = os.open(
            os.fspath(path),
            os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0),
        )
    except FileNotFoundError:
        return _EvidenceFileSnapshot(content=None, mode=None)
    content, current_stat = _read_opened_regular_file(descriptor)
    return _EvidenceFileSnapshot(
        content=content,
        mode=current_stat.st_mode & 0o777,
        generation=_evidence_file_generation(current_stat),
    )


def _write_pinned_evidence_bytes(
    output: _PinnedEvidenceOutput,
    content: bytes,
    *,
    mode: int,
    require_current_parent: bool = True,
) -> None:
    if require_current_parent:
        _assert_pinned_parent_current(output)
    _reject_pinned_final_symlink(output)
    temporary_name = f".loopx-traex-evidence-{uuid4().hex}.tmp"
    descriptor = _open_pinned_output(
        _PinnedEvidenceOutput(
            identity=output.identity,
            parent_fd=output.parent_fd,
            parent_device=output.parent_device,
            parent_inode=output.parent_inode,
            filename=temporary_name,
            path=output.path,
        ),
        flags=os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode=0o600,
    )
    try:
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        if require_current_parent:
            _assert_pinned_parent_current(output)
        _reject_pinned_final_symlink(output)
        os.rename(
            temporary_name,
            output.filename,
            src_dir_fd=output.parent_fd,
            dst_dir_fd=output.parent_fd,
        )
        if require_current_parent:
            _assert_pinned_parent_current(output)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=output.parent_fd)
        except FileNotFoundError:
            pass


def _write_evidence_bytes(path: Path, content: bytes, *, mode: int) -> None:
    output = _active_pinned_output(path)
    if output is not None:
        _write_pinned_evidence_bytes(output, content, mode=mode)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.rollback.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_write_json(
    path: Path, payload: dict[str, Any], *, preserve_mode: bool = False
) -> None:
    output = _active_pinned_output(path)
    if output is None:
        _registry_atomic_write_json(path, payload, preserve_mode=preserve_mode)
        return
    mode = 0o600
    if preserve_mode:
        snapshot = _snapshot_evidence_file(path)
        if snapshot.mode is not None:
            mode = snapshot.mode
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_pinned_evidence_bytes(output, content, mode=mode)


def _expected_json_snapshot(
    payload: Mapping[str, Any], snapshot: _EvidenceFileSnapshot
) -> _EvidenceFileSnapshot:
    mode = snapshot.mode if snapshot.mode is not None else 0o600
    return _EvidenceFileSnapshot(
        content=(json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        ),
        mode=mode,
    )


def _restore_evidence_file(path: Path, snapshot: _EvidenceFileSnapshot) -> None:
    if snapshot.content is None:
        output = _active_pinned_output(path)
        if output is None:
            path.unlink(missing_ok=True)
        else:
            try:
                os.unlink(output.filename, dir_fd=output.parent_fd)
            except FileNotFoundError:
                pass
        return
    if snapshot.mode is None:  # pragma: no cover - invalid internal snapshot
        raise ValueError("traex_evidence_snapshot_mode_missing")
    output = _active_pinned_output(path)
    if output is None:
        _write_evidence_bytes(path, snapshot.content, mode=snapshot.mode)
    else:
        _write_pinned_evidence_bytes(
            output,
            snapshot.content,
            mode=snapshot.mode,
            require_current_parent=False,
        )


def _evidence_file_matches_snapshot(
    path: Path, snapshot: _EvidenceFileSnapshot
) -> bool:
    try:
        output = _active_pinned_output(path)
        if output is None:
            current = _snapshot_evidence_file(path)
        else:
            current = _read_pinned_evidence_file(path)
    except OSError:
        return False
    return (current.content, current.mode) == (snapshot.content, snapshot.mode)


def _evidence_file_matches_owned_generation(
    path: Path, snapshot: _EvidenceFileSnapshot
) -> bool:
    """Return true only while the visible file is the transaction's file."""

    if snapshot.generation is None:
        return False
    try:
        current = _snapshot_evidence_file(path)
    except OSError:
        return False
    return current == snapshot


def _check_lock_leases(leases: Iterable[ExclusiveFileLockLease]) -> None:
    for lease in leases:
        lease.check()


def _publish_evidence_pair(
    atif: Path,
    trajectory: dict[str, Any],
    route_path: Path,
    route_receipt: dict[str, Any],
) -> None:
    _reject_symlink_outputs((atif, route_path))
    phase = "locking"
    try:
        with ExitStack() as locks:
            lock_leases: list[ExclusiveFileLockLease] = []
            for lock_target in _ordered_evidence_lock_targets((atif, route_path)):
                lease = locks.enter_context(
                    exclusive_file_lock(
                        lock_target,
                        operation="traex_evidence_pair_publish",
                        expose_lease=True,
                    )
                )
                lock_leases.append(lease)
            _check_lock_leases(lock_leases)
            _reject_symlink_outputs((atif, route_path))
            phase = "snapshotting"
            pinned_outputs: dict[Path, _PinnedEvidenceOutput] = {}
            try:
                for path in (atif, route_path):
                    pinned_outputs[path] = _pin_evidence_output(path)
                token = _ACTIVE_PINNED_OUTPUTS.set(
                    {output.identity: output for output in pinned_outputs.values()}
                )
            except TraexEvidencePairPublishError:
                for output in pinned_outputs.values():
                    os.close(output.parent_fd)
                raise
            except Exception as snapshot_error:
                for output in pinned_outputs.values():
                    os.close(output.parent_fd)
                raise TraexEvidencePairPublishError(
                    classification="snapshot_failed",
                    write_state="no_write_snapshot_failed",
                    rollback_verified=None,
                ) from snapshot_error
            try:
                try:
                    snapshots = {
                        atif: _snapshot_evidence_file(atif),
                        route_path: _snapshot_evidence_file(route_path),
                    }
                    _assert_pinned_outputs_current(pinned_outputs.values())
                except TraexEvidencePairPublishError:
                    raise
                except Exception as snapshot_error:
                    raise TraexEvidencePairPublishError(
                        classification="snapshot_failed",
                        write_state="no_write_snapshot_failed",
                        rollback_verified=None,
                    ) from snapshot_error
                phase = "publishing"
                owned_snapshots: dict[Path, _EvidenceFileSnapshot] = {}
                try:
                    _check_lock_leases(lock_leases)
                    atomic_write_json(atif, trajectory, preserve_mode=True)
                    _check_lock_leases(lock_leases)
                    _assert_pinned_outputs_current(pinned_outputs.values())
                    owned_snapshots[atif] = _snapshot_evidence_file(atif)
                    if not _evidence_file_matches_snapshot(
                        atif, _expected_json_snapshot(trajectory, snapshots[atif])
                    ):
                        raise OSError("traex_evidence_atif_readback_mismatch")
                    _check_lock_leases(lock_leases)
                    atomic_write_json(route_path, route_receipt, preserve_mode=True)
                    _check_lock_leases(lock_leases)
                    _assert_pinned_outputs_current(pinned_outputs.values())
                    owned_snapshots[route_path] = _snapshot_evidence_file(route_path)
                    expected_snapshots = {
                        atif: _expected_json_snapshot(trajectory, snapshots[atif]),
                        route_path: _expected_json_snapshot(
                            route_receipt, snapshots[route_path]
                        ),
                    }
                    if not all(
                        _evidence_file_matches_snapshot(path, expected)
                        and _evidence_file_matches_owned_generation(
                            path, owned_snapshots[path]
                        )
                        for path, expected in expected_snapshots.items()
                    ):
                        raise OSError("traex_evidence_pair_readback_mismatch")
                    _check_lock_leases(lock_leases)
                except Exception as publish_error:
                    rollback_safe = True
                    try:
                        _check_lock_leases(lock_leases)
                    except OSError:
                        rollback_safe = False
                    if rollback_safe:
                        # A wrapper may report failure immediately after the
                        # durable replace. While every lease is still current,
                        # no conforming writer can have produced these exact
                        # bytes, so capture their generation for rollback.
                        expected_for_ownership = {
                            atif: _expected_json_snapshot(trajectory, snapshots[atif]),
                            route_path: _expected_json_snapshot(
                                route_receipt, snapshots[route_path]
                            ),
                        }
                        for path, expected in expected_for_ownership.items():
                            if path in owned_snapshots:
                                continue
                            try:
                                current = _snapshot_evidence_file(path)
                            except OSError:
                                continue
                            if (current.content, current.mode) == (
                                expected.content,
                                expected.mode,
                            ):
                                owned_snapshots[path] = current
                    if rollback_safe:
                        for path, owned in owned_snapshots.items():
                            if not _evidence_file_matches_owned_generation(path, owned):
                                rollback_safe = False
                                break
                    if rollback_safe:
                        for path, owned in owned_snapshots.items():
                            try:
                                _check_lock_leases(lock_leases)
                                if not _evidence_file_matches_owned_generation(
                                    path, owned
                                ):
                                    rollback_safe = False
                                    break
                                _restore_evidence_file(path, snapshots[path])
                                _check_lock_leases(lock_leases)
                            except Exception:
                                rollback_safe = False
                                break
                    rollback_verified = rollback_safe and all(
                        _evidence_file_matches_snapshot(path, snapshot)
                        for path, snapshot in snapshots.items()
                    )
                    classification = "publish_failed"
                    if isinstance(
                        publish_error, TraexEvidencePairPublishError
                    ) and publish_error.classification in {
                        "output_ancestor_symlink_rejected",
                        "output_symlink_rejected",
                    }:
                        classification = publish_error.classification
                    raise TraexEvidencePairPublishError(
                        classification=classification,
                        write_state=(
                            "rolled_back_verified" if rollback_verified else "unknown"
                        ),
                        rollback_verified=rollback_verified,
                    ) from publish_error
                phase = "published"
            finally:
                _ACTIVE_PINNED_OUTPUTS.reset(token)
                for output in pinned_outputs.values():
                    os.close(output.parent_fd)
    except TraexEvidencePairPublishError:
        raise
    except Exception as lock_error:
        if phase == "locking":
            raise TraexEvidencePairPublishError(
                classification="lock_failed",
                write_state="no_write_lock_failed",
                rollback_verified=None,
                failure_metadata=_public_lock_failure_metadata(lock_error),
            ) from lock_error
        raise TraexEvidencePairPublishError(
            classification="publish_failed",
            write_state="unknown",
            rollback_verified=False,
        ) from lock_error


def capture_traex_benchmark_evidence(
    *,
    source_jsonl: str | Path,
    atif_output: str | Path,
    route_receipt_output: str | Path,
    requested_model: str,
    requested_provider: str = "trae",
    route_source_jsonl: str | Path | None = None,
    run_id: str | None = None,
    arm_id: str | None = None,
    launch_binding_digest: str | None = None,
    authority: str | None = None,
    sensitive_values: Iterable[str] = (),
    require_runtime_route: bool = False,
    execute: bool = False,
) -> dict[str, Any]:
    """Write private ATIF plus a public-safe model route receipt."""

    if not isinstance(require_runtime_route, bool) or not isinstance(execute, bool):
        raise TypeError("traex_evidence_execution_flags_invalid")
    secrets = normalize_sensitive_values(sensitive_values)
    model = normalize_public_route_label(
        requested_model, field="requested_model", sensitive_values=secrets
    )
    provider = normalize_public_route_label(
        requested_provider, field="requested_provider", sensitive_values=secrets
    )
    binding = _normalize_route_binding(
        run_id=run_id,
        arm_id=arm_id,
        launch_binding_digest=launch_binding_digest,
        authority=authority,
        sensitive_values=secrets,
    )
    atif = Path(atif_output).expanduser()
    route_path = Path(route_receipt_output).expanduser()
    if execute:
        _reject_symlink_outputs((atif, route_path))
    source = Path(source_jsonl).expanduser()
    events = _read_jsonl(source)
    route_source = (
        Path(route_source_jsonl).expanduser()
        if route_source_jsonl is not None
        else source
    )
    if _paths_overlap(atif, route_path) or any(
        _paths_overlap(input_path, output_path)
        for input_path in (source, route_source)
        for output_path in (atif, route_path)
    ):
        raise ValueError("traex_evidence_paths_overlap")
    route_events = events if route_source == source else _read_jsonl(route_source)
    if route_source != source:
        _verify_route_source_binding(events, route_events)
    trajectory = convert_traex_events_to_atif(events)
    route_receipt = build_traex_model_route_receipt(
        route_events,
        requested_model=model,
        requested_provider=provider,
        run_id=binding["run_id"] if binding is not None else None,
        arm_id=binding["arm_id"] if binding is not None else None,
        launch_binding_digest=(
            binding["launch_binding_digest"] if binding is not None else None
        ),
        authority=binding["authority"] if binding is not None else None,
        sensitive_values=secrets,
    )
    if binding is not None:
        route_receipt = normalize_benchmark_model_route_receipt_v1(
            route_receipt, sensitive_values=secrets
        )
    route_verified = route_receipt["status"] == "runtime_route_verified"
    route_requirement_blocked = execute and require_runtime_route and not route_verified
    if execute and not route_requirement_blocked:
        _publish_evidence_pair(atif, trajectory, route_path, route_receipt)

    return {
        "ok": not route_requirement_blocked,
        "schema_version": TRAE_BENCHMARK_EVIDENCE_SCHEMA_VERSION,
        "status": (
            "runtime_route_not_verified"
            if route_requirement_blocked
            else "captured"
            if execute
            else "previewed"
        ),
        "source_runtime": "traex",
        "event_count": len(events),
        "route_event_count": len(route_events),
        "route_source_bound": True,
        "step_count": len(trajectory["steps"]),
        "tool_call_count": sum(
            len(step.get("tool_calls") or []) for step in trajectory["steps"]
        ),
        "trajectory_sha256": hashlib.sha256(
            _canonical_json(trajectory).encode("utf-8")
        ).hexdigest(),
        "private_atif_written": execute and not route_requirement_blocked,
        "route_receipt_written": execute and not route_requirement_blocked,
        "write_performed": execute and not route_requirement_blocked,
        "publication_contract": dict(TRAE_EVIDENCE_PAIR_PUBLICATION_CONTRACT),
        "model_route": route_receipt,
        "public_boundary": {
            "raw_content_recorded": False,
            "input_path_recorded": False,
            "output_path_recorded": False,
        },
    }


__all__ = [
    "ATIF_SCHEMA_VERSION",
    "BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION",
    "BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION",
    "TRAE_BENCHMARK_EVIDENCE_SCHEMA_VERSION",
    "TRAE_EVIDENCE_PAIR_PUBLICATION_CONTRACT",
    "TraexEvidencePairPublishError",
    "build_traex_model_route_receipt",
    "normalize_benchmark_model_route_receipt_v1",
    "capture_traex_benchmark_evidence",
    "convert_traex_events_to_atif",
]
