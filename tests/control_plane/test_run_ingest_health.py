from __future__ import annotations

from loopx.control_plane.runtime.run_ingest_health import (
    compact_worker_bridge_outcome,
    worker_bridge_ingest_health_note,
)


def test_compact_worker_bridge_outcome_preserves_public_contract() -> None:
    compact = compact_worker_bridge_outcome(
        {
            "schema_version": "worker_bridge_outcome_v0",
            "bridge_surface": "command_file_bridge",
            "runner_return_status": "completed",
            "official_score_status": "completed",
            "worker_bridge_verified": True,
            "worker_loopx_cli_call_total": 3,
            "official_score_value": 1.0,
            "failure_attribution_labels": ["a", "b", "c", "d", "e", "f"],
            "wall_time_policy": {
                "schema_version": "wall_time_policy_v0",
                "kind": "bounded",
                "interrupted": False,
                "wall_time_seconds": 42.5,
                "private_detail": "drop",
            },
            "claim_boundary": {
                "public_claim_allowed": "bridge connectivity only",
                "bridge_connectivity_claim_allowed": True,
                "forbidden_claims": ["one", "two", "three", "four", "five", "six"],
            },
            "environment_setup_failure_context": {
                "schema_version": "environment_setup_failure_context_v0",
                "surface": "worker_startup",
                "environment_setup_present": True,
                "environment_setup_duration_seconds": 12.0,
                "private_detail": "drop",
            },
            "private_detail": "drop",
        }
    )

    assert compact["schema_version"] == "worker_bridge_outcome_v0"
    assert compact["worker_bridge_verified"] is True
    assert compact["worker_loopx_cli_call_total"] == 3
    assert compact["official_score_value"] == 1.0
    assert compact["failure_attribution_labels"] == ["a", "b", "c", "d", "e"]
    assert compact["wall_time_policy"] == {
        "schema_version": "wall_time_policy_v0",
        "kind": "bounded",
        "interrupted": False,
        "wall_time_seconds": 42.5,
    }
    assert compact["claim_boundary"]["forbidden_claims"] == [
        "one",
        "two",
        "three",
        "four",
        "five",
    ]
    assert compact["environment_setup_failure_context"] == {
        "schema_version": "environment_setup_failure_context_v0",
        "surface": "worker_startup",
        "environment_setup_present": True,
        "environment_setup_duration_seconds": 12.0,
    }
    assert "private_detail" not in compact


def test_worker_bridge_health_uses_compact_outcome() -> None:
    outcome = compact_worker_bridge_outcome(
        {
            "worker_bridge_verified": True,
            "runner_return_status": "completed",
            "official_score_status": "completed",
            "worker_loopx_cli_call_total": 2,
            "required_worker_loopx_cli_call_total_min": 1,
        }
    )

    health = worker_bridge_ingest_health_note(
        {
            "schema_version": "benchmark_run_v0",
            "worker_bridge_outcome": outcome,
            "validation": {"all_passed": True},
        }
    )

    assert health is not None
    assert health["health_state"] == "official_score_ingested"
    assert health["evidence_layer"] == "official_sample_score"
    assert health["validation_all_passed"] is True
