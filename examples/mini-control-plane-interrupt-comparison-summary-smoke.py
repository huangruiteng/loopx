#!/usr/bin/env python3
"""Smoke-test a compact interrupt versus non-interrupt comparison summary."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SMOKE = REPO_ROOT / "examples" / "codex-cli-long-run-benchmark-smoke.py"
CONTRACT_DOC = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "mini-control-plane-interrupt-comparison-summary-v0.md"
)

SUMMARY_SCHEMA = "benchmark_interrupt_comparison_summary_v0"
FORBIDDEN_MARKERS = (
    "/" + "Users/",
    "/" + "tmp/",
    "".join(["OPEN", "AI", "_API", "_KEY"]),
    "".join(["ANTH", "ROPIC", "_API", "_KEY"]),
    "_".join(["raw", "thread"]),
    "_".join(["session", "history"]),
    "PRIVATE_MARKER_DO_NOT_COPY",
)


def load_benchmark_smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("codex_cli_long_run_benchmark_smoke", BENCHMARK_SMOKE)
    assert spec is not None and spec.loader is not None, BENCHMARK_SMOKE
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_MARKERS if marker in text]
    assert not leaked, leaked


def component_deltas(baseline: dict[str, Any], interrupt: dict[str, Any]) -> dict[str, float]:
    baseline_components = baseline["control_plane_score"]["components"]
    interrupt_components = interrupt["control_plane_score"]["components"]
    return {
        component: round(interrupt_components[component] - baseline_components[component], 3)
        for component in baseline["control_plane_score"]["component_order"]
    }


def comparison_summary(module: ModuleType, baseline: dict[str, Any], interrupt: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA,
        "task_family": module.TASK_ID,
        "mode_pair": [baseline["scenario_id"], interrupt["scenario_id"]],
        "baseline_task_id": baseline["task_id"],
        "interrupt_task_id": interrupt["task_id"],
        "official_task_score_delta": round(
            interrupt["official_task_score"]["value"] - baseline["official_task_score"]["value"], 3
        ),
        "official_scores": {
            baseline["scenario_id"]: baseline["official_task_score"],
            interrupt["scenario_id"]: interrupt["official_task_score"],
        },
        "control_plane_score_delta": round(
            interrupt["control_plane_score"]["value"] - baseline["control_plane_score"]["value"], 3
        ),
        "control_plane_scores": {
            baseline["scenario_id"]: baseline["control_plane_score"],
            interrupt["scenario_id"]: interrupt["control_plane_score"],
        },
        "control_plane_component_deltas": component_deltas(baseline, interrupt),
        "restart_resume_evidence": {
            "interrupt_events": interrupt["interrupt_events"],
            "resume_decision_applied_after_recheck": interrupt["resume_decision_applied_after_recheck"],
            "first_failed_phase": interrupt["first_failed_phase"],
            "side_effect_audit_passed": interrupt["side_effect_audit_passed"],
            "spend_after_validation_only": interrupt["spend_count"] == 1
            and interrupt["spend_before_validation_count"] == 0,
        },
        "failure_attribution": {
            "baseline_labels": baseline["failure_attribution_labels"],
            "interrupt_labels": interrupt["failure_attribution_labels"],
            "new_labels": sorted(
                set(interrupt["failure_attribution_labels"]) - set(baseline["failure_attribution_labels"])
            ),
        },
        "overhead": {
            "wall_time_ms_delta": round(interrupt["wall_time_ms"] - baseline["wall_time_ms"], 3),
            "writeback_delta": interrupt["writeback_count"] - baseline["writeback_count"],
            "spend_delta": interrupt["spend_count"] - baseline["spend_count"],
            "validation_fail_delta": interrupt["validation_fail_count"] - baseline["validation_fail_count"],
        },
        "claim_boundary": {
            "may_claim": [
                "local deterministic interrupt recovery was exercised",
                "official fixture score stayed unchanged under the interrupt slice",
                "failure attribution records validation pressure separately from task success",
            ],
            "must_not_claim": [
                "official benchmark or leaderboard uplift",
                "model-backed simulator benefit",
                "real Terminal-Bench or Harbor runner result",
            ],
        },
        "next_decision": {
            "decision": "keep_fixture_only_until_real_runner_or_operator_simulator_evidence_exists",
            "minimum_next_evidence": [
                "status_or_review_packet_projection_if_agents_need_this_summary",
                "real no-submit runner output only after explicit operator approval",
            ],
        },
    }


def assert_summary_contract(summary: dict[str, Any]) -> None:
    assert summary["schema_version"] == SUMMARY_SCHEMA, summary
    assert summary["mode_pair"] == ["with_loopx", "with_loopx_interrupt"], summary
    assert summary["baseline_task_id"] == "mini_control_plane_repair_v0", summary
    assert summary["interrupt_task_id"] == "mini_control_plane_repair_with_interrupt_v0", summary
    assert summary["official_task_score_delta"] == 0.0, summary
    assert summary["control_plane_score_delta"] <= 0.0, summary
    assert set(summary["restart_resume_evidence"]["interrupt_events"]) == {
        "worker_kill_after_partial_goal_tick_writeback",
        "stale_latest_run_trap",
        "forced_validation_failure_before_success",
        "human_gate_resume_after_state_policy_quota_authority_recheck",
    }, summary
    assert summary["restart_resume_evidence"]["resume_decision_applied_after_recheck"] is True, summary
    assert summary["restart_resume_evidence"]["first_failed_phase"] == "validate", summary
    assert summary["restart_resume_evidence"]["side_effect_audit_passed"] is True, summary
    assert summary["restart_resume_evidence"]["spend_after_validation_only"] is True, summary
    assert "validation" in summary["failure_attribution"]["new_labels"], summary
    assert summary["overhead"]["validation_fail_delta"] >= 1, summary
    assert summary["overhead"]["spend_delta"] < 0, summary
    assert "official benchmark or leaderboard uplift" in summary["claim_boundary"]["must_not_claim"], summary
    assert_public_safe(summary)


def assert_contract_doc() -> None:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    required = [
        SUMMARY_SCHEMA,
        "official_task_score_delta",
        "control_plane_score_delta",
        "restart_resume_evidence",
        "failure_attribution",
        "No real benchmark runner",
    ]
    missing = [item for item in required if item not in text]
    assert not missing, missing
    assert_public_safe({"contract": text})


def main() -> int:
    module = load_benchmark_smoke()
    with tempfile.TemporaryDirectory(prefix="mini-control-plane-interrupt-comparison-") as raw_tmp:
        root = Path(raw_tmp)
        baseline_fixture = module.write_fixture(root, "with_loopx")
        without_fixture = module.write_fixture(root, "without_loopx")
        interrupt_fixture = module.write_fixture(root, "with_loopx_interrupt")
        baseline, baseline_rows = module.run_harness_scenario(baseline_fixture)
        without = module.run_without_harness_scenario(without_fixture)
        interrupt, interrupt_rows = module.run_interrupt_harness_scenario(interrupt_fixture)
        module.assert_result_contract([baseline, without], baseline_rows, module.comparison([baseline, without]))
        module.assert_interrupt_contract(interrupt, interrupt_rows)
        summary = comparison_summary(module, baseline, interrupt)

    assert_summary_contract(summary)
    assert_contract_doc()
    print(
        "mini-control-plane-interrupt-comparison-summary-smoke ok "
        f"official_delta={summary['official_task_score_delta']} "
        f"control_delta={summary['control_plane_score_delta']} "
        f"events={len(summary['restart_resume_evidence']['interrupt_events'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
