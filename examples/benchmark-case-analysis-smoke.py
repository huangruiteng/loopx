#!/usr/bin/env python3
"""Validate benchmark case analysis artifacts stay public-safe and useful."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_case_analysis import (  # noqa: E402
    harness_interaction_public_summary_coverage,
    trajectory_public_summary_coverage,
)
ANALYSIS_JSON = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "benchmark-case-analysis.json"
)
ANALYSIS_MD = ANALYSIS_JSON.with_suffix(".md")
LEDGER_JSON = ANALYSIS_JSON.with_name("benchmark-run-ledger.json")


FORBIDDEN_PATTERNS = [
    re.compile(r"/Users/"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"trajectory/", re.IGNORECASE),
    re.compile(r"\.local/private-benchmark-jobs/"),
]


def assert_public_safe(text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), pattern.pattern


def assert_compact_legacy_result(result: dict) -> None:
    assert result["schema_version"] == "compact_legacy_case_result_v0", result
    noisy_legacy_fields = {
        "capability_signal",
        "control_plane_signal",
        "optimization_guidance",
        "routing_guidance",
        "stability_assessment",
        "trajectory_analysis",
    }
    assert noisy_legacy_fields.isdisjoint(result), result


def test_case_analysis_json() -> None:
    payload = json.loads(ANALYSIS_JSON.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER_JSON.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "benchmark_case_analysis_v0", payload
    assert payload["update_policy"]["raw_logs_recorded"] is False, payload
    assert payload["update_policy"]["raw_task_text_recorded"] is False, payload
    assert payload["update_policy"]["trajectory_recorded"] is False, payload
    assert payload["update_policy"]["absolute_paths_recorded"] is False, payload

    cases = payload.get("cases")
    assert isinstance(cases, list) and len(cases) >= 2, payload
    trajectory_coverage = trajectory_public_summary_coverage(payload)
    assert trajectory_coverage["schema_version"] == (
        "trajectory_public_summary_coverage_v0"
    ), trajectory_coverage
    assert trajectory_coverage["summary_count"] == 5, trajectory_coverage
    assert trajectory_coverage["public_safe_count"] == 5, trajectory_coverage
    assert trajectory_coverage["attribution_conclusion_count"] == 5, (
        trajectory_coverage
    )
    coverage_rows = {
        (row["benchmark_id"], row["case_id"], row["summary_path"]): row
        for row in trajectory_coverage["rows"]
    }
    assert (
        "skillsbench@1.1",
        "citation-check",
        "post_stop_policy_raw_rerun.trajectory_public_summary",
    ) in coverage_rows, trajectory_coverage
    assert (
        "skillsbench@1.1",
        "3d-scan-calc",
        (
            "historical_final_only_lifecycle_trajectory_summaries"
            ".baseline.trajectory_public_summary"
        ),
    ) in coverage_rows, trajectory_coverage
    scan_treatment_trajectory = coverage_rows[
        (
            "skillsbench@1.1",
            "3d-scan-calc",
            (
                "historical_final_only_lifecycle_trajectory_summaries"
                ".treatment.trajectory_public_summary"
            ),
        )
    ]
    assert scan_treatment_trajectory["round_count"] == 8, scan_treatment_trajectory
    assert scan_treatment_trajectory["tool_call_count"] == 138, (
        scan_treatment_trajectory
    )
    assert scan_treatment_trajectory["loopx_cli_call_count"] == 73, (
        scan_treatment_trajectory
    )
    assert (
        "skillsbench@1.1",
        "debug-trl-grpo",
        "trajectory_public_summary",
    ) in coverage_rows, trajectory_coverage
    assert (
        "skillsbench@1.1",
        "paratransit-routing",
        "legacy_blind_loop_positive_result.trajectory_public_summary",
    ) in coverage_rows, trajectory_coverage
    for row in trajectory_coverage["rows"]:
        assert row["public_safe"] is True, row
        assert row["private_trajectory_present"] is True, row
    harness_coverage = harness_interaction_public_summary_coverage(payload)
    assert harness_coverage["schema_version"] == (
        "harness_interaction_public_summary_coverage_v0"
    ), harness_coverage
    assert harness_coverage["raw_trajectory_recorded"] is False, harness_coverage
    assert harness_coverage["raw_task_text_recorded"] is False, harness_coverage
    assert harness_coverage["raw_verifier_output_recorded"] is False, harness_coverage
    assert harness_coverage["raw_logs_recorded"] is False, harness_coverage
    assert harness_coverage["summary_count"] >= 8, harness_coverage
    assert harness_coverage["public_safe_count"] == harness_coverage[
        "summary_count"
    ], harness_coverage
    assert {"skillsbench@1.1", "terminal-bench@2.0", "swe-marathon"}.issubset(
        set(harness_coverage["benchmark_ids"])
    ), harness_coverage
    harness_rows = {
        (row["benchmark_id"], row["case_id"], row["summary_path"]): row
        for row in harness_coverage["rows"]
    }
    swe_zstd_harness = harness_rows[
        ("swe-marathon", "zstd-decoder", "arms.treatment")
    ]
    assert swe_zstd_harness["loopx_cli_call_count"] == 31, swe_zstd_harness
    assert swe_zstd_harness["lifecycle_observed"] is True, swe_zstd_harness
    terminal_nginx_harness = harness_rows[
        ("terminal-bench@2.0", "nginx-request-logging", "arms.treatment")
    ]
    assert terminal_nginx_harness["source_kind"] == "case_arm", (
        terminal_nginx_harness
    )
    assert terminal_nginx_harness["loopx_cli_call_count"] == 0, (
        terminal_nginx_harness
    )
    skillsbench_native_harness = harness_rows[
        (
            "skillsbench@1.1",
            "llm-prefix-cache-replay",
            "native_goal_route_observations",
        )
    ]
    assert skillsbench_native_harness["controller_trace_present"] is True, (
        skillsbench_native_harness
    )
    debug_trajectory_harness = harness_rows[
        ("skillsbench@1.1", "debug-trl-grpo", "trajectory_public_summary")
    ]
    assert debug_trajectory_harness["tool_call_count"] == 112, (
        debug_trajectory_harness
    )
    assert debug_trajectory_harness["private_trajectory_present"] is True, (
        debug_trajectory_harness
    )
    by_case = {(case["benchmark_id"], case["case_id"]): case for case in cases}
    terminal_coverage = payload["terminal_bench_current_protocol_coverage"]
    assert terminal_coverage["schema_version"] == (
        "terminal_bench_current_protocol_coverage_v0"
    ), terminal_coverage
    assert terminal_coverage["latest_decision_filter"] == (
        "paired_baseline_solved_treatment_preserved"
    ), terminal_coverage
    expected_terminal_cases = {
        case_id
        for case_id, case in ledger["benchmarks"]["terminal-bench@2.0"][
            "cases"
        ].items()
        if (case.get("latest_decision") or {}).get("decision")
        == "paired_baseline_solved_treatment_preserved"
    }
    coverage_by_case = {
        row["case_id"]: row for row in terminal_coverage["rows"]
    }
    assert set(coverage_by_case) == expected_terminal_cases, coverage_by_case
    for case_id, row in coverage_by_case.items():
        latest = ledger["benchmarks"]["terminal-bench@2.0"]["cases"][case_id][
            "latest_decision"
        ]
        assert row["baseline_run_id"] == latest["baseline_run_id"], row
        assert row["treatment_run_id"] == latest["treatment_run_id"], row
        assert row["decision"] == "paired_baseline_solved_treatment_preserved", row
        assert row["baseline_official_score"] == 1, row
        assert row["treatment_official_score"] == 1, row
        assert row["official_score_delta"] == 0.0, row
        assert row["claimable_uplift"] is False, row
        assert row["main_table_role"] == (
            "current_protocol_baseline_solved_non_regression_guard"
        ), row
    uplift = by_case[("terminal-bench@2.0", "multi-source-data-merger")]
    nginx_route_canary = by_case[("terminal-bench@2.0", "nginx-request-logging")]
    skillsbench_uplift = by_case[("skillsbench@1.1", "llm-prefix-cache-replay")]
    skillsbench_dapt_uplift = by_case[("skillsbench@1.1", "dapt-intrusion-detection")]
    paratransit_uplift = by_case[("skillsbench@1.1", "paratransit-routing")]
    regression = by_case[("skillsbench@1.1", "debug-trl-grpo")]
    civ6_neutral = by_case[("skillsbench@1.1", "civ6-adjacency-optimizer")]
    manufacturing_neutral = by_case[
        ("skillsbench@1.1", "manufacturing-codebook-normalization")
    ]
    software_neutral = by_case[("skillsbench@1.1", "software-dependency-audit")]
    react_neutral = by_case[("skillsbench@1.1", "react-performance-debugging")]
    pddl_neutral = by_case[("skillsbench@1.1", "pddl-airport-planning")]
    make_doom_timeout = by_case[("terminal-bench@2.0", "make-doom-for-mips")]
    mteb_setup_probe = by_case[("terminal-bench@2.0", "mteb-retrieve")]
    pytorch_exception = by_case[("terminal-bench@2.0", "pytorch-model-recovery")]
    ada_success = by_case[("skillsbench@1.1", "ada-bathroom-plan-repair")]
    organize_success = by_case[("skillsbench@1.1", "organize-messy-files")]
    citation_success = by_case[("skillsbench@1.1", "citation-check")]
    scan_success = by_case[("skillsbench@1.1", "3d-scan-calc")]
    bike_success = by_case[("skillsbench@1.1", "bike-rebalance")]
    adaptive_setup = by_case[("skillsbench@1.1", "adaptive-cruise-control")]
    swe_zstd_regression = by_case[("swe-marathon", "zstd-decoder")]

    assert uplift["classification"] == (
        "baseline_solved_non_regression_asset"
    ), uplift
    assert uplift["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), uplift
    assert uplift["scores"]["official_score_delta"] == 0.0, uplift
    assert uplift["scores"]["claimable_uplift"] is False, uplift
    current_protocol = uplift["current_protocol_recheck"]
    assert current_protocol["schema_version"] == (
        "terminal_bench_current_protocol_recheck_v0"
    ), current_protocol
    assert current_protocol["baseline_route"] == "hardened-codex", current_protocol
    assert current_protocol["loopx_route"] == (
        "loopx-managed-codex"
    ), current_protocol
    assert current_protocol["baseline_official_score"] == 1, current_protocol
    assert current_protocol["treatment_official_score"] == 1, current_protocol
    assert current_protocol["official_score_delta"] == 0, current_protocol
    assert current_protocol["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), current_protocol
    assert uplift["arms"]["baseline"]["run_id"] == "37d3587daf12", uplift
    assert uplift["arms"]["treatment"]["run_id"] == "76cbfb57f1ea", uplift
    legacy_uplift = uplift["legacy_positive_result"]
    assert_compact_legacy_result(legacy_uplift)
    assert legacy_uplift["classification"] == "positive_uplift_asset", legacy_uplift
    assert legacy_uplift["decision"] == "paired_treatment_improved", legacy_uplift
    assert legacy_uplift["scores"]["official_score_delta"] == 1.0, legacy_uplift
    assert nginx_route_canary["classification"] == (
        "baseline_solved_non_regression_asset"
    ), (
        nginx_route_canary
    )
    assert nginx_route_canary["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), nginx_route_canary
    assert nginx_route_canary["scores"]["official_score_delta"] == 0, (
        nginx_route_canary
    )
    assert nginx_route_canary["scores"]["claimable_uplift"] is False, (
        nginx_route_canary
    )
    assert nginx_route_canary["arms"]["baseline"]["run_id"] == "c9e583310242", (
        nginx_route_canary
    )
    assert nginx_route_canary["arms"]["treatment"]["run_id"] == "2a6a46cfb953", (
        nginx_route_canary
    )
    assert nginx_route_canary["arms"]["baseline"]["failure_scope"] == "passed", (
        nginx_route_canary
    )
    assert nginx_route_canary["arms"]["treatment"]["failure_scope"] == "passed", (
        nginx_route_canary
    )
    legacy_nginx = nginx_route_canary["legacy_runner_materialization_asset"]
    assert legacy_nginx["classification"] == "runner_materialization_asset", (
        legacy_nginx
    )
    assert legacy_nginx["decision"] == (
        "paired_baseline_runner_or_setup_repair_required"
    ), legacy_nginx
    assert legacy_nginx["scores"]["official_score_delta"] == 1.0, legacy_nginx
    assert legacy_nginx["arms"]["baseline"]["run_id"] == "890f0a8487e4", (
        legacy_nginx
    )
    assert legacy_nginx["arms"]["baseline"]["failure_scope"] == (
        "runner_or_setup"
    ), legacy_nginx
    assert legacy_nginx["compact_lifecycle_analysis"][
        "baseline_case_attempt_countable"
    ] is False, legacy_nginx
    assert legacy_nginx["compact_lifecycle_analysis"][
        "claimable_uplift"
    ] is False, legacy_nginx
    assert nginx_route_canary["arms"]["treatment"][
        "worker_loopx_cli_call_total"
    ] == 0, nginx_route_canary
    nginx_probe = legacy_nginx["worker_materialization_probe"]
    assert nginx_probe["run_id"] == "51fa05316d18", nginx_probe
    assert nginx_probe["failure_class"] == "codex_cli_not_on_path", nginx_probe
    assert nginx_probe["case_solution_attempted"] is False, nginx_probe
    assert nginx_probe["benchmark_budget_countable"] is False, nginx_probe
    assert legacy_nginx["compact_lifecycle_analysis"][
        "baseline_repair_probe_failure"
    ] == "codex_cli_not_on_path", legacy_nginx
    assert nginx_route_canary["routing_guidance"]["repeat_policy"] == (
        "repeat_only_after_worker_setup_or_managed_route_policy_change"
    ), nginx_route_canary
    assert skillsbench_uplift["classification"] == (
        "reward_feedback_positive_blind_loop_neutral_asset"
    ), skillsbench_uplift
    assert skillsbench_uplift["decision"] == (
        "reward_feedback_positive_primary_blind_loop_no_uplift"
    ), skillsbench_uplift
    assert skillsbench_uplift["scores"]["official_score_delta"] == 0.0, skillsbench_uplift
    assert skillsbench_uplift["scores"]["claimable_uplift"] is False, skillsbench_uplift
    legacy_reward_uplift = skillsbench_uplift["legacy_reward_feedback_result"]
    assert_compact_legacy_result(legacy_reward_uplift)
    assert legacy_reward_uplift["scores"]["official_score_delta"] == 1.0, (
        legacy_reward_uplift
    )
    assert legacy_reward_uplift["arms"]["treatment"]["failure_scope"] == "passed", (
        legacy_reward_uplift
    )
    blind_recheck = skillsbench_uplift["blind_loop_recheck"]
    assert blind_recheck["decision"] == "paired_no_score_uplift", blind_recheck
    assert blind_recheck["official_score_delta"] == 0.0, blind_recheck
    assert blind_recheck["reward_feedback_forwarded"] is False, blind_recheck
    assert blind_recheck["official_feedback_blinded"] is True, blind_recheck
    assert blind_recheck["first_success_round"] is None, blind_recheck
    max5_recheck = skillsbench_uplift["max5_blind_loop_recheck"]
    assert max5_recheck["decision"] == "paired_no_score_uplift", max5_recheck
    assert max5_recheck["max_rounds_budget"] == 5, max5_recheck
    assert max5_recheck["official_score_delta"] == 0.0, max5_recheck
    assert max5_recheck["reward_feedback_forwarded"] is False, max5_recheck
    assert max5_recheck["official_feedback_blinded"] is True, max5_recheck
    assert max5_recheck["first_success_round"] is None, max5_recheck
    assert max5_recheck["baseline_round_rewards"] == (
        "1:0,2:0,3:0,4:0,5:0"
    ), max5_recheck
    assert max5_recheck["treatment_round_rewards"] == (
        "1:0,2:0,3:0,4:0,5:0"
    ), max5_recheck
    assert skillsbench_dapt_uplift["classification"] == (
        "reward_feedback_positive_blind_loop_neutral_asset"
    ), skillsbench_dapt_uplift
    assert skillsbench_dapt_uplift["decision"] == (
        "reward_feedback_positive_primary_blind_loop_no_uplift"
    ), skillsbench_dapt_uplift
    assert skillsbench_dapt_uplift["scores"]["official_score_delta"] == 0.0, skillsbench_dapt_uplift
    assert skillsbench_dapt_uplift["scores"]["claimable_uplift"] is False, (
        skillsbench_dapt_uplift
    )
    legacy_dapt_uplift = skillsbench_dapt_uplift["legacy_reward_feedback_result"]
    assert_compact_legacy_result(legacy_dapt_uplift)
    assert legacy_dapt_uplift["scores"]["official_score_delta"] == 1.0, (
        legacy_dapt_uplift
    )
    assert legacy_dapt_uplift["decision"] == "paired_treatment_improved", (
        legacy_dapt_uplift
    )
    dapt_blind_recheck = skillsbench_dapt_uplift["blind_loop_recheck"]
    assert dapt_blind_recheck["decision"] == "paired_no_score_uplift", dapt_blind_recheck
    assert dapt_blind_recheck["official_score_delta"] == 0.0, dapt_blind_recheck
    assert dapt_blind_recheck["reward_feedback_forwarded"] is False, dapt_blind_recheck
    assert dapt_blind_recheck["official_feedback_blinded"] is True, dapt_blind_recheck
    assert dapt_blind_recheck["first_success_round"] is None, dapt_blind_recheck
    assert paratransit_uplift["classification"] == (
        "product_mode_invalid_shallow_loopx_asset"
    ), paratransit_uplift
    assert paratransit_uplift["decision"] == (
        "product_mode_treatment_invalid_shallow_loopx_lifecycle"
    ), paratransit_uplift
    assert paratransit_uplift["current_protocol_claim_status"] == (
        "product_mode_treatment_invalid_shallow_loopx_lifecycle"
    ), paratransit_uplift
    assert paratransit_uplift["evidence_status"] == (
        "compact_pair_complete_but_treatment_lifecycle_invalid"
    ), paratransit_uplift
    assert paratransit_uplift["scores"]["baseline_official_score"] == 0.0, (
        paratransit_uplift
    )
    assert paratransit_uplift["scores"]["treatment_official_score"] == 0.0, (
        paratransit_uplift
    )
    assert paratransit_uplift["scores"]["official_score_delta"] == 0.0, (
        paratransit_uplift
    )
    assert paratransit_uplift["scores"]["claimable_uplift"] is False, (
        paratransit_uplift
    )
    assert paratransit_uplift["scores"]["treatment_round_rewards"] == "1:0", (
        paratransit_uplift
    )
    assert paratransit_uplift["arms"]["treatment"]["loopx_cli_call_count"] == 1, (
        paratransit_uplift
    )
    assert paratransit_uplift["arms"]["treatment"]["agent_declared_done"] is True, (
        paratransit_uplift
    )
    assert paratransit_uplift["arms"]["treatment"]["reward_feedback_forwarded"] is False, (
        paratransit_uplift
    )
    assert paratransit_uplift["arms"]["treatment"]["official_feedback_blinded"] is True, (
        paratransit_uplift
    )
    product_recheck = paratransit_uplift["product_mode_recheck"]
    assert product_recheck["product_mode_pair_complete"] is False, product_recheck
    assert product_recheck["product_mode_treatment_valid"] is False, product_recheck
    assert product_recheck["invalid_reason"] == (
        "shallow_loopx_lifecycle_only_goal_discovery_no_state_read_write_or_replan"
    ), product_recheck
    depth_gate = paratransit_uplift["depth_gate_repair_result"]
    assert depth_gate["run_id"] == "c9e2eebe7a8e", depth_gate
    assert depth_gate["official_score"] == 1.0, depth_gate
    assert depth_gate["first_success_round"] == 5, depth_gate
    assert depth_gate["agent_declared_done"] is False, depth_gate
    legacy_paratransit = paratransit_uplift["legacy_blind_loop_positive_result"]
    assert_compact_legacy_result(legacy_paratransit)
    assert legacy_paratransit["classification"] == "positive_uplift_asset", (
        legacy_paratransit
    )
    assert legacy_paratransit["scores"]["official_score_delta"] == 1.0, (
        legacy_paratransit
    )
    assert legacy_paratransit["arms"]["treatment"]["last_decision"] == (
        "stop_after_blind_loop_official_success_observed_without_feedback"
    ), legacy_paratransit
    paratransit_trace = legacy_paratransit["trajectory_public_summary"]
    assert paratransit_trace["raw_text_copied_to_public"] is False, paratransit_trace
    assert paratransit_trace["round_count"] == 1, paratransit_trace
    assert paratransit_trace["tool_call_count"] == 16, paratransit_trace
    assert paratransit_trace["loopx_cli_call_count"] == 0, paratransit_trace
    assert paratransit_trace["loopx_cli_calls"] == [], paratransit_trace
    assert paratransit_trace["protected_path_edit_signal_count"] == 0, (
        paratransit_trace
    )
    assert bike_success["classification"] == (
        "baseline_solved_non_regression_asset"
    ), bike_success
    assert bike_success["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), bike_success
    assert bike_success["scores"]["baseline_official_score"] == 1.0, bike_success
    assert bike_success["scores"]["treatment_official_score"] == 1.0, bike_success
    assert bike_success["scores"]["official_score_delta"] == 0.0, bike_success
    assert bike_success["arms"]["baseline"]["failure_class"] == "none", bike_success
    assert bike_success["arms"]["baseline"]["repaired_from"]["failure_class"] == (
        "skillsbench_runner_error"
    ), bike_success
    assert adaptive_setup["classification"] == "setup_blocker_asset", (
        adaptive_setup
    )
    assert adaptive_setup["decision"] == (
        "baseline_runner_or_setup_repair_required"
    ), adaptive_setup
    assert adaptive_setup["scores"]["baseline_official_score"] is None, (
        adaptive_setup
    )
    assert adaptive_setup["arms"]["baseline"]["run_id"] == "235f52dc6a5b", (
        adaptive_setup
    )
    assert adaptive_setup["arms"]["baseline"]["failure_class"] == (
        "skillsbench_docker_compose_apt_repository_failure"
    ), adaptive_setup
    assert adaptive_setup["arms"]["baseline"]["task_staging"][
        "apt_retry_patch_applied"
    ] is True, adaptive_setup
    assert adaptive_setup["arms"]["baseline"]["task_staging"][
        "staged"
    ] is True, adaptive_setup
    assert adaptive_setup["arms"]["treatment"] is None, adaptive_setup
    assert adaptive_setup["routing_guidance"]["repeat_policy"] == (
        "use_fail_fast_preflight_or_material_setup_route_change_before_repeat"
    ), adaptive_setup
    assert any(
        "--fail-fast-on-apt-risk" in item
        for item in adaptive_setup["optimization_guidance"]
    ), adaptive_setup
    assert swe_zstd_regression["classification"] == (
        "extended_round_product_path_negative_asset"
    ), swe_zstd_regression
    assert swe_zstd_regression["evidence_status"] == (
        "compact_pair_complete_product_path_verified_extended_round"
    ), swe_zstd_regression
    assert swe_zstd_regression["decision"] == "paired_treatment_regressed", (
        swe_zstd_regression
    )
    assert swe_zstd_regression["scores"]["baseline_official_score"] == 1.0, (
        swe_zstd_regression
    )
    assert swe_zstd_regression["scores"]["treatment_official_score"] == 0.0, (
        swe_zstd_regression
    )
    assert swe_zstd_regression["scores"]["official_score_delta"] == -1.0, (
        swe_zstd_regression
    )
    assert swe_zstd_regression["scores"]["claimable_uplift"] is False, (
        swe_zstd_regression
    )
    assert swe_zstd_regression["arms"]["baseline"]["run_id"] == "9ae95dbf5ab4", (
        swe_zstd_regression
    )
    assert swe_zstd_regression["arms"]["treatment"]["run_id"] == "1e3c8703e24b", (
        swe_zstd_regression
    )
    assert swe_zstd_regression["arms"]["treatment"]["first_blocker"] == "none", (
        swe_zstd_regression
    )
    zstd_timeout = swe_zstd_regression["timeout_comparability"]
    assert zstd_timeout["baseline_wall_time_limit_seconds"] == 3600, (
        zstd_timeout
    )
    assert zstd_timeout["treatment_wall_time_limit_seconds"] == 900, (
        zstd_timeout
    )
    assert zstd_timeout["baseline_official_timeout_comparable"] is False, (
        zstd_timeout
    )
    assert zstd_timeout["treatment_official_timeout_comparable"] is False, (
        zstd_timeout
    )
    assert zstd_timeout["treatment_max_round_observed"] == 5, zstd_timeout
    assert zstd_timeout["treatment_followup_prompt_count"] == 4, zstd_timeout
    assert zstd_timeout["timeout_causality_claim"] == (
        "earlier_900s_one_round_timeout_confound_superseded_by_pr467_extended_round_negative"
    ), zstd_timeout
    zstd_product_path = swe_zstd_regression["product_path_validation"]
    assert zstd_product_path["treatment_loopx_inside_case"] is True, (
        zstd_product_path
    )
    assert zstd_product_path["treatment_loopx_cli_call_count"] == 31, (
        zstd_product_path
    )
    assert zstd_product_path["treatment_controller_max_round_observed"] == 5, (
        zstd_product_path
    )
    assert zstd_product_path["treatment_controller_followup_prompt_count"] == 4, (
        zstd_product_path
    )
    assert zstd_product_path["treatment_worker_bridge_materialization_status"] == (
        "verified"
    ), zstd_product_path
    zstd_superseded = swe_zstd_regression["superseded_observations"]
    assert zstd_superseded[0]["run_id"] == "1252c5786080", zstd_superseded
    assert zstd_superseded[0]["classification"] == (
        "timeout_confounded_product_path_negative_asset"
    ), zstd_superseded
    assert zstd_superseded[1]["run_id"] == "e0a2cb412ee9", zstd_superseded
    assert zstd_superseded[1]["classification"] == (
        "worker_or_driver_blocker"
    ), zstd_superseded
    bike_blind_recheck = bike_success["blind_loop_recheck"]
    assert bike_blind_recheck["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), bike_blind_recheck
    assert bike_blind_recheck["baseline_official_score"] == 1.0, bike_blind_recheck
    assert bike_blind_recheck["treatment_official_score"] == 1.0, bike_blind_recheck
    assert bike_blind_recheck["official_score_delta"] == 0.0, bike_blind_recheck
    assert bike_blind_recheck["baseline_round_rewards"] == "1:1", bike_blind_recheck
    assert bike_blind_recheck["treatment_round_rewards"] == "1:1", (
        bike_blind_recheck
    )
    assert bike_blind_recheck["first_success_round"] == 1, bike_blind_recheck
    assert bike_blind_recheck["reward_feedback_forwarded"] is False, (
        bike_blind_recheck
    )
    assert bike_blind_recheck["official_feedback_blinded"] is True, (
        bike_blind_recheck
    )
    assert regression["classification"] == "regression_asset", regression
    assert regression["scores"]["official_score_delta"] == -0.25, regression
    assert regression["scores"]["baseline_best_round_score"] == 0.25, regression
    assert regression["scores"]["treatment_best_round_score"] == 0.25, regression
    assert regression["scores"]["best_round_score_delta"] == 0.0, regression
    assert regression["scores"]["final_round_score_delta"] == -0.25, regression
    assert regression["scores"]["score_policy_for_loop_analysis"] == (
        "best_round_score"
    ), regression
    debug_blind_recheck = regression["blind_loop_recheck"]
    assert debug_blind_recheck["decision"] == "paired_treatment_regressed", debug_blind_recheck
    assert debug_blind_recheck["official_score_delta"] == -0.25, debug_blind_recheck
    assert debug_blind_recheck["baseline_official_score"] == 0.25, debug_blind_recheck
    assert debug_blind_recheck["treatment_official_score"] == 0.0, debug_blind_recheck
    assert debug_blind_recheck["baseline_round_rewards"] == "1:0.25,2:0.25", debug_blind_recheck
    assert debug_blind_recheck["treatment_round_rewards"] == "1:0.25,2:0", debug_blind_recheck
    assert debug_blind_recheck["reward_feedback_forwarded"] is False, debug_blind_recheck
    assert debug_blind_recheck["official_feedback_blinded"] is True, debug_blind_recheck
    assert debug_blind_recheck["first_success_round"] is None, debug_blind_recheck
    debug_max5_recheck = regression["max5_blind_loop_recheck"]
    assert debug_max5_recheck["decision"] == "paired_treatment_regressed", (
        debug_max5_recheck
    )
    assert debug_max5_recheck["run_group_id"] == (
        "skillsbench-debug-trl-grpo-blind-loop-max5-20260616T144124CST"
    ), debug_max5_recheck
    assert debug_max5_recheck["max_rounds_budget"] == 5, debug_max5_recheck
    assert debug_max5_recheck["baseline_official_score"] == 0.25, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["treatment_official_score"] == 0.0, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["official_score_delta"] == -0.25, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["baseline_best_round_score"] == 0.25, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["treatment_best_round_score"] == 0.25, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["best_round_score_delta"] == 0.0, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["final_round_score_delta"] == -0.25, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["baseline_round_rewards"] == (
        "1:0.25,2:0.25,3:0.25,4:0.25,5:0.25"
    ), debug_max5_recheck
    assert debug_max5_recheck["treatment_round_rewards"] == (
        "1:0.25,2:0.25,3:0,4:0,5:0"
    ), debug_max5_recheck
    assert debug_max5_recheck["reward_feedback_forwarded"] is False, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["official_feedback_blinded"] is True, (
        debug_max5_recheck
    )
    assert debug_max5_recheck["first_success_round"] is None, debug_max5_recheck
    debug_trace = regression["trajectory_public_summary"]
    assert debug_trace["raw_text_copied_to_public"] is False, debug_trace
    assert debug_trace["round_count"] == 5, debug_trace
    assert debug_trace["tool_call_count"] == 112, debug_trace
    assert debug_trace["loopx_cli_call_count"] == 0, debug_trace
    assert debug_trace["loopx_cli_calls"] == [], debug_trace
    assert debug_trace["protected_path_mentions"] == [
        "/app/reward_fn.py",
        "/app/train_grpo.py",
    ], debug_trace
    assert debug_trace["protected_path_edit_rounds"] == {
        "/app/train_grpo.py": [3, 4]
    }, debug_trace
    assert "round 1 contained protected paths" in debug_trace[
        "continuation_constraint_projection_gap"
    ], debug_trace
    assert "re-project the durable round-1 controller contract" in debug_trace[
        "controller_repair"
    ], debug_trace
    debug_prompt_ablation = regression["baseline_safe_prompt_ablation"]
    assert debug_prompt_ablation["treatment_prompt_style"] == (
        "baseline-safe"
    ), debug_prompt_ablation
    assert debug_prompt_ablation["treatment_run_id"] == "f37b0a3e9654", debug_prompt_ablation
    assert debug_prompt_ablation["official_score"] == 0.25, debug_prompt_ablation
    assert debug_prompt_ablation["round_rewards"] == (
        "1:0.25,2:0.25"
    ), debug_prompt_ablation
    assert debug_prompt_ablation["official_score_delta_vs_baseline"] == (
        0.0
    ), debug_prompt_ablation
    assert debug_prompt_ablation[
        "official_score_delta_vs_structured_treatment"
    ] == 0.25, debug_prompt_ablation
    assert debug_prompt_ablation["reward_feedback_forwarded"] is False, (
        debug_prompt_ablation
    )
    assert debug_prompt_ablation["official_feedback_blinded"] is True, (
        debug_prompt_ablation
    )
    assert civ6_neutral["classification"] == "no_uplift_asset", civ6_neutral
    assert civ6_neutral["scores"]["official_score_delta"] == 0.0, civ6_neutral
    civ6_blind_recheck = civ6_neutral["blind_loop_recheck"]
    assert civ6_blind_recheck["decision"] == "paired_no_score_uplift", civ6_blind_recheck
    assert civ6_blind_recheck["official_score_delta"] == 0.0, civ6_blind_recheck
    assert civ6_blind_recheck["baseline_round_rewards"] == "1:0,2:0", civ6_blind_recheck
    assert civ6_blind_recheck["treatment_round_rewards"] == "1:0,2:0", civ6_blind_recheck
    assert civ6_blind_recheck["reward_feedback_forwarded"] is False, civ6_blind_recheck
    assert civ6_blind_recheck["official_feedback_blinded"] is True, civ6_blind_recheck
    assert civ6_blind_recheck["first_success_round"] is None, civ6_blind_recheck
    assert manufacturing_neutral["classification"] == "no_uplift_asset", manufacturing_neutral
    assert manufacturing_neutral["scores"]["official_score_delta"] == 0.0, manufacturing_neutral
    manufacturing_blind_recheck = manufacturing_neutral["blind_loop_recheck"]
    assert manufacturing_blind_recheck["decision"] == (
        "paired_no_score_uplift"
    ), manufacturing_blind_recheck
    assert manufacturing_blind_recheck["official_score_delta"] == 0.0, manufacturing_blind_recheck
    assert manufacturing_blind_recheck["baseline_round_rewards"] == "1:0,2:0", manufacturing_blind_recheck
    assert manufacturing_blind_recheck["treatment_round_rewards"] == "1:0,2:0", manufacturing_blind_recheck
    assert manufacturing_blind_recheck["reward_feedback_forwarded"] is False, manufacturing_blind_recheck
    assert manufacturing_blind_recheck["official_feedback_blinded"] is True, manufacturing_blind_recheck
    assert manufacturing_blind_recheck["first_success_round"] is None, manufacturing_blind_recheck
    assert software_neutral["classification"] == "no_uplift_asset", software_neutral
    assert software_neutral["scores"]["official_score_delta"] == 0.0, software_neutral
    software_blind_recheck = software_neutral["blind_loop_recheck"]
    assert software_blind_recheck["decision"] == "paired_no_score_uplift", software_blind_recheck
    assert software_blind_recheck["official_score_delta"] == 0.0, software_blind_recheck
    assert software_blind_recheck["baseline_round_rewards"] == "1:0,2:0", software_blind_recheck
    assert software_blind_recheck["treatment_round_rewards"] == "1:0,2:0", software_blind_recheck
    assert software_blind_recheck["reward_feedback_forwarded"] is False, software_blind_recheck
    assert software_blind_recheck["official_feedback_blinded"] is True, software_blind_recheck
    assert software_blind_recheck["first_success_round"] is None, software_blind_recheck
    assert react_neutral["classification"] == "no_uplift_asset", react_neutral
    assert react_neutral["scores"]["official_score_delta"] == 0.0, react_neutral
    react_blind_recheck = react_neutral["blind_loop_recheck"]
    assert react_blind_recheck["decision"] == "paired_no_score_uplift", react_blind_recheck
    assert react_blind_recheck["official_score_delta"] == 0.0, react_blind_recheck
    assert react_blind_recheck["baseline_round_rewards"] == "1:0,2:0", react_blind_recheck
    assert react_blind_recheck["treatment_round_rewards"] == "1:0,2:0", react_blind_recheck
    assert react_blind_recheck["baseline_run_id"] == "851ca794f780", react_blind_recheck
    assert react_blind_recheck["treatment_run_id"] == "8efed51d81e5", react_blind_recheck
    assert react_blind_recheck["reward_feedback_forwarded"] is False, react_blind_recheck
    assert react_blind_recheck["official_feedback_blinded"] is True, react_blind_recheck
    assert react_blind_recheck["first_success_round"] is None, react_blind_recheck
    assert pddl_neutral["classification"] == "no_uplift_asset", pddl_neutral
    assert pddl_neutral["scores"]["official_score_delta"] == 0.0, pddl_neutral
    pddl_blind_recheck = pddl_neutral["blind_loop_recheck"]
    assert pddl_blind_recheck["decision"] == "paired_no_score_uplift", pddl_blind_recheck
    assert pddl_blind_recheck["official_score_delta"] == 0.0, pddl_blind_recheck
    assert pddl_blind_recheck["baseline_round_rewards"] == "1:0,2:0", pddl_blind_recheck
    assert pddl_blind_recheck["treatment_round_rewards"] == "1:0,2:0", pddl_blind_recheck
    assert pddl_blind_recheck["baseline_run_id"] == "adf46f67374c", pddl_blind_recheck
    assert pddl_blind_recheck["treatment_run_id"] == "1564d6cfc2fb", pddl_blind_recheck
    assert pddl_blind_recheck["reward_feedback_forwarded"] is False, pddl_blind_recheck
    assert pddl_blind_recheck["official_feedback_blinded"] is True, pddl_blind_recheck
    assert pddl_blind_recheck["first_success_round"] is None, pddl_blind_recheck
    assert make_doom_timeout["classification"] == "timeout_attribution_asset", make_doom_timeout
    assert make_doom_timeout["decision"] == "paired_result_requires_attribution", make_doom_timeout
    assert make_doom_timeout["scores"]["official_score_delta"] == 0.0, make_doom_timeout
    assert (
        make_doom_timeout["routing_guidance"]["repeat_policy"]
        == "do_not_repeat_until_phase_attribution_available"
    ), make_doom_timeout
    assert mteb_setup_probe["classification"] == "setup_probe_asset", (
        mteb_setup_probe
    )
    assert mteb_setup_probe["decision"] == (
        "environment_setup_probe_materialized_with_exception_repeat_blocked"
    ), mteb_setup_probe
    assert mteb_setup_probe["arms"]["baseline"]["run_id"] == (
        "f51ed0bc44ef"
    ), mteb_setup_probe
    assert mteb_setup_probe["arms"]["treatment"]["run_id"] == (
        "4dca7e651fac"
    ), mteb_setup_probe
    setup_probe = mteb_setup_probe["arms"]["setup_probe"]
    assert setup_probe["run_id"] == "b1c43dfaaa19", setup_probe
    assert setup_probe["worker_start_status"] == (
        "environment_setup_probe_materialized"
    ), setup_probe
    assert setup_probe["trial_result_present_count"] == 1, setup_probe
    assert setup_probe["artifact_manifest_present_count"] == 1, setup_probe
    assert setup_probe["exception_present"] is True, setup_probe
    assert setup_probe["probe_outcome"] == "materialized_with_exception", setup_probe
    assert setup_probe["repeat_blocked_by"] == (
        "environment_setup_probe_exception_requires_interpretation"
    ), setup_probe
    assert setup_probe["case_attempt_countable"] is False, setup_probe
    assert setup_probe["benchmark_budget_countable"] is False, setup_probe
    lifecycle = mteb_setup_probe["setup_probe_lifecycle"]
    assert lifecycle["current_phase"] == (
        "environment_setup_probe_completed"
    ), lifecycle
    assert lifecycle["next_required_transition"] == (
        "case_repeat_decision"
    ), lifecycle
    assert lifecycle["first_blocker"] == (
        "environment_setup_probe_exception_requires_interpretation"
    ), lifecycle
    assert lifecycle["probe_outcome"] == "materialized_with_exception", lifecycle
    assert lifecycle["repeat_allowed"] is False, lifecycle
    assert mteb_setup_probe["routing_guidance"]["repeat_policy"] == (
        "do_not_repeat_until_probe_exception_classified"
    ), mteb_setup_probe
    assert pytorch_exception["classification"] == (
        "exception_attribution_asset"
    ), pytorch_exception
    assert pytorch_exception["decision"] == (
        "paired_no_score_uplift_exception_research_required"
    ), pytorch_exception
    assert pytorch_exception["scores"]["official_score_delta"] == 0.0, (
        pytorch_exception
    )
    assert pytorch_exception["arms"]["baseline"]["run_id"] == (
        "2db3f1047704"
    ), pytorch_exception
    assert pytorch_exception["arms"]["treatment"]["run_id"] == (
        "9ba1b6872167"
    ), pytorch_exception
    assert pytorch_exception["arms"]["baseline"]["verifier_reward_present"] is (
        False
    ), pytorch_exception
    assert pytorch_exception["arms"]["treatment"][
        "worker_bridge_materialization_status"
    ] == "not_materialized", pytorch_exception
    compact_review = pytorch_exception["compact_attribution_review"]
    assert compact_review["baseline_attribution_class"] == (
        "agent_exception_score_failure"
    ), compact_review
    assert compact_review["requires_case_exception_research"] is True, (
        compact_review
    )
    assert compact_review["requires_finer_compact_attribution"] is False, (
        compact_review
    )
    assert compact_review["repeat_allowed"] is False, compact_review
    assert compact_review["blocked_action_scope"] == (
        "same_task_repeat_until_exception_hypothesis"
    ), compact_review
    assert ada_success["classification"] == (
        "baseline_solved_non_regression_asset"
    ), ada_success
    assert ada_success["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), ada_success
    assert ada_success["scores"]["baseline_official_score"] == 1.0, ada_success
    assert ada_success["scores"]["treatment_official_score"] == 1.0, ada_success
    assert ada_success["scores"]["official_score_delta"] == 0.0, ada_success
    assert ada_success["arms"]["baseline"]["run_id"] == "7d919631a765", ada_success
    assert ada_success["arms"]["treatment"]["run_id"] == "52a934d39c59", ada_success
    assert {
        attempt["failure_class"] for attempt in ada_success["historical_setup_blockers"]
    } == {
        "skillsbench_codex_acp_launch_failed",
        "skillsbench_codex_acp_binary_missing",
    }, ada_success
    ada_blind_recheck = ada_success["blind_loop_recheck"]
    assert ada_blind_recheck["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), ada_blind_recheck
    assert ada_blind_recheck["baseline_official_score"] == 1.0, ada_blind_recheck
    assert ada_blind_recheck["treatment_official_score"] == 1.0, ada_blind_recheck
    assert ada_blind_recheck["baseline_round_rewards"] == "1:1", ada_blind_recheck
    assert ada_blind_recheck["treatment_round_rewards"] == "1:1", ada_blind_recheck
    assert ada_blind_recheck["first_success_round"] == 1, ada_blind_recheck
    assert ada_blind_recheck["reward_feedback_forwarded"] is False, ada_blind_recheck
    assert ada_blind_recheck["official_feedback_blinded"] is True, ada_blind_recheck
    assert organize_success["classification"] == (
        "baseline_solved_non_regression_asset"
    ), organize_success
    assert organize_success["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), organize_success
    assert organize_success["scores"]["baseline_official_score"] == 1.0, organize_success
    assert organize_success["scores"]["treatment_official_score"] == 1.0, organize_success
    assert organize_success["scores"]["official_score_delta"] == 0.0, organize_success
    assert organize_success["arms"]["baseline"]["run_id"] == "f25208ace86a", organize_success
    assert organize_success["arms"]["treatment"]["run_id"] == "60878623ceca", organize_success
    assert organize_success["arms"]["treatment"]["treatment_prompt_style"] == (
        "baseline-safe"
    ), organize_success
    assert {
        attempt["failure_class"]
        for attempt in organize_success["historical_setup_blockers"]
    } == {"skillsbench_docker_compose_setup_failure"}, organize_success
    organize_blind_recheck = organize_success["blind_loop_recheck"]
    assert organize_blind_recheck["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), organize_blind_recheck
    assert organize_blind_recheck["baseline_official_score"] == 1.0, (
        organize_blind_recheck
    )
    assert organize_blind_recheck["treatment_official_score"] == 1.0, (
        organize_blind_recheck
    )
    assert organize_blind_recheck["baseline_round_rewards"] == "1:1", (
        organize_blind_recheck
    )
    assert organize_blind_recheck["treatment_round_rewards"] == "1:1", (
        organize_blind_recheck
    )
    assert organize_blind_recheck["first_success_round"] == 1, (
        organize_blind_recheck
    )
    assert organize_blind_recheck["reward_feedback_forwarded"] is False, (
        organize_blind_recheck
    )
    assert organize_blind_recheck["official_feedback_blinded"] is True, (
        organize_blind_recheck
    )
    assert organize_blind_recheck["treatment_prompt_style"] == "baseline-safe", (
        organize_blind_recheck
    )
    assert citation_success["classification"] == (
        "baseline_solved_non_regression_asset"
    ), citation_success
    assert citation_success["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), citation_success
    assert citation_success["scores"]["baseline_official_score"] == 1.0, (
        citation_success
    )
    assert citation_success["scores"]["treatment_official_score"] == 1.0, (
        citation_success
    )
    assert citation_success["scores"]["official_score_delta"] == 0.0, (
        citation_success
    )
    assert citation_success["arms"]["baseline"]["run_id"] == "9b4df14b3ed8", (
        citation_success
    )
    assert citation_success["arms"]["treatment"]["run_id"] == "d553e635f00c", (
        citation_success
    )
    assert citation_success["arms"]["treatment"]["treatment_prompt_style"] == (
        "baseline-safe"
    ), citation_success
    assert {
        attempt["failure_class"]
        for attempt in citation_success["historical_setup_blockers"]
    } == {"skillsbench_environment_app_mount_missing"}, citation_success
    citation_blind_recheck = citation_success["blind_loop_recheck"]
    assert citation_blind_recheck["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), citation_blind_recheck
    assert citation_blind_recheck["baseline_official_score"] == 1.0, (
        citation_blind_recheck
    )
    assert citation_blind_recheck["treatment_official_score"] == 1.0, (
        citation_blind_recheck
    )
    assert citation_blind_recheck["baseline_round_rewards"] == "1:1", (
        citation_blind_recheck
    )
    assert citation_blind_recheck["treatment_round_rewards"] == "1:1", (
        citation_blind_recheck
    )
    assert citation_blind_recheck["first_success_round"] == 1, (
        citation_blind_recheck
    )
    assert citation_blind_recheck["reward_feedback_forwarded"] is False, (
        citation_blind_recheck
    )
    assert citation_blind_recheck["official_feedback_blinded"] is True, (
        citation_blind_recheck
    )
    assert citation_blind_recheck["treatment_prompt_style"] == "baseline-safe", (
        citation_blind_recheck
    )
    assert scan_success["classification"] == (
        "baseline_solved_non_regression_asset"
    ), scan_success
    assert scan_success["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), scan_success
    assert scan_success["scores"]["baseline_official_score"] == 1.0, (
        scan_success
    )
    assert scan_success["scores"]["treatment_official_score"] == 1.0, (
        scan_success
    )
    assert scan_success["scores"]["official_score_delta"] == 0.0, scan_success
    assert scan_success["arms"]["baseline"]["run_id"] == "9b1d8be29eb4", (
        scan_success
    )
    assert scan_success["arms"]["treatment"]["run_id"] == "306537fca3ac", (
        scan_success
    )
    assert scan_success["arms"]["treatment"]["treatment_prompt_style"] == (
        "baseline-safe"
    ), scan_success
    assert scan_success["historical_setup_blockers"] == [], scan_success
    scan_blind_recheck = scan_success["blind_loop_recheck"]
    assert scan_blind_recheck["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), scan_blind_recheck
    assert scan_blind_recheck["baseline_official_score"] == 1.0, (
        scan_blind_recheck
    )
    assert scan_blind_recheck["treatment_official_score"] == 1.0, (
        scan_blind_recheck
    )
    assert scan_blind_recheck["baseline_round_rewards"] == "1:1", (
        scan_blind_recheck
    )
    assert scan_blind_recheck["treatment_round_rewards"] == "1:1", (
        scan_blind_recheck
    )
    assert scan_blind_recheck["first_success_round"] == 1, scan_blind_recheck
    assert scan_blind_recheck["reward_feedback_forwarded"] is False, (
        scan_blind_recheck
    )
    assert scan_blind_recheck["official_feedback_blinded"] is True, (
        scan_blind_recheck
    )
    assert scan_blind_recheck["treatment_prompt_style"] == "baseline-safe", (
        scan_blind_recheck
    )

    controls = payload["treatment_policy_controls"]
    assert controls["control_set_id"] == "skillsbench_automation_loop_policy_controls_20260615", controls
    positive_control_ids = {case["case_id"] for case in controls["positive_controls"]}
    regression_control_ids = {case["case_id"] for case in controls["regression_controls"]}
    neutral_control_ids = {case["case_id"] for case in controls["neutral_controls"]}
    success_control_ids = {case["case_id"] for case in controls["success_controls"]}
    assert {"llm-prefix-cache-replay", "dapt-intrusion-detection"} <= positive_control_ids, controls
    assert "debug-trl-grpo" in regression_control_ids, controls
    assert "civ6-adjacency-optimizer" in neutral_control_ids, controls
    assert "manufacturing-codebook-normalization" in neutral_control_ids, controls
    assert "software-dependency-audit" in neutral_control_ids, controls
    assert "react-performance-debugging" in neutral_control_ids, controls
    assert "pddl-airport-planning" in neutral_control_ids, controls
    assert "ada-bathroom-plan-repair" in success_control_ids, controls
    assert "organize-messy-files" in success_control_ids, controls
    assert "citation-check" in success_control_ids, controls
    assert "3d-scan-calc" in success_control_ids, controls
    assert "route-wide improvement" in controls["policy_gate"]["claim_rule"], controls
    interaction = controls["interaction_count_assessment"]
    assert interaction["conclusion"] == (
        "existing_uplift_is_reward_feedback_evidence_not_blind_control_plane_evidence"
    ), interaction
    assert interaction["baseline_route"] == "codex_goal_mode_baseline", interaction
    route_audit = interaction["baseline_route_semantics_audit"]
    assert route_audit["current_recorded_runs_native_goal_mode_confirmed"] is False, route_audit
    assert route_audit["legacy_arm_name"] == "codex_goal_mode_baseline", route_audit
    assert "codex-acp" in route_audit["observed_current_run_semantics"], route_audit
    assert "interactive Codex CLI slash-command goal state" in route_audit[
        "required_future_baseline_semantics"
    ], route_audit
    assert "native_goal_mode_requested" in route_audit["runner_contract_fix"], route_audit
    reward_payload = interaction["reward_feedback_payload"]
    assert reward_payload["default_verifier_output_tail_chars_after_fix"] == 0, reward_payload
    assert "ablation" in reward_payload["classification_after_protocol_revision"], reward_payload
    assert reward_payload["fields_forwarded_after_failed_reward"] == [
        "previous_reward",
        "previous_verifier_error",
        "previous_tool_calls",
    ], reward_payload
    blind_protocol = interaction["primary_comparison_protocol"]
    assert blind_protocol["baseline_route"] == "raw-codex-autonomous-max5", blind_protocol
    assert blind_protocol["treatment_route"] == "loopx-product-mode", blind_protocol
    assert "LoopX product-mode" in blind_protocol["inner_case_actor"], blind_protocol
    assert blind_protocol["headline_metrics"] == [
        "best_score",
        "final_score",
        "first_success_round",
        "declared_done_score",
    ], blind_protocol
    assert "do not return official reward" in blind_protocol["feedback_policy"], blind_protocol
    assert "previous_reward" in blind_protocol["forbidden_agent_signals"], blind_protocol
    assert "official_feedback_blinded=true" in controls["policy_gate"]["blind_loop_rule"], controls
    assert interaction["baseline_controller_interactions"] == 0, interaction
    assert "reward-feedback ablation" in interaction["treatment_controller_pattern"], interaction
    prompt_ablation = {
        case["case_id"]: case for case in interaction["prompt_ablation_results"]
    }
    assert prompt_ablation["debug-trl-grpo"]["treatment_prompt_style"] == (
        "baseline-safe"
    ), prompt_ablation
    assert prompt_ablation["debug-trl-grpo"]["official_score"] == 0.25, (
        prompt_ablation
    )
    assert prompt_ablation["debug-trl-grpo"]["round_rewards"] == (
        "1:0.25,2:0.25"
    ), prompt_ablation
    blind_rechecks = interaction["blind_loop_rechecks"]
    blind_recheck_ids = {case["case_id"] for case in blind_rechecks}
    assert {
        "llm-prefix-cache-replay",
        "dapt-intrusion-detection",
        "debug-trl-grpo",
        "civ6-adjacency-optimizer",
        "manufacturing-codebook-normalization",
        "software-dependency-audit",
        "react-performance-debugging",
        "pddl-airport-planning",
        "ada-bathroom-plan-repair",
        "organize-messy-files",
        "citation-check",
        "3d-scan-calc",
        "bike-rebalance",
    } <= blind_recheck_ids, blind_rechecks
    by_blind_recheck = {case["case_id"]: case for case in blind_rechecks}
    assert by_blind_recheck["llm-prefix-cache-replay"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["dapt-intrusion-detection"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["debug-trl-grpo"]["decision"] == (
        "paired_treatment_regressed"
    ), blind_rechecks
    assert by_blind_recheck["civ6-adjacency-optimizer"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["manufacturing-codebook-normalization"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["software-dependency-audit"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["react-performance-debugging"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["pddl-airport-planning"]["decision"] == (
        "paired_no_score_uplift"
    ), blind_rechecks
    assert by_blind_recheck["ada-bathroom-plan-repair"]["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), blind_rechecks
    assert by_blind_recheck["ada-bathroom-plan-repair"][
        "first_success_round"
    ] == 1, blind_rechecks
    assert by_blind_recheck["organize-messy-files"]["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), blind_rechecks
    assert by_blind_recheck["organize-messy-files"][
        "first_success_round"
    ] == 1, blind_rechecks
    assert by_blind_recheck["organize-messy-files"][
        "treatment_prompt_style"
    ] == "baseline-safe", blind_rechecks
    assert by_blind_recheck["citation-check"]["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), blind_rechecks
    assert by_blind_recheck["citation-check"]["first_success_round"] == 1, (
        blind_rechecks
    )
    assert by_blind_recheck["citation-check"]["treatment_prompt_style"] == (
        "baseline-safe"
    ), blind_rechecks
    assert by_blind_recheck["3d-scan-calc"]["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), blind_rechecks
    assert by_blind_recheck["3d-scan-calc"]["first_success_round"] == 1, (
        blind_rechecks
    )
    assert by_blind_recheck["3d-scan-calc"]["treatment_prompt_style"] == (
        "baseline-safe"
    ), blind_rechecks
    assert by_blind_recheck["bike-rebalance"]["decision"] == (
        "paired_baseline_solved_treatment_preserved"
    ), blind_rechecks
    assert by_blind_recheck["bike-rebalance"]["treatment_official_score"] == 1.0, (
        blind_rechecks
    )
    assert by_blind_recheck["bike-rebalance"]["baseline_official_score"] == 1.0, (
        blind_rechecks
    )
    assert by_blind_recheck["bike-rebalance"]["official_score_delta"] == 0.0, (
        blind_rechecks
    )
    assert by_blind_recheck["bike-rebalance"]["first_success_round"] == 1, (
        blind_rechecks
    )
    assert "no longer support" in interaction["blind_loop_recheck_conclusion"], interaction
    assert "debug-trl-grpo" in interaction["blind_loop_recheck_conclusion"], interaction
    assert "civ6-adjacency-optimizer" in interaction["blind_loop_recheck_conclusion"], interaction
    assert "manufacturing-codebook-normalization" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "software-dependency-audit" in interaction["blind_loop_recheck_conclusion"], interaction
    assert "react-performance-debugging" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "pddl-airport-planning" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "ada-bathroom-plan-repair" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "organize-messy-files" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "citation-check" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "3d-scan-calc" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "bike-rebalance" in interaction[
        "blind_loop_recheck_conclusion"
    ], interaction
    assert "ada-bathroom-plan-repair" in {
        case["case_id"] for case in interaction["success_controls"]
    }, interaction
    assert "organize-messy-files" in {
        case["case_id"] for case in interaction["success_controls"]
    }, interaction
    assert "citation-check" in {
        case["case_id"] for case in interaction["success_controls"]
    }, interaction
    assert "3d-scan-calc" in {
        case["case_id"] for case in interaction["success_controls"]
    }, interaction
    assert "bike-rebalance" in {
        case["case_id"] for case in interaction["success_controls"]
    }, interaction
    assert "bike-rebalance" in {
        case["case_id"] for case in controls["success_controls"]
    }, controls
    assert "bike-rebalance" not in {
        case["case_id"] for case in controls["runner_repair_controls"]
    }, controls
    assert interaction["loopx_inside_case"] is False, interaction
    assert "debug-trl-grpo" in {
        case["case_id"] for case in interaction["negative_and_neutral_controls"]
    }, interaction
    debug_policy_recheck = next(
        case
        for case in interaction["blind_loop_rechecks"]
        if case["case_id"] == "debug-trl-grpo"
    )
    debug_policy_max5 = debug_policy_recheck["max5_recheck"]
    assert debug_policy_max5["max_rounds_budget"] == 5, debug_policy_max5
    assert debug_policy_max5["baseline_round_rewards"] == (
        "1:0.25,2:0.25,3:0.25,4:0.25,5:0.25"
    ), debug_policy_max5
    assert debug_policy_max5["treatment_round_rewards"] == (
        "1:0.25,2:0.25,3:0,4:0,5:0"
    ), debug_policy_max5

    assert_public_safe(json.dumps(payload, sort_keys=True))


def test_case_analysis_markdown() -> None:
    text = ANALYSIS_MD.read_text(encoding="utf-8")
    assert "multi-source-data-merger" in text, text
    assert "llm-prefix-cache-replay" in text, text
    assert "dapt-intrusion-detection" in text, text
    assert "debug-trl-grpo" in text, text
    assert "zstd-decoder" in text, text
    assert "extended round product path negative asset" in text, text
    assert "Product-path verification does not prove causal regression" in text, text
    assert "31 LoopX CLI calls" in text, text
    assert "make-doom-for-mips" in text, text
    assert "pytorch-model-recovery" in text, text
    assert "agent_exception_score_failure" in text, text
    assert "ada-bathroom-plan-repair" in text, text
    assert "organize-messy-files" in text, text
    assert "citation-check" in text, text
    assert "3d-scan-calc" in text, text
    assert "bike-rebalance" in text, text
    assert "manufacturing-codebook-normalization" in text, text
    assert "civ6-adjacency-optimizer" in text, text
    assert "software-dependency-audit" in text, text
    assert "react-performance-debugging" in text, text
    assert "pddl-airport-planning" in text, text
    assert "timeout attribution asset" in text, text
    assert "exception attribution asset" in text, text
    assert "baseline-solved non-regression asset" in text, text
    assert "skillsbench_codex_acp_launch_failed" in text, text
    assert "skillsbench_codex_acp_binary_missing" in text, text
    assert "positive-control" in text, text
    assert "negative-control" in text, text
    assert "Treatment Policy Control Set" in text, text
    assert "Terminal-Bench Current-Protocol Coverage" in text, text
    assert "Public Trajectory Summary Coverage" in text, text
    assert "trajectory_public_summary_coverage_v0" in text, text
    assert "Public Harness Interaction Coverage" in text, text
    assert "harness_interaction_public_summary_coverage_v0" in text, text
    assert "`swe-marathon` | `zstd-decoder` | `arms.treatment`" in text, text
    assert "`terminal-bench@2.0` | `nginx-request-logging` | `arms.treatment`" in text, text
    assert "native_goal_route_observations" in text, text
    assert "legacy_blind_loop_positive_result.trajectory_public_summary" in text, text
    assert "post_stop_policy_raw_rerun.trajectory_public_summary" in text, text
    assert "`citation-check` | `post_stop_policy_raw_rerun.trajectory_public_summary`" in text, text
    assert "historical_final_only_lifecycle_trajectory_summaries" in text, text
    assert "`3d-scan-calc` | `historical_final_only_lifecycle_trajectory_summaries.treatment.trajectory_public_summary`" in text, text
    assert "`debug-trl-grpo` | `trajectory_public_summary`" in text, text
    assert "current-protocol success-preservation guards" in text, text
    assert "cobol-modernization" in text, text
    assert "git-multibranch" in text, text
    assert "large-scale-text-editing" in text, text
    assert "regex-log" in text, text
    assert "current_protocol_baseline_solved_non_regression_guard" in text, text
    assert "protected files" in text, text
    assert "Interaction-count assessment" in text, text
    assert "codex_goal_mode_baseline" in text, text
    assert "legacy arm name" in text, text
    assert "native `/goal` baseline" in text, text
    assert "native_goal_mode_requested" in text, text
    assert "native_goal_mode_invoked" in text, text
    assert "ACP prompt text" in text and "not sufficient confirmation" in text, text
    assert "private verifier output tail can leak" in text, text
    assert "reward-feedback ablation" in text, text
    assert "codex-acp-blind-loop-baseline" in text, text
    assert "loopx-blind-loop-treatment" in text, text
    assert "official_feedback_blinded=true" in text, text
    assert "two controller decisions" in text, text
    assert "not explained by interaction count alone" in text, text
    assert "protocol v10" in text and "paired_no_score_uplift" in text, text
    assert "max-5 rerun" in text and "1:0,2:0,3:0,4:0,5:0" in text, text
    assert "reward feedback positive blind loop neutral asset" in text, text
    assert "protocol v0" in text and "first_success_round=null" in text, text
    assert "blind-loop regression" in text, text
    assert "1:0.25,2:0.25" in text and "1:0.25,2:0" in text, text
    assert "skillsbench-debug-trl-grpo-blind-loop-max5-20260616T144124CST" in text, text
    assert "1:0.25,2:0.25,3:0.25,4:0.25,5:0.25" in text, text
    assert "1:0.25,2:0.25,3:0,4:0,5:0" in text, text
    assert "continuation-risk diagnosis" in text, text
    assert "baseline-safe treatment prompt v0" in text, text
    assert "recovered to baseline partial credit" in text, text
    assert "blind-loop neutral" in text, text
    assert "civ6-adjacency-optimizer` protocol v0" in text, text
    assert "manufacturing-codebook-normalization` protocol v0" in text, text
    assert "software-dependency-audit` protocol v0" in text, text
    assert "react-performance-debugging` protocol v0" in text, text
    assert "pddl-airport-planning` protocol v0" in text, text
    assert "ada-bathroom-plan-repair` protocol" in text, text
    assert "organize-messy-files` protocol" in text, text
    assert "citation-check` protocol" in text, text
    assert "baseline-solved treatment non-regression guard" in text, text
    assert "bike-rebalance` also moved" in text, text
    assert "baseline-solved non-regression asset" in text, text
    assert "Baseline comparability must be repaired" in text, text
    assert "skillsbench_runner_error" in text, text
    assert "treatment first success round: `1`" in text, text
    assert "Docker compose setup blocker" in text, text
    assert "app-mount setup failures" in text, text
    assert "skillsbench_environment_app_mount_missing" in text, text
    assert "first_success_round=1" in text, text
    assert "rounds `1:0,2:0`" in text, text
    assert "reward-feedback-ablation" in text, text
    assert_public_safe(text)


if __name__ == "__main__":
    test_case_analysis_json()
    test_case_analysis_markdown()
    print("benchmark-case-analysis-smoke ok")
