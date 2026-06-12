#!/usr/bin/env python3
"""Smoke-test the AgentIssue-Bench runner publication change-set packet."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
PACKET = TOPIC_DIR / "agentissue-bench-codex-cli-runner-publication-change-set-v0.md"
BENCHMARK = REPO_ROOT / "goal_harness" / "benchmark.py"
CLI = REPO_ROOT / "goal_harness" / "cli.py"

DOCS = [
    "agentissue-bench-codex-cli-runner-contract-v0.md",
    "agentissue-bench-codex-cli-runner-flow-plan-v0.md",
    "agentissue-bench-codex-cli-runner-dry-run-wrapper-v0.md",
    "agentissue-bench-codex-cli-runner-synthetic-staging-v0.md",
    "agentissue-bench-codex-cli-runner-execution-gate-v0.md",
    "agentissue-bench-codex-cli-runner-first-run-handoff-v0.md",
    "agentissue-bench-codex-cli-runner-workflow-check-v0.md",
    "agentissue-bench-codex-cli-runner-run-gate-v0.md",
    "agentissue-bench-codex-cli-runner-pr-ready-packet-v0.md",
    "agentissue-bench-codex-cli-runner-publication-change-set-v0.md",
]

SMOKES = [
    "agentissue-bench-codex-cli-runner-contract-smoke.py",
    "agentissue-bench-codex-cli-runner-flow-smoke.py",
    "agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py",
    "agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py",
    "agentissue-bench-codex-cli-runner-execution-gate-smoke.py",
    "agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py",
    "agentissue-bench-codex-cli-runner-workflow-check-smoke.py",
    "agentissue-bench-codex-cli-runner-run-gate-smoke.py",
    "agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py",
    "agentissue-bench-codex-cli-runner-publication-change-set-smoke.py",
]

MIXED_TRACKED_FILES = [
    "goal_harness/benchmark.py",
    "goal_harness/cli.py",
    "goal_harness/status.py",
    "docs/research/long-horizon-agent-benchmarks/README.md",
]

REQUIRED_SOURCE_SNIPPETS = [
    "AGENTISSUE_BENCHMARK_ID",
    "AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION",
    "build_agentissue_codex_cli_runner_wrapper",
    "materialize_agentissue_codex_cli_runner_synthetic_staging",
    "materialize_agentissue_codex_cli_runner_execution_gate",
    "materialize_agentissue_codex_cli_runner_first_run_handoff",
    "materialize_agentissue_codex_cli_runner_workflow_check",
    "materialize_agentissue_codex_cli_runner_run_gate",
    "agentissue-codex-runner-flow",
    "--synthetic-staging-root",
    "--execution-gate-root",
    "--first-run-handoff-root",
    "--workflow-check-root",
    "--run-gate-root",
    "read_boundary",
]

FORBIDDEN_PACKET_TEXT = [
    "/" + "Users/",
    ".codex/auth.json",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "GOOGLE" + "_API_KEY",
    "CODEX" + "_ACCESS_TOKEN",
    "raw_issue_body:",
    "raw_patch:",
    "raw_log:",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def git_diff_name_only() -> set[str] | None:
    changed: set[str] = set()
    for diff_args in (
        ["git", "diff", "--name-only", "--"],
        ["git", "diff", "--cached", "--name-only", "--"],
        ["git", "diff", "--name-only", "origin/main", "--"],
    ):
        result = subprocess.run(
            diff_args + MIXED_TRACKED_FILES,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return None
        changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return changed


def assert_packet_exists_and_indexed() -> None:
    assert PACKET.exists(), PACKET
    readme = read(README)
    assert PACKET.name in readme


def assert_include_lists() -> None:
    packet = read(PACKET)
    missing_docs = [name for name in DOCS if name not in packet]
    missing_smokes = [name for name in SMOKES if name not in packet]
    missing_mixed = [name for name in MIXED_TRACKED_FILES if name not in packet]
    assert not missing_docs, missing_docs
    assert not missing_smokes, missing_smokes
    assert not missing_mixed, missing_mixed
    assert "do not stage them with a whole-file `git add`" in packet
    assert "hunk-level staging" in packet
    assert "not part of this runner-flow publication change set" in packet


def assert_source_and_readme_contract() -> None:
    source = read(BENCHMARK) + "\n" + read(CLI)
    missing = [snippet for snippet in REQUIRED_SOURCE_SNIPPETS if snippet not in source]
    assert not missing, missing
    readme = read(README)
    for name in DOCS:
        assert name in readme, name
    assert readme.count("agentissue-bench-codex-cli-runner-") >= len(DOCS)


def assert_mixed_files_are_detected() -> None:
    changed = git_diff_name_only()
    if changed is None or not changed:
        missing_paths = [name for name in MIXED_TRACKED_FILES if not (REPO_ROOT / name).exists()]
        assert not missing_paths, missing_paths
        return
    unexpected = [name for name in changed if name not in MIXED_TRACKED_FILES]
    assert not unexpected, unexpected
    assert "goal_harness/benchmark.py" in changed, changed
    assert "goal_harness/cli.py" in changed, changed
    assert "docs/research/long-horizon-agent-benchmarks/README.md" in changed, changed


def assert_public_boundary() -> None:
    packet = read(PACKET)
    leaked = [marker for marker in FORBIDDEN_PACKET_TEXT if marker in packet]
    assert not leaked, leaked
    assert "real_run=false" in packet
    assert "submit_eligible=false" in packet
    assert "leaderboard_evidence=false" in packet
    assert "Codex, Docker, model APIs" in packet


def main() -> None:
    assert_packet_exists_and_indexed()
    assert_include_lists()
    assert_source_and_readme_contract()
    assert_mixed_files_are_detected()
    assert_public_boundary()
    print(
        "agentissue-bench-codex-cli-runner-publication-change-set-smoke ok "
        "docs=10 smokes=10 mixed_files_subset_documented real_run=False"
    )


if __name__ == "__main__":
    main()
