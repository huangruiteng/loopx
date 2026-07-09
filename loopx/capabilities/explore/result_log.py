"""Append-only exploration topology events: nodes, edges, and findings.

Long-running exploration loops (Codex, Claude Code, or another runtime driven
through LoopX) record compact, public-safe result facts here as a topology:
exploration nodes (questions, areas, hypotheses, experiments, artifacts) with
explicit status including where the loop is blocked and why, typed edges
between nodes, and findings attached to nodes. The log is the bounded LoopX
projection source for operator display sinks such as the Lark exploration
result board; sinks render the projection built by
:func:`build_explore_result_projection` and never read raw transcripts,
session files, or private planning documents.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPLORE_RESULT_EVENT_SCHEMA_VERSION = "loopx_explore_result_event_v0"
EXPLORE_RESULT_PROJECTION_VERSION = "loopx_explore_result_projection_v0"
DEFAULT_EXPLORE_RESULT_LOG_NAME = "explore-result-log.jsonl"

EVENT_KIND_NODE = "node"
EVENT_KIND_EDGE = "edge"
EVENT_KIND_FINDING = "finding"
EXPLORE_EVENT_KINDS = {EVENT_KIND_NODE, EVENT_KIND_EDGE, EVENT_KIND_FINDING}

NODE_KIND_QUESTION = "question"
NODE_KIND_AREA = "area"
NODE_KIND_HYPOTHESIS = "hypothesis"
NODE_KIND_EXPERIMENT = "experiment"
NODE_KIND_ARTIFACT = "artifact"
NODE_KINDS = {
    NODE_KIND_QUESTION,
    NODE_KIND_AREA,
    NODE_KIND_HYPOTHESIS,
    NODE_KIND_EXPERIMENT,
    NODE_KIND_ARTIFACT,
}

NODE_STATUS_OPEN = "open"
NODE_STATUS_EXPLORING = "exploring"
NODE_STATUS_BLOCKED = "blocked"
NODE_STATUS_RESOLVED = "resolved"
NODE_STATUS_DEAD_END = "dead_end"
NODE_STATUSES = {
    NODE_STATUS_OPEN,
    NODE_STATUS_EXPLORING,
    NODE_STATUS_BLOCKED,
    NODE_STATUS_RESOLVED,
    NODE_STATUS_DEAD_END,
}

EDGE_TYPE_SUBTOPIC_OF = "subtopic_of"
EDGE_TYPES = {
    EDGE_TYPE_SUBTOPIC_OF,
    "depends_on",
    "answers",
    "supports",
    "refutes",
    "leads_to",
}

FINDING_STATUS_TENTATIVE = "tentative"
FINDING_STATUS_CONFIRMED = "confirmed"
FINDING_STATUS_REFUTED = "refuted"
FINDING_STATUSES = {
    FINDING_STATUS_TENTATIVE,
    FINDING_STATUS_CONFIRMED,
    FINDING_STATUS_REFUTED,
}

TITLE_LIMIT = 200
SUMMARY_LIMIT = 1200
REF_LIMIT = 240
MAX_EVIDENCE_REFS = 16
MAX_TAGS = 8
DEFAULT_FINDING_LIMIT = 200
DEFAULT_MERMAID_NODE_LIMIT = 60
DEFAULT_TREE_DEPTH_LIMIT = 6

RESULT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,95}$")
_WINDOWS_ABS_PATH = re.compile(r"(?<![A-Za-z0-9_.-])[A-Za-z]:[\\/](?![\\/])")

FORBIDDEN_TEXT_MARKERS = (
    "/" + "Users/",
    "/" + "root/",
    "/" + "home/",
    "/" + "private/",
    "\\" + "Users\\",
    "\\" + "root\\",
    "\\" + "home\\",
    "\\" + "private\\",
    ".local/" + "private",
    ".local\\" + "private",
    "Auth" + "orization:",
    "api" + "_key",
    "api" + "key",
    "pass" + "word",
    "sec" + "ret=",
    "tok" + "en=",
)

PUBLIC_BOUNDARY = {
    "raw_task_text_recorded": False,
    "raw_logs_recorded": False,
    "raw_trajectory_recorded": False,
    "raw_session_transcript_recorded": False,
    "credential_values_recorded": False,
    "absolute_paths_recorded": False,
}


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _compact_text(value: Any, *, limit: int, field: str) -> str:
    text = " ".join(str(value or "").split())
    lowered = text.lower()
    if "file://" in lowered or _WINDOWS_ABS_PATH.search(text):
        raise ValueError(f"{field} contains private or credential-like material")
    for marker in FORBIDDEN_TEXT_MARKERS:
        if marker.lower() in lowered:
            raise ValueError(f"{field} contains private or credential-like material")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _safe_public_ref(value: Any, *, field: str) -> str:
    text = _compact_text(value, limit=REF_LIMIT, field=field)
    if not text:
        raise ValueError(f"{field} is empty")
    path = Path(text)
    if (
        text.startswith(("~", "/", "\\"))
        or text.lower().startswith("file://")
        or _WINDOWS_ABS_PATH.match(text)
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise ValueError(f"{field} must be a public relative ref or opaque id, not a local path")
    return text


def _safe_public_refs(values: Sequence[Any] | None, *, field: str, max_items: int) -> list[str]:
    refs: list[str] = []
    for index, value in enumerate(values or []):
        refs.append(_safe_public_ref(value, field=f"{field}[{index}]"))
    return refs[:max_items]


def _safe_result_id(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not RESULT_ID_PATTERN.match(text):
        raise ValueError(f"{field} must match {RESULT_ID_PATTERN.pattern}")
    return text


def _safe_goal_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("goal_id is required")
    if text != Path(text).name or text in {".", ".."}:
        raise ValueError("goal_id must be a single path segment")
    return text


def _safe_confidence(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return round(number, 3)


def _event_id(payload: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in payload.items() if key != "event_id"}
    encoded = json.dumps(stable, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _derived_result_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def explore_result_log_path(runtime_root: Path, goal_id: str) -> Path:
    return (
        runtime_root.expanduser()
        / "goals"
        / _safe_goal_id(goal_id)
        / DEFAULT_EXPLORE_RESULT_LOG_NAME
    )


def _choice(value: Any, *, choices: set[str], default: str, field: str) -> str:
    text = str(value or default).strip().lower()
    if text not in choices:
        raise ValueError(f"unsupported {field} {value!r}; choose {', '.join(sorted(choices))}")
    return text


def build_explore_node_event(
    *,
    goal_id: str,
    title: str,
    node_id: str | None = None,
    node_kind: str | None = None,
    status: str | None = None,
    summary: str | None = None,
    blocked_reason: str | None = None,
    parent_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    evidence_refs: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    supersedes: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _safe_goal_id(goal_id)
    safe_title = _compact_text(title, limit=TITLE_LIMIT, field="title")
    if not safe_title:
        raise ValueError("title is required")
    resolved_status = _choice(status, choices=NODE_STATUSES, default=NODE_STATUS_OPEN, field="status")
    safe_blocked_reason = _compact_text(blocked_reason, limit=SUMMARY_LIMIT, field="blocked_reason")
    if resolved_status == NODE_STATUS_BLOCKED and not safe_blocked_reason:
        raise ValueError("blocked nodes must state a blocked_reason")
    event = _base_event(
        goal_id=safe_goal_id,
        event_kind=EVENT_KIND_NODE,
        title=safe_title,
        summary=summary,
        agent_id=agent_id,
        run_id=run_id,
        evidence_refs=evidence_refs,
        tags=tags,
        supersedes=supersedes,
        recorded_at=recorded_at,
    )
    event["result_id"] = (
        _safe_result_id(node_id, field="node_id")
        if node_id
        else _derived_result_id("node", safe_goal_id, safe_title.lower())
    )
    event["node_kind"] = _choice(node_kind, choices=NODE_KINDS, default=NODE_KIND_AREA, field="node_kind")
    event["status"] = resolved_status
    if safe_blocked_reason:
        event["blocked_reason"] = safe_blocked_reason
    if parent_id:
        event["parent_id"] = _safe_result_id(parent_id, field="parent_id")
    event["event_id"] = _event_id(event)
    return event


def build_explore_edge_event(
    *,
    goal_id: str,
    from_node: str,
    to_node: str,
    edge_type: str,
    summary: str | None = None,
    confidence: float | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _safe_goal_id(goal_id)
    safe_from = _safe_result_id(from_node, field="from_node")
    safe_to = _safe_result_id(to_node, field="to_node")
    if safe_from == safe_to:
        raise ValueError("edge must connect two different nodes")
    resolved_type = _choice(edge_type, choices=EDGE_TYPES, default="", field="edge_type")
    event = _base_event(
        goal_id=safe_goal_id,
        event_kind=EVENT_KIND_EDGE,
        title=f"{safe_from} -{resolved_type}-> {safe_to}",
        summary=summary,
        agent_id=agent_id,
        run_id=run_id,
        evidence_refs=None,
        tags=None,
        supersedes=None,
        recorded_at=recorded_at,
    )
    event["result_id"] = _derived_result_id("edge", safe_goal_id, safe_from, resolved_type, safe_to)
    event["from_node"] = safe_from
    event["to_node"] = safe_to
    event["edge_type"] = resolved_type
    safe_confidence = _safe_confidence(confidence)
    if safe_confidence is not None:
        event["confidence"] = safe_confidence
    event["event_id"] = _event_id(event)
    return event


def build_explore_finding_event(
    *,
    goal_id: str,
    title: str,
    finding_id: str | None = None,
    node_id: str | None = None,
    status: str | None = None,
    summary: str | None = None,
    confidence: float | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    evidence_refs: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    supersedes: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _safe_goal_id(goal_id)
    safe_title = _compact_text(title, limit=TITLE_LIMIT, field="title")
    if not safe_title:
        raise ValueError("title is required")
    event = _base_event(
        goal_id=safe_goal_id,
        event_kind=EVENT_KIND_FINDING,
        title=safe_title,
        summary=summary,
        agent_id=agent_id,
        run_id=run_id,
        evidence_refs=evidence_refs,
        tags=tags,
        supersedes=supersedes,
        recorded_at=recorded_at,
    )
    event["result_id"] = (
        _safe_result_id(finding_id, field="finding_id")
        if finding_id
        else _derived_result_id("finding", safe_goal_id, safe_title.lower())
    )
    if node_id:
        event["node_id"] = _safe_result_id(node_id, field="node_id")
    event["status"] = _choice(
        status, choices=FINDING_STATUSES, default=FINDING_STATUS_TENTATIVE, field="status"
    )
    safe_confidence = _safe_confidence(confidence)
    if safe_confidence is not None:
        event["confidence"] = safe_confidence
    event["event_id"] = _event_id(event)
    return event


def _base_event(
    *,
    goal_id: str,
    event_kind: str,
    title: str,
    summary: str | None,
    agent_id: str | None,
    run_id: str | None,
    evidence_refs: Sequence[str] | None,
    tags: Sequence[str] | None,
    supersedes: str | None,
    recorded_at: str | None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema_version": EXPLORE_RESULT_EVENT_SCHEMA_VERSION,
        "goal_id": goal_id,
        "event_kind": event_kind,
        "recorded_at": str(recorded_at or _now_iso()),
        "title": title,
        "boundary": dict(PUBLIC_BOUNDARY),
    }
    safe_summary = _compact_text(summary, limit=SUMMARY_LIMIT, field="summary")
    if safe_summary:
        event["summary"] = safe_summary
    if agent_id:
        event["agent_id"] = _compact_text(agent_id, limit=80, field="agent_id")
    if run_id:
        event["run_id"] = _safe_public_ref(run_id, field="run_id")
    refs = _safe_public_refs(evidence_refs, field="evidence_refs", max_items=MAX_EVIDENCE_REFS)
    if refs:
        event["evidence_refs"] = refs
    safe_tags = [
        _compact_text(tag, limit=48, field=f"tags[{index}]")
        for index, tag in enumerate(tags or [])
    ]
    safe_tags = [tag for tag in safe_tags if tag][:MAX_TAGS]
    if safe_tags:
        event["tags"] = safe_tags
    if supersedes:
        event["supersedes"] = _safe_result_id(supersedes, field="supersedes")
    return event


def append_explore_result_event(path: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    if event.get("schema_version") != EXPLORE_RESULT_EVENT_SCHEMA_VERSION:
        raise ValueError(
            f"explore result event must use schema {EXPLORE_RESULT_EVENT_SCHEMA_VERSION}"
        )
    log_path = path.expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(event), ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "ok": True,
        "schema_version": EXPLORE_RESULT_EVENT_SCHEMA_VERSION,
        "path": str(log_path),
        "event_id": event.get("event_id"),
        "result_id": event.get("result_id"),
        "event_kind": event.get("event_kind"),
    }


def load_explore_result_events(
    path: Path,
    *,
    goal_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    log_path = path.expanduser()
    if not log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("schema_version") != EXPLORE_RESULT_EVENT_SCHEMA_VERSION:
            continue
        if payload.get("event_kind") not in EXPLORE_EVENT_KINDS:
            continue
        if goal_id and str(payload.get("goal_id") or "") != goal_id:
            continue
        events.append(payload)
    if limit is not None and limit >= 0:
        events = events[-limit:] if limit else []
    return events


def _fold_by_result_id(
    events: Sequence[Mapping[str, Any]], *, event_kind: str
) -> list[dict[str, Any]]:
    folded: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_kind") != event_kind:
            continue
        result_id = str(event.get("result_id") or "")
        if not result_id:
            continue
        prior = folded.get(result_id)
        view = dict(event)
        view["first_recorded_at"] = (
            prior["first_recorded_at"] if prior else str(event.get("recorded_at") or "")
        )
        view["last_updated_at"] = str(event.get("recorded_at") or "")
        view["update_count"] = (prior["update_count"] + 1) if prior else 1
        folded[result_id] = view
    return list(folded.values())


def _node_view(event: Mapping[str, Any], *, finding_count: int) -> dict[str, Any]:
    return {
        "node_id": str(event.get("result_id") or ""),
        "title": str(event.get("title") or ""),
        "node_kind": str(event.get("node_kind") or NODE_KIND_AREA),
        "status": str(event.get("status") or NODE_STATUS_OPEN),
        "summary": str(event.get("summary") or ""),
        "blocked_reason": str(event.get("blocked_reason") or ""),
        "parent_id": str(event.get("parent_id") or ""),
        "agent_id": str(event.get("agent_id") or ""),
        "evidence_refs": list(event.get("evidence_refs") or []),
        "tags": list(event.get("tags") or []),
        "supersedes": str(event.get("supersedes") or ""),
        "finding_count": finding_count,
        "first_recorded_at": str(event.get("first_recorded_at") or ""),
        "last_updated_at": str(event.get("last_updated_at") or ""),
        "update_count": int(event.get("update_count") or 1),
    }


def _edge_view(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "edge_id": str(event.get("result_id") or ""),
        "from_node": str(event.get("from_node") or ""),
        "to_node": str(event.get("to_node") or ""),
        "edge_type": str(event.get("edge_type") or ""),
        "summary": str(event.get("summary") or ""),
        "confidence": event.get("confidence"),
        "last_updated_at": str(event.get("last_updated_at") or ""),
    }


def _materialized_parent_edges(
    nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Represent node parent links as display edges for graph-oriented sinks.

    ``parent_id`` is the compact tree source of truth, but visual consumers such
    as Base relationship views and Sankey-like components need rows in the edge
    table. These derived edges are parent -> child and use ``supports`` so they
    do not alter the ``subtopic_of`` tree parser.
    """

    known = {str(node.get("node_id") or "") for node in nodes}
    existing_pairs = {
        frozenset((str(edge.get("from_node") or ""), str(edge.get("to_node") or "")))
        for edge in edges
    }
    derived: list[dict[str, Any]] = []
    for node in nodes:
        child = str(node.get("node_id") or "")
        parent = str(node.get("parent_id") or "")
        if not child or not parent or child == parent or parent not in known:
            continue
        if frozenset((parent, child)) in existing_pairs:
            continue
        digest = hashlib.sha1(f"{parent}->{child}".encode("utf-8")).hexdigest()[:12]
        derived.append(
            {
                "edge_id": f"parent_{digest}",
                "from_node": parent,
                "to_node": child,
                "edge_type": "supports",
                "summary": "Parent topic contains this exploration node.",
                "confidence": 1.0,
                "last_updated_at": str(node.get("last_updated_at") or ""),
                "materialized_from": "node_parent_id",
            }
        )
    return derived


def _finding_view(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "finding_id": str(event.get("result_id") or ""),
        "finding": str(event.get("title") or ""),
        "summary": str(event.get("summary") or ""),
        "status": str(event.get("status") or FINDING_STATUS_TENTATIVE),
        "confidence": event.get("confidence"),
        "node_id": str(event.get("node_id") or ""),
        "agent_id": str(event.get("agent_id") or ""),
        "evidence_refs": list(event.get("evidence_refs") or []),
        "tags": list(event.get("tags") or []),
        "supersedes": str(event.get("supersedes") or ""),
        "first_recorded_at": str(event.get("first_recorded_at") or ""),
        "last_updated_at": str(event.get("last_updated_at") or ""),
        "update_count": int(event.get("update_count") or 1),
    }


def _parent_map(nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    known = {str(node.get("node_id")) for node in nodes}
    parents: dict[str, str] = {}
    for edge in edges:
        if str(edge.get("edge_type")) != EDGE_TYPE_SUBTOPIC_OF:
            continue
        child = str(edge.get("from_node") or "")
        parent = str(edge.get("to_node") or "")
        if child in known and parent in known:
            parents[child] = parent
    for node in nodes:
        parent = str(node.get("parent_id") or "")
        if parent and parent in known:
            parents[str(node.get("node_id"))] = parent
    return parents


def _build_tree(
    nodes: Sequence[Mapping[str, Any]],
    parents: Mapping[str, str],
    *,
    depth_limit: int = DEFAULT_TREE_DEPTH_LIMIT,
) -> list[dict[str, Any]]:
    children: dict[str, list[str]] = {}
    node_by_id = {str(node.get("node_id")): node for node in nodes}
    roots: list[str] = []
    for node_id in node_by_id:
        parent = parents.get(node_id)
        if parent and parent != node_id and parent in node_by_id:
            children.setdefault(parent, []).append(node_id)
        else:
            roots.append(node_id)

    def branch(node_id: str, *, depth: int, seen: frozenset[str]) -> dict[str, Any]:
        node = node_by_id[node_id]
        view = {
            "node_id": node_id,
            "title": str(node.get("title") or ""),
            "status": str(node.get("status") or NODE_STATUS_OPEN),
            "children": [],
        }
        if depth < depth_limit:
            view["children"] = [
                branch(child, depth=depth + 1, seen=seen | {node_id})
                for child in children.get(node_id, [])
                if child not in seen
            ]
        return view

    return [branch(root, depth=1, seen=frozenset({root})) for root in roots]


_MERMAID_STATUS_CLASS = {
    NODE_STATUS_OPEN: "open",
    NODE_STATUS_EXPLORING: "exploring",
    NODE_STATUS_BLOCKED: "blocked",
    NODE_STATUS_RESOLVED: "resolved",
    NODE_STATUS_DEAD_END: "deadend",
}


def _mermaid_label(text: str) -> str:
    cleaned = re.sub(r'["\[\]{}<>`|]', "'", str(text or ""))
    return cleaned[:60].strip() or "untitled"


def _mermaid_id(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(node_id))


def build_explore_mermaid(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    *,
    node_limit: int = DEFAULT_MERMAID_NODE_LIMIT,
) -> str:
    """Render the exploration topology as Mermaid flowchart source."""

    lines = ["flowchart TD"]
    shown = list(nodes)[:node_limit]
    shown_ids = {str(node.get("node_id")) for node in shown}
    for node in shown:
        node_id = _mermaid_id(str(node.get("node_id")))
        status = str(node.get("status") or NODE_STATUS_OPEN)
        marker = {"blocked": " (BLOCKED)", "resolved": " (done)", "dead_end": " (dead end)"}.get(
            status, ""
        )
        label = _mermaid_label(f"{node.get('title')}{marker}")
        lines.append(f'    {node_id}["{label}"]:::{_MERMAID_STATUS_CLASS.get(status, "open")}')
    for edge in edges:
        from_node = str(edge.get("from_node") or "")
        to_node = str(edge.get("to_node") or "")
        if from_node not in shown_ids or to_node not in shown_ids:
            continue
        label = _mermaid_label(str(edge.get("edge_type") or ""))
        lines.append(f"    {_mermaid_id(from_node)} -->|{label}| {_mermaid_id(to_node)}")
    if len(nodes) > node_limit:
        lines.append(f"    %% {len(nodes) - node_limit} more nodes omitted")
    lines.extend(
        [
            "    classDef open fill:#f5f5f5,stroke:#9e9e9e",
            "    classDef exploring fill:#e3f2fd,stroke:#1e88e5",
            "    classDef blocked fill:#ffebee,stroke:#e53935,stroke-width:2px",
            "    classDef resolved fill:#e8f5e9,stroke:#43a047",
            "    classDef deadend fill:#eeeeee,stroke:#9e9e9e,stroke-dasharray: 4 4",
        ]
    )
    return "\n".join(lines)


def build_explore_result_projection(
    events: Sequence[Mapping[str, Any]],
    *,
    goal_id: str,
    finding_limit: int = DEFAULT_FINDING_LIMIT,
    mermaid_node_limit: int = DEFAULT_MERMAID_NODE_LIMIT,
) -> dict[str, Any]:
    """Fold result events into the bounded projection display sinks render."""

    safe_goal_id = _safe_goal_id(goal_id)
    scoped = [event for event in events if str(event.get("goal_id") or "") == safe_goal_id]

    folded_findings = _fold_by_result_id(scoped, event_kind=EVENT_KIND_FINDING)
    finding_counts: dict[str, int] = {}
    for finding in folded_findings:
        node_id = str(finding.get("node_id") or "")
        if node_id:
            finding_counts[node_id] = finding_counts.get(node_id, 0) + 1

    nodes = [
        _node_view(event, finding_count=finding_counts.get(str(event.get("result_id")), 0))
        for event in sorted(
            _fold_by_result_id(scoped, event_kind=EVENT_KIND_NODE),
            key=lambda item: str(item.get("first_recorded_at") or ""),
        )
    ]
    edges = [
        _edge_view(event) for event in _fold_by_result_id(scoped, event_kind=EVENT_KIND_EDGE)
    ]
    edges = [*edges, *_materialized_parent_edges(nodes, edges)]
    findings = sorted(
        (_finding_view(event) for event in folded_findings),
        key=lambda item: item["last_updated_at"],
        reverse=True,
    )

    nodes_by_status: dict[str, int] = {status: 0 for status in sorted(NODE_STATUSES)}
    for node in nodes:
        nodes_by_status[node["status"]] = nodes_by_status.get(node["status"], 0) + 1
    findings_by_status: dict[str, int] = {status: 0 for status in sorted(FINDING_STATUSES)}
    for finding in findings:
        findings_by_status[finding["status"]] = findings_by_status.get(finding["status"], 0) + 1

    parents = _parent_map(nodes, edges)
    return {
        "ok": True,
        "schema_version": EXPLORE_RESULT_PROJECTION_VERSION,
        "goal_id": safe_goal_id,
        "generated_at": _now_iso(),
        "source_event_count": len(scoped),
        "counts": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "finding_count": len(findings),
            "nodes_by_status": nodes_by_status,
            "findings_by_status": findings_by_status,
        },
        "nodes": nodes,
        "edges": edges,
        "findings": findings[: max(0, finding_limit)] if finding_limit else [],
        "stuck": [node for node in nodes if node["status"] == NODE_STATUS_BLOCKED],
        "frontier": [node for node in nodes if node["status"] == NODE_STATUS_EXPLORING],
        "tree": _build_tree(nodes, parents),
        "mermaid": build_explore_mermaid(nodes, edges, node_limit=max(1, mermaid_node_limit)),
        "boundary": dict(PUBLIC_BOUNDARY),
    }
