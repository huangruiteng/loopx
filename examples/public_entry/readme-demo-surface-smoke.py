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
    readme_zh = read("README.zh-CN.md")
    demo = read("docs/product/use-cases/cross-runtime/cross-runtime-impl-review-demo.md")
    product_index = read("docs/product/README.md")
    cross_runtime_index = read("docs/product/use-cases/cross-runtime/README.md")
    getting_started = read("docs/guides/getting-started.md")
    compact_readme = compact(readme)
    compact_readme_zh = "".join(readme_zh.split())
    compact_demo = compact(demo)
    auto_research = readme.split("### Auto Research", 1)[1].split(
        "### Used In Real Projects", 1
    )[0]
    auto_research_zh = readme_zh.split("### Auto Research", 1)[1].split(
        "### 真实项目中的使用", 1
    )[0]

    for required in [
        '<div align="center">',
        "docs/assets/loopx-social-preview.png",
        "LoopX loop engineering social preview banner",
        "Loop engineering for long-horizon AI agents and peer agent teams.",
        "The open, provider-neutral, stateful control plane for long-horizon agents.",
        "preserves objectives, gates, todos, evidence, quota, and handoffs across turns",
        "## Why LoopX",
        "objective / issue / project",
        "LoopX state: objective + gates + todos + scope + evidence + quota",
        "## Try LoopX",
        "### Start From Your Agent",
        "Codex App",
        "Codex CLI",
        "Claude Code",
        "Cursor, shell, or custom runner",
        "Claude implements and Codex reviews",
        "docs/product/use-cases/cross-runtime/cross-runtime-impl-review-demo.md",
        "## Advanced Paths",
        "200+ hours of elapsed loop lifetime",
        "200+ hour public contribution arc",
        "Redacted owner-run showcase",
        "not continuous model execution or unattended production autonomy",
        "docs/assets/long-running-loop-openviking-trajectory.png",
        "docs/assets/long-running-loop-ml-experiment-trajectory.png",
        "### Presets and Auto Research",
        "### Review Agent Work",
        "### App and Projection Paths",
        '<a id="how-it-works"></a>',
        '<a id="quick-start"></a>',
        '<a id="see-it-in-action"></a>',
        '<a id="capability-surface"></a>',
        '<a id="community--feedback"></a>',
        "LoopX 1.0 is a usable local control plane",
        "docs/assets/loopx-lark-developer-group.png",
        "docs/assets/loopx-wechat-contact.png",
        "WeChat: <code>huangrt00</code>",
        "loopx configure-goal --goal-id <goal-id>",
        "loopx preset show daily-triage",
    ]:
        assert required in readme, required

    for required in [
        '<a id="快速开始"></a>',
        '<a id="看几个例子"></a>',
        "200+ 小时自然时长",
        "超过 200 小时的公开贡献轨迹",
        "经过脱敏的 owner-run showcase",
        "LoopX 1.0 已经是一套可用的长程 Agent 本地控制面",
        "docs/assets/loopx-lark-developer-group.png",
        "docs/assets/loopx-wechat-contact.png",
        "微信：<code>huangrt00</code>",
        "loopx configure-goal --goal-id <goal-id>",
        "loopx preset show daily-triage",
    ]:
        assert required in readme_zh, required

    first_screen = readme.split("## Why LoopX", 1)[0]
    assert "docs/assets/loopx-logo.png" not in first_screen

    for required in [
        "company or employer endorsement",
        "independent reproduction",
    ]:
        assert required in compact_readme, required
    for required in [
        "不是连续模型执行时长或无人值守的生产自治",
        "公司或雇主背书",
        "第三方独立复现",
    ]:
        assert required.replace(" ", "") in compact_readme_zh, required

    for required in [
        "Reproducible public KNN demo",
        "deterministic CPU evaluator",
        "docs/product/use-cases/auto-research/decentralized-auto-research-showcase.md",
    ]:
        assert required in auto_research, required
    assert "redacted" not in auto_research.lower()

    for required in [
        "可复现的公开 KNN demo",
        "deterministic CPU evaluator",
        "docs/product/use-cases/auto-research/decentralized-auto-research-showcase.md",
    ]:
        assert required in auto_research_zh, required
    assert "脱敏" not in auto_research_zh

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

    assert "use-cases/README.md" in product_index
    assert "cross-runtime-impl-review-demo.md" in cross_runtime_index
    assert "### Recover History Index Collisions" in getting_started
    assert "history rebuild-index-collisions" in getting_started
    assert "--review-plan-json reviewed-plan.json" in getting_started

    print("readme-demo-surface-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
