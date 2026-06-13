#!/usr/bin/env python3
"""Smoke-test the public ALE local Docker + host Codex route note."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "agents-last-exam-local-docker-host-codex-route-v0.md"
)
README = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks" / "README.md"


def normalized(text: str) -> str:
    return " ".join(text.split())


def main() -> None:
    doc = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    compact = normalized(doc)
    compact_readme = normalized(readme)
    for phrase in (
        "non-GCP ALE route",
        "local Docker/Colima",
        "host Codex CLI",
        "Docker provider",
        "CUA/MCP bridge",
        "Google Cloud is the supported provider",
        "output_path: local",
        "agentslastexam/ale-kasm:latest",
        "demo/tool_smoke",
        "score `1.0`",
        "computing_math/os_log_permission_guard_v1",
        "requires_task_data=True",
        "task_data_source=baked_in_sandbox",
        "gs://ale-data-public",
        "--requires-task-data false",
        "--enforce-task-data-source",
        "No upload, no submit, no leaderboard claim",
        "raw trajectories, screenshots, raw logs, credential values, or local host paths",
        "Colima",
        "gcloud",
        "GCP_PROJECT",
        "GCP_SA_KEY",
    ):
        assert phrase in compact, phrase

    assert "agents-last-exam-local-docker-host-codex-route-v0.md" in compact_readme
    assert "local Docker/Colima plus host Codex CLI" in compact_readme
    assert "score `1.0` canary as route evidence rather than uplift" in compact_readme


if __name__ == "__main__":
    main()
    print("agents-last-exam-local-docker-host-codex-route-smoke ok")
