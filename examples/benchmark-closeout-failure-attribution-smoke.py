#!/usr/bin/env python3
"""Smoke-test public-safe benchmark closeout failure attribution."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTION_JSON = (
    REPO_ROOT
    / "docs/research/long-horizon-agent-benchmarks/"
    / "benchmark-closeout-failure-attribution-20260620.json"
)
ATTRIBUTION_MD = (
    REPO_ROOT
    / "docs/research/long-horizon-agent-benchmarks/"
    / "benchmark-closeout-failure-attribution-20260620.md"
)


FORBIDDEN_MARKERS = [
    "/Users/",
    "/private/",
    "/home/",
    "/root/",
    ".local/private-benchmark-jobs",
    "BEGIN OPENSSH PRIVATE KEY",
    "OPENAI_API_KEY",
    # Keep active leak markers split in source so `loopx check` can
    # scan this public smoke while the runtime assertion still tests the full
    # forbidden marker in rendered artifacts.
    "Author" + "ization:",
    '"raw_task_text_copied": true',
    '"raw_logs_copied": true',
    '"raw_verifier_output_copied": true',
    '"raw_trajectory_copied": true',
    '"credential_material_copied": true',
    '"private_or_absolute_paths_copied": true',
]


def main() -> None:
    payload = json.loads(ATTRIBUTION_JSON.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "benchmark_closeout_failure_attribution_v0"
    assert payload["policy"]["closeout_requires_failure_attribution_before_rotation"]

    boundary = payload["public_boundary"]
    for key in [
        "raw_task_text_copied",
        "raw_logs_copied",
        "raw_verifier_output_copied",
        "raw_trajectory_copied",
        "credential_material_copied",
        "private_or_absolute_paths_copied",
    ]:
        assert boundary[key] is False, (key, boundary)

    cases = {
        (case["benchmark_id"], case["case_id"]): case
        for case in payload["case_attributions"]
    }
    case_entries = payload["case_attributions"]

    def find_case(
        benchmark_id: str,
        case_id: str,
        refined_attribution: str,
    ) -> dict[str, object]:
        for case in case_entries:
            if (
                case["benchmark_id"] == benchmark_id
                and case["case_id"] == case_id
                and case["refined_attribution"] == refined_attribution
            ):
                return case
        raise AssertionError((benchmark_id, case_id, refined_attribution))
    expected = {
        ("terminal-bench@2.0", "build-cython-ext"),
        ("terminal-bench@2.0", "multi-source-data-merger"),
        ("terminal-bench@2.0", "nginx-request-logging"),
        ("swe-marathon", "find-network-alignments"),
        ("swe-marathon", "rust-c-compiler"),
        ("skillsbench@1.1", "react-performance-debugging"),
        ("skillsbench@1.1", "llm-prefix-cache-replay"),
        ("skillsbench@1.1", "tictoc-unnecessary-abort-detection"),
    }
    assert expected <= set(cases), cases

    terminal = cases[("terminal-bench@2.0", "build-cython-ext")]
    assert terminal["native_codex_goal_evidence"] is True
    assert (
        terminal["refined_attribution"]
        == "official_zero_native_goal_regression_needs_phase_attribution"
    )
    assert terminal["run_ids"]["historical_passing_control"] == "53729101fea3"

    swe = cases[("swe-marathon", "find-network-alignments")]
    assert swe["native_codex_goal_evidence"] is True
    assert (
        swe["refined_attribution"]
        == "official_zero_native_goal_first_closeout_needs_solution_phase_counters"
    )

    terminal_pass = cases[("terminal-bench@2.0", "nginx-request-logging")]
    assert terminal_pass["native_codex_goal_evidence"] is True
    assert terminal_pass["official_passed"] is True
    assert (
        terminal_pass["refined_attribution"]
        == "native_goal_route_sanity_pass_current_protocol_control"
    )

    terminal_zero = cases[("terminal-bench@2.0", "multi-source-data-merger")]
    assert terminal_zero["native_codex_goal_evidence"] is True
    assert terminal_zero["official_passed"] is False
    assert (
        terminal_zero["refined_attribution"]
        == "official_zero_current_app_server_goal_baseline_needs_phase_or_treatment_comparison"
    )

    skills_native = cases[("skillsbench@1.1", "react-performance-debugging")]
    assert skills_native["native_codex_goal_evidence"] is True
    assert skills_native["ledger_failure_class"] == "skillsbench_runner_error"
    assert (
        skills_native["refined_attribution"]
        == "native_goal_worker_connected_trace_dir_missing_not_solver_quality_evidence"
    )

    skills_marker = find_case(
        "skillsbench@1.1",
        "llm-prefix-cache-replay",
        "native_goal_worker_marker_handoff_repaired_official_zero_needs_solution_phase_attribution",
    )
    assert skills_marker["native_codex_goal_evidence"] is True
    assert skills_marker["ledger_failure_class"] == "official_score_zero_case_failure"
    assert "marker route" in skills_marker["next_obligation"]

    for key in [
        ("skillsbench@1.1", "llm-prefix-cache-replay"),
        ("skillsbench@1.1", "tictoc-unnecessary-abort-detection"),
    ]:
        case = cases[key]
        assert case["native_codex_goal_evidence"] is False
        assert (
            case["refined_attribution"]
            == "paired_zero_acp_blind_loop_non_native_goal_no_uplift"
        )
        assert "native SkillsBench app-server Goal worker" in case["next_obligation"]

    decisions = {entry["route"]: entry for entry in payload["route_decisions"]}
    assert (
        decisions["skillsbench"]["decision"]
        == "native_marker_handoff_repaired_add_solution_phase_attribution"
    )

    rendered = json.dumps(payload, sort_keys=True) + "\n" + ATTRIBUTION_MD.read_text(
        encoding="utf-8"
    )
    leaks = [marker for marker in FORBIDDEN_MARKERS if marker in rendered]
    assert not leaks, leaks
    print("ok")


if __name__ == "__main__":
    main()
