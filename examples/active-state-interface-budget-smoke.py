#!/usr/bin/env python3
"""Smoke-test that live active-state handoffs stay compact."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILES = (
    REPO_ROOT / "examples" / "active-goal-state.example.md",
    REPO_ROOT / "goals" / "goal-harness-meta" / "ACTIVE_GOAL_STATE.md",
)
NEXT_ACTION_MAX_LINES = 4
NEXT_ACTION_MAX_CHARS = 360
HISTORY_MARKERS = (
    "This turn",
    "Validation:",
    "Critic:",
    "Recent Progress",
    "Progress Ledger",
    "monitor is complete",
    "pushed to",
)


def section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    in_section = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line[3:].strip() == heading
            continue
        if in_section and line.strip():
            collected.append(line.strip())
    return collected


def compact_action(lines: list[str]) -> str:
    parts: list[str] = []
    for line in lines:
        cleaned = line
        if cleaned.startswith("- "):
            cleaned = cleaned[2:]
        elif cleaned.startswith("* "):
            cleaned = cleaned[2:]
        parts.append(cleaned.strip())
    return " ".join(part for part in parts if part)


def assert_next_action_budget(path: Path) -> None:
    lines = section_lines(path.read_text(encoding="utf-8"), "Next Action")
    assert lines, f"{path.relative_to(REPO_ROOT)} has no Next Action"
    action = compact_action(lines)
    assert len(lines) <= NEXT_ACTION_MAX_LINES, (
        path.relative_to(REPO_ROOT),
        len(lines),
        NEXT_ACTION_MAX_LINES,
    )
    assert len(action) <= NEXT_ACTION_MAX_CHARS, (
        path.relative_to(REPO_ROOT),
        len(action),
        NEXT_ACTION_MAX_CHARS,
    )
    for marker in HISTORY_MARKERS:
        assert marker not in action, (path.relative_to(REPO_ROOT), marker)


def main() -> int:
    for path in STATE_FILES:
        assert_next_action_budget(path)
    print("active-state-interface-budget-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
