#!/usr/bin/env python3
"""Smoke the Explore Harness restart and per-item failure contracts."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.explore.harness_runtime import (  # noqa: E402
    HARNESS_CHECKPOINT_SCHEMA_VERSION,
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
            {"item_id": "fails", "family": "alpha", "concurrency_key": "shared"},
            {"item_id": "after", "family": "alpha", "concurrency_key": "shared"},
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-explore-runtime-resume-") as tmp:
        root = Path(tmp)
        check_resume_contract(root / "resume")
        check_item_failure_isolation(root / "failures")
    print("explore-harness-runtime-resume-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
