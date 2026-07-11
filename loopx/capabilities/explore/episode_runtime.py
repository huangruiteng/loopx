"""Generic shared-prefix execution for Explore Harness experiment adapters.

The runtime knows only seed lineage, opaque handles, and observation records.
Application restore, replay, isolation, and cleanup remain adapter-owned.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


RECOVERABLE_EPISODE_MODE = "recoverable-v0"

RECORD_KIND_SHARED_PREFIX = "shared_prefix"
RECORD_KIND_EPISODE_SUFFIX = "episode_suffix"
RECORD_KIND_STANDALONE = "standalone"

_PROTOCOL_METHODS = (
    "prepare_episode_group",
    "execute_episode",
    "release_episode_group",
)
_GROUP_SEED = "_loopx_episode_seed"
_GROUP_ITEMS = "_loopx_episode_items"
_GROUP_INVALID = "_loopx_episode_invalid"


def item_concurrency_keys(item: Mapping[str, Any]) -> tuple[str, ...]:
    """Normalize one or many generic exclusion keys for a queue item."""

    raw_keys = item.get("concurrency_keys")
    keys: list[str] = []
    if isinstance(raw_keys, Sequence) and not isinstance(raw_keys, (str, bytes)):
        for raw_key in raw_keys:
            if raw_key is None:
                continue
            key = str(raw_key).strip()
            if key:
                keys.append(key)
    if not keys:
        fallback = str(item.get("concurrency_key") or item.get("family") or "").strip()
        if fallback:
            keys.append(fallback)
    return tuple(dict.fromkeys(keys))


def recoverable_episode_mode(adapter: Any) -> str | None:
    """Return the optional episode protocol version, rejecting partial adapters."""

    declared = [hasattr(adapter, name) for name in _PROTOCOL_METHODS]
    implemented = [callable(getattr(adapter, name, None)) for name in _PROTOCOL_METHODS]
    if any(declared) and not all(implemented):
        missing = [
            name for name, available in zip(_PROTOCOL_METHODS, implemented) if not available
        ]
        raise ValueError(
            "recoverable episode adapters must implement all protocol methods; "
            f"missing callable(s): {', '.join(missing)}"
        )
    return RECOVERABLE_EPISODE_MODE if all(implemented) else None


def build_episode_execution_units(
    items: Sequence[Mapping[str, Any]],
    *,
    arm: str,
    epoch: int,
    fatal_preflight: bool = False,
) -> list[dict[str, Any]]:
    """Collapse each seed and its variants into one sequential execution unit.

    Malformed items (empty item_id, duplicate seed item_id, variants whose
    seed_item_id names no seed in this epoch) never crash grouping: they become
    invalid units that the execution layer resolves through the configured
    item failure policy — a structured error record under ``record``, a raised
    ``ValueError`` under ``fatal``. Passing ``fatal_preflight=True`` raises on
    the first known structural error before any execution unit is dispatched.
    Otherwise grouping stays total so one malformed agent- or adapter-authored
    item cannot take down the whole arm.
    """

    copied = [dict(item) for item in items]
    seeds: OrderedDict[str, dict[str, Any]] = OrderedDict()
    seed_indices: dict[str, int] = {}
    ambiguous_seed_ids: set[str] = set()
    invalid_reasons: dict[int, str] = {}
    for index, item in enumerate(copied):
        if item.get("is_variant"):
            continue
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            invalid_reasons[index] = (
                "recoverable episode seed items require a non-empty item_id"
            )
            continue
        if item_id in seeds:
            reason = f"recoverable episode seed item_id is duplicated: {item_id!r}"
            invalid_reasons.setdefault(seed_indices[item_id], reason)
            invalid_reasons[index] = reason
            ambiguous_seed_ids.add(item_id)
            continue
        seeds[item_id] = item
        seed_indices[item_id] = index

    variants: dict[str, list[dict[str, Any]]] = {}
    variant_item_ids: set[str] = set()
    for index, item in enumerate(copied):
        if not item.get("is_variant"):
            continue
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            invalid_reasons[index] = (
                "recoverable episode variant items require a non-empty item_id"
            )
            continue
        if item_id in seeds:
            invalid_reasons[index] = (
                "recoverable episode variant item_id collides with a seed item_id: "
                f"{item_id!r}"
            )
            variant_item_ids.add(item_id)
            continue
        if item_id in variant_item_ids:
            invalid_reasons[index] = (
                f"recoverable episode variant item_id is duplicated: {item_id!r}"
            )
            continue
        variant_item_ids.add(item_id)
        seed_item_id = str(item.get("seed_item_id") or "").strip()
        if seed_item_id in ambiguous_seed_ids:
            invalid_reasons[index] = (
                "recoverable episode variant seed_item_id is ambiguous because the "
                f"seed item_id is duplicated: {seed_item_id!r}"
            )
            continue
        if not seed_item_id or seed_item_id not in seeds:
            invalid_reasons[index] = (
                "recoverable episode variant requires seed_item_id matching an epoch seed: "
                f"{item.get('item_id')!r}"
            )
            continue
        variants.setdefault(seed_item_id, []).append(item)

    if fatal_preflight and invalid_reasons:
        first_invalid_index = min(invalid_reasons)
        raise ValueError(invalid_reasons[first_invalid_index])

    units: list[dict[str, Any]] = []
    group_index = 0
    for index, item in enumerate(copied):
        reason = invalid_reasons.get(index)
        if reason is not None:
            unit = dict(item)
            unit[_GROUP_INVALID] = reason
            units.append(unit)
            continue
        if item.get("is_variant"):
            continue  # scheduled inside its seed's group
        seed_item_id = str(item.get("item_id")).strip()
        group_index += 1
        group_id = f"{arm}:epoch-{int(epoch)}:group-{group_index:04d}"
        episode_items = [item, *variants.get(seed_item_id, [])]
        concurrency_keys: list[str] = []
        for episode_item in episode_items:
            for key in item_concurrency_keys(episode_item):
                if key not in concurrency_keys:
                    concurrency_keys.append(key)
        units.append(
            {
                "item_id": group_id,
                "family": item.get("family"),
                "concurrency_key": item.get("concurrency_key") or item.get("family"),
                "concurrency_keys": concurrency_keys,
                "execution_group_id": group_id,
                "seed_item_id": seed_item_id,
                _GROUP_SEED: item,
                _GROUP_ITEMS: episode_items,
            }
        )
    return units


def _elapsed_minutes(started_at: float) -> float:
    return (time.perf_counter() - started_at) / 60.0


def _normalize_item_record(
    record: Any,
    item: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("adapter execution must return a dict observation record")
    normalized = dict(record)
    normalized["item_id"] = item.get("item_id")
    normalized["family"] = item.get("family")
    normalized["is_variant"] = bool(item.get("is_variant"))
    if item.get("is_variant"):
        spec = item.get("variant_spec")
        if isinstance(spec, Mapping):
            normalized["variant_spec_id"] = spec.get("spec_id")
    else:
        normalized.pop("variant_spec_id", None)
    return normalized


def _annotate_group_record(
    record: Mapping[str, Any],
    *,
    group_id: str,
    seed_item_id: str,
    record_kind: str,
    prefix_reused: bool,
    checkpoint_ref: str | None,
) -> dict[str, Any]:
    annotated = dict(record)
    annotated["execution_group_id"] = group_id
    annotated["record_kind"] = record_kind
    annotated["seed_item_id"] = seed_item_id
    annotated["prefix_reused"] = bool(prefix_reused)
    if checkpoint_ref is not None:
        annotated["checkpoint_ref"] = checkpoint_ref
    else:
        annotated.pop("checkpoint_ref", None)
    return annotated


def _standalone_record(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized.pop("execution_group_id", None)
    normalized["record_kind"] = RECORD_KIND_STANDALONE
    normalized["prefix_reused"] = False
    return normalized


def _attach_release_error(
    record: dict[str, Any],
    release_error: Mapping[str, Any],
) -> None:
    record["episode_release_error"] = {
        "duration_minutes": release_error.get("duration_minutes"),
        "retryable_infra_error": bool(release_error.get("retryable_infra_error")),
        "adapter_error": release_error.get("adapter_error"),
    }
    record["retryable_infra_error"] = bool(
        record.get("retryable_infra_error")
        or release_error.get("retryable_infra_error")
    )


def execute_episode_group(
    group_item: Mapping[str, Any],
    *,
    adapter: Any,
    failure_policy: str,
    fatal_failure_policy: str,
    error_record_factory: Callable[..., dict[str, Any]],
    run_root: Path,
    arm: str,
    epoch: int,
    branch_id: str,
) -> list[dict[str, Any]]:
    """Prepare one prefix, execute sibling suffixes, and always release it.

    Returning ``None`` from ``prepare_episode_group`` is the adapter's explicit,
    side-effect-free opt-out for this group; child items then use the legacy
    ``execute`` method. Exceptions never trigger that fallback.
    """

    invalid_reason = group_item.get(_GROUP_INVALID)
    if invalid_reason is not None:
        error = ValueError(str(invalid_reason))
        if failure_policy == fatal_failure_policy:
            raise error
        record = error_record_factory(group_item, error, duration_minutes=0.0)
        record["episode_stage"] = "group_validation"
        return [_standalone_record(record)]

    seed = dict(group_item.get(_GROUP_SEED) or {})
    episode_items = [dict(item) for item in group_item.get(_GROUP_ITEMS) or []]
    group_id = str(group_item.get("execution_group_id") or group_item.get("item_id"))
    seed_item_id = str(group_item.get("seed_item_id") or seed.get("item_id") or "")
    context = {
        "run_root": Path(run_root),
        "arm": arm,
        "epoch": int(epoch),
        "branch_id": branch_id,
        "execution_group_id": group_id,
    }

    prepare_started = time.perf_counter()
    try:
        prepared = adapter.prepare_episode_group(
            dict(seed), [dict(item) for item in episode_items], **context
        )
    except Exception as error:
        if failure_policy == fatal_failure_policy:
            raise
        failed = error_record_factory(
            seed,
            error,
            duration_minutes=_elapsed_minutes(prepare_started),
        )
        failed["episode_stage"] = "prepare"
        return [
            _annotate_group_record(
                failed,
                group_id=group_id,
                seed_item_id=seed_item_id,
                record_kind=RECORD_KIND_SHARED_PREFIX,
                prefix_reused=False,
                checkpoint_ref=None,
            )
        ]

    if prepared is None:
        records: list[dict[str, Any]] = []
        legacy_context = {
            key: value for key, value in context.items() if key != "execution_group_id"
        }
        for item in episode_items:
            item_started = time.perf_counter()
            try:
                record = _normalize_item_record(
                    adapter.execute(item, **legacy_context), item
                )
            except Exception as error:
                if failure_policy == fatal_failure_policy:
                    raise
                record = error_record_factory(
                    item,
                    error,
                    duration_minutes=_elapsed_minutes(item_started),
                )
                record["episode_stage"] = "legacy_execute"
            record = _standalone_record(record)
            record["episode_fallback"] = "prepare_returned_none"
            records.append(record)
        return records

    handle_available = isinstance(prepared, Mapping) and "handle" in prepared
    handle = prepared.get("handle") if isinstance(prepared, Mapping) else None
    try:
        if not isinstance(prepared, Mapping):
            raise TypeError("prepare_episode_group must return a dict or None")
        if not handle_available:
            raise TypeError("prepare_episode_group result must contain handle")
        prefix_payload = prepared.get("prefix_record")
        if not isinstance(prefix_payload, Mapping):
            raise TypeError("prepare_episode_group result must contain prefix_record dict")
        checkpoint_value = prepared.get("checkpoint_ref")
        if checkpoint_value is not None and not isinstance(checkpoint_value, str):
            raise TypeError("checkpoint_ref must be a string or None")
        checkpoint_ref = checkpoint_value
        prefix = dict(prefix_payload)
        prefix.setdefault("item_id", f"{seed_item_id}:shared-prefix")
        prefix["family"] = seed.get("family")
        prefix["is_variant"] = False
        prefix.pop("variant_spec_id", None)
        prefix.setdefault("accepted", True)
        prefix = _annotate_group_record(
            prefix,
            group_id=group_id,
            seed_item_id=seed_item_id,
            record_kind=RECORD_KIND_SHARED_PREFIX,
            prefix_reused=len(episode_items) > 1,
            checkpoint_ref=checkpoint_ref,
        )
    except Exception as error:
        release_error: dict[str, Any] | None = None
        cleanup_exc: Exception | None = None
        if handle_available:
            release_started = time.perf_counter()
            try:
                adapter.release_episode_group(handle, **context)
            except Exception as cleanup_error:
                cleanup_exc = cleanup_error
                release_error = error_record_factory(
                    seed,
                    cleanup_error,
                    duration_minutes=_elapsed_minutes(release_started),
                )
        if failure_policy == fatal_failure_policy:
            if cleanup_exc is not None:
                # Keep the validation error primary; the failed cleanup rides
                # along as its cause instead of vanishing.
                raise error from cleanup_exc
            raise
        failed = error_record_factory(
            seed,
            error,
            duration_minutes=_elapsed_minutes(prepare_started),
        )
        failed["episode_stage"] = "prepare"
        if release_error is not None:
            _attach_release_error(failed, release_error)
        return [
            _annotate_group_record(
                failed,
                group_id=group_id,
                seed_item_id=seed_item_id,
                record_kind=RECORD_KIND_SHARED_PREFIX,
                prefix_reused=False,
                checkpoint_ref=None,
            )
        ]

    records = [prefix]
    fatal_error: Exception | None = None
    try:
        for item in episode_items:
            item_started = time.perf_counter()
            try:
                record = _normalize_item_record(
                    adapter.execute_episode(handle, item, **context), item
                )
            except Exception as error:
                if failure_policy == fatal_failure_policy:
                    fatal_error = error
                    break
                record = error_record_factory(
                    item,
                    error,
                    duration_minutes=_elapsed_minutes(item_started),
                )
                record["episode_stage"] = "execute"
            records.append(
                _annotate_group_record(
                    record,
                    group_id=group_id,
                    seed_item_id=seed_item_id,
                    record_kind=RECORD_KIND_EPISODE_SUFFIX,
                    prefix_reused=len(episode_items) > 1,
                    checkpoint_ref=checkpoint_ref,
                )
            )
    finally:
        release_started = time.perf_counter()
        try:
            adapter.release_episode_group(handle, **context)
        except Exception as error:
            if fatal_error is not None:
                # Both failed: the suffix error stays primary, the cleanup
                # failure is chained as its cause instead of vanishing.
                raise fatal_error from error
            if failure_policy == fatal_failure_policy:
                raise
            release_error = error_record_factory(
                seed,
                error,
                duration_minutes=_elapsed_minutes(release_started),
            )
            # The prepare itself succeeded and its observations are real, so
            # the prefix keeps its own execution_status and accepted flag; the
            # cleanup failure is carried in dedicated fields.
            _attach_release_error(prefix, release_error)
            prefix["episode_stage"] = "release"
    if fatal_error is not None:
        raise fatal_error
    return records


def _duration(record: Mapping[str, Any]) -> float:
    try:
        return max(0.0, float(record.get("duration_minutes") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def summarize_execution_records(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compute actual component cost and avoided prefix recomputation.

    ``avoided_recompute_minutes`` counts the structural prefix work avoided by
    every attempted suffix. ``successful_avoided_recompute_minutes`` is the
    conservative outcome-equivalent view and counts only suffixes that emitted
    a non-error observation. Failed suffixes remain visible separately as
    ``episode_error_count``.
    """

    shared_prefix_minutes = 0.0
    suffix_minutes = 0.0
    standalone_minutes = 0.0
    groups: dict[str, dict[str, float]] = {}
    episode_count = 0
    episode_error_count = 0
    for record in records:
        kind = str(record.get("record_kind") or RECORD_KIND_STANDALONE)
        duration = _duration(record)
        failed = str(record.get("execution_status") or "") == "adapter_error"
        if kind == RECORD_KIND_SHARED_PREFIX:
            shared_prefix_minutes += duration
        elif kind == RECORD_KIND_EPISODE_SUFFIX:
            suffix_minutes += duration
            episode_count += 1
            if failed:
                episode_error_count += 1
        else:
            standalone_minutes += duration
        group_id = str(record.get("execution_group_id") or "").strip()
        if group_id:
            group = groups.setdefault(
                group_id,
                {
                    "prefix": 0.0,
                    "attempted_episodes": 0.0,
                    "successful_episodes": 0.0,
                },
            )
            if kind == RECORD_KIND_SHARED_PREFIX:
                group["prefix"] += duration
            elif kind == RECORD_KIND_EPISODE_SUFFIX:
                group["attempted_episodes"] += 1.0
                if not failed:
                    group["successful_episodes"] += 1.0

    avoided = sum(
        group["prefix"] * max(0.0, group["attempted_episodes"] - 1.0)
        for group in groups.values()
    )
    successful_avoided = sum(
        group["prefix"] * max(0.0, group["successful_episodes"] - 1.0)
        for group in groups.values()
    )
    effective = shared_prefix_minutes + suffix_minutes + standalone_minutes
    return {
        "shared_prefix_compute_minutes": round(shared_prefix_minutes, 6),
        "episode_suffix_compute_minutes": round(suffix_minutes, 6),
        "standalone_compute_minutes": round(standalone_minutes, 6),
        "effective_compute_minutes": round(effective, 6),
        "avoided_recompute_minutes": round(avoided, 6),
        "successful_avoided_recompute_minutes": round(successful_avoided, 6),
        "episode_group_count": len(groups),
        "episode_count": episode_count,
        "episode_error_count": episode_error_count,
    }


def combine_execution_metrics(
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    minute_fields = (
        "shared_prefix_compute_minutes",
        "episode_suffix_compute_minutes",
        "standalone_compute_minutes",
        "effective_compute_minutes",
        "avoided_recompute_minutes",
        "successful_avoided_recompute_minutes",
    )
    count_fields = ("episode_group_count", "episode_count", "episode_error_count")
    combined: dict[str, Any] = {
        field: round(sum(float(part.get(field) or 0.0) for part in metrics), 6)
        for field in minute_fields
    }
    combined.update(
        {
            field: sum(int(part.get(field) or 0) for part in metrics)
            for field in count_fields
        }
    )
    return combined


def build_router_probes(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Fold sibling prefix/suffix records into one router observation."""

    ordered: list[tuple[str, Any]] = []
    grouped: OrderedDict[str, list[Mapping[str, Any]]] = OrderedDict()
    for index, record in enumerate(records):
        group_id = str(record.get("execution_group_id") or "").strip()
        if not group_id:
            ordered.append(("record", (index, record)))
            continue
        if group_id not in grouped:
            grouped[group_id] = []
            ordered.append(("group", group_id))
        grouped[group_id].append(record)

    probes: list[dict[str, Any]] = []
    for kind, value in ordered:
        if kind == "record":
            _, record = value
            probes.append(
                {
                    "family": str(record.get("family") or "general"),
                    "duration_minutes": record.get("duration_minutes"),
                    "observation_keys": record.get("observation_keys") or [],
                    "weighted_flags": record.get("weighted_flags") or {},
                    "accepted": bool(record.get("accepted")),
                    "retryable_infra_error": bool(
                        record.get("retryable_infra_error")
                    ),
                }
            )
            continue

        group_id = str(value)
        siblings = grouped[group_id]
        keys: list[str] = []
        seen_keys: set[str] = set()
        flags: dict[str, float] = {}
        for record in siblings:
            for key in record.get("observation_keys") or []:
                normalized = str(key)
                if normalized not in seen_keys:
                    seen_keys.add(normalized)
                    keys.append(normalized)
            weighted = record.get("weighted_flags")
            if isinstance(weighted, Mapping):
                for name, weight in weighted.items():
                    normalized_name = str(name)
                    flags[normalized_name] = max(
                        flags.get(normalized_name, float("-inf")), float(weight)
                    )
        suffixes = [
            record
            for record in siblings
            if record.get("record_kind") == RECORD_KIND_EPISODE_SUFFIX
        ]
        acceptance_records = suffixes or siblings
        accepted_count = sum(
            1 for record in acceptance_records if bool(record.get("accepted"))
        )
        attempt_count = len(acceptance_records)
        probes.append(
            {
                "execution_group_id": group_id,
                "family": str(siblings[0].get("family") or "general"),
                "duration_minutes": sum(_duration(record) for record in siblings),
                "observation_keys": keys,
                "weighted_flags": flags,
                "accepted": accepted_count > 0,
                # Runs remain grouped for routing, while these integer counts
                # preserve per-suffix acceptance weighting across group sizes.
                "accepted_count": accepted_count,
                "attempt_count": attempt_count,
                "retryable_infra_error": any(
                    bool(record.get("retryable_infra_error")) for record in siblings
                ),
            }
        )
    return probes
