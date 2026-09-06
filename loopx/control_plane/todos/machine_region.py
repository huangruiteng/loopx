"""Versioned ownership of generated Todo regions, not a general Markdown parser.

Legacy import accepts the actual LoopX-produced H2/list/metadata grammar.
New projections have paired markers, shared by the writer and readers.
Text outside that grammar is never silently adopted as machine-owned content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .contract import TODO_TASK_PATTERN, parse_todo_metadata_line


TODO_REGION_PREFIX = "<!-- loopx:todo-region-v0 "
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_ROLE_HEADINGS = {
    "user todo": "user",
    "user todo / owner review reading queue": "user",
    "owner review reading queue": "user",
    "owner reading queue": "user",
    "agent todo": "agent",
    "codex todo": "agent",
    "project agent todo": "agent",
    "completed work archive": "archive",
}


@dataclass(frozen=True)
class TodoRegion:
    role: str
    start: int
    end: int
    body_end: int
    heading: str
    marked: bool


def todo_region_marker(role: str, edge: str) -> str:
    if role not in {"user", "agent", "archive"} or edge not in {"begin", "end"}:
        raise ValueError("invalid Todo region marker")
    return f"{TODO_REGION_PREFIX}role={role} {edge} -->"


def find_todo_regions(lines: list[str]) -> list[TodoRegion]:
    """Locate generated regions without consuming narrative or code examples.

    Offsets are half-open line indexes. A marked region includes its heading
    and both delimiters; body_end excludes the end marker for legacy editors.
    The legacy import stops at the first non-generated line, not the next H2.
    """
    regions: list[TodoRegion] = []
    fence: str | None = None
    in_comment = False
    index = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None)
        if end is None:
            raise ValueError("unterminated Goal frontmatter")
        index = end + 1
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        if fence is not None:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*", line):
                fence = None
            index += 1
            continue
        if in_comment:
            in_comment = "-->" not in line
            index += 1
            continue
        opening = _FENCE.fullmatch(line)
        if opening:
            fence = opening.group(1)
            index += 1
            continue
        if line.lstrip().startswith("<!--") and "-->" not in line:
            in_comment = True
            index += 1
            continue
        if TODO_REGION_PREFIX in line:
            raise ValueError("orphan or malformed Todo region marker")
        heading = line[3:].strip() if line.startswith("## ") else ""
        role = _ROLE_HEADINGS.get(heading.lower())
        if role is None:
            index += 1
            continue
        start = index
        index += 1
        marked = index < len(lines) and lines[index].rstrip("\r\n") == todo_region_marker(role, "begin")
        if marked:
            index += 1
        while index < len(lines):
            content = lines[index].rstrip("\r\n")
            if content == todo_region_marker(role, "end") and marked:
                break
            if TODO_REGION_PREFIX in content:
                raise ValueError("nested, mismatched, or malformed Todo region marker")
            generated = (
                not content.strip()
                or TODO_TASK_PATTERN.match(content) is not None
                or parse_todo_metadata_line(content) is not None
                or content.startswith("<!-- loopx:todo-section-projection-v0 ")
            )
            if not generated:
                if marked:
                    raise ValueError("non-generated content inside marked Todo region")
                break
            index += 1
        if marked and index == len(lines):
            raise ValueError("unterminated Todo region")
        body_end = index
        if marked:
            index += 1
        regions.append(TodoRegion(role, start, index, body_end, heading, marked))
    return regions
