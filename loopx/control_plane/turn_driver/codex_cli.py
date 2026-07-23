"""Native Codex CLI host for one governed LoopX Turn."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...authority import validate_public_safe_text
from ...runtime import validate_goal_id_path_segment
from .executor import (
    HOST_AGENT_VISION_JSON_MAX_CHARS,
    HOST_RESULT_TEXT_LIMITS,
    BuiltInHostError,
    LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION,
    validate_loopx_turn_host_result,
)
from .model_usage import (
    advisor_decision_receipt,
    advisor_model_usage,
    aggregate_provider_usage,
    direct_model_usage,
    event_usage,
    latest_cumulative_provider_usage,
    normalize_provider_usage,
    provider_usage_delta,
)
from .transaction import LOOPX_TURN_RESULT_SCHEMA_VERSION, TRANSACTION_PHASES


CODEX_CLI_SESSION_SCHEMA_VERSION = "loopx_codex_cli_session_v2"
LOOPX_TURN_ADVISOR_SCHEMA_VERSION = "loopx_turn_advisor_v0"
LOOPX_TURN_ADVISOR_CONTEXT_SCHEMA_VERSION = "loopx_turn_advisor_context_v0"
LOOPX_TURN_COMPLEXITY_CHECKPOINT_SCHEMA_VERSION = (
    "loopx_turn_complexity_checkpoint_v0"
)
_ADVISOR_CONTEXT_MAX_FILES = 8
_ADVISOR_CONTEXT_MAX_BYTES = 24_000
_COMPLEXITY_SIGNALS = (
    "cross_file_reasoning",
    "ambiguous_root_cause",
    "invariant_risk",
    "validation_uncertainty",
    "external_contract",
)
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
    usage_baseline = normalize_provider_usage(value.get("usage_baseline"))
    if usage_baseline is None:
        return None
    return {
        **value,
        "session_id": session_id,
        "usage_baseline": usage_baseline,
    }


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
    usage_baseline: Mapping[str, int] | None = None,
) -> None:
    normalized_session_id = _valid_session_id(session_id)
    if not normalized_session_id:
        raise ValueError("Codex CLI returned an invalid session id")
    normalized_baseline = (
        normalize_provider_usage(usage_baseline)
        if usage_baseline is not None
        else None
    )
    existing = load_codex_cli_session(runtime_root, lineage=lineage)
    if (
        normalized_baseline is None
        and existing is not None
        and existing.get("session_id") == normalized_session_id
    ):
        normalized_baseline = dict(existing["usage_baseline"])
    if normalized_baseline is None:
        normalized_baseline = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
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
                    "usage_baseline": normalized_baseline,
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


_FINAL_RESULT_INSTRUCTIONS = (
    "For validated_progress, repair_required, or replan_required, fill every material field with public-safe evidence.",
    "For those material results, set path_delta_mode=material_replan only when this Turn changes a prior assumption, route, scope, acceptance rule, or stops prior work; then provide a complete bounded agent vision packet with goal_path_delta_v0 in agent_vision_json and leave vision_unchanged_reason empty.",
    "For routine continuation, retry, successor creation, or no-change replanning, set path_delta_mode=unchanged, leave agent_vision_json empty, and provide vision_unchanged_reason.",
    "For user_action_required or wait, leave material-only fields empty and explain the stop in summary.",
    'completed_phases must be exactly ["host_execute","typed_result"], and turn_key must match the request.',
)


def _prompt(
    request: Mapping[str, Any],
    *,
    advisor: Mapping[str, Any] | None = None,
    complexity_checkpoint: Mapping[str, Any] | None = None,
    advisor_failure_category: str | None = None,
) -> str:
    request_json = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    lines = [
        "Execute exactly one bounded LoopX Turn in the current workspace.",
        "Use the TurnEnvelope as the source of truth. Perform work only when its contract allows it.",
        "Do not write LoopX state, spend quota, or apply scheduler changes; the adapter owns those effects.",
        "Return only the schema-constrained result.",
        *_FINAL_RESULT_INSTRUCTIONS,
        "Turn request:",
        request_json,
    ]
    if complexity_checkpoint is not None:
        lines.extend(
            [
                "Continue from the complexity checkpoint produced earlier in this same executor session.",
                json.dumps(
                    dict(complexity_checkpoint),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ]
        )
        if complexity_checkpoint.get("complexity") == "simple":
            lines.extend(
                [
                    "The checkpoint found no reason to request Advisor guidance.",
                    "Now execute and validate the bounded Turn normally, then return its final typed result.",
                ]
            )
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
                "This is the execution phase, not another planning checkpoint. When the Turn has a write scope, invoke workspace tools to inspect, edit, and validate before returning the typed result; never claim an edit that tools did not perform.",
            ]
        )
    elif advisor_failure_category:
        lines.extend(
            [
                "Advisor review was triggered but unavailable. Continue independently from verified repository evidence; do not wait or invent guidance.",
                f"Bounded advisor failure category: {advisor_failure_category}",
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


def codex_cli_complexity_checkpoint_schema() -> dict[str, Any]:
    item = {"type": "string", "minLength": 1, "maxLength": 400}
    properties: dict[str, Any] = {
        "schema_version": {
            "type": "string",
            "enum": [LOOPX_TURN_COMPLEXITY_CHECKPOINT_SCHEMA_VERSION],
        },
        "turn_key": {"type": "string"},
        "complexity": {"type": "string", "enum": ["simple", "complex"]},
        "signals": {
            "type": "array",
            "items": {"type": "string", "enum": list(_COMPLEXITY_SIGNALS)},
            "maxItems": 4,
        },
        "evidence_summary": item,
        "relevant_paths": {"type": "array", "items": item, "maxItems": 8},
        "open_questions": {"type": "array", "items": item, "maxItems": 4},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _complexity_checkpoint_prompt(request: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "Begin exactly one bounded LoopX Turn in the current workspace.",
            "Use the TurnEnvelope as the source of truth. Inspect only enough repository evidence to classify the work; do not modify files or run the requested implementation yet.",
            "Return exactly one schema-constrained complexity checkpoint.",
            "Classify simple only when the root cause, patch boundary, preserved invariant, and focused validation are all clear; use no complexity signals or open questions.",
            "Classify complex when strong-model review could change the implementation plan, and name only supported signals, repository-relative relevant paths, verified evidence, and unresolved questions.",
            "Do not write LoopX state, spend quota, or apply scheduler changes; the adapter owns those effects.",
            "Turn request:",
            json.dumps(
                dict(request),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        ]
    )


def _normalize_complexity_checkpoint(
    value: Any,
    *,
    turn_key: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BuiltInHostError("codex_cli_complexity_checkpoint_not_object")
    expected_fields = {
        "schema_version",
        "turn_key",
        "complexity",
        "signals",
        "evidence_summary",
        "relevant_paths",
        "open_questions",
    }
    if set(value) != expected_fields:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
    if value.get("schema_version") != LOOPX_TURN_COMPLEXITY_CHECKPOINT_SCHEMA_VERSION:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
    if value.get("turn_key") != turn_key:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_turn_key_mismatch")
    complexity = str(value.get("complexity") or "")
    if complexity not in {"simple", "complex"}:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")

    normalized: dict[str, Any] = {
        "schema_version": LOOPX_TURN_COMPLEXITY_CHECKPOINT_SCHEMA_VERSION,
        "turn_key": turn_key,
        "complexity": complexity,
    }
    for field, maximum in (("signals", 4), ("relevant_paths", 8), ("open_questions", 4)):
        raw_items = value.get(field)
        if not isinstance(raw_items, list) or len(raw_items) > maximum:
            raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
        items: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if not text or len(text) > 400:
                raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
            if field == "signals" and text not in _COMPLEXITY_SIGNALS:
                raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
            if field == "relevant_paths":
                path = Path(text)
                if path.is_absolute() or ".." in path.parts:
                    raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
            try:
                validate_public_safe_text(f"complexity_checkpoint.{field}", text)
            except ValueError as exc:
                raise BuiltInHostError(
                    "codex_cli_complexity_checkpoint_not_public_safe"
                ) from exc
            items.append(text)
        normalized[field] = items
    evidence_summary = str(value.get("evidence_summary") or "").strip()
    if not evidence_summary or len(evidence_summary) > 400:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
    try:
        validate_public_safe_text(
            "complexity_checkpoint.evidence_summary", evidence_summary
        )
    except ValueError as exc:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_not_public_safe") from exc
    normalized["evidence_summary"] = evidence_summary
    if complexity == "simple" and (
        normalized["signals"] or normalized["open_questions"]
    ):
        raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
    if complexity == "complex" and not normalized["signals"]:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_contract_invalid")
    return normalized


def _advisor_workspace_context(
    request: Mapping[str, Any],
    *,
    project: Path,
    complexity_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = _mapping(request.get("turn_envelope"))
    boundary = _mapping(envelope.get("boundary"))
    raw_scope = boundary.get("write_scope")
    scopes = list(raw_scope) if isinstance(raw_scope, list) else []
    if complexity_checkpoint is not None:
        relevant_paths = complexity_checkpoint.get("relevant_paths")
        if isinstance(relevant_paths, list):
            scopes.extend(relevant_paths)
    root = project.resolve()
    files: list[dict[str, str]] = []
    used_bytes = 0
    request_text = json.dumps(dict(request), ensure_ascii=False)
    request_anchors = list(
        dict.fromkeys(
            match.group(1)
            for match in re.finditer(
                r"\b[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)\b",
                request_text,
            )
        )
    )
    pending: list[tuple[str, list[str]]] = [
        (str(item), request_anchors) for item in scopes
    ]
    seen: set[str] = set()
    while pending and len(files) < _ADVISOR_CONTEXT_MAX_FILES:
        raw_path, anchors = pending.pop(0)
        relative = str(raw_path or "").strip()
        if (
            not relative
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or any(marker in relative for marker in ("*", "?", "[", "]"))
        ):
            continue
        seen.add(relative)
        candidate = project / relative
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        remaining = _ADVISOR_CONTEXT_MAX_BYTES - used_bytes
        if remaining <= 0:
            continue
        per_file_budget = min(12_000, remaining)
        excerpt = _advisor_source_excerpt(
            content, anchors=anchors, max_bytes=per_file_budget
        )
        if not excerpt:
            continue
        files.append({"path": relative, "content": excerpt})
        used_bytes += len(excerpt.encode("utf-8"))
        if candidate.suffix == ".py":
            pending.extend(
                _advisor_python_dependencies(
                    relative, content=content, excerpt=excerpt, project=project
                )
            )
    return {
        "schema_version": LOOPX_TURN_ADVISOR_CONTEXT_SCHEMA_VERSION,
        "files": files,
    }


def _advisor_source_excerpt(
    content: str, *, anchors: list[str], max_bytes: int
) -> str:
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    center = 0
    for anchor in anchors:
        match = re.search(rf"\bdef\s+{re.escape(anchor)}\b", content)
        if match:
            center = len(content[: match.start()].encode("utf-8"))
            break
    start = max(0, center - max_bytes // 4)
    end = min(len(encoded), start + max_bytes)
    start = max(0, end - max_bytes)
    excerpt = encoded[start:end].decode("utf-8", errors="ignore")
    if start:
        excerpt = "# ... preceding source omitted ...\n" + excerpt
    if end < len(encoded):
        excerpt += "\n# ... following source omitted ..."
    while len(excerpt.encode("utf-8")) > max_bytes:
        excerpt = excerpt[:-1]
    return excerpt


def _advisor_python_dependencies(
    relative: str, *, content: str, excerpt: str, project: Path
) -> list[tuple[str, list[str]]]:
    dependencies: list[tuple[str, list[str]]] = []
    for match in re.finditer(
        r"^from\s+(\.+[A-Za-z0-9_.]*)\s+import\s+([^\n]+)$",
        content,
        flags=re.MULTILINE,
    ):
        module, imported = match.groups()
        dots = len(module) - len(module.lstrip("."))
        module_parts = [part for part in module[dots:].split(".") if part]
        base = Path(relative).parent
        for _ in range(max(0, dots - 1)):
            base = base.parent
        dependency = base.joinpath(*module_parts).with_suffix(".py")
        if not (project / dependency).is_file():
            continue
        for raw_name in imported.split(","):
            imported_name = raw_name.strip().split(" as ")[-1].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", imported_name):
                continue
            anchors = list(
                dict.fromkeys(
                    found.group(1)
                    for found in re.finditer(
                        rf"\b{re.escape(imported_name)}\.([A-Za-z_][A-Za-z0-9_]*)\b",
                        excerpt,
                    )
                )
            )
            if anchors:
                dependencies.append((str(dependency), anchors))
                break
    return dependencies


def _advisor_prompt(
    request: Mapping[str, Any],
    *,
    workspace_context: Mapping[str, Any],
    complexity_checkpoint: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "Review one complex checkpoint from a cheaper executor working on a bounded LoopX Turn.",
            "No repository is mounted. Do not invoke workspace tools. Use only the bounded context packet below.",
            "Do not execute the todo, write LoopX state, spend quota, or change scheduler state.",
            "Challenge the executor's current plan: resolve its open questions, identify a missed invariant or counterexample, and narrow the smallest correct patch and focused validation.",
            "For every directly called public dependency included in the bounded context, explicitly test whether the same input contract applies at that boundary. Name every required file in the recommendations; do not recommend a caller-only patch until the dependency contract is ruled out with source evidence.",
            "Treat every counterpart explicitly named by the task as an acceptance candidate. When its source has the same input-type assumption, include it as a required change even if its current docstring does not advertise the contract; missing documentation is not evidence that the task excludes it.",
            "The TurnEnvelope boundary.write_scope is the only code scope. Do not narrow it from the todo title or primary path. Resolve conditional advice into a definite required-change or no-change conclusion using the supplied source excerpts.",
            "The TurnEnvelope remains authoritative. Return only compact corrective implementation guidance, risks, and independent validation focus in the required schema; do not include hidden reasoning.",
            "Keep the summary and every list item at or below 400 Unicode characters; prefer one concrete sentence per item.",
            "Turn request:",
            json.dumps(
                dict(request),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "Executor complexity checkpoint:",
            json.dumps(
                dict(complexity_checkpoint),
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
            if not text:
                raise BuiltInHostError("codex_cli_advisor_result_contract_invalid")
            if field == "recommendations" and re.match(
                r"(?i)^(optionally|if\b|consider\b)", text
            ):
                raise BuiltInHostError("codex_cli_advisor_result_contract_invalid")
            try:
                validate_public_safe_text(f"advisor.{field}", text)
            except ValueError as exc:
                raise BuiltInHostError("codex_cli_advisor_result_not_public_safe") from exc
            if len(text) > 400:
                text = text[:397].rstrip() + "..."
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


def _codex_cli_event_has_workspace_inspection(event: Mapping[str, Any]) -> bool:
    if event.get("type") not in {
        "item.started",
        "item.completed",
        "item_started",
        "item_completed",
        "response_item",
    }:
        return False
    item = event.get("item")
    if not isinstance(item, Mapping):
        payload = event.get("payload")
        item = payload if isinstance(payload, Mapping) else {}
    return item.get("type") in {
        "command_execution",
        "custom_tool_call",
        "function_call",
        "mcp_tool_call",
        "shell_command",
        "web_search_call",
    }


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
    dialect = _cli_dialect(codex_bin)
    if session_id:
        command = [
            codex_bin,
            "exec",
            "resume",
        ]
        if dialect == "traex":
            command.extend(
                [
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--permission-mode",
                    "custom",
                ]
            )
        command.extend(
            [
                "-c",
                'approval_policy="never"',
                "-c",
                f'sandbox_mode="{sandbox}"',
                "--skip-git-repo-check",
            ]
        )
        if dialect == "codex":
            command.extend(["--output-schema", str(schema_path)])
        command.extend(
            [
                "--output-last-message",
                str(output_path),
                "--json",
            ]
        )
    else:
        command = [
            codex_bin,
            "exec",
        ]
        if dialect == "traex":
            command.extend(["--ignore-user-config", "--ignore-rules"])
        command.extend([
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "-C",
            str(project),
            "--output-last-message",
            str(output_path),
            "--json",
        ])
        if dialect == "codex":
            output_index = command.index("--output-last-message")
            command[output_index:output_index] = ["--output-schema", str(schema_path)]
        if ephemeral:
            command.insert(2, "--ephemeral")
    if model:
        command.extend(["--model", model])
    if session_id:
        command.append(session_id)
    command.append("-")
    return command


def _cli_dialect(executable: str) -> str:
    name = Path(executable).name.lower()
    return "traex" if name in {"traex", "trae-cli", "traecli"} else "codex"


def _structured_prompt(prompt: str, *, schema_path: Path, dialect: str) -> str:
    if dialect != "traex":
        return prompt
    schema = schema_path.read_text(encoding="utf-8")
    return "\n".join(
        [
            prompt,
            "TraeX provider structured output is unavailable for this model.",
            "Return only one JSON object matching the exact schema below. Do not add Markdown fences or explanatory prose.",
            schema,
        ]
    )


def _read_structured_result(output_path: Path, *, dialect: str) -> Any:
    try:
        raw = output_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    if dialect != "traex":
        return None
    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL)
    if len(fenced) != 1:
        return None
    try:
        return json.loads(fenced[0])
    except json.JSONDecodeError:
        return None


def _traex_receipt_repair_command(
    command: list[str], *, session_id: str, output_path: Path
) -> list[str]:
    repaired = [
        command[0],
        "exec",
        "resume",
        "--ignore-user-config",
        "--ignore-rules",
        "--permission-mode",
        "custom",
        "-c",
        'approval_policy="never"',
        "-c",
        'sandbox_mode="read-only"',
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
        "--json",
    ]
    if "--model" in command:
        model_index = command.index("--model")
        repaired.extend(["--model", command[model_index + 1]])
    repaired.extend([session_id, "-"])
    return repaired


def _run_codex_process(
    command: list[str],
    *,
    project: Path,
    prompt: str,
    schema_path: Path,
    output_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    dialect = _cli_dialect(command[0])

    def invoke(
        active_command: list[str], active_prompt: str, active_timeout: float
    ) -> dict[str, Any]:
        proc = subprocess.Popen(
            active_command,
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
        workspace_inspection_observed = False

        def consume_events() -> None:
            nonlocal workspace_inspection_observed
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
                    if _codex_cli_event_has_workspace_inspection(event):
                        workspace_inspection_observed = True

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
            try:
                proc.stdin.write(active_prompt)
                proc.stdin.close()
            except BrokenPipeError:
                pass
            returncode = proc.wait(timeout=max(1.0, active_timeout))
        except subprocess.TimeoutExpired:
            _terminate_process(proc)
            timed_out = True
            returncode = proc.returncode
        finally:
            reader.join(timeout=2)
            stderr_reader.join(timeout=2)
        result = None
        if not timed_out and returncode == 0:
            result = _read_structured_result(output_path, dialect=dialect)
        return {
            "returncode": returncode,
            "timed_out": timed_out,
            "session_id": observed_session[0] if observed_session else None,
            "failure_category": (
                failure_categories[0] if failure_categories else "exit_nonzero"
            ),
            "usage": observed_usage[-1] if observed_usage else None,
            "workspace_inspection_observed": workspace_inspection_observed,
            "result": result,
        }

    invocation = invoke(
        command,
        _structured_prompt(prompt, schema_path=schema_path, dialect=dialect),
        timeout_seconds,
    )
    if (
        dialect == "traex"
        and invocation["returncode"] == 0
        and invocation["result"] is None
        and invocation["session_id"]
        and "--ephemeral" not in command
    ):
        repair_prompt = _structured_prompt(
            "Do not perform more workspace work. Your previous response was not a valid typed receipt. Re-emit only the final receipt for the work already completed.",
            schema_path=schema_path,
            dialect=dialect,
        )
        repair = invoke(
            _traex_receipt_repair_command(
                command,
                session_id=str(invocation["session_id"]),
                output_path=output_path,
            ),
            repair_prompt,
            min(timeout_seconds, 60.0),
        )
        if repair.get("session_id") != invocation["session_id"]:
            repair["returncode"] = 1
            repair["failure_category"] = "receipt_repair_session_mismatch"
            repair["usage"] = None
        else:
            first_usage = invocation.get("usage")
            repair_usage = repair.get("usage")
            if isinstance(first_usage, Mapping) and isinstance(
                repair_usage, Mapping
            ):
                repair["usage"] = latest_cumulative_provider_usage(
                    first_usage, repair_usage
                )
                if repair["usage"] is None:
                    repair["returncode"] = 1
                    repair["failure_category"] = "usage_counter_regression"
            elif repair_usage is None:
                repair["usage"] = first_usage
        invocation = repair
    return {
        **invocation,
    }


@dataclass(frozen=True)
class _ComplexityCheckpointRun:
    checkpoint: dict[str, Any]
    usage: dict[str, int]
    session_id: str
    decision: dict[str, Any] | None


@dataclass(frozen=True)
class _AdvisorReviewRun:
    advice: dict[str, Any] | None
    usage: dict[str, int] | None
    attempt_usage: dict[str, int] | None
    failure_category: str | None
    decision: dict[str, Any]


def _run_complexity_checkpoint(
    request: Mapping[str, Any],
    *,
    temporary: Path,
    codex_bin: str,
    project: Path,
    sandbox: str,
    model: str | None,
    session_id: str | None,
    runtime_root: Path,
    lineage: Mapping[str, str],
    timeout_seconds: float,
) -> _ComplexityCheckpointRun:
    schema_path = temporary / "complexity-checkpoint-schema.json"
    output_path = temporary / "complexity-checkpoint.json"
    schema_path.write_text(
        json.dumps(
            codex_cli_complexity_checkpoint_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    invocation = _run_codex_process(
        _codex_command(
            codex_bin=codex_bin,
            project=project,
            schema_path=schema_path,
            output_path=output_path,
            sandbox=sandbox,
            model=model,
            session_id=session_id,
        ),
        project=project,
        prompt=_complexity_checkpoint_prompt(request),
        schema_path=schema_path,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
    )
    if session_id is not None and invocation.get("session_id") != session_id:
        raise BuiltInHostError(
            "codex_cli_complexity_checkpoint_resume_session_mismatch"
        )
    observed_session_id = str(invocation.get("session_id") or session_id or "")
    category = str(invocation["failure_category"])
    if invocation["timed_out"]:
        if observed_session_id:
            _store_codex_cli_session(
                runtime_root, lineage=lineage, session_id=observed_session_id
            )
        raise BuiltInHostError("codex_cli_complexity_checkpoint_timeout")
    if observed_session_id:
        if (
            invocation["returncode"] == 0
            or category not in SESSION_INVALIDATING_FAILURE_CATEGORIES
        ):
            _store_codex_cli_session(
                runtime_root, lineage=lineage, session_id=observed_session_id
            )
        else:
            _discard_codex_cli_session(runtime_root, lineage=lineage)
    if invocation["returncode"] != 0:
        raise BuiltInHostError(f"codex_cli_complexity_checkpoint_{category}")
    if not observed_session_id:
        raise BuiltInHostError("codex_cli_complexity_checkpoint_session_missing")
    turn_key = str(request.get("turn_key") or "")
    raw_usage = invocation.get("usage")
    workspace_inspection_observed = (
        invocation.get("workspace_inspection_observed") is True
    )
    try:
        checkpoint = _normalize_complexity_checkpoint(
            invocation["result"], turn_key=turn_key
        )
    except BuiltInHostError as exc:
        if str(exc) != "codex_cli_complexity_checkpoint_turn_key_mismatch":
            raise
        output_path.unlink(missing_ok=True)
        repair = _run_codex_process(
            _codex_command(
                codex_bin=codex_bin,
                project=project,
                schema_path=schema_path,
                output_path=output_path,
                sandbox="read-only",
                model=model,
                session_id=observed_session_id,
            ),
            project=project,
            prompt="\n".join(
                [
                    "Do not perform more workspace work. The prior complexity checkpoint receipt violated the LoopX contract.",
                    "Re-emit only a corrected checkpoint receipt for the inspection already completed.",
                    f"Correct this validation error: {exc}",
                    "Turn request:",
                    json.dumps(
                        dict(request),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ]
            ),
            schema_path=schema_path,
            output_path=output_path,
            timeout_seconds=min(timeout_seconds, 60.0),
        )
        if repair["timed_out"]:
            raise BuiltInHostError(
                "codex_cli_complexity_checkpoint_repair_timeout"
            ) from exc
        if repair["returncode"] != 0:
            raise BuiltInHostError(
                "codex_cli_complexity_checkpoint_repair_"
                + str(repair["failure_category"])
            ) from exc
        if repair.get("session_id") != observed_session_id:
            raise BuiltInHostError(
                "codex_cli_complexity_checkpoint_repair_session_mismatch"
            ) from exc
        checkpoint = _normalize_complexity_checkpoint(
            repair["result"], turn_key=turn_key
        )
        repair_usage = repair.get("usage")
        if not isinstance(raw_usage, Mapping) or not isinstance(
            repair_usage, Mapping
        ):
            raise BuiltInHostError(
                "codex_cli_complexity_checkpoint_usage_missing"
            ) from exc
        raw_usage = latest_cumulative_provider_usage(raw_usage, repair_usage)
        if raw_usage is None:
            raise BuiltInHostError(
                "codex_cli_complexity_checkpoint_usage_counter_regression"
            ) from exc
    if (
        checkpoint["complexity"] == "simple"
        and not workspace_inspection_observed
    ):
        checkpoint = {
            **checkpoint,
            "complexity": "complex",
            "signals": ["validation_uncertainty"],
            "evidence_summary": (
                "Executor reported a simple route without observable workspace "
                "inspection; strong review must verify the patch and validation boundary."
            ),
            "open_questions": [
                "Which repository evidence proves the proposed patch and validation boundary?"
            ],
        }
    if not isinstance(raw_usage, Mapping):
        raise BuiltInHostError("codex_cli_complexity_checkpoint_usage_missing")
    decision = (
        advisor_decision_receipt(checkpoint, decision="skipped_simple")
        if checkpoint["complexity"] == "simple"
        else None
    )
    return _ComplexityCheckpointRun(
        checkpoint=checkpoint,
        usage=dict(raw_usage),
        session_id=observed_session_id,
        decision=decision,
    )


def _run_advisor_review(
    request: Mapping[str, Any],
    *,
    temporary: Path,
    project: Path,
    codex_bin: str,
    advisor_model: str,
    checkpoint: Mapping[str, Any],
    timeout_seconds: float,
) -> _AdvisorReviewRun:
    advisor_project = temporary / "advisor-workspace"
    advisor_project.mkdir()
    schema_path = temporary / "advisor-schema.json"
    output_path = temporary / "advisor-message.json"
    schema_path.write_text(
        json.dumps(
            codex_cli_advisor_schema(), ensure_ascii=False, separators=(",", ":")
        ),
        encoding="utf-8",
    )
    dialect = _cli_dialect(codex_bin)
    advisor_command = _codex_command(
        codex_bin=codex_bin,
        project=advisor_project,
        schema_path=schema_path,
        output_path=output_path,
        sandbox="read-only",
        model=advisor_model,
        session_id=None,
        ephemeral=dialect != "traex",
    )
    invocation = _run_codex_process(
        advisor_command,
        project=advisor_project,
        prompt=_advisor_prompt(
            request,
            workspace_context=_advisor_workspace_context(
                request, project=project, complexity_checkpoint=checkpoint
            ),
            complexity_checkpoint=checkpoint,
        ),
        schema_path=schema_path,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
    )
    raw_usage = invocation.get("usage")
    attempt_usage = dict(raw_usage) if isinstance(raw_usage, Mapping) else None
    failure_category: str | None = None
    advice: dict[str, Any] | None = None
    if invocation["timed_out"]:
        failure_category = "timeout"
    elif invocation["returncode"] != 0:
        failure_category = str(invocation["failure_category"])
    else:
        try:
            advice = _normalize_advisor_result(
                invocation["result"], turn_key=str(request.get("turn_key") or "")
            )
        except BuiltInHostError:
            failure_category = "invalid_result"
        if (
            advice is None
            and dialect == "traex"
            and invocation.get("session_id")
        ):
            advisor_session_id = str(invocation["session_id"])
            repair = _run_codex_process(
                _codex_command(
                    codex_bin=codex_bin,
                    project=advisor_project,
                    schema_path=schema_path,
                    output_path=output_path,
                    sandbox="read-only",
                    model=advisor_model,
                    session_id=advisor_session_id,
                ),
                project=advisor_project,
                prompt=(
                    "Do not perform more analysis or workspace work. Re-emit only "
                    "the Advisor receipt for your completed review. Preserve the "
                    "same turn_key, include every required field, use at most four "
                    "items per list, and keep every string at or below 400 Unicode "
                    "characters. Recommendations must be definite actions backed "
                    "by the supplied source; do not use optional or conditional "
                    "recommendations."
                ),
                schema_path=schema_path,
                output_path=output_path,
                timeout_seconds=min(timeout_seconds, 60.0),
            )
            if repair.get("session_id") != advisor_session_id:
                repair["returncode"] = 1
                repair["failure_category"] = "receipt_repair_session_mismatch"
                repair["usage"] = None
            repair_usage = repair.get("usage")
            if isinstance(raw_usage, Mapping) and isinstance(repair_usage, Mapping):
                raw_usage = latest_cumulative_provider_usage(
                    raw_usage, repair_usage
                )
            elif isinstance(repair_usage, Mapping):
                raw_usage = repair_usage
            attempt_usage = dict(raw_usage) if isinstance(raw_usage, Mapping) else None
            if not repair["timed_out"] and repair["returncode"] == 0:
                try:
                    advice = _normalize_advisor_result(
                        repair["result"],
                        turn_key=str(request.get("turn_key") or ""),
                    )
                except BuiltInHostError:
                    pass
            if advice is not None:
                failure_category = None
        if advice is not None and attempt_usage is None:
            advice = None
            failure_category = "usage_missing"
    decision = advisor_decision_receipt(
        checkpoint,
        decision="applied_complexity" if advice is not None else "fallback_failure",
        failure_category=None if advice is not None else failure_category or "unknown",
    )
    return _AdvisorReviewRun(
        advice=advice,
        usage=attempt_usage if advice is not None else None,
        attempt_usage=attempt_usage,
        failure_category=failure_category,
        decision=decision,
    )


def _attach_model_usage(
    result: dict[str, Any],
    *,
    adaptive_mode: bool,
    executor_usage: dict[str, int] | None,
    checkpoint_usage: Mapping[str, int] | None,
    checkpoint_decision: Mapping[str, Any] | None,
    review: _AdvisorReviewRun | None,
) -> None:
    if adaptive_mode and executor_usage is None:
        raise BuiltInHostError("codex_cli_executor_usage_missing")
    if executor_usage is None:
        return
    if checkpoint_usage is not None:
        cumulative_usage = latest_cumulative_provider_usage(
            checkpoint_usage, executor_usage
        )
        if cumulative_usage is None:
            raise BuiltInHostError("codex_cli_executor_usage_counter_regression")
        executor_usage = cumulative_usage
    if review is not None and review.advice is not None:
        if review.usage is None:
            raise BuiltInHostError("codex_cli_executor_usage_missing")
        result["model_usage"] = advisor_model_usage(
            advisor=review.usage,
            executor=executor_usage,
            advice=review.advice,
        )
        result["model_usage"]["advisor_decision"] = review.decision
        result["model_usage"]["usage_complete"] = True
        return
    decision = review.decision if review is not None else checkpoint_decision
    attempt_usage = review.attempt_usage if review is not None else None
    failure_category = review.failure_category if review is not None else None
    result["model_usage"] = direct_model_usage(
        executor_usage,
        advisor_decision=decision,
        advisor_attempt=attempt_usage,
        usage_complete=failure_category is None or attempt_usage is not None,
    )


def _run_final_executor(
    request: Mapping[str, Any],
    *,
    temporary: Path,
    codex_bin: str,
    project: Path,
    sandbox: str,
    model: str | None,
    session_id: str | None,
    runtime_root: Path,
    lineage: Mapping[str, str],
    timeout_seconds: float,
    checkpoint_run: _ComplexityCheckpointRun | None,
    review: _AdvisorReviewRun | None,
) -> dict[str, Any]:
    schema_path = temporary / "result-schema.json"
    output_path = temporary / "last-message.json"
    schema_path.write_text(
        json.dumps(codex_cli_result_schema(), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    invocation = _run_codex_process(
        _codex_command(
            codex_bin=codex_bin,
            project=project,
            schema_path=schema_path,
            output_path=output_path,
            sandbox=sandbox,
            model=model,
            session_id=session_id,
        ),
        project=project,
        prompt=_prompt(
            request,
            advisor=review.advice if review is not None else None,
            complexity_checkpoint=(
                checkpoint_run.checkpoint if checkpoint_run is not None else None
            ),
            advisor_failure_category=(
                review.failure_category if review is not None else None
            ),
        ),
        schema_path=schema_path,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
    )
    if session_id is not None and invocation.get("session_id") != session_id:
        raise BuiltInHostError("codex_cli_executor_resume_session_mismatch")
    observed_session_id = str(invocation.get("session_id") or session_id or "")
    category = str(invocation["failure_category"])
    if invocation["timed_out"]:
        if observed_session_id:
            _store_codex_cli_session(
                runtime_root, lineage=lineage, session_id=observed_session_id
            )
        raise BuiltInHostError("codex_cli_timeout")
    if invocation["returncode"] != 0 and category in SESSION_INVALIDATING_FAILURE_CATEGORIES:
        _discard_codex_cli_session(runtime_root, lineage=lineage)
    elif observed_session_id:
        _store_codex_cli_session(
            runtime_root, lineage=lineage, session_id=observed_session_id
        )
    if invocation["returncode"] != 0:
        raise BuiltInHostError(f"codex_cli_{category}")
    raw_usage = invocation.get("usage")
    boundary = _mapping(_mapping(request.get("turn_envelope")).get("boundary"))
    write_scope = boundary.get("write_scope")
    if (
        review is not None
        and review.advice is not None
        and sandbox == "workspace-write"
        and isinstance(write_scope, list)
        and bool(write_scope)
        and invocation.get("workspace_inspection_observed") is not True
    ):
        if not observed_session_id:
            raise BuiltInHostError("codex_cli_executor_session_missing")
        output_path.unlink(missing_ok=True)
        execution_retry = _run_codex_process(
            _codex_command(
                codex_bin=codex_bin,
                project=project,
                schema_path=schema_path,
                output_path=output_path,
                sandbox=sandbox,
                model=model,
                session_id=observed_session_id,
            ),
            project=project,
            prompt="\n".join(
                [
                    "EXECUTION RETRY: your prior response used no workspace tools.",
                    "Use the shell/read/edit tools now. Inspect the relevant file, apply the smallest in-scope patch, and run focused validation.",
                    "Do not return a typed result until tool execution finishes. If tools cannot run, return repair_required and state the concrete blocker; never describe an edit that did not occur.",
                    "Turn identity: "
                    + json.dumps(
                        {"turn_key": request.get("turn_key")},
                        separators=(",", ":"),
                    ),
                    *_FINAL_RESULT_INSTRUCTIONS,
                ]
            ),
            schema_path=schema_path,
            output_path=output_path,
            timeout_seconds=timeout_seconds,
        )
        if execution_retry["timed_out"]:
            raise BuiltInHostError("codex_cli_executor_retry_timeout")
        if execution_retry["returncode"] != 0:
            raise BuiltInHostError(
                f"codex_cli_executor_retry_{execution_retry['failure_category']}"
            )
        if execution_retry.get("session_id") != observed_session_id:
            raise BuiltInHostError("codex_cli_executor_retry_session_mismatch")
        retry_usage = execution_retry.get("usage")
        if isinstance(raw_usage, Mapping) and isinstance(retry_usage, Mapping):
            raw_usage = latest_cumulative_provider_usage(raw_usage, retry_usage)
            if raw_usage is None:
                raise BuiltInHostError(
                    "codex_cli_executor_retry_usage_counter_regression"
                )
        elif retry_usage is not None:
            raw_usage = retry_usage
        invocation = execution_retry
    result = invocation.get("result")
    if result is None:
        raise BuiltInHostError("codex_cli_final_result_missing")
    if not isinstance(result, dict):
        raise BuiltInHostError("codex_cli_final_result_not_object")
    validation_plan = {
        "transaction": {"turn_key": request.get("turn_key")},
        "turn_envelope": request.get("turn_envelope"),
    }
    validation = validate_loopx_turn_host_result(validation_plan, result)
    if not validation["ok"]:
        if not observed_session_id:
            raise BuiltInHostError("codex_cli_final_result_contract_invalid")
        output_path.unlink(missing_ok=True)
        repair = _run_codex_process(
            _codex_command(
                codex_bin=codex_bin,
                project=project,
                schema_path=schema_path,
                output_path=output_path,
                sandbox="read-only",
                model=model,
                session_id=observed_session_id,
            ),
            project=project,
            prompt="\n".join(
                [
                    "Do not perform more workspace work. The prior final receipt violated the LoopX result contract.",
                    "Re-emit only a corrected final typed receipt for work already attempted.",
                    "Correct these validation errors: "
                    + "; ".join(str(item) for item in validation["errors"][:4]),
                    "Turn request:",
                    json.dumps(
                        dict(request),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    *_FINAL_RESULT_INSTRUCTIONS,
                ]
            ),
            schema_path=schema_path,
            output_path=output_path,
            timeout_seconds=min(timeout_seconds, 60.0),
        )
        if repair["timed_out"]:
            raise BuiltInHostError("codex_cli_final_result_repair_timeout")
        if repair["returncode"] != 0:
            raise BuiltInHostError(
                f"codex_cli_final_result_repair_{repair['failure_category']}"
            )
        if repair.get("session_id") != observed_session_id:
            raise BuiltInHostError(
                "codex_cli_final_result_repair_session_mismatch"
            )
        repaired_result = repair.get("result")
        if not isinstance(repaired_result, dict):
            raise BuiltInHostError("codex_cli_final_result_contract_invalid")
        repaired_validation = validate_loopx_turn_host_result(
            validation_plan, repaired_result
        )
        if not repaired_validation["ok"]:
            raise BuiltInHostError("codex_cli_final_result_contract_invalid")
        repair_usage = repair.get("usage")
        if isinstance(raw_usage, Mapping) and isinstance(repair_usage, Mapping):
            raw_usage = latest_cumulative_provider_usage(raw_usage, repair_usage)
            if raw_usage is None:
                raise BuiltInHostError(
                    "codex_cli_final_result_repair_usage_counter_regression"
                )
        elif repair_usage is not None:
            raw_usage = repair_usage
        result = repaired_result
    _attach_model_usage(
        result,
        adaptive_mode=checkpoint_run is not None,
        executor_usage=dict(raw_usage) if isinstance(raw_usage, Mapping) else None,
        checkpoint_usage=(
            checkpoint_run.usage if checkpoint_run is not None else None
        ),
        checkpoint_decision=(
            checkpoint_run.decision if checkpoint_run is not None else None
        ),
        review=review,
    )
    return result


def _apply_turn_usage_baseline(
    result: dict[str, Any],
    *,
    baseline: Mapping[str, int],
) -> dict[str, int] | None:
    model_usage = result.get("model_usage")
    if not isinstance(model_usage, dict):
        return None
    latest = model_usage.get("executor")
    if not isinstance(latest, Mapping):
        return None
    turn_executor = provider_usage_delta(latest, baseline)
    if turn_executor is None:
        raise BuiltInHostError("codex_cli_executor_usage_baseline_regression")
    model_usage["executor"] = turn_executor
    independent_usage = model_usage.get("advisor")
    if not isinstance(independent_usage, Mapping):
        independent_usage = model_usage.get("advisor_attempt")
    model_usage["total"] = (
        aggregate_provider_usage(turn_executor, independent_usage)
        if isinstance(independent_usage, Mapping)
        else dict(turn_executor)
    )
    return dict(latest)


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
        checkpoint_run: _ComplexityCheckpointRun | None = None
        review: _AdvisorReviewRun | None = None
        if advisor_model:
            checkpoint_run = _run_complexity_checkpoint(
                request,
                temporary=temporary,
                codex_bin=str(resolved),
                project=project,
                sandbox=sandbox,
                model=model,
                session_id=session_id,
                runtime_root=runtime_root,
                lineage=lineage,
                timeout_seconds=advisor_timeout_seconds,
            )
            if checkpoint_run.checkpoint["complexity"] == "complex":
                review = _run_advisor_review(
                    request,
                    temporary=temporary,
                    project=project,
                    codex_bin=str(resolved),
                    advisor_model=advisor_model,
                    checkpoint=checkpoint_run.checkpoint,
                    timeout_seconds=advisor_timeout_seconds,
                )
        result = _run_final_executor(
            request,
            temporary=temporary,
            codex_bin=str(resolved),
            project=project,
            sandbox=sandbox,
            model=model,
            session_id=(checkpoint_run.session_id if checkpoint_run else session_id),
            runtime_root=runtime_root,
            lineage=lineage,
            timeout_seconds=timeout_seconds,
            checkpoint_run=checkpoint_run,
            review=review,
        )
        baseline = (
            _mapping(binding.get("usage_baseline"))
            if binding is not None
            else {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
        )
        latest_usage = _apply_turn_usage_baseline(result, baseline=baseline)
        if latest_usage is not None:
            stored = load_codex_cli_session(runtime_root, lineage=lineage)
            if stored is None:
                raise BuiltInHostError("codex_cli_executor_session_missing")
            _store_codex_cli_session(
                runtime_root,
                lineage=lineage,
                session_id=str(stored["session_id"]),
                usage_baseline=latest_usage,
            )
        return result
