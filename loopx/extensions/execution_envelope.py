from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import re
from typing import Any


EXTENSION_EXECUTION_ENVELOPE_SCHEMA_VERSION = "loopx_extension_execution_envelope_v0"
_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
_ENVELOPE_FIELDS = {
    "schema_version",
    "action",
    "scope",
    "extension",
    "request_digest",
}


def _token(value: object, label: str) -> str:
    token = str(value or "").strip()
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError(f"{label} must be a lower-case execution token")
    return token


def _canonical(value: object, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON serializable") from exc


def extension_request_digest(request: Mapping[str, Any]) -> str:
    """Digest the exact provider request without its execution envelope."""

    if not isinstance(request, Mapping):
        raise ValueError("extension request must be an object")
    payload = {str(key): deepcopy(value) for key, value in request.items()}
    payload.pop("execution_envelope", None)
    encoded = _canonical(payload, "extension request").encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _scope(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("extension execution scope must be a non-empty object")
    normalized = {str(key): deepcopy(item) for key, item in value.items()}
    serialized = _canonical(normalized, "extension execution scope")
    if len(serialized.encode("utf-8")) > 16_384:
        raise ValueError("extension execution scope exceeds 16384 bytes")
    return normalized


def build_extension_execution_envelope(
    *,
    action: str,
    scope: Mapping[str, Any],
    extension_id: str,
    extension_revision: str,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one synchronous provider dispatch to its exact effect operation."""

    revision = str(extension_revision or "").strip()
    if not revision:
        raise ValueError("extension_revision is required")
    return {
        "schema_version": EXTENSION_EXECUTION_ENVELOPE_SCHEMA_VERSION,
        "action": _token(action, "action"),
        "scope": _scope(scope),
        "extension": {
            "id": _token(extension_id, "extension_id"),
            "revision": revision,
        },
        "request_digest": extension_request_digest(request),
    }


def validate_extension_execution_envelope(
    raw: Mapping[str, Any],
    *,
    action: str,
    scope: Mapping[str, Any],
    extension_id: str,
    extension_revision: str,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Revalidate the request, revision, action, and scope before effects."""

    if not isinstance(raw, Mapping):
        raise ValueError("extension execution envelope must be an object")
    envelope = {str(key): deepcopy(value) for key, value in raw.items()}
    if set(envelope) != _ENVELOPE_FIELDS:
        raise ValueError("extension execution envelope fields do not match the schema")
    if envelope.get("schema_version") != EXTENSION_EXECUTION_ENVELOPE_SCHEMA_VERSION:
        raise ValueError(
            "extension execution envelope must use "
            f"{EXTENSION_EXECUTION_ENVELOPE_SCHEMA_VERSION}"
        )
    expected_fields = {
        "action": _token(action, "action"),
        "scope": _scope(scope),
        "extension": {
            "id": _token(extension_id, "extension_id"),
            "revision": str(extension_revision or "").strip(),
        },
        "request_digest": extension_request_digest(request),
    }
    if not expected_fields["extension"]["revision"]:
        raise ValueError("extension_revision is required")
    for key, expected in expected_fields.items():
        if envelope.get(key) != expected:
            raise ValueError(
                f"extension execution envelope {key} does not match the operation"
            )
    return envelope
