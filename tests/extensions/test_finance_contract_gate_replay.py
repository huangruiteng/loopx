from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ROOT = ROOT / "packages" / "loopx-finance-value-discovery"
EXTENSION_SRC = EXTENSION_ROOT / "src"
EXAMPLE = EXTENSION_ROOT / "examples" / "finance-case-gates-v1.json"
sys.path.insert(0, str(EXTENSION_SRC))

from loopx_finance_value_discovery.cli import run  # noqa: E402
from loopx_finance_value_discovery.replay import (  # noqa: E402
    build_finance_case_evaluation,
    canonical_json_bytes,
    replay_finance_case_evaluation,
)


def _example() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_missing_gate_short_circuits_to_insufficient_evidence() -> None:
    payload = _example()
    evaluation = build_finance_case_evaluation(payload)

    assert evaluation["schema_version"] == "finance_case_gate_evaluation_v1"
    assert evaluation["disposition"] == "insufficient_evidence"
    assert evaluation["first_blocking_gate"] == {
        "gate_id": "terminal_risk",
        "state": "missing",
        "reason": "A complete terminal-loss path is not yet supported.",
    }
    assert evaluation["boundary"] == {
        "public_evidence_only_state": "caller_asserted",
        "outcome_blind_state": "caller_asserted",
        "investment_advice": False,
        "trading_allowed": False,
        "automatic_promotion_allowed": False,
        "human_decision_owner": True,
    }


def test_all_passed_only_allows_a_research_successor() -> None:
    payload = _example()
    payload["observations"][-1] = {
        "gate_id": "terminal_risk",
        "observation_state": "observed",
        "value": True,
        "evidence_refs": ["terminal-risk-bridge"],
        "reason": "The terminal-loss path is bounded by frozen evidence.",
    }

    evaluation = build_finance_case_evaluation(payload)

    assert evaluation["disposition"] == "eligible_for_research_successor"
    assert evaluation["first_blocking_gate"] is None
    assert evaluation["boundary"]["automatic_promotion_allowed"] is False
    assert evaluation["boundary"]["trading_allowed"] is False


@pytest.mark.parametrize("state", ["failed", "missing", "conflict"])
def test_first_blocker_controls_disposition_and_later_gates_do_not_run(
    state: str,
) -> None:
    payload = _example()
    observation_state = "observed" if state == "failed" else state
    payload["observations"][2] = {
        "gate_id": "evidence_quality",
        "observation_state": observation_state,
        "value": 1 if state == "failed" else None,
        "evidence_refs": (
            []
            if state == "missing"
            else ["filing-primary", "market-independent"]
            if state == "conflict"
            else ["filing-primary"]
        ),
        "reason": "The evidence-quality gate blocks this case.",
    }
    for observation in payload["observations"][3:]:
        observation["observation_state"] = "not_run"
        observation["value"] = None
        observation["evidence_refs"] = []
        observation["reason"] = "Not run after the evidence-quality blocker."

    evaluation = build_finance_case_evaluation(payload)

    assert evaluation["disposition"] == (
        "rejected" if state == "failed" else "insufficient_evidence"
    )
    assert evaluation["first_blocking_gate"]["gate_id"] == "evidence_quality"
    assert evaluation["first_blocking_gate"]["state"] == state


def test_gate_order_and_short_circuit_are_enforced() -> None:
    out_of_order = _example()
    out_of_order["observations"][0], out_of_order["observations"][1] = (
        out_of_order["observations"][1],
        out_of_order["observations"][0],
    )
    with pytest.raises(ValueError, match="exactly match"):
        build_finance_case_evaluation(out_of_order)

    post_blocker_execution = _example()
    post_blocker_execution["observations"][2]["observation_state"] = "missing"
    post_blocker_execution["observations"][2]["value"] = None
    post_blocker_execution["observations"][2]["evidence_refs"] = []
    with pytest.raises(ValueError, match="after the first blocking gate"):
        build_finance_case_evaluation(post_blocker_execution)

    premature_not_run = _example()
    premature_not_run["observations"][0]["observation_state"] = "not_run"
    premature_not_run["observations"][0]["value"] = None
    premature_not_run["observations"][0]["evidence_refs"] = []
    with pytest.raises(ValueError, match="requires an earlier blocking gate"):
        build_finance_case_evaluation(premature_not_run)


@pytest.mark.parametrize(
    ("gate_id", "observation_state", "evidence_refs", "message"),
    [
        ("universe", "observed", [], "observed values require evidence_refs"),
        (
            "evidence_quality",
            "conflict",
            ["filing-primary"],
            "conflicts require at least two evidence_refs",
        ),
        (
            "de_beta_residual",
            "not_run",
            ["valuation-bridge"],
            "not_run cannot include evidence_refs",
        ),
    ],
)
def test_gate_observation_states_enforce_evidence_ref_invariants(
    gate_id: str,
    observation_state: str,
    evidence_refs: list[str],
    message: str,
) -> None:
    payload = _example()
    observation = next(
        observation
        for observation in payload["observations"]
        if observation["gate_id"] == gate_id
    )
    observation["observation_state"] = observation_state
    if observation_state != "observed":
        observation["value"] = None
    observation["evidence_refs"] = evidence_refs

    with pytest.raises(ValueError, match=message):
        build_finance_case_evaluation(payload)


def test_provider_cannot_declare_pass_fail_or_change_value_type() -> None:
    declared_result = _example()
    declared_result["observations"][0]["state"] = "passed"
    with pytest.raises(ValueError, match="unsupported fields"):
        build_finance_case_evaluation(declared_result)

    wrong_type = _example()
    wrong_type["observations"][2]["value"] = "two"
    with pytest.raises(ValueError, match="must be a number"):
        build_finance_case_evaluation(wrong_type)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_numeric_gate_rejects_non_finite_thresholds_and_observations(
    invalid: float,
) -> None:
    invalid_threshold = _example()
    invalid_threshold["contract"]["gates"][2]["reference_value"] = invalid
    with pytest.raises(ValueError, match="finite number"):
        build_finance_case_evaluation(invalid_threshold)

    invalid_observation = _example()
    invalid_observation["observations"][2]["value"] = invalid
    with pytest.raises(ValueError, match="finite number"):
        build_finance_case_evaluation(invalid_observation)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload["contract"].update(
            {"thresholds_frozen": False}
        ),
        lambda payload: payload["contract"].update(
            {"point_in_time": "2026-07-24"}
        ),
        lambda payload: payload["observations"][0].update(
            {"reason": "Mutated after the original evaluation."}
        ),
    ],
)
def test_replay_rejects_contract_or_input_mutation(mutator) -> None:
    payload = _example()
    expected = build_finance_case_evaluation(payload)
    mutated = deepcopy(payload)
    mutator(mutated)

    with pytest.raises(ValueError):
        replay_finance_case_evaluation(mutated, expected)


def test_replay_requires_byte_identical_evaluation() -> None:
    payload = _example()
    expected = build_finance_case_evaluation(payload)
    verified = replay_finance_case_evaluation(payload, expected)
    assert verified["replay_verified"] is True

    tampered = deepcopy(expected)
    tampered["first_blocking_gate"]["reason"] = "Changed result text."
    with pytest.raises(ValueError, match="bytes mismatch"):
        replay_finance_case_evaluation(payload, tampered)

    reordered = json.loads(
        json.dumps(expected, sort_keys=False),
        object_pairs_hook=dict,
    )
    assert canonical_json_bytes(reordered) == canonical_json_bytes(expected)


def test_historical_positive_and_rejection_replay_under_one_contract() -> None:
    positive = _example()
    positive["case_id"] = "historical-paypal-bounded-successor"
    positive["contract"]["point_in_time"] = "2026-07-06"
    positive["contract"]["universe_id"] = "historical-legacy-payments-screen"
    positive["contract"]["gates"] = positive["contract"]["gates"][:4]
    positive["observations"] = positive["observations"][:4]
    positive["observations"][2]["evidence_refs"] = [
        "pypl-filing-facts",
        "pypl-adjusted-history",
    ]
    positive["observations"][3]["evidence_refs"] = [
        "pypl-adjusted-history",
        "legacy-payments-controls",
    ]

    positive_evaluation = build_finance_case_evaluation(positive)
    assert positive_evaluation["disposition"] == "eligible_for_research_successor"
    assert replay_finance_case_evaluation(
        positive, positive_evaluation
    )["replay_verified"]

    rejected = deepcopy(positive)
    rejected["case_id"] = "historical-groupwide-derating-rejection"
    rejected["observations"][3]["value"] = -0.12
    rejected["observations"][3]["reason"] = (
        "The residual does not clear the frozen idiosyncratic threshold."
    )

    rejected_evaluation = build_finance_case_evaluation(rejected)
    assert rejected_evaluation["disposition"] == "rejected"
    assert rejected_evaluation["first_blocking_gate"]["gate_id"] == (
        "de_beta_residual"
    )
    assert replay_finance_case_evaluation(
        rejected, rejected_evaluation
    )["replay_verified"]


def test_direct_cli_evaluate_and_replay(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(["evaluate", "--input-json", str(EXAMPLE)]) == 0
    evaluation = json.loads(capsys.readouterr().out)
    assert evaluation["disposition"] == "insufficient_evidence"

    expected = tmp_path / "evaluation.json"
    expected.write_text(json.dumps(evaluation), encoding="utf-8")
    assert (
        run(
            [
                "replay",
                "--input-json",
                str(EXAMPLE),
                "--expected-json",
                str(expected),
            ]
        )
        == 0
    )
    verified = json.loads(capsys.readouterr().out)
    assert verified["replay_verified"] is True


def test_point_in_time_after_evaluation_as_of_is_rejected() -> None:
    payload = _example()
    # future cutoff: point_in_time later than evaluation_as_of must fail closed
    payload["contract"]["point_in_time"] = "2999-12-31"
    with pytest.raises(ValueError, match="must not be after"):
        build_finance_case_evaluation(payload)


def test_offset_aware_point_in_time_after_cutoff_is_rejected() -> None:
    payload = _example()
    payload["contract"]["point_in_time"] = "2026-07-27T23:30:00-04:00"
    payload["contract"]["evaluation_as_of"] = "2026-07-28T03:00:00Z"

    with pytest.raises(ValueError, match="must not be after"):
        build_finance_case_evaluation(payload)


def test_evaluation_as_of_is_required() -> None:
    payload = _example()
    del payload["contract"]["evaluation_as_of"]
    with pytest.raises(ValueError, match="evaluation_as_of"):
        build_finance_case_evaluation(payload)


def test_unverified_guarantees_are_recorded_as_caller_asserted() -> None:
    payload = _example()
    evaluation = build_finance_case_evaluation(payload)
    # the engine records the caller's assertion state, not an unverified fact
    assert evaluation["boundary"]["outcome_blind_state"] == "caller_asserted"
    assert evaluation["boundary"]["public_evidence_only_state"] == "caller_asserted"
    assert evaluation["contract"]["outcome_blind_state"] == "caller_asserted"
    assert evaluation["contract"]["public_evidence_only_state"] == "caller_asserted"
    assert "outcome_blind" not in evaluation["boundary"]
    assert "public_evidence_only" not in evaluation["boundary"]
