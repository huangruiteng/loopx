#!/usr/bin/env python3
"""Smoke-test compact issue-fix feasibility routing and domain-state writeback."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    ISSUE_FIX_FEASIBILITY_PACKET_SCHEMA_VERSION,
    build_issue_fix_feasibility_packet,
)


URL = "https://github.com/owner/repo/issues/123"


def assert_boundary(packet: dict[str, object]) -> None:
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "todo_write_performed",
        "issue_body_captured",
        "comment_bodies_captured",
        "response_payloads_captured",
        "raw_logs_captured",
        "local_paths_captured",
        "destructive_git_used",
    ):
        assert packet[key] is False, (key, packet)
    text = json.dumps(packet, sort_keys=True)
    assert "/Users/" not in text, text
    assert "/private/tmp/" not in text, text
    assert "raw issue body" not in text, text
    assert "raw check log" not in text, text


def main() -> int:
    fix = build_issue_fix_feasibility_packet(
        url=URL,
        reproduction_status="confirmed",
        reproduction_label="focused unit repro",
        scope_class="bounded",
        validation_label="focused unit test",
    )
    assert fix["ok"] is True, fix
    assert fix["schema_version"] == ISSUE_FIX_FEASIBILITY_PACKET_SCHEMA_VERSION
    assert fix["decision"]["route"] == "fix_pr", fix
    assert fix["transition"]["decision"] == "runnable_successor", fix
    assert fix["transition"]["projected_todo"]["action_kind"] == (
        "issue_fix_branch_validation"
    ), fix
    assert_boundary(fix)

    planned = build_issue_fix_feasibility_packet(
        url=URL,
        reproduction_status="planned",
        reproduction_label="focused repro plan",
        scope_class="bounded",
        validation_label="focused unit test",
    )
    assert planned["decision"]["route"] == "fix_pr", planned
    assert planned["transition"]["projected_todo"]["action_kind"] == (
        "issue_fix_confirm_reproduction"
    ), planned

    comment = build_issue_fix_feasibility_packet(
        url=URL,
        reproduction_status="missing",
        scope_class="uncertain",
        comment_value="clarification",
    )
    assert comment["decision"]["route"] == "comment_only", comment
    assert comment["transition"]["projected_todo"]["action_kind"] == (
        "issue_fix_external_comment_packet"
    ), comment
    assert comment["transition"]["external_write_gate"]["satisfied"] is False
    assert_boundary(comment)

    triage = build_issue_fix_feasibility_packet(
        url=URL,
        reproduction_status="missing",
        scope_class="oversized",
    )
    assert triage["decision"]["route"] == "triage_only", triage
    assert triage["transition"]["decision"] == "no_followup", triage
    assert triage["transition"]["projected_todo"] is None, triage
    assert_boundary(triage)

    try:
        build_issue_fix_feasibility_packet(
            url=URL,
            reproduction_status="confirmed",
            reproduction_label="/Users/example/private/repro.log",
            scope_class="bounded",
            validation_label="focused unit test",
        )
    except ValueError as exc:
        assert "reproduction_label" in str(exc), exc
    else:
        raise AssertionError("local path reproduction label must be rejected")

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-feasibility-") as tmpdir:
        project = Path(tmpdir)
        command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "issue-fix",
            "feasibility",
            "--url",
            URL,
            "--reproduction-status",
            "confirmed",
            "--reproduction-label",
            "focused unit repro",
            "--scope-class",
            "bounded",
            "--validation-label",
            "focused unit test",
            "--goal-id",
            "pilot-goal",
            "--project",
            str(project),
        ]
        first = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        first_packet = json.loads(first.stdout)
        assert first_packet["domain_state_projection"]["write_performed"] is True
        ledger = (
            project
            / ".loopx"
            / "domain-state"
            / "pilot-goal"
            / "issue_fix"
            / "feasibility.jsonl"
        )
        assert ledger.exists(), ledger
        rows = ledger.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1, rows
        first_row = json.loads(rows[0])
        first_projection = first_row["domain_state_projection"]
        assert first_projection["write_performed"] is True, first_row
        assert "write_result" not in first_projection, first_row

        second_command = command.copy()
        second_command[second_command.index("confirmed")] = "missing"
        repro_index = second_command.index("--reproduction-label")
        del second_command[repro_index : repro_index + 2]
        validation_index = second_command.index("--validation-label")
        del second_command[validation_index : validation_index + 2]
        second_command.extend(["--comment-value", "diagnosis"])
        second = subprocess.run(
            second_command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        second_packet = json.loads(second.stdout)
        assert second_packet["decision"]["route"] == "comment_only", second_packet
        rows = ledger.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1, rows
        second_row = json.loads(rows[0])
        assert second_row["decision"]["route"] == "comment_only", rows
        second_projection = second_row["domain_state_projection"]
        assert second_projection["write_performed"] is True, second_row
        assert "write_result" not in second_projection, second_row

    print("issue-fix-feasibility-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
