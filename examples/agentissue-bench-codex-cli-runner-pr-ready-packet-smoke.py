#!/usr/bin/env python3
"""Smoke-test the AgentIssue-Bench Codex CLI runner PR-ready packet."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
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
]

REQUIRED_PACKET_SNIPPETS = [
    "AgentIssue-Bench Codex CLI Runner PR-Ready Packet V0",
    "contract -> flow plan -> dry-run wrapper -> synthetic staging -> execution gate -> first-run handoff -> workflow check -> run-specific gate -> PR-ready packet",
    "--synthetic-staging-root",
    "--execution-gate-root",
    "--first-run-handoff-root",
    "--workflow-check-root",
    "--run-gate-root",
    "real_run=false",
    "submit_eligible=false",
    "leaderboard_evidence=false",
]

REQUIRED_SOURCE_SNIPPETS = [
    "AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION",
    "AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION",
    "materialize_agentissue_codex_cli_runner_synthetic_staging",
    "materialize_agentissue_codex_cli_runner_execution_gate",
    "materialize_agentissue_codex_cli_runner_first_run_handoff",
    "materialize_agentissue_codex_cli_runner_workflow_check",
    "materialize_agentissue_codex_cli_runner_run_gate",
    "--first-run-handoff-root",
    "--workflow-check-root",
    "--run-gate-root",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    ".codex/auth.json",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "GOOGLE" + "_API_KEY",
    "CODEX" + "_ACCESS_TOKEN",
    "raw" + "_issue_body:",
    "raw" + "_patch:",
    "raw" + "_log:",
    "trajectory.json",
    "screenshot.png",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_exists() -> None:
    missing_docs = [name for name in DOCS if not (TOPIC_DIR / name).exists()]
    missing_smokes = [name for name in SMOKES if not (REPO_ROOT / "examples" / name).exists()]
    assert not missing_docs, missing_docs
    assert not missing_smokes, missing_smokes


def assert_readme_indexed() -> None:
    text = read(README)
    missing = [name for name in DOCS if name not in text]
    assert not missing, missing


def assert_packet_contract() -> None:
    packet = read(TOPIC_DIR / "agentissue-bench-codex-cli-runner-pr-ready-packet-v0.md")
    missing = [snippet for snippet in REQUIRED_PACKET_SNIPPETS if snippet not in packet]
    assert not missing, missing
    assert packet.count("agentissue-bench-codex-cli-runner-") >= len(DOCS), packet
    assert packet.count("examples/agentissue-bench-codex-cli-runner-") >= len(SMOKES), packet


def assert_source_contract() -> None:
    source = read(BENCHMARK) + "\n" + read(CLI)
    missing = [snippet for snippet in REQUIRED_SOURCE_SNIPPETS if snippet not in source]
    assert not missing, missing
    assert source.count("real_codex_invoked") >= 1, "missing Codex no-run flag"
    assert source.count("real_docker_invoked") >= 1, "missing Docker no-run flag"
    assert "agentissue-codex-runner-flow accepts at most one root option, not both" in source


def assert_public_boundary() -> None:
    public_text = "\n".join(read(TOPIC_DIR / name) for name in DOCS)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in public_text]
    assert not leaked, leaked
    assert "<private-root>" in public_text or "<private-gate-root>" in public_text
    assert "<abs-private-job-root>" in public_text
    assert not re.search(r"/var/folders/|/tmp/agentissue|/home/[^<]", public_text), "local path leak"


def main() -> None:
    assert_exists()
    assert_readme_indexed()
    assert_packet_contract()
    assert_source_contract()
    assert_public_boundary()
    print(
        "agentissue-bench-codex-cli-runner-pr-ready-packet-smoke ok "
        "docs=9 smokes=9 real_run=False"
    )


if __name__ == "__main__":
    main()
