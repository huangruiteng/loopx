"""Public-safe auto-research evidence packets and rollout events."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from ...rollout_event_log import build_rollout_event


RESEARCH_CONTRACT_SCHEMA_VERSION = "research_contract_v0"
RESEARCH_HYPOTHESIS_SCHEMA_VERSION = "research_hypothesis_v0"
RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION = "research_evidence_event_v0"
AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION = "auto_research_evidence_packet_v0"
AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION = "auto_research_rollout_append_v0"

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
    return {
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
