from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, Sequence


CONTEXT_PROVIDER_RETRIEVAL_SCHEMA_VERSION = "context_provider_retrieval_v0"
CONTEXT_PROVIDER_SYNC_SCHEMA_VERSION = "context_provider_sync_v0"


def opaque_provider_ref(*, provider: str, namespace: str, resource_ref: str) -> str:
    digest = hashlib.sha256(
        f"{provider}\n{namespace}\n{resource_ref}".encode("utf-8")
    ).hexdigest()[:20]
    return f"provider-{digest}"


def canonical_context_text(value: str) -> str:
    """Normalise transport-only line endings and one terminal newline."""

    return value.replace("\r\n", "\n").removesuffix("\n")


def canonical_context_lines(value: str) -> tuple[str, ...]:
    return tuple(
        line.rstrip()
        for line in canonical_context_text(value).splitlines()
        if line.strip()
    )


def canonical_context_matches(candidate: str, source: str) -> bool:
    """Verify exact text or a parser-split chunk against current source lines."""

    if canonical_context_text(candidate) == canonical_context_text(source):
        return True
    candidate_lines = canonical_context_lines(candidate)
    if len(candidate_lines) < 3 or len(candidate) < 80:
        return False
    source_lines = set(canonical_context_lines(source))
    matched = sum(line in source_lines for line in candidate_lines)
    return matched / len(candidate_lines) >= 0.98


@dataclass(frozen=True)
class ContextProviderItem:
    """One transient provider hit.

    ``content`` and ``resource_ref`` are intentionally available only to the
    in-process caller. Public packets retain an opaque reference and compact
    summary, never raw provider payloads or exact content.
    """

    resource_ref: str
    summary: str
    content: str
    score: float | None = None


@dataclass(frozen=True)
class ContextProviderRetrieval:
    provider: str
    namespace: str
    status: str
    query_summary: str
    observed_at: str
    search_performed: bool
    read_performed: bool
    items: tuple[ContextProviderItem, ...] = ()
    reason_code: str | None = None
    provider_version: str | None = None
    latency_ms: int = 0
    requested_limit: int = 0

    def public_packet(self) -> dict[str, object]:
        return {
            "schema_version": CONTEXT_PROVIDER_RETRIEVAL_SCHEMA_VERSION,
            "ok": self.status == "completed",
            "provider": self.provider,
            "namespace": self.namespace,
            "visibility": "public",
            "status": self.status,
            "reason_code": self.reason_code,
            "provider_version": self.provider_version,
            "query_summary": self.query_summary,
            "observed_at": self.observed_at,
            "search_performed": self.search_performed,
            "read_performed": self.read_performed,
            "requested_limit": self.requested_limit,
            "result_count": len(self.items),
            "results": [
                {
                    "provider_ref": opaque_provider_ref(
                        provider=self.provider,
                        namespace=self.namespace,
                        resource_ref=item.resource_ref,
                    ),
                    "summary": item.summary,
                    "score": item.score,
                }
                for item in self.items
            ],
            "telemetry": {
                "latency_ms": max(0, self.latency_ms),
                "result_cap_applied": len(self.items) >= self.requested_limit > 0,
            },
            "fail_open": True,
            "external_writes_performed": False,
            "raw_provider_payload_captured": False,
            "raw_content_captured": False,
            "credentials_captured": False,
        }


@dataclass(frozen=True)
class ContextProviderSync:
    provider: str
    namespace: str
    status: str
    observed_at: str
    requested_count: int
    completed_count: int
    write_count: int = 0
    reason_code: str | None = None
    provider_version: str | None = None
    latency_ms: int = 0
    result_refs: tuple[str, ...] = field(default_factory=tuple)

    def public_packet(self) -> dict[str, object]:
        return {
            "schema_version": CONTEXT_PROVIDER_SYNC_SCHEMA_VERSION,
            "ok": self.status in {"completed", "planned"},
            "provider": self.provider,
            "namespace": self.namespace,
            "visibility": "public",
            "status": self.status,
            "reason_code": self.reason_code,
            "provider_version": self.provider_version,
            "observed_at": self.observed_at,
            "requested_count": self.requested_count,
            "completed_count": self.completed_count,
            "write_count": self.write_count,
            "result_refs": [
                opaque_provider_ref(
                    provider=self.provider,
                    namespace=self.namespace,
                    resource_ref=ref,
                )
                for ref in self.result_refs
            ],
            "telemetry": {"latency_ms": max(0, self.latency_ms)},
            "external_writes_performed": self.write_count > 0,
            "raw_provider_payload_captured": False,
            "raw_content_captured": False,
            "credentials_captured": False,
        }


class ContextProvider(Protocol):
    provider_id: str

    def retrieve(
        self,
        *,
        namespace: str,
        scope_ref: str,
        query: str,
        query_summary: str,
        max_results: int,
        timeout_seconds: float,
        observed_at: str,
    ) -> ContextProviderRetrieval: ...

    def sync(
        self,
        *,
        namespace: str,
        resources: Sequence[tuple[str, str]],
        timeout_seconds: float,
        observed_at: str,
        execute: bool,
    ) -> ContextProviderSync: ...
