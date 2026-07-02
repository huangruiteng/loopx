"""Small read-model helpers for auto-research worker state.

This module turns LoopX quota/todo state and rollout evidence events into the
minimal frontier, evidence graph, and decision-candidate shapes that worker
turns need. It intentionally avoids demo boards, quickstart packs, and other
legacy presentation code.
"""

from __future__ import annotations

import re
from typing import Any

from .evidence_packet import (
    METRIC_DIRECTIONS,
    RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
    RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
    _compact_public_text,
    _compact_public_text_list,
    _compact_public_token,
    _derive_hypothesis_status,
    _finite_float,
    _is_negative_evidence_event,
    _is_retry_evidence_event,
    _json_obj,
    _metric_improved,
    _metric_rank_key,
    validate_research_evidence_event,
    validate_research_hypothesis,
)


AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION = "decentralized_auto_research_projection_v0"
AUTO_RESEARCH_PUBLIC_CLAIM_BOUNDARY_SCHEMA_VERSION = "auto_research_public_claim_boundary_v0"
RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION = "research_evidence_graph_v0"
RESEARCH_FRONTIER_SCHEMA_VERSION = "decentralized_research_frontier_v0"
RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION = "research_showcase_projection_v0"
ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND = "loopx_rollout_event_log"


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


def _claimed_by_current_or_unclaimed(item: dict[str, Any], *, agent_id: str) -> bool:
    claimed_by = str(item.get("claimed_by") or "").strip()
    return not claimed_by or claimed_by == agent_id


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
    summary = {
        "hypothesis_id": _live_hypothesis_id(todo_id),
        "todo_id": todo_id,
        "claimed_by": claimed_by,
        "status": "active" if status == "open" else status,
        "mechanism_family": _compact_optional_text(
            item.get("action_kind") or item.get("task_class") or "advancement_task",
            field="live.mechanism_family",
            default="advancement_task",
            max_len=96,
        ),
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
    if str(event.get("classification") or "") != RESEARCH_HYPOTHESIS_SCHEMA_VERSION:
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
    return validate_research_hypothesis(
        {
            "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
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
    if str(event.get("classification") or "") != RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION:
        return None
    details = _json_obj(event.get("details") or {}, field="rollout.evidence.details")
    return validate_research_evidence_event(
        {
            "schema_version": RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
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
    return validate_research_hypothesis(
        {
            "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
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


def _best_metric(events: list[dict[str, Any]], *, split: str, direction: str) -> float | None:
    values = [
        event["metric"]["value"]
        for event in events
        if event["split"] == split and event["eval_status"] == "scored"
    ]
    if not values:
        return None
    return max(values, key=lambda value: _metric_rank_key(value, direction=direction))


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
    if direction not in METRIC_DIRECTIONS:
        raise ValueError("metric.direction must be maximize or minimize")
    name = _compact_public_token(metric_name, field="metric.name")
    source = _compact_public_token(source_kind, field="source_kind")
    hypotheses = [validate_research_hypothesis(dict(item)) for item in hypotheses]
    events = [validate_research_evidence_event(dict(event)) for event in evidence_events]
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
        item_artifact_refs = sorted(
            {
                ref
                for event in item_events
                for ref in event.get("artifact_refs", [])
                if ref
            }
        )
        item_splits = sorted({event["split"] for event in item_events if event.get("split")})
        item_negative_count = len([event for event in item_events if _is_negative_evidence_event(event)])
        item_retry_count = len([event for event in item_events if _is_retry_evidence_event(event)])
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


def build_research_decision_candidates(evidence_graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    graph = _json_obj(evidence_graph, field="evidence_graph")
    metric = graph.get("metric") if isinstance(graph.get("metric"), dict) else {}
    direction = str(metric.get("direction") or "maximize")
    if direction not in METRIC_DIRECTIONS:
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
        if status in {"contradicted", "retired"} or negative_count > 0:
            retirement_candidates.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "todo_id": todo_id,
                    "status": status,
                    "negative_evidence_count": negative_count,
                    "evidence_event_count": evidence_count,
                    "reason": "negative_or_guardrail_evidence" if negative_count else f"status:{status}",
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


def _public_claim_boundary(
    *,
    source_kind: str,
    best_dev: Any,
    best_holdout: Any,
) -> dict[str, Any]:
    dev_metric = _finite_float(best_dev, field="claim_boundary.best_dev")
    holdout_metric = _finite_float(best_holdout, field="claim_boundary.best_holdout")
    return {
        "schema_version": AUTO_RESEARCH_PUBLIC_CLAIM_BOUNDARY_SCHEMA_VERSION,
        "metric_source_kind": source_kind,
        "claim_source": "live_codex_e2e",
        "live_claim_scope": "dev_only" if dev_metric is not None else "none",
        "dev_metric_present": dev_metric is not None,
        "holdout_metric_present": holdout_metric is not None,
        "holdout_result_scope": "rollout_context_only",
        "holdout_claim_allowed": False,
        "promotion_result_scope": "candidate_only_not_auto_promoted",
        "promotion_claim_allowed": False,
        "first_screen_claim_allowed": False,
        "blocked_claims": [
            "live_holdout_result_without_authority",
            "automatic_promotion",
            "first_screen_product_claim_without_owner_review",
        ],
    }


def _minimal_artifact_packet(
    evidence_graph: dict[str, Any],
    *,
    decision_candidates: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source_kind = str(evidence_graph.get("source_kind") or "unknown_source")
    return {
        "ok": True,
        "schema_version": "auto_research_artifact_packet_v0",
        "goal_id": evidence_graph.get("goal_id"),
        "source_kind": source_kind,
        "rollout_backed": source_kind == ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND,
        "source_map": [
            {
                "source_id": f"hypothesis:{node.get('hypothesis_id')}",
                "source_kind": node.get("source_kind") or source_kind,
                "todo_id": node.get("todo_id"),
                "claimed_by": node.get("claimed_by"),
                "status": node.get("status"),
            }
            for node in evidence_graph.get("nodes") or []
            if isinstance(node, dict)
        ],
        "decision_packet": {
            "schema_version": "auto_research_decision_packet_v0",
            "promotion_candidates": decision_candidates["promotion_candidates"],
            "retirement_candidates": decision_candidates["retirement_candidates"],
            "requires_operator_gate": bool(decision_candidates["promotion_candidates"]),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "raw_source_bodies_recorded": False,
            "source": source_kind,
        },
    }


def build_live_auto_research_projection(
    *,
    goal_id: str,
    agent_id: str,
    quota_payload: dict[str, Any],
    rollout_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    goal = _compact_public_token(goal_id, field="goal_id")
    agent = _compact_public_token(agent_id, field="agent_id")
    if not quota_payload.get("ok"):
        raise ValueError("quota payload must be ok for live auto-research projection")

    gate = quota_payload.get("capability_gate")
    if not isinstance(gate, dict):
        gate = {}
    runnable_candidates = [
        item for item in gate.get("runnable_candidates") or [] if isinstance(item, dict)
    ]
    blocked_candidates = [
        item for item in gate.get("blocked_candidates") or [] if isinstance(item, dict)
    ]
    selected_raw = quota_payload.get("agent_lane_next_action")
    selected = None
    if (
        isinstance(selected_raw, dict)
        and selected_raw.get("todo_id")
        and _claimed_by_current_or_unclaimed(selected_raw, agent_id=agent)
    ):
        selected = _todo_frontier_item(selected_raw, default_agent_id=agent)
    else:
        for item in runnable_candidates:
            if _claimed_by_current_or_unclaimed(item, agent_id=agent):
                selected = _todo_frontier_item(item, default_agent_id=agent)
                break

    runnable: list[dict[str, Any]] = []
    seen_todos: set[str] = set()
    for item in runnable_candidates:
        if not item.get("todo_id") or not _claimed_by_current_or_unclaimed(item, agent_id=agent):
            continue
        summary = _todo_frontier_item(item, default_agent_id=agent)
        if summary["todo_id"] in seen_todos:
            continue
        seen_todos.add(summary["todo_id"])
        runnable.append(summary)

    blocked: list[dict[str, Any]] = []
    other_claimed_context = [
        item
        for item in runnable_candidates
        if item.get("todo_id") and not _claimed_by_current_or_unclaimed(item, agent_id=agent)
    ]
    for item in [*other_claimed_context, *blocked_candidates][:12]:
        if not item.get("todo_id"):
            continue
        claimed_by = item.get("claimed_by")
        status = item.get("status") or "blocked"
        reason = f"claimed_by:{claimed_by}" if claimed_by and claimed_by != agent else f"status:{status}"
        blocked.append(_todo_frontier_item(item, default_agent_id=agent, blocked_by=reason))

    todo_graph = {
        "schema_version": RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION,
        "goal_id": goal,
        "hypothesis_count": len(runnable) + len(blocked),
        "evidence_event_count": 0,
        "todo_ids": sorted({item["todo_id"] for item in [*runnable, *blocked]}),
        "agent_ids": sorted({item["claimed_by"] for item in [*runnable, *blocked]}),
        "metric": {
            "name": "runnable_hypotheses",
            "direction": "maximize",
            "baseline": 0.0,
        },
        "baseline_metric": None,
        "best_dev_metric": None,
        "best_holdout_metric": None,
        "holdout_improved": False,
        "negative_evidence_count": 0,
        "needs_retry_count": 0,
        "nodes": [
            {
                "hypothesis_id": item["hypothesis_id"],
                "parent_hypothesis_id": None,
                "todo_id": item["todo_id"],
                "claimed_by": item["claimed_by"],
                "status": item["status"],
                "source_kind": item["source_kind"],
            }
            for item in [*runnable, *blocked]
        ],
        "source_kind": "loopx_live_quota_status",
    }
    rollout_graph = build_research_evidence_graph_from_rollout_events(
        goal_id=goal,
        rollout_events=rollout_events or [],
    )
    evidence_graph = (
        rollout_graph
        if rollout_graph["evidence_event_count"] or rollout_graph["hypothesis_count"]
        else todo_graph
    )
    decisions = build_research_decision_candidates(evidence_graph)
    source_kind = str(evidence_graph.get("source_kind") or "loopx_live_quota_status")
    claim_boundary = _public_claim_boundary(
        source_kind=source_kind,
        best_dev=evidence_graph.get("best_dev_metric"),
        best_holdout=evidence_graph.get("best_holdout_metric"),
    )
    frontier = {
        "schema_version": RESEARCH_FRONTIER_SCHEMA_VERSION,
        "goal_id": goal,
        "agent_id": agent,
        "selected": selected,
        "runnable": runnable,
        "blocked": blocked,
        "promotion_candidates": decisions["promotion_candidates"],
        "retirement_candidates": decisions["retirement_candidates"],
        "source_kind": "loopx_live_quota_status",
    }
    graph_metric = evidence_graph.get("metric") if isinstance(evidence_graph.get("metric"), dict) else {}
    showcase_projection = {
        "schema_version": RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION,
        "title": "LoopX Live Auto Research Frontier",
        "goal_id": goal,
        "objective": selected.get("title") if isinstance(selected, dict) else "No runnable hypothesis",
        "metric": {
            "name": graph_metric.get("name") or "runnable_hypotheses",
            "direction": graph_metric.get("direction") or "maximize",
            "baseline": graph_metric.get("baseline") or 0.0,
        },
        "best_dev_metric": evidence_graph.get("best_dev_metric"),
        "best_holdout_metric": evidence_graph.get("best_holdout_metric"),
        "holdout_improved": evidence_graph.get("holdout_improved"),
        "promotion_candidates": decisions["promotion_candidates"],
        "retirement_candidates": decisions["retirement_candidates"],
        "negative_evidence_count": evidence_graph.get("negative_evidence_count"),
        "claim_boundary": claim_boundary,
        "decentralized_pattern": (
            "todo_backed_live_frontier_rollout_evidence_graph"
            if source_kind == ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND
            else "todo_backed_live_frontier_agent_scoped_quota_projection"
        ),
        "source_kind": source_kind,
    }
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
        "source_schema_version": "loopx_live_quota_status_v0",
        "frontier": frontier,
        "evidence_graph": evidence_graph,
        "showcase_projection": showcase_projection,
        "artifact_packet": _minimal_artifact_packet(evidence_graph, decision_candidates=decisions),
        "public_claim_boundary": claim_boundary,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "source": (
                "live_quota_status_and_rollout_event_log"
                if source_kind == ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND
                else "live_quota_status_projection"
            ),
        },
    }
