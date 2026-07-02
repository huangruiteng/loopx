#!/usr/bin/env python3
"""Smoke-check the reusable multi-agent product recipe documentation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "docs" / "guides" / "multi-agent-product-recipe.md"
DOCS_INDEX = ROOT / "docs" / "README.md"
AUTO_RESEARCH_GUIDE = ROOT / "docs" / "guides" / "auto-research-command-path.md"


PRIVATE_MARKERS = [
    "byte" + "dance",
    "lark" + "office",
    "fei" + "shu.cn",
    "/" + "Users" + "/",
    "/" + "private" + "/",
    "/" + "tmp" + "/",
    "api" + "_key",
    "pass" + "word",
    "sec" + "ret",
]


def read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def require(text: str, snippets: list[str], *, source: Path) -> None:
    compact = " ".join(text.split())
    missing = [
        snippet for snippet in snippets if snippet not in text and " ".join(snippet.split()) not in compact
    ]
    assert not missing, f"{source}: missing {missing}"


def assert_public_safe(text: str, label: str) -> None:
    lower = text.lower()
    leaked = [marker for marker in PRIVATE_MARKERS if marker.lower() in lower]
    assert not leaked, f"{label} leaks private markers: {leaked}"


def main() -> int:
    recipe = read(RECIPE)
    docs_index = read(DOCS_INDEX)
    auto_research_guide = read(AUTO_RESEARCH_GUIDE)

    assert_public_safe(recipe, "multi-agent product recipe")
    require(
        recipe,
        [
            "# Multi-Agent Product Recipe",
            "User layer",
            "Product preset",
            "Multi-agent kernel",
            "It is not enough to make the user command\nshort if the auto-research preset becomes a second runner",
            "Both the user layer\nand the product preset must stay thin",
            "role list",
            "agent scope",
            "worker-local skill snippet",
            "handoff/todo hints",
            "One-Command Launch",
            "Attach, Stop, Retry",
            "loopx multi-agent launch",
            "loopx auto-research demo-e2e",
            "real interactive Codex CLI TUI panes",
            "first action is the pane-local A2A tick",
            "machine JSON is written to public artifacts",
            "todos and evidence are the only handoff authority",
            "Auto-research should stay a reference preset, not the kernel",
            "implement it in the\nmulti-agent kernel first",
        ],
        source=RECIPE,
    )
    require(
        docs_index,
        [
            "Multi-agent product recipe",
            "guides/multi-agent-product-recipe.md",
        ],
        source=DOCS_INDEX,
    )
    require(
        auto_research_guide,
        [
            "Multi-agent product recipe",
            "multi-agent-product-recipe.md",
            "copy the pattern without copying auto-research code",
        ],
        source=AUTO_RESEARCH_GUIDE,
    )

    forbidden = [
        "auto-research owns the runner",
        "preset owns tmux",
        "hidden workflow engine",
        "raw JSON should be visible first",
    ]
    for phrase in forbidden:
        assert phrase not in recipe, f"forbidden phrase present: {phrase}"

    print("multi-agent-product-recipe-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
