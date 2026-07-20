from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest

from loopx.capabilities.periodic_report import (
    build_periodic_report_delivery_receipt,
    build_periodic_report_document,
    build_periodic_report_extension_readiness,
    build_periodic_report_generation_bundle,
    build_periodic_report_source_result,
)
from loopx.presentation.renderers.periodic_report_html import (
    render_periodic_report_html,
)
from loopx.presentation.renderers.periodic_report_markdown import (
    render_periodic_report_markdown,
)


def _document() -> dict[str, Any]:
    source = build_periodic_report_source_result(
        source_id="project_progress",
        source_kind="validated_outcomes",
        status="complete",
        observed_at="2026-07-20T00:40:00Z",
        sections=[
            {
                "section_id": "completed",
                "title": "Completed",
                "order": 10,
                "items": [
                    {
                        "item_id": "release_2.4",
                        "title": "Release 2.4",
                        "summary": "Published the stable release.",
                        "value_rank": 50,
                    }
                ],
            }
        ],
    )
    return build_periodic_report_document(
        title="Project report",
        generated_at="2026-07-20T01:00:00Z",
        period_window={
            "start_at": "2026-07-13T00:00:00Z",
            "end_at": "2026-07-20T00:00:00Z",
        },
        profile={"profile_id": "project", "profile_version": "v1"},
        sources=[source],
    )


def _generation() -> dict[str, Any]:
    document = _document()
    return build_periodic_report_generation_bundle(
        document=document,
        artifacts=[
            render_periodic_report_markdown(document),
            render_periodic_report_html(document),
        ],
    )


def _binding(*, policy: str = "required") -> dict[str, Any]:
    return {
        "schema_version": "periodic_report_sink_binding_v0",
        "sink_id": "team_chat_delivery",
        "sink_kind": "team_chat_message",
        "sink_role": "delivery",
        "dependency_policy": policy,
        "capability": {
            "capability_id": "report.message.write",
            "capability_version": "v0",
        },
        "extension": {
            "extension_id": "team_chat_report_sink",
            "extension_version": "1.0.0",
            "protocol": "periodic_report_sink_v0",
        },
    }


def _extension_receipt(*, verified: bool = True) -> dict[str, Any]:
    return {
        "extension_id": "team_chat_report_sink",
        "extension_version": "1.0.0",
        "protocol": "periodic_report_sink_v0",
        "status": "ready",
        "readback_verified": verified,
        "capabilities": [
            {
                "capability_id": "report.message.write",
                "capability_version": "v0",
            }
        ],
    }


def _sent_result() -> dict[str, Any]:
    return {
        "schema_version": "periodic_report_sink_result_v0",
        "sink_id": "team_chat_delivery",
        "sink_kind": "team_chat_message",
        "sink_role": "delivery",
        "status": "sent",
        "idempotency_key": "report-delivery-example",
        "receipt_ref": "message:example",
        "result_id": "message-result-example",
        "readback_verified": True,
        "retryable": False,
    }


def _readiness_identity(receipt: dict[str, Any]) -> str:
    identity = {
        "generation_id": receipt["generation_id"],
        "mode": receipt["delivery_mode"],
        "bindings": receipt["sink_readiness"],
    }
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"report_readiness_{hashlib.sha256(encoded).hexdigest()[:24]}"


def test_generation_bundle_is_provider_free_and_binds_both_artifacts() -> None:
    bundle = _generation()

    assert bundle["ok"] is True
    assert bundle["generation_receipt"]["provider_required"] is False
    assert bundle["generation_receipt"]["external_writes_performed"] is False
    assert {artifact["renderer_kind"] for artifact in bundle["artifacts"]} == {
        "html",
        "markdown",
    }
    assert {artifact["document_digest"] for artifact in bundle["artifacts"]} == {
        bundle["generation_receipt"]["document_digest"]
    }


def test_portable_generation_needs_no_provider_or_delivery() -> None:
    generation = _generation()["generation_receipt"]
    readiness = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[],
    )
    delivery = build_periodic_report_delivery_receipt(
        generation_receipt=generation,
        readiness_receipt=readiness,
    )

    assert readiness["delivery_mode"] == "portable"
    assert readiness["status"] == "not_required"
    assert readiness["generation_usable"] is True
    assert delivery["status"] == "not_required"
    assert delivery["ok"] is True


def test_optional_provider_degrades_without_invalidating_generation() -> None:
    generation = _generation()["generation_receipt"]
    readiness = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[_binding(policy="optional")],
    )
    delivery = build_periodic_report_delivery_receipt(
        generation_receipt=generation,
        readiness_receipt=readiness,
    )

    assert readiness["delivery_mode"] == "enhanced"
    assert readiness["status"] == "degraded"
    assert readiness["generation_usable"] is True
    assert readiness["formal_delivery_required"] is False
    assert delivery["status"] == "partial"
    assert delivery["retryable_sinks"] == ["team_chat_delivery"]


def test_required_provider_fails_closed_until_exact_readback() -> None:
    generation = _generation()["generation_receipt"]
    missing = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[_binding()],
    )
    blocked = build_periodic_report_delivery_receipt(
        generation_receipt=generation,
        readiness_receipt=missing,
    )
    assert missing["delivery_mode"] == "durable"
    assert missing["status"] == "blocked"
    assert blocked["status"] == "failed"
    assert blocked["ok"] is False

    ready = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[_binding()],
        extension_receipts=[_extension_receipt()],
    )
    delivered = build_periodic_report_delivery_receipt(
        generation_receipt=generation,
        readiness_receipt=ready,
        sink_results=[_sent_result()],
    )
    assert ready["status"] == "ready"
    assert ready["delivery_allowed"] is True
    assert delivered["status"] == "succeeded"
    assert delivered["sink_receipts"][0]["readback_verified"] is True


def test_mismatched_or_unverified_extension_is_not_ready() -> None:
    generation = _generation()["generation_receipt"]
    incompatible = _extension_receipt()
    incompatible["extension_version"] = "2.0.0"

    version_mismatch = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[_binding()],
        extension_receipts=[incompatible],
    )
    unverified = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[_binding()],
        extension_receipts=[_extension_receipt(verified=False)],
    )

    assert version_mismatch["sink_readiness"][0]["status"] == "incompatible"
    assert version_mismatch["status"] == "blocked"
    assert unverified["sink_readiness"][0]["status"] == "unverified"
    assert unverified["status"] == "blocked"


def test_generation_and_delivery_receipts_reject_tampering() -> None:
    bundle = _generation()
    generation = bundle["generation_receipt"]
    readiness = build_periodic_report_extension_readiness(
        generation_receipt=generation,
        sink_bindings=[_binding()],
        extension_receipts=[_extension_receipt()],
    )

    other_document = deepcopy(bundle["document"])
    other_document["title"] = "A different report"
    with pytest.raises(ValueError, match="does not match document"):
        build_periodic_report_generation_bundle(
            document=other_document,
            artifacts=bundle["artifacts"],
        )

    tampered_readiness = deepcopy(readiness)
    tampered_readiness["sink_readiness"][0]["ready"] = False
    with pytest.raises(ValueError, match="ready does not match"):
        build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=tampered_readiness,
            sink_results=[_sent_result()],
        )

    forged_readiness = deepcopy(readiness)
    forged_readiness["sink_readiness"][0]["provider_receipt"] = None
    forged_readiness["readiness_id"] = _readiness_identity(forged_readiness)
    with pytest.raises(ValueError, match="status does not match provider receipt"):
        build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=forged_readiness,
            sink_results=[_sent_result()],
        )

    missing_readback = _sent_result()
    missing_readback["readback_verified"] = False
    with pytest.raises(ValueError, match="requires exact readback"):
        build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=readiness,
            sink_results=[missing_readback],
        )

    unknown_sink = _sent_result()
    unknown_sink["sink_id"] = "unbound_delivery"
    with pytest.raises(ValueError, match="unbound sink"):
        build_periodic_report_delivery_receipt(
            generation_receipt=generation,
            readiness_receipt=readiness,
            sink_results=[unknown_sink],
        )
