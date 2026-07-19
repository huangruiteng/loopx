#!/usr/bin/env python3
"""Smoke-test the cross-runtime implementation/review demo packet."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.handoff.cross_runtime_impl_review import (  # noqa: E402
    CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION,
    build_cross_runtime_impl_review_demo_packet,
    render_cross_runtime_impl_review_demo_markdown,
)


def run_loopx(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def assert_packet_shape(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION, payload
    assert payload["preset"] == "claude-codex", payload
    assert payload["dry_run"] is True, payload
    assert payload["writes_state"] is False, payload
    assert payload["launches_runtime"] is False, payload
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["raw_transcripts_captured"] is False, payload

    roles = payload["roles"]
    assert roles["implementer"]["agent_id"] == "claude-code-impl", roles
    assert roles["implementer"]["runtime"] == "claude_code", roles
    assert "/loopx <implementation goal>" in roles["implementer"]["visible_entry"], roles
    assert roles["reviewer"]["agent_id"] == "codex-review", roles
    assert roles["reviewer"]["runtime"] == "codex", roles

    todos = {todo["todo_key"]: todo for todo in payload["planned_todos"]}
    assert set(todos) == {"implementation", "review"}, todos
    assert todos["implementation"]["claimed_by"] == "claude-code-impl", todos
    assert todos["review"]["claimed_by"] == "codex-review", todos
    assert all(todo["would_write"] is False for todo in todos.values()), todos

    commands = [command["command"] for command in payload["commands"]]
    assert any(command.startswith("loopx todo add") for command in commands), commands
    assert any("quota should-run" in command for command in commands), commands
    assert any(command.startswith("loopx review-packet") for command in commands), commands

    verdict = payload["review_verdict_contract"]
    for key in ["verdict", "blockers", "suggestions", "verifier", "handoff"]:
        assert key in verdict, verdict

    forbidden = " ".join(payload["evidence_boundary"]["forbidden"])
    assert "raw Claude or Codex transcripts" in forbidden, forbidden
    assert "raw benchmark task text" in forbidden, forbidden


def assert_cli_json_packet() -> None:
    completed = run_loopx(
        "--format",
        "json",
        "demo",
        "impl-review",
        "--preset",
        "claude-codex",
        "--dry-run",
        "--requirement",
        "Ship a small public-safe docs change",
        "--verifier",
        "python3 examples/public_entry/readme-demo-surface-smoke.py",
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert_packet_shape(payload)
    assert payload["goal_id"] == "cross-runtime-impl-review-demo", payload
    assert payload["requirement"] == "Ship a small public-safe docs change", payload


def assert_cli_markdown_packet() -> None:
    completed = run_loopx("demo", "impl-review", "--dry-run")
    assert completed.returncode == 0, completed.stderr
    assert "# Cross-Runtime Impl/Review Demo Packet" in completed.stdout, completed.stdout
    assert "`loopx review-packet --goal-id cross-runtime-impl-review-demo`" in completed.stdout
    assert "`handoff`" in completed.stdout, completed.stdout


def assert_rejects_live_and_private_inputs() -> None:
    no_dry_run = run_loopx("--format", "json", "demo", "impl-review")
    assert no_dry_run.returncode == 1, no_dry_run.stdout
    no_dry_payload = json.loads(no_dry_run.stdout)
    assert no_dry_payload["ok"] is False, no_dry_payload
    assert "dry-run only" in no_dry_payload["error"], no_dry_payload

    private_requirement = run_loopx(
        "--format",
        "json",
        "demo",
        "impl-review",
        "--dry-run",
        "--requirement",
        "Read /Users/example/private-plan.md",
    )
    assert private_requirement.returncode == 1, private_requirement.stdout
    private_payload = json.loads(private_requirement.stdout)
    assert private_payload["ok"] is False, private_payload
    assert "private-looking" in private_payload["error"], private_payload


def assert_docs_expose_command_and_schema() -> None:
    doc = (REPO_ROOT / "docs/product/cross-runtime-impl-review-demo.md").read_text(
        encoding="utf-8"
    )
    assert "loopx demo impl-review --preset claude-codex --dry-run" in doc, doc
    assert CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION in doc, doc


def main() -> int:
    payload = build_cross_runtime_impl_review_demo_packet()
    assert_packet_shape(payload)
    markdown = render_cross_runtime_impl_review_demo_markdown(payload)
    assert "# Cross-Runtime Impl/Review Demo Packet" in markdown, markdown
    assert "loopx review-packet --goal-id cross-runtime-impl-review-demo" in markdown
    assert_cli_json_packet()
    assert_cli_markdown_packet()
    assert_rejects_live_and_private_inputs()
    assert_docs_expose_command_and_schema()
    print("cross-runtime-impl-review-demo-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
