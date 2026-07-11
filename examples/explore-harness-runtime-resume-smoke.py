#!/usr/bin/env python3
"""Smoke the Explore Harness restart and per-item failure contracts."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_text = str(REPO_ROOT)
if repo_root_text in sys.path:
    sys.path.remove(repo_root_text)
sys.path.insert(0, repo_root_text)

from loopx.capabilities.explore.harness_checkpoint import (  # noqa: E402
    HARNESS_CHECKPOINT_SCHEMA_VERSION,
    load_arm_checkpoint,
)
from loopx.capabilities.explore.harness_runtime import (  # noqa: E402
    ITEM_FAILURE_POLICY_FATAL,
    run_budget_arm,
    run_queue_epoch,
)


class SyntheticRetryableError(RuntimeError):
    retryable_infra_error = True


class ResumeAdapter:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def list_seed_items(self) -> list[dict]:
        return [
            {
                "item_id": "seed-alpha",
                "text": "Probe alpha",
                "family": "alpha",
                "concurrency_key": "alpha",
            }
        ]

    def compile_variant(self, spec: dict, seed_item: dict) -> dict:
        spec_id = str(spec["spec_id"])
        return {
            "item_id": f"variant-{spec_id}",
            "text": spec.get("intent"),
            "family": seed_item["family"],
            "concurrency_key": f"alpha:{spec_id}",
        }

    def execute(self, item: dict, **_: object) -> dict:
        item_id = str(item["item_id"])
        self.executed.append(item_id)
        return {
            "item_id": item_id,
            "family": item["family"],
            "observation_keys": ["shared-observation"],
            "weighted_flags": {},
            "accepted": True,
            "duration_minutes": 0.1,
            "retryable_infra_error": False,
        }


class RecoverableBlackBoxAdapter:
    """Synthetic adapter shaped like a checkpointable external application."""

    def __init__(
        self,
        *,
        prepare_behavior: str = "ready",
        fail_episode: str | None = None,
    ) -> None:
        self.prepare_behavior = prepare_behavior
        self.fail_episode = fail_episode
        self.handle = object()
        self.prepare_calls: list[list[str]] = []
        self.episode_calls: list[str] = []
        self.release_calls = 0
        self.legacy_calls: list[str] = []

    def list_seed_items(self) -> list[dict]:
        return [
            {
                "item_id": "seed-alpha",
                "text": "Open a base state and probe a black-box application",
                "family": "alpha",
                "concurrency_key": "application-alpha",
            }
        ]

    def compile_variant(self, spec: dict, seed_item: dict) -> dict:
        return {
            "item_id": f"variant-{spec['spec_id']}",
            "text": spec.get("intent"),
            "family": seed_item["family"],
            "concurrency_key": "application-alpha",
        }

    def prepare_episode_group(
        self, seed_item: dict, episode_items: list[dict], **_: object
    ) -> dict | None:
        self.prepare_calls.append([str(item["item_id"]) for item in episode_items])
        if self.prepare_behavior == "none":
            return None
        return {
            "handle": self.handle,
            "checkpoint_ref": "opaque:black-box-state-1",
            "prefix_record": {
                "family": seed_item["family"],
                "observation_keys": ["application-ready"],
                "weighted_flags": {"shared-state": 2.0},
                "accepted": True,
                "duration_minutes": 0.4,
                "retryable_infra_error": False,
            },
        }

    def execute_episode(self, handle: object, item: dict, **_: object) -> dict:
        assert handle is self.handle
        item_id = str(item["item_id"])
        self.episode_calls.append(item_id)
        if item_id == self.fail_episode:
            raise SyntheticRetryableError(f"suffix failed: {item_id}")
        is_variant = bool(item.get("is_variant"))
        return {
            "item_id": item_id,
            "family": item["family"],
            "observation_keys": ["variant-path" if is_variant else "seed-path"],
            "weighted_flags": {},
            "accepted": True,
            "duration_minutes": 0.3 if is_variant else 0.2,
            "retryable_infra_error": False,
        }

    def release_episode_group(self, handle: object, **_: object) -> None:
        assert handle is self.handle
        self.release_calls += 1

    # Keep a strict legacy signature to prove fallback does not leak episode-
    # only context into adapters implementing the original execute contract.
    def execute(
        self,
        item: dict,
        *,
        run_root: Path,
        arm: str,
        epoch: int,
        branch_id: str,
    ) -> dict:
        del run_root, arm, epoch, branch_id
        item_id = str(item["item_id"])
        self.legacy_calls.append(item_id)
        return {
            "item_id": item_id,
            "family": item["family"],
            "observation_keys": [f"fresh:{item_id}"],
            "weighted_flags": {},
            "accepted": True,
            "duration_minutes": 0.6,
            "retryable_infra_error": False,
        }


def write_catalog(path: Path, spec_ids: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_explore_variant_catalog_v0",
                "specs": [
                    {
                        "spec_id": spec_id,
                        "seed_family": "alpha",
                        "intent": f"Try {spec_id}",
                        "priority": len(spec_ids) - index,
                    }
                    for index, spec_id in enumerate(spec_ids)
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def check_resume_contract(root: Path) -> None:
    root.mkdir(parents=True)
    adapter = ResumeAdapter()
    default_run = run_budget_arm(
        adapter,
        arm_key="default-arm",
        run_root=root,
        budget_minutes=1.0,
        worker_count=1,
        max_epochs=1,
    )
    assert default_run["resume"]["enabled"] is False, default_run
    assert default_run["resume"]["checkpoint_path"] is None, default_run
    assert not (root / "arm_checkpoint_default-arm.json").exists(), default_run

    try:
        run_budget_arm(
            adapter,
            arm_key="missing-arm",
            run_root=root,
            budget_minutes=1.0,
            worker_count=1,
            max_epochs=1,
            resume=True,
        )
    except ValueError as error:
        assert "does not exist" in str(error), error
    else:
        raise AssertionError("missing resume checkpoint should fail closed")

    catalog_path = root / "variant_catalog.json"
    write_catalog(catalog_path, ["spec-alpha-1"])
    common = {
        "adapter": adapter,
        "arm_key": "resume-arm",
        "run_root": root,
        "budget_minutes": 60.0,
        "worker_count": 2,
        "use_router": True,
        "frontier_max_lanes": 1,
        "variant_catalog_path": catalog_path,
        "duration_guard_factor": 0.0,
        "resumable": True,
    }
    first = run_budget_arm(max_epochs=1, **common)
    checkpoint_path = root / "arm_checkpoint_resume-arm.json"
    assert checkpoint_path.exists(), first
    assert first["epoch_count"] == 1, first
    assert first["novel_value_total"] == 1.0, first
    assert first["variant_records_total"] == 1, first
    assert first["resume"]["resumed"] is False, first
    assert json.loads((root / "variant_consumption_resume-arm.json").read_text()) == [
        "spec-alpha-1"
    ]

    write_catalog(catalog_path, ["spec-alpha-1", "spec-alpha-2"])
    # The manifest, not a loose observability file, is restart authority.
    (root / "variant_consumption_resume-arm.json").write_text("[]\n", encoding="utf-8")
    resumed = run_budget_arm(max_epochs=2, resume=True, **common)
    assert resumed["epoch_count"] == 2, resumed
    assert resumed["resume"]["restored_epoch_count"] == 1, resumed
    assert resumed["novel_value_total"] == 1.0, resumed
    assert resumed["variant_records_total"] == 2, resumed
    assert resumed["raw_value_total"] > first["raw_value_total"], resumed
    assert [epoch["epoch"] for epoch in resumed["epochs"]] == [1, 2], resumed
    assert adapter.executed.count("variant-spec-alpha-1") == 1, adapter.executed
    assert adapter.executed.count("variant-spec-alpha-2") == 1, adapter.executed
    assert json.loads((root / "variant_consumption_resume-arm.json").read_text()) == [
        "spec-alpha-1",
        "spec-alpha-2",
    ]
    guidance = resumed["runtime_policy"]["planner_guidance"]
    assert guidance["retry_backoff"] == {
        "enforced": False,
        "owner": "external_runner",
    }, resumed

    manifest = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == HARNESS_CHECKPOINT_SCHEMA_VERSION, manifest
    assert manifest["completed_epochs"] == 2, manifest
    assert manifest["state"]["novelty_seen"] == ["shared-observation"], manifest
    assert manifest["state"]["router_state"]["totals"]["observed_epochs"] == 2, manifest

    valid_manifest = checkpoint_path.read_text(encoding="utf-8")
    checkpoint_path.write_text("{\n", encoding="utf-8")
    try:
        run_budget_arm(max_epochs=3, resume=True, **common)
    except ValueError as error:
        assert "invalid JSON" in str(error), error
    else:
        raise AssertionError("corrupt resume checkpoint should fail closed")
    checkpoint_path.write_text(valid_manifest, encoding="utf-8")

    incompatible = dict(common)
    incompatible["worker_count"] = 3
    try:
        run_budget_arm(max_epochs=3, resume=True, **incompatible)
    except ValueError as error:
        assert "runtime is incompatible" in str(error), error
        assert "worker_count" in str(error), error
    else:
        raise AssertionError("incompatible resume checkpoint should fail closed")


def check_item_failure_isolation(root: Path) -> None:
    root.mkdir(parents=True)
    calls: list[str] = []

    def execute(item: dict, **_: object) -> dict:
        item_id = str(item["item_id"])
        calls.append(item_id)
        if item_id == "fails":
            raise SyntheticRetryableError("transient provider failure")
        return {
            "item_id": item_id,
            "family": item["family"],
            "observation_keys": [item_id],
            "weighted_flags": {},
            "accepted": True,
            "duration_minutes": 0.1,
        }

    lanes = run_queue_epoch(
        [
            {
                "item_id": "fails",
                "family": "alpha",
                "concurrency_keys": ["shared", "first-only"],
            },
            {
                "item_id": "after",
                "family": "alpha",
                "concurrency_keys": ["shared", "second-only"],
            },
            {"item_id": "other", "family": "beta", "concurrency_key": "other"},
        ],
        execute=execute,
        worker_count=2,
        run_root=root,
        arm="failure-arm",
        epoch=1,
    )
    records = [record for lane in lanes for record in lane["results"]]
    assert {record["item_id"] for record in records} == {"fails", "after", "other"}, records
    failed = next(record for record in records if record["item_id"] == "fails")
    assert failed["execution_status"] == "adapter_error", failed
    assert failed["accepted"] is False, failed
    assert failed["retryable_infra_error"] is True, failed
    assert failed["adapter_error"]["type"] == "SyntheticRetryableError", failed
    assert calls.index("after") > calls.index("fails"), calls

    try:
        run_queue_epoch(
            [{"item_id": "fails", "family": "alpha", "concurrency_key": "shared"}],
            execute=execute,
            worker_count=1,
            run_root=root,
            arm="fatal-arm",
            epoch=1,
            item_failure_policy=ITEM_FAILURE_POLICY_FATAL,
        )
    except SyntheticRetryableError:
        pass
    else:
        raise AssertionError("fatal item failure policy should preserve fail-fast behavior")

    empty_lanes = run_queue_epoch(
        [{"item_id": "empty", "family": "alpha"}],
        execute=lambda *_args, **_kwargs: [],
        worker_count=1,
        run_root=root,
        arm="empty-result-arm",
        epoch=1,
    )
    empty_record = empty_lanes[0]["results"][0]
    assert empty_record["execution_status"] == "adapter_error", empty_record
    assert empty_record["adapter_error"]["type"] == "TypeError", empty_record

    class FatalAdapter:
        item_failure_policy = "fatal"

        def list_seed_items(self) -> list[dict]:
            return [{"item_id": "fatal", "family": "fatal"}]

        def execute(self, item: dict, **_: object) -> dict:
            raise SyntheticRetryableError(str(item["item_id"]))

    try:
        run_budget_arm(
            FatalAdapter(),
            arm_key="adapter-fatal-arm",
            run_root=root / "adapter-fatal",
            budget_minutes=1.0,
            worker_count=1,
            max_epochs=1,
        )
    except SyntheticRetryableError:
        pass
    else:
        raise AssertionError("adapter fatal policy should reach the budget-arm runner")


def _arm_records(arm: dict) -> list[dict]:
    return [
        record
        for epoch in arm["epochs"]
        for lane in epoch["lanes"]
        for record in lane["results"]
    ]


def check_recoverable_episode_contract(root: Path) -> None:
    root.mkdir(parents=True)
    catalog_path = root / "variant_catalog.json"
    write_catalog(catalog_path, ["spec-alpha-episode"])

    def run(
        adapter: RecoverableBlackBoxAdapter,
        name: str,
        *,
        item_failure_policy: str | None = None,
        max_epochs: int = 1,
        resumable: bool = False,
        resume: bool = False,
    ) -> dict:
        return run_budget_arm(
            adapter,
            arm_key=name,
            run_root=root / name,
            budget_minutes=5.0,
            worker_count=2,
            max_epochs=max_epochs,
            use_router=True,
            frontier_max_lanes=1,
            variant_catalog_path=catalog_path,
            duration_guard_factor=0.0,
            item_failure_policy=item_failure_policy,
            resumable=resumable,
            resume=resume,
        )

    adapter = RecoverableBlackBoxAdapter()
    arm = run(adapter, "recoverable")
    records = _arm_records(arm)
    prefix = [
        record for record in records if record.get("record_kind") == "shared_prefix"
    ]
    suffixes = [
        record for record in records if record.get("record_kind") == "episode_suffix"
    ]
    assert len(prefix) == 1, records
    assert len(suffixes) == 2, records
    assert {record["execution_group_id"] for record in records} == {
        prefix[0]["execution_group_id"]
    }, records
    assert prefix[0]["checkpoint_ref"] == "opaque:black-box-state-1", prefix
    assert all(record["prefix_reused"] is True for record in records), records
    assert adapter.prepare_calls == [
        ["seed-alpha", "variant-spec-alpha-episode"]
    ], adapter.prepare_calls
    assert adapter.episode_calls == [
        "seed-alpha",
        "variant-spec-alpha-episode",
    ], adapter.episode_calls
    assert adapter.release_calls == 1, adapter.release_calls
    assert adapter.legacy_calls == [], adapter.legacy_calls
    assert arm["raw_value_total"] == 5.0, arm
    assert arm["novel_value_total"] == 5.0, arm
    assert arm["epochs"][0]["queue_size"] == 2, arm
    assert arm["epochs"][0]["execution_unit_count"] == 1, arm
    assert arm["execution_metrics"] == {
        "shared_prefix_compute_minutes": 0.4,
        "episode_suffix_compute_minutes": 0.5,
        "standalone_compute_minutes": 0.0,
        "effective_compute_minutes": 0.9,
        "avoided_recompute_minutes": 0.4,
        "successful_avoided_recompute_minutes": 0.4,
        "episode_group_count": 1,
        "episode_count": 2,
        "episode_error_count": 0,
    }, arm
    assert arm["runtime_policy"]["episode_execution"] == {
        "mode": "recoverable-v0",
        "adapter_owned_restore": True,
    }, arm
    router_state = json.loads(
        (root / "recoverable" / "router_state_recoverable.json").read_text()
    )
    assert router_state["totals"]["dispatches"] == 1, router_state
    assert router_state["families"]["alpha"]["runs"] == 1, router_state
    assert router_state["last_epoch"]["minutes_by_family"] == {"alpha": 0.9}, router_state
    assert router_state["seen_observation_keys"] == [
        "application-ready",
        "flag:alpha:shared-state",
        "seed-path",
        "variant-path",
    ], router_state
    assert router_state["families"]["alpha"]["accept_rate_ema"] == 1.0, router_state
    assert router_state["families"]["alpha"]["infra_ema"] == 0.0, router_state

    fallback_adapter = RecoverableBlackBoxAdapter(prepare_behavior="none")
    fallback = run(fallback_adapter, "fallback")
    fallback_records = _arm_records(fallback)
    assert {record["record_kind"] for record in fallback_records} == {"standalone"}
    assert fallback_adapter.legacy_calls == [
        "seed-alpha",
        "variant-spec-alpha-episode",
    ], fallback_adapter.legacy_calls
    assert fallback_adapter.release_calls == 0, fallback_adapter.release_calls
    assert fallback["execution_metrics"]["episode_group_count"] == 0, fallback
    assert fallback["execution_metrics"]["standalone_compute_minutes"] == 1.2, fallback

    resume_adapter = RecoverableBlackBoxAdapter()
    write_catalog(catalog_path, ["spec-alpha-resume-1"])
    first_episode = run(
        resume_adapter,
        "episode-resume",
        resumable=True,
    )
    write_catalog(
        catalog_path,
        ["spec-alpha-resume-1", "spec-alpha-resume-2"],
    )
    resumed_episode = run(
        resume_adapter,
        "episode-resume",
        max_epochs=2,
        resumable=True,
        resume=True,
    )
    assert first_episode["execution_metrics"]["episode_group_count"] == 1, first_episode
    assert resumed_episode["execution_metrics"] == {
        "shared_prefix_compute_minutes": 0.8,
        "episode_suffix_compute_minutes": 1.0,
        "standalone_compute_minutes": 0.0,
        "effective_compute_minutes": 1.8,
        "avoided_recompute_minutes": 0.8,
        "successful_avoided_recompute_minutes": 0.8,
        "episode_group_count": 2,
        "episode_count": 4,
        "episode_error_count": 0,
    }, resumed_episode
    assert len(resume_adapter.prepare_calls) == 2, resume_adapter.prepare_calls
    episode_manifest_path = (
        root / "episode-resume" / "arm_checkpoint_episode-resume.json"
    )
    episode_manifest_text = episode_manifest_path.read_text(encoding="utf-8")
    assert '"handle"' not in episode_manifest_text, episode_manifest_text
    episode_manifest = json.loads(episode_manifest_text)
    assert episode_manifest["runtime_signature"]["episode_mode"] == (
        "recoverable-v0"
    ), episode_manifest
    standalone_signature = dict(episode_manifest["runtime_signature"])
    standalone_signature["episode_mode"] = None
    try:
        load_arm_checkpoint(
            episode_manifest_path,
            expected_signature=standalone_signature,
        )
    except ValueError as error:
        assert "episode_mode" in str(error), error
    else:
        raise AssertionError("recoverable checkpoint must not resume as standalone")
    write_catalog(catalog_path, ["spec-alpha-episode"])

    failing_adapter = RecoverableBlackBoxAdapter(
        fail_episode="variant-spec-alpha-episode"
    )
    failed = run(failing_adapter, "suffix-failure")
    failed_records = _arm_records(failed)
    failed_suffix = next(
        record
        for record in failed_records
        if record.get("item_id") == "variant-spec-alpha-episode"
    )
    assert failed_suffix["execution_status"] == "adapter_error", failed_suffix
    assert failed_suffix["episode_stage"] == "execute", failed_suffix
    assert failing_adapter.release_calls == 1, failing_adapter.release_calls
    failed_metrics = failed["execution_metrics"]
    assert failed_metrics["episode_count"] == 2, failed_metrics
    assert failed_metrics["episode_error_count"] == 1, failed_metrics
    # Structural reuse and successful-equivalent reuse remain separate.
    assert failed_metrics["avoided_recompute_minutes"] == 0.4, failed_metrics
    assert failed_metrics["successful_avoided_recompute_minutes"] == 0.0, (
        failed_metrics
    )
    failed_router_state = json.loads(
        (root / "suffix-failure" / "router_state_suffix-failure.json").read_text()
    )
    # Folded group probes keep the per-suffix reject rate via integer counts:
    # one accepted seed suffix + one failed variant suffix reads as 0.5.
    assert failed_router_state["families"]["alpha"]["accept_rate_ema"] == 0.5, (
        failed_router_state
    )

def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-explore-runtime-resume-") as tmp:
        root = Path(tmp)
        check_resume_contract(root / "resume")
        check_item_failure_isolation(root / "failures")
        check_recoverable_episode_contract(root / "episodes")
    print("explore-harness-runtime-resume-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
