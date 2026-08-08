"""Finance-owned decision-research presentation view schema.

This is the finance extension's OWN view contract. It is not a generic LoopX
Core presentation schema: Core keeps only the provider-neutral presentation
lifecycle envelope and explicitly loads the manifest-declared validator for
``decision_research_dashboard_v0``. Publishing a finance surface therefore
validates the finance view here, in the extension, rather than in Core.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .presentation_validation import (
    ANCHOR_RE,
    assert_allowed_keys_recursively as _assert_allowed_keys_recursively,
    boolean as _boolean,
    bounded_list as _bounded_list,
    enum as _enum,
    evidence_reference as _evidence_reference,
    identifier as _identifier,
    iso_value as _iso_value,
    number as _number,
    record as _record,
    required_text as _required_text,
    text_list as _text_list,
)

DECISION_RESEARCH_VIEW_SCHEMA_VERSION = "decision_research_dashboard_v0"


_DECISIONS = {
    "selected",
    "rejected",
    "insufficient_evidence",
    "blocked",
    "superseded",
}
_CONFIDENCE = {"high", "medium", "low"}
_TONES = {"neutral", "success", "warning", "info", "danger"}
_LAYER_STATES = {
    "supported",
    "partial",
    "rejected",
    "insufficient_evidence",
    "blocked",
    "pending",
}
_GATE_STATES = {
    "passed",
    "failed",
    "pending",
    "blocked",
    "insufficient_evidence",
    "partial",
}
_EVENT_STATES = {
    "pending",
    "partially_adjudicated",
    "selected",
    "rejected",
    "insufficient_evidence",
    "blocked",
    "superseded",
}


def _identity(value: Any) -> dict[str, Any]:
    record = _record(
        value,
        context="view.identity",
        allowed={"title", "subtitle", "as_of", "evidence_cutoff"},
    )
    return {
        "title": _required_text(record, "title", context="view.identity", max_length=160),
        "subtitle": _required_text(
            record,
            "subtitle",
            context="view.identity",
            max_length=240,
        ),
        "as_of": _iso_value(
            record.get("as_of"),
            context="view.identity.as_of",
            date_only_allowed=False,
        ),
        "evidence_cutoff": _iso_value(
            record.get("evidence_cutoff"),
            context="view.identity.evidence_cutoff",
        ),
    }


def _adjudication(value: Any) -> dict[str, Any]:
    record = _record(
        value,
        context="view.adjudication",
        allowed={"status", "label", "summary", "confidence"},
    )
    return {
        "status": _enum(
            record.get("status"),
            _DECISIONS,
            context="view.adjudication.status",
        ),
        "label": _required_text(
            record,
            "label",
            context="view.adjudication",
            max_length=120,
        ),
        "summary": _required_text(
            record,
            "summary",
            context="view.adjudication",
            max_length=800,
        ),
        "confidence": _enum(
            record.get("confidence"),
            _CONFIDENCE,
            context="view.adjudication.confidence",
        ),
    }


def _metrics(value: Any) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(value, context="view.metrics", minimum=1, maximum=12)
    ):
        context = f"view.metrics[{index}]"
        record = _record(
            item,
            context=context,
            allowed={"id", "label", "value", "detail", "tone"},
        )
        metrics.append(
            {
                "id": _identifier(record.get("id"), context=f"{context}.id"),
                "label": _required_text(record, "label", context=context, max_length=80),
                "value": _required_text(record, "value", context=context, max_length=120),
                "detail": _required_text(
                    record,
                    "detail",
                    context=context,
                    max_length=400,
                ),
                "tone": _enum(record.get("tone"), _TONES, context=f"{context}.tone"),
            }
        )
    return metrics


def _dashboard_summaries(value: Any) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(value, context="view.dashboard_summaries", maximum=3)
    ):
        context = f"view.dashboard_summaries[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "id",
                "label",
                "title",
                "summary",
                "tone",
                "destination_anchor",
            },
        )
        destination_anchor = _required_text(
            record,
            "destination_anchor",
            context=context,
            max_length=80,
        )
        if not ANCHOR_RE.fullmatch(destination_anchor):
            raise ValueError(
                f"{context}.destination_anchor must be a lower-kebab anchor"
            )
        summaries.append(
            {
                "id": _identifier(record.get("id"), context=f"{context}.id"),
                "label": _required_text(record, "label", context=context, max_length=80),
                "title": _required_text(record, "title", context=context, max_length=160),
                "summary": _required_text(
                    record,
                    "summary",
                    context=context,
                    max_length=500,
                ),
                "tone": _enum(record.get("tone"), _TONES, context=f"{context}.tone"),
                "destination_anchor": destination_anchor,
            }
        )
    return summaries


def _layers(value: Any) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    seen_orders: set[int] = set()
    for index, item in enumerate(
        _bounded_list(value, context="view.layers", minimum=1, maximum=12)
    ):
        context = f"view.layers[{index}]"
        record = _record(
            item,
            context=context,
            allowed={"id", "order", "label", "status", "summary", "evidence_points"},
        )
        order = record.get("order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ValueError(f"{context}.order must be a positive integer")
        if order in seen_orders:
            raise ValueError("view.layers order values must be unique")
        seen_orders.add(order)
        layers.append(
            {
                "id": _identifier(record.get("id"), context=f"{context}.id"),
                "order": order,
                "label": _required_text(record, "label", context=context, max_length=100),
                "status": _enum(
                    record.get("status"),
                    _LAYER_STATES,
                    context=f"{context}.status",
                ),
                "summary": _required_text(
                    record,
                    "summary",
                    context=context,
                    max_length=600,
                ),
                "evidence_points": _text_list(
                    record.get("evidence_points"),
                    context=f"{context}.evidence_points",
                    minimum=1,
                    maximum=12,
                ),
            }
        )
    return sorted(layers, key=lambda item: item["order"])


def _observations(value: Any, *, entity_context: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(
            value,
            context=f"{entity_context}.observations",
            minimum=1,
            maximum=20,
        )
    ):
        context = f"{entity_context}.observations[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "id",
                "label",
                "kind",
                "value",
                "as_of",
                "source_ref",
                "source_type",
                "confidence",
                "invalidation",
            },
        )
        kind = _enum(
            record.get("kind"),
            {
                "observation_range",
                "current_fact",
                "historical_fact",
                "management_guidance",
                "analyst_estimate",
                "agent_inference",
            },
            context=f"{context}.kind",
        )
        invalidation = _required_text(
            record,
            "invalidation",
            context=context,
            max_length=500,
        )
        observations.append(
            {
                "id": _identifier(record.get("id"), context=f"{context}.id"),
                "label": _required_text(record, "label", context=context, max_length=100),
                "kind": kind,
                "value": _required_text(record, "value", context=context, max_length=200),
                "as_of": _iso_value(record.get("as_of"), context=f"{context}.as_of"),
                "source_ref": _evidence_reference(
                    record.get("source_ref"),
                    context=f"{context}.source_ref",
                ),
                "source_type": _enum(
                    record.get("source_type"),
                    {
                        "company_filing",
                        "company_guidance",
                        "regulator",
                        "exchange",
                        "market_data",
                        "industry_source",
                        "high_quality_media",
                        "community_signal",
                        "agent_analysis",
                    },
                    context=f"{context}.source_type",
                ),
                "confidence": _enum(
                    record.get("confidence"),
                    _CONFIDENCE,
                    context=f"{context}.confidence",
                ),
                "invalidation": invalidation,
            }
        )
    return observations


def _scenario_estimates(
    value: Any,
    *,
    entity_context: str,
) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(
        _bounded_list(
            value,
            context=f"{entity_context}.scenario_estimates",
            minimum=3,
            maximum=3,
        )
    ):
        context = f"{entity_context}.scenario_estimates[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "scenario",
                "label",
                "value",
                "horizon",
                "probability",
                "assumptions",
            },
        )
        scenario = _enum(
            record.get("scenario"),
            {"bull", "base", "bear"},
            context=f"{context}.scenario",
        )
        if scenario in seen:
            raise ValueError(f"{entity_context}.scenario_estimates must be unique")
        seen.add(scenario)
        probability = _number(
            record.get("probability"),
            context=f"{context}.probability",
        )
        if probability < 0 or probability > 1:
            raise ValueError(f"{context}.probability must be between 0 and 1")
        scenarios.append(
            {
                "scenario": scenario,
                "label": _required_text(record, "label", context=context, max_length=100),
                "value": _required_text(record, "value", context=context, max_length=160),
                "horizon": _required_text(
                    record,
                    "horizon",
                    context=context,
                    max_length=100,
                ),
                "probability": probability,
                "assumptions": _text_list(
                    record.get("assumptions"),
                    context=f"{context}.assumptions",
                    minimum=1,
                    maximum=8,
                ),
            }
        )
    if seen != {"bull", "base", "bear"}:
        raise ValueError(
            f"{entity_context}.scenario_estimates must contain bull, base and bear"
        )
    if abs(sum(item["probability"] for item in scenarios) - 1.0) > 0.000001:
        raise ValueError(
            f"{entity_context}.scenario_estimates probabilities must sum to 1"
        )
    return scenarios


def _entities(value: Any) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(value, context="view.entities", maximum=24)
    ):
        context = f"view.entities[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "entity_id",
                "symbol",
                "display_name",
                "classification",
                "status",
                "confidence",
                "inference",
                "observations",
                "scenario_estimates",
                "counterevidence",
                "thesis_breakers",
                "next_events",
            },
        )
        entities.append(
            {
                "entity_id": _identifier(
                    record.get("entity_id"),
                    context=f"{context}.entity_id",
                ),
                "symbol": _required_text(
                    record,
                    "symbol",
                    context=context,
                    max_length=24,
                ),
                "display_name": _required_text(
                    record,
                    "display_name",
                    context=context,
                    max_length=160,
                ),
                "classification": _required_text(
                    record,
                    "classification",
                    context=context,
                    max_length=80,
                ),
                "status": _enum(
                    record.get("status"),
                    _DECISIONS,
                    context=f"{context}.status",
                ),
                "confidence": _enum(
                    record.get("confidence"),
                    _CONFIDENCE,
                    context=f"{context}.confidence",
                ),
                "inference": _required_text(
                    record,
                    "inference",
                    context=context,
                    max_length=700,
                ),
                "observations": _observations(
                    record.get("observations"),
                    entity_context=context,
                ),
                "scenario_estimates": _scenario_estimates(
                    record.get("scenario_estimates"),
                    entity_context=context,
                ),
                "counterevidence": _text_list(
                    record.get("counterevidence"),
                    context=f"{context}.counterevidence",
                    minimum=1,
                    maximum=12,
                ),
                "thesis_breakers": _text_list(
                    record.get("thesis_breakers"),
                    context=f"{context}.thesis_breakers",
                    minimum=1,
                    maximum=12,
                ),
                "next_events": _text_list(
                    record.get("next_events"),
                    context=f"{context}.next_events",
                    maximum=12,
                ),
            }
        )
    return entities


def _research_ledger(value: Any) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(value, context="view.research_ledger", maximum=40)
    ):
        context = f"view.research_ledger[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "case_id",
                "label",
                "gate_states",
                "decision",
                "summary",
                "evidence_refs",
            },
        )
        gate_states: list[dict[str, Any]] = []
        for gate_index, gate in enumerate(
            _bounded_list(
                record.get("gate_states"),
                context=f"{context}.gate_states",
                minimum=1,
                maximum=16,
            )
        ):
            gate_context = f"{context}.gate_states[{gate_index}]"
            gate_record = _record(
                gate,
                context=gate_context,
                allowed={"gate_id", "label", "status", "summary"},
            )
            gate_states.append(
                {
                    "gate_id": _identifier(
                        gate_record.get("gate_id"),
                        context=f"{gate_context}.gate_id",
                    ),
                    "label": _required_text(
                        gate_record,
                        "label",
                        context=gate_context,
                        max_length=100,
                    ),
                    "status": _enum(
                        gate_record.get("status"),
                        _GATE_STATES,
                        context=f"{gate_context}.status",
                    ),
                    "summary": _required_text(
                        gate_record,
                        "summary",
                        context=gate_context,
                        max_length=500,
                    ),
                }
            )
        evidence_refs = [
            _evidence_reference(
                reference,
                context=f"{context}.evidence_refs[{reference_index}]",
            )
            for reference_index, reference in enumerate(
                _bounded_list(
                    record.get("evidence_refs"),
                    context=f"{context}.evidence_refs",
                    minimum=1,
                    maximum=20,
                )
            )
        ]
        ledger.append(
            {
                "case_id": _identifier(
                    record.get("case_id"),
                    context=f"{context}.case_id",
                ),
                "label": _required_text(record, "label", context=context, max_length=180),
                "gate_states": gate_states,
                "decision": _enum(
                    record.get("decision"),
                    _DECISIONS,
                    context=f"{context}.decision",
                ),
                "summary": _required_text(
                    record,
                    "summary",
                    context=context,
                    max_length=700,
                ),
                "evidence_refs": evidence_refs,
            }
        )
    return ledger


def _artifacts(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    artifacts: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(value, context="view.artifacts", maximum=20)
    ):
        context = f"view.artifacts[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "artifact_id",
                "kind",
                "label",
                "summary",
                "artifact_ref",
                "evidence_refs",
            },
        )
        evidence_refs = [
            _evidence_reference(
                reference,
                context=f"{context}.evidence_refs[{reference_index}]",
            )
            for reference_index, reference in enumerate(
                _bounded_list(
                    record.get("evidence_refs"),
                    context=f"{context}.evidence_refs",
                    minimum=1,
                    maximum=20,
                )
            )
        ]
        artifacts.append(
            {
                "artifact_id": _identifier(
                    record.get("artifact_id"),
                    context=f"{context}.artifact_id",
                ),
                "kind": _enum(
                    record.get("kind"),
                    {
                        "research_packet",
                        "evidence_matrix",
                        "event_gate_packet",
                        "methodology_note",
                    },
                    context=f"{context}.kind",
                ),
                "label": _required_text(
                    record,
                    "label",
                    context=context,
                    max_length=160,
                ),
                "summary": _required_text(
                    record,
                    "summary",
                    context=context,
                    max_length=700,
                ),
                "artifact_ref": _evidence_reference(
                    record.get("artifact_ref"),
                    context=f"{context}.artifact_ref",
                ),
                "evidence_refs": evidence_refs,
            }
        )
    return artifacts


def _event_gates(value: Any) -> list[dict[str, Any]]:
    event_gates: list[dict[str, Any]] = []
    for index, item in enumerate(
        _bounded_list(value, context="view.event_gates", maximum=32)
    ):
        context = f"view.event_gates[{index}]"
        record = _record(
            item,
            context=context,
            allowed={
                "event_id",
                "label",
                "status",
                "observation_window",
                "frozen_hypothesis",
                "observables",
                "current_evidence",
                "supports",
                "refutes",
                "thesis_breakers",
                "next_review",
            },
        )
        event_gates.append(
            {
                "event_id": _identifier(
                    record.get("event_id"),
                    context=f"{context}.event_id",
                ),
                "label": _required_text(record, "label", context=context, max_length=180),
                "status": _enum(
                    record.get("status"),
                    _EVENT_STATES,
                    context=f"{context}.status",
                ),
                "observation_window": _required_text(
                    record,
                    "observation_window",
                    context=context,
                    max_length=240,
                ),
                "frozen_hypothesis": _required_text(
                    record,
                    "frozen_hypothesis",
                    context=context,
                    max_length=700,
                ),
                "observables": _text_list(
                    record.get("observables"),
                    context=f"{context}.observables",
                    minimum=1,
                    maximum=16,
                ),
                "current_evidence": _text_list(
                    record.get("current_evidence"),
                    context=f"{context}.current_evidence",
                    maximum=16,
                ),
                "supports": _text_list(
                    record.get("supports"),
                    context=f"{context}.supports",
                    minimum=1,
                    maximum=12,
                ),
                "refutes": _text_list(
                    record.get("refutes"),
                    context=f"{context}.refutes",
                    minimum=1,
                    maximum=12,
                ),
                "thesis_breakers": _text_list(
                    record.get("thesis_breakers"),
                    context=f"{context}.thesis_breakers",
                    minimum=1,
                    maximum=12,
                ),
                "next_review": _required_text(
                    record,
                    "next_review",
                    context=context,
                    max_length=240,
                ),
            }
        )
    return event_gates


def _method_state(value: Any) -> dict[str, Any]:
    record = _record(
        value,
        context="view.method_state",
        allowed={"revision", "lifecycle_state", "active_method_changed", "summary"},
    )
    return {
        "revision": _identifier(
            record.get("revision"),
            context="view.method_state.revision",
        ),
        "lifecycle_state": _identifier(
            record.get("lifecycle_state"),
            context="view.method_state.lifecycle_state",
        ),
        "active_method_changed": _boolean(
            record.get("active_method_changed"),
            context="view.method_state.active_method_changed",
        ),
        "summary": _required_text(
            record,
            "summary",
            context="view.method_state",
            max_length=500,
        ),
    }


def _boundary(value: Any) -> dict[str, Any]:
    record = _record(
        value,
        context="view.boundary",
        allowed={
            "research_aid_only",
            "investment_advice",
            "trading_allowed",
            "raw_provider_payload_recorded",
            "private_source_content_read",
        },
    )
    result = {
        key: _boolean(record.get(key), context=f"view.boundary.{key}")
        for key in (
            "research_aid_only",
            "investment_advice",
            "trading_allowed",
            "raw_provider_payload_recorded",
            "private_source_content_read",
        )
    }
    if result != {
        "research_aid_only": True,
        "investment_advice": False,
        "trading_allowed": False,
        "raw_provider_payload_recorded": False,
        "private_source_content_read": False,
    }:
        raise ValueError("view.boundary violates the research boundary")
    return result


def validate_decision_research_view(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one domain-neutral, presentation-oriented research view."""

    _assert_allowed_keys_recursively(value)
    record = _record(
        value,
        context="view",
        allowed={
            "identity",
            "adjudication",
            "metrics",
            "dashboard_summaries",
            "layers",
            "entities",
            "research_ledger",
            "artifacts",
            "event_gates",
            "method_state",
            "boundary",
        },
    )
    return {
        "identity": _identity(record.get("identity")),
        "adjudication": _adjudication(record.get("adjudication")),
        "metrics": _metrics(record.get("metrics")),
        "dashboard_summaries": _dashboard_summaries(
            record.get("dashboard_summaries")
        ),
        "layers": _layers(record.get("layers")),
        "entities": _entities(record.get("entities")),
        "research_ledger": _research_ledger(record.get("research_ledger")),
        "artifacts": _artifacts(record.get("artifacts")),
        "event_gates": _event_gates(record.get("event_gates")),
        "method_state": _method_state(record.get("method_state")),
        "boundary": _boundary(record.get("boundary")),
    }
