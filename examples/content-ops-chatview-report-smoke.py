#!/usr/bin/env python3
"""Smoke-test the ChatView report command and aggregation path."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.content_ops_surface import (  # noqa: E402
    CONTENT_OPS_CHATVIEW_CONNECTOR_REPORT_SCHEMA_VERSION,
    CONTENT_OPS_PRIVATE_CONNECTOR_GATE_PACKET_SCHEMA_VERSION,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"payload matched private pattern {pattern.pattern!r}")
    forbidden_values = [
        "full chat transcript",
        "raw platform post body",
        "secret-value",
        "credential-value",
        "source body text",
        "response payload text",
    ]
    leaked = [value for value in forbidden_values if value in text]
    assert not leaked, leaked


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


CHATVIEW_ARGS = [
    "content-ops",
    "project-chatview-report",
    "--channel-count",
    "2",
    "--recent-record-count",
    "50",
    "--report-count",
    "5",
    "--api-request-count",
    "54",
    "--api-path-count",
    "/api/channels=1",
    "--api-path-count",
    "/api/messages=1",
    "--api-path-count",
    "/api/channel-state=1",
    "--api-path-count",
    "/api/reports=1",
    "--api-path-count",
    "/api/messages/:id=50",
    "--source-item-id",
    "source_chatview_metadata_signal_live_fixture",
]


def main() -> int:
    result = run_cli(["--format", "json", *CHATVIEW_ARGS])
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CONTENT_OPS_PRIVATE_CONNECTOR_GATE_PACKET_SCHEMA_VERSION
    assert payload["mode"] == "content-ops-project-chatview-report", payload
    assert payload["aggregation_ready"] is True, payload
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["autopublish_allowed"] is False, payload

    report = payload["chatview_report"]
    assert (
        report["schema_version"] == CONTENT_OPS_CHATVIEW_CONNECTOR_REPORT_SCHEMA_VERSION
    ), report
    assert report["operator_card"] == (
        "2 channels, 50 recent records, 5 reports detected; "
        "private source use remains gated."
    ), report
    observed = report["observed_shape"]
    assert observed["channel_count"] == 2, observed
    assert observed["recent_record_count"] == 50, observed
    assert observed["report_count"] == 5, observed
    assert observed["api_request_count"] == 54, observed
    assert observed["api_path_counts"]["/api/messages/:id"] == 50, observed
    boundary = report["boundary"]
    assert boundary["source_bodies_saved"] is False, boundary
    assert boundary["response_payloads_saved"] is False, boundary
    assert boundary["external_write_performed"] is False, boundary
    assert boundary["autopublish_allowed"] is False, boundary

    source_item = payload["source_item"]
    assert source_item["source_status"] == "private_needs_review", source_item
    assert source_item["allowed_use"] == "metadata_only", source_item
    assert "No source body or response payload was saved." in source_item["summary"]

    markdown = run_cli(CHATVIEW_ARGS).stdout
    assert "LoopX Content-Ops ChatView Report" in markdown, markdown
    assert "2 channels, 50 recent records, 5 reports detected" in markdown, markdown
    assert "source_bodies_saved: `False`" in markdown, markdown
    assert_public_safe(payload)

    public_packet = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "observe-public-handle",
            "--url",
            "https://x.com/OpenAI",
            "--source-item-id",
            "source_x_openai_public_handle_fixture",
            "--no-fetch",
        ]
    ).stdout
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        public_path = tmp_path / "public-packet.json"
        chatview_path = tmp_path / "chatview-report.json"
        public_path.write_text(public_packet, encoding="utf-8")
        chatview_path.write_text(result.stdout, encoding="utf-8")
        aggregated = run_cli(
            [
                "--format",
                "json",
                "content-ops",
                "aggregate-packets",
                "--public-packet-json",
                str(public_path),
                "--private-gate-packet-json",
                str(chatview_path),
            ]
        )
    aggregate_payload = json.loads(aggregated.stdout)
    assert aggregate_payload["ok"] is True, aggregate_payload
    assert aggregate_payload["input_summary"]["private_connector_gate_packet_count"] == 1
    assert aggregate_payload["projection"]["connector_trials"][
        "owner_gate_required_count"
    ] == 1
    assert_public_safe(aggregate_payload)

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "project-chatview-report",
            "--channel-count",
            "-1",
            "--recent-record-count",
            "0",
            "--report-count",
            "0",
            "--api-request-count",
            "0",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "channel_count must be non-negative" in rejected_payload["error"]

    print("content-ops-chatview-report-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
