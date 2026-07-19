#!/usr/bin/env python3
"""Validate the public README and cross-runtime demo surface."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


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
        "Loop engineering for long-running AI agents and peer agent teams.",
        "A lightweight state kernel and agent-agnostic local control plane for",
        "Codex, Claude Code, Cursor, and other runtimes: objectives, gates, todos,",
        "## How It Works",
        "objective / issue / project",
        "LoopX state: objective + gates + todos + scope + evidence + quota",
        "Start agent-first: paste one setup message for the surface you already use",
        "Choose your surface:",
        "Codex App",
        "Codex CLI",
        "Claude Code",
        "Manual shell / other agents",
        "Candidate: Claude implements + Codex reviews",
        "docs/product/cross-runtime-impl-review-demo.md",
        "## Optional Capabilities",
        "docs/assets/long-running-loop-openviking-trajectory.png",
        "docs/assets/long-running-loop-ml-experiment-trajectory.png",
        "### Start With A Useful Loop",
        "### Auto Research One-Click Start",
        "### Review Agent Work",
        "### Long-Running Agent App Paths",
    ]:
        assert required in readme, required

    first_screen = readme.split("## How It Works", 1)[0]
    assert "docs/assets/loopx-logo.png" not in first_screen

    for required in [
        "`$loopx <complex task>`",
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
        "loopx demo impl-review --preset claude-codex --dry-run",
        "loopx --format json quota should-run --goal-id <goal> --agent-id claude-code-impl",
        "loopx review-packet --goal-id <goal>",
        "cross_runtime_impl_review_demo_packet_v0",
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
