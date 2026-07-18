from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from html import escape
from typing import Any
from urllib.parse import urlparse

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


def _safe_text(value: object, *, maximum: int) -> str:
    return escape(str(redact_public_text(value, limit=maximum)))


def _safe_attr(value: object, *, maximum: int) -> str:
    return escape(
        str(redact_public_text(value, limit=maximum)),
        quote=True,
    )


def _safe_http_url(value: object) -> str | None:
    raw = str(redact_public_text(value, limit=500))
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return escape(raw, quote=True)


def _document_digest(document: Mapping[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _render_item(item: Mapping[str, Any]) -> str:
    title = _safe_text(item.get("title"), maximum=240)
    summary = _safe_text(item.get("summary"), maximum=1000)
    status = _safe_text(item.get("status"), maximum=80)
    source_id = _safe_text(item.get("source_id"), maximum=128)
    next_action = _safe_text(item.get("next_action"), maximum=500)
    source_ref = item.get("source_ref")
    source_url = _safe_http_url(source_ref)
    search_text = " ".join(
        str(item.get(field) or "")
        for field in ("title", "summary", "status", "source_id", "next_action")
    )
    chips = []
    if status:
        chips.append(f'<span class="chip chip-status">{status}</span>')
    if source_id:
        chips.append(f'<span class="chip">{source_id}</span>')
    source = ""
    if source_url:
        source = (
            f'<a class="source-link" href="{source_url}" '
            'target="_blank" rel="noopener noreferrer">Source</a>'
        )
    elif source_ref:
        source = (
            f'<span class="source-ref">{_safe_text(source_ref, maximum=500)}</span>'
        )
    next_block = ""
    if next_action:
        next_block = (
            '<div class="next-action"><strong>Next</strong>'
            f"<span>{next_action}</span></div>"
        )
    return (
        f'<article class="report-item" data-search="{_safe_attr(search_text, maximum=1800)}">'
        '<div class="item-heading">'
        f"<h3>{title}</h3>"
        f'<div class="chips">{"".join(chips)}</div>'
        "</div>"
        f"<p>{summary}</p>"
        f"{next_block}"
        f'<div class="item-footer">{source}</div>'
        "</article>"
    )


def _render_section(section: Mapping[str, Any]) -> str:
    section_id = _safe_attr(section.get("section_id"), maximum=128)
    title = _safe_text(section.get("title"), maximum=160)
    items = _items(section.get("items"))
    body = "".join(_render_item(item) for item in items)
    if not body:
        body = '<p class="empty">No items in this section.</p>'
    return (
        f'<section class="report-section" id="section-{section_id}" '
        f'data-section="{section_id}">'
        '<div class="section-heading">'
        f"<h2>{title}</h2>"
        f'<span class="section-count">{len(items)} items</span>'
        "</div>"
        f'<div class="item-grid">{body}</div>'
        "</section>"
    )


def _render_source_health(sources: Sequence[Mapping[str, Any]]) -> str:
    pills = []
    for source in sources:
        source_id = _safe_text(source.get("source_id"), maximum=128)
        status = _safe_text(source.get("status"), maximum=80)
        pills.append(
            '<span class="source-health">'
            f"<strong>{source_id}</strong><span>{status}</span>"
            "</span>"
        )
    return "".join(pills)


_CSS = """
:root {
  color-scheme: light;
  --ink: #17202f;
  --muted: #687287;
  --line: #dce2ec;
  --paper: #ffffff;
  --wash: #f2f5f9;
  --accent: #315efb;
  --accent-soft: #e9efff;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  background: var(--wash);
  color: var(--ink);
}
* { box-sizing: border-box; }
body { margin: 0; min-width: 300px; }
main { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 44px 0 64px; }
.hero {
  position: relative;
  overflow: hidden;
  border: 1px solid #cad5ff;
  border-radius: 24px;
  padding: 34px;
  background: linear-gradient(135deg, #ffffff 0%, #eef2ff 62%, #e4f5f0 100%);
  box-shadow: 0 18px 55px rgba(39, 55, 96, 0.11);
}
.eyebrow { margin: 0 0 10px; color: var(--accent); font-size: 12px; font-weight: 800;
  letter-spacing: .13em; text-transform: uppercase; }
h1 { max-width: 820px; margin: 0; font-size: clamp(32px, 6vw, 62px); line-height: 1.03;
  letter-spacing: -.045em; }
.period { margin: 18px 0 0; color: var(--muted); font-size: 15px; }
.metrics { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px;
  margin-top: 28px; }
.metric { border: 1px solid rgba(49, 94, 251, .18); border-radius: 15px; padding: 14px 16px;
  background: rgba(255, 255, 255, .76); }
.metric strong { display: block; font-size: 27px; line-height: 1; }
.metric span { display: block; margin-top: 7px; color: var(--muted); font-size: 12px; }
.source-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.source-health { display: inline-flex; gap: 8px; align-items: center; border: 1px solid var(--line);
  border-radius: 999px; padding: 7px 10px; background: rgba(255,255,255,.82); font-size: 12px; }
.source-health span { color: var(--accent); }
.controls { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; gap: 10px;
  margin: 24px 0; padding: 12px; border: 1px solid var(--line); border-radius: 16px;
  background: rgba(242, 245, 249, .92); backdrop-filter: blur(12px); }
.controls input { flex: 1 1 280px; min-width: 0; border: 1px solid #cbd3df; border-radius: 11px;
  padding: 11px 13px; background: var(--paper); color: var(--ink); font: inherit; }
.filter { border: 1px solid #cbd3df; border-radius: 999px; padding: 9px 13px;
  background: var(--paper); color: var(--ink); cursor: pointer; font: inherit; font-size: 13px; }
.filter[aria-pressed="true"] { border-color: var(--accent); background: var(--accent);
  color: #fff; }
.report-section { margin-top: 32px; scroll-margin-top: 96px; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 14px;
  margin-bottom: 13px; }
h2 { margin: 0; font-size: 24px; letter-spacing: -.02em; }
.section-count { color: var(--muted); font-size: 13px; }
.item-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.report-item { display: flex; flex-direction: column; min-height: 190px; border: 1px solid var(--line);
  border-radius: 17px; padding: 20px; background: var(--paper); box-shadow: 0 7px 20px rgba(27, 36, 55, .05); }
.item-heading { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
h3 { margin: 0; font-size: 17px; line-height: 1.35; }
.chips { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; }
.chip { border-radius: 999px; padding: 4px 8px; background: #edf0f5; color: #566075;
  font-size: 11px; white-space: nowrap; }
.chip-status { background: var(--accent-soft); color: #2446b7; }
.report-item > p { margin: 13px 0 0; color: #4e596d; line-height: 1.56; }
.next-action { display: grid; grid-template-columns: auto 1fr; gap: 9px; margin-top: 15px;
  border-left: 3px solid var(--accent); padding: 8px 0 8px 11px; color: #384358; font-size: 13px; }
.item-footer { min-height: 18px; margin-top: auto; padding-top: 16px; font-size: 12px; }
.source-link { color: var(--accent); font-weight: 700; text-decoration: none; }
.source-link:hover { text-decoration: underline; }
.source-ref { color: var(--muted); overflow-wrap: anywhere; }
.empty { border: 1px dashed #cbd3df; border-radius: 15px; padding: 20px; color: var(--muted); }
[hidden] { display: none !important; }
footer { margin-top: 36px; color: var(--muted); font-size: 12px; text-align: center; }
@media (max-width: 760px) {
  main { width: min(100% - 20px, 1180px); padding-top: 10px; }
  .hero { border-radius: 18px; padding: 24px 20px; }
  .metrics { grid-template-columns: 1fr; }
  .item-grid { grid-template-columns: 1fr; }
  .controls { top: 6px; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""


_SCRIPT = """
(() => {
  const search = document.querySelector('[data-report-search]');
  const filters = [...document.querySelectorAll('[data-section-filter]')];
  const sections = [...document.querySelectorAll('[data-section]')];
  let active = 'all';
  const apply = () => {
    const query = (search?.value || '').trim().toLocaleLowerCase();
    sections.forEach((section) => {
      const sectionMatch = active === 'all' || section.dataset.section === active;
      let visible = 0;
      section.querySelectorAll('[data-search]').forEach((item) => {
        const itemMatch = !query || (item.dataset.search || '').toLocaleLowerCase().includes(query);
        item.hidden = !(sectionMatch && itemMatch);
        if (!item.hidden) visible += 1;
      });
      section.hidden = !sectionMatch || visible === 0;
    });
  };
  search?.addEventListener('input', apply);
  filters.forEach((button) => button.addEventListener('click', () => {
    active = button.dataset.sectionFilter || 'all';
    filters.forEach((candidate) => candidate.setAttribute(
      'aria-pressed', String(candidate === button)
    ));
    apply();
  }));
})();
"""


def render_periodic_report_html(document: Mapping[str, Any]) -> dict[str, Any]:
    """Render a self-contained, zero-build interactive HTML report."""

    if document.get("schema_version") != DOCUMENT_SCHEMA:
        raise ValueError(f"document must use {DOCUMENT_SCHEMA}")
    sections = _items(document.get("sections"))
    sources = _items(document.get("source_snapshots"))
    window = _mapping(document.get("period_window"))
    title = _safe_text(document.get("title"), maximum=200)
    item_count = sum(len(_items(section.get("items"))) for section in sections)
    filters = [
        '<button class="filter" data-section-filter="all" '
        'aria-pressed="true">All</button>'
    ]
    for section in sections:
        section_id = _safe_attr(section.get("section_id"), maximum=128)
        section_title = _safe_text(section.get("title"), maximum=160)
        filters.append(
            f'<button class="filter" data-section-filter="{section_id}" '
            f'aria-pressed="false">{section_title}</button>'
        )
    content = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; img-src data:\">"
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        '<main data-renderer="html_artifact_v0">'
        '<header class="hero"><p class="eyebrow">Periodic report</p>'
        f"<h1>{title}</h1>"
        '<p class="period">'
        f"{_safe_text(window.get('start_at'), maximum=80)} — "
        f"{_safe_text(window.get('end_at'), maximum=80)}</p>"
        '<div class="metrics">'
        f'<div class="metric"><strong>{len(sections)}</strong><span>Sections</span></div>'
        f'<div class="metric"><strong>{item_count}</strong><span>Items</span></div>'
        f'<div class="metric"><strong>{len(sources)}</strong><span>Sources</span></div>'
        "</div>"
        f'<div class="source-row">{_render_source_health(sources)}</div>'
        "</header>"
        '<nav class="controls" aria-label="Report filters">'
        '<input type="search" data-report-search placeholder="Filter report items" '
        'aria-label="Filter report items">'
        f"{''.join(filters)}</nav>"
        f"{''.join(_render_section(section) for section in sections)}"
        "<footer>Generated from a renderer-neutral periodic_report_v0 document.</footer>"
        f"</main><script>{_SCRIPT}</script></body></html>\n"
    )
    content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "schema_version": ARTIFACT_SCHEMA,
        "artifact_id": "periodic_report_html",
        "renderer_id": "html_artifact_v0",
        "renderer_kind": "html",
        "media_type": "text/html; charset=utf-8",
        "content": content,
        "content_digest": f"sha256:{content_digest}",
        "artifact_ref": f"artifact:periodic-report/{content_digest[:24]}",
        "document_digest": f"sha256:{_document_digest(document)}",
        "single_file": True,
        "zero_build": True,
        "external_dependencies": [],
        "interactive_controls": ["section_filter", "text_filter"],
        "boundary": {
            "schedule_policy_applied": False,
            "business_evidence_judged": False,
            "external_writes_performed": False,
        },
    }


def periodic_report_html_renderer_adapter() -> PeriodicReportRendererAdapter:
    return PeriodicReportRendererAdapter(
        renderer_id="html_artifact_v0",
        renderer_kind="html",
        render=render_periodic_report_html,
    )
