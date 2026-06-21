#!/usr/bin/env python3
"""Smoke-test the long-horizon benchmark roadmap contract."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
ROADMAP = TOPIC_DIR / "roadmap.md"


REQUIRED_SNIPPETS = [
    "Primary: Long-Horizon Engineering Leaderboards",
    "paper-and-runner dossier",
    "SOTA long-horizon agent papers",
    "open-source and runnable from a clean checkout",
    "Initial paper and benchmark scan",
    "Terminal-Bench 2.0",
    "SWE-Marathon",
    "LongCLI-Bench",
    "RoadmapBench",
    "WildClawBench",
    "HORIZON",
    "Codex CLI",
    "Codex goal-mode baseline failures",
    "Tau-Style Simulator Research Track",
    "tau-bench / tau2-bench / tau3-bench",
    "not as the primary long-horizon leaderboard target",
    "https://arxiv.org/abs/2406.12045",
    "https://github.com/sierra-research/tau2-bench",
    "https://arxiv.org/abs/2601.11868",
    "LoopX Operator Simulator Program",
    "Official leaderboard mode",
    "Passive control-plane mode",
    "helps without any operator simulator",
    "Assisted operator-simulator mode",
    "operator simulator must not act as an oracle",
    "intervention budget",
    "Passive Baseline Hypotheses",
    "H1: Restartability",
    "H2: Stale-state avoidance",
    "H3: Continuation quality",
    "Passive LoopX Baseline",
    "Codex CLI goal mode without LoopX state",
    "No operator-simulator intervention",
    "Autonomous Planning Triggers",
    "Periodic research review",
    "No-progress streak",
    "Repeated-action loop",
    "Backlog mismatch",
    "Planning-Trigger Regression",
    "split it",
    "same-family simulator and agent",
    "stronger simulator with weaker agent",
    "weaker simulator with stronger agent",
    "`benchmark_run_v0`",
    "Goal Tick phases",
    "native, passive control-plane, and assisted operator-simulator modes",
    "benchmark selection dossier",
    "Official Long-Horizon Engineering Pilot",
    "Operator-Simulator Overlay Pilot",
    "Publication Readiness",
    "Do not alter benchmark scoring",
]


def main() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "This topic folder owns LoopX research" in readme
    assert "Do not implement LoopX product capability here." in readme
    assert "Foundational capability" in readme
    assert "existing code, examples, and contract documents" in readme
    assert "`roadmap.md`" in readme

    text = ROADMAP.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert text.count("- [ ]") >= 5
    print("long-horizon-agent-benchmark-roadmap-smoke ok")


if __name__ == "__main__":
    main()
