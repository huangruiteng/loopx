#!/usr/bin/env python3
"""Smoke-test content-ops packet aggregation into a surface projection."""

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
    CONTENT_OPS_PACKET_AGGREGATION_SCHEMA_VERSION,
    CONTENT_OPS_SURFACE_PROJECTION_SCHEMA_VERSION,
    CONTENT_OPS_SURFACE_SCHEMA_VERSION,
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


def main() -> int:
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
    private_packet = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "project-private-connector-gate",
        ]
    ).stdout

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        public_path = tmp_path / "public-packet.json"
        private_path = tmp_path / "private-gate.json"
        public_path.write_text(public_packet, encoding="utf-8")
        private_path.write_text(private_packet, encoding="utf-8")

        result = run_cli(
            [
                "--format",
                "json",
                "content-ops",
                "aggregate-packets",
                "--public-packet-json",
                str(public_path),
                "--private-gate-packet-json",
                str(private_path),
                "--surface-id",
                "content_ops_packet_aggregation_smoke",
            ]
        )
        markdown = run_cli(
            [
                "content-ops",
                "aggregate-packets",
                "--public-packet-json",
                str(public_path),
                "--private-gate-packet-json",
                str(private_path),
            ]
        ).stdout
        assert "LoopX Content-Ops Packet Aggregation" in markdown, markdown
        assert "owner_gate_required_count: `1`" in markdown, markdown

    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CONTENT_OPS_PACKET_AGGREGATION_SCHEMA_VERSION
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["autopublish_allowed"] is False, payload

    summary = payload["input_summary"]
    assert summary["public_handle_packet_count"] == 1, summary
    assert summary["private_connector_gate_packet_count"] == 1, summary
    assert summary["source_item_count"] == 2, summary
    assert summary["owner_gate_required_count"] == 1, summary

    surface = payload["surface"]
    assert surface["schema_version"] == CONTENT_OPS_SURFACE_SCHEMA_VERSION, surface
    assert surface["surface_id"] == "content_ops_packet_aggregation_smoke", surface
    assert surface["boundary"]["public_safe"] is True, surface
    assert surface["boundary"]["connector_bodies_are_source_of_truth"] is False, surface

    projection = payload["projection"]
    assert (
        projection["schema_version"] == CONTENT_OPS_SURFACE_PROJECTION_SCHEMA_VERSION
    ), projection
    first_screen = projection["first_screen"]
    assert first_screen["user_action_required"] is True, first_screen
    assert first_screen["agent_can_continue"] is True, first_screen
    assert first_screen["source_review_required_count"] == 2, first_screen
    assert first_screen["publish_decision_count"] == 1, first_screen

    connector_trials = projection["connector_trials"]
    assert connector_trials["count"] == 2, connector_trials
    assert connector_trials["states"] == {
        "metadata_packet_collected": 1,
        "needs_owner_gate": 1,
    }, connector_trials
    assert connector_trials["ready_for_metadata_trial_count"] == 0, connector_trials
    assert connector_trials["owner_gate_required_count"] == 1, connector_trials

    todo_candidates = projection["todo_candidates"]
    action_kinds = {candidate["action_kind"] for candidate in todo_candidates}
    assert "content_ops_draft_from_angle" in action_kinds, todo_candidates
    assert "content_ops_source_review" in action_kinds, todo_candidates
    assert "content_ops_publish_gate" in action_kinds, todo_candidates
    assert "content_ops_connector_owner_gate" in action_kinds, todo_candidates
    assert "content_ops_connector_metadata_trial" not in action_kinds, todo_candidates

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "aggregate-packets",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "at least one public handle observation packet" in rejected_payload["error"]

    assert_public_safe(payload)
    print("content-ops-packet-aggregation-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
