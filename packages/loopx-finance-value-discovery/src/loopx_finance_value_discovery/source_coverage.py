"""Offline coverage assessment of normalized, read-only source receipts.

Transport adapters own source decoding, market identity and snapshot assertions.
A complete result covers only the supplied query and asserted snapshot. It does
not establish source truth, publication time, new economic events or alpha.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .boundary import reject_forbidden_material

MAX_PAGES = 128
MAX_ROWS_PER_PAGE = 500
MAX_ROWS = 5000
PAGE_FIELDS = {
    "request_identity",
    "page_number",
    "source_status",
    "started_at",
    "observed_at",
    "rows",
    "total_count",
    "has_more",
    "snapshot_id",
    "snapshot_evidence_ref",
}
ROW_FIELDS = {"id", "market", "content_sha256", "publication_at"}


class CoverageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNSTABLE = "unstable"
    SOURCE_ERROR = "source_error"


def timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40 or "T" not in value:
        raise ValueError("coverage timestamps require ISO datetime with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "coverage timestamps require ISO datetime with timezone"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError("coverage timestamps require ISO datetime with timezone")
    return parsed.astimezone(UTC)


def _label(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise ValueError(
            f"{field} requires a nonempty string of at most 120 characters"
        )
    reject_forbidden_material(value, path=field)
    return value


def validate_coverage_requirement(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "request_identity",
        "collection_started_at",
    }:
        raise ValueError(
            "source_coverage requires request_identity and collection_started_at"
        )
    identity = value["request_identity"]
    if not isinstance(identity, Mapping) or set(identity) != {
        "market",
        "universe_id",
        "query_id",
    }:
        raise ValueError("coverage identity requires market, universe_id, query_id")
    return {
        "request_identity": {
            key: _label(identity[key], key) for key in sorted(identity)
        },
        "collection_started_at": timestamp(value["collection_started_at"]).isoformat(),
    }


def assess_pages(
    pages: object,
    *,
    request_identity: Mapping[str, Any],
    frozen_at: str,
    evaluated_at: str,
) -> dict[str, Any]:
    """Assess normalized pages while preserving observed IDs and versions.

    Each page has request_identity (excluding page number), page_number,
    source_status, started_at, observed_at, rows, total_count and has_more.
    Rows have id, market and content_sha256, with optional publication_at.
    Completeness additionally requires a common nonempty snapshot_id and
    snapshot_evidence_ref asserted by the adapter. No such evidence
    means partial even when counts match. Missing/error payloads are not empty
    successes. Caller contract violations raise ValueError.
    """
    requirement = validate_coverage_requirement(
        {
            "request_identity": request_identity,
            "collection_started_at": frozen_at,
        }
    )
    request_identity = requirement["request_identity"]
    if not isinstance(pages, list) or len(pages) > MAX_PAGES:
        raise ValueError(f"source_pages requires at most {MAX_PAGES} receipts")
    reject_forbidden_material(pages, path="source_pages")
    for page in pages:
        if not isinstance(page, dict) or set(page) - PAGE_FIELDS:
            raise ValueError("coverage pages accept only normalized receipt metadata")
        rows = page.get("rows")
        if isinstance(rows, list):
            if len(rows) > MAX_ROWS_PER_PAGE:
                raise ValueError("source_pages exceeds normalized row budget")
            for row in rows:
                if not isinstance(row, dict) or set(row) - ROW_FIELDS:
                    raise ValueError(
                        "coverage rows accept only identity and version metadata"
                    )
    if sum(len(p["rows"]) for p in pages if isinstance(p.get("rows"), list)) > MAX_ROWS:
        raise ValueError("source_pages exceeds normalized row budget")
    frozen, evaluated = timestamp(frozen_at), timestamp(evaluated_at)
    if frozen > evaluated:
        raise ValueError("invalid_evaluation_clock")
    errors, instability, gaps = set(), set(), set()
    observations, page_versions, page_ids = {}, {}, {}
    totals, terminals, snapshots, snapshot_refs = set(), set(), set(), set()
    raw_count = 0
    for page in pages:
        start, observed = (
            timestamp(page.get("started_at")),
            timestamp(page.get("observed_at")),
        )
        if not frozen <= start <= observed <= evaluated:
            raise ValueError("invalid_observation_clock")
        number = page.get("page_number")
        if type(number) is not int or number < 1:
            raise ValueError("positive_page_number_required")
        if page.get("request_identity") != request_identity:
            errors.add("request_identity_mismatch")
        if page.get("source_status") != "ok":
            errors.add("source_error_or_unknown")
            continue
        rows = page.get("rows")
        if not isinstance(rows, list):
            errors.add("missing_rows")
            continue
        total = page.get("total_count")
        if total is None:
            gaps.add("total_unknown")
        elif type(total) is not int or total < 0:
            errors.add("invalid_total")
        else:
            totals.add(total)
        more = page.get("has_more")
        if more is False:
            terminals.add(number)
        elif more is not True:
            gaps.add("terminal_unknown")
        snapshot, snapshot_ref = (
            page.get("snapshot_id"),
            page.get("snapshot_evidence_ref"),
        )
        if (
            snapshot is None
            or snapshot == ""
            or snapshot_ref is None
            or snapshot_ref == ""
        ):
            gaps.add("snapshot_unattested")
        else:
            snapshots.add(_label(snapshot, "snapshot_id"))
            snapshot_refs.add(_label(snapshot_ref, "snapshot_evidence_ref"))
        raw_count += len(rows)
        signature, ids = [], set()
        for row in rows:
            key, digest = row.get("id"), row.get("content_sha256")
            if (
                not isinstance(key, str)
                or not key.strip()
                or len(key) > 120
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                errors.add("row_identity_or_digest_missing")
                continue
            if row.get("market") != request_identity["market"]:
                errors.add("row_market_mismatch")
            pub = row.get("publication_at")
            if pub is not None:
                try:
                    if timestamp(pub) > observed:
                        errors.add("publication_after_observation")
                except (ValueError, AttributeError, TypeError):
                    errors.add("invalid_publication_time")
                    pub = None
            if key in ids:
                instability.add("duplicate_within_page")
            ids.add(key)
            signature.append((key, digest, pub))
            seen = observed.isoformat()
            item = observations.setdefault(
                key, {"id": key, "versions": {}, "first_observed_at": seen}
            )
            if observed < timestamp(item["first_observed_at"]):
                item["first_observed_at"] = seen
            version = item["versions"].setdefault(
                digest,
                {
                    "content_sha256": digest,
                    "first_observed_at": seen,
                    "publication_at_values": [],
                },
            )
            if observed < timestamp(version["first_observed_at"]):
                version["first_observed_at"] = seen
            if pub not in version["publication_at_values"]:
                version["publication_at_values"].append(pub)
                version["publication_at_values"].sort(
                    key=lambda p: (p is not None, p or "")
                )
            if len(item["versions"]) > 1 or len(version["publication_at_values"]) > 1:
                instability.add("record_version_conflict")
        encoded = json.dumps(
            {
                "rows": signature,
                "has_more": more,
                "total_count": total,
                "snapshot_id": snapshot,
                "snapshot_evidence_ref": snapshot_ref,
            },
            ensure_ascii=False,
        )
        if number in page_versions and encoded != page_versions[number]:
            instability.add("repeated_page_changed")
        page_versions.setdefault(number, encoded)
        page_ids.setdefault(number, set()).update(ids)
    seen_ids = set()
    for number in sorted(page_ids):
        if seen_ids & page_ids[number]:
            instability.add("cross_page_overlap")
        seen_ids.update(page_ids[number])
    if len(totals) > 1:
        instability.add("reported_total_changed")
    if len(snapshots) > 1 or len(snapshot_refs) > 1:
        instability.add("snapshot_changed")
    if len(terminals) > 1:
        instability.add("inconsistent_terminal")
    if len(terminals) != 1:
        gaps.add("terminal_not_established")
    elif next(iter(terminals)) != len(page_ids) or any(
        number != index for index, number in enumerate(sorted(page_ids), 1)
    ):
        gaps.add("noncontiguous_pages_or_pages_after_terminal")
    if len(totals) != 1 or len(observations) != next(iter(totals), None):
        gaps.add("reported_count_not_covered")
    if not pages:
        gaps.add("no_observations")
    state = (
        CoverageState.SOURCE_ERROR
        if errors
        else CoverageState.UNSTABLE
        if instability
        else CoverageState.PARTIAL
        if gaps
        else CoverageState.COMPLETE
    )
    return {
        "schema_version": "finance_source_coverage_v1",
        "state": state.value,
        "requirement": requirement,
        "evaluated_at": evaluated.isoformat(),
        "row_count_including_replays": raw_count,
        "receipt_count": len(pages),
        "unique_ids": len(observations),
        "reported_totals": sorted(totals),
        "observed_page_numbers": sorted(page_ids),
        "errors": sorted(errors),
        "instability": sorted(instability),
        "gaps": sorted(gaps),
        "records": [observations[k] for k in sorted(observations)],
        "snapshot_evidence_state": "adapter_asserted" if snapshots else "missing",
        "publication_time_verified": False,
        "event_novelty_verified": False,
        "limitation": "Conditional on adapter identities and snapshot assertions; query coverage does not prove source truth, historical availability, or an investment edge.",
    }


def coverage_observation(
    value: Mapping[str, Any],
    *,
    rule: Mapping[str, Any],
    evaluation_as_of: str,
) -> dict[str, Any]:
    if set(value) != {"gate_id", "source_pages"} or value["gate_id"] != rule["gate_id"]:
        raise ValueError(
            "a source-coverage observation requires only the bound gate_id and source_pages"
        )
    # Case dates mean midnight UTC. Datetimes in coverage-enabled cases must
    # carry an offset; do not infer the host timezone for receipt verification.
    if "T" not in evaluation_as_of:
        evaluation_as_of += "T00:00:00+00:00"
    requirement = rule["source_coverage"]
    report = assess_pages(
        value["source_pages"],
        request_identity=requirement["request_identity"],
        frozen_at=requirement["collection_started_at"],
        evaluated_at=evaluation_as_of,
    )
    complete = report["state"] == CoverageState.COMPLETE
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return {
        "gate_id": rule["gate_id"],
        "observation_state": "observed" if complete else "missing",
        "value": True if complete else None,
        "evidence_refs": [f"coverage:{digest}"],
        "reason": f"Source query coverage is {report['state']}; snapshot evidence remains adapter-asserted.",
        "source_coverage": report,
    }
