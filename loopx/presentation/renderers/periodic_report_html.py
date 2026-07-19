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
from .periodic_report_markdown import render_periodic_report_markdown


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _safe_text(value: object, *, maximum: int) -> str:
    return escape(str(redact_public_text(value, limit=maximum)))


def _safe_attr(value: object, *, maximum: int) -> str:
    return escape(str(redact_public_text(value, limit=maximum)), quote=True)


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


def _embedded_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _render_tags(value: object) -> str:
    tags = [
        _safe_text(tag, maximum=128)
        for tag in value
        if isinstance(tag, str) and tag.strip()
    ] if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []
    if not tags:
        return ""
    return '<span class="tags">' + "".join(
        f'<span class="tag">{tag}</span>' for tag in tags
    ) + "</span>"


def _render_item(item: Mapping[str, Any], *, index: int) -> str:
    title = _safe_text(item.get("title"), maximum=240)
    summary = _safe_text(item.get("summary"), maximum=1000)
    status = _safe_text(item.get("status"), maximum=80)
    source_id = _safe_text(item.get("source_id"), maximum=128)
    next_action = _safe_text(item.get("next_action"), maximum=500)
    source_ref = item.get("source_ref")
    source_url = _safe_http_url(source_ref)
    search_text = " ".join(
        str(item.get(field) or "")
        for field in (
            "title",
            "summary",
            "status",
            "source_id",
            "next_action",
            "tags",
        )
    )
    kicker = ""
    if status:
        kicker += f'<span class="status">{status}</span>'
    kicker += _render_tags(item.get("tags"))
    next_block = ""
    if next_action:
        next_block = (
            '<div class="next-action"><span>Next</span>'
            f"<p>{next_action}</p></div>"
        )
    if source_url:
        source = (
            f'<a class="source-link" href="{source_url}" '
            'target="_blank" rel="noopener noreferrer">Evidence ↗</a>'
        )
    elif source_ref:
        source = (
            '<span class="source-ref">'
            f"{_safe_text(source_ref, maximum=500)}</span>"
        )
    elif source_id:
        source = f'<span class="source-ref">{source_id}</span>'
    else:
        source = ""
    footer = f'<div class="item-footer">{source}</div>' if source else ""
    return (
        f'<article class="report-row" data-search="{_safe_attr(search_text, maximum=2200)}">'
        f'<div class="row-index">{index:02d}</div>'
        '<div class="row-main">'
        f'<div class="row-kicker">{kicker}</div>'
        f"<h3>{title}</h3>"
        f'<p class="summary">{summary}</p>'
        f"{next_block}{footer}"
        "</div></article>"
    )


def _render_section(
    section: Mapping[str, Any],
    *,
    section_index: int,
    item_start: int,
) -> tuple[str, int]:
    section_id = _safe_attr(section.get("section_id"), maximum=128)
    title = _safe_text(section.get("title"), maximum=160)
    items = _items(section.get("items"))
    rows = "".join(
        _render_item(item, index=item_start + offset)
        for offset, item in enumerate(items)
    )
    if not rows:
        rows = '<p class="empty">No items in this section.</p>'
    content = (
        f'<section class="report-section" id="section-{section_id}" '
        f'data-section="{section_id}">'
        '<div class="section-heading"><div>'
        f'<p class="eyebrow">{section_index:02d} / Report</p>'
        f"<h2>{title}</h2></div>"
        f'<span class="section-count">{len(items)} items</span>'
        f'</div><div class="rows">{rows}</div></section>'
    )
    return content, item_start + len(items)


def _render_source_receipts(sources: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for source in sources:
        rows.append(
            "<tr>"
            f'<th scope="row">{_safe_text(source.get("source_id"), maximum=128)}</th>'
            f'<td>{_safe_text(source.get("status"), maximum=80)}</td>'
            f'<td>{_safe_text(source.get("item_count"), maximum=40)}</td>'
            f'<td><code>{_safe_text(source.get("snapshot_digest"), maximum=128)}</code></td>'
            "</tr>"
        )
    if not rows:
        return '<p class="empty">No source receipts.</p>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>Source</th><th>Status</th><th>Items</th><th>Snapshot</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


_CSS = """
:root {
  color-scheme: light;
  --ivory: #faf9f5;
  --ink: #171714;
  --paper: #ffffff;
  --clay: #d97757;
  --oat: #e3dacc;
  --line: #d1cfc5;
  --muted: #77766f;
  --soft: #f0eee6;
  --serif: ui-serif, Georgia, Cambria, "Times New Roman", serif;
  --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  --mono: ui-monospace, "SFMono-Regular", Consolas, monospace;
  background: var(--ivory);
  color: var(--ink);
  font-family: var(--sans);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; min-width: 300px; font-size: 15px; line-height: 1.65; }
button, input { font: inherit; }
.shell { width: min(1220px, calc(100% - 40px)); margin: 0 auto; padding: 40px 0 80px; }
.masthead { border-top: 8px solid var(--ink); border-bottom: 1.5px solid var(--ink);
  padding: 27px 0 26px; }
.mast-grid { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 28px;
  align-items: end; }
.eyebrow { margin: 0 0 8px; color: var(--muted); font: 650 10px/1.4 var(--mono);
  letter-spacing: .1em; text-transform: uppercase; }
h1, h2, h3 { font-family: var(--serif); font-weight: 500; letter-spacing: -.018em; }
h1 { max-width: 900px; margin: 0; font-size: clamp(39px, 6vw, 72px); line-height: .98; }
.period { margin: 18px 0 0; color: #454541; font-size: 15px; }
.report-facts { display: grid; grid-template-columns: repeat(3, minmax(78px, 1fr)); gap: 1px;
  border: 1px solid var(--line); background: var(--line); }
.fact { min-width: 92px; padding: 13px 14px; background: var(--paper); }
.fact strong { display: block; font: 500 28px/1 var(--serif); }
.fact span { display: block; margin-top: 5px; color: var(--muted); font-size: 10px;
  letter-spacing: .04em; text-transform: uppercase; }
.layout { display: grid; grid-template-columns: 205px minmax(0, 1fr); gap: 48px;
  margin-top: 44px; }
.rail { position: sticky; top: 18px; align-self: start; }
.rail-label { margin: 0 0 10px; color: var(--muted); font: 650 10px/1.4 var(--mono);
  letter-spacing: .09em; text-transform: uppercase; }
.rail nav { display: grid; border-top: 1px solid var(--line); }
.section-filter { display: grid; grid-template-columns: 26px 1fr; gap: 8px; width: 100%;
  border: 0; border-bottom: 1px solid var(--line); padding: 10px 2px; background: transparent;
  color: #3e3e3a; cursor: pointer; text-align: left; font-size: 13px; }
.section-filter span { color: var(--muted); font: 10px/1.7 var(--mono); }
.section-filter[aria-pressed="true"] { color: var(--clay); }
.search { width: 100%; margin-top: 15px; border: 1px solid var(--line); border-radius: 8px;
  padding: 9px 10px; background: var(--paper); color: var(--ink); font-size: 12px; }
.tools { display: grid; grid-template-columns: 1fr; gap: 7px; margin-top: 9px; }
.tool { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
  background: var(--paper); color: var(--ink); cursor: pointer; text-align: left; font-size: 12px; }
.tool:hover, .search:focus { border-color: var(--ink); outline: none; }
.report-section { margin-bottom: 58px; scroll-margin-top: 20px; }
.section-heading { display: flex; justify-content: space-between; gap: 20px; align-items: end;
  padding-bottom: 13px; border-bottom: 2px solid var(--ink); }
h2 { margin: 0; font-size: 33px; line-height: 1.05; }
.section-count { color: var(--muted); font: 11px/1.4 var(--mono); white-space: nowrap; }
.rows { border-bottom: 1px solid var(--line); }
.report-row { display: grid; grid-template-columns: 50px minmax(0, 1fr); gap: 18px;
  padding: 24px 0; border-top: 1px solid var(--line); }
.report-row:first-child { border-top: 0; }
.row-index { color: var(--line); font: 500 28px/1 var(--serif); }
.row-kicker { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; min-height: 20px;
  margin-bottom: 6px; }
.status { border-radius: 999px; padding: 2px 8px; background: var(--oat); color: #454541;
  font: 10px/1.5 var(--mono); }
.tags { display: inline-flex; flex-wrap: wrap; gap: 5px; }
.tag { color: var(--muted); font: 9px/1.4 var(--mono); letter-spacing: .04em;
  text-transform: uppercase; }
.tag + .tag::before { content: "·"; margin-right: 5px; color: var(--line); }
h3 { margin: 0; font-size: 24px; line-height: 1.2; }
.summary { max-width: 820px; margin: 9px 0 0; color: #42423e; line-height: 1.72; }
.next-action { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 11px;
  margin-top: 14px; border-left: 3px solid var(--clay); padding: 7px 0 7px 11px; }
.next-action span { color: var(--clay); font: 650 9px/1.6 var(--mono); letter-spacing: .06em;
  text-transform: uppercase; }
.next-action p { margin: 0; color: #4a4a45; font-size: 13px; }
.item-footer { margin-top: 11px; }
.source-link, .source-ref { color: var(--clay); font: 650 10px/1.4 var(--mono);
  letter-spacing: .04em; text-decoration: none; overflow-wrap: anywhere; }
.source-link:hover { text-decoration: underline; }
.source-ref { color: var(--muted); }
.supporting { margin: 10px 0 0; border-top: 1px solid var(--line); padding-top: 14px; }
.supporting > summary { cursor: pointer; color: var(--muted); font-size: 12px; }
.supporting[open] > summary { color: var(--ink); }
.supporting-body { margin-top: 13px; border: 1px solid var(--line); border-radius: 10px;
  padding: 14px; background: var(--paper); }
.metadata { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 5px 14px;
  margin: 0 0 13px; font-size: 11px; }
.metadata dt { color: var(--muted); }
.metadata dd { margin: 0; overflow-wrap: anywhere; }
.metadata code, td code { font: 10px/1.45 var(--mono); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 11px; text-align: left; }
th, td { border-top: 1px solid var(--line); padding: 7px 9px; vertical-align: top; }
thead th { border-top: 0; color: var(--muted); font-weight: 600; }
.empty { padding: 18px 0; color: var(--muted); }
.toast { position: fixed; right: 20px; bottom: 20px; transform: translateY(16px);
  opacity: 0; border-radius: 8px; padding: 9px 12px; background: var(--ink); color: #fff;
  font-size: 12px; transition: .18s ease; pointer-events: none; }
.toast.show { transform: none; opacity: 1; }
[hidden] { display: none !important; }
@media (max-width: 820px) {
  .shell { width: min(100% - 26px, 760px); padding-top: 20px; }
  .mast-grid { grid-template-columns: 1fr; }
  .report-facts { width: 100%; }
  .layout { grid-template-columns: 1fr; gap: 32px; }
  .rail { position: static; }
  .rail nav { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tools { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 520px) {
  h1 { font-size: 41px; }
  .report-facts { grid-template-columns: 1fr; }
  .fact { display: flex; justify-content: space-between; align-items: baseline; }
  .rail nav, .tools { grid-template-columns: 1fr; }
  .report-row { grid-template-columns: 34px minmax(0, 1fr); gap: 9px; }
  h3 { font-size: 21px; }
}
@media print {
  .rail, .toast, .supporting { display: none !important; }
  .layout { grid-template-columns: 1fr; }
  .shell { width: 100%; padding: 0; }
  body { background: #fff; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .toast { transition: none; }
}
"""


_SCRIPT = """
(() => {
  const search = document.querySelector('[data-report-search]');
  const filters = [...document.querySelectorAll('[data-section-filter]')];
  const sections = [...document.querySelectorAll('[data-section]')];
  let active = 'all';
  const apply = () => {
    const query = (search && search.value || '').trim().toLocaleLowerCase();
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
  if (search) search.addEventListener('input', apply);
  filters.forEach((button) => button.addEventListener('click', () => {
    active = button.dataset.sectionFilter || 'all';
    filters.forEach((candidate) => candidate.setAttribute(
      'aria-pressed', String(candidate === button)
    ));
    apply();
  }));
  const toast = document.querySelector('[data-copy-toast]');
  const copy = document.querySelector('[data-copy-markdown]');
  if (copy) copy.addEventListener('click', async () => {
    const payload = document.querySelector('[data-report-markdown]');
    const text = payload ? JSON.parse(payload.textContent || '\"\"') : '';
    await navigator.clipboard.writeText(text);
    if (toast) {
      toast.classList.add('show');
      window.setTimeout(() => toast.classList.remove('show'), 1400);
    }
  });
  const print = document.querySelector('[data-print-report]');
  if (print) print.addEventListener('click', () => window.print());
})();
"""


def render_periodic_report_html(document: Mapping[str, Any]) -> dict[str, Any]:
    """Render one dense, self-contained report without changing its semantics."""

    if document.get("schema_version") != DOCUMENT_SCHEMA:
        raise ValueError(f"document must use {DOCUMENT_SCHEMA}")
    sections = _items(document.get("sections"))
    sources = _items(document.get("source_snapshots"))
    window = _mapping(document.get("period_window"))
    profile = _mapping(document.get("profile"))
    title = _safe_text(document.get("title"), maximum=200)
    item_count = sum(len(_items(section.get("items"))) for section in sections)
    document_digest = _document_digest(document)
    markdown_artifact = render_periodic_report_markdown(document)

    filters = [
        '<button class="section-filter" data-section-filter="all" '
        'aria-pressed="true"><span>00</span>All sections</button>'
    ]
    rendered_sections = []
    next_item_index = 1
    for section_index, section in enumerate(sections, start=1):
        section_id = _safe_attr(section.get("section_id"), maximum=128)
        section_title = _safe_text(section.get("title"), maximum=160)
        filters.append(
            f'<button class="section-filter" data-section-filter="{section_id}" '
            f'aria-pressed="false"><span>{section_index:02d}</span>{section_title}</button>'
        )
        section_html, next_item_index = _render_section(
            section,
            section_index=section_index,
            item_start=next_item_index,
        )
        rendered_sections.append(section_html)

    generated_at = _safe_text(document.get("generated_at"), maximum=80)
    profile_id = _safe_text(profile.get("profile_id"), maximum=128)
    profile_version = _safe_text(profile.get("profile_version"), maximum=128)
    content = (
        "<!doctype html>\n"
        '<html lang="und"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; img-src data:\">"
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        '<div class="shell" data-renderer="html_artifact_v0" '
        'data-presentation="editorial_dense_v1">'
        '<header class="masthead"><div class="mast-grid"><div>'
        '<p class="eyebrow">Periodic report</p>'
        f"<h1>{title}</h1>"
        f'<p class="period">{_safe_text(window.get("start_at"), maximum=80)} — '
        f'{_safe_text(window.get("end_at"), maximum=80)}</p></div>'
        '<div class="report-facts" aria-label="Report facts">'
        f'<div class="fact"><strong>{len(sections)}</strong><span>Sections</span></div>'
        f'<div class="fact"><strong>{item_count}</strong><span>Items</span></div>'
        f'<div class="fact"><strong>{len(sources)}</strong><span>Sources</span></div>'
        '</div></div></header><div class="layout">'
        '<aside class="rail"><p class="rail-label">Report index</p><nav>'
        f"{''.join(filters)}</nav>"
        '<input class="search" type="search" data-report-search '
        'placeholder="Filter report" aria-label="Filter report items">'
        '<div class="tools"><button class="tool" type="button" data-copy-markdown>'
        'Copy Markdown</button><button class="tool" type="button" data-print-report>'
        'Print / PDF</button></div></aside><main>'
        f"{''.join(rendered_sections)}"
        '<details class="supporting" data-supporting-context><summary>'
        'Report metadata and source receipts</summary><div class="supporting-body">'
        '<dl class="metadata">'
        f'<dt>Profile</dt><dd>{profile_id} · {profile_version}</dd>'
        f'<dt>Generated</dt><dd>{generated_at}</dd>'
        f'<dt>Document</dt><dd><code>sha256:{document_digest}</code></dd>'
        f'<dt>Markdown</dt><dd><code>{_safe_text(markdown_artifact["content_digest"], maximum=80)}</code></dd>'
        '</dl>'
        f"{_render_source_receipts(sources)}"
        '</div></details></main></div></div>'
        '<div class="toast" data-copy-toast role="status" aria-live="polite">'
        'Markdown copied</div>'
        '<script type="application/json" data-report-markdown>'
        f'{_embedded_json(markdown_artifact["content"])}</script>'
        f"<script>{_SCRIPT}</script></body></html>\n"
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
        "document_digest": f"sha256:{document_digest}",
        "companion_markdown_digest": markdown_artifact["content_digest"],
        "single_file": True,
        "zero_build": True,
        "external_dependencies": [],
        "interactive_controls": [
            "section_filter",
            "text_filter",
            "copy_markdown",
            "print_report",
        ],
        "presentation_profile": "editorial_dense_v1",
        "content_policy": {
            "primary_body_fields": [
                "title",
                "status",
                "tags",
                "summary",
                "next_action",
                "source_ref",
            ],
            "supporting_context": "collapsed",
            "process_narration_default_visible": False,
        },
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
