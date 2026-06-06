#!/usr/bin/env python3
"""Smoke-test the Codex CLI long-run regression spec contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = REPO_ROOT / "docs" / "codex-cli-long-run-regression.md"

REQUIRED_PHRASES = (
    "empty isolated `HOME`, runtime root, global registry, project registry, and active state fixture",
    "complete in `3-5` worker steps",
    "does not invoke Codex CLI yet",
    "Record a JSONL run log with one row per worker step",
    "`quota should-run` before work",
    "validated artifact or state writeback before `quota spend-slot`",
    "Do not depend on real session history",
    "Each worker step should do exactly one bounded transition",
    "Spend exactly one quota slot only after validation and writeback",
    "`step_index`",
    "`duration_ms`",
    "`should_run_before`",
    "`writeback_event`",
    "`spend_event`",
    "Every completed work step has a validation result, writeback event, and one",
    "No step spends when `should_run_before=false`",
    "deleting the worker process",
    "python3 examples/codex-cli-long-run-regression-runner-smoke.py",
    "running exactly `3` isolated worker steps",
    "`status`, `quota should-run`, `refresh-state`, and",
    "leaving a clear path for replacing the shim action with a real Codex CLI worker later",
    "The next implementation stage should add an explicit, low-frequency runner mode",
    "The deterministic Goal Harness CLI shim remains the default public smoke",
    "The real-worker mode should be opt-in",
    "should not read real session history or Codex App thread state",
    "The real-worker mode must reuse the same pass criteria as the shim",
    "the log should record the public-safe blocker",
    "fixed session-history replay",
    "compact synthetic transcripts, not copies of real user sessions",
)

FORBIDDEN_PHRASES = (
    "agent-harness-side-bypass",
    "tiger-team",
    "premium-ui",
    "OpenViking",
    "/Users/bytedance/",
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
