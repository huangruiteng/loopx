from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .model_behavior_qualification import build_model_behavior_actor_request


MODEL_BEHAVIOR_RETAINED_CASE_SCHEMA_VERSION = "model_behavior_retained_case_v0"
MODEL_BEHAVIOR_RETAINED_STORE_SCHEMA_VERSION = "model_behavior_retained_store_v0"
MAX_RETAINED_CASE_BYTES = 131_072
MAX_RETAINED_CASES = 24

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")
_SOURCE_KINDS = {"real_quota_shadow", "owner_approved_public_fixture"}
_CASE_FIELDS = {
    "schema_version",
    "case_id",
    "source_kind",
    "recorded_at",
    "packet_digest",
    "full_packet",
    "retention_boundary",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _identifier(value: str, *, field: str) -> str:
    text = str(value or "").strip()
    if not _ID_PATTERN.fullmatch(text):
        raise ValueError(f"{field} must be a compact public-safe identifier")
    return text


def _recorded_at(value: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("recorded_at must be an ISO timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError("recorded_at must include a timezone")
    return text


def _validate_packet(packet: Mapping[str, Any], *, case_id: str) -> dict[str, Any]:
    decoded = json.loads(_canonical_json(dict(packet)))
    if not isinstance(decoded, dict):
        raise ValueError("retained full packet must be an object")
    normalized: dict[str, Any] = {str(key): value for key, value in decoded.items()}
    build_model_behavior_actor_request(
        normalized,
        qualification_id=f"retain-{case_id}",
        arm="full_packet",
    )
    if len(_canonical_json(normalized).encode("utf-8")) > MAX_RETAINED_CASE_BYTES:
        raise ValueError("retained full packet exceeds the size limit")
    return normalized


def build_model_behavior_retained_case(
    full_packet: Mapping[str, Any],
    *,
    case_id: str,
    source_kind: str,
    recorded_at: str,
) -> dict[str, Any]:
    normalized_id = _identifier(case_id, field="case_id")
    if source_kind not in _SOURCE_KINDS:
        raise ValueError("source_kind is not allowed for retained model behavior cases")
    packet = _validate_packet(full_packet, case_id=normalized_id)
    return {
        "schema_version": MODEL_BEHAVIOR_RETAINED_CASE_SCHEMA_VERSION,
        "case_id": normalized_id,
        "source_kind": source_kind,
        "recorded_at": _recorded_at(recorded_at),
        "packet_digest": _digest(packet),
        "full_packet": packet,
        "retention_boundary": {
            "local_runtime_only": True,
            "public_safe_packet_required": True,
            "model_response_retained": False,
            "conversation_retained": False,
            "credential_metadata_retained": False,
            "repository_commit_allowed": False,
        },
    }


def normalize_model_behavior_retained_case(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("retained case must be an object")
    unknown = sorted(set(raw) - _CASE_FIELDS)
    if unknown:
        raise ValueError(f"unknown retained case field(s): {', '.join(unknown)}")
    if raw.get("schema_version") != MODEL_BEHAVIOR_RETAINED_CASE_SCHEMA_VERSION:
        raise ValueError("retained case schema is not supported")
    packet = raw.get("full_packet")
    if not isinstance(packet, Mapping):
        raise ValueError("retained case full_packet must be an object")
    normalized = build_model_behavior_retained_case(
        packet,
        case_id=str(raw.get("case_id") or ""),
        source_kind=str(raw.get("source_kind") or ""),
        recorded_at=str(raw.get("recorded_at") or ""),
    )
    if raw.get("packet_digest") != normalized["packet_digest"]:
        raise ValueError("retained case packet digest does not match")
    if raw.get("retention_boundary") != normalized["retention_boundary"]:
        raise ValueError("retained case boundary contract does not match")
    return normalized


def _store_directory(runtime_root: Path, goal_id: str) -> Path:
    normalized_goal_id = _identifier(goal_id, field="goal_id")
    root = runtime_root.expanduser().resolve()
    for candidate in (root, *root.parents):
        if (candidate / ".git").exists():
            raise ValueError(
                "retained case runtime root must be outside a git worktree"
            )
    return root / "goals" / normalized_goal_id / "model-behavior" / "retained-cases"


def write_model_behavior_retained_case(
    case: Mapping[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
) -> dict[str, Any]:
    """Atomically write one explicit local-runtime case with mode 0600."""

    normalized = normalize_model_behavior_retained_case(case)
    store = _store_directory(runtime_root, goal_id)
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    if store.is_symlink():
        raise ValueError("retained case store must not be a symlink")
    target = store / f"{normalized['case_id']}.json"
    if target.is_symlink():
        raise ValueError("retained case target must not be a symlink")
    existing_paths = sorted(store.glob("*.json"))
    if target.exists():
        existing = normalize_model_behavior_retained_case(
            json.loads(target.read_text(encoding="utf-8"))
        )
        if existing != normalized:
            raise ValueError("retained case id already exists with different content")
        os.chmod(target, 0o600)
        return {
            "schema_version": MODEL_BEHAVIOR_RETAINED_STORE_SCHEMA_VERSION,
            "case_id": normalized["case_id"],
            "packet_digest": normalized["packet_digest"],
            "created": False,
            "case_count": len(existing_paths),
        }
    if len(existing_paths) >= MAX_RETAINED_CASES:
        raise ValueError("retained case store reached its case limit")
    encoded = (
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temp = store / f".{normalized['case_id']}.{os.getpid()}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
        os.chmod(target, 0o600)
    finally:
        if temp.exists():
            temp.unlink()
    return {
        "schema_version": MODEL_BEHAVIOR_RETAINED_STORE_SCHEMA_VERSION,
        "case_id": normalized["case_id"],
        "packet_digest": normalized["packet_digest"],
        "created": True,
        "case_count": len(existing_paths) + 1,
    }


def load_model_behavior_retained_cases(
    *,
    runtime_root: Path,
    goal_id: str,
) -> list[dict[str, Any]]:
    store = _store_directory(runtime_root, goal_id)
    if not store.exists():
        return []
    if store.is_symlink():
        raise ValueError("retained case store must not be a symlink")
    paths = sorted(store.glob("*.json"))
    if len(paths) > MAX_RETAINED_CASES:
        raise ValueError("retained case store exceeds its case limit")
    cases = []
    for path in paths:
        if path.is_symlink():
            raise ValueError("retained case files must not be symlinks")
        cases.append(
            normalize_model_behavior_retained_case(
                json.loads(path.read_text(encoding="utf-8"))
            )
        )
    return cases


def retained_cases_as_corpus_inputs(
    cases: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "case_id": normalized["case_id"],
            "packet": normalized["full_packet"],
        }
        for case in cases
        for normalized in [normalize_model_behavior_retained_case(case)]
    ]
