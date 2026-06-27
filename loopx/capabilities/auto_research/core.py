from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from ...rollout_event_log import build_rollout_event


AUTO_RESEARCH_FIXTURE_SCHEMA_VERSION = "decentralized_auto_research_fixture_v0"
RESEARCH_CONTRACT_SCHEMA_VERSION = "research_contract_v0"
RESEARCH_HYPOTHESIS_SCHEMA_VERSION = "research_hypothesis_v0"
RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION = "research_evidence_event_v0"
RESEARCH_FRONTIER_SCHEMA_VERSION = "decentralized_research_frontier_v0"
RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION = "research_evidence_graph_v0"
RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION = "research_showcase_projection_v0"
AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION = "decentralized_auto_research_projection_v0"
AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION = "auto_research_evidence_packet_v0"
AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION = "auto_research_rollout_append_v0"
ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND = "loopx_rollout_event_log"

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
NEGATIVE_PRIMARY_METRIC_STATUSES = {"failed", "regressed"}
RETRY_PRIMARY_METRIC_STATUSES = {"inconclusive"}

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


def _load_json_object(path: str | Path, *, field: str) -> dict[str, Any]:
    return _json_obj(json.loads(Path(path).expanduser().read_text(encoding="utf-8")), field=field)


def _eval_result_to_evidence_event(
    result: dict[str, Any],
    *,
    hypothesis_id: str,
    todo_id: str,
    agent_id: str,
    attempt: int,
    branch_ref: str | None = None,
) -> dict[str, Any]:
    result = _json_obj(result, field="eval_result")
    if result.get("no_upload") is False:
        raise ValueError("eval_result.no_upload must not be false for public auto-research evidence")
    metric = _json_obj(result.get("metric"), field="eval_result.metric")
    artifact_refs = _compact_public_text_list(result.get("artifact_refs"), field="eval_result.artifact_refs")
    if branch_ref:
        artifact_refs.append(f"branch:{_compact_public_text(branch_ref, field='branch_ref', max_len=160)}")
    event = {
        "schema_version": RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
        "hypothesis_id": hypothesis_id,
        "todo_id": todo_id,
        "agent_id": agent_id,
        "attempt": attempt,
        "split": result.get("split"),
        "metric": {
            "name": metric.get("name"),
            "value": metric.get("value"),
            "direction": metric.get("direction"),
        },
        "baseline_metric": metric.get("baseline", result.get("baseline_metric")),
        "eval_status": result.get("eval_status"),
        "primary_metric_status": result.get("primary_metric_status"),
        "artifact_refs": artifact_refs,
        "protected_scope_clean": bool(result.get("protected_scope_clean")),
    }
    return validate_research_evidence_event(event)


def _derive_hypothesis_status(events: list[dict[str, Any]]) -> str:
    if any(
        not event["protected_scope_clean"]
        or event["eval_status"] == "guardrail_failed"
        or event["primary_metric_status"] in NEGATIVE_PRIMARY_METRIC_STATUSES
        for event in events
    ):
        return "contradicted"
    if any(
        event["eval_status"] in {"failed_to_run", "inconclusive"}
        or event["primary_metric_status"] in RETRY_PRIMARY_METRIC_STATUSES
        for event in events
    ):
        return "needs_retry"
    if any(
        _metric_improved(
            value=event["metric"]["value"],
            baseline=event["baseline_metric"],
            direction=event["metric"]["direction"],
        )
        for event in events
        if event["eval_status"] == "scored"
    ):
        return "supported"
    return "active"


def _is_negative_evidence_event(event: dict[str, Any]) -> bool:
    return (
        not event["protected_scope_clean"]
        or event["eval_status"] == "guardrail_failed"
        or event["primary_metric_status"] in NEGATIVE_PRIMARY_METRIC_STATUSES
    )


def _is_retry_evidence_event(event: dict[str, Any]) -> bool:
    return (
        event["eval_status"] in {"failed_to_run", "inconclusive"}
        or event["primary_metric_status"] in RETRY_PRIMARY_METRIC_STATUSES
    )


def build_auto_research_evidence_packet(
    *,
    contract: dict[str, Any],
    eval_results: list[dict[str, Any]],
    hypothesis_id: str,
    todo_id: str,
    agent_id: str,
    claimed_by: str,
    mechanism_family: str,
    hypothesis: str,
    parent_hypothesis_id: str | None = None,
    grounding_refs: list[str] | None = None,
    novelty_audit_ref: str | None = None,
    branch_ref: str | None = None,
    attempt_start: int = 1,
) -> dict[str, Any]:
    """Build public-safe research hypothesis/evidence records from eval outputs."""

    contract = validate_research_contract(contract)
    if not eval_results:
        raise ValueError("at least one eval result is required")
    hypothesis_token = _compact_public_token(hypothesis_id, field="hypothesis_id")
    todo_token = _compact_public_token(todo_id, field="todo_id")
    agent_token = _compact_public_token(agent_id, field="agent_id")
    events = [
        _eval_result_to_evidence_event(
            result,
            hypothesis_id=hypothesis_token,
            todo_id=todo_token,
            agent_id=agent_token,
            attempt=attempt_start + index,
            branch_ref=branch_ref,
        )
        for index, result in enumerate(eval_results)
    ]
    status = _derive_hypothesis_status(events)
    blocked_by = []
    if status == "contradicted":
        blocked_by.append("evidence_or_boundary_guardrail_failed")
    hypothesis_node = validate_research_hypothesis(
        {
            "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            "hypothesis_id": hypothesis_token,
            "parent_hypothesis_id": parent_hypothesis_id,
            "todo_id": todo_token,
            "claimed_by": claimed_by,
            "mechanism_family": mechanism_family,
            "hypothesis": hypothesis,
            "status": status,
            "grounding_refs": grounding_refs or [],
            "novelty_audit_ref": novelty_audit_ref,
            "blocked_by": blocked_by,
        }
    )
    negative_count = len([event for event in events if _is_negative_evidence_event(event)])
    packet = {
        "ok": True,
        "schema_version": AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION,
        "research_contract": contract,
        "hypothesis": hypothesis_node,
        "evidence_events": events,
        "summary": {
            "goal_id": contract["goal_id"],
            "hypothesis_id": hypothesis_node["hypothesis_id"],
            "todo_id": hypothesis_node["todo_id"],
            "status": hypothesis_node["status"],
            "evidence_event_count": len(events),
            "splits": sorted({event["split"] for event in events}),
            "negative_evidence_count": negative_count,
            "needs_retry_count": len([event for event in events if _is_retry_evidence_event(event)]),
            "protected_scope_clean": all(event["protected_scope_clean"] for event in events),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "source": "public_eval_result_projection",
        },
    }
    return packet


def load_auto_research_evidence_packet_inputs(
    *,
    contract_path: str | Path,
    eval_result_paths: list[str | Path],
    **kwargs: Any,
) -> dict[str, Any]:
    return build_auto_research_evidence_packet(
        contract=_load_json_object(contract_path, field="research_contract_file"),
        eval_results=[
            _load_json_object(path, field="eval_result_file")
            for path in eval_result_paths
        ],
        **kwargs,
    )


def load_auto_research_evidence_packet(path: str | Path) -> dict[str, Any]:
    return validate_auto_research_evidence_packet(
        _load_json_object(path, field="auto_research_evidence_packet_file")
    )


def validate_auto_research_evidence_packet(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _json_obj(payload, field="auto_research_evidence_packet")
    schema = _compact_public_token(payload.get("schema_version"), field="schema_version")
    if schema != AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION}")
    if payload.get("ok") is False:
        raise ValueError("auto_research_evidence_packet.ok must not be false")
    contract = validate_research_contract(_json_obj(payload.get("research_contract"), field="research_contract"))
    hypothesis = validate_research_hypothesis(_json_obj(payload.get("hypothesis"), field="hypothesis"))
    evidence_events = [
        validate_research_evidence_event(_json_obj(item, field="evidence_events[]"))
        for item in _json_list(payload.get("evidence_events"), field="evidence_events")
    ]
    if not evidence_events:
        raise ValueError("auto_research_evidence_packet requires at least one evidence event")
    for event in evidence_events:
        if event["hypothesis_id"] != hypothesis["hypothesis_id"]:
            raise ValueError("evidence event hypothesis_id must match packet hypothesis")
        if event["todo_id"] != hypothesis["todo_id"]:
            raise ValueError("evidence event todo_id must match packet hypothesis")
    public_boundary = _json_obj(payload.get("public_boundary"), field="public_boundary")
    if public_boundary.get("raw_logs_recorded") or public_boundary.get("private_artifacts_recorded"):
        raise ValueError("auto_research_evidence_packet must not record raw logs or private artifacts")
    return {
        "ok": True,
        "schema_version": schema,
        "research_contract": contract,
        "hypothesis": hypothesis,
        "evidence_events": evidence_events,
        "summary": {
            "goal_id": contract["goal_id"],
            "hypothesis_id": hypothesis["hypothesis_id"],
            "todo_id": hypothesis["todo_id"],
            "status": hypothesis["status"],
            "evidence_event_count": len(evidence_events),
            "splits": sorted({event["split"] for event in evidence_events}),
            "negative_evidence_count": len(
                [event for event in evidence_events if _is_negative_evidence_event(event)]
            ),
            "needs_retry_count": len([event for event in evidence_events if _is_retry_evidence_event(event)]),
            "protected_scope_clean": all(event["protected_scope_clean"] for event in evidence_events),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "source": "public_eval_result_projection",
        },
    }


def build_auto_research_rollout_events(
    packet: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    packet = validate_auto_research_evidence_packet(packet)
    contract = packet["research_contract"]
    hypothesis = packet["hypothesis"]
    summary = packet["summary"]
    goal_id = contract["goal_id"]
    hypothesis_id = hypothesis["hypothesis_id"]
    claimed_by = hypothesis["claimed_by"]
    source_refs = [
        {"kind": "grounding", "id": ref}
        for ref in hypothesis.get("grounding_refs") or []
    ]
    if hypothesis.get("novelty_audit_ref"):
        source_refs.append({"kind": "novelty_audit", "id": hypothesis["novelty_audit_ref"]})
    events = [
        build_rollout_event(
            goal_id=goal_id,
            event_kind="research_hypothesis",
            agent_id=claimed_by,
            todo_id=hypothesis["todo_id"],
            lane_id=f"agent:{claimed_by}",
            agent_role="auto_research_lane",
            status=hypothesis["status"],
            classification=RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            labels=[
                "auto_research",
                "research_hypothesis",
                hypothesis["status"],
                hypothesis["mechanism_family"],
            ],
            summary=(
                f"auto-research hypothesis {hypothesis_id} status={hypothesis['status']}: "
                f"{hypothesis['hypothesis']}"
            ),
            source_refs=source_refs,
            details={
                "hypothesis_id": hypothesis_id,
                "parent_hypothesis_id": hypothesis.get("parent_hypothesis_id") or "",
                "mechanism_family": hypothesis["mechanism_family"],
                "evidence_event_count": summary["evidence_event_count"],
                "negative_evidence_count": summary["negative_evidence_count"],
                "needs_retry_count": summary["needs_retry_count"],
                "protected_scope_clean": summary["protected_scope_clean"],
            },
            recorded_at=recorded_at,
        )
    ]
    for evidence in packet["evidence_events"]:
        metric = evidence["metric"]
        events.append(
            build_rollout_event(
                goal_id=goal_id,
                event_kind="research_evidence",
                agent_id=evidence["agent_id"],
                todo_id=evidence["todo_id"],
                run_id=f"{evidence['hypothesis_id']}:{evidence['attempt']}:{evidence['split']}",
                lane_id=f"agent:{evidence['agent_id']}",
                agent_role="auto_research_lane",
                status=evidence["eval_status"],
                classification=RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
                labels=[
                    "auto_research",
                    "research_evidence",
                    evidence["split"],
                    evidence["eval_status"],
                    evidence["primary_metric_status"],
                ],
                summary=(
                    f"auto-research evidence {evidence['hypothesis_id']} "
                    f"split={evidence['split']} status={evidence['primary_metric_status']} "
                    f"value={metric['value']}"
                ),
                artifact_refs=evidence["artifact_refs"],
                details={
                    "hypothesis_id": evidence["hypothesis_id"],
                    "attempt": evidence["attempt"],
                    "split": evidence["split"],
                    "metric_name": metric["name"],
                    "metric_value": metric["value"],
                    "metric_direction": metric["direction"],
                    "baseline_metric": evidence["baseline_metric"],
                    "primary_metric_status": evidence["primary_metric_status"],
                    "eval_status": evidence["eval_status"],
                    "protected_scope_clean": evidence["protected_scope_clean"],
                },
                recorded_at=recorded_at,
            )
        )
    return events


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
    """Render a read-only auto-research frontier from live LoopX quota state.

    This intentionally consumes the existing quota/status projection instead of
    parsing ACTIVE_GOAL_STATE.md directly. The source of truth stays in the
    LoopX control plane; auto-research only reframes todo-backed work as a
    decentralized research frontier.
    """

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
        if not item.get("todo_id"):
            continue
        if not _claimed_by_current_or_unclaimed(item, agent_id=agent):
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

    nodes = [
        {
            "hypothesis_id": item["hypothesis_id"],
            "parent_hypothesis_id": None,
            "todo_id": item["todo_id"],
            "claimed_by": item["claimed_by"],
            "status": item["status"],
            "source_kind": item["source_kind"],
        }
        for item in [*runnable, *blocked]
    ]
    agent_ids = sorted({item["claimed_by"] for item in [*runnable, *blocked]})
    todo_ids = sorted({item["todo_id"] for item in [*runnable, *blocked]})
    todo_evidence_graph = {
        "schema_version": RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION,
        "goal_id": goal,
        "hypothesis_count": len(nodes),
        "evidence_event_count": 0,
        "todo_ids": todo_ids,
        "agent_ids": agent_ids,
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
        "nodes": nodes,
        "source_kind": "loopx_live_quota_status",
    }
    rollout_evidence_graph = build_research_evidence_graph_from_rollout_events(
        goal_id=goal,
        rollout_events=rollout_events or [],
    )
    if rollout_evidence_graph["evidence_event_count"] or rollout_evidence_graph["hypothesis_count"]:
        evidence_graph = rollout_evidence_graph
    else:
        evidence_graph = todo_evidence_graph
    frontier = {
        "schema_version": RESEARCH_FRONTIER_SCHEMA_VERSION,
        "goal_id": goal,
        "agent_id": agent,
        "selected": selected,
        "runnable": runnable,
        "blocked": blocked,
        "promotion_candidates": [],
        "source_kind": "loopx_live_quota_status",
    }
    selected_title = selected.get("title") if isinstance(selected, dict) else "No runnable hypothesis"
    graph_metric = evidence_graph.get("metric") if isinstance(evidence_graph.get("metric"), dict) else {}
    source_kind = str(evidence_graph.get("source_kind") or "loopx_live_quota_status")
    showcase_projection = {
        "schema_version": RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION,
        "title": "LoopX Live Auto Research Frontier",
        "goal_id": goal,
        "objective": selected_title,
        "metric": {
            "name": graph_metric.get("name") or "runnable_hypotheses",
            "direction": graph_metric.get("direction") or "maximize",
            "baseline": graph_metric.get("baseline") or 0.0,
        },
        "baseline_metric": evidence_graph.get("baseline_metric"),
        "best_dev_metric": evidence_graph.get("best_dev_metric"),
        "best_holdout_metric": evidence_graph.get("best_holdout_metric"),
        "holdout_improved": evidence_graph.get("holdout_improved"),
        "promoted_hypotheses": [],
        "retired_or_contradicted_hypotheses": [],
        "negative_evidence_count": evidence_graph.get("negative_evidence_count"),
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
        "negative_evidence_count": len(
            [
                event
                for event in events
                if event["primary_metric_status"] in {"regressed", "failed", "inconclusive"}
                or event["eval_status"] != "scored"
            ]
        ),
        "needs_retry_count": len([item for item in hypotheses if item["status"] == "needs_retry"]),
        "nodes": [
            {
                "hypothesis_id": item["hypothesis_id"],
                "parent_hypothesis_id": item["parent_hypothesis_id"],
                "todo_id": item["todo_id"],
                "claimed_by": item["claimed_by"],
                "status": item["status"],
            }
            for item in hypotheses
        ],
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


def render_auto_research_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    if payload.get("schema_version") == AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION:
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
    if payload.get("schema_version") == AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION:
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
    return render_auto_research_projection_markdown(payload)
