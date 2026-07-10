from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from ..context_providers import build_context_provider, canonical_context_matches
from ..context_providers.base import ContextProvider, opaque_provider_ref
from ...control_plane.runtime.public_safety import public_safe_compact_text
from .repository_memory import (
    ISSUE_FIX_REPOSITORY_MEMORY_READ_RESULT_SCHEMA_VERSION,
    MAX_MEMORY_RESULTS,
    SUPPORT_ASPECTS,
)


ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG_SCHEMA_VERSION = (
    "issue_fix_repository_memory_provider_config_v0"
)
PROVIDER_CONFIG_ENV = "LOOPX_ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG"
MAX_PROVIDER_TIMEOUT_SECONDS = 60.0
MAX_PROVIDER_SYNC_TIMEOUT_SECONDS = 600.0
MAX_PROVIDER_SYNC_REFERENCES = 24

_CONFIG_FIELDS = {
    "schema_version",
    "enabled",
    "provider",
    "provider_binary",
    "minimum_provider_version",
    "namespace",
    "visibility",
    "scope_ref",
    "repository_revision",
    "max_results",
    "timeout_seconds",
    "sync_timeout_seconds",
    "resource_references",
}
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


def default_repository_memory_provider_config_path() -> str | None:
    value = os.environ.get(PROVIDER_CONFIG_ENV, "").strip()
    return value or None


def _compact(value: Any, *, field: str, limit: int) -> str:
    text = public_safe_compact_text(value, limit=limit)
    if not text:
        raise ValueError(f"{field} must be compact and public-safe")
    return text


def _label(value: Any, *, field: str) -> str:
    value = _compact(value, field=field, limit=120)
    if not _LABEL.fullmatch(value):
        raise ValueError(f"{field} must be a compact public-safe label")
    return value


def _disabled_memory_input(
    *,
    provider: str,
    namespace: str,
    query_summary: str,
    observed_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": ISSUE_FIX_REPOSITORY_MEMORY_READ_RESULT_SCHEMA_VERSION,
        "provider": provider,
        "namespace": namespace,
        "visibility": "public",
        "status": "disabled",
        "query_summary": query_summary,
        "observed_at": observed_at,
        "search_performed": False,
        "read_performed": False,
        "reason_code": "provider_disabled",
        "writeback_performed": False,
        "automatic_capture_performed": False,
        "results": [],
    }


def _unavailable_memory_input(
    *,
    provider: str,
    namespace: str,
    query_summary: str,
    observed_at: str,
    search_performed: bool,
    read_performed: bool,
    reason_code: str,
) -> dict[str, Any]:
    return {
        "schema_version": ISSUE_FIX_REPOSITORY_MEMORY_READ_RESULT_SCHEMA_VERSION,
        "provider": provider,
        "namespace": namespace,
        "visibility": "public",
        "status": "unavailable",
        "query_summary": query_summary,
        "observed_at": observed_at,
        "search_performed": search_performed,
        "read_performed": read_performed,
        "reason_code": _label(reason_code, field="reason_code"),
        "writeback_performed": False,
        "automatic_capture_performed": False,
        "results": [],
    }


def _normalise_config(
    config: Mapping[str, Any],
    *,
    repository_revision: str,
) -> dict[str, Any]:
    if (
        config.get("schema_version")
        != ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG_SCHEMA_VERSION
    ):
        raise ValueError(
            "repository memory provider config schema_version must be "
            "issue_fix_repository_memory_provider_config_v0"
        )
    unknown = sorted(set(config) - _CONFIG_FIELDS)
    if unknown:
        raise ValueError(
            f"repository memory provider config has unsupported fields: {unknown}"
        )
    provider = _label(config.get("provider"), field="provider")
    namespace = _label(config.get("namespace"), field="namespace")
    if config.get("visibility") != "public":
        raise ValueError("repository memory provider visibility must be public")
    configured_revision = _compact(
        config.get("repository_revision"),
        field="repository_revision",
        limit=120,
    )
    if not re.fullmatch(r"[0-9a-fA-F]{12,64}", configured_revision):
        raise ValueError("repository memory provider revision must be a git object id")
    if configured_revision != repository_revision:
        raise ValueError(
            "repository memory provider revision must match current checkout"
        )
    scope_ref = _compact(config.get("scope_ref"), field="scope_ref", limit=500)
    if not scope_ref.startswith("viking://"):
        raise ValueError("repository memory provider scope_ref must use viking://")
    if repository_revision[:12] not in scope_ref:
        raise ValueError("repository memory provider scope_ref must be revision-scoped")
    max_results = min(
        max(1, int(config.get("max_results") or 3)),
        MAX_MEMORY_RESULTS,
    )
    timeout_seconds = min(
        max(1.0, float(config.get("timeout_seconds") or 15.0)),
        MAX_PROVIDER_TIMEOUT_SECONDS,
    )
    sync_timeout_seconds = min(
        max(1.0, float(config.get("sync_timeout_seconds") or 180.0)),
        MAX_PROVIDER_SYNC_TIMEOUT_SECONDS,
    )
    raw_resource_references = config.get("resource_references") or []
    if not isinstance(raw_resource_references, Sequence) or isinstance(
        raw_resource_references, (str, bytes)
    ):
        raise ValueError("resource_references must be a list")
    if len(raw_resource_references) > MAX_PROVIDER_SYNC_REFERENCES:
        raise ValueError(
            f"resource_references supports at most {MAX_PROVIDER_SYNC_REFERENCES} files"
        )
    resource_references: list[str] = []
    for index, raw_reference in enumerate(raw_resource_references):
        reference = PurePosixPath(
            _compact(raw_reference, field=f"resource_references[{index}]", limit=260)
        )
        if reference.is_absolute() or ".." in reference.parts:
            raise ValueError("resource_references must be repository-relative")
        normalised_reference = reference.as_posix()
        if normalised_reference not in resource_references:
            resource_references.append(normalised_reference)
    return {
        **dict(config),
        "provider": provider,
        "namespace": namespace,
        "scope_ref": scope_ref.rstrip("/"),
        "repository_revision": configured_revision,
        "max_results": max_results,
        "timeout_seconds": timeout_seconds,
        "sync_timeout_seconds": sync_timeout_seconds,
        "resource_references": resource_references,
        "enabled": config.get("enabled") is not False,
    }


def _repo_relative_ref(
    *,
    scope_ref: str,
    resource_ref: str,
    configured_references: Sequence[str],
) -> str | None:
    prefix = scope_ref.rstrip("/") + "/"
    if not resource_ref.startswith(prefix):
        return None
    relative = unquote(resource_ref.removeprefix(prefix)).strip("/")
    if not relative:
        return None
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    normalised = path.as_posix()
    for reference in sorted(configured_references, key=len, reverse=True):
        if normalised == reference or normalised.startswith(
            reference.rstrip("/") + "/"
        ):
            return reference
    return normalised if not configured_references else None


def _checkout_content(repo_path: Path, reference: str) -> str | None:
    root = repo_path.expanduser().resolve()
    candidate = (root / reference).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def retrieve_issue_fix_repository_memory(
    *,
    config: Mapping[str, Any],
    repo_path: str | Path,
    repository_revision: str,
    query: str,
    query_summary: str,
    supports: Sequence[str],
    observed_at: str,
    provider: ContextProvider | None = None,
) -> dict[str, Any]:
    """Run a configured provider and convert it into issue-fix advisory evidence."""

    normalised = _normalise_config(config, repository_revision=repository_revision)
    query = _compact(query, field="query", limit=500)
    query_summary = _compact(query_summary, field="query_summary", limit=220)
    support_values = sorted(
        {str(value).strip() for value in supports if str(value).strip()}
    )
    if not support_values or any(
        value not in SUPPORT_ASPECTS for value in support_values
    ):
        raise ValueError(f"supports must use {sorted(SUPPORT_ASPECTS)}")
    provider_id = str(normalised["provider"])
    namespace = str(normalised["namespace"])
    if not normalised["enabled"]:
        memory_input = _disabled_memory_input(
            provider=provider_id,
            namespace=namespace,
            query_summary=query_summary,
            observed_at=observed_at,
        )
        return {
            "memory_input": memory_input,
            "provider_projection": {
                "status": "disabled",
                "fail_open": True,
                "result_count": 0,
            },
        }

    provider = provider or build_context_provider(normalised)
    retrieval = provider.retrieve(
        namespace=namespace,
        scope_ref=str(normalised["scope_ref"]),
        query=query,
        query_summary=query_summary,
        max_results=int(normalised["max_results"]),
        timeout_seconds=float(normalised["timeout_seconds"]),
        observed_at=observed_at,
    )
    provider_projection = retrieval.public_packet()
    if retrieval.status != "completed":
        memory_input = _unavailable_memory_input(
            provider=provider_id,
            namespace=namespace,
            query_summary=query_summary,
            observed_at=observed_at,
            search_performed=retrieval.search_performed,
            read_performed=retrieval.read_performed,
            reason_code=retrieval.reason_code or "provider_unavailable",
        )
        memory_input.update(
            {
                key: value
                for key, value in {
                    "provider_version": retrieval.provider_version,
                    "latency_ms": retrieval.latency_ms,
                    "requested_limit": retrieval.requested_limit,
                    "configured_resource_count": len(normalised["resource_references"]),
                    "stale_or_unmapped_count": 0,
                    "verification_mode": "canonical_text_or_parser_chunk",
                }.items()
                if value is not None
            }
        )
        return {
            "memory_input": memory_input,
            "provider_projection": provider_projection,
        }

    root = Path(repo_path)
    results: list[dict[str, Any]] = []
    confirmed_count = 0
    stale_or_unmapped_count = 0
    for item in retrieval.items:
        reference = _repo_relative_ref(
            scope_ref=str(normalised["scope_ref"]),
            resource_ref=item.resource_ref,
            configured_references=normalised["resource_references"],
        )
        checkout_content = _checkout_content(root, reference) if reference else None
        confirmed = checkout_content is not None and canonical_context_matches(
            item.content, checkout_content
        )
        row: dict[str, Any] = {
            "memory_ref": opaque_provider_ref(
                provider=provider_id,
                namespace=namespace,
                resource_ref=item.resource_ref,
            ),
            "summary": _compact(item.summary, field="result.summary", limit=220),
            "supports": support_values,
            "verification_status": "confirmed" if confirmed else "unverified",
        }
        if confirmed and reference:
            row["verification_reference"] = reference
            row["verification_revision"] = repository_revision
            confirmed_count += 1
        else:
            stale_or_unmapped_count += 1
        results.append(row)

    memory_input = {
        "schema_version": ISSUE_FIX_REPOSITORY_MEMORY_READ_RESULT_SCHEMA_VERSION,
        "provider": provider_id,
        "namespace": namespace,
        "visibility": "public",
        "status": "completed",
        "query_summary": query_summary,
        "observed_at": observed_at,
        "search_performed": retrieval.search_performed,
        "read_performed": retrieval.read_performed,
        "writeback_performed": False,
        "automatic_capture_performed": False,
        "provider_version": retrieval.provider_version,
        "latency_ms": retrieval.latency_ms,
        "requested_limit": retrieval.requested_limit,
        "configured_resource_count": len(normalised["resource_references"]),
        "stale_or_unmapped_count": stale_or_unmapped_count,
        "verification_mode": "canonical_text_or_parser_chunk",
        "results": results,
    }
    if memory_input["provider_version"] is None:
        del memory_input["provider_version"]
    provider_projection["checkout_verification"] = {
        "revision": repository_revision,
        "confirmed_count": confirmed_count,
        "stale_or_unmapped_count": stale_or_unmapped_count,
        "patch_influence_allowed_count": confirmed_count,
        "configured_resource_count": len(normalised["resource_references"]),
        "verification_mode": "canonical_text_or_parser_chunk",
    }
    return {
        "memory_input": memory_input,
        "provider_projection": provider_projection,
    }


def sync_issue_fix_repository_memory(
    *,
    config: Mapping[str, Any],
    repo_path: str | Path,
    repository_revision: str,
    references: Sequence[str],
    observed_at: str,
    execute: bool,
    provider: ContextProvider | None = None,
) -> dict[str, Any]:
    """Bound an explicit provider resource refresh to one revision checkout."""

    normalised = _normalise_config(config, repository_revision=repository_revision)
    if not normalised["enabled"]:
        return {
            "schema_version": "issue_fix_repository_memory_sync_v0",
            "ok": False,
            "status": "disabled",
            "provider": normalised["provider"],
            "namespace": normalised["namespace"],
            "repository_revision": repository_revision,
            "requested_reference_count": 0,
            "external_writes_performed": False,
            "fail_open": True,
        }
    scope_ref = str(normalised["scope_ref"])
    if not scope_ref.startswith("viking://resources/"):
        raise ValueError("issue-fix repository sync requires a resources scope")
    if len(references) > MAX_PROVIDER_SYNC_REFERENCES:
        raise ValueError(
            f"sync supports at most {MAX_PROVIDER_SYNC_REFERENCES} references"
        )
    bounded = list(dict.fromkeys(str(reference) for reference in references))
    if not bounded:
        raise ValueError("at least one repository reference is required")
    root = Path(repo_path).expanduser().resolve()
    configured_references = set(normalised["resource_references"])
    if configured_references and any(
        str(PurePosixPath(reference)) not in configured_references
        for reference in bounded
    ):
        raise ValueError("sync references must be declared in resource_references")
    resources: list[tuple[str, str]] = []
    for index, raw_reference in enumerate(bounded):
        reference = PurePosixPath(
            _compact(raw_reference, field=f"references[{index}]", limit=260)
        )
        if reference.is_absolute() or ".." in reference.parts:
            raise ValueError("sync references must be repository-relative")
        source = (root / reference.as_posix()).resolve()
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise ValueError("sync reference escapes the repository") from exc
        if not source.is_file():
            raise ValueError(f"sync reference is not a file: {reference.as_posix()}")
        resources.append((str(source), f"{scope_ref}/{reference.as_posix()}"))

    provider = provider or build_context_provider(normalised)
    sync = provider.sync(
        namespace=str(normalised["namespace"]),
        resources=resources,
        timeout_seconds=float(normalised["sync_timeout_seconds"]),
        observed_at=observed_at,
        execute=execute,
    )
    packet = sync.public_packet()
    packet.update(
        {
            "schema_version": "issue_fix_repository_memory_sync_v0",
            "repository_revision": repository_revision,
            "requested_reference_count": len(resources),
            "revision_scoped": True,
            "automatic_capture_performed": False,
            "memory_writeback_performed": False,
        }
    )
    return packet


def render_issue_fix_repository_memory_sync_markdown(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "# Issue Fix Repository Memory Sync",
            "",
            f"- ok: `{bool(payload.get('ok'))}`",
            f"- status: `{payload.get('status')}`",
            f"- provider: `{payload.get('provider')}`",
            f"- namespace: `{payload.get('namespace')}`",
            f"- repository revision: `{payload.get('repository_revision')}`",
            f"- requested references: `{payload.get('requested_reference_count', 0)}`",
            f"- completed resources: `{payload.get('completed_count', 0)}`",
            f"- provider writes: `{payload.get('write_count', 0)}`",
            f"- external writes performed: `{bool(payload.get('external_writes_performed'))}`",
        ]
    )
