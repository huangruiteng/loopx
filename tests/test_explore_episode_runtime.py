from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from loopx.capabilities.explore.episode_runtime import (
    build_episode_execution_units,
    summarize_execution_records,
)
from loopx.capabilities.explore.harness_runtime import (
    ITEM_FAILURE_POLICY_FATAL,
    aggregate_arms,
    run_budget_arm,
    run_queue_epoch,
)


class SyntheticEpisodeError(RuntimeError):
    retryable_infra_error = True


class EpisodeAdapter:
    def __init__(
        self,
        seeds: list[dict[str, Any]],
        *,
        barrier: threading.Barrier | None = None,
        orphan_variants: bool = False,
        fail_item_id: str | None = None,
        fail_release: bool = False,
    ) -> None:
        self.seeds = seeds
        self.barrier = barrier
        self.orphan_variants = orphan_variants
        self.fail_item_id = fail_item_id
        self.fail_release = fail_release
        self.prepare_calls: list[str] = []
        self.execute_calls: list[str] = []
        self.release_calls = 0
        self.compile_calls = 0
        self.active_handles: set[object] = set()
        self._lock = threading.Lock()

    def list_seed_items(self) -> list[dict[str, Any]]:
        return [dict(seed) for seed in self.seeds]

    def compile_variant(
        self, spec: dict[str, Any], seed_item: dict[str, Any]
    ) -> dict[str, Any]:
        self.compile_calls += 1
        item = {
            "item_id": f"variant-{spec['spec_id']}",
            "family": seed_item["family"],
            "concurrency_key": seed_item.get("concurrency_key"),
        }
        if self.orphan_variants:
            item["seed_item_id"] = "missing-seed"
        return item

    def prepare_episode_group(
        self,
        seed_item: dict[str, Any],
        episode_items: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        del episode_items
        seed_id = str(seed_item["item_id"])
        handle = object()
        with self._lock:
            self.prepare_calls.append(seed_id)
            self.active_handles.add(handle)
        if self.barrier is not None:
            self.barrier.wait(timeout=3.0)
        return {
            "handle": handle,
            "checkpoint_ref": f"opaque:{seed_id}",
            "prefix_record": {
                "family": seed_item["family"],
                "observation_keys": [f"ready:{seed_id}"],
                "weighted_flags": {},
                "accepted": True,
                "duration_minutes": 0.4,
            },
        }

    def execute_episode(
        self, handle: object, item: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        with self._lock:
            assert handle in self.active_handles
            self.execute_calls.append(str(item["item_id"]))
        if item.get("item_id") == self.fail_item_id:
            raise SyntheticEpisodeError(str(item["item_id"]))
        return {
            "item_id": item["item_id"],
            "family": item["family"],
            "observation_keys": [f"suffix:{item['item_id']}"],
            "weighted_flags": {},
            "accepted": True,
            "duration_minutes": 0.2,
        }

    def release_episode_group(self, handle: object, **_: Any) -> None:
        with self._lock:
            assert handle in self.active_handles
            self.active_handles.remove(handle)
            self.release_calls += 1
        if self.fail_release:
            raise SyntheticEpisodeError("release failed")


def _seed(item_id: str, family: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "text": f"Probe {item_id}",
        "family": family,
        "concurrency_key": f"application:{family}",
    }


def _write_catalog(path: Path, spec_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_explore_variant_catalog_v0",
                "specs": [
                    {
                        "spec_id": spec_id,
                        "seed_family": "alpha",
                        "intent": "Probe a variant",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _records(arm: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record
        for epoch in arm["epochs"]
        for lane in epoch["lanes"]
        for record in lane["results"]
    ]


def test_fatal_structural_preflight_runs_before_episode_lifecycle_calls(
    tmp_path: Path,
) -> None:
    seeds = [_seed("duplicate", "alpha"), _seed("duplicate", "beta")]
    for use_router in (False, True):
        adapter = EpisodeAdapter(seeds)
        with pytest.raises(ValueError, match="duplicated"):
            run_budget_arm(
                adapter,
                arm_key=f"fatal-preflight-{use_router}",
                run_root=tmp_path / str(use_router),
                budget_minutes=1.0,
                worker_count=2,
                max_epochs=1,
                use_router=use_router,
                item_failure_policy=ITEM_FAILURE_POLICY_FATAL,
            )
        assert adapter.prepare_calls == []
        assert adapter.execute_calls == []
        assert adapter.release_calls == 0

    record_adapter = EpisodeAdapter(seeds)
    duplicate_catalog = tmp_path / "duplicate_catalog.json"
    _write_catalog(duplicate_catalog, "duplicate-seed-variant")
    record_arm = run_budget_arm(
        record_adapter,
        arm_key="record-preflight-router",
        run_root=tmp_path / "record",
        budget_minutes=1.0,
        worker_count=2,
        max_epochs=1,
        use_router=True,
        frontier_max_lanes=1,
        variant_catalog_path=duplicate_catalog,
    )
    validation_errors = [
        record
        for record in _records(record_arm)
        if record.get("episode_stage") == "group_validation"
    ]
    assert len(validation_errors) == 3
    assert record_adapter.prepare_calls == []


def test_record_orphan_variant_is_consumed_once_across_resume(tmp_path: Path) -> None:
    catalog = tmp_path / "variant_catalog.json"
    _write_catalog(catalog, "orphan")
    fatal_adapter = EpisodeAdapter(
        [_seed("seed-alpha", "alpha")], orphan_variants=True
    )
    with pytest.raises(ValueError, match="matching an epoch seed"):
        run_budget_arm(
            fatal_adapter,
            arm_key="orphan-fatal",
            run_root=tmp_path / "fatal-run",
            budget_minutes=5.0,
            worker_count=2,
            max_epochs=1,
            use_router=True,
            frontier_max_lanes=1,
            variant_catalog_path=catalog,
            duration_guard_factor=0.0,
            item_failure_policy=ITEM_FAILURE_POLICY_FATAL,
        )
    assert fatal_adapter.prepare_calls == []
    assert fatal_adapter.execute_calls == []
    assert fatal_adapter.release_calls == 0

    adapter = EpisodeAdapter([_seed("seed-alpha", "alpha")], orphan_variants=True)
    common = {
        "adapter": adapter,
        "arm_key": "orphan",
        "run_root": tmp_path / "run",
        "budget_minutes": 5.0,
        "worker_count": 2,
        "use_router": True,
        "frontier_max_lanes": 1,
        "variant_catalog_path": catalog,
        "duration_guard_factor": 0.0,
        "resumable": True,
    }

    first = run_budget_arm(max_epochs=1, **common)
    resumed = run_budget_arm(max_epochs=2, resume=True, **common)

    validation_errors = [
        record
        for record in _records(resumed)
        if record.get("episode_stage") == "group_validation"
    ]
    assert len(validation_errors) == 1
    assert adapter.compile_calls == 1
    assert first["epoch_count"] == 1
    assert resumed["epoch_count"] == 2
    consumption = json.loads(
        (tmp_path / "run" / "variant_consumption_orphan.json").read_text()
    )
    assert consumption == ["orphan"]


def test_episode_only_adapter_prepares_distinct_groups_concurrently(
    tmp_path: Path,
) -> None:
    adapter = EpisodeAdapter(
        [_seed("seed-alpha", "alpha"), _seed("seed-beta", "beta")],
        barrier=threading.Barrier(2),
    )

    arm = run_budget_arm(
        adapter,
        arm_key="concurrent-groups",
        run_root=tmp_path,
        budget_minutes=1.0,
        worker_count=2,
        max_epochs=1,
        duration_guard_factor=0.0,
        item_failure_policy=ITEM_FAILURE_POLICY_FATAL,
    )

    assert arm["epochs"][0]["execution_unit_count"] == 2
    assert sorted(adapter.prepare_calls) == ["seed-alpha", "seed-beta"]
    assert adapter.release_calls == 2
    assert adapter.active_handles == set()


def test_all_concurrency_keys_are_locked_and_disjoint_work_overlaps(
    tmp_path: Path,
) -> None:
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    active: set[str] = set()
    overlap_snapshots: list[set[str]] = []

    def execute(item: dict[str, Any], **_: Any) -> dict[str, Any]:
        item_id = str(item["item_id"])
        with lock:
            active.add(item_id)
            if item_id == "blocked-b":
                assert "first-a" not in active
        try:
            if item_id in {"first-a", "disjoint-c"}:
                barrier.wait(timeout=3.0)
                with lock:
                    overlap_snapshots.append(set(active))
                barrier.wait(timeout=3.0)
            return {
                "item_id": item_id,
                "family": item["family"],
                "observation_keys": [item_id],
                "weighted_flags": {},
                "accepted": True,
                "duration_minutes": 0.1,
            }
        finally:
            with lock:
                active.remove(item_id)

    run_queue_epoch(
        [
            {
                "item_id": "first-a",
                "family": "alpha",
                "concurrency_keys": ["a-only", "shared"],
            },
            {
                "item_id": "blocked-b",
                "family": "beta",
                "concurrency_keys": ["b-only", "other", "shared"],
            },
            {
                "item_id": "disjoint-c",
                "family": "gamma",
                "concurrency_keys": ["c-only"],
            },
        ],
        execute=execute,
        worker_count=2,
        run_root=tmp_path,
        arm="multi-key",
        epoch=1,
        item_failure_policy=ITEM_FAILURE_POLICY_FATAL,
    )

    assert len(overlap_snapshots) == 2
    assert all({"first-a", "disjoint-c"} <= snapshot for snapshot in overlap_snapshots)


def test_fatal_suffix_and_release_errors_are_chained(tmp_path: Path) -> None:
    adapter = EpisodeAdapter(
        [_seed("seed-alpha", "alpha")],
        fail_item_id="seed-alpha",
        fail_release=True,
    )

    with pytest.raises(SyntheticEpisodeError, match="seed-alpha") as raised:
        run_budget_arm(
            adapter,
            arm_key="double-fatal",
            run_root=tmp_path,
            budget_minutes=1.0,
            worker_count=1,
            max_epochs=1,
            item_failure_policy=ITEM_FAILURE_POLICY_FATAL,
        )

    assert isinstance(raised.value.__cause__, SyntheticEpisodeError)
    assert "release failed" in str(raised.value.__cause__)
    assert adapter.release_calls == 1


def test_record_cleanup_and_prepare_failures_never_fresh_fallback(
    tmp_path: Path,
) -> None:
    release_adapter = EpisodeAdapter(
        [_seed("seed-alpha", "alpha")], fail_release=True
    )
    release_arm = run_budget_arm(
        release_adapter,
        arm_key="release-record",
        run_root=tmp_path / "release",
        budget_minutes=1.0,
        worker_count=1,
        max_epochs=1,
    )
    prefix = next(
        record
        for record in _records(release_arm)
        if record.get("record_kind") == "shared_prefix"
    )
    assert prefix["accepted"] is True
    assert prefix["episode_stage"] == "release"
    assert prefix["episode_release_error"]["adapter_error"]["type"] == (
        "SyntheticEpisodeError"
    )

    class PrepareErrorAdapter(EpisodeAdapter):
        legacy_calls = 0

        def prepare_episode_group(self, *_: Any, **__: Any) -> dict[str, Any]:
            raise SyntheticEpisodeError("prepare failed")

        def execute(self, *_: Any, **__: Any) -> dict[str, Any]:
            self.legacy_calls += 1
            return {}

    prepare_adapter = PrepareErrorAdapter([_seed("seed-alpha", "alpha")])
    prepare_arm = run_budget_arm(
        prepare_adapter,
        arm_key="prepare-record",
        run_root=tmp_path / "prepare",
        budget_minutes=1.0,
        worker_count=1,
        max_epochs=1,
    )
    prepare_record = _records(prepare_arm)[0]
    assert prepare_record["episode_stage"] == "prepare"
    assert prepare_record["execution_status"] == "adapter_error"
    assert prepare_adapter.legacy_calls == 0


def test_partial_episode_protocol_fails_closed(tmp_path: Path) -> None:
    class PartialAdapter:
        def prepare_episode_group(self, *_: Any, **__: Any) -> None:
            return None

    with pytest.raises(ValueError, match="must implement all protocol methods"):
        run_budget_arm(
            PartialAdapter(),
            arm_key="partial",
            run_root=tmp_path,
            budget_minutes=1.0,
            worker_count=1,
            max_epochs=1,
        )


def test_duplicate_variant_ids_preflight_and_dual_reuse_metrics() -> None:
    items = [
        _seed("seed-alpha", "alpha"),
        {
            "item_id": "variant-dup",
            "family": "alpha",
            "is_variant": True,
            "seed_item_id": "seed-alpha",
        },
        {
            "item_id": "variant-dup",
            "family": "alpha",
            "is_variant": True,
            "seed_item_id": "seed-alpha",
        },
    ]
    with pytest.raises(ValueError, match="variant item_id is duplicated"):
        build_episode_execution_units(
            items,
            arm="duplicate-variant",
            epoch=1,
            fatal_preflight=True,
        )

    metrics = summarize_execution_records(
        [
            {
                "record_kind": "shared_prefix",
                "execution_group_id": "group-1",
                "duration_minutes": 0.4,
            },
            {
                "record_kind": "episode_suffix",
                "execution_group_id": "group-1",
                "duration_minutes": 0.2,
            },
            {
                "record_kind": "episode_suffix",
                "execution_group_id": "group-1",
                "duration_minutes": 0.05,
                "execution_status": "adapter_error",
            },
        ]
    )
    assert metrics["avoided_recompute_minutes"] == 0.4
    assert metrics["successful_avoided_recompute_minutes"] == 0.0
    assert metrics["episode_error_count"] == 1


def test_aggregate_arms_projects_execution_economics() -> None:
    execution_metrics = {
        "effective_compute_minutes": 2.0,
        "avoided_recompute_minutes": 1.5,
        "successful_avoided_recompute_minutes": 1.0,
        "episode_error_count": 1,
    }
    summary = aggregate_arms(
        {
            "episode": {
                "novel_value_total": 6.0,
                "execution_metrics": execution_metrics,
                "checkpoints": [],
            }
        },
        budget_minutes=5.0,
        worker_count=2,
    )

    projected = summary["arms"]["episode"]
    assert projected["execution_metrics"] == execution_metrics
    assert projected["novel_value_per_effective_compute_minute"] == 3.0
