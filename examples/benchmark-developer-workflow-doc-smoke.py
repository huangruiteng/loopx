#!/usr/bin/env python3
"""Smoke-test the public benchmark developer workflow guide."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "benchmark-developer-workflow.md"
README = REPO_ROOT / "README.md"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
TASKS = REPO_ROOT / "CONTRIBUTOR_TASKS.md"

FORBIDDEN_SNIPPETS = (
    "/Users/",
    "~/.codex",
    ".codex/auth.json",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "password",
    "secret",
)


def require(text: str, snippets: list[str], *, source: Path) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, f"{source} missing {missing}"


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    require(
        doc,
        [
            "# Benchmark Developer Workflow",
            "Goal Harness treats benchmark execution as a developer workflow",
            "## Golden Path",
            "## Capture The Process While Running",
            "Each real run should improve the developer workflow",
            "Before launch, write down the intended route",
            "## Cloud ECS Benchmark Host Route",
            "Use the cloud ECS benchmark host route as the default",
            "ECS-style cloud VM",
            "Cloud-host Codex connectivity is its own preflight",
            "### ECS Host Bootstrap SOP",
            "scripts/benchmark_ecs_bootstrap.py",
            "scripts/benchmark_agent_runtime_layer.py",
            "preinstalled as a stable layer",
            "harbor_codex_cli_tools",
            "No module named 'harbor_host_codex_goal_agent'",
            "importlib.import_module(\"harbor_host_codex_goal_agent\")",
            "importlib.import_module(\"goal_harness.benchmark_core.loop_protocol\")",
            "tmux`, `launchd`, or a generated `run.sh`",
            "packet_only_observation",
            "goal_harness.benchmark_core.loop_protocol",
            "baseline: native Codex app-server Goal mode",
            "test: Goal Harness prompt-driven polling",
            "goal-harness-prompt-polling-test",
            "goal_harness_experiment_protocol=max5_blind_loop_no_feedback",
            "goal_harness_prompt_polling_rounds=5",
            "goal_harness_prompt_polling_round_timeout_sec=900",
            "follow-up",
            "`turn/start` calls in the same thread",
            "harbor_prompt_polling_round_timeout_before_completion",
            "max_rounds_budget=5",
            "official_feedback_forwarded=false",
            "official_feedback_blinded_count",
            "do not compare it as test",
            "case-local Goal Harness surface",
            "/app/.local/bin/goal-harness",
            "todo_benchmark_case_main",
            "host controller must then run the",
            "case-local CLI as a scheduler lifecycle",
            "goal_harness_case_scheduler_command_count",
            "goal_harness_case_rollout_event_counts",
            "goal_harness_case_rollout_trace.public.json",
            "main project goal or side-agent",
            "benchflow_js_agent_runtime",
            "scripts/skillsbench_agent_runtime_layer.py",
            "scripts/terminal_bench_no_upload_smoke.py",
            "scripts/terminal_bench_compose_startup_reducer.py",
            "scripts/skillsbench_verifier_prewarm_plan.py",
            "For SkillsBench, prove the verifier dependency substrate",
            "skillsbench_verifier_dependency_prewarm_required",
            "Do not repair that first by globally extending timeouts",
            ".goal-harness-upstream",
            "materialized copy",
            "**Auth**",
            "**Network**",
            "**Execution**",
            "loopback-only proxy or tunnel",
            "The reusable trick is the shape, not the private wiring",
            "### SSH Session Hygiene",
            "SSH multiplexed master",
            "ControlPath ~/.ssh/cm/%C",
            "ControlPersist 8h",
            "ssh -MNf",
            "Keep commands through the master connection mostly serial",
            "foreground SSH session",
            "tmux",
            "capture-pane",
            "## Split-Control Route",
            "fallback and research route",
            "## Current Benchmark Families",
            "Terminal-Bench",
            "SkillsBench",
            "Agents' Last Exam",
            "Benchmark evidence must not include",
            "raw task text",
            "raw trajectories",
            "credentials",
            "uploads, submit paths, or leaderboard claims",
        ],
        source=DOC,
    )
    leaked = [snippet for snippet in FORBIDDEN_SNIPPETS if snippet in doc]
    assert not leaked, leaked

    readme = README.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    tasks = TASKS.read_text(encoding="utf-8")
    require(readme, ["docs/benchmark-developer-workflow.md"], source=README)
    require(docs_index, ["benchmark-developer-workflow.md"], source=DOCS_INDEX)
    require(tasks, ["GH-C40", "benchmark developer workflow"], source=TASKS)

    print("benchmark-developer-workflow-doc-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
