from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from ...extensions.manifest import validate_extension_id
from ...extensions.runtime import (
    default_extension_state_file,
    execute_extension_runtime_binding,
    resolve_optional_capability_binding,
)
from ..context_providers.base import (
    ContextProviderItem,
    ContextProviderRetrieval,
    ContextProviderSync,
)


EXTENSION_CONTEXT_PROVIDER_ID = "extension"
DECISION_CONTEXT_CAPABILITY_ID = "decision-context"
DECISION_CONTEXT_ADVISORY_PROVIDER_PROTOCOL = (
    "decision_context_advisory_provider_v0"
)
DECISION_CONTEXT_ADVISORY_PERMISSION = "decision_context.read"
DECISION_CONTEXT_ADVISORY_REQUEST_SCHEMA = (
    "decision_context_advisory_retrieve_request_v0"
)
DECISION_CONTEXT_ADVISORY_RESPONSE_SCHEMA = (
    "decision_context_advisory_retrieve_response_v0"
)
MAX_EXTENSION_CONTEXT_ITEMS = 8
MAX_EXTENSION_CONTEXT_CONTENT_CHARS = 16_000
MAX_EXTENSION_CONTEXT_REF_CHARS = 512
MAX_EXTENSION_CONTEXT_TIMEOUT_SECONDS = 120.0
_RESPONSE_FIELDS = {
    "schema_version",
    "ok",
    "status",
    "reason_code",
    "items",
}
_ITEM_FIELDS = {"resource_ref", "summary", "content", "score"}


def _extension_id(config: Mapping[str, Any]) -> str | None:
    value = config.get("extension_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            "extension context provider extension_id must be a string"
        )
    return validate_extension_id(value)


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"extension context provider {field} is invalid")
    return value.strip()


def _public_safe_text(value: object, *, field: str, maximum: int) -> str:
    text = public_safe_compact_text(value, limit=maximum)
    if text is None:
        raise ValueError(
            f"extension context provider {field} is not public safe"
        )
    return text


def _reason_code(value: object) -> str | None:
    if value is None:
        return None
    reason = public_safe_compact_text(value, limit=120)
    if reason is None or any(character.isspace() for character in reason):
        raise ValueError(
            "extension context provider reason_code must be a public-safe token"
        )
    return reason


def _score(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("extension context provider score must be numeric")
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("extension context provider score must be finite")
    return score


def _positive_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            "extension context provider timeout_seconds must be numeric"
        )
    timeout = float(value)
    if not math.isfinite(timeout) or not 1 <= timeout <= MAX_EXTENSION_CONTEXT_TIMEOUT_SECONDS:
        raise ValueError(
            "extension context provider timeout_seconds must be between 1 and 120"
        )
    return timeout


def _validate_exact_fields(
    value: Mapping[str, Any],
    *,
    expected: set[str],
    subject: str,
) -> None:
    actual = set(value)
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    if not unexpected and not missing:
        return
    details = []
    if unexpected:
        details.append("unsupported: " + ", ".join(unexpected))
    if missing:
        details.append("missing: " + ", ".join(missing))
    raise ValueError(
        f"extension context provider {subject} fields are invalid: "
        + "; ".join(details)
    )


def _validated_response_envelope(
    response: Mapping[str, Any],
    *,
    requested_limit: int,
) -> list[object]:
    _validate_exact_fields(response, expected=_RESPONSE_FIELDS, subject="response")
    if (
        response.get("schema_version")
        != DECISION_CONTEXT_ADVISORY_RESPONSE_SCHEMA
        or response.get("ok") is not True
    ):
        raise ValueError(
            "extension context provider response has an invalid envelope"
        )
    status = str(response.get("status") or "")
    if status not in {"completed", "unavailable"}:
        raise ValueError("extension context provider status is invalid")
    raw_items = response.get("items")
    if (
        not isinstance(raw_items, list)
        or len(raw_items) > requested_limit
        or len(raw_items) > MAX_EXTENSION_CONTEXT_ITEMS
    ):
        raise ValueError(
            "extension context provider items must be a bounded list"
        )
    if status == "unavailable" and raw_items:
        raise ValueError(
            "an unavailable extension context provider cannot return items"
        )
    return raw_items


def _response_item(raw_item: object) -> ContextProviderItem:
    if not isinstance(raw_item, Mapping):
        raise ValueError("extension context provider items must be objects")
    _validate_exact_fields(raw_item, expected=_ITEM_FIELDS, subject="item")
    summary = public_safe_compact_text(raw_item.get("summary"), limit=220)
    if summary is None:
        raise ValueError(
            "extension context provider item summary is not public safe"
        )
    return ContextProviderItem(
        resource_ref=_bounded_text(
            raw_item.get("resource_ref"),
            field="resource_ref",
            maximum=MAX_EXTENSION_CONTEXT_REF_CHARS,
        ),
        summary=summary,
        content=_bounded_text(
            raw_item.get("content"),
            field="content",
            maximum=MAX_EXTENSION_CONTEXT_CONTENT_CHARS,
        ),
        score=_score(raw_item.get("score")),
    )


def _response_items(
    response: Mapping[str, Any],
    *,
    requested_limit: int,
) -> tuple[ContextProviderItem, ...]:
    raw_items = _validated_response_envelope(
        response,
        requested_limit=requested_limit,
    )
    return tuple(_response_item(raw_item) for raw_item in raw_items)


class DecisionContextExtensionProvider:
    """Adapt one lifecycle-gated extension to Decision Context recall.

    Lifecycle readiness and the executable binding are resolved together for
    each retrieval. The resulting snapshot never grants Goal or write authority.
    """

    def __init__(
        self,
        *,
        state_file: Path,
        extension_id: str | None,
    ) -> None:
        self.state_file = state_file
        self.extension_id = extension_id
        self.provider_id = extension_id or "context-provider"

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
    ) -> ContextProviderRetrieval:
        started = time.monotonic()
        namespace = _public_safe_text(namespace, field="namespace", maximum=120)
        scope_ref = _bounded_text(scope_ref, field="scope_ref", maximum=2_048)
        query = _bounded_text(query, field="query", maximum=1_000)
        query_summary = _public_safe_text(
            query_summary, field="query_summary", maximum=220
        )
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            raise ValueError(
                "extension context provider max_results must be an integer"
            )
        requested_limit = min(max(1, max_results), MAX_EXTENSION_CONTEXT_ITEMS)
        requested_timeout = _positive_timeout(timeout_seconds)

        resolution = resolve_optional_capability_binding(
            state_file=self.state_file,
            extension_id=self.extension_id,
            capability_id=DECISION_CONTEXT_CAPABILITY_ID,
            protocol=DECISION_CONTEXT_ADVISORY_PROVIDER_PROTOCOL,
            permission=DECISION_CONTEXT_ADVISORY_PERMISSION,
        )
        readiness = resolution.public_readiness()
        resolved_extension_id = resolution.extension_id
        provider_id = resolved_extension_id or self.provider_id
        if resolution.status != "ready":
            return ContextProviderRetrieval(
                provider=provider_id,
                namespace=namespace,
                status="unavailable",
                query_summary=query_summary,
                observed_at=observed_at,
                search_performed=False,
                read_performed=False,
                reason_code=resolution.status,
                requested_limit=requested_limit,
                provider_readiness=readiness,
            )

        binding = resolution.binding
        if not isinstance(binding, Mapping):
            raise ValueError("ready extension resolution requires a binding")
        effective_timeout = min(
            requested_timeout,
            _positive_timeout(binding.get("timeout_seconds")),
        )
        execution_binding = dict(binding)
        execution_binding["timeout_seconds"] = effective_timeout
        response = execute_extension_runtime_binding(
            execution_binding,
            request={
                "schema_version": DECISION_CONTEXT_ADVISORY_REQUEST_SCHEMA,
                "operation": "retrieve",
                "namespace": namespace,
                "scope_ref": scope_ref,
                "query": query,
                "query_summary": query_summary,
                "max_results": requested_limit,
                "timeout_seconds": effective_timeout,
                "observed_at": observed_at,
            },
        )
        items = _response_items(response, requested_limit=requested_limit)
        status = str(response["status"])
        reason_code = _reason_code(response.get("reason_code"))
        if status == "completed" and reason_code is not None:
            raise ValueError(
                "a completed extension context provider cannot return reason_code"
            )
        if status == "unavailable" and reason_code is None:
            raise ValueError(
                "an unavailable extension context provider requires reason_code"
            )
        return ContextProviderRetrieval(
            provider=provider_id,
            namespace=namespace,
            status=status,
            query_summary=query_summary,
            observed_at=observed_at,
            search_performed=True,
            read_performed=bool(items),
            items=items,
            reason_code=reason_code,
            provider_version=str(binding.get("provider_version") or "") or None,
            latency_ms=int((time.monotonic() - started) * 1_000),
            requested_limit=requested_limit,
            provider_readiness=readiness,
        )

    def sync(
        self,
        *,
        namespace: str,
        resources: Sequence[tuple[str, str]],
        timeout_seconds: float,
        observed_at: str,
        execute: bool,
    ) -> ContextProviderSync:
        del timeout_seconds, execute
        return ContextProviderSync(
            provider=self.provider_id,
            namespace=namespace,
            status="unavailable",
            observed_at=observed_at,
            requested_count=len(resources),
            completed_count=0,
            reason_code="read_only_provider",
        )


def build_extension_context_provider(
    config: Mapping[str, Any],
    *,
    runtime_root: str | Path | None = None,
) -> DecisionContextExtensionProvider:
    supported = {"provider", "extension_id"}
    unexpected = sorted(set(config) - supported)
    if unexpected:
        raise ValueError(
            "extension context provider config contains unsupported fields: "
            + ", ".join(unexpected)
        )
    return DecisionContextExtensionProvider(
        state_file=default_extension_state_file(runtime_root),
        extension_id=_extension_id(config),
    )
