from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...extensions.execution_envelope import (
    build_extension_execution_envelope,
    validate_extension_execution_envelope,
)


PERIODIC_REPORT_CAPABILITY_ID = "periodic-report"
OPENVIKING_PERIODIC_REPORT_EXTENSION_ID = "openviking-periodic-report"
OPENVIKING_PERIODIC_REPORT_PERMISSION = "openviking_context_write"
PERIODIC_REPORT_SINK_PROTOCOL = "periodic_report_sink_v0"
OPENVIKING_PERIODIC_REPORT_ACTION = "report.archive.write"


def _effect_scope(request: Mapping[str, Any]) -> dict[str, str]:
    context = request.get("context")
    if not isinstance(context, Mapping):
        raise ValueError("request.context must be an object")
    scope = {
        "sink_id": str(context.get("sink_id") or "").strip(),
        "archive_root_uri": str(context.get("archive_root_uri") or "").strip(),
        "idempotency_key": str(context.get("idempotency_key") or "").strip(),
    }
    missing = [key for key, value in scope.items() if not value]
    if missing:
        raise ValueError(f"extension execution scope is missing {missing}")
    return scope


def build_openviking_archive_execution_envelope(
    request: Mapping[str, Any],
    *,
    extension_revision: str,
) -> dict[str, Any]:
    envelope = build_extension_execution_envelope(
        action=OPENVIKING_PERIODIC_REPORT_ACTION,
        scope=_effect_scope(request),
        extension_id=OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
        extension_revision=extension_revision,
        request=request,
    )
    return validate_openviking_archive_execution_envelope(
        envelope,
        request=request,
        extension_revision=extension_revision,
    )


def validate_openviking_archive_execution_envelope(
    raw: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    extension_revision: str,
) -> dict[str, Any]:
    return validate_extension_execution_envelope(
        raw,
        action=OPENVIKING_PERIODIC_REPORT_ACTION,
        scope=_effect_scope(request),
        extension_id=OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
        extension_revision=extension_revision,
        request=request,
    )
