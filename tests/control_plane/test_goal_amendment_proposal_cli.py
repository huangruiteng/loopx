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
from loopx.control_plane.goals.goal_amendment_proposal import (
    build_replan_obligation_authority_envelope,
)
from tests.control_plane.test_goal_amendment_proposal import (
    GOAL_ID,
    _default_events,
    _derived_source_basis,
    _fixture_obligation,
    _proposal,
    _status_item,
    _write_fixture,
)


def _run_amendment_cli(
    capsys: pytest.CaptureFixture[str],
    registry: Path,
    *argv: str,
    runtime_root: Path | None = None,
) -> tuple[int, dict[str, Any], str]:
    top_argv = ["--registry", str(registry)]
    if runtime_root is not None:
        top_argv.extend(["--runtime-root", str(runtime_root)])
    exit_code = cli_main([*top_argv, *argv])
    captured = capsys.readouterr()
    payload: dict[str, Any] = {}
    if "--format" in argv and "json" in argv:
        payload = json.loads(captured.out)
    return exit_code, payload, captured.out


def _obligation_envelope(
    paths: dict[str, Path],
    *,
    goal_id: str = GOAL_ID,
    obligations_by_agent: dict[str, dict[str, object]] | None = None,
    derived_basis: dict[str, object] | None = None,
    receipt_id: str | None = None,
) -> dict[str, Any]:
    basis = (
        derived_basis
        if derived_basis is not None
        else _derived_source_basis(paths)
    )
    by_agent = (
        obligations_by_agent
        if obligations_by_agent is not None
        else {"agent-a": _fixture_obligation("agent-a")}
    )
    return build_replan_obligation_authority_envelope(
        goal_id=goal_id,
        derived_basis=basis,
        obligations_by_agent=by_agent,
        receipt_id=receipt_id,
    )


def _write_submit_inputs(
    tmp_path: Path,
    paths: dict[str, Path],
    proposal: dict[str, object],
    *,
    envelope: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    proposal_json = tmp_path / "proposal.json"
    proposal_json.write_text(json.dumps(proposal), encoding="utf-8")
    obligations_json = tmp_path / "obligations.json"
    payload = (
        envelope
        if envelope is not None
        else _obligation_envelope(
            paths, goal_id=str(proposal.get("goal_id") or GOAL_ID)
        )
    )
    obligations_json.write_text(json.dumps(payload), encoding="utf-8")
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


def test_cli_list_path_traversal_sibling_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    # Place a sibling journal under runtime/goals/victim/amendment-proposals/journal.jsonl
    sibling_journal = (
        paths["runtime"]
        / "goals"
        / "victim"
        / "amendment-proposals"
        / "journal.jsonl"
    )
    sibling_journal.parent.mkdir(parents=True, exist_ok=True)
    sibling_journal.write_text(
        json.dumps(
            {"proposal_id": "gap_victim_001", "journal_append_sequence": 1}
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        "../victim",
        "--format",
        "json",
        runtime_root=paths["runtime"],
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "single path segment" in payload["error"]
    assert "gap_victim_001" not in str(payload)


def test_cli_list_path_traversal_dotdot_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        "..",
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "single path segment" in payload["error"]


def test_cli_list_absolute_path_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        "/victim",
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "single path segment" in payload["error"]


def test_cli_list_path_separator_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        "victim/extra",
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "single path segment" in payload["error"]


def test_cli_list_unknown_goal_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    exit_code, payload, _ = _run_amendment_cli(
        capsys,
        paths["registry"],
        "goal-amendment-proposal",
        "--list",
        "--goal-id",
        "goal_unknown",
        "--format",
        "json",
    )

    assert exit_code == 1
    assert payload["ok"] is False
    assert "goal is not registered" in payload["error"]


def test_cli_submit_fabricated_obligation_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)

    # 1. Raw unverified JSON dictionary without envelope/receipt
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal, envelope=_status_item()
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
    assert "verified envelope" in payload["error"]

    # 2. Tampered receipt digest
    tampered_envelope = _obligation_envelope(paths)
    tampered_envelope["receipt"]["receipt_digest"] = "sha256:deadbeef" * 8
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal, envelope=tampered_envelope
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
    assert "fabricated or tampered" in payload["error"]


def test_cli_submit_stale_obligation_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)

    # Stale sequence
    stale_seq_envelope = _obligation_envelope(
        paths,
        derived_basis={
            **_derived_source_basis(paths),
            "state_event_basis_sequence": 999,
        },
    )
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal, envelope=stale_seq_envelope
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
    assert "stale" in payload["error"]
    assert "sequence mismatch" in payload["error"]

    # Stale digest
    stale_digest_envelope = _obligation_envelope(
        paths,
        derived_basis={
            **_derived_source_basis(paths),
            "source_basis_digest": "sha256:0123456789abcdef" * 4,
        },
    )
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal, envelope=stale_digest_envelope
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
    assert "stale" in payload["error"]
    assert "source_basis_digest mismatch" in payload["error"]


def test_cli_submit_wrong_goal_obligation_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)

    wrong_goal_envelope = _obligation_envelope(paths, goal_id="goal_sibling")
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal, envelope=wrong_goal_envelope
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
    assert "goal_id mismatch" in payload["error"]


def test_cli_submit_valid_receipt_bound_obligation_admitted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)

    valid_envelope = _obligation_envelope(paths, goal_id=GOAL_ID)
    proposal_json, obligations_json = _write_submit_inputs(
        tmp_path, paths, proposal, envelope=valid_envelope
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
