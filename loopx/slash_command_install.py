from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .opencode_goal_mode import plugin_source, runtime_source
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
    "opencode-goal-plugin": "0.6.5",
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
            "argument_hint": "[task text]",
            "instructions": [
                "Visible command arguments: `$ARGUMENTS`.",
                "Before start-goal, identify the exact current host: use `codex-app` for the desktop app, `codex-ide-plugin` only for the IDE plugin, `codex-cli-tui` for the terminal TUI, or `opencode` for OpenCode.",
                f"If arguments are present, preserve them as the task text and run `{cli_bin} start-goal --guided --project . --goal-text \"$ARGUMENTS\" --host-surface <exact-current-host>` before planning work. If the host is unclear, omit the flag once and follow the returned host-surface selection gate.",
                f"If that packet exposes a goal-selection gate, rerun one exact choice before any mutation. When the user asks to create or become a new peer/meta/supervisor agent, do not reuse an existing registered identity: choose a new public-safe agent id, preview then apply `{cli_bin} register-agent --goal-id <selected-goal-id> --agent-id <new-agent-id> --execute`, and rerun start-goal with explicit `--goal-id` and `--agent-id` before todo writeback.",
                f"If arguments are empty, inspect `{cli_bin} bootstrap-command-pack --project .`, `{cli_bin} status`, and `{cli_bin} slash-commands` before changing files.",
                f"Use `{cli_bin} agent-onboard --list-agent-types` when the host runtime is unclear; pass an exact type such as `codex-app`, `codex-ide-plugin`, `codex-cli`, `claude-code`, or `opencode`, never ambiguous `codex`.",
                f"Do not configure optional features during first-run. Only when the task needs bounded child agents or Explore, inspect `{cli_bin} configure-goal --goal-id <resolved-goal-id>` and its `configuration_catalog`; preview before explicit apply and never auto-enable a feature merely because it exists.",
                "When project work is started, plan ordered P0/P1/P2 todos, write them through LoopX todo state, refresh state, activate the host loop if missing/stale, run quota, and complete one bounded delivery segment through validation plus LoopX writeback or an exact blocker; do not return merely after setup, planning, or claim.",
                "Host loop activation means Codex App heartbeat automation, Codex IDE plugin or CLI visible `/goal <task_body>`, Claude Code native `/loop`, OpenCode `loopx_goal_activate`, or a custom host-loop gate from `loopx agent-onboard`.",
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
                f"Run `{cli_bin} --format json pr-review $ARGUMENTS` first and keep `agent_response_contract`, `review_groups`, `pull_requests[].review_template`, and `pull_requests[].evidence_commands` visible.",
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
        if any(
            str(plugin) == package or str(plugin).startswith(f"{package}@")
            for plugin in plugins
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
        elif surface in {"codex-app", "codex-ide-plugin", "codex-ide", "codex-cli"}:
            candidates = ["codex"]
        else:
            candidates = [surface]
        for candidate in candidates:
            if candidate not in normalized:
                normalized.append(candidate)
    return normalized


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
) -> dict[str, Any]:
    specs = _command_prompt_specs(cli_bin=cli_bin, include_legacy_aliases=include_legacy_aliases)
    effective_surfaces = _normalize_surfaces(surfaces)
    codex_root = _codex_home(codex_home)
    claude_root = _claude_home(claude_home)
    opencode_root = _opencode_home(opencode_home)
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
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
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
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
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
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
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
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
                        "mechanism": "codex_skill_openai_metadata",
                        "command": spec["command"],
                        "path": str(metadata_path),
                        "status": metadata_status,
                        "invoke_as": [f"${spec['name']}", "/skills"],
                    }
                )
                continue
            skill_content = _skill_body(
                command=str(spec["command"]),
                title=f"LoopX {spec['command']}",
                description=str(spec["description"]),
                argument_hint=str(spec["argument_hint"]),
                instructions=list(spec["instructions"]),
                surface="codex-skills",
                front_matter_name=str(spec["name"]),
            )
            skill_status = _target_status(skill_path, skill_content, execute=execute)
            installed.append(
                {
                    "surface": "codex",
                    "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
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
                        "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
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
                            "host_surfaces": ["codex-cli", "codex-ide-plugin", "codex-app"],
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

    if "opencode" in effective_surfaces:
        commands_dir = opencode_root / "commands"
        plugin_path = opencode_root / "plugins" / "loopx-goal.js"
        runtime_path = opencode_root / "loopx" / "goal-bridge-runtime.mjs"
        package_path = opencode_root / "package.json"

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
                        ("opencode_goal_bridge_runtime", runtime_path, runtime_source()),
                        ("opencode_goal_bridge", plugin_path, plugin_source()),
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
            "opencode_command_dir": str(opencode_root / "commands") if "opencode" in effective_surfaces else None,
            "opencode_plugin_path": str(opencode_root / "plugins" / "loopx-goal.js") if "opencode" in effective_surfaces and with_goal_bridge else None,
            "opencode_package_path": str(opencode_root / "package.json") if "opencode" in effective_surfaces and with_goal_bridge else None,
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
            "The default all surface installs only OpenCode's static command facade; the executable goal bridge requires --with-goal-bridge.",
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
