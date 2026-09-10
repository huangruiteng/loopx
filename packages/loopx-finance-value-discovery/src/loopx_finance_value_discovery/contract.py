from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from math import isfinite
from typing import Any

from .boundary import reject_forbidden_material
from .source_coverage import validate_coverage_requirement

FINANCE_CASE_CONTRACT_SCHEMA_VERSION = "finance_case_contract_v1"
FINANCE_CASE_INPUT_SCHEMA_VERSION = "finance_case_gate_input_v1"
FINANCE_CASE_EVALUATION_SCHEMA_VERSION = "finance_case_gate_evaluation_v1"

MIN_GATE_COUNT = 1
MAX_GATE_COUNT = 16
VALUE_TYPES = {"boolean", "number", "string"}
OPERATORS_BY_VALUE_TYPE = {
    "boolean": {"eq"},
    "number": {"eq", "gt", "gte", "lt", "lte"},
    "string": {"eq"},
}


def _text(value: object, *, field: str, limit: int = 160) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise ValueError(f"{field} is required")
    if len(result) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    reject_forbidden_material(result, path=field)
    return result


def validate_iso_date(value: object, *, field: str) -> str:
    result = _text(value, field=field, limit=40)
    try:
        if "T" in result:
            datetime.fromisoformat(result.replace("Z", "+00:00"))
        else:
            date.fromisoformat(result)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 date or datetime") from exc
    return result


def iso_comparable_datetime(value: str) -> datetime:
    """Parse an ISO date or datetime into a comparable datetime (UTC-naive)."""
    if "T" in value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed
    return datetime.combine(date.fromisoformat(value), datetime.min.time())


def _required_boolean(
    payload: Mapping[str, Any],
    field: str,
    *,
    expected: bool,
) -> bool:
    if payload.get(field) is not expected:
        raise ValueError(f"{field} must be {str(expected).lower()}")
    return expected


def _gate_rule(value: object, *, index: int) -> dict[str, Any]:
    field = f"contract.gates[{index}]"
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    allowed = {"gate_id", "value_type", "operator", "reference_value", "source_coverage"}
    if set(value) - allowed:
        raise ValueError(f"{field} has unsupported fields")
    value_type = _text(
        value.get("value_type"), field=f"{field}.value_type", limit=24
    )
    if value_type not in VALUE_TYPES:
        raise ValueError(f"{field}.value_type must be one of {sorted(VALUE_TYPES)}")
    operator = _text(value.get("operator"), field=f"{field}.operator", limit=16)
    if operator not in OPERATORS_BY_VALUE_TYPE[value_type]:
        raise ValueError(
            f"{field}.operator must be one of "
            f"{sorted(OPERATORS_BY_VALUE_TYPE[value_type])}"
        )
    reference = value.get("reference_value")
    if value_type == "boolean" and not isinstance(reference, bool):
        raise ValueError(f"{field}.reference_value must be a boolean")
    if value_type == "number":
        if not isinstance(reference, (int, float)) or isinstance(reference, bool):
            raise ValueError(f"{field}.reference_value must be a number")
        if isinstance(reference, float) and not isfinite(reference):
            raise ValueError(f"{field}.reference_value must be a finite number")
    if value_type == "string":
        reference = _text(
            reference, field=f"{field}.reference_value", limit=120
        )
    rule = {
        "gate_id": _text(value.get("gate_id"), field=f"{field}.gate_id", limit=80),
        "value_type": value_type,
        "operator": operator,
        "reference_value": reference,
    }
    if "source_coverage" in value:
        if value_type != "boolean" or operator != "eq" or reference is not True:
            raise ValueError("source_coverage requires a boolean eq true gate")
        rule["source_coverage"] = validate_coverage_requirement(value["source_coverage"])
    return rule


def validate_finance_case_contract(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("contract must be an object")
    reject_forbidden_material(value, path="contract")
    allowed = {
        "schema_version",
        "contract_id",
        "method_revision",
        "point_in_time",
        "evaluation_as_of",
        "universe_id",
        "universe_frozen",
        "identities_frozen",
        "thresholds_frozen",
        "outcome_blind",
        "public_evidence_only",
        "gates",
        "investment_advice_allowed",
        "trading_allowed",
        "automatic_promotion_allowed",
    }
    if set(value) - allowed:
        raise ValueError("contract has unsupported fields")
    if value.get("schema_version") != FINANCE_CASE_CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"contract.schema_version must be {FINANCE_CASE_CONTRACT_SCHEMA_VERSION}"
        )
    raw_gates = value.get("gates")
    if not isinstance(raw_gates, Sequence) or isinstance(
        raw_gates, (str, bytes, bytearray)
    ):
        raise ValueError("contract.gates must be a list")
    if not MIN_GATE_COUNT <= len(raw_gates) <= MAX_GATE_COUNT:
        raise ValueError(
            f"contract.gates must contain between {MIN_GATE_COUNT} "
            f"and {MAX_GATE_COUNT} gates"
        )
    gates = [
        _gate_rule(item, index=index)
        for index, item in enumerate(raw_gates)
    ]
    gate_ids = [item["gate_id"] for item in gates]
    if len(gate_ids) != len(set(gate_ids)):
        raise ValueError("contract.gates must use unique gate ids")
    point_in_time = validate_iso_date(
        value.get("point_in_time"), field="contract.point_in_time"
    )
    evaluation_as_of = validate_iso_date(
        value.get("evaluation_as_of"), field="contract.evaluation_as_of"
    )
    if iso_comparable_datetime(point_in_time) > iso_comparable_datetime(evaluation_as_of):
        raise ValueError(
            "contract.point_in_time must not be after contract.evaluation_as_of"
        )
    universe_id = _text(value.get("universe_id"), field="contract.universe_id", limit=96)
    for rule in gates:
        requirement = rule.get("source_coverage")
        if requirement is None:
            continue
        if requirement["request_identity"]["universe_id"] != universe_id:
            raise ValueError("source_coverage universe_id must match contract.universe_id")
        if not (
            iso_comparable_datetime(point_in_time)
            <= iso_comparable_datetime(requirement["collection_started_at"])
            <= iso_comparable_datetime(evaluation_as_of)
        ):
            raise ValueError(
                "source_coverage collection start must be inside the case window"
            )
    return {
        "schema_version": FINANCE_CASE_CONTRACT_SCHEMA_VERSION,
        "contract_id": _text(
            value.get("contract_id"), field="contract.contract_id", limit=96
        ),
        "method_revision": _text(
            value.get("method_revision"),
            field="contract.method_revision",
            limit=96,
        ),
        "point_in_time": point_in_time,
        "evaluation_as_of": evaluation_as_of,
        "universe_id": universe_id,
        "universe_frozen": _required_boolean(
            value, "universe_frozen", expected=True
        ),
        "identities_frozen": _required_boolean(
            value, "identities_frozen", expected=True
        ),
        "thresholds_frozen": _required_boolean(
            value, "thresholds_frozen", expected=True
        ),
        # These two remain caller assertions until a public lineage contract can
        # verify them; the engine records the assertion state rather than
        # projecting an unverified guarantee as fact.
        "outcome_blind_state": (
            "caller_asserted"
            if _required_boolean(value, "outcome_blind", expected=True)
            else "unset"
        ),
        "public_evidence_only_state": (
            "caller_asserted"
            if _required_boolean(value, "public_evidence_only", expected=True)
            else "unset"
        ),
        "gates": gates,
        "investment_advice_allowed": _required_boolean(
            value, "investment_advice_allowed", expected=False
        ),
        "trading_allowed": _required_boolean(
            value, "trading_allowed", expected=False
        ),
        "automatic_promotion_allowed": _required_boolean(
            value, "automatic_promotion_allowed", expected=False
        ),
    }


def validate_finance_case_input(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("finance case input must be an object")
    reject_forbidden_material(value)
    allowed = {"schema_version", "case_id", "subject_ref", "contract", "observations"}
    if set(value) - allowed:
        raise ValueError("finance case input has unsupported fields")
    if value.get("schema_version") != FINANCE_CASE_INPUT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {FINANCE_CASE_INPUT_SCHEMA_VERSION}"
        )
    observations = value.get("observations")
    if not isinstance(observations, Sequence) or isinstance(
        observations, (str, bytes, bytearray)
    ):
        raise ValueError("observations must be a list")
    return {
        "schema_version": FINANCE_CASE_INPUT_SCHEMA_VERSION,
        "case_id": _text(value.get("case_id"), field="case_id", limit=96),
        # The subject the gated case is about. Binding it here makes it part of
        # the canonical case identity, so a passing gate cannot be reused to
        # present an attribution for a different security as research-complete.
        "subject_ref": _text(
            value.get("subject_ref"), field="subject_ref", limit=96
        ),
        "contract": validate_finance_case_contract(value.get("contract")),
        "observations": list(observations),
    }
