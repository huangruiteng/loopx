#!/usr/bin/env python3
"""Validate the public biweekly update-note archive wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS_INDEX = ROOT / "docs" / "README.md"
NOTES_DIR = ROOT / "docs" / "update-notes"
NOTES_INDEX = NOTES_DIR / "README.md"
AUTOMATION = NOTES_DIR / "automation.md"
NOTE_FILES = [
    NOTES_DIR / "2026-05-31-to-2026-06-13.md",
    NOTES_DIR / "2026-06-14-to-2026-06-27.md",
]

FORBIDDEN_PUBLIC_STRINGS = [
    "/Users/",
    "/private/tmp/",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "raw_thread",
    "session_history",
    "verifier_output_tail",
    "ACTIVE_GOAL_STATE.md:",
]


def read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing expected file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} is missing {needle!r}")


def assert_not_contains(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"{label} contains forbidden string {needle!r}")


def validate_public_boundary(path: Path) -> None:
    text = read(path)
    label = str(path.relative_to(ROOT))
    for forbidden in FORBIDDEN_PUBLIC_STRINGS:
        assert_not_contains(text, forbidden, label)


def validate_indexes() -> None:
    root_readme = read(README)
    docs_index = read(DOCS_INDEX)
    notes_index = read(NOTES_INDEX)

    assert_contains(root_readme, "docs/update-notes/README.md", "root README")
    assert_contains(docs_index, "update-notes/README.md", "docs README")
    assert_contains(notes_index, "2026-06-14-to-2026-06-27.md", "notes index")
    assert_contains(notes_index, "2026-05-31-to-2026-06-13.md", "notes index")
    assert_contains(notes_index, "automation.md", "notes index")
    assert_contains(notes_index, "2026-06-28 to 2026-07-11", "notes index")


def validate_notes() -> None:
    for note in NOTE_FILES:
        text = read(note)
        label = str(note.relative_to(ROOT))
        assert_contains(text, "# Biweekly Update Note:", label)
        assert_contains(text, "## Source Boundary", label)
        assert_contains(text, "## Highlights", label)
        assert_contains(text, "## What Shipped", label)
        assert_contains(text, "## Validation And Public Boundary", label)

    latest = read(NOTE_FILES[-1])
    assert_contains(latest, "`/loopx <goal>`", "latest note")
    assert_contains(latest, "issue-fix", "latest note")
    assert_contains(latest, "Task graph", "latest note")


def validate_automation_plan() -> None:
    text = read(AUTOMATION)
    assert_contains(text, "separate publication workflow", "automation plan")
    assert_contains(text, "custom behavior", "automation plan")
    assert_contains(text, "active heartbeat", "automation plan")
    assert_contains(text, "workflow_dispatch", "automation plan")
    assert_contains(text, "Open a reviewable PR", "automation plan")
    assert_contains(text, "2026-07-12", "automation plan")
    assert_contains(text, "--dry-run", "automation plan")
    assert_contains(text, "--open-pr", "automation plan")


def main() -> None:
    for path in [README, DOCS_INDEX, NOTES_INDEX, AUTOMATION, *NOTE_FILES]:
        validate_public_boundary(path)
    validate_indexes()
    validate_notes()
    validate_automation_plan()
    print("update notes archive smoke: ok")


if __name__ == "__main__":
    main()
