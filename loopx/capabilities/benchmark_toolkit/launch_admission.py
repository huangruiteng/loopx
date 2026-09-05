"""Public-safe launch lineage for provider-neutral benchmark qualification."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .route_receipt import (
    PublicIdentityKind,
    normalize_public_identity_token,
    normalize_public_route_label,
    normalize_sensitive_values,
)

BENCHMARK_LAUNCH_ADMISSION_RECEIPT_SCHEMA_VERSION = (
    "benchmark_launch_admission_receipt_v0"
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MECHANISM_FIELDS = {"mechanism", "authority", "evidence_sha256"}
_RECEIPT_FIELDS = {
    "schema_version",
    "benchmark_id",
    "case_id",
    "run_id",
    "arm_id",
    "instruction_sha256",
    "integrity_policy_sha256",
    "expected_route",
    "containment_binding_sha256",
    "runtime_binding_sha256",
    "credential_isolation",
    "controller_isolation",
    "runner_authority",
    "provider_authority",
    "issued_at",
    "launch_binding_digest",
    "public_boundary",
}
_PUBLIC_BOUNDARY = {
    "raw_instruction_recorded": False,
    "raw_credential_recorded": False,
    "raw_controller_state_recorded": False,
    "raw_runtime_identity_recorded": False,
    "path_recorded": False,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _identity_token(
    value: Any,
    *,
    field: str,
    kind: PublicIdentityKind,
    sensitive_values: Iterable[str],
    allow_namespaced: bool = False,
) -> str:
    try:
        return normalize_public_identity_token(
            value,
            field=field,
            kind=kind,
            sensitive_values=sensitive_values,
            allow_namespaced=allow_namespaced,
        )
    except (TypeError, ValueError) as exc:
        error_type = TypeError if isinstance(exc, TypeError) else ValueError
        raise error_type(f"benchmark_launch_admission_{field}_invalid") from exc


def _route_label(value: Any, *, field: str, sensitive_values: Iterable[str]) -> str:
    try:
        return normalize_public_route_label(
            value, field=field, sensitive_values=sensitive_values
        )
    except (TypeError, ValueError) as exc:
        error_type = TypeError if isinstance(exc, TypeError) else ValueError
        raise error_type(f"benchmark_launch_admission_{field}_invalid") from exc


def _digest(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"benchmark_launch_admission_{field}_invalid")
    text = value.strip()
    if _SHA256.fullmatch(text) is None:
        raise ValueError(f"benchmark_launch_admission_{field}_invalid")
    return text


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("benchmark_launch_admission_issued_at_invalid")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("benchmark_launch_admission_issued_at_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("benchmark_launch_admission_issued_at_invalid")
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return canonical.replace("+00:00", "Z")


def _mechanism(
    value: Any, *, field: str, sensitive_values: Iterable[str]
) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _MECHANISM_FIELDS:
        raise ValueError(f"benchmark_launch_admission_{field}_invalid")
    return {
        "mechanism": _route_label(
            value.get("mechanism"),
            field=f"{field}_mechanism",
            sensitive_values=sensitive_values,
        ),
        "authority": _identity_token(
            value.get("authority"),
            field=f"{field}_authority",
            kind=PublicIdentityKind.AUTHORITY,
            sensitive_values=sensitive_values,
        ),
        "evidence_sha256": _digest(
            value.get("evidence_sha256"), field=f"{field}_evidence_sha256"
        ),
    }


def _binding_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: receipt[key]
        for key in sorted(
            _RECEIPT_FIELDS - {"launch_binding_digest", "public_boundary"}
        )
    }


def _binding_digest(receipt: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(_binding_payload(receipt)).encode()
    ).hexdigest()


def build_benchmark_launch_admission_receipt(
    *,
    benchmark_id: str,
    case_id: str,
    run_id: str,
    arm_id: str,
    instruction_sha256: str,
    integrity_policy_sha256: str,
    expected_provider: str,
    expected_model: str,
    containment_binding_sha256: str,
    runtime_binding_sha256: str,
    credential_isolation: Mapping[str, Any],
    controller_isolation: Mapping[str, Any],
    runner_authority: str,
    provider_authority: str,
    issued_at: str,
    sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a content-addressed receipt without retaining private source facts."""

    secrets = normalize_sensitive_values(sensitive_values)
    receipt: dict[str, Any] = {
        "schema_version": BENCHMARK_LAUNCH_ADMISSION_RECEIPT_SCHEMA_VERSION,
        "benchmark_id": _identity_token(
            benchmark_id,
            field="benchmark_id",
            kind=PublicIdentityKind.BENCHMARK,
            sensitive_values=secrets,
        ),
        "case_id": _identity_token(
            case_id,
            field="case_id",
            kind=PublicIdentityKind.CASE,
            sensitive_values=secrets,
            allow_namespaced=True,
        ),
        "run_id": _identity_token(
            run_id,
            field="run_id",
            kind=PublicIdentityKind.RUN,
            sensitive_values=secrets,
        ),
        "arm_id": _identity_token(
            arm_id,
            field="arm_id",
            kind=PublicIdentityKind.ARM,
            sensitive_values=secrets,
        ),
        "instruction_sha256": _digest(instruction_sha256, field="instruction_sha256"),
        "integrity_policy_sha256": _digest(
            integrity_policy_sha256, field="integrity_policy_sha256"
        ),
        "expected_route": {
            "provider": _route_label(
                expected_provider,
                field="expected_provider",
                sensitive_values=secrets,
            ),
            "model": _route_label(
                expected_model,
                field="expected_model",
                sensitive_values=secrets,
            ),
        },
        "containment_binding_sha256": _digest(
            containment_binding_sha256, field="containment_binding_sha256"
        ),
        "runtime_binding_sha256": _digest(
            runtime_binding_sha256, field="runtime_binding_sha256"
        ),
        "credential_isolation": _mechanism(
            credential_isolation,
            field="credential_isolation",
            sensitive_values=secrets,
        ),
        "controller_isolation": _mechanism(
            controller_isolation,
            field="controller_isolation",
            sensitive_values=secrets,
        ),
        "runner_authority": _identity_token(
            runner_authority,
            field="runner_authority",
            kind=PublicIdentityKind.AUTHORITY,
            sensitive_values=secrets,
        ),
        "provider_authority": _identity_token(
            provider_authority,
            field="provider_authority",
            kind=PublicIdentityKind.AUTHORITY,
            sensitive_values=secrets,
        ),
        "issued_at": _timestamp(issued_at),
        "public_boundary": dict(_PUBLIC_BOUNDARY),
    }
    if receipt["credential_isolation"]["authority"] != receipt["runner_authority"]:
        raise ValueError(
            "benchmark_launch_admission_credential_isolation_authority_mismatch"
        )
    if receipt["controller_isolation"]["authority"] != receipt["runner_authority"]:
        raise ValueError(
            "benchmark_launch_admission_controller_isolation_authority_mismatch"
        )
    receipt["launch_binding_digest"] = _binding_digest(receipt)
    return receipt


def normalize_benchmark_launch_admission_receipt(
    value: Mapping[str, Any],
    *,
    sensitive_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate the strict schema and its canonical binding digest."""

    if not isinstance(value, Mapping) or set(value) != _RECEIPT_FIELDS:
        raise ValueError("benchmark_launch_admission_fields_invalid")
    schema_version = value.get("schema_version")
    if not isinstance(schema_version, str):
        raise TypeError("benchmark_launch_admission_schema_invalid")
    if schema_version != BENCHMARK_LAUNCH_ADMISSION_RECEIPT_SCHEMA_VERSION:
        raise ValueError("benchmark_launch_admission_schema_unsupported")
    route = value.get("expected_route")
    if not isinstance(route, Mapping) or set(route) != {"provider", "model"}:
        raise ValueError("benchmark_launch_admission_expected_route_invalid")
    if value.get("public_boundary") != _PUBLIC_BOUNDARY:
        raise ValueError("benchmark_launch_admission_public_boundary_invalid")

    normalized = build_benchmark_launch_admission_receipt(
        benchmark_id=value["benchmark_id"],
        case_id=value["case_id"],
        run_id=value["run_id"],
        arm_id=value["arm_id"],
        instruction_sha256=value["instruction_sha256"],
        integrity_policy_sha256=value["integrity_policy_sha256"],
        expected_provider=route["provider"],
        expected_model=route["model"],
        containment_binding_sha256=value["containment_binding_sha256"],
        runtime_binding_sha256=value["runtime_binding_sha256"],
        credential_isolation=value["credential_isolation"],
        controller_isolation=value["controller_isolation"],
        runner_authority=value["runner_authority"],
        provider_authority=value["provider_authority"],
        issued_at=value["issued_at"],
        sensitive_values=sensitive_values,
    )
    supplied = _digest(value.get("launch_binding_digest"), field="binding_digest")
    if supplied != normalized["launch_binding_digest"]:
        raise ValueError("benchmark_launch_admission_binding_digest_mismatch")
    return normalized


__all__ = [
    "BENCHMARK_LAUNCH_ADMISSION_RECEIPT_SCHEMA_VERSION",
    "build_benchmark_launch_admission_receipt",
    "normalize_benchmark_launch_admission_receipt",
]
