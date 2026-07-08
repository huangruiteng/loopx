#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    "examples/skillsbench-app-server-goal-worker-smoke.py": (
        "Split native app-server Goal lifecycle fixtures into focused launch, "
        "resume, and closeout smokes, then lower this pin again."
    ),
    "examples/skillsbench-benchmark-run-smoke.py": (
        "Extract SkillsBench ledger/reduce-only fixture groups into narrower "
        "smokes, then lower this pin again after the next stable split."
    ),
    "examples/terminal-bench-private-runner-env-guard-smoke.py": (
        "Split TerminalBench private-runner environment guard fixtures into "
        "focused setup, credential-boundary, and no-submit smoke helpers, then "
        "lower this pin again."
    ),
    "loopx/benchmark_adapters/skillsbench.py": (
        "Continue extracting SkillsBench discovery, counter, and reducer helpers "
        "into focused adapter modules, then lower this pin again."
    ),
    "loopx/benchmark_adapters/skillsbench_acp_relay.py": (
        "Split ACP relay bootstrap, app-server lifecycle, and reducer-facing "
        "status helpers into focused modules, then lower this pin again."
    ),
    "loopx/benchmark_adapters/terminal_bench.py": (
        "Continue extracting TerminalBench runner setup, private-source guards, "
        "and route attribution helpers into focused adapter modules, then lower "
        "this pin again."
    ),
    "scripts/skillsbench_automation_loop.py": (
        "Extract native app-server Goal/reduce-only closeout helpers into "
        "scripts or benchmark adapter modules, then lower this pin again."
    ),
}

LEGACY_OVERSIZED_LIMITS = {
    "examples/benchmark-run-ledger-smoke.py": 2106,
    "examples/skillsbench-app-server-goal-worker-smoke.py": 3119,
    "examples/skillsbench-benchmark-run-smoke.py": 14821,
    "examples/skillsbench-host-local-launch-plan-smoke.py": 2373,
    "examples/terminal-bench-harbor-runner-ingest-smoke.py": 2759,
    "examples/terminal-bench-private-runner-env-guard-smoke.py": 2619,
    "loopx/benchmark.py": 2875,
    "loopx/benchmark_adapters/agentissue.py": 2644,
    "loopx/benchmark_adapters/agents_last_exam.py": 3998,
    "loopx/benchmark_adapters/skillsbench.py": 5994,
    "examples/control_plane/work-lane-contract-smoke.py": 2244,
    "loopx/benchmark_adapters/skillsbench_acp_relay.py": 4005,
    "loopx/benchmark_adapters/terminal_bench.py": 10083,
    "loopx/benchmark_ledger.py": 3745,
    "loopx/presentation/sinks/lark/kanban.py": 2614,
    "loopx/codex_cli_probe.py": 2643,
    "loopx/quota.py": 2455,
    "loopx/status.py": 6926,
    "loopx/terminal_bench_agent.py": 2056,
    "scripts/harbor_host_codex_goal_agent.py": 2091,
    "scripts/skillsbench_automation_loop.py": 17631,
}

RETIREMENT_PLAN_REQUIRED_PATHS = {
    "examples/skillsbench-app-server-goal-worker-smoke.py",
    "examples/skillsbench-benchmark-run-smoke.py",
    "examples/terminal-bench-private-runner-env-guard-smoke.py",
    "loopx/benchmark_adapters/skillsbench.py",
    "loopx/benchmark_adapters/skillsbench_acp_relay.py",
    "loopx/benchmark_adapters/terminal_bench.py",
    "scripts/skillsbench_automation_loop.py",
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


def git_name_only(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def changed_python_paths() -> set[str]:
    changed = set()
    changed.update(git_name_only("diff", "--name-only", "origin/main...HEAD"))
    changed.update(git_name_only("diff", "--name-only"))
    changed.update(git_name_only("diff", "--cached", "--name-only"))
    return {path for path in changed if path.endswith(".py")}


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Python source line budgets.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on every over-budget tracked Python file instead of only changed files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = tracked_python_files()
    counts = {rel(path): line_count(path) for path in files}
    changed_paths = changed_python_paths()

    missing_budgets = sorted(set(LEGACY_OVERSIZED_LIMITS) - set(counts))
    require(not missing_budgets, f"line budgets reference missing files: {missing_budgets}")

    missing_retirement_plans = sorted(
        path
        for path, limit in LEGACY_OVERSIZED_LIMITS.items()
        if limit > DEFAULT_MAX_LINES
        and path in RETIREMENT_PLAN_REQUIRED_PATHS
        and not LEGACY_OVERSIZED_RETIREMENT_PLANS.get(path)
    )
    require(
        not missing_retirement_plans,
        "legacy line-budget increases require retirement plans: "
        + ", ".join(missing_retirement_plans),
    )

    all_failures: list[str] = []
    changed_failures: list[str] = []
    for path, count in sorted(counts.items()):
        limit = LEGACY_OVERSIZED_LIMITS.get(path, DEFAULT_MAX_LINES)
        if count > limit:
            message = (
                f"{path} has {count} lines, above budget {limit}; "
                "pause and consider a better module boundary before adding more code"
            )
            all_failures.append(message)
            if path in changed_paths:
                changed_failures.append(message)

    active_failures = all_failures if args.strict else changed_failures
    require(
        not active_failures,
        "repo Python line-budget violations:\n- " + "\n- ".join(active_failures),
    )

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
        f"default_max={DEFAULT_MAX_LINES}, legacy_budgets={len(LEGACY_OVERSIZED_LIMITS)}, "
        f"changed_python_files={len(changed_paths)}, "
        f"existing_over_budget={len(all_failures) - len(changed_failures)}, "
        f"strict={args.strict})"
    )


if __name__ == "__main__":
    main()
