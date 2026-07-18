from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .base import (
    ContextProviderItem,
    ContextProviderRetrieval,
    ContextProviderSync,
    canonical_context_lines,
    canonical_context_matches,
)


OPENVIKING_PROVIDER_ID = "openviking"
MAX_OPENVIKING_RESULTS = 6
MAX_OPENVIKING_SYNC_RESOURCES = 24
DEFAULT_MINIMUM_VERSION = "0.4.9"
ACTOR_PEER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _compact(value: Any, *, limit: int) -> str:
    return public_safe_compact_text(value, limit=limit)


def _extract_json(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise ValueError("provider returned empty output")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            value, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        return value
    raise ValueError("provider output did not contain JSON")


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("provider version is not semantic")
    return tuple(int(part) for part in match.groups())


def _mapping_candidates(value: Any) -> list[Mapping[str, Any]]:
    candidates: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        for key in ("resources", "memories", "skills", "results", "items"):
            rows = value.get(key)
            if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
                candidates.extend(row for row in rows if isinstance(row, Mapping))
        for key in ("result", "data"):
            nested = value.get(key)
            if nested is not value:
                candidates.extend(_mapping_candidates(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        candidates.extend(row for row in value if isinstance(row, Mapping))
    return candidates


def _resource_ref(row: Mapping[str, Any]) -> str:
    for key in ("uri", "resource_uri", "path", "url"):
        value = str(row.get(key) or "").strip()
        if value.startswith("viking://"):
            return value
    return ""


def _resource_summary(row: Mapping[str, Any]) -> str:
    for key in ("abstract", "summary", "overview", "description", "title"):
        value = _compact(row.get(key), limit=220)
        if value:
            return value
    return "Retrieved scoped public context from the configured provider."


def _resource_score(row: Mapping[str, Any]) -> float | None:
    for key in ("score", "similarity", "distance"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _read_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("content", "text"):
            content = value.get(key)
            if isinstance(content, str):
                return content
        for key in ("result", "data"):
            content = _read_content(value.get(key))
            if content:
                return content
    return ""


class OpenVikingContextProvider:
    """Bounded OpenViking CLI integration with compact, fail-open outputs."""

    provider_id = OPENVIKING_PROVIDER_ID

    def __init__(
        self,
        *,
        executable: str = "ov",
        minimum_version: str = DEFAULT_MINIMUM_VERSION,
        actor_peer_id: str | None = None,
        env: Mapping[str, str] | None = None,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        normalized_actor_peer_id = str(actor_peer_id or "").strip()
        if normalized_actor_peer_id and not ACTOR_PEER_ID_RE.fullmatch(
            normalized_actor_peer_id
        ):
            raise ValueError("actor_peer_id must be a compact public-safe token")
        self.executable = executable
        self.minimum_version = minimum_version
        self.actor_peer_id = normalized_actor_peer_id or None
        self.env = dict(env) if env is not None else dict(os.environ)
        self.runner = runner

    def _run(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        command = [self.executable]
        if self.actor_peer_id and args and args[0] not in {"--version", "status"}:
            command.extend(["--actor-peer-id", self.actor_peer_id])
        command.extend(args)
        return self.runner(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(1.0, timeout_seconds),
            env=self.env,
            check=False,
        )

    def _preflight(self, *, timeout_seconds: float) -> tuple[str | None, str | None]:
        try:
            version_result = self._run(["--version"], timeout_seconds=timeout_seconds)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None, "provider_cli_unavailable"
        if version_result.returncode != 0:
            return None, "provider_version_preflight_failed"
        version = _compact(version_result.stdout, limit=80)
        try:
            if _version_tuple(version) < _version_tuple(self.minimum_version):
                return version, "provider_version_incompatible"
        except ValueError:
            return version, "provider_version_unparseable"
        try:
            status_result = self._run(
                ["status", "-o", "json", "-c", "true"],
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return version, "provider_service_timeout"
        if status_result.returncode != 0:
            return version, "provider_service_unavailable"
        return version, None

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
        namespace = _compact(namespace, limit=120)
        query = _compact(query, limit=500)
        query_summary = _compact(query_summary, limit=220)
        requested_limit = min(max(1, int(max_results)), MAX_OPENVIKING_RESULTS)
        if not namespace or not query or not query_summary:
            raise ValueError("namespace, query, and query_summary are required")
        if not scope_ref.startswith("viking://"):
            raise ValueError("OpenViking scope_ref must use viking://")

        version, blocker = self._preflight(timeout_seconds=timeout_seconds)
        if blocker:
            return ContextProviderRetrieval(
                provider=self.provider_id,
                namespace=namespace,
                status="unavailable",
                query_summary=query_summary,
                observed_at=observed_at,
                search_performed=False,
                read_performed=False,
                reason_code=blocker,
                provider_version=version,
                latency_ms=int((time.monotonic() - started) * 1000),
                requested_limit=requested_limit,
            )

        try:
            search_result = self._run(
                [
                    "search",
                    query,
                    "-u",
                    scope_ref,
                    "-n",
                    str(requested_limit),
                    "-o",
                    "json",
                    "-c",
                    "true",
                ],
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            search_result = None
        if search_result is None or search_result.returncode != 0:
            return ContextProviderRetrieval(
                provider=self.provider_id,
                namespace=namespace,
                status="unavailable",
                query_summary=query_summary,
                observed_at=observed_at,
                search_performed=search_result is not None,
                read_performed=False,
                reason_code=(
                    "provider_search_timeout"
                    if search_result is None
                    else "provider_search_failed"
                ),
                provider_version=version,
                latency_ms=int((time.monotonic() - started) * 1000),
                requested_limit=requested_limit,
            )
        try:
            rows = _mapping_candidates(_extract_json(search_result.stdout))
        except ValueError:
            return ContextProviderRetrieval(
                provider=self.provider_id,
                namespace=namespace,
                status="unavailable",
                query_summary=query_summary,
                observed_at=observed_at,
                search_performed=True,
                read_performed=False,
                reason_code="provider_search_parse_failed",
                provider_version=version,
                latency_ms=int((time.monotonic() - started) * 1000),
                requested_limit=requested_limit,
            )

        items: list[ContextProviderItem] = []
        seen_refs: set[str] = set()
        read_attempted = False
        for row in rows:
            resource_ref = _resource_ref(row)
            if not resource_ref or not (
                resource_ref == scope_ref
                or resource_ref.startswith(scope_ref.rstrip("/") + "/")
            ):
                continue
            if resource_ref in seen_refs:
                continue
            seen_refs.add(resource_ref)
            read_attempted = True
            remaining = max(1.0, timeout_seconds - (time.monotonic() - started))
            try:
                read_result = self._run(
                    ["read", resource_ref, "-o", "json", "-c", "true"],
                    timeout_seconds=remaining,
                )
            except subprocess.TimeoutExpired:
                continue
            if read_result.returncode != 0:
                continue
            try:
                content = _read_content(_extract_json(read_result.stdout))
            except ValueError:
                continue
            if not content:
                continue
            items.append(
                ContextProviderItem(
                    resource_ref=resource_ref,
                    summary=_resource_summary(row),
                    content=content,
                    score=_resource_score(row),
                )
            )
            if len(items) >= requested_limit:
                break

        return ContextProviderRetrieval(
            provider=self.provider_id,
            namespace=namespace,
            status="completed",
            query_summary=query_summary,
            observed_at=observed_at,
            search_performed=True,
            read_performed=read_attempted,
            items=tuple(items),
            reason_code=(
                "provider_reads_unusable" if read_attempted and not items else None
            ),
            provider_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            requested_limit=requested_limit,
        )

    def _reconcile_uncertain_sync_write(
        self,
        *,
        target: str,
        source_content: str,
        timeout_seconds: float,
    ) -> str:
        """Classify an uncertain write without retrying it.

        ``add-resource --wait`` can lose its transport after the server has
        already materialized the target and queued semantic work.  Read back
        the immutable target before deciding whether another write is safe.
        """

        try:
            exact = self._run(
                ["read", target, "-o", "json", "-c", "true"],
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return "reconciliation_unavailable"
        if exact.returncode == 0:
            try:
                content = _read_content(_extract_json(exact.stdout))
            except ValueError:
                content = ""
            if content and canonical_context_matches(content, source_content):
                return "verified_success"
            return "committed_pending"

        try:
            tree = self._run(
                ["tree", target, "-L", "3", "-o", "json", "-c", "true"],
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return "reconciliation_unavailable"
        if tree.returncode == 0:
            try:
                refs = [
                    ref
                    for row in _mapping_candidates(_extract_json(tree.stdout))
                    if (ref := _resource_ref(row))
                ]
            except ValueError:
                refs = []
            if refs:
                contents: list[str] = []
                for ref in refs:
                    try:
                        read = self._run(
                            ["read", ref, "-o", "json", "-c", "true"],
                            timeout_seconds=timeout_seconds,
                        )
                    except subprocess.TimeoutExpired:
                        continue
                    if read.returncode != 0:
                        continue
                    try:
                        content = _read_content(_extract_json(read.stdout))
                    except ValueError:
                        continue
                    if content:
                        contents.append(content)
                source_lines = set(canonical_context_lines(source_content))
                matched_source_lines = {
                    line
                    for content in contents
                    for line in canonical_context_lines(content)
                    if line in source_lines
                }
                coverage = len(matched_source_lines) / max(1, len(source_lines))
                if (
                    contents
                    and all(
                        canonical_context_matches(content, source_content)
                        for content in contents
                    )
                    and coverage >= 0.8
                ):
                    return "verified_success"
                return "committed_pending"

        parent = target.rstrip("/").rsplit("/", 1)[0]
        try:
            listing = self._run(
                ["ls", parent, "-n", "100", "-o", "json", "-c", "true"],
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return "reconciliation_unavailable"
        if listing.returncode == 0:
            try:
                listed_refs = [
                    ref
                    for row in _mapping_candidates(_extract_json(listing.stdout))
                    if (ref := _resource_ref(row))
                ]
            except ValueError:
                return "reconciliation_unavailable"
            if any(
                ref == target or ref.startswith(target.rstrip("/") + "/")
                for ref in listed_refs
            ):
                return "committed_pending"
        return "absent_safe_to_retry"

    def sync(
        self,
        *,
        namespace: str,
        resources: Sequence[tuple[str, str]],
        timeout_seconds: float,
        observed_at: str,
        execute: bool,
    ) -> ContextProviderSync:
        started = time.monotonic()
        namespace = _compact(namespace, limit=120)
        if len(resources) > MAX_OPENVIKING_SYNC_RESOURCES:
            raise ValueError(
                f"OpenViking sync supports at most {MAX_OPENVIKING_SYNC_RESOURCES} resources"
            )
        bounded = list(resources[:MAX_OPENVIKING_SYNC_RESOURCES])
        if not namespace:
            raise ValueError("namespace is required")
        if not bounded:
            raise ValueError("at least one resource is required")
        for source, target in bounded:
            source_path = Path(source).expanduser()
            if not source_path.is_file():
                raise ValueError("every sync source must be an existing file")
            if not target.startswith("viking://resources/"):
                raise ValueError("sync targets must stay under viking://resources/")
            if source_path.name != target.rstrip("/").rsplit("/", 1)[-1]:
                raise ValueError("sync target basename must match source basename")
        if not execute:
            return ContextProviderSync(
                provider=self.provider_id,
                namespace=namespace,
                status="planned",
                observed_at=observed_at,
                requested_count=len(bounded),
                completed_count=0,
                write_count=0,
                reason_code="execute_required_for_resource_write",
                latency_ms=int((time.monotonic() - started) * 1000),
                retry_disposition="execute_required",
            )

        version, blocker = self._preflight(timeout_seconds=timeout_seconds)
        if blocker:
            return ContextProviderSync(
                provider=self.provider_id,
                namespace=namespace,
                status="unavailable",
                observed_at=observed_at,
                requested_count=len(bounded),
                completed_count=0,
                write_count=0,
                reason_code=blocker,
                provider_version=version,
                latency_ms=int((time.monotonic() - started) * 1000),
            )

        completed_refs: list[str] = []
        pending_refs: list[str] = []
        write_count = 0
        sync_reason: str | None = None
        reconciliation_performed = False
        retry_disposition = "no_retry"
        for source, target in bounded:
            parent = target.rstrip("/").rsplit("/", 1)[0]
            try:
                source_content = Path(source).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                sync_reason = "provider_sync_source_read_failed"
                break
            remaining = max(1.0, timeout_seconds - (time.monotonic() - started))
            try:
                existing = self._run(
                    ["read", target, "-o", "json", "-c", "true"],
                    timeout_seconds=remaining,
                )
            except subprocess.TimeoutExpired:
                sync_reason = "provider_sync_timeout"
                break
            if existing.returncode == 0:
                try:
                    existing_content = _read_content(_extract_json(existing.stdout))
                except (OSError, UnicodeDecodeError, ValueError):
                    sync_reason = "provider_sync_existing_read_failed"
                    break
                if not canonical_context_matches(existing_content, source_content):
                    sync_reason = "provider_sync_revision_conflict"
                    break
                completed_refs.append(target)
                continue
            try:
                tree_result = self._run(
                    ["tree", target, "-L", "3", "-o", "json", "-c", "true"],
                    timeout_seconds=remaining,
                )
            except subprocess.TimeoutExpired:
                sync_reason = "provider_sync_timeout"
                break
            tree_refs: list[str] = []
            if tree_result.returncode == 0:
                try:
                    tree_refs = [
                        ref
                        for row in _mapping_candidates(
                            _extract_json(tree_result.stdout)
                        )
                        if (ref := _resource_ref(row))
                    ]
                except ValueError:
                    sync_reason = "provider_sync_tree_parse_failed"
                    break
            tree_contents: list[str] = []
            for tree_ref in tree_refs:
                try:
                    tree_read = self._run(
                        ["read", tree_ref, "-o", "json", "-c", "true"],
                        timeout_seconds=remaining,
                    )
                except subprocess.TimeoutExpired:
                    sync_reason = "provider_sync_timeout"
                    break
                if tree_read.returncode != 0:
                    continue
                try:
                    tree_content = _read_content(_extract_json(tree_read.stdout))
                except ValueError:
                    continue
                tree_contents.append(tree_content)
            if sync_reason:
                break
            source_lines = set(canonical_context_lines(source_content))
            matched_source_lines = {
                line
                for content in tree_contents
                for line in canonical_context_lines(content)
                if line in source_lines
            }
            coverage = len(matched_source_lines) / max(1, len(source_lines))
            if (
                tree_contents
                and all(
                    canonical_context_matches(content, source_content)
                    for content in tree_contents
                )
                and coverage >= 0.8
            ):
                completed_refs.append(target)
                continue
            if tree_refs:
                sync_reason = "provider_sync_revision_conflict"
                break
            try:
                parent_probe = self._run(
                    ["ls", parent, "-n", "1", "-o", "json", "-c", "true"],
                    timeout_seconds=remaining,
                )
            except subprocess.TimeoutExpired:
                sync_reason = "provider_sync_timeout"
                break
            if parent_probe.returncode != 0:
                try:
                    mkdir_result = self._run(
                        ["mkdir", parent, "-o", "json", "-c", "true"],
                        timeout_seconds=remaining,
                    )
                except subprocess.TimeoutExpired:
                    sync_reason = "provider_sync_timeout"
                    break
                if mkdir_result.returncode != 0:
                    sync_reason = "provider_sync_parent_create_failed"
                    break
            reserve = min(15.0, max(1.0, remaining * 0.2))
            write_timeout = max(1.0, remaining - reserve)
            try:
                result = self._run(
                    [
                        "add-resource",
                        source,
                        "--to",
                        target,
                        "--wait",
                        "--timeout",
                        str(max(1, int(write_timeout))),
                        "-o",
                        "json",
                        "-c",
                        "true",
                    ],
                    timeout_seconds=write_timeout,
                )
            except subprocess.TimeoutExpired:
                result = None
            if result is None or result.returncode != 0:
                reconciliation_performed = True
                reconciliation = self._reconcile_uncertain_sync_write(
                    target=target,
                    source_content=source_content,
                    timeout_seconds=reserve,
                )
                if reconciliation == "verified_success":
                    completed_refs.append(target)
                    write_count += 1
                    continue
                if reconciliation == "committed_pending":
                    pending_refs.append(target)
                    write_count += 1
                    retry_disposition = "wait_and_reconcile"
                    continue
                if reconciliation == "absent_safe_to_retry":
                    sync_reason = (
                        "provider_sync_write_timeout_absent"
                        if result is None
                        else "provider_sync_write_failed_absent"
                    )
                    retry_disposition = "safe_to_retry"
                else:
                    sync_reason = "provider_sync_reconciliation_unavailable"
                    retry_disposition = "manual_reconcile"
                break
            completed_refs.append(target)
            write_count += 1

        accounted_count = len(completed_refs) + len(pending_refs)
        if len(completed_refs) == len(bounded):
            status = "completed"
        elif accounted_count == len(bounded) and pending_refs:
            status = "committed_pending"
            sync_reason = "provider_sync_committed_pending"
        else:
            status = "partial"
        return ContextProviderSync(
            provider=self.provider_id,
            namespace=namespace,
            status=status,
            observed_at=observed_at,
            requested_count=len(bounded),
            completed_count=len(completed_refs),
            write_count=write_count,
            reason_code=(
                None
                if status == "completed"
                else sync_reason or "provider_sync_incomplete"
            ),
            provider_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            result_refs=tuple([*completed_refs, *pending_refs]),
            pending_count=len(pending_refs),
            reconciliation_performed=reconciliation_performed,
            retry_disposition=retry_disposition,
        )


def build_openviking_context_provider(
    config: Mapping[str, Any],
) -> OpenVikingContextProvider:
    return OpenVikingContextProvider(
        executable=str(config.get("provider_binary") or "ov"),
        minimum_version=str(
            config.get("minimum_provider_version") or DEFAULT_MINIMUM_VERSION
        ),
        actor_peer_id=str(config.get("actor_peer_id") or "").strip() or None,
    )
