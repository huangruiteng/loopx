#!/usr/bin/env python3
"""Validate the GitHub Actions full-public smoke workflow contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "full-public-smokes.yml"


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")

    for required in [
        "name: Full Public Smokes",
        "workflow_dispatch:",
        "schedule:",
        "push:",
        "branches:",
        "- main",
        "permissions:",
        "contents: read",
        "fail-fast: false",
        "timeout-minutes: 120",
        "actions/setup-python@v5",
        "python-version: \"3.11\"",
        "python3 examples/run-smokes.py",
        "--suite full-public",
        "--offset \"${{ matrix.offset }}\"",
        "--limit \"${SHARD_LIMIT}\"",
        "--timeout-seconds \"${SMOKE_TIMEOUT_SECONDS}\"",
        "SMOKE_JOBS: \"4\"",
        "--jobs \"${SMOKE_JOBS}\"",
        "--no-execute",
        "--json",
        "actions/upload-artifact@v4",
        "smoke-results/full-public-shard-${{ matrix.shard }}.json",
    ]:
        assert required in text, required

    assert "pull_request:" not in text
    assert "contents: write" not in text
    assert "pull-requests: write" not in text
    assert "sec" + "rets." not in text

    for shard, offset in enumerate(range(0, 600, 100)):
        assert f"shard: {shard}" in text, shard
        assert f"offset: {offset}" in text, offset

    print("full-public-smokes-workflow-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
