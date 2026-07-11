#!/usr/bin/env python3
"""Smoke-test bounded, public-safe issue-fix JSON CLI inputs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "synthetic-payload-must-not-be-echoed"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.cli import (  # noqa: E402
    _MAX_INLINE_JSON_CHARS,
    _load_json_object,
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    inline = json.dumps(
        {
            "number": 123,
            "state": "open",
            "title": "Synthetic issue metadata",
            "labels": [{"name": "bug"}],
        }
    )
    accepted = run_cli(
        "issue-fix",
        "workflow-plan",
        "--url",
        "https://github.com/example/project/issues/123",
        "--metadata-json",
        inline,
    )
    assert accepted.returncode == 0, accepted.stdout
    accepted_payload = json.loads(accepted.stdout)
    assert accepted_payload["ok"] is True, accepted_payload
    assert accepted_payload["external_writes_performed"] is False, accepted_payload

    malformed = '{"title":"' + SENTINEL + "-" + ("x" * 5000)
    rejected = run_cli(
        "issue-fix",
        "workflow-plan",
        "--url",
        "https://github.com/example/project/issues/123",
        "--metadata-json",
        malformed,
    )
    assert rejected.returncode != 0, rejected.stdout
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload == {
        "ok": False,
        "mode": "issue-fix",
        "error": "JSON input is invalid",
    }, rejected_payload
    combined_output = rejected.stdout + rejected.stderr
    assert SENTINEL not in combined_output, combined_output
    assert "File name too long" not in combined_output, combined_output

    oversized = '{"value":"' + ("x" * _MAX_INLINE_JSON_CHARS) + '"}'
    try:
        _load_json_object(oversized)
    except ValueError as exc:
        assert str(exc) == "inline JSON input exceeds the 1 MiB limit", exc
    else:
        raise AssertionError("oversized inline JSON should be rejected")

    missing = run_cli(
        "issue-fix",
        "workflow-plan",
        "--url",
        "https://github.com/example/project/issues/123",
        "--metadata-json",
        "missing-synthetic-metadata.json",
    )
    assert missing.returncode != 0, missing.stdout
    missing_payload = json.loads(missing.stdout)
    assert missing_payload["error"] == "could not read JSON input file", missing_payload
    assert "missing-synthetic-metadata.json" not in missing.stdout, missing.stdout

    help_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "issue-fix",
            "reviewer-request",
            "--help",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    normalized_help = " ".join(help_result.stdout.split())
    assert "inline JSON object, file path" in normalized_help, help_result.stdout

    print("issue-fix-json-input-boundary-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
