"""Provider-neutral validation for bound benchmark model-route receipts."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from enum import Enum
from typing import Any

from ...control_plane.runtime.public_safety import validate_public_safe_value

BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION = "benchmark_model_route_receipt_v1"

_PUBLIC_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,127}$")
_NAMESPACED_PUBLIC_IDENTITY = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,79}/[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,119}$"
)
_PUBLIC_IDENTITY_DIGEST = re.compile(
    r"^public:(?P<kind>[a-z][a-z0-9_]{0,31}):sha256:(?P<digest>[0-9a-f]{64})$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_FIELDS = (
    "schema_version",
    "runtime",
    "requested_model",
    "requested_provider",
    "status",
    "runtime_audited",
    "matched",
    "observed_route_count",
    "raw_content_recorded",
    "input_path_recorded",
    "run_id",
    "arm_id",
    "launch_binding_digest",
    "authority",
)
_OPTIONAL_FIELDS = (
    "observed_model",
    "observed_provider",
    "observed_backend_variant",
)
_STATUSES = {
    "route_requested_not_runtime_audited",
    "runtime_route_ambiguous",
    "runtime_route_mismatch",
    "runtime_route_verified",
}


class PublicIdentityKind(str, Enum):
    """Typed domains for opaque identities crossing the public boundary."""

    BENCHMARK = "benchmark"
    CASE = "case"
    RUN = "run"
    ARM = "arm"
    AUTHORITY = "authority"
    BACKEND_VARIANT = "backend_variant"


def normalize_sensitive_values(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("sensitive_values must be an iterable of strings")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("sensitive_values must contain non-empty strings")
        if len(value) < 8:
            raise ValueError("sensitive_values must contain at least 8 characters")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _reject_private_label(
    value: str, *, field: str, sensitive_values: tuple[str, ...]
) -> None:
    # Reuse the control plane's domain-neutral public boundary scanner instead
    # of guessing provider- or product-specific secret prefixes here. Explicit
    # sensitive values cover otherwise innocuous private identifiers.
    validate_public_safe_value(value, path=field)
    if any(sensitive in value for sensitive in sensitive_values):
        raise ValueError(f"{field} contains a declared sensitive value")


def _token_shape(value: Any, *, field: str, allow_namespaced: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a compact public-safe token")
    text = value.strip()
    valid = _PUBLIC_TOKEN.fullmatch(text) is not None
    if allow_namespaced:
        valid = valid or _NAMESPACED_PUBLIC_IDENTITY.fullmatch(text) is not None
    if not valid:
        raise ValueError(f"{field} must be a compact public-safe token")
    return text


def public_identity_digest(value: str, *, kind: PublicIdentityKind) -> str:
    """Return a domain-separated public label for one private identity.

    Callers must opt in to this transformation. Provider and model labels stay
    human-auditable and are never silently replaced with a digest.
    """

    if not isinstance(value, str):
        raise TypeError("public identity source must be a string")
    if not value:
        raise ValueError("public identity source must be non-empty")
    if not isinstance(kind, PublicIdentityKind):
        raise TypeError("public identity kind must be a PublicIdentityKind")
    digest = hashlib.sha256(
        f"loopx-public-identity-v1\0{kind.value}\0{value}".encode("utf-8")
    ).hexdigest()
    return f"public:{kind.value}:sha256:{digest}"


def normalize_public_identity_token(
    value: Any,
    *,
    field: str,
    kind: PublicIdentityKind,
    sensitive_values: Iterable[str] = (),
    allow_namespaced: bool = False,
) -> str:
    """Validate a caller-asserted public label or typed opaque digest."""

    text = _token_shape(value, field=field, allow_namespaced=allow_namespaced)
    digest_match = _PUBLIC_IDENTITY_DIGEST.fullmatch(text)
    if text.startswith("public:") and digest_match is None:
        raise ValueError(f"{field} public identity digest is invalid")
    if digest_match is not None and digest_match.group("kind") != kind.value:
        raise ValueError(f"{field} public identity digest kind is invalid")
    _reject_private_label(
        text, field=field, sensitive_values=normalize_sensitive_values(sensitive_values)
    )
    return text


def normalize_public_route_label(
    value: Any, *, field: str, sensitive_values: Iterable[str] = ()
) -> str:
    """Validate an auditable provider, model, runtime, or mechanism label."""

    text = _token_shape(value, field=field)
    if text.startswith("public:"):
        raise ValueError(f"{field} must be an explicit public route label")
    _reject_private_label(
        text, field=field, sensitive_values=normalize_sensitive_values(sensitive_values)
    )
    return text


def route_identity_matches(
    *,
    requested_model: str,
    requested_provider: str,
    observed_model: str,
    observed_provider: str,
) -> bool:
    """Return whether requested and observed provider/model identities match."""

    return (
        observed_model.casefold() == requested_model.casefold()
        and observed_provider.casefold() == requested_provider.casefold()
    )


def normalize_benchmark_model_route_receipt_v1(
    value: Mapping[str, Any],
    *,
    sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate one bound provider-neutral route observation receipt."""

    required = set(_REQUIRED_FIELDS)
    optional = set(_OPTIONAL_FIELDS)
    if (
        not isinstance(value, Mapping)
        or not required <= set(value)
        or set(value) - required - optional
    ):
        raise ValueError("benchmark_model_route_receipt_v1_fields_invalid")
    schema_version = value.get("schema_version")
    if not isinstance(schema_version, str):
        raise TypeError("benchmark_model_route_receipt_v1_schema_invalid")
    if schema_version != BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION:
        raise ValueError("benchmark_model_route_receipt_v1_schema_unsupported")

    secrets = normalize_sensitive_values(sensitive_values)
    normalized = {field: value[field] for field in _REQUIRED_FIELDS}
    for field in ("runtime", "requested_model", "requested_provider"):
        normalized[field] = normalize_public_route_label(
            value.get(field), field=field, sensitive_values=secrets
        )
    for field, kind in (
        ("run_id", PublicIdentityKind.RUN),
        ("arm_id", PublicIdentityKind.ARM),
        ("authority", PublicIdentityKind.AUTHORITY),
    ):
        normalized[field] = normalize_public_identity_token(
            value.get(field),
            field=field,
            kind=kind,
            sensitive_values=secrets,
        )

    raw_digest = value.get("launch_binding_digest")
    if not isinstance(raw_digest, str):
        raise TypeError("benchmark_model_route_launch_binding_digest_invalid")
    digest = raw_digest.strip()
    if _SHA256.fullmatch(digest) is None:
        raise ValueError("benchmark_model_route_launch_binding_digest_invalid")
    normalized["launch_binding_digest"] = digest

    if (
        value.get("raw_content_recorded") is not False
        or value.get("input_path_recorded") is not False
    ):
        raise ValueError("benchmark_model_route_public_boundary_invalid")
    if not isinstance(value.get("runtime_audited"), bool) or not isinstance(
        value.get("matched"), bool
    ):
        raise TypeError("benchmark_model_route_audit_state_invalid")

    count = value.get("observed_route_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("benchmark_model_route_observed_count_invalid")
    raw_status = value.get("status")
    if not isinstance(raw_status, str):
        raise TypeError("benchmark_model_route_status_invalid")
    status = raw_status.strip()
    if status not in _STATUSES:
        raise ValueError("benchmark_model_route_status_invalid")
    normalized["status"] = status

    for field in ("observed_model", "observed_provider"):
        if field in value:
            normalized[field] = normalize_public_route_label(
                value.get(field), field=field, sensitive_values=secrets
            )
    if "observed_backend_variant" in value:
        normalized["observed_backend_variant"] = normalize_public_identity_token(
            value.get("observed_backend_variant"),
            field="observed_backend_variant",
            kind=PublicIdentityKind.BACKEND_VARIANT,
            sensitive_values=secrets,
        )
    observed_fields = optional & set(normalized)
    has_observed_route = {"observed_model", "observed_provider"} <= observed_fields
    observation_matches = has_observed_route and route_identity_matches(
        requested_model=normalized["requested_model"],
        requested_provider=normalized["requested_provider"],
        observed_model=normalized["observed_model"],
        observed_provider=normalized["observed_provider"],
    )
    audit_state = (value["runtime_audited"], value["matched"], count)
    state_valid = (
        (
            status == "route_requested_not_runtime_audited"
            and audit_state == (False, False, 0)
            and not observed_fields
        )
        or (
            status == "runtime_route_ambiguous"
            and value["runtime_audited"] is True
            and value["matched"] is False
            and count > 1
            and not observed_fields
        )
        or (
            status == "runtime_route_mismatch"
            and audit_state == (True, False, 1)
            and has_observed_route
            and not observation_matches
        )
        or (
            status == "runtime_route_verified"
            and audit_state == (True, True, 1)
            and has_observed_route
            and observation_matches
        )
    )
    if not state_valid:
        raise ValueError("benchmark_model_route_state_inconsistent")
    return normalized


__all__ = [
    "BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION",
    "PublicIdentityKind",
    "normalize_benchmark_model_route_receipt_v1",
    "normalize_public_identity_token",
    "normalize_public_route_label",
    "normalize_sensitive_values",
    "public_identity_digest",
    "route_identity_matches",
]
