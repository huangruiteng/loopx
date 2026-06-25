#!/usr/bin/env python3
"""Smoke-test the value connector starter CLI."""

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

from loopx.capabilities.value_connectors.github_public import (  # noqa: E402
    GITHUB_PUBLIC_CHANNEL_PROBE_PACKET_SCHEMA_VERSION,
    VALUE_CONNECTOR_INSTALL_CHECK_PACKET_SCHEMA_VERSION,
)
from loopx.capabilities.value_connectors.planner import (  # noqa: E402
    VALUE_CONNECTOR_PLAN_PACKET_SCHEMA_VERSION,
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
    "raw provider payload",
    "comment body text",
    "issue body text",
    "restricted-value",
    "sensitive-value",
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


def main() -> int:
    install = json.loads(
        run_cli(["--format", "json", "value-connectors", "install-check"]).stdout
    )
    assert install["ok"] is True, install
    assert install["schema_version"] == VALUE_CONNECTOR_INSTALL_CHECK_PACKET_SCHEMA_VERSION
    connector_ids = {item["connector_id"] for item in install["checks"]}
    assert "github_public_channel" in connector_ids, connector_ids
    assert "botmail_identity" in connector_ids, connector_ids
    assert_public_safe(install)

    probe = json.loads(
        run_cli(
            [
                "--format",
                "json",
                "value-connectors",
                "github-public-probe",
                "--url",
                "https://github.com/huangruiteng/loopx/issues/670",
            ]
        ).stdout
    )
    assert probe["ok"] is True, probe
    assert probe["schema_version"] == GITHUB_PUBLIC_CHANNEL_PROBE_PACKET_SCHEMA_VERSION
    assert probe["external_reads_performed"] is False, probe
    assert probe["external_writes_performed"] is False, probe
    assert probe["raw_body_captured"] is False, probe
    assert probe["comment_bodies_captured"] is False, probe
    assert probe["metadata"] is None, probe
    assert probe["connector_call"]["money_metric"], probe
    assert_public_safe(probe)

    plan = json.loads(
        run_cli(["--format", "json", "value-connectors", "plan"]).stdout
    )
    assert plan["ok"] is True, plan
    assert plan["schema_version"] == VALUE_CONNECTOR_PLAN_PACKET_SCHEMA_VERSION
    assert plan["external_writes_performed"] is False, plan
    assert plan["validation"]["ok"] is True, plan["validation"]
    assert plan["projection"]["first_screen"]["gated_call_count"] == 2, plan
    assert "github_issue_intake" in plan["projection"]["safe_prepare_calls"], plan
    assert_public_safe(plan)

    gated = json.loads(
        run_cli(
            [
                "--format",
                "json",
                "value-connectors",
                "plan",
                "--connector-id",
                "community_channel",
                "--connector-kind",
                "community_channel",
                "--channel",
                "public community thread",
                "--stage",
                "external_write_request",
                "--target-ref",
                "thread asking about agent workflow operations",
                "--external-write-requested",
                "--money-metric",
                "qualified workflow owner asks for a LoopX audit",
                "--success-metric",
                "one audit or demo request",
                "--kill-condition",
                "channel rules reject the reply or no workflow owner appears",
            ]
        ).stdout
    )
    assert gated["ok"] is True, gated
    call = gated["plan"]["connector_calls"][0]
    assert call["external_write_requested"] is True, call
    assert call["external_writes_allowed"] is False, call
    assert call["requires_user_approval"] is True, call
    assert gated["projection"]["first_screen"]["waiting_on"] == "user", gated
    assert_public_safe(gated)

    rejected = run_cli(
        [
            "--format",
            "json",
            "value-connectors",
            "github-public-probe",
            "--url",
            "https://github.com/owner/repo/issues/1?x=sensitive-value",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert rejected_payload["schema_version"] == "github_public_channel_probe_error_v0", rejected_payload
    assert "query or fragment" in rejected_payload["error"], rejected_payload

    rejected_markdown = run_cli(
        [
            "value-connectors",
            "github-public-probe",
            "--url",
            "https://github.com/owner/repo/issues/1?x=sensitive-value",
        ],
        check=False,
    )
    assert rejected_markdown.returncode == 1, rejected_markdown
    assert "LoopX GitHub Public Channel Probe" in rejected_markdown.stdout, rejected_markdown.stdout
    assert "LoopX Value Connector Plan" not in rejected_markdown.stdout, rejected_markdown.stdout

    markdown = run_cli(
        [
            "value-connectors",
            "github-public-probe",
            "--url",
            "https://github.com/huangruiteng/loopx/issues/670",
        ]
    ).stdout
    assert "LoopX GitHub Public Channel Probe" in markdown, markdown
    assert "external_writes_performed: `False`" in markdown, markdown
    assert_public_safe(markdown)

    print("value-connectors-github-public-probe-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
