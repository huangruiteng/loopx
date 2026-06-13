from __future__ import annotations

import re
from typing import Any


TODO_TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[([ xX-])\]\s+(.+?)\s*$")
TODO_METADATA_PATTERN = re.compile(r"^\s*<!--\s*goal-harness:(?:todo\s+)?(?P<body>.*?)\s*-->\s*$")
TODO_METADATA_TOKEN_PATTERN = re.compile(r"(?P<key>[a-z_][a-z0-9_-]*)=(?P<value>[A-Za-z0-9_.:-]+)")
TODO_ACTION_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
TODO_TASK_CLASS_MONITOR = "continuous_monitor"
TODO_TASK_CLASS_VALUES = {TODO_TASK_CLASS_ADVANCEMENT, TODO_TASK_CLASS_MONITOR}

TODO_ACTION_KIND_ADVANCEMENT_VALUES = {
    "advance",
    "analyze",
    "benchmark_run",
    "codex_run",
    "compact_blocker_writeback",
    "compare",
    "execute",
    "fix",
    "implement",
    "rebuild",
    "rebuild_score",
    "repair",
    "run",
    "run_eval",
    "test",
    "validate",
    "writeback",
}
TODO_ACTION_KIND_MONITOR_VALUES = {
    "external_evidence",
    "monitor",
    "observe",
    "poll",
    "watch",
}

TODO_HARD_MONITOR_PATTERNS = (
    re.compile(r"(?i)\bdo not\b.*\b(?:launch|run|execute|start)\b.*\buntil\b"),
    re.compile(r"(?i)\b(?:only|just)\b.*\b(?:after|when|once)\b.*\b(?:owner|user|credential|approval|prerequisite|evidence)\b"),
    re.compile(r"(?i)\b(?:credential|gcp|gcs|gcp_project|gcp_sa_key|gs://)\b.*\b(?:missing|required|provide|proof|prerequisite|gate|gated)\b"),
    re.compile(r"(?i)\b(?:readiness|proof)\b.*\bbefore any formal\b.*\brun\b"),
    re.compile(r"(?i)\bremaining formal\b.*\bpath\b"),
    re.compile(r"(?i)\b(?:route|input)\b.*\babsent\b"),
    re.compile(r"(?i)\b0\b.*\b(?:candidate|candidates)\b"),
)

TODO_ADVANCEMENT_OVERRIDE_PATTERNS = (
    re.compile(
        r"(?i)(?:^|[:：]\s*)(?:implement|add|make|fix|build|wire|define|compare|run|"
        r"execute|test|validate|rebuild|repair|archive|publish|merge|write|attribute)\b"
    ),
    re.compile(
        r"(?i)\b(?:implementation slice|validation-backed patch|smoke fixture|"
        r"regression suite|readiness scan|source preflight|setup-readiness scan)\b"
    ),
)
TODO_BLOCKED_MONITOR_PATTERNS = (
    *TODO_HARD_MONITOR_PATTERNS,
    re.compile(r"(?i)\b(?:blocked|gated|waiting)\b.*\b(?:owner|user|credential|substrate|proof|prerequisite|evidence)\b"),
)
TODO_MONITOR_PATTERNS = (
    re.compile(r"(?i)\bdependency monitor\b"),
    re.compile(r"(?i)\bobservation lane\b"),
    re.compile(r"(?i)(?:^|[:：]\s*)observe\b"),
    re.compile(r"(?i)(?:^|[:：]\s*)poll\b"),
    re.compile(r"(?i)(?:^|[:：]\s*)watch\b"),
    re.compile(r"(?i)\bmonitor-only\b"),
    *TODO_BLOCKED_MONITOR_PATTERNS,
)
TODO_ADVANCEMENT_PATTERNS = (
    *TODO_ADVANCEMENT_OVERRIDE_PATTERNS,
    re.compile(r"(?i)\b(?:task|validation hypothesis|validation step|bounded step|learning run)\b"),
)

NEXT_ACTION_HARD_MONITOR_PATTERNS = (
    re.compile(r"(?i)\bdo not\b.*\b(?:launch|run|execute|start)\b.*\buntil\b"),
    re.compile(r"(?i)\b(?:waiting|blocked|gated)\b.*\b(?:owner|user|credential|approval|prerequisite|evidence)\b"),
)
NEXT_ACTION_ADVANCEMENT_HINT_PATTERNS = (
    re.compile(r"(?i)\bplanning/self[- ]?repair\b"),
    re.compile(r"(?i)\bplanning[- ]?self[- ]?repair\b"),
    re.compile(r"(?i)\bself[- ]?repair capability\b"),
    re.compile(r"(?i)\badvance(?:ment)?[- ]class\b"),
    re.compile(r"(?i)\badvance primary backlog\b"),
    re.compile(r"(?i)\bnext eligible advancement turn\b"),
    re.compile(r"(?i)\bpackage\b.*\b(?:adapter|contract|artifact)\b"),
    re.compile(r"(?i)\bselect\b.*\b(?:task|validation hypothesis|validation step)\b"),
    re.compile(r"(?i)\b(?:local-material-ready|material-ready)\b.*\b(?:task|run|validation)\b"),
    re.compile(r"(?i)\b(?:run|test)\b.*\bvalidation hypothesis\b"),
    re.compile(
        r"(?i)(?:^|[.;:：]\s*)(?:run|execute|test|validate|rebuild|compare|implement|fix|write|package)\b"
    ),
)


def compact_todo_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_todo_action_kind(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    if TODO_ACTION_KIND_PATTERN.match(candidate):
        return candidate
    return None


def parse_todo_metadata_line(line: str) -> dict[str, str] | None:
    match = TODO_METADATA_PATTERN.match(line)
    if not match:
        return None
    metadata: dict[str, str] = {}
    for token in TODO_METADATA_TOKEN_PATTERN.finditer(match.group("body")):
        key = token.group("key").replace("-", "_")
        value = token.group("value")
        if key == "task_class" and value in TODO_TASK_CLASS_VALUES:
            metadata["task_class"] = value
        elif key == "action_kind":
            action_kind = normalize_todo_action_kind(value)
            if action_kind:
                metadata["action_kind"] = action_kind
    return metadata or None


def format_todo_metadata_line(
    *,
    task_class: str | None = None,
    action_kind: str | None = None,
) -> str | None:
    fields: list[str] = []
    if task_class:
        if task_class not in TODO_TASK_CLASS_VALUES:
            raise ValueError(f"todo task_class must be one of: {', '.join(sorted(TODO_TASK_CLASS_VALUES))}")
        fields.append(f"task_class={task_class}")
    normalized_action_kind = normalize_todo_action_kind(action_kind)
    if action_kind and not normalized_action_kind:
        raise ValueError("todo action_kind must be a public-safe token: lowercase letters, digits, '_' or '-'")
    if normalized_action_kind:
        fields.append(f"action_kind={normalized_action_kind}")
    if not fields:
        return None
    return f"  <!-- goal-harness:todo {' '.join(fields)} -->"


def todo_task_class_for_text(text: str) -> str:
    compact = compact_todo_text(text)
    for pattern in TODO_HARD_MONITOR_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_MONITOR
    for pattern in TODO_ADVANCEMENT_OVERRIDE_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_ADVANCEMENT
    for pattern in TODO_BLOCKED_MONITOR_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_MONITOR
    for pattern in TODO_MONITOR_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_MONITOR
    for pattern in TODO_ADVANCEMENT_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_ADVANCEMENT
    return TODO_TASK_CLASS_ADVANCEMENT


def normalize_todo_task_class(value: Any, *, text: str, action_kind: Any = None) -> str:
    candidate = str(value or "").strip()
    if candidate in TODO_TASK_CLASS_VALUES:
        return candidate
    normalized_action_kind = normalize_todo_action_kind(action_kind)
    if normalized_action_kind in TODO_ACTION_KIND_ADVANCEMENT_VALUES:
        return TODO_TASK_CLASS_ADVANCEMENT
    if normalized_action_kind in TODO_ACTION_KIND_MONITOR_VALUES:
        return TODO_TASK_CLASS_MONITOR
    return todo_task_class_for_text(text)


def next_action_requires_advancement_text(text: str) -> bool:
    compact = compact_todo_text(text)
    if not compact:
        return False
    if any(pattern.search(compact) for pattern in NEXT_ACTION_HARD_MONITOR_PATTERNS):
        return False
    return any(pattern.search(compact) for pattern in NEXT_ACTION_ADVANCEMENT_HINT_PATTERNS)
