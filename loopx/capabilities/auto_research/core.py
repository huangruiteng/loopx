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
AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION = "auto_research_rollout_append_v0"
AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION = "auto_research_quickstart_v0"
AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION = "auto_research_demo_supervisor_plan_v0"
AUTO_RESEARCH_DEFAULT_GOAL_ID = "loopx-auto-research-knn"
AUTO_RESEARCH_DEFAULT_OBJECTIVE = "Improve exact k-nearest-neighbor inference under a protected evaluator."
AUTO_RESEARCH_QUICKSTART_TEMPLATE = "knn-exact"
ROLLOUT_EVIDENCE_GRAPH_SOURCE_KIND = "loopx_rollout_event_log"
AUTO_RESEARCH_DEMO_DEFAULT_LANES = (
    (
        "codex-side-bypass",
        "hypothesis-runner",
        "Claim the next runnable hypothesis and run dev evidence without owning promotion.",
    ),
    (
        "codex-product-capability",
        "evidence-promoter",
        "Read scored evidence, promotion candidates, and product metric gaps.",
    ),
    (
        "codex-main-control",
        "control-plane-guard",
        "Guard repo, review, merge, and user-gate boundaries without acting as a research leader.",
    ),
    (
        "codex-value-explorer",
        "research-narrator",
        "Turn accepted evidence into public-safe showcase and value-metric summaries.",
    ),
)

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


def _demo_lane_specs(agent_specs: Iterable[str] | None) -> list[dict[str, str]]:
    raw_specs = list(agent_specs or [])
    parsed_specs: list[tuple[str, str, str]] = []
    if raw_specs:
        for index, raw in enumerate(raw_specs, start=1):
            text = _compact_public_text(raw, field="agent[]", max_len=180)
            if ":" in text:
                agent_id, lane_id = text.split(":", 1)
            else:
                agent_id = text
                lane_id = f"research-lane-{index}"
            parsed_specs.append(
                (
                    _compact_public_token(agent_id, field="agent_id"),
                    _compact_public_token(lane_id, field="lane_id"),
                    "Work from the shared LoopX frontier for this lane; do not assume a leader agent.",
                )
            )
    else:
        parsed_specs = list(AUTO_RESEARCH_DEMO_DEFAULT_LANES)

    lanes: list[dict[str, str]] = []
    seen_agents: set[str] = set()
    seen_lanes: set[str] = set()
    for agent_id, lane_id, responsibility in parsed_specs:
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


def _env_bootstrap_command(*, cli_bin: str, goal_id: str, agent_id: str) -> str:
    return (
        f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
        "--project \"$LOOPX_PROJECT\" "
        f"--goal-id {_shell_arg(goal_id)} --agent-id {_shell_arg(agent_id)}"
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
    lanes = _demo_lane_specs(agent_specs)

    pane_plans: list[dict[str, Any]] = []
    for lane in lanes:
        agent_id = lane["agent_id"]
        lane_id = lane["lane_id"]
        quota_command = _env_quota_command(cli_bin=cli, goal_id=goal, agent_id=agent_id)
        frontier_command = _env_frontier_command(cli_bin=cli, goal_id=goal, agent_id=agent_id)
        bootstrap_command = _env_bootstrap_command(cli_bin=cli, goal_id=goal, agent_id=agent_id)
        pane_plans.append(
            {
                "lane_id": lane_id,
                "agent_id": agent_id,
                "responsibility": lane["responsibility"],
                "window_name": lane_id,
                "quota_guard": quota_command,
                "frontier": frontier_command,
                "bootstrap_message": bootstrap_command,
                "visible_codex_tui": codex,
                "start_sequence": [
                    "run quota_guard and stop when user_channel.action_required=true",
                    "render the lane frontier from LoopX state",
                    "print the public-safe bootstrap message for this visible TUI",
                    "start Codex CLI visibly; do not inject hidden prompts into an existing session",
                ],
                "lane_timeline": [
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
                        "operator_visible_signal": "public-safe Codex bootstrap message printed in the lane pane",
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
        "set -euo pipefail",
        ": ${LOOPX_PROJECT:?set LOOPX_PROJECT to the repo root before running}",
        ": ${LOOPX_REGISTRY:?set LOOPX_REGISTRY to the LoopX registry path before running}",
        ": ${LOOPX_RUNTIME_ROOT:?set LOOPX_RUNTIME_ROOT to the LoopX runtime root before running}",
    ]
    start_script = [
        *env_lines,
        f"{_shell_arg(tmux)} new-session -d -s {_shell_arg(session)} -n frontier",
        (
            f"{_shell_arg(tmux)} send-keys -t {_shell_arg(session)}:frontier "
            f"{_shell_arg(_env_frontier_command(cli_bin=cli, goal_id=goal, agent_id=lanes[0]['agent_id']))} C-m"
        ),
    ]
    for pane in pane_plans:
        lane_id = str(pane["lane_id"])
        lane_command = (
            f"cd \"$LOOPX_PROJECT\"; {pane['quota_guard']}; {pane['frontier']}; "
            f"{pane['bootstrap_message']}; {pane['visible_codex_tui']}"
        )
        start_script.extend(
            [
                f"{_shell_arg(tmux)} new-window -d -t {_shell_arg(session)} -n {_shell_arg(lane_id)}",
                f"{_shell_arg(tmux)} send-keys -t {_shell_arg(session)}:{_shell_arg(lane_id)} {_shell_arg(lane_command)} C-m",
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
        "coordination_model": {
            "leader_agent_required": False,
            "supervisor_role": "host_shell_layout_only",
            "source_of_truth": [
                "quota_should_run",
                "todo_claims",
                "auto_research_frontier",
                "research_evidence_graph",
            ],
            "decentralized_rule": "each lane reads its own quota/frontier projection and writes back through normal LoopX todo/evidence APIs",
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
                "lanes[].quota_guard",
                "lanes[].frontier",
                "lanes[].bootstrap_message",
                "lanes[].lane_timeline",
                "user_takeover.operator_controls",
                "boundary",
            ],
            "operator_can_accept_when": [
                "the rehearsal script prints the real start script without executing it",
                "every lane has a quota guard before frontier/bootstrap/Codex startup",
                "the attach command is visible before any Codex prompt is accepted",
                "the stop command and terminal interrupt path are visible",
                "boundary fields prove no tmux/Codex/state/quota side effects in dry-run mode",
            ],
            "operator_must_reject_when": [
                "a lane can start without quota should-run",
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
                "each lane window prints its own quota guard before Codex starts",
                "each lane window prints its own auto-research frontier before Codex starts",
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
        },
        "operator_notes": [
            "Set LOOPX_PROJECT, LOOPX_REGISTRY, and LOOPX_RUNTIME_ROOT in the user shell before running the script.",
            "Attach to tmux before accepting any Codex prompt so every lane stays visible and interruptible.",
            "Use the printed quota/frontier packet in each pane to decide whether that lane should continue, ask, or stop.",
        ],
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
                f"- `{item.get('lane_id')}` / `{item.get('agent_id')}`: {item.get('responsibility')}"
            )
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
    return render_auto_research_projection_markdown(payload)
