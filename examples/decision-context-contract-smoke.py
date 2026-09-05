#!/usr/bin/env python3
"""Smoke-test the public Decision Context Stage-0 contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.decision_context import (  # noqa: E402
    DecisionSourceSpec,
    build_decision_context_architecture_packet,
    build_decision_evidence_packet,
    build_decision_outcome_receipt,
    build_decision_proposal,
    build_decision_review_receipt,
    build_decision_source_manifest,
)

OBSERVED_AT = "2026-07-25T13:30:00+00:00"
REVIEW_AT = "2026-07-28T13:30:00+00:00"


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


def main() -> int:
    architecture = build_decision_context_architecture_packet()
    assert architecture["capability"]["default_enabled"] is False
    assert architecture["capability"]["creates_authority"] is False
    assert architecture["provider_boundaries"]["provider_failure_policy"] == (
        "fail_open_to_current_authority"
    )
    assert architecture["local_private_transient_schemas"] == [
        "decision_context_ephemeral_recall_v0"
    ]
    assert run_cli("decision-context", "architecture") == architecture

    source = DecisionSourceSpec(
        source_id="source:repository:signals",
        provider_id="repository-provider",
        source_kind="repository",
        priority="p0",
        evidence_level="s1",
        objectives=("adoption",),
        scan_mode="incremental",
        exact_read_policy="material_change",
        freshness_seconds=3600,
        private_locator="private-repository-locator",
    )
    manifest = build_decision_source_manifest(
        goal_id="goal:example",
        observed_at=OBSERVED_AT,
        sources=[source],
    )
    assert "private-repository-locator" not in json.dumps(manifest)

    evidence = build_decision_evidence_packet(
        goal_id="goal:example",
        decision_id="decision:priority",
        observed_at=OBSERVED_AT,
        changed_facts=[
            {
                "fact_id": "fact:pilot",
                "summary": "One bounded pilot produced a current authority receipt.",
                "source_ref": "source:repository:signals",
                "source_revision": "revision:1",
                "observed_at": OBSERVED_AT,
            }
        ],
        provider_health=[
            {
                "provider": "repository-provider",
                "status": "healthy",
                "observed_at": OBSERVED_AT,
                "fail_open": True,
            }
        ],
    )
    proposal = build_decision_proposal(
        goal_id="goal:example",
        decision_id="decision:priority",
        evidence_packet_ref=str(evidence["packet_ref"]),
        observed_at=OBSERVED_AT,
        review_at=REVIEW_AT,
        objective_scores=[
            {
                "objective_id": "objective:adoption",
                "score": 0.8,
                "rationale": "Current outcome evidence supports closing the pilot.",
            }
        ],
        recommended_decision={
            "option_id": "option:close-pilot",
            "summary": "Close the pilot before expanding the protocol.",
            "rationale": "Verified adoption compounds more than another surface.",
            "confidence": 0.8,
        },
    )
    review_receipts = {
        disposition: build_decision_review_receipt(
            goal_id="goal:example",
            decision_id="decision:priority",
            evidence_packet_ref=str(evidence["packet_ref"]),
            proposal_packet_ref=str(proposal["packet_ref"]),
            gate_todo_id=f"todo:review:{disposition}",
            source_event_id=f"event:review:{disposition}",
            recorded_at=REVIEW_AT,
            disposition=disposition,
            actor_ref="owner:goal",
            reason_code=f"owner_{disposition}",
            summary=f"The owner recorded {disposition} through the existing gate.",
        )
        for disposition in ("approve", "reject", "defer")
    }
    review_receipts["no_change"] = build_decision_review_receipt(
        goal_id="goal:example",
        decision_id="decision:priority",
        evidence_packet_ref=str(evidence["packet_ref"]),
        recorded_at=REVIEW_AT,
        disposition="no_change",
        actor_ref="agent:decision-advisor",
        reason_code="no_material_change",
        summary="The source update does not alter the current decision.",
    )
    assert review_receipts["approve"]["outcome_observation_required"] is True
    assert review_receipts["reject"]["outcome_observation_required"] is False
    assert review_receipts["defer"]["outcome_observation_required"] is False
    assert review_receipts["no_change"]["quiet_noop"] is True
    outcome = build_decision_outcome_receipt(
        goal_id="goal:example",
        decision_id="decision:priority",
        proposal_packet_ref=str(proposal["packet_ref"]),
        recorded_at=REVIEW_AT,
        review_at="2026-08-01T13:30:00+00:00",
        verification_status="verified",
        accepted_decision={
            "option_id": "option:close-pilot",
            "summary": "Close the pilot before expanding the protocol.",
            "accepted_by": "owner:goal",
            "accepted_at": OBSERVED_AT,
        },
        observed_outcomes=[
            {
                "outcome_id": "outcome:pilot",
                "summary": "The pilot owner verified one realized outcome.",
                "evidence_ref": "evidence:pilot",
                "status": "verified",
                "observed_at": REVIEW_AT,
            }
        ],
    )
    assert outcome["reward_memory_candidate_eligible"] is True
    assert outcome["capability"]["mutates_core_state"] is False

    print(
        json.dumps(
            {
                "ok": True,
                "schema_version": architecture["schema_version"],
                "manifest_ref": manifest["manifest_ref"],
                "evidence_ref": evidence["packet_ref"],
                "proposal_ref": proposal["packet_ref"],
                "review_refs": {
                    disposition: receipt["packet_ref"]
                    for disposition, receipt in sorted(review_receipts.items())
                },
                "outcome_ref": outcome["packet_ref"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
