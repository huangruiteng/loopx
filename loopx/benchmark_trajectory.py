from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any


PUBLIC_TRAJECTORY_SUMMARY_SCHEMA_VERSION = "public_trajectory_summary_v0"

SANDBOX_PATH_RE = re.compile(r"/(?:app|root|workspace|tmp)/[A-Za-z0-9_./-]+")
LOOPX_CLI_RE = re.compile(r"(?:^|\s)loopx(?:\s|$)")
SHELL_EDIT_RE = re.compile(
    r"(?i)(?:apply_patch|perl\b.*\s-[0-9a-z]*p|sed\b.*\s-i|"
    r"python\b[\s\S]*(?:write_text|open\(.+['\"]w|Path\(.+\)\.write)|"
    r"(?:^|\s)(?:tee|cat)\s*>|(?:^|\s)(?:mv|cp)\s+)"
)
SHELL_READ_RE = re.compile(
    r"(?i)(?:^|\s)(?:cat|sed|grep|rg|head|tail|less)\b|"
    r"python\b[\s\S]*(?:read_text|open\(.+['\"]r)"
)
PROTECTED_DIRECTIVE_RE = re.compile(
    r"(?i)(?:do\s+not|don't|must\s+not|never|禁止|不要|不得|别).{0,120}"
    r"(?:modify|edit|change|write|touch|修改|编辑|改动|写)"
)
LOOPX_ACTIVE_STATE_BASENAME = "ACTIVE_GOAL_STATE.md"

LOOPX_READ_COMMANDS = {
    "check",
    "history",
    "quota",
    "read-only-map",
    "review-packet",
    "status",
}
LOOPX_WRITE_COMMANDS = {
    "archive-runtime",
    "configure-goal",
    "connect",
    "import-doc-registry-authority",
    "operator-gate",
    "refresh-state",
    "register-authority-source",
    "reward",
    "sync-global",
}
LOOPX_TODO_WRITE_ACTIONS = {
    "add",
    "archive-completed",
    "complete",
    "supersede",
    "update",
}
LOOPX_BENCHMARK_WRITE_ACTIONS = {
    "run-ledger-upsert",
}
LOOPX_CONTEXT_COMMANDS = {
    ("which", "goal"),
}


def _top_counts(counter: dict[str, int], *, limit: int = 12) -> dict[str, int]:
    return {
        key: count
        for key, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
        if count > 0
    }


def _tool_title_kind(title: str) -> str:
    text = " ".join(str(title or "").strip().split())
    if not text:
        return "unknown"
    lower = text.lower()
    if LOOPX_CLI_RE.search(text):
        return "loopx_cli"
    if lower.startswith("read "):
        return "read_file"
    if lower.startswith("search "):
        return "search"
    if lower.startswith("list "):
        return "list"
    if lower == "pwd" or lower.startswith("pwd "):
        return "pwd"
    if lower.startswith("python -m py_compile"):
        return "python_py_compile"
    if lower.startswith("python"):
        return "python"
    if lower.startswith("pytest"):
        return "pytest"
    if lower.startswith("git "):
        return "git"
    if SHELL_EDIT_RE.search(text):
        return "shell_edit"
    return lower.split()[0][:40]


def _tool_action_category(kind: str) -> str:
    if kind == "loopx_cli":
        return "loopx_cli"
    if kind == "shell_edit":
        return "edit"
    if kind in {"python_py_compile", "pytest"}:
        return "validation"
    if kind in {"read_file", "search", "list", "pwd"}:
        return "inspection"
    if kind == "python":
        return "execution"
    if kind == "git":
        return "vcs"
    if kind == "unknown":
        return "unknown"
    return "tool_other"


def normalized_loopx_cli_call(
    title: str,
    *,
    round_index: int,
) -> dict[str, Any]:
    text = " ".join(str(title or "").strip().split())
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    command_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if token == "loopx" or token.endswith("/loopx")
        ),
        -1,
    )
    after = tokens[command_index + 1 :] if command_index >= 0 else []
    subcommands: list[str] = []
    flags: list[str] = []
    for token in after:
        if token.startswith("--"):
            flags.append(token.split("=", 1)[0][:60])
            continue
        if token.startswith("-"):
            flags.append(token[:20])
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$", token):
            subcommands.append(token)
            if len(subcommands) >= 2:
                break
    command = " ".join(["loopx", *subcommands])
    return {
        "round": max(1, round_index),
        "command": command,
        "subcommands": subcommands,
        "flags": sorted(set(flags))[:8],
        "raw_title_copied": False,
        "raw_output_copied": False,
    }


def loopx_cli_state_usage(call: dict[str, Any]) -> str:
    subcommands = call.get("subcommands")
    if not isinstance(subcommands, list):
        subcommands = []
    normalized = tuple(
        str(item)
        for item in subcommands[:2]
        if isinstance(item, str) and item.strip()
    )
    if normalized in LOOPX_CONTEXT_COMMANDS:
        return "context_lookup"
    primary = normalized[0] if normalized else ""
    secondary = normalized[1] if len(normalized) > 1 else ""
    if primary == "todo":
        return "state_write" if secondary in LOOPX_TODO_WRITE_ACTIONS else "state_read"
    if primary == "benchmark" and secondary in LOOPX_BENCHMARK_WRITE_ACTIONS:
        return "state_write"
    if primary in LOOPX_WRITE_COMMANDS:
        return "state_write"
    if primary in LOOPX_READ_COMMANDS:
        return "state_read"
    return "other"


def sandbox_paths(text: str) -> list[str]:
    paths: set[str] = set()
    for match in SANDBOX_PATH_RE.findall(text or ""):
        clean = match.rstrip(".,:;)`]")
        if clean:
            paths.add(clean)
    return sorted(paths)


def loopx_case_state_paths(paths: list[str]) -> list[str]:
    case_state_paths: list[str] = []
    for path in paths:
        basename = path.rsplit("/", 1)[-1]
        if basename == LOOPX_ACTIVE_STATE_BASENAME and "/.codex/goals/" in path:
            case_state_paths.append(path)
    return sorted(set(case_state_paths))


def protected_paths_from_instruction(text: str) -> list[str]:
    protected: set[str] = set()
    for chunk in re.split(r"(?<=[A-Za-z0-9_)\]])\.\s+|[\n。!?；;]+", text or ""):
        if PROTECTED_DIRECTIVE_RE.search(chunk):
            protected.update(sandbox_paths(chunk))
    return sorted(protected)


def summarize_public_acp_trajectory(
    path: Path,
    *,
    schema_version: str = PUBLIC_TRAJECTORY_SUMMARY_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Reduce an ACP trajectory to public-safe counters only.

    The reducer intentionally copies no raw task text, verifier output, tool
    output, prompts, or trajectory body. It keeps only counts, normalized
    command labels, sandbox-path signals, and coarse action/state categories.
    """

    event_count = 0
    round_index = 0
    type_counts: dict[str, int] = {}
    tool_kind_counts: dict[str, int] = {}
    tool_status_counts: dict[str, int] = {}
    action_category_counts: dict[str, int] = {}
    round_action_category_counts: dict[str, dict[str, int]] = {}
    path_mentions: dict[str, int] = {}
    path_edit_signals: dict[str, int] = {}
    path_first_edit_round: dict[str, int] = {}
    protected_paths: set[str] = set()
    protected_path_edit_rounds: dict[str, list[int]] = {}
    loopx_cli_rounds: list[int] = []
    loopx_cli_calls: list[dict[str, Any]] = []
    loopx_cli_call_count = 0
    loopx_state_usage_counts: dict[str, int] = {}
    loopx_case_state_read_count = 0
    loopx_case_state_write_count = 0
    loopx_case_state_paths_seen: set[str] = set()
    user_message_count = 0
    agent_message_count = 0
    tool_call_count = 0

    with path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_count += 1
            event_type = str(event.get("type") or "unknown")
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

            text = str(event.get("text") or "")
            title = str(event.get("title") or "")
            status = str(event.get("status") or "")
            searchable = " ".join(part for part in (title, text) if part)

            if event_type == "user_message":
                user_message_count += 1
                round_index += 1
                protected_paths.update(protected_paths_from_instruction(text))
            elif event_type == "agent_message":
                agent_message_count += 1
            elif event_type == "tool_call":
                tool_call_count += 1
                kind = _tool_title_kind(title)
                category = _tool_action_category(kind)
                current_round = max(1, round_index)
                round_key = str(current_round)
                tool_kind_counts[kind] = tool_kind_counts.get(kind, 0) + 1
                action_category_counts[category] = (
                    action_category_counts.get(category, 0) + 1
                )
                round_counts = round_action_category_counts.setdefault(round_key, {})
                round_counts[category] = round_counts.get(category, 0) + 1
                if status:
                    tool_status_counts[status] = tool_status_counts.get(status, 0) + 1
                if kind == "loopx_cli":
                    loopx_cli_call_count += 1
                    if current_round not in loopx_cli_rounds:
                        loopx_cli_rounds.append(current_round)
                    call = normalized_loopx_cli_call(
                        title,
                        round_index=current_round,
                    )
                    usage = loopx_cli_state_usage(call)
                    loopx_state_usage_counts[usage] = (
                        loopx_state_usage_counts.get(usage, 0) + 1
                    )
                    if len(loopx_cli_calls) < 8:
                        call["state_usage"] = usage
                        loopx_cli_calls.append(call)

            paths = sandbox_paths(searchable)
            case_state_paths = loopx_case_state_paths(paths)
            loopx_case_state_paths_seen.update(case_state_paths)
            for sandbox_path in paths:
                path_mentions[sandbox_path] = path_mentions.get(sandbox_path, 0) + 1

            if event_type == "tool_call" and case_state_paths:
                if SHELL_READ_RE.search(title):
                    loopx_case_state_read_count += len(case_state_paths)
                if SHELL_EDIT_RE.search(title):
                    loopx_case_state_write_count += len(case_state_paths)

            if event_type == "tool_call" and SHELL_EDIT_RE.search(title):
                current_round = max(1, round_index)
                for sandbox_path in paths:
                    path_edit_signals[sandbox_path] = path_edit_signals.get(sandbox_path, 0) + 1
                    path_first_edit_round.setdefault(sandbox_path, current_round)
                    if sandbox_path in protected_paths:
                        protected_path_edit_rounds.setdefault(sandbox_path, [])
                        if current_round not in protected_path_edit_rounds[sandbox_path]:
                            protected_path_edit_rounds[sandbox_path].append(current_round)

    return {
        "schema_version": schema_version,
        "schema_family": PUBLIC_TRAJECTORY_SUMMARY_SCHEMA_VERSION,
        "summary_publicness": (
            "public_counts_only_no_raw_task_text_no_verifier_output_no_trajectory_body"
        ),
        "private_trajectory_present": True,
        "raw_text_copied_to_public": False,
        "raw_task_text_copied_to_public": False,
        "raw_verifier_output_copied_to_public": False,
        "host_path_recorded": False,
        "artifact_basename": path.name,
        "event_count": event_count,
        "round_count": round_index,
        "user_message_count": user_message_count,
        "agent_message_count": agent_message_count,
        "tool_call_count": tool_call_count,
        "event_type_counts": _top_counts(type_counts, limit=8),
        "tool_title_kind_counts": _top_counts(tool_kind_counts, limit=12),
        "tool_status_counts": _top_counts(tool_status_counts, limit=8),
        "action_category_counts": _top_counts(action_category_counts, limit=12),
        "round_action_category_counts": {
            round_key: _top_counts(counts, limit=12)
            for round_key, counts in sorted(
                round_action_category_counts.items(),
                key=lambda item: int(item[0]),
            )[:12]
        },
        "loopx_cli_call_count": loopx_cli_call_count,
        "loopx_cli_call_rounds": loopx_cli_rounds[:8],
        "loopx_cli_calls": loopx_cli_calls,
        "loopx_cli_state_usage_counts": _top_counts(
            loopx_state_usage_counts,
            limit=8,
        ),
        "loopx_cli_state_read_count": loopx_state_usage_counts.get(
            "state_read",
            0,
        ),
        "loopx_cli_state_write_count": loopx_state_usage_counts.get(
            "state_write",
            0,
        ),
        "loopx_case_state_path_count": len(loopx_case_state_paths_seen),
        "loopx_case_state_paths": sorted(loopx_case_state_paths_seen)[:4],
        "loopx_case_state_read_count": loopx_case_state_read_count,
        "loopx_case_state_write_count": loopx_case_state_write_count,
        "sandbox_path_mention_counts": _top_counts(path_mentions, limit=12),
        "sandbox_path_edit_signal_counts": _top_counts(path_edit_signals, limit=12),
        "sandbox_path_first_edit_round": {
            path: path_first_edit_round[path]
            for path in sorted(path_first_edit_round)[:12]
        },
        "protected_path_mention_count": len(protected_paths),
        "protected_path_mentions": sorted(protected_paths)[:12],
        "protected_path_edit_signal_count": sum(
            len(rounds) for rounds in protected_path_edit_rounds.values()
        ),
        "protected_path_edit_rounds": {
            path: rounds[:8]
            for path, rounds in sorted(protected_path_edit_rounds.items())[:12]
        },
    }
