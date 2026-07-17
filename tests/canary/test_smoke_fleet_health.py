from __future__ import annotations

import json
from pathlib import Path

from loopx.canary.smoke_health import build_smoke_fleet_health


def _passing_receipt(scripts: list[str]) -> dict[str, object]:
    return {
        "schema_version": "canary_smoke_suite_run_v0",
        "suite": "full-public",
        "timeout_seconds": 120.0,
        "failure_count": 0,
        "timeout_count": 0,
        "selected_checks": [
            {
                "normalized": {"script": script},
                "status": "passed",
                "ok": True,
                "duration_seconds": float((index % 7) + 1),
            }
            for index, script in enumerate(scripts)
        ],
    }


def test_static_health_is_compact_and_classifies_cadence() -> None:
    payload = build_smoke_fleet_health()

    assert payload["ok"] is True
    assert payload["ready"] is False
    assert payload["inventory_count"] >= 500
    assert payload["cadence_counts"]["daily_full_public"] == payload["inventory_count"]
    assert payload["cadence_counts"]["pr_fast"] == 1
    assert payload["cadence_counts"]["catalog_canary"] > 0
    assert payload["cadence_counts"]["release_gate"] > 0
    assert payload["owner_gap_count"] > 0
    assert payload["workflow_contract"]["missing_scripts"] == []
    assert payload["contract_reuse"]["semantic_duplicate_inference"] == "manual_review_required"
    assert "inventory" not in payload
    assert len(json.dumps(payload, ensure_ascii=False)) < 30_000


def test_receipts_prove_complete_health_without_copying_raw_output(tmp_path: Path) -> None:
    inventory_payload = build_smoke_fleet_health(include_inventory=True)
    scripts = [entry["script"] for entry in inventory_payload["inventory"]]
    receipt = _passing_receipt(scripts)
    receipt["selected_checks"][0]["stdout_tail"] = "private-looking raw output"
    receipt["selected_checks"][0]["stderr_tail"] = "/tmp/local-path"
    receipt_path = tmp_path / "full-public-shard.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    payload = build_smoke_fleet_health(receipt_paths=[receipt_path])

    assert payload["ok"] is True
    assert payload["ready"] is True
    assert payload["receipt_health"]["observed_script_count"] == len(scripts)
    assert payload["receipt_health"]["missing_script_count"] == 0
    assert payload["receipt_health"]["failure_count"] == 0
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "private-looking raw output" not in rendered
    assert "/tmp/local-path" not in rendered
    assert str(tmp_path) not in rendered


def test_failed_and_invalid_receipts_remain_distinct(tmp_path: Path) -> None:
    inventory_payload = build_smoke_fleet_health(include_inventory=True)
    scripts = [entry["script"] for entry in inventory_payload["inventory"]]
    receipt = _passing_receipt(scripts)
    receipt["failure_count"] = 1
    receipt["selected_checks"][0].update({"status": "failed", "ok": False})
    failed_path = tmp_path / "failed.json"
    failed_path.write_text(json.dumps(receipt), encoding="utf-8")

    failed = build_smoke_fleet_health(receipt_paths=[failed_path])
    assert failed["ok"] is True
    assert failed["ready"] is False
    assert failed["receipt_health"]["failure_count"] == 1

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{}", encoding="utf-8")
    invalid = build_smoke_fleet_health(receipt_paths=[invalid_path])
    assert invalid["ok"] is False
    assert invalid["ready"] is False
    assert invalid["warnings"][0]["kind"] == "unsupported_receipt"
