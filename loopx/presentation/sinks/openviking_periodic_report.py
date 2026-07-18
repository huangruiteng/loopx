from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ...capabilities.periodic_report.adapters import (
    ARTIFACT_SCHEMA,
    SINK_RESULT_SCHEMA,
    PeriodicReportSinkAdapter,
)


OpenVikingWriteEffect = Callable[[Mapping[str, Any], str], Mapping[str, Any]]
OpenVikingReadbackEffect = Callable[[str], Mapping[str, Any]]


def _required_text(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def periodic_report_openviking_sink_adapter(
    *,
    write: OpenVikingWriteEffect,
    readback: OpenVikingReadbackEffect,
    sink_id: str = "openviking_archive",
) -> PeriodicReportSinkAdapter:
    """Build the minimal OpenViking artifact-and-readback seam.

    Manifest policy and history indexing remain a separate archive capability;
    this adapter only writes a renderer artifact and verifies its exact result id.
    """

    def deliver(
        artifact: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        if artifact.get("schema_version") != ARTIFACT_SCHEMA:
            raise ValueError(f"artifact must use {ARTIFACT_SCHEMA}")
        idempotency_key = _required_text(
            context.get("idempotency_key"), "idempotency_key"
        )
        base: dict[str, Any] = {
            "schema_version": SINK_RESULT_SCHEMA,
            "sink_id": sink_id,
            "sink_kind": "openviking_resource",
            "sink_role": "archive",
            "idempotency_key": idempotency_key,
            "schedule_policy_applied": False,
            "business_evidence_judged": False,
        }
        if context.get("execute") is not True:
            return {
                **base,
                "status": "pending",
                "retryable": False,
                "readback_verified": False,
                "external_writes_performed": False,
            }
        write_payload = {
            "schema_version": "periodic_report_openviking_write_v0",
            "artifact_ref": artifact.get("artifact_ref"),
            "content": artifact.get("content"),
            "content_digest": artifact.get("content_digest"),
            "document_digest": artifact.get("document_digest"),
            "semantic_type": "periodic_report",
        }
        written = dict(write(write_payload, idempotency_key))
        receipt_ref = _required_text(
            written.get("receipt_ref") or written.get("resource_uri"),
            "OpenViking receipt_ref",
        )
        result_id = _required_text(written.get("result_id"), "OpenViking result_id")
        observed = dict(readback(receipt_ref))
        observed_ref = str(
            observed.get("receipt_ref") or observed.get("resource_uri") or ""
        ).strip()
        observed_result_id = str(observed.get("result_id") or "").strip()
        verified = (
            observed.get("verified") is True
            and observed_ref == receipt_ref
            and observed_result_id == result_id
        )
        return {
            **base,
            "status": "sent" if verified else "unknown",
            "retryable": not verified,
            "receipt_ref": receipt_ref,
            "result_id": result_id,
            "readback_verified": verified,
            "external_writes_performed": True,
        }

    return PeriodicReportSinkAdapter(
        sink_id=sink_id,
        sink_kind="openviking_resource",
        sink_role="archive",
        deliver=deliver,
    )
