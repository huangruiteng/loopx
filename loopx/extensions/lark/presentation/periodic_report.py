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
    _normalize_artifact_result,
)
from ....capabilities.periodic_report.audience import (
    build_periodic_report_announcement_plan,
)
from ....capabilities.periodic_report.bindings import (
    _normalize_periodic_report_access_scope_readback,
    _normalize_periodic_report_release_readback,
)
from ....capabilities.periodic_report.core import _reject_raw_keys
from ..goal_channel_delivery_contract import goal_channel_delivery_route
from .message_card import build_lark_markdown_reply_card

LarkSendEffect = Callable[
    [Mapping[str, Any], str, Mapping[str, Any]], Mapping[str, Any]
]
LarkReadbackEffect = Callable[[str], Mapping[str, Any]]
LarkGoalChannelResolver = Callable[[str], Mapping[str, Any]]
LarkGoalChannelVerifier = Callable[[Mapping[str, Any]], bool]
LarkRecipientMentionRenderer = Callable[[str], str]
MiaodaPublishEffect = Callable[[Mapping[str, Any], str, str], Mapping[str, Any]]
MiaodaReadbackEffect = Callable[[str, str], Mapping[str, Any]]

MIAODA_HTML_MAX_BYTES = 10 * 1024 * 1024
MIAODA_ARCHIVE_MAX_BYTES = 20 * 1024 * 1024
MIAODA_UNCOMPRESSED_MAX_BYTES = 200 * 1024 * 1024
_MIAODA_APP_ID_RE = re.compile(r"^app_[a-z0-9]+$")
_LARK_MENTION_MARKUP_RE = re.compile(r"<\s*at\b", re.IGNORECASE)
_LARK_RENDERED_MENTION_RE = re.compile(
    r"^<at\b[^>]*>[^<>]*</at>$",
    re.IGNORECASE,
)
_CALLER_IDENTITY_OVERRIDE_KEYS = frozenset(
    {
        "bot_app_id",
        "bot_display_name",
        "chat_id",
        "identity_mode",
        "lark_profile",
        "profile",
        "sender_identity",
        "sender_profile",
    }
)


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


def _reject_lark_mention_markup(value: object, label: str) -> None:
    if _LARK_MENTION_MARKUP_RE.search(str(value or "")):
        raise ValueError(
            f"{label} must not contain Lark mention markup; use audience_policy"
        )


def _render_lark_mentions(
    recipient_ids: list[str],
    render_recipient_mention: LarkRecipientMentionRenderer | None,
) -> str:
    if not recipient_ids:
        return ""
    if render_recipient_mention is None:
        raise ValueError("matched audience recipients require render_recipient_mention")
    mentions: list[str] = []
    for recipient_id in recipient_ids:
        mention = _required_text(
            render_recipient_mention(recipient_id),
            f"mention for recipient {recipient_id}",
        )
        if not _LARK_RENDERED_MENTION_RE.fullmatch(mention):
            raise ValueError(
                "render_recipient_mention must return one Lark <at> element"
            )
        mentions.append(mention)
    return " ".join(mentions)


def _goal_channel_delivery_route(
    goal_id: object,
    resolve_goal_channel: LarkGoalChannelResolver,
) -> dict[str, Any]:
    return goal_channel_delivery_route(goal_id, resolve_goal_channel)


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
        details = ", ".join(f"{name}={sizes[name]}>{limits[name]}" for name in exceeded)
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
    resolve_goal_channel: LarkGoalChannelResolver,
    verify_goal_channel: LarkGoalChannelVerifier,
    render_recipient_mention: LarkRecipientMentionRenderer | None = None,
    sink_id: str = "lark_delivery",
) -> PeriodicReportSinkAdapter:
    """Build a Lark delivery sink with injected write and readback effects."""

    def deliver(
        artifact: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        if artifact.get("schema_version") != ARTIFACT_SCHEMA:
            raise ValueError(f"artifact must use {ARTIFACT_SCHEMA}")
        override_keys = sorted(_CALLER_IDENTITY_OVERRIDE_KEYS.intersection(context))
        if override_keys:
            raise ValueError(
                "periodic report sender identity is owned by Goal Channel; "
                f"caller overrides are forbidden: {', '.join(override_keys)}"
            )
        route = _goal_channel_delivery_route(
            context.get("goal_id"),
            resolve_goal_channel,
        )
        has_document = context.get("document") is not None
        has_audience_policy = context.get("audience_policy") is not None
        if has_document != has_audience_policy:
            raise ValueError("document and audience_policy must be provided together")
        announcement_plan: dict[str, Any] | None = None
        if has_document:
            document = dict(context["document"])
            _normalize_artifact_result(artifact, expected_document=document)
            announcement_plan = build_periodic_report_announcement_plan(
                document=document,
                audience_policy=dict(context["audience_policy"]),
            )
        idempotency_key = _required_text(
            context.get("idempotency_key"), "idempotency_key"
        )
        title = _card_text(context.get("title"), "title", default="Periodic report")
        footer = _card_text(
            context.get("footer"),
            "footer",
            default="LoopX periodic_report_v0",
        )
        _reject_raw_keys({"title": title, "footer": footer}, "lark_context")
        _reject_lark_mention_markup(artifact.get("content"), "artifact.content")
        _reject_lark_mention_markup(title, "title")
        _reject_lark_mention_markup(footer, "footer")
        base: dict[str, Any] = {
            "schema_version": SINK_RESULT_SCHEMA,
            "sink_id": adapter.sink_id,
            "sink_kind": "lark_message",
            "sink_role": "delivery",
            "idempotency_key": idempotency_key,
            "schedule_policy_applied": False,
            "business_evidence_judged": False,
            "goal_channel_bound": True,
            "sender_identity_required": "project_bot",
        }
        if announcement_plan is not None:
            base["announcement_plan"] = announcement_plan
        if context.get("execute") is not True:
            return {
                **base,
                "status": "pending",
                "retryable": False,
                "readback_verified": False,
                "external_writes_performed": False,
            }
        if verify_goal_channel(route) is not True:
            raise ValueError(
                "periodic report Goal Channel sender identity could not be verified"
            )
        recipient_ids = (
            list(announcement_plan["mentioned_recipient_ids"])
            if announcement_plan is not None
            else []
        )
        mentions = _render_lark_mentions(
            recipient_ids,
            render_recipient_mention,
        )
        markdown = str(artifact.get("content") or "")
        if mentions:
            markdown = f"{mentions}\n\n{markdown}"
        card = build_lark_markdown_reply_card(
            markdown,
            title=title,
            footer=footer,
        )
        sent = dict(send(card, idempotency_key, route))
        receipt_ref = _required_text(
            sent.get("receipt_ref") or sent.get("message_id"), "Lark receipt_ref"
        )
        observed = dict(readback(receipt_ref))
        observed_ref = str(
            observed.get("receipt_ref") or observed.get("message_id") or ""
        ).strip()
        verified = bool(
            observed.get("verified") is True
            and observed_ref == receipt_ref
            and str(observed.get("chat_id") or "") == route["chat_id"]
            and str(observed.get("sender_app_id") or "") == route["bot_app_id"]
            and str(observed.get("sender_identity") or "") == "bot"
            and str(observed.get("sender_evidence_source") or "") == "message_readback"
        )
        return {
            **base,
            "status": "sent" if verified else "unknown",
            "retryable": not verified,
            "receipt_ref": receipt_ref,
            "readback_verified": verified,
            "goal_channel_verified": verified,
            "sender_identity_verified": verified,
            "semantic_dedupe_status": str(
                sent.get("semantic_dedupe_status") or "provider_write_performed"
            ),
            "external_writes_performed": (
                sent.get("external_write_performed") is not False
            ),
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
    """Publish a rendered HTML report to a request-selected existing Miaoda app."""

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
        release_id = _required_text(
            published.get("release_id"), "Miaoda publish release_id"
        )
        observed = dict(readback(app_id, release_id))
        observed_app_id = str(observed.get("app_id") or "").strip()
        observed_url = str(
            observed.get("online_url") or observed.get("url") or ""
        ).strip()
        release_readback = _normalize_periodic_report_release_readback(
            observed.get("release_readback"),
            "Miaoda release_readback",
            expected_release_id=release_id,
        )
        access_scope_readback = _normalize_periodic_report_access_scope_readback(
            observed.get("access_scope_readback"), "Miaoda access_scope_readback"
        )
        verified = (
            observed.get("is_published") is True
            and observed_app_id == app_id
            and observed_url == online_url
            and release_readback["release_id"] == release_id
            and release_readback["status"] == "finished"
            and release_readback["verified"] is True
        )
        result: dict[str, Any] = {
            **base,
            "status": "sent" if verified else "unknown",
            "retryable": not verified,
            "receipt_ref": online_url,
            "result_id": app_id,
            "online_url": online_url,
            "release_id": release_id,
            "release_readback": release_readback,
            "access_scope_readback": access_scope_readback,
            "content_readback": {
                "status": "unavailable",
                "digest_verified": False,
                "reason": "provider_does_not_expose_remote_content_digest",
            },
            "readback_verified": verified,
            "external_writes_performed": True,
        }
        access_scope = access_scope_readback.get("scope")
        if access_scope is not None:
            result["access_scope"] = _required_text(access_scope, "Miaoda access_scope")
        if access_scope_readback.get("require_login") is not None:
            result["require_login"] = access_scope_readback["require_login"]
        return result

    adapter = PeriodicReportSinkAdapter(
        sink_id=sink_id,
        sink_kind="miaoda_html",
        sink_role="delivery",
        deliver=deliver,
    )
    return adapter
