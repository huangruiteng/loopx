#!/usr/bin/env python3
"""Smoke-test the content-ops public-handle observation CLI."""

from __future__ import annotations

import json
import os
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
    CONTENT_OPS_PUBLIC_HANDLE_OBSERVATION_PACKET_SCHEMA_VERSION,
    CONTENT_OPS_PUBLIC_HANDLE_OBSERVATION_SCHEMA_VERSION,
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


def assert_observation_packet(payload: dict[str, Any], *, fetched: bool) -> None:
    assert payload["ok"] is True, payload
    assert (
        payload["schema_version"]
        == CONTENT_OPS_PUBLIC_HANDLE_OBSERVATION_PACKET_SCHEMA_VERSION
    ), payload
    assert payload["external_reads_performed"] is fetched, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["autopublish_allowed"] is False, payload
    assert payload["promotion_target"] == "source_item_v0", payload
    runtime_policy = payload["runtime_policy"]
    assert (
        runtime_policy["schema_version"]
        == CONTENT_OPS_CONNECTOR_RUNTIME_POLICY_SCHEMA_VERSION
    ), runtime_policy
    assert runtime_policy["safe_default"] == "head_only_metadata_probe", runtime_policy
    assert runtime_policy["browser_open_allowed_before_gate"] is False, runtime_policy
    assert "HEAD" in runtime_policy["allowed_probe_methods"], runtime_policy
    assert "media download" in runtime_policy["forbidden_before_approval"], runtime_policy

    source_item = payload["source_item"]
    assert source_item["schema_version"] == SOURCE_ITEM_SCHEMA_VERSION, source_item
    assert source_item["source_item_id"] == "source_x_openai_public_handle_fixture"
    assert source_item["source_kind"] == "x_public_profile_handle", source_item
    assert source_item["source_status"] == "public", source_item
    assert source_item["allowed_use"] == "metadata_only", source_item
    assert source_item["attribution"] == "x.com/OpenAI", source_item

    observation = payload["observation"]
    assert (
        observation["schema_version"]
        == CONTENT_OPS_PUBLIC_HANDLE_OBSERVATION_SCHEMA_VERSION
    ), observation
    assert observation["input_url"] == "https://x.com/OpenAI", observation
    assert observation["url_host"] == "x.com", observation
    assert observation["url_path"] == "/OpenAI", observation
    assert observation["content_bytes_read"] == 0, observation
    assert observation["external_write_performed"] is False, observation
    assert observation["login_used"] is False, observation
    assert observation["cookies_sent"] is False, observation
    assert observation["private_source_content_read"] is False, observation
    assert observation["autopublish_allowed"] is False, observation
    assert_public_safe(payload)


def main() -> int:
    result = run_cli(
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
    )
    payload = json.loads(result.stdout)
    assert_observation_packet(payload, fetched=False)
    assert payload["observation"]["http_method"] == "none", payload
    assert payload["observation"]["observation_status"] == "not_fetched", payload

    markdown = run_cli(
        [
            "content-ops",
            "observe-public-handle",
            "--url",
            "https://x.com/OpenAI",
            "--source-item-id",
            "source_x_openai_public_handle_fixture",
            "--no-fetch",
        ]
    ).stdout
    assert "LoopX Content-Ops Public Handle Observation" in markdown, markdown
    assert "external_writes_performed: `False`" in markdown, markdown
    assert "content_bytes_read: `0`" in markdown, markdown

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "observe-public-handle",
            "--url",
            "http://localhost/private",
            "--source-item-id",
            "source_bad_local",
            "--no-fetch",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "https URL" in rejected_payload["error"], rejected_payload

    if os.environ.get("LOOPX_LIVE_PUBLIC_HANDLE_SMOKE") == "1":
        live = run_cli(
            [
                "--format",
                "json",
                "content-ops",
                "observe-public-handle",
                "--url",
                "https://x.com/OpenAI",
                "--source-item-id",
                "source_x_openai_public_handle_fixture",
                "--timeout-seconds",
                "20",
            ]
        )
        live_payload = json.loads(live.stdout)
        assert_observation_packet(live_payload, fetched=True)
        assert live_payload["observation"]["http_method"] == "HEAD", live_payload
        assert isinstance(live_payload["observation"]["http_status"], int), live_payload

    print("content-ops-public-handle-observation-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
