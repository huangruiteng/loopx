#!/usr/bin/env python3
"""Smoke-check the goal vision/replan contract stays compact and reusable."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "reference" / "protocols" / "goal-vision-replan-contract-v0.md"
PROTOCOL_INDEX = ROOT / "docs" / "reference" / "protocols" / "README.md"
DOCS_INDEX = ROOT / "docs" / "README.md"
STATE_MACHINE = ROOT / "docs" / "product" / "core-control-plane" / "state-machine.md"
RULE_SEAM = ROOT / "docs" / "product" / "core-control-plane" / "rule-seam-map.md"
THREE_LAYER = ROOT / "docs" / "reference" / "protocols" / "multi-agent-three-layer-minimality-v0.md"


PRIVATE_MARKERS = [
    "byte" + "dance",
    "lark" + "office",
    "/" + "Users" + "/",
    "/" + "private" + "/",
    "/" + "tmp" + "/",
    "api" + "_key",
    "pass" + "word",
    "sec" + "ret",
]


def read(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def require(text: str, snippets: list[str], *, source: Path) -> None:
    compact = " ".join(text.split())
    missing = [
        snippet for snippet in snippets if snippet not in text and " ".join(snippet.split()) not in compact
    ]
    assert not missing, f"{source}: missing {missing}"


def assert_public_safe(text: str, label: str) -> None:
    lower = text.lower()
    leaked = [marker for marker in PRIVATE_MARKERS if marker.lower() in lower]
    assert not leaked, f"{label} leaks private markers: {leaked}"


def main() -> int:
    protocol = read(PROTOCOL)
    protocol_index = read(PROTOCOL_INDEX)
    docs_index = read(DOCS_INDEX)
    state_machine = read(STATE_MACHINE)
    rule_seam = read(RULE_SEAM)
    three_layer = read(THREE_LAYER)

    assert_public_safe(
        "\n".join([protocol, protocol_index, docs_index, state_machine, rule_seam, three_layer]),
        "goal vision/replan docs",
    )

    require(
        protocol,
        [
            "goal_vision_replan_contract_v0",
            "CLI Budget",
            "`vision_summary` | 420",
            "`total_agent_vision` | 1200",
            "Reject over-budget writes with `vision_budget_exceeded`",
            "Do not silently truncate fields",
            "Long reasoning belongs in evidence artifacts or design docs",
            "`loopx refresh-state --agent-vision-json",
            "`goal_vision_patch` repair delta",
            "State Machine",
            "ActiveVision --> VisionDriftDetected",
            "ReplanRequired --> ReplanDrafted",
            "VisionPatchProposed --> ActiveVision",
            "The replan decision must not be disturbed by monitor quiet skip",
            "Bad Case: ACK Hidden By Scheduler Accounting",
            "status must project the newest durable replan ACK across neutral",
            "An acknowledgement without a vision, todo, acceptance, or no-follow-up delta is",
            "`replan_noop`",
            "durable replan ACKs survive neutral scheduler/accounting runs",
            "`quota.py` consumes the resulting projection instead of storing vision logic",
        ],
        source=PROTOCOL,
    )
    require(
        state_machine,
        [
            "Agent Vision / Replan Machine",
            "required replan is evaluated before",
            "An acknowledgement without a vision, todo, acceptance, or no-follow-up",
            "goal-vision-replan-contract-v0.md",
        ],
        source=STATE_MACHINE,
    )
    require(
        rule_seam,
        [
            "Agent vision and goal routing contract",
            "Over-budget vision fails or compacts before status/quota",
            "rather than expanding `quota.py`",
            "Per-agent vision is a bounded goal-routing contract",
        ],
        source=RULE_SEAM,
    )
    require(
        three_layer,
        [
            "per-agent vision/replan state",
            "per-agent vision budgets",
            "vision/replan state transitions",
            "product-specific fork of per-agent vision/replan mechanics",
        ],
        source=THREE_LAYER,
    )
    require(
        protocol_index,
        ["goal_vision_replan_contract_v0", "goal-vision-replan-contract-v0.md"],
        source=PROTOCOL_INDEX,
    )
    require(
        docs_index,
        ["Goal vision replan contract v0", "reference/protocols/goal-vision-replan-contract-v0.md"],
        source=DOCS_INDEX,
    )

    print("goal-vision-replan-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
