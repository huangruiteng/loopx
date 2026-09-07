# Kiro CLI goal mode

LoopX adapter for [Kiro CLI](https://kiro.dev/) (binary `kiro-cli`) — a
terminal coding agent with skills, steering files, agent configs, hooks, MCP,
and a native goal loop. Kiro CLI ships both halves of a goal-mode host: a goal
primitive *and* a host-enforced iteration budget, so LoopX binds the objective
to the host's own loop instead of pretending the agent merely drives itself.

## Native goal primitive

`/goal <description> [--max N]` — built-in command. The host re-dispatches
turns toward the stated objective, and the model must prove completion through
the built-in `goal` tool before the loop ends.

- Iteration budget is host-enforced: default `5`, ceiling `50`. This is the
  one part of the loop LoopX does not have to trust the model for.
- `/goal clear` cancels the active goal. The loop also stops in `Exhausted`
  (budget spent without completion) and pauses after 3 consecutive dispatch
  failures.
- The `goal` tool's `complete` command enforces a completion contract: each
  success criterion needs cited tool output, and belief or narrative
  confidence is explicitly not evidence — the same standard LoopX writeback
  wants.

Verified against `kiro-cli 1.0.437` (TUI shell `2.21.1`): `/goal` is present
in the binary's slash-command registry, and the host's own `/goal` and `goal`
tool references document the iteration budget, terminal states, and completion
contract.

## Native hook seam

Agent configs (`~/.kiro/agents/<name>.json` or `.kiro/agents/<name>.json`)
carry `hooks` for `agentSpawn`, `userPromptSubmit`, `preToolUse`,
`postToolUse`, and `stop`; a `preToolUse` hook can block a tool call by exiting
`2`. That is a real machine-enforceable seam, but **LoopX installs no Kiro
hook today**, so this surface does not claim enforcement. The trigger list is
recorded in `__init__.py` so a future enforced-quota binding has one place to
start from rather than rediscovering it from host docs.

## What this surface is

Kiro CLI discovers global skills from `~/.kiro/skills/<name>/SKILL.md` and
workspace skills from `.kiro/skills/<name>/SKILL.md`; the default agent carries
both as `skill://` resources, and every discovered skill is invocable as a
`/<skill-name>` slash command with `$ARGUMENTS` expansion. LoopX reaches a
Kiro CLI session through the generated `/loopx` skill facade, and the
activation binds the objective with the native `/goal <task_body> --max <N>`.

Three honest limits, stated in the activation packet:

- **Quota pacing is advisory.** LoopX installs no Kiro hook that intercepts a
  native goal iteration, so `quota should-run` entry is facade guidance the
  agent is instructed to follow — not a host-enforced gate.
- **The loop lives and dies with the session.** The `/goal` loop runs only
  while the CLI session is alive; there is no cross-session daemon, so it
  bounds a live session's segments, not an unattended host loop.
- **A same-named file prompt wins.** Kiro resolves `.kiro/prompts/*.md` and
  `~/.kiro/prompts/*.md` before skills, so a user prompt named `loopx` shadows
  the managed skill. The installer never touches the prompt directories.

## Install

```bash
loopx slash-commands --install --surface kiro-cli
```

Writes the managed LoopX skill facades (`loopx/SKILL.md`,
`loopx-global-*/SKILL.md`, …) into `~/.kiro/skills/` using Kiro's per-skill
directory layout. The host documents no home override for this root
(`KIRO_AGENT_CONFIG_DIR` relocates agent configs only, not skills), so LoopX
offers none either: installs target exactly that path. Managed files carry the
`loopx-managed-slash-command` marker and are refreshed by rerunning the
installer; user-owned files are never overwritten.

## Use

From a Kiro CLI session in a connected project, run `/loopx <complex task>`.
The facade instructs the agent to run:

```bash
loopx start-goal --guided --project . --slash-command-arguments="<task>" --host-surface kiro-cli
```

After todo writeback, bind the generated heartbeat task body with
`/goal <task_body> --max <N>` — with `N` taken from the remaining quota slots
and never above the host ceiling of 50 — start every turn and native goal
iteration with `quota should-run` (advisory guidance; LoopX does not intercept
native host iterations), and settle through the built-in `goal` tool only after
LoopX writeback so the cited evidence matches what LoopX recorded.

Kiro CLI exports `KIRO_SESSION_ID` for every session; it is the stable value a
LoopX thread binding should key on instead of prose.

## Layout

- `__init__.py` — host facts: install surface id, fixed skills root resolution,
  the agent-type catalog entry, and the activation extras (native goal command,
  host iteration budget, completion tool, advisory quota boundary).
