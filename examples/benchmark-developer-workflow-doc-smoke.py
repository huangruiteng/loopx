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
            "ControlPersist=600",
            "Keep commands through the master connection mostly serial",
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
