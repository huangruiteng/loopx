#!/usr/bin/env python3
"""Smoke-test the Codex CLI long-run benchmark design contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN = REPO_ROOT / "docs" / "codex-cli-long-run-benchmark-design.md"

REQUIRED_PHRASES = (
    "mini_control_plane_repair_v0",
    "`3-5` worker steps",
    "`docs/authority.md` declares the accepted queue ordering contract",
    "`state/ACTIVE_GOAL_STATE.md` contains stale latest-run text",
    "`private/DO_NOT_READ.md` exists and is forbidden",
    "`src/control_plane.py` mis-sorts",
    "Move old completed todos into a `Completed Work Archive` section",
    "`artifacts/final_report.json`",
    "With Goal Harness",
    "Without Goal Harness",
    "`quota should-run` before work",
    "`refresh-state` after validated work",
    "`quota spend-slot` only after validation/writeback",
    "`scenario_id`",
    "`with_goal_harness` or `without_goal_harness`",
    "`benchmark_result_v0`",
    "`official_task_score`",
    "`control_plane_score`",
    "`harness_identity`",
    "`worker_surface`",
    "`forbidden_access_count`",
    "`stale_state_error_count`",
    "`open_todo_preserved`",
    "`archive_hygiene_passed`",
    "`queue_contract_passed`",
    "`trace_publicness`",
    "`failure_attribution_labels`",
    "`goal_tick_phase_coverage`",
    "`spend_before_validation_count`",
    "`state_reconstructable`",
    "Core v0 fields",
    "Candidate extensions, promoted only when needed",
    "Terminal-Bench 2.0 and Harbor remain the first official-runner probe",
    "SWE-Marathon is a later heavy SWE lane",
    "LongCLI-Bench contributes step-level stall",
    "WildClawBench motivates evaluating the model and harness as a pair",
    "Harness-1, agent libOS, natural-language harnesses, ASSERT, and ACS",
    "mini_control_plane_repair_with_interrupt_v0",
    "Simulate a worker kill after a partial Goal Tick writeback",
    "stale latest-run trap",
    "Force one validation failure",
    "human gate resume",
    "official-task and control-plane score split",
    "Which mode avoided stale latest-run traps?",
    "Did Goal Harness improve `control_plane_score`",
    "How much overhead did Goal Harness add in steps and wall time?",
    "default CI remains deterministic and uses fake or shim workers only",
    "real Codex CLI execution remains explicit and low-frequency",
    "python3 examples/codex-cli-long-run-benchmark-smoke.py",
    "`benchmark_comparison_v0`",
    "The with-harness path records Goal Tick",
    "The without-harness path performs the same public fixture repairs",
    "Do not benchmark against real user sessions or raw chat history",
)

FORBIDDEN_PHRASES = (
    "/Users/bytedance/",
    "agent-harness-side-bypass",
    "tiger-team",
    "premium-ui",
    "OpenViking",
)


def main() -> int:
    text = DESIGN.read_text(encoding="utf-8")
    compact = " ".join(text.split())
    for phrase in REQUIRED_PHRASES:
        assert phrase in compact, phrase
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, phrase
    assert text.count("## ") >= 8, text
    assert text.count("| `") >= 16, text
    print("codex-cli-long-run-benchmark-design-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
