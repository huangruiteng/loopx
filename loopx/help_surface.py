from __future__ import annotations

import re
from typing import Any

from . import __version__

GLOBAL_OPTIONS_WITH_VALUE = {"--registry", "--runtime-root", "--format"}
GLOBAL_OPTIONS_WITH_EQUALS = tuple(f"{option}=" for option in sorted(GLOBAL_OPTIONS_WITH_VALUE))
HELP_FLAGS = {"-h", "--help"}


COMMAND_GROUPS: list[dict[str, object]] = [
    {
        "title": "Start here",
        "commands": [
            {
                "command": "/loopx",
                "purpose": "Ask the agent to inspect LoopX status, gates, todos, and next action.",
            },
            {
                "command": "/loopx <goal text>",
                "purpose": "Start or continue one concrete long-running goal through the agent.",
            },
            {
                "command": "loopx doctor",
                "purpose": "Check install, PATH, release snapshot, skills, and import health.",
            },
            {
                "command": "loopx slash-commands --install",
                "purpose": "Refresh host slash-command prompt and skill files.",
            },
            {
                "command": "loopx preset list",
                "purpose": "Show beginner-safe and opt-in advanced loop start packets.",
            },
            {
                "command": "loopx ready-score --goal-id <goal-id>",
                "purpose": "Score install, status, quota, scheduler, todo, and evidence readiness without writing badges.",
            },
            {
                "command": 'loopx start-goal --guided --project . --goal-text "<goal>"',
                "purpose": "Preview the shell fallback for the same agent-safe `/loopx <goal>` path.",
            },
            {
                "command": "loopx agent-onboard --agent-type codex-cli --project .",
                "purpose": "Generate the exact host-loop activation packet for one agent runtime.",
            },
            {
                "command": "loopx bootstrap-command-pack --project .",
                "purpose": "Generate the lower-level host handoff packet.",
            },
        ],
    },
    {
        "title": "Daily operator commands",
        "commands": [
            {"command": "loopx status", "purpose": "Show goals, gates, attention queue, and next action."},
            {
                "command": "loopx diagnose --goal-id <goal-id>",
                "purpose": "Build a compact evidence packet when behavior is surprising.",
            },
            {
                "command": "loopx review-packet --goal-id <goal-id>",
                "purpose": "Render a handoff or review packet with any required evidence-log reads.",
            },
            {
                "command": "loopx evidence-log --goal-id <goal-id> --agent-id <agent-id> --thin",
                "purpose": "Read the current agent's thin public-safe ledger before replan or handoff.",
            },
            {"command": "loopx todo --help", "purpose": "Show todo lifecycle commands."},
            {
                "command": "loopx task-lease --help",
                "purpose": "Acquire, renew, transfer, release, or inspect a hard per-todo lease.",
            },
            {"command": "loopx quota should-run", "purpose": "Decide whether the next agent turn should run."},
            {"command": "loopx history --goal-id <goal-id>", "purpose": "Read compact run history."},
            {
                "command": "loopx history trajectory-hygiene --goal-id <goal-id> --limit 100",
                "purpose": "Measure controller density and attribution gaps from compact history without reading raw sessions.",
            },
        ],
    },
    {
        "title": "Loop driver hints",
        "commands": [
            {
                "command": "Codex App automation",
                "purpose": "Use `/loopx <goal>` and let the app create or refresh the heartbeat automation.",
            },
            {
                "command": "Codex CLI visible goal",
                "purpose": "Stay in the visible TUI; use `loopx codex-cli-bootstrap-message` for setup when needed.",
            },
            {
                "command": "Claude Code /loop",
                "purpose": "Use installed slash skills for `/loopx`; enable the adapter only when native `/loop` should be gated by LoopX.",
            },
            {
                "command": "OpenCode goal bridge",
                "purpose": "Opt into `--with-goal-bridge`, then use `loopx_goal_activate` to bind the quota-gated bridge.",
            },
            {
                "command": "Other agent or shell",
                "purpose": "Use a CLI, task, automation, heartbeat, or scheduler hook; otherwise drive LoopX manually.",
            },
            {
                "command": "loopx turn plan --goal-id <goal-id> --agent-id <agent-id>",
                "purpose": "Plan one governed external-host turn from live LoopX state without launching an agent or writing state.",
            },
            {
                "command": "loopx host-mode-plan --goal-id <goal-id> --intent <intent> --host-capability <capability>",
                "purpose": "Select a safe host mode (visible, isolated headless Turn, gateway, timer, hybrid) and show the matching Turn/quota preview commands.",
            },
        ],
    },
    {
        "title": "Setup and automation commands",
        "commands": [
            {"command": "loopx bootstrap / loopx connect", "purpose": "Create or connect project-local state."},
            {
                "command": "loopx new-project-prompt",
                "purpose": "Generate a copy-paste project connection prompt for an agent.",
            },
            {
                "command": "loopx codex-cli-bootstrap-message",
                "purpose": "Generate the visible Codex CLI TUI setup message.",
            },
            {
                "command": "loopx codex-cli-tui-bootstrap-smoke-bundle",
                "purpose": "Generate a transcript-free Codex CLI first-run smoke bundle.",
            },
            {
                "command": "loopx codex-cli-visible-attach-acceptance",
                "purpose": "Check public-safe visible Codex CLI attach evidence.",
            },
            {"command": "loopx heartbeat-prompt", "purpose": "Generate a guarded heartbeat automation body."},
            {
                "command": "loopx supervisor-prompt",
                "purpose": "Generate the dedicated task body for an opt-in proposal-only peer supervisor.",
            },
            {
                "command": "loopx supervisor-observe",
                "purpose": "Read one public-safe supervisor packet over peer status and evidence.",
            },
            {
                "command": "loopx supervisor-event",
                "purpose": "Preview, append, or read supervisor proposals and host execution receipts.",
            },
            {"command": "loopx upgrade-plan", "purpose": "Plan default heartbeat upgrade propagation."},
            {"command": "loopx update", "purpose": "Check, dry-run, or execute the no-clone update path."},
        ],
    },
    {
        "title": "Maintainer and adapter commands",
        "commands": [
            {"command": "loopx check", "purpose": "Run contract and public/private boundary checks."},
            {"command": "loopx registry", "purpose": "Inspect registered goals and adapters."},
            {"command": "loopx sync-global", "purpose": "Merge project state into the shared registry."},
            {
                "command": "loopx retire-global-goal",
                "purpose": "Safely retire explicitly named orphaned global goal routes.",
            },
            {"command": "loopx register-agent", "purpose": "Register an automation agent."},
            {"command": "loopx lark-kanban", "purpose": "Project LoopX state into a Feishu/Lark Base board."},
            {
                "command": "loopx presentation",
                "purpose": "Package, roll back, and verify provider-neutral static presentation artifacts.",
            },
            {
                "command": "loopx explore",
                "purpose": "Record the exploration topology (nodes, edges, findings) and project it to a Feishu/Lark result board.",
            },
            {
                "command": "loopx extension",
                "purpose": "Inspect and manage doctor-verified subprocess extension activations.",
            },
            {"command": "loopx issue-fix", "purpose": "Build public-safe issue or PR fix workflow packets."},
            {
                "command": "loopx review-batch",
                "purpose": "Compose provider-neutral bounded review packets and bind exact decisions.",
            },
            {
                "command": "loopx periodic-report",
                "purpose": "Resolve a portable weekly profile, evaluate report triggers, and compose provider-neutral run receipts.",
            },
            {"command": "loopx auto-research", "purpose": "Project public-safe research frontiers."},
            {"command": "loopx multi-agent", "purpose": "Launch visible role-scoped Codex TUI agents."},
            {"command": "loopx canary", "purpose": "Plan or run catalog-informed smoke profiles."},
            {"command": "loopx benchmark", "purpose": "Use fixture-only benchmark runner skeletons by default."},
        ],
    },
]


# Every top-level parser command must either be represented in COMMAND_GROUPS
# or be explicitly kept on its command-specific help surface. This makes a new
# command an intentional manual-visibility decision instead of a silent omission.
MANPAGE_COMMAND_HELP_ONLY = frozenset(
    {
        "archive-runtime",
        "backup-state",
        "capability",
        "codex-cli-bounded-visible-pilot-adapter",
        "codex-cli-exec-handoff",
        "codex-cli-local-driver-plan",
        "codex-cli-local-scheduler-exec",
        "codex-cli-local-scheduler-tick",
        "codex-cli-one-message-loop-pilot",
        "codex-cli-runtime-idle-detector",
        "codex-cli-session-probe",
        "codex-cli-visible-driver-plan",
        "codex-cli-visible-driver-run",
        "codex-cli-visible-first-response-capture-plan",
        "codex-cli-visible-local-driver-pilot",
        "codex-cli-visible-session-proof",
        "configure-goal",
        "content-ops",
        "demo",
        "dreaming",
        "global-summary",
        "heartbeat-prequota",
        "import-doc-registry-authority",
        "lark-inbox",
        "migrate-state",
        "ml-experiment",
        "operator-gate",
        "pr-review",
        "promotion-gate",
        "read-only-map",
        "refresh-state",
        "register-authority-source",
        "registry-boundary",
        "reward",
        "reward-memory",
        "semantic-preference",
        "serve-status",
        "uninstall-project",
        "value-connectors",
        "version",
        "worker-bridge",
    }
)


def manpage_top_level_commands() -> frozenset[str]:
    commands = {"commands"}
    for group in COMMAND_GROUPS:
        entries = group.get("commands")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            command = str(entry.get("command") or "")
            commands.update(
                re.findall(r"(?:^| / )loopx ([a-z0-9][a-z0-9-]*)", command)
            )
    return frozenset(commands)


def _program_name(program: str) -> str:
    name = program.rsplit("/", 1)[-1]
    if name in {"loopx", "cli.py", "__main__.py"}:
        return "loopx"
    if program.endswith("loopx.cli") or " -m loopx.cli" in program:
        return "loopx"
    return program or "loopx"


def top_level_help_requested(argv: list[str]) -> bool:
    if not argv:
        return True
    help_positions = [index for index, value in enumerate(argv) if value in HELP_FLAGS]
    if not help_positions:
        return False
    help_index = help_positions[0]
    index = 0
    while index < help_index:
        value = argv[index]
        if value in GLOBAL_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if value.startswith(GLOBAL_OPTIONS_WITH_EQUALS):
            index += 1
            continue
        return False
    return True


def render_concise_help(program: str = "loopx") -> str:
    program = _program_name(program)
    return "\n".join(
        [
            "LoopX keeps long-running agent work moving by preserving goals, todos, gates, quota,",
            "and evidence between agent turns.",
            "",
            "Usage:",
            f"  {program} [global options] <command> [command options]",
            f"  {program} <command> --help",
            "",
            "Start here:",
            "  /loopx                         Ask the agent to inspect LoopX state.",
            "  /loopx <goal text>             Start or continue a concrete long-running goal.",
            "  loopx doctor                   Check install, PATH, release snapshot, and skills.",
            "  loopx slash-commands --install Refresh host slash-command skill files.",
            "  loopx preset list              Show safe preset start packets.",
            "  loopx ready-score --goal-id ID Score install/status/quota readiness.",
            "  loopx start-goal --guided --project . --goal-text \"<goal>\"",
            "                                  Preview the shell fallback for /loopx <goal>.",
            "",
            "Daily operator commands:",
            "  loopx status                   Show current goals, gates, and next action.",
            "  loopx diagnose --goal-id ID    Build a compact evidence packet.",
            "  loopx evidence-log --goal-id ID --agent-id AGENT --thin",
            "                                  Read this agent's thin ledger before replan.",
            "  loopx todo --help              Add, claim, complete, update, or archive todos.",
            "  loopx task-lease --help        Manage a hard per-todo lease.",
            "  loopx quota should-run         Decide whether the next agent turn should run.",
            "",
            "Run the loop:",
            "  Codex App      use /loopx <goal>; let the app set the heartbeat automation.",
            "  Codex CLI      keep visible TUI; run loopx codex-cli-bootstrap-message.",
            "  Claude Code    use installed /loopx skills; adapter only for gated native /loop.",
            "  OpenCode       opt into the goal bridge, then use loopx_goal_activate.",
            "  Other agents   need a CLI/task/automation/loop hook, or run LoopX manually.",
            "",
            "Global options: --registry PATH   --runtime-root PATH   --format markdown|json",
            "More:",
            "  loopx commands                 Show grouped command reference.",
            "  loopx <command> --help         Show flags for one command.",
            "  man loopx                      Open the installed manual page.",
            "",
        ]
    )


def build_command_reference_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": "loopx_command_reference_v0",
        "summary": "Grouped LoopX command reference for operators and contributors.",
        "groups": COMMAND_GROUPS,
        "more": [
            "loopx <command> --help",
            "man loopx",
            "docs/guides/getting-started.md#command-reference",
        ],
    }


def render_command_reference_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX command reference",
        "",
        str(payload.get("summary") or ""),
        "",
    ]
    groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
    for group in groups:
        if not isinstance(group, dict):
            continue
        title = str(group.get("title") or "Commands")
        lines.extend([f"## {title}", ""])
        commands = group.get("commands") if isinstance(group.get("commands"), list) else []
        for command in commands:
            if not isinstance(command, dict):
                continue
            name = str(command.get("command") or "").strip()
            purpose = str(command.get("purpose") or "").strip()
            if name and purpose:
                lines.append(f"- `{name}` - {purpose}")
        lines.append("")
    lines.extend(
        [
            "For command-specific flags, run `loopx <command> --help`.",
            "For the manual page, run `man loopx` after installing LoopX.",
            "",
        ]
    )
    return "\n".join(lines)


def _roff_text(value: object) -> str:
    text = str(value).replace("\\", r"\e").replace("-", r"\-")
    if text.startswith((".", "'")):
        return rf"\&{text}"
    return text


def render_manpage(*, version: str = __version__) -> str:
    """Render the CLI manual from the canonical command catalog."""

    lines = [
        f'.TH LOOPX 1 "" "LoopX {_roff_text(version)}" "User Commands"',
        ".SH NAME",
        r"loopx \- control-plane helper for long-running agent work",
        ".SH SYNOPSIS",
        ".B loopx",
        r"[\fB\-\-registry\fR \fIPATH\fR]",
        r"[\fB\-\-runtime\-root\fR \fIPATH\fR]",
        r"[\fB\-\-format\fR \fImarkdown|json\fR]",
        r"\fICOMMAND\fR",
        r"[\fIARGS\fR]",
        ".br",
        ".B loopx",
        r"\fICOMMAND\fR",
        r"\fB\-\-help\fR",
        ".br",
        ".B loopx commands",
        ".SH DESCRIPTION",
        "LoopX keeps long-running agent work moving by preserving goals, todos, gates,",
        "quota, and evidence between agent turns.",
        ".PP",
        "The command sections below are generated from the same canonical catalog used by",
        r"\fBloopx commands\fR. Command-specific flags remain available through",
        r"\fBloopx COMMAND \-\-help\fR.",
    ]

    for group in COMMAND_GROUPS:
        title = _roff_text(str(group.get("title") or "Commands").upper())
        lines.append(f".SH {title}")
        commands = group.get("commands")
        if not isinstance(commands, list):
            continue
        for entry in commands:
            if not isinstance(entry, dict):
                continue
            command = str(entry.get("command") or "").strip()
            purpose = str(entry.get("purpose") or "").strip()
            if not command or not purpose:
                continue
            lines.extend(
                [
                    ".TP",
                    rf"\fB{_roff_text(command)}\fR",
                    _roff_text(purpose),
                ]
            )

    lines.extend(
        [
            ".SH MORE",
            ".TP",
            r"\fBloopx COMMAND \-\-help\fR",
            "Show flags for one command.",
            ".TP",
            r"\fBman loopx\fR",
            "Open this installed manual page.",
            ".TP",
            r"\fBdocs/guides/getting\-started.md#command\-reference\fR",
            "Read the longer operator and contributor guide.",
            ".SH INSTALL NOTES",
            "The LoopX local installer writes this manual to",
            r"\fI$HOME/.local/share/man/man1/loopx.1.gz\fR by default and adds",
            r"\fI$HOME/.local/share/man\fR to MANPATH in the selected shell profile.",
            "If the current shell has not reloaded that profile, run:",
            ".PP",
            r"\fBMANPATH=\"$HOME/.local/share/man:${MANPATH:\-}\" man loopx\fR",
            ".SH SEE ALSO",
            ".BR man (1)",
            "",
        ]
    )
    return "\n".join(lines)
