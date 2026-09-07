from __future__ import annotations

from pathlib import Path
from typing import Any

KIRO_CLI_INSTALL_SURFACE = "kiro-cli"
KIRO_CLI_AGENT_TYPE = "kiro-cli"
DEFAULT_KIRO_CLI_HOME = ".kiro"
SKILLS_SUBDIR = "skills"
SKILLS_ROOT_LABEL = "~/.kiro/skills"
KIRO_CLI_ACCEPTED_INPUTS = (
    "kiro-cli",
    "kiro_cli",
    "kiro cli",
    "kirocli",
    "kiro",
    "kiro-cli-tui",
    "kiro tui",
)

# Native goal primitive built into the kiro-cli binary (probed live on
# kiro-cli 1.0.437 / TUI shell 2.21.1: `/goal` is present in the binary's
# slash-command registry and documented by the host's own `/goal` reference).
# The host owns the iteration loop: it re-dispatches the turn until the model
# proves completion through the `goal` tool or the iteration budget runs out.
KIRO_CLI_GOAL_COMMAND = "/goal"
KIRO_CLI_GOAL_CLEAR_COMMAND = "/goal clear"
KIRO_CLI_GOAL_MAX_FLAG = "--max"
KIRO_CLI_GOAL_DEFAULT_MAX_ITERATIONS = 5
KIRO_CLI_GOAL_MAX_ITERATION_CEILING = 50
KIRO_CLI_GOAL_COMPLETION_TOOL = "goal"
KIRO_CLI_GOAL_TERMINAL_STATES = ("completed", "exhausted")

# Kiro CLI stamps every session with a stable id, which is what a LoopX
# thread binding can key on instead of prose.
KIRO_CLI_SESSION_ID_ENV = "KIRO_SESSION_ID"

# The host ships a real hook seam, and `preToolUse` can block a tool call by
# exiting 2. LoopX installs no hook today, so quota pacing stays advisory; the
# seam is recorded here so the honest claim and the future binding point stay
# in one place instead of being rediscovered from host docs.
KIRO_CLI_HOOK_TRIGGERS = (
    "agentSpawn",
    "userPromptSubmit",
    "preToolUse",
    "postToolUse",
    "stop",
)
KIRO_CLI_HOOK_CONFIG_LABEL = "~/.kiro/agents/<name>.json (or .kiro/agents/<name>.json)"

KIRO_CLI_NATIVE_GOAL_FACTS = (
    "native `/goal <description> [--max N]` command: the host re-dispatches "
    "turns toward one objective until completion is proven or the iteration "
    "budget is spent (default 5, ceiling 50)",
    "the built-in `goal` tool's `complete` command enforces a completion "
    "contract: every success criterion needs cited tool output, not narrative "
    "confidence",
    "`/goal clear` cancels the active goal; the loop also stops on Exhausted "
    "and pauses after 3 consecutive dispatch failures",
    "`hooks` in the agent config expose agentSpawn/userPromptSubmit/"
    "preToolUse/postToolUse/stop, and preToolUse can block a tool call with "
    "exit code 2",
)

KIRO_CLI_AGENT_TYPE_CATALOG_ENTRY: dict[str, Any] = {
    "display_name": "Kiro CLI",
    "host_loop": (
        "Kiro CLI native /goal iteration loop bounded by the host's own "
        "iteration budget (LoopX quota pacing is advisory)"
    ),
    "entry": f"/loopx <task> from the LoopX skill installed in {SKILLS_ROOT_LABEL}",
    "accepted_inputs": list(KIRO_CLI_ACCEPTED_INPUTS),
}


def kiro_cli_activation_extras() -> dict[str, Any]:
    """Keyword overrides for ``_kiro_cli_activation``'s facade call.

    Keeps the Kiro CLI host facts (goal command, iteration budget, completion
    tool, gate text, activation steps) in this package instead of growing
    ``host_loop_activation.py`` past its module metric budget. Kiro CLI ships
    both halves of a goal-mode host: a native goal primitive — ``/goal <task>
    [--max N]`` whose host-side loop re-dispatches turns until the model
    proves completion through the ``goal`` tool — and a bounded iteration
    budget the host itself enforces (default 5, ceiling 50). What it does not
    ship is a cross-session daemon, and LoopX installs no hook, so quota
    pacing is instructed rather than enforced.
    """
    return {
        "activation_method": "bind_native_goal_with_advisory_quota_entry",
        "extra_host_mutation": {
            "host_loop_primitive": "kiro-cli-/goal-iteration-loop",
            "loop_driver": "kiro_cli_native_goal_loop",
            "quota_gate_enforcement": "advisory_only",
            "native_goal_command": KIRO_CLI_GOAL_COMMAND,
            "native_goal_cancel_command": KIRO_CLI_GOAL_CLEAR_COMMAND,
            "native_goal_max_flag": KIRO_CLI_GOAL_MAX_FLAG,
            "native_goal_default_max_iterations": (
                KIRO_CLI_GOAL_DEFAULT_MAX_ITERATIONS
            ),
            "native_goal_max_iteration_ceiling": (
                KIRO_CLI_GOAL_MAX_ITERATION_CEILING
            ),
            "native_goal_completion_tool": KIRO_CLI_GOAL_COMPLETION_TOOL,
            "host_session_id_env": KIRO_CLI_SESSION_ID_ENV,
            "host_hook_triggers": list(KIRO_CLI_HOOK_TRIGGERS),
            "missing_host_tool_gate": (
                "Kiro CLI's /goal loop runs only while the CLI session is "
                "alive; there is no cross-session daemon and the host caps it "
                f"at {KIRO_CLI_GOAL_MAX_ITERATION_CEILING} iterations. LoopX "
                "installs no Kiro hook, so no host hook intercepts a native "
                "iteration and quota pacing is advisory: the facade instructs, "
                "it cannot enforce. If the goal reaches Exhausted or the "
                "session ends with work remaining, show the exact "
                "heartbeat-prompt command for the user to run and do not "
                "claim unattended heartbeat support."
            ),
        },
        "extra_activation_steps": [
            "Bind the objective with the native goal command: "
            f"`{KIRO_CLI_GOAL_COMMAND} <task_body> {KIRO_CLI_GOAL_MAX_FLAG} <N>` "
            "— choose N from the remaining quota slots, not from ambition, and "
            f"never above the host ceiling of "
            f"{KIRO_CLI_GOAL_MAX_ITERATION_CEILING} "
            f"(host default is {KIRO_CLI_GOAL_DEFAULT_MAX_ITERATIONS}); "
            f"`{KIRO_CLI_GOAL_CLEAR_COMMAND}` cancels it.",
            "Start every turn and native goal iteration with `quota "
            "should-run` and honor a stop/throttle decision before any "
            "delivery work — instructed pacing, not a host-enforced gate.",
            f"Settle the goal through the built-in `{KIRO_CLI_GOAL_COMPLETION_TOOL}` "
            "tool only after LoopX writeback: its completion contract wants "
            "the same cited evidence LoopX records, so cite the validated "
            "commands rather than a narrative summary.",
            "When the goal reports Exhausted and quota still allows more "
            "work, re-arm one further bounded goal instead of free-running, "
            "and re-enter through `quota should-run` on the same advisory "
            "basis.",
        ],
        "host_scheduler_note": (
            "the native `/goal` iteration loop drives this session within the "
            "host's own iteration budget; quota should-run entry is advisory "
            "guidance in the facade, not a host-enforced gate."
        ),
    }


def kiro_home(value: str | None = None) -> Path:
    """The fixed Kiro CLI home: ``~/.kiro``.

    Kiro CLI discovers global skills from ``~/.kiro/skills/<name>/SKILL.md``
    and workspace skills from ``.kiro/skills/<name>/SKILL.md``; the default
    agent carries both as ``skill://`` resources. The host documents no home
    override for this root (``KIRO_AGENT_CONFIG_DIR`` relocates agent configs
    only, not skills), so LoopX exposes none either: installs target exactly
    this path, HOME-relative so tests stay hermetic. ``value`` is an internal
    injection point for tests, not a public override.
    """
    raw = value or str(Path.home() / DEFAULT_KIRO_CLI_HOME)
    return Path(raw).expanduser()
