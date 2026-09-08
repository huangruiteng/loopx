from __future__ import annotations

import copy
import json

import pytest

from loopx.capabilities.pr_review_queue import review_contract
from loopx.capabilities.pr_review_queue.result_check import check_review_result
from loopx.capabilities.pr_review_queue.review_contract import (
    build_review_execution_contract,
    build_review_plan,
)
from loopx.cli import main


def _review():
    item = {"number": 42, "head_oid": "a" * 40, "areas": {"product_runtime": 1}}
    result = build_review_plan(item)["result_template"]
    requirements = {
        row["evidence_id"]: row
        for row in build_review_execution_contract()["evidence_requirements"]
    }
    for key, row in result["evidence"].items():
        row.update(
            status="verified",
            evidence="Synthetic consistency fixture, not a real review.",
            **{
                field: "Synthetic consistency fixture, not a real review."
                for field in requirements[key].get("fields", [])
            },
        )
        if "verdict_values" in requirements[key]:
            row["verdict"] = requirements[key]["verdict_values"][0]
    result["verdict"] = "APPROVE"
    return {"pull_requests": [item]}, result


def test_result_check_is_not_semantic_or_merge_authority():
    packet, result = _review()
    checked = check_review_result(packet, result)
    assert checked["ok"] and checked["approval_consistent"]
    assert not checked["evidence_truth_verified"]
    assert not checked["remote_head_verified"]
    assert not checked["external_writes_performed"]


@pytest.mark.parametrize(
    "kind", ["missing", "unverified", "empty", "blocking", "finding", "unknown_verdict"]
)
def test_approval_cannot_hide_missing_or_contradictory_evidence(kind):
    packet, result = _review()
    row = result["evidence"]["change_proportionality"]
    if kind == "missing":
        del result["evidence"]["change_proportionality"]
    elif kind == "unverified":
        row["status"] = "unverified"
    elif kind == "empty":
        for field in list(row):
            if field not in {"status", "verdict"}:
                del row[field]
    elif kind == "blocking":
        row["verdict"] = "disproportionate"
    elif kind == "unknown_verdict":
        row["verdict"] = "looks_good"
    else:
        result["findings"] = [{"severity": "P1", "blocking": False}]
    # Caller cannot weaken the policy by changing its saved plan/contract.
    packet["pull_requests"][0]["review_plan"] = {"required_evidence_ids": []}
    packet["agent_response_contract"] = {"review_execution_contract": {}}
    checked = check_review_result(packet, result)
    assert not checked["ok"]
    assert "approval_contradicts_evidence" in checked["errors"]
    result["verdict"] = "REQUEST_CHANGES"
    assert check_review_result(packet, result)["ok"]


def test_nonblocking_suggestion_does_not_force_rejection():
    packet, result = _review()
    result["findings"] = [{"severity": "P2", "blocking": False}]
    assert check_review_result(packet, result)["approval_consistent"]


@pytest.mark.parametrize("revision", [None, 0, True, "1", 999])
def test_old_or_invalid_policy_cannot_certify_current_approval(revision):
    packet, result = _review()
    result["review_policy_revision"] = revision
    checked = check_review_result(packet, result)
    assert "review_policy_revision:stale_or_missing" in checked["approval_blockers"]
    assert not checked["ok"]
    result["verdict"] = "REQUEST_CHANGES"
    assert check_review_result(packet, result)["ok"]


def test_pinned_result_is_rejected_after_installed_policy_bump(monkeypatch):
    packet, result = _review()
    pinned_revision = result["review_policy_revision"]
    monkeypatch.setattr(
        review_contract,
        "REVIEW_POLICY_REVISION",
        pinned_revision + 1,
    )

    checked = check_review_result(packet, result)

    assert "review_policy_revision:stale_or_missing" in checked["approval_blockers"]
    assert not checked["ok"]
    result["verdict"] = "REQUEST_CHANGES"
    assert check_review_result(packet, result)["ok"]


def test_verified_label_and_generic_prose_do_not_replace_rule_ownership():
    packet, result = _review()
    del result["evidence"]["repository_reuse"]["rule_ownership"]
    result["evidence"]["repository_reuse"]["evidence"] = "All providers passed."
    checked = check_review_result(packet, result)
    assert "repository_reuse:missing_field:rule_ownership" in checked["approval_blockers"]
    assert not checked["ok"]
    result["verdict"] = "REQUEST_CHANGES"
    assert check_review_result(packet, result)["ok"]


@pytest.mark.parametrize("mutation", ["head", "duplicate", "shape"])
def test_saved_head_must_match_exactly_once(mutation):
    packet, result = _review()
    if mutation == "head":
        result["target_exact_head"] = "42@" + "b" * 40
    elif mutation == "duplicate":
        packet["pull_requests"].append(copy.deepcopy(packet["pull_requests"][0]))
    else:
        packet["pull_requests"] = {}
    with pytest.raises((ValueError, TypeError)):
        check_review_result(packet, result)


def test_public_cli_check_has_no_github_or_checkpoint_effects(
    tmp_path, monkeypatch, capsys
):
    packet, result = _review()
    packet_path, result_path = tmp_path / "packet.json", tmp_path / "result.json"
    packet_path.write_text(json.dumps(packet))
    result_path.write_text(json.dumps(result))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(
        "loopx.cli_commands.pr_review.resolve_current_github_repository",
        lambda: pytest.fail("result check must not discover GitHub"),
    )
    argv = [
        "--format",
        "json",
        "pr-review",
        "--check-result",
        str(result_path),
        "--packet",
        str(packet_path),
    ]
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["approval_consistent"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    result["evidence"]["failure_analysis"]["status"] = "unverified"
    result_path.write_text(json.dumps(result))
    assert main(argv) == 1
    assert not json.loads(capsys.readouterr().out)["approval_consistent"]


def test_unreadable_check_input_does_not_expose_local_path(tmp_path, capsys):
    path = tmp_path / "not-present.json"
    assert (
        main(
            [
                "--format",
                "json",
                "pr-review",
                "--check-result",
                str(path),
                "--packet",
                str(path),
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert str(tmp_path) not in output
    assert "unreadable" in json.loads(output)["error"]
