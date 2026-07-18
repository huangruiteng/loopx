from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .core import _normalize_trigger_receipt, _reject_raw_keys


SOURCE_RESULT_SCHEMA = "periodic_report_source_result_v0"
SECTION_SCHEMA = "periodic_report_section_v0"
DOCUMENT_SCHEMA = "periodic_report_document_v0"
ARTIFACT_SCHEMA = "periodic_report_artifact_v0"
SINK_RESULT_SCHEMA = "periodic_report_sink_result_v0"

_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SOURCE_STATUSES = {"complete", "partial", "failed", "unknown"}
_SINK_STATUSES = {"pending", "sent", "failed", "skipped", "unknown"}
_SINK_ROLES = {"archive", "delivery"}
SourceCollector = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ArtifactRenderer = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ArtifactSink = Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _sequence(value: object, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be a list")
    return list(value)


def _text(value: object, label: str, *, maximum: int = 1000) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return text


def _optional_text(
    value: object,
    label: str,
    *,
    maximum: int = 1000,
) -> str | None:
    if value is None:
        return None
    return _text(value, label, maximum=maximum)


def _token(value: object, label: str) -> str:
    token = _text(value, label, maximum=128).lower()
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError(f"{label} must be a lower-snake-like public token")
    return token


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = 1000000,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{label} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _timestamp(value: object, label: str) -> str:
    raw = _text(value, label, maximum=80)
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _reject_private_fields(value: object, label: str) -> None:
    _reject_raw_keys(value, label)


def _digest(value: object, *, prefix: str) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _normalize_item(raw: object, *, label: str) -> dict[str, Any]:
    item = _mapping(raw, label)
    normalized: dict[str, Any] = {
        "item_id": _token(item.get("item_id"), f"{label}.item_id"),
        "title": _text(item.get("title"), f"{label}.title", maximum=240),
        "summary": _text(item.get("summary"), f"{label}.summary", maximum=1000),
        "value_rank": _integer(
            item.get("value_rank", 500),
            f"{label}.value_rank",
            maximum=10000,
        ),
    }
    for field, maximum in (
        ("status", 80),
        ("source_ref", 500),
        ("next_action", 500),
    ):
        value = _optional_text(item.get(field), f"{label}.{field}", maximum=maximum)
        if value:
            normalized[field] = value
    tags = sorted(
        {
            _token(value, f"{label}.tags[]")
            for value in _sequence(item.get("tags", []), f"{label}.tags")
        }
    )
    if tags:
        normalized["tags"] = tags
    return normalized


def _normalize_sections(raw: object, *, label: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    seen_sections: set[str] = set()
    for section_index, raw_section in enumerate(_sequence(raw, label)):
        section_label = f"{label}[{section_index}]"
        section = _mapping(raw_section, section_label)
        section_id = _token(section.get("section_id"), f"{section_label}.section_id")
        if section_id in seen_sections:
            raise ValueError(f"duplicate section_id {section_id!r}")
        seen_sections.add(section_id)
        items = [
            _normalize_item(value, label=f"{section_label}.items[{item_index}]")
            for item_index, value in enumerate(
                _sequence(section.get("items", []), f"{section_label}.items")
            )
        ]
        item_ids = [str(item["item_id"]) for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError(f"{section_label}.items contains duplicate item_id")
        sections.append(
            {
                "schema_version": SECTION_SCHEMA,
                "section_id": section_id,
                "title": _text(
                    section.get("title"), f"{section_label}.title", maximum=160
                ),
                "order": _integer(
                    section.get("order", section_index),
                    f"{section_label}.order",
                    maximum=10000,
                ),
                "items": sorted(
                    items,
                    key=lambda item: (int(item["value_rank"]), str(item["item_id"])),
                ),
            }
        )
    return sorted(sections, key=lambda item: (int(item["order"]), item["section_id"]))


def build_periodic_report_source_result(
    *,
    source_id: str,
    source_kind: str,
    status: str,
    observed_at: str,
    sections: Sequence[Mapping[str, Any]],
    snapshot_ref: str | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Build one public-safe source snapshot and its report sections."""

    normalized_status = _token(status, "status")
    if normalized_status not in _SOURCE_STATUSES:
        raise ValueError("status is invalid")
    raw_sections = list(sections)
    _reject_private_fields(raw_sections, "sections")
    normalized_sections = _normalize_sections(raw_sections, label="sections")
    result: dict[str, Any] = {
        "schema_version": SOURCE_RESULT_SCHEMA,
        "source_id": _token(source_id, "source_id"),
        "source_kind": _token(source_kind, "source_kind"),
        "status": normalized_status,
        "observed_at": _timestamp(observed_at, "observed_at"),
        "snapshot_digest": _digest(normalized_sections, prefix="snapshot"),
        "item_count": sum(len(section["items"]) for section in normalized_sections),
        "retryable": _boolean(retryable, "retryable"),
        "sections": normalized_sections,
        "boundary": {
            "business_semantics_owned_by_source": True,
            "schedule_policy_owned_by_source": False,
            "external_reads_performed": False,
            "external_writes_performed": False,
            "raw_content_persisted": False,
        },
    }
    if snapshot_ref:
        result["snapshot_ref"] = _text(snapshot_ref, "snapshot_ref", maximum=500)
    _reject_private_fields(result, "source_result")
    return result


def normalize_periodic_report_source_result(
    raw: Mapping[str, Any],
    *,
    expected_source_id: str | None = None,
    expected_source_kind: str | None = None,
) -> dict[str, Any]:
    payload = _mapping(raw, "source_result")
    _reject_private_fields(payload, "source_result")
    if payload.get("schema_version") != SOURCE_RESULT_SCHEMA:
        raise ValueError(f"source_result must use {SOURCE_RESULT_SCHEMA}")
    normalized = build_periodic_report_source_result(
        source_id=str(payload.get("source_id") or ""),
        source_kind=str(payload.get("source_kind") or ""),
        status=str(payload.get("status") or ""),
        observed_at=str(payload.get("observed_at") or ""),
        sections=_sequence(payload.get("sections", []), "source_result.sections"),
        snapshot_ref=_optional_text(
            payload.get("snapshot_ref"), "source_result.snapshot_ref", maximum=500
        ),
        retryable=_boolean(payload.get("retryable", False), "source_result.retryable"),
    )
    supplied_digest = _text(
        payload.get("snapshot_digest"),
        "source_result.snapshot_digest",
        maximum=128,
    )
    if supplied_digest != normalized["snapshot_digest"]:
        raise ValueError("source_result.snapshot_digest does not match sections")
    if expected_source_id and normalized["source_id"] != expected_source_id:
        raise ValueError("source adapter returned a different source_id")
    if expected_source_kind and normalized["source_kind"] != expected_source_kind:
        raise ValueError("source adapter returned a different source_kind")
    return normalized


def build_periodic_report_document(
    *,
    title: str,
    generated_at: str,
    period_window: Mapping[str, Any],
    profile: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    trigger_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge normalized source sections into one renderer-neutral document."""

    start_at = _timestamp(period_window.get("start_at"), "period_window.start_at")
    end_at = _timestamp(period_window.get("end_at"), "period_window.end_at")
    start_value = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    end_value = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    if start_value >= end_value:
        raise ValueError("period_window.start_at must be earlier than end_at")
    normalized_sources = [
        normalize_periodic_report_source_result(source) for source in sources
    ]
    source_ids = [str(source["source_id"]) for source in normalized_sources]
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ValueError("sources must contain unique source_id values")

    merged: dict[str, dict[str, Any]] = {}
    for source in normalized_sources:
        for section in source["sections"]:
            section_id = str(section["section_id"])
            target = merged.setdefault(
                section_id,
                {
                    "schema_version": SECTION_SCHEMA,
                    "section_id": section_id,
                    "title": section["title"],
                    "order": section["order"],
                    "items": [],
                },
            )
            if target["title"] != section["title"]:
                raise ValueError(
                    f"section {section_id!r} has conflicting titles across sources"
                )
            target["order"] = min(int(target["order"]), int(section["order"]))
            target["items"].extend(
                {**item, "source_id": source["source_id"]} for item in section["items"]
            )
    for section in merged.values():
        identities = [
            (str(item["source_id"]), str(item["item_id"])) for item in section["items"]
        ]
        if len(identities) != len(set(identities)):
            raise ValueError(
                f"section {section['section_id']!r} contains duplicate source items"
            )
        section["items"] = sorted(
            section["items"],
            key=lambda item: (
                int(item["value_rank"]),
                str(item["source_id"]),
                str(item["item_id"]),
            ),
        )

    normalized_trigger = _normalize_trigger_receipt(trigger_receipt)
    normalized_profile = {
        "profile_id": _token(profile.get("profile_id"), "profile.profile_id"),
        "profile_version": _token(
            profile.get("profile_version"), "profile.profile_version"
        ),
    }
    if normalized_trigger is not None and any(
        normalized_trigger["profile"].get(key) != value
        for key, value in normalized_profile.items()
    ):
        raise ValueError("trigger_receipt.profile must match the document profile")
    document = {
        "schema_version": DOCUMENT_SCHEMA,
        "title": _text(title, "title", maximum=200),
        "generated_at": _timestamp(generated_at, "generated_at"),
        "period_window": {"start_at": start_at, "end_at": end_at},
        "profile": normalized_profile,
        "source_snapshots": [
            {
                key: source[key]
                for key in (
                    "source_id",
                    "source_kind",
                    "status",
                    "observed_at",
                    "snapshot_digest",
                    "snapshot_ref",
                    "item_count",
                    "retryable",
                )
                if key in source
            }
            for source in sorted(
                normalized_sources, key=lambda item: str(item["source_id"])
            )
        ],
        "sections": sorted(
            merged.values(),
            key=lambda item: (int(item["order"]), str(item["section_id"])),
        ),
        "boundary": {
            "schedule_policy_owned_by_profile": True,
            "business_semantics_owned_by_sources": True,
            "renderer_owns_business_semantics": False,
            "sink_owns_business_semantics": False,
            "external_writes_performed": False,
        },
    }
    if normalized_trigger:
        document["trigger_receipt"] = normalized_trigger
    _reject_private_fields(document, "document")
    return document


def _normalize_artifact_result(
    raw: Mapping[str, Any],
    *,
    expected_renderer_id: str | None = None,
    expected_renderer_kind: str | None = None,
    expected_document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = _mapping(raw, "artifact")
    _reject_private_fields(artifact, "artifact")
    if artifact.get("schema_version") != ARTIFACT_SCHEMA:
        raise ValueError(f"artifact must use {ARTIFACT_SCHEMA}")
    renderer_id = _token(artifact.get("renderer_id"), "artifact.renderer_id")
    renderer_kind = _token(artifact.get("renderer_kind"), "artifact.renderer_kind")
    if expected_renderer_id and renderer_id != expected_renderer_id:
        raise ValueError("renderer returned a different renderer_id")
    if expected_renderer_kind and renderer_kind != expected_renderer_kind:
        raise ValueError("renderer returned a different renderer_kind")
    raw_content = artifact.get("content")
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise ValueError("artifact.content is required")
    if len(raw_content) > 1000000:
        raise ValueError("artifact.content exceeds 1000000 characters")
    content = raw_content
    expected_digest = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    if artifact.get("content_digest") != expected_digest:
        raise ValueError("artifact.content_digest does not match content")
    document_digest = _text(
        artifact.get("document_digest"), "artifact.document_digest", maximum=80
    )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", document_digest):
        raise ValueError("artifact.document_digest must use sha256")
    if expected_document is not None:
        expected_document_digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    expected_document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        )
        if document_digest != expected_document_digest:
            raise ValueError("artifact.document_digest does not match document")
    boundary = _mapping(artifact.get("boundary"), "artifact.boundary")
    for field in (
        "schedule_policy_applied",
        "business_evidence_judged",
        "external_writes_performed",
    ):
        if boundary.get(field) is not False:
            raise ValueError(f"artifact.boundary.{field} must be false")
    return {
        **artifact,
        "artifact_id": _token(artifact.get("artifact_id"), "artifact.artifact_id"),
        "renderer_id": renderer_id,
        "renderer_kind": renderer_kind,
        "artifact_ref": _text(
            artifact.get("artifact_ref"), "artifact.artifact_ref", maximum=500
        ),
        "content": content,
        "content_digest": expected_digest,
        "document_digest": document_digest,
        "boundary": boundary,
    }


@dataclass(frozen=True)
class PeriodicReportSourceAdapter:
    source_id: str
    source_kind: str
    collect: SourceCollector

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _token(self.source_id, "source_id"))
        object.__setattr__(self, "source_kind", _token(self.source_kind, "source_kind"))
        if not callable(self.collect):
            raise ValueError("source collect must be callable")


@dataclass(frozen=True)
class PeriodicReportRendererAdapter:
    renderer_id: str
    renderer_kind: str
    render: ArtifactRenderer

    def __post_init__(self) -> None:
        object.__setattr__(self, "renderer_id", _token(self.renderer_id, "renderer_id"))
        object.__setattr__(
            self, "renderer_kind", _token(self.renderer_kind, "renderer_kind")
        )
        if not callable(self.render):
            raise ValueError("renderer render must be callable")


@dataclass(frozen=True)
class PeriodicReportSinkAdapter:
    sink_id: str
    sink_kind: str
    sink_role: str
    deliver: ArtifactSink

    def __post_init__(self) -> None:
        object.__setattr__(self, "sink_id", _token(self.sink_id, "sink_id"))
        object.__setattr__(self, "sink_kind", _token(self.sink_kind, "sink_kind"))
        role = _token(self.sink_role, "sink_role")
        object.__setattr__(self, "sink_role", role)
        if role not in _SINK_ROLES:
            raise ValueError("sink_role must be archive or delivery")
        if not callable(self.deliver):
            raise ValueError("sink deliver must be callable")


class PeriodicReportAdapterRegistry:
    """Register typed adapters without granting them scheduling authority."""

    def __init__(self) -> None:
        self._sources: dict[str, PeriodicReportSourceAdapter] = {}
        self._renderers: dict[str, PeriodicReportRendererAdapter] = {}
        self._sinks: dict[str, PeriodicReportSinkAdapter] = {}

    @staticmethod
    def _register(target: dict[str, Any], identity: str, adapter: Any) -> None:
        if identity in target:
            raise ValueError(f"duplicate periodic report adapter {identity!r}")
        target[identity] = adapter

    def register_source(self, adapter: PeriodicReportSourceAdapter) -> None:
        self._register(self._sources, adapter.source_id, adapter)

    def register_renderer(self, adapter: PeriodicReportRendererAdapter) -> None:
        self._register(self._renderers, adapter.renderer_id, adapter)

    def register_sink(self, adapter: PeriodicReportSinkAdapter) -> None:
        self._register(self._sinks, adapter.sink_id, adapter)

    def collect(self, source_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        canonical_source_id = _token(source_id, "source_id")
        adapter = self._sources.get(canonical_source_id)
        if adapter is None:
            raise ValueError(f"unknown periodic report source {source_id!r}")
        return normalize_periodic_report_source_result(
            adapter.collect(request),
            expected_source_id=adapter.source_id,
            expected_source_kind=adapter.source_kind,
        )

    def render(self, renderer_id: str, document: Mapping[str, Any]) -> dict[str, Any]:
        canonical_renderer_id = _token(renderer_id, "renderer_id")
        adapter = self._renderers.get(canonical_renderer_id)
        if adapter is None:
            raise ValueError(f"unknown periodic report renderer {renderer_id!r}")
        canonical_document = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        expected_document = json.loads(canonical_document)
        renderer_document = json.loads(canonical_document)
        return _normalize_artifact_result(
            adapter.render(renderer_document),
            expected_renderer_id=adapter.renderer_id,
            expected_renderer_kind=adapter.renderer_kind,
            expected_document=expected_document,
        )

    def deliver(
        self,
        sink_id: str,
        artifact: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        canonical_sink_id = _token(sink_id, "sink_id")
        adapter = self._sinks.get(canonical_sink_id)
        if adapter is None:
            raise ValueError(f"unknown periodic report sink {sink_id!r}")
        normalized_artifact = _normalize_artifact_result(artifact)
        result = _mapping(adapter.deliver(normalized_artifact, context), "sink_result")
        if result.get("schema_version") != SINK_RESULT_SCHEMA:
            raise ValueError(f"sink_result must use {SINK_RESULT_SCHEMA}")
        expected = {
            "sink_id": adapter.sink_id,
            "sink_kind": adapter.sink_kind,
            "sink_role": adapter.sink_role,
        }
        if any(result.get(key) != value for key, value in expected.items()):
            raise ValueError("sink returned a different adapter identity")
        status = str(result.get("status") or "")
        if status not in _SINK_STATUSES:
            raise ValueError("sink_result.status is invalid")
        if result.get("schedule_policy_applied") is not False:
            raise ValueError("sink must not apply schedule policy")
        if result.get("business_evidence_judged") is not False:
            raise ValueError("sink must not judge business evidence")
        if status == "sent":
            expected_idempotency_key = _text(
                context.get("idempotency_key"),
                "context.idempotency_key",
                maximum=128,
            )
            if result.get("idempotency_key") != expected_idempotency_key:
                raise ValueError(
                    "sent sink result idempotency_key must match the delivery context"
                )
            if not (
                result.get("receipt_ref") and result.get("readback_verified") is True
            ):
                raise ValueError("sent sink result requires receipt_ref and readback")
        _reject_private_fields(result, "sink_result")
        return result

    def describe(self) -> dict[str, Any]:
        return {
            "schema_version": "periodic_report_adapter_registry_v0",
            "sources": sorted(self._sources),
            "renderers": sorted(self._renderers),
            "sinks": sorted(self._sinks),
            "schedule_policy_owned": False,
            "business_evidence_judged": False,
        }
