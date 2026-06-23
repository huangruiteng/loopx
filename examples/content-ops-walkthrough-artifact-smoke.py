#!/usr/bin/env python3
"""Smoke-test the public-safe content-ops walkthrough artifact."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.content_ops.surface import (  # noqa: E402
    CONTENT_OPS_WALKTHROUGH_ARTIFACT_SCHEMA_VERSION,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


FORBIDDEN_VALUES = [
    "full chat transcript",
    "raw platform post body",
    "secret-value",
    "credential-value",
    "source body text",
    "response payload text",
]


def assert_public_safe(payload: dict[str, Any] | str) -> None:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"payload matched private pattern {pattern.pattern!r}")
    leaked = [value for value in FORBIDDEN_VALUES if value in text]
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


WALKTHROUGH_ARGS = [
    "content-ops",
    "walkthrough-artifact",
    "--public-handle-url",
    "https://x.com/OpenAI",
    "--public-source-item-id",
    "source_x_openai_public_walkthrough_fixture",
    "--chatview-source-item-id",
    "source_chatview_metadata_walkthrough_fixture",
    "--channel-count",
    "2",
    "--recent-record-count",
    "50",
    "--report-count",
    "2",
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
    "--private-preview-item-count",
    "12",
    "--theme-signal",
    "market-risk watch",
    "--theme-signal",
    "semiconductor earnings pressure",
]


def main() -> int:
    result = run_cli(["--format", "json", *WALKTHROUGH_ARGS])
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CONTENT_OPS_WALKTHROUGH_ARTIFACT_SCHEMA_VERSION
    assert payload["mode"] == "content-ops-walkthrough-artifact", payload
    assert payload["public_repo_safe"] is True, payload
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["autopublish_allowed"] is False, payload

    operator_artifact = payload["operator_artifact"]
    assert "explicit gates" in operator_artifact["headline"], operator_artifact
    source_cards = operator_artifact["source_cards"]
    assert len(source_cards) == 2, source_cards
    statuses = {item["source_status"] for item in source_cards}
    assert statuses == {"public", "private_needs_review"}, statuses

    preview = operator_artifact["private_operator_preview"]
    assert preview["available_in_current_operator_session"] is True, preview
    assert preview["sample_record_count"] == 12, preview
    assert preview["theme_signals"] == [
        "market-risk watch",
        "semiconductor earnings pressure",
    ], preview
    assert preview["stored_in_repo"] is False, preview
    assert preview["source_content_recorded"] is False, preview
    assert preview["response_payload_recorded"] is False, preview

    draft_gate = operator_artifact["draft_gate"]
    assert draft_gate["publish_status"] == "blocked_until_user_approval", draft_gate
    assert draft_gate["approval_required"] is True, draft_gate
    assert draft_gate["autopublish_allowed"] is False, draft_gate

    step_names = [item["step"] for item in payload["chain_steps"]]
    assert step_names == [
        "public_signal_intake",
        "private_connector_operator_card",
        "aggregate_surface_projection",
        "draft_publish_gate",
    ], step_names
    private_step = payload["chain_steps"][1]
    assert private_step["owner_gate_required"] is True, private_step
    assert private_step["observed_shape"]["recent_record_count"] == 50, private_step

    first_screen = payload["aggregation_projection"]["first_screen"]
    assert first_screen["waiting_on"] == "user", first_screen
    assert first_screen["user_action_required"] is True, first_screen
    assert first_screen["agent_can_continue"] is True, first_screen

    packet_summary = payload["packet_summary"]
    assert packet_summary["source_item_count"] == 2, packet_summary
    assert packet_summary["owner_gate_required_count"] == 1, packet_summary
    assert payload["validation"]["ok"] is True, payload["validation"]
    assert_public_safe(payload)

    markdown = run_cli(WALKTHROUGH_ARGS).stdout
    assert "LoopX Content-Ops Walkthrough Artifact" in markdown, markdown
    assert "market-risk watch" in markdown, markdown
    assert "blocked_until_user_approval" in markdown, markdown
    assert_public_safe(markdown)

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "walkthrough-artifact",
            "--channel-count",
            "0",
            "--recent-record-count",
            "0",
            "--report-count",
            "0",
            "--api-request-count",
            "0",
            "--theme-signal",
            "https://example.com/not-a-label",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "theme_signal must be a compact public-safe label" in rejected_payload["error"]

    print("content-ops-walkthrough-artifact-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
