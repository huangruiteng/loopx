#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench runner mode contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-runner-mode-contract-v0.md"
README = TOPIC_DIR / "README.md"

CONTRACT_SCHEMA = "terminal_bench_runner_mode_contract_v0"
MODES = ("codex-goal-mode", "codex-loopx")

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench Runner Mode Contract V0",
    "core LoopX research",
    "loopx benchmark run terminal-bench",
    "--mode codex-goal-mode | codex-loopx",
    "Parent runner control plane",
    "Codex goal-mode baseline",
    "LoopX treatment worker",
    "Why Not Keep Bare Codex",
    "Run both arms in parallel",
    "case_semantics_changed_by_harness",
    "loopx_inside_case",
    "official_score_comparable_to_native_codex",
    "model + harness",
    "no-run/no-submit",
    "python3 examples/terminal-bench-runner-mode-contract-smoke.py",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "ARK" + "_BASE_URL=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
]


def mode_contract() -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "benchmark_id": "terminal-bench",
        "runner": "harbor",
        "parent_runner_control_plane": {
            "identity": "loopx_parent_runner",
            "purpose": "runner_wiring_and_result_ingest_control_plane",
            "may_select_task_slice": True,
            "may_recheck_quota_and_gates": True,
            "may_append_compact_history": True,
            "may_change_case_prompt_tests_scoring_or_timeout": False,
            "may_upload_or_submit": False,
        },
        "modes": {
            "codex-goal-mode": {
                "worker_mode": "codex_goal_mode_baseline",
                "loopx_around_case": "parent_runner_only",
                "loopx_inside_case": False,
                "case_semantics_changed_by_harness": False,
                "official_score_comparable_to_native_codex": False,
                "official_score_comparable_to_loopx_treatment": True,
                "control_plane_score_applicable": False,
                "injects_review_packet_or_active_state": False,
                "codex_goal_mode_baseline": True,
                "leaderboard_evidence": False,
                "is_core_loopx_experiment": False,
                "primary_use": "true Codex goal-mode baseline for LoopX experiments",
            },
            "codex-loopx": {
                "worker_mode": "codex_loopx_cli",
                "loopx_around_case": "parent_runner_plus_managed_checkpoints",
                "loopx_inside_case": True,
                "case_semantics_changed_by_harness": True,
                "official_score_comparable_to_native_codex": False,
                "official_score_comparable_to_loopx_treatment": False,
                "control_plane_score_applicable": True,
                "injects_review_packet_or_active_state": "allowed_only_as_managed_mode_surface",
                "leaderboard_evidence": False,
                "is_core_loopx_experiment": True,
                "primary_use": "core experiment evaluating Codex plus LoopX as a model-plus-harness pair",
            },
        },
        "baseline_policy": {
            "bare_codex_runner_path_enabled": False,
            "codex_goal_mode_is_primary_baseline": True,
            "hardened_install_is_optional_calibration": True,
            "run_arms_in_parallel": True,
        },
        "baseline_invariants": {
            "task_prompt_changed": False,
            "tests_scoring_resources_timeout_changed": False,
            "loopx_state_injected": False,
            "upload_share_or_leaderboard_flags": False,
        },
        "managed_mode_required_fields": [
            "case_semantics_changed_by_harness",
            "state_surfaces_available_to_worker",
            "intervention_checkpoint_replan_counts",
            "claim_boundary_model_plus_harness_pair",
        ],
        "recommended_implementation_order": [
            "codex_goal_mode_baseline_no_run_fixture_and_command_envelope",
            "codex_loopx_worker_bridge_fixture",
            "private_no_upload_runner_wrapper_with_two_primary_modes",
            "paired_parallel_hard_task_runs",
        ],
        "stop_conditions": [
            "do_not_reintroduce_bare_codex_as_primary_baseline",
            "do_not_inject_loopx_state_into_goal_mode_baseline_case",
            "do_not_call_codex_loopx_native_codex_baseline",
            "do_not_upload_submit_or_claim_leaderboard",
            "do_not_record_credentials_raw_sessions_raw_logs_or_host_paths",
        ],
        "real_run": False,
        "submit_eligible": False,
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 14000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    leaked = [snippet for snippet in FORBIDDEN_TEXT if snippet in text]
    assert not leaked, leaked
    assert "terminal-bench-runner-mode-contract-v0.md" in readme, readme


def assert_mode_contract(payload: dict[str, Any]) -> None:
    assert payload["schema_version"] == CONTRACT_SCHEMA, payload
    assert payload["real_run"] is False, payload
    assert payload["submit_eligible"] is False, payload
    parent = payload["parent_runner_control_plane"]
    assert parent["identity"] == "loopx_parent_runner", parent
    assert parent["may_append_compact_history"] is True, parent
    assert parent["may_change_case_prompt_tests_scoring_or_timeout"] is False, parent
    assert parent["may_upload_or_submit"] is False, parent

    modes = payload["modes"]
    assert tuple(modes) == MODES, modes
    baseline = modes["codex-goal-mode"]
    treatment = modes["codex-loopx"]
    baseline_policy = payload["baseline_policy"]

    assert baseline["loopx_inside_case"] is False, baseline
    assert baseline["case_semantics_changed_by_harness"] is False, baseline
    assert baseline["official_score_comparable_to_native_codex"] is False, baseline
    assert baseline["official_score_comparable_to_loopx_treatment"] is True, baseline
    assert baseline["injects_review_packet_or_active_state"] is False, baseline
    assert baseline["codex_goal_mode_baseline"] is True, baseline
    assert baseline["leaderboard_evidence"] is False, baseline
    assert baseline["is_core_loopx_experiment"] is False, baseline

    assert treatment["loopx_inside_case"] is True, treatment
    assert treatment["case_semantics_changed_by_harness"] is True, treatment
    assert treatment["official_score_comparable_to_native_codex"] is False, treatment
    assert treatment["control_plane_score_applicable"] is True, treatment
    assert treatment["leaderboard_evidence"] is False, treatment
    assert treatment["is_core_loopx_experiment"] is True, treatment

    assert baseline_policy["bare_codex_runner_path_enabled"] is False, baseline_policy
    assert baseline_policy["codex_goal_mode_is_primary_baseline"] is True, baseline_policy
    assert baseline_policy["hardened_install_is_optional_calibration"] is True, baseline_policy
    assert baseline_policy["run_arms_in_parallel"] is True, baseline_policy

    invariants = payload["baseline_invariants"]
    assert all(value is False for value in invariants.values()), invariants
    assert "do_not_inject_loopx_state_into_goal_mode_baseline_case" in payload["stop_conditions"], payload
    assert "codex_loopx_worker_bridge_fixture" in payload[
        "recommended_implementation_order"
    ], payload
    assert_public_safe(payload)


def main() -> None:
    assert_doc_contract()
    payload = mode_contract()
    assert_mode_contract(payload)
    print(
        "terminal-bench-runner-mode-contract-smoke ok "
        f"modes={len(payload['modes'])} "
        f"baseline_inside={payload['modes']['codex-goal-mode']['loopx_inside_case']} "
        f"treatment_inside={payload['modes']['codex-loopx']['loopx_inside_case']}"
    )


if __name__ == "__main__":
    main()
