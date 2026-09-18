"""Focused regressions for the `formal_model` signature, hierarchy, and lanes.

`examples/semantic-vocabulary-drift-smoke.py::check_formal_model` is the only
guard standing between a hand-written metadata block and a reader who takes it
for a machine-checked proof. Before this file, exactly one test touched it
(`test_candidate_decisions_are_exhaustive_and_default_to_unknown`), and that test
reads two fields of `candidate_decisions`. Everything else the checker does --
the exact key set, the five roles, the consumer hierarchy, the six invariant ids,
the per-invariant shape, and the four-lane partition -- was unmutated, so a
regression that deleted any of it would have merged green.

Each case below mutates exactly one thing and asserts the checker fails closed
*naming that rule*. The `match` string is part of the contract: a mutation that
fails for an unrelated reason proves nothing, and the regression would rot into
a test that only asserts "something, somewhere, raised".

These tests are deliberately about the *schema* of the claim, not the claim.
`check_formal_model` validates that an obligation declares a stage, an evidence
string and a derived domain; it never executes the obligation. The distinction
is the point of slice B0 of #4447, and
``test_metadata_shape_is_not_an_executed_proof`` pins it so no later reader can
recover the conflation from this file.
"""

from __future__ import annotations

import copy
import runpy
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "examples" / "semantic-vocabulary-drift-smoke.py"

Mutation = Callable[[dict[str, Any], dict[str, Any]], None]


@pytest.fixture(scope="module")
def smoke() -> dict[str, Any]:
    """Load the smoke once; every test deep-copies the registry before mutating."""
    return runpy.run_path(str(SMOKE))


@pytest.fixture()
def registry(smoke: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(smoke["load_registry"]())


# --- one mutation per row; the match string names the rule that must fire ------------


def drop_required_key(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model.pop("proof_boundary")


def add_unknown_key(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # An unreviewed lane smuggled in as data is how a fifth enforcement class
    # would arrive without a code edit.
    model["blocking_eventually"] = ["F6_persistence_version_compatibility"]


def drop_universe(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["universes"].pop("roles")


def drop_role(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["roles"].remove("pass_through")


def drop_subrole_from_hierarchy(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # The subrole survives in `roles` but stops being a consumer, which is how a
    # pass-through would quietly acquire a role of its own.
    model["role_hierarchy"]["consumer"].remove("pass_through")


def empty_role_hierarchy(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["role_hierarchy"] = {}


def reparent_hierarchy_to_owner(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["role_hierarchy"] = {"owner": ["interpreter", "pass_through"]}


def drop_relation_kind(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # `persists` is the edge F6 is stated over; dropping it would leave F6
    # quantifying over a relation the model no longer declares.
    model["relations"].pop("persists")


def add_relation_kind(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["relations"]["validates"] = "X ⊆ L × V: a site validates a value"


def drop_invariant(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["invariants"] = [i for i in model["invariants"] if i["id"] != "F4_scope_separation"]
    model["enforcement_policy"]["blocking_next"].remove("F4_scope_separation")


def duplicate_invariant_id(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # Two entries for one id: both validate, and the last one silently wins every
    # dict the checker builds from the list. See the dedicated test below.
    original = next(i for i in model["invariants"] if i["id"] == "F1_producer_closedness")
    model["invariants"].append(copy.deepcopy(original))


def unknown_enforcement_stage(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    invariant(model, "F3_consumer_domain_closedness")["enforcement"] = "mostly_blocking"


def empty_statement(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    invariant(model, "F1_producer_closedness")["statement"] = "   "


def empty_evidence(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # An obligation with no evidence string is the exact shape B0 exists to stop:
    # a stage label with nothing behind it reads as a discharged proof.
    invariant(model, "F5_projection_totality")["evidence"] = ""


def invariant_missing_domain(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    invariant(model, "F5_projection_totality").pop("domain")


def invariant_extra_field(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    invariant(model, "F5_projection_totality")["proved"] = True


def invariant_in_two_lanes(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["enforcement_policy"]["advisory"].append("F5_projection_totality")


def lane_disagrees_with_enforcement(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # F5 is the one obligation the M0 smoke blocks on today; moving its id into
    # the advisory lane without touching its stage is how a blocking check would
    # be downgraded in a data-only diff.
    model["enforcement_policy"]["blocking_now"].remove("F5_projection_totality")
    model["enforcement_policy"]["advisory"].append("F5_projection_totality")


def drop_policy_lane(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["enforcement_policy"].pop("unproved")
    model["enforcement_policy"]["advisory"].append("F6_persistence_version_compatibility")


def unproved_stage_claims_verified_members(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    invariant(model, "F6_persistence_version_compatibility")["domain"]["verified"] = 1


def advisory_stage_claims_verified_members(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    invariant(model, "F3_consumer_domain_closedness")["domain"]["verified"] = 26


def widen_declared_domain(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    # Restating F1 over every vocabulary rather than the kernel tier is a
    # normative widening; FORMAL_DOMAIN_ANCHOR must make it a code edit.
    invariant(model, "F1_producer_closedness")["domain"]["quantifies_over"] = "vocabularies[*]"


def proof_boundary_empty_claim(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["proof_boundary"]["unproved"].append("  ")


def drop_proof_boundary_class(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["proof_boundary"].pop("unknown")


def schema_version_drift(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["schema_version"] = "loopx_semantic_formal_model_v1"


def candidate_default_is_not_unknown(model: dict[str, Any], _registry: dict[str, Any]) -> None:
    model["candidate_decisions"]["default"] = "reuse_existing"


def invariant(model: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in model["invariants"] if item["id"] == name)


MUTATIONS: dict[str, tuple[Mutation, str]] = {
    # --- the signature itself ---
    "missing_key": (drop_required_key, "keys must be exactly"),
    "extra_key": (add_unknown_key, "keys must be exactly"),
    "schema_version_drift": (schema_version_drift, "schema_version drift"),
    "dropped_universe": (drop_universe, "universes must name the declared sets"),
    # --- roles and hierarchy ---
    "dropped_role": (drop_role, "roles must include the consumer role"),
    "dropped_subrole": (drop_subrole_from_hierarchy, "must classify interpreter and pass_through"),
    "empty_role_hierarchy": (empty_role_hierarchy, "must classify interpreter and pass_through"),
    "hierarchy_reparented_to_owner": (reparent_hierarchy_to_owner, "must classify interpreter and pass_through"),
    # --- relations ---
    "dropped_relation_kind": (drop_relation_kind, "relations must be the declared edge kinds"),
    "extra_relation_kind": (add_relation_kind, "relations must be the declared edge kinds"),
    # --- invariant entries ---
    "missing_invariant": (drop_invariant, "must cover exactly F1-F6"),
    "duplicated_invariant_id": (duplicate_invariant_id, "exactly once"),
    "unknown_enforcement_stage": (unknown_enforcement_stage, "unknown enforcement stage"),
    "empty_statement": (empty_statement, "needs a statement and evidence"),
    "empty_evidence": (empty_evidence, "needs a statement and evidence"),
    "invariant_missing_domain": (invariant_missing_domain, "invalid shape"),
    "invariant_extra_field": (invariant_extra_field, "invalid shape"),
    # --- the four lanes ---
    "invariant_in_two_lanes": (invariant_in_two_lanes, "partition all invariants exactly once"),
    "lane_disagrees_with_enforcement": (lane_disagrees_with_enforcement, "disagrees with invariant enforcement stage"),
    "dropped_policy_lane": (drop_policy_lane, "must separate current, next, advisory, and unproved"),
    # --- stage versus walked domain ---
    "unproved_claims_verified": (unproved_stage_claims_verified_members, "an unenforced stage walks nothing"),
    "advisory_claims_verified": (advisory_stage_claims_verified_members, "an unenforced stage walks nothing"),
    "widened_domain": (widen_declared_domain, "FORMAL_DOMAIN_ANCHOR"),
    # --- proof boundary and candidate decisions ---
    "proof_boundary_empty_claim": (proof_boundary_empty_claim, "must contain non-empty claim names"),
    "dropped_proof_boundary_class": (drop_proof_boundary_class, "must separate established, bounded, unknown"),
    "candidate_default_changed": (candidate_default_is_not_unknown, "default unresolved candidates to unknown"),
}


def test_committed_formal_model_passes_its_own_checker(
    smoke: dict[str, Any], registry: dict[str, Any]
) -> None:
    """The baseline must be green, or every mutation below proves nothing."""
    smoke["check_formal_model"](registry["formal_model"], registry)


@pytest.mark.parametrize("case", sorted(MUTATIONS))
def test_formal_model_mutation_fails_closed(
    smoke: dict[str, Any], registry: dict[str, Any], case: str
) -> None:
    mutate, expected = MUTATIONS[case]
    mutate(registry["formal_model"], registry)
    with pytest.raises(smoke["Drift"], match=expected):
        smoke["check_formal_model"](registry["formal_model"], registry)


def test_duplicate_invariant_entry_cannot_restate_an_obligation(
    smoke: dict[str, Any], registry: dict[str, Any]
) -> None:
    """Two entries for one id must fail, even when both entries are individually valid.

    The id set and the lane partition are both sets, so a repeated entry leaves
    them unchanged, and every dict the checker builds by id keeps only the last
    entry. A second `F1_producer_closedness` carrying a weaker statement was
    therefore accepted, and a reader of the registry could not tell which of the
    two the smoke was reporting on. This is the duplicate-entry case B0 names.
    """
    model = registry["formal_model"]
    weakened = copy.deepcopy(invariant(model, "F1_producer_closedness"))
    weakened["statement"] = "Producers are closed over every registered vocabulary."
    model["invariants"].append(weakened)
    with pytest.raises(smoke["Drift"], match="exactly once"):
        smoke["check_formal_model"](model, registry)


def test_role_hierarchy_keeps_both_subroles_under_consumer(
    smoke: dict[str, Any], registry: dict[str, Any]
) -> None:
    """Interpreter and pass-through are consumers (I11), not roles of their own."""
    model = registry["formal_model"]
    assert model["role_hierarchy"] == {"consumer": ["interpreter", "pass_through"]}
    assert set(model["role_hierarchy"]) <= set(model["roles"])
    for subrole in model["role_hierarchy"]["consumer"]:
        assert subrole in model["roles"], subrole


def test_every_invariant_sits_in_exactly_one_lane_matching_its_stage(
    smoke: dict[str, Any], registry: dict[str, Any]
) -> None:
    model = registry["formal_model"]
    stage_for_lane = {
        "blocking_now": "m0",
        "blocking_next": "m0_5",
        "advisory": "advisory",
        "unproved": "unproved",
    }
    stages = {item["id"]: item["enforcement"] for item in model["invariants"]}
    placed = [item_id for ids in model["enforcement_policy"].values() for item_id in ids]
    assert sorted(placed) == sorted(stages), (sorted(placed), sorted(stages))
    assert len(placed) == len(set(placed)), placed
    for lane, ids in model["enforcement_policy"].items():
        for item_id in ids:
            assert stages[item_id] == stage_for_lane[lane], (lane, item_id, stages[item_id])


def test_metadata_shape_is_not_an_executed_proof(
    smoke: dict[str, Any], registry: dict[str, Any]
) -> None:
    """Every obligation keeps stage, evidence and walked domain separately readable.

    This is the B0 exit condition in executable form. A validated `formal_model`
    block asserts only that each obligation *declares* an implementation stage, a
    non-empty evidence boundary and a domain whose sizes the smoke recomputes
    from the registry. It never asserts that the obligation holds. The two
    unenforced stages must walk nothing, and the enforced ones must walk a
    strictly smaller-or-equal sub-domain than the population they are stated
    over -- so a full ratio can never be inferred from the stage label alone.
    """
    model = registry["formal_model"]
    unenforced = {"advisory", "unproved"}
    for item in model["invariants"]:
        stage, domain = item["enforcement"], item["domain"]
        assert item["statement"].strip(), item["id"]
        assert item["evidence"].strip(), item["id"]
        assert domain["verified"] <= domain["registered"], item["id"]
        if stage in unenforced:
            assert domain["verified"] == 0, (item["id"], stage, domain)
        else:
            assert domain["verified"] > 0, (item["id"], stage, domain)
    # The proof boundary must keep an explicit unproved class; an empty one would
    # mean the model claims nothing is left to prove.
    assert model["proof_boundary"]["unproved"], model["proof_boundary"]
    assert "unknown" in model["proof_boundary"], model["proof_boundary"]
