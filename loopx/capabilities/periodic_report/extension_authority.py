from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from ...extensions.authority import (
    build_extension_authority_decision,
    validate_extension_authority_decision,
)


PERIODIC_REPORT_CAPABILITY_ID = "periodic-report"
OPENVIKING_PERIODIC_REPORT_EXTENSION_ID = "openviking-periodic-report"
OPENVIKING_PERIODIC_REPORT_PERMISSION = "openviking_context_write"
PERIODIC_REPORT_SINK_PROTOCOL = "periodic_report_sink_v0"
OPENVIKING_PERIODIC_REPORT_ACTION = "report.archive.write"


def _authority_scope(request: Mapping[str, Any]) -> dict[str, str]:
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
        raise ValueError(f"extension authority scope is missing {missing}")
    return scope


def build_openviking_archive_authority_decision(
    request: Mapping[str, Any],
    *,
    extension_revision: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    decision = build_extension_authority_decision(
        capability_id=PERIODIC_REPORT_CAPABILITY_ID,
        protocol=PERIODIC_REPORT_SINK_PROTOCOL,
        permission=OPENVIKING_PERIODIC_REPORT_PERMISSION,
        action=OPENVIKING_PERIODIC_REPORT_ACTION,
        scope=_authority_scope(request),
        extension_id=OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
        extension_revision=extension_revision,
        request=request,
        now=now,
    )
    return validate_openviking_archive_authority_decision(
        decision,
        request=request,
        extension_revision=extension_revision,
        now=now,
    )


def validate_openviking_archive_authority_decision(
    raw: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    extension_revision: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    return validate_extension_authority_decision(
        raw,
        capability_id=PERIODIC_REPORT_CAPABILITY_ID,
        protocol=PERIODIC_REPORT_SINK_PROTOCOL,
        permission=OPENVIKING_PERIODIC_REPORT_PERMISSION,
        action=OPENVIKING_PERIODIC_REPORT_ACTION,
        scope=_authority_scope(request),
        extension_id=OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
        extension_revision=extension_revision,
        request=request,
        now=now,
    )
