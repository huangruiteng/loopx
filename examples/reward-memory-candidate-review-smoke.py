#!/usr/bin/env python3
"""Smoke-test the stateless Stage-2 candidate and review seam."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.reward_memory import (  # noqa: E402
    build_reward_memory_candidate,
    issue_fix_verified_contributor_candidate_fixture,
    review_reward_memory_candidate,
)


def run_cli(*args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def review(decision: str, **extra: str) -> dict[str, str]:
    return {
        "decision": decision,
        "reviewer_ref": "github:user:maintainer",
        "review_ref": f"review:smoke:{decision}",
        "reasoning_summary": "The scoped candidate was reviewed.",
        **extra,
    }


def expect_value_error(callable_) -> None:
    try:
        callable_()
    except ValueError:
        return
    raise AssertionError("expected a ValueError")


def main() -> int:
    adapter = issue_fix_verified_contributor_candidate_fixture()
    assert adapter["schema_version"] == ("issue_fix_reward_memory_candidate_adapter_v0")
    assert adapter["adapter_role"] == (
        "field_mapping_only_shared_core_owns_semantics_and_lifecycle"
    )
    assert adapter["fresh_execution_context_source"] == ("existing_loopx_control_plane")
    candidate = adapter["shared_candidate"]
    assert candidate["schema_version"] == "reward_memory_candidate_v0"
    assert candidate["status"] == "review_ready"
    assert candidate["guard"]["passed"] is True
    assert candidate["guard"]["semantic_reasoning_preserved"] is True
    assert candidate["candidate"]["target_class"] == "hard_policy"
    assert candidate["candidate"]["requested_action_scopes"] == [
        "issue_fix:scope_selection"
    ]
    assert candidate["candidate"]["guard_context"] == {
        "source_freshness": "current",
        "conflict_state": "clear",
        "current_artifact_verified": True,
    }
    assert candidate["authority_checkpoint"]["action_scopes"] == [
        "issue_fix:scope_selection"
    ]
    assert candidate["candidate_persisted"] is False
    assert candidate["provider_write_performed"] is False

    accepted = review_reward_memory_candidate(candidate, review("accept"))
    assert accepted["effective_decision"] == "accept"
    assert accepted["status"] == "active"
    assert accepted["record"]["lifecycle"]["state"] == "active"
    assert accepted["grants_new_action_authority"] is False
    assert accepted["persistence_next_step"] == (
        "caller_uses_declared_corpus_write_authority_then_readback"
    )
    assert accepted["provider_write_performed"] is False

    retired = review_reward_memory_candidate(accepted, review("retire"))
    assert retired["status"] == "retired"
    assert retired["record"]["lifecycle"]["state"] == "retired"

    edited = review_reward_memory_candidate(
        candidate,
        review(
            "edit",
            edited_content_summary=(
                "Keep focused fixes within the affected module unless current "
                "evidence requires a broader surface."
            ),
        ),
    )
    assert edited["status"] == "review_ready"
    assert (
        edited["record"]["candidate_ref"] != (candidate["candidate"]["candidate_ref"])
    )
    assert edited["record"]["lifecycle"]["supersedes_refs"] == [
        candidate["candidate"]["candidate_ref"]
    ]
    accepted_edit = review_reward_memory_candidate(edited, review("accept"))
    assert accepted_edit["record"]["lifecycle"]["supersedes_refs"] == [
        candidate["candidate"]["candidate_ref"]
    ]

    rejected = review_reward_memory_candidate(candidate, review("reject"))
    assert rejected["status"] == "rejected"
    no_write = review_reward_memory_candidate(candidate, review("no_write"))
    assert no_write["status"] == "no_write"
    assert no_write["persistence_next_step"] == "none"

    unverified = deepcopy(candidate)
    unverified["authority_checkpoint"]["verified"] = False
    unverified["authority_checkpoint"]["source_ref"] = None
    proposal = deepcopy(unverified["candidate"])
    proposal.pop("schema_version")
    proposal.pop("candidate_ref")
    proposal.pop("lifecycle")
    proposal.pop("privacy")
    proposal["raw_content_captured"] = False
    blocked = build_reward_memory_candidate(
        proposal,
        authority_checkpoint=unverified["authority_checkpoint"],
    )
    assert blocked["status"] == "guard_blocked"
    blocked_review = review_reward_memory_candidate(blocked, review("accept"))
    assert blocked_review["requested_decision"] == "accept"
    assert blocked_review["effective_decision"] == "no_write"
    assert blocked_review["status"] == "guard_blocked"
    assert blocked_review["persistence_next_step"] == "none"
    blocked_retry = review_reward_memory_candidate(blocked_review, review("accept"))
    assert blocked_retry["effective_decision"] == "no_write"
    assert blocked_retry["guard_passed"] is False

    widened = deepcopy(proposal)
    widened["requested_action_scopes"] = [
        "issue_fix:scope_selection",
        "repository:publish",
    ]
    widened_packet = build_reward_memory_candidate(
        widened,
        authority_checkpoint=candidate["authority_checkpoint"],
    )
    assert (
        "requested_action_scope_exceeds_verified_authority"
        in (widened_packet["guard"]["reason_codes"])
    )

    conflicted = deepcopy(proposal)
    conflicted["guard_context"]["conflict_state"] = "unresolved"
    conflicted_packet = build_reward_memory_candidate(
        conflicted,
        authority_checkpoint=candidate["authority_checkpoint"],
    )
    assert (
        "unresolved_higher_authority_conflict"
        in conflicted_packet["guard"]["reason_codes"]
    )

    advisory = deepcopy(proposal)
    advisory["target_class"] = "soft_preference"
    advisory_packet = build_reward_memory_candidate(advisory)
    assert advisory_packet["status"] == "guard_blocked"
    assert (
        "advisory_class_requested_action_authority"
        in (advisory_packet["guard"]["reason_codes"])
    )

    raw = deepcopy(proposal)
    raw["raw_content_captured"] = True
    expect_value_error(lambda: build_reward_memory_candidate(raw))
    expect_value_error(
        lambda: review_reward_memory_candidate(candidate, review("retire"))
    )

    cli_accept = run_cli(
        "reward-memory",
        "candidate-review",
        "--case",
        "issue-fix-verified-contributor",
        "--decision",
        "accept",
    )
    assert cli_accept["status"] == "active"
    assert cli_accept["adapter"]["shared_candidate"]["status"] == "review_ready"
    cli_retire = run_cli(
        "reward-memory",
        "candidate-review",
        "--decision",
        "retire",
    )
    assert cli_retire["status"] == "retired"
    assert cli_retire["external_writes_performed"] is False

    assert adapter["provider_write_performed"] is False
    assert adapter["external_writes_performed"] is False
    assert adapter["raw_content_captured"] is False
    print("reward-memory-candidate-review-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
