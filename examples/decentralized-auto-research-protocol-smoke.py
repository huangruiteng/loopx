#!/usr/bin/env python3
"""Smoke-check the decentralized auto-research protocol docs.

This guards the durable product contract: Arbor-inspired auto research must
remain LoopX-native and decentralized, with todo-linked hypotheses,
agent-scoped frontiers, split-aware evidence, and no public/private leakage.
"""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/reference/protocols/decentralized-auto-research-state-v0.md"
LANE_CONTRACT = ROOT / "docs/reference/protocols/auto-research-lane-contract-v1.md"
ROLE_STATE_MACHINE = ROOT / "docs/reference/protocols/auto-research-role-state-machine-v0.md"
PROTOCOL_README = ROOT / "docs/reference/protocols/README.md"
BLUEPRINT = ROOT / "docs/product/decentralized-auto-research-showcase.md"


PRIVATE_MARKERS = [
    "byte" + "dance",
    "lark" + "office",
    "fei" + "shu.cn",
    "/" + "Users" + "/",
    "/" + "private" + "/",
    "api" + "_key",
    "pass" + "word",
    "sec" + "ret",
]


def _read(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def _assert_public_safe(text: str, label: str) -> None:
    lower = text.lower()
    for marker in PRIVATE_MARKERS:
        assert marker.lower() not in lower, f"{label} leaks private marker {marker!r}"


def main() -> None:
    protocol = _read(PROTOCOL)
    lane_contract = _read(LANE_CONTRACT)
    role_state_machine = _read(ROLE_STATE_MACHINE)
    protocol_readme = _read(PROTOCOL_README)
    blueprint = _read(BLUEPRINT)
    combined = (
        protocol
        + "\n"
        + lane_contract
        + "\n"
        + role_state_machine
        + "\n"
        + protocol_readme
        + "\n"
        + blueprint
    )
    compact_protocol = re.sub(r"\s+", " ", protocol)
    compact_lane_contract = re.sub(r"\s+", " ", lane_contract)
    compact_role_state_machine = re.sub(r"\s+", " ", role_state_machine)

    _assert_public_safe(combined, "decentralized auto-research docs")

    required_protocol_terms = [
        "decentralized_auto_research_state_v0",
        "research_contract_v0",
        "research_hypothesis_v0",
        "research_evidence_event_v0",
        "decentralized_research_frontier_v0",
        "auto_research_artifact_packet_v0",
        "source_map",
        "claim_ledger",
        "contradiction_review",
        "citation_packet",
        "decision_packet",
        "rollout_backed",
        "agent_lane_next_action_v0",
        "claimed_by",
        "todo_id",
        "agent_id",
        "needs_retry",
        "held-out",
        "grounded_ideation",
        "novelty_audit",
    ]
    for term in required_protocol_terms:
        assert term in protocol, f"protocol missing {term!r}"
    assert "No agent owns the whole research tree" in compact_protocol
    assert "auto_research_lane_contract_v1" in protocol
    assert "auto_research_role_state_machine_v0" in protocol
    assert "auto_research_lane_contract_v1" in protocol_readme
    assert "auto_research_role_state_machine_v0" in protocol_readme

    required_lane_terms = [
        "auto_research_lane_contract_v1",
        "research_curator",
        "hypothesis_proposer",
        "research_executor",
        "evaluator_promoter",
        "product_narrator",
        "auto_research_lane_claim_v1",
        "research_contract_v0",
        "research_hypothesis_v0",
        "auto_research_evidence_packet_v0",
        "research_evidence_event_v0",
        "research_evidence_graph_v0",
        "research_showcase_projection_v0",
        "quota should-run --agent-id",
        "first-screen review gate",
    ]
    for term in required_lane_terms:
        assert term in lane_contract, f"lane contract missing {term!r}"
    assert "No lane is privileged" in compact_lane_contract
    assert "not a lock on the full graph" in compact_lane_contract
    assert "no public surface needs a leader or coordinator agent" in compact_lane_contract

    required_role_state_machine_terms = [
        "auto_research_role_state_machine_v0",
        "auto_research_state_transition_v0",
        "Research curator",
        "Hypothesis mapper",
        "Evidence runner",
        "Evidence verifier",
        "always-on role set small",
        "transition duties",
        "Read-only projection builder",
        "Future Role Splits",
        "Gate steward",
        "Synthesis narrator",
        "Frontier janitor",
        "contract_ready",
        "hypothesis_proposed",
        "frontier_selected",
        "attempt_running",
        "evidence_recorded",
        "evaluated",
        "promotion_gate",
        "research_showcase_projection_v0",
        "quota should-run --agent-id",
        "operator_gate",
        "todo_id",
        "claimed_by",
        "No role owns the full graph",
    ]
    for term in required_role_state_machine_terms:
        assert term in role_state_machine, f"role state machine missing {term!r}"
    assert "not a coordinator" in compact_role_state_machine
    assert "not start Codex, write LoopX state, or spend quota" in compact_role_state_machine
    assert "Future versions may split gate stewardship" in compact_role_state_machine
    assert "outside the v0 always-on role set" in compact_role_state_machine
    assert "Promoting any future role requires a smoke update" in compact_role_state_machine
    assert "Gate handling is a transition duty" in compact_role_state_machine
    for future_role in ("Frontier janitor", "Synthesis narrator", "Gate steward"):
        assert f"| {future_role} |" in role_state_machine, f"future split missing {future_role}"

    required_blueprint_terms = [
        "Decentralized Auto Research: k-NN Speedup",
        "not a claim that LoopX has already achieved",
        "Research Contract card",
        "Decentralized frontier",
        "Evidence timeline",
        "Promotion decision",
        "no leader agent owns the graph",
        "auto_research_lane_contract_v1",
        "auto_research_role_state_machine_v0",
        "curator",
        "hypothesis proposer",
        "executor",
        "evaluator/promoter",
        "product narrator",
    ]
    for term in required_blueprint_terms:
        assert term in blueprint, f"blueprint missing {term!r}"

    forbidden_patterns = [
        r"single leader agent owns",
        r"leader agent owns the full",
        r"leader agent.*full hypothesis graph",
        r"central Coordinator owns",
        r"Coordinator owns the tree",
        r"Coordinator.*promotion decisions live",
        r"single agent owns the whole research tree",
        r"supervisor owns the full",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, combined, re.IGNORECASE), (
            f"docs drifted toward centralized wording: {pattern}"
        )

    assert "not one leader Coordinator" in blueprint or "no leader agent" in blueprint
    print("decentralized auto-research protocol smoke passed")


if __name__ == "__main__":
    main()
