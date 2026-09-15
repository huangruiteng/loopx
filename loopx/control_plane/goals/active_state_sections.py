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


def active_state_section_text(
    state_text: str,
    heading: str,
    *,
    normalize_text: NormalizeText,
) -> str:
    """Read back one ``## <heading>`` section as flattened prose.

    Counterpart of the quote-isolated objective writers: lines starting
    with ``>`` lose their quote prefix so quote-isolated prose round-trips
    verbatim, legacy lines keep the bullet-prefix flattening, and comment
    markers, blank lines, and later ``## `` sections never become content.
    """
    marker = f"## {heading}"
    start = state_text.find(marker)
    if start < 0:
        return ""
    content_start = start + len(marker)
    end = state_text.find("\n## ", content_start)
    section = state_text[content_start : end if end >= 0 else None]
    lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        else:
            stripped = stripped.removeprefix("- ").strip()
        lines.append(stripped)
    return normalize_text(" ".join(lines))


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
