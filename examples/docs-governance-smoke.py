#!/usr/bin/env python3
"""Smoke-test the public docs information architecture."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"


MOVED_PATHS = {
    "docs/commit-readiness-manifest-20260603.md": (
        "docs/archive/release-readiness/commit-readiness-manifest-20260603.md"
    ),
    "docs/commit-readiness-manifest-20260606.md": (
        "docs/archive/release-readiness/commit-readiness-manifest-20260606.md"
    ),
    "docs/outcome-floor-safe-bypass-incident-20260606.md": (
        "docs/archive/incidents/outcome-floor-safe-bypass-incident-20260606.md"
    ),
    "docs/public-launch-narrative-draft.md": (
        "docs/outreach/public-launch-narrative-draft.md"
    ),
    "docs/xiaohongshu-launch-draft.md": (
        "docs/outreach/xiaohongshu-launch-draft.md"
    ),
    "docs/protocol-action-packet-codex-cli-wrapper-v0.md": (
        "docs/reference/protocols/protocol-action-packet-codex-cli-wrapper-v0.md"
    ),
    "docs/protocol-action-packet-decision-v0.md": (
        "docs/reference/protocols/protocol-action-packet-decision-v0.md"
    ),
    "docs/protocol-action-packet-router-comparison-v0.md": (
        "docs/reference/protocols/protocol-action-packet-router-comparison-v0.md"
    ),
    "docs/codex-cli-long-run-benchmark-design.md": (
        "docs/research/long-horizon-agent-benchmarks/"
        "codex-cli-long-run-benchmark-design.md"
    ),
    "docs/codex-cli-long-run-regression.md": (
        "docs/research/long-horizon-agent-benchmarks/"
        "codex-cli-long-run-regression.md"
    ),
}


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def compact(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    docs_index = read("docs/README.md")
    auto_research_command_path = read("docs/guides/auto-research-command-path.md")
    codex_cli_tui_loop = read("docs/product/codex-cli-tui-loop.md")
    project_agent_contract = read("docs/project-agent-todo-contract.md")
    status_contract = read("docs/status-data-contract.md")
    compact_auto_research_command_path = compact(auto_research_command_path)
    compact_codex_cli_tui_loop = compact(codex_cli_tui_loop)
    compact_project_agent_contract = compact(project_agent_contract)
    compact_status_contract = compact(status_contract)

    for required in [
        "## Start Here",
        "## Stable Reference",
        "## Governance Rules",
        "docs/research/",
        "docs/archive/",
        "docs/outreach/",
        "docs/product/",
        "docs/reference/",
        "docs/showcases/",
        "product/codex-cli-tui-loop.md",
        "guides/auto-research-command-path.md",
        "guides/multi-agent-product-recipe.md",
    ]:
        assert required in docs_index, required

    for path in [
        "docs/archive/README.md",
        "docs/archive/incidents/README.md",
        "docs/archive/release-readiness/README.md",
        "docs/outreach/README.md",
        "docs/product/README.md",
        "docs/guides/auto-research-command-path.md",
        "docs/guides/multi-agent-product-recipe.md",
        "docs/reference/README.md",
        "docs/reference/protocols/README.md",
        "docs/research/long-horizon-agent-benchmarks/README.md",
        "docs/showcases/README.md",
        "docs/product/codex-cli-tui-loop.md",
    ]:
        assert (REPO_ROOT / path).is_file(), path

    root_markdown = sorted(DOCS.glob("*.md"))
    assert len(root_markdown) <= 30, [path.name for path in root_markdown]

    for old_path, new_path in MOVED_PATHS.items():
        assert not (REPO_ROOT / old_path).exists(), old_path
        assert (REPO_ROOT / new_path).is_file(), new_path

    combined_public_indexes = "\n".join(
        [
            read("README.md"),
            read("CONTRIBUTOR_TASKS.md"),
            read("docs/README.md"),
            read("docs/archive/README.md"),
            read("docs/outreach/README.md"),
            read("docs/product/README.md"),
            read("docs/reference/protocols/README.md"),
            read("docs/research/long-horizon-agent-benchmarks/README.md"),
            read("docs/showcases/README.md"),
        ]
    )
    for old_path in MOVED_PATHS:
        assert old_path not in combined_public_indexes, old_path
    for new_path in MOVED_PATHS.values():
        basename = Path(new_path).name
        assert (
            new_path in combined_public_indexes
            or basename in combined_public_indexes
            or new_path.startswith("docs/archive/")
        ), new_path

    for required in [
        "Do not append a follow-up goal-level `surface_only` sync",
        "--delivery-outcome outcome_progress",
    ]:
        assert required in compact_project_agent_contract, required

    for required in [
        "The best first-run experience is one TUI setup message",
        "Session-Attached Automation",
        "Headless Disabled Boundary",
    ]:
        assert required in compact_codex_cli_tui_loop, required

    for required in [
        "A later `surface_only` project-level sync will become the latest non-agent-lane run",
        "agent_lane_recommendation",
    ]:
        assert required in compact_status_contract, required

    for required in [
        "Start From A Clean Workspace",
        "loopx-auto-research-demo",
        "auto-research demo-e2e",
        "auto-research demo-supervisor",
        "auto-research worker-loop",
        "research-curator",
        "hypothesis-proposer",
        "research-executor",
        "evaluator-promoter",
        "tmux attach -t loopx-auto-research",
        "tmux kill-session -t loopx-auto-research",
        "not a leader agent",
    ]:
        assert required in compact_auto_research_command_path, required

    multi_agent_product_recipe = read("docs/guides/multi-agent-product-recipe.md")
    compact_multi_agent_product_recipe = compact(multi_agent_product_recipe)
    for required in [
        "Multi-Agent Product Recipe",
        "Product preset",
        "Multi-agent kernel",
        "role list",
        "agent scope",
        "worker-local skill snippet",
        "handoff/todo hints",
        "One-Command Launch",
        "Attach, Stop, Retry",
        "Auto-research should stay a reference preset, not the kernel",
    ]:
        assert required in compact_multi_agent_product_recipe, required

    print("docs-governance-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
