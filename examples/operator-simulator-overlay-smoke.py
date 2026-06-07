#!/usr/bin/env python3
"""Smoke-test the operator-simulator overlay protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
ROADMAP = TOPIC_DIR / "roadmap.md"
PROTOCOL = TOPIC_DIR / "operator-simulator-overlay-v0.md"

PLAN_SCHEMA = "operator_simulator_overlay_v0"
RUN_SCHEMA = "operator_simulator_run_v0"
BENCHMARK_ID = "goal-harness-local-operator-simulator@v0"
TASK_ID = "mini_control_plane_repair_v0"

SIMULATOR_SETTINGS = [
    "deterministic_scripted_user",
    "same_family_simulator_agent",
    "stronger_simulator_weaker_agent",
    "weaker_simulator_stronger_agent",
    "codex_worker_non_codex_simulator",
    "doubao2_simulator_or_worker",
]

COMPARISON_MODES = [
    "official_or_native",
    "passive_goal_harness_wrapper",
    "assisted_operator_simulator",
]

ALLOWED_VISIBILITY = [
    "public_task_statement",
    "benchmark_visible_worker_context",
    "public_safe_goal_harness_state_summary",
    "public_safe_todos_gates_review_packet",
    "goal_tick_phases",
    "worker_visible_validation_output",
    "public_safe_artifact_manifest",
    "compact_run_summary",
]

FORBIDDEN_VISIBILITY = [
    "hidden_tests",
    "expected_solutions",
    "benchmark_answer_keys",
    "private_project_material",
    "credentials",
    "raw_transcript_material",
    "raw_runner_logs",
    "local_host_paths",
    "benchmark_forbidden_state",
]

ALLOWED_INTERVENTIONS = [
    "plan_approval",
    "scope_clarification",
    "continue_or_stop_after_failed_validation",
    "validation_triage",
    "process_drift_correction",
    "evidence_request",
    "handoff_quality_check",
]

FORBIDDEN_INTERVENTIONS = [
    "hidden_answer_hint",
    "benchmark_solution_steps",
    "private_data_lookup",
    "direct_code_patch",
    "tool_execution_on_worker_behalf",
    "benchmark_prompt_or_test_mutation",
    "timeout_resource_scoring_or_upload_change",
]

FAILURE_LABELS = [
    "simulator_oracle_leak",
    "simulator_overguidance",
    "simulator_underhelp",
    "premature_stop",
    "missed_process_drift",
    "stale_state_reinforcement",
    "ambiguity_injection",
    "tool_state_mismatch",
    "budget_exhaustion",
    "model_capability_mismatch",
    "policy_violation",
    "intervention_latency",
    "unsupported_runner_boundary",
    "worker_ignored_valid_guidance",
    "worker_overfit_to_guidance",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "DAYTONA" + "_API_KEY",
    "lark" + "office",
    "fei" + "shu.cn",
    "raw" + "_thread",
    "session" + "_history",
    "s" + "k-" + "example",
]


def overlay_plan() -> dict[str, Any]:
    return {
        "schema_version": PLAN_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "task_id": TASK_ID,
        "comparison_modes": COMPARISON_MODES,
        "default_smoke_setting": "deterministic_scripted_user",
        "simulator_settings": SIMULATOR_SETTINGS,
        "preconditions": {
            "passive_baseline_required": True,
            "official_score_separation_required": True,
            "leaderboard_claim_allowed": False,
            "model_backed_simulator_default": False,
        },
        "visibility_policy": {
            "policy_id": "public_worker_visible_state_only",
            "allowed": ALLOWED_VISIBILITY,
            "forbidden": FORBIDDEN_VISIBILITY,
        },
        "intervention_budget": {
            "max_turns": 4,
            "max_chars_per_turn": 800,
            "allowed_types": ALLOWED_INTERVENTIONS,
            "forbidden_types": FORBIDDEN_INTERVENTIONS,
            "may_ask_clarifying_question": True,
            "on_budget_exhausted": "stop_or_return_to_passive_mode",
        },
        "failure_taxonomy": FAILURE_LABELS,
        "output_schema": RUN_SCHEMA,
        "side_effect_budget": {
            "model_api": False,
            "docker": False,
            "cloud_sandbox": False,
            "paid_compute": False,
            "leaderboard_upload": False,
            "benchmark_mutation": False,
        },
    }


def scripted_run_row(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "benchmark_id": plan["benchmark_id"],
        "task_id": plan["task_id"],
        "mode": "assisted_operator_simulator",
        "worker_identity": {
            "surface": "codex_cli_fixture",
            "model_family": "deterministic_shim",
        },
        "simulator_identity": {
            "setting": "deterministic_scripted_user",
            "model_family": "scripted",
            "seed": "operator-simulator-overlay-smoke-v0",
        },
        "visibility_policy_id": plan["visibility_policy"]["policy_id"],
        "intervention_budget": plan["intervention_budget"],
        "interventions": [
            {
                "turn": 1,
                "type": "scope_clarification",
                "chars": 118,
                "accepted_by_worker": True,
            },
            {
                "turn": 2,
                "type": "validation_triage",
                "chars": 156,
                "accepted_by_worker": True,
            },
        ],
        "official_task_score_reference": {
            "kind": "not_run",
            "value": None,
            "reason": "operator-simulator smoke does not run an official benchmark",
        },
        "control_plane_score_reference": {
            "kind": "local_contract_check",
            "value": 1.0,
        },
        "failure_labels": [],
        "simulator_induced_error_count": 0,
        "overhead": {
            "extra_turns": 2,
            "wall_time_seconds": 0,
            "cost_usd": 0.0,
        },
        "trace_publicness": "public_contract_fixture",
        "side_effect_audit_passed": True,
    }


def assert_doc_contract() -> None:
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    compact_protocol = " ".join(protocol.split())
    required = [
        "Operator-Simulator Overlay V0",
        PLAN_SCHEMA,
        RUN_SCHEMA,
        "Comparison Modes",
        "Simulator Matrix",
        "Visibility Limits",
        "Intervention Budget",
        "Failure Taxonomy",
        "deterministic_scripted_user",
        "same_family_simulator_agent",
        "stronger_simulator_weaker_agent",
        "weaker_simulator_stronger_agent",
        "codex_worker_non_codex_simulator",
        "doubao2_simulator_or_worker",
        "simulator_oracle_leak",
        "worker_overfit_to_guidance",
        "Never merge assisted-mode gains into official leaderboard scores.",
        "python3 examples/operator-simulator-overlay-smoke.py",
    ]
    missing = [snippet for snippet in required if snippet not in compact_protocol]
    assert not missing, missing
    assert "operator-simulator-overlay-v0.md" in readme, readme
    assert "operator-simulator overlay" in roadmap, roadmap
    assert "Assisted operator-simulator mode" in roadmap, roadmap

    leaked = [marker for marker in FORBIDDEN_TEXT if marker in protocol]
    assert not leaked, leaked


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 14000, len(text)


def assert_plan_contract(plan: dict[str, Any]) -> None:
    assert plan["schema_version"] == PLAN_SCHEMA, plan
    assert plan["comparison_modes"] == COMPARISON_MODES, plan
    assert plan["default_smoke_setting"] == "deterministic_scripted_user", plan
    assert set(plan["simulator_settings"]) == set(SIMULATOR_SETTINGS), plan
    assert plan["preconditions"]["passive_baseline_required"] is True, plan
    assert plan["preconditions"]["official_score_separation_required"] is True, plan
    assert plan["preconditions"]["leaderboard_claim_allowed"] is False, plan
    assert plan["preconditions"]["model_backed_simulator_default"] is False, plan
    assert set(plan["visibility_policy"]["allowed"]) == set(ALLOWED_VISIBILITY), plan
    assert set(plan["visibility_policy"]["forbidden"]) == set(FORBIDDEN_VISIBILITY), plan
    assert set(plan["intervention_budget"]["allowed_types"]) == set(ALLOWED_INTERVENTIONS), plan
    assert set(plan["intervention_budget"]["forbidden_types"]) == set(FORBIDDEN_INTERVENTIONS), plan
    assert set(plan["failure_taxonomy"]) == set(FAILURE_LABELS), plan
    assert all(value is False for value in plan["side_effect_budget"].values()), plan
    assert_public_safe(plan)


def assert_run_contract(plan: dict[str, Any], row: dict[str, Any]) -> None:
    assert row["schema_version"] == RUN_SCHEMA, row
    assert row["mode"] == "assisted_operator_simulator", row
    assert row["simulator_identity"]["setting"] == plan["default_smoke_setting"], row
    assert row["visibility_policy_id"] == plan["visibility_policy"]["policy_id"], row
    assert row["official_task_score_reference"]["kind"] == "not_run", row
    assert row["official_task_score_reference"]["value"] is None, row
    assert row["simulator_induced_error_count"] == 0, row
    assert row["side_effect_audit_passed"] is True, row
    assert row["trace_publicness"] == "public_contract_fixture", row
    assert all(
        intervention["type"] in plan["intervention_budget"]["allowed_types"]
        for intervention in row["interventions"]
    ), row
    assert row["overhead"]["cost_usd"] == 0.0, row
    assert_public_safe({"plan": plan, "run": row})


def main() -> None:
    assert_doc_contract()
    plan = overlay_plan()
    assert_plan_contract(plan)
    row = scripted_run_row(plan)
    assert_run_contract(plan, row)
    print(
        "operator-simulator-overlay-smoke ok "
        f"settings={len(plan['simulator_settings'])} "
        f"interventions={len(row['interventions'])} "
        f"model_api={plan['side_effect_budget']['model_api']}"
    )


if __name__ == "__main__":
    main()
