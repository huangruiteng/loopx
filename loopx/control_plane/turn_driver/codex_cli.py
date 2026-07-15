"""Native Codex CLI host for one governed LoopX Turn."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...runtime import validate_goal_id_path_segment
from .executor import (
    HOST_RESULT_TEXT_LIMITS,
    BuiltInHostError,
    LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION,
)
from .transaction import LOOPX_TURN_RESULT_SCHEMA_VERSION, TRANSACTION_PHASES


CODEX_CLI_SESSION_SCHEMA_VERSION = "loopx_codex_cli_session_v0"
CODEX_CLI_RESULT_KINDS = (
    "validated_progress",
    "repair_required",
    "replan_required",
    "user_action_required",
    "wait",
)
CODEX_CLI_SANDBOXES = ("read-only", "workspace-write")
SESSION_ID_MAX_CHARS = 256


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _lineage(request: Mapping[str, Any]) -> dict[str, str]:
    envelope = _mapping(request.get("turn_envelope"))
    action = _mapping(envelope.get("action"))
    todo = _mapping(action.get("selected_todo"))
    lineage = {
        "goal_id": str(envelope.get("goal_id") or "").strip(),
        "agent_id": str(envelope.get("agent_id") or "").strip(),
        "todo_id": str(todo.get("todo_id") or "").strip(),
    }
    if not all(lineage.values()):
        raise ValueError("Codex CLI host request has incomplete turn lineage")
    lineage["goal_id"] = validate_goal_id_path_segment(lineage["goal_id"])
    return lineage


def _session_path(runtime_root: Path, lineage: Mapping[str, str]) -> Path:
    digest = hashlib.sha256(
        json.dumps(
            dict(lineage),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return (
        runtime_root
        / "goals"
        / validate_goal_id_path_segment(lineage["goal_id"])
        / "turn-sessions"
        / f"{digest}.json"
    )


def _valid_session_id(value: Any) -> str | None:
    session_id = str(value or "").strip()
    if not session_id or len(session_id) > SESSION_ID_MAX_CHARS:
        return None
    if any(character in session_id for character in ("\x00", "\r", "\n")):
        return None
    return session_id


def load_codex_cli_session(
    runtime_root: Path,
    *,
    lineage: Mapping[str, str],
) -> dict[str, Any] | None:
    path = _session_path(runtime_root, lineage)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != CODEX_CLI_SESSION_SCHEMA_VERSION:
        return None
    if any(value.get(field) != lineage[field] for field in lineage):
        return None
    session_id = _valid_session_id(value.get("session_id"))
    if not session_id:
        return None
    return {**value, "session_id": session_id}


def codex_cli_session_binding(
    runtime_root: Path,
    turn_envelope: Mapping[str, Any],
) -> dict[str, str] | None:
    request = {"turn_envelope": dict(turn_envelope)}
    lineage = _lineage(request)
    if load_codex_cli_session(runtime_root, lineage=lineage) is None:
        return None
    return {
        "schema_version": "loopx_turn_session_binding_v0",
        **lineage,
    }


def _store_codex_cli_session(
    runtime_root: Path,
    *,
    lineage: Mapping[str, str],
    session_id: str,
) -> None:
    normalized_session_id = _valid_session_id(session_id)
    if not normalized_session_id:
        raise ValueError("Codex CLI returned an invalid session id")
    path = _session_path(runtime_root, lineage)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": CODEX_CLI_SESSION_SCHEMA_VERSION,
                    **lineage,
                    "host": "codex-cli",
                    "session_id": normalized_session_id,
                },
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def codex_cli_result_schema() -> dict[str, Any]:
    text_limits = dict(HOST_RESULT_TEXT_LIMITS)
    properties: dict[str, Any] = {
        "schema_version": {
            "type": "string",
            "enum": [LOOPX_TURN_RESULT_SCHEMA_VERSION],
        },
        "turn_key": {"type": "string"},
        "result_kind": {"type": "string", "enum": list(CODEX_CLI_RESULT_KINDS)},
        "completed_phases": {
            "type": "array",
            "items": {"type": "string", "enum": list(TRANSACTION_PHASES[:2])},
            "minItems": 2,
            "maxItems": 2,
        },
        "classification": {
            "type": "string",
            "maxLength": text_limits["classification"],
        },
        "recommended_action": {
            "type": "string",
            "maxLength": text_limits["recommended_action"],
        },
        "next_action": {
            "type": "string",
            "maxLength": text_limits["next_action"],
        },
        "delivery_batch_scale": {
            "type": "string",
            "enum": [
                "",
                "test_only",
                "single_surface",
                "multi_surface",
                "implementation",
            ],
        },
        "delivery_outcome": {
            "type": "string",
            "enum": [
                "",
                "surface_only",
                "outcome_gap",
                "outcome_progress",
                "primary_goal_outcome",
            ],
        },
        "vision_unchanged_reason": {
            "type": "string",
            "maxLength": text_limits["vision_unchanged_reason"],
        },
        "summary": {"type": "string", "maxLength": text_limits["summary"]},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _prompt(request: Mapping[str, Any]) -> str:
    request_json = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "\n".join(
        [
            "Execute exactly one bounded LoopX Turn in the current workspace.",
            "Use the TurnEnvelope as the source of truth. Perform work only when its contract allows it.",
            "Do not write LoopX state, spend quota, or apply scheduler changes; the adapter owns those effects.",
            "Return only the schema-constrained result. For validated_progress, repair_required, or replan_required, fill every material field with public-safe evidence.",
            "For user_action_required or wait, leave material-only fields empty and explain the stop in summary.",
            'completed_phases must be exactly ["host_execute","typed_result"], and turn_key must match the request.',
            "Turn request:",
            request_json,
        ]
    )


def _event_session_id(event: Mapping[str, Any]) -> str | None:
    if event.get("type") not in {"thread.started", "thread_started"}:
        return None
    for candidate in (
        event.get("thread_id"),
        event.get("threadId"),
        event.get("session_id"),
        _mapping(event.get("thread")).get("id"),
    ):
        session_id = _valid_session_id(candidate)
        if session_id:
            return session_id
    return None


def _stderr_failure_category(line: str) -> str | None:
    text = line.lower()
    if "requires a newer version of codex" in text:
        return "model_requires_newer_codex"
    if "invalid_json_schema" in text or ("output schema" in text and "invalid" in text):
        return "output_schema_rejected"
    if any(
        marker in text
        for marker in ("unauthorized", "authentication failed", "login required")
    ):
        return "auth_failed"
    if any(
        marker in text
        for marker in ("rate limit", "too many requests", "quota exceeded")
    ):
        return "rate_limited"
    if "session" in text and "not found" in text:
        return "session_missing"
    return None


def _terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            proc.kill()


def _codex_command(
    *,
    codex_bin: str,
    project: Path,
    schema_path: Path,
    output_path: Path,
    sandbox: str,
    model: str | None,
    session_id: str | None,
) -> list[str]:
    if session_id:
        command = [
            codex_bin,
            "exec",
            "resume",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--json",
        ]
    else:
        command = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "-C",
            str(project),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--json",
        ]
    if model:
        command.extend(["--model", model])
    if session_id:
        command.append(session_id)
    command.append("-")
    return command


def run_codex_cli_host(
    request: Mapping[str, Any],
    *,
    runtime_root: Path,
    project: Path,
    codex_bin: str = "codex",
    sandbox: str = "read-only",
    model: str | None = None,
    timeout_seconds: float = 115.0,
) -> dict[str, Any]:
    if request.get("schema_version") != LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION:
        raise ValueError("unsupported LoopX Turn host request schema")
    if sandbox not in CODEX_CLI_SANDBOXES:
        raise ValueError("Codex CLI sandbox must be read-only or workspace-write")
    resolved = shutil.which(codex_bin) if os.path.sep not in codex_bin else codex_bin
    if not resolved or not Path(resolved).exists():
        raise ValueError("Codex CLI executable is unavailable")
    lineage = _lineage(request)
    binding = load_codex_cli_session(runtime_root, lineage=lineage)
    planned_session = _mapping(request.get("session"))
    planned_action = str(planned_session.get("action") or "")
    if planned_action == "resume" and binding is None:
        raise RuntimeError("Codex CLI resume binding disappeared after planning")
    if planned_action == "start_new" and binding is not None:
        raise RuntimeError("Codex CLI session binding changed after planning")
    if planned_action not in {"resume", "start_new"}:
        raise ValueError("Codex CLI host request has no executable session action")
    session_id = str(binding.get("session_id")) if binding else None

    with tempfile.TemporaryDirectory(prefix="loopx-turn-codex-") as directory:
        temporary = Path(directory)
        schema_path = temporary / "result-schema.json"
        output_path = temporary / "last-message.json"
        schema_path.write_text(
            json.dumps(
                codex_cli_result_schema(), ensure_ascii=False, separators=(",", ":")
            ),
            encoding="utf-8",
        )
        command = _codex_command(
            codex_bin=str(resolved),
            project=project,
            schema_path=schema_path,
            output_path=output_path,
            sandbox=sandbox,
            model=model,
            session_id=session_id,
        )
        proc = subprocess.Popen(
            command,
            cwd=project,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        observed_session: list[str] = []
        failure_categories: list[str] = []

        def discard_events() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    candidate = _event_session_id(event)
                    if candidate and not observed_session:
                        observed_session.append(candidate)

        reader = threading.Thread(target=discard_events, daemon=True)

        def discard_stderr() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                category = _stderr_failure_category(line)
                if category and not failure_categories:
                    failure_categories.append(category)

        stderr_reader = threading.Thread(target=discard_stderr, daemon=True)
        reader.start()
        stderr_reader.start()
        assert proc.stdin is not None
        try:
            proc.stdin.write(_prompt(request))
            proc.stdin.close()
            returncode = proc.wait(timeout=max(1.0, timeout_seconds))
        except subprocess.TimeoutExpired as exc:
            _terminate_process(proc)
            raise BuiltInHostError("codex_cli_timeout") from exc
        finally:
            reader.join(timeout=2)
            stderr_reader.join(timeout=2)
        if observed_session:
            _store_codex_cli_session(
                runtime_root,
                lineage=lineage,
                session_id=observed_session[0],
            )
        if returncode != 0:
            category = failure_categories[0] if failure_categories else "exit_nonzero"
            raise BuiltInHostError(f"codex_cli_{category}")
        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BuiltInHostError("codex_cli_final_result_missing") from exc
        if not isinstance(result, dict):
            raise BuiltInHostError("codex_cli_final_result_not_object")
        return result
