#!/usr/bin/env python3
"""Smoke-test the value connector starter CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.value_connectors.github_public import (  # noqa: E402
    GITHUB_PUBLIC_CHANNEL_PROBE_PACKET_SCHEMA_VERSION,
    GITHUB_PUBLIC_REPLY_MONITOR_PACKET_SCHEMA_VERSION,
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
        "comment body that must stay gated",
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


def run_cli(
    args: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        env=env,
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

    reply_provider = {
        "comments": [
            {
                "author": "loopx-operator",
                "author_association": "NONE",
                "created_at": "2026-06-25T06:54:50Z",
                "updated_at": "2026-06-25T06:54:50Z",
                "url": "https://github.com/huangruiteng/loopx/issues/670#issuecomment-1",
                "body": "comment body that must stay gated",
                "raw": "raw provider payload",
            },
            {
                "author": "maintainer-one",
                "author_association": "MEMBER",
                "created_at": "2026-06-25T07:10:00Z",
                "updated_at": "2026-06-25T07:10:00Z",
                "url": "https://github.com/huangruiteng/loopx/issues/670#issuecomment-2",
                "body": "comment body text",
            },
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        reply_path = Path(tmpdir) / "reply-comments.json"
        reply_path.write_text(json.dumps(reply_provider), encoding="utf-8")
        reply_monitor = json.loads(
            run_cli(
                [
                    "--format",
                    "json",
                    "value-connectors",
                    "github-reply-monitor",
                    "--issue-url",
                    "https://github.com/huangruiteng/loopx/issues/670",
                    "--after-comment-url",
                    "https://github.com/huangruiteng/loopx/issues/670#issuecomment-1",
                    "--metadata-json",
                    str(reply_path),
                ]
            ).stdout
        )
    assert reply_monitor["ok"] is True, reply_monitor
    assert reply_monitor["schema_version"] == GITHUB_PUBLIC_REPLY_MONITOR_PACKET_SCHEMA_VERSION
    assert reply_monitor["external_reads_performed"] is False, reply_monitor
    assert reply_monitor["external_writes_performed"] is False, reply_monitor
    assert reply_monitor["comment_bodies_captured"] is False, reply_monitor
    assert reply_monitor["raw_provider_payload_captured"] is False, reply_monitor
    assert reply_monitor["maintainer_reply_count"] == 1, reply_monitor
    assert reply_monitor["money_signal"] == "public_maintainer_interest", reply_monitor
    assert reply_monitor["recommended_action"] == "prepare_public_triage_note", reply_monitor
    assert reply_monitor["validation"]["gated_provider_field_count"] == 3, reply_monitor
    assert_public_safe(reply_monitor)

    with tempfile.TemporaryDirectory() as tmpdir:
        fake_bin = Path(tmpdir)
        gh = fake_bin / "gh"
        gh.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json",
                    "import sys",
                    "argv = sys.argv[1:]",
                    "assert argv[:2] == ['api', '-H'], argv",
                    "assert 'repos/huangruiteng/loopx/issues/670/comments?per_page=100' in argv, argv",
                    "assert '--jq' in argv, argv",
                    "json.dump([",
                    "  {",
                    "    'author': 'loopx-operator',",
                    "    'author_association': 'NONE',",
                    "    'created_at': '2026-06-25T06:54:50Z',",
                    "    'updated_at': '2026-06-25T06:54:50Z',",
                    "    'url': 'https://github.com/huangruiteng/loopx/issues/670#issuecomment-1',",
                    "  }",
                    "], sys.stdout)",
                    "sys.stdout.write('\\n')",
                ]
            ),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        live_env = {**os.environ, "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"}
        live_reply_monitor = json.loads(
            run_cli(
                [
                    "--format",
                    "json",
                    "value-connectors",
                    "github-reply-monitor",
                    "--issue-url",
                    "https://github.com/huangruiteng/loopx/issues/670",
                    "--after-comment-url",
                    "https://github.com/huangruiteng/loopx/issues/670#issuecomment-1",
                    "--fetch-metadata",
                ],
                env=live_env,
            ).stdout
        )
    assert live_reply_monitor["ok"] is True, live_reply_monitor
    assert live_reply_monitor["external_reads_performed"] is True, live_reply_monitor
    assert live_reply_monitor["external_writes_performed"] is False, live_reply_monitor
    assert live_reply_monitor["maintainer_reply_count"] == 0, live_reply_monitor
    assert live_reply_monitor["recommended_action"] == "wait_no_bump", live_reply_monitor
    assert live_reply_monitor["comment_bodies_captured"] is False, live_reply_monitor
    assert live_reply_monitor["validation"]["anchor_found"] is True, live_reply_monitor
    assert_public_safe(live_reply_monitor)

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

    rejected_reply = run_cli(
        [
            "--format",
            "json",
            "value-connectors",
            "github-reply-monitor",
            "--issue-url",
            "https://github.com/owner/repo/issues/1",
            "--after-comment-url",
            "https://github.com/owner/repo/issues/1#issuecomment-1?x=sensitive-value",
        ],
        check=False,
    )
    assert rejected_reply.returncode == 1, rejected_reply
    rejected_reply_payload = json.loads(rejected_reply.stdout)
    assert rejected_reply_payload["ok"] is False, rejected_reply_payload
    assert rejected_reply_payload["schema_version"] == "github_public_reply_monitor_error_v0"

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

    reply_markdown = run_cli(
        [
            "value-connectors",
            "github-reply-monitor",
            "--issue-url",
            "https://github.com/huangruiteng/loopx/issues/670",
            "--after-comment-url",
            "https://github.com/huangruiteng/loopx/issues/670#issuecomment-1",
        ]
    ).stdout
    assert "LoopX GitHub Public Reply Monitor" in reply_markdown, reply_markdown
    assert "recommended_action: `wait_no_bump`" in reply_markdown, reply_markdown
    assert_public_safe(reply_markdown)

    print("value-connectors-github-public-probe-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
