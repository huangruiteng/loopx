from __future__ import annotations

import copy
import json

import pytest

from loopx.capabilities.review_batch import (
    bind_review_batch_decisions,
    build_review_batch,
)
from loopx.cli import main


def _request() -> dict[str, object]:
    return {
        "schema_version": "review_batch_request_v0",
        "batch_id": "maintainer_daily_001",
        "generated_at": "2026-07-15T10:00:00Z",
        "policy": {
            "soft_limit": 2,
            "hard_limit": 3,
            "priority_reason_order": [
                "correctness_risk",
                "user_impact",
                "evidence_ready",
            ],
            "decision_values": ["approve", "revise", "hold", "skip"],
        },
        "candidate_sources": [
            {
                "source_id": "change_queue",
                "source_kind": "change_request",
                "candidates": [
                    {
                        "candidate_id": "change_2",
                        "source_ref": "public:change/2",
                        "title": "Small verified correction",
                        "summary": "A bounded change with focused evidence.",
                        "priority_tier": 1,
                        "priority_reasons": [
                            {"code": "evidence_ready", "detail": "Focused checks passed."}
                        ],
                        "evidence_status": "verified",
                        "evidence_refs": ["public:check/2"],
                        "proposal": {"action": "Route to human review."},
                    },
                    {
                        "candidate_id": "change_1",
                        "source_ref": "public:change/1",
                        "title": "Correctness risk",
                        "summary": "A behavior change with a known correctness concern.",
                        "priority_tier": 0,
                        "priority_reasons": [
                            {
                                "code": "correctness_risk",
                                "detail": "Current evidence exposes a correctness gap.",
                            }
                        ],
                        "evidence_status": "needs_revision",
                        "evidence_refs": ["public:review/1"],
                        "proposal": {"draft": "Please address the focused blocker."},
                    },
                ],
            },
            {
                "source_id": "question_queue",
                "source_kind": "response_draft",
                "candidates": [
                    {
                        "candidate_id": "question_1",
                        "source_ref": "public:question/1",
                        "title": "Evidence request",
                        "summary": "A response draft that asks for missing evidence.",
                        "priority_tier": 1,
                        "priority_reasons": [
                            {"code": "user_impact", "detail": "The report is user-visible."}
                        ],
                        "evidence_status": "missing_evidence",
                        "evidence_refs": [],
                        "proposal": {"action": "Request bounded diagnostics."},
                    }
                ],
            },
        ],
        "sink_receipts": [
            {
                "sink_id": "owner_document",
                "sink_kind": "managed_document",
                "status": "preview",
                "readback_verified": False,
            }
        ],
    }


def test_review_batch_is_bounded_deterministic_and_provider_neutral() -> None:
    request = _request()
    first = build_review_batch(request)
    reversed_request = copy.deepcopy(request)
    reversed_request["candidate_sources"] = list(
        reversed(reversed_request["candidate_sources"])
    )
    for source in reversed_request["candidate_sources"]:
        source["candidates"] = list(reversed(source["candidates"]))
    second = build_review_batch(reversed_request)

    assert first["schema_version"] == "review_batch_v0"
    assert [item["candidate_id"] for item in first["candidates"]] == [
        "change_1",
        "question_1",
    ]
    assert first["candidate_counts"] == {
        "input": 3,
        "within_hard_limit": 3,
        "selected": 2,
        "overflow": 1,
    }
    assert first["decision_digest"] == second["decision_digest"]
    assert first["boundary"] == {
        "provider_neutral": True,
        "raw_content_persisted": False,
        "external_writes_performed": False,
        "candidate_adapters_execute_outside_core": True,
        "sink_delivery_executes_outside_core": True,
    }
    encoded = json.dumps(first, sort_keys=True)
    assert "github" not in encoded.lower()
    assert "lark" not in encoded.lower()
    assert "openviking" not in encoded.lower()


def test_sent_sink_receipt_requires_idempotency_and_readback() -> None:
    request = _request()
    request["sink_receipts"] = [
        {
            "sink_id": "owner_document",
            "sink_kind": "managed_document",
            "status": "sent",
            "receipt_ref": "public:receipt/1",
            "readback_verified": True,
        }
    ]
    with pytest.raises(ValueError, match="sent receipts require idempotency_key"):
        build_review_batch(request)


def test_raw_content_and_unregistered_reason_are_rejected() -> None:
    raw_request = _request()
    raw_request["candidate_sources"][0]["candidates"][0]["raw_body"] = "do not persist"
    with pytest.raises(ValueError, match="forbidden raw/private field"):
        build_review_batch(raw_request)

    reason_request = _request()
    reason_request["candidate_sources"][0]["candidates"][0]["priority_reasons"] = [
        "provider_specific_magic"
    ]
    with pytest.raises(ValueError, match="unregistered code"):
        build_review_batch(reason_request)


def test_bind_decisions_requires_exact_batch_and_candidate_digests() -> None:
    batch = build_review_batch(_request())
    candidate = batch["candidates"][0]
    decisions = {
        "schema_version": "review_batch_decisions_v0",
        "decision_digest": batch["decision_digest"],
        "decisions": [
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_decision_digest": candidate["decision_digest"],
                "decision": "revise",
                "note": "Keep the current blocker focused.",
            }
        ],
    }
    receipt = bind_review_batch_decisions(batch, decisions)

    assert receipt["schema_version"] == "review_batch_decision_receipt_v0"
    assert receipt["boundary"]["exact_digest_binding"] is True
    assert receipt["boundary"]["external_writes_performed"] is False

    stale = copy.deepcopy(decisions)
    stale["decisions"][0]["candidate_decision_digest"] = "candidate_stale"
    with pytest.raises(ValueError, match="does not match candidate"):
        bind_review_batch_decisions(batch, stale)

    raw_decision = copy.deepcopy(decisions)
    raw_decision["decisions"][0]["raw_message"] = "do not persist"
    with pytest.raises(ValueError, match="forbidden raw/private field"):
        bind_review_batch_decisions(batch, raw_decision)


def test_bind_decisions_recomputes_batch_and_candidate_integrity() -> None:
    batch = build_review_batch(_request())
    candidate = batch["candidates"][0]
    decisions = {
        "schema_version": "review_batch_decisions_v0",
        "decision_digest": batch["decision_digest"],
        "decisions": [
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_decision_digest": candidate["decision_digest"],
                "decision": "approve",
            }
        ],
    }

    tampered_candidate = copy.deepcopy(batch)
    tampered_candidate["candidates"][0]["proposal"] = {
        "action": "A different action inserted after composition."
    }
    with pytest.raises(ValueError, match="batch candidate digest does not match"):
        bind_review_batch_decisions(tampered_candidate, decisions)

    tampered_policy = copy.deepcopy(batch)
    tampered_policy["policy"]["decision_values"].append("delete")
    tampered_decisions = copy.deepcopy(decisions)
    tampered_decisions["decisions"][0]["decision"] = "delete"
    with pytest.raises(ValueError, match="batch decision digest does not match"):
        bind_review_batch_decisions(tampered_policy, tampered_decisions)


def test_review_batch_cli_composes_json(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert main(["--format", "json", "review-batch", "compose", "--request-json", str(request_path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "review_batch_v0"
    assert payload["candidate_counts"]["selected"] == 2
