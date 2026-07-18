#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.periodic_report import build_periodic_report_run  # noqa: E402


def main() -> None:
    payload = build_periodic_report_run(
        {
            "schema_version": "periodic_report_run_request_v0",
            "generated_at": "2026-07-20T01:00:00Z",
            "period_window": {
                "start_at": "2026-07-13T00:00:00Z",
                "end_at": "2026-07-20T00:00:00Z",
            },
            "profile": {
                "profile_id": "sample_weekly",
                "profile_version": "v1",
            },
            "source_snapshots": [
                {
                    "source_id": "activity",
                    "source_kind": "project_activity",
                    "status": "complete",
                    "observed_at": "2026-07-20T00:30:00Z",
                    "snapshot_digest": "sha256:sample",
                    "item_count": 4,
                }
            ],
            "artifact_receipt": {
                "artifact_id": "sample_digest",
                "renderer_id": "sample_markdown",
                "renderer_kind": "markdown",
                "status": "pending",
            },
            "sink_receipts": [
                {
                    "sink_id": "sample_archive",
                    "sink_kind": "resource_store",
                    "sink_role": "archive",
                    "status": "pending",
                },
                {
                    "sink_id": "sample_delivery",
                    "sink_kind": "message_channel",
                    "sink_role": "delivery",
                    "status": "pending",
                },
            ],
            "retry_policy": {"attempt": 1, "max_attempts": 3},
        }
    )
    assert payload["schema_version"] == "periodic_report_v0"
    assert payload["run_state"]["status"] == "pending"
    assert payload["boundary"]["provider_neutral"] is True
    print(payload["run_id"])


if __name__ == "__main__":
    main()
