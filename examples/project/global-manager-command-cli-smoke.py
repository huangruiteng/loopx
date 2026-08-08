#!/usr/bin/env python3
"""Smoke-test the public-safe global manager CLI commands."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "smoke-goal"
AGENT_ID = "codex-smoke"
BLOCKED_TODO_ID = "todo_blocked"
PRIVATE_PATTERNS = [
    re.compile(r"/" + r"Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/" + r"private/"),
    re.compile(r"/tmp/"),
    re.compile(r"/var/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
]


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(
                f"global manager payload leaked private pattern {pattern.pattern!r}"
            )
    if "/loopx-summary-all" in text:
        raise AssertionError("global manager payload exposed a superseded alias")


def run_cli(
    *,
    registry: Path,
    runtime: Path,
    command: str,
    output_format: str,
    command_args: list[str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            output_format,
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime),
            command,
            *(command_args or []),
        ],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry = root / "registry.global.json"
    run_index = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    state.parent.mkdir(parents=True)
    state.write_text(
        "---\n"
        "status: active\n"
        f"goal_id: {GOAL_ID}\n"
        "updated_at: 2026-06-26T00:00:00+00:00\n"
        "---\n\n"
        "# Global Manager CLI Smoke\n\n"
        "## User Todo\n\n"
        "- [ ] [P0] Approve the public-safe blocked delivery.\n"
        "  <!-- loopx:todo todo_id=todo_gate_approve status=open "
        "task_class=user_gate action_kind=approve "
        f"blocks_agent={AGENT_ID} unblocks_todo_id={BLOCKED_TODO_ID} -->\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] Deliver the approved public-safe change.\n"
        f"  <!-- loopx:todo todo_id={BLOCKED_TODO_ID} status=open "
        f"task_class=advancement_task claimed_by={AGENT_ID} -->\n\n"
        "## Next Action\n\n"
        "- Approve the public-safe blocked delivery.\n",
        encoding="utf-8",
    )
    registry.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "objective": "Smoke global manager commands.",
                        "domain": "loopx-smoke",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                        "adapter": {
                            "kind": "read_only_project_map_v0",
                            "status": "connected-read-only",
                        },
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_index.parent.mkdir(parents=True)
    run_index.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-26T00:00:00+00:00",
                "classification": "smoke_progress",
                "recommended_action": "Continue the next public-safe smoke step.",
                "json_exists": True,
                "markdown_exists": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry, runtime, state, run_index


def snapshot_files(paths: list[Path]) -> dict[Path, tuple[bytes, int]]:
    return {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in paths
    }


def assert_summary_payload(payload: dict[str, object]) -> None:
    assert payload["schema_version"] == "global_manager_command_response_v0", payload
    request = payload["request"]
    assert request["command"] == "/loopx-global-summary", request
    assert "/loop-global-summary" in request["legacy_aliases"], request
    assert request["cli_command"] == "loopx global-summary", request
    assert request["privacy_mode"] == "public_safe_summary", request
    assert request["dry_run"] is True, request
    assert payload["boundary"]["absolute_paths_recorded"] is False, payload["boundary"]
    assert "groups" in payload and "recent_progress" in payload["groups"], payload
    assert_public_safe(payload)


def assert_gates_payload(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    request = payload["request"]
    assert request["command"] == "/loopx-global-gates", request
    assert request["legacy_aliases"] == ["/loop-global-gates"], request
    assert request["cli_command"] == "loopx global-gates", request
    assert request["dry_run"] is True, request
    assert payload["summary"]["open_gate_count"] == 1, payload
    assert payload["gates"][0]["blocks"] == [BLOCKED_TODO_ID], payload
    assert_public_safe(payload)


def assert_gates_markdown(markdown: str, *, private_root: Path) -> None:
    assert "# LoopX Global Gates" in markdown, markdown
    assert "`/loopx-global-gates`" in markdown, markdown
    assert f"`{GOAL_ID}`" in markdown, markdown
    assert f"blocks=`{BLOCKED_TODO_ID}`" in markdown, markdown
    assert "Recent Progress" not in markdown, markdown
    assert "Risks" not in markdown, markdown
    assert str(private_root) not in markdown, markdown


def assert_error_envelope(root: Path, *, runtime: Path) -> None:
    error_registry = root / "private" / "error-registry"
    error_registry.mkdir(parents=True)
    error_proc = run_cli(
        registry=error_registry,
        runtime=runtime,
        command="global-gates",
        output_format="json",
        check=False,
    )
    assert error_proc.returncode != 0, error_proc
    payload = json.loads(error_proc.stdout)
    assert payload["request"]["command"] == "/loopx-global-gates", payload
    assert str(error_registry) not in error_proc.stdout, error_proc.stdout
    assert "<local-path-redacted>" in error_proc.stdout, error_proc.stdout
    assert_public_safe(payload)


def assert_unhealthy_status_envelope(
    root: Path, *, registry: Path, runtime: Path
) -> None:
    unhealthy_registry = root / "unhealthy-registry.json"
    unhealthy_payload = json.loads(registry.read_text(encoding="utf-8"))
    del unhealthy_payload["goals"][0]["domain"]
    unhealthy_registry.write_text(
        json.dumps(unhealthy_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    status_proc = run_cli(
        registry=unhealthy_registry,
        runtime=runtime,
        command="status",
        output_format="json",
        check=False,
    )
    status_payload = json.loads(status_proc.stdout)
    assert status_payload["ok"] is False, status_proc
    assert "attention_queue" in status_payload, status_payload
    assert "error" not in status_payload, status_payload

    gates_proc = run_cli(
        registry=unhealthy_registry,
        runtime=runtime,
        command="global-gates",
        output_format="json",
        check=False,
    )
    assert gates_proc.returncode != 0, gates_proc
    payload = json.loads(gates_proc.stdout)
    assert payload["ok"] is False, payload
    assert payload["error"] == "Global status source unavailable.", payload
    assert "summary" not in payload, payload
    assert "gates" not in payload, payload
    assert "lanes" not in payload, payload
    assert str(root) not in gates_proc.stdout, gates_proc.stdout
    assert_public_safe(payload)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-global-manager-smoke-") as tmp:
        root = Path(tmp)
        registry, runtime, state, run_index = write_fixture(root)
        files = [registry, state, run_index]
        before = snapshot_files(files)

        summary_proc = run_cli(
            registry=registry,
            runtime=runtime,
            command="global-summary",
            output_format="json",
            command_args=["--agent-id", AGENT_ID, "--limit", "5"],
        )
        gates_proc = run_cli(
            registry=registry,
            runtime=runtime,
            command="global-gates",
            output_format="json",
            command_args=["--agent-id", AGENT_ID, "--limit", "5"],
        )
        markdown_proc = run_cli(
            registry=registry,
            runtime=runtime,
            command="global-gates",
            output_format="markdown",
            command_args=["--agent-id", AGENT_ID, "--limit", "5"],
        )

        assert_summary_payload(json.loads(summary_proc.stdout))
        assert_gates_payload(json.loads(gates_proc.stdout))
        assert_gates_markdown(markdown_proc.stdout, private_root=root)
        assert snapshot_files(files) == before
        assert_error_envelope(root, runtime=runtime)
        assert_unhealthy_status_envelope(
            root,
            registry=registry,
            runtime=runtime,
        )

    print("global-manager-command-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
