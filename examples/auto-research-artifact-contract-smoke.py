#!/usr/bin/env python3
"""Smoke-test the auto-research artifact packet projection."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.legacy_core import (  # noqa: E402
    AUTO_RESEARCH_ARTIFACT_PACKET_SCHEMA_VERSION,
    RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION,
    build_auto_research_projection,
    build_research_artifact_packet,
    build_research_evidence_graph_from_rollout_events,
    load_auto_research_fixture,
)
from loopx.capabilities.auto_research.evidence_packet import (  # noqa: E402
    AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION,
    build_auto_research_evidence_packet,
    build_auto_research_rollout_events,
)


GOAL_ID = "loopx-auto-research-knn"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def sample_contract() -> dict[str, Any]:
    return {
        "schema_version": "research_contract_v0",
        "goal_id": GOAL_ID,
        "research_objective": "Select a public-safe exact k-NN candidate for promotion.",
        "editable_scope": ["solution_candidate.py"],
        "protected_scope": ["protected_eval.py"],
        "metric": {"name": "speedup", "direction": "maximize", "baseline": 1.0},
        "dev_eval": "python3 protected_eval.py --split dev",
        "holdout_eval": "python3 protected_eval.py --split holdout",
        "promotion_policy": "requires_holdout_improvement_and_clean_boundary",
    }


def eval_result(split: str, value: float) -> dict[str, Any]:
    return {
        "split": split,
        "metric": {"name": "speedup", "direction": "maximize", "value": value, "baseline": 1.0},
        "baseline_metric": 1.0,
        "eval_status": "scored",
        "primary_metric_status": "improved",
        "protected_scope_clean": True,
        "no_upload": True,
        "artifact_refs": [f"public-report:hyp_partial_selection:{split}"],
    }


def assert_artifact_contract(
    packet: dict[str, Any],
    *,
    rollout_backed: bool,
    expected_negative_count: int,
    expected_claim_id: str,
) -> None:
    assert packet["ok"] is True, packet
    assert packet["schema_version"] == AUTO_RESEARCH_ARTIFACT_PACKET_SCHEMA_VERSION, packet
    assert packet["goal_id"] == GOAL_ID, packet
    assert packet["rollout_backed"] is rollout_backed, packet
    assert packet["source_map"], packet
    assert packet["claim_ledger"], packet
    assert packet["citation_packet"]["items"], packet
    assert packet["citation_packet"]["raw_source_bodies_included"] is False, packet
    assert packet["decision_packet"]["recommended_decision"] == "review_promotion_candidate", packet
    assert packet["decision_packet"]["promotion_candidates"], packet
    assert packet["decision_packet"]["requires_operator_gate"] is True, packet
    assert packet["contradiction_review"]["negative_evidence_count"] == expected_negative_count, packet
    assert packet["public_boundary"]["raw_logs_recorded"] is False, packet
    assert packet["public_boundary"]["private_artifacts_recorded"] is False, packet
    assert packet["public_boundary"]["raw_source_bodies_recorded"] is False, packet
    assert any(
        item["supports_claim_id"] == expected_claim_id
        for item in packet["citation_packet"]["items"]
    ), packet
    assert_public_safe(packet)


def main() -> int:
    evidence_packet = build_auto_research_evidence_packet(
        contract=sample_contract(),
        eval_results=[eval_result("dev", 1.4), eval_result("holdout", 1.2)],
        hypothesis_id="hyp_partial_selection",
        todo_id="todo_auto_research_pack_001",
        agent_id="codex-side-bypass",
        claimed_by="codex-side-bypass",
        mechanism_family="partial_selection",
        hypothesis="Use exact partial selection to avoid full distance sorting.",
        grounding_refs=["knn_pack_public_contract"],
        branch_ref="codex/auto-research-artifact-contract-smoke",
    )
    assert evidence_packet["schema_version"] == AUTO_RESEARCH_EVIDENCE_PACKET_SCHEMA_VERSION
    rollout_events = build_auto_research_rollout_events(evidence_packet)
    graph = build_research_evidence_graph_from_rollout_events(
        goal_id=GOAL_ID,
        rollout_events=rollout_events,
    )
    assert graph["schema_version"] == RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION
    assert graph["source_kind"] == "loopx_rollout_event_log", graph

    artifact_packet = build_research_artifact_packet(
        graph,
        question="Which exact k-NN candidate should be promoted?",
    )
    assert_artifact_contract(
        artifact_packet,
        rollout_backed=True,
        expected_negative_count=0,
        expected_claim_id="claim:hyp_partial_selection",
    )

    fixture = load_auto_research_fixture(REPO_ROOT / "examples/fixtures/decentralized-auto-research-knn.public.json")
    fixture_projection = build_auto_research_projection(fixture, agent_id="codex-side-bypass")
    assert "artifact_packet" in fixture_projection, fixture_projection
    assert_artifact_contract(
        fixture_projection["artifact_packet"],
        rollout_backed=False,
        expected_negative_count=1,
        expected_claim_id="claim:hyp_001",
    )

    markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "auto-research",
            "frontier",
            "--fixture",
            "examples/fixtures/decentralized-auto-research-knn.public.json",
            "--agent-id",
            "codex-side-bypass",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "artifact packet: `auto_research_artifact_packet_v0`" in markdown, markdown
    assert "source map entries:" in markdown, markdown
    assert "claim ledger entries:" in markdown, markdown
    assert "citation items:" in markdown, markdown
    assert "recommended decision:" in markdown, markdown
    assert_public_safe(markdown)

    print("auto-research-artifact-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
