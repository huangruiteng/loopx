"""First-class Explore board styles and their Lark rendering contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping


BOARD_STYLE_AUTO_FLOW = "auto_flow"
BOARD_STYLE_SEMANTIC_LANE_COLUMNS = "semantic_lane_columns"


@dataclass(frozen=True)
class ExploreBoardStyle:
    name: str
    renderer: str
    source_key: str
    input_format: str
    extension: str


_BOARD_STYLES = {
    BOARD_STYLE_AUTO_FLOW: ExploreBoardStyle(
        name=BOARD_STYLE_AUTO_FLOW,
        renderer="mermaid",
        source_key="mermaid",
        input_format="mermaid",
        extension="mmd",
    ),
    BOARD_STYLE_SEMANTIC_LANE_COLUMNS: ExploreBoardStyle(
        name=BOARD_STYLE_SEMANTIC_LANE_COLUMNS,
        renderer="stage_svg",
        source_key="svg",
        input_format="svg",
        extension="svg",
    ),
}
BOARD_STYLES = frozenset(_BOARD_STYLES)
_RENDERER_BOARD_STYLES = {
    style.renderer: style for style in _BOARD_STYLES.values()
}


def explore_board_style(name: str) -> ExploreBoardStyle:
    style_name = str(name or BOARD_STYLE_AUTO_FLOW).strip()
    if style_name not in _BOARD_STYLES:
        raise ValueError(f"board_style must be one of {sorted(BOARD_STYLES)}")
    return _BOARD_STYLES[style_name]


def resolve_explore_board_style(
    visual_sink: Mapping[str, Any],
) -> ExploreBoardStyle:
    """Resolve new style configs plus legacy renderer-only Mermaid configs."""

    style_name = str(visual_sink.get("board_style") or "").strip()
    renderer = str(visual_sink.get("renderer") or "").strip()
    if style_name:
        style = explore_board_style(style_name)
        if renderer and renderer != style.renderer:
            raise ValueError(
                f"board_style {style.name} requires renderer {style.renderer}"
            )
        return style
    renderer = renderer or "mermaid"
    if renderer not in _RENDERER_BOARD_STYLES:
        raise ValueError(
            "legacy grid/SVG Explore renderers were removed; use "
            "board_style=auto_flow or board_style=semantic_lane_columns"
        )
    return _RENDERER_BOARD_STYLES[renderer]


def summarize_explore_visual_sync(
    *,
    views: Mapping[str, Mapping[str, Any]],
    configured_roles: list[str],
    recommended_roles: list[str],
    execute: bool,
) -> dict[str, Any]:
    """Fail closed when a recommended visual role is not configured."""

    missing_roles = [
        role for role in recommended_roles if role not in configured_roles
    ]
    retryable_roles = [
        role
        for role, view in views.items()
        if isinstance(view, Mapping) and bool(view.get("retryable"))
    ]
    configured_views_ok = all(bool(view.get("ok")) for view in views.values())
    ok = configured_views_ok and not missing_roles
    if missing_roles and (not views or configured_views_ok):
        status = "sink_unsatisfied"
    elif not views:
        status = "not_configured"
    elif not configured_views_ok:
        status = "publish_failed" if execute else "invalid_projection"
    else:
        status = "published" if execute else "would_publish"
    missing_roles_label = ", ".join(missing_roles)
    retryable_roles_label = ", ".join(retryable_roles)
    return {
        "ok": ok,
        "status": status,
        "published": bool(execute and ok),
        "retryable": bool(missing_roles or retryable_roles),
        "required_action": (
            f"configure the {missing_roles_label} visual role"
            f"{'s' if len(missing_roles) != 1 else ''} and retry Explore visual sync"
            if missing_roles
            else f"retry Explore visual sync for the {retryable_roles_label} marker readback"
            if retryable_roles
            else None
        ),
        "configured_roles": configured_roles,
        "missing_recommended_roles": missing_roles,
    }


def board_source_with_delivery_marker(
    source: str,
    marker: str,
    *,
    style: ExploreBoardStyle,
) -> str:
    if style.input_format == "svg":
        marker_text = (
            f'<text x="1" y="1" fill="#ffffff" font-size="1">{marker}</text>'
        )
        closing = source.rfind("</svg>")
        if closing < 0:
            raise ValueError("stage SVG source is missing the closing </svg> tag")
        return source[:closing] + marker_text + source[closing:]
    marker_id = f"loopx_delivery_{hashlib.sha256(marker.encode('utf-8')).hexdigest()[:10]}"
    return "\n".join(
        [
            source.rstrip(),
            f'    {marker_id}["{marker}"]',
            f"    style {marker_id} fill:#ffffff,stroke:#ffffff,color:#ffffff",
        ]
    )
