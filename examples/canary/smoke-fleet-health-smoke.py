#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.smoke_health import build_smoke_fleet_health  # noqa: E402


def main() -> int:
    inventory_payload = build_smoke_fleet_health(include_inventory=True)
    inventory = inventory_payload["inventory"]
    scripts = [entry["script"] for entry in inventory]
    assert len(scripts) >= 500
    assert inventory_payload["cadence_counts"]["daily_full_public"] == len(scripts)
    assert inventory_payload["workflow_contract"]["missing_scripts"] == []

    receipt = {
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
                "duration_seconds": 1.0,
            }
            for script in scripts
        ],
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        receipt_path = Path(temp_dir) / "full-public.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        health = build_smoke_fleet_health(receipt_paths=[receipt_path])

    assert health["ok"] is True
    assert health["ready"] is True
    assert health["receipt_health"]["observed_script_count"] == len(scripts)
    assert health["contract_reuse"]["semantic_duplicate_inference"] == "manual_review_required"
    assert "inventory" not in health
    assert len(json.dumps(health, ensure_ascii=False)) < 30_000
    print(
        "smoke-fleet-health-smoke ok "
        f"inventory={len(scripts)} owners={health['targeted_owner_count']} "
        f"owner_gaps={health['owner_gap_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
