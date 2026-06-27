from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION = "decentralized_auto_research_fixture_v0"
RESEARCH_CONTRACT_SCHEMA_VERSION = "research_contract_v0"
RESEARCH_HYPOTHESIS_SCHEMA_VERSION = "research_hypothesis_v0"
RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION = "research_evidence_event_v0"
RESEARCH_FRONTIER_SCHEMA_VERSION = "decentralized_research_frontier_v0"
RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION = "research_evidence_graph_v0"
RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION = "research_showcase_projection_v0"
AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION = "decentralized_auto_research_projection_v0"

HYPOTHESIS_STATUSES = {
    "proposed",
    "active",
    "running",
    "needs_retry",
    "supported",
    "contradicted",
    "promoted",
    "retired",
}
EVIDENCE_STATUSES = {
    "scored",
    "failed_to_run",
    "guardrail_failed",
    "inconclusive",
}
METRIC_DIRECTIONS = {"maximize", "minimize"}

_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,95}$")
_ABSOLUTE_PATH_RE = re.compile(
    r"(^|[\s:=])(?:"
    + "/" + "Users/"
    + "|/" + "private/"
    + "|/" + "tmp/"
    + "|~[/\\s]|[A-Za-z]:\\\\)"
)
_URL_OR_REMOTE_PATH_RE = re.compile(r"(?i)\b(?:file|s3|gs|tos|hdfs)://")
_PRIVATE_MARKER_TERMS = [
    "author" + "ization:",
    r"bearer\s+[A-Za-z0-9._-]+",
    r"api[_-]?" + "key",
    "pass" + "word",
    "sec" + "ret",
    r"begin (?:rsa |open)?private " + "key",
    "lark" + "office",
    r"fei" + r"shu\.cn",
    "byte" + "dance",
]
_PRIVATE_MARKER_RE = re.compile(r"(?i)(" + "|".join(_PRIVATE_MARKER_TERMS) + ")")


def _compact_public_text(value: Any, *, field: str, max_len: int = 240) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > max_len:
        raise ValueError(f"{field} is too long for a compact public-safe field")
    if ".." in text:
        raise ValueError(f"{field} must not contain parent-directory markers")
    if _ABSOLUTE_PATH_RE.search(text) or text.startswith(("/", "~")):
        raise ValueError(f"{field} must use a public alias, not a local/private path")
    if _URL_OR_REMOTE_PATH_RE.search(text):
        raise ValueError(f"{field} must use a public alias, not a raw remote path")
    if _PRIVATE_MARKER_RE.search(text):
        raise ValueError(f"{field} contains a private or credential-like marker")
    return text


def _compact_public_token(value: Any, *, field: str) -> str:
    token = _compact_public_text(value, field=field, max_len=96)
    if not _TOKEN_RE.match(token):
        raise ValueError(
            f"{field} must be a compact public token using letters, digits, dot, colon, dash, or underscore"
        )
    return token


def _compact_public_text_list(values: Iterable[Any] | None, *, field: str) -> list[str]:
    return [_compact_public_text(value, field=f"{field}[]") for value in values or []]


def _finite_float(value: float | int | str | None, *, field: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _json_obj(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _json_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON list")
    return value


def _metric_improved(
    *,
    value: float | None,
    baseline: float | None,
    direction: str,
) -> bool:
    if value is None or baseline is None:
        return False
    return value > baseline if direction == "maximize" else value < baseline


def _metric_rank_key(value: float | None, *, direction: str) -> float:
    if value is None:
        return float("-inf")
    return value if direction == "maximize" else -value


def load_auto_research_fixture(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    return validate_auto_research_fixture(payload)


def validate_auto_research_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _json_obj(payload, field="fixture")
    schema = _compact_public_token(payload.get("schema_version"), field="schema_version")
    if schema != AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION}")

    contract = validate_research_contract(_json_obj(payload.get("research_contract"), field="research_contract"))
    hypotheses = [
        validate_research_hypothesis(_json_obj(item, field="hypotheses[]"))
        for item in _json_list(payload.get("hypotheses"), field="hypotheses")
    ]
    evidence_events = [
        validate_research_evidence_event(_json_obj(item, field="evidence_events[]"))
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


def validate_research_contract(contract: dict[str, Any]) -> dict[str, Any]:
    schema = _compact_public_token(contract.get("schema_version"), field="research_contract.schema_version")
    if schema != RESEARCH_CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"research_contract.schema_version must be {RESEARCH_CONTRACT_SCHEMA_VERSION}")
    metric = _json_obj(contract.get("metric"), field="research_contract.metric")
    direction = _compact_public_token(metric.get("direction"), field="metric.direction")
    if direction not in METRIC_DIRECTIONS:
        raise ValueError("metric.direction must be maximize or minimize")
    return {
        "schema_version": schema,
        "goal_id": _compact_public_token(contract.get("goal_id"), field="goal_id"),
        "research_objective": _compact_public_text(contract.get("research_objective"), field="research_objective"),
        "editable_scope": _compact_public_text_list(contract.get("editable_scope"), field="editable_scope"),
        "protected_scope": _compact_public_text_list(contract.get("protected_scope"), field="protected_scope"),
        "metric": {
            "name": _compact_public_token(metric.get("name"), field="metric.name"),
            "direction": direction,
            "baseline": _finite_float(metric.get("baseline"), field="metric.baseline"),
        },
        "dev_eval": _compact_public_text(contract.get("dev_eval"), field="dev_eval"),
        "holdout_eval": _compact_public_text(contract.get("holdout_eval"), field="holdout_eval"),
        "promotion_policy": _compact_public_token(contract.get("promotion_policy"), field="promotion_policy"),
    }


def validate_research_hypothesis(item: dict[str, Any]) -> dict[str, Any]:
    schema = _compact_public_token(item.get("schema_version"), field="hypothesis.schema_version")
    if schema != RESEARCH_HYPOTHESIS_SCHEMA_VERSION:
        raise ValueError(f"hypothesis.schema_version must be {RESEARCH_HYPOTHESIS_SCHEMA_VERSION}")
    status = _compact_public_token(item.get("status"), field="hypothesis.status")
    if status not in HYPOTHESIS_STATUSES:
        raise ValueError(f"hypothesis.status must be one of {', '.join(sorted(HYPOTHESIS_STATUSES))}")
    return {
        "schema_version": schema,
        "hypothesis_id": _compact_public_token(item.get("hypothesis_id"), field="hypothesis_id"),
        "parent_hypothesis_id": (
            _compact_public_token(item.get("parent_hypothesis_id"), field="parent_hypothesis_id")
            if item.get("parent_hypothesis_id")
            else None
        ),
        "todo_id": _compact_public_token(item.get("todo_id"), field="todo_id"),
        "claimed_by": _compact_public_token(item.get("claimed_by"), field="claimed_by"),
        "mechanism_family": _compact_public_text(item.get("mechanism_family"), field="mechanism_family"),
        "hypothesis": _compact_public_text(item.get("hypothesis"), field="hypothesis"),
        "status": status,
        "grounding_refs": _compact_public_text_list(item.get("grounding_refs"), field="grounding_refs"),
        "novelty_audit_ref": (
            _compact_public_text(item.get("novelty_audit_ref"), field="novelty_audit_ref")
            if item.get("novelty_audit_ref")
            else None
        ),
        "blocked_by": _compact_public_text_list(item.get("blocked_by"), field="blocked_by"),
    }


def validate_research_evidence_event(item: dict[str, Any]) -> dict[str, Any]:
    schema = _compact_public_token(item.get("schema_version"), field="evidence.schema_version")
    if schema != RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION:
        raise ValueError(f"evidence.schema_version must be {RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION}")
    eval_status = _compact_public_token(item.get("eval_status"), field="eval_status")
    if eval_status not in EVIDENCE_STATUSES:
        raise ValueError(f"eval_status must be one of {', '.join(sorted(EVIDENCE_STATUSES))}")
    metric = _json_obj(item.get("metric"), field="evidence.metric")
    direction = _compact_public_token(metric.get("direction"), field="evidence.metric.direction")
    if direction not in METRIC_DIRECTIONS:
        raise ValueError("evidence.metric.direction must be maximize or minimize")
    return {
        "schema_version": schema,
        "hypothesis_id": _compact_public_token(item.get("hypothesis_id"), field="hypothesis_id"),
        "todo_id": _compact_public_token(item.get("todo_id"), field="todo_id"),
        "agent_id": _compact_public_token(item.get("agent_id"), field="agent_id"),
        "attempt": int(item.get("attempt") or 1),
        "split": _compact_public_token(item.get("split"), field="split"),
        "metric": {
            "name": _compact_public_token(metric.get("name"), field="evidence.metric.name"),
            "value": _finite_float(metric.get("value"), field="evidence.metric.value"),
            "direction": direction,
        },
        "baseline_metric": _finite_float(item.get("baseline_metric"), field="baseline_metric"),
        "eval_status": eval_status,
        "primary_metric_status": _compact_public_token(
            item.get("primary_metric_status"),
            field="primary_metric_status",
        ),
        "artifact_refs": _compact_public_text_list(item.get("artifact_refs"), field="artifact_refs"),
        "protected_scope_clean": bool(item.get("protected_scope_clean")),
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
    direction = contract["metric"]["direction"]
    baseline = contract["metric"]["baseline"]
    hypotheses = fixture["hypotheses"]
    events = fixture["evidence_events"]

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

    promotion_candidates = []
    for item in hypotheses:
        item_events = [event for event in events if event["hypothesis_id"] == item["hypothesis_id"]]
        dev_best = _best_metric(item_events, split="dev", direction=direction)
        holdout_best = _best_metric(item_events, split="holdout", direction=direction)
        if item["status"] in {"supported", "promoted"} or _metric_improved(
            value=dev_best,
            baseline=baseline,
            direction=direction,
        ):
            requires = ["boundary_scan"]
            if not _metric_improved(value=holdout_best, baseline=baseline, direction=direction):
                requires.append("holdout_eval")
            promotion_candidates.append(
                {
                    "hypothesis_id": item["hypothesis_id"],
                    "todo_id": item["todo_id"],
                    "dev_metric": dev_best,
                    "holdout_metric": holdout_best,
                    "requires": requires,
                }
            )

    frontier = {
        "schema_version": RESEARCH_FRONTIER_SCHEMA_VERSION,
        "goal_id": contract["goal_id"],
        "agent_id": agent,
        "selected": selected,
        "runnable": runnable,
        "blocked": blocked,
        "promotion_candidates": promotion_candidates,
    }
    evidence_graph = build_research_evidence_graph(fixture)
    showcase_projection = build_research_showcase_projection(fixture, evidence_graph=evidence_graph)
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
        "source_schema_version": fixture["schema_version"],
        "frontier": frontier,
        "evidence_graph": evidence_graph,
        "showcase_projection": showcase_projection,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "source": "public_fixture",
        },
    }


def _best_metric(events: list[dict[str, Any]], *, split: str, direction: str) -> float | None:
    values = [
        event["metric"]["value"]
        for event in events
        if event["split"] == split and event["eval_status"] == "scored"
    ]
    if not values:
        return None
    return max(values, key=lambda value: _metric_rank_key(value, direction=direction))


def build_research_evidence_graph(fixture: dict[str, Any]) -> dict[str, Any]:
    contract = fixture["research_contract"]
    direction = contract["metric"]["direction"]
    events = fixture["evidence_events"]
    baseline = contract["metric"]["baseline"]
    scored_events = [event for event in events if event["eval_status"] == "scored"]
    best_dev = _best_metric(scored_events, split="dev", direction=direction)
    best_holdout = _best_metric(scored_events, split="holdout", direction=direction)
    return {
        "schema_version": RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION,
        "goal_id": contract["goal_id"],
        "hypothesis_count": len(fixture["hypotheses"]),
        "evidence_event_count": len(events),
        "todo_ids": sorted({item["todo_id"] for item in fixture["hypotheses"]}),
        "agent_ids": sorted({item["claimed_by"] for item in fixture["hypotheses"]}),
        "baseline_metric": baseline,
        "best_dev_metric": best_dev,
        "best_holdout_metric": best_holdout,
        "holdout_improved": _metric_improved(value=best_holdout, baseline=baseline, direction=direction),
        "negative_evidence_count": len(
            [
                event
                for event in events
                if event["primary_metric_status"] in {"regressed", "failed", "inconclusive"}
                or event["eval_status"] != "scored"
            ]
        ),
        "needs_retry_count": len([item for item in fixture["hypotheses"] if item["status"] == "needs_retry"]),
        "nodes": [
            {
                "hypothesis_id": item["hypothesis_id"],
                "parent_hypothesis_id": item["parent_hypothesis_id"],
                "todo_id": item["todo_id"],
                "claimed_by": item["claimed_by"],
                "status": item["status"],
            }
            for item in fixture["hypotheses"]
        ],
    }


def build_research_showcase_projection(
    fixture: dict[str, Any],
    *,
    evidence_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = fixture["research_contract"]
    graph = evidence_graph or build_research_evidence_graph(fixture)
    promoted = [
        item["hypothesis_id"]
        for item in fixture["hypotheses"]
        if item["status"] == "promoted"
    ]
    retired = [
        item["hypothesis_id"]
        for item in fixture["hypotheses"]
        if item["status"] in {"retired", "contradicted"}
    ]
    return {
        "schema_version": RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION,
        "title": "Decentralized Auto Research: k-NN Speedup",
        "goal_id": contract["goal_id"],
        "objective": contract["research_objective"],
        "metric": contract["metric"],
        "baseline_metric": graph["baseline_metric"],
        "best_dev_metric": graph["best_dev_metric"],
        "best_holdout_metric": graph["best_holdout_metric"],
        "holdout_improved": graph["holdout_improved"],
        "promoted_hypotheses": promoted,
        "retired_or_contradicted_hypotheses": retired,
        "negative_evidence_count": graph["negative_evidence_count"],
        "decentralized_pattern": "todo_linked_hypotheses_agent_scoped_frontier_shared_evidence_graph",
    }


def render_auto_research_projection_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    frontier = payload["frontier"]  # type: ignore[index]
    graph = payload["evidence_graph"]  # type: ignore[index]
    showcase = payload["showcase_projection"]  # type: ignore[index]
    selected = frontier.get("selected") if isinstance(frontier, dict) else None
    lines = [
        "# LoopX Auto Research Frontier",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- agent_id: `{frontier.get('agent_id')}`",
        f"- title: {showcase.get('title')}",
        f"- selected: `{selected.get('hypothesis_id') if isinstance(selected, dict) else 'none'}`",
        f"- hypotheses: `{graph.get('hypothesis_count')}`",
        f"- evidence events: `{graph.get('evidence_event_count')}`",
        f"- best dev metric: `{graph.get('best_dev_metric')}`",
        f"- best holdout metric: `{graph.get('best_holdout_metric')}`",
        f"- holdout improved: `{graph.get('holdout_improved')}`",
    ]
    return "\n".join(lines) + "\n"
