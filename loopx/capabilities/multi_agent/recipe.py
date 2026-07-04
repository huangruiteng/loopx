from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping


GENERIC_MULTI_AGENT_MINIMAL_RECIPE_SCHEMA_VERSION = (
    "generic_multi_agent_minimal_recipe_v0"
)

DEFAULT_DECENTRALIZED_A2A_PROOF_CONTRACT: dict[str, object] = {
    "broadcaster_selects_todo": False,
    "broadcaster_runs_worker_turn": False,
    "each_pane_reads_own_quota_frontier": True,
    "successor_todos_declared_by_role_profile": True,
    "leader_agent_required": False,
}

DEFAULT_MULTI_AGENT_KERNEL_REUSE = (
    "generic visible multi-agent runner",
    "fixed prompt broadcast",
    "pane-local A2A tick",
    "LoopX todo/evidence/status protocol",
)


def _recipe_lines(lines: Iterable[object] | None) -> list[str]:
    return [str(line).strip() for line in lines or [] if str(line).strip()]


def build_minimal_decentralized_a2a_recipe(
    *,
    user_recipe_lines: Iterable[object],
    preset_recipe_lines: Iterable[object],
    product_id: str,
    claim: str,
    claim_boundary: str,
    schema_version: str = GENERIC_MULTI_AGENT_MINIMAL_RECIPE_SCHEMA_VERSION,
    line_unit: str = "declarative_recipe_line",
    coordination_model: str = "decentralized_state_a2a",
    a2a_proof_contract: Mapping[str, object] | None = None,
    kernel_reuse: Iterable[object] | None = None,
    shared_kernel_counted_as_recipe_lines: bool = False,
) -> dict[str, object]:
    """Return the generic line-count contract for a product preset.

    Product presets provide only user and preset recipe lines. The generic
    kernel owns decentralized A2A proof fields, process launch, pane-local
    ticks, and LoopX state handoff mechanics.
    """

    user_lines = _recipe_lines(user_recipe_lines)
    preset_lines = _recipe_lines(preset_recipe_lines)
    proof = dict(a2a_proof_contract or DEFAULT_DECENTRALIZED_A2A_PROOF_CONTRACT)
    kernel_lines = _recipe_lines(kernel_reuse or DEFAULT_MULTI_AGENT_KERNEL_REUSE)
    return {
        "schema_version": schema_version,
        "product_id": str(product_id or "").strip() or "multi-agent-product",
        "claim": claim,
        "line_unit": line_unit,
        "user_line_count": len(user_lines),
        "preset_role_spec_line_count": len(preset_lines),
        "user_plus_preset_line_count": len(user_lines) + len(preset_lines),
        "shared_kernel_counted_as_recipe_lines": shared_kernel_counted_as_recipe_lines,
        "claim_boundary": claim_boundary,
        "user_recipe_lines": user_lines,
        "preset_recipe_lines": preset_lines,
        "coordination_model": coordination_model,
        "a2a_proof_contract": proof,
        "kernel_reuse": kernel_lines,
        "owner_layers": {
            "user_layer": "intent_lines_only",
            "preset_layer": "role_defaults_and_domain_handoff_only",
            "kernel_layer": "decentralized_a2a_runtime_and_state_protocol",
        },
    }


def parse_multi_agent_role_spec_lines(
    *,
    agent_specs: Iterable[object] | None,
    default_agent_specs: Iterable[object],
    resolve_role_id: Callable[[str, int], str],
    default_scope_by_lane: Mapping[str, object] | None = None,
) -> list[dict[str, str]]:
    """Parse `agent_id[:lane_id[:role_id[:scope]]]` recipe lines."""

    parsed_specs = _recipe_lines(agent_specs) or _recipe_lines(default_agent_specs)
    default_scope = {
        str(lane_id): str(scope)
        for lane_id, scope in (default_scope_by_lane or {}).items()
        if str(lane_id).strip()
    }
    lanes: list[dict[str, str]] = []
    for index, raw in enumerate(parsed_specs, start=1):
        parts = [part.strip() for part in raw.split(":")]
        if len(parts) not in {1, 2, 3, 4} or not parts[0]:
            raise ValueError("agent specs must be agent_id[:lane_id[:role_id[:scope]]]")
        agent_id = parts[0]
        lane_id = parts[1] if len(parts) >= 2 and parts[1] else f"lane-{index}"
        role_id = resolve_role_id(parts[2] if len(parts) >= 3 else "", index)
        scope = parts[3] if len(parts) >= 4 and parts[3] else default_scope.get(lane_id, role_id)
        lanes.append(
            {
                "agent_id": agent_id,
                "lane_id": lane_id,
                "role_id": role_id,
                "scope": scope,
            }
        )
    return lanes
