#!/usr/bin/env python3
"""Validate the Codex CLI TUI continuation scheduling contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "product" / "codex-cli-tui-continuation-priority.md"
PRODUCT_README = REPO_ROOT / "docs" / "product" / "README.md"
GETTING_STARTED = REPO_ROOT / "docs" / "guides" / "getting-started.md"


def normalize(text: str) -> str:
    return " ".join(text.split())


def assert_contract_doc() -> None:
    text = DOC.read_text(encoding="utf-8")
    normalized = normalize(text)

    must_have = (
        "Codex CLI TUI Continuation Priority",
        "Frontstage and showcase work are important support surfaces",
        "must not outrank a runnable Codex CLI TUI continuation task",
        "one pasted LoopX message starts the loop",
        "later steer or resume work through the same visible TUI",
        "Codex CLI TUI continuation wins over frontstage polish",
        "planning drift and run self-repair",
        "same_tui_continuation_proven",
        "same_tui_continuation_blocked",
        "same_tui_continuation_gated",
        "visible proof and runtime idle evidence",
        "must not read raw Codex transcripts, session files",
    )
    for phrase in must_have:
        assert phrase in normalized, phrase

    priority_index = normalized.index("Scheduling Rule")
    frontstage_index = normalized.index("frontstage or showcase support work")
    assert priority_index < frontstage_index, text


def assert_indexes() -> None:
    product = PRODUCT_README.read_text(encoding="utf-8")
    getting_started = GETTING_STARTED.read_text(encoding="utf-8")

    link = "codex-cli-tui-continuation-priority.md"
    assert link in product, product
    assert f"../product/{link}" in getting_started, getting_started
    assert "same-open-TUI continuation ahead of" in product, product
    assert "frontstage or showcase polish" in getting_started, getting_started


def main() -> int:
    assert_contract_doc()
    assert_indexes()
    print("codex-cli-tui-continuation-priority-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
