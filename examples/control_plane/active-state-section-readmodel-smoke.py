#!/usr/bin/env python3
"""Smoke-test active-state section parsing read-model wrappers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.projections.active_state_sections import (  # noqa: E402
    active_state_section_entries as direct_active_state_section_entries,
    active_state_sections as direct_active_state_sections,
)
from loopx.status import (  # noqa: E402
    BACKLOG_HYGIENE_BULLET_PATTERN,
    SECTION_HEADING_PATTERN,
    active_state_section_entries,
    active_state_sections,
    normalize_todo_text,
)


STATE_TEXT = """# Goal

## Next Action

- Continue canary-gated read-model cleanup
  after PR #1284

## Operating Lessons

Plain observation
1. First numbered item
   continued

### Nested Heading

Should not land in requested sections
"""


def main() -> int:
    headings = ("Next Action", "Operating Lessons", "Missing Section")
    direct_sections = direct_active_state_sections(
        STATE_TEXT,
        headings,
        section_heading_pattern=SECTION_HEADING_PATTERN,
    )
    wrapper_sections = active_state_sections(STATE_TEXT, headings)
    assert wrapper_sections == direct_sections, (wrapper_sections, direct_sections)
    assert wrapper_sections["Missing Section"] == [], wrapper_sections
    assert "Continue canary-gated read-model cleanup" in "\n".join(
        wrapper_sections["Next Action"]
    ), wrapper_sections

    direct_entries = direct_active_state_section_entries(
        wrapper_sections["Operating Lessons"],
        bullet_pattern=BACKLOG_HYGIENE_BULLET_PATTERN,
        normalize_text=normalize_todo_text,
    )
    wrapper_entries = active_state_section_entries(wrapper_sections["Operating Lessons"])
    assert wrapper_entries == direct_entries, (wrapper_entries, direct_entries)
    assert wrapper_entries == [
        "Plain observation",
        "First numbered item continued",
    ], wrapper_entries

    next_entries = active_state_section_entries(wrapper_sections["Next Action"])
    assert next_entries == [
        "Continue canary-gated read-model cleanup after PR #1284",
    ], next_entries

    print("active-state-section-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
