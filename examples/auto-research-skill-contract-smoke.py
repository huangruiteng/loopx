#!/usr/bin/env python3
"""Smoke-test the worker-local loopx-auto-research playbook contract."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.doctor import REQUIRED_INSTALLED_SKILL_PHRASES  # noqa: E402


SKILL = ROOT / "loopx" / "capabilities" / "auto_research" / "worker_skill" / "SKILL.md"
ROLE_PROFILE = ROOT / "docs" / "reference" / "protocols" / "auto-research-role-profile-v0.md"
ROLE_STATE_MACHINE = ROOT / "docs" / "reference" / "protocols" / "auto-research-role-state-machine-v0.md"
LANE_CONTRACT = ROOT / "docs" / "reference" / "protocols" / "auto-research-lane-contract-v1.md"
GETTING_STARTED = ROOT / "docs" / "guides" / "getting-started.md"


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
    leaked = [marker for marker in PRIVATE_MARKERS if marker.lower() in lower]
    assert not leaked, f"{label} leaks private marker(s): {leaked}"


def main() -> int:
    skill = _read(SKILL)
    compact_skill = " ".join(skill.split())
    role_profile = _read(ROLE_PROFILE)
    role_state_machine = _read(ROLE_STATE_MACHINE)
    lane_contract = _read(LANE_CONTRACT)
    getting_started = _read(GETTING_STARTED)

    _assert_public_safe(
        "\n".join([skill, role_profile, role_state_machine, lane_contract, getting_started]),
        "auto-research skill contract",
    )

    assert "loopx-auto-research" not in REQUIRED_INSTALLED_SKILL_PHRASES

    required_skill_terms = [
        "name: loopx-auto-research",
        "worker-local role playbook",
        "not a global LoopX skill",
        "Identity comes from LoopX control-plane metadata",
        "Pane Tick Contract",
        "generic multi-agent kernel owns the default LoopX project/doc-registry skills",
        "fixed A2A wake prompt",
        "auto_research_role_profile_v0",
        'loopx --format json auto-research frontier --goal-id "$LOOPX_GOAL_ID" --agent-id "$LOOPX_AGENT_ID"',
        "No role owns the full graph",
        "Do not infer role from pane title",
        "Research Curator",
        "Hypothesis Proposer",
        "Research Executor",
        "Evaluator/Promoter",
        "Projection Narrator",
        "Control-Plane Guard",
        "Shared Stop Conditions",
        "research_contract_v0",
        "research_hypothesis_v0",
        "auto_research_evidence_packet_v0",
        "research_evidence_graph_v0",
        "quota should-run",
        "demo-supervisor",
        "--execute",
    ]
    for term in required_skill_terms:
        assert term in compact_skill, f"skill missing {term!r}"

    forbidden_skill_terms = [
        "skill assigns identity",
        "pane title is authoritative",
        "leader agent required",
        "coordinator owns the graph",
        "promote without evidence",
        "First Commands",
        "$loopx-project",
        "$loopx-doc-registry",
    ]
    lowered = compact_skill.lower()
    for term in forbidden_skill_terms:
        assert term.lower() not in lowered, f"skill drifted into forbidden term {term!r}"

    assert "required_skill\": \"loopx-auto-research\"" in role_profile, role_profile
    assert "worker-local" in role_profile, role_profile
    assert "auto_research_role_profile_v0" in role_state_machine, role_state_machine
    assert "product_narrator" in lane_contract, lane_contract
    assert (
        "`loopx-auto-research` | Running role-scoped auto-research lanes"
        not in getting_started
    ), getting_started
    assert "worker-local" in getting_started, getting_started
    assert "~/.codex/skills/loopx-auto-research" not in getting_started, getting_started

    print("auto-research-skill-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
