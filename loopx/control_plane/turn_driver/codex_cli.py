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

from ...authority import validate_public_safe_text
from ...runtime import validate_goal_id_path_segment
from .executor import (
    HOST_AGENT_VISION_JSON_MAX_CHARS,
    HOST_RESULT_TEXT_LIMITS,
    BuiltInHostError,
    LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION,
)
from .model_usage import advisor_model_usage, direct_model_usage, event_usage
from .transaction import LOOPX_TURN_RESULT_SCHEMA_VERSION, TRANSACTION_PHASES


CODEX_CLI_SESSION_SCHEMA_VERSION = "loopx_codex_cli_session_v1"
LOOPX_TURN_ADVISOR_SCHEMA_VERSION = "loopx_turn_advisor_v0"
LOOPX_TURN_ADVISOR_CONTEXT_SCHEMA_VERSION = "loopx_turn_advisor_context_v0"
_ADVISOR_CONTEXT_MAX_FILES = 8
_ADVISOR_CONTEXT_MAX_BYTES = 24_000
CODEX_CLI_RESULT_KINDS = (
    "validated_progress",
    "repair_required",
    "replan_required",
    "user_action_required",
    "wait",
)
CODEX_CLI_SANDBOXES = ("read-only", "workspace-write")
SESSION_ID_MAX_CHARS = 256
SESSION_INVALIDATING_FAILURE_CATEGORIES = frozenset(
    {
        "model_requires_newer_codex",
        "output_schema_rejected",
        "session_missing",
    }
)


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


def _discard_codex_cli_session(
    runtime_root: Path,
    *,
    lineage: Mapping[str, str],
) -> None:
    _session_path(runtime_root, lineage).unlink(missing_ok=True)


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
        "path_delta_mode": {
            "type": "string",
            "enum": ["", "unchanged", "material_replan"],
        },
        "agent_vision_json": {
            "type": "string",
            "maxLength": HOST_AGENT_VISION_JSON_MAX_CHARS,
        },
        "summary": {"type": "string", "maxLength": text_limits["summary"]},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _prompt(
    request: Mapping[str, Any],
    *,
    advisor: Mapping[str, Any] | None = None,
) -> str:
    request_json = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    lines = [
            "Execute exactly one bounded LoopX Turn in the current workspace.",
            "Use the TurnEnvelope as the source of truth. Perform work only when its contract allows it.",
            "Do not write LoopX state, spend quota, or apply scheduler changes; the adapter owns those effects.",
            "Return only the schema-constrained result. For validated_progress, repair_required, or replan_required, fill every material field with public-safe evidence.",
            "For those material results, set path_delta_mode=material_replan only when this Turn changes a prior assumption, route, scope, acceptance rule, or stops prior work; then provide a complete bounded agent vision packet with goal_path_delta_v0 in agent_vision_json and leave vision_unchanged_reason empty.",
            "For routine continuation, retry, successor creation, or no-change replanning, set path_delta_mode=unchanged, leave agent_vision_json empty, and provide vision_unchanged_reason.",
            "For user_action_required or wait, leave material-only fields empty and explain the stop in summary.",
            'completed_phases must be exactly ["host_execute","typed_result"], and turn_key must match the request.',
            "Turn request:",
            request_json,
        ]
    if advisor is not None:
        lines.extend(
            [
                "A read-only advisor produced the following bounded guidance. Treat it as non-authoritative advice: the TurnEnvelope, repository evidence, and independent validator still control execution.",
                json.dumps(
                    dict(advisor),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ]
        )
    return "\n".join(lines)


def codex_cli_advisor_schema() -> dict[str, Any]:
    item = {"type": "string", "minLength": 1, "maxLength": 400}
    properties: dict[str, Any] = {
        "schema_version": {
            "type": "string",
            "enum": [LOOPX_TURN_ADVISOR_SCHEMA_VERSION],
        },
        "turn_key": {"type": "string"},
        "summary": {"type": "string", "minLength": 1, "maxLength": 400},
        "recommendations": {
            "type": "array",
            "items": item,
            "maxItems": 4,
        },
        "risks": {"type": "array", "items": item, "maxItems": 4},
        "validation_focus": {
            "type": "array",
            "items": item,
            "maxItems": 4,
        },
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _advisor_workspace_context(
    request: Mapping[str, Any], *, project: Path
) -> dict[str, Any]:
    envelope = _mapping(request.get("turn_envelope"))
    boundary = _mapping(envelope.get("boundary"))
    raw_scope = boundary.get("write_scope")
    scopes = raw_scope if isinstance(raw_scope, list) else []
    root = project.resolve()
    files: list[dict[str, str]] = []
    used_bytes = 0
    for raw_path in scopes:
        relative = str(raw_path or "").strip()
        if (
            not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or any(marker in relative for marker in ("*", "?", "[", "]"))
        ):
            continue
        candidate = project / relative
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        size = len(content.encode("utf-8"))
        if size > _ADVISOR_CONTEXT_MAX_BYTES - used_bytes:
            continue
        files.append({"path": relative, "content": content})
        used_bytes += size
        if len(files) >= _ADVISOR_CONTEXT_MAX_FILES:
            break
    return {
        "schema_version": LOOPX_TURN_ADVISOR_CONTEXT_SCHEMA_VERSION,
        "files": files,
    }


def _advisor_prompt(
    request: Mapping[str, Any], *, workspace_context: Mapping[str, Any]
) -> str:
    return "\n".join(
        [
            "Advise on exactly one bounded LoopX Turn.",
            "No repository is mounted. Do not invoke workspace tools. Use only the bounded context packet below.",
            "Do not execute the todo, write LoopX state, spend quota, or change scheduler state.",
            "The TurnEnvelope remains authoritative. Return only compact implementation guidance, risks, and independent validation focus in the required schema; do not include hidden reasoning.",
            "Turn request:",
            json.dumps(
                dict(request),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "Bounded workspace context:",
            json.dumps(
                dict(workspace_context),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        ]
    )


def _normalize_advisor_result(
    value: Any,
    *,
    turn_key: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BuiltInHostError("codex_cli_advisor_result_not_object")
    expected_fields = {
        "schema_version",
        "turn_key",
        "summary",
        "recommendations",
        "risks",
        "validation_focus",
    }
    if set(value) != expected_fields:
        raise BuiltInHostError("codex_cli_advisor_result_contract_invalid")
    if value.get("schema_version") != LOOPX_TURN_ADVISOR_SCHEMA_VERSION:
        raise BuiltInHostError("codex_cli_advisor_result_contract_invalid")
    if value.get("turn_key") != turn_key:
        raise BuiltInHostError("codex_cli_advisor_turn_key_mismatch")
    normalized: dict[str, Any] = {
        "schema_version": LOOPX_TURN_ADVISOR_SCHEMA_VERSION,
        "turn_key": turn_key,
    }
    for field in ("summary", "recommendations", "risks", "validation_focus"):
        raw_items = [value.get(field)] if field == "summary" else value.get(field)
        if not isinstance(raw_items, list) or len(raw_items) > (1 if field == "summary" else 4):
            raise BuiltInHostError("codex_cli_advisor_result_contract_invalid")
        items: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if not text or len(text) > 400:
                raise BuiltInHostError("codex_cli_advisor_result_contract_invalid")
            try:
                validate_public_safe_text(f"advisor.{field}", text)
            except ValueError as exc:
                raise BuiltInHostError("codex_cli_advisor_result_not_public_safe") from exc
            items.append(text)
        normalized[field] = items[0] if field == "summary" else items
    return normalized


def codex_cli_event_session_id(event: Mapping[str, Any]) -> str | None:
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


def codex_cli_session_id_from_jsonl(value: str) -> str | None:
    """Return the first opaque Codex thread id from an exec JSONL stream."""

    for line in value.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, Mapping):
            if session_id := codex_cli_event_session_id(event):
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
    ephemeral: bool = False,
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
        if ephemeral:
            command.insert(2, "--ephemeral")
    if model:
        command.extend(["--model", model])
    if session_id:
        command.append(session_id)
    command.append("-")
    return command


def _run_codex_process(
    command: list[str],
    *,
    project: Path,
    prompt: str,
    output_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
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
    observed_usage: list[dict[str, int]] = []

    def consume_events() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                candidate = codex_cli_event_session_id(event)
                if candidate and not observed_session:
                    observed_session.append(candidate)
                usage = event_usage(event)
                if usage is not None:
                    observed_usage.append(usage)

    def consume_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            category = _stderr_failure_category(line)
            if category and not failure_categories:
                failure_categories.append(category)

    reader = threading.Thread(target=consume_events, daemon=True)
    stderr_reader = threading.Thread(target=consume_stderr, daemon=True)
    reader.start()
    stderr_reader.start()
    assert proc.stdin is not None
    timed_out = False
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
        returncode = proc.wait(timeout=max(1.0, timeout_seconds))
    except subprocess.TimeoutExpired:
        _terminate_process(proc)
        timed_out = True
        returncode = proc.returncode
    finally:
        reader.join(timeout=2)
        stderr_reader.join(timeout=2)
    result: Any = None
    if not timed_out and returncode == 0:
        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = None
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "session_id": observed_session[0] if observed_session else None,
        "failure_category": (
            failure_categories[0] if failure_categories else "exit_nonzero"
        ),
        "usage": observed_usage[-1] if observed_usage else None,
        "result": result,
    }


def run_codex_cli_host(
    request: Mapping[str, Any],
    *,
    runtime_root: Path,
    project: Path,
    codex_bin: str = "codex",
    sandbox: str = "read-only",
    model: str | None = None,
    advisor_model: str | None = None,
    advisor_timeout_seconds: float = 60.0,
    timeout_seconds: float = 115.0,
) -> dict[str, Any]:
    if request.get("schema_version") != LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION:
        raise ValueError("unsupported LoopX Turn host request schema")
    if sandbox not in CODEX_CLI_SANDBOXES:
        raise ValueError("Codex CLI sandbox must be read-only or workspace-write")
    if advisor_model and (not model or advisor_model == model):
        raise ValueError(
            "Codex CLI advisor mode requires distinct explicit advisor and executor models"
        )
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
        advisor: dict[str, Any] | None = None
        advisor_usage: dict[str, int] | None = None
        advisor_context = (
            _advisor_workspace_context(request, project=project)
            if advisor_model
            else None
        )
        if advisor_model and advisor_context and advisor_context["files"]:
            advisor_project = temporary / "advisor-workspace"
            advisor_project.mkdir()
            advisor_schema_path = temporary / "advisor-schema.json"
            advisor_output_path = temporary / "advisor-message.json"
            advisor_schema_path.write_text(
                json.dumps(
                    codex_cli_advisor_schema(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            advisor_command = _codex_command(
                codex_bin=str(resolved),
                project=advisor_project,
                schema_path=advisor_schema_path,
                output_path=advisor_output_path,
                sandbox="read-only",
                model=advisor_model,
                session_id=None,
                ephemeral=True,
            )
            advisor_invocation = _run_codex_process(
                advisor_command,
                project=advisor_project,
                prompt=_advisor_prompt(
                    request,
                    workspace_context=advisor_context,
                ),
                output_path=advisor_output_path,
                timeout_seconds=advisor_timeout_seconds,
            )
            if advisor_invocation["timed_out"]:
                raise BuiltInHostError("codex_cli_advisor_timeout")
            if advisor_invocation["returncode"] != 0:
                raise BuiltInHostError(
                    "codex_cli_advisor_"
                    + str(advisor_invocation["failure_category"])
                )
            advisor = _normalize_advisor_result(
                advisor_invocation["result"],
                turn_key=str(request.get("turn_key") or ""),
            )
            usage_value = advisor_invocation.get("usage")
            advisor_usage = dict(usage_value) if isinstance(usage_value, Mapping) else None
            if advisor_usage is None:
                raise BuiltInHostError("codex_cli_advisor_usage_missing")
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
        invocation = _run_codex_process(
            command,
            project=project,
            prompt=_prompt(request, advisor=advisor),
            output_path=output_path,
            timeout_seconds=timeout_seconds,
        )
        observed_session = (
            [str(invocation["session_id"])] if invocation.get("session_id") else []
        )
        timed_out = invocation["timed_out"]
        returncode = invocation["returncode"]
        if timed_out:
            if observed_session:
                _store_codex_cli_session(
                    runtime_root,
                    lineage=lineage,
                    session_id=observed_session[0],
                )
            raise BuiltInHostError("codex_cli_timeout")
        category = str(invocation["failure_category"])
        if returncode != 0 and category in SESSION_INVALIDATING_FAILURE_CATEGORIES:
            _discard_codex_cli_session(runtime_root, lineage=lineage)
        if observed_session:
            if returncode == 0 or category not in SESSION_INVALIDATING_FAILURE_CATEGORIES:
                _store_codex_cli_session(
                    runtime_root,
                    lineage=lineage,
                    session_id=observed_session[0],
                )
        if returncode != 0:
            raise BuiltInHostError(f"codex_cli_{category}")
        result = invocation.get("result")
        if result is None:
            raise BuiltInHostError("codex_cli_final_result_missing")
        if not isinstance(result, dict):
            raise BuiltInHostError("codex_cli_final_result_not_object")
        executor_usage_value = invocation.get("usage")
        executor_usage = (
            dict(executor_usage_value)
            if isinstance(executor_usage_value, Mapping)
            else None
        )
        if advisor is not None:
            if executor_usage is None or advisor_usage is None:
                raise BuiltInHostError("codex_cli_executor_usage_missing")
            result["model_usage"] = advisor_model_usage(
                advisor=advisor_usage,
                executor=executor_usage,
                advice=advisor,
            )
        elif executor_usage is not None:
            result["model_usage"] = direct_model_usage(executor_usage)
        return result
