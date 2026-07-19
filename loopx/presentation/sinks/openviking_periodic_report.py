from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ...capabilities.periodic_report.adapters import (
    ARTIFACT_SCHEMA,
    SINK_RESULT_SCHEMA,
    PeriodicReportSinkAdapter,
)
from ...capabilities.periodic_report.archive import (
    build_periodic_report_archive_bundle,
    verify_periodic_report_archive_receipts,
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
    """Archive a report body and manifest with exact Resource readback."""

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
            "sink_id": adapter.sink_id,
            "sink_kind": "openviking_resource",
            "sink_role": "archive",
            "idempotency_key": idempotency_key,
            "schedule_policy_applied": False,
            "business_evidence_judged": False,
        }
        bundle = build_periodic_report_archive_bundle(
            artifact=artifact,
            document=dict(context.get("document") or {}),
            archive_root_uri=_required_text(
                context.get("archive_root_uri"), "archive_root_uri"
            ),
            delivery_receipts=list(context.get("delivery_receipts") or []),
            semantic_tags=list(context.get("semantic_tags") or []),
            memory_conclusions=list(context.get("memory_conclusions") or []),
        )
        if context.get("execute") is not True:
            return {
                **base,
                "status": "pending",
                "retryable": False,
                "readback_verified": False,
                "external_writes_performed": False,
                "archive_id": bundle["archive_id"],
                "desired_resource_uris": [
                    item["resource_uri"] for item in bundle["resources"]
                ],
                "memory_reference": bundle["memory_reference"],
            }
        write_payload = {
            **bundle,
            "schema_version": "periodic_report_openviking_archive_write_v0",
            "semantic_type": "periodic_report_archive",
            "boundary": {
                **bundle["boundary"],
                "external_writes_performed": False,
            },
        }
        written = dict(write(write_payload, idempotency_key))
        verification = verify_periodic_report_archive_receipts(
            bundle=bundle,
            written=written,
            readback=readback,
        )
        verified = verification["verified"] is True
        manifest_receipt = next(
            item
            for item in verification["resource_receipts"]
            if item["resource_kind"] == "manifest"
        )
        return {
            **base,
            "status": "sent" if verified else "unknown",
            "retryable": not verified,
            "receipt_ref": manifest_receipt["resource_uri"],
            "result_id": manifest_receipt["result_id"],
            "readback_verified": verified,
            "external_writes_performed": True,
            "archive_id": bundle["archive_id"],
            "resource_receipts": verification["resource_receipts"],
            "memory_reference": bundle["memory_reference"],
        }

    adapter = PeriodicReportSinkAdapter(
        sink_id=sink_id,
        sink_kind="openviking_resource",
        sink_role="archive",
        deliver=deliver,
    )
    return adapter
