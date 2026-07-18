from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any
from urllib.parse import quote, unquote

from ...repository_identity import normalize_repository_identity


TODO_TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[([ xX-])\]\s+(.+?)\s*$")
TODO_METADATA_PATTERN = re.compile(r"^\s*<!--\s*loopx:(?:todo\s+)?(?P<body>.*?)\s*-->\s*$")
TODO_METADATA_TOKEN_PATTERN = re.compile(r"(?P<key>[a-z_][a-z0-9_-]*)=(?P<value>[^\s<>]+)")
TODO_ACTION_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
TODO_ID_PATTERN = re.compile(r"^todo_[a-z0-9_-]{3,64}$")
TODO_AGENT_CLAIM_PATTERN = re.compile(r"^[a-z][a-z0-9_.:@-]{0,79}$")
TODO_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_:-]{0,63}$")
TODO_EXPLORE_RESULT_NODE_REF_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,95}$")
TODO_EXPLORE_RESULT_NODE_REF_LIMIT = 8
TODO_DECISION_SCOPE_KEY_PATTERN = re.compile(r"^(?:\*|[a-z0-9][a-z0-9_.:@*/-]{0,95})$")
TODO_RESUME_KIND_TODO_DONE = "todo_done"
TODO_RESUME_KIND_PR_MERGED = "pr_merged"
TODO_RESUME_KIND_CAPACITY_AVAILABLE = "capacity_available"
TODO_RESUME_KIND_VALUES = {
    TODO_RESUME_KIND_TODO_DONE,
    TODO_RESUME_KIND_PR_MERGED,
    TODO_RESUME_KIND_CAPACITY_AVAILABLE,
}
TODO_RESUME_WHEN_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}(?::[a-z0-9_.:@-]{1,96})?$")
TODO_RESUME_PR_MERGED_PATTERN = re.compile(
    r"^pr_merged:(?:(?:[a-z0-9_.-]{1,80})/(?:[a-z0-9_.-]{1,100}))?#[1-9][0-9]{0,8}$"
)
TODO_WRITE_SCOPE_MAX_CHARS = 160
TODO_MONITOR_METADATA_FIELDS = (
    "target_key",
    "cadence",
    "next_due_at",
    "expires_at",
    "last_checked_at",
    "result_hash",
    "consecutive_no_change",
    "material_change",
    "max_no_change_before_replan",
)
TODO_METADATA_FIELDS = (
    "todo_id", "status", "task_class", "action_kind", "continuation_policy",
    "task_repository", "required_write_scopes", "required_capabilities", "target_capabilities",
    "explore_result_node_refs",
    "decision_scope", "required_decision_scopes", "decision_outcome",
    "decision_scope_outcomes", "claimed_by", "bound_agent", "goal_bound",
    "blocks_agent", "excluded_agents", "global_gate", "unblocks_todo_id", "successor_todo_ids",
    "resume_when", "no_followup", *TODO_MONITOR_METADATA_FIELDS, "note", "evidence",
    "reason", "completed_at", "updated_at", "superseded_by",
)

TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
TODO_TASK_CLASS_MONITOR = "continuous_monitor"
TODO_TASK_CLASS_USER_GATE = "user_gate"
TODO_TASK_CLASS_USER_ACTION = "user_action"
TODO_TASK_CLASS_BLOCKER = "blocker"
TODO_TASK_CLASS_VALUES = {
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    TODO_TASK_CLASS_USER_ACTION,
    TODO_TASK_CLASS_BLOCKER,
}
TODO_DECISION_SCOPE_SCHEMA_VERSION = "decision_scope_v0"
TODO_DECISION_SCOPE_OUTCOME_SCHEMA_VERSION = "todo_decision_scope_outcome_v0"
TODO_DECISION_OUTCOME_VALUES = {"approve", "reject", "cancel"}
TODO_DECISION_SCOPE_KIND_VALUES = {
    "private_read",
    "write_scope",
    "resource",
    "production",
    "public_claim",
    "direction",
    "other",
}
TODO_DECISION_SCOPE_GRANULARITY_VALUES = {
    "action",
    "lane",
    "goal",
    "project",
    "global",
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
TODO_LEGACY_TERMINAL_STATUS_VALUES = {"completed", "closed", "archived"}

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


class TodoContinuationPolicy(str, Enum):
    INDEPENDENT_HANDOFF = "independent_handoff"
    SAME_AGENT_NON_DELIVERY = "same_agent_non_delivery"


TODO_CONTINUATION_POLICY_VALUES = {
    policy.value for policy in TodoContinuationPolicy
}
TODO_REMOVED_REVIEW_CONTINUATION_POLICY_VALUES = {
    "primary_review",
    "review_handoff",
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


def normalize_todo_task_repository(value: Any) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    try:
        return normalize_repository_identity(candidate)
    except ValueError:
        return None


def normalize_todo_continuation_policy(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate in TODO_CONTINUATION_POLICY_VALUES:
        return candidate
    return None


def normalize_removed_todo_continuation_policy(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate in TODO_REMOVED_REVIEW_CONTINUATION_POLICY_VALUES:
        return candidate
    return None


def resolve_todo_continuation_policy(
    value: Any,
    *,
    action_kind: Any = None,
) -> TodoContinuationPolicy:
    del action_kind
    explicit = normalize_todo_continuation_policy(value)
    if explicit:
        return TodoContinuationPolicy(explicit)
    return TodoContinuationPolicy.INDEPENDENT_HANDOFF


def normalize_todo_claimed_by(value: Any) -> str | None:
    candidate = compact_todo_text(value).lower().replace(" ", "-")
    if candidate and TODO_AGENT_CLAIM_PATTERN.match(candidate):
        return candidate
    return None


def normalize_todo_blocks_agent(value: Any) -> str | None:
    return normalize_todo_claimed_by(value)


def normalize_todo_bound_agent(value: Any) -> str | None:
    return normalize_todo_claimed_by(value)


def normalize_todo_goal_bound(value: Any) -> bool | None:
    return normalize_todo_global_gate(value)


def normalize_todo_excluded_agents(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        candidates = [value]
    return sorted(
        {
            agent_id
            for candidate in candidates
            for agent_id in [normalize_todo_claimed_by(candidate)]
            if agent_id
        }
    )


def require_todo_excluded_agents(
    value: Any,
    *,
    field: str = "excluded_agents",
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        candidates = [value]
    normalized: set[str] = set()
    for candidate in candidates:
        agent_id = normalize_todo_claimed_by(candidate)
        if not agent_id:
            raise ValueError(
                f"{field} must contain public-safe agent tokens such as codex-side-bypass"
            )
        normalized.add(agent_id)
    return sorted(normalized)


def normalize_todo_resume_when(value: Any) -> str | None:
    candidate = compact_todo_text(value).lower()
    if candidate and TODO_RESUME_PR_MERGED_PATTERN.match(candidate):
        return candidate
    if candidate and TODO_RESUME_WHEN_PATTERN.match(candidate):
        return candidate
    return None


def normalize_supported_todo_resume_when(value: Any) -> str | None:
    """Normalize resume conditions that LoopX can safely evaluate."""
    candidate = normalize_todo_resume_when(value)
    if not candidate:
        return None
    kind, separator, target = candidate.partition(":")
    if kind == TODO_RESUME_KIND_TODO_DONE:
        return candidate if separator and normalize_todo_id(target) else None
    if kind == TODO_RESUME_KIND_PR_MERGED:
        return candidate if TODO_RESUME_PR_MERGED_PATTERN.match(candidate) else None
    if kind == TODO_RESUME_KIND_CAPACITY_AVAILABLE:
        return candidate if separator and TODO_CAPABILITY_PATTERN.match(target) else None
    return None


def require_supported_todo_resume_when(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = normalize_supported_todo_resume_when(value)
    if normalized:
        return normalized
    raise ValueError(
        "resume_when must use a supported condition: todo_done:<todo_id>, "
        "pr_merged:[owner/repo]#<number>, or capacity_available:<capability>"
    )


def normalize_todo_no_followup(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    candidate = compact_todo_text(value).lower()
    if candidate in {"1", "true", "yes", "y", "no_followup", "no-followup"}:
        return True
    if candidate in {"0", "false", "no", "n"}:
        return False
    return None


def normalize_todo_global_gate(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    candidate = compact_todo_text(value).lower()
    if candidate in {"1", "true", "yes", "y", "global_gate", "global-gate"}:
        return True
    if candidate in {"0", "false", "no", "n"}:
        return False
    return None


def normalize_todo_id(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    if candidate and TODO_ID_PATTERN.match(candidate):
        return candidate
    return None


def normalize_todo_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    todo_ids: list[str] = []
    for raw_value in raw_values:
        for match in re.findall(r"\btodo_[A-Za-z0-9_-]+\b", str(raw_value or "")):
            todo_id = normalize_todo_id(match)
            if todo_id and todo_id not in todo_ids:
                todo_ids.append(todo_id)
        todo_id = normalize_todo_id(raw_value)
        if todo_id and todo_id not in todo_ids:
            todo_ids.append(todo_id)
    return todo_ids


def merge_todo_id_lists(*values: Any) -> list[str]:
    todo_ids: list[str] = []
    for value in values:
        for todo_id in normalize_todo_id_list(value):
            if todo_id not in todo_ids:
                todo_ids.append(todo_id)
    return todo_ids


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


def normalize_explore_result_node_refs(value: Any) -> list[str]:
    """Normalize explicit public-safe Explore node ids attached to a todo."""

    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = [str(item or "") for item in value]
    else:
        raw_values = re.split(r"[,;|]", str(value or ""))
    refs: list[str] = []
    for raw in raw_values:
        ref = compact_todo_text(raw)
        if not ref or not TODO_EXPLORE_RESULT_NODE_REF_PATTERN.match(ref):
            continue
        if ref not in refs:
            refs.append(ref)
        if len(refs) >= TODO_EXPLORE_RESULT_NODE_REF_LIMIT:
            break
    return refs


def normalize_todo_decision_scope(value: Any) -> dict[str, str] | None:
    """Normalize the compact decision-scope metadata token.

    Markdown todo metadata stores the v0 shape as
    ``kind:granularity:scope_key`` so authors do not need to embed JSON in
    active-state comments. Status and quota expose the normalized object.
    """

    raw_kind: Any = None
    raw_granularity: Any = None
    raw_scope_key: Any = None
    raw_decision_id: Any = None
    if isinstance(value, dict):
        raw_kind = value.get("kind")
        raw_granularity = value.get("granularity")
        raw_scope_key = value.get("scope_key")
        raw_decision_id = value.get("decision_id")
    else:
        candidate = compact_todo_text(value).lower()
        parts = candidate.split(":", 2)
        if len(parts) != 3:
            return None
        raw_kind, raw_granularity, raw_scope_key = parts

    kind = compact_todo_text(raw_kind).lower()
    granularity = compact_todo_text(raw_granularity).lower()
    scope_key = compact_todo_text(raw_scope_key).lower()
    if kind not in TODO_DECISION_SCOPE_KIND_VALUES:
        return None
    if granularity not in TODO_DECISION_SCOPE_GRANULARITY_VALUES:
        return None
    if not TODO_DECISION_SCOPE_KEY_PATTERN.match(scope_key):
        return None

    payload: dict[str, str] = {
        "schema_version": TODO_DECISION_SCOPE_SCHEMA_VERSION,
        "kind": kind,
        "granularity": granularity,
        "scope_key": scope_key,
    }
    decision_id = normalize_todo_id(raw_decision_id)
    if decision_id:
        payload["decision_id"] = decision_id
    return payload


def normalize_todo_decision_outcome(value: Any) -> str | None:
    candidate = compact_todo_text(value).lower()
    return candidate if candidate in TODO_DECISION_OUTCOME_VALUES else None


def require_todo_decision_outcome(value: Any) -> str:
    outcome = normalize_todo_decision_outcome(value)
    if not outcome:
        raise ValueError(
            "decision_outcome must be one of: "
            + ", ".join(sorted(TODO_DECISION_OUTCOME_VALUES))
        )
    return outcome


def require_todo_decision_scope(value: Any) -> dict[str, str]:
    scope = normalize_todo_decision_scope(value)
    if not scope:
        raise ValueError(
            "decision_scope must use kind:granularity:scope_key, such as "
            "private_read:project:authority"
        )
    return scope


def _normalize_todo_required_decision_scopes(
    value: Any,
    *,
    strict: bool,
) -> list[dict[str, str]]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = re.split(r"[,;|]", str(value or ""))
    scopes: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in raw_values:
        scope = normalize_todo_decision_scope(raw)
        if not scope:
            if strict:
                raise ValueError(
                    "required_decision_scopes must contain "
                    "kind:granularity:scope_key tokens"
                )
            continue
        identity = (scope["kind"], scope["granularity"], scope["scope_key"])
        if identity in seen:
            continue
        seen.add(identity)
        scopes.append(scope)
    return scopes


def normalize_todo_required_decision_scopes(value: Any) -> list[dict[str, str]]:
    return _normalize_todo_required_decision_scopes(value, strict=False)


def require_todo_required_decision_scopes(value: Any) -> list[dict[str, str]]:
    return _normalize_todo_required_decision_scopes(value, strict=True)


def decision_scope_metadata_value(value: Any) -> str | None:
    if value is None:
        return None
    scope = require_todo_decision_scope(value)
    return f"{scope['kind']}:{scope['granularity']}:{scope['scope_key']}"


def required_decision_scopes_metadata_value(value: Any) -> str | None:
    if value is None:
        return None
    scopes = require_todo_required_decision_scopes(value)
    if not scopes:
        return None
    return ",".join(
        f"{scope['kind']}:{scope['granularity']}:{scope['scope_key']}"
        for scope in scopes
    )


def normalize_todo_decision_scope_outcomes(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    raw_values = list(value) if isinstance(value, (list, tuple, set)) else [value]
    if isinstance(value, str):
        raw_values = [item for item in value.split(",") if item]
    outcomes: list[dict[str, Any]] = []
    positions: dict[tuple[str, str, str], int] = {}
    for raw in raw_values:
        raw_outcome: Any = None
        raw_scope: Any = None
        raw_source_todo_id: Any = None
        if isinstance(raw, dict):
            raw_outcome = raw.get("outcome")
            raw_scope = raw.get("decision_scope") or raw.get("scope")
            raw_source_todo_id = raw.get("source_todo_id")
        else:
            parts = str(raw or "").split("|", 2)
            if len(parts) == 3:
                raw_outcome, raw_scope, raw_source_todo_id = parts
        outcome = normalize_todo_decision_outcome(raw_outcome)
        scope = normalize_todo_decision_scope(raw_scope)
        source_todo_id = normalize_todo_id(raw_source_todo_id)
        if not outcome or not scope or not source_todo_id:
            continue
        payload = {
            "schema_version": TODO_DECISION_SCOPE_OUTCOME_SCHEMA_VERSION,
            "outcome": outcome,
            "decision_scope": scope,
            "source_todo_id": source_todo_id,
        }
        identity = (scope["kind"], scope["granularity"], scope["scope_key"])
        if identity in positions:
            outcomes[positions[identity]] = payload
        else:
            positions[identity] = len(outcomes)
            outcomes.append(payload)
    return outcomes


def decision_scope_outcomes_metadata_value(value: Any) -> str | None:
    outcomes = normalize_todo_decision_scope_outcomes(value)
    if not outcomes:
        return None
    return ",".join(
        "|".join(
            (
                item["outcome"],
                ":".join(
                    (
                        item["decision_scope"]["kind"],
                        item["decision_scope"]["granularity"],
                        item["decision_scope"]["scope_key"],
                    )
                ),
                item["source_todo_id"],
            )
        )
        for item in outcomes
    )


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


def todo_terminal_for_status(status: Any) -> bool:
    candidate = str(status or "").strip().lower()
    return (
        normalize_todo_status(candidate) in TODO_TERMINAL_STATUS_VALUES
        or candidate in TODO_LEGACY_TERMINAL_STATUS_VALUES
    )


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


def parse_todo_metadata_tokens(line: str) -> list[tuple[str, str]] | None:
    match = TODO_METADATA_PATTERN.match(line)
    if not match:
        return None
    return [
        (
            token.group("key").replace("-", "_"),
            decode_metadata_value(token.group("value")),
        )
        for token in TODO_METADATA_TOKEN_PATTERN.finditer(match.group("body"))
    ]


def parse_todo_metadata_line(line: str) -> dict[str, Any] | None:
    tokens = parse_todo_metadata_tokens(line)
    if tokens is None:
        return None
    metadata: dict[str, Any] = {}
    for key, value in tokens:
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
        elif key == "task_repository":
            task_repository = normalize_todo_task_repository(value)
            if task_repository:
                metadata["task_repository"] = task_repository
        elif key == "continuation_policy":
            continuation_policy = normalize_todo_continuation_policy(value)
            if continuation_policy:
                metadata["continuation_policy"] = continuation_policy
            else:
                removed_policy = normalize_removed_todo_continuation_policy(value)
                if removed_policy:
                    metadata["removed_continuation_policy"] = removed_policy
        elif key == "removed_continuation_policy":
            removed_policy = normalize_removed_todo_continuation_policy(value)
            if removed_policy:
                metadata["removed_continuation_policy"] = removed_policy
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
        elif key in {"explore_result_node_ref", "explore_result_node_refs"}:
            refs = normalize_explore_result_node_refs(value)
            if refs:
                metadata["explore_result_node_refs"] = refs
        elif key == "decision_scope":
            decision_scope = normalize_todo_decision_scope(value)
            if decision_scope:
                metadata["decision_scope"] = decision_scope
        elif key in {"required_decision_scope", "required_decision_scopes"}:
            decision_scopes = normalize_todo_required_decision_scopes(value)
            if decision_scopes:
                metadata["required_decision_scopes"] = decision_scopes
        elif key == "decision_outcome":
            outcome = normalize_todo_decision_outcome(value)
            if outcome:
                metadata["decision_outcome"] = outcome
        elif key == "decision_scope_outcomes":
            outcomes = normalize_todo_decision_scope_outcomes(value)
            if outcomes:
                metadata["decision_scope_outcomes"] = outcomes
        elif key == "claimed_by":
            claimed_by = normalize_todo_claimed_by(value)
            if claimed_by:
                metadata["claimed_by"] = claimed_by
        elif key == "bound_agent":
            bound_agent = normalize_todo_bound_agent(value)
            if bound_agent:
                metadata["bound_agent"] = bound_agent
        elif key == "goal_bound":
            goal_bound = normalize_todo_goal_bound(value)
            if goal_bound is not None:
                metadata["goal_bound"] = goal_bound
        elif key == "blocks_agent":
            blocks_agent = normalize_todo_blocks_agent(value)
            if blocks_agent:
                metadata["blocks_agent"] = blocks_agent
        elif key in {"excluded_agent", "excluded_agents"}:
            excluded_agents = normalize_todo_excluded_agents(value)
            if excluded_agents:
                metadata["excluded_agents"] = excluded_agents
        elif key == "global_gate":
            global_gate = normalize_todo_global_gate(value)
            if global_gate is not None:
                metadata["global_gate"] = global_gate
        elif key == "unblocks_todo_id":
            todo_id = normalize_todo_id(value)
            if todo_id:
                metadata["unblocks_todo_id"] = todo_id
        elif key in {"successor_todo_id", "successor_todo_ids"}:
            todo_ids = normalize_todo_id_list(value)
            if todo_ids:
                metadata["successor_todo_ids"] = todo_ids
        elif key == "resume_when":
            resume_when = normalize_todo_resume_when(value)
            if resume_when:
                metadata["resume_when"] = resume_when
        elif key == "no_followup":
            no_followup = normalize_todo_no_followup(value)
            if no_followup is not None:
                metadata["no_followup"] = no_followup
        elif key in TODO_MONITOR_METADATA_FIELDS:
            if value:
                metadata[key] = value
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
    task_repository: str | None = None,
    continuation_policy: str | None = None,
    removed_continuation_policy: str | None = None,
    required_write_scopes: Any = None,
    required_capabilities: Any = None,
    target_capabilities: Any = None,
    explore_result_node_refs: Any = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    decision_outcome: str | None = None,
    decision_scope_outcomes: Any = None,
    claimed_by: str | None = None,
    bound_agent: str | None = None,
    goal_bound: bool | None = None,
    blocks_agent: str | None = None,
    excluded_agents: Any = None,
    global_gate: bool | None = None,
    unblocks_todo_id: str | None = None,
    successor_todo_ids: Any = None,
    resume_when: str | None = None,
    no_followup: bool | None = None,
    target_key: str | None = None,
    cadence: str | None = None,
    next_due_at: str | None = None,
    expires_at: str | None = None,
    last_checked_at: str | None = None,
    result_hash: str | None = None,
    consecutive_no_change: str | None = None,
    material_change: str | None = None,
    max_no_change_before_replan: str | None = None,
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
    normalized_task_repository = normalize_todo_task_repository(task_repository)
    if task_repository and not normalized_task_repository:
        raise ValueError(
            "todo task_repository must be a credential-free Git remote or canonical "
            "git:<host>/<path> identity"
        )
    if normalized_task_repository:
        fields.append(
            f"task_repository={encode_metadata_value(normalized_task_repository)}"
        )
    normalized_continuation_policy = normalize_todo_continuation_policy(
        continuation_policy
    )
    if continuation_policy and not normalized_continuation_policy:
        raise ValueError(
            "todo continuation_policy must be one of: "
            + ", ".join(sorted(TODO_CONTINUATION_POLICY_VALUES))
        )
    if normalized_continuation_policy:
        fields.append(
            "continuation_policy="
            f"{encode_metadata_value(normalized_continuation_policy)}"
        )
    normalized_removed_continuation_policy = (
        normalize_removed_todo_continuation_policy(removed_continuation_policy)
    )
    if removed_continuation_policy and not normalized_removed_continuation_policy:
        raise ValueError(
            "removed_continuation_policy must be one of: "
            + ", ".join(sorted(TODO_REMOVED_REVIEW_CONTINUATION_POLICY_VALUES))
        )
    if normalized_continuation_policy and normalized_removed_continuation_policy:
        raise ValueError(
            "continuation_policy and removed_continuation_policy are mutually exclusive"
        )
    if normalized_removed_continuation_policy:
        fields.append(
            "removed_continuation_policy="
            f"{encode_metadata_value(normalized_removed_continuation_policy)}"
        )
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
    normalized_explore_result_node_refs = normalize_explore_result_node_refs(
        explore_result_node_refs
    )
    if explore_result_node_refs and not normalized_explore_result_node_refs:
        raise ValueError(
            "explore_result_node_refs must contain public-safe Explore node ids"
        )
    if normalized_explore_result_node_refs:
        fields.append(
            "explore_result_node_refs="
            f"{encode_metadata_value(','.join(normalized_explore_result_node_refs))}"
        )
    normalized_decision_scope = decision_scope_metadata_value(decision_scope)
    if normalized_decision_scope:
        fields.append(f"decision_scope={encode_metadata_value(normalized_decision_scope)}")
    normalized_required_decision_scopes = required_decision_scopes_metadata_value(required_decision_scopes)
    if normalized_required_decision_scopes:
        fields.append(
            "required_decision_scopes="
            f"{encode_metadata_value(normalized_required_decision_scopes)}"
        )
    normalized_decision_outcome = normalize_todo_decision_outcome(decision_outcome)
    if decision_outcome and not normalized_decision_outcome:
        raise ValueError(
            "decision_outcome must be one of: "
            + ", ".join(sorted(TODO_DECISION_OUTCOME_VALUES))
        )
    if normalized_decision_outcome:
        fields.append(
            f"decision_outcome={encode_metadata_value(normalized_decision_outcome)}"
        )
    normalized_scope_outcomes = decision_scope_outcomes_metadata_value(
        decision_scope_outcomes
    )
    if decision_scope_outcomes and not normalized_scope_outcomes:
        raise ValueError(
            "decision_scope_outcomes must contain outcome, decision_scope, and "
            "source_todo_id"
        )
    if normalized_scope_outcomes:
        fields.append(
            "decision_scope_outcomes="
            f"{encode_metadata_value(normalized_scope_outcomes)}"
        )
    normalized_claimed_by = normalize_todo_claimed_by(claimed_by)
    if claimed_by and not normalized_claimed_by:
        raise ValueError("claimed_by must be a public-safe agent token such as codex-main-control")
    if normalized_claimed_by:
        fields.append(f"claimed_by={encode_metadata_value(normalized_claimed_by)}")
    normalized_bound_agent = normalize_todo_bound_agent(bound_agent)
    if bound_agent and not normalized_bound_agent:
        raise ValueError("bound_agent must be a public-safe agent token such as codex-main-control")
    if normalized_bound_agent:
        fields.append(f"bound_agent={encode_metadata_value(normalized_bound_agent)}")
    if goal_bound is not None:
        fields.append(f"goal_bound={encode_metadata_value('true' if goal_bound else 'false')}")
    normalized_blocks_agent = normalize_todo_blocks_agent(blocks_agent)
    if blocks_agent and not normalized_blocks_agent:
        raise ValueError("blocks_agent must be a public-safe agent token such as codex-side-bypass")
    if normalized_blocks_agent:
        fields.append(f"blocks_agent={encode_metadata_value(normalized_blocks_agent)}")
    normalized_excluded_agents = require_todo_excluded_agents(excluded_agents)
    if normalized_claimed_by and normalized_claimed_by in normalized_excluded_agents:
        raise ValueError(
            f"claimed_by={normalized_claimed_by!r} cannot also appear in excluded_agents"
        )
    if normalized_excluded_agents:
        fields.append(
            "excluded_agents="
            f"{encode_metadata_value(','.join(normalized_excluded_agents))}"
        )
    if global_gate is not None:
        fields.append(f"global_gate={encode_metadata_value('true' if global_gate else 'false')}")
    normalized_unblocks_todo_id = normalize_todo_id(unblocks_todo_id)
    if unblocks_todo_id and not normalized_unblocks_todo_id:
        raise ValueError("unblocks_todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
    if normalized_unblocks_todo_id:
        fields.append(f"unblocks_todo_id={encode_metadata_value(normalized_unblocks_todo_id)}")
    normalized_successor_todo_ids = normalize_todo_id_list(successor_todo_ids)
    if successor_todo_ids and not normalized_successor_todo_ids:
        raise ValueError("successor_todo_ids must contain public todo_<letters-digits-underscore-hyphen> tokens")
    if normalized_successor_todo_ids:
        fields.append(
            "successor_todo_ids="
            f"{encode_metadata_value(','.join(normalized_successor_todo_ids))}"
        )
    normalized_resume_when = normalize_todo_resume_when(resume_when)
    if resume_when and not normalized_resume_when:
        raise ValueError("resume_when must be public-safe, e.g. todo_done:todo_ab12cd34ef56 or pr_merged:#532")
    if normalized_resume_when:
        fields.append(f"resume_when={encode_metadata_value(normalized_resume_when)}")
    if no_followup is not None:
        fields.append(f"no_followup={encode_metadata_value('true' if no_followup else 'false')}")
    for key, value in (
        ("target_key", target_key),
        ("cadence", cadence),
        ("next_due_at", next_due_at),
        ("expires_at", expires_at),
        ("last_checked_at", last_checked_at),
        ("result_hash", result_hash),
        ("consecutive_no_change", consecutive_no_change),
        ("material_change", material_change),
        ("max_no_change_before_replan", max_no_change_before_replan),
    ):
        if value:
            fields.append(f"{key}={encode_metadata_value(value)}")
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


def todo_block_metadata(block: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in TODO_METADATA_FIELDS:
        value = block.get(key)
        if value is None:
            continue
        normalized: Any
        if key == "required_write_scopes":
            normalized = normalize_required_write_scopes(value)
        elif key == "task_repository":
            normalized = normalize_todo_task_repository(value)
        elif key == "required_capabilities":
            normalized = normalize_required_capabilities(value)
        elif key == "target_capabilities":
            normalized = normalize_target_capabilities(value)
        elif key == "excluded_agents":
            normalized = normalize_todo_excluded_agents(value)
        elif key == "explore_result_node_refs":
            normalized = normalize_explore_result_node_refs(value)
        elif key == "continuation_policy":
            normalized = normalize_todo_continuation_policy(value)
        elif key == "decision_scope":
            normalized = normalize_todo_decision_scope(value)
        elif key == "required_decision_scopes":
            normalized = normalize_todo_required_decision_scopes(value)
        elif key == "decision_outcome":
            normalized = normalize_todo_decision_outcome(value)
        elif key == "decision_scope_outcomes":
            normalized = normalize_todo_decision_scope_outcomes(value)
        elif key == "no_followup":
            normalized = normalize_todo_no_followup(value)
        elif key in {"global_gate", "goal_bound"}:
            normalized = normalize_todo_global_gate(value)
        else:
            normalized = str(value).strip()
        if normalized is not None and normalized != [] and normalized != "":
            metadata[key] = normalized
    return metadata


def metadata_line_for_todo_block(
    block: dict[str, Any],
    updates: dict[str, Any],
) -> str | None:
    metadata = todo_block_metadata(block)
    for key, value in updates.items():
        if key not in TODO_METADATA_FIELDS:
            continue
        if value is None:
            metadata.pop(key, None)
        elif key == "required_write_scopes":
            normalized = normalize_required_write_scopes(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "task_repository":
            normalized = normalize_todo_task_repository(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "required_capabilities":
            normalized = normalize_required_capabilities(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "target_capabilities":
            normalized = normalize_target_capabilities(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "excluded_agents":
            normalized = normalize_todo_excluded_agents(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "explore_result_node_refs":
            normalized = normalize_explore_result_node_refs(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "continuation_policy":
            normalized = normalize_todo_continuation_policy(value)
            if normalized:
                metadata[key] = normalized
            elif value:
                raise ValueError(
                    "todo continuation_policy must be one of: "
                    + ", ".join(sorted(TODO_CONTINUATION_POLICY_VALUES))
                )
            else:
                metadata.pop(key, None)
        elif key == "decision_scope":
            metadata[key] = require_todo_decision_scope(value)
        elif key == "required_decision_scopes":
            normalized = require_todo_required_decision_scopes(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "decision_outcome":
            metadata[key] = require_todo_decision_outcome(value)
        elif key == "decision_scope_outcomes":
            normalized_scope_outcomes = normalize_todo_decision_scope_outcomes(value)
            if normalized_scope_outcomes:
                metadata[key] = normalized_scope_outcomes
            else:
                metadata.pop(key, None)
        elif key == "no_followup":
            normalized = normalize_todo_no_followup(value)
            if normalized is not None:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key == "successor_todo_ids":
            normalized = normalize_todo_id_list(value)
            if normalized:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif key in {"global_gate", "goal_bound"}:
            normalized = normalize_todo_global_gate(value)
            if normalized is not None:
                metadata[key] = normalized
            else:
                metadata.pop(key, None)
        elif str(value).strip():
            metadata[key] = str(value).strip()
    if "todo_id" not in metadata and block.get("todo_id"):
        metadata["todo_id"] = str(block["todo_id"])
    if "status" not in metadata:
        metadata["status"] = TODO_STATUS_DONE if block.get("done") else TODO_STATUS_OPEN
    return format_todo_metadata_line(**metadata)


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
