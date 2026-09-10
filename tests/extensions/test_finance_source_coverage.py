"""Public source coverage must gate real evaluation, without inventing truth."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "packages" / "loopx-finance-value-discovery"
sys.path.insert(0, str(PACKAGE / "src"))

from loopx_finance_value_discovery.replay import (  # noqa: E402
    build_finance_case_evaluation,
    canonical_json_bytes,
    replay_finance_case_evaluation,
)
from loopx_finance_value_discovery.source_coverage import (  # noqa: E402
    MAX_PAGES,
    MAX_ROWS,
    MAX_ROWS_PER_PAGE,
)


def example():
    return json.loads(
        (PACKAGE / "examples/finance-source-coverage-v1.json").read_text()
    )


def pages(payload):
    return payload["observations"][0]["source_pages"]


def skip_later(payload):
    payload["observations"][1] = {
        "gate_id": "economic_evidence",
        "observation_state": "not_run",
        "value": None,
        "evidence_refs": [],
        "reason": "Coverage prevents downstream evaluation.",
    }


def result(payload):
    return build_finance_case_evaluation(payload)


def coverage(evaluation):
    return evaluation["gate_results"][0]["source_coverage"]


def two_pages(payload):
    first = pages(payload)[0]
    first.update(total_count=2, has_more=True)
    second = deepcopy(first)
    second.update(page_number=2, has_more=False)
    second["rows"][0]["id"] = "synthetic-filing-b"
    pages(payload).append(second)


def test_complete_coverage_only_passes_its_own_gate():
    evaluation = result(example())
    report = coverage(evaluation)
    assert report["state"] == "complete"
    assert report["unique_ids"] == 1
    assert report["snapshot_evidence_state"] == "adapter_asserted"
    assert report["publication_time_verified"] is False
    assert report["event_novelty_verified"] is False
    assert report["records"][0]["versions"]["a" * 64]["publication_at_values"] == [None]
    assert evaluation["gate_results"][0]["state"] == "passed"
    assert evaluation["first_blocking_gate"]["gate_id"] == "economic_evidence"
    assert evaluation["disposition"] == "insufficient_evidence"
    assert evaluation["boundary"]["trading_allowed"] is False


@pytest.mark.parametrize(
    "missing",
    ["snapshot_id", "snapshot_evidence_ref", "total_count", "has_more", "rows"],
)
def test_counts_are_not_proof_and_missing_payload_is_not_empty_success(missing):
    payload = example()
    pages(payload)[0].pop(missing)
    skip_later(payload)
    evaluation = result(payload)
    assert coverage(evaluation)["state"] == (
        "source_error" if missing == "rows" else "partial"
    )
    assert evaluation["disposition"] == "insufficient_evidence"
    assert evaluation["first_blocking_gate"]["state"] == "missing"
    assert evaluation["gate_results"][1]["state"] == "not_run"


@pytest.mark.parametrize("source_status", ["error", "unknown", None])
def test_error_empty_is_not_complete_empty(source_status):
    payload = example()
    pages(payload)[0].update(source_status=source_status, rows=[], total_count=0)
    skip_later(payload)
    assert coverage(result(payload))["state"] == "source_error"


def test_no_receipts_and_attested_empty_have_different_meanings():
    payload = example()
    payload["observations"][0]["source_pages"] = []
    skip_later(payload)
    assert coverage(result(payload))["state"] == "partial"
    payload = example()
    pages(payload)[0].update(rows=[], total_count=0)
    assert coverage(result(payload))["state"] == "complete"


@pytest.mark.parametrize(
    "change,reason",
    [
        ("overlap", "cross_page_overlap"),
        ("snapshot", "snapshot_changed"),
        ("count", "reported_total_changed"),
        ("terminal", "inconsistent_terminal"),
    ],
)
def test_cross_page_instability_blocks_without_rejecting_hypothesis(change, reason):
    payload = example()
    two_pages(payload)
    if change == "overlap":
        pages(payload)[1]["rows"][0]["id"] = pages(payload)[0]["rows"][0]["id"]
    elif change == "snapshot":
        pages(payload)[1]["snapshot_id"] = "another-snapshot"
    elif change == "count":
        pages(payload)[1]["total_count"] = 3
    else:
        pages(payload)[0]["has_more"] = False
    skip_later(payload)
    evaluation = result(payload)
    assert coverage(evaluation)["state"] == "unstable"
    assert reason in coverage(evaluation)["instability"]
    assert evaluation["disposition"] == "insufficient_evidence"


@pytest.mark.parametrize("number", [3, 10**12])
def test_missing_pages_do_not_allocate_a_range_of_claimed_page_numbers(number):
    payload = example()
    two_pages(payload)
    pages(payload)[1]["page_number"] = number
    skip_later(payload)
    assert coverage(result(payload))["state"] == "partial"


def test_two_pages_and_exact_replay_are_complete_but_do_not_create_new_records():
    payload = example()
    two_pages(payload)
    pages(payload).append(deepcopy(pages(payload)[0]))
    report = coverage(result(payload))
    assert report["state"] == "complete"
    assert report["unique_ids"] == 2
    assert report["row_count_including_replays"] == 3


def test_changed_replay_retains_versions_and_first_observation():
    payload = example()
    later = deepcopy(pages(payload)[0])
    later.update(started_at="2026-01-02T02:00:00Z", observed_at="2026-01-02T02:01:00Z")
    later["rows"][0]["content_sha256"] = "b" * 64
    pages(payload).insert(0, later)
    skip_later(payload)
    report = coverage(result(payload))
    assert report["state"] == "unstable"
    assert "repeated_page_changed" in report["instability"]
    assert "record_version_conflict" in report["instability"]
    assert report["records"][0]["first_observed_at"] == "2026-01-02T01:01:00+00:00"
    assert set(report["records"][0]["versions"]) == {"a" * 64, "b" * 64}


@pytest.mark.parametrize(
    "field,value",
    [
        ("started_at", "2026-01-01T00:00:00Z"),
        ("started_at", "2026-01-02T02:00:00Z"),
        ("observed_at", "2026-01-02T04:00:00Z"),
        ("observed_at", "2026-01-02T01:01:00"),
        ("observed_at", "not-a-clock"),
        ("page_number", True),
        ("page_number", 0),
    ],
)
def test_malformed_or_outside_window_receipts_fail_closed(field, value):
    payload = example()
    pages(payload)[0][field] = value
    with pytest.raises(ValueError):
        result(payload)


@pytest.mark.parametrize("field", ["market", "query_id", "universe_id"])
def test_adapter_cannot_substitute_the_frozen_query(field):
    payload = example()
    pages(payload)[0]["request_identity"][field] = "another-scope"
    skip_later(payload)
    assert "request_identity_mismatch" in coverage(result(payload))["errors"]


def test_contract_cannot_bind_coverage_to_another_universe_or_weaken_rule():
    for patch in (
        {"reference_value": False},
        {"value_type": "string", "reference_value": "complete"},
    ):
        payload = example()
        payload["contract"]["gates"][0].update(patch)
        with pytest.raises(ValueError, match="boolean eq true"):
            result(payload)
    payload = example()
    payload["contract"]["universe_id"] = "another-universe"
    with pytest.raises(ValueError, match="universe_id"):
        result(payload)


def test_provider_cannot_self_assert_coverage_or_smuggle_rows_into_an_unbound_gate():
    payload = example()
    payload["observations"][0] = {
        "gate_id": "disclosure_coverage",
        "observation_state": "observed",
        "value": True,
        "evidence_refs": ["trust-me"],
        "reason": "Caller asserts success.",
    }
    with pytest.raises(ValueError, match="requires only"):
        result(payload)
    payload = example()
    payload["contract"]["gates"][0].pop("source_coverage")
    with pytest.raises(ValueError, match="unsupported fields"):
        result(payload)


def test_later_gates_still_must_not_run_after_coverage_gap():
    payload = example()
    pages(payload)[0].pop("snapshot_evidence_ref")
    with pytest.raises(ValueError, match="after the first blocking gate"):
        result(payload)


@pytest.mark.parametrize(
    "patch,reason",
    [
        ({"market": "OTHER"}, "row_market_mismatch"),
        ({"content_sha256": "invalid"}, "row_identity_or_digest_missing"),
        ({"publication_at": "2026-01-02T02:00:00Z"}, "publication_after_observation"),
        ({"publication_at": {"invalid": True}}, "invalid_publication_time"),
    ],
)
def test_invalid_record_metadata_cannot_pass(patch, reason):
    payload = example()
    pages(payload)[0]["rows"][0].update(patch)
    skip_later(payload)
    assert reason in coverage(result(payload))["errors"]


@pytest.mark.parametrize("value", [True, -1, 1.5, "1"])
def test_total_requires_a_nonnegative_integer(value):
    payload = example()
    pages(payload)[0]["total_count"] = value
    skip_later(payload)
    assert coverage(result(payload))["state"] == "source_error"


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("page", "body", "not accepted"),
        ("row", "extra", "unmodeled content"),
        ("page", "snapshot_evidence_ref", "/Users/example/source.json"),
    ],
)
def test_raw_or_private_material_is_rejected(target, key, value):
    payload = example()
    item = pages(payload)[0] if target == "page" else pages(payload)[0]["rows"][0]
    item[key] = value
    with pytest.raises(ValueError):
        result(payload)


def test_receipt_and_row_budgets():
    payload = example()
    payload["observations"][0]["source_pages"] *= MAX_PAGES + 1
    with pytest.raises(ValueError, match="at most"):
        result(payload)
    payload = example()
    pages(payload)[0]["rows"] *= MAX_ROWS_PER_PAGE + 1
    with pytest.raises(ValueError, match="row budget"):
        result(payload)
    payload = example()
    pages(payload)[0]["rows"] *= MAX_ROWS_PER_PAGE
    payload["observations"][0]["source_pages"] *= MAX_ROWS // MAX_ROWS_PER_PAGE + 1
    with pytest.raises(ValueError, match="row budget"):
        result(payload)


def test_replay_binds_query_receipts_and_computed_coverage():
    payload = example()
    expected = result(payload)
    assert replay_finance_case_evaluation(payload, expected)["replay_verified"] is True
    mutated = deepcopy(payload)
    pages(mutated)[0]["rows"][0]["content_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="mismatch"):
        replay_finance_case_evaluation(mutated, expected)
    altered = deepcopy(expected)
    coverage(altered)["state"] = "partial"
    with pytest.raises(ValueError, match="mismatch"):
        replay_finance_case_evaluation(payload, altered)


def test_real_cli_evaluate_replay_and_managed_stdin(tmp_path):
    env = dict(
        os.environ, PYTHONPATH=os.pathsep.join((str(PACKAGE / "src"), str(ROOT)))
    )
    command = [sys.executable, "-m", "loopx_finance_value_discovery.cli"]
    input_path = PACKAGE / "examples/finance-source-coverage-v1.json"
    evaluated = subprocess.run(
        command + ["evaluate", "--input-json", str(input_path)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    evaluation = json.loads(evaluated.stdout)
    assert coverage(evaluation)["state"] == "complete"
    expected_path = tmp_path / "evaluation.json"
    expected_path.write_text(evaluated.stdout)
    replay = subprocess.run(
        command
        + [
            "replay",
            "--input-json",
            str(input_path),
            "--expected-json",
            str(expected_path),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(replay.stdout)["replay_verified"] is True
    managed = subprocess.run(
        command,
        input=input_path.read_text(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert canonical_json_bytes(json.loads(managed.stdout)) == canonical_json_bytes(
        evaluation
    )
    invalid = example()
    pages(invalid)[0]["observed_at"] = "invalid"
    failed = subprocess.run(
        command, input=json.dumps(invalid), env=env, capture_output=True, text=True
    )
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["ok"] is False


def test_opt_out_preserves_the_pre_coverage_replay_hash():
    legacy = json.loads((PACKAGE / "examples/finance-case-gates-v1.json").read_text())
    evaluation = result(legacy)
    # Captured from the shipped 0.4.0 implementation before this change.
    assert evaluation["replay"]["evaluation_sha256"] == (
        "8ff7517fe0e8d285d8144bae9b7d52f02d7ae2e397860bef25f83d2c8ea92015"
    )
    assert all("source_coverage" not in item for item in evaluation["gate_results"])


def test_coverage_gate_can_remain_not_run_after_an_earlier_blocker():
    payload = example()
    payload["contract"]["gates"].reverse()
    payload["observations"].reverse()
    payload["observations"][1] = {
        "gate_id": "disclosure_coverage",
        "observation_state": "not_run",
        "value": None,
        "evidence_refs": [],
        "reason": "Earlier evidence is missing.",
    }
    evaluation = result(payload)
    assert evaluation["gate_results"][1]["state"] == "not_run"
    assert "source_coverage" not in evaluation["gate_results"][1]


def test_duplicate_rows_and_terminal_flip_are_not_complete():
    for kind in ("duplicate", "terminal_flip"):
        payload = example()
        if kind == "duplicate":
            pages(payload)[0]["rows"] *= 2
        else:
            repeated = deepcopy(pages(payload)[0])
            repeated["has_more"] = True
            pages(payload).append(repeated)
        skip_later(payload)
        assert coverage(result(payload))["state"] == "unstable"


def test_offsets_compare_as_instants_and_date_only_cutoff_is_midnight():
    payload = example()
    pages(payload)[0].update(
        started_at="2026-01-02T09:00:00+08:00", observed_at="2026-01-02T09:01:00+08:00"
    )
    assert (
        coverage(result(payload))["records"][0]["first_observed_at"]
        == "2026-01-02T01:01:00+00:00"
    )
    payload["contract"]["evaluation_as_of"] = "2026-01-02"
    with pytest.raises(ValueError, match="observation_clock"):
        result(payload)
