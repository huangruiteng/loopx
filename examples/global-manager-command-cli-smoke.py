#!/usr/bin/env python3
"""Smoke-test the public-safe `loopx global-summary` command."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATTERNS = [
    re.compile(r"/" + r"Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/" + r"private/"),
    re.compile(r"/tmp/"),
    re.compile(r"/var/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
]


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"global-summary payload leaked private pattern {pattern.pattern!r}")
    if "/loopx-summary-all" in text:
        raise AssertionError("global-summary payload should not expose the superseded /loopx-summary-all alias")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-global-summary-smoke-") as tmp:
        root = Path(tmp)
        runtime = root / "runtime"
        registry = root / "registry.global.json"
        registry.write_text(
            json.dumps(
                {
                    "common_runtime_root": str(runtime),
                    "goals": [
                        {
                            "id": "smoke-goal",
                            "objective": "Smoke global summary.",
                            "domain": "loopx-smoke",
                            "status": "active",
                            "adapter": {"kind": "read_only_project_map_v0", "status": "connected-read-only"},
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runs = runtime / "goals" / "smoke-goal" / "runs"
        runs.mkdir(parents=True)
        runs.joinpath("index.jsonl").write_text(
            json.dumps(
                {
                    "generated_at": "2026-06-26T00:00:00+00:00",
                    "classification": "smoke_progress",
                    "recommended_action": "Continue the next public-safe smoke step.",
                    "json_exists": True,
                    "markdown_exists": True,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "global-summary",
                "--limit",
                "5",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "global_manager_command_response_v0", payload
    request = payload["request"]
    assert request["command"] == "/loopx-global-summary", request
    assert "/loop-global-summary" in request["legacy_aliases"], request
    assert request["cli_command"] == "loopx global-summary", request
    assert request["privacy_mode"] == "public_safe_summary", request
    assert request["dry_run"] is True, request
    assert payload["boundary"]["absolute_paths_recorded"] is False, payload["boundary"]
    assert "groups" in payload and "recent_progress" in payload["groups"], payload
    assert_public_safe(payload)

    print("global-manager-command-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
