#!/usr/bin/env python3
"""Smoke-test the long-horizon paper and runner dossier."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOSSIER = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "paper-runner-dossier.md"
)


REQUIRED_SNIPPETS = [
    "Use Terminal-Bench 2.0 as the first official-runner probe",
    "first heavy long-horizon software-engineering probe",
    "Terminal-Bench 2.0",
    "SWE-Marathon",
    "LongCLI-Bench",
    "WildClawBench",
    "HORIZON / METR-style signals",
    "RoadmapBench",
    "SWE-EVO",
    "ALE-Bench",
    "OSWorld / WebArena / TheAgentCompany",
    "RALPHBench",
    "LongDS-Bench",
    "Tau-style suites",
    "Codex CLI",
    "Simple Codex",
    "terminal_bench_official_pilot_decision_packet_v0",
    "First Official-Pilot Decision Packet",
    "Every official-task result should be paired with a compact `benchmark_run_v0` event",
    "benchmark_result_v0",
    "Do not start SWE-Marathon until the",
    "Terminal-Bench wrapper boundary is known.",
    "terminal_bench_probe_v0",
    "https://epoch.ai/benchmarks/terminal-bench/",
    "https://arxiv.org/abs/2601.11868",
    "https://www.tbench.ai/leaderboard/terminal-bench/2.0",
    "https://github.com/harbor-framework/terminal-bench",
    "https://github.com/abundant-ai/swe-marathon",
    "https://huggingface.co/datasets/rdesai2/swe-marathon",
    "https://arxiv.org/abs/2602.14337",
    "https://arxiv.org/abs/2605.10912",
    "https://arxiv.org/abs/2604.11978",
    "https://horizonbench.org/",
    "https://arxiv.org/abs/2605.30434",
    "https://arxiv.org/abs/2605.15846",
    "https://github.com/SWE-EVO/SWE-EVO",
    "https://github.com/SakanaAI/ALE-Bench",
    "https://os-world.github.io/",
    "https://github.com/web-arena-x/webarena",
    "https://openreview.net/pdf?id=LZnKNApvhG",
    "https://www.ralphbench.org/",
]


def main() -> None:
    text = DOSSIER.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert text.count("|") >= 20
    assert text.count("Sources:") >= 3
    print("long-horizon-paper-runner-dossier-smoke ok")


if __name__ == "__main__":
    main()
