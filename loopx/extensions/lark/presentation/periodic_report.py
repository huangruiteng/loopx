from __future__ import annotations

import gzip
import io
import re
import tarfile
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

from ....capabilities.periodic_report.adapters import (
    ARTIFACT_SCHEMA,
    SINK_RESULT_SCHEMA,
    PeriodicReportSinkAdapter,
)
from ....capabilities.periodic_report.core import _reject_raw_keys
from .message_card import build_lark_markdown_reply_card


LarkSendEffect = Callable[[Mapping[str, Any], str], Mapping[str, Any]]
LarkReadbackEffect = Callable[[str], Mapping[str, Any]]
MiaodaPublishEffect = Callable[
    [Mapping[str, Any], str, str], Mapping[str, Any]
]
MiaodaReadbackEffect = Callable[[str], Mapping[str, Any]]

MIAODA_HTML_MAX_BYTES = 10 * 1024 * 1024
MIAODA_ARCHIVE_MAX_BYTES = 20 * 1024 * 1024
MIAODA_UNCOMPRESSED_MAX_BYTES = 200 * 1024 * 1024
_MIAODA_APP_ID_RE = re.compile(r"^app_[a-z0-9]+$")


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


def _miaoda_app_id(value: object) -> str:
    app_id = _required_text(value, "app_id")
    if not _MIAODA_APP_ID_RE.fullmatch(app_id):
        raise ValueError("app_id must be a Miaoda HTML app id beginning with app_")
    return app_id


def _https_url(value: object, label: str) -> str:
    url = _required_text(value, label)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{label} must be an https URL")
    return url


def _miaoda_html_preflight(artifact: Mapping[str, Any]) -> dict[str, Any]:
    if artifact.get("renderer_kind") != "html":
        raise ValueError("Miaoda publication requires an HTML artifact")
    if artifact.get("single_file") is not True:
        raise ValueError("Miaoda publication requires a single-file HTML artifact")
    content = artifact.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("artifact.content is required")
    html_bytes = content.encode("utf-8")
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
        info = tarfile.TarInfo("index.html")
        info.size = len(html_bytes)
        info.mode = 0o644
        info.mtime = 0
        archive.addfile(info, io.BytesIO(html_bytes))
    archive_bytes = gzip.compress(tar_buffer.getvalue(), mtime=0)
    sizes = {
        "html_bytes": len(html_bytes),
        "archive_bytes": len(archive_bytes),
        "uncompressed_bytes": len(html_bytes),
    }
    limits = {
        "html_bytes": MIAODA_HTML_MAX_BYTES,
        "archive_bytes": MIAODA_ARCHIVE_MAX_BYTES,
        "uncompressed_bytes": MIAODA_UNCOMPRESSED_MAX_BYTES,
    }
    exceeded = [name for name, value in sizes.items() if value > limits[name]]
    if exceeded:
        details = ", ".join(
            f"{name}={sizes[name]}>{limits[name]}" for name in exceeded
        )
        raise ValueError(f"Miaoda HTML publication size limit exceeded: {details}")
    return {
        "status": "passed",
        **sizes,
        "limits": limits,
    }


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


def periodic_report_miaoda_html_sink_adapter(
    *,
    publish: MiaodaPublishEffect,
    readback: MiaodaReadbackEffect,
    sink_id: str = "miaoda_html_delivery",
) -> PeriodicReportSinkAdapter:
    """Publish a rendered HTML report to a profile-owned Miaoda app."""

    def deliver(
        artifact: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        if artifact.get("schema_version") != ARTIFACT_SCHEMA:
            raise ValueError(f"artifact must use {ARTIFACT_SCHEMA}")
        idempotency_key = _required_text(
            context.get("idempotency_key"), "idempotency_key"
        )
        app_id = _miaoda_app_id(context.get("app_id"))
        preflight = _miaoda_html_preflight(artifact)
        base: dict[str, Any] = {
            "schema_version": SINK_RESULT_SCHEMA,
            "sink_id": adapter.sink_id,
            "sink_kind": "miaoda_html",
            "sink_role": "delivery",
            "idempotency_key": idempotency_key,
            "app_id": app_id,
            "artifact_digest": artifact.get("content_digest"),
            "preflight": preflight,
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

        published = dict(publish(artifact, app_id, idempotency_key))
        published_app_id = _miaoda_app_id(published.get("app_id") or app_id)
        if published_app_id != app_id:
            raise ValueError("Miaoda publish returned a different app_id")
        online_url = _https_url(
            published.get("online_url") or published.get("url"),
            "Miaoda online_url",
        )
        observed = dict(readback(app_id))
        observed_app_id = str(observed.get("app_id") or "").strip()
        observed_url = str(
            observed.get("online_url") or observed.get("url") or ""
        ).strip()
        verified = (
            observed.get("is_published") is True
            and observed_app_id == app_id
            and observed_url == online_url
        )
        result: dict[str, Any] = {
            **base,
            "status": "sent" if verified else "unknown",
            "retryable": not verified,
            "receipt_ref": online_url,
            "result_id": app_id,
            "online_url": online_url,
            "readback_verified": verified,
            "external_writes_performed": True,
        }
        access_scope = observed.get("access_scope") or observed.get("scope")
        if access_scope is not None:
            result["access_scope"] = _required_text(
                access_scope, "Miaoda access_scope"
            )
        if observed.get("require_login") is not None:
            if not isinstance(observed["require_login"], bool):
                raise ValueError("Miaoda require_login must be a boolean")
            result["require_login"] = observed["require_login"]
        return result

    adapter = PeriodicReportSinkAdapter(
        sink_id=sink_id,
        sink_kind="miaoda_html",
        sink_role="delivery",
        deliver=deliver,
    )
    return adapter
