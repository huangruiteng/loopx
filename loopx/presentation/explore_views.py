"""Same-source canonical and executive views over Explore evidence.

The Explore result projection remains the only evidence source.  This module
adds presentation advice and derived display views; it never mutates or
truncates the canonical node, edge, or finding collections.
"""

from __future__ import annotations

import hashlib
import json
import re
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
    "executive_counterevidence_limit": 8,
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


def _mermaid_label(value: str) -> str:
    cleaned = re.sub(r'["\[\]{}<>`|]', "'", str(value or ""))
    return cleaned[:60].strip() or "untitled"


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
) -> dict[str, Any]:
    """Render a complete top-to-bottom evidence atlas for a large graph."""

    node_list = [node for node in nodes if str(node.get("node_id") or "")]
    group_limit = max(4, int(group_node_limit))
    groups = _canonical_group_specs(node_list, group_node_limit=group_limit)
    role = "executive" if view_role == "executive" else "canonical"
    atlas_title = f"{role.title()} evidence timeline"

    node_by_id = {str(node.get("node_id") or ""): node for node in node_list}
    shown_ids = set(node_by_id)
    lines = ["flowchart TB", f'    subgraph {role}_atlas["{atlas_title}"]']
    lines.append("        direction TB")
    group_chains = []
    for group_index, group in enumerate(groups, start=1):
        group_id = f"{role}_group_{group_index}"
        lines.append(f'        subgraph {group_id}["{_mermaid_label(group["title"])}"]')
        lines.append("            direction TB")
        chain = []
        for node_id in group["node_ids"]:
            node = node_by_id[node_id]
            status = str(node.get("status") or "open")
            marker = {
                "blocked": " (BLOCKED)",
                "resolved": " (done)",
                "dead_end": " (dead end)",
            }.get(status, "")
            label = _mermaid_label(f"{node.get('title')}{marker}")
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
        "strategy": "vertical_evidence_timeline",
        "view_role": role,
        "group_count": len(groups),
        "column_count": 1,
        "orientation": "top_to_bottom",
        "max_group_node_count": group_limit,
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
        for key in ("overlap_detected", "text_overflow_detected", "canvas_expansion_detected")
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
        ("incumbent", {"current-best", "incumbent", "leader", "provisional-leader", "winner"}),
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
    executive_edges = [
        dict(edge, source_edge_id=str(edge.get("edge_id") or ""))
        for edge in edges
        if str(edge.get("from_node") or "") in executive_ids
        and str(edge.get("to_node") or "") in executive_ids
    ]
    executive_layout = build_vertical_explore_mermaid(
        executive_nodes,
        executive_edges,
        view_role="executive",
        group_node_limit=int(thresholds["atlas_group_node_limit"]),
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
        "graph_counts": {
            "node_count": len(executive_nodes),
            "edge_count": len(executive_edges),
            "finding_count": len(executive_findings),
            "canonical_node_count": len(canonical_nodes),
        },
        "filter": {
            "projection_mode": "executive_auto",
            "selection": "active_or_tagged_plus_material_neighbors_and_lineage",
            "truncated": False,
            "layout": {
                key: value
                for key, value in executive_layout.items()
                if key != "mermaid"
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
