"""Same-source canonical and executive views over Explore evidence.

The Explore result projection remains the only evidence source.  This module
adds presentation advice and derived display views; it never mutates or
truncates the canonical node, edge, or finding collections.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

EXPLORE_PRESENTATION_BUNDLE_VERSION = "loopx_explore_presentation_bundle_v0"
EXPLORE_PRESENTATION_ASSESSMENT_VERSION = "loopx_explore_presentation_assessment_v0"
EXPLORE_CANONICAL_VIEW_VERSION = "loopx_explore_canonical_view_v0"
EXPLORE_EXECUTIVE_VIEW_VERSION = "loopx_explore_executive_view_v0"

PRESENTATION_MODE_CANONICAL_ONLY = "canonical_only"
PRESENTATION_MODE_DUAL_VIEW = "dual_view"

_ACTIVE_STATUSES = {"open", "exploring", "blocked"}
_TERMINAL_STATUSES = {"resolved", "dead_end"}
_DECISION_TAGS = {
    "active",
    "baseline",
    "capacity",
    "contract",
    "current-best",
    "decision",
    "executive",
    "guardrail",
    "incumbent",
    "resource",
    "risk",
}
_LEGACY_LEADER_TAGS = {"leader", "provisional-leader", "winner"}
_COUNTEREVIDENCE_TAGS = {
    "counterevidence",
    "negative",
    "no-promote",
    "no_promote",
    "refuted",
    "retired",
}
_EXECUTIVE_EXPANSION_EDGE_TYPES = {"answers", "depends_on", "leads_to", "refutes"}
_VOLATILE_VIEW_KEYS = {
    "first_recorded_at",
    "last_updated_at",
    "update_count",
    "generated_at",
    "log_path",
}

DEFAULT_EXPLORE_PRESENTATION_POLICY: dict[str, float | int] = {
    "decision_density_node_floor": 24,
    "decision_density_ceiling": 0.35,
    "terminal_ratio_node_floor": 30,
    "terminal_ratio_floor": 0.60,
    "terminal_neighborhood_floor": 2,
    "decision_depth_floor": 6,
    "readability_node_floor": 60,
    "readability_edge_density_floor": 2.0,
    "readability_label_chars": 96,
    "readability_root_count_floor": 16,
    "readability_root_ratio_floor": 0.30,
    "atlas_group_node_limit": 10,
    "atlas_column_count": 1,
    "executive_counterevidence_limit": 8,
    "executive_hub_edge_degree_floor": 4,
}

_MERMAID_STATUS_CLASS = {
    "open": "open",
    "exploring": "exploring",
    "blocked": "blocked",
    "resolved": "resolved",
    "dead_end": "deadend",
}


def _material_rows(values: Sequence[Any] | None, *, id_key: str) -> list[dict[str, Any]]:
    rows = []
    for value in values or []:
        if not isinstance(value, Mapping):
            continue
        row = {
            key: item
            for key, item in value.items()
            if key not in _VOLATILE_VIEW_KEYS
        }
        if row.get(id_key):
            rows.append(row)
    return sorted(rows, key=lambda item: str(item.get(id_key) or ""))


def explore_source_digest(projection: Mapping[str, Any]) -> str:
    """Return a stable digest for the complete canonical evidence projection."""

    material = {
        "goal_id": projection.get("goal_id"),
        "nodes": _material_rows(projection.get("nodes"), id_key="node_id"),
        "edges": _material_rows(projection.get("edges"), id_key="edge_id"),
        "findings": _material_rows(projection.get("findings"), id_key="finding_id"),
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def explore_source_revision(projection: Mapping[str, Any], *, digest: str | None = None) -> str:
    source_digest = digest or explore_source_digest(projection)
    event_count = max(0, int(projection.get("source_event_count") or 0))
    return f"events-{event_count}-{source_digest[:12]}"


def _parent_map(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    parents = {
        str(node.get("node_id") or ""): str(node.get("parent_id") or "")
        for node in nodes
        if str(node.get("node_id") or "") and str(node.get("parent_id") or "")
    }
    for edge in edges:
        if str(edge.get("edge_type") or "") != "subtopic_of":
            continue
        child = str(edge.get("from_node") or "")
        parent = str(edge.get("to_node") or "")
        if child and parent:
            parents.setdefault(child, parent)
    return parents


def _lineage(node_id: str, parents: Mapping[str, str], node_ids: set[str]) -> list[str]:
    path = [node_id]
    seen = {node_id}
    parent = parents.get(node_id)
    while parent and parent in node_ids and parent not in seen:
        path.append(parent)
        seen.add(parent)
        parent = parents.get(parent)
    path.reverse()
    return path


def _node_depths(node_ids: set[str], parents: Mapping[str, str]) -> dict[str, int]:
    return {
        node_id: max(0, len(_lineage(node_id, parents, node_ids)) - 1)
        for node_id in node_ids
    }


def _mermaid_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value))


def _mermaid_label(value: str, *, limit: int = 60) -> str:
    cleaned = re.sub(r'["\[\]{}<>`|]', "'", str(value or ""))
    return _truncate_display(cleaned, limit=limit) or "untitled"


_METRIC_SIGNAL = re.compile(
    r"(?:"
    r"[+-]\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*/\s*[+-]?\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*(?:bp|bps|%|ms|sec|secs|seconds?|x|×)\b"
    r")",
    flags=re.IGNORECASE,
)

_NODE_STATUS_LABEL = {
    "open": "OPEN",
    "exploring": "ACTIVE",
    "blocked": "BLOCKED",
    "resolved": "DONE",
    "dead_end": "NO-PROMOTE",
}


def _summary_clauses(value: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    if not normalized:
        return []
    return [
        clause.strip(" .;。；")
        for clause in re.split(r"(?<=[!?。！？；;])\s*|(?<=\.)\s+", normalized)
        if clause.strip(" .;。；")
    ]


def _compact_detail_clause(value: str, *, limit: int) -> str:
    """Keep a metric-bearing portion visible when a long clause is compacted."""

    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    metric = _METRIC_SIGNAL.search(normalized)
    if metric and _display_width(normalized) > limit:
        context_width = max(18, limit // 3)
        prefix = normalized[: metric.start()].rstrip()
        metric_and_tail = normalized[metric.start() :]
        if _display_width(prefix) > context_width:
            prefix = "…" + _tail_display(prefix, limit=context_width - 1)
        normalized = f"{prefix} {metric_and_tail}".strip()
    return _truncate_display(normalized, limit=limit)


def _node_decision_lines(
    node: Mapping[str, Any],
    *,
    detail_limit: int,
) -> list[str]:
    """Project one metric-bearing evidence line and one conclusion line."""

    clauses = _summary_clauses(str(node.get("summary") or ""))
    if not clauses:
        return []
    metric_clause = next((clause for clause in clauses if _METRIC_SIGNAL.search(clause)), None)
    selected = []
    if metric_clause:
        selected.append(metric_clause)
    else:
        selected.append(clauses[0])
    if clauses[-1] != selected[0]:
        selected.append(clauses[-1])
    return [
        _compact_detail_clause(clause, limit=detail_limit)
        for clause in selected[:2]
    ]


def _node_display_lines(
    node: Mapping[str, Any],
    *,
    title_limit: int,
    detail_limit: int,
) -> list[str]:
    status = str(node.get("status") or "open")
    title = _truncate_display(
        str(node.get("title") or node.get("node_id") or "untitled"),
        limit=title_limit,
    )
    header = f"{title} · {_NODE_STATUS_LABEL.get(status, status.upper())}"
    return [header, *_node_decision_lines(node, detail_limit=detail_limit)]


def _node_detail_coverage(nodes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary_nodes = [node for node in nodes if str(node.get("summary") or "").strip()]
    rendered = [node for node in summary_nodes if _node_decision_lines(node, detail_limit=112)]
    metric_nodes = [
        node for node in summary_nodes if _METRIC_SIGNAL.search(str(node.get("summary") or ""))
    ]
    rendered_metric_nodes = [
        node
        for node in metric_nodes
        if _METRIC_SIGNAL.search(" ".join(_node_decision_lines(node, detail_limit=112)))
    ]
    complete = len(rendered) == len(summary_nodes) and len(rendered_metric_nodes) == len(metric_nodes)
    return {
        "summary_eligible_node_count": len(summary_nodes),
        "summary_rendered_node_count": len(rendered),
        "metric_eligible_node_count": len(metric_nodes),
        "metric_rendered_node_count": len(rendered_metric_nodes),
        "complete": complete,
    }


def _canonical_group_specs(
    nodes: Sequence[Mapping[str, Any]],
    *,
    group_node_limit: int,
) -> list[dict[str, Any]]:
    """Split stable source order into navigable evidence epochs."""

    node_by_id = {str(node.get("node_id") or ""): node for node in nodes}
    ordered_ids = list(node_by_id)
    specs = []
    for offset in range(0, len(ordered_ids), group_node_limit):
        chunk = ordered_ids[offset : offset + group_node_limit]
        first_title = str(node_by_id[chunk[0]].get("title") or chunk[0])
        specs.append(
            {
                "title": (
                    f"Evidence epoch {offset // group_node_limit + 1:02d} · "
                    f"{first_title}"
                ),
                "node_ids": chunk,
                "order": offset,
            }
        )
    return specs


def build_vertical_explore_mermaid(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    *,
    view_role: str,
    group_node_limit: int = 10,
    column_count: int = 1,
) -> dict[str, Any]:
    """Render a complete evidence atlas for a large graph.

    The single-column default preserves the timeline view. Wider embedded
    whiteboards can opt into multiple columns without changing the canonical
    source projection.
    """

    node_list = [node for node in nodes if str(node.get("node_id") or "")]
    group_limit = max(4, int(group_node_limit))
    groups = _canonical_group_specs(node_list, group_node_limit=group_limit)
    columns = min(max(1, int(column_count)), max(1, len(groups)))
    multi_column = columns > 1
    role = "executive" if view_role == "executive" else "canonical"
    atlas_title = (
        f"{role.title()} evidence atlas"
        if multi_column
        else f"{role.title()} evidence timeline"
    )

    node_by_id = {str(node.get("node_id") or ""): node for node in node_list}
    shown_ids = set(node_by_id)
    detail_coverage = _node_detail_coverage(node_list)
    if not detail_coverage["complete"]:
        raise ValueError("Explore node detail projection lost summary or metric evidence")
    flow_direction = "LR" if multi_column else "TB"
    lines = [
        f"flowchart {flow_direction}",
        f'    subgraph {role}_atlas["{atlas_title}"]',
    ]
    lines.append(f"        direction {flow_direction}")
    group_chains = []
    for group_index, group in enumerate(groups, start=1):
        group_id = f"{role}_group_{group_index}"
        lines.append(f'        subgraph {group_id}["{_mermaid_label(group["title"])}"]')
        lines.append("            direction TB")
        chain = []
        for node_id in group["node_ids"]:
            node = node_by_id[node_id]
            status = str(node.get("status") or "open")
            label = "<br/>".join(
                _mermaid_label(line, limit=112)
                for line in _node_display_lines(
                    node,
                    title_limit=64,
                    detail_limit=112,
                )
            )
            mermaid_id = _mermaid_id(node_id)
            chain.append(mermaid_id)
            lines.append(
                f'            {mermaid_id}["{label}"]:::{_MERMAID_STATUS_CLASS.get(status, "open")}'
            )
        if len(chain) > 1:
            lines.append(f"            {' ~~~ '.join(chain)}")
        lines.append("        end")
        group_chains.append(chain)
    for previous, current in zip(group_chains, group_chains[1:]):
        lines.append(f"        {previous[-1]} ~~~ {current[0]}")
    lines.append("    end")
    for edge in edges:
        source = str(edge.get("from_node") or "")
        target = str(edge.get("to_node") or "")
        if source not in shown_ids or target not in shown_ids:
            continue
        label = _mermaid_label(str(edge.get("edge_type") or ""))
        lines.append(f"    {_mermaid_id(source)} -->|{label}| {_mermaid_id(target)}")
    lines.append(
        f"    style {role}_atlas fill:#ffffff,stroke:#90a4ae,stroke-width:2px"
    )
    for group_index in range(1, len(groups) + 1):
        lines.append(
            f"    style {role}_group_{group_index} fill:#fafafa,stroke:#cfd8dc"
        )
    lines.extend(
        [
            "    classDef open fill:#f5f5f5,stroke:#9e9e9e",
            "    classDef exploring fill:#e3f2fd,stroke:#1e88e5",
            "    classDef blocked fill:#ffebee,stroke:#e53935,stroke-width:2px",
            "    classDef resolved fill:#e8f5e9,stroke:#43a047",
            "    classDef deadend fill:#eeeeee,stroke:#9e9e9e,stroke-dasharray: 4 4",
        ]
    )
    return {
        "mermaid": "\n".join(lines),
        "strategy": (
            "multi_column_evidence_atlas"
            if multi_column
            else "vertical_evidence_timeline"
        ),
        "view_role": role,
        "group_count": len(groups),
        "column_count": columns,
        "orientation": "left_to_right" if multi_column else "top_to_bottom",
        "max_group_node_count": group_limit,
        "node_detail_coverage": detail_coverage,
    }


_ATLAS_PALETTE = (
    ("#F0F4FC", "#5178C6"),
    ("#EAE2FE", "#8569CB"),
    ("#DFF5E5", "#509863"),
    ("#FEF1CE", "#D4B45B"),
)
_ATLAS_STATUS_COLOR = {
    "open": "#9E9E9E",
    "exploring": "#1E88E5",
    "blocked": "#E53935",
    "resolved": "#43A047",
    "dead_end": "#9E9E9E",
}

_BOARD_EDGE_STYLE = {
    "answers": ("#7B61A8", ""),
    "depends_on": ("#D97706", "6 5"),
    "leads_to": ("#3370FF", ""),
    "refutes": ("#D9363E", "6 5"),
    "supports": ("#2E9B65", ""),
}
_BOARD_FRONTIER_TAGS = {
    "active",
    "ci_pending",
    "current-best",
    "current-frontier",
    "incumbent",
    "open-pr",
    "review_wait",
}


def _display_width(value: str) -> int:
    return sum(2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1 for character in value)


def _truncate_display(value: str, *, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if _display_width(cleaned) <= limit:
        return cleaned
    result = []
    width = 0
    for character in cleaned:
        character_width = 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        if width + character_width > max(1, limit - 1):
            break
        result.append(character)
        width += character_width
    truncated = "".join(result).rstrip()
    if (
        truncated
        and len(truncated) < len(cleaned)
        and truncated[-1].isascii()
        and truncated[-1].isalnum()
        and cleaned[len(truncated)].isascii()
        and cleaned[len(truncated)].isalnum()
    ):
        boundary = truncated.rfind(" ")
        if boundary >= max(1, len(truncated) // 2):
            truncated = truncated[:boundary].rstrip()
    return truncated + "…"


def _tail_display(value: str, *, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if _display_width(cleaned) <= limit:
        return cleaned
    result = []
    width = 0
    for character in reversed(cleaned):
        character_width = 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        if width + character_width > limit:
            break
        result.append(character)
        width += character_width
    tail = "".join(reversed(result)).lstrip()
    if tail and tail[0].isascii() and tail[0].isalnum():
        boundary = tail.find(" ")
        if 0 < boundary <= len(tail) // 2:
            tail = tail[boundary + 1 :].lstrip()
    return tail


def build_explore_svg_atlas(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    *,
    view_role: str,
    group_node_limit: int = 10,
    column_count: int = 2,
) -> dict[str, Any]:
    """Render a deterministic owner-facing evidence atlas as standalone SVG.

    Mermaid remains useful for topology exchange, but target layout engines are
    free to ignore subgraph hints. This renderer owns the final geometry so a
    material refresh cannot collapse the evidence epochs into a thin strip.
    """

    node_list = [node for node in nodes if str(node.get("node_id") or "")]
    group_limit = max(4, int(group_node_limit))
    groups = _canonical_group_specs(node_list, group_node_limit=group_limit)
    columns = min(max(1, int(column_count)), max(1, len(groups)))
    row_count = max(1, (len(groups) + columns - 1) // columns)
    role = "executive" if view_role == "executive" else "canonical"

    canvas_width = 1400
    margin = 40
    column_gap = 28
    row_gap = 28
    header_height = 142
    footer_height = 42
    card_width = (canvas_width - 2 * margin - (columns - 1) * column_gap) / columns
    item_columns = 2 if card_width >= 560 else 1
    item_gap = 12
    item_height = 90
    card_padding = 20
    card_header_height = 54
    item_rows = max(1, (group_limit + item_columns - 1) // item_columns)
    card_height = card_header_height + item_rows * item_height + (item_rows - 1) * 10 + 2 * card_padding
    canvas_height = (
        header_height
        + row_count * card_height
        + max(0, row_count - 1) * row_gap
        + footer_height
        + margin
    )
    item_width = (
        card_width - 2 * card_padding - max(0, item_columns - 1) * item_gap
    ) / item_columns

    node_by_id = {str(node.get("node_id") or ""): node for node in node_list}
    visible_ids = set(node_by_id)
    detail_coverage = _node_detail_coverage(node_list)
    if not detail_coverage["complete"]:
        raise ValueError("Explore node detail projection lost summary or metric evidence")
    visible_edge_count = sum(
        1
        for edge in edges
        if str(edge.get("from_node") or "") in visible_ids
        and str(edge.get("to_node") or "") in visible_ids
    )
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height:.0f}" width="{canvas_width}" height="{canvas_height:.0f}">',
        "<defs>",
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">',
        '<feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#1F2329" flood-opacity="0.10"/>',
        "</filter>",
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">',
        '<path d="M0,0 L8,4 L0,8 Z" fill="#BBBFC4"/>',
        "</marker>",
        "</defs>",
        f'<rect width="{canvas_width}" height="{canvas_height:.0f}" rx="18" fill="#FFFFFF"/>',
        '<text x="700" y="42" text-anchor="middle" font-size="28" font-weight="700" fill="#1F2329" font-family="Arial, PingFang SC, sans-serif">'
        f'{role.title()} Explore Evidence Atlas</text>',
        '<text x="700" y="72" text-anchor="middle" font-size="14" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">'
        f'{len(node_list)} decision nodes · {visible_edge_count} material relations · same-source owner projection</text>',
    ]

    if groups:
        pill_width = min(210.0, (canvas_width - 2 * margin - (len(groups) - 1) * 18) / len(groups))
        total_pill_width = len(groups) * pill_width + max(0, len(groups) - 1) * 18
        pill_x = (canvas_width - total_pill_width) / 2
        for group_index, group in enumerate(groups):
            x = pill_x + group_index * (pill_width + 18)
            fill, border = _ATLAS_PALETTE[group_index % len(_ATLAS_PALETTE)]
            if group_index:
                previous_right = x - 18
                svg.append(
                    f'<line x1="{previous_right + 3:.1f}" y1="104" x2="{x - 4:.1f}" y2="104" stroke="#BBBFC4" stroke-width="2" marker-end="url(#arrow)"/>'
                )
            svg.extend(
                [
                    f'<rect x="{x:.1f}" y="87" width="{pill_width:.1f}" height="34" rx="17" fill="{fill}" stroke="{border}" stroke-width="2"/>',
                    f'<text x="{x + pill_width / 2:.1f}" y="109" text-anchor="middle" font-size="14" font-weight="600" fill="#1F2329" font-family="Arial, PingFang SC, sans-serif">Epoch {group_index + 1:02d}</text>',
                ]
            )

    for group_index, group in enumerate(groups):
        row = group_index // columns
        column = group_index % columns
        x = margin + column * (card_width + column_gap)
        y = header_height + row * (card_height + row_gap)
        fill, border = _ATLAS_PALETTE[group_index % len(_ATLAS_PALETTE)]
        first_title = _truncate_display(
            str(node_by_id[group["node_ids"][0]].get("title") or "Evidence"),
            limit=48,
        )
        svg.extend(
            [
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{card_width:.1f}" height="{card_height:.1f}" rx="14" fill="{fill}" stroke="{border}" stroke-width="2" filter="url(#shadow)"/>',
                f'<text x="{x + card_padding:.1f}" y="{y + 30:.1f}" font-size="16" font-weight="700" fill="#1F2329" font-family="Arial, PingFang SC, sans-serif">{html.escape(f"Epoch {group_index + 1:02d} · {first_title}")}</text>',
                f'<text x="{x + card_width - card_padding:.1f}" y="{y + 30:.1f}" text-anchor="end" font-size="13" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">{len(group["node_ids"])} nodes</text>',
            ]
        )
        for item_index, node_id in enumerate(group["node_ids"]):
            node = node_by_id[node_id]
            item_row = item_index // item_columns
            item_column = item_index % item_columns
            item_x = x + card_padding + item_column * (item_width + item_gap)
            item_y = y + card_header_height + card_padding + item_row * (item_height + 10)
            status = str(node.get("status") or "open")
            status_color = _ATLAS_STATUS_COLOR.get(status, "#9E9E9E")
            display_lines = _node_display_lines(
                node,
                title_limit=68,
                detail_limit=76,
            )
            svg.extend(
                [
                    f'<rect x="{item_x:.1f}" y="{item_y:.1f}" width="{item_width:.1f}" height="{item_height}" rx="8" fill="#FFFFFF" stroke="{border}" stroke-width="2"/>',
                    f'<circle cx="{item_x + 15:.1f}" cy="{item_y + 21:.1f}" r="5" fill="{status_color}"/>',
                    f'<text x="{item_x + 28:.1f}" y="{item_y + 25:.1f}" font-size="13" font-weight="600" fill="#1F2329" font-family="Arial, PingFang SC, sans-serif">{html.escape(display_lines[0])}</text>',
                ]
            )
            for detail_index, detail in enumerate(display_lines[1:3], start=1):
                svg.append(
                    f'<text x="{item_x + 28:.1f}" y="{item_y + 25 + detail_index * 23:.1f}" font-size="11" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">{html.escape(detail)}</text>'
                )

    svg.append(
        f'<text x="700" y="{canvas_height - 22:.1f}" text-anchor="middle" font-size="13" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">Complete Nodes / Edges / Findings remain in the linked canonical result board.</text>'
    )
    svg.append("</svg>")
    return {
        "svg": "\n".join(svg),
        "strategy": "fixed_grid_evidence_atlas",
        "view_role": role,
        "group_count": len(groups),
        "column_count": columns,
        "row_count": row_count,
        "item_column_count": item_columns,
        "max_group_node_count": group_limit,
        "rendered_relation_count": max(0, len(groups) - 1),
        "source_edge_count": visible_edge_count,
        "node_detail_coverage": detail_coverage,
        "canvas_width": canvas_width,
        "canvas_height": round(canvas_height),
    }


def _board_lane_id(
    node: Mapping[str, Any],
    *,
    lane_ids: set[str],
) -> str | None:
    node_id = str(node.get("node_id") or "")
    if node_id in lane_ids:
        return node_id
    for ancestor_id in reversed([str(item or "") for item in node.get("lineage") or []]):
        if ancestor_id in lane_ids:
            return ancestor_id
    return None


def _is_board_frontier(node: Mapping[str, Any]) -> bool:
    return str(node.get("status") or "") in {"blocked", "open"} or bool(_tags(node).intersection(_BOARD_FRONTIER_TAGS))


def build_explore_svg_board(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    *,
    view_role: str,
) -> dict[str, Any]:
    """Render a live owner board that preserves Explore semantics.

    The board derives swimlanes from ``lane-*`` tagged nodes, highlights the
    current frontier from status and tags, and draws the actual material
    relations in the selected view. Hierarchy is encoded by lane containment,
    so only ``subtopic_of`` relations are intentionally omitted.
    """

    node_list = [dict(node) for node in nodes if str(node.get("node_id") or "")]
    node_by_id = {str(node.get("node_id") or ""): node for node in node_list}
    visible_ids = set(node_by_id)
    role = "executive" if view_role == "executive" else "canonical"
    detail_coverage = _node_detail_coverage(node_list)
    if not detail_coverage["complete"]:
        raise ValueError("Explore node detail projection lost summary or metric evidence")

    lane_nodes = [
        node
        for node in node_list
        if str(node.get("node_kind") or "") == "area"
        if any(tag.startswith("lane-") for tag in _tags(node))
    ]
    if not lane_nodes:
        root_ids = {str(node.get("node_id") or "") for node in node_list if len(node.get("lineage") or []) <= 1}
        candidate_lane_ids = {
            str(node.get("node_id") or "")
            for node in node_list
            if str(node.get("parent_id") or "") in root_ids and str(node.get("node_kind") or "") == "area"
        }
        lane_nodes = [node for node in node_list if str(node.get("node_id") or "") in candidate_lane_ids]

    synthetic_lane = not lane_nodes
    if synthetic_lane:
        lane_nodes = [
            {
                "node_id": "__explore_work__",
                "title": "Explore work",
                "status": "exploring",
                "tags": ["lane-explore"],
            }
        ]
    lane_ids = {str(node.get("node_id") or "") for node in lane_nodes}
    lane_by_id = {str(node.get("node_id") or ""): node for node in lane_nodes}
    lane_items: dict[str, list[dict[str, Any]]] = {lane_id: [] for lane_id in lane_ids}
    context_nodes: list[dict[str, Any]] = []
    for node in node_list:
        node_id = str(node.get("node_id") or "")
        if node_id in lane_ids:
            continue
        lane_id = "__explore_work__" if synthetic_lane else _board_lane_id(node, lane_ids=lane_ids)
        if lane_id:
            lane_items[lane_id].append(node)
        else:
            context_nodes.append(node)

    ordered_lane_ids = [
        str(node.get("node_id") or "") for node in lane_nodes if lane_items.get(str(node.get("node_id") or ""))
    ]
    if not ordered_lane_ids:
        ordered_lane_ids = [str(lane_nodes[0].get("node_id") or "")]
        lane_items[ordered_lane_ids[0]] = [node for node in node_list if str(node.get("node_id") or "") not in lane_ids]

    canvas_width = 1800
    margin = 42
    header_height = 174
    footer_height = 46
    lane_gap = 28
    lane_columns = min(2, len(ordered_lane_ids))
    lane_rows = (len(ordered_lane_ids) + lane_columns - 1) // lane_columns
    lane_width = (canvas_width - 2 * margin - max(0, lane_columns - 1) * lane_gap) / lane_columns
    card_gap_x = 18
    card_gap_y = 16
    lane_padding = 22
    lane_header_height = 86
    card_columns = 2 if lane_width >= 760 else 1
    card_width = (lane_width - 2 * lane_padding - max(0, card_columns - 1) * card_gap_x) / card_columns
    card_height = 126
    lane_card_rows = {
        lane_id: max(
            1,
            (len(lane_items[lane_id]) + card_columns - 1) // card_columns,
        )
        for lane_id in ordered_lane_ids
    }
    row_heights = []
    for row_index in range(lane_rows):
        ids = ordered_lane_ids[row_index * lane_columns : (row_index + 1) * lane_columns]
        max_card_rows = max(lane_card_rows[lane_id] for lane_id in ids)
        row_heights.append(
            lane_header_height + 2 * lane_padding + max_card_rows * card_height + max(0, max_card_rows - 1) * card_gap_y
        )
    canvas_height = header_height + sum(row_heights) + max(0, lane_rows - 1) * lane_gap + footer_height + margin

    lane_geometry: dict[str, tuple[float, float, float, float]] = {}
    card_geometry: dict[str, tuple[float, float, float, float]] = {}
    row_y = header_height
    for row_index, row_height in enumerate(row_heights):
        ids = ordered_lane_ids[row_index * lane_columns : (row_index + 1) * lane_columns]
        for column_index, lane_id in enumerate(ids):
            lane_x = margin + column_index * (lane_width + lane_gap)
            lane_geometry[lane_id] = (lane_x, row_y, lane_width, row_height)
            for item_index, node in enumerate(lane_items[lane_id]):
                item_row = item_index // card_columns
                item_column = item_index % card_columns
                x = lane_x + lane_padding + item_column * (card_width + card_gap_x)
                y = row_y + lane_header_height + lane_padding + item_row * (card_height + card_gap_y)
                card_geometry[str(node.get("node_id") or "")] = (
                    x,
                    y,
                    card_width,
                    card_height,
                )
        row_y += row_height + lane_gap

    material_edges = [
        dict(edge)
        for edge in edges
        if str(edge.get("from_node") or "") in card_geometry
        and str(edge.get("to_node") or "") in card_geometry
        and str(edge.get("edge_type") or "") != "subtopic_of"
    ]
    source_edge_count = sum(
        1
        for edge in edges
        if str(edge.get("from_node") or "") in visible_ids
        and str(edge.get("to_node") or "") in visible_ids
    )
    cross_lane_count = 0
    for edge in material_edges:
        source_lane = _board_lane_id(node_by_id[str(edge["from_node"])], lane_ids=lane_ids)
        target_lane = _board_lane_id(node_by_id[str(edge["to_node"])], lane_ids=lane_ids)
        if source_lane != target_lane:
            cross_lane_count += 1
    frontier_count = sum(1 for lane_id in ordered_lane_ids for node in lane_items[lane_id] if _is_board_frontier(node))
    root_summary = _truncate_display(
        str(context_nodes[0].get("summary") or "") if context_nodes else "",
        limit=150,
    )

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height:.0f}" width="{canvas_width}" height="{canvas_height:.0f}">',
        "<defs>",
        '<filter id="board-shadow" x="-10%" y="-10%" width="120%" height="130%">',
        '<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#1F2329" flood-opacity="0.10"/>',
        "</filter>",
    ]
    for edge_type, (color, _) in _BOARD_EDGE_STYLE.items():
        svg.extend(
            [
                f'<marker id="arrow-{edge_type}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">',
                f'<path d="M0,0 L9,4.5 L0,9 Z" fill="{color}"/>',
                "</marker>",
            ]
        )
    svg.extend(
        [
            "</defs>",
            f'<rect width="{canvas_width}" height="{canvas_height:.0f}" rx="18" fill="#F7F8FA"/>',
            '<text x="42" y="47" font-size="30" font-weight="700" fill="#1F2329" font-family="Arial, PingFang SC, sans-serif">Live Explore Decision Board</text>',
            f'<text x="42" y="80" font-size="15" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">{html.escape(root_summary or "Canonical state → real work lanes → current frontier → material causal relations")}</text>',
            f'<rect x="42" y="121" width="142" height="34" rx="17" fill="#E8F3FF"/><text x="113" y="143" text-anchor="middle" font-size="14" font-weight="600" fill="#1456B8" font-family="Arial, PingFang SC, sans-serif">{len(card_geometry)} work nodes</text>',
            f'<rect x="196" y="121" width="154" height="34" rx="17" fill="#EAF8F1"/><text x="273" y="143" text-anchor="middle" font-size="14" font-weight="600" fill="#207A50" font-family="Arial, PingFang SC, sans-serif">{len(material_edges)} real relations</text>',
            f'<rect x="362" y="121" width="148" height="34" rx="17" fill="#FFF3E5"/><text x="436" y="143" text-anchor="middle" font-size="14" font-weight="600" fill="#AD5700" font-family="Arial, PingFang SC, sans-serif">{frontier_count} at frontier</text>',
            f'<text x="1758" y="142" text-anchor="end" font-size="13" fill="#8F959E" font-family="Arial, PingFang SC, sans-serif">{role} · {len(context_nodes)} context nodes encoded in lineage</text>',
        ]
    )

    lane_palette = (
        ("#EDF4FF", "#4C7DCC"),
        ("#ECF9F0", "#4A9B68"),
        ("#F5F0FF", "#8065C4"),
        ("#FFF7E6", "#C58B2B"),
    )
    for lane_index, lane_id in enumerate(ordered_lane_ids):
        x, y, width, height = lane_geometry[lane_id]
        fill, border = lane_palette[lane_index % len(lane_palette)]
        lane = lane_by_id[lane_id]
        lane_title = _truncate_display(str(lane.get("title") or lane_id), limit=60)
        lane_summary = _truncate_display(str(lane.get("summary") or ""), limit=82)
        lane_frontier = sum(1 for node in lane_items[lane_id] if _is_board_frontier(node))
        svg.extend(
            [
                f'<g data-lane-id="{html.escape(lane_id)}">',
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="16" fill="{fill}" stroke="{border}" stroke-width="2"/>',
                f'<text x="{x + lane_padding:.1f}" y="{y + 38:.1f}" font-size="19" font-weight="700" fill="#1F2329" font-family="Arial, PingFang SC, sans-serif">{html.escape(lane_title)}</text>',
                f'<text x="{x + width - lane_padding:.1f}" y="{y + 38:.1f}" text-anchor="end" font-size="13" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">{len(lane_items[lane_id])} nodes · {lane_frontier} frontier</text>',
                f'<text x="{x + lane_padding:.1f}" y="{y + 65:.1f}" font-size="12" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">{html.escape(lane_summary)}</text>',
                "</g>",
            ]
        )

    for edge in material_edges:
        source_id = str(edge.get("from_node") or "")
        target_id = str(edge.get("to_node") or "")
        edge_id = str(edge.get("edge_id") or f"{source_id}-{target_id}")
        edge_type = str(edge.get("edge_type") or "leads_to")
        color, dash = _BOARD_EDGE_STYLE.get(edge_type, ("#8F959E", "4 4"))
        source_x, source_y, source_w, source_h = card_geometry[source_id]
        target_x, target_y, target_w, target_h = card_geometry[target_id]
        start_x = source_x + source_w
        start_y = source_y + source_h / 2
        end_x = target_x
        end_y = target_y + target_h / 2
        if end_x <= start_x:
            start_x = source_x + source_w / 2
            start_y = source_y + source_h
            end_x = target_x + target_w / 2
            end_y = target_y
        bend = max(42.0, abs(end_x - start_x) * 0.45)
        path = (
            f"M {start_x:.1f} {start_y:.1f} "
            f"C {start_x + bend:.1f} {start_y:.1f}, "
            f"{end_x - bend:.1f} {end_y:.1f}, {end_x:.1f} {end_y:.1f}"
        )
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(
            f'<path data-edge-id="{html.escape(edge_id)}" data-edge-type="{html.escape(edge_type)}" d="{path}" fill="none" stroke="{color}" stroke-width="2.2" opacity="0.78"{dash_attr} marker-end="url(#arrow-{edge_type if edge_type in _BOARD_EDGE_STYLE else "leads_to"})"/>'
        )
        source_lane = _board_lane_id(node_by_id[source_id], lane_ids=lane_ids)
        target_lane = _board_lane_id(node_by_id[target_id], lane_ids=lane_ids)
        if source_lane != target_lane or edge_type in {"depends_on", "refutes"}:
            label_x = (start_x + end_x) / 2
            label_y = (start_y + end_y) / 2 - 8
            label_width = max(58, 12 + len(edge_type) * 7)
            svg.extend(
                [
                    f'<rect x="{label_x - label_width / 2:.1f}" y="{label_y - 14:.1f}" width="{label_width}" height="22" rx="11" fill="#FFFFFF" stroke="{color}" stroke-width="1" opacity="0.94"/>',
                    f'<text x="{label_x:.1f}" y="{label_y + 1:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="{color}" font-family="Arial, PingFang SC, sans-serif">{html.escape(edge_type)}</text>',
                ]
            )

    for lane_id in ordered_lane_ids:
        _, border = lane_palette[ordered_lane_ids.index(lane_id) % len(lane_palette)]
        for node in lane_items[lane_id]:
            node_id = str(node.get("node_id") or "")
            x, y, width, height = card_geometry[node_id]
            status = str(node.get("status") or "open")
            status_color = _ATLAS_STATUS_COLOR.get(status, "#9E9E9E")
            frontier = _is_board_frontier(node)
            display_lines = _node_display_lines(
                node,
                title_limit=48,
                detail_limit=56,
            )
            node_kind = _truncate_display(str(node.get("node_kind") or "work"), limit=18)
            card_stroke = "#FF8F1F" if frontier else border
            card_stroke_width = 3 if frontier else 1.6
            svg.extend(
                [
                    f'<g data-node-id="{html.escape(node_id)}" data-status="{html.escape(status)}" data-frontier="{str(frontier).lower()}">',
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="11" fill="#FFFFFF" stroke="{card_stroke}" stroke-width="{card_stroke_width}" filter="url(#board-shadow)"/>',
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="8" height="{height:.1f}" rx="4" fill="{status_color}"/>',
                ]
            )
            for line_index, line in enumerate(display_lines[:3]):
                svg.append(
                    f'<text x="{x + 24:.1f}" y="{y + 30 + line_index * 24:.1f}" font-size="{14 if line_index == 0 else 11}" font-weight="{600 if line_index == 0 else 400}" fill="{"#1F2329" if line_index == 0 else "#646A73"}" font-family="Arial, PingFang SC, sans-serif">{html.escape(line)}</text>'
                )
            svg.extend(
                [
                    f'<text x="{x + 24:.1f}" y="{y + height - 13:.1f}" font-size="11" fill="#8F959E" font-family="Arial, PingFang SC, sans-serif">{html.escape(node_kind)} · {html.escape(status)}</text>',
                    (
                        f'<text x="{x + width - 16:.1f}" y="{y + height - 13:.1f}" text-anchor="end" font-size="11" font-weight="700" fill="#AD5700" font-family="Arial, PingFang SC, sans-serif">FRONTIER</text>'
                        if frontier
                        else ""
                    ),
                    "</g>",
                ]
            )

    svg.extend(
        [
            f'<text x="42" y="{canvas_height - 20:.1f}" font-size="12" fill="#646A73" font-family="Arial, PingFang SC, sans-serif">Solid: supports / leads_to / answers · dashed: depends_on / refutes · lane containment encodes subtopic lineage</text>',
            f'<text x="1758" y="{canvas_height - 20:.1f}" text-anchor="end" font-size="12" fill="#8F959E" font-family="Arial, PingFang SC, sans-serif">Full Nodes / Edges / Findings remain in the canonical Base</text>',
            "</svg>",
        ]
    )
    return {
        "svg": "\n".join(item for item in svg if item),
        "strategy": "semantic_lane_decision_board",
        "view_role": role,
        "lane_count": len(ordered_lane_ids),
        "lane_ids": ordered_lane_ids,
        "rendered_node_count": len(card_geometry),
        "context_node_count": len(context_nodes) + len(lane_ids),
        "frontier_node_count": frontier_count,
        "rendered_relation_count": len(material_edges),
        "cross_lane_relation_count": cross_lane_count,
        "suppressed_relation_count": source_edge_count - len(material_edges),
        "source_edge_count": source_edge_count,
        "semantic_contract": {
            "real_relations_only": True,
            "frontier_explicit": True,
            "lane_membership_from_lineage": True,
            "chronological_buckets": False,
        },
        "node_detail_coverage": detail_coverage,
        "canvas_width": canvas_width,
        "canvas_height": round(canvas_height),
    }


def _tags(node: Mapping[str, Any]) -> set[str]:
    return {str(tag or "").strip().lower() for tag in node.get("tags") or [] if str(tag or "").strip()}


def _decision_seed_ids(nodes: Sequence[Mapping[str, Any]]) -> set[str]:
    seeds = set()
    has_current_incumbent = any(
        _tags(node).intersection({"current-best", "incumbent"})
        for node in nodes
    )
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        if not node_id:
            continue
        tags = _tags(node)
        if (
            str(node.get("status") or "") in _ACTIVE_STATUSES
            or tags.intersection(_DECISION_TAGS)
            or (not has_current_incumbent and tags.intersection(_LEGACY_LEADER_TAGS))
        ):
            seeds.add(node_id)
    return seeds


def _terminal_neighborhood_count(
    nodes: Sequence[Mapping[str, Any]],
    parents: Mapping[str, str],
) -> int:
    statuses = {
        str(node.get("node_id") or ""): str(node.get("status") or "")
        for node in nodes
    }
    children: dict[str, list[str]] = defaultdict(list)
    for child, parent in parents.items():
        children[parent].append(child)
    return sum(
        1
        for child_ids in children.values()
        if len(child_ids) >= 3
        and sum(statuses.get(child) in _TERMINAL_STATUSES for child in child_ids) >= 3
    )


def assess_explore_presentation(
    projection: Mapping[str, Any],
    *,
    readability_check: Mapping[str, Any] | None = None,
    policy: Mapping[str, float | int] | None = None,
) -> dict[str, Any]:
    """Recommend one or two views from several advisory readability signals."""

    thresholds = dict(DEFAULT_EXPLORE_PRESENTATION_POLICY)
    thresholds.update(policy or {})
    nodes = [item for item in projection.get("nodes") or [] if isinstance(item, Mapping)]
    edges = [item for item in projection.get("edges") or [] if isinstance(item, Mapping)]
    node_ids = {str(node.get("node_id") or "") for node in nodes if str(node.get("node_id") or "")}
    parents = _parent_map(nodes, edges)
    depths = _node_depths(node_ids, parents)
    decision_ids = _decision_seed_ids(nodes)
    terminal_count = sum(str(node.get("status") or "") in _TERMINAL_STATUSES for node in nodes)
    node_count = len(nodes)
    edge_count = len(edges)
    decision_density = len(decision_ids) / node_count if node_count else 1.0
    terminal_ratio = terminal_count / node_count if node_count else 0.0
    edge_density = edge_count / node_count if node_count else 0.0
    max_depth = max(depths.values(), default=0)
    root_count = sum(not parents.get(node_id) for node_id in node_ids)
    root_ratio = root_count / node_count if node_count else 0.0
    terminal_neighborhoods = _terminal_neighborhood_count(nodes, parents)
    long_label_count = sum(
        len(str(node.get("title") or "")) > int(thresholds["readability_label_chars"])
        for node in nodes
    )

    reasons = []
    if (
        node_count >= int(thresholds["decision_density_node_floor"])
        and decision_density < float(thresholds["decision_density_ceiling"])
    ):
        reasons.append("low_decision_density")
    if (
        terminal_neighborhoods >= int(thresholds["terminal_neighborhood_floor"])
        or (
            node_count >= int(thresholds["terminal_ratio_node_floor"])
            and terminal_ratio >= float(thresholds["terminal_ratio_floor"])
        )
    ):
        reasons.append("excessive_terminal_branches")
    if max_depth >= int(thresholds["decision_depth_floor"]):
        reasons.append("deep_decision_path")

    observed_readability_failure = any(
        readability_check and readability_check.get(key) is True
        for key in (
            "overlap_detected",
            "text_overflow_detected",
            "canvas_expansion_detected",
        )
    )
    estimated_readability_failure = (
        node_count >= int(thresholds["readability_node_floor"])
        and (
            edge_density >= float(thresholds["readability_edge_density_floor"])
            or long_label_count > 0
            or max_depth >= int(thresholds["decision_depth_floor"])
            or (
                root_count >= int(thresholds["readability_root_count_floor"])
                and root_ratio >= float(thresholds["readability_root_ratio_floor"])
            )
        )
    )
    if observed_readability_failure or estimated_readability_failure:
        reasons.append("readability_check_failed")

    mode = (
        PRESENTATION_MODE_DUAL_VIEW
        if "readability_check_failed" in reasons or len(reasons) >= 2
        else PRESENTATION_MODE_CANONICAL_ONLY
    )
    return {
        "schema_version": EXPLORE_PRESENTATION_ASSESSMENT_VERSION,
        "presentation_mode": mode,
        "reason_codes": reasons,
        "metrics": {
            "node_count": node_count,
            "edge_count": edge_count,
            "decision_node_count": len(decision_ids),
            "decision_density": round(decision_density, 4),
            "terminal_node_count": terminal_count,
            "terminal_ratio": round(terminal_ratio, 4),
            "terminal_neighborhood_count": terminal_neighborhoods,
            "max_depth": max_depth,
            "root_node_count": root_count,
            "root_ratio": round(root_ratio, 4),
            "edge_density": round(edge_density, 4),
            "long_label_count": long_label_count,
        },
        "readability_check": {
            "source": "observed" if readability_check else "static_estimate",
            "failed": observed_readability_failure or estimated_readability_failure,
        },
        "policy": thresholds,
        "advisory_only": True,
        "canonical_truncation_allowed": False,
    }


def _executive_roles(node: Mapping[str, Any]) -> list[str]:
    roles = []
    status = str(node.get("status") or "")
    tags = _tags(node)
    if status in _ACTIVE_STATUSES:
        roles.append("active_work")
    for role, role_tags in (
        ("decision_contract", {"contract", "decision"}),
        ("baseline", {"baseline"}),
        (
            "incumbent",
            {"current-best", "incumbent", "leader", "provisional-leader", "winner"},
        ),
        ("guardrail", {"guardrail", "risk"}),
        ("resource_state", {"capacity", "resource"}),
        ("counterevidence", {"counterevidence", "negative", "no-promote", "retired"}),
    ):
        if tags.intersection(role_tags):
            roles.append(role)
    if status == "dead_end" and "counterevidence" not in roles:
        roles.append("counterevidence")
    return roles or ["lineage_context"]


def _executive_node_ids(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    parents: Mapping[str, str],
    *,
    counterevidence_limit: int,
) -> set[str]:
    node_ids = {str(node.get("node_id") or "") for node in nodes if str(node.get("node_id") or "")}
    selected = _decision_seed_ids(nodes)
    if not selected:
        selected = {node_id for node_id in node_ids if not parents.get(node_id)}
    counterevidence_by_parent: dict[str, str] = {}
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        status = str(node.get("status") or "")
        if not node_id or not (
            status == "dead_end" or _tags(node).intersection(_COUNTEREVIDENCE_TAGS)
        ):
            continue
        neighborhood = parents.get(node_id) or node_id
        counterevidence_by_parent.setdefault(neighborhood, node_id)
    selected.update(
        list(counterevidence_by_parent.values())[: max(0, counterevidence_limit)]
    )
    relation_seeds = set(selected)
    for edge in edges:
        if str(edge.get("edge_type") or "") not in _EXECUTIVE_EXPANSION_EDGE_TYPES:
            continue
        source = str(edge.get("from_node") or "")
        target = str(edge.get("to_node") or "")
        if source in relation_seeds or target in relation_seeds:
            selected.update({source, target}.intersection(node_ids))
    for node_id in tuple(selected):
        selected.update(_lineage(node_id, parents, node_ids))
    return selected


def _view_node(
    node: Mapping[str, Any],
    *,
    parents: Mapping[str, str],
    node_ids: set[str],
    executive: bool,
) -> dict[str, Any]:
    view = dict(node)
    node_id = str(node.get("node_id") or "")
    view["source_node_id"] = node_id
    view["lineage"] = _lineage(node_id, parents, node_ids)
    if executive:
        view["executive_roles"] = _executive_roles(node)
    return view


def _executive_edge_projection(
    edges: Sequence[Mapping[str, Any]],
    executive_ids: set[str],
    *,
    hub_degree_floor: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hide lineage and dense hub scaffolding that the executive layout already conveys."""

    candidates = [
        edge
        for edge in edges
        if str(edge.get("from_node") or "") in executive_ids
        and str(edge.get("to_node") or "") in executive_ids
    ]
    outgoing_counts: dict[str, int] = defaultdict(int)
    for edge in candidates:
        outgoing_counts[str(edge.get("from_node") or "")] += 1

    visible = []
    suppressed = []
    degree_floor = max(2, int(hub_degree_floor))
    for edge in candidates:
        edge_type = str(edge.get("edge_type") or "")
        source = str(edge.get("from_node") or "")
        suppression_reason = None
        if edge_type == "subtopic_of":
            suppression_reason = "lineage_encoded_on_node"
        elif edge_type == "supports" and outgoing_counts[source] >= degree_floor:
            suppression_reason = "dense_hub_scaffolding"
        projected = dict(edge, source_edge_id=str(edge.get("edge_id") or ""))
        if suppression_reason:
            suppressed.append(dict(projected, suppression_reason=suppression_reason))
        else:
            visible.append(projected)
    return visible, suppressed


def build_explore_presentation_bundle(
    projection: Mapping[str, Any],
    *,
    readability_check: Mapping[str, Any] | None = None,
    policy: Mapping[str, float | int] | None = None,
) -> dict[str, Any]:
    """Build canonical and executive views atomically from one projection."""

    nodes = [dict(item) for item in projection.get("nodes") or [] if isinstance(item, Mapping)]
    edges = [dict(item) for item in projection.get("edges") or [] if isinstance(item, Mapping)]
    findings = [dict(item) for item in projection.get("findings") or [] if isinstance(item, Mapping)]
    counts = projection.get("counts")
    declared_finding_count = (
        int(counts.get("finding_count") or 0)
        if isinstance(counts, Mapping)
        else len(findings)
    )
    if declared_finding_count > len(findings):
        raise ValueError(
            "Explore presentation requires the complete canonical finding set"
        )
    node_ids = {str(node.get("node_id") or "") for node in nodes if str(node.get("node_id") or "")}
    parents = _parent_map(nodes, edges)
    digest = explore_source_digest(projection)
    revision = explore_source_revision(projection, digest=digest)
    assessment = assess_explore_presentation(
        projection,
        readability_check=readability_check,
        policy=policy,
    )

    canonical_nodes = [
        _view_node(node, parents=parents, node_ids=node_ids, executive=False)
        for node in nodes
    ]
    canonical_edges = [dict(edge, source_edge_id=str(edge.get("edge_id") or "")) for edge in edges]
    thresholds = dict(DEFAULT_EXPLORE_PRESENTATION_POLICY)
    thresholds.update(policy or {})
    canonical_layout = build_vertical_explore_mermaid(
        canonical_nodes,
        canonical_edges,
        view_role="canonical",
        group_node_limit=int(thresholds["atlas_group_node_limit"]),
        column_count=int(thresholds["atlas_column_count"]),
    )
    canonical_svg_layout = build_explore_svg_atlas(
        canonical_nodes,
        canonical_edges,
        view_role="canonical",
        group_node_limit=int(thresholds["atlas_group_node_limit"]),
        column_count=int(thresholds["atlas_column_count"]),
    )
    canonical_board_layout = build_explore_svg_board(
        canonical_nodes,
        canonical_edges,
        view_role="canonical",
    )
    canonical = {
        "schema_version": EXPLORE_CANONICAL_VIEW_VERSION,
        "goal_id": projection.get("goal_id"),
        "view_role": "canonical",
        "source_revision": revision,
        "source_digest": digest,
        "nodes": canonical_nodes,
        "edges": canonical_edges,
        "findings": findings,
        "mermaid": canonical_layout["mermaid"],
        "svg": canonical_svg_layout["svg"],
        "svg_board": canonical_board_layout["svg"],
        "graph_counts": {
            "node_count": len(canonical_nodes),
            "edge_count": len(canonical_edges),
            "finding_count": len(findings),
        },
        "filter": {
            "projection_mode": "canonical_full",
            "truncated": False,
            "layout": {
                key: value
                for key, value in canonical_layout.items()
                if key != "mermaid"
            },
            "renderer_layouts": {
                "svg_atlas": {
                    key: value
                    for key, value in canonical_svg_layout.items()
                    if key != "svg"
                },
                "svg_board": {
                    key: value
                    for key, value in canonical_board_layout.items()
                    if key != "svg"
                },
            },
        },
    }

    executive_ids = _executive_node_ids(
        nodes,
        edges,
        parents,
        counterevidence_limit=int(thresholds["executive_counterevidence_limit"]),
    )
    executive_nodes = [
        _view_node(node, parents=parents, node_ids=node_ids, executive=True)
        for node in nodes
        if str(node.get("node_id") or "") in executive_ids
    ]
    executive_edges, suppressed_executive_edges = _executive_edge_projection(
        edges,
        executive_ids,
        hub_degree_floor=int(thresholds["executive_hub_edge_degree_floor"]),
    )
    executive_layout = build_vertical_explore_mermaid(
        executive_nodes,
        executive_edges,
        view_role="executive",
        group_node_limit=int(thresholds["atlas_group_node_limit"]),
        column_count=int(thresholds["atlas_column_count"]),
    )
    executive_svg_layout = build_explore_svg_atlas(
        executive_nodes,
        executive_edges,
        view_role="executive",
        group_node_limit=int(thresholds["atlas_group_node_limit"]),
        column_count=int(thresholds["atlas_column_count"]),
    )
    executive_board_layout = build_explore_svg_board(
        executive_nodes,
        executive_edges,
        view_role="executive",
    )
    executive_findings = [
        finding
        for finding in findings
        if str(finding.get("node_id") or "") in executive_ids
    ]
    executive = {
        "schema_version": EXPLORE_EXECUTIVE_VIEW_VERSION,
        "goal_id": projection.get("goal_id"),
        "view_role": "executive",
        "source_revision": revision,
        "source_digest": digest,
        "source_node_ids": sorted(executive_ids),
        "nodes": executive_nodes,
        "edges": executive_edges,
        "findings": executive_findings,
        "mermaid": executive_layout["mermaid"],
        "svg": executive_svg_layout["svg"],
        "svg_board": executive_board_layout["svg"],
        "graph_counts": {
            "node_count": len(executive_nodes),
            "edge_count": len(executive_edges),
            "canonical_edge_count": len(canonical_edges),
            "suppressed_edge_count": len(suppressed_executive_edges),
            "finding_count": len(executive_findings),
            "canonical_node_count": len(canonical_nodes),
        },
        "filter": {
            "projection_mode": "executive_auto",
            "selection": "active_or_tagged_plus_material_neighbors_and_lineage",
            "truncated": False,
            "edge_projection": {
                "selection": "material_edges_without_lineage_or_dense_hub_scaffolding",
                "suppressed_source_edge_ids": [
                    str(edge.get("source_edge_id") or "")
                    for edge in suppressed_executive_edges
                ],
                "suppression_counts": {
                    reason: sum(
                        1
                        for edge in suppressed_executive_edges
                        if edge.get("suppression_reason") == reason
                    )
                    for reason in (
                        "lineage_encoded_on_node",
                        "dense_hub_scaffolding",
                    )
                },
            },
            "layout": {
                key: value
                for key, value in executive_layout.items()
                if key != "mermaid"
            },
            "renderer_layouts": {
                "svg_atlas": {
                    key: value
                    for key, value in executive_svg_layout.items()
                    if key != "svg"
                },
                "svg_board": {
                    key: value
                    for key, value in executive_board_layout.items()
                    if key != "svg"
                },
            },
        },
    }
    return {
        "ok": True,
        "schema_version": EXPLORE_PRESENTATION_BUNDLE_VERSION,
        "goal_id": projection.get("goal_id"),
        "presentation_mode": assessment["presentation_mode"],
        "reason_codes": assessment["reason_codes"],
        "source_revision": revision,
        "source_digest": digest,
        "assessment": assessment,
        "canonical": canonical,
        "executive": executive,
    }


def validate_explore_view_freshness(
    projection: Mapping[str, Any],
    view: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed when a derived display view is not from this projection."""

    digest = explore_source_digest(projection)
    revision = explore_source_revision(projection, digest=digest)
    observed_digest = str(view.get("source_digest") or "")
    observed_revision = str(view.get("source_revision") or "")
    fresh = observed_digest == digest and observed_revision == revision
    return {
        "ok": fresh,
        "fresh": fresh,
        "expected_source_digest": digest,
        "observed_source_digest": observed_digest or None,
        "expected_source_revision": revision,
        "observed_source_revision": observed_revision or None,
        "reason": None if fresh else "derived Explore view is stale; rebuild it from the current canonical projection",
    }
