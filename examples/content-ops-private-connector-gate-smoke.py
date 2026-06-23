#!/usr/bin/env python3
"""Smoke-test the content-ops private connector owner-gate CLI."""

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

from loopx.content_ops_surface import (  # noqa: E402
    CONTENT_OPS_CONNECTOR_RUNTIME_POLICY_SCHEMA_VERSION,
    CONTENT_OPS_PRIVATE_CONNECTOR_GATE_PACKET_SCHEMA_VERSION,
    CONTENT_OPS_PRIVATE_CONNECTOR_OWNER_GATE_SCHEMA_VERSION,
    SOURCE_ITEM_SCHEMA_VERSION,
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
    result = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "project-private-connector-gate",
        ]
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert (
        payload["schema_version"]
        == CONTENT_OPS_PRIVATE_CONNECTOR_GATE_PACKET_SCHEMA_VERSION
    ), payload
    assert payload["owner_gate_required"] is True, payload
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["autopublish_allowed"] is False, payload
    runtime_policy = payload["runtime_policy"]
    assert (
        runtime_policy["schema_version"]
        == CONTENT_OPS_CONNECTOR_RUNTIME_POLICY_SCHEMA_VERSION
    ), runtime_policy
    assert runtime_policy["safe_default"] == "gate_projection_only", runtime_policy
    assert runtime_policy["browser_open_allowed_before_gate"] is False, runtime_policy
    assert "/api/messages" in runtime_policy[
        "forbidden_url_path_prefixes_before_approval"
    ], runtime_policy
    assert "/api/reports" in runtime_policy[
        "forbidden_url_path_prefixes_before_approval"
    ], runtime_policy
    assert "message-detail API calls" in runtime_policy[
        "forbidden_before_approval"
    ], runtime_policy

    connector = payload["connector"]
    assert connector["connector_id"] == "chatlog_alpha_chatview", connector
    assert connector["connector_name"] == "chatlog-alpha/chatview", connector
    assert connector["access_mode"] == "private_metadata_only", connector
    assert connector["source_status"] == "private_needs_review", connector
    assert connector["allowed_use"] == "metadata_only", connector

    gate = payload["owner_gate"]
    assert (
        gate["schema_version"]
        == CONTENT_OPS_PRIVATE_CONNECTOR_OWNER_GATE_SCHEMA_VERSION
    ), gate
    assert gate["status"] == "blocked_until_user_approval", gate
    assert gate["approval_required"] is True, gate
    assert "source content read" in gate["forbidden_until_approved"], gate
    assert "autopublish" in gate["forbidden_until_approved"], gate
    assert gate["runtime_policy"]["safe_default"] == "gate_projection_only", gate

    source_item = payload["source_item"]
    assert source_item["schema_version"] == SOURCE_ITEM_SCHEMA_VERSION, source_item
    assert source_item["source_status"] == "private_needs_review", source_item
    assert source_item["allowed_use"] == "metadata_only", source_item
    assert source_item["owner_gate"]["gate_id"] == gate["gate_id"], source_item

    todo = payload["user_todo_projection"]
    assert todo["role"] == "user", todo
    assert todo["action_kind"] == "content_ops_private_connector_owner_gate", todo
    assert todo["gate_id"] == gate["gate_id"], todo
    assert "before LoopX reads any private source content" in todo["title"], todo
    assert_public_safe(payload)

    markdown = run_cli(
        [
            "content-ops",
            "project-private-connector-gate",
        ]
    ).stdout
    assert "LoopX Content-Ops Private Connector Gate" in markdown, markdown
    assert "owner_gate_required: `True`" in markdown, markdown
    assert "external_reads_performed: `False`" in markdown, markdown
    assert "private_source_bodies_read: `False`" in markdown, markdown

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "project-private-connector-gate",
            "--proposed-source-item-id",
            "",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "proposed_source_item_id is required" in rejected_payload["error"]

    print("content-ops-private-connector-gate-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
