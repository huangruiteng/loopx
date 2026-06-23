#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_LINES = 1000

# Keep this source-focused: docs and data can be intentionally long, while
# Python mega-files usually mean ownership and validation boundaries are blurry.
LEGACY_OVERSIZED_LIMITS = {
    "examples/benchmark-case-analysis-smoke.py": 1350,
    "examples/benchmark-run-ledger-smoke.py": 1600,
    "examples/codex-cli-long-run-benchmark-smoke.py": 1100,
    "examples/heartbeat-prompt-smoke.py": 1350,
    "examples/heartbeat-quota-flow-smoke.py": 1050,
    "examples/quota-plan-smoke.py": 2000,
    "examples/review-packet-cli-smoke.py": 1300,
    "examples/skillsbench-app-server-goal-worker-smoke.py": 1150,
    "examples/skillsbench-benchmark-run-smoke.py": 4900,
    "examples/status-markdown-smoke.py": 2250,
    "examples/terminal-bench-codex-loopx-active-cli-bridge-smoke.py": 1750,
    "examples/terminal-bench-harbor-runner-ingest-smoke.py": 2800,
    "examples/terminal-bench-private-runner-env-guard-smoke.py": 2550,
    "examples/work-lane-contract-smoke.py": 1400,
    "loopx/benchmark.py": 2900,
    "loopx/benchmark_adapters/agentissue.py": 2700,
    "loopx/benchmark_adapters/agents_last_exam.py": 4000,
    "loopx/benchmark_adapters/skillsbench.py": 3000,
    "loopx/benchmark_adapters/terminal_bench.py": 10100,
    "loopx/benchmark_case_analysis.py": 1300,
    "loopx/benchmark_ledger.py": 2300,
    "loopx/cli_commands/benchmark_review_lifecycle.py": 1300,
    "loopx/cli_commands/terminal_bench_environment_result.py": 1300,
    "loopx/codex_cli_probe.py": 3500,
    "loopx/history.py": 1500,
    "loopx/quota.py": 7500,
    "loopx/review_packet.py": 1250,
    "loopx/status.py": 8850,
    "loopx/terminal_bench_agent.py": 2100,
    "loopx/todos.py": 1300,
    "loopx/worker_bridge.py": 1600,
    "scripts/harbor_host_codex_goal_agent.py": 2150,
    "scripts/skillsbench_automation_loop.py": 4350,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def tracked_python_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    files = tracked_python_files()
    counts = {rel(path): line_count(path) for path in files}

    missing_budgets = sorted(set(LEGACY_OVERSIZED_LIMITS) - set(counts))
    require(not missing_budgets, f"line budgets reference missing files: {missing_budgets}")

    failures: list[str] = []
    for path, count in sorted(counts.items()):
        limit = LEGACY_OVERSIZED_LIMITS.get(path, DEFAULT_MAX_LINES)
        if count > limit:
            failures.append(
                f"{path} has {count} lines, above budget {limit}; "
                "split ownership before adding more code"
            )

    require(not failures, "repo Python line-budget violations:\n- " + "\n- ".join(failures))

    stale_budgets = [
        path for path in sorted(LEGACY_OVERSIZED_LIMITS) if counts[path] <= DEFAULT_MAX_LINES
    ]
    require(
        not stale_budgets,
        "remove legacy line-budget entries after shrink: "
        + ", ".join(stale_budgets),
    )

    print(
        "repo-python-line-budget-smoke: ok "
        f"({len(files)} tracked Python files, "
        f"default_max={DEFAULT_MAX_LINES}, legacy_budgets={len(LEGACY_OVERSIZED_LIMITS)})"
    )


if __name__ == "__main__":
    main()
