#!/usr/bin/env python3
"""Smoke-test the agent_management_projection_v0 contract."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "docs/reference/protocols/agent-management-projection-v0.md"
PROTOCOL_INDEX_PATH = REPO_ROOT / "docs/reference/protocols/README.md"

PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def main() -> int:
    contract = read(CONTRACT_PATH)
    protocol_index = read(PROTOCOL_INDEX_PATH)

    assert_public_safe(contract, "contract")
    assert_public_safe(protocol_index, "protocol index")

    for needle in [
        "agent_management_projection_v0",
        "`todo_id` remains the",
        "read-only operator view",
        "does not introduce a runtime `task` object",
        '"mode": "read_only"',
        '"projection_is_writable": false',
        '"introduces_task_runtime": false',
        "not an automatic reclaim rule",
        "reuse_public_compatible_code_only",
        "copied code keeps required attribution or notice text",
        "dashboard consumers remain functional when the projection is absent",
        "top-level\n`agent_management_projection` key",
    ]:
        assert_contains(contract, needle, "contract")

    for forbidden in [
        "new `task_id`",
        "automatic dispatch",
        "workspace allocation runtime",
        "clear the claim, reassign work, or discard evidence",
    ]:
        assert_contains(contract, forbidden, "contract non-goals")

    assert_contains(protocol_index, "agent_management_projection_v0", "protocol index")
    print("agent-management-projection-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
