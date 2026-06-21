#!/usr/bin/env python3
"""Smoke-test a deterministic active-user assisted pilot row."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
ROADMAP = TOPIC_DIR / "roadmap.md"
PILOT_DOC = TOPIC_DIR / "active-user-assisted-pilot-v0.md"
OVERLAY_DOC = TOPIC_DIR / "operator-simulator-overlay-v0.md"

PILOT_SCHEMA = "active_user_assisted_pilot_v0"
ACTIVE_INJECTION_SCHEMA = "active_user_simulator_injection_v0"
RUN_SCHEMA = "operator_simulator_run_v0"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "train-fasttext"

FAILED_AUTONOMOUS_MODES = [
    {
        "mode": "hardened_codex_baseline",
        "official_task_score": 0.0,
        "loopx_cli_calls": 0,
    },
    {
        "mode": "codex_loopx",
        "official_task_score": 0.0,
        "loopx_cli_calls": 2,
    },
]

ALLOWED_VISIBILITY = [
    "public_task_statement",
    "compact_failure_summary",
    "worker_visible_validation_output",
    "public_safe_loopx_state_summary",
]

NO_ORACLE_AUDIT_KEYS = [
    "hidden_tests_seen",
    "expected_solution_seen",
    "answer_key_seen",
    "private_material_seen",
    "raw_forbidden_logs_seen",
    "direct_patch_supplied",
    "tool_executed_for_worker",
    "benchmark_scoring_or_resource_changed",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "DAYTONA" + "_API_KEY",
    "raw" + "_thread",
    "session" + "_history",
    "s" + "k-" + "example",
]


def pilot_plan() -> dict[str, Any]:
    return {
        "schema_version": PILOT_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "task_id": TASK_ID,
        "trigger": {
            "kind": "previous_compact_negative_result",
            "failed_autonomous_modes": FAILED_AUTONOMOUS_MODES,
            "both_autonomous_modes_failed": True,
            "assisted_score_kind": "not_run",
        },
        "active_injection_contract": {
            "schema_version": ACTIVE_INJECTION_SCHEMA,
            "simulator_setting": "deterministic_scripted_user",
            "proactive_intervention_allowed": True,
            "directive_feedback_allowed": True,
            "artificial_mildness_required": False,
        },
        "frequency_budget": {
            "max_interventions": 3,
            "max_proactive_interventions": 2,
            "min_worker_events_between_proactive": 2,
            "max_chars_per_intervention": 800,
        },
        "visibility_policy": {
            "policy_id": "compact_failure_and_worker_visible_state_only",
            "allowed": ALLOWED_VISIBILITY,
            "forbidden": [
                "hidden_tests",
                "expected_solutions",
                "benchmark_answer_keys",
                "private_project_material",
                "raw_runner_logs",
                "local_host_paths",
            ],
        },
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "leaderboard_claim_allowed": False,
        },
    }


def assisted_run(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "pilot_schema_version": plan["schema_version"],
        "benchmark_id": plan["benchmark_id"],
        "task_id": plan["task_id"],
        "mode": "assisted_operator_simulator",
        "worker_identity": {
            "surface": "codex_loopx_fixture",
            "model_family": "deterministic_shim",
        },
        "simulator_identity": {
            "setting": "deterministic_scripted_user",
            "model_family": "scripted",
            "seed": "active-user-assisted-pilot-v0",
        },
        "failed_autonomous_reference": plan["trigger"]["failed_autonomous_modes"],
        "visibility_policy_id": plan["visibility_policy"]["policy_id"],
        "intervention_budget": plan["frequency_budget"],
        "interventions": [
            {
                "turn": 1,
                "channel": "simulator_proactive_user_message",
                "proactive": True,
                "type": "strategy_redirection",
                "chars": 312,
                "worker_events_since_previous_proactive": 3,
                "visible_evidence_basis": [
                    "public_task_statement",
                    "compact_failure_summary",
                    "worker_visible_validation_output",
                ],
                "no_oracle_audit": {key: False for key in NO_ORACLE_AUDIT_KEYS},
                "accepted_by_worker": True,
            },
            {
                "turn": 2,
                "channel": "simulator_proactive_user_message",
                "proactive": True,
                "type": "validation_triage",
                "chars": 241,
                "worker_events_since_previous_proactive": 2,
                "visible_evidence_basis": [
                    "compact_failure_summary",
                    "worker_visible_validation_output",
                ],
                "no_oracle_audit": {key: False for key in NO_ORACLE_AUDIT_KEYS},
                "accepted_by_worker": True,
            },
        ],
        "official_task_score_reference": {
            "kind": "not_run",
            "value": None,
            "reason": "deterministic assisted pilot does not execute Terminal-Bench",
        },
        "collaboration_hypothesis": {
            "kind": "assisted_recovery_from_failed_autonomous_case",
            "expected_signal": "reduced_invalid_exploration_before_next_real_run",
        },
        "failure_labels": [],
        "simulator_induced_error_count": 0,
        "frequency_budget_audit": {
            "proactive_interventions": 2,
            "max_proactive_interventions": plan["frequency_budget"]["max_proactive_interventions"],
            "min_worker_events_between_proactive_satisfied": True,
        },
        "side_effect_audit": {
            "model_api": False,
            "benchmark_run": False,
            "docker": False,
            "cloud_sandbox": False,
            "paid_compute": False,
            "private_artifact_read": False,
            "leaderboard_upload": False,
        },
        "next_run_decision": {
            "decision": "eligible_for_private_no_upload_assisted_treatment",
            "requires_real_runner_approval": True,
            "keep_official_scores_separate": True,
        },
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 14000, len(text)


def assert_docs() -> None:
    pilot_doc = PILOT_DOC.read_text(encoding="utf-8")
    overlay_doc = OVERLAY_DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    required = [
        "Active User Assisted Pilot V0",
        PILOT_SCHEMA,
        ACTIVE_INJECTION_SCHEMA,
        RUN_SCHEMA,
        "terminal-bench@2.0/train-fasttext",
        "assisted score: `not_run`",
        "maximum proactive interventions",
        "no-oracle audit",
        "python3 examples/active-user-assisted-pilot-smoke.py",
    ]
    missing = [snippet for snippet in required if snippet not in pilot_doc]
    assert not missing, missing
    assert ACTIVE_INJECTION_SCHEMA in overlay_doc, overlay_doc
    assert "active-user-assisted-pilot-v0.md" in readme, readme
    assert "deterministic active-user assisted pilot" in roadmap, roadmap


def assert_plan(plan: dict[str, Any]) -> None:
    assert plan["schema_version"] == PILOT_SCHEMA, plan
    assert plan["trigger"]["both_autonomous_modes_failed"] is True, plan
    assert plan["trigger"]["assisted_score_kind"] == "not_run", plan
    assert all(item["official_task_score"] == 0.0 for item in plan["trigger"]["failed_autonomous_modes"]), plan
    assert plan["active_injection_contract"]["proactive_intervention_allowed"] is True, plan
    assert plan["active_injection_contract"]["directive_feedback_allowed"] is True, plan
    assert plan["active_injection_contract"]["artificial_mildness_required"] is False, plan
    assert plan["claim_boundary"]["official_score_claim_allowed"] is False, plan
    assert plan["claim_boundary"]["assisted_collaboration_claim_allowed"] is True, plan
    assert set(plan["visibility_policy"]["allowed"]) == set(ALLOWED_VISIBILITY), plan
    assert_public_safe(plan)


def assert_run(plan: dict[str, Any], row: dict[str, Any]) -> None:
    assert row["schema_version"] == RUN_SCHEMA, row
    assert row["pilot_schema_version"] == plan["schema_version"], row
    assert row["official_task_score_reference"]["kind"] == "not_run", row
    assert row["official_task_score_reference"]["value"] is None, row
    assert row["next_run_decision"]["keep_official_scores_separate"] is True, row
    assert all(value is False for value in row["side_effect_audit"].values()), row
    proactive = [item for item in row["interventions"] if item["proactive"]]
    assert len(proactive) == row["frequency_budget_audit"]["proactive_interventions"], row
    assert len(proactive) <= plan["frequency_budget"]["max_proactive_interventions"], row
    assert row["frequency_budget_audit"]["min_worker_events_between_proactive_satisfied"] is True, row
    assert all(item["chars"] <= plan["frequency_budget"]["max_chars_per_intervention"] for item in row["interventions"]), row
    assert all(
        item["worker_events_since_previous_proactive"]
        >= plan["frequency_budget"]["min_worker_events_between_proactive"]
        for item in proactive
    ), row
    assert all(
        set(item["visible_evidence_basis"]) <= set(plan["visibility_policy"]["allowed"])
        for item in row["interventions"]
    ), row
    assert all(
        set(item["no_oracle_audit"]) == set(NO_ORACLE_AUDIT_KEYS)
        and not any(item["no_oracle_audit"].values())
        for item in row["interventions"]
    ), row
    assert_public_safe({"plan": plan, "run": row})


def main() -> None:
    assert_docs()
    plan = pilot_plan()
    assert_plan(plan)
    row = assisted_run(plan)
    assert_run(plan, row)
    print(
        "active-user-assisted-pilot-smoke ok "
        f"task={row['task_id']} "
        f"failed_modes={len(row['failed_autonomous_reference'])} "
        f"proactive={row['frequency_budget_audit']['proactive_interventions']} "
        f"official={row['official_task_score_reference']['kind']}"
    )


if __name__ == "__main__":
    main()
