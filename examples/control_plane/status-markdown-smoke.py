#!/usr/bin/env python3
"""Smoke-test agent-facing status and quota hints.

This stays dependency-free and uses the public status collector against a
temporary planned read-only-map goal.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import (  # noqa: E402
    build_promotion_readiness_summary,
    build_contract_health_projection,
    collect_status,
    delivery_batch_scale_for_run,
    delivery_outcome_for_run,
    project_asset_summary_is_public_safe,
    project_asset_todo_summary,
    render_status_markdown,
)
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.cli_commands.status import attach_agent_lane_next_actions, _review_handoff_agent  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.handoff_budget import PROJECT_AGENT_HANDOFF_BUDGET  # noqa: E402


OLD_PLANNED_ACTION = "先审阅 LoopX operator gate；同意后再发送项目 agent 命令"
NEW_PLANNED_ACTION = "先在 LoopX 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run"
APPROVED_ACTION = "把已批准的 agent_command 发给目标项目 agent；这不是写权限授权"
APPROVED_COMMAND = "loopx read-only-map --goal-id planned-main-control --dry-run"
POST_HANDOFF_ACTION = "post-handoff fixture run is visible; choose the next bounded delivery step"
POST_HANDOFF_CLASSIFICATION = "read_only_project_map"
REJECTED_ACTION = "保持 goal 在 gate 状态，修改 handoff 后再请求 operator 判断"
DEFERRED_ACTION = "保持 goal 在 gate 状态，先补齐要求的证据后再请求判断"
REGISTRY_OVERRIDE_STATUS = "owner_sop_review_pending"
REGISTRY_OVERRIDE_ACTION = "请先完成 owner/SOP 判断；未决前不要让项目 agent 继续推进"
REGISTRY_OVERRIDE_QUESTION = "是否同意 owner/SOP review 完成后继续推进？"
REGISTRY_OVERRIDE_HANDOFF = "owner/SOP decision recorded"
USER_TODO_TEXT = "Read source topic account-vs-group note before owner review."
AGENT_TODO_TEXT = "Build the P0 two-layer config worksheet."
DELIVERY_GOAL_ID = "delivery-side-bypass"
DELIVERY_ACTION = "Continue the ranker path with the next clean readiness implementation/test batch."
DELIVERY_AGENT_TODO = "Add the readiness smoke plus the matching implementation guard when both paths are clean."
CONNECTED_READONLY_GOAL_ID = "connected-readonly-progress"
CONNECTED_READONLY_CLASSIFICATION = "status_markdown_usage_summary_progress_signal"
CONNECTED_READONLY_ACTION = "continue the next compact self-improvement slice after the progress run"
EXPLICIT_REFRESH_CLASSIFICATION = "dashboard_home_browser_smoke_regression"
DEPENDENCY_CURRENT_GOAL_ID = "meta-hardening-fixture"
DEPENDENCY_BLOCKER_GOAL_ID = "dependency-owner-gate"
DEPENDENCY_AGENT_TODO = "Continue the gate-independent P1/P2 product-hardening slice."
DEPENDENCY_MONITOR_TODO = "Side-bypass dependency monitor: observe public-safe replay transitions only."
DEPENDENCY_USER_TODO = "Confirm the sibling project evidence gate before its controller resumes delivery."


def assert_handoff_budget_contract(readiness: dict, label: str) -> None:
    budget = readiness.get("handoff_interface_budget")
    assert isinstance(budget, dict), (label, readiness)
    assert budget["mode"] == PROJECT_AGENT_HANDOFF_BUDGET["mode"], (label, budget)
    assert budget["max_lines"] == PROJECT_AGENT_HANDOFF_BUDGET["max_lines"], (label, budget)
    assert budget["max_chars"] == PROJECT_AGENT_HANDOFF_BUDGET["max_chars"], (label, budget)


def write_planned_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    goal_id = "planned-main-control"
    state_file = f".codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: planned-high-complexity\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Planned Main Control\n\n"
        "## User Todo / Owner Review Reading Queue\n\n"
        f"- [ ] {USER_TODO_TEXT}\n"
        "- [x] Open owner worksheet.\n\n"
        "## Agent Todo\n\n"
        f"- [ ] {AGENT_TODO_TEXT}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": goal_id,
                        "domain": "complex-project",
                        "status": "planned-high-complexity",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "complex_project_read_only_map_v0",
                            "status": "planned",
                        },
                        "authority_sources": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry_path


def mark_planned_todos_done(root: Path) -> None:
    goal_id = "planned-main-control"
    state_path = root / "project" / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
    state_text = state_path.read_text(encoding="utf-8")
    state_text = state_text.replace(f"- [ ] {USER_TODO_TEXT}", f"- [x] {USER_TODO_TEXT}")
    state_text = state_text.replace(f"- [ ] {AGENT_TODO_TEXT}", f"- [x] {AGENT_TODO_TEXT}")
    state_path.write_text(state_text, encoding="utf-8")


def write_connected_delivery_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{DELIVERY_GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Connected Delivery\n\n"
        "## Agent Todo\n\n"
        f"- [ ] {DELIVERY_AGENT_TODO}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": DELIVERY_GOAL_ID,
                        "domain": "connected-delivery-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_delivery_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {
                            "compute": 0.33,
                            "window_hours": 24,
                        },
                        "coordination": {
                            "write_scope": ["src/**", "tests/**"],
                            "requires_parent_approval": ["publish", "production-action"],
                        },
                        "spawn_policy": {
                            "mode": "multi_subagent",
                            "allowed": True,
                            "max_children": 2,
                            "allowed_domains": ["docs-map", "validation-map"],
                        },
                        "execution_profile": {
                            "cadence": "bounded_progress_segment",
                            "minimum_scale": "implementation",
                            "must_include": [
                                "implementation_artifact",
                                "targeted_validation",
                                "state_writeback",
                            ],
                            "spend_rule": "spend_only_after_artifact_validation_writeback",
                            "outcome_floor": {
                                "required_when": "after_surface_progress_streak",
                                "surface_streak_threshold": 2,
                                "outcome_markers": [
                                    "ranker_readiness_batch",
                                    "macro_evidence",
                                    "evidence_segment",
                                    "ranker_fit",
                                    "eval_metric",
                                ],
                                "surface_only_hints": [
                                    "forecast",
                                    "runbook",
                                    "queue",
                                    "fields",
                                ],
                                "must_advance": [
                                    "ranker_or_cross_domain_evidence",
                                ],
                                "avoid": [
                                    "surface_only_progress_loop",
                                ],
                                "if_unavailable": "report_blocker_without_spend",
                            },
                            "degradation_policy": {
                                "small_scale_streak_threshold": 3,
                                "on_degradation": "require_blocker_or_expand_next_batch",
                            },
                        },
                        "guards": [
                            "low-conflict delivery within declared write_scope",
                        ],
                        "next_probe": f"loopx quota should-run --goal-id {DELIVERY_GOAL_ID}",
                        "authority_sources": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry_path


def write_global_source_registry_shadow(root: Path, registry_path: Path, *, goal_id: str) -> None:
    runtime = root / "runtime"
    local_registry = json.loads(registry_path.read_text(encoding="utf-8"))
    goals = local_registry.get("goals") if isinstance(local_registry.get("goals"), list) else []
    local_goal = next(goal for goal in goals if isinstance(goal, dict) and goal.get("id") == goal_id)
    shadow_goal = dict(local_goal)
    shadow_goal["source_registry"] = str(root / "missing-source" / "registry.json")
    shadow_goal["synced_at"] = "2026-01-01T00:00:00+00:00"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "registry.global.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [shadow_goal],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_connected_readonly_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{CONNECTED_READONLY_GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Connected Readonly Progress\n\n"
        "## Next Action\n\n"
        f"- {CONNECTED_READONLY_ACTION}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": CONNECTED_READONLY_GOAL_ID,
                        "domain": "connected-readonly-fixture",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_readonly_v0",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry_path


def write_dependency_blocker_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    registry_path = project / ".loopx" / "registry.json"
    current_state_file = f".codex/goals/{DEPENDENCY_CURRENT_GOAL_ID}/ACTIVE_GOAL_STATE.md"
    blocker_state_file = f".codex/goals/{DEPENDENCY_BLOCKER_GOAL_ID}/ACTIVE_GOAL_STATE.md"

    (project / Path(current_state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / current_state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Meta Hardening Fixture\n\n"
        "## Agent Todo\n\n"
        f"- [ ] {DEPENDENCY_AGENT_TODO}\n"
        f"- [ ] {DEPENDENCY_MONITOR_TODO}\n",
        encoding="utf-8",
    )
    (project / Path(blocker_state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / blocker_state_file).write_text(
        "---\n"
        "status: planned-high-complexity\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Dependency Owner Gate\n\n"
        "## User Todo / Owner Review Reading Queue\n\n"
        f"- [ ] {DEPENDENCY_USER_TODO}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": DEPENDENCY_CURRENT_GOAL_ID,
                        "domain": "meta-hardening-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": current_state_file,
                        "adapter": {
                            "kind": "fixture_connected_readonly_v0",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                    },
                    {
                        "id": DEPENDENCY_BLOCKER_GOAL_ID,
                        "domain": "dependency-gate-fixture",
                        "status": "planned-high-complexity",
                        "repo": str(project),
                        "state_file": blocker_state_file,
                        "adapter": {
                            "kind": "complex_project_read_only_map_v0",
                            "status": "planned",
                        },
                        "authority_sources": [],
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry_path


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
    registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def collect_fixture_status(root: Path, registry_path: Path) -> tuple[dict, str]:
    payload = collect_status(
        registry_path=registry_path,
        runtime_root_override=str(root / "runtime"),
        scan_roots=[root / "project"],
        limit=5,
    )
    return payload, render_status_markdown(payload)


def append_explicit_delivery_refresh(root: Path, registry_path: Path) -> dict:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(root / "runtime"),
        "--format",
        "json",
        "refresh-state",
        "--goal-id",
        DELIVERY_GOAL_ID,
        "--classification",
        EXPLICIT_REFRESH_CLASSIFICATION,
        "--recommended-action",
        DELIVERY_ACTION,
        "--delivery-batch-scale",
        "multi_surface",
        "--delivery-outcome",
        "outcome_progress",
    ]
    dry_run = subprocess.run(
        [*command, "--dry-run", "--no-global-sync"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    dry_payload = json.loads(dry_run.stdout)
    assert dry_payload["appended"] is False, dry_payload
    assert dry_payload["delivery_batch_scale"] == "multi_surface", dry_payload
    assert dry_payload["delivery_outcome"] == "outcome_progress", dry_payload

    result = subprocess.run(
        [*command, "--no-global-sync"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload["appended"] is True, payload
    assert payload["delivery_batch_scale"] == "multi_surface", payload
    assert payload["delivery_outcome"] == "outcome_progress", payload
    index_lines = (root / "runtime" / "goals" / DELIVERY_GOAL_ID / "runs" / "index.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    latest_index = json.loads(index_lines[-1])
    assert latest_index["delivery_batch_scale"] == "multi_surface", latest_index
    assert latest_index["delivery_outcome"] == "outcome_progress", latest_index
    return payload


def assert_operator_gate_waits_for_user(payload: dict, markdown: str, *, status: str, action: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == "planned-main-control", item
    assert item["status"] == status, item
    assert item["waiting_on"] == "user_or_controller", item
    assert item["recommended_action"] == action, item
    assert "agent_command" not in item, item
    assert "operator_question" in item, item
    assert "agent_command:" not in markdown, markdown
    assert "operator_gate_dry_run" not in markdown, markdown


def assert_missing_project_asset_markdown_fallback() -> None:
    markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 0,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "item_count": 1,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 1,
            "watching_external_evidence": 0,
            "items": [
                {
                    "goal_id": "legacy-status-only",
                    "status": "state_refreshed",
                    "lifecycle_phase": "refreshed",
                    "waiting_on": "codex",
                    "severity": "action",
                    "source": "latest_run",
                    "recommended_action": "raw queue action should be labeled as fallback",
                }
            ],
        },
        "run_history": {"goals": []},
    })

    assert "project_asset_source: legacy/raw fallback" in markdown, markdown
    assert "owner/gate/stop are not project_asset-backed" in markdown, markdown
    assert "project_asset: owner=" not in markdown, markdown


def assert_usage_summary_markdown() -> None:
    markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 2,
        "run_count": 4,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "usage_summary": {
            "available": True,
            "source": "run_history",
            "sample_run_count": 4,
            "totals": {
                "runs_24h": 4,
                "runs_7d": 4,
                "quota_spend_slots_24h": 2,
                "quota_spend_slots_7d": 2,
                "automation_run_count_24h": 2,
                "automation_run_count_7d": 2,
                "progress_signal_run_count_24h": 1,
                "progress_signal_run_count_7d": 1,
            },
            "goals": [
                {
                    "goal_id": "meta-loop",
                    "runs_24h": 3,
                    "runs_7d": 3,
                    "quota_spend_slots_24h": 2,
                    "automation_run_count_24h": 2,
                    "progress_signal_run_count_24h": 0,
                    "project_share_24h": 0.75,
                },
                {
                    "goal_id": "delivery-signal",
                    "runs_24h": 1,
                    "runs_7d": 1,
                    "quota_spend_slots_24h": 0,
                    "automation_run_count_24h": 0,
                    "progress_signal_run_count_24h": 1,
                    "project_share_24h": 0.25,
                },
            ],
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "items": [],
        },
        "run_history": {"goals": []},
    })

    assert "## Usage Summary" in markdown, markdown
    assert "samples=4" in markdown, markdown
    assert "quota_slots_24h=2" in markdown, markdown
    assert "progress_signals_24h=1" in markdown, markdown
    assert "`meta-loop`: runs_24h=3" in markdown, markdown
    assert "`delivery-signal`: runs_24h=1" in markdown, markdown
    assert "progress_signals_24h=0" in markdown, markdown
    assert "progress_signals_24h=1" in markdown, markdown


def assert_event_ledger_summary_markdown() -> None:
    markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 2,
        "run_count": 5,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "event_ledger_summary": {
            "available": True,
            "source": "run_history",
            "sample_run_count": 5,
            "event_classes": ["accounting", "decision", "evidence", "state", "work"],
            "totals": {
                "events_24h": 5,
                "events_7d": 5,
                "by_class_24h": {
                    "accounting": 1,
                    "decision": 1,
                    "evidence": 1,
                    "state": 1,
                    "work": 1,
                },
                "by_class_7d": {
                    "accounting": 1,
                    "decision": 1,
                    "evidence": 1,
                    "state": 1,
                    "work": 1,
                },
            },
            "goals": [
                {
                    "goal_id": "meta-loop",
                    "events_24h": 3,
                    "events_7d": 3,
                    "latest_event_class": "work",
                    "by_class_24h": {
                        "accounting": 1,
                        "decision": 0,
                        "evidence": 0,
                        "state": 1,
                        "work": 1,
                    },
                },
                {
                    "goal_id": "operator-gate",
                    "events_24h": 2,
                    "events_7d": 2,
                    "latest_event_class": "decision",
                    "by_class_24h": {
                        "accounting": 0,
                        "decision": 1,
                        "evidence": 1,
                        "state": 0,
                        "work": 0,
                    },
                },
            ],
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "items": [],
        },
        "run_history": {"goals": []},
    })

    assert "## Event Ledger Summary" in markdown, markdown
    assert "samples=5" in markdown, markdown
    assert "events_24h=5" in markdown, markdown
    assert "classes_24h=accounting=1 decision=1 evidence=1 state=1 work=1" in markdown, markdown
    assert "`meta-loop`: events_24h=3" in markdown, markdown
    assert "latest=work" in markdown, markdown
    assert "`operator-gate`: events_24h=2" in markdown, markdown
    assert "latest=decision" in markdown, markdown


def assert_promotion_readiness_summary_markdown() -> None:
    markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 2,
        "run_count": 5,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "promotion_readiness_summary": {
            "available": True,
            "source": "run_history",
            "goal_id": "loopx-meta",
            "generated_at": "2026-06-01T00:00:00+00:00",
            "classification": "canary_promotion_readiness_smoke_group",
            "delivery_outcome": "primary_goal_outcome",
            "json_exists": True,
            "markdown_exists": True,
            "freshness_status": "stale",
            "age_hours": 25.0,
            "requires_readiness_run": True,
            "freshness_window_hours": 24,
            "sample_run_count": 1,
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "items": [],
        },
        "run_history": {"goals": []},
    })

    assert "## Promotion Readiness Summary" in markdown, markdown
    assert "source=run_history" in markdown, markdown
    assert "available=True" in markdown, markdown
    assert "freshness=stale" in markdown, markdown
    assert "age_hours=25.0" in markdown, markdown
    assert "requires_readiness_run=True" in markdown, markdown
    assert "window_hours=24" in markdown, markdown
    assert "goal=loopx-meta" in markdown, markdown
    assert "classification=canary_promotion_readiness_smoke_group" in markdown, markdown
    assert "artifacts=True/True" in markdown, markdown


def assert_promotion_gate_summary_markdown() -> None:
    markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 2,
        "run_count": 5,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "promotion_gate": {
            "ok": True,
            "gate": "promotion_readiness",
            "gate_state": "ready",
            "can_promote": True,
            "should_warn": False,
            "non_blocking": True,
            "recommended_action": "promotion readiness is fresh",
            "readiness": {
                "freshness_status": "fresh",
                "requires_readiness_run": False,
                "generated_at": "2026-06-01T00:00:00+00:00",
                "age_hours": 0.25,
            },
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "items": [],
        },
        "run_history": {"goals": []},
    })

    assert "## Promotion Gate" in markdown, markdown
    assert "state=ready" in markdown, markdown
    assert "can_promote=True" in markdown, markdown
    assert "should_warn=False" in markdown, markdown
    assert "non_blocking=True" in markdown, markdown
    assert "freshness=fresh" in markdown, markdown
    assert "requires_readiness_run=False" in markdown, markdown
    assert "generated_at=2026-06-01T00:00:00+00:00" in markdown, markdown
    assert "age_hours=0.25" in markdown, markdown
    assert "action=promotion readiness is fresh" in markdown, markdown

    warning_markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 2,
        "run_count": 5,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "promotion_gate": {
            "ok": True,
            "gate": "promotion_readiness",
            "gate_state": "warning",
            "can_promote": False,
            "should_warn": True,
            "non_blocking": True,
            "recommended_action": "python3 examples/canary/canary-promotion-readiness-smoke.py",
            "warning_message": "promotion-readiness evidence is missing; generated_at=none",
            "readiness": {
                "freshness_status": "missing",
                "requires_readiness_run": True,
                "generated_at": None,
                "age_hours": None,
            },
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "items": [],
        },
        "run_history": {"goals": []},
    })

    assert "## Promotion Gate" in warning_markdown, warning_markdown
    assert "state=warning" in warning_markdown, warning_markdown
    assert "can_promote=False" in warning_markdown, warning_markdown
    assert "should_warn=True" in warning_markdown, warning_markdown
    assert "freshness=missing" in warning_markdown, warning_markdown
    assert "requires_readiness_run=True" in warning_markdown, warning_markdown
    assert "action=python3 examples/canary/canary-promotion-readiness-smoke.py" in warning_markdown, warning_markdown
    assert "warning: promotion-readiness evidence is missing; generated_at=none" in warning_markdown, warning_markdown


def assert_promotion_readiness_full_scan_fallback() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-promotion-readiness-full-scan-") as raw_tmp:
        root = Path(raw_tmp)
        runtime = root / "runtime"
        runs_dir = runtime / "goals" / "loopx-meta" / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        readiness_json = runs_dir / "2026-01-01T00-00-00-readiness.json"
        readiness_markdown = runs_dir / "2026-01-01T00-00-00-readiness.md"
        readiness_json.write_text("{}", encoding="utf-8")
        readiness_markdown.write_text("# readiness\n", encoding="utf-8")
        (runs_dir / "index.jsonl").write_text(
            json.dumps(
                {
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "goal_id": "loopx-meta",
                    "classification": "canary_promotion_readiness_smoke_group",
                    "delivery_batch_scale": "multi_surface",
                    "delivery_outcome": "primary_goal_outcome",
                    "recommended_action": "fixture readiness evidence",
                    "json_path": str(readiness_json),
                    "markdown_path": str(readiness_markdown),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        summary = build_promotion_readiness_summary(
            {"runs": [{"classification": "quota_slot_spent", "generated_at": "2026-01-02T00:00:00+00:00"}]},
            runtime_root=runtime,
        )
        assert summary["available"] is True, summary
        assert summary["source"] == "run_history_full_scan", summary
        assert summary["sample_run_count"] == 0, summary
        assert summary["classification"] == "canary_promotion_readiness_smoke_group", summary
        assert summary["delivery_outcome"] == "primary_goal_outcome", summary
        assert summary["json_exists"] is True, summary
        assert summary["markdown_exists"] is True, summary


def assert_promotion_readiness_warning_in_quota_guard() -> None:
    goal_id = "loopx-meta"

    def status_payload(readiness_summary: dict) -> dict:
        return {
            "ok": True,
            "registry": "./fixtures/registry.json",
            "runtime_root": "./fixtures/runtime",
            "goal_count": 1,
            "run_count": 1,
            "attention_queue": {
                "items": [
                    {
                        "goal_id": goal_id,
                        "status": "promotion_readiness_guard_fixture",
                        "waiting_on": "codex",
                        "severity": "action",
                        "recommended_action": "continue release-readiness guard fixture",
                        "source": "fixture",
                        "quota": {
                            "compute": 1,
                            "window_hours": 24,
                            "slot_minutes": 1,
                            "allowed_slots": 1440,
                            "spent_slots": 0,
                            "state": "eligible",
                            "reason": "fixture eligible quota",
                        },
                    }
                ],
            },
            "run_history": {
                "goals": [
                    {
                        "id": goal_id,
                        "status": "promotion_readiness_guard_fixture",
                        "registry_member": True,
                        "latest_runs": [],
                    }
                ]
            },
            "promotion_readiness_summary": readiness_summary,
        }

    stale_payload = build_quota_should_run(
        status_payload(
            {
                "available": True,
                "source": "run_history",
                "goal_id": goal_id,
                "generated_at": "2026-06-01T00:00:00+00:00",
                "classification": "canary_promotion_readiness_smoke_group",
                "freshness_status": "stale",
                "requires_readiness_run": True,
                "freshness_window_hours": 24,
                "age_hours": 25.0,
                "sample_run_count": 1,
                "json_exists": True,
                "markdown_exists": True,
            }
        ),
        goal_id=goal_id,
    )
    assert stale_payload["should_run"] is True, stale_payload
    stale_warning = stale_payload["promotion_readiness_warning"]
    assert stale_warning["freshness_status"] == "stale", stale_warning
    assert stale_warning["requires_readiness_run"] is True, stale_warning
    assert stale_warning["age_hours"] == 25.0, stale_warning
    stale_markdown = render_quota_should_run_markdown(stale_payload)
    assert "promotion_readiness_warning: status=stale requires_readiness_run=True" in stale_markdown, stale_markdown
    assert "promotion_readiness_action: promotion readiness evidence is missing, stale, or unknown" in stale_markdown, stale_markdown
    assert "promotion_readiness_evidence: goal=loopx-meta" in stale_markdown, stale_markdown
    assert "age_hours=25.0" in stale_markdown, stale_markdown
    assert "artifacts=True/True" in stale_markdown, stale_markdown

    missing_payload = build_quota_should_run(
        status_payload(
            {
                "available": False,
                "source": "run_history",
                "reason": "no canary promotion readiness run found in sampled history",
                "freshness_status": "missing",
                "requires_readiness_run": True,
                "freshness_window_hours": 24,
                "age_hours": None,
                "sample_run_count": 0,
            }
        ),
        goal_id=goal_id,
    )
    assert missing_payload["should_run"] is True, missing_payload
    missing_warning = missing_payload["promotion_readiness_warning"]
    assert missing_warning["freshness_status"] == "missing", missing_warning
    assert missing_warning["available"] is False, missing_warning
    missing_markdown = render_quota_should_run_markdown(missing_payload)
    assert "promotion_readiness_warning: status=missing requires_readiness_run=True" in missing_markdown, missing_markdown
    assert "promotion_readiness_reason: no canary promotion readiness run found in sampled history" in missing_markdown, missing_markdown

    fresh_payload = build_quota_should_run(
        status_payload(
            {
                "available": True,
                "source": "run_history",
                "goal_id": goal_id,
                "generated_at": "2026-06-01T00:00:00+00:00",
                "classification": "canary_promotion_readiness_smoke_group",
                "freshness_status": "fresh",
                "requires_readiness_run": False,
                "freshness_window_hours": 24,
                "age_hours": 1.0,
                "sample_run_count": 1,
                "json_exists": True,
                "markdown_exists": True,
            }
        ),
        goal_id=goal_id,
    )
    assert fresh_payload["should_run"] is True, fresh_payload
    assert "promotion_readiness_warning" not in fresh_payload, fresh_payload


def assert_decision_freshness_summary_markdown() -> None:
    markdown = render_status_markdown({
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 2,
        "run_count": 5,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "decision_freshness_summary": {
            "available": True,
            "source": "run_history",
            "sample_run_count": 5,
            "window_days": 7,
            "summary": {
                "decision_count": 2,
                "stale_count": 1,
                "rebase_required_count": 2,
                "fresh_count": 0,
            },
            "items": [
                {
                    "goal_id": "meta-loop",
                    "decision_kind": "human_reward",
                    "decision_at": "2026-05-20T12:00:00+00:00",
                    "age_days": 8.25,
                    "newer_event_count_7d": 3,
                    "freshness_state": "stale_rebase_required",
                },
                {
                    "goal_id": "operator-gate",
                    "decision_kind": "operator_gate",
                    "decision_at": "2026-05-27T12:00:00+00:00",
                    "age_days": 0.25,
                    "newer_event_count_7d": 1,
                    "freshness_state": "rebase_required",
                },
            ],
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "items": [],
        },
        "run_history": {"goals": []},
    })

    assert "## Decision Freshness Summary" in markdown, markdown
    assert "window_days=7" in markdown, markdown
    assert "decisions=2" in markdown, markdown
    assert "stale=1" in markdown, markdown
    assert "rebase_required=2" in markdown, markdown
    assert "`meta-loop`: kind=human_reward state=stale_rebase_required" in markdown, markdown
    assert "`operator-gate`: kind=operator_gate state=rebase_required" in markdown, markdown


def assert_status_agent_lane_next_action_projection() -> None:
    goal_id = "agent-lane-status-fixture"
    primary_action = "[P0] Continue the primary controller benchmark route."
    side_action = (
        "[P0] Codex CLI TUI continuation: prove the visible steering turn "
        "without losing user takeover."
    )
    side_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_side_tui",
        "index": 2,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "action_kind": "codex_cli_tui_continuation",
        "claimed_by": "codex-side-bypass",
        "required_capabilities": ["shell", "filesystem_write"],
        "text": side_action,
    }
    primary_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_primary_route",
        "index": 1,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "claimed_by": "codex-main-control",
        "text": primary_action,
    }
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "open_count": 2,
        "done_count": 0,
        "total_count": 2,
        "first_open_items": [
            primary_todo,
            side_todo,
        ],
        "items": [primary_todo, side_todo],
        "first_executable_items": [side_todo],
    }
    coordination = {
        "primary_agent": "codex-main-control",
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
        "agent_profiles": {
            "codex-side-bypass": {
                "schema_version": "agent_profile_v0",
                "agent_id": "codex-side-bypass",
                "role": "side-agent",
                "scope_summary": "productization showcase docs lane",
                "worktree_policy": {
                    "mode": "independent_worktree_required",
                    "requires_independent_worktree": True,
                },
                "review_policy": {
                    "handoff_agent": "codex-main-control",
                    "can_self_merge": "small_validated_docs_or_metadata_only",
                },
            }
        },
    }
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "available": True,
            "item_count": 1,
            "items": [
                {
                    "goal_id": goal_id,
                    "status": "primary_route_active",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": primary_action,
                    "source": "registry",
                    "coordination": coordination,
                    "quota": {
                        "state": "eligible",
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "owner": "codex-main-control",
                        "gate": "none",
                        "stop_condition": "stop on unsafe workspace or user gate",
                        "next_action": primary_action,
                        "agent_todos": project_asset_todo_summary(agent_todos, role="agent"),
                    },
                }
            ],
        },
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "registry_member": True,
                    "status": "primary_route_active",
                    "coordination": coordination,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    attach_agent_lane_next_actions(payload, agent_id="codex-side-bypass")
    item = payload["attention_queue"]["items"][0]
    next_action = item["agent_lane_next_action"]
    assert next_action["schema_version"] == "agent_lane_next_action_v0", next_action
    assert next_action["todo_id"] == "todo_side_tui", next_action
    assert next_action["agent_id"] == "codex-side-bypass", next_action
    assert next_action["preserves_goal_next_action"] is True, next_action
    goal_frontier = item["goal_frontier_projection"]
    assert goal_frontier["deferred_successors"]["ready_count"] == 0, goal_frontier
    assert goal_frontier["acceptance_gaps"] == [], goal_frontier
    assert item["recommended_action"] == primary_action, item
    assert item["project_asset"]["next_action"] == primary_action, item
    member = item["agent_member"]
    assert member["schema_version"] == "agent_member_v0", member
    assert member["agent_id"] == "codex-side-bypass", member
    assert member["role"] == "side-agent", member
    assert member["scope_summary"] == "productization showcase docs lane", member
    assert member["worktree_policy"] == "independent_worktree_required", member
    assert member["requires_independent_worktree"] is True, member
    assert member["current_claims"] == ["todo_side_tui"], member
    assert member["lease_projection"]["source"] == "todo.claimed_by", member
    assert member["lease_projection"]["hard_lease_available"] is False, member
    assert member["handoff_agent"] == "codex-main-control", member
    assert member["role_is_advisory"] is True, member
    assert item["project_asset"]["agent_member"] == member, item
    projection = payload["agent_member_projection"]
    assert projection["schema_version"] == "agent_member_projection_v0", projection
    assert projection["attached_count"] == 1, projection
    assert projection["projection_is_authoritative"] is False, projection
    markdown = render_status_markdown(payload)
    assert "agent_member: agent=codex-side-bypass role=side-agent" in markdown, markdown
    assert "worktree_policy=independent_worktree_required" in markdown, markdown
    assert "claims=todo_side_tui" in markdown, markdown
    assert "current_agent_todo: agent=codex-side-bypass todo_id=todo_side_tui" in markdown, markdown
    assert "source=agent_lane_next_action" in markdown, markdown
    assert "goal_frontier_projection: replan_required=False" in markdown, markdown
    assert "deferred_ready=0 acceptance_gaps=0" in markdown, markdown
    assert side_action in markdown, markdown
    assert f"next_agent_todo: {primary_action} claimed_by=codex-main-control scope=goal_all_agents" in markdown, markdown
    assert f"asset_agent_todo: {primary_action} claimed_by=codex-main-control scope=goal_all_agents" in markdown, markdown
    packet = build_review_packet(payload, goal_id=goal_id, action_kind="codex")
    assert packet["agent_member"]["agent_id"] == "codex-side-bypass", packet
    assert "Agent 成员：agent=codex-side-bypass role=side-agent" in packet["project_agent_handoff"], packet
    assert "authority=advisory_projection" in packet["project_agent_handoff"], packet


def assert_status_agent_member_selected_lane_claim_survives_truncated_claim_list() -> None:
    goal_id = "agent-lane-truncated-claims-fixture"
    selected_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_selected_lane",
        "index": 116,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "action_kind": "rapid_self_merge_kernel_iteration",
        "claimed_by": "codex-side-bypass",
        "text": "[P0] Continue the selected side-agent lane.",
    }
    visible_stale_claims = [
        {
            "schema_version": "todo_item_v0",
            "todo_id": f"todo_visible_stale_claim_{offset}",
            "index": 56 + offset,
            "role": "agent",
            "status": "blocked",
            "priority": "P0",
            "task_class": "advancement_task",
            "action_kind": "old_side_lane",
            "claimed_by": "codex-side-bypass",
            "text": "[P0] Old side-agent claim kept in the visible status window.",
        }
        for offset in range(10)
    ]
    primary_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_primary_visible",
        "index": 22,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "blocker",
        "claimed_by": "codex-main-control",
        "text": "[P0] Primary visible item.",
    }
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "open_count": 105,
        "done_count": 0,
        "total_count": 105,
        "items": [primary_todo, *visible_stale_claims, selected_todo],
        "first_open_items": [primary_todo, *visible_stale_claims[:2]],
        "first_executable_items": [selected_todo],
    }
    coordination = {
        "primary_agent": "codex-main-control",
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
    }
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "available": True,
            "item_count": 1,
            "items": [
                {
                    "goal_id": goal_id,
                    "status": "primary_route_active",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": primary_todo["text"],
                    "source": "registry",
                    "coordination": coordination,
                    "quota": {
                        "state": "eligible",
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "owner": "codex-main-control",
                        "gate": "none",
                        "stop_condition": "stop on unsafe workspace or user gate",
                        "next_action": primary_todo["text"],
                        "agent_todos": project_asset_todo_summary(agent_todos, role="agent"),
                    },
                }
            ],
        },
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "registry_member": True,
                    "status": "primary_route_active",
                    "coordination": coordination,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    attach_agent_lane_next_actions(payload, agent_id="codex-side-bypass")
    item = payload["attention_queue"]["items"][0]
    assert item["agent_lane_next_action"]["todo_id"] == "todo_selected_lane", item
    member = item["agent_member"]
    assert member["current_claims"][0] == "todo_selected_lane", member
    assert "todo_visible_stale_claim_0" in member["current_claims"], member
    markdown = render_status_markdown(payload)
    assert "claims=todo_selected_lane,todo_visible_stale_claim_0" in markdown, markdown


def assert_status_agent_member_handoff_uses_quota_identity() -> None:
    assert (
        _review_handoff_agent(
            coordination={},
            profile={},
            identity={"handoff_agent": "codex-product-capability"},
            role="side-agent",
        )
        == "codex-product-capability"
    )
    assert (
        _review_handoff_agent(
            coordination={"side_agent_handoff_agent": "codex-main-control"},
            profile={},
            identity={"handoff_agent": "codex-product-capability"},
            role="side-agent",
        )
        == "codex-product-capability"
    )


def assert_status_contract_health_projection() -> None:
    projection = build_contract_health_projection(
        {
            "summary": {"errors": 0, "warnings": 4, "checks": 8},
            "errors": [],
            "warnings": [
                "fixture-goal: duplicate index rows raw=2 unique=1 unexpected=1",
                "fixture-goal: stale projection warning A",
                "fixture-goal: stale projection warning B",
                "fixture-goal: stale projection warning C",
            ],
        }
    )
    assert projection["contract_summary"] == {"errors": 0, "warnings": 4, "checks": 8}, projection
    assert projection["contract_warnings_total_count"] == 4, projection
    assert projection["contract_warnings_truncated"] is True, projection
    assert len(projection["contract_warnings"]) == 3, projection
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "status_contract": {
            "schema_version": 2,
            "minimum_dashboard_schema_version": 2,
            "producer": "loopx status",
        },
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 4, "checks": 8}},
        **projection,
        "global_registry": {"available": False, "summary": {}},
    }
    markdown = render_status_markdown(payload)
    assert "Status Contract Signals" in markdown, markdown
    assert "duplicate index rows raw=2 unique=1 unexpected=1" in markdown, markdown
    assert "contract_warnings_truncated: total=4" in markdown, markdown


def assert_status_agent_lane_frontier_hint_projection() -> None:
    goal_id = "agent-lane-frontier-status-fixture"
    primary_action = "[P0] Continue the primary controller benchmark route."
    primary_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_primary_route",
        "index": 1,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "claimed_by": "codex-main-control",
        "text": primary_action,
    }
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "open_count": 1,
        "done_count": 0,
        "total_count": 1,
        "first_open_items": [primary_todo],
        "items": [primary_todo],
    }
    coordination = {
        "primary_agent": "codex-main-control",
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
    }
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "available": True,
            "item_count": 1,
            "items": [
                {
                    "goal_id": goal_id,
                    "status": "primary_route_active",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": primary_action,
                    "source": "registry",
                    "coordination": coordination,
                    "quota": {
                        "state": "eligible",
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "owner": "codex-main-control",
                        "gate": "none",
                        "stop_condition": "stop on unsafe workspace or user gate",
                        "next_action": primary_action,
                        "agent_todos": project_asset_todo_summary(agent_todos, role="agent"),
                    },
                }
            ],
        },
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "registry_member": True,
                    "status": "primary_route_active",
                    "coordination": coordination,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    attach_agent_lane_next_actions(payload, agent_id="codex-side-bypass")
    item = payload["attention_queue"]["items"][0]
    assert "agent_lane_next_action" not in item, item
    frontier = item["agent_scope_frontier"]
    assert frontier["action"] == "agent_scope_wait", frontier
    goal_frontier = item["goal_frontier_projection"]
    assert goal_frontier["remaining_advancement_frontier"] == {
        "current_agent_claimed_advancement_count": 0,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 1,
    }, goal_frontier
    assert goal_frontier["deferred_successors"]["ready_count"] == 0, goal_frontier
    assert goal_frontier["acceptance_gaps"] == [], goal_frontier
    hint = item["agent_lane_frontier_hint"]
    assert hint["schema_version"] == "agent_lane_frontier_hint_v0", hint
    assert hint["decision"] == "quiet_noop_blocker", hint
    assert hint["source"] == "agent_scope_frontier", hint
    assert hint["target_todo_id"] == "todo_primary_route", hint
    projection = payload["agent_lane_next_action_projection"]
    assert projection["attached_count"] == 0, projection
    assert projection["frontier_attached_count"] == 1, projection
    assert projection["frontier_hint_attached_count"] == 1, projection
    markdown = render_status_markdown(payload)
    assert "agent_lane_frontier_hint: agent=codex-side-bypass" in markdown, markdown
    assert "decision=quiet_noop_blocker" in markdown, markdown
    assert "target_todo_id=todo_primary_route" in markdown, markdown
    assert "goal_frontier_projection: replan_required=False" in markdown, markdown
    assert "other_agent_advancement=1 deferred_ready=0 acceptance_gaps=0" in markdown, markdown


def assert_quota_should_run(
    payload: dict,
    *,
    expected: bool,
    state: str,
    waiting_on: str,
    expect_operator_question: bool = True,
) -> dict:
    quota_payload = build_quota_should_run(payload, goal_id="planned-main-control")
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    assert quota_payload["should_run"] is expected, quota_payload
    assert quota_payload["state"] == state, quota_payload
    assert quota_payload["waiting_on"] == waiting_on, quota_payload
    if expected:
        assert quota_payload["decision"] == "run", quota_payload
        assert quota_payload["agent_command"] == APPROVED_COMMAND, quota_payload
        assert f"agent_command: `{APPROVED_COMMAND}`" in quota_markdown, quota_markdown
    else:
        assert quota_payload["decision"] == "skip", quota_payload
        if state == "operator_gate":
            assert quota_payload["reason"] == "operator gate blocks gated delivery; safe non-gated steering may continue", quota_payload
            assert quota_payload["safe_bypass_allowed"] is True, quota_payload
            assert quota_payload["blocked_action_scope"] == "gated_delivery", quota_payload
            if expect_operator_question:
                assert quota_payload["operator_question"], quota_payload
                assert "建议回复格式" in quota_markdown, quota_markdown
            else:
                assert "operator_question" not in quota_payload, quota_payload
            assert quota_payload["gate_prompt"], quota_payload
            assert quota_payload["notify_user_on_gate"] is True, quota_payload
            assert "Gate Prompt" in quota_markdown, quota_markdown
            assert "safe_bypass_allowed: `True`" in quota_markdown, quota_markdown
        assert "agent_command" not in quota_payload, quota_payload
        assert "agent_command:" not in quota_markdown, quota_markdown
    return quota_payload


def assert_planned_preview_is_not_runnable(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == "planned-main-control", item
    assert item["waiting_on"] == "controller", item
    assert item["recommended_action"] == USER_TODO_TEXT, item
    assert item["project_asset"]["owner"] == "controller", item
    assert item["project_asset"]["gate"] == "active_state_user_todo", item
    assert item["project_asset"]["next_action"] == USER_TODO_TEXT, item
    assert "stop until the controller or owner resolves this gate" in item["project_asset"]["stop_condition"], item
    assert item["project_asset"]["user_todos"]["open"] == 1, item
    assert item["project_asset"]["agent_todos"]["open"] == 1, item
    assert item["project_asset"]["quota"]["compute"] == 1.0, item
    assert item["project_asset"]["quota"]["state"] == "operator_gate", item
    assert "agent_command" not in item, item
    assert "operator_gate_dry_run" not in item, item
    assert OLD_PLANNED_ACTION not in json.dumps(payload, ensure_ascii=False), payload
    assert OLD_PLANNED_ACTION not in markdown, markdown
    assert USER_TODO_TEXT in markdown, markdown
    assert "project_asset: owner=controller gate=active_state_user_todo" in markdown, markdown
    assert f"asset_next_action: {USER_TODO_TEXT}" in markdown, markdown
    assert "asset_todos: user_open=1 agent_open=1" in markdown, markdown
    assert f"asset_user_todo: {USER_TODO_TEXT}" in markdown, markdown
    assert f"asset_agent_todo: {AGENT_TODO_TEXT}" in markdown, markdown
    assert "asset_quota: compute=1.0 state=operator_gate" in markdown, markdown

    assert "operator_gate_dry_run" not in markdown, markdown

    quota_payload = assert_quota_should_run(
        payload,
        expected=False,
        state="operator_gate",
        waiting_on="controller",
        expect_operator_question=False,
    )
    assert quota_payload["status"] == "active_state_user_todo", quota_payload


def assert_project_local_status_excludes_runtime_orphans(registry_path: Path) -> None:
    root = registry_path.parents[2]
    orphan_goal_id = "unregistered-orphan-goal"
    append_orphan_runtime_fixture(root, goal_id=orphan_goal_id, generated_at="2026-01-01T00:05:00+00:00")
    payload, markdown = collect_fixture_status(root, registry_path)
    goal_ids = {item["id"] for item in payload["run_history"]["goals"]}
    queue_goal_ids = {item["goal_id"] for item in payload["attention_queue"]["items"]}
    assert goal_ids == {"planned-main-control"}, payload
    assert queue_goal_ids == {"planned-main-control"}, payload
    assert orphan_goal_id not in markdown, markdown
    quota_payload = build_quota_should_run(payload, goal_id="planned-main-control")
    assert quota_payload["plan_summary"]["health_blockers"] == 0, quota_payload


def assert_registry_attention_override(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == "planned-main-control", item
    assert item["status"] == REGISTRY_OVERRIDE_STATUS, item
    assert item["waiting_on"] == "user_or_controller", item
    assert item["source"] == "registry", item
    assert item["recommended_action"] == REGISTRY_OVERRIDE_ACTION, item
    assert item["project_asset"]["owner"] == "user_or_controller", item
    assert item["project_asset"]["gate"] == "operator_question", item
    assert item["project_asset"]["next_action"] == REGISTRY_OVERRIDE_ACTION, item
    assert item["project_asset"]["stop_condition"] == REGISTRY_OVERRIDE_HANDOFF, item
    assert item["project_asset"]["user_todos"]["open"] == 0, item
    assert item["project_asset"]["agent_todos"]["open"] == 0, item
    assert item["project_asset"]["quota"]["state"] == "operator_gate", item
    assert item["project_asset"]["latest_validation"]["classification"] == "state_refreshed", item
    assert item["operator_question"] == REGISTRY_OVERRIDE_QUESTION, item
    assert item["next_handoff_condition"] == REGISTRY_OVERRIDE_HANDOFF, item
    assert item["user_todos"]["open_count"] == 0, item
    assert item["user_todos"]["done_count"] == 2, item
    assert item["agent_todos"]["open_count"] == 0, item
    assert item["agent_todos"]["done_count"] == 1, item
    assert "agent_command" not in item, item
    assert REGISTRY_OVERRIDE_STATUS in markdown, markdown
    assert REGISTRY_OVERRIDE_ACTION in markdown, markdown
    assert "project_asset: owner=user_or_controller gate=operator_question" in markdown, markdown
    assert f"asset_next_action: {REGISTRY_OVERRIDE_ACTION}" in markdown, markdown
    assert "asset_todos: user_open=0 agent_open=0" in markdown, markdown
    assert f"asset_user_todo: {USER_TODO_TEXT}" not in markdown, markdown
    assert f"asset_agent_todo: {AGENT_TODO_TEXT}" not in markdown, markdown
    assert "latest_validation: classification=state_refreshed" in markdown, markdown
    assert f"next_user_todo: {USER_TODO_TEXT}" not in markdown, markdown
    assert f"next_agent_todo: {AGENT_TODO_TEXT}" not in markdown, markdown
    assert "state_refreshed" in json.dumps(payload["run_history"], ensure_ascii=False), payload
    assert_quota_should_run(
        payload,
        expected=False,
        state="operator_gate",
        waiting_on="user_or_controller",
    )


def assert_connected_delivery_custom_run_stays_runnable(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == DELIVERY_GOAL_ID, item
    assert item["status"] == "delivery_ranker_readiness_batch", item
    assert item["waiting_on"] == "codex", item
    assert item["source"] == "latest_run", item
    assert item["recommended_action"] == DELIVERY_ACTION, item
    assert item["project_asset"]["owner"] == "codex", item
    assert item["project_asset"]["next_action"] == DELIVERY_ACTION, item
    assert item["project_asset"]["execution_profile"]["minimum_scale"] == "implementation", item
    assert item["project_asset"]["execution_profile"]["degradation_policy"]["small_scale_streak_threshold"] == 3, item
    assert item["project_asset"]["orchestration"]["mode"] == "multi_subagent", item
    assert item["project_asset"]["orchestration"]["max_children"] == 2, item
    assert item["project_asset"]["agent_todos"]["open"] == 1, item
    assert item["agent_todos"]["open_count"] == 1, item
    assert item["agent_todos"]["items"][0]["text"] == DELIVERY_AGENT_TODO, item
    readiness = item["handoff_readiness"]
    assert readiness["handoff_status"] == "post_handoff_run_seen", readiness
    assert readiness["post_handoff_run_seen"] is True, readiness
    assert "handoff_ready_at" not in readiness, readiness
    assert readiness["post_handoff_latest_run"]["classification"] == "delivery_ranker_readiness_batch", readiness
    assert readiness["post_handoff_latest_run"]["delivery_batch_scale"] == "multi_surface", readiness
    assert readiness["post_handoff_latest_run"]["delivery_outcome"] == "outcome_progress", readiness
    assert readiness["post_handoff_recent_runs"][0]["delivery_batch_scale"] == "multi_surface", readiness
    assert readiness["post_handoff_recent_runs"][0]["delivery_outcome"] == "outcome_progress", readiness
    assert readiness["post_handoff_small_scale_streak"] == 0, readiness
    assert readiness["post_handoff_outcome_gap_streak"] == 0, readiness
    assert_handoff_budget_contract(readiness, "connected delivery status readiness")
    assert "delivery_ranker_readiness_batch" in markdown, markdown
    assert "handoff_interface_budget: mode=project_agent_handoff max_lines=16 max_chars=1800" in markdown, markdown
    assert "handoff_state: status=post_handoff_run_seen post_handoff_run_seen=True ready_at=" in markdown, markdown
    assert "post_handoff_run: classification=delivery_ranker_readiness_batch" in markdown, markdown
    assert "scale=multi_surface" in markdown, markdown
    assert "outcome=outcome_progress" in markdown, markdown
    assert (
        "post_handoff_recent_scales: multi_surface small_streak=0 "
        "outcome=outcome_progress turn_kind=compact_evidence outcome_gap_streak=0"
    ) in markdown, markdown
    assert "execution_profile: cadence=bounded_progress_segment minimum=implementation" in markdown, markdown
    assert "orchestration: mode=multi_subagent spawn_allowed=True max_children=2" in markdown, markdown
    assert f"asset_agent_todo: {DELIVERY_AGENT_TODO}" in markdown, markdown

    quota_payload = build_quota_should_run(payload, goal_id=DELIVERY_GOAL_ID)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["state"] == "eligible", quota_payload
    assert quota_payload["waiting_on"] == "codex", quota_payload
    assert quota_payload["agent_todo_summary"]["open_count"] == 1, quota_payload
    assert quota_payload["goal_boundary"]["adapter"]["status"] == "connected-delivery", quota_payload
    assert quota_payload["goal_boundary"]["write_scope"] == ["src/**", "tests/**"], quota_payload
    assert quota_payload["execution_profile"]["minimum_scale"] == "implementation", quota_payload
    assert quota_payload["goal_boundary"]["execution_profile"]["minimum_scale"] == "implementation", quota_payload
    assert quota_payload["goal_boundary"]["orchestration"]["mode"] == "multi_subagent", quota_payload
    assert quota_payload["goal_boundary"]["orchestration"]["max_children"] == 2, quota_payload
    assert (
        quota_payload["handoff_readiness"]["post_handoff_latest_run"]["delivery_batch_scale"]
        == "multi_surface"
    ), quota_payload
    assert (
        quota_payload["handoff_readiness"]["post_handoff_latest_run"]["delivery_outcome"]
        == "outcome_progress"
    ), quota_payload
    assert (
        quota_payload["handoff_readiness"]["post_handoff_recent_runs"][0]["delivery_batch_scale"]
        == "multi_surface"
    ), quota_payload
    assert quota_payload["handoff_readiness"]["post_handoff_small_scale_streak"] == 0, quota_payload
    assert quota_payload["handoff_readiness"]["post_handoff_outcome_gap_streak"] == 0, quota_payload
    assert_handoff_budget_contract(quota_payload["handoff_readiness"], "connected delivery quota readiness")
    assert quota_payload["heartbeat_recommendation"]["recommended_mode"] == "steering_audit_then_one_step", quota_payload
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    assert "- handoff_interface_budget: mode=project_agent_handoff max_lines=16 max_chars=1800" in quota_markdown, quota_markdown
    assert "execution_profile: cadence=bounded_progress_segment minimum=implementation" in quota_markdown, quota_markdown
    assert "goal_boundary_orchestration: mode=multi_subagent spawn_allowed=True max_children=2" in quota_markdown, quota_markdown


def assert_source_registry_shadow_collapses_into_live_queue_item(payload: dict) -> None:
    registry_summary = payload["global_registry"]["summary"]
    assert registry_summary["action"] == 1, payload["global_registry"]
    assert "source_registry_missing" in json.dumps(payload["global_registry"], ensure_ascii=False), payload

    items = payload["attention_queue"]["items"]
    goal_items = [item for item in items if item["goal_id"] == DELIVERY_GOAL_ID]
    assert len(goal_items) == 1, items
    item = goal_items[0]
    assert item["status"] == "delivery_ranker_readiness_batch", item
    assert item["source"] == "latest_run", item
    assert not any(queue_item["status"] == "source_registry_missing" for queue_item in items), items
    shadows = item["global_registry_shadow_findings"]
    assert shadows[0]["kind"] == "source_registry_missing", shadows
    assert item["project_asset"]["global_registry_shadow_findings"]["open"] == 1, item

    quota_payload = build_quota_should_run(payload, goal_id=DELIVERY_GOAL_ID)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["state"] == "eligible", quota_payload
    assert quota_payload["plan_summary"]["health_blockers"] == 0, quota_payload


def assert_connected_readonly_progress_run_stays_runnable(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == CONNECTED_READONLY_GOAL_ID, item
    assert item["status"] == CONNECTED_READONLY_CLASSIFICATION, item
    assert item["waiting_on"] == "codex", item
    assert item["source"] == "latest_run", item
    assert item["recommended_action"] == CONNECTED_READONLY_ACTION, item
    assert item["project_asset"]["owner"] == "codex", item
    assert item["project_asset"]["next_action"] == CONNECTED_READONLY_ACTION, item
    assert CONNECTED_READONLY_CLASSIFICATION in markdown, markdown
    assert "waiting_on=codex" in markdown, markdown

    quota_payload = build_quota_should_run(payload, goal_id=CONNECTED_READONLY_GOAL_ID)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["state"] == "eligible", quota_payload
    assert quota_payload["waiting_on"] == "codex", quota_payload
    assert quota_payload["status"] == CONNECTED_READONLY_CLASSIFICATION, quota_payload
    assert quota_payload["recommended_action"] == CONNECTED_READONLY_ACTION, quota_payload
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    assert "should_run: `True`" in quota_markdown, quota_markdown
    assert f"status: `{CONNECTED_READONLY_CLASSIFICATION}`" in quota_markdown, quota_markdown


def assert_dependency_blockers_stay_separate(payload: dict, markdown: str) -> None:
    items_by_goal = {
        item["goal_id"]: item
        for item in payload["attention_queue"]["items"]
    }
    current_item = items_by_goal[DEPENDENCY_CURRENT_GOAL_ID]
    blocker_item = items_by_goal[DEPENDENCY_BLOCKER_GOAL_ID]
    assert current_item["waiting_on"] == "codex", current_item
    assert current_item["agent_todos"]["open_count"] == 2, current_item
    assert "user_todos" not in current_item, current_item
    blockers = current_item["dependency_blockers"]
    assert blockers["open_count"] == 1, blockers
    assert blockers["source"] == "attention_queue.user_todos", blockers
    assert blockers["items"][0]["goal_id"] == DEPENDENCY_BLOCKER_GOAL_ID, blockers
    assert blockers["items"][0]["text"] == DEPENDENCY_USER_TODO, blockers
    assert blocker_item["user_todos"]["open_count"] == 1, blocker_item
    assert "dependency_blockers" not in blocker_item, blocker_item
    assert "dependency_blockers: open=1 source=attention_queue.user_todos" in markdown, markdown
    assert f"dependency_user_todo: goal={DEPENDENCY_BLOCKER_GOAL_ID}" in markdown, markdown
    backlog = payload["attention_queue"]["autonomous_backlog_candidates"]
    assert backlog["open_count"] == 1, backlog
    assert backlog["source"] == "attention_queue.agent_todos", backlog
    assert backlog["task_class"] == "advancement_task", backlog
    assert backlog["items"][0]["goal_id"] == DEPENDENCY_CURRENT_GOAL_ID, backlog
    assert backlog["items"][0]["text"] == DEPENDENCY_AGENT_TODO, backlog
    assert DEPENDENCY_MONITOR_TODO not in [item["text"] for item in backlog["items"]], backlog
    assert (
        "autonomous_backlog_candidates: open=1 task_class=advancement_task source=attention_queue.agent_todos"
        in markdown
    ), markdown
    assert f"autonomous_candidate: goal={DEPENDENCY_CURRENT_GOAL_ID}" in markdown, markdown
    monitors = payload["attention_queue"]["autonomous_monitor_candidates"]
    assert monitors["open_count"] == 1, monitors
    assert monitors["task_class"] == "continuous_monitor", monitors
    assert monitors["items"][0]["goal_id"] == DEPENDENCY_CURRENT_GOAL_ID, monitors
    assert monitors["items"][0]["text"] == DEPENDENCY_MONITOR_TODO, monitors
    assert (
        "autonomous_monitor_candidates: open=1 task_class=continuous_monitor source=attention_queue.agent_todos"
        in markdown
    ), markdown
    assert f"autonomous_monitor_candidate: goal={DEPENDENCY_CURRENT_GOAL_ID}" in markdown, markdown
    quota_payload = build_quota_should_run(payload, goal_id=DEPENDENCY_CURRENT_GOAL_ID)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["state"] == "eligible", quota_payload
    assert quota_payload["waiting_on"] == "codex", quota_payload
    assert quota_payload["autonomous_backlog_candidates"]["items"][0]["text"] == DEPENDENCY_AGENT_TODO
    assert quota_payload["autonomous_monitor_candidates"]["items"][0]["text"] == DEPENDENCY_MONITOR_TODO


def assert_connected_delivery_no_baseline_small_streak(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == DELIVERY_GOAL_ID, item
    assert item["project_asset"]["execution_profile"]["minimum_scale"] == "implementation", item
    assert item["project_asset"]["execution_profile"]["degradation_policy"]["small_scale_streak_threshold"] == 3, item
    readiness = item["handoff_readiness"]
    assert readiness["handoff_status"] == "post_handoff_run_seen", readiness
    assert readiness["post_handoff_run_seen"] is True, readiness
    assert "handoff_ready_at" not in readiness, readiness
    assert [run["delivery_batch_scale"] for run in readiness["post_handoff_recent_runs"]] == [
        "test_only",
        "test_only",
    ], readiness
    assert readiness["post_handoff_small_scale_streak"] == 2, readiness
    assert "post_handoff_recent_scales: test_only,test_only small_streak=2" in markdown, markdown

    quota_payload = build_quota_should_run(payload, goal_id=DELIVERY_GOAL_ID)
    quota_readiness = quota_payload["handoff_readiness"]
    assert [run["delivery_batch_scale"] for run in quota_readiness["post_handoff_recent_runs"]] == [
        "test_only",
        "test_only",
    ], quota_payload
    assert quota_readiness["post_handoff_small_scale_streak"] == 2, quota_payload
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    assert "post_handoff_recent_scales: test_only,test_only small_streak=2" in quota_markdown, quota_markdown
    assert "execution_profile: cadence=bounded_progress_segment minimum=implementation" in quota_markdown, quota_markdown


def assert_connected_delivery_surface_loop(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["quota"]["state"] == "focus_wait", item
    assert item["quota"]["blocked_action_scope"] == "delivery_outcome_floor", item
    assert item["quota"]["safe_bypass_allowed"] is True, item
    assert item["quota"]["safe_bypass_kind"] == "outcome_floor_recovery", item
    assert item["project_asset"]["quota"]["state"] == "focus_wait", item
    readiness = item["handoff_readiness"]
    assert readiness["ready"] is False, readiness
    assert readiness["codex_ready"] is False, readiness
    assert readiness["quota_state"] == "focus_wait", readiness
    assert [run["delivery_batch_scale"] for run in readiness["post_handoff_recent_runs"]] == [
        "implementation",
        "implementation",
        "implementation",
    ], readiness
    assert [run["delivery_outcome"] for run in readiness["post_handoff_recent_runs"]] == [
        "surface_only",
        "surface_only",
        "surface_only",
    ], readiness
    assert readiness["post_handoff_small_scale_streak"] == 0, readiness
    assert readiness["post_handoff_outcome_gap_streak"] == 3, readiness
    assert readiness["handoff_status"] == "post_handoff_run_seen", readiness
    assert "scale=implementation outcome=surface_only" in markdown, markdown
    assert "quota_state=focus_wait" in markdown, markdown
    assert "handoff_checks: pass=project_asset_backed,same_source_should_run,handoff_has_next_action,handoff_has_stop_condition,handoff_sanitized_surface fail=codex_ready" in markdown, markdown
    assert (
        "post_handoff_recent_scales: implementation,implementation,implementation "
        "small_streak=0 outcome=surface_only,surface_only,surface_only "
        "turn_kind=contract_only_preparation,contract_only_preparation,contract_only_preparation "
        "outcome_gap_streak=3"
    ) in markdown, markdown

    quota_payload = build_quota_should_run(payload, goal_id=DELIVERY_GOAL_ID)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["decision"] == "safe_bypass_recovery", quota_payload
    assert quota_payload["recovery_delivery_allowed"] is True, quota_payload
    assert quota_payload["normal_delivery_allowed"] is False, quota_payload
    assert quota_payload["state"] == "focus_wait", quota_payload
    assert quota_payload["quota"]["blocked_action_scope"] == "delivery_outcome_floor", quota_payload
    assert quota_payload["quota"]["handoff_outcome_floor_block"] is True, quota_payload
    assert quota_payload["safe_bypass_allowed"] is True, quota_payload
    assert quota_payload["safe_bypass_kind"] == "outcome_floor_recovery", quota_payload
    assert quota_payload["quota"]["post_handoff_outcome_gap_streak"] == 3, quota_payload
    assert quota_payload["heartbeat_recommendation"]["recommended_mode"] == "outcome_floor_recovery", quota_payload
    assert quota_payload["heartbeat_recommendation"]["notify"] == "DONT_NOTIFY", quota_payload
    quota_readiness = quota_payload["handoff_readiness"]
    assert quota_readiness["post_handoff_outcome_gap_streak"] == 3, quota_payload
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    assert "- decision: `safe_bypass_recovery`" in quota_markdown, quota_markdown
    assert "- should_run: `True`" in quota_markdown, quota_markdown
    assert "- recovery_delivery_allowed: `True`" in quota_markdown, quota_markdown
    assert "- state: `focus_wait`" in quota_markdown, quota_markdown
    assert "- safe_bypass_allowed: `True`" in quota_markdown, quota_markdown
    assert "- safe_bypass_kind: outcome_floor_recovery" in quota_markdown, quota_markdown
    assert "handoff outcome floor not met" in quota_markdown, quota_markdown
    assert "mode=outcome_floor_recovery notify=DONT_NOTIFY" in quota_markdown, quota_markdown
    assert "outcome_gap_streak=3" in quota_markdown, quota_markdown


def assert_delivery_batch_scale_prefers_test_named_runs() -> None:
    assert (
        delivery_batch_scale_for_run(
            {
                "classification": "dashboard_home_browser_smoke_regression",
                "delivery_batch_scale": "multi_surface",
            }
        )
        == "multi_surface"
    )
    assert (
        delivery_batch_scale_for_run(
            {"classification": "side_bypass_validation_plan_source_shape_consumer_test"}
        )
        == "test_only"
    )
    assert (
        delivery_batch_scale_for_run({"classification": "owner_handoff_consumer_test"})
        == "test_only"
    )
    assert (
        delivery_batch_scale_for_run({"classification": "delivery_ranker_readiness_batch"})
        == "multi_surface"
    )
    assert (
        delivery_batch_scale_for_run({"classification": "feedback_reranker_adapter_slice"})
        == "implementation"
    )
    profile = {
        "outcome_floor": {
            "surface_streak_threshold": 2,
            "outcome_markers": ["macro_evidence", "evidence_segment", "ranker_fit", "eval_metric"],
            "surface_only_hints": ["forecast", "runbook", "queue", "fields"],
        }
    }
    assert (
        delivery_outcome_for_run(
            {"classification": "side_bypass_owner_drop_landing_forecast_implementation"},
            profile,
        )
        == "surface_only"
    )
    assert (
        delivery_outcome_for_run(
            {"classification": "side_bypass_ranker_fit_metric_implementation"},
            profile,
        )
        == "outcome_progress"
    )
    assert (
        delivery_outcome_for_run(
            {"classification": "side_bypass_macro_evidence_segment_implementation"},
            profile,
        )
        == "outcome_progress"
    )
    assert (
        delivery_outcome_for_run(
            {"classification": "status_refresh_without_marker", "delivery_outcome": "primary_goal_outcome"},
            profile,
        )
        == "primary_goal_outcome"
    )


def assert_project_asset_secret_scanner_boundaries() -> None:
    assert project_asset_summary_is_public_safe(
        {
            "latest_validation": {
                "classification": "skill_delivery_hint_contract",
                "summary": "mask_delivery_hint_contract is also ordinary public text",
            }
        }
    )
    for value in (
        "s" + "k-" + "1234567890abcdef",
        "s" + "k_" + "1234567890abcdef",
        "a" + "k_" + "1234567890abcdef",
        "Bear" + "er " + "abcdefghijklmnop",
        "tok" + "en=" + "abcdefghijklmnop",
    ):
        assert not project_asset_summary_is_public_safe({"latest_validation": {"summary": value}}), value


def assert_explicit_delivery_refresh(payload: dict, markdown: str) -> None:
    item = payload["attention_queue"]["items"][0]
    assert item["goal_id"] == DELIVERY_GOAL_ID, item
    assert item["status"] == EXPLICIT_REFRESH_CLASSIFICATION, item
    readiness = item["handoff_readiness"]
    assert readiness["post_handoff_latest_run"]["classification"] == EXPLICIT_REFRESH_CLASSIFICATION, readiness
    assert readiness["post_handoff_latest_run"]["delivery_batch_scale"] == "multi_surface", readiness
    assert readiness["post_handoff_latest_run"]["delivery_outcome"] == "outcome_progress", readiness
    assert readiness["post_handoff_recent_runs"][0]["delivery_batch_scale"] == "multi_surface", readiness
    assert readiness["post_handoff_recent_runs"][0]["delivery_outcome"] == "outcome_progress", readiness
    assert readiness["post_handoff_small_scale_streak"] == 0, readiness
    assert readiness["post_handoff_outcome_gap_streak"] == 0, readiness
    assert "post_handoff_run: classification=dashboard_home_browser_smoke_regression" in markdown, markdown
    assert "scale=multi_surface" in markdown, markdown
    assert "outcome=outcome_progress" in markdown, markdown

    quota_payload = build_quota_should_run(payload, goal_id=DELIVERY_GOAL_ID)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["handoff_readiness"]["post_handoff_latest_run"]["delivery_batch_scale"] == "multi_surface", quota_payload
    assert quota_payload["handoff_readiness"]["post_handoff_latest_run"]["delivery_outcome"] == "outcome_progress", quota_payload


def assert_stale_latest_run_projection_warning(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    item = items[0]
    warning = item["stale_latest_run_warning"]
    assert warning["kind"] == "stale_latest_run_projection", warning
    assert warning["requires_refresh_state"] is True, warning
    assert warning["active_state_updated_at"] == "2026-01-01T00:03:00+00:00", warning
    assert warning["latest_run_generated_at"] == "2026-01-01T00:02:00+00:00", warning
    assert "active_state_updated_after_latest_run" in warning["reason"], warning
    assert "active_state_digest_differs_from_latest_run_snapshot" in warning["reason"], warning
    assert item["project_asset"]["stale_latest_run_warning"] == warning, item
    assert "stale_latest_run_warning: requires_refresh_state=True" in markdown, markdown
    assert "active_state_updated_at=2026-01-01T00:03:00+00:00" in markdown, markdown

    quota_payload = build_quota_should_run(payload, goal_id="planned-main-control")
    quota_warning = quota_payload["stale_latest_run_warning"]
    assert quota_warning["requires_refresh_state"] is True, quota_payload
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    assert "stale_latest_run_warning: requires_refresh_state=True" in quota_markdown, quota_markdown
    assert "stale_latest_run_action: run refresh-state before trusting latest_run-derived routing" in quota_markdown, quota_markdown

    packet = build_review_packet(payload, goal_id="planned-main-control", action_kind="codex")
    assert packet["stale_latest_run_warning"]["requires_refresh_state"] is True, packet
    assert "【状态投影警告】" in packet["packet"], packet
    assert "先 refresh-state，再信任基于 latest_run 的路由/交接" in packet["packet"], packet


def assert_handoff_waiting_for_post_run(item: dict, markdown: str) -> None:
    readiness = item["handoff_readiness"]
    assert readiness["ready"] is True, readiness
    assert readiness["handoff_status"] == "ready_waiting_for_run", readiness
    assert readiness["post_handoff_run_seen"] is False, readiness
    assert readiness["handoff_ready_at"] == "2026-01-01T00:01:00+00:00", readiness
    assert readiness["handoff_ready_classification"] == "operator_gate_approved", readiness
    assert "post_handoff_latest_run" not in readiness, readiness
    assert (
        "handoff_state: status=ready_waiting_for_run "
        "post_handoff_run_seen=False ready_at=2026-01-01T00:01:00+00:00"
    ) in markdown, markdown
    assert "post_handoff_run:" not in markdown.split("## Run History")[0], markdown


def assert_post_handoff_run_seen(payload: dict, markdown: str) -> None:
    items = payload["attention_queue"]["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["goal_id"] == "planned-main-control", item
    assert item["status"] == POST_HANDOFF_CLASSIFICATION, item
    assert item["waiting_on"] == "codex", item
    assert item["recommended_action"] == POST_HANDOFF_ACTION, item
    readiness = item["handoff_readiness"]
    assert readiness["ready"] is True, readiness
    assert readiness["handoff_status"] == "post_handoff_run_seen", readiness
    assert readiness["post_handoff_run_seen"] is True, readiness
    assert readiness["handoff_ready_at"] == "2026-01-01T00:01:00+00:00", readiness
    assert readiness["handoff_ready_classification"] == "operator_gate_approved", readiness
    assert readiness["post_handoff_latest_run"]["classification"] == POST_HANDOFF_CLASSIFICATION, readiness
    assert readiness["post_handoff_latest_run"]["generated_at"] == "2026-01-01T00:01:45+00:00", readiness
    assert readiness["post_handoff_latest_run"]["delivery_batch_scale"] == "single_surface", readiness
    assert [run["delivery_batch_scale"] for run in readiness["post_handoff_recent_runs"]] == [
        "single_surface",
        "single_surface",
    ], readiness
    assert readiness["post_handoff_small_scale_streak"] == 2, readiness
    assert (
        "handoff_state: status=post_handoff_run_seen "
        "post_handoff_run_seen=True ready_at=2026-01-01T00:01:00+00:00"
    ) in markdown, markdown
    assert (
        "post_handoff_run: classification=read_only_project_map "
        "at=2026-01-01T00:01:45+00:00 scale=single_surface"
    ) in markdown, markdown
    assert "post_handoff_recent_scales: single_surface,single_surface small_streak=2" in markdown, markdown
    quota_payload = build_quota_should_run(payload, goal_id="planned-main-control")
    quota_markdown = render_quota_should_run_markdown(quota_payload)
    quota_readiness = quota_payload["handoff_readiness"]
    assert quota_readiness["handoff_status"] == "post_handoff_run_seen", quota_payload
    assert quota_readiness["post_handoff_run_seen"] is True, quota_payload
    assert quota_readiness["post_handoff_latest_run"]["classification"] == POST_HANDOFF_CLASSIFICATION, quota_payload
    assert quota_readiness["post_handoff_latest_run"]["delivery_batch_scale"] == "single_surface", quota_payload
    assert [run["delivery_batch_scale"] for run in quota_readiness["post_handoff_recent_runs"]] == [
        "single_surface",
        "single_surface",
    ], quota_payload
    assert quota_readiness["post_handoff_small_scale_streak"] == 2, quota_payload
    assert "handoff_state: status=post_handoff_run_seen post_handoff_run_seen=True" in quota_markdown, quota_markdown
    assert (
        "post_handoff_run: classification=read_only_project_map "
        "at=2026-01-01T00:01:45+00:00 scale=single_surface"
    ) in quota_markdown, quota_markdown
    assert "post_handoff_recent_scales: single_surface,single_surface small_streak=2" in quota_markdown, quota_markdown


def assert_static_dashboard_post_handoff_scale(payload: dict, root: Path) -> None:
    status_path = root / "status.json"
    html_path = root / "status.html"
    status_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "examples/render-status-dashboard.py",
            str(status_path),
            str(html_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    html = html_path.read_text(encoding="utf-8")
    assert "Post-handoff run" in html, html
    assert "scale=single_surface" in html, html
    assert "Recent scales" in html, html
    assert "single_surface, single_surface; small_streak 2" in html, html


def main() -> int:
    assert_missing_project_asset_markdown_fallback()
    assert_usage_summary_markdown()
    assert_event_ledger_summary_markdown()
    assert_promotion_readiness_summary_markdown()
    assert_promotion_gate_summary_markdown()
    assert_decision_freshness_summary_markdown()
    assert_status_contract_health_projection()
    with tempfile.TemporaryDirectory(prefix="loopx-status-smoke-") as tmp:
        root = Path(tmp)
        registry_path = write_planned_registry(root)
        assert_project_local_status_excludes_runtime_orphans(registry_path)
        payload, markdown = collect_fixture_status(root, registry_path)
        mark_planned_todos_done(root)
        append_operator_gate_fixture(
            root,
            decision="approve",
            generated_at="2026-01-01T00:01:00+00:00",
            recommended_action=APPROVED_ACTION,
        )
        approved_payload, approved_markdown = collect_fixture_status(root, registry_path)
        append_quota_slot_spend_fixture(root, generated_at="2026-01-01T00:01:30+00:00")
        post_spend_payload, post_spend_markdown = collect_fixture_status(root, registry_path)
        append_post_handoff_run_fixture(root, generated_at="2026-01-01T00:01:40+00:00")
        append_post_handoff_run_fixture(root, generated_at="2026-01-01T00:01:45+00:00")
        post_handoff_payload, post_handoff_markdown = collect_fixture_status(root, registry_path)
        assert_static_dashboard_post_handoff_scale(post_handoff_payload, root)
        append_operator_gate_fixture(
            root,
            decision="reject",
            generated_at="2026-01-01T00:02:00+00:00",
            recommended_action=REJECTED_ACTION,
        )
        rejected_payload, rejected_markdown = collect_fixture_status(root, registry_path)
        append_operator_gate_fixture(
            root,
            decision="defer",
            generated_at="2026-01-01T00:03:00+00:00",
            recommended_action=DEFERRED_ACTION,
        )
        deferred_payload, deferred_markdown = collect_fixture_status(root, registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-registry-override-smoke-") as tmp:
        root = Path(tmp)
        registry_path = write_planned_registry(root)
        mark_planned_todos_done(root)
        append_state_refreshed_fixture(root, generated_at="2026-01-01T00:04:00+00:00")
        set_registry_attention_override(registry_path)
        override_payload, override_markdown = collect_fixture_status(root, registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-connected-delivery-smoke-") as tmp:
        root = Path(tmp)
        delivery_registry_path = write_connected_delivery_registry(root)
        append_connected_delivery_fixture(root, generated_at="2026-01-01T00:05:00+00:00")
        delivery_payload, delivery_markdown = collect_fixture_status(root, delivery_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-source-registry-shadow-") as tmp:
        root = Path(tmp)
        shadow_registry_path = write_connected_delivery_registry(root)
        write_global_source_registry_shadow(root, shadow_registry_path, goal_id=DELIVERY_GOAL_ID)
        append_connected_delivery_fixture(root, generated_at="2026-01-01T00:05:00+00:00")
        shadow_payload, _shadow_markdown = collect_fixture_status(root, shadow_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-explicit-refresh-scale-") as tmp:
        root = Path(tmp)
        explicit_registry_path = write_connected_delivery_registry(root)
        append_explicit_delivery_refresh(root, explicit_registry_path)
        explicit_payload, explicit_markdown = collect_fixture_status(root, explicit_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-stale-latest-run-") as tmp:
        root = Path(tmp)
        stale_projection_registry_path = write_planned_registry(root)
        append_stale_state_projection_fixture(root)
        stale_projection_payload, stale_projection_markdown = collect_fixture_status(root, stale_projection_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-connected-readonly-progress-") as tmp:
        root = Path(tmp)
        readonly_registry_path = write_connected_readonly_registry(root)
        append_connected_readonly_progress_fixture(root, generated_at="2026-01-01T00:05:00+00:00")
        readonly_payload, readonly_markdown = collect_fixture_status(root, readonly_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-dependency-blockers-") as tmp:
        root = Path(tmp)
        dependency_registry_path = write_dependency_blocker_registry(root)
        dependency_payload, dependency_markdown = collect_fixture_status(root, dependency_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-connected-delivery-small-streak-") as tmp:
        root = Path(tmp)
        delivery_registry_path = write_connected_delivery_registry(root)
        append_connected_delivery_fixture(
            root,
            generated_at="2026-01-01T00:05:00+00:00",
            classification="delivery_owner_drop_shape_test",
        )
        append_connected_delivery_fixture(
            root,
            generated_at="2026-01-01T00:06:00+00:00",
            classification="delivery_active_blocker_snapshot_test",
        )
        small_streak_payload, small_streak_markdown = collect_fixture_status(root, delivery_registry_path)
    with tempfile.TemporaryDirectory(prefix="loopx-status-connected-delivery-surface-loop-") as tmp:
        root = Path(tmp)
        delivery_registry_path = write_connected_delivery_registry(root)
        append_connected_delivery_fixture(
            root,
            generated_at="2026-01-01T00:05:00+00:00",
            classification="delivery_owner_drop_landing_forecast_implementation",
        )
        append_connected_delivery_fixture(
            root,
            generated_at="2026-01-01T00:06:00+00:00",
            classification="delivery_owner_drop_scenario_runbook_implementation",
        )
        append_connected_delivery_fixture(
            root,
            generated_at="2026-01-01T00:07:00+00:00",
            classification="delivery_next_action_queue_owner_drop_fields_implementation",
        )
        surface_loop_payload, surface_loop_markdown = collect_fixture_status(root, delivery_registry_path)

    assert_planned_preview_is_not_runnable(payload, markdown)
    approved_items = approved_payload["attention_queue"]["items"]
    assert len(approved_items) == 1, approved_items
    approved_item = approved_items[0]
    assert approved_item["goal_id"] == "planned-main-control", approved_item
    assert approved_item["status"] == "operator_gate_approved", approved_item
    assert approved_item["waiting_on"] == "codex", approved_item
    assert approved_item["recommended_action"] == APPROVED_ACTION, approved_item
    assert approved_item["project_asset"]["owner"] == "codex", approved_item
    assert approved_item["project_asset"]["gate"] == "none", approved_item
    assert approved_item["project_asset"]["next_action"] == APPROVED_ACTION, approved_item
    assert "command fails" in approved_item["project_asset"]["stop_condition"], approved_item
    assert approved_item["project_asset"]["latest_validation"]["classification"] == "operator_gate_approved", approved_item
    assert approved_item["agent_command"] == APPROVED_COMMAND, approved_item
    assert "operator_question" not in approved_item, approved_item
    assert "operator_gate_dry_run" not in approved_markdown, approved_markdown
    assert "latest_validation: classification=operator_gate_approved" in approved_markdown, approved_markdown
    assert f"agent_command: `{APPROVED_COMMAND}`" in approved_markdown, approved_markdown
    approved_run = approved_payload["run_history"]["goals"][0]["latest_runs"][0]
    resume_contract = approved_run["operator_gate_resume_contract"]
    assert resume_contract["version"] == "operator_gate_resume_contract_v0", resume_contract
    assert resume_contract["gate_id"] == "read_only_map_opt_in", resume_contract
    assert resume_contract["operator_decision"] == "approve", resume_contract
    assert "decision_point_rebase_only" in resume_contract["migration_or_rebase_result"], resume_contract
    assert "whole repo/worktree" in resume_contract["migration_or_rebase_result"], resume_contract
    assert "operator_gate_resume_contract: version=operator_gate_resume_contract_v0" in approved_markdown, approved_markdown
    assert_handoff_waiting_for_post_run(approved_item, approved_markdown)
    approved_quota_payload = assert_quota_should_run(
        approved_payload,
        expected=True,
        state="eligible",
        waiting_on="codex",
    )
    approved_quota_readiness = approved_quota_payload["handoff_readiness"]
    assert approved_quota_readiness["handoff_status"] == "ready_waiting_for_run", approved_quota_payload
    assert approved_quota_readiness["post_handoff_run_seen"] is False, approved_quota_payload
    approved_quota_markdown = render_quota_should_run_markdown(approved_quota_payload)
    assert "handoff_state: status=ready_waiting_for_run post_handoff_run_seen=False" in approved_quota_markdown, approved_quota_markdown
    post_spend_items = post_spend_payload["attention_queue"]["items"]
    assert len(post_spend_items) == 1, post_spend_items
    post_spend_item = post_spend_items[0]
    assert post_spend_item["status"] == "operator_gate_approved", post_spend_item
    assert post_spend_item["recommended_action"] == APPROVED_ACTION, post_spend_item
    assert "quota_slot_spent" in json.dumps(post_spend_payload["run_history"], ensure_ascii=False), post_spend_payload
    assert "quota_slot_spent" not in post_spend_markdown.split("## Run History")[0], post_spend_markdown
    assert_handoff_waiting_for_post_run(post_spend_item, post_spend_markdown)
    assert_post_handoff_run_seen(post_handoff_payload, post_handoff_markdown)
    assert_operator_gate_waits_for_user(
        rejected_payload,
        rejected_markdown,
        status="operator_gate_rejected",
        action=REJECTED_ACTION,
    )
    assert_quota_should_run(
        rejected_payload,
        expected=False,
        state="operator_gate",
        waiting_on="user_or_controller",
    )
    assert_operator_gate_waits_for_user(
        deferred_payload,
        deferred_markdown,
        status="operator_gate_deferred",
        action=DEFERRED_ACTION,
    )
    assert_quota_should_run(
        deferred_payload,
        expected=False,
        state="operator_gate",
        waiting_on="user_or_controller",
    )
    assert_registry_attention_override(override_payload, override_markdown)
    assert_connected_delivery_custom_run_stays_runnable(delivery_payload, delivery_markdown)
    assert_source_registry_shadow_collapses_into_live_queue_item(shadow_payload)
    assert_explicit_delivery_refresh(explicit_payload, explicit_markdown)
    assert_stale_latest_run_projection_warning(stale_projection_payload, stale_projection_markdown)
    assert_connected_readonly_progress_run_stays_runnable(readonly_payload, readonly_markdown)
    assert_dependency_blockers_stay_separate(dependency_payload, dependency_markdown)
    assert_connected_delivery_no_baseline_small_streak(small_streak_payload, small_streak_markdown)
    assert_connected_delivery_surface_loop(surface_loop_payload, surface_loop_markdown)
    assert_delivery_batch_scale_prefers_test_named_runs()
    assert_project_asset_secret_scanner_boundaries()
    assert_promotion_readiness_full_scan_fallback()
    assert_promotion_readiness_warning_in_quota_guard()
    assert_status_agent_lane_next_action_projection()
    assert_status_agent_member_selected_lane_claim_survives_truncated_claim_list()
    assert_status_agent_member_handoff_uses_quota_identity()
    assert_status_agent_lane_frontier_hint_projection()
    print("status-markdown-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
