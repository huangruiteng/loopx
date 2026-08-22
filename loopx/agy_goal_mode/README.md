# Antigravity CLI goal mode

LoopX adapter for the [Antigravity CLI](https://antigravity.google/docs/cli/using/)
(binary `agy`) — Google's terminal coding agent whose extension points are
markdown skills and MCP config. It has no persistent goal primitive (no
`/goal`, no goal store) for LoopX to bind, but it does ship native
in-session automation, so the loop is not waiting on the user to return.

## Native wake primitives (verified live on agy 1.1.18)

- `schedule` tool — `DurationSeconds` + `Prompt` (wake message), recurring
  wakes via `MaxIterations`, one-shot timers with early-termination
  conditions. Live probe: a turn that ended with "scheduled" at T received a
  SYSTEM_MESSAGE wake at T+25s and the session answered autonomously — no
  external driver, no user input.
- Background tasks (`manage_task`) and async subagents
  (`invoke_subagent`/`send_message`) wake a live session; agent messages land
  in the session inbox (`manage_inbox`).
- `hooks.json` (user or plugin) runs `PostToolUse`/`Stop`/`PostInvocation`
  automation on tool events.

These wakes only fire while the CLI session is alive — there is no
cross-session daemon — so they arm a live session's next bounded segment,
not an unattended host loop.

## What this surface is

Antigravity CLI discovers skills the same way the other skill-facade CLI hosts
do: a directory per skill with a `SKILL.md` inside, rooted at
`~/.gemini/antigravity-cli/skills`. LoopX therefore reaches an `agy` session
through the generated `/loopx` skill facade only. The loop driver is the
agent's own turn loop, and every continuation — each turn and each native
`schedule` wake — enters through LoopX `quota should-run`; a stop decision
ends the session loop.

The wake primitives make `agy` stronger than a plain turn-loop facade host:
when a turn ends with work remaining and quota allows more, the session can
arm its own next wake with `schedule` instead of idling. The guarantee is
still weaker than a host-owned loop (no daemon survives the CLI process) and
is stated as such in the activation packet.

## Install

```bash
loopx slash-commands --install --surface agy
```

Writes the managed LoopX skill facades (`loopx`, `loopx-global-*`, …) into
`AGY_CLI_HOME/skills` (default `~/.gemini/antigravity-cli/skills`; override
with `AGY_CLI_HOME` or `--agy-cli-home`). Managed files carry the
`loopx-managed-slash-command` marker and are refreshed by rerunning the
installer; user-owned files are never overwritten.

## Use

From an Antigravity CLI session in a connected project, invoke the `loopx`
skill (or type `/loopx <complex task>`). The facade instructs the agent to run:

```bash
loopx start-goal --guided --project . --slash-command-arguments="<task>" --host-surface agy
```

After todo writeback, carry the generated heartbeat task body as the session
objective, start every following turn (and every `schedule` wake) with
`quota should-run`, and arm the next bounded wake with the native `schedule`
tool only when quota allows more work.

## Layout

- `__init__.py` — host facts: install surface id, skills root resolution, the
  env override used by the installer and the activation packet, and the
  native wake primitives the activation cites.
