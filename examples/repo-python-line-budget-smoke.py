#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_LINES = 1000

# Keep this source-focused: docs and data can be intentionally long, while
# Python mega-files usually mean ownership and validation boundaries are blurry.
# Existing oversized files are pinned to their current line count. When this
# smoke fails, first split ownership or extract a module; only raise a legacy
# budget with an explicit follow-up plan for retiring that whitelist entry.
LEGACY_OVERSIZED_LIMITS = {
    "examples/benchmark-case-analysis-smoke.py": 1355,
    "examples/benchmark-run-ledger-smoke.py": 2106,
    "examples/codex-cli-long-run-benchmark-smoke.py": 1050,
    "examples/heartbeat-prompt-smoke.py": 1455,
    "examples/heartbeat-quota-flow-smoke.py": 1114,
    "examples/quota-plan-smoke.py": 2137,
    "examples/review-packet-cli-smoke.py": 1284,
    "examples/showcase-html-pages.py": 1235,
    "examples/skillsbench-app-server-goal-worker-smoke.py": 2864,
    "examples/skillsbench-benchmark-run-smoke.py": 14493,
    "examples/skillsbench-host-local-launch-plan-smoke.py": 2274,
    "examples/skillsbench-reverse-channel-bridge-smoke.py": 1091,
    "examples/status-markdown-smoke.py": 2411,
    "examples/terminal-bench-codex-loopx-active-cli-bridge-smoke.py": 1732,
    "examples/terminal-bench-harbor-runner-ingest-smoke.py": 2759,
    "examples/terminal-bench-private-runner-env-guard-smoke.py": 2585,
    "examples/work-lane-contract-smoke.py": 2264,
    "loopx/benchmark.py": 2875,
    "loopx/benchmark_adapters/agentissue.py": 2644,
    "loopx/benchmark_adapters/agents_last_exam.py": 3998,
    "loopx/benchmark_adapters/skillsbench.py": 5844,
    "loopx/benchmark_adapters/skillsbench_acp_relay.py": 3092,
    "loopx/benchmark_adapters/terminal_bench.py": 10045,
    "loopx/benchmark_case_analysis.py": 1276,
    "loopx/benchmark_case_state.py": 1030,
    "loopx/benchmark_ledger.py": 3535,
    "loopx/canary/planner.py": 1602,
    "loopx/capabilities/auto_research/cli.py": 1006,
    "loopx/capabilities/auto_research/legacy_core.py": 3013,
    "loopx/capabilities/content_ops/surface.py": 2549,
    "loopx/capabilities/lark/kanban.py": 3034,
    "loopx/cli_commands/benchmark_review_lifecycle.py": 1274,
    "loopx/cli_commands/terminal_bench_environment_result.py": 1246,
    "loopx/codex_cli_probe.py": 3546,
    "loopx/heartbeat_prompt.py": 1072,
    "loopx/history.py": 1468,
    "loopx/pr_review.py": 1137,
    "loopx/quota.py": 10093,
    "loopx/review_packet.py": 1294,
    "loopx/status.py": 11475,
    "loopx/terminal_bench_agent.py": 2056,
    "loopx/todos.py": 2105,
    "loopx/visible_multi_agent_launcher.py": 1097,
    "loopx/worker_bridge.py": 1574,
    "scripts/codex_app_server_goal_driver.py": 1074,
    "scripts/harbor_host_codex_goal_agent.py": 2140,
    "scripts/skillsbench_automation_loop.py": 16072,
    "scripts/skillsbench_reverse_channel_bridge.py": 1147,
    "scripts/skillsbench_reverse_tunnel_supervisor.py": 1058,
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
