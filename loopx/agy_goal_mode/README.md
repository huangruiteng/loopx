# Antigravity CLI goal mode

LoopX adapter for the [Antigravity CLI](https://antigravity.google/docs/cli/using/)
(binary `agy`) — Google's terminal coding agent. agy ships both halves of a
goal-mode host natively: a goal primitive and an in-session scheduler, so
LoopX binds the objective to the host's own loop instead of pretending the
agent merely drives itself.

## Native goal primitive (verified live on agy 1.1.18)

`/goal <task>` — built-in command, "Run until the specified goal is
completely finished." The host injects a forced-continuation contract that
keeps auditing the work until the model emits `<!-- GOAL_COMPLETE -->`
(cancel with `<!-- GOAL_CANCELLED -->`). Live evidence:

- Interactive TUI (tmux): `/goal Create the file … and verify …` ran
  "Initiating Goal Analysis", created the file, self-verified content, and
  completed — file landed on disk with exact content.
- Headless print mode: `agy -p '/goal just reply ok'` returned a response
  ending in `<!-- GOAL_COMPLETE -->`.
- The mechanism is built into the binary (command description,
  forced-continuation system prompt, `GoalState` persistence, both tokens).

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

## What this surface is

Antigravity CLI discovers global skills from the fixed
`~/.gemini/antigravity-cli/skills` root using its documented flat layout —
one `<name>.md` file per skill. LoopX reaches an `agy` session through the
generated `/loopx` skill facade, and the activation binds the objective with
the native `/goal <task_body>` command.

Two honest limits, stated in the activation packet:

- **Quota pacing is advisory.** LoopX installs no AGY hook that intercepts
  native continuations or wakes, so `quota should-run` entry is facade
  guidance the agent is instructed to follow — not a host-enforced gate. agy
  will continue natively without it.
- **Everything lives and dies with the session.** The goal loop and wakes
  fire only while the CLI session is alive — there is no cross-session
  daemon — so they arm a live session's bounded segments, not an unattended
  host loop.

## Install

```bash
loopx slash-commands --install --surface agy
```

Writes the managed LoopX skill facades (`loopx.md`, `loopx-global-*.md`, …)
flat into `~/.gemini/antigravity-cli/skills/` — the documented agy layout.
The official CLI documents no home override, so LoopX offers none either:
installs target exactly that path. Managed files carry the
`loopx-managed-slash-command` marker and are refreshed by rerunning the
installer; user-owned files are never overwritten.

## Use

From an Antigravity CLI session in a connected project, invoke the `loopx`
skill (or type `/loopx <complex task>`). The facade instructs the agent to run:

```bash
loopx start-goal --guided --project . --slash-command-arguments="<task>" --host-surface agy
```

After todo writeback, bind the generated heartbeat task body with the native
`/goal <task_body>`, start every following turn (and every `schedule` wake
and audit-continuation) with `quota should-run`, and arm the next bounded
wake with the native `schedule` tool only when quota allows more work.

## Layout

- `__init__.py` — host facts: install surface id, skills root resolution, the
  env override used by the installer and the activation packet, and the
  native goal + wake primitives the activation cites.
