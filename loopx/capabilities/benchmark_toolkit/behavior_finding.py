"""Bounded observational findings without complete benchmark result uploads.

This is a benchmark-toolkit record, not a new provider or scoring authority.
Evidence digests are producer attestations; validation cannot verify unshared
trajectories or turn a selected example into a population effect.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .study_projection import (
    _DIGEST_RE,
    _active_envelopes,
    _bounded_text,
    _finite_number,
    _reject_unknown_fields,
    _token,
)

BENCHMARK_BEHAVIOR_FINDING_SCHEMA_VERSION = "benchmark_behavior_finding_v0"


def _object(value: Any, fields: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    _reject_unknown_fields(value, allowed=fields, field=name)
    if set(value) != fields:
        raise ValueError(f"{name} requires: {', '.join(sorted(fields))}")
    return value


def _choice(value: Any, choices: set[str], name: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(sorted(choices))}")
    return value


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _items(value: Any, name: str, *, minimum: int = 1, maximum: int = 16) -> list:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} requires {minimum} to {maximum} items")
    return value


def normalize_benchmark_behavior_finding(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an analysis-only finding, with explicit sampling and limitations."""
    fields = {
        "schema_version",
        "benchmark_id",
        "study_id",
        "finding_id",
        "title",
        "claim_scope",
        "settings",
        "selection",
        "observation",
        "interpretation",
        "measures",
        "evidence",
        "limitations",
        "counterevidence",
        "next_probe",
        "privacy_classification",
        "producer_redaction_attested",
    }
    p = _object(payload, fields, "behavior finding")
    if p["schema_version"] != BENCHMARK_BEHAVIOR_FINDING_SCHEMA_VERSION:
        raise ValueError("behavior finding schema mismatch")
    if p["claim_scope"] != "exploratory_behavior":
        raise ValueError("behavior findings only support exploratory_behavior")
    if (
        p["privacy_classification"] != "public_safe"
        or p["producer_redaction_attested"] is not True
    ):
        raise ValueError("behavior findings require public_safe redaction attestation")
    selection = _object(
        p["selection"],
        {
            "basis",
            "rule",
            "unit",
            "population_count",
            "sample_count",
            "cohort_digest",
        },
        "selection",
    )
    population = _count(selection["population_count"], "population_count")
    sample = _count(selection["sample_count"], "sample_count")
    if sample > population:
        raise ValueError("sample_count cannot exceed population_count")
    digest = selection["cohort_digest"]
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        raise ValueError("cohort_digest must be SHA-256")
    measures = []
    for item in _items(p["measures"], "measures", minimum=0):
        m = _object(
            item, {"name", "unit", "aggregation", "groups", "caveat"}, "measure"
        )
        groups = []
        for group in _items(m["groups"], "measure groups"):
            g = _object(group, {"label", "value", "n"}, "group")
            n = _count(g["n"], "group.n")
            if n > sample:
                raise ValueError("group.n cannot exceed sample_count")
            groups.append(
                {
                    "label": _bounded_text(g["label"], field="label", limit=100),
                    "value": _finite_number(g["value"], field="value"),
                    "n": n,
                }
            )
        if len({g["label"] for g in groups}) != len(groups):
            raise ValueError("measure group labels must be unique")
        if m["aggregation"] == "count" and any(
            g["value"] != int(g["value"]) or not 0 <= g["value"] <= g["n"]
            for g in groups
        ):
            raise ValueError("count must be an integer between zero and group.n")
        if m["aggregation"] == "rate" and any(not 0 <= g["value"] <= 1 for g in groups):
            raise ValueError("rate must be a fraction between zero and one")
        measures.append(
            {
                "name": _bounded_text(m["name"], field="measure.name", limit=120),
                "unit": _token(m["unit"], field="unit"),
                "aggregation": _choice(
                    m["aggregation"],
                    {"count", "sum", "mean", "median", "rate", "difference"},
                    "aggregation",
                ),
                "groups": groups,
                "caveat": _bounded_text(m["caveat"], field="caveat"),
            }
        )
    evidence = []
    for item in _items(p["evidence"], "evidence"):
        e = _object(
            item, {"kind", "digest", "label", "relation", "summary"}, "evidence"
        )
        if not isinstance(e["digest"], str) or not _DIGEST_RE.fullmatch(e["digest"]):
            raise ValueError("evidence digest must be SHA-256")
        evidence.append(
            {
                "kind": _choice(
                    e["kind"],
                    {"case_insight", "cohort_summary", "protocol"},
                    "evidence.kind",
                ),
                "digest": e["digest"],
                "label": _bounded_text(e["label"], field="label", limit=160),
                "relation": _choice(
                    e["relation"], {"supports", "contradicts", "context"}, "relation"
                ),
                "summary": _bounded_text(e["summary"], field="summary"),
            }
        )
    return {
        "schema_version": BENCHMARK_BEHAVIOR_FINDING_SCHEMA_VERSION,
        **{
            k: _token(p[k], field=k) for k in ("benchmark_id", "study_id", "finding_id")
        },
        "title": _bounded_text(p["title"], field="title", limit=160),
        "claim_scope": "exploratory_behavior",
        "settings": _bounded_text(p["settings"], field="settings", limit=2000),
        "selection": {
            "basis": _choice(
                selection["basis"],
                {"post_hoc", "predeclared", "all_available"},
                "selection.basis",
            ),
            "rule": _bounded_text(
                selection["rule"], field="selection.rule", limit=1200
            ),
            "unit": _token(selection["unit"], field="selection.unit"),
            "population_count": population,
            "sample_count": sample,
            "cohort_digest": digest,
        },
        **{
            k: _bounded_text(p[k], field=k, limit=2000)
            for k in ("observation", "interpretation", "counterevidence", "next_probe")
        },
        "limitations": [
            _bounded_text(v, field="limitation")
            for v in _items(p["limitations"], "limitations")
        ],
        "measures": measures,
        "evidence": evidence,
        "privacy_classification": "public_safe",
        "producer_redaction_attested": True,
    }


def build_benchmark_behavior_report(
    records: Iterable[Mapping[str, Any]],
    *,
    benchmark_id: str,
    study_id: str,
) -> dict[str, Any]:
    """Project active findings only; never derive leaderboard or arm scores."""
    benchmark_id = _token(benchmark_id, field="benchmark_id")
    study_id = _token(study_id, field="study_id")
    selected = [
        e
        for e in _active_envelopes(records)
        if e["record_kind"] == "behavior_finding"
        and e["benchmark_id"] == benchmark_id
        and e["study_id"] == study_id
    ]
    if len({e["payload"]["finding_id"] for e in selected}) != len(selected):
        raise ValueError("active behavior findings must have unique finding_id")
    return {
        "schema_version": "benchmark_behavior_report_v0",
        "benchmark_id": benchmark_id,
        "study_id": study_id,
        "claim_scope": "exploratory_behavior",
        "score_authority": False,
        "evidence_verification": "producer_attested_unshared_sources_not_verified",
        "findings": [
            {
                "finding": e["payload"],
                "provenance": {
                    k: e[k]
                    for k in (
                        "record_id",
                        "payload_digest",
                        "source_revision",
                        "producer_id",
                        "observed_at",
                    )
                },
            }
            for e in selected
        ],
    }
