#!/usr/bin/env python3
"""Smoke-test the content-ops preview CLI."""

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
    CONTENT_OPS_PREVIEW_PACKET_SCHEMA_VERSION,
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


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    result = run_cli(["--format", "json", "content-ops", "preview"])
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CONTENT_OPS_PREVIEW_PACKET_SCHEMA_VERSION, payload
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["autopublish_allowed"] is False, payload

    connector_trials = payload["connector_trials"]
    assert connector_trials["count"] == 2, connector_trials
    assert connector_trials["ready_for_metadata_trial_count"] == 1, connector_trials
    assert connector_trials["owner_gate_required_count"] == 1, connector_trials
    assert connector_trials["surfaces"] == {
        "wechat_private_archive": 1,
        "x_public_feed": 1,
    }, connector_trials
    assert connector_trials["access_modes"] == {
        "private_metadata_only": 1,
        "public_metadata_only": 1,
    }, connector_trials

    todo_candidates = payload["projection"]["todo_candidates"]
    action_kinds = {candidate["action_kind"] for candidate in todo_candidates}
    assert "content_ops_connector_metadata_trial" in action_kinds, todo_candidates
    assert "content_ops_connector_owner_gate" in action_kinds, todo_candidates
    assert_public_safe(payload)

    markdown = run_cli(["content-ops", "preview"]).stdout
    assert "LoopX Content-Ops Preview" in markdown, markdown
    assert "external_reads_performed: `False`" in markdown, markdown
    assert "owner_gate_required_count: `1`" in markdown, markdown

    print("content-ops-preview-cli-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
