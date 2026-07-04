#!/usr/bin/env python3
"""Smoke-check that auto-research stays a thin developer-facing preset."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.auto_research.preset import (  # noqa: E402
    build_auto_research_minimal_a2a_recipe,
)
from loopx.capabilities.multi_agent.recipe import (  # noqa: E402
    DEFAULT_DECENTRALIZED_A2A_PROOF_CONTRACT,
    build_minimal_decentralized_a2a_recipe,
    parse_multi_agent_role_spec_lines,
)


def main() -> int:
    preset_source = ROOT / "loopx" / "capabilities" / "auto_research" / "preset.py"
    generic_source = ROOT / "loopx" / "capabilities" / "multi_agent" / "recipe.py"
    preset_text = preset_source.read_text(encoding="utf-8")
    generic_text = generic_source.read_text(encoding="utf-8")

    for proof_key in DEFAULT_DECENTRALIZED_A2A_PROOF_CONTRACT:
        assert proof_key not in preset_text, proof_key
        assert proof_key in generic_text, proof_key

    auto_recipe = build_auto_research_minimal_a2a_recipe(
        open_question="Can decentralized A2A improve research quality?",
        output_language="zh",
    )
    assert auto_recipe["schema_version"] == "auto_research_minimal_a2a_recipe_v0"
    assert auto_recipe["product_id"] == "auto-research"
    assert auto_recipe["user_line_count"] == 1
    assert auto_recipe["preset_role_spec_line_count"] == 4
    assert auto_recipe["user_plus_preset_line_count"] == 5
    assert auto_recipe["shared_kernel_counted_as_recipe_lines"] is False
    assert auto_recipe["a2a_proof_contract"] == DEFAULT_DECENTRALIZED_A2A_PROOF_CONTRACT
    assert auto_recipe["owner_layers"]["preset_layer"] == (
        "role_defaults_and_domain_handoff_only"
    )

    generic_recipe = build_minimal_decentralized_a2a_recipe(
        product_id="custom-research",
        claim="one command plus two roles starts decentralized A2A",
        claim_boundary="count only user and preset recipe lines",
        user_recipe_lines=["loopx custom-research start '<topic>' --execute"],
        preset_recipe_lines=["agent-a:curator", "agent-b:runner"],
    )
    assert generic_recipe["schema_version"] == "generic_multi_agent_minimal_recipe_v0"
    assert generic_recipe["user_plus_preset_line_count"] == 3
    assert generic_recipe["a2a_proof_contract"] == DEFAULT_DECENTRALIZED_A2A_PROOF_CONTRACT

    lanes = parse_multi_agent_role_spec_lines(
        agent_specs=["agent-a:plan:planner:Plan a focused slice", "agent-b"],
        default_agent_specs=[],
        resolve_role_id=lambda raw, index: raw or f"role-{index}",
        default_scope_by_lane={"lane-2": "Run the bounded work"},
    )
    assert lanes == [
        {
            "agent_id": "agent-a",
            "lane_id": "plan",
            "role_id": "planner",
            "scope": "Plan a focused slice",
        },
        {
            "agent_id": "agent-b",
            "lane_id": "lane-2",
            "role_id": "role-2",
            "scope": "Run the bounded work",
        },
    ]

    preset_line_count = len(preset_text.splitlines())
    generic_line_count = len(generic_text.splitlines())
    assert preset_line_count <= 430, preset_line_count
    assert generic_line_count <= 120, generic_line_count

    print("auto-research-dev-thin-preset-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
