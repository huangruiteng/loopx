#!/usr/bin/env python3
"""Smoke-test the Stage-1 reward-memory corpus registry and health contract."""

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
    build_reward_memory_corpus_health_packet,
    build_reward_memory_corpus_registry_packet,
    reward_memory_health_case,
    semantic_preference_inventory_to_reward_corpora,
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


def expect_value_error(callable_) -> None:
    try:
        callable_()
    except ValueError:
        return
    raise AssertionError("expected a ValueError")


def main() -> int:
    registry = build_reward_memory_corpus_registry_packet()
    assert registry["schema_version"] == "reward_memory_corpus_registry_v0"
    assert registry["status"] == "reference_registry"
    assert registry["corpus_count"] == 7
    assert set(registry["class_coverage"]) == {
        "run_bound_reward",
        "hard_policy",
        "soft_preference",
        "procedural_experience",
        "working_context",
    }
    assert registry["class_coverage"]["procedural_experience"] == [
        "distilled_experiences",
        "execution_trajectories",
    ]
    assert registry["registry_role"] == (
        "stateless_read_model_not_memory_source_of_truth"
    )
    assert registry["raw_memory_captured"] is False
    assert registry["registry_persisted"] is False
    assert registry["external_writes_performed"] is False

    serialized = json.dumps(registry, ensure_ascii=False)
    assert "raw chat" not in serialized.lower()
    assert all(
        item["privacy"]["raw_content_in_registry"] is False
        for item in registry["corpora"]
    )

    preference_inventory = [
        {
            "corpus_id": "project_peer_preferences",
            "scope_ref": "viking://user/example/agents/project/memories/preferences",
            "read_role": "primary",
            "write_mode": "provider_managed",
            "write_actor_ref": "peer:project",
            "source_of_truth": "repository_revision_and_explicit_feedback",
            "writeback_triggers": ["explicit_feedback", "source_truth_changed"],
            "closure_policy": "write_wait_l2_read_scoped_recall",
        }
    ]
    bridged = semantic_preference_inventory_to_reward_corpora(
        preference_inventory,
        provider_id="openviking",
        workspace_ref="workspace:example",
        project_ref="project:example",
        surface="issue_fix.pr_description",
        source_revision="revision:abc123",
    )
    assert bridged["status"] == "registered"
    assert bridged["bridge_schema_version"] == (
        "reward_memory_semantic_preference_registry_bridge_v0"
    )
    bridged_corpus = bridged["corpora"][0]
    assert bridged_corpus["class_id"] == "soft_preference"
    assert bridged_corpus["write_authority"] == "provider_managed"
    assert bridged_corpus["freshness"] == {
        "mode": "revision_bound",
        "source_revision": "revision:abc123",
        "max_age_seconds": None,
    }
    assert bridged_corpus["provider_scope_ref_digest"]
    assert bridged_corpus["maintenance"] == {
        "writeback_triggers": ["explicit_feedback", "source_truth_changed"],
        "closure_policy": "write_wait_l2_read_scoped_recall",
        "retirement_authority": "peer:project",
    }
    assert "viking://" not in json.dumps(bridged), bridged

    expected_states = {
        "unavailable": "unavailable",
        "empty": "empty",
        "stale": "stale",
        "wrong-project": "wrong_project",
        "wrong-surface": "wrong_surface",
        "index-unavailable": "index_unavailable",
        "retrieval-failed": "retrieval_failed",
        "readback-unverified": "readback_unverified",
        "retrieval-verified": "retrieval_verified",
        "applied-verified": "applied_verified",
    }
    health_packets: dict[str, dict[str, object]] = {}
    for case, expected in expected_states.items():
        corpus, observation = reward_memory_health_case(case)
        packet = build_reward_memory_corpus_health_packet(corpus, observation)
        health_packets[case] = packet
        assert packet["health_state"] == expected, packet
        assert packet["memory_patch_authority"] is False
        assert packet["external_write_authorized"] is False
        assert packet["raw_memory_captured"] is False

    assert health_packets["empty"]["pipeline"]["corpus_present"] is True
    assert health_packets["empty"]["pipeline"]["record_count"] == 0
    assert health_packets["index-unavailable"]["pipeline"]["corpus_present"] is True
    assert health_packets["index-unavailable"]["pipeline"]["index_present"] is False
    assert health_packets["retrieval-failed"]["pipeline"]["index_present"] is True
    assert (
        health_packets["readback-unverified"]["pipeline"]["retrieval_query_succeeded"]
        is True
    )
    assert (
        health_packets["readback-unverified"]["pipeline"]["result_readback_verified"]
        is False
    )
    assert health_packets["retrieval-verified"]["may_apply_memory"] is True
    assert (
        health_packets["retrieval-verified"]["pipeline"]["memory_applied_with_receipt"]
        is False
    )
    assert (
        health_packets["applied-verified"]["pipeline"]["memory_applied_with_receipt"]
        is True
    )

    corpus, observation = reward_memory_health_case("retrieval-verified")
    contradictory = observation | {
        "result_readback_verified": False,
        "memory_applied_with_receipt": True,
    }
    expect_value_error(
        lambda: build_reward_memory_corpus_health_packet(corpus, contradictory)
    )

    duplicate = [deepcopy(registry["corpora"][0])] * 2
    expect_value_error(lambda: build_reward_memory_corpus_registry_packet(duplicate))
    unsafe = deepcopy(registry["corpora"][0])
    unsafe["privacy"]["raw_content_in_registry"] = True
    expect_value_error(lambda: build_reward_memory_corpus_registry_packet([unsafe]))

    cli_registry = run_cli("reward-memory", "corpus-registry")
    assert cli_registry["corpus_count"] == 7
    cli_health = run_cli("reward-memory", "health-check", "--case", "wrong-surface")
    assert cli_health["health_state"] == "wrong_surface"
    assert cli_health["may_apply_memory"] is False

    print("reward-memory-corpus-registry-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
