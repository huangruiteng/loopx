from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any

from ..control_plane.runtime.time import parse_timestamp, utc_isoformat


EXTENSION_AUTHORITY_DECISION_SCHEMA_VERSION = "loopx_extension_authority_decision_v0"
MAX_EXTENSION_AUTHORITY_LIFETIME_SECONDS = 300
MAX_EXTENSION_AUTHORITY_CLOCK_SKEW_SECONDS = 30
_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
_DECISION_FIELDS = {
    "schema_version",
    "decision",
    "issuer",
    "protocol",
    "permission",
    "action",
    "scope",
    "extension",
    "request_digest",
    "issued_at",
    "expires_at",
    "decision_id",
}


def _token(value: object, label: str) -> str:
    token = str(value or "").strip()
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError(f"{label} must be a lower-case authority token")
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


def _digest(value: object, label: str) -> str:
    encoded = _canonical(value, label).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def extension_authority_request_digest(request: Mapping[str, Any]) -> str:
    """Digest the exact provider request without its attached decision."""

    if not isinstance(request, Mapping):
        raise ValueError("extension authority request must be an object")
    payload = {str(key): deepcopy(value) for key, value in request.items()}
    payload.pop("authority_decision", None)
    return _digest(payload, "extension authority request")


def _scope(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("extension authority scope must be a non-empty object")
    normalized = {str(key): deepcopy(item) for key, item in value.items()}
    serialized = _canonical(normalized, "extension authority scope")
    if len(serialized.encode("utf-8")) > 16_384:
        raise ValueError("extension authority scope exceeds 16384 bytes")
    return normalized


def _decision_id(payload: Mapping[str, Any]) -> str:
    return (
        "extauth_"
        + _digest(payload, "extension authority decision").split(":", 1)[1][:24]
    )


def build_extension_authority_decision(
    *,
    capability_id: str,
    protocol: str,
    permission: str,
    action: str,
    scope: Mapping[str, Any],
    extension_id: str,
    extension_revision: str,
    request: Mapping[str, Any],
    now: datetime | None = None,
    lifetime_seconds: int = MAX_EXTENSION_AUTHORITY_LIFETIME_SECONDS,
) -> dict[str, Any]:
    """Issue one short-lived, request-bound extension operation decision."""

    if not 1 <= lifetime_seconds <= MAX_EXTENSION_AUTHORITY_LIFETIME_SECONDS:
        raise ValueError(
            "extension authority lifetime_seconds must be between 1 and 300"
        )
    issued = (
        (now or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .replace(microsecond=0)
    )
    expires = issued + timedelta(seconds=lifetime_seconds)
    decision: dict[str, Any] = {
        "schema_version": EXTENSION_AUTHORITY_DECISION_SCHEMA_VERSION,
        "decision": "allow",
        "issuer": {
            "kind": "capability",
            "capability_id": _token(capability_id, "capability_id"),
        },
        "protocol": _token(protocol, "protocol"),
        "permission": _token(permission, "permission"),
        "action": _token(action, "action"),
        "scope": _scope(scope),
        "extension": {
            "id": _token(extension_id, "extension_id"),
            "revision": str(extension_revision or "").strip(),
        },
        "request_digest": extension_authority_request_digest(request),
        "issued_at": utc_isoformat(issued),
        "expires_at": utc_isoformat(expires),
    }
    if not decision["extension"]["revision"]:
        raise ValueError("extension_revision is required")
    decision["decision_id"] = _decision_id(decision)
    return decision


def validate_extension_authority_decision(
    raw: Mapping[str, Any],
    *,
    capability_id: str,
    protocol: str,
    permission: str,
    action: str,
    scope: Mapping[str, Any],
    extension_id: str,
    extension_revision: str,
    request: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Revalidate one typed decision against the exact provider operation."""

    if not isinstance(raw, Mapping):
        raise ValueError("extension authority decision must be an object")
    decision = {str(key): deepcopy(value) for key, value in raw.items()}
    if set(decision) != _DECISION_FIELDS:
        raise ValueError("extension authority decision fields do not match the schema")
    if decision.get("schema_version") != EXTENSION_AUTHORITY_DECISION_SCHEMA_VERSION:
        raise ValueError(
            "extension authority decision must use "
            f"{EXTENSION_AUTHORITY_DECISION_SCHEMA_VERSION}"
        )
    if decision.get("decision") != "allow":
        raise ValueError(
            "extension authority decision must explicitly allow the action"
        )
    issuer = decision.get("issuer")
    if not isinstance(issuer, Mapping) or dict(issuer) != {
        "kind": "capability",
        "capability_id": _token(capability_id, "capability_id"),
    }:
        raise ValueError("extension authority issuer does not match the capability")
    expected_fields = {
        "protocol": _token(protocol, "protocol"),
        "permission": _token(permission, "permission"),
        "action": _token(action, "action"),
        "scope": _scope(scope),
        "extension": {
            "id": _token(extension_id, "extension_id"),
            "revision": str(extension_revision or "").strip(),
        },
        "request_digest": extension_authority_request_digest(request),
    }
    for key, expected in expected_fields.items():
        if decision.get(key) != expected:
            raise ValueError(f"extension authority {key} does not match the operation")

    issued = parse_timestamp(decision.get("issued_at"))
    expires = parse_timestamp(decision.get("expires_at"))
    if issued is None or expires is None:
        raise ValueError(
            "extension authority decision timestamps must be ISO timestamps"
        )
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued > current + timedelta(seconds=MAX_EXTENSION_AUTHORITY_CLOCK_SKEW_SECONDS):
        raise ValueError("extension authority decision was issued in the future")
    if expires <= current:
        raise ValueError("extension authority decision has expired")
    lifetime = (expires - issued).total_seconds()
    if not 0 < lifetime <= MAX_EXTENSION_AUTHORITY_LIFETIME_SECONDS:
        raise ValueError("extension authority decision lifetime is invalid")

    supplied_id = str(decision.pop("decision_id", "")).strip()
    if supplied_id != _decision_id(decision):
        raise ValueError("extension authority decision_id does not match its contents")
    decision["decision_id"] = supplied_id
    return decision
