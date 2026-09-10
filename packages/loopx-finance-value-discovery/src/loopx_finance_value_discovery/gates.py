from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

from .boundary import reject_forbidden_material
from .contract import (
    FINANCE_CASE_EVALUATION_SCHEMA_VERSION,
    validate_finance_case_input,
)
from .source_coverage import coverage_observation

OBSERVATION_STATES = {"observed", "missing", "conflict", "not_run"}
BLOCKING_GATE_STATES = {"failed", "missing", "conflict"}
DISPOSITION_BY_BLOCKING_STATE = {
    "failed": "rejected",
    "missing": "insufficient_evidence",
    "conflict": "insufficient_evidence",
}


def _text(value: object, *, field: str, limit: int = 320) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise ValueError(f"{field} is required")
    if len(result) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    reject_forbidden_material(result, path=field)
    return result


def _evidence_refs(value: object, *, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be a list")
    if len(value) > 12:
        raise ValueError(f"{field} must contain at most 12 items")
    refs = [
        _text(item, field=f"{field}[{index}]", limit=120)
        for index, item in enumerate(value)
    ]
    if len(refs) != len(set(refs)):
        raise ValueError(f"{field} must use unique evidence refs")
    return refs


def _observation(value: object, *, index: int) -> dict[str, Any]:
    field = f"observations[{index}]"
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    allowed = {
        "gate_id",
        "observation_state",
        "value",
        "evidence_refs",
        "reason",
    }
    if set(value) - allowed:
        raise ValueError(f"{field} has unsupported fields")
    observation_state = _text(
        value.get("observation_state"),
        field=f"{field}.observation_state",
        limit=24,
    )
    if observation_state not in OBSERVATION_STATES:
        raise ValueError(
            f"{field}.observation_state must be one of "
            f"{sorted(OBSERVATION_STATES)}"
        )
    refs = _evidence_refs(value.get("evidence_refs"), field=f"{field}.evidence_refs")
    if observation_state == "observed" and not refs:
        raise ValueError(f"{field} observed values require evidence_refs")
    if observation_state == "conflict" and len(refs) < 2:
        raise ValueError(f"{field} conflicts require at least two evidence_refs")
    if observation_state == "not_run" and refs:
        raise ValueError(f"{field} not_run cannot include evidence_refs")
    observed_value = value.get("value")
    if observation_state == "observed" and observed_value is None:
        raise ValueError(f"{field} observed values require value")
    if observation_state != "observed" and observed_value is not None:
        raise ValueError(f"{field} value is only valid when observed")
    return {
        "gate_id": _text(value.get("gate_id"), field=f"{field}.gate_id", limit=80),
        "observation_state": observation_state,
        "value": observed_value,
        "evidence_refs": refs,
        "reason": _text(value.get("reason"), field=f"{field}.reason"),
    }


def _observed_value_matches(rule: Mapping[str, Any], value: object) -> bool:
    value_type = rule["value_type"]
    if value_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"gate {rule['gate_id']} value must be a boolean")
    elif value_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"gate {rule['gate_id']} value must be a number")
        if isinstance(value, float) and not isfinite(value):
            raise ValueError(f"gate {rule['gate_id']} value must be a finite number")
    elif value_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"gate {rule['gate_id']} value must be a string")
        reject_forbidden_material(value, path=f"gate {rule['gate_id']} value")

    reference = rule["reference_value"]
    operator = rule["operator"]
    if operator == "eq":
        return value == reference
    if operator == "gt":
        return value > reference
    if operator == "gte":
        return value >= reference
    if operator == "lt":
        return value < reference
    if operator == "lte":
        return value <= reference
    raise ValueError(f"gate {rule['gate_id']} has unsupported operator")


def evaluate_finance_case_gates(value: object) -> dict[str, Any]:
    payload = validate_finance_case_input(value)
    contract = payload["contract"]
    if len(payload["observations"]) != len(contract["gates"]):
        raise ValueError("observations must exactly match contract.gates order")
    observations = []
    for index, (rule, item) in enumerate(
        zip(contract["gates"], payload["observations"], strict=True)
    ):
        if (
            "source_coverage" in rule
            and isinstance(item, Mapping)
            and item.get("observation_state") != "not_run"
        ):
            observation = coverage_observation(
                item, rule=rule, evaluation_as_of=contract["evaluation_as_of"]
            )
        else:
            observation = _observation(item, index=index)
        observations.append(observation)
    gate_order = [item["gate_id"] for item in contract["gates"]]
    observed_order = [item["gate_id"] for item in observations]
    if observed_order != gate_order:
        raise ValueError("observations must exactly match contract.gates order")

    blocking_gate: dict[str, Any] | None = None
    gate_results: list[dict[str, Any]] = []
    for rule, observation in zip(contract["gates"], observations, strict=True):
        observation_state = observation["observation_state"]
        if blocking_gate is not None:
            if observation_state != "not_run":
                raise ValueError(
                    "gates after the first blocking gate must use state=not_run"
                )
            state = "not_run"
            gate_results.append({**observation, "rule": rule, "state": state})
            continue
        if observation_state == "not_run":
            raise ValueError("state=not_run requires an earlier blocking gate")
        state = observation_state
        if observation_state == "observed":
            state = (
                "passed"
                if _observed_value_matches(rule, observation["value"])
                else "failed"
            )
        gate_result = {**observation, "rule": rule, "state": state}
        gate_results.append(gate_result)
        if state in BLOCKING_GATE_STATES:
            blocking_gate = gate_result

    if blocking_gate is None:
        disposition = "eligible_for_research_successor"
    else:
        disposition = DISPOSITION_BY_BLOCKING_STATE[blocking_gate["state"]]
    return {
        "ok": True,
        "schema_version": FINANCE_CASE_EVALUATION_SCHEMA_VERSION,
        "case_id": payload["case_id"],
        "subject_ref": payload["subject_ref"],
        "contract": contract,
        "gate_results": gate_results,
        "disposition": disposition,
        "first_blocking_gate": (
            {
                "gate_id": blocking_gate["gate_id"],
                "state": blocking_gate["state"],
                "reason": blocking_gate["reason"],
            }
            if blocking_gate is not None
            else None
        ),
        "boundary": {
            "public_evidence_only_state": contract["public_evidence_only_state"],
            "outcome_blind_state": contract["outcome_blind_state"],
            "investment_advice": False,
            "trading_allowed": False,
            "automatic_promotion_allowed": False,
            "human_decision_owner": True,
        },
    }
