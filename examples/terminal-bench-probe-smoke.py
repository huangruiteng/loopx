#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench runner-boundary probe note."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTE = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "terminal-bench-probe-v0.md"
)
README = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "README.md"
)

REQUIRED_SNIPPETS = [
    "Terminal-Bench Probe V0",
    "Terminal-Bench public repository",
    "1a6ffa9674b571da0ed040c470cb40c4d85f9b9b",
    "Harbor public repository",
    "8cfac6ad91c5c566ff14040cc4acbfe94ad42356",
    "redacted authority context",
    "--agent-import-path",
    "built-in `codex`",
    "Codex CLI",
    "ATIF",
    "trajectory.json",
    "lock.json",
    "result.json",
    "results.json",
    "tb.lock",
    "run_metadata.json",
    "benchmark_run_v0",
    "terminal_bench_probe_v0_codex_builtin",
    "terminal_bench_probe_v0_goal_harness_wrapper",
    "Do not run these automatically in a heartbeat.",
    "Stop before any of the following",
    "paid model execution",
    "official leaderboard submission",
]

FORBIDDEN_SNIPPETS = [
    "/" + "Users/",
    "/" + "tmp/",
    "lark" + "office",
    "fei" + "shu.cn",
    "wiki" + "_node_token",
    "document" + "_id",
    "doc" + "_url",
    "wiki" + "_url",
]


def main() -> None:
    text = NOTE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    assert not missing, missing

    leaked = [snippet for snippet in FORBIDDEN_SNIPPETS if snippet in text]
    assert not leaked, leaked

    assert "terminal-bench-probe-v0.md" in readme
    assert text.count("```bash") == 3
    assert text.count("harbor run") >= 2
    assert text.count("tb run") >= 1
    print("terminal-bench-probe-smoke ok")


if __name__ == "__main__":
    main()
