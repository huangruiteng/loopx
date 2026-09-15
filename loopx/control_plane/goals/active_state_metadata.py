from __future__ import annotations


USER_TODO_HEADER_MARKERS = (
    "user todo",
    "owner review reading queue",
    "owner reading queue",
)
AGENT_TODO_HEADER_MARKERS = (
    "agent todo",
    "codex todo",
    "project agent todo",
)
TODO_ARCHIVE_HEADER_MARKERS = (
    "todo archive",
    "work archive",
    "completed archive",
    "completed work",
    "完成归档",
    "待办归档",
)

# Generated objective text is presentation data, never machine-owned Markdown.
# Objectives are arbitrary user prose, so they may contain fenced blocks, tilde
# fences, HTML comments, or text that merely looks like a Todo row. Writing one
# straight into the document body lets it open a construct that swallows the
# generated Todo sections below it. The markers below isolate that prose so
# readers keep treating it as text.
OBJECTIVE_REGION_BEGIN = "<!-- loopx:objective-v0 begin -->"
OBJECTIVE_REGION_END = "<!-- loopx:objective-v0 end -->"


def render_objective_block(objective: str) -> str:
    """Render generated objective text as an isolated, non-authoritative block.

    The returned text preserves the objective verbatim between two marker
    comments, so a direct objective readback still sees the prose while
    Markdown readers never let it open a fence, open an HTML comment, or
    contribute rows to the Todo sections that follow.
    """
    text = str(objective or "").strip("\n")
    if not text.strip():
        return ""
    return f"{OBJECTIVE_REGION_BEGIN}\n{text}\n{OBJECTIVE_REGION_END}"


def read_objective_text(state_text: str) -> str:
    """Read back the generated objective text from an isolated region.

    Returns an empty string for legacy state documents written before the
    objective region existed, so callers keep their previous fallback.
    """
    lines = str(state_text or "").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.strip() == OBJECTIVE_REGION_BEGIN), None
    )
    if start is None:
        return ""
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() == OBJECTIVE_REGION_END),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end]).strip()


def parse_state_frontmatter(state_text: str) -> dict[str, str]:
    if not state_text.startswith("---"):
        return {}
    parts = state_text.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def todo_role_for_heading(heading: str) -> str | None:
    normalized = heading.strip().lower()
    if any(marker in normalized for marker in TODO_ARCHIVE_HEADER_MARKERS):
        return None
    if any(marker in normalized for marker in USER_TODO_HEADER_MARKERS):
        return "user"
    if any(marker in normalized for marker in AGENT_TODO_HEADER_MARKERS):
        return "agent"
    return None
