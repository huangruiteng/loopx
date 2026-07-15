from __future__ import annotations

import copy
import json

import pytest

from loopx.control_plane.testing.cli_output_budget import measure_cli_output
from loopx.control_plane.testing.cli_output_differential import (
    CLI_OUTPUT_FIXTURE_CONTRACT_VERSION,
    CLI_OUTPUT_PROBE_SCHEMA_VERSION,
    compare_cli_output_receipts,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "row_id": "surface/status/small/json",
        "surface_id": "status",
        "variant_id": None,
        "scenario": "small",
        "format": "json",
        "qualification_policy": "absolute_hot_path",
        "chars": 40_000,
        "utf8_bytes": 40_000,
        "lines": 1_000,
        "compact_payload_chars": 20_000,
        "semantic_json_keys": ["status_contract", "attention_queue"],
        "json_shape_paths": ["$", "$.status_contract", "$.attention_queue"],
        "markdown_headings": [],
        "markdown_anchor": "# LoopX Status",
        "action_signature_sha256": "semantic-signature",
    }
    row.update(overrides)
    return row


def _receipt(*rows: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": CLI_OUTPUT_PROBE_SCHEMA_VERSION,
        "fixture_contract_version": CLI_OUTPUT_FIXTURE_CONTRACT_VERSION,
        "rows": list(rows),
    }


def test_measurement_records_semantic_shape_without_runtime_hash_noise() -> None:
    def payload(runtime_hash: str, source_hash: str) -> str:
        return json.dumps(
            {
                "action": {"todo_id": "todo_fixture"},
                "action_signature": {
                    "schema_version": "loopx_action_signature_v0",
                    "coverage": ["action", "writeback"],
                    "source_hash": runtime_hash,
                    "envelope_hash": runtime_hash,
                    "source_decision_hash": source_hash,
                    "matches": True,
                },
            }
        )

    first = measure_cli_output(
        payload("first-runtime", "first-source"), output_format="json"
    )
    second = measure_cli_output(
        payload("second-runtime", "second-source"),
        output_format="json",
    )
    assert "$.action.todo_id" in first["json_shape_paths"]
    assert first["action_signature_sha256"] == second["action_signature_sha256"]

    with_observability_field = json.loads(payload("third-runtime", "third-source"))
    with_observability_field["action_signature"]["diagnostic_note"] = "new"
    third = measure_cli_output(
        json.dumps(with_observability_field),
        output_format="json",
    )
    assert first["action_signature_sha256"] == third["action_signature_sha256"]

    without_hash_pair = json.loads(payload("fourth-runtime", "fourth-source"))
    del without_hash_pair["action_signature"]["source_hash"]
    del without_hash_pair["action_signature"]["envelope_hash"]
    fourth = measure_cli_output(json.dumps(without_hash_pair), output_format="json")
    assert first["action_signature_sha256"] != fourth["action_signature_sha256"]

    markdown = measure_cli_output(
        "# LoopX Status\n\n## Attention Queue\n",
        output_format="markdown",
    )
    assert markdown["markdown_headings"] == ["# LoopX Status", "## Attention Queue"]


def test_unchanged_large_inherited_baseline_passes() -> None:
    base = _receipt(_row())
    result = compare_cli_output_receipts(base, copy.deepcopy(base))
    assert result["ok"] is True
    assert result["failed_row_count"] == 0


def test_growth_above_policy_allowance_fails() -> None:
    base = _receipt(_row())
    candidate = _receipt(_row(chars=41_000))
    result = compare_cli_output_receipts(base, candidate)
    assert result["ok"] is False
    assert "chars grew" in result["rows"][0]["failures"][0]


def test_shrink_with_semantic_shape_retained_passes() -> None:
    base = _receipt(_row())
    candidate = _receipt(
        _row(chars=20_000, utf8_bytes=20_000, lines=500, compact_payload_chars=10_000)
    )
    assert compare_cli_output_receipts(base, candidate)["ok"] is True


@pytest.mark.parametrize(
    ("candidate", "failure_fragment"),
    [
        (_row(semantic_json_keys=["status_contract"]), "semantic_json_keys removed"),
        (
            _row(action_signature_sha256="changed"),
            "action_signature semantic digest changed",
        ),
    ],
)
def test_smaller_candidate_still_fails_when_semantics_are_removed(
    candidate: dict[str, object],
    failure_fragment: str,
) -> None:
    candidate.update(chars=20_000, utf8_bytes=20_000, lines=500)
    result = compare_cli_output_receipts(_receipt(_row()), _receipt(candidate))
    assert result["ok"] is False
    assert any(failure_fragment in failure for failure in result["rows"][0]["failures"])


def test_observed_shape_removal_is_a_review_signal_not_a_permanent_red_light() -> None:
    candidate = _row(json_shape_paths=["$", "$.status_contract"])
    candidate.update(chars=20_000, utf8_bytes=20_000, lines=500)
    result = compare_cli_output_receipts(_receipt(_row()), _receipt(candidate))
    assert result["ok"] is True
    assert result["review_required"] is True
    assert "json_shape_paths removed" in result["rows"][0]["review_signals"][0]


def test_markdown_heading_removal_requires_review() -> None:
    base_row = _row(
        row_id="surface/status/small/markdown",
        format="markdown",
        chars=2_000,
        utf8_bytes=2_000,
        lines=30,
        compact_payload_chars=None,
        semantic_json_keys=[],
        json_shape_paths=[],
        markdown_headings=["# LoopX Status", "## Attention Queue"],
        action_signature_sha256=None,
    )
    candidate = copy.deepcopy(base_row)
    candidate["markdown_headings"] = ["# LoopX Status"]
    result = compare_cli_output_receipts(_receipt(base_row), _receipt(candidate))
    assert result["ok"] is True
    assert result["review_required"] is True
    assert "markdown_headings removed" in result["rows"][0]["review_signals"][0]


def test_candidate_only_row_is_allowed_but_base_row_removal_fails() -> None:
    extra = _row(row_id="surface/new/small/json", surface_id="new")
    candidate_only = compare_cli_output_receipts(_receipt(), _receipt(extra))
    assert candidate_only["ok"] is True
    assert candidate_only["candidate_only_row_count"] == 1

    removed = compare_cli_output_receipts(_receipt(_row()), _receipt())
    assert removed["ok"] is False
    assert "missing from candidate" in removed["rows"][0]["failures"][0]


def test_fixture_contract_mismatch_fails_closed() -> None:
    candidate = _receipt(_row())
    candidate["fixture_contract_version"] = "different"
    with pytest.raises(ValueError, match="fixture_contract_version"):
        compare_cli_output_receipts(_receipt(_row()), candidate)
