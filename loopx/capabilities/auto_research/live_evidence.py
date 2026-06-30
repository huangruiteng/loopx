from __future__ import annotations

import json
from pathlib import Path

from .core import (
    AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
    load_auto_research_evidence_packet,
    validate_auto_research_evidence_packet,
)


LIVE_CODEX_E2E_EVIDENCE_SCHEMA_VERSION = "auto_research_live_codex_lane_e2e_evidence_v0"
LIVE_CODEX_E2E_DEFAULT_OUTPUT = "live-codex-e2e-evidence.public.json"


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"live evidence field `{key}` must be an object")
    return value


def _require_bool(value: object, *, field: str, expected: bool = True) -> None:
    if value is not expected:
        raise ValueError(f"live evidence field `{field}` must be {expected}")


def _require_positive_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"live evidence field `{field}` must be a positive integer")
    return value


def _assert_live_evidence_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    if leaked:
        raise ValueError("live evidence must be compact and public-safe; forbidden material detected")


def _load_json_object(path: str | Path, *, field: str) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{field} must be readable JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{field} root must be an object")
    return payload


def _metric_by_split(packet: dict[str, object], split: str) -> object:
    for event in packet.get("evidence_events") or []:
        if not isinstance(event, dict) or event.get("split") != split:
            continue
        metric = event.get("metric")
        if isinstance(metric, dict):
            return metric.get("value")
    return None


def build_live_codex_e2e_evidence_from_packet(
    *,
    packet: dict[str, object],
    append_result: dict[str, object],
    agent_id: str,
    lane_count: int,
    visible_lanes_accepted: bool,
) -> dict[str, object]:
    packet = validate_auto_research_evidence_packet(packet)
    if append_result.get("schema_version") != AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION:
        raise ValueError(f"append result schema_version must be {AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION}")
    if append_result.get("dry_run") is not False:
        raise ValueError("append result must come from a real append-evidence run")
    summary = packet["summary"]
    goal_id = summary["goal_id"]
    if append_result.get("goal_id") != goal_id:
        raise ValueError("append result goal_id must match the evidence packet")
    if str(agent_id) != str(packet["hypothesis"]["claimed_by"]):
        raise ValueError("agent_id must match the packet hypothesis claimed_by field")
    if not isinstance(lane_count, int) or lane_count <= 0:
        raise ValueError("lane_count must be a positive integer")
    if not visible_lanes_accepted:
        raise ValueError("live evidence capture requires accepted visible lanes")
    if append_result.get("appended_count", 0) <= 0:
        raise ValueError("append result must include at least one fresh appended event")
    counts = append_result.get("counts_by_kind")
    if not isinstance(counts, dict) or int(counts.get("research_evidence") or 0) <= 0:
        raise ValueError("append result must include at least one research_evidence event")
    if summary.get("status") != "supported":
        raise ValueError("live evidence can only be captured from a supported packet")
    if summary.get("protected_scope_clean") is not True:
        raise ValueError("live evidence requires protected_scope_clean=true")
    if int(summary.get("negative_evidence_count") or 0) != 0:
        raise ValueError("live evidence requires zero negative evidence")
    if int(summary.get("needs_retry_count") or 0) != 0:
        raise ValueError("live evidence requires zero retry-needed evidence")
    payload = {
        "ok": True,
        "schema_version": LIVE_CODEX_E2E_EVIDENCE_SCHEMA_VERSION,
        "source": "live_codex_lane_output",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "visible_lanes": {
            "launched": True,
            "accepted": True,
            "lane_count": lane_count,
        },
        "lane_evidence": {
            "lane_authored": True,
            "evidence_source": "live_codex_lane_output",
            "append_status": "appended_to_loopx_state",
            "evidence_event_count": int(summary["evidence_event_count"]),
            "result_status": summary["status"],
            "protected_scope_clean": True,
            "dev_metric": _metric_by_split(packet, "dev"),
            "holdout_metric": _metric_by_split(packet, "holdout"),
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
        },
    }
    _assert_live_evidence_public_safe(payload)
    return payload


def capture_live_codex_e2e_evidence(
    *,
    packet_path: str,
    append_result_path: str,
    agent_id: str,
    lane_count: int,
    visible_lanes_accepted: bool,
) -> dict[str, object]:
    packet = load_auto_research_evidence_packet(packet_path)
    append_result = _load_json_object(append_result_path, field="append_result_file")
    return build_live_codex_e2e_evidence_from_packet(
        packet=packet,
        append_result=append_result,
        agent_id=agent_id,
        lane_count=lane_count,
        visible_lanes_accepted=visible_lanes_accepted,
    )


def load_live_codex_e2e_evidence(
    *,
    evidence_path: str,
    goal_id: str,
    agent_id: str,
) -> dict[str, object]:
    try:
        raw = Path(evidence_path).read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as exc:
        raise ValueError("live evidence must be readable JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("live evidence root must be an object")
    if payload.get("schema_version") != LIVE_CODEX_E2E_EVIDENCE_SCHEMA_VERSION:
        raise ValueError(
            "live evidence schema_version must be "
            f"{LIVE_CODEX_E2E_EVIDENCE_SCHEMA_VERSION}"
        )
    if payload.get("source") != "live_codex_lane_output":
        raise ValueError("live evidence source must be live_codex_lane_output")
    if payload.get("goal_id") != goal_id:
        raise ValueError("live evidence goal_id does not match the demo goal")
    if payload.get("agent_id") != agent_id:
        raise ValueError("live evidence agent_id does not match the demo agent")

    visible = _require_dict(payload, "visible_lanes")
    lane_evidence = _require_dict(payload, "lane_evidence")
    boundary = _require_dict(payload, "public_boundary")
    _require_bool(visible.get("launched"), field="visible_lanes.launched")
    _require_bool(visible.get("accepted"), field="visible_lanes.accepted")
    lane_count = _require_positive_int(visible.get("lane_count"), field="visible_lanes.lane_count")
    _require_bool(lane_evidence.get("lane_authored"), field="lane_evidence.lane_authored")
    if lane_evidence.get("evidence_source") != "live_codex_lane_output":
        raise ValueError("lane_evidence.evidence_source must be live_codex_lane_output")
    if lane_evidence.get("append_status") != "appended_to_loopx_state":
        raise ValueError("lane_evidence.append_status must be appended_to_loopx_state")
    evidence_event_count = _require_positive_int(
        lane_evidence.get("evidence_event_count"),
        field="lane_evidence.evidence_event_count",
    )
    if lane_evidence.get("result_status") != "supported":
        raise ValueError("lane_evidence.result_status must be supported")
    _require_bool(
        lane_evidence.get("protected_scope_clean"),
        field="lane_evidence.protected_scope_clean",
    )
    for key in (
        "raw_logs_recorded",
        "private_artifacts_recorded",
        "absolute_paths_recorded",
        "credentials_recorded",
    ):
        _require_bool(boundary.get(key), field=f"public_boundary.{key}", expected=False)
    _require_bool(
        boundary.get("local_workspace_path_redacted"),
        field="public_boundary.local_workspace_path_redacted",
    )
    _assert_live_evidence_public_safe(payload)
    return {
        "schema_version": payload["schema_version"],
        "source": payload["source"],
        "goal_id": goal_id,
        "agent_id": agent_id,
        "lane_count": lane_count,
        "evidence_event_count": evidence_event_count,
        "result_status": lane_evidence.get("result_status"),
        "protected_scope_clean": True,
        "dev_metric": lane_evidence.get("dev_metric"),
        "holdout_metric": lane_evidence.get("holdout_metric"),
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
        },
    }


def build_live_codex_claim_from_evidence(evidence: dict[str, object]) -> dict[str, object]:
    return {
        "executed": True,
        "claim_allowed": True,
        "visible_lanes_launched": True,
        "visible_lanes_accepted": True,
        "evidence_source": "live_codex_lane_output",
        "reason": (
            "compact live Codex lane-authored evidence was validated; raw transcripts, "
            "private artifacts, credentials, and local paths were not recorded."
        ),
        "evidence_schema_version": evidence.get("schema_version"),
        "lane_count": evidence.get("lane_count"),
        "evidence_event_count": evidence.get("evidence_event_count"),
        "result_status": evidence.get("result_status"),
        "protected_scope_clean": evidence.get("protected_scope_clean"),
        "dev_metric": evidence.get("dev_metric"),
        "holdout_metric": evidence.get("holdout_metric"),
        "public_boundary": evidence.get("public_boundary"),
    }
