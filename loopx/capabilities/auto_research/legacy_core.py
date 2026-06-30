from __future__ import annotations

import json
import math
import re
import shlex
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
AUTO_RESEARCH_ARTIFACT_PACKET_SCHEMA_VERSION = "auto_research_artifact_packet_v0"
AUTO_RESEARCH_BOARD_SCHEMA_VERSION = "auto_research_frontstage_board_v0"
AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION = "auto_research_rollout_append_v0"
AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION = "auto_research_quickstart_v0"
AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION = "auto_research_demo_supervisor_plan_v0"
AUTO_RESEARCH_DEMO_ACCEPTANCE_PACKET_SCHEMA_VERSION = "auto_research_demo_acceptance_packet_v0"
AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION = "auto_research_demo_e2e_result_v0"
AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION = "auto_research_role_profile_v0"
AUTO_RESEARCH_PUBLIC_CLAIM_BOUNDARY_SCHEMA_VERSION = "auto_research_public_claim_boundary_v0"
AUTO_RESEARCH_DEFAULT_GOAL_ID = "loopx-auto-research-knn"
AUTO_RESEARCH_DEFAULT_OBJECTIVE = "Improve exact k-nearest-neighbor inference under a protected evaluator."
AUTO_RESEARCH_QUICKSTART_TEMPLATE = "knn-exact"
ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND = "loopx_rollout_event_log"
AUTO_RESEARCH_DEMO_DEFAULT_LANES = (
    (
        "codex-product-capability",
        "research-curator",
        "research_curator",
        "Keep the research contract, protected boundary, metric, stop policy, evidence review, and operator gates explicit.",
    ),
    (
        "codex-side-bypass",
        "hypothesis-mapper",
        "hypothesis_mapper",
        "Turn research ideas into todo-backed hypotheses, successor links, and retirement rationale.",
    ),
    (
        "codex-main-control",
        "evidence-runner",
        "evidence_runner",
        "Execute one selected hypothesis under an isolated attempt boundary and preserve scored or unscored evidence.",
    ),
)
AUTO_RESEARCH_ROLE_PROFILE_REF = AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION
AUTO_RESEARCH_REQUIRED_SKILL = "loopx-auto-research"
AUTO_RESEARCH_ROLE_PROFILE_ORDER = (
    "research_curator",
    "hypothesis_mapper",
    "evidence_runner",
    "evidence_verifier",
)
AUTO_RESEARCH_ROLE_PROFILE_TEMPLATES: dict[str, dict[str, Any]] = {
    "research_curator": {
        "display_name": "Research curator",
        "phase": "contract_ready",
        "skill_section": "Research curator",
        "allowed_actions": [
            "write_research_contract",
            "record_protected_boundary",
            "open_operator_gate_todo",
            "request_public_projection",
        ],
        "write_scope": [
            "research_contract_v0",
            "protected_boundary_notes",
            "owner_gate_todos",
            "public_projection_requests",
        ],
        "protected_scope": [
            "experiment_execution",
            "promotion_decision_without_evidence",
            "public_first_screen_without_owner_review",
        ],
        "stop_conditions": [
            "the next step would pick a winner",
            "the next step would run an experiment",
            "the next step would publish unsupported evidence",
            "operator gate is projected",
        ],
        "handoff_outputs": [
            "research_contract_v0",
            "protected_boundary_note",
            "operator_gate_todo",
        ],
    },
    "hypothesis_mapper": {
        "display_name": "Hypothesis mapper",
        "phase": "hypothesis_proposed",
        "skill_section": "Hypothesis mapper",
        "allowed_actions": [
            "propose_hypothesis",
            "link_parent_hypothesis",
            "open_successor_todo",
            "record_no_followup_rationale",
        ],
        "write_scope": [
            "research_hypothesis_v0",
            "successor_todos",
            "grounding_refs",
            "no_followup_rationale",
        ],
        "protected_scope": [
            "evidence_execution",
            "evidence_deletion",
            "novelty_claim_from_ideation_source",
        ],
        "stop_conditions": [
            "novelty requires the same source that inspired the idea",
            "negative evidence would be hidden",
            "quota frontier is empty or claimed by another agent",
            "operator gate is projected",
        ],
        "handoff_outputs": [
            "research_hypothesis_v0",
            "successor_todo",
            "retirement_or_no_followup_rationale",
        ],
    },
    "evidence_runner": {
        "display_name": "Evidence runner",
        "phase": "attempt_running",
        "skill_section": "Evidence runner",
        "allowed_actions": [
            "claim_attempt",
            "edit_allowed_scope",
            "run_dev_eval",
            "write_evidence",
        ],
        "write_scope": [
            "claimed_hypothesis_worktree",
            "branch_refs",
            "research_evidence_event_v0",
            "retry_packets",
        ],
        "protected_scope": [
            "protected_evaluator",
            "promotion_gate",
            "raw_private_artifacts",
            "credentials",
        ],
        "stop_conditions": [
            "protected scope would be edited",
            "promotion decision is needed",
            "private material or credentials are required",
            "quota should-run returns false",
        ],
        "handoff_outputs": [
            "research_evidence_event_v0",
            "branch_or_artifact_ref",
            "retry_or_retirement_rationale",
        ],
    },
    "evidence_verifier": {
        "display_name": "Evidence verifier",
        "phase": "evaluated",
        "skill_section": "Evidence verifier",
        "allowed_actions": [
            "classify_evidence",
            "write_evaluation_summary",
            "open_promotion_gate",
            "open_retirement_candidate",
        ],
        "write_scope": [
            "evaluation_summary",
            "promotion_candidate",
            "retirement_candidate",
            "gate_todos",
            "projection_ready_evidence",
        ],
        "protected_scope": [
            "experiment_execution",
            "dev_only_promotion",
            "gate_bypass",
            "hidden_negative_evidence",
        ],
        "stop_conditions": [
            "held-out evidence is missing when required",
            "dev-only lift would be presented as promoted",
            "operator gate is projected",
            "public/private boundary is unclear",
        ],
        "handoff_outputs": [
            "evaluation_summary",
            "promotion_or_retirement_candidate",
            "gate_todo",
        ],
    },
}
AUTO_RESEARCH_ROLE_PROFILE_ALIASES = {
    "curator": "research_curator",
    "research-curator": "research_curator",
    "research_curator": "research_curator",
    "hypothesis-runner": "hypothesis_mapper",
    "hypothesis-mapper": "hypothesis_mapper",
    "hypothesis_mapper": "hypothesis_mapper",
    "mapper": "hypothesis_mapper",
    "runner": "evidence_runner",
    "evidence-runner": "evidence_runner",
    "evidence_runner": "evidence_runner",
    "executor": "evidence_runner",
    "promoter": "evidence_verifier",
    "evidence-promoter": "evidence_verifier",
    "evidence-verifier": "evidence_verifier",
    "evidence_verifier": "evidence_verifier",
    "verifier": "evidence_verifier",
    "control-plane-guard": "research_curator",
}

AUTO_RESEARCH_DEMO_LANE_PROFILES: dict[str, dict[str, Any]] = {
    "hypothesis-runner": {
        "role_id": "evidence_runner",
        "display_name": "Hypothesis runner",
        "phase": "frontier_selected",
        "capability_token": "evidence_runner",
        "allowed_actions": [
            "claim_attempt",
            "edit_allowed_scope",
            "run_dev_eval",
            "write_evidence",
        ],
        "write_scope": ["examples/auto_research_knn_pack/**", "experiments/**", "solution.py"],
        "protected_scope": ["protected_eval.py", "eval.py", "data/**"],
        "skill_section": "Evidence runner",
        "handoff_outputs": [
            "auto_research_evidence_packet_v0",
            "branch_or_artifact_ref",
            "retry_or_retirement_rationale",
        ],
    },
    "evidence-promoter": {
        "role_id": "evidence_verifier",
        "display_name": "Evidence promoter",
        "phase": "evidence_recorded",
        "capability_token": "evidence_verifier",
        "allowed_actions": [
            "classify_evidence",
            "write_promotion_candidate",
            "write_retirement_candidate",
            "write_gate_todo",
        ],
        "write_scope": [
            "research_evidence_event_v0",
            "promotion_candidates/**",
            "retirement_candidates/**",
        ],
        "protected_scope": ["protected_eval.py", "eval.py", "data/**"],
        "skill_section": "Evidence verifier",
        "handoff_outputs": [
            "evaluation_summary",
            "promotion_or_retirement_candidate",
            "gate_todo",
        ],
    },
    "control-plane-guard": {
        "role_id": "research_curator",
        "display_name": "Control-plane guard",
        "phase": "contract_ready",
        "capability_token": "research_curator",
        "allowed_actions": [
            "run_quota_status_check",
            "validate_public_boundary",
            "record_gate_or_blocker",
            "verify_takeover_controls",
        ],
        "write_scope": ["research_contract_v0", "gate_todos/**", "boundary_notes/**"],
        "protected_scope": ["credentials", "raw_logs", "session_files", "private_material"],
        "skill_section": "Control-plane guard",
        "handoff_outputs": [
            "boundary_check",
            "operator_gate_todo",
            "takeover_acceptance_note",
        ],
    },
    "research-narrator": {
        "role_id": "product_narrator",
        "display_name": "Research narrator",
        "phase": "research_showcase_projection_v0",
        "capability_token": "product_narrator",
        "allowed_actions": [
            "render_read_only_projection",
            "summarize_promoted_retired_retry_evidence",
            "request_first_screen_review",
        ],
        "write_scope": ["research_showcase_projection_v0", "docs/product/**", "apps/dashboard/**"],
        "protected_scope": ["raw_logs", "private_material", "protected_eval.py", "data/**"],
        "skill_section": "Projection narrator",
        "handoff_outputs": [
            "research_showcase_projection_v0",
            "public_safe_value_summary",
            "first_screen_review_request",
        ],
    },
}

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


def _relative_pack_dir(value: Any) -> Path:
    text = _compact_public_text(value, field="output_dir", max_len=160)
    if "\\" in text:
        raise ValueError("output_dir must use forward-slash relative paths")
    path = Path(text)
    if path.is_absolute():
        raise ValueError("output_dir must be relative")
    if not path.parts:
        raise ValueError("output_dir must be non-empty")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("output_dir must not contain current or parent-directory markers")
    return path


def _shell_arg(value: str) -> str:
    return shlex.quote(value)


def _role_id_for_lane(*, lane_id: str, index: int, explicit_role_id: str | None = None) -> str:
    raw = explicit_role_id or lane_id
    role_id = AUTO_RESEARCH_ROLE_PROFILE_ALIASES.get(raw, raw)
    if role_id in AUTO_RESEARCH_ROLE_PROFILE_TEMPLATES:
        return role_id
    if explicit_role_id is not None:
        allowed = ", ".join(AUTO_RESEARCH_ROLE_PROFILE_ORDER)
        raise ValueError(f"agent[] role_id must be one of: {allowed}")
    return AUTO_RESEARCH_ROLE_PROFILE_ORDER[(index - 1) % len(AUTO_RESEARCH_ROLE_PROFILE_ORDER)]


def _demo_lane_specs(agent_specs: Iterable[str] | None) -> list[dict[str, str]]:
    raw_specs = list(agent_specs or [])
    parsed_specs: list[tuple[str, str, str, str]] = []
    if raw_specs:
        for index, raw in enumerate(raw_specs, start=1):
            text = _compact_public_text(raw, field="agent[]", max_len=180)
            if ":" in text:
                parts = text.split(":")
                if len(parts) == 2:
                    agent_id, lane_id = parts
                    explicit_role_id = None
                elif len(parts) == 3:
                    agent_id, lane_id, explicit_role_id = parts
                else:
                    raise ValueError("agent[] must be agent_id:lane_id or agent_id:lane_id:role_id")
            else:
                agent_id = text
                lane_id = f"research-lane-{index}"
                explicit_role_id = None
            parsed_specs.append(
                (
                    _compact_public_token(agent_id, field="agent_id"),
                    _compact_public_token(lane_id, field="lane_id"),
                    _compact_public_token(
                        _role_id_for_lane(
                            lane_id=lane_id,
                            index=index,
                            explicit_role_id=explicit_role_id,
                        ),
                        field="role_id",
                    ),
                    "Work from the shared LoopX frontier for this lane; do not assume a leader agent.",
                )
            )
    else:
        parsed_specs = list(AUTO_RESEARCH_DEMO_DEFAULT_LANES)

    lanes: list[dict[str, str]] = []
    seen_agents: set[str] = set()
    seen_lanes: set[str] = set()
    for agent_id, lane_id, role_id, responsibility in parsed_specs:
        if agent_id in seen_agents:
            raise ValueError(f"duplicate agent_id in demo supervisor lane plan: {agent_id}")
        if lane_id in seen_lanes:
            raise ValueError(f"duplicate lane_id in demo supervisor lane plan: {lane_id}")
        seen_agents.add(agent_id)
        seen_lanes.add(lane_id)
        lanes.append(
            {
                "agent_id": agent_id,
                "lane_id": lane_id,
                "role_id": role_id,
                "responsibility": _compact_public_text(
                    responsibility,
                    field="lane.responsibility",
                    max_len=180,
                ),
            }
        )
    return lanes


def _env_quota_command(*, cli_bin: str, goal_id: str, agent_id: str) -> str:
    return (
        f"{_shell_arg(cli_bin)} --format json "
        "--registry \"$LOOPX_REGISTRY\" --runtime-root \"$LOOPX_RUNTIME_ROOT\" "
        f"quota should-run --goal-id {_shell_arg(goal_id)} --agent-id {_shell_arg(agent_id)}"
    )


def _env_frontier_command(*, cli_bin: str, goal_id: str, agent_id: str) -> str:
    return (
        f"{_shell_arg(cli_bin)} --format json "
        "--registry \"$LOOPX_REGISTRY\" --runtime-root \"$LOOPX_RUNTIME_ROOT\" "
        f"auto-research frontier --goal-id {_shell_arg(goal_id)} --agent-id {_shell_arg(agent_id)}"
    )


def _compact_prompt_list(items: Any) -> str:
    if not isinstance(items, list):
        return "none"
    values = [
        _compact_public_text(str(item), field="bootstrap_prompt.list_item", max_len=100)
        for item in items
        if str(item).strip()
    ]
    return ", ".join(values) if values else "none"


def _auto_research_codex_bootstrap_prompt(
    *,
    goal_id: str,
    lane: dict[str, str],
    role_profile: dict[str, Any],
    reasoning_effort: str,
) -> str:
    agent_id = _compact_public_token(role_profile.get("agent_id"), field="bootstrap.agent_id")
    lane_id = _compact_public_token(role_profile.get("lane_id"), field="bootstrap.lane_id")
    role_id = _compact_public_token(role_profile.get("role_id"), field="bootstrap.role_id")
    skill_section = _compact_public_text(
        str(role_profile.get("skill_section") or role_id),
        field="bootstrap.skill_section",
        max_len=80,
    )
    responsibility = _compact_public_text(
        str(lane.get("responsibility") or ""),
        field="bootstrap.responsibility",
        max_len=180,
    )
    allowed_actions = _compact_prompt_list(role_profile.get("allowed_actions"))
    handoff_outputs = _compact_prompt_list(role_profile.get("handoff_outputs"))
    write_scope = _compact_prompt_list(role_profile.get("write_scope"))
    protected_scope = _compact_prompt_list(role_profile.get("protected_scope"))
    stop_conditions = _compact_prompt_list(role_profile.get("stop_conditions"))
    effort = _compact_public_token(reasoning_effort, field="bootstrap.reasoning_effort")
    goal = _compact_public_token(goal_id, field="bootstrap.goal_id")
    return "\n".join(
        [
            "You are a visible LoopX auto-research lane, not a generic LoopX heartbeat worker.",
            "Use skills in this order: loopx-project for quota/status, then loopx-auto-research for this role.",
            "Do not run loopx bootstrap-command-pack, loopx heartbeat-prompt, or generic onboarding unless the printed frontier explicitly asks for it.",
            "",
            f"Goal: {goal}",
            f"Agent: {agent_id}",
            f"Lane: {lane_id}",
            f"Role: {role_id}",
            f"Skill section: {skill_section}",
            f"Responsibility: {responsibility}",
            f"Reasoning: model_reasoning_effort={effort}",
            "",
            "Before any write, resolve identity from LOOPX_ROLE_PROFILE_JSON, the printed quota packet, and the printed auto-research frontier.",
            "If any of those disagree, stop and report the blocker in this pane.",
            f"Allowed actions: {allowed_actions}",
            f"Allowed write scope: {write_scope}",
            f"Protected scope: {protected_scope}",
            f"Expected handoff outputs: {handoff_outputs}",
            f"Stop conditions: {stop_conditions}",
            "",
            "Live E2E proof contract:",
            "- Work only from the printed auto-research frontier and this role profile.",
            "- Deterministic replay is not live Codex evidence; do not claim replay metrics as lane-authored results.",
            "- If you author evidence, use public-safe loopx auto-research evidence and append-evidence commands.",
            "- A controller may later run capture-live-evidence to create live-codex-e2e-evidence.public.json.",
            "- claim_allowed must remain false until that public-safe live evidence file exists and validates.",
            "",
            "Never include credentials, raw private logs, raw session transcripts, local absolute paths, or private artifacts.",
            "End with a compact public-safe summary of commands run, evidence written, blocker, or next role-local todo.",
        ]
    )


def _env_auto_research_bootstrap_command(
    *,
    goal_id: str,
    lane: dict[str, str],
    role_profile: dict[str, Any],
    reasoning_effort: str,
) -> str:
    prompt = _auto_research_codex_bootstrap_prompt(
        goal_id=goal_id,
        lane=lane,
        role_profile=role_profile,
        reasoning_effort=reasoning_effort,
    )
    return f"printf '%s\\n' {_shell_arg(prompt)}"


def _role_profile_for_lane(*, goal_id: str, lane: dict[str, str]) -> dict[str, Any]:
    role_id = _compact_public_token(lane["role_id"], field="lane.role_id")
    template = AUTO_RESEARCH_ROLE_PROFILE_TEMPLATES[role_id]
    return {
        "schema_version": AUTO_RESEARCH_ROLE_PROFILE_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": lane["agent_id"],
        "lane_id": lane["lane_id"],
        "role_id": role_id,
        "display_name": template["display_name"],
        "phase": template["phase"],
        "capability_token": role_id,
        "todo_id": "pending_frontier_selection",
        "hypothesis_id": "pending_frontier_selection",
        "allowed_actions": list(template["allowed_actions"]),
        "write_scope": list(template["write_scope"]),
        "protected_scope": list(template["protected_scope"]),
        "required_skill": AUTO_RESEARCH_REQUIRED_SKILL,
        "skill_section": template["skill_section"],
        "agents_overlay": ["workspace/AGENTS.md"],
        "stop_conditions": list(template["stop_conditions"]),
        "takeover_controls": [
            "tmux attach before accepting any Codex prompt",
            "normal terminal interrupt for one lane",
            "tmux kill-session for whole demo abort",
        ],
        "handoff_outputs": list(template["handoff_outputs"]),
        "identity_source": "loopx_control_plane_profile_then_quota_frontier",
        "identity_resolution_order": [
            "role_profile",
            "quota_should_run",
            "auto_research_frontier",
            "AGENTS.md",
            "loopx-auto-research skill section",
        ],
        "pane_title_is_authority": False,
    }

def _role_profile_shell_prefix(role_profile: dict[str, Any]) -> str:
    profile_json = json.dumps(role_profile, sort_keys=True, separators=(",", ":"))
    return (
        f"export LOOPX_AGENT_ID={_shell_arg(str(role_profile['agent_id']))}; "
        f"export LOOPX_ROLE_ID={_shell_arg(str(role_profile['role_id']))}; "
        f"export LOOPX_ROLE_PHASE={_shell_arg(str(role_profile['phase']))}; "
        f"export LOOPX_ROLE_PROFILE_REF={_shell_arg(str(role_profile['schema_version']))}; "
        f"export LOOPX_REQUIRED_SKILL={_shell_arg(str(role_profile['required_skill']))}; "
        f"LOOPX_ROLE_PROFILE_JSON={_shell_arg(profile_json)}; "
        "export LOOPX_ROLE_PROFILE_JSON; "
        "printf '\\n[LoopX role profile]\\n'; "
        "printf '%s\\n' \"$LOOPX_ROLE_PROFILE_JSON\"; "
    )


_QUOTA_GATE_PY = (
    "import json,sys; "
    "p=json.load(sys.stdin); "
    "u=p.get('interaction_contract',{}).get('user_channel',{}); "
    "a=p.get('interaction_contract',{}).get('agent_channel',{}); "
    "delivery=a.get('delivery_allowed', p.get('should_run', True)); "
    "ok=(not bool(u.get('action_required'))) and delivery is not False; "
    "sys.exit(0 if ok else 42)"
)

_QUOTA_BLOCKER_SUMMARY_PY = (
    "import json,sys; "
    "p=json.load(sys.stdin); "
    "ic=p.get('interaction_contract',{}); "
    "u=ic.get('user_channel',{}); "
    "a=ic.get('agent_channel',{}); "
    "reason=u.get('reason') or p.get('reason') or p.get('recommended_action') or 'blocked'; "
    "primary=a.get('primary_action') or p.get('recommended_action') or ''; "
    "print('reason=' + str(reason)); "
    "print('primary_action=' + str(primary))"
)


def _env_lane_launch_command(
    *,
    role_id: str,
    quota_command: str,
    frontier_command: str,
    bootstrap_command: str,
    codex_bin: str,
    reasoning_effort: str,
    role_profile: dict[str, Any],
) -> str:
    role_profile_prefix = _role_profile_shell_prefix(role_profile)
    visible_summary = (
        'printf "\\n[LoopX visible acceptance]\\n"; '
        'printf "role_profile=printed\\n"; '
        'printf "quota_guard=printed\\n"; '
        'printf "frontier_or_blocked_reason=printed\\n"; '
        'printf "bootstrap_or_stop=printed\\n"; '
        'printf "takeover_controls=visible\\n"; '
        f"printf 'reasoning_effort=%s\\n' {_shell_arg(reasoning_effort)}"
    )
    keep_visible = (
        f"{visible_summary}; "
        'printf "\\n[user takeover]\\ninspect this pane; interrupt, close, or retry manually\\n"; '
        "exec /bin/sh -i"
    )
    return (
        "set -uo pipefail; "
        f"export LOOPX_ROLE_ID={_shell_arg(role_id)}; "
        f"export LOOPX_ROLE_PROFILE_REF={_shell_arg(AUTO_RESEARCH_ROLE_PROFILE_REF)}; "
        'cd "$LOOPX_PROJECT"; '
        f"{role_profile_prefix}"
        "printf '\\n[LoopX quota guard]\\n'; "
        f"QUOTA_PACKET=\"$({quota_command} 2>&1)\"; "
        "QUOTA_STATUS=$?; "
        "printf '%s\\n' \"$QUOTA_PACKET\"; "
        "if [ \"$QUOTA_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'quota_command_failed exit=%s\\n' \"$QUOTA_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_shell_arg(_QUOTA_GATE_PY)}; "
        "QUOTA_GATE_STATUS=$?; "
        "if [ \"$QUOTA_GATE_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_shell_arg(_QUOTA_BLOCKER_SUMMARY_PY)} || true; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        "printf '\\n[LoopX auto-research frontier]\\n'; "
        f"{frontier_command}; "
        "FRONTIER_STATUS=$?; "
        "if [ \"$FRONTIER_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'frontier_command_failed exit=%s\\n' \"$FRONTIER_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_bootstrap\\n'; "
        f"{keep_visible}; "
        "fi; "
        "printf '\\n[bootstrap-or-stop]\\ncontinuing_to_visible_bootstrap\\n'; "
        "printf '\\n[Codex bootstrap prompt]\\n'; "
        f"BOOTSTRAP_PROMPT=\"$({bootstrap_command} 2>&1)\"; "
        "BOOTSTRAP_STATUS=$?; "
        "printf '%s\\n' \"$BOOTSTRAP_PROMPT\"; "
        "if [ \"$BOOTSTRAP_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'bootstrap_command_failed exit=%s\\n' \"$BOOTSTRAP_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_codex\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"{visible_summary}; "
        'sleep "${LOOPX_VISIBLE_BOOTSTRAP_PAUSE_SECONDS:-1}"; '
        "printf '\\n[Starting visible Codex CLI]\\n'; "
        f"{_shell_arg(codex_bin)} -c model_reasoning_effort={_shell_arg(reasoning_effort)} \"$BOOTSTRAP_PROMPT\"; "
        "CODEX_STATUS=$?; "
        "printf '\\n[Codex CLI exited]\\nexit=%s\\n' \"$CODEX_STATUS\"; "
        f"{keep_visible}"
    )


def _demo_rehearsal_script(*, session: str, start_script: list[str], attach_command: str, stop_command: str) -> list[str]:
    """Return a copy-paste dry-run script that prints the real launch plan only."""

    quoted_start_lines = " ".join(_shell_arg(line) for line in start_script)
    return [
        "set -euo pipefail",
        "echo 'LoopX auto-research demo supervisor: dry-run rehearsal only'",
        "echo 'This script does not start tmux, launch Codex, mutate LoopX state, or spend quota.'",
        ": ${LOOPX_PROJECT:?set LOOPX_PROJECT to the repo root before rehearsal}",
        ": ${LOOPX_REGISTRY:?set LOOPX_REGISTRY to the LoopX registry path before rehearsal}",
        ": ${LOOPX_RUNTIME_ROOT:?set LOOPX_RUNTIME_ROOT to the LoopX runtime root before rehearsal}",
        "printf '\\n[visible session]\\n'",
        f"printf '%s\\n' {_shell_arg(session)}",
        "printf '\\n[start script - inspect before pasting]\\n'",
        f"printf '%s\\n' {quoted_start_lines}",
        "printf '\\n[attach after start]\\n'",
        f"printf '%s\\n' {_shell_arg(attach_command)}",
        "printf '\\n[stop / user takeover abort]\\n'",
        f"printf '%s\\n' {_shell_arg(stop_command)}",
    ]


def build_auto_research_demo_supervisor_plan(
    *,
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    agent_specs: Iterable[str] | None = None,
    session_name: str = "loopx-auto-research",
    cli_bin: str = "loopx",
    codex_bin: str = "codex",
    tmux_bin: str = "tmux",
    reasoning_effort: str = "high",
) -> dict[str, Any]:
    """Build a dry-run tmux/Codex-CLI supervisor plan for auto research.

    The supervisor is a host convenience packet, not a leader agent. It gives a
    user one place to inspect the shell script that would open visible panes for
    several decentralized lanes. The default packet does not start tmux, launch
    Codex, read session files, write LoopX state, or spend quota.
    """

    goal = _compact_public_token(goal_id, field="goal_id")
    session = _compact_public_token(session_name, field="session_name")
    cli = _compact_public_token(cli_bin, field="cli_bin")
    codex = _compact_public_token(codex_bin, field="codex_bin")
    tmux = _compact_public_token(tmux_bin, field="tmux_bin")
    effort = _compact_public_token(reasoning_effort, field="reasoning_effort")
    uses_default_lanes = agent_specs is None
    lanes = _demo_lane_specs(agent_specs)
    default_lane_ids = [
        lane_id
        for _agent_id, lane_id, _role_id, _responsibility in AUTO_RESEARCH_DEMO_DEFAULT_LANES
    ]

    pane_plans: list[dict[str, Any]] = []
    for lane in lanes:
        agent_id = lane["agent_id"]
        lane_id = lane["lane_id"]
        role_id = lane["role_id"]
        role_profile = _role_profile_for_lane(goal_id=goal, lane=lane)
        quota_command = _env_quota_command(cli_bin=cli, goal_id=goal, agent_id=agent_id)
        frontier_command = _env_frontier_command(cli_bin=cli, goal_id=goal, agent_id=agent_id)
        bootstrap_command = _env_auto_research_bootstrap_command(
            goal_id=goal,
            lane=lane,
            role_profile=role_profile,
            reasoning_effort=effort,
        )
        pane_plans.append(
            {
                "lane_id": lane_id,
                "agent_id": agent_id,
                "role_id": role_id,
                "responsibility": lane["responsibility"],
                "role_profile": role_profile,
                "window_name": lane_id,
                "quota_guard": quota_command,
                "frontier": frontier_command,
                "bootstrap_message": bootstrap_command,
                "visible_codex_tui": codex,
                "reasoning_effort": effort,
                "visible_launch_command": _env_lane_launch_command(
                    role_id=role_id,
                    quota_command=quota_command,
                    frontier_command=frontier_command,
                    bootstrap_command=bootstrap_command,
                    codex_bin=codex,
                    reasoning_effort=effort,
                    role_profile=role_profile,
                ),
                "start_sequence": [
                    "print role_profile_v0 identity before any quota/frontier/bootstrap command",
                    "run quota_guard and stop when user_channel.action_required=true",
                    "render the lane frontier from LoopX state",
                    "print the role-scoped auto-research bootstrap message for this visible TUI",
                    "start Codex CLI visibly; do not inject hidden prompts into an existing session",
                ],
                "lane_timeline": [
                    {
                        "phase": "role_profile",
                        "command_ref": "role_profile",
                        "operator_visible_signal": "agent_id, role_id, phase, required skill, write boundary, stop conditions, and takeover controls",
                        "continue_when": "profile matches quota/frontier identity for this lane",
                        "stop_when": "profile conflicts with quota, frontier, AGENTS.md, or required skill",
                    },
                    {
                        "phase": "quota_guard",
                        "command_ref": "quota_guard",
                        "operator_visible_signal": "should-run packet for this agent lane",
                        "continue_when": "agent_channel.delivery_allowed=true and user_channel.action_required=false",
                        "stop_when": "user_channel.action_required=true or quota says do not run",
                    },
                    {
                        "phase": "frontier_projection",
                        "command_ref": "frontier",
                        "operator_visible_signal": "current auto-research frontier and todo/evidence hints",
                        "continue_when": "frontier contains a bounded lane-local next action",
                        "stop_when": "frontier is empty, contradictory, private, or asks for owner input",
                    },
                    {
                        "phase": "bootstrap_prompt",
                        "command_ref": "bootstrap_message",
                        "operator_visible_signal": "role-scoped auto-research Codex bootstrap message printed in the lane pane",
                        "continue_when": "bootstrap scope matches the lane frontier",
                        "stop_when": "bootstrap would bypass LoopX quota, todo claims, or evidence writeback",
                    },
                    {
                        "phase": "visible_codex",
                        "command_ref": "visible_codex_tui",
                        "operator_visible_signal": "Codex CLI starts only in the visible tmux lane",
                        "continue_when": "operator is attached and can interrupt the lane",
                        "stop_when": "pane is hidden, detached, or starts mutating state before review",
                    },
                ],
            }
        )

    env_lines = [
        "set -uo pipefail",
        ": ${LOOPX_PROJECT:?set LOOPX_PROJECT to the repo root before running}",
        ": ${LOOPX_REGISTRY:?set LOOPX_REGISTRY to the LoopX registry path before running}",
        ": ${LOOPX_RUNTIME_ROOT:?set LOOPX_RUNTIME_ROOT to the LoopX runtime root before running}",
    ]
    frontier_launch_command = (
        'cd "$LOOPX_PROJECT"; '
        + _env_frontier_command(cli_bin=cli, goal_id=goal, agent_id=lanes[0]["agent_id"])
        + '; FRONTIER_STATUS=$?; '
        + 'printf "\\n[frontier window ready]\\nexit=%s\\n" "$FRONTIER_STATUS"; '
        + 'exec /bin/sh -i'
    )
    start_script = [
        *env_lines,
        (
            f"{_shell_arg(tmux)} new-session -d -s {_shell_arg(session)} -n frontier "
            f"bash -lc {_shell_arg(frontier_launch_command)}"
        ),
        (
            f"{_shell_arg(tmux)} display-message -t {_shell_arg(session)} "
            f"{_shell_arg('LoopX auto-research supervisor started; attach before accepting prompts')}"
        ),
    ]
    for pane in pane_plans:
        lane_id = str(pane["lane_id"])
        start_script.extend(
            [
                (
                    f"{_shell_arg(tmux)} new-window -d -t {_shell_arg(session)} "
                    f"-n {_shell_arg(lane_id)} bash -lc {_shell_arg(str(pane['visible_launch_command']))}"
                ),
            ]
        )
    attach_command = f"{_shell_arg(tmux)} attach -t {_shell_arg(session)}"
    stop_command = f"{_shell_arg(tmux)} kill-session -t {_shell_arg(session)}"
    rehearsal_script = _demo_rehearsal_script(
        session=session,
        start_script=start_script,
        attach_command=attach_command,
        stop_command=stop_command,
    )

    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
        "mode": "dry_run",
        "goal_id": goal,
        "session_name": session,
        "reasoning_contract": {
            "schema_version": "auto_research_reasoning_contract_v0",
            "default_reasoning_effort": effort,
            "codex_cli_config_key": "model_reasoning_effort",
            "applies_to": "visible_codex_lanes",
        },
        "coordination_model": {
            "leader_agent_required": False,
            "supervisor_role": "host_shell_layout_only",
            "source_of_truth": [
                "role_profile_v0",
                "quota_should_run",
                "todo_claims",
                "auto_research_frontier",
                "research_evidence_graph",
            ],
            "decentralized_rule": "each lane reads its own quota/frontier projection and writes back through normal LoopX todo/evidence APIs",
        },
        "goal_surface": {
            "schema_version": "auto_research_shared_goal_surface_v0",
            "shared_goal_id": goal,
            "lane_count": len(pane_plans),
            "lane_ids": [str(pane["lane_id"]) for pane in pane_plans],
            "uses_default_lanes": uses_default_lanes,
            "default_lane_count": len(default_lane_ids),
            "default_lane_ids": default_lane_ids,
            "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
            "shared_frontier": True,
            "lane_identity_source": "role_profile_v0_plus_agent_scoped_quota",
            "all_lane_workspace_isolation": False,
            "mutation_isolation_policy": (
                "only mutating evidence-runner attempts require a claimed git worktree "
                "or equivalent execution boundary"
            ),
            "explicit_agent_override": True,
        },
        "lanes": pane_plans,
        "commands": {
            "start_script": start_script,
            "attach": attach_command,
            "stop": stop_command,
            "one_click_dry_run_rehearsal": rehearsal_script,
        },
        "one_click_demo": {
            "schema_version": "auto_research_one_click_demo_v0",
            "mode": "copy_paste_dry_run_rehearsal",
            "default_safe": True,
            "description": (
                "Copy the rehearsal script into the user shell to verify environment variables "
                "and print the visible tmux/Codex plan without launching sessions."
            ),
            "script": rehearsal_script,
            "expected_visible_result": [
                "prints the tmux session name",
                "prints every command that would be pasted into a visible pane",
                "prints attach and stop commands for user takeover",
            ],
            "does_not": [
                "start tmux",
                "launch Codex",
                "read session files",
                "write LoopX state",
                "spend quota",
            ],
        },
        "demo_acceptance": {
            "schema_version": "auto_research_demo_acceptance_v0",
            "required_visible_fields": [
                "commands.one_click_dry_run_rehearsal",
                "commands.start_script",
                "commands.attach",
                "commands.stop",
                "lanes[].role_id",
                "lanes[].role_profile",
                "lanes[].quota_guard",
                "lanes[].frontier",
                "lanes[].bootstrap_message",
                "lanes[].reasoning_effort",
                "lanes[].lane_timeline",
                "user_takeover.operator_controls",
                "boundary",
            ],
            "operator_can_accept_when": [
                "the rehearsal script prints the real start script without executing it",
                "every lane prints role_profile_v0 before quota, frontier, bootstrap, or Codex startup",
                "every lane has a quota guard before frontier/bootstrap/Codex startup",
                "the attach command is visible before any Codex prompt is accepted",
                "the stop command and terminal interrupt path are visible",
                "boundary fields prove no tmux/Codex/state/quota side effects in dry-run mode",
            ],
            "operator_must_reject_when": [
                "a lane lacks role_profile_v0, skill section, write scope, or stop conditions",
                "a lane can start without quota should-run",
                "a lane lacks a role_profile_v0 identity packet",
                "the packet hides attach/stop controls",
                "the packet embeds local absolute paths, credentials, raw sessions, or private links",
                "the supervisor becomes a leader or writes LoopX state directly",
            ],
        },
        "user_takeover": {
            "schema_version": "auto_research_user_takeover_v0",
            "operator_controls": [
                "run the rehearsal script first and inspect the printed start script",
                "paste start_script manually only after deciding to launch the visible demo",
                "attach to tmux before accepting any Codex prompt",
                "use the stop command to kill the whole demo session",
                "interrupt an individual pane with the normal terminal interrupt before any write path",
            ],
            "visible_status_cues": [
                "frontier window shows the shared research frontier",
                "each lane window prints its role_profile_v0 before quota/frontier/bootstrap",
                "each lane window prints its own quota guard before Codex starts",
                "each lane window prints its own auto-research frontier before Codex starts",
                f"each lane window prints reasoning_effort={effort} before Codex starts",
                "bootstrap message is visible in the same pane that would run Codex",
            ],
            "handoff_boundary": "the shell supervisor owns layout only; LoopX quota, todo claims, frontier, and evidence graph remain source of truth",
        },
        "future_gates": [
            {
                "capability": "execute_start_script",
                "state": "future_gated",
                "required_contract": "explicit user shell authority plus visible tmux attach before Codex starts",
            },
            {
                "capability": "same_session_prompt_injection",
                "state": "blocked_without_visible_attach_proof",
                "required_contract": "codex_cli_visible_attach_acceptance_v0 with fresh idle guard",
            },
            {
                "capability": "state_write_from_supervisor",
                "state": "not_allowed",
                "required_contract": "normal LoopX CLI todo/evidence/writeback commands only",
            },
        ],
        "boundary": {
            "dry_run_plan_only": True,
            "starts_tmux": False,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_credentials": False,
            "mutates_codex_session": False,
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "external_service_call": False,
            "shared_goal_surface": True,
            "all_lane_workspace_isolation": False,
            "mutation_isolation_policy": (
                "only mutating evidence-runner attempts require a claimed git worktree "
                "or equivalent execution boundary"
            ),
        },
        "operator_notes": [
            "Set LOOPX_PROJECT, LOOPX_REGISTRY, and LOOPX_RUNTIME_ROOT in the user shell before running the script.",
            "Attach to tmux before accepting any Codex prompt so every lane stays visible and interruptible.",
            "Use the printed quota/frontier packet in each pane to decide whether that lane should continue, ask, or stop.",
        ],
    }


def _command_available(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_auto_research_demo_acceptance_packet(
    board: dict[str, Any],
    supervisor: dict[str, Any],
) -> dict[str, Any]:
    """Bind board and dry-run supervisor output into a user acceptance packet.

    The packet is a read-only operator aid. It does not re-run research,
    launch tmux/Codex, write state, spend quota, or decide promotion. It only
    names the visible checks a user should inspect before turning the
    experimental auto-research demo into a real local launch.
    """

    board = _json_obj(board, field="board")
    supervisor = _json_obj(supervisor, field="supervisor")
    board_schema = _compact_public_token(
        board.get("schema_version"),
        field="board.schema_version",
    )
    supervisor_schema = _compact_public_token(
        supervisor.get("schema_version"),
        field="supervisor.schema_version",
    )
    if board_schema != AUTO_RESEARCH_BOARD_SCHEMA_VERSION:
        raise ValueError(f"board.schema_version must be {AUTO_RESEARCH_BOARD_SCHEMA_VERSION}")
    if supervisor_schema != AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION:
        raise ValueError(f"supervisor.schema_version must be {AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION}")
    if not board.get("ok"):
        raise ValueError("board must be ok")
    if not supervisor.get("ok"):
        raise ValueError("supervisor must be ok")

    binding = _json_obj(board.get("projection_binding"), field="board.projection_binding")
    claim_boundary = _json_obj(board.get("claim_boundary"), field="board.claim_boundary")
    surface = _json_obj(board.get("surface"), field="board.surface")
    research_contract = _json_obj(board.get("research_contract"), field="board.research_contract")
    decisions = _json_obj(board.get("decision_candidates"), field="board.decision_candidates")
    commands = _json_obj(supervisor.get("commands"), field="supervisor.commands")
    one_click = _json_obj(supervisor.get("one_click_demo"), field="supervisor.one_click_demo")
    acceptance = _json_obj(supervisor.get("demo_acceptance"), field="supervisor.demo_acceptance")
    takeover = _json_obj(supervisor.get("user_takeover"), field="supervisor.user_takeover")
    boundary = _json_obj(supervisor.get("boundary"), field="supervisor.boundary")
    lanes = [item for item in supervisor.get("lanes") or [] if isinstance(item, dict)]
    gates = [item for item in board.get("user_gates") or [] if isinstance(item, dict)]
    metrics = [item for item in board.get("value_metrics") or [] if isinstance(item, dict)]
    promotion_candidates = [
        item for item in decisions.get("promotion_candidates") or [] if isinstance(item, dict)
    ]
    retirement_candidates = [
        item for item in decisions.get("retirement_candidates") or [] if isinstance(item, dict)
    ]

    attach = _compact_optional_text(
        commands.get("attach"),
        field="acceptance.attach",
        default="attach command missing",
    )
    stop = _compact_optional_text(
        commands.get("stop"),
        field="acceptance.stop",
        default="stop command missing",
    )
    start_script = [str(item) for item in commands.get("start_script") or []]
    rehearsal_script = [str(item) for item in one_click.get("script") or []]
    attach_visible = _command_available(commands.get("attach"))
    stop_visible = _command_available(commands.get("stop"))
    dry_run_safe = all(
        boundary.get(field) is expected
        for field, expected in {
            "dry_run_plan_only": True,
            "starts_tmux": False,
            "runs_codex": False,
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "reads_credentials": False,
            "reads_session_files": False,
        }.items()
    )
    lane_checks = [
        {
            "lane_id": _compact_public_token(lane.get("lane_id"), field="acceptance.lane_id"),
            "agent_id": _compact_public_token(lane.get("agent_id"), field="acceptance.agent_id"),
            "role_profile_visible": isinstance(lane.get("role_profile"), dict),
            "role_id": _compact_optional_token(
                (lane.get("role_profile") or {}).get("role_id") if isinstance(lane.get("role_profile"), dict) else None,
                field="acceptance.role_id",
                default="missing_role",
            ),
            "phase": _compact_optional_token(
                (lane.get("role_profile") or {}).get("phase") if isinstance(lane.get("role_profile"), dict) else None,
                field="acceptance.phase",
                default="missing_phase",
            ),
            "required_skill": _compact_optional_token(
                (lane.get("role_profile") or {}).get("required_skill") if isinstance(lane.get("role_profile"), dict) else None,
                field="acceptance.required_skill",
                default="missing_skill",
            ),
            "quota_guard_visible": _command_available(lane.get("quota_guard")),
            "frontier_visible": _command_available(lane.get("frontier")),
            "bootstrap_visible": _command_available(lane.get("bootstrap_message")),
            "visible_codex_tui": _compact_optional_token(
                lane.get("visible_codex_tui"),
                field="acceptance.visible_codex_tui",
                default="codex",
            ),
        }
        for lane in lanes
    ]
    lanes_ready = bool(lane_checks) and all(
        check["role_profile_visible"]
        and check["quota_guard_visible"]
        and check["frontier_visible"]
        and check["bootstrap_visible"]
        for check in lane_checks
    )

    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_DEMO_ACCEPTANCE_PACKET_SCHEMA_VERSION,
        "goal_id": _compact_public_token(
            research_contract.get("goal_id"),
            field="acceptance.goal_id",
        ),
        "surface": {
            "title": _compact_optional_text(
                surface.get("title"),
                field="acceptance.title",
                default="Auto Research Demo Acceptance",
            ),
            "stage": _compact_optional_token(surface.get("stage"), field="acceptance.stage", default="experimental"),
            "first_screen_policy": _compact_optional_token(
                binding.get("first_screen_policy"),
                field="acceptance.first_screen_policy",
                default="experimental_only_not_first_screen_without_owner_review",
            ),
        },
        "readiness_summary": {
            "operator_can_review_now": True,
            "ready_for_real_launch": bool(
                binding.get("read_only")
                and dry_run_safe
                and attach_visible
                and stop_visible
                and lanes_ready
            ),
            "ready_for_public_first_screen": False,
            "reason": (
                "Board and dry-run supervisor are inspectable; real launch still requires explicit local user action."
                if dry_run_safe and lanes_ready
                else "Missing a visible lane, attach/stop control, or dry-run boundary field."
            ),
        },
        "board_output": {
            "schema_version": board.get("schema_version"),
            "read_only": bool(binding.get("read_only")),
            "source_kind": _compact_optional_token(
                binding.get("source_kind"),
                field="acceptance.source_kind",
                default="unknown_source",
            ),
            "rollout_backed": bool(binding.get("rollout_backed")),
            "value_metric_count": len(metrics),
            "promotion_candidate_count": len(promotion_candidates),
            "retirement_candidate_count": len(retirement_candidates),
            "user_gate_count": len(gates),
            "claim_boundary": {
                "live_claim_scope": claim_boundary.get("live_claim_scope"),
                "holdout_result_scope": claim_boundary.get("holdout_result_scope"),
                "holdout_claim_allowed": bool(claim_boundary.get("holdout_claim_allowed")),
                "promotion_claim_allowed": bool(claim_boundary.get("promotion_claim_allowed")),
                "first_screen_claim_allowed": bool(claim_boundary.get("first_screen_claim_allowed")),
            },
        },
        "supervisor_rehearsal": {
            "schema_version": supervisor.get("schema_version"),
            "mode": _compact_optional_token(supervisor.get("mode"), field="acceptance.mode", default="dry_run"),
            "session_name": _compact_optional_token(
                supervisor.get("session_name"),
                field="acceptance.session_name",
                default="loopx-auto-research",
            ),
            "lane_count": len(lanes),
            "one_click_mode": _compact_optional_token(
                one_click.get("mode"),
                field="acceptance.one_click_mode",
                default="copy_paste_dry_run_rehearsal",
            ),
            "default_safe": bool(one_click.get("default_safe")),
            "rehearsal_script_visible": bool(rehearsal_script),
            "start_script_visible": bool(start_script),
            "attach": attach,
            "stop": stop,
        },
        "lane_checks": lane_checks,
        "operator_checklist": [
            "Run the dry-run rehearsal first and inspect the printed start script.",
            "Confirm every lane prints role_profile_v0 with agent_id, role_id, phase, allowed writes, required skill, stop conditions, and takeover controls.",
            "Confirm every lane prints quota should-run before frontier, bootstrap, or Codex.",
            "Confirm attach and stop commands are visible before accepting any Codex prompt.",
            "Confirm the board is read-only and still experimental.",
            "Confirm promotion candidates remain decision items, not automatic public claims.",
        ],
        "accept_when": _compact_public_text_list(
            acceptance.get("operator_can_accept_when") or [],
            field="acceptance.accept_when",
        ),
        "reject_when": _compact_public_text_list(
            acceptance.get("operator_must_reject_when") or [],
            field="acceptance.reject_when",
        ),
        "user_takeover": {
            "operator_controls": _compact_public_text_list(
                takeover.get("operator_controls") or [],
                field="acceptance.operator_controls",
            ),
            "visible_status_cues": _compact_public_text_list(
                takeover.get("visible_status_cues") or [],
                field="acceptance.visible_status_cues",
            ),
            "handoff_boundary": _compact_optional_text(
                takeover.get("handoff_boundary"),
                field="acceptance.handoff_boundary",
                default="supervisor owns layout only; LoopX remains source of truth",
            ),
        },
        "upgrade_path": [
            "Keep this packet as the required preflight before any real tmux/Codex launch.",
            "Only after user approval, paste the printed start_script in a visible shell.",
            "Attach to the tmux session before accepting any Codex prompt.",
            "Use normal LoopX todo/evidence writeback; the supervisor never writes state directly.",
        ],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "local_paths_recorded": False,
            "credentials_recorded": False,
            "starts_tmux": bool(boundary.get("starts_tmux")),
            "runs_codex": bool(boundary.get("runs_codex")),
            "writes_loopx_state": bool(boundary.get("writes_loopx_state")),
            "spends_loopx_quota": bool(boundary.get("spends_loopx_quota")),
        },
    }


def _quickstart_contract(*, goal_id: str, objective: str) -> dict[str, Any]:
    contract = validate_research_contract(
        {
            "schema_version": RESEARCH_CONTRACT_SCHEMA_VERSION,
            "goal_id": goal_id,
            "research_objective": objective,
            "editable_scope": ["solution_candidate.py"],
            "protected_scope": [
                "protected_eval.py",
                "solution_baseline.py",
                "research_contract.json",
            ],
            "metric": {
                "name": "deterministic_speedup",
                "direction": "maximize",
                "baseline": 1.0,
            },
            "dev_eval": "python3 protected_eval.py --solution solution_candidate.py --split dev",
            "holdout_eval": "python3 protected_eval.py --solution solution_candidate.py --split holdout",
            "promotion_policy": "requires_dev_and_holdout_improvement_exactness_and_clean_boundary",
        }
    )
    contract["no_upload"] = True
    return contract


_QUICKSTART_PROTECTED_EVAL = '''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "auto_research_knn_eval_result_v0"
PACK_DIR = Path(__file__).resolve().parent
Point = tuple[float, ...]

SPLITS: dict[str, dict[str, int]] = {
    "dev": {"seed": 17, "train_count": 256, "query_count": 18, "dims": 4, "k": 3},
    "holdout": {"seed": 31, "train_count": 512, "query_count": 24, "dims": 4, "k": 3},
}


def _point(seed: int, index: int, dims: int) -> Point:
    values = []
    for dim in range(dims):
        raw = (seed * (dim + 5) + index * (dim * 23 + 11) + index * index * (dim + 3)) % 997
        values.append(raw / 97.0)
    return tuple(values)


def build_split(split: str) -> tuple[list[Point], list[Point], int, dict[str, int]]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    spec = SPLITS[split]
    train = [_point(spec["seed"], index, spec["dims"]) for index in range(spec["train_count"])]
    queries = [
        _point(spec["seed"] + 101, index, spec["dims"])
        for index in range(spec["query_count"])
    ]
    return train, queries, spec["k"], spec


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def oracle_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    expected: list[list[int]] = []
    for query in queries:
        ranked = sorted((_squared_distance(query, point), index) for index, point in enumerate(train))
        expected.append([index for _, index in ranked[:k]])
    return expected


def load_solution(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("auto_research_knn_solution", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load solution from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "solve_knn"):
        raise ValueError("solution must define solve_knn(train, queries, k)")
    return module


def ranking_work_units(strategy: str, *, train_count: int, query_count: int, k: int) -> int:
    if strategy == "partial_selection":
        rank_factor = max(1, math.ceil(math.log2(k + 1)))
    else:
        rank_factor = max(1, math.ceil(math.log2(train_count)))
    return query_count * train_count * rank_factor


def evaluate(solution_path: Path, split: str) -> dict[str, Any]:
    solution_path = solution_path.resolve()
    train, queries, k, spec = build_split(split)
    module = load_solution(solution_path)
    strategy = str(getattr(module, "STRATEGY", "unknown"))
    expected = oracle_knn(train, queries, k)
    actual = module.solve_knn(train, queries, k)
    exact = actual == expected

    baseline_units = ranking_work_units(
        "full_sort",
        train_count=spec["train_count"],
        query_count=spec["query_count"],
        k=k,
    )
    candidate_units = ranking_work_units(
        strategy,
        train_count=spec["train_count"],
        query_count=spec["query_count"],
        k=k,
    )
    speedup = baseline_units / candidate_units if exact else None
    improved = bool(speedup is not None and speedup > 1.0)
    protected_scope_clean = solution_path.parent == PACK_DIR and solution_path.name in {
        "solution_baseline.py",
        "solution_candidate.py",
    }
    promotion_ready = exact and improved and protected_scope_clean
    return {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "solution": solution_path.name,
        "strategy": strategy,
        "dataset": {
            "train_count": spec["train_count"],
            "query_count": spec["query_count"],
            "dims": spec["dims"],
            "k": k,
            "seed": spec["seed"],
        },
        "metric": {
            "name": "deterministic_speedup",
            "direction": "maximize",
            "value": round(speedup, 6) if speedup is not None else None,
            "baseline": 1.0,
        },
        "work_units": {
            "baseline_full_sort": baseline_units,
            "candidate": candidate_units,
        },
        "exact": exact,
        "protected_scope_clean": protected_scope_clean,
        "no_upload": True,
        "eval_status": "scored" if exact else "guardrail_failed",
        "primary_metric_status": "improved" if improved else ("baseline" if exact else "failed"),
        "promotion_gate": {
            "requires": [
                "exact_neighbor_identity",
                "dev_and_holdout_improvement",
                "protected_scope_clean",
                "no_upload",
            ],
            "ready_for_split": promotion_ready,
        },
        "artifact_refs": [
            f"knn_pack:{split}:{strategy}",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Protected evaluator for the public LoopX auto-research k-NN pack.")
    parser.add_argument("--solution", required=True, help="Path to a solution module.")
    parser.add_argument("--split", choices=sorted(SPLITS), required=True)
    args = parser.parse_args()
    payload = evaluate(Path(args.solution), args.split)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["exact"] and payload["protected_scope_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


_QUICKSTART_SOLUTION_BASELINE = '''from __future__ import annotations


STRATEGY = "full_sort"


Point = tuple[float, ...]


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    """Reference exact k-NN solver using a full distance sort per query."""

    results: list[list[int]] = []
    for query in queries:
        ranked = sorted((_squared_distance(query, point), index) for index, point in enumerate(train))
        results.append([index for _, index in ranked[:k]])
    return results
'''


_QUICKSTART_SOLUTION_CANDIDATE = '''from __future__ import annotations

import heapq


STRATEGY = "partial_selection"


Point = tuple[float, ...]


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    """Exact k-NN using partial selection instead of sorting every distance."""

    results: list[list[int]] = []
    for query in queries:
        nearest = heapq.nsmallest(
            k,
            ((_squared_distance(query, point), index) for index, point in enumerate(train)),
        )
        results.append([index for _, index in nearest])
    return results
'''


_QUICKSTART_README = '''# LoopX Auto Research k-NN Pack

This generated pack is a public-safe starter for a decentralized auto-research
run. Edit only `solution_candidate.py`; keep `protected_eval.py`,
`solution_baseline.py`, and `research_contract.json` unchanged.

Run dev:

```bash
python3 protected_eval.py --solution solution_candidate.py --split dev
```

Run holdout:

```bash
python3 protected_eval.py --solution solution_candidate.py --split holdout
```

Promotion requires exact neighbor identity, dev and holdout improvement, clean
protected scope, and no upload/private artifacts.
'''


def _quickstart_template_files(contract: dict[str, Any]) -> dict[str, str]:
    return {
        "research_contract.json": json.dumps(contract, indent=2, sort_keys=True) + "\n",
        "protected_eval.py": _QUICKSTART_PROTECTED_EVAL,
        "solution_baseline.py": _QUICKSTART_SOLUTION_BASELINE,
        "solution_candidate.py": _QUICKSTART_SOLUTION_CANDIDATE,
        "README.md": _QUICKSTART_README,
    }


def _quickstart_file_summary(
    *,
    pack_dir: Path,
    files: dict[str, str],
    write_status: str,
) -> list[dict[str, Any]]:
    protected_names = {"protected_eval.py", "solution_baseline.py", "research_contract.json"}
    role_by_name = {
        "README.md": "operator_notes",
        "protected_eval.py": "protected_evaluator",
        "research_contract.json": "research_contract",
        "solution_baseline.py": "protected_baseline",
        "solution_candidate.py": "editable_candidate",
    }
    return [
        {
            "path": f"{pack_dir.as_posix()}/{name}",
            "role": role_by_name.get(name, "pack_file"),
            "protected": name in protected_names,
            "write_status": write_status,
        }
        for name in sorted(files)
    ]


def build_auto_research_quickstart(
    *,
    agent_id: str,
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    objective: str = AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    output_dir: str = "auto_research_knn_pack",
    template: str = AUTO_RESEARCH_QUICKSTART_TEMPLATE,
    execute: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Create or preview the public k-NN auto-research starter contract.

    The default mode is read-only. `execute=True` writes a protected evaluator
    pack below the current working directory and refuses to overwrite an
    existing pack, so heartbeat agents can preview the next hypothesis without
    producing local artifacts by accident.
    """

    agent = _compact_public_token(agent_id, field="agent_id")
    goal = _compact_public_token(goal_id, field="goal_id")
    objective_text = _compact_public_text(objective, field="objective", max_len=240)
    selected_template = _compact_public_token(template, field="template")
    if selected_template != AUTO_RESEARCH_QUICKSTART_TEMPLATE:
        raise ValueError(f"template must be {AUTO_RESEARCH_QUICKSTART_TEMPLATE}")
    pack_dir = _relative_pack_dir(output_dir)
    contract = _quickstart_contract(goal_id=goal, objective=objective_text)
    files = _quickstart_template_files(contract)
    dev_command = (
        f"python3 {pack_dir.as_posix()}/protected_eval.py "
        f"--solution {pack_dir.as_posix()}/solution_candidate.py --split dev"
    )
    holdout_command = (
        f"python3 {pack_dir.as_posix()}/protected_eval.py "
        f"--solution {pack_dir.as_posix()}/solution_candidate.py --split holdout"
    )
    hypothesis = validate_research_hypothesis(
        {
            "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            "hypothesis_id": "hyp_quickstart_partial_selection",
            "todo_id": "todo_auto_research_quickstart_001",
            "claimed_by": agent,
            "mechanism_family": "partial_selection",
            "hypothesis": "Use exact partial selection to avoid full distance sorting.",
            "status": "active",
            "grounding_refs": ["quickstart:knn_exact_pack"],
            "blocked_by": [],
        }
    )
    write_status = "would_write"
    if execute:
        root = (cwd or Path.cwd()).resolve()
        target_dir = (root / pack_dir).resolve()
        try:
            target_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("output_dir must resolve inside the current working directory") from exc
        if target_dir.exists():
            raise ValueError(f"output_dir already exists: {pack_dir.as_posix()}")
        target_dir.mkdir(parents=True)
        for name, contents in files.items():
            target = target_dir / name
            target.write_text(contents, encoding="utf-8")
            if name == "protected_eval.py":
                target.chmod(0o755)
        write_status = "created"
    file_summary = _quickstart_file_summary(
        pack_dir=pack_dir,
        files=files,
        write_status=write_status,
    )
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "template": selected_template,
        "research_contract": contract,
        "pack_dir": pack_dir.as_posix(),
        "files": file_summary,
        "next_runnable_hypothesis": hypothesis | {
            "allowed_action": "run_dev_attempt",
            "run_command": dev_command,
        },
        "next_commands": [
            {
                "label": "create_pack",
                "command": (
                    f"loopx --format json auto-research quickstart --agent-id {agent} "
                    f"--goal-id {goal} --output-dir {pack_dir.as_posix()} --execute"
                ),
                "required_when": "dry_run",
            },
            {"label": "run_dev", "command": dev_command},
            {"label": "run_holdout", "command": holdout_command},
            {
                "label": "record_evidence",
                "command": (
                    "loopx --format json auto-research evidence "
                    f"--contract {pack_dir.as_posix()}/research_contract.json "
                    "--eval-result dev-result.public.json --eval-result holdout-result.public.json "
                    "--hypothesis-id hyp_quickstart_partial_selection "
                    "--todo-id todo_auto_research_quickstart_001 "
                    f"--agent-id {agent} --claimed-by {agent} "
                    "--mechanism-family partial_selection "
                    '--hypothesis "Use exact partial selection to avoid full distance sorting."'
                ),
            },
        ],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "source": "generated_public_quickstart_contract",
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
    showcase_projection = build_research_showcase_projection(fixture, evidence_graph=evidence_graph)
    artifact_packet = build_research_artifact_packet(
        evidence_graph,
        question=contract["research_objective"],
    )
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
        "source_schema_version": fixture["schema_version"],
        "frontier": frontier,
        "evidence_graph": evidence_graph,
        "showcase_projection": showcase_projection,
        "artifact_packet": artifact_packet,
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
    decision_candidates = build_research_decision_candidates(evidence_graph)
    frontier = {
        "schema_version": RESEARCH_FRONTIER_SCHEMA_VERSION,
        "goal_id": goal,
        "agent_id": agent,
        "selected": selected,
        "runnable": runnable,
        "blocked": blocked,
        "promotion_candidates": decision_candidates["promotion_candidates"],
        "retirement_candidates": decision_candidates["retirement_candidates"],
        "source_kind": "loopx_live_quota_status",
    }
    selected_title = selected.get("title") if isinstance(selected, dict) else "No runnable hypothesis"
    graph_metric = evidence_graph.get("metric") if isinstance(evidence_graph.get("metric"), dict) else {}
    source_kind = str(evidence_graph.get("source_kind") or "loopx_live_quota_status")
    promoted = [
        node.get("hypothesis_id")
        for node in evidence_graph.get("nodes") or []
        if isinstance(node, dict) and node.get("status") == "promoted" and node.get("hypothesis_id")
    ]
    retired = [item["hypothesis_id"] for item in decision_candidates["retirement_candidates"]]
    claim_boundary = _board_public_claim_boundary(
        source_kind=source_kind,
        best_dev=evidence_graph.get("best_dev_metric"),
        best_holdout=evidence_graph.get("best_holdout_metric"),
    )
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
        "promotion_candidates": decision_candidates["promotion_candidates"],
        "retirement_candidates": decision_candidates["retirement_candidates"],
        "promoted_hypotheses": promoted,
        "retired_or_contradicted_hypotheses": retired,
        "negative_evidence_count": evidence_graph.get("negative_evidence_count"),
        "claim_boundary": claim_boundary,
        "decentralized_pattern": (
            "todo_backed_live_frontier_rollout_evidence_graph"
            if source_kind == ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND
            else "todo_backed_live_frontier_agent_scoped_quota_projection"
        ),
        "source_kind": source_kind,
    }
    artifact_packet = build_research_artifact_packet(
        evidence_graph,
        question=str(showcase_projection["objective"]),
    )
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
        "source_schema_version": "loopx_live_quota_status_v0",
        "frontier": frontier,
        "evidence_graph": evidence_graph,
        "showcase_projection": showcase_projection,
        "artifact_packet": artifact_packet,
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


def _metric_display(value: Any, *, suffix: str = "x") -> str:
    number = _finite_float(value, field="board.metric_value")
    if number is None:
        return "not scored"
    if number == int(number):
        return f"{int(number)}{suffix}"
    return f"{number:.1f}{suffix}"


def _board_public_claim_boundary(
    *,
    source_kind: str,
    best_dev: Any,
    best_holdout: Any,
) -> dict[str, Any]:
    dev_present = _finite_float(best_dev, field="board.claim_boundary.best_dev") is not None
    holdout_present = _finite_float(best_holdout, field="board.claim_boundary.best_holdout") is not None
    rollout_backed = source_kind == ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND
    return {
        "schema_version": AUTO_RESEARCH_PUBLIC_CLAIM_BOUNDARY_SCHEMA_VERSION,
        "metric_source_kind": source_kind,
        "claim_source": "live_codex_e2e",
        "live_claim_scope": "dev_only",
        "dev_metric_present": dev_present,
        "holdout_metric_present": holdout_present,
        "holdout_result_scope": "rollout_context_only" if rollout_backed else "projection_context_only",
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


def _board_user_gates() -> list[dict[str, str]]:
    return [
        {
            "gate_id": "first_screen_review_gate",
            "decision_owner": "product owner",
            "purpose": "Keep this board experimental until the first visible screen is explicitly reviewed.",
            "trigger": "Any change that moves the auto-research value path into README, hosted frontstage home, showcase index, or another first viewport.",
            "takeover_action": "Review the local preview or screenshot before the change is committed, pushed, or self-merged.",
            "public_evidence": "AGENTS.md first-screen review gate",
        },
        {
            "gate_id": "promotion_gate",
            "decision_owner": "research operator",
            "purpose": "Promote a hypothesis only when the evidence graph proves value on both dev and held-out splits.",
            "trigger": "A promotion candidate reports improved holdout metric and clean protected-boundary evidence.",
            "takeover_action": "Approve, reject, or defer promotion from the decision packet; agents may not promote from dev-only evidence.",
            "public_evidence": "artifact_packet.decision_packet",
        },
        {
            "gate_id": "protected_scope_gate",
            "decision_owner": "maintainer",
            "purpose": "Prevent benchmark or evaluator edits from being hidden inside a research run.",
            "trigger": "A candidate touches protected files, raw logs, upload paths, credentials, or non-public source material.",
            "takeover_action": "Stop the lane, keep the attempt visible as blocked or retired, and require a boundary repair before retry.",
            "public_evidence": "public_boundary and quality_gates",
        },
        {
            "gate_id": "real_launch_gate",
            "decision_owner": "local user",
            "purpose": "Keep the multi-agent demo visible and interruptible before any local Codex sessions are launched.",
            "trigger": "The dry-run supervisor is converted into real tmux/Codex process startup.",
            "takeover_action": "Inspect the rehearsal output, attach to the session, and keep a stop command visible before accepting agent prompts.",
            "public_evidence": "auto_research_demo_supervisor_v0",
        },
    ]


def _board_lanes(agent_id: str) -> list[dict[str, Any]]:
    agent = _compact_public_token(agent_id, field="board.agent_id")
    return [
        {
            "role_id": "curator",
            "display_name": "Curator",
            "agent_id": "codex-product-capability",
            "responsibility": "Keep the research contract, protected scope, and public boundary clear.",
            "produces": ["research_contract_v0", "scope boundary notes"],
            "does_not_own": "Experiment execution or promotion by persuasion.",
        },
        {
            "role_id": "hypothesis_proposer",
            "display_name": "Hypothesis proposer",
            "agent_id": agent,
            "responsibility": "Propose todo-linked hypotheses and parent-child refinements from the current frontier.",
            "produces": ["research_hypothesis_v0", "grounding refs"],
            "does_not_own": "Novelty claims from the same material used for ideation.",
        },
        {
            "role_id": "research_executor",
            "display_name": "Research executor",
            "agent_id": agent,
            "responsibility": "Run one claimed hypothesis in an isolated worktree and emit split-aware evidence.",
            "produces": ["auto_research_evidence_packet_v0", "branch refs"],
            "does_not_own": "Protected files, evaluator behavior, or promotion gates.",
        },
        {
            "role_id": "evaluator_promoter",
            "display_name": "Evaluator / promoter",
            "agent_id": "codex-product-capability",
            "responsibility": "Classify scored attempts into promote, retry, or retire using dev and holdout evidence.",
            "produces": ["promotion candidates", "retirement candidates", "gate todos"],
            "does_not_own": "Dev-only promotion or hidden bypass of user gates.",
        },
        {
            "role_id": "product_narrator",
            "display_name": "Product narrator",
            "agent_id": agent,
            "responsibility": "Turn the evidence graph into a public showcase without leaking private material.",
            "produces": ["research_showcase_projection_v0", "Frontstage board"],
            "does_not_own": "Changing public first screens without owner review.",
        },
    ]


def _board_decision_candidate(raw: dict[str, Any], *, decision: str) -> dict[str, Any]:
    candidate = {
        "hypothesis_id": _compact_public_token(raw.get("hypothesis_id"), field="board.candidate.hypothesis_id"),
        "todo_id": _compact_public_token(raw.get("todo_id"), field="board.candidate.todo_id"),
        "decision": _compact_public_token(decision, field="board.candidate.decision"),
        "reason": _compact_optional_text(
            raw.get("reason") or raw.get("status") or decision,
            field="board.candidate.reason",
            default=decision,
            max_len=180,
        ),
    }
    if raw.get("dev_metric") is not None:
        candidate["dev_metric"] = _metric_display(raw.get("dev_metric"))
    if raw.get("holdout_metric") is not None:
        candidate["holdout_metric"] = _metric_display(raw.get("holdout_metric"))
    if raw.get("requires"):
        candidate["requires"] = _compact_public_text_list(raw.get("requires"), field="board.candidate.requires")
    if decision.startswith("promote"):
        candidate["user_value"] = "A promotion candidate survived the read-only evidence graph and still requires an operator gate."
    return candidate


def build_auto_research_board_projection(
    projection: dict[str, Any],
    *,
    stage: str = "experimental",
) -> dict[str, Any]:
    """Build the Frontstage board packet from an existing read-only projection.

    This is deliberately a wrapper over `frontier` projection output. It does
    not parse private state files, launch experiments, or become a second source
    of truth; live boards come from quota/status plus rollout events, while
    fixture boards come from public fixture records.
    """

    projection = _json_obj(projection, field="auto_research_projection")
    schema = _compact_public_token(projection.get("schema_version"), field="projection.schema_version")
    if schema != AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION:
        raise ValueError(f"projection.schema_version must be {AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION}")
    if not projection.get("ok"):
        raise ValueError("projection must be ok")
    frontier = _json_obj(projection.get("frontier"), field="projection.frontier")
    graph = _json_obj(projection.get("evidence_graph"), field="projection.evidence_graph")
    showcase = _json_obj(projection.get("showcase_projection"), field="projection.showcase_projection")
    artifact = _json_obj(projection.get("artifact_packet"), field="projection.artifact_packet")
    goal = _compact_public_token(graph.get("goal_id") or frontier.get("goal_id"), field="board.goal_id")
    agent = _compact_public_token(frontier.get("agent_id"), field="board.agent_id")
    source_kind = _compact_optional_token(graph.get("source_kind"), field="board.source_kind", default="unknown_source")
    metric = graph.get("metric") if isinstance(graph.get("metric"), dict) else {}
    baseline = metric.get("baseline")
    best_dev = graph.get("best_dev_metric")
    best_holdout = graph.get("best_holdout_metric")
    promotion_candidates = [
        _board_decision_candidate(dict(item), decision="promote_after_operator_gate")
        for item in frontier.get("promotion_candidates") or []
        if isinstance(item, dict)
    ]
    retirement_candidates = [
        _board_decision_candidate(dict(item), decision="retire_or_block_until_repaired")
        for item in frontier.get("retirement_candidates") or []
        if isinstance(item, dict)
    ]
    retry_candidates = [
        {
            "hypothesis_id": _compact_public_token(item.get("hypothesis_id"), field="board.retry.hypothesis_id"),
            "todo_id": _compact_public_token(item.get("todo_id"), field="board.retry.todo_id"),
            "decision": "retry_with_executor_lane",
            "reason": "Visible unresolved or runnable hypothesis without held-out promotion evidence.",
        }
        for item in frontier.get("runnable") or []
        if isinstance(item, dict)
    ][:3]
    claim_boundary = _board_public_claim_boundary(
        source_kind=source_kind,
        best_dev=best_dev,
        best_holdout=best_holdout,
    )
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_BOARD_SCHEMA_VERSION,
        "generated_from": schema,
        "surface": {
            "id": f"{goal}_frontstage_board",
            "title": _compact_optional_text(showcase.get("title"), field="board.title", default="Auto Research Product Board"),
            "subtitle": "Read-only Frontstage board for decentralized auto research.",
            "stage": _compact_public_token(stage, field="board.stage"),
            "positioning": "LoopX shows autonomous research as lanes, claims, evidence, promotion decisions, user gates, and value metrics without a leader agent.",
            "public_boundary": "Projection data only; no raw logs, credentials, local paths, private source bodies, hidden leader transcript, or first-screen takeover.",
        },
        "projection_binding": {
            "read_only": True,
            "source_schema_version": projection.get("source_schema_version"),
            "source_kind": source_kind,
            "rollout_backed": bool(artifact.get("rollout_backed")),
            "first_screen_policy": "experimental_only_not_first_screen_without_owner_review",
            "public_claim_boundary_schema": claim_boundary["schema_version"],
            "frontier_agent_id": agent,
        },
        "research_contract": {
            "goal_id": goal,
            "objective": _compact_optional_text(
                showcase.get("objective"),
                field="board.objective",
                default=f"Read the current decentralized research frontier for {goal}.",
            ),
            "editable_scope": ["claimed hypothesis worktree"],
            "protected_scope": ["protected evaluator", "promotion gate", "first-screen review gate"],
            "metric": {
                "name": _compact_optional_token(metric.get("name"), field="board.metric.name", default="research_metric"),
                "direction": _compact_optional_token(
                    metric.get("direction"),
                    field="board.metric.direction",
                    default="maximize",
                ),
                "baseline": _metric_display(baseline),
            },
            "promotion_policy": (
                "Default public projection may show dev-only live evidence; held-out rollout context "
                "and promotion require separate authority."
            ),
            "commands": [
                {
                    "label": "frontier",
                    "command": f"loopx --format json auto-research frontier --goal-id {goal} --agent-id {agent}",
                },
                {
                    "label": "board",
                    "command": f"loopx --format json auto-research board --goal-id {goal} --agent-id {agent}",
                },
            ],
        },
        "claim_boundary": claim_boundary,
        "value_metrics": [
            {
                "label": "Rollout held-out context",
                "value": _metric_display(best_holdout),
                "baseline": _metric_display(baseline),
                "interpretation": "Shown as rollout or replay context, not as a live Codex holdout claim.",
                "source": "evidence_graph.best_holdout_metric",
            },
            {
                "label": "Dev to holdout transfer",
                "value": f"{_metric_display(best_dev)} -> {_metric_display(best_holdout)}",
                "baseline": "dev evidence before promotion",
                "interpretation": "The board keeps dev iteration, held-out context, and public claim authority separate.",
                "source": "research_evidence_graph_v0",
            },
            {
                "label": "Promotion candidates",
                "value": str(len(promotion_candidates)),
                "baseline": "0 without evidence",
                "interpretation": "Candidates remain review items; the board does not auto-promote or make first-screen claims.",
                "source": "artifact_packet.decision_packet",
            },
            {
                "label": "User gates visible",
                "value": str(len(_board_user_gates())),
                "baseline": "0 hidden gates",
                "interpretation": "Human takeover points are part of the product surface, not buried in logs.",
                "source": "user_gates",
            },
        ],
        "lane_contract": {
            "topology": "decentralized",
            "anti_pattern": "single leader agent owns the whole hypothesis tree",
            "lanes": _board_lanes(agent),
        },
        "frontier": frontier,
        "evidence_graph": graph,
        "artifact_packet": artifact,
        "decision_candidates": {
            "promotion_candidates": promotion_candidates,
            "retry_candidates": retry_candidates,
            "retirement_candidates": retirement_candidates,
        },
        "user_gates": _board_user_gates(),
        "showcase_projection": showcase,
        "quality_gates": [
            "All promoted work needs split-aware evidence.",
            "Protected scope edits fail the promotion gate.",
            "Every hypothesis stays todo-linked and agent-scoped.",
            "Negative evidence remains visible as reusable research memory.",
            "Public boards render projections, not raw logs or private planning text.",
        ],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "raw_source_bodies_recorded": False,
            "source": "read_only_auto_research_projection",
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


def build_research_decision_candidates(evidence_graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Derive public promotion and retirement candidates from evidence graph nodes."""

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
            promotion_candidates.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "todo_id": todo_id,
                    "status": status,
                    "dev_metric": dev_metric,
                    "holdout_metric": holdout_metric,
                    "evidence_event_count": evidence_count,
                    "requires": requires,
                    "source_kind": source_kind,
                }
            )
    return {
        "promotion_candidates": promotion_candidates,
        "retirement_candidates": retirement_candidates,
    }


def build_research_artifact_packet(
    evidence_graph: dict[str, Any],
    *,
    question: str | None = None,
) -> dict[str, Any]:
    """Project the evidence graph into a user-facing research artifact chain.

    This is a read-only product packet. It does not introduce a leader agent or
    a second source of truth; every claim points back to graph nodes, todo ids,
    rollout/event source kind, and compact artifact references.
    """

    graph = _json_obj(evidence_graph, field="evidence_graph")
    schema = _compact_public_token(graph.get("schema_version"), field="evidence_graph.schema_version")
    if schema != RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION:
        raise ValueError(f"evidence_graph.schema_version must be {RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION}")
    goal = _compact_public_token(graph.get("goal_id"), field="evidence_graph.goal_id")
    source_kind = _compact_optional_token(
        graph.get("source_kind"),
        field="evidence_graph.source_kind",
        default="unknown_source",
    )
    artifact_question = _compact_optional_text(
        question,
        field="artifact_question",
        default=f"What does the current auto-research evidence support for {goal}?",
        max_len=240,
    )
    decision_candidates = build_research_decision_candidates(graph)

    source_map: list[dict[str, Any]] = []
    claim_ledger: list[dict[str, Any]] = []
    citation_items: list[dict[str, Any]] = []
    contradicted_items: list[dict[str, Any]] = []
    retry_items: list[dict[str, Any]] = []
    unresolved_items: list[dict[str, Any]] = []

    for raw_node in graph.get("nodes") or []:
        if not isinstance(raw_node, dict):
            continue
        hypothesis_id = _compact_public_token(raw_node.get("hypothesis_id"), field="artifact.node.hypothesis_id")
        todo_id = _compact_public_token(raw_node.get("todo_id"), field="artifact.node.todo_id")
        claimed_by = _compact_public_token(raw_node.get("claimed_by"), field="artifact.node.claimed_by")
        status = _compact_optional_token(raw_node.get("status"), field="artifact.node.status", default="active")
        evidence_count = int(raw_node.get("evidence_event_count") or 0)
        negative_count = int(raw_node.get("negative_evidence_count") or 0)
        retry_count = int(raw_node.get("needs_retry_count") or 0)
        artifact_refs = _compact_public_text_list(raw_node.get("artifact_refs"), field="artifact.node.artifact_refs")
        grounding_refs = _compact_public_text_list(raw_node.get("grounding_refs"), field="artifact.node.grounding_refs")
        splits = [
            _compact_public_token(split, field="artifact.node.splits[]")
            for split in raw_node.get("splits", [])
        ]
        node_source_kind = _compact_optional_token(
            raw_node.get("source_kind"),
            field="artifact.node.source_kind",
            default=source_kind,
        )
        source_refs = [f"hypothesis:{hypothesis_id}", *grounding_refs, *artifact_refs]
        source_map.append(
            {
                "source_id": f"hypothesis:{hypothesis_id}",
                "source_kind": node_source_kind,
                "todo_id": todo_id,
                "claimed_by": claimed_by,
                "status": status,
                "grounding_refs": grounding_refs,
                "artifact_refs": artifact_refs,
                "split_refs": splits,
            }
        )
        claim_ledger.append(
            {
                "claim_id": f"claim:{hypothesis_id}",
                "hypothesis_id": hypothesis_id,
                "todo_id": todo_id,
                "claimed_by": claimed_by,
                "status": status,
                "evidence_event_count": evidence_count,
                "best_dev_metric": _finite_float(raw_node.get("best_dev_metric"), field="artifact.node.best_dev_metric"),
                "best_holdout_metric": _finite_float(
                    raw_node.get("best_holdout_metric"),
                    field="artifact.node.best_holdout_metric",
                ),
                "source_id": f"hypothesis:{hypothesis_id}",
            }
        )
        citation_items.append(
            {
                "citation_id": f"citation:{hypothesis_id}",
                "supports_claim_id": f"claim:{hypothesis_id}",
                "source_refs": source_refs,
                "split_refs": splits,
                "public_safe": True,
            }
        )
        if status in {"contradicted", "retired"} or negative_count:
            contradicted_items.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "todo_id": todo_id,
                    "status": status,
                    "negative_evidence_count": negative_count,
                    "source_id": f"hypothesis:{hypothesis_id}",
                }
            )
        elif status == "needs_retry" or retry_count:
            retry_items.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "todo_id": todo_id,
                    "status": status,
                    "needs_retry_count": retry_count,
                    "source_id": f"hypothesis:{hypothesis_id}",
                }
            )
        elif status not in {"supported", "promoted"} and evidence_count == 0:
            unresolved_items.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "todo_id": todo_id,
                    "status": status,
                    "source_id": f"hypothesis:{hypothesis_id}",
                }
            )

    has_promotion = bool(decision_candidates["promotion_candidates"])
    has_retirement = bool(decision_candidates["retirement_candidates"] or contradicted_items)
    if has_promotion:
        recommended_decision = "review_promotion_candidate"
    elif has_retirement:
        recommended_decision = "review_retirement_candidate"
    elif retry_items:
        recommended_decision = "review_retry_candidate"
    else:
        recommended_decision = "continue_research"

    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_ARTIFACT_PACKET_SCHEMA_VERSION,
        "goal_id": goal,
        "question": artifact_question,
        "source_kind": source_kind,
        "rollout_backed": source_kind == ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND,
        "source_map": source_map,
        "claim_ledger": claim_ledger,
        "contradiction_review": {
            "negative_evidence_count": int(graph.get("negative_evidence_count") or 0),
            "needs_retry_count": int(graph.get("needs_retry_count") or 0),
            "contradicted_or_retired": contradicted_items,
            "needs_retry": retry_items,
            "unresolved_without_evidence": unresolved_items,
        },
        "citation_packet": {
            "schema_version": "auto_research_citation_packet_v0",
            "items": citation_items,
            "raw_source_bodies_included": False,
        },
        "decision_packet": {
            "schema_version": "auto_research_decision_packet_v0",
            "recommended_decision": recommended_decision,
            "promotion_candidates": decision_candidates["promotion_candidates"],
            "retirement_candidates": decision_candidates["retirement_candidates"],
            "requires_operator_gate": has_promotion,
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "raw_source_bodies_recorded": False,
            "source": source_kind,
        },
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


def build_research_showcase_projection(
    fixture: dict[str, Any],
    *,
    evidence_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = fixture["research_contract"]
    graph = evidence_graph or build_research_evidence_graph(fixture)
    decision_candidates = build_research_decision_candidates(graph)
    promoted = [
        node["hypothesis_id"]
        for node in graph["nodes"]
        if node["status"] == "promoted"
    ]
    retired = [item["hypothesis_id"] for item in decision_candidates["retirement_candidates"]]
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
        "promotion_candidates": decision_candidates["promotion_candidates"],
        "retirement_candidates": decision_candidates["retirement_candidates"],
        "promoted_hypotheses": promoted,
        "retired_or_contradicted_hypotheses": retired,
        "negative_evidence_count": graph["negative_evidence_count"],
        "decentralized_pattern": "todo_linked_hypotheses_agent_scoped_frontier_shared_evidence_graph",
        "source_kind": graph["source_kind"],
    }


def render_auto_research_projection_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    frontier = payload["frontier"]  # type: ignore[index]
    graph = payload["evidence_graph"]  # type: ignore[index]
    showcase = payload["showcase_projection"]  # type: ignore[index]
    artifact = payload.get("artifact_packet") if isinstance(payload.get("artifact_packet"), dict) else {}
    selected = frontier.get("selected") if isinstance(frontier, dict) else None
    citation_packet = artifact.get("citation_packet") if isinstance(artifact.get("citation_packet"), dict) else {}
    decision_packet = artifact.get("decision_packet") if isinstance(artifact.get("decision_packet"), dict) else {}
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
        f"- promotion candidates: `{len(frontier.get('promotion_candidates') or [])}`",
        f"- retirement candidates: `{len(frontier.get('retirement_candidates') or [])}`",
        f"- artifact packet: `{artifact.get('schema_version')}`",
        f"- source map entries: `{len(artifact.get('source_map') or [])}`",
        f"- claim ledger entries: `{len(artifact.get('claim_ledger') or [])}`",
        f"- citation items: `{len(citation_packet.get('items') or [])}`",
        f"- recommended decision: `{decision_packet.get('recommended_decision')}`",
    ]
    return "\n".join(lines) + "\n"


def render_auto_research_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# LoopX Auto Research\n\n- ok: `False`\n- error: `{payload.get('error')}`\n"
    if payload.get("schema_version") == AUTO_RESEARCH_DEMO_ACCEPTANCE_PACKET_SCHEMA_VERSION:
        surface = payload.get("surface") if isinstance(payload.get("surface"), dict) else {}
        summary = (
            payload.get("readiness_summary")
            if isinstance(payload.get("readiness_summary"), dict)
            else {}
        )
        board = payload.get("board_output") if isinstance(payload.get("board_output"), dict) else {}
        rehearsal = (
            payload.get("supervisor_rehearsal")
            if isinstance(payload.get("supervisor_rehearsal"), dict)
            else {}
        )
        checks = payload.get("operator_checklist") if isinstance(payload.get("operator_checklist"), list) else []
        controls = (
            payload.get("user_takeover")
            if isinstance(payload.get("user_takeover"), dict)
            else {}
        )
        control_items = (
            controls.get("operator_controls")
            if isinstance(controls.get("operator_controls"), list)
            else []
        )
        lines = [
            "# LoopX Auto Research Demo Acceptance",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- title: {surface.get('title')}",
            f"- stage: `{surface.get('stage')}`",
            f"- operator_can_review_now: `{summary.get('operator_can_review_now')}`",
            f"- ready_for_real_launch: `{summary.get('ready_for_real_launch')}`",
            f"- ready_for_public_first_screen: `{summary.get('ready_for_public_first_screen')}`",
            f"- board_read_only: `{board.get('read_only')}`",
            f"- board_source_kind: `{board.get('source_kind')}`",
            f"- board_rollout_backed: `{board.get('rollout_backed')}`",
            f"- supervisor_mode: `{rehearsal.get('mode')}`",
            f"- lane_count: `{rehearsal.get('lane_count')}`",
            f"- attach: `{rehearsal.get('attach')}`",
            f"- stop: `{rehearsal.get('stop')}`",
            "",
            "## Operator Checklist",
            "",
        ]
        for item in checks:
            lines.append(f"- {item}")
        if control_items:
            lines.extend(["", "## User Takeover", ""])
            for item in control_items:
                lines.append(f"- {item}")
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == AUTO_RESEARCH_DEMO_E2E_SCHEMA_VERSION:
        replay = payload.get("replay_result") if isinstance(payload.get("replay_result"), dict) else {}
        append = payload.get("append") if isinstance(payload.get("append"), dict) else {}
        board = payload.get("board") if isinstance(payload.get("board"), dict) else {}
        acceptance = payload.get("acceptance") if isinstance(payload.get("acceptance"), dict) else {}
        supervisor = payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}
        commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
        route = payload.get("route_contract") if isinstance(payload.get("route_contract"), dict) else {}
        live_codex = (
            payload.get("live_codex_e2e")
            if isinstance(payload.get("live_codex_e2e"), dict)
            else {}
        )
        board_claim_boundary = (
            board.get("claim_boundary")
            if isinstance(board.get("claim_boundary"), dict)
            else {}
        )
        lines = [
            "# LoopX Auto Research Demo Replay",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- mode: `{payload.get('mode')}`",
            f"- execution_kind: `{payload.get('execution_kind')}`",
            f"- result_source: `{payload.get('result_source')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- tracking_goal_id: `{payload.get('tracking_goal_id')}`",
            f"- frontier_goal_id: `{route.get('frontier_goal_id')}`",
            f"- tracking_goal_drives_frontier: `{route.get('tracking_goal_drives_frontier')}`",
            f"- agent_id: `{payload.get('agent_id')}`",
            f"- reasoning_effort: `{payload.get('reasoning_effort')}`",
            f"- replay_executed: `{replay.get('executed')}`",
            f"- replay_result_source: `{replay.get('result_source')}`",
            f"- status: `{replay.get('status')}`",
            f"- dev_metric: `{replay.get('dev_metric')}`",
            f"- holdout_metric: `{replay.get('holdout_metric')}`",
            f"- protected_scope_clean: `{replay.get('protected_scope_clean')}`",
            f"- live_codex_e2e_executed: `{live_codex.get('executed')}`",
            f"- live_codex_e2e_claim_allowed: `{live_codex.get('claim_allowed')}`",
            f"- live_codex_e2e_claim_scope: `{live_codex.get('claim_scope')}`",
            f"- live_codex_e2e_holdout_claim_allowed: `{live_codex.get('holdout_claim_allowed')}`",
            f"- live_codex_e2e_promotion_claim_allowed: `{live_codex.get('promotion_claim_allowed')}`",
            f"- live_codex_e2e_evidence_source: `{live_codex.get('evidence_source')}`",
            f"- visible_lanes_launched: `{live_codex.get('visible_lanes_launched')}`",
            f"- appended_events: `{append.get('appended_count')}`",
            f"- skipped_existing_events: `{append.get('skipped_existing_count')}`",
            f"- board_rollout_backed: `{board.get('rollout_backed')}`",
            f"- promotion_candidates: `{board.get('promotion_candidate_count')}`",
            f"- ready_for_real_launch: `{acceptance.get('ready_for_real_launch')}`",
            f"- supervisor_lanes: `{supervisor.get('lane_count')}`",
            "",
            "## Commands",
            "",
            f"- deterministic replay: `{commands.get('deterministic_replay')}`",
            f"- replay plus visible lanes: `{commands.get('deterministic_replay_with_visible_lanes')}`",
        ]
        if board_claim_boundary:
            lines.extend(
                [
                    "",
                    "## Board Claim Boundary",
                    "",
                    f"- board_live_claim_scope: `{board_claim_boundary.get('live_claim_scope')}`",
                    f"- board_holdout_result_scope: `{board_claim_boundary.get('holdout_result_scope')}`",
                    f"- board_promotion_claim_allowed: `{board_claim_boundary.get('promotion_claim_allowed')}`",
                ]
            )
        return "\n".join(lines) + "\n"
    if payload.get("schema_version") == AUTO_RESEARCH_BOARD_SCHEMA_VERSION:
        surface = payload.get("surface") if isinstance(payload.get("surface"), dict) else {}
        binding = (
            payload.get("projection_binding")
            if isinstance(payload.get("projection_binding"), dict)
            else {}
        )
        decisions = (
            payload.get("decision_candidates")
            if isinstance(payload.get("decision_candidates"), dict)
            else {}
        )
        claim_boundary = (
            payload.get("claim_boundary")
            if isinstance(payload.get("claim_boundary"), dict)
            else {}
        )
        gates = payload.get("user_gates") if isinstance(payload.get("user_gates"), list) else []
        metrics = payload.get("value_metrics") if isinstance(payload.get("value_metrics"), list) else []
        lines = [
            "# LoopX Auto Research Board",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- title: {surface.get('title')}",
            f"- stage: `{surface.get('stage')}`",
            f"- read_only: `{binding.get('read_only')}`",
            f"- source_kind: `{binding.get('source_kind')}`",
            f"- rollout_backed: `{binding.get('rollout_backed')}`",
            f"- first_screen_policy: `{binding.get('first_screen_policy')}`",
            f"- live_claim_scope: `{claim_boundary.get('live_claim_scope')}`",
            f"- holdout_result_scope: `{claim_boundary.get('holdout_result_scope')}`",
            f"- promotion_claim_allowed: `{claim_boundary.get('promotion_claim_allowed')}`",
            f"- first_screen_claim_allowed: `{claim_boundary.get('first_screen_claim_allowed')}`",
            f"- value metrics: `{len(metrics)}`",
            f"- promotion candidates: `{len(decisions.get('promotion_candidates') or [])}`",
            f"- retirement candidates: `{len(decisions.get('retirement_candidates') or [])}`",
            f"- user gates: `{len(gates)}`",
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
        acceptance = (
            payload.get("demo_acceptance")
            if isinstance(payload.get("demo_acceptance"), dict)
            else {}
        )
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
                f"- `{profile.get('role_id')}`: skill `{profile.get('required_skill')}` / "
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
            lines.append(f"- required_skill: `{profile.get('required_skill')}`")
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
        accept_when = acceptance.get("operator_can_accept_when") or []
        reject_when = acceptance.get("operator_must_reject_when") or []
        if accept_when or reject_when:
            lines.extend(["", "## Demo Acceptance", ""])
            for item in accept_when:
                lines.append(f"- accept when: {item}")
            for item in reject_when:
                lines.append(f"- reject when: {item}")
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
        for line in commands.get("start_script") or []:
            lines.append(f"- `{line}`")
        lines.extend(
            [
                "",
                "## Attach",
                "",
                f"`{commands.get('attach')}`",
            ]
        )
        return "\n".join(lines) + "\n"
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
