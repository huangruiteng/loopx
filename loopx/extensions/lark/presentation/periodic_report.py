from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ....capabilities.periodic_report.adapters import (
    ARTIFACT_SCHEMA,
    SINK_RESULT_SCHEMA,
    PeriodicReportSinkAdapter,
)
from ....capabilities.periodic_report.core import _reject_raw_keys
from .message_card import build_lark_markdown_reply_card


LarkSendEffect = Callable[[Mapping[str, Any], str], Mapping[str, Any]]
LarkReadbackEffect = Callable[[str], Mapping[str, Any]]


def _required_text(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _card_text(value: object, label: str, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return _required_text(value, label)


def periodic_report_lark_sink_adapter(
    *,
    send: LarkSendEffect,
    readback: LarkReadbackEffect,
    sink_id: str = "lark_delivery",
) -> PeriodicReportSinkAdapter:
    """Build a Lark delivery sink with injected write and readback effects."""

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
            "sink_kind": "lark_message",
            "sink_role": "delivery",
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
        title = _card_text(context.get("title"), "title", default="Periodic report")
        footer = _card_text(
            context.get("footer"),
            "footer",
            default="LoopX periodic_report_v0",
        )
        _reject_raw_keys({"title": title, "footer": footer}, "lark_context")
        card = build_lark_markdown_reply_card(
            artifact.get("content"),
            title=title,
            footer=footer,
        )
        sent = dict(send(card, idempotency_key))
        receipt_ref = _required_text(
            sent.get("receipt_ref") or sent.get("message_id"), "Lark receipt_ref"
        )
        observed = dict(readback(receipt_ref))
        observed_ref = str(
            observed.get("receipt_ref") or observed.get("message_id") or ""
        ).strip()
        verified = observed.get("verified") is True and observed_ref == receipt_ref
        return {
            **base,
            "status": "sent" if verified else "unknown",
            "retryable": not verified,
            "receipt_ref": receipt_ref,
            "readback_verified": verified,
            "external_writes_performed": True,
        }

    adapter = PeriodicReportSinkAdapter(
        sink_id=sink_id,
        sink_kind="lark_message",
        sink_role="delivery",
        deliver=deliver,
    )
    return adapter
