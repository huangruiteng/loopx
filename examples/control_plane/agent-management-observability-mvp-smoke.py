#!/usr/bin/env python3
"""Smoke-test the Agent Management Observability MVP note."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs/product/agent-management-observability-mvp.md"
PRODUCT_INDEX_PATH = REPO_ROOT / "docs/product/README.md"

PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
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
    doc = read(DOC_PATH)
    product_index = read(PRODUCT_INDEX_PATH)

    assert_public_safe(doc, "mvp doc")
    assert_public_safe(product_index, "product index")

    for needle in [
        "Use the mature agent-console direction",
        "does not copy Hermes source code",
        "LoopX already has the durable work unit: `todo_id` inside `goal_id`.",
        "The MVP must not expose:",
        "claim/reclaim",
        "dispatch",
        "stale claim is a warning only",
        "agent_management_projection_v0",
        "export-agent-management-status-example.py",
        "does not invent workspace or handoff fields",
        "license/attribution note",
    ]:
        assert_contains(doc, needle, "mvp doc")

    for url in [
        "https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/kanban.md",
        "https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/delegation.md",
        "https://github.com/NousResearch/hermes-agent/blob/main/LICENSE",
    ]:
        assert_contains(doc, url, "source links")

    assert_contains(
        product_index,
        "Agent management observability MVP",
        "product index",
    )

    print("agent-management-observability-mvp-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
