"""Reusable runtime fixtures for the status markdown smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from status_markdown_fixtures import (
    APPROVED_COMMAND,
    CONNECTED_READONLY_ACTION,
    CONNECTED_READONLY_CLASSIFICATION,
    CONNECTED_READONLY_GOAL_ID,
    DELIVERY_ACTION,
    DELIVERY_GOAL_ID,
    POST_HANDOFF_ACTION,
    POST_HANDOFF_CLASSIFICATION,
    REGISTRY_OVERRIDE_ACTION,
    REGISTRY_OVERRIDE_HANDOFF,
    REGISTRY_OVERRIDE_QUESTION,
    REGISTRY_OVERRIDE_STATUS,
)


def _append_index_record(run_dir: Path, record: dict, json_path: Path, markdown_path: Path) -> None:
    with (run_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    **record,
                    "json_path": str(json_path),
                    "markdown_path": str(markdown_path),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def append_connected_delivery_fixture(
    root: Path,
    *,
    generated_at: str,
    classification: str = "delivery_ranker_readiness_batch",
) -> None:
    run_dir = root / "runtime" / "goals" / DELIVERY_GOAL_ID / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-connected-delivery.json"
    markdown_path = run_dir / f"{compact_time}-connected-delivery.md"
    record = {
        "generated_at": generated_at,
        "goal_id": DELIVERY_GOAL_ID,
        "classification": classification,
        "recommended_action": DELIVERY_ACTION,
        "health_check": "fixture connected delivery run with custom classification",
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture connected delivery run\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_connected_readonly_progress_fixture(root: Path, *, generated_at: str) -> None:
    run_dir = root / "runtime" / "goals" / CONNECTED_READONLY_GOAL_ID / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-connected-readonly-progress.json"
    markdown_path = run_dir / f"{compact_time}-connected-readonly-progress.md"
    record = {
        "generated_at": generated_at,
        "goal_id": CONNECTED_READONLY_GOAL_ID,
        "classification": CONNECTED_READONLY_CLASSIFICATION,
        "recommended_action": CONNECTED_READONLY_ACTION,
        "health_check": "fixture connected read-only progress run",
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture connected read-only progress run\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_operator_gate_fixture(
    root: Path,
    *,
    decision: str,
    generated_at: str,
    recommended_action: str,
) -> None:
    run_dir = root / "runtime" / "goals" / "planned-main-control" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-operator-gate.json"
    markdown_path = run_dir / f"{compact_time}-operator-gate.md"
    operator_gate = {
        "recorded_at": generated_at,
        "gate": "read_only_map_opt_in",
        "decision": decision,
        "operator_question": "是否同意 `planned-main-control` 先执行 read-only map opt-in？",
        "reason_summary": f"{decision} fixture reason",
    }
    if decision == "approve":
        operator_gate["agent_command"] = APPROVED_COMMAND
    resume_contract = {
        "version": "operator_gate_resume_contract_v0",
        "goal_id": "planned-main-control",
        "run_id": f"{compact_time}-operator-gate",
        "gate_id": "read_only_map_opt_in",
        "created_state_ref": "goal=planned-main-control; status=planned-high-complexity; latest_run=none",
        "created_policy_version": "operator_gate_resume_contract_v0",
        "interrupt_payload": {
            "question": operator_gate["operator_question"],
            "choices": ["approve", "defer", "reject"],
        },
        "allowed_decisions": ["approve", "defer", "reject"],
        "operator_decision": decision,
        "latest_state_ref": "goal=planned-main-control; status=planned-high-complexity; latest_run=none",
        "freshness_check": "resume must re-read current decision-point authority: registry, ACTIVE_GOAL_STATE, quota, repo dirty/ref snapshot, policy, and run status",
        "precondition_check": "decision is actionable only at this gate decision point if current authority still matches the gate intent and stop condition",
        "migration_or_rebase_result": "decision_point_rebase_only; do not restore, rewind, or carry the whole repo/worktree back to the created checkpoint",
        "resulting_action": recommended_action,
        "validation_after_resume": "after resume, run the approved command in its declared mode and record validation before quota spend or follow-up side effects",
    }
    classification = {
        "approve": "operator_gate_approved",
        "reject": "operator_gate_rejected",
        "defer": "operator_gate_deferred",
    }[decision]
    record = {
        "generated_at": generated_at,
        "goal_id": "planned-main-control",
        "classification": classification,
        "recommended_action": recommended_action,
        "health_check": (
            f"fixture operator_gate decision={decision}; "
            f"agent_command {1 if decision == 'approve' else 0}/1"
        ),
        "operator_gate": operator_gate,
        "operator_gate_resume_contract": resume_contract,
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture operator gate approval\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_quota_slot_spend_fixture(root: Path, *, generated_at: str) -> None:
    run_dir = root / "runtime" / "goals" / "planned-main-control" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-quota-slot-spent.json"
    markdown_path = run_dir / f"{compact_time}-quota-slot-spent.md"
    record = {
        "generated_at": generated_at,
        "goal_id": "planned-main-control",
        "classification": "quota_slot_spent",
        "recommended_action": "account for one automatic heartbeat slot",
        "health_check": "fixture quota slot spend event",
        "quota_event": {
            "event_type": "quota_slot_spent",
            "source": "heartbeat",
            "slots": 1,
        },
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture quota slot spend\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_post_handoff_run_fixture(root: Path, *, generated_at: str) -> None:
    run_dir = root / "runtime" / "goals" / "planned-main-control" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-post-handoff-run.json"
    markdown_path = run_dir / f"{compact_time}-post-handoff-run.md"
    record = {
        "generated_at": generated_at,
        "goal_id": "planned-main-control",
        "classification": POST_HANDOFF_CLASSIFICATION,
        "recommended_action": POST_HANDOFF_ACTION,
        "health_check": "fixture target agent run after approved handoff",
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture post-handoff run\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_state_refreshed_fixture(root: Path, *, generated_at: str) -> None:
    run_dir = root / "runtime" / "goals" / "planned-main-control" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-state-refreshed.json"
    markdown_path = run_dir / f"{compact_time}-state-refreshed.md"
    record = {
        "generated_at": generated_at,
        "goal_id": "planned-main-control",
        "classification": "state_refreshed",
        "recommended_action": "inspect refreshed active goal state and continue",
        "health_check": "fixture state refresh",
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture state refresh\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_orphan_runtime_fixture(root: Path, *, goal_id: str, generated_at: str) -> None:
    run_dir = root / "runtime" / "goals" / goal_id / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-operator-gate-approved.json"
    markdown_path = run_dir / f"{compact_time}-operator-gate-approved.md"
    record = {
        "generated_at": generated_at,
        "goal_id": goal_id,
        "classification": "operator_gate_approved",
        "recommended_action": "orphan runtime fixture should only appear in global views",
        "health_check": "fixture orphan runtime goal",
        "operator_gate": {
            "recorded_at": generated_at,
            "gate": "read_only_map_opt_in",
            "decision": "approve",
        },
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture orphan runtime goal\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)


def append_stale_state_projection_fixture(root: Path) -> None:
    goal_id = "planned-main-control"
    state_path = root / "project" / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
    old_state_text = state_path.read_text(encoding="utf-8")
    old_state_text = old_state_text.replace(
        "updated_at: 2026-01-01T00:00:00+00:00",
        "updated_at: 2026-01-01T00:01:00+00:00",
    )
    state_path.write_text(old_state_text, encoding="utf-8")
    run_dir = root / "runtime" / "goals" / goal_id / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    generated_at = "2026-01-01T00:02:00+00:00"
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-state-refreshed.json"
    markdown_path = run_dir / f"{compact_time}-state-refreshed.md"
    record = {
        "generated_at": generated_at,
        "goal_id": goal_id,
        "classification": "state_refreshed",
        "recommended_action": "inspect refreshed active goal state and continue",
        "health_check": "fixture state refresh with stale later active state",
        "state": {
            "sha256_16": hashlib.sha256(old_state_text.encode("utf-8")).hexdigest()[:16],
            "frontmatter": {
                "status": "planned-high-complexity",
                "updated_at": "2026-01-01T00:01:00+00:00",
            },
        },
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture state refresh\n", encoding="utf-8")
    _append_index_record(run_dir, record, json_path, markdown_path)
    new_state_text = old_state_text.replace(
        "updated_at: 2026-01-01T00:01:00+00:00",
        "updated_at: 2026-01-01T00:03:00+00:00",
    )
    state_path.write_text(new_state_text, encoding="utf-8")


def set_registry_attention_override(registry_path: Path) -> None:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["goals"][0].update(
        {
            "waiting_on": "user_or_controller",
            "attention_status": REGISTRY_OVERRIDE_STATUS,
            "recommended_action": REGISTRY_OVERRIDE_ACTION,
            "operator_question": REGISTRY_OVERRIDE_QUESTION,
            "next_handoff_condition": REGISTRY_OVERRIDE_HANDOFF,
        }
    )
    registry_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
