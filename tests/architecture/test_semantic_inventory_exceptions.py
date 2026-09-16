"""Q7 reuses the existing lifecycle without changing semantic debt targets."""

from copy import deepcopy
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "examples/semantic-vocabulary-drift-smoke.py"


@pytest.fixture
def smoke():
    return runpy.run_path(str(SMOKE))


def evaluate(smoke, *, key="same_runtime_forks", amount=1, exceptions=None):
    summary = dict(smoke["BUDGET_ANCHOR"])
    summary[key] += amount
    if exceptions is not None:
        smoke["evaluate_inventory_budget_findings"].__globals__[
            "REVIEWED_SEMANTIC_INVENTORY_EXCEPTIONS"
        ] = exceptions
    return smoke["evaluate_inventory_budget_findings"](
        summary, summary["multi_value_forks_semantic"], dict(smoke["BUDGET_ANCHOR"])
    )


def exception(smoke, *, key="same_runtime_forks", amount=1):
    return {
        f"semantic_inventory_budget:{key}": {
            "reason": "A bounded compatibility overlap needs staged retirement.",
            "retirement_plan": "Remove the old definitions and delete this exception.",
            "metric_ceilings": {key: smoke["BUDGET_ANCHOR"][key] + amount},
        }
    }


def test_no_current_exception_is_installed(smoke):
    assert smoke["REVIEWED_SEMANTIC_INVENTORY_EXCEPTIONS"] == {}


@pytest.mark.parametrize(
    "key",
    [
        "same_runtime_forks",
        "same_runtime_fork_definitions",
        "conflicting_values",
        "conflicting_definitions",
        "schema_version_same_runtime_forks",
        "multi_value_twins",
        "multi_value_forks",
        "multi_value_forks_semantic",
        "multi_value_fork_definitions",
        "same_runtime_forks_semantic",
        "conflicting_values_semantic",
    ],
)
@pytest.mark.parametrize("amount", [-1, 0, 1])
def test_empty_exception_policy_preserves_each_independent_budget_verdict(
    smoke, key, amount
):
    report = evaluate(smoke, key=key, amount=amount)
    assert report["ok"] is (amount <= 0)
    if amount > 0:
        finding = report["unreviewed_findings"][0]
        assert finding["id"] == f"semantic_inventory_budget:{key}"
        assert finding["metrics"] == {key: smoke["BUDGET_ANCHOR"][key] + amount}
        assert finding["budget"] == smoke["BUDGET_ANCHOR"][key]
    else:
        assert report["findings"] == []


def test_reviewed_exception_is_bounded_and_does_not_raise_the_target(smoke):
    policy = exception(smoke, amount=2)
    assert evaluate(smoke, amount=1, exceptions=policy)["ok"] is True
    admitted = evaluate(smoke, amount=2)
    assert admitted["ok"] is True
    assert (
        admitted["findings"][0]["budget"]
        == smoke["BUDGET_ANCHOR"]["same_runtime_forks"]
    )
    exceeded = evaluate(smoke, amount=3)
    assert exceeded["ok"] is False
    assert exceeded["magnitude_regression_count"] == 1
    assert exceeded["magnitude_regressions"][0]["metric_regressions"] == [
        {
            "metric": "same_runtime_forks",
            "actual": smoke["BUDGET_ANCHOR"]["same_runtime_forks"] + 3,
            "ceiling": smoke["BUDGET_ANCHOR"]["same_runtime_forks"] + 2,
        }
    ]


@pytest.mark.parametrize("amount", [0, -1])
def test_exception_must_be_retired_when_the_overrun_disappears(smoke, amount):
    report = evaluate(smoke, amount=amount, exceptions=exception(smoke))
    assert report["ok"] is False
    assert (
        report["stale_exceptions"][0]["id"]
        == "semantic_inventory_budget:same_runtime_forks"
    )


@pytest.mark.parametrize(
    "defect",
    [
        "reason",
        "retirement_plan",
        "missing_ceiling",
        "wrong_metric",
        "bool",
        "negative",
    ],
)
def test_existing_api_rejects_invalid_semantic_exceptions(smoke, defect):
    policy = exception(smoke)
    entry = next(iter(policy.values()))
    if defect in {"reason", "retirement_plan"}:
        entry[defect] = " "
    elif defect == "missing_ceiling":
        del entry["metric_ceilings"]
    elif defect == "wrong_metric":
        entry["metric_ceilings"] = {"unrelated": 100}
    else:
        entry["metric_ceilings"] = {
            "same_runtime_forks": True if defect == "bool" else -1
        }
    report = evaluate(smoke, exceptions=policy)
    assert report["ok"] is False
    assert report["invalid_exceptions"] == [
        "semantic_inventory_budget:same_runtime_forks"
    ]


def test_one_exception_cannot_waive_a_different_semantic_target(smoke):
    report = evaluate(smoke, key="conflicting_values", exceptions=exception(smoke))
    assert report["ok"] is False
    assert report["unreviewed_count"] == 1
    assert report["stale_exception_count"] == 1


def test_exception_cannot_relax_anchor_equality(smoke):
    summary = dict(smoke["BUDGET_ANCHOR"])
    ratchets = dict(summary)
    ratchets["same_runtime_forks"] += 1
    with pytest.raises(smoke["Drift"], match="BUDGET_ANCHOR"):
        smoke["evaluate_inventory_budget_findings"](
            summary, summary["multi_value_forks_semantic"], ratchets
        )


def test_active_inventory_check_calls_existing_evaluator_and_enforces_lifecycle(
    smoke, tmp_path, monkeypatch
):
    from loopx.canary.maintainability_ratchet import evaluate_maintainability_findings

    registry = deepcopy(smoke["load_registry"]())
    inventory = smoke["build_inventory"](ROOT)
    inventory["summary"]["same_runtime_forks"] = (
        smoke["BUDGET_ANCHOR"]["same_runtime_forks"] + 1
    )
    path = tmp_path / "inventory.json"
    path.write_text(smoke["render_inventory"](inventory))
    namespace = smoke["check_inventory"].__globals__
    monkeypatch.setitem(namespace, "build_inventory", lambda *a, **kw: inventory)
    calls = []

    def observed(findings, *, reviewed_exceptions):
        calls.append((findings, reviewed_exceptions))
        return evaluate_maintainability_findings(
            findings, reviewed_exceptions=reviewed_exceptions
        )

    monkeypatch.setitem(namespace, "evaluate_maintainability_findings", observed)
    with pytest.raises(smoke["Drift"], match="unreviewed"):
        smoke["check_inventory"](registry, [])
    policy = exception(smoke)
    monkeypatch.setitem(namespace, "REVIEWED_SEMANTIC_INVENTORY_EXCEPTIONS", policy)
    _, report = smoke["check_inventory"](registry, [])
    assert "reviewed_inventory_exceptions=1" in report
    assert calls[-1][1] is policy
    # Q9: the inventory is computed from the tracked tree on every run, so there is
    # no committed snapshot whose freshness could be a precondition. A report file
    # on disk is ignored rather than compared.
    _, again = smoke["check_inventory"](registry, [])
    assert "reviewed_inventory_exceptions=1" in again
