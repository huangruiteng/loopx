from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import quote, unquote


TODO_TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[([ xX-])\]\s+(.+?)\s*$")
TODO_METADATA_PATTERN = re.compile(r"^\s*<!--\s*loopx:(?:todo\s+)?(?P<body>.*?)\s*-->\s*$")
TODO_METADATA_TOKEN_PATTERN = re.compile(r"(?P<key>[a-z_][a-z0-9_-]*)=(?P<value>[^\s<>]+)")
TODO_ACTION_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
TODO_ID_PATTERN = re.compile(r"^todo_[a-z0-9_-]{3,64}$")
TODO_AGENT_CLAIM_PATTERN = re.compile(r"^[a-z][a-z0-9_.:@-]{0,79}$")
TODO_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_:-]{0,63}$")
TODO_WRITE_SCOPE_MAX_CHARS = 160

TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
TODO_TASK_CLASS_MONITOR = "continuous_monitor"
TODO_TASK_CLASS_USER_GATE = "user_gate"
TODO_TASK_CLASS_BLOCKER = "blocker"
TODO_TASK_CLASS_VALUES = {
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    TODO_TASK_CLASS_BLOCKER,
}

TODO_STATUS_OPEN = "open"
TODO_STATUS_DONE = "done"
TODO_STATUS_BLOCKED = "blocked"
TODO_STATUS_DEFERRED = "deferred"
TODO_STATUS_VALUES = {
    TODO_STATUS_OPEN,
    TODO_STATUS_DONE,
    TODO_STATUS_BLOCKED,
    TODO_STATUS_DEFERRED,
}
TODO_TERMINAL_STATUS_VALUES = {TODO_STATUS_DONE, TODO_STATUS_DEFERRED}

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
        r"execute|test|validate|rebuild|repair|archive|publish|merge|write|attribute|"
        r"collect|aggregate|generate|produce|materialize|rerun|repeat|eval|evaluate|score)\b"
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
        r"(?i)\b(?:collect|aggregate|generate|produce|materialize)\b.*\b(?:then|and)\b.*\b"
        r"(?:run|rerun|repeat|rebuild|score|scorer|gate|eval|evaluate|validate)\b"
    ),
    re.compile(
        r"(?i)(?:^|[.;:：]\s*)(?:run|execute|test|validate|rebuild|compare|implement|fix|"
        r"write|package|collect|aggregate|generate|produce|materialize|rerun|repeat|"
        r"eval|evaluate|score)\b"
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


def normalize_todo_claimed_by(value: Any) -> str | None:
    candidate = compact_todo_text(value).lower().replace(" ", "-")
    if candidate and TODO_AGENT_CLAIM_PATTERN.match(candidate):
        return candidate
    return None


def normalize_todo_id(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate and TODO_ID_PATTERN.match(candidate):
        return candidate
    return None


def normalize_required_write_scopes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = [str(item or "") for item in value]
    else:
        raw_values = re.split(r"[,;|]", str(value or ""))
    scopes: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        scope = compact_todo_text(raw)
        if not scope:
            continue
        if len(scope) > TODO_WRITE_SCOPE_MAX_CHARS:
            continue
        if scope.startswith(("/", "~")) or ".." in scope.split("/"):
            continue
        if re.search(r"[\s<>]", scope):
            continue
        if scope in seen:
            continue
        seen.add(scope)
        scopes.append(scope)
    return scopes


def normalize_required_capabilities(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = [str(item or "") for item in value]
    else:
        raw_values = re.split(r"[,;|]", str(value or ""))
    capabilities: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        capability = compact_todo_text(raw).lower().replace("-", "_").replace(" ", "_")
        if not capability:
            continue
        if not TODO_CAPABILITY_PATTERN.match(capability):
            continue
        if capability in seen:
            continue
        seen.add(capability)
        capabilities.append(capability)
    return capabilities


def normalize_target_capabilities(value: Any) -> list[str]:
    return normalize_required_capabilities(value)


def build_todo_id(
    *,
    role: Any,
    source_section: Any,
    index: Any,
    text: Any,
) -> str:
    identity = "|".join(str(part or "") for part in (role, source_section, index, compact_todo_text(text)))
    return f"todo_{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:12]}"


def normalize_explicit_todo_task_class(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate in TODO_TASK_CLASS_VALUES:
        return candidate
    return None


def normalize_todo_status(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate in TODO_STATUS_VALUES:
        return candidate
    return None


def todo_done_for_status(status: Any) -> bool:
    return normalize_todo_status(status) in TODO_TERMINAL_STATUS_VALUES


def todo_status_from_marker(marker: Any) -> str:
    candidate = str(marker or "").strip().lower()
    if candidate == "x":
        return TODO_STATUS_DONE
    if candidate == "-":
        return TODO_STATUS_DEFERRED
    return TODO_STATUS_OPEN


def todo_marker_for_status(status: Any) -> str:
    normalized = normalize_todo_status(status) or TODO_STATUS_OPEN
    if normalized == TODO_STATUS_DEFERRED:
        return "-"
    if normalized == TODO_STATUS_DONE:
        return "x"
    return " "


def encode_metadata_value(value: Any) -> str:
    compact = compact_todo_text(value)
    return quote(compact, safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:-")


def decode_metadata_value(value: Any) -> str:
    return compact_todo_text(unquote(str(value or "")))


def parse_todo_metadata_line(line: str) -> dict[str, Any] | None:
    match = TODO_METADATA_PATTERN.match(line)
    if not match:
        return None
    metadata: dict[str, Any] = {}
    for token in TODO_METADATA_TOKEN_PATTERN.finditer(match.group("body")):
        key = token.group("key").replace("-", "_")
        value = decode_metadata_value(token.group("value"))
        if key == "todo_id":
            todo_id = normalize_todo_id(value)
            if todo_id:
                metadata["todo_id"] = todo_id
        elif key == "status":
            status = normalize_todo_status(value)
            if status:
                metadata["status"] = status
        elif key == "task_class":
            task_class = normalize_explicit_todo_task_class(value)
            if task_class:
                metadata["task_class"] = task_class
        elif key == "action_kind":
            action_kind = normalize_todo_action_kind(value)
            if action_kind:
                metadata["action_kind"] = action_kind
        elif key in {"required_write_scope", "required_write_scopes"}:
            scopes = normalize_required_write_scopes(value)
            if scopes:
                metadata["required_write_scopes"] = scopes
        elif key in {"required_capability", "required_capabilities"}:
            capabilities = normalize_required_capabilities(value)
            if capabilities:
                metadata["required_capabilities"] = capabilities
        elif key in {"target_capability", "target_capabilities"}:
            capabilities = normalize_target_capabilities(value)
            if capabilities:
                metadata["target_capabilities"] = capabilities
        elif key == "claimed_by":
            claimed_by = normalize_todo_claimed_by(value)
            if claimed_by:
                metadata["claimed_by"] = claimed_by
        elif key in {"note", "evidence", "reason", "completed_at", "updated_at"}:
            if value:
                metadata[key] = value
        elif key == "superseded_by":
            todo_id = normalize_todo_id(value)
            if todo_id:
                metadata["superseded_by"] = todo_id
    return metadata or None


def format_todo_metadata_line(
    *,
    todo_id: str | None = None,
    status: str | None = None,
    task_class: str | None = None,
    action_kind: str | None = None,
    required_write_scopes: Any = None,
    required_capabilities: Any = None,
    target_capabilities: Any = None,
    claimed_by: str | None = None,
    note: str | None = None,
    evidence: str | None = None,
    reason: str | None = None,
    completed_at: str | None = None,
    updated_at: str | None = None,
    superseded_by: str | None = None,
) -> str | None:
    fields: list[str] = []
    normalized_todo_id = normalize_todo_id(todo_id)
    if todo_id and not normalized_todo_id:
        raise ValueError("todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
    if normalized_todo_id:
        fields.append(f"todo_id={encode_metadata_value(normalized_todo_id)}")
    normalized_status = normalize_todo_status(status)
    if status and not normalized_status:
        raise ValueError(f"todo status must be one of: {', '.join(sorted(TODO_STATUS_VALUES))}")
    if normalized_status:
        fields.append(f"status={encode_metadata_value(normalized_status)}")
    if task_class:
        task_class = normalize_explicit_todo_task_class(task_class)
        if not task_class:
            raise ValueError(f"todo task_class must be one of: {', '.join(sorted(TODO_TASK_CLASS_VALUES))}")
        fields.append(f"task_class={encode_metadata_value(task_class)}")
    normalized_action_kind = normalize_todo_action_kind(action_kind)
    if action_kind and not normalized_action_kind:
        raise ValueError("todo action_kind must be a public-safe token: lowercase letters, digits, '_' or '-'")
    if normalized_action_kind:
        fields.append(f"action_kind={encode_metadata_value(normalized_action_kind)}")
    normalized_write_scopes = normalize_required_write_scopes(required_write_scopes)
    if required_write_scopes and not normalized_write_scopes:
        raise ValueError("required_write_scopes must contain public-safe relative scope tokens")
    if normalized_write_scopes:
        fields.append(
            "required_write_scopes="
            f"{encode_metadata_value(','.join(normalized_write_scopes))}"
        )
    normalized_capabilities = normalize_required_capabilities(required_capabilities)
    if required_capabilities and not normalized_capabilities:
        raise ValueError("required_capabilities must contain public-safe capability tokens")
    if normalized_capabilities:
        fields.append(
            "required_capabilities="
            f"{encode_metadata_value(','.join(normalized_capabilities))}"
        )
    normalized_target_capabilities = normalize_target_capabilities(target_capabilities)
    if target_capabilities and not normalized_target_capabilities:
        raise ValueError("target_capabilities must contain public-safe capability tokens")
    if normalized_target_capabilities:
        fields.append(
            "target_capabilities="
            f"{encode_metadata_value(','.join(normalized_target_capabilities))}"
        )
    normalized_claimed_by = normalize_todo_claimed_by(claimed_by)
    if claimed_by and not normalized_claimed_by:
        raise ValueError("claimed_by must be a public-safe agent token such as codex-main-control")
    if normalized_claimed_by:
        fields.append(f"claimed_by={encode_metadata_value(normalized_claimed_by)}")
    for key, value in (
        ("note", note),
        ("evidence", evidence),
        ("reason", reason),
        ("completed_at", completed_at),
        ("updated_at", updated_at),
    ):
        if value:
            fields.append(f"{key}={encode_metadata_value(value)}")
    normalized_superseded_by = normalize_todo_id(superseded_by)
    if superseded_by and not normalized_superseded_by:
        raise ValueError("superseded_by must use the public token shape todo_<letters-digits-underscore-hyphen>")
    if normalized_superseded_by:
        fields.append(f"superseded_by={encode_metadata_value(normalized_superseded_by)}")
    if not fields:
        return None
    return f"  <!-- loopx:todo {' '.join(fields)} -->"


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
    candidate = normalize_explicit_todo_task_class(value)
    if candidate:
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
