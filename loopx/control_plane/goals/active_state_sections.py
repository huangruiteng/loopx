from __future__ import annotations

import re
from typing import Callable


NormalizeText = Callable[..., str]


def active_state_sections(
    state_text: str,
    headings: tuple[str, ...],
    *,
    section_heading_pattern: re.Pattern[str],
) -> dict[str, list[str]]:
    wanted = {heading.lower(): heading for heading in headings}
    current: str | None = None
    sections: dict[str, list[str]] = {heading: [] for heading in headings}
    for line in state_text.splitlines():
        match = section_heading_pattern.match(line)
        if match:
            normalized = match.group(1).strip().lower()
            current = wanted.get(normalized)
            continue
        if current:
            sections[current].append(line)
    return sections


def active_state_section_entries(
    lines: list[str],
    *,
    bullet_pattern: re.Pattern[str],
    normalize_text: NormalizeText,
) -> list[str]:
    entries: list[str] = []
    current: list[str] = []
    for line in lines:
        bullet_match = bullet_pattern.match(line)
        if bullet_match:
            if current:
                entries.append(normalize_text(" ".join(current)))
            current = [bullet_match.group(1)]
            continue
        if current and line.startswith((" ", "\t")):
            continuation = line.strip()
            if continuation:
                current.append(continuation)
            continue
        if current:
            entries.append(normalize_text(" ".join(current)))
            current = []
        stripped = line.strip()
        if stripped:
            entries.append(stripped)
    if current:
        entries.append(normalize_text(" ".join(current)))
    return entries
