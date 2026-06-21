#!/usr/bin/env python3
"""Smoke-test the public Codex CLI automation driver audit contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs/product/codex-cli-automation-driver.md"
PRODUCT_INDEX = REPO_ROOT / "docs/product/README.md"


def main() -> int:
    doc = DOC.read_text()
    index = PRODUCT_INDEX.read_text()

    required_contracts = [
        "one Goal-Harness-generated message",
        "does not expose a mature native recurring scheduler",
        "recurrence as a LoopX local-driver concern",
        "codex resume [SESSION_ID] [PROMPT]",
        "codex exec",
        "remote-control",
        "loopx codex-cli-visible-driver-plan",
        "loopx codex-cli-exec-handoff",
        "TUI bootstrap primary",
        "headless-disabled boundary",
        "idle guard",
        "validated writeback",
    ]
    for phrase in required_contracts:
        assert phrase in doc, phrase

    boundary_terms = [
        "raw Codex transcripts",
        "credentials",
        "hidden session files",
    ]
    for phrase in boundary_terms:
        assert phrase in doc, phrase

    assert "codex-cli-automation-driver.md" in index, "product index link"

    print("codex-cli-automation-driver-audit-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
