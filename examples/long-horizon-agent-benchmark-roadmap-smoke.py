#!/usr/bin/env python3
"""Smoke-test the long-horizon benchmark roadmap contract."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP = REPO_ROOT / "docs" / "long-horizon-agent-benchmark-roadmap.md"


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
    "Codex-adapter baseline availability",
    "Tau-Style User-Simulator Research Track",
    "tau-bench / tau2-bench / tau3-bench",
    "not as the primary long-horizon leaderboard target",
    "https://arxiv.org/abs/2406.12045",
    "https://github.com/sierra-research/tau2-bench",
    "https://arxiv.org/abs/2601.11868",
    "user-simulator",
    "same-family simulator and agent",
    "stronger simulator with weaker agent",
    "weaker simulator with stronger agent",
    "`benchmark_run_v0`",
    "Goal Tick phases",
    "with-harness and without-harness modes",
    "benchmark selection dossier",
    "Official Long-Horizon Engineering Pilot",
    "Publication Readiness",
    "Do not alter benchmark scoring",
]


def main() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert text.count("- [ ]") >= 5
    print("long-horizon-agent-benchmark-roadmap-smoke ok")


if __name__ == "__main__":
    main()
