from __future__ import annotations

from typing import Any, Callable, Optional


CompactProjection = Callable[[Any], Optional[dict[str, Any]]]
NormalizeOperatorQuestion = Callable[..., str]


def readiness_attention_fields(
    run: dict[str, Any] | None,
    *,
    compact_controller_readiness: CompactProjection,
) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if not readiness:
        return {}
    fields: dict[str, Any] = {}
    if readiness.get("classification"):
        fields["controller_stage"] = readiness.get("classification")
    missing = readiness.get("missing_gates")
    if isinstance(missing, list):
        public_missing = [str(gate) for gate in missing if gate]
        if public_missing:
            fields["missing_gates"] = public_missing
    if readiness.get("next_handoff_condition"):
        fields["next_handoff_condition"] = readiness.get("next_handoff_condition")
    return fields


def operator_gate_attention_fields(
    run: dict[str, Any] | None,
    *,
    compact_operator_gate: CompactProjection,
    normalize_operator_question: NormalizeOperatorQuestion,
    default_operator_gate: str,
) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if not operator_gate:
        return {}
    fields: dict[str, Any] = {}
    if operator_gate.get("decision") != "approve" and operator_gate.get("operator_question"):
        fields["operator_question"] = normalize_operator_question(
            str(operator_gate.get("operator_question") or ""),
            goal_id=str(run.get("goal_id") or ""),
            gate=str(operator_gate.get("gate") or default_operator_gate),
        )
    if operator_gate.get("decision") == "approve" and operator_gate.get("agent_command"):
        fields["agent_command"] = operator_gate.get("agent_command")
    if operator_gate.get("follow_up"):
        fields["next_handoff_condition"] = operator_gate.get("follow_up")
    return fields
