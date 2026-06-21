#!/usr/bin/env python3
"""Smoke-test the interrupt/recovery slice for mini_control_plane_repair_v0."""

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
    / "mini-control-plane-repair-with-interrupt-v0.md"
)

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


def assert_contract_doc() -> None:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    required = [
        "mini_control_plane_repair_with_interrupt_v0",
        "worker_kill_after_partial_goal_tick_writeback",
        "stale_latest_run_trap",
        "forced_validation_failure_before_success",
        "human_gate_resume_after_state_policy_quota_authority_recheck",
        "official_task_score",
        "control_plane_score",
        "side_effect_audit_passed",
        "No real benchmark runner",
    ]
    missing = [item for item in required if item not in text]
    assert not missing, missing
    assert_public_safe({"contract": text})


def report_slice(result: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "mini_control_plane_repair_with_interrupt_v0",
        "task_id": result["task_id"],
        "scenario_id": result["scenario_id"],
        "official_task_score": result["official_task_score"],
        "control_plane_score": result["control_plane_score"],
        "interrupt_events": result["interrupt_events"],
        "first_failed_phase": result["first_failed_phase"],
        "stall_step_index": result["stall_step_index"],
        "resume_decision_applied_after_recheck": result["resume_decision_applied_after_recheck"],
        "side_effect_audit_passed": result["side_effect_audit_passed"],
        "failure_attribution_labels": result["failure_attribution_labels"],
        "spend_count": result["spend_count"],
        "spend_before_validation_count": result["spend_before_validation_count"],
        "goal_tick_phase_coverage": result["goal_tick_phase_coverage"],
        "row_count": len(rows),
    }


def main() -> int:
    module = load_benchmark_smoke()
    with tempfile.TemporaryDirectory(prefix="mini-control-plane-interrupt-") as raw_tmp:
        fixture = module.write_fixture(Path(raw_tmp), "with_loopx_interrupt")
        result, rows = module.run_interrupt_harness_scenario(fixture)
        module.assert_interrupt_contract(result, rows)
        compact = report_slice(result, rows)

    expected_events = {
        "worker_kill_after_partial_goal_tick_writeback",
        "stale_latest_run_trap",
        "forced_validation_failure_before_success",
        "human_gate_resume_after_state_policy_quota_authority_recheck",
    }
    assert set(compact["interrupt_events"]) == expected_events, compact
    assert compact["official_task_score"]["value"] == 1.0, compact
    assert compact["control_plane_score"]["schema_version"] == "control_plane_score_core_v0", compact
    assert compact["resume_decision_applied_after_recheck"] is True, compact
    assert compact["side_effect_audit_passed"] is True, compact
    assert compact["spend_count"] == 1, compact
    assert compact["spend_before_validation_count"] == 0, compact
    assert compact["first_failed_phase"] == "validate", compact
    assert "validation" in compact["failure_attribution_labels"], compact
    assert compact["row_count"] == 2, compact
    assert_public_safe(compact)
    assert_contract_doc()
    print(
        "mini-control-plane-repair-with-interrupt-smoke ok "
        f"events={len(compact['interrupt_events'])} spend={compact['spend_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
