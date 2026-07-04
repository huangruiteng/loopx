#!/usr/bin/env python3
"""Smoke-test promotion readiness read-model parity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.runtime import promotion_readiness as readiness_read_model  # noqa: E402


def normalize_dynamic_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for key in ("freshness_reference_time", "age_seconds", "age_hours"):
        normalized.pop(key, None)
    return normalized


def direct_summary(
    history: dict[str, Any],
    *,
    runtime_root: Path | None = None,
    goal_id_filter: str | None = None,
) -> dict[str, Any]:
    return readiness_read_model.build_promotion_readiness_summary(
        history,
        parse_timestamp=status_module.parse_timestamp,
        readiness_classifications=status_module.PROMOTION_READINESS_CLASSIFICATIONS,
        add_promotion_readiness_freshness=status_module.add_promotion_readiness_freshness,
        latest_promotion_readiness_event=lambda root: status_module.latest_promotion_readiness_event(
            root,
            goal_id=goal_id_filter,
        ),
        freshness_hours=status_module.PROMOTION_READINESS_FRESHNESS_HOURS,
        runtime_root=runtime_root,
        proxy_note=status_module.PROMOTION_READINESS_PROXY_NOTE,
    )


def write_indexed_readiness_run(
    runtime_root: Path,
    *,
    goal_id: str,
    generated_at: str,
    classification: str = "canary_promotion_readiness_smoke_group",
) -> None:
    run_dir = runtime_root / "goals" / goal_id / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "readiness.json"
    markdown_path = run_dir / "readiness.md"
    json_path.write_text("{}\n", encoding="utf-8")
    markdown_path.write_text("# readiness\n", encoding="utf-8")
    record = {
        "goal_id": goal_id,
        "generated_at": generated_at,
        "classification": classification,
        "delivery_batch_scale": "multi_surface",
        "delivery_outcome": "primary_goal_outcome",
        "recommended_action": "promotion readiness smoke passed",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    with (run_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def assert_parity(
    history: dict[str, Any],
    *,
    runtime_root: Path | None = None,
    goal_id_filter: str | None = None,
) -> dict[str, Any]:
    wrapper = status_module.build_promotion_readiness_summary(
        history,
        runtime_root=runtime_root,
        goal_id_filter=goal_id_filter,
    )
    direct = direct_summary(
        history,
        runtime_root=runtime_root,
        goal_id_filter=goal_id_filter,
    )
    assert normalize_dynamic_freshness(direct) == normalize_dynamic_freshness(wrapper), (direct, wrapper)
    return wrapper


def main() -> None:
    now = datetime.now(timezone.utc)
    sampled_history = {
        "runs": [
            {
                "goal_id": "project-a",
                "generated_at": (now - timedelta(hours=1)).isoformat(),
                "classification": "canary_promotion_readiness_smoke_group",
                "delivery_batch_scale": "multi_surface",
                "delivery_outcome": "primary_goal_outcome",
                "recommended_action": "promotion ready",
                "json_exists": True,
                "markdown_exists": True,
            },
            {
                "goal_id": "project-a",
                "generated_at": (now - timedelta(hours=3)).isoformat(),
                "classification": "canary_promotion_readiness_smoke_group",
                "delivery_batch_scale": "single_surface",
                "delivery_outcome": "test_only",
                "json_exists": False,
                "markdown_exists": False,
            },
            {
                "goal_id": "project-b",
                "generated_at": "not-a-timestamp",
                "classification": "canary_promotion_readiness_smoke_group",
            },
            {
                "goal_id": "project-b",
                "generated_at": (now - timedelta(minutes=10)).isoformat(),
                "classification": "state_refreshed",
            },
        ]
    }
    sampled = assert_parity(sampled_history)
    assert sampled["available"] is True, sampled
    assert sampled["source"] == "run_history", sampled
    assert sampled["goal_id"] == "project-a", sampled
    assert sampled["sample_run_count"] == 3, sampled
    assert sampled["freshness_status"] == "fresh", sampled
    assert sampled["requires_readiness_run"] is False, sampled
    assert sampled["delivery_outcome"] == "primary_goal_outcome", sampled
    assert sampled["json_exists"] is True, sampled
    assert sampled["markdown_exists"] is True, sampled

    with tempfile.TemporaryDirectory(prefix="loopx-promotion-readiness-") as tmp:
        runtime_root = Path(tmp) / "runtime"
        generated_at = (now - timedelta(hours=2)).isoformat()
        write_indexed_readiness_run(runtime_root, goal_id="project-c", generated_at=generated_at)
        fallback = assert_parity({"runs": []}, runtime_root=runtime_root, goal_id_filter="project-c")
        assert fallback["available"] is True, fallback
        assert fallback["source"] == "run_history_full_scan", fallback
        assert fallback["goal_id"] == "project-c", fallback
        assert fallback["sample_run_count"] == 0, fallback
        assert fallback["json_exists"] is True, fallback
        assert fallback["markdown_exists"] is True, fallback

        missing = assert_parity({"runs": []}, runtime_root=runtime_root / "empty", goal_id_filter="missing")
        assert missing["available"] is False, missing
        assert missing["source"] == "run_history", missing
        assert missing["freshness_status"] == "missing", missing
        assert missing["requires_readiness_run"] is True, missing
        assert missing["reason"] == "no canary promotion readiness run found in full run history", missing

    sampled_missing = assert_parity({"runs": []})
    assert sampled_missing["reason"] == "no canary promotion readiness run found in sampled history", sampled_missing
    print("promotion-readiness-readmodel-smoke ok")


if __name__ == "__main__":
    main()
