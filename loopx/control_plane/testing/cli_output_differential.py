from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal


CLI_OUTPUT_PROBE_SCHEMA_VERSION = "loopx_cli_output_probe_v0"
CLI_OUTPUT_FIXTURE_CONTRACT_VERSION = "loopx_cli_output_public_fixture_v0"
CLI_OUTPUT_DIFFERENTIAL_SCHEMA_VERSION = "loopx_cli_output_differential_v0"

Metric = Literal["chars", "utf8_bytes", "lines", "compact_payload_chars"]


@dataclass(frozen=True)
class GrowthAllowance:
    ratio: float
    json: dict[Metric, int]
    markdown: dict[Metric, int]


_GROWTH_ALLOWANCE_BY_POLICY: dict[str, GrowthAllowance] = {
    "absolute_hot_path": GrowthAllowance(
        ratio=0.005,
        json={"chars": 64, "utf8_bytes": 128, "lines": 2, "compact_payload_chars": 64},
        markdown={
            "chars": 32,
            "utf8_bytes": 64,
            "lines": 1,
            "compact_payload_chars": 0,
        },
    ),
    "baseline_and_growth": GrowthAllowance(
        ratio=0.005,
        json={
            "chars": 128,
            "utf8_bytes": 256,
            "lines": 2,
            "compact_payload_chars": 128,
        },
        markdown={
            "chars": 64,
            "utf8_bytes": 128,
            "lines": 1,
            "compact_payload_chars": 0,
        },
    ),
    "explicit_limit_cold_path": GrowthAllowance(
        ratio=0.01,
        json={
            "chars": 256,
            "utf8_bytes": 512,
            "lines": 3,
            "compact_payload_chars": 256,
        },
        markdown={
            "chars": 128,
            "utf8_bytes": 256,
            "lines": 2,
            "compact_payload_chars": 0,
        },
    ),
    "explicit_opt_in_cold_path": GrowthAllowance(
        ratio=0.01,
        json={
            "chars": 256,
            "utf8_bytes": 512,
            "lines": 3,
            "compact_payload_chars": 256,
        },
        markdown={
            "chars": 128,
            "utf8_bytes": 256,
            "lines": 2,
            "compact_payload_chars": 0,
        },
    ),
}


def _rows_by_id(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if receipt.get("schema_version") != CLI_OUTPUT_PROBE_SCHEMA_VERSION:
        raise ValueError("CLI output probe receipt has an unsupported schema_version")
    if receipt.get("fixture_contract_version") != CLI_OUTPUT_FIXTURE_CONTRACT_VERSION:
        raise ValueError(
            "CLI output probe receipt has an unsupported fixture_contract_version"
        )
    rows = receipt.get("rows")
    if not isinstance(rows, list):
        raise ValueError("CLI output probe receipt rows must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("row_id"), str):
            raise ValueError("CLI output probe row must be an object with row_id")
        row_id = row["row_id"]
        if row_id in indexed:
            raise ValueError(f"duplicate CLI output probe row_id: {row_id}")
        indexed[row_id] = row
    return indexed


def _growth_limit(*, policy: str, output_format: str, metric: Metric, base: int) -> int:
    allowance = _GROWTH_ALLOWANCE_BY_POLICY.get(policy)
    if allowance is None:
        raise ValueError(f"unsupported CLI output qualification policy: {policy}")
    floors = allowance.json if output_format == "json" else allowance.markdown
    return max(floors[metric], math.ceil(base * allowance.ratio))


def _removed(base: dict[str, Any], candidate: dict[str, Any], field: str) -> list[str]:
    base_values = {str(value) for value in base.get(field, [])}
    candidate_values = {str(value) for value in candidate.get(field, [])}
    return sorted(base_values - candidate_values)


def _compare_row(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    row_id = str(base["row_id"])
    failures: list[str] = []
    review_signals: list[str] = []
    policy = str(base.get("qualification_policy") or "")
    output_format = str(base.get("format") or "")
    if candidate.get("qualification_policy") != policy:
        failures.append("qualification_policy changed")
    if candidate.get("format") != output_format:
        failures.append("format changed")

    deltas: dict[str, int | None] = {}
    allowances: dict[str, int | None] = {}
    for metric in ("chars", "utf8_bytes", "lines", "compact_payload_chars"):
        base_value = base.get(metric)
        candidate_value = candidate.get(metric)
        if not isinstance(base_value, int) or not isinstance(candidate_value, int):
            deltas[metric] = None
            allowances[metric] = None
            continue
        delta = candidate_value - base_value
        allowance = _growth_limit(
            policy=policy,
            output_format=output_format,
            metric=metric,
            base=base_value,
        )
        deltas[metric] = delta
        allowances[metric] = allowance
        if delta > allowance:
            failures.append(f"{metric} grew by {delta}; allowance is {allowance}")

    for field in ("semantic_json_keys",):
        missing = _removed(base, candidate, field)
        if missing:
            preview = ", ".join(missing[:5])
            suffix = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            failures.append(f"{field} removed: {preview}{suffix}")

    for field in ("json_shape_paths", "markdown_headings"):
        missing = _removed(base, candidate, field)
        if missing:
            preview = ", ".join(missing[:5])
            suffix = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            review_signals.append(f"{field} removed: {preview}{suffix}")

    base_anchor = base.get("markdown_anchor")
    if base_anchor and candidate.get("markdown_anchor") != base_anchor:
        failures.append("markdown_anchor changed")
    base_signature = base.get("action_signature_sha256")
    if base_signature and candidate.get("action_signature_sha256") != base_signature:
        failures.append("action_signature semantic digest changed")

    return {
        "row_id": row_id,
        "status": "failed" if failures else "passed",
        "deltas": deltas,
        "allowances": allowances,
        "failures": failures,
        "review_signals": review_signals,
    }


def compare_cli_output_receipts(
    base_receipt: dict[str, Any],
    candidate_receipt: dict[str, Any],
) -> dict[str, Any]:
    base_rows = _rows_by_id(base_receipt)
    candidate_rows = _rows_by_id(candidate_receipt)
    results: list[dict[str, Any]] = []
    for row_id in sorted(base_rows.keys() | candidate_rows.keys()):
        base = base_rows.get(row_id)
        candidate = candidate_rows.get(row_id)
        if base is None:
            results.append(
                {
                    "row_id": row_id,
                    "status": "candidate_only",
                    "deltas": {},
                    "allowances": {},
                    "failures": [],
                    "review_signals": [],
                }
            )
        elif candidate is None:
            results.append(
                {
                    "row_id": row_id,
                    "status": "failed",
                    "deltas": {},
                    "allowances": {},
                    "failures": ["qualified base row is missing from candidate"],
                    "review_signals": [],
                }
            )
        else:
            results.append(_compare_row(base, candidate))

    failed_rows = [row for row in results if row["status"] == "failed"]
    review_rows = [row for row in results if row["review_signals"]]
    return {
        "schema_version": CLI_OUTPUT_DIFFERENTIAL_SCHEMA_VERSION,
        "ok": not failed_rows,
        "base_row_count": len(base_rows),
        "candidate_row_count": len(candidate_rows),
        "compared_row_count": len(results),
        "failed_row_count": len(failed_rows),
        "review_required": bool(review_rows),
        "review_row_count": len(review_rows),
        "candidate_only_row_count": sum(
            row["status"] == "candidate_only" for row in results
        ),
        "rows": results,
    }
