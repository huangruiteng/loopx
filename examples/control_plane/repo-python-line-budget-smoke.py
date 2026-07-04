#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAX_LINES = 2000

# Keep this source-focused: docs and data can be intentionally long, while
# Python mega-files usually mean ownership and validation boundaries are blurry.
# Existing oversized files are pinned to their current line count. When this
# smoke fails, first split ownership or extract a module; only raise a legacy
# budget with an explicit follow-up plan for retiring that whitelist entry.
LEGACY_OVERSIZED_RETIREMENT_PLANS = {
    "examples/skillsbench-benchmark-run-smoke.py": (
        "Extract SkillsBench ledger/reduce-only fixture groups into narrower "
        "smokes, then lower this pin again after the next stable split."
    ),
    "loopx/benchmark_adapters/skillsbench.py": (
        "Continue extracting SkillsBench discovery, counter, and reducer helpers "
        "into focused adapter modules, then lower this pin again."
    ),
    "scripts/skillsbench_automation_loop.py": (
        "Extract native app-server Goal/reduce-only closeout helpers into "
        "scripts or benchmark adapter modules, then lower this pin again."
    ),
}

LEGACY_OVERSIZED_LIMITS = {
    "examples/benchmark-run-ledger-smoke.py": 2106,
    "examples/control_plane/quota-plan-smoke.py": 2176,
    "examples/skillsbench-app-server-goal-worker-smoke.py": 3056,
    "examples/skillsbench-benchmark-run-smoke.py": 14430,
    "examples/skillsbench-host-local-launch-plan-smoke.py": 2373,
    "examples/control_plane/status-markdown-smoke.py": 2607,
    "examples/terminal-bench-harbor-runner-ingest-smoke.py": 2759,
    "examples/terminal-bench-private-runner-env-guard-smoke.py": 2585,
    "loopx/benchmark.py": 2875,
    "loopx/benchmark_adapters/agentissue.py": 2644,
    "loopx/benchmark_adapters/agents_last_exam.py": 3998,
    "loopx/benchmark_adapters/skillsbench.py": 5817,
    "examples/control_plane/work-lane-contract-smoke.py": 2336,
    "loopx/benchmark_adapters/skillsbench_acp_relay.py": 3144,
    "loopx/benchmark_adapters/terminal_bench.py": 10045,
    "loopx/benchmark_ledger.py": 3745,
    "loopx/capabilities/content_ops/surface.py": 2549,
    "loopx/capabilities/lark/kanban.py": 3034,
    "loopx/codex_cli_probe.py": 3546,
    "loopx/quota.py": 10628,
    "loopx/status.py": 11758,
    "loopx/terminal_bench_agent.py": 2056,
    "loopx/todos.py": 2105,
    "scripts/harbor_host_codex_goal_agent.py": 2140,
    "scripts/skillsbench_automation_loop.py": 16682,
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
    return [path for line in result.stdout.splitlines() if line and (path := ROOT / line).exists()]


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    files = tracked_python_files()
    counts = {rel(path): line_count(path) for path in files}

    missing_budgets = sorted(set(LEGACY_OVERSIZED_LIMITS) - set(counts))
    require(not missing_budgets, f"line budgets reference missing files: {missing_budgets}")

    missing_retirement_plans = sorted(
        path
        for path, limit in LEGACY_OVERSIZED_LIMITS.items()
        if limit > DEFAULT_MAX_LINES
        and path in {
            "examples/skillsbench-benchmark-run-smoke.py",
            "loopx/benchmark_adapters/skillsbench.py",
            "scripts/skillsbench_automation_loop.py",
        }
        and not LEGACY_OVERSIZED_RETIREMENT_PLANS.get(path)
    )
    require(
        not missing_retirement_plans,
        "legacy line-budget increases require retirement plans: "
        + ", ".join(missing_retirement_plans),
    )

    failures: list[str] = []
    for path, count in sorted(counts.items()):
        limit = LEGACY_OVERSIZED_LIMITS.get(path, DEFAULT_MAX_LINES)
        if count > limit:
            failures.append(
                f"{path} has {count} lines, above budget {limit}; "
                "pause and consider a better module boundary before adding more code"
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
