#!/usr/bin/env python3
"""Validate the public README and cross-runtime demo surface."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def compact(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    readme = read("README.md")
    demo = read("docs/product/cross-runtime-impl-review-demo.md")
    product_index = read("docs/product/README.md")
    compact_readme = compact(readme)
    compact_demo = compact(demo)

    for required in [
        '<div align="center">',
        "docs/assets/loopx-social-preview.png",
        "LoopX loop engineering social preview banner",
        "Loop engineering for long-running AI agents.",
        "Manage Codex, Claude Code, Cursor, and other agent runtimes",
        "## How It Works",
        "goal / issue / project",
        "LoopX state: objective + gates + todos + scope + evidence + quota",
        "Pick the surface you already use:",
        "Codex App",
        "Codex CLI",
        "Claude Code",
        "Manual shell / other agents",
        "Candidate: Claude implements + Codex reviews",
        "docs/product/cross-runtime-impl-review-demo.md",
    ]:
        assert required in readme, required

    first_screen = readme.split("## How It Works", 1)[0]
    assert "docs/assets/loopx-logo.png" not in first_screen

    for required in [
        "`/loopx <implementation goal>`",
        "`loopx todo claim`",
        "`loopx review-packet`",
    ]:
        assert required in compact_readme, required

    for required in [
        "# Cross-Runtime Implement/Review Demo",
        "Claude Code owns an implementation todo",
        "Codex owns a review todo",
        "LoopX owns todo claims, gates, evidence, quota, and the next handoff",
        "loopx todo add --goal-id <goal> --role agent",
        "loopx --format json quota should-run --goal-id <goal> --agent-id claude-code-impl",
        "loopx review-packet --goal-id <goal>",
        "Review Verdict Contract",
        "Forbidden evidence",
        "raw Claude or Codex transcripts",
    ]:
        assert required in demo, required

    for required in [
        "verdict",
        "blockers",
        "suggestions",
        "verifier",
        "handoff",
        "docs plus fixture validation",
    ]:
        assert required in compact_demo, required

    assert "Cross-runtime implement/review demo" in product_index
    assert "cross-runtime-impl-review-demo.md" in product_index

    print("readme-demo-surface-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
