from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ...capabilities.periodic_report.adapters import (
    ARTIFACT_SCHEMA,
    DOCUMENT_SCHEMA,
    PeriodicReportRendererAdapter,
)
from ..public_safety import redact_public_text


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _safe(value: object, *, maximum: int) -> str:
    return str(redact_public_text(value, limit=maximum))


def render_periodic_report_markdown(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Render normalized sections without changing ordering or business meaning."""

    if document.get("schema_version") != DOCUMENT_SCHEMA:
        raise ValueError(f"document must use {DOCUMENT_SCHEMA}")
    title = _safe(document.get("title"), maximum=200)
    window = _mapping(document.get("period_window"))
    lines = [
        f"# {title}",
        "",
        f"Period: `{window.get('start_at')}` – `{window.get('end_at')}`",
    ]
    for section in _items(document.get("sections")):
        lines.extend(["", f"## {_safe(section.get('title'), maximum=160)}", ""])
        section_items = _items(section.get("items"))
        if not section_items:
            lines.append("- No items.")
            continue
        for item in section_items:
            item_title = _safe(item.get("title"), maximum=240)
            source_ref = _safe(item.get("source_ref"), maximum=500)
            status = _safe(item.get("status"), maximum=80)
            headline = f"- **{item_title}**"
            if status:
                headline += f" · `{status}`"
            if source_ref:
                headline += f" · [source]({source_ref})"
            lines.append(headline)
            lines.append(f"  - {_safe(item.get('summary'), maximum=1000)}")
            next_action = _safe(item.get("next_action"), maximum=500)
            if next_action:
                lines.append(f"  - Next: {next_action}")
    content = "\n".join(lines).rstrip() + "\n"
    content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    document_digest = hashlib.sha256(
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": ARTIFACT_SCHEMA,
        "artifact_id": "periodic_report_markdown",
        "renderer_id": "markdown_v0",
        "renderer_kind": "markdown",
        "content": content,
        "content_digest": f"sha256:{content_digest}",
        "artifact_ref": f"artifact:periodic-report/{content_digest[:24]}",
        "document_digest": f"sha256:{document_digest}",
        "boundary": {
            "schedule_policy_applied": False,
            "business_evidence_judged": False,
            "external_writes_performed": False,
        },
    }


def periodic_report_markdown_renderer_adapter() -> PeriodicReportRendererAdapter:
    return PeriodicReportRendererAdapter(
        renderer_id="markdown_v0",
        renderer_kind="markdown",
        render=render_periodic_report_markdown,
    )
