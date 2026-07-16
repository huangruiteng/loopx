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
        "loopx_turn_v0",
        "loopx turn plan",
        "loopx turn run-once",
        "interactive-visible",
        "isolated-headless",
        "must never switch",
        "independent validation",
        "durable writeback",
        "quota",
        "scheduler state",
        "generic-cli",
        "typed candidate result",
    ]
    for phrase in required_contracts:
        assert phrase in doc, phrase

    boundary_terms = [
        "Raw host material stays outside LoopX state",
        "raw task text",
        "raw trajectories",
        "credentials",
        "local artifact paths",
    ]
    for phrase in boundary_terms:
        assert phrase in doc, phrase

    unfinished_boundaries = [
        "interactive-visible` still needs",
        "Trae still needs a thin adapter",
        "recurring external scheduling must compose",
        "benchmark promotion still requires",
    ]
    for phrase in unfinished_boundaries:
        assert phrase in doc, phrase

    assert "codex-cli-automation-driver.md" in index, "product index link"

    print("codex-cli-automation-driver-audit-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
