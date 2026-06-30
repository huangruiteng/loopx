from __future__ import annotations

import json
from pathlib import Path


LIVE_CODEX_E2E_EVIDENCE_SCHEMA_VERSION = "auto_research_live_codex_lane_e2e_evidence_v0"


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
