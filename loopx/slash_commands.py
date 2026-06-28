from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "loopx_slash_command_catalog_v0"


def _command(
    *,
    command: str,
    scope: str,
    intent: str,
    mutation_policy: str,
    cli_reference: str,
    legacy_aliases: list[str] | None = None,
    implementation_status: str = "available",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "command": command,
        "scope": scope,
        "intent": intent,
        "mutation_policy": mutation_policy,
        "cli_reference": cli_reference,
        "implementation_status": implementation_status,
    }
    if legacy_aliases:
        item["legacy_aliases"] = legacy_aliases
    return item


def build_slash_command_catalog(
    *,
    cli_bin: str = "loopx",
    include_legacy_aliases: bool = True,
) -> dict[str, Any]:
    legacy_summary = ["/loop-global-summary"] if include_legacy_aliases else []
    legacy_gates = ["/loop-global-gates"] if include_legacy_aliases else []
    legacy_todos = ["/loop-global-todos"] if include_legacy_aliases else []
    legacy_risks = ["/loop-global-risks"] if include_legacy_aliases else []
    commands = [
        _command(
            command="/loopx",
            scope="project",
            intent="Inspect or preview this project's LoopX connection, status, gates, and next safe action.",
            mutation_policy="read_first; ask before bootstrap/connect writes",
            cli_reference=f"{cli_bin} bootstrap-command-pack --project .",
        ),
        _command(
            command="/loopx <goal text>",
            scope="project",
            intent="Start a concrete project goal: plan ordered todos, write them in priority order, then enter the quota-gated loop.",
            mutation_policy="explicit goal-start intent may write project-local LoopX state after planning",
            cli_reference=f"{cli_bin} bootstrap-command-pack --project . --goal-text '<goal text>'",
        ),
        _command(
            command="/loopx-global-summary",
            scope="global",
            intent="Read a progress digest across visible LoopX goals.",
            mutation_policy="read_only",
            cli_reference=f"{cli_bin} global-summary",
            legacy_aliases=legacy_summary,
        ),
        _command(
            command="/loopx-global-gates",
            scope="global",
            intent="List open user/controller gates and what each blocks.",
            mutation_policy="read_only",
            cli_reference=f"{cli_bin} slash-commands; use {cli_bin} global-summary for the current compact global packet",
            legacy_aliases=legacy_gates,
            implementation_status="host_command_defined",
        ),
        _command(
            command="/loopx-global-todos",
            scope="global",
            intent="List top runnable, blocked, deferred-ready, and review todos across visible goals.",
            mutation_policy="read_only",
            cli_reference=f"{cli_bin} slash-commands; use {cli_bin} global-summary for the current compact global packet",
            legacy_aliases=legacy_todos,
            implementation_status="host_command_defined",
        ),
        _command(
            command="/loopx-global-risks",
            scope="global",
            intent="Show stale runs, boundary risks, failing checks, and rollback candidates.",
            mutation_policy="read_only",
            cli_reference=f"{cli_bin} slash-commands; use {cli_bin} global-summary for the current compact global packet",
            legacy_aliases=legacy_risks,
            implementation_status="host_command_defined",
        ),
        _command(
            command="/loopx-pr-review",
            scope="repo",
            intent="List open and merged pull requests for the current project or explicit --repo target and generate a guided review queue with motivation, change scope, checks, risks, and per-PR review prompts.",
            mutation_policy="read_only; does not comment, approve, merge, or spend quota",
            cli_reference=f"{cli_bin} pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]",
        ),
    ]
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "canonical_prefix": "/loopx",
        "commands": commands,
        "onboarding": {
            "tell_new_users": True,
            "suggested_user_note": render_onboarding_slash_command_note(commands, cli_bin=cli_bin),
        },
        "help": {
            "cli_command": f"{cli_bin} slash-commands",
            "legacy_alias_policy": "legacy /loop-global-* forms may be accepted during migration, but help should show /loopx-global-* as canonical",
        },
    }


def render_onboarding_slash_command_note(commands: list[dict[str, Any]], *, cli_bin: str = "loopx") -> str:
    command_by_name = {str(item.get("command")): item for item in commands}
    project = command_by_name.get("/loopx", {})
    goal = command_by_name.get("/loopx <goal text>", {})
    return "\n".join(
        [
            "LoopX command surface is available. Useful commands:",
            f"- `/loopx`: {project.get('intent', 'inspect this project')}",
            f"- `/loopx <goal text>`: {goal.get('intent', 'start a concrete project goal')}",
            "- `/loopx-global-summary`: read the global progress digest.",
            "- `/loopx-global-gates`, `/loopx-global-todos`, `/loopx-global-risks`: inspect manager-level gates, work, and risks.",
            "- `/loopx-pr-review`: review the current project's open and merged PRs one by one with motivation, scope, checks, and risks.",
            f"CLI help: `{cli_bin} slash-commands`.",
        ]
    )


def _markdown_table_cell(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|")


def render_slash_command_catalog_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "# LoopX Slash Commands\n\n- ok: `False`"
    lines = [
        "# LoopX Slash Commands",
        "",
        str(payload.get("onboarding", {}).get("suggested_user_note") or ""),
        "",
        "| Command | Scope | Intent | Mutation policy | CLI reference |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in payload.get("commands") or []:
        if not isinstance(item, dict):
            continue
        legacy = item.get("legacy_aliases") or []
        intent = str(item.get("intent") or "")
        if legacy:
            intent += " Legacy aliases: " + ", ".join(f"`{alias}`" for alias in legacy) + "."
        lines.append(
            "| "
            f"`{_markdown_table_cell(item.get('command'))}` | "
            f"{_markdown_table_cell(item.get('scope'))} | "
            f"{_markdown_table_cell(intent)} | "
            f"{_markdown_table_cell(item.get('mutation_policy'))} | "
            f"`{_markdown_table_cell(item.get('cli_reference'))}` |"
        )
    lines.extend(
        [
            "",
            "Global manager commands are read-only by default. Project-local `/loopx <goal text>` is the only slash form here that can authorize project-local state writes, and it must plan before writing todos.",
        ]
    )
    return "\n".join(lines)
