"""CLI tests for governed goal amendment proposal submission and readback.

Verifies ``loopx goal-amendment-proposal`` and its ``loopx
amendment-proposal`` alias end to end: a proposal submitted through the CLI
lands in ``runtime/goals/<goal>/amendment-proposals/journal.jsonl`` and the
``--list`` readback returns the same retained row (the Stage 2 production
consumer loop), plus markdown output, idempotent resubmission, and the
fail-closed negative paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.cli import main as cli_main
from tests.control_plane.test_goal_amendment_proposal import (
    GOAL_ID,
    _default_events,
    _proposal,
    _status_item,
    _write_fixture,
)


def _run_amendment_cli(
    capsys: pytest.CaptureFixture[str],
    registry: Path,
    *argv: str,
) -> tuple[int, dict[str, Any], str]:
    exit_code = cli_main(["--registry", str(registry), *argv])
    captured = capsys.readouterr()
    payload: dict[str, Any] = {}
    if "--format" in argv and "json" in argv:
        payload = json.loads(captured.out)
    return exit_code, payload, captured.out


def _write_submit_inputs(
    tmp_path: Path,
    paths: dict[str, Path],
    proposal: dict[str, object],
) -> tuple[Path, Path]:
    proposal_json = tmp_path / "proposal.json"
    proposal_json.write_text(json.dumps(proposal), encoding="utf-8")
    obligations_json = tmp_path / "obligations.json"
    obligations_json.write_text(json.dumps(_status_item()), encoding="utf-8")
    return proposal_json, obligations_json


def _submit_argv(
    paths: dict[str, Path],
    proposal_json: Path,
    obligations_json: Path,
    *extra: str,
) -> tuple[str, ...]:
    return (
        "--proposal-json",
        str(proposal_json),
        "--obligations-json",
        str(obligations_json),
        "--project",
        str(paths["project"]),
        *extra,
    )


def test_cli_submits_proposal_and_lists_journal_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal
    )

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "json",
    )

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["admission"] == "admitted"
    assert payload["canonical_effect"] == "none"
    assert payload["proposal_id"] == "gap_stage2_001"
    assert payload["journal_append_sequence"] == 1

    journal = (
        paths["runtime"]
        / "goals"
        / GOAL_ID
        / "amendment-proposals"
        / "journal.jsonl"
    )
    assert journal.is_file()
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    retained = json.loads(lines[0])
    assert retained["proposal_id"] == "gap_stage2_001"

    # End-to-end readback: the journal row the CLI wrote is what --list
    # returns, through the same runtime root the registry carries.
    list_code, list_payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        GOAL_ID,
        "--format",
        "json",
    )

    assert list_code == 0
    assert list_payload["ok"] is True
    assert list_payload["goal_id"] == GOAL_ID
    assert list_payload["count"] == 1
    assert list_payload["rows"][0]["proposal_id"] == "gap_stage2_001"
    assert list_payload["rows"][0]["journal_append_sequence"] == 1


def test_cli_submits_proposal_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal
    )

    exit_code, _, stdout = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "markdown",
    )

    assert exit_code == 0
    assert "# LoopX Goal Amendment Proposal" in stdout
    assert "- ok: `True`" in stdout
    assert f"- goal_id: `{GOAL_ID}`" in stdout
    assert "- admission: `admitted`" in stdout
    assert "- canonical_effect: `none`" in stdout

    list_code, _, list_stdout = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        GOAL_ID,
        "--format",
        "markdown",
    )

    assert list_code == 0
    assert "- count: 1" in list_stdout
    assert "`gap_stage2_001` admission=`admitted` sequence=1" in list_stdout


def test_cli_alias_amendment_proposal_matches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal
    )

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "json",
    )

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["admission"] == "admitted"


def test_cli_resubmission_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal
    )

    first_code, first_payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "json",
    )
    second_code, second_payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "json",
    )

    assert first_code == second_code == 0
    assert (
        second_payload["journal_append_sequence"]
        == first_payload["journal_append_sequence"]
        == 1
    )
    _, list_payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        GOAL_ID,
        "--format",
        "json",
    )
    assert list_payload["count"] == 1


def test_cli_nonexistent_obligation_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths, {"replan_obligation_id": "replan-deadbeefdeadbeef"})
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal
    )

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "does not match an open replan obligation" in payload["error"]
    journal = (
        paths["runtime"]
        / "goals"
        / GOAL_ID
        / "amendment-proposals"
        / "journal.jsonl"
    )
    assert not journal.exists()


def test_cli_unregistered_proposer_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths, {"proposer_agent_id": "agent-z"})
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal
    )

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        *_submit_argv(paths, proposal_json, obligations_json),
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "not registered" in payload["error"]


def test_cli_list_without_goal_id_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "--list requires --goal-id" in payload["error"]


def test_cli_malformed_proposal_json_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal_json = tmp_path / "broken.json"
    proposal_json.write_text('{"schema_version": tru', encoding="utf-8")

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--proposal-json",
        str(proposal_json),
        "--project",
        str(paths["project"]),
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "error" in payload


def test_cli_submit_without_obligations_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No authority payload supplied: the obligation inventory is empty and
    # the causal chain cannot be verified from string shape alone.
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)
    proposal_json, _ = _write_submit_inputs(tmp_path, paths, proposal)

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--proposal-json",
        str(proposal_json),
        "--project",
        str(paths["project"]),
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "does not match an open replan obligation" in payload["error"]
