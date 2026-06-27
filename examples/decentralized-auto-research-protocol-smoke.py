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
    blueprint = _read(BLUEPRINT)
    combined = protocol + "\n" + blueprint
    compact_protocol = re.sub(r"\s+", " ", protocol)

    _assert_public_safe(combined, "decentralized auto-research docs")

    required_protocol_terms = [
        "decentralized_auto_research_state_v0",
        "research_contract_v0",
        "research_hypothesis_v0",
        "research_evidence_event_v0",
        "decentralized_research_frontier_v0",
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

    required_blueprint_terms = [
        "Decentralized Auto Research: k-NN Speedup",
        "not a claim that LoopX has already achieved",
        "Research Contract card",
        "Decentralized frontier",
        "Evidence timeline",
        "Promotion decision",
        "no leader agent owns the graph",
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
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, combined, re.IGNORECASE), (
            f"docs drifted toward centralized wording: {pattern}"
        )

    assert "not one leader Coordinator" in blueprint or "no leader agent" in blueprint
    print("decentralized auto-research protocol smoke passed")


if __name__ == "__main__":
    main()
