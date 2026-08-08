from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .opencode_goal_mode import plugin_source, runtime_source
from .pi_goal_mode import extension_source as pi_extension_source
from .pi_goal_mode import runtime_source as pi_runtime_source
from .slash_commands import build_slash_command_catalog

SCHEMA_VERSION = "loopx_slash_command_install_v0"
MANAGED_MARKER_PREFIX = "<!-- loopx-managed-slash-command:v1"
LEGACY_UPGRADABLE_SIGNATURES = (
    "loopx goal-mode setup (NOT Claude Code's built-in /goal)",
    "The output is loopx control-plane SETUP",
    "goalmode_cmd.py",
)
EXISTING_LOOPX_CAPABILITY_SKILL_SIGNATURES = (
    "# LoopX PR Review",
    "Run `loopx pr-review` first",
)
OPENCODE_GOAL_DEPENDENCIES = {
    "@opencode-ai/plugin": ">=1.17.15 <2",
    "opencode-goal-plugin": "0.7.0",
}


def _managed_marker(*, command: str, surface: str) -> str:
    return f"{MANAGED_MARKER_PREFIX} command={command} surface={surface} -->"


def _front_matter(*, fields: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        escaped = value.replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def _skill_body(
    *,
    command: str,
    title: str,
    description: str,
    argument_hint: str,
    instructions: list[str],
    surface: str,
    front_matter_name: str | None = None,
) -> str:
    fields = {
        "description": description,
        "argument-hint": argument_hint,
    }
    if front_matter_name:
        fields = {"name": front_matter_name, **fields}
    surface_label = "slash command" if surface == "claude-skills" else "explicit LoopX command skill"
    return "\n\n".join(
        [
            _front_matter(fields=fields),
            _managed_marker(command=command, surface=surface),
            f"# {title}",
            f"Treat this as the LoopX `{command}` {surface_label}.",
            "\n".join(instructions),
            "Keep public/private boundaries intact and do not perform external writes unless the active LoopX state or owner explicitly authorizes them.",
        ]
    ) + "\n"


def _openai_skill_metadata(*, command: str, display_name: str, short_description: str) -> str:
    return "\n".join(
        [
            f"# {_managed_marker(command=command, surface='codex-skill-metadata')}",
            "interface:",
            f'  display_name: "{display_name}"',
            f'  short_description: "{short_description}"',
            "policy:",
            "  allow_implicit_invocation: false",
            "",
        ]
    )


def _opencode_command_body(spec: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            _front_matter(
                fields={
                    "description": str(spec["description"]),
                    "agent": "build",
                }
            ),
            _managed_marker(command=str(spec["command"]), surface="opencode-command"),
            f"Treat this as the LoopX `{spec['command']}` OpenCode command.",
            (
                "The exact current host is OpenCode. For goal start, pass "
                "`--host-surface opencode` and use `loopx_goal_activate` from the "
                "returned host-loop activation packet."
            ),
            "\n".join(str(item) for item in spec["instructions"]),
            (
                "Keep public/private boundaries intact and do not perform external "
                "writes unless the active LoopX state or owner explicitly authorizes them."
            ),
        ]
    ) + "\n"


def _command_prompt_specs(*, cli_bin: str, include_legacy_aliases: bool) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "command": "/loopx",
            "name": "loopx",
            "description": "Inspect LoopX state, or start concrete project work when arguments are provided.",
            "argument_hint": "[--capability-route issue-fix] [task text]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                "Before start-goal, identify the exact current host: use `codex-app` for the desktop app with automation tools, `codex-app-ssh` for the desktop app over SSH without automation tools, `codex-ide-plugin` only for the IDE plugin, `codex-cli-tui` for the terminal TUI, `opencode` for OpenCode, `traex-cli` for the TraeX terminal TUI, `pi` for Pi, `gemini-cli` for the Gemini CLI, `cursor-agent` for the Cursor agent CLI, or `ark-managed-agent` for Ark Managed Agent.",
                f"If arguments are present, parse only an optional leading `--capability-route issue-fix` as an explicit product-route switch, remove that prefix from the task text, and pass it to `{cli_bin} start-goal --guided --project . --goal-text \"<remaining exact arguments>\" --host-surface <exact-current-host>`. Without that switch, preserve all arguments as task text and do not add a capability route. Never infer a route from issue/PR wording or URLs. If the host is unclear, omit the host flag once and follow the returned host-surface selection gate.",
                f"Treat the returned `ordered_steps` as a required transaction. On first connection, run its bootstrap command and resolve the returned agent-identity gate before planning; a stable unbound host thread is a new session and defaults to fresh registration. Then plan and execute at least one business `{cli_bin} todo add` derived from `$ARGUMENTS` before substantive task work. Encode priority in the todo text such as `[P0]`; `{cli_bin} todo add` has no `--priority` flag. Do not continue until LoopX status shows that business Agent Todo.",
                f"If `selected_capability_route` is present, run its entry and admission commands before substantive implementation, and treat `{cli_bin} capability show <capability-id> --format json` as the authoritative later-transition command surface. Use capability-owned commands for listed external transitions instead of substituting provider CLIs. Keep capability facts in capability-owned state; generic Todos remain scheduling records.",
                f"Before dependent work, persist material scope, acceptance, or non-goal changes in current Todo evidence and the next executable Todo; then run `{cli_bin} refresh-state` and verify quota readback. Chat/model summaries are not durable state.",
                f"If that packet exposes a goal-selection gate, rerun one exact choice before any mutation. Resolve agent identity in this order: reuse the packet's verified thread binding; otherwise reuse the exact agent id already named by this host task's active LoopX interaction contract or heartbeat; otherwise treat a stable unbound host thread as a new session and follow the packet's fresh-registration default. Select an existing registered lane only for explicit takeover, then complete the returned bind/readback step. Codex App `start-goal` automatically reads its stable ambient thread id when available. Never treat a new Todo, worktree, or argument-bearing invocation as a new peer by itself, and never infer identity from registry order. When no stable thread id is available, fresh registration requires explicit new-peer/session intent and `--new-peer`. Preview `{cli_bin} register-agent --goal-id <selected-goal-id> --agent-id <new-agent-id> --require-new`, then apply with `--execute` and continue only when the result reports `ok=true`, `changed=true`, `written=true`, successful global sync, and verified registration readback. Rerun start-goal with the verified `--agent-id` before todo writeback.",
                f"If arguments are empty and the host task already identifies an active LoopX goal, run its exact CLI `interaction_contract` or quota command first; do not call `start-goal` or bootstrap another goal. Only when no active goal contract is present, inspect `{cli_bin} bootstrap-command-pack --project .`, `{cli_bin} status`, and `{cli_bin} slash-commands` before changing files.",
                f"Use `{cli_bin} agent-onboard --list-agent-types` when the host runtime is unclear; pass an exact type such as `codex-app`, `codex-app-ssh`, `codex-ide-plugin`, `codex-cli`, `claude-code`, `opencode`, `traex-cli`, `pi`, or `ark-managed-agent`, never ambiguous `codex`.",
                f"Do not configure optional features during first-run. Only when the task needs bounded child agents or Explore, inspect `{cli_bin} configure-goal --goal-id <resolved-goal-id>` and its `configuration_catalog`; preview before explicit apply and never auto-enable a feature merely because it exists.",
                "When project work is started, plan ordered P0/P1/P2 todos, write them through LoopX todo state, refresh state, activate the host loop if missing/stale, run quota, and complete one bounded delivery segment through validation plus LoopX writeback or an exact blocker; do not return merely after setup, planning, or claim.",
                "Host loop activation means Codex App heartbeat automation; Codex App over SSH, the Codex IDE plugin, or CLI visible `/goal <task_body>`; Claude Code native `/loop`; OpenCode `loopx_goal_activate`; TraeX visible `/goal <task_body>`; Ark Managed Agent one-shot Goal submission; or a custom host-loop gate from `loopx agent-onboard`.",
                "If this session cannot mutate the host loop surface, surface the exact pasteable gate instead of saying LoopX is autonomously connected.",
            ],
        },
        {
            "command": "/loopx-global-summary",
            "name": "loopx-global-summary",
            "description": "Read the compact global LoopX progress digest.",
            "argument_hint": "[optional focus]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                f"Run `{cli_bin} global-summary` first and summarize visible projects, gates, monitor status, and next safe actions.",
                "This command is read-only unless the user explicitly asks for a state update.",
            ],
        },
        {
            "command": "/loopx-global-gates",
            "name": "loopx-global-gates",
            "description": "List open LoopX user/controller gates and what each blocks.",
            "argument_hint": "[optional focus]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                f"Run `{cli_bin} global-summary` first, then focus the answer on open gates, blocked work, owner decisions, and exact next questions.",
                "This command is read-only unless the user explicitly asks for a state update.",
            ],
        },
        {
            "command": "/loopx-global-todos",
            "name": "loopx-global-todos",
            "description": "List runnable, blocked, deferred-ready, and review LoopX todos across visible projects.",
            "argument_hint": "[optional focus]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                f"Run `{cli_bin} global-summary` first, then focus the answer on prioritized todos and ownership across visible projects.",
                "This command is read-only unless the user explicitly asks for a state update.",
            ],
        },
        {
            "command": "/loopx-global-risks",
            "name": "loopx-global-risks",
            "description": "Show stale LoopX runs, boundary risks, failing checks, and rollback candidates.",
            "argument_hint": "[optional focus]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                f"Run `{cli_bin} global-summary` first, then focus the answer on stale work, public/private boundary risks, failing checks, and rollback candidates.",
                "This command is read-only unless the user explicitly asks for a state update.",
            ],
        },
        {
            "command": "/loopx-pr-review",
            "name": "loopx-pr-review",
            "description": "Run the LoopX PR-review packet first, then review selected PR groups with evidence.",
            "argument_hint": "[--repo owner/repo] [--state open|merged|all] [--since ISO]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                "Use the installed `loopx-pr-review` skill when available.",
                f"Run `{cli_bin} --format json pr-review $ARGUMENTS` first and keep `agent_response_contract.review_execution_contract`, `review_groups`, `pull_requests[].review_plan`, `pull_requests[].review_template`, and `pull_requests[].evidence_commands` visible.",
                "Do not reconstruct the PR queue manually from ad hoc GitHub calls before reading the LoopX packet.",
                "This command is read-only; do not comment, approve, merge, rerun CI, or spend quota unless separately authorized.",
            ],
        },
    ]
    if include_legacy_aliases:
        legacy_specs = []
        for canonical in specs:
            name = canonical["name"]
            if not str(name).startswith("loopx-global-"):
                continue
            legacy_name = str(name).replace("loopx-global-", "loop-global-", 1)
            legacy_specs.append(
                {
                    **canonical,
                    "command": "/" + legacy_name,
                    "name": legacy_name,
                    "description": canonical["description"] + " Legacy alias for the canonical /loopx-global-* command.",
                }
            )
        specs.extend(legacy_specs)
    return specs


def _command_skill_content(spec: dict[str, Any], *, surface: str) -> str:
    return _skill_body(
        command=str(spec["command"]),
        title=f"LoopX {spec['command']}",
        description=str(spec["description"]),
        argument_hint=str(spec["argument_hint"]),
        instructions=list(spec["instructions"]),
        surface=surface,
        front_matter_name=str(spec["name"]),
    )


def materialize_loopx_entry_skill(
    *,
    skills_dir: Path,
    execute: bool,
    cli_bin: str = "loopx",
    host_surface: str | None = None,
) -> dict[str, Any]:
    """Materialize the generated ``$loopx`` entry skill into a host skill root."""

    if host_surface not in {None, "ark-managed-agent"}:
        raise ValueError(f"unsupported fixed LoopX entry host surface: {host_surface}")
    spec = next(
        item
        for item in _command_prompt_specs(
            cli_bin=cli_bin,
            include_legacy_aliases=False,
        )
        if item["name"] == "loopx"
    )
    if host_surface:
        instructions = list(spec["instructions"])
        instructions[1] = (
            "This entry skill is installed for the exact current host "
            f"`{host_surface}`; do not infer or substitute another host surface."
        )
        instructions[2] = (
            f"If arguments are present, parse only an optional leading "
            "`--capability-route issue-fix` as an explicit product-route switch, "
            "remove that prefix from the task text, and pass it to "
            f'`{cli_bin} start-goal --guided --project . --goal-text "<remaining exact arguments>" '
            f"--host-surface {host_surface}`. Without that switch, preserve all "
            "arguments as task text and do not add a capability route. Never infer "
            "a route from issue/PR wording or URLs."
        )
        spec = {**spec, "instructions": instructions}
    skill_path = skills_dir / "loopx" / "SKILL.md"
    content = _command_skill_content(spec, surface="codex-skills")
    return {
        "skill_id": "loopx",
        "path": str(skill_path),
        "status": _target_status(skill_path, content, execute=execute),
    }


def _is_legacy_upgradable_loopx_file(existing: str) -> bool:
    return any(signature in existing for signature in LEGACY_UPGRADABLE_SIGNATURES)


def _is_existing_loopx_capability_skill(existing: str) -> bool:
    return any(signature in existing for signature in EXISTING_LOOPX_CAPABILITY_SKILL_SIGNATURES)


def _target_status(path: Path, content: str, *, execute: bool) -> str:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if MANAGED_MARKER_PREFIX not in existing:
            if _is_legacy_upgradable_loopx_file(existing):
                if execute:
                    path.write_text(content, encoding="utf-8")
                return "upgraded_legacy_managed"
            if path.name == "SKILL.md" and _is_existing_loopx_capability_skill(existing):
                return "preserved_existing_loopx_skill"
            return "skipped_user_file"
        if existing == content:
            return "unchanged"
        if execute:
            path.write_text(content, encoding="utf-8")
        return "updated"
    if execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return "created" if execute else "would_create"


def _retire_managed_file(path: Path, *, execute: bool) -> str | None:
    if not path.exists():
        return None
    existing = path.read_text(encoding="utf-8")
    if MANAGED_MARKER_PREFIX not in existing:
        return "skipped_user_file"
    if execute:
        path.unlink()
    return "retired_managed_file" if execute else "would_retire_managed_file"


def _retire_status(path: Path, *, execute: bool) -> str:
    return _retire_managed_file(path, execute=execute) or "absent"


def _codex_home(value: str | None = None) -> Path:
    raw = value or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return Path(raw).expanduser()


def _claude_home(value: str | None = None) -> Path:
    raw = value or os.environ.get("CLAUDE_HOME") or str(Path.home() / ".claude")
    return Path(raw).expanduser()


def _gemini_home(value: str | None = None) -> Path:
    """Gemini CLI reads user skills from GEMINI_HOME/skills (default ~/.gemini)."""
    raw = value or os.environ.get("GEMINI_HOME") or str(Path.home() / ".gemini")
    return Path(raw).expanduser()


def _cursor_home(value: str | None = None) -> Path:
    """Cursor CLI reads MCP servers from CURSOR_HOME/mcp.json (default ~/.cursor)."""
    raw = value or os.environ.get("CURSOR_HOME") or str(Path.home() / ".cursor")
    return Path(raw).expanduser()


def _opencode_home(value: str | None = None) -> Path:
    raw = value or os.environ.get("OPENCODE_CONFIG_DIR")
    if not raw:
        config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        raw = str(Path(config_home) / "opencode")
    return Path(raw).expanduser()


def _strip_jsonc_comments(content: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(content):
        char = content[index]
        next_char = content[index + 1] if index + 1 < len(content) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            output.extend((" ", " "))
            index += 2
            while index < len(content) and content[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if char == "/" and next_char == "*":
            output.extend((" ", " "))
            index += 2
            while index < len(content):
                if index + 1 < len(content) and content[index : index + 2] == "*/":
                    output.extend((" ", " "))
                    index += 2
                    break
                output.append("\n" if content[index] == "\n" else " ")
                index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _strip_jsonc_trailing_commas(content: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(content):
        char = content[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(content) and content[lookahead].isspace():
                lookahead += 1
            if lookahead < len(content) and content[lookahead] in "]}":
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def _opencode_plugin_name(plugin: Any) -> str | None:
    if isinstance(plugin, str):
        return plugin
    if (
        isinstance(plugin, list)
        and plugin
        and isinstance(plugin[0], str)
    ):
        return plugin[0]
    return None


def _opencode_direct_goal_plugin_conflicts(root: Path) -> tuple[list[str], list[str]]:
    conflicts: list[str] = []
    invalid: list[str] = []
    goal_plugins = {
        "opencode-goal-plugin",
        "@heimoshuiyu/opencode-goal-plugin",
        "@prevalentware/opencode-goal-plugin",
    }
    for name in ("opencode.json", "opencode.jsonc"):
        path = root / name
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix == ".jsonc":
                content = _strip_jsonc_trailing_commas(_strip_jsonc_comments(content))
            payload = json.loads(content)
        except (json.JSONDecodeError, OSError):
            invalid.append(str(path))
            continue
        if not isinstance(payload, dict):
            invalid.append(str(path))
            continue
        plugins = payload.get("plugin") or []
        if isinstance(plugins, str):
            plugins = [plugins]
        if not isinstance(plugins, list):
            invalid.append(str(path))
            continue
        plugin_names = [
            name
            for plugin in plugins
            if (name := _opencode_plugin_name(plugin)) is not None
        ]
        if any(
            plugin == package or plugin.startswith(f"{package}@")
            for plugin in plugin_names
            for package in goal_plugins
        ):
            conflicts.append(str(path))
    return conflicts, invalid


def _target_package_dependencies(
    path: Path,
    dependencies: dict[str, str],
    *,
    execute: bool,
) -> str:
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return "blocked_invalid_user_package_json"
        if not isinstance(payload, dict):
            return "blocked_invalid_user_package_json"
        current = payload.get("dependencies")
        if current is None:
            current = {}
        if not isinstance(current, dict):
            return "blocked_invalid_user_package_json"
        wanted = {**current, **dependencies}
        if wanted == current:
            return "unchanged"
        payload["dependencies"] = wanted
        status = "updated" if execute else "would_update"
    else:
        payload = {"private": True, "dependencies": dependencies}
        status = "created" if execute else "would_create"
    if execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    return status


def _normalize_surfaces(surfaces: list[str] | None) -> list[str]:
    requested = surfaces or ["all"]
    normalized: list[str] = []
    for surface in requested:
        if surface == "all":
            candidates = ["codex", "claude-code", "opencode"]
        elif surface == "codex":
            candidates = ["codex"]
        elif surface in {"codex-app", "codex-app-ssh", "codex-ide-plugin", "codex-ide", "codex-cli"}:
            candidates = ["codex"]
        elif surface in {"gemini-cli", "gemini-code"}:
            candidates = ["gemini"]
        elif surface in {"cursor-agent", "cursor-cli"}:
            candidates = ["cursor"]
        else:
            candidates = [surface]
        for candidate in candidates:
            if candidate not in normalized:
                normalized.append(candidate)
    return normalized


CURSOR_MCP_KEY = "loopx"
CURSOR_MCP_MARKER_NAME = ".loopx-managed-mcp.json"
CURSOR_MCP_MARKER_SCHEMA_VERSION = "loopx_managed_cursor_mcp_v0"


def _loopx_mcp_command() -> tuple[str, str] | None:
    """Interpreter and script for the LoopX stdio MCP server, or None.

    Reuses the Claude adapter's provisioning so all surfaces share one server
    and one `mcp` dependency. Returns None when `mcp` cannot be provisioned —
    the caller records that instead of writing a config that would fail to
    start.
    """
    try:
        from loopx.claude_goal_mode.scripts import install as claude_install
    except ImportError:
        return None
    try:
        script = claude_install._p("mcp", "loopx_mcp.py")
        # Provisioning narrates to stdout ("[deps] creating mcp venv …"), which
        # would land in the middle of `--format json` and make the whole install
        # result unparseable. The narration is still worth keeping — on stderr.
        with contextlib.redirect_stdout(sys.stderr):
            interpreter = claude_install.provision_mcp_python(dry=False)
    except (OSError, ValueError):
        # Provisioning shells out to venv and pip; a failure there means the
        # surface is skipped, never that the whole install run dies.
        return None
    if not interpreter or not Path(script).exists():
        return None
    if not claude_install._has_mcp(interpreter):
        return None
    return str(interpreter), str(script)


def _cursor_mcp_marker_path(cursor_root: Path) -> Path:
    """Sidecar recording the exact `mcp.json` entry LoopX last wrote.

    Markdown surfaces carry `MANAGED_MARKER_PREFIX` inside the file, but
    `mcp.json` belongs to Cursor's schema, so provenance is kept beside it
    rather than smuggled into an entry the host has to parse.
    """
    return cursor_root / CURSOR_MCP_MARKER_NAME


def _read_cursor_mcp_marker(cursor_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            _cursor_mcp_marker_path(cursor_root).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    servers = payload.get("servers")
    return servers if isinstance(servers, dict) else {}


def _write_json_atomic(path: Path, payload: Any) -> None:
    """Replace `path` in one step, so an interrupted run cannot truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, indent=2) + "\n")
        if mode is not None:
            os.chmod(tmp, mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _merge_cursor_mcp(cursor_root: Path, *, uninstall: bool, execute: bool) -> str:
    """Add or remove the `loopx` entry in CURSOR_HOME/mcp.json — and nothing else.

    `mcp.json` is a user-owned file that LoopX did not create, so every path
    here fails closed: an unexpected shape is reported instead of normalized, a
    same-name entry LoopX cannot prove it wrote is left alone, and uninstall
    removes only an entry that still matches what LoopX recorded. Sharing the
    `loopx` name with a user's own server is unlikely but cheap to survive;
    silently replacing that server, or dropping their `mcpServers` list while
    "merging", is not.
    """
    path = cursor_root / "mcp.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return "blocked_invalid_cursor_mcp_json"
    if not isinstance(raw, dict):
        return "blocked_invalid_cursor_mcp_json"
    servers = raw.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        # A list-valued or scalar `mcpServers` is not something to overwrite:
        # either the file follows a shape LoopX does not understand, or it is
        # damaged. Both are the user's to resolve.
        return "blocked_invalid_cursor_mcp_json"

    existing = servers.get(CURSOR_MCP_KEY)
    recorded = _read_cursor_mcp_marker(cursor_root).get(CURSOR_MCP_KEY)
    # Ownership is only demonstrable when the entry still matches what LoopX
    # recorded writing. A hand-edited entry counts as the user's from then on.
    loopx_owned = existing is not None and existing == recorded

    if uninstall:
        if existing is None:
            return "absent"
        if not loopx_owned:
            return "skipped_user_owned_mcp_entry"
        if not execute:
            return "would_retire"
        servers.pop(CURSOR_MCP_KEY, None)
        raw["mcpServers"] = servers
        _write_json_atomic(path, raw)
        _cursor_mcp_marker_path(cursor_root).unlink(missing_ok=True)
        return "retired"

    if existing is not None and not loopx_owned:
        return "skipped_user_owned_mcp_entry"
    if not execute:
        # A dry run must not touch anything: provisioning `mcp` would create a
        # venv on disk during a run whose only job is to report what would happen.
        return "unchanged" if existing is not None else "would_write"
    command = _loopx_mcp_command()
    if command is None:
        return "skipped_mcp_dependency_missing"
    entry = {"command": command[0], "args": [command[1]]}
    if existing == entry:
        return "unchanged"
    servers[CURSOR_MCP_KEY] = entry
    raw["mcpServers"] = servers
    _write_json_atomic(path, raw)
    _write_json_atomic(
        _cursor_mcp_marker_path(cursor_root),
        {
            "schema_version": CURSOR_MCP_MARKER_SCHEMA_VERSION,
            "servers": {CURSOR_MCP_KEY: entry},
        },
    )
    return "written"


def _pi_extension_path(project_root: Path) -> Path:
    return project_root / ".pi" / "extensions" / "loopx-goal.ts"


def _pi_runtime_path(project_root: Path) -> Path:
    return project_root / ".pi" / "extensions" / "pi-goal-loop-runtime.mjs"


def install_slash_commands(
    *,
    execute: bool,
    uninstall: bool = False,
    with_goal_bridge: bool = False,
    surfaces: list[str] | None = None,
    cli_bin: str = "loopx",
    include_legacy_aliases: bool = True,
    codex_home: str | None = None,
    claude_home: str | None = None,
    opencode_home: str | None = None,
    gemini_home: str | None = None,
    cursor_home: str | None = None,
    pi_project: str | None = None,
) -> dict[str, Any]:
    specs = _command_prompt_specs(cli_bin=cli_bin, include_legacy_aliases=include_legacy_aliases)
    effective_surfaces = _normalize_surfaces(surfaces)
    codex_root = _codex_home(codex_home)
    claude_root = _claude_home(claude_home)
    opencode_root = _opencode_home(opencode_home)
    gemini_root = _gemini_home(gemini_home)
    cursor_root = _cursor_home(cursor_home)
    pi_project_root = Path(pi_project or ".").expanduser().resolve()
    installed: list[dict[str, Any]] = []

    if with_goal_bridge and "opencode" not in effective_surfaces:
        installed.append(
            {
                "surface": "opencode",
                "host_surfaces": ["opencode"],
                "mechanism": "opencode_goal_bridge",
                "command": "/goal",
                "path": None,
                "status": "blocked_goal_bridge_requires_opencode_surface",
                "invoke_as": [],
                "reason": "Select --surface opencode when using --with-goal-bridge.",
            }
        )

    if "codex" in effective_surfaces:
        prompt_dir = codex_root / "prompts"
        for spec in specs:
            prompt_path = prompt_dir / f"{spec['name']}.md"
            if uninstall:
                retire_status = _retire_status(prompt_path, execute=execute)
                installed.append(
                    {
                        "surface": "codex",
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                        "mechanism": "retired_codex_custom_prompt",
                        "command": spec["command"],
                        "path": str(prompt_path),
                        "status": retire_status,
                        "invoke_as": [],
                    }
                )
                continue
            retire_status = _retire_managed_file(prompt_path, execute=execute)
            if retire_status:
                installed.append(
                    {
                        "surface": "codex",
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                        "mechanism": "retired_codex_custom_prompt",
                        "command": spec["command"],
                        "path": str(prompt_path),
                        "status": retire_status,
                        "invoke_as": [],
                    }
                )

        skill_dir = codex_root / "skills"
        for spec in specs:
            skill_path = skill_dir / str(spec["name"]) / "SKILL.md"
            metadata_path = skill_path.parent / "agents" / "openai.yaml"
            if uninstall:
                skill_status = _retire_status(skill_path, execute=execute)
                installed.append(
                    {
                        "surface": "codex",
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                        "mechanism": "codex_explicit_skills",
                        "command": spec["command"],
                        "path": str(skill_path),
                        "status": skill_status,
                        "invoke_as": [f"${spec['name']}", "/skills"],
                    }
                )
                metadata_status = _retire_status(metadata_path, execute=execute)
                installed.append(
                    {
                        "surface": "codex",
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                        "mechanism": "codex_skill_openai_metadata",
                        "command": spec["command"],
                        "path": str(metadata_path),
                        "status": metadata_status,
                        "invoke_as": [f"${spec['name']}", "/skills"],
                    }
                )
                continue
            skill_content = _command_skill_content(spec, surface="codex-skills")
            skill_status = _target_status(skill_path, skill_content, execute=execute)
            installed.append(
                {
                    "surface": "codex",
                    "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                    "mechanism": "codex_explicit_skills",
                    "command": spec["command"],
                    "path": str(skill_path),
                    "status": skill_status,
                    "invoke_as": [f"${spec['name']}", "/skills"],
                }
            )
            if skill_status not in {"skipped_user_file", "preserved_existing_loopx_skill"}:
                display_name = (
                    "LoopX" if spec["command"] == "/loopx" else f"LoopX {spec['command']}"
                )
                metadata = _openai_skill_metadata(
                    command=str(spec["command"]),
                    display_name=display_name,
                    short_description=str(spec["description"]),
                )
                metadata_status = _target_status(metadata_path, metadata, execute=execute)
                installed.append(
                    {
                        "surface": "codex",
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                        "mechanism": "codex_skill_openai_metadata",
                        "command": spec["command"],
                        "path": str(metadata_path),
                        "status": metadata_status,
                        "invoke_as": [f"${spec['name']}", "/skills"],
                    }
                )
            elif skill_status in {"skipped_user_file", "preserved_existing_loopx_skill"}:
                retire_status = _retire_managed_file(metadata_path, execute=execute)
                if retire_status:
                    installed.append(
                        {
                            "surface": "codex",
                            "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app", "codex-app-ssh"],
                            "mechanism": "retired_codex_command_metadata",
                            "command": spec["command"],
                            "path": str(metadata_path),
                            "status": retire_status,
                            "invoke_as": [],
                        }
                    )
        for spec in specs:
            installed.append(
                {
                    "surface": "codex",
                    "host_surfaces": ["codex-cli"],
                    "mechanism": "unsupported_native_slash_registry",
                    "command": spec["command"],
                    "path": None,
                    "status": "unsupported_host_surface",
                    "invoke_as": [],
                    "reason": (
                        "Current Codex does not support user-defined native top-level slash "
                        "commands. Use explicit skills instead."
                    ),
                    "native_registry_supported": False,
                    "failure_policy": "fail_closed_to_explicit_skill",
                    "fallback": (
                        f"Use `${spec['name']}` or `/skills` to explicitly invoke the LoopX "
                        "command skill; for the visible TUI loop, run "
                        "`loopx codex-cli-bootstrap-message --project .`, paste the setup "
                        "message, then set `/goal <thin task_body>`."
                    ),
                }
            )

    if "claude-code" in effective_surfaces:
        skills_dir = claude_root / "skills"
        for spec in specs:
            path = skills_dir / str(spec["name"]) / "SKILL.md"
            if uninstall:
                status = _retire_status(path, execute=execute)
                installed.append(
                    {
                        "surface": "claude-code",
                        "mechanism": "claude_code_skills",
                        "command": spec["command"],
                        "path": str(path),
                        "status": status,
                        "invoke_as": [str(spec["command"])],
                    }
                )
                continue
            content = _skill_body(
                command=str(spec["command"]),
                title=f"LoopX {spec['command']}",
                description=str(spec["description"]),
                argument_hint=str(spec["argument_hint"]),
                instructions=list(spec["instructions"]),
                surface="claude-skills",
                front_matter_name=str(spec["name"]),
            )
            status = _target_status(path, content, execute=execute)
            installed.append(
                {
                    "surface": "claude-code",
                    "mechanism": "claude_code_skills",
                    "command": spec["command"],
                    "path": str(path),
                    "status": status,
                    "invoke_as": [str(spec["command"])],
                }
            )

    def _install_skill_facade(
        *,
        skills_dir: Path,
        surface: str,
        host_surfaces: list[str],
        mechanism: str,
        invoke_prefix: str = "",
    ) -> None:
        """Write the command facade as SKILL.md files under `skills_dir`.

        Claude Code, Gemini CLI and Cursor all discover user skills the same
        way — a directory per skill with SKILL.md front matter — so the body is
        identical and only the root differs.
        """
        for spec in specs:
            path = skills_dir / str(spec["name"]) / "SKILL.md"
            if uninstall:
                installed.append(
                    {
                        "surface": surface,
                        "host_surfaces": list(host_surfaces),
                        "mechanism": mechanism,
                        "command": spec["command"],
                        "path": str(path),
                        "status": _retire_status(path, execute=execute),
                        "invoke_as": [],
                    }
                )
                continue
            content = _skill_body(
                command=str(spec["command"]),
                title=f"LoopX {spec['command']}",
                description=str(spec["description"]),
                argument_hint=str(spec["argument_hint"]),
                instructions=list(spec["instructions"]),
                surface="claude-skills",
                front_matter_name=str(spec["name"]),
            )
            installed.append(
                {
                    "surface": surface,
                    "host_surfaces": list(host_surfaces),
                    "mechanism": mechanism,
                    "command": spec["command"],
                    "path": str(path),
                    "status": _target_status(path, content, execute=execute),
                    "invoke_as": [f"{invoke_prefix}{spec['name']}"],
                }
            )

    if "gemini" in effective_surfaces:
        # Gemini CLI discovers user skills from GEMINI_HOME/skills. Files are
        # written directly, not through `gemini skills install --consent`: that
        # command copies from a git URL or an existing local path and the host
        # owns the copy, so LoopX would lose the managed marker, the per-file
        # status and the dry run that every other surface reports — and it would
        # need the `gemini` binary on PATH to install a file it already has.
        _install_skill_facade(
            skills_dir=gemini_root / "skills",
            surface="gemini",
            host_surfaces=["gemini-cli"],
            mechanism="gemini_cli_skills",
        )

    if "cursor" in effective_surfaces:
        # Cursor reads SKILL.md from CURSOR_HOME/skills (its skill roots also
        # include .claude/skills and .codex/skills, but relying on another
        # host's directory would break the moment that host is uninstalled).
        _install_skill_facade(
            skills_dir=cursor_root / "skills",
            surface="cursor",
            host_surfaces=["cursor-agent"],
            mechanism="cursor_skills",
        )
        # `cursor-agent mcp` can list and enable servers but not add them, so
        # the entry is merged into CURSOR_HOME/mcp.json. Only our own `loopx`
        # key is touched — a user's other servers are left exactly as they are.
        status = _merge_cursor_mcp(cursor_root, uninstall=uninstall, execute=execute)
        installed.append(
            {
                "surface": "cursor",
                "host_surfaces": ["cursor-agent"],
                "mechanism": "cursor_mcp_server",
                "command": "loopx",
                "path": str(cursor_root / "mcp.json"),
                "status": status,
                "invoke_as": [],
            }
        )

    if "opencode" in effective_surfaces:
        # OpenCode reads global skills from OPENCODE_CONFIG_DIR/skills. The
        # static command facade below stays as it is — a command is something
        # the user types, a skill is something the model can reach for itself.
        _install_skill_facade(
            skills_dir=opencode_root / "skills",
            surface="opencode",
            host_surfaces=["opencode"],
            mechanism="opencode_skills",
        )
        commands_dir = opencode_root / "commands"
        plugin_path = opencode_root / "plugins" / "loopx-goal.js"
        runtime_path = opencode_root / "loopx" / "goal-bridge-runtime.mjs"
        package_path = opencode_root / "package.json"
        plugin_content = plugin_source()
        runtime_content = runtime_source()

        bridge_preflight_blocked = False
        if with_goal_bridge and not uninstall:
            conflicts, invalid_configs = _opencode_direct_goal_plugin_conflicts(opencode_root)
            if invalid_configs:
                installed.append(
                    {
                        "surface": "opencode",
                        "host_surfaces": ["opencode"],
                        "mechanism": "opencode_goal_bridge",
                        "command": "/goal",
                        "path": str(plugin_path),
                        "status": "blocked_invalid_opencode_config",
                        "invoke_as": [],
                        "reason": (
                            "Repair the listed OpenCode JSON/JSONC config before installing "
                            "the bridge so direct plugin conflicts can be checked safely."
                        ),
                        "invalid_configs": invalid_configs,
                    }
                )
                bridge_preflight_blocked = True
            elif conflicts:
                installed.append(
                    {
                        "surface": "opencode",
                        "host_surfaces": ["opencode"],
                        "mechanism": "opencode_goal_bridge",
                        "command": "/goal",
                        "path": str(plugin_path),
                        "status": "blocked_conflicting_direct_plugin",
                        "invoke_as": [],
                        "reason": (
                            "Remove direct goal-plugin registration from the listed "
                            "OpenCode config, then rerun installation. The bridge imports "
                            "the pinned plugin and both must not be loaded independently."
                        ),
                        "conflicts": conflicts,
                    }
                )
                bridge_preflight_blocked = True
            else:
                user_owned_bridge_paths = [
                    str(path)
                    for path, content in (
                        (plugin_path, plugin_content),
                        (runtime_path, runtime_content),
                    )
                    if _target_status(path, content, execute=False)
                    == "skipped_user_file"
                ]
                if user_owned_bridge_paths:
                    installed.append(
                        {
                            "surface": "opencode",
                            "host_surfaces": ["opencode"],
                            "mechanism": "opencode_goal_bridge",
                            "command": "/goal",
                            "path": str(plugin_path),
                            "status": "blocked_user_owned_bridge_file",
                            "invoke_as": [],
                            "reason": (
                                "Move or rename the listed user-owned OpenCode bridge "
                                "files before installing LoopX so no partial bridge or "
                                "dependency update is applied."
                            ),
                            "conflicts": user_owned_bridge_paths,
                        }
                    )
                    bridge_preflight_blocked = True

            if not bridge_preflight_blocked:
                package_status = _target_package_dependencies(
                    package_path,
                    OPENCODE_GOAL_DEPENDENCIES,
                    execute=False,
                )
                if package_status == "blocked_invalid_user_package_json":
                    installed.append(
                        {
                            "surface": "opencode",
                            "host_surfaces": ["opencode"],
                            "mechanism": "opencode_goal_dependencies",
                            "command": "/goal",
                            "path": str(package_path),
                            "status": package_status,
                            "invoke_as": [],
                        }
                    )
                    bridge_preflight_blocked = True

        if with_goal_bridge and not bridge_preflight_blocked:
            if uninstall:
                for mechanism, path in (
                    ("opencode_goal_bridge", plugin_path),
                    ("opencode_goal_bridge_runtime", runtime_path),
                ):
                    installed.append(
                        {
                            "surface": "opencode",
                            "host_surfaces": ["opencode"],
                            "mechanism": mechanism,
                            "command": "/goal",
                            "path": str(path),
                            "status": _retire_status(path, execute=execute),
                            "invoke_as": ["/goal", "loopx_goal_activate"],
                        }
                    )
                installed.append(
                    {
                        "surface": "opencode",
                        "host_surfaces": ["opencode"],
                        "mechanism": "opencode_goal_dependencies",
                        "command": "/goal",
                        "path": str(package_path),
                        "status": "preserved_shared_dependencies",
                        "invoke_as": [],
                    }
                )
            else:
                package_status = _target_package_dependencies(
                    package_path,
                    OPENCODE_GOAL_DEPENDENCIES,
                    execute=execute,
                )
                installed.append(
                    {
                        "surface": "opencode",
                        "host_surfaces": ["opencode"],
                        "mechanism": "opencode_goal_dependencies",
                        "command": "/goal",
                        "path": str(package_path),
                        "status": package_status,
                        "invoke_as": [],
                    }
                )
                if package_status == "blocked_invalid_user_package_json":
                    bridge_preflight_blocked = True
                else:
                    for mechanism, path, content in (
                        ("opencode_goal_bridge_runtime", runtime_path, runtime_content),
                        ("opencode_goal_bridge", plugin_path, plugin_content),
                    ):
                        installed.append(
                            {
                                "surface": "opencode",
                                "host_surfaces": ["opencode"],
                                "mechanism": mechanism,
                                "command": "/goal",
                                "path": str(path),
                                "status": _target_status(path, content, execute=execute),
                                "invoke_as": ["/goal", "loopx_goal_activate"],
                            }
                        )

        if not bridge_preflight_blocked:
            for spec in specs:
                path = commands_dir / f"{spec['name']}.md"
                status = (
                    _retire_status(path, execute=execute)
                    if uninstall
                    else _target_status(
                        path,
                        _opencode_command_body(spec),
                        execute=execute,
                    )
                )
                installed.append(
                    {
                        "surface": "opencode",
                        "host_surfaces": ["opencode"],
                        "mechanism": "opencode_commands",
                        "command": spec["command"],
                        "path": str(path),
                        "status": status,
                        "invoke_as": [str(spec["command"])],
                    }
                )

    if "pi" in effective_surfaces:
        extension_path = _pi_extension_path(pi_project_root)
        runtime_path = _pi_runtime_path(pi_project_root)
        extension_content = pi_extension_source()
        runtime_content = pi_runtime_source()
        if uninstall:
            for mechanism, path in (
                ("pi_goal_extension", extension_path),
                ("pi_goal_extension_runtime", runtime_path),
            ):
                installed.append(
                    {
                        "surface": "pi",
                        "host_surfaces": ["pi"],
                        "mechanism": mechanism,
                        "command": "/loopx",
                        "path": str(path),
                        "status": _retire_status(path, execute=execute),
                        "invoke_as": ["/loopx", "loopx_goal_activate"],
                    }
                )
        else:
            # The adapter and its loop runtime are one atomic delivery unit:
            # preflight both targets and fail closed with zero writes when any
            # target is a user-owned file, so a newly created managed adapter
            # can never import an unmanaged runtime that may lack the exports
            # it needs.
            user_owned_pi_paths = [
                str(path)
                for path, content in (
                    (extension_path, extension_content),
                    (runtime_path, runtime_content),
                )
                if _target_status(path, content, execute=False) == "skipped_user_file"
            ]
            if user_owned_pi_paths:
                installed.append(
                    {
                        "surface": "pi",
                        "host_surfaces": ["pi"],
                        "mechanism": "pi_goal_extension",
                        "command": "/loopx",
                        "path": str(extension_path),
                        "status": "blocked_user_owned_pi_file",
                        "invoke_as": ["/loopx", "loopx_goal_activate"],
                        "reason": (
                            "Move or rename the listed user-owned Pi files before "
                            "installing LoopX so the adapter and its loop runtime "
                            "are installed as one atomic unit; no Pi file was written."
                        ),
                        "conflicts": user_owned_pi_paths,
                    }
                )
            else:
                for mechanism, path, content in (
                    ("pi_goal_extension", extension_path, extension_content),
                    ("pi_goal_extension_runtime", runtime_path, runtime_content),
                ):
                    installed.append(
                        {
                            "surface": "pi",
                            "host_surfaces": ["pi"],
                            "mechanism": mechanism,
                            "command": "/loopx",
                            "path": str(path),
                            "status": _target_status(path, content, execute=execute),
                            "invoke_as": ["/loopx", "loopx_goal_activate"],
                        }
                    )

    status_counts: dict[str, int] = {}
    for item in installed:
        status = str(item["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "ok": not any(status.startswith("blocked_") for status in status_counts),
        "schema_version": SCHEMA_VERSION,
        "operation": "uninstall" if uninstall else "install",
        "execute": execute,
        "with_goal_bridge": with_goal_bridge,
        "requested_surfaces": surfaces or ["all"],
        "effective_surfaces": effective_surfaces,
        "catalog_schema_version": build_slash_command_catalog(
            cli_bin=cli_bin,
            include_legacy_aliases=include_legacy_aliases,
        )["schema_version"],
        "summary": {
            "codex_prompt_dir": None,
            "codex_skill_dir": str(codex_root / "skills") if "codex" in effective_surfaces else None,
            "claude_skill_dir": str(claude_root / "skills") if "claude-code" in effective_surfaces else None,
            "gemini_skill_dir": str(gemini_root / "skills") if "gemini" in effective_surfaces else None,
            "cursor_skill_dir": str(cursor_root / "skills") if "cursor" in effective_surfaces else None,
            "cursor_mcp_path": str(cursor_root / "mcp.json") if "cursor" in effective_surfaces else None,
            "opencode_skill_dir": str(opencode_root / "skills") if "opencode" in effective_surfaces else None,
            "opencode_command_dir": str(opencode_root / "commands") if "opencode" in effective_surfaces else None,
            "opencode_plugin_path": str(opencode_root / "plugins" / "loopx-goal.js") if "opencode" in effective_surfaces and with_goal_bridge else None,
            "opencode_package_path": str(opencode_root / "package.json") if "opencode" in effective_surfaces and with_goal_bridge else None,
            "pi_extension_path": str(_pi_extension_path(pi_project_root)) if "pi" in effective_surfaces else None,
            "pi_runtime_path": str(_pi_runtime_path(pi_project_root)) if "pi" in effective_surfaces else None,
            "status_counts": status_counts,
            "skip_policy": (
                "Uninstall removes only LoopX-managed files; user files without a LoopX managed marker are preserved"
                if uninstall
                else "LoopX-managed files are upgraded; same-name user files without a LoopX managed marker or legacy signature are never overwritten"
            ),
        },
        "installed": installed,
        "notes": [
            "Codex does not currently support user-defined native top-level slash commands; use explicit skill invocation through `$loopx` or `/skills`.",
            "Explicit LoopX command-facade skills use agents/openai.yaml policy allow_implicit_invocation=false and remain distinct from richer workflow skills such as loopx-project.",
            "Claude Code discovers user skills from CLAUDE_HOME/skills and exposes each skill name as a slash command.",
            "Gemini CLI discovers user skills from GEMINI_HOME/skills with the same SKILL.md front matter; files are written directly because `gemini skills install` copies from a git URL or an existing local path and hands the copy to the host, which would lose the managed marker, per-file status and dry-run reporting every other surface has.",
            "Cursor discovers skills from CURSOR_HOME/skills and has no user-defined slash commands, so the cursor surface installs the skill facade and registers the LoopX MCP server in CURSOR_HOME/mcp.json; run `cursor-agent mcp enable loopx` once to approve it.",
            "OpenCode discovers global skills from OPENCODE_CONFIG_DIR/skills in addition to the static command facade; a command is typed by the user, a skill can be reached by the model itself.",
            "The default all surface installs only OpenCode's static command facade; the executable goal bridge requires --with-goal-bridge.",
            "The Pi surface is opt-in and installs the self-contained goal extension and its loop runtime into the project's .pi/extensions/; it is not part of the default all surface.",
            "The OpenCode goal bridge uses Bun-managed config-directory dependencies and must replace any direct goal-plugin registration.",
            "OpenCode bridge uninstall preserves package.json dependencies because they may be shared by user-owned local plugins.",
            "Uninstall is fail-closed: it retires only files carrying the LoopX managed marker and leaves user-owned files in place.",
        ],
    }


def render_slash_command_install_markdown(payload: dict[str, Any]) -> str:
    operation = str(payload.get("operation") or "install")
    lines = [
        "# LoopX Slash Command Uninstall" if operation == "uninstall" else "# LoopX Slash Command Install",
        "",
        f"- operation: `{operation}`",
        f"- execute: `{payload.get('execute')}`",
        f"- surfaces: `{','.join(payload.get('effective_surfaces') or [])}`",
        f"- skip policy: `{payload.get('summary', {}).get('skip_policy')}`",
    ]
    codex_prompt_dir = payload.get("summary", {}).get("codex_prompt_dir")
    codex_skill_dir = payload.get("summary", {}).get("codex_skill_dir")
    claude_skill_dir = payload.get("summary", {}).get("claude_skill_dir")
    opencode_command_dir = payload.get("summary", {}).get("opencode_command_dir")
    opencode_plugin_path = payload.get("summary", {}).get("opencode_plugin_path")
    if codex_prompt_dir:
        lines.append(f"- codex prompts: `{codex_prompt_dir}`")
    if codex_skill_dir:
        lines.append(f"- codex skills: `{codex_skill_dir}`")
    if claude_skill_dir:
        lines.append(f"- claude skills: `{claude_skill_dir}`")
    if opencode_command_dir:
        lines.append(f"- opencode commands: `{opencode_command_dir}`")
    if opencode_plugin_path:
        lines.append(f"- opencode bridge: `{opencode_plugin_path}`")
    pi_extension_path = payload.get("summary", {}).get("pi_extension_path")
    if pi_extension_path:
        lines.append(f"- pi extension: `{pi_extension_path}`")
    pi_runtime_path = payload.get("summary", {}).get("pi_runtime_path")
    if pi_runtime_path:
        lines.append(f"- pi loop runtime: `{pi_runtime_path}`")
    counts = payload.get("summary", {}).get("status_counts") or {}
    if isinstance(counts, dict) and counts:
        count_text = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        lines.append(f"- statuses: `{count_text}`")
    skipped = [
        item for item in payload.get("installed") or []
        if isinstance(item, dict) and item.get("status") == "skipped_user_file"
    ]
    if skipped:
        lines.append("")
        lines.append("Skipped user-owned files:")
        for item in skipped:
            lines.append(f"- `{item.get('command')}` at `{item.get('path')}`")
    notes = [note for note in payload.get("notes") or [] if isinstance(note, str)]
    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            lines.append(f"- {note}")
    lines.append("")
    lines.append("Restart the host if its slash-command menu was already open.")
    return "\n".join(lines)
