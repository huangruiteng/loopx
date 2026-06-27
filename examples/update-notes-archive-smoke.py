#!/usr/bin/env python3
"""Validate the public biweekly update-note archive wiring."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS_INDEX = ROOT / "docs" / "README.md"
NOTES_DIR = ROOT / "docs" / "update-notes"
NOTES_INDEX = NOTES_DIR / "README.md"
AUTOMATION = NOTES_DIR / "automation.md"
WORKFLOW = ROOT / ".github" / "workflows" / "update-notes.yml"
GENERATOR = ROOT / "scripts" / "update_notes_release_job.py"
NOTE_FILE_RE = re.compile(r"\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.md$")

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


def note_files() -> list[Path]:
    files = sorted(path for path in NOTES_DIR.glob("*.md") if NOTE_FILE_RE.match(path.name))
    if len(files) < 2:
        raise AssertionError("expected at least two archived update notes")
    return files


def validate_indexes() -> None:
    root_readme = read(README)
    docs_index = read(DOCS_INDEX)
    notes_index = read(NOTES_INDEX)
    files = note_files()

    assert_contains(root_readme, "docs/update-notes/README.md", "root README")
    assert_contains(docs_index, "update-notes/README.md", "docs README")
    for note in files:
        assert_contains(notes_index, note.name, "notes index")
    assert_contains(notes_index, files[-1].name, "notes index latest")
    assert_contains(notes_index, "automation.md", "notes index")
    if not re.search(r"Next expected window: \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\.", notes_index):
        raise AssertionError("notes index missing next expected window")


def validate_notes() -> None:
    for note in note_files():
        text = read(note)
        label = str(note.relative_to(ROOT))
        assert_contains(text, "# Biweekly Update Note:", label)
        assert_contains(text, "## Source Boundary", label)
        assert_contains(text, "## Highlights", label)
        assert_contains(text, "## What Shipped", label)
        assert_contains(text, "## Validation And Public Boundary", label)


def validate_automation_plan() -> None:
    text = read(AUTOMATION)
    assert_contains(text, "separate publication workflow", "automation plan")
    assert_contains(text, ".github/workflows/update-notes.yml", "automation plan")
    assert_contains(text, "scripts/update_notes_release_job.py", "automation plan")
    assert_contains(text, "custom behavior", "automation plan")
    assert_contains(text, "active heartbeat", "automation plan")
    assert_contains(text, "workflow_dispatch", "automation plan")
    assert_contains(text, "since", "automation plan")
    assert_contains(text, "until", "automation plan")
    assert_contains(text, "Open a reviewable draft PR", "automation plan")
    assert_contains(text, "2026-07-12", "automation plan")
    assert_contains(text, "--dry-run", "automation plan")
    assert_contains(text, "--open-pr", "automation plan")


def validate_project_automation() -> None:
    workflow = read(WORKFLOW)
    generator = read(GENERATOR)
    assert_contains(workflow, "schedule:", "update notes workflow")
    assert_contains(workflow, "workflow_dispatch:", "update notes workflow")
    assert_contains(workflow, "fetch-depth: 0", "update notes workflow")
    assert_contains(workflow, "scripts/update_notes_release_job.py", "update notes workflow")
    assert_contains(workflow, "peter-evans/create-pull-request", "update notes workflow")
    assert_contains(workflow, "draft: true", "update notes workflow")
    assert_contains(generator, "def infer_next_window", "update notes generator")
    assert_contains(generator, "def collect_commits", "update notes generator")
    assert_contains(generator, "GITHUB_OUTPUT", "update notes generator")
    assert_contains(generator, "does not use an LLM", "update notes generator")
    assert_contains(generator, "does not include private operator state", "update notes generator")


def main() -> None:
    for path in [README, DOCS_INDEX, NOTES_INDEX, AUTOMATION, WORKFLOW, GENERATOR, *note_files()]:
        validate_public_boundary(path)
    validate_indexes()
    validate_notes()
    validate_automation_plan()
    validate_project_automation()
    print("update notes archive smoke: ok")


if __name__ == "__main__":
    main()
