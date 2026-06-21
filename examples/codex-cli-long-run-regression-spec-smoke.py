#!/usr/bin/env python3
"""Smoke-test the Codex CLI long-run regression spec contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "codex-cli-long-run-regression.md"
)

REQUIRED_PHRASES = (
    "empty isolated `HOME`, runtime root, global registry, project registry, and active state fixture",
    "complete in `3-5` worker steps",
    "Run through the deterministic shim by default",
    "Real Codex CLI invocation is an explicit low-frequency mode",
    "Record a JSONL run log with one row per worker step",
    "`quota should-run` before work",
    "validated artifact or state writeback before `quota spend-slot`",
    "Do not depend on real session history",
    "Each worker step should do exactly one bounded transition",
    "Goal Tick Output Protocol",
    "`goal_tick_output_protocol_v0`",
    "`read_state`",
    "`propose_step`",
    "`execute`",
    "`validate`",
    "`critic`",
    "`writeback`",
    "Spend exactly one quota slot only after validation and writeback",
    "`step_index`",
    "`duration_ms`",
    "`should_run_before`",
    "`goal_tick_output_protocol`",
    "`writeback_event`",
    "`spend_event`",
    "Every completed work step has a validation result, writeback event, and one",
    "Every completed work step has all six Goal Tick phases with evidence",
    "No step spends when `should_run_before=false`",
    "deleting the worker process",
    "python3 examples/codex-cli-long-run-regression-runner-smoke.py",
    "running exactly `3` isolated worker steps",
    "`status`, `quota should-run`, `refresh-state`, and",
    "leaving a clear path for replacing the shim action with a real Codex CLI worker later",
    "The shim log also emits `goal_tick_output_protocol` for every row",
    "--worker-mode real-codex",
    "--codex-cli /path/to/codex",
    "codex exec --skip-git-repo-check --ephemeral --ignore-user-config",
    "--ignore-rules --sandbox workspace-write --ask-for-approval never",
    "The deterministic LoopX CLI shim remains the default public smoke",
    "The real-worker mode is opt-in",
    "starts from an empty isolated `HOME` and `CODEX_HOME`",
    "must not read real session history or Codex App thread state",
    "The real-worker mode must reuse the same pass criteria as the shim",
    "Goal Tick Output Protocol evidence",
    "the log should record the public-safe blocker",
    "public contract smoke does not call a real external Codex worker",
    "temporary fake executable",
    "python3 examples/codex-cli-long-run-real-worker-contract-smoke.py",
    "fixed session-history replay",
    "compact synthetic transcripts, not copies of real user sessions",
)

FORBIDDEN_PHRASES = (
    "internal-project-alpha",
    "internal-team-beta",
    "internal-product-gamma",
    "private-runtime-delta",
    "PRIVATE_HOME/",
    "~/.codex/sessions",
)


def main() -> int:
    text = SPEC.read_text(encoding="utf-8")
    compact = " ".join(text.split())
    for phrase in REQUIRED_PHRASES:
        assert phrase in compact, phrase
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, phrase
    assert text.count("## ") >= 6, text
    assert text.count("| `") >= 10, text
    print("codex-cli-long-run-regression-spec-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
