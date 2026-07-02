"""Legacy auto-research quickstart/demo internals.

New product logic belongs in the lightweight kernel or generic multi-agent
runner. This module is intentionally not a compatibility export surface; keep
only the legacy paths that still back current worker/demo behavior until they
are migrated or deleted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import evidence_packet as _evidence_packet
from .quickstart_seed import (
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
    AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION,
    AUTO_RESEARCH_QUICKSTART_TEMPLATE,
    build_auto_research_quickstart,
)
from .demo_supervisor import (
    AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
    build_auto_research_demo_supervisor_plan,
)
from .research_state import (
    build_live_auto_research_projection as _build_live_auto_research_projection,
)


_EP_RESEARCH_CONTRACT_SCHEMA_VERSION = _evidence_packet.RESEARCH_CONTRACT_SCHEMA_VERSION
_EP_RESEARCH_HYPOTHESIS_SCHEMA_VERSION = _evidence_packet.RESEARCH_HYPOTHESIS_SCHEMA_VERSION
_EP_RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION = _evidence_packet.RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION
_EP_AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION = _evidence_packet.AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION
_EP_AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION = _evidence_packet.AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION
_compact_public_text = _evidence_packet._compact_public_text
_compact_public_text_list = _evidence_packet._compact_public_text_list
_compact_public_token = _evidence_packet._compact_public_token
_finite_float = _evidence_packet._finite_float
_json_list = _evidence_packet._json_list
_json_obj = _evidence_packet._json_obj
_METRIC_DIRECTIONS = _evidence_packet.METRIC_DIRECTIONS
_is_negative_evidence_event = _evidence_packet._is_negative_evidence_event
_is_retry_evidence_event = _evidence_packet._is_retry_evidence_event
_load_json_object = _evidence_packet._load_json_object
_metric_improved = _evidence_packet._metric_improved
_metric_rank_key = _evidence_packet._metric_rank_key
_validate_research_contract = _evidence_packet.validate_research_contract
_validate_research_evidence_event = _evidence_packet.validate_research_evidence_event
_validate_research_hypothesis = _evidence_packet.validate_research_hypothesis


AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION = "decentralized_auto_research_fixture_v0"
RESEARCH_FRONTIER_SCHEMA_VERSION = "decentralized_research_frontier_v0"
RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION = "research_evidence_graph_v0"
AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION = "decentralized_auto_research_projection_v0"
AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION = "auto_research_demo_e2e_result_v0"
ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND = "loopx_rollout_event_log"


def load_auto_research_fixture(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    return validate_auto_research_fixture(payload)


def validate_auto_research_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _json_obj(payload, field="fixture")
    schema = _compact_public_token(payload.get("schema_version"), field="schema_version")
    if schema != AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION}")

    contract = _validate_research_contract(_json_obj(payload.get("research_contract"), field="research_contract"))
    hypotheses = [
        _validate_research_hypothesis(_json_obj(item, field="hypotheses[]"))
        for item in _json_list(payload.get("hypotheses"), field="hypotheses")
    ]
    evidence_events = [
        _validate_research_evidence_event(_json_obj(item, field="evidence_events[]"))
        for item in _json_list(payload.get("evidence_events"), field="evidence_events")
    ]

    hypothesis_ids = {item["hypothesis_id"] for item in hypotheses}
    todo_ids = {item["todo_id"] for item in hypotheses if item.get("todo_id")}
    for item in evidence_events:
        if item["hypothesis_id"] not in hypothesis_ids:
            raise ValueError(f"evidence references unknown hypothesis_id {item['hypothesis_id']}")
        if item.get("todo_id") and item["todo_id"] not in todo_ids:
            raise ValueError(f"evidence references unknown todo_id {item['todo_id']}")

    agents = [
        _compact_public_token(value, field="agents[]")
        for value in _json_list(payload.get("agents"), field="agents")
    ]

    return {
        "schema_version": schema,
        "generated_at": _compact_public_text(payload.get("generated_at"), field="generated_at"),
        "research_contract": contract,
        "agents": agents,
        "hypotheses": hypotheses,
        "evidence_events": evidence_events,
        "raw_logs_recorded": False,
        "private_artifacts_recorded": False,
    }


def build_auto_research_projection(
    fixture: dict[str, Any],
    *,
    agent_id: str,
) -> dict[str, Any]:
    fixture = validate_auto_research_fixture(fixture)
    agent = _compact_public_token(agent_id, field="agent_id")
    contract = fixture["research_contract"]
    hypotheses = fixture["hypotheses"]
    evidence_graph = build_research_evidence_graph(fixture)
    decision_candidates = build_research_decision_candidates(evidence_graph)

    runnable_statuses = {"active", "needs_retry"}
    selected = None
    blocked: list[dict[str, Any]] = []
    runnable: list[dict[str, Any]] = []
    for item in hypotheses:
        item_summary = {
            "hypothesis_id": item["hypothesis_id"],
            "todo_id": item["todo_id"],
            "claimed_by": item["claimed_by"],
            "status": item["status"],
            "mechanism_family": item["mechanism_family"],
        }
        if item["claimed_by"] == agent and item["status"] in runnable_statuses and not item["blocked_by"]:
            runnable.append(item_summary | {"allowed_action": "run_dev_attempt"})
            selected = selected or runnable[-1]
        elif item["claimed_by"] != agent and item["status"] in runnable_statuses:
            blocked.append(item_summary | {"blocked_by": f"claimed_by:{item['claimed_by']}"})
        elif item["blocked_by"]:
            blocked.append(item_summary | {"blocked_by": ",".join(item["blocked_by"])})

    frontier = {
        "schema_version": RESEARCH_FRONTIER_SCHEMA_VERSION,
        "goal_id": contract["goal_id"],
        "agent_id": agent,
        "selected": selected,
        "runnable": runnable,
        "blocked": blocked,
        "promotion_candidates": decision_candidates["promotion_candidates"],
        "retirement_candidates": decision_candidates["retirement_candidates"],
    }
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
        "source_schema_version": fixture["schema_version"],
        "frontier": frontier,
        "evidence_graph": evidence_graph,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "source": "public_fixture",
        },
    }


def _compact_optional_token(value: Any, *, field: str, default: str) -> str:
    if value is None or str(value).strip() == "":
        return default
    return _compact_public_token(value, field=field)


def _compact_optional_text(value: Any, *, field: str, default: str, max_len: int = 240) -> str:
    if value is None or str(value).strip() == "":
        return default
    text = " ".join(str(value).strip().split())
    _compact_public_text(text, field=field, max_len=max(len(text), max_len))
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "."
    return _compact_public_text(text, field=field, max_len=max_len)


def _live_hypothesis_id(todo_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_:-]+", "_", todo_id.replace("todo_", "", 1))
    return _compact_public_token(f"hyp_{suffix}", field="live.hypothesis_id")


def _rollout_source_refs(event: dict[str, Any]) -> tuple[list[str], str | None]:
    grounding_refs: list[str] = []
    novelty_audit_ref: str | None = None
    for index, ref in enumerate(event.get("source_refs") or []):
        if not isinstance(ref, dict):
            continue
        kind = str(ref.get("kind") or "").strip()
        ref_id = ref.get("id")
        if not ref_id:
            continue
        if kind == "grounding":
            grounding_refs.append(
                _compact_public_text(ref_id, field=f"rollout.source_refs[{index}].id")
            )
        elif kind == "novelty_audit" and novelty_audit_ref is None:
            novelty_audit_ref = _compact_public_text(
                ref_id,
                field=f"rollout.source_refs[{index}].id",
            )
    return grounding_refs, novelty_audit_ref


def _rollout_hypothesis_text(event: dict[str, Any], details: dict[str, Any]) -> str:
    if details.get("hypothesis"):
        return _compact_public_text(details["hypothesis"], field="rollout.details.hypothesis")
    summary = str(event.get("summary") or "")
    prefix = "auto-research hypothesis "
    if summary.startswith(prefix) and ": " in summary:
        return _compact_public_text(
            summary.split(": ", 1)[1],
            field="rollout.summary.hypothesis",
        )
    fallback = f"Evidence-backed hypothesis {details.get('hypothesis_id') or event.get('todo_id')}"
    return _compact_public_text(fallback, field="rollout.summary.hypothesis")


def _research_hypothesis_from_rollout_event(event: dict[str, Any]) -> dict[str, Any] | None:
    if str(event.get("event_kind") or "") != "research_hypothesis":
        return None
    if str(event.get("classification") or "") != _EP_RESEARCH_HYPOTHESIS_SCHEMA_VERSION:
        return None
    details = _json_obj(event.get("details") or {}, field="rollout.hypothesis.details")
    grounding_refs, novelty_audit_ref = _rollout_source_refs(event)
    negative_count = int(details.get("negative_evidence_count") or 0)
    retry_count = int(details.get("needs_retry_count") or 0)
    status = details.get("status") or event.get("status") or "active"
    blocked_by: list[str] = []
    if str(status) == "contradicted" or negative_count:
        blocked_by.append("evidence_or_boundary_guardrail_failed")
    elif str(status) == "needs_retry" or retry_count:
        blocked_by.append("needs_retry_evidence")
    return _validate_research_hypothesis(
        {
            "schema_version": _EP_RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            "hypothesis_id": details.get("hypothesis_id"),
            "parent_hypothesis_id": details.get("parent_hypothesis_id") or None,
            "todo_id": event.get("todo_id"),
            "claimed_by": event.get("agent_id") or "unknown_agent",
            "mechanism_family": details.get("mechanism_family") or "rollout_imported",
            "hypothesis": _rollout_hypothesis_text(event, details),
            "status": status,
            "grounding_refs": grounding_refs,
            "novelty_audit_ref": novelty_audit_ref,
            "blocked_by": blocked_by,
        }
    )


def _research_evidence_from_rollout_event(event: dict[str, Any]) -> dict[str, Any] | None:
    if str(event.get("event_kind") or "") != "research_evidence":
        return None
    if str(event.get("classification") or "") != _EP_RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION:
        return None
    details = _json_obj(event.get("details") or {}, field="rollout.evidence.details")
    return _validate_research_evidence_event(
        {
            "schema_version": _EP_RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
            "hypothesis_id": details.get("hypothesis_id"),
            "todo_id": event.get("todo_id"),
            "agent_id": event.get("agent_id") or "unknown_agent",
            "attempt": details.get("attempt") or 1,
            "split": details.get("split"),
            "metric": {
                "name": details.get("metric_name"),
                "value": details.get("metric_value"),
                "direction": details.get("metric_direction"),
            },
            "baseline_metric": details.get("baseline_metric"),
            "eval_status": details.get("eval_status") or event.get("status"),
            "primary_metric_status": details.get("primary_metric_status") or "inconclusive",
            "artifact_refs": event.get("artifact_refs") or [],
            "protected_scope_clean": bool(details.get("protected_scope_clean")),
        }
    )


def _synthetic_hypothesis_from_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    first = events[0]
    status = _derive_hypothesis_status(events)
    blocked_by = []
    if status == "contradicted":
        blocked_by.append("evidence_or_boundary_guardrail_failed")
    elif status == "needs_retry":
        blocked_by.append("needs_retry_evidence")
    return _validate_research_hypothesis(
        {
            "schema_version": _EP_RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            "hypothesis_id": first["hypothesis_id"],
            "parent_hypothesis_id": None,
            "todo_id": first["todo_id"],
            "claimed_by": first["agent_id"],
            "mechanism_family": "rollout_evidence_only",
            "hypothesis": f"Evidence-backed hypothesis {first['hypothesis_id']}",
            "status": status,
            "grounding_refs": [],
            "novelty_audit_ref": None,
            "blocked_by": blocked_by,
        }
    )


def _todo_frontier_item(
    item: dict[str, Any],
    *,
    default_agent_id: str,
    blocked_by: str | None = None,
) -> dict[str, Any]:
    todo_id = _compact_public_token(item.get("todo_id"), field="live.todo_id")
    claimed_by = _compact_optional_token(
        item.get("claimed_by"),
        field="live.claimed_by",
        default=default_agent_id,
    )
    status = _compact_optional_token(item.get("status"), field="live.status", default="open")
    mechanism_family = _compact_optional_text(
        item.get("action_kind") or item.get("task_class") or "advancement_task",
        field="live.mechanism_family",
        default="advancement_task",
        max_len=96,
    )
    summary = {
        "hypothesis_id": _live_hypothesis_id(todo_id),
        "todo_id": todo_id,
        "claimed_by": claimed_by,
        "status": "active" if status == "open" else status,
        "mechanism_family": mechanism_family,
        "source_kind": "todo_item_v0",
        "title": _compact_optional_text(
            item.get("title") or item.get("text"),
            field="live.title",
            default=todo_id,
            max_len=220,
        ),
    }
    if blocked_by:
        summary["blocked_by"] = _compact_public_text(blocked_by, field="live.blocked_by", max_len=160)
    else:
        summary["allowed_action"] = _compact_optional_text(
            item.get("action_kind") or "advance_todo",
            field="live.allowed_action",
            default="advance_todo",
            max_len=96,
        )
    return summary


def _claimed_by_current_or_unclaimed(item: dict[str, Any], *, agent_id: str) -> bool:
    claimed_by = str(item.get("claimed_by") or "").strip()
    return not claimed_by or claimed_by == agent_id


def build_live_auto_research_projection(
    *,
    goal_id: str,
    agent_id: str,
    quota_payload: dict[str, Any],
    rollout_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Delegate live frontier read-model rendering to the lightweight kernel."""

    return _build_live_auto_research_projection(
        goal_id=goal_id,
        agent_id=agent_id,
        quota_payload=quota_payload,
        rollout_events=rollout_events,
    )


def _best_metric(events: list[dict[str, Any]], *, split: str, direction: str) -> float | None:
    values = [
        event["metric"]["value"]
        for event in events
        if event["split"] == split and event["eval_status"] == "scored"
    ]
    if not values:
        return None
    return max(values, key=lambda value: _metric_rank_key(value, direction=direction))


def build_research_decision_candidates(evidence_graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Derive public promotion and retirement candidates from evidence graph nodes."""

    graph = _json_obj(evidence_graph, field="evidence_graph")
    metric = graph.get("metric") if isinstance(graph.get("metric"), dict) else {}
    direction = str(metric.get("direction") or "maximize")
    if direction not in _METRIC_DIRECTIONS:
        direction = "maximize"
    baseline = _finite_float(metric.get("baseline"), field="evidence_graph.metric.baseline")
    source_kind = _compact_optional_token(
        graph.get("source_kind"),
        field="evidence_graph.source_kind",
        default="unknown_source",
    )
    promotion_candidates: list[dict[str, Any]] = []
    dev_promotion_candidates: list[dict[str, Any]] = []
    validated_promotion_candidates: list[dict[str, Any]] = []
    retirement_candidates: list[dict[str, Any]] = []
    for raw_node in graph.get("nodes") or []:
        if not isinstance(raw_node, dict):
            continue
        hypothesis_id = _compact_public_token(raw_node.get("hypothesis_id"), field="node.hypothesis_id")
        todo_id = _compact_public_token(raw_node.get("todo_id"), field="node.todo_id")
        status = _compact_optional_token(raw_node.get("status"), field="node.status", default="active")
        dev_metric = _finite_float(raw_node.get("best_dev_metric"), field="node.best_dev_metric")
        holdout_metric = _finite_float(raw_node.get("best_holdout_metric"), field="node.best_holdout_metric")
        negative_count = int(raw_node.get("negative_evidence_count") or 0)
        evidence_count = int(raw_node.get("evidence_event_count") or 0)
        dev_improved = bool(raw_node.get("dev_improved")) or _metric_improved(
            value=dev_metric,
            baseline=baseline,
            direction=direction,
        )
        holdout_improved = bool(raw_node.get("holdout_improved")) or _metric_improved(
            value=holdout_metric,
            baseline=baseline,
            direction=direction,
        )
        is_retirement_status = status in {"contradicted", "retired"}
        if is_retirement_status or negative_count > 0:
            reason = "negative_or_guardrail_evidence" if negative_count > 0 else f"status:{status}"
            retirement_candidates.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "todo_id": todo_id,
                    "status": status,
                    "negative_evidence_count": negative_count,
                    "evidence_event_count": evidence_count,
                    "reason": reason,
                    "source_kind": source_kind,
                }
            )
            continue
        if status in {"supported", "promoted"} or dev_improved:
            requires = ["boundary_scan"]
            requires.append("promotion_decision" if holdout_improved else "holdout_eval")
            candidate = {
                "hypothesis_id": hypothesis_id,
                "todo_id": todo_id,
                "status": status,
                "dev_metric": dev_metric,
                "holdout_metric": holdout_metric,
                "evidence_event_count": evidence_count,
                "requires": requires,
                "source_kind": source_kind,
            }
            promotion_candidates.append(candidate)
            if holdout_improved:
                validated_promotion_candidates.append(candidate)
            else:
                dev_promotion_candidates.append(candidate)
    return {
        "dev_promotion_candidates": dev_promotion_candidates,
        "validated_promotion_candidates": validated_promotion_candidates,
        "promotion_candidates": promotion_candidates,
        "retirement_candidates": retirement_candidates,
    }


def build_research_evidence_graph_from_records(
    *,
    goal_id: str,
    hypotheses: list[dict[str, Any]],
    evidence_events: list[dict[str, Any]],
    metric_name: str,
    metric_direction: str,
    baseline_metric: float | None,
    source_kind: str = "public_records",
) -> dict[str, Any]:
    goal = _compact_public_token(goal_id, field="goal_id")
    direction = _compact_public_token(metric_direction, field="metric.direction")
    if direction not in _METRIC_DIRECTIONS:
        raise ValueError("metric.direction must be maximize or minimize")
    name = _compact_public_token(metric_name, field="metric.name")
    source = _compact_public_token(source_kind, field="source_kind")
    hypotheses = [_validate_research_hypothesis(dict(item)) for item in hypotheses]
    events = [_validate_research_evidence_event(dict(event)) for event in evidence_events]
    baseline = _finite_float(baseline_metric, field="baseline_metric")
    scored_events = [event for event in events if event["eval_status"] == "scored"]
    best_dev = _best_metric(scored_events, split="dev", direction=direction)
    best_holdout = _best_metric(scored_events, split="holdout", direction=direction)
    events_by_hypothesis: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_hypothesis.setdefault(event["hypothesis_id"], []).append(event)
    nodes = []
    for item in hypotheses:
        item_events = events_by_hypothesis.get(item["hypothesis_id"], [])
        item_scored_events = [event for event in item_events if event["eval_status"] == "scored"]
        item_best_dev = _best_metric(item_scored_events, split="dev", direction=direction)
        item_best_holdout = _best_metric(item_scored_events, split="holdout", direction=direction)
        item_negative_count = len([event for event in item_events if _is_negative_evidence_event(event)])
        item_retry_count = len([event for event in item_events if _is_retry_evidence_event(event)])
        item_artifact_refs = sorted(
            {
                ref
                for event in item_events
                for ref in event.get("artifact_refs", [])
                if ref
            }
        )
        item_splits = sorted({event["split"] for event in item_events if event.get("split")})
        nodes.append(
            {
                "hypothesis_id": item["hypothesis_id"],
                "parent_hypothesis_id": item["parent_hypothesis_id"],
                "todo_id": item["todo_id"],
                "claimed_by": item["claimed_by"],
                "status": item["status"],
                "grounding_refs": item["grounding_refs"],
                "novelty_audit_ref": item["novelty_audit_ref"],
                "artifact_refs": item_artifact_refs,
                "splits": item_splits,
                "evidence_event_count": len(item_events),
                "best_dev_metric": item_best_dev,
                "best_holdout_metric": item_best_holdout,
                "dev_improved": _metric_improved(
                    value=item_best_dev,
                    baseline=baseline,
                    direction=direction,
                ),
                "holdout_improved": _metric_improved(
                    value=item_best_holdout,
                    baseline=baseline,
                    direction=direction,
                ),
                "negative_evidence_count": item_negative_count,
                "needs_retry_count": item_retry_count,
                "source_kind": source,
            }
        )
    return {
        "schema_version": RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION,
        "goal_id": goal,
        "hypothesis_count": len(hypotheses),
        "evidence_event_count": len(events),
        "todo_ids": sorted({item["todo_id"] for item in hypotheses}),
        "agent_ids": sorted({item["claimed_by"] for item in hypotheses}),
        "metric": {
            "name": name,
            "direction": direction,
            "baseline": baseline,
        },
        "baseline_metric": baseline,
        "best_dev_metric": best_dev,
        "best_holdout_metric": best_holdout,
        "holdout_improved": _metric_improved(value=best_holdout, baseline=baseline, direction=direction),
        "negative_evidence_count": len([event for event in events if _is_negative_evidence_event(event)]),
        "needs_retry_count": len(
            [event for event in events if _is_retry_evidence_event(event)]
        ) + len([item for item in hypotheses if item["status"] == "needs_retry"]),
        "nodes": nodes,
        "source_kind": source,
    }


def build_research_evidence_graph(fixture: dict[str, Any]) -> dict[str, Any]:
    contract = fixture["research_contract"]
    return build_research_evidence_graph_from_records(
        goal_id=contract["goal_id"],
        hypotheses=fixture["hypotheses"],
        evidence_events=fixture["evidence_events"],
        metric_name=contract["metric"]["name"],
        metric_direction=contract["metric"]["direction"],
        baseline_metric=contract["metric"]["baseline"],
        source_kind="public_fixture",
    )


def build_research_evidence_graph_from_rollout_events(
    *,
    goal_id: str,
    rollout_events: list[dict[str, Any]],
) -> dict[str, Any]:
    goal = _compact_public_token(goal_id, field="goal_id")
    hypotheses_by_id: dict[str, dict[str, Any]] = {}
    evidence_events: list[dict[str, Any]] = []
    for event in rollout_events:
        hypothesis = _research_hypothesis_from_rollout_event(event)
        if hypothesis:
            hypotheses_by_id[hypothesis["hypothesis_id"]] = hypothesis
            continue
        evidence = _research_evidence_from_rollout_event(event)
        if evidence:
            evidence_events.append(evidence)

    events_by_hypothesis: dict[str, list[dict[str, Any]]] = {}
    for evidence in evidence_events:
        events_by_hypothesis.setdefault(evidence["hypothesis_id"], []).append(evidence)
    for hypothesis_id, events in events_by_hypothesis.items():
        if hypothesis_id not in hypotheses_by_id:
            hypotheses_by_id[hypothesis_id] = _synthetic_hypothesis_from_evidence(events)

    first_metric_event = evidence_events[0] if evidence_events else None
    metric = first_metric_event["metric"] if first_metric_event else {}
    return build_research_evidence_graph_from_records(
        goal_id=goal,
        hypotheses=list(hypotheses_by_id.values()),
        evidence_events=evidence_events,
        metric_name=metric.get("name") or "research_metric",
        metric_direction=metric.get("direction") or "maximize",
        baseline_metric=first_metric_event.get("baseline_metric") if first_metric_event else None,
        source_kind=ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND,
    )


def render_auto_research_projection_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    frontier = payload["frontier"]  # type: ignore[index]
    graph = payload["evidence_graph"]  # type: ignore[index]
    selected = frontier.get("selected") if isinstance(frontier, dict) else None
    lines = [
        "# LoopX Auto Research Frontier",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- agent_id: `{frontier.get('agent_id')}`",
        f"- selected: `{selected.get('hypothesis_id') if isinstance(selected, dict) else 'none'}`",
        f"- hypotheses: `{graph.get('hypothesis_count')}`",
        f"- evidence events: `{graph.get('evidence_event_count')}`",
        f"- best dev metric: `{graph.get('best_dev_metric')}`",
        f"- best holdout metric: `{graph.get('best_holdout_metric')}`",
        f"- promotion candidates: `{len(frontier.get('promotion_candidates') or [])}`",
        f"- retirement candidates: `{len(frontier.get('retirement_candidates') or [])}`",
    ]
    return "\n".join(lines) + "\n"

def _render_auto_research_worker_turn_markdown(payload: dict[str, object]) -> str:
    frontier_packet = payload.get("frontier") if isinstance(payload.get("frontier"), dict) else {}
    quota = frontier_packet.get("quota") if isinstance(frontier_packet.get("quota"), dict) else {}
    frontier = (
        frontier_packet.get("frontier")
        if isinstance(frontier_packet.get("frontier"), dict)
        else {}
    )
    selected = frontier.get("selected") if isinstance(frontier.get("selected"), dict) else {}
    completion = payload.get("completion") if isinstance(payload.get("completion"), dict) else {}
    append = payload.get("append") if isinstance(payload.get("append"), dict) else {}
    live_evidence = (
        payload.get("live_evidence")
        if isinstance(payload.get("live_evidence"), dict)
        else {}
    )
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    lines = [
        "# LoopX Auto Research Worker Turn",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- quota_should_run: `{quota.get('should_run')}`",
        f"- quota_state: `{quota.get('state')}`",
        f"- user_action_required: `{quota.get('user_action_required')}`",
        f"- selected_todo: `{payload.get('selected_todo_id') or selected.get('todo_id')}`",
        f"- selected_action: `{payload.get('selected_action') or selected.get('allowed_action')}`",
        f"- selected_title: {selected.get('title')}",
        f"- blocker: `{payload.get('blocker')}`",
        f"- blocker_detail: {payload.get('blocker_detail')}",
        f"- executed: `{payload.get('executed')}`",
        f"- would_execute: `{payload.get('would_execute')}`",
        f"- completion_status: `{completion.get('status')}`",
        f"- completion_executed: `{completion.get('executed')}`",
        f"- artifact: `{artifact.get('filename') or artifacts.get('evidence_packet')}`",
        f"- artifact_status: `{payload.get('artifact_status') or payload.get('packet_status')}`",
        f"- dev_metric: `{payload.get('dev_metric')}`",
        f"- holdout_metric: `{payload.get('holdout_metric')}`",
        f"- appended_count: `{append.get('appended_count')}`",
        f"- live_evidence_written: `{live_evidence.get('written')}`",
        f"- public_boundary: raw_logs=`False`, private_artifacts=`False`, paths=`local-only`",
    ]
    return "\n".join(lines) + "\n"


def _render_auto_research_worker_loop_markdown(payload: dict[str, object]) -> str:
    turns = payload.get("turns") if isinstance(payload.get("turns"), list) else []
    lines = [
        "# LoopX Auto Research Worker Loop",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- round_count: `{payload.get('round_count')}`",
        f"- max_rounds: `{payload.get('max_rounds')}`",
        f"- stop_reason: `{payload.get('stop_reason')}`",
        f"- turn_count: `{payload.get('turn_count')}`",
        f"- executed_turn_count: `{payload.get('executed_turn_count')}`",
        f"- completed_turn_count: `{payload.get('completed_turn_count')}`",
        f"- selected_actions: `{', '.join(str(action) for action in payload.get('selected_actions') or [])}`",
        "",
        "## Turns",
        "",
    ]
    if not turns:
        lines.append("- none")
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        lines.append(
            f"- round `{turn.get('round')}` agent `{turn.get('agent_id')}` "
            f"mode `{turn.get('mode')}` action `{turn.get('selected_action')}` "
            f"executed `{turn.get('executed')}` completion `{turn.get('completion_status')}` "
            f"dev `{turn.get('dev_metric')}` holdout `{turn.get('holdout_metric')}`"
        )
    return "\n".join(lines) + "\n"


def render_auto_research_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    if payload.get("schema_version") == "auto_research_worker_turn_v0":
        return _render_auto_research_worker_turn_markdown(payload)
    if payload.get("schema_version") == "auto_research_worker_loop_v0":
        return _render_auto_research_worker_loop_markdown(payload)
    if payload.get("schema_version") == AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION:
        worker_loop = (
            payload.get("worker_loop")
            if isinstance(payload.get("worker_loop"), dict)
            else {}
        )
        tonight = (
            payload.get("tonight_experience")
            if isinstance(payload.get("tonight_experience"), dict)
            else {}
        )
        supervisor = payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}
        commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
        route = payload.get("route_contract") if isinstance(payload.get("route_contract"), dict) else {}
        live = payload.get("visible_worker_proof") if isinstance(payload.get("visible_worker_proof"), dict) else {}
        lines = [
            "# LoopX Auto Research Minimal E2E Demo",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- mode: `{payload.get('mode')}`",
            f"- execution_kind: `{payload.get('execution_kind')}`",
            f"- result_source: `{payload.get('result_source')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- tracking_goal_id: `{payload.get('tracking_goal_id')}`",
            f"- frontier_goal_id: `{route.get('frontier_goal_id')}`",
            f"- agent_id: `{payload.get('agent_id')}`",
            f"- reasoning_effort: `{payload.get('reasoning_effort')}`",
            f"- worker_loop_executed_turns: `{worker_loop.get('executed_turn_count')}`",
            f"- worker_loop_completed_turns: `{worker_loop.get('completed_turn_count')}`",
            f"- worker_loop_selected_actions: `{worker_loop.get('selected_actions')}`",
            f"- worker_loop_stop_reason: `{worker_loop.get('stop_reason')}`",
            f"- tonight_ready: `{tonight.get('ready')}`",
            f"- tonight_coordination_pattern: `{tonight.get('coordination_pattern')}`",
            f"- tonight_dev_metric: `{tonight.get('dev_metric')}`",
            f"- tonight_holdout_metric: `{tonight.get('holdout_metric')}`",
            f"- tonight_positive_result: `{tonight.get('positive_result')}`",
            f"- visible_lanes_launched: `{live.get('visible_lanes_launched')}`",
            f"- visible_lanes_accepted: `{live.get('visible_lanes_accepted')}`",
            f"- supervisor_lanes: `{supervisor.get('lane_count')}`",
            "",
            "## Commands",
            "",
            f"- one-command worker-loop: `{commands.get('one_command_worker_loop')}`",
            f"- worker-loop plus visible lanes: `{commands.get('one_command_worker_loop_with_visible_lanes')}`",
        ]
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION:
        contract = payload["research_contract"]  # type: ignore[index]
        hypothesis = payload["next_runnable_hypothesis"]  # type: ignore[index]
        commands = payload.get("next_commands") or []
        lines = [
            "# LoopX Auto Research Quickstart",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- mode: `{payload.get('mode')}`",
            f"- pack_dir: `{payload.get('pack_dir')}`",
            f"- goal_id: `{contract.get('goal_id')}`",
            f"- objective: {contract.get('research_objective')}",
            f"- next hypothesis: `{hypothesis.get('hypothesis_id')}`",
            f"- allowed action: `{hypothesis.get('allowed_action')}`",
            "",
            "## Next Commands",
        ]
        for item in commands:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('label')}: `{item.get('command')}`")
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION:
        lanes = payload.get("lanes") or []
        commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
        one_click = payload.get("one_click_demo") if isinstance(payload.get("one_click_demo"), dict) else {}
        takeover = payload.get("user_takeover") if isinstance(payload.get("user_takeover"), dict) else {}
        coordination = (
            payload.get("coordination_model")
            if isinstance(payload.get("coordination_model"), dict)
            else {}
        )
        launch_result = (
            payload.get("launch_result")
            if isinstance(payload.get("launch_result"), dict)
            else {}
        )
        lines = [
            "# LoopX Auto Research Demo Supervisor",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- mode: `{payload.get('mode')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- session: `{payload.get('session_name')}`",
            f"- leader_agent_required: `{coordination.get('leader_agent_required')}`",
            f"- lanes: `{len(lanes)}`",
            "",
            "## Lanes",
        ]
        for item in lanes:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('lane_id')}` / `{item.get('agent_id')}` / `{item.get('role_id')}`: "
                f"{item.get('responsibility')}"
            )
        lines.extend(["", "## Role Profile Summary", ""])
        for item in lanes:
            if not isinstance(item, dict):
                continue
            profile = item.get("role_profile") if isinstance(item.get("role_profile"), dict) else {}
            lines.append(
                f"- `{profile.get('role_id')}`: worker playbook `{profile.get('required_skill')}` / "
                f"section `{profile.get('skill_section')}` / phase `{profile.get('phase')}`"
            )
        lines.extend(["", "## Role Profiles", ""])
        for item in lanes:
            if not isinstance(item, dict):
                continue
            profile = item.get("role_profile") if isinstance(item.get("role_profile"), dict) else {}
            if not profile:
                continue
            lines.append(f"### {item.get('lane_id')}")
            lines.append(f"- role_id: `{profile.get('role_id')}`")
            lines.append(f"- phase: `{profile.get('phase')}`")
            lines.append(f"- required_worker_playbook: `{profile.get('required_skill')}`")
            lines.append(f"- skill_distribution: `{profile.get('skill_distribution')}`")
            lines.append(f"- worker_skill_source: `{profile.get('worker_skill_source')}`")
            lines.append(f"- skill_section: `{profile.get('skill_section')}`")
            lines.append(
                "- allowed_actions: `"
                + ",".join(str(action) for action in profile.get("allowed_actions") or [])
                + "`"
            )
            lines.append(
                "- write_scope: `"
                + ",".join(str(scope) for scope in profile.get("write_scope") or [])
                + "`"
            )
            lines.append(
                "- stop_conditions: `"
                + " | ".join(str(condition) for condition in profile.get("stop_conditions") or [])
                + "`"
            )
            lines.append("")
        lines.extend(["", "## Lane Timeline", ""])
        for item in lanes:
            if not isinstance(item, dict):
                continue
            timeline = item.get("lane_timeline") if isinstance(item.get("lane_timeline"), list) else []
            if not timeline:
                continue
            lines.append(f"### {item.get('lane_id')}")
            for phase in timeline:
                if not isinstance(phase, dict):
                    continue
                lines.append(
                    f"- `{phase.get('phase')}` via `{phase.get('command_ref')}`: "
                    f"{phase.get('operator_visible_signal')}"
                )
            lines.append("")
        lines.extend(["", "## One-Click Dry Run", ""])
        lines.append(f"- mode: `{one_click.get('mode')}`")
        lines.append(f"- default_safe: `{one_click.get('default_safe')}`")
        lines.append(f"- description: {one_click.get('description')}")
        lines.append("")
        lines.append("```bash")
        for line in one_click.get("script") or []:
            lines.append(str(line))
        lines.append("```")
        controls = takeover.get("operator_controls") or []
        if controls:
            lines.extend(["", "## User Takeover", ""])
            for item in controls:
                lines.append(f"- {item}")
        cues = takeover.get("visible_status_cues") or []
        if cues:
            lines.extend(["", "## Visible Status Cues", ""])
            for item in cues:
                lines.append(f"- {item}")
        if launch_result:
            lines.extend(["", "## Visible Launch Result", ""])
            lines.append(f"- launcher: `{launch_result.get('launcher')}`")
            lines.append(f"- executed: `{launch_result.get('executed')}`")
            lines.append(f"- started_lanes: `{launch_result.get('started_lane_count')}`")
            lines.append(f"- surviving_lanes: `{launch_result.get('surviving_lane_count')}`")
            lines.append(f"- attach: `{launch_result.get('attach_command')}`")
            lines.append(f"- stop: `{launch_result.get('stop_command')}`")
            lines.append(f"- takeover: {launch_result.get('operator_takeover')}")
            acceptance = (
                launch_result.get("visible_acceptance")
                if isinstance(launch_result.get("visible_acceptance"), dict)
                else {}
            )
            if acceptance:
                lines.append(f"- visible_acceptance: `{acceptance.get('accepted')}`")
        lines.extend(["", "## Shell Plan", ""])
        lines.append("- start_script: `machine_json_only`")
        lines.append("- launch: `loopx auto-research demo-e2e --execute`")
        lines.extend(
            [
                "",
                "## Attach",
                "",
                f"`{commands.get('attach')}`",
            ]
        )
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == _EP_AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION:
        summary = payload["summary"]  # type: ignore[index]
        hypothesis = payload["hypothesis"]  # type: ignore[index]
        lines = [
            "# LoopX Auto Research Evidence",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- hypothesis: `{hypothesis.get('hypothesis_id')}`",
            f"- todo: `{hypothesis.get('todo_id')}`",
            f"- status: `{hypothesis.get('status')}`",
            f"- evidence events: `{summary.get('evidence_event_count')}`",
            f"- splits: `{', '.join(summary.get('splits', []))}`",
            f"- negative evidence: `{summary.get('negative_evidence_count')}`",
            f"- protected scope clean: `{summary.get('protected_scope_clean')}`",
        ]
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == _EP_AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION:
        lines = [
            "# LoopX Auto Research Rollout Append",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- dry_run: `{payload.get('dry_run')}`",
            f"- events: `{payload.get('event_count')}`",
            f"- appended: `{payload.get('appended_count')}`",
            f"- would_append: `{payload.get('would_append_count')}`",
            f"- skipped_existing: `{payload.get('skipped_existing_count')}`",
        ]
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == "auto_research_live_codex_lane_e2e_evidence_v0":
        visible = payload.get("visible_lanes") if isinstance(payload.get("visible_lanes"), dict) else {}
        evidence = payload.get("lane_evidence") if isinstance(payload.get("lane_evidence"), dict) else {}
        lines = [
            "# LoopX Auto Research Live Evidence",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- agent_id: `{payload.get('agent_id')}`",
            f"- source: `{payload.get('source')}`",
            f"- visible_lanes_accepted: `{visible.get('accepted')}`",
            f"- lane_count: `{visible.get('lane_count')}`",
            f"- evidence_events: `{evidence.get('evidence_event_count')}`",
            f"- result_status: `{evidence.get('result_status')}`",
            f"- protected_scope_clean: `{evidence.get('protected_scope_clean')}`",
        ]
        return "\n".join(lines) + "\n"
    return render_auto_research_projection_markdown(payload)
