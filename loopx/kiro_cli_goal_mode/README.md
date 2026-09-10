# Kiro CLI goal mode

LoopX adapter for [Kiro CLI](https://kiro.dev/) (binary `kiro-cli`) — a
terminal coding agent with skills, steering files, agent configs, hooks, MCP,
and a native goal loop. Kiro CLI ships both halves of a goal-mode host: a goal
primitive *and* a host-enforced iteration budget, so LoopX binds the objective
to the host's own loop instead of pretending the agent merely drives itself.

## Native goal primitive

`/goal [--max N] <description> | clear` — the built-in command as the host
contracts it. The host re-dispatches turns toward the stated objective, verifies
each iteration against the acceptance criteria it derives from the goal
statement, and the model must prove completion through the built-in `goal` tool
before the loop ends.

- Iteration budget: the host default is `5`, raised with `--max`. The flag
  precedes the description, and everything after it is the goal statement.
- **Acceptance criteria travel inside the description.** The host derives them
  from the goal statement, so LoopX appends the criteria its todo already owns
  (after `Done when:`) instead of passing a separate flag. There is no criteria
  flag to pass: an unrecognised flag after the description would be read as more
  goal text, polluting the objective and silently dropping `--max`.
- `/goal clear` cancels the active goal. A running goal is steered in place
  rather than read back — the host advertises no goal status subcommand.
- The `goal` tool's `complete` command enforces a completion contract: each
  success criterion needs cited tool output, and belief or narrative
  confidence is explicitly not evidence — the same standard LoopX writeback
  wants.

The contracted surface is checked against the host itself, not transcribed. The
installed binary advertises its own command registry over ACP, so the shape can
be replayed on any machine that has the CLI:

```bash
python3 examples/kiro-cli-goal-command-contract-probe.py
```

It asserts that `/goal` exists and that its advertised subcommands are exactly
the ones LoopX projects. An earlier revision of this document claimed
`--validate`, `--agent` and `/goal status` and cited a `strings` probe of the
binary; that probe returns nothing on the shipped app bundle, and neither the
published command reference nor the host's own registry contracts those
arguments, so they are no longer projected.

## Native hook seam

Agent configs (`~/.kiro/agents/<name>.json` or `.kiro/agents/<name>.json`)
carry `hooks` for `agentSpawn`, `userPromptSubmit`, `preToolUse`,
`postToolUse`, and `stop`; a `preToolUse` hook can block a tool call by exiting
`2`. That is a real machine-enforceable seam, but **LoopX installs no Kiro
hook today**, so this surface does not claim enforcement. The trigger list is
recorded in `__init__.py` so a future enforced-quota binding has one place to
start from rather than rediscovering it from host docs.

## What this surface is

Kiro CLI discovers global skills from `<KIRO_HOME>/skills/<name>/SKILL.md`
(`~/.kiro` when `KIRO_HOME` is unset) and workspace skills from
`.kiro/skills/<name>/SKILL.md`; the default agent carries
both as `skill://` resources, and every discovered skill is invocable as a
`/<skill-name>` slash command with `$ARGUMENTS` expansion. LoopX reaches a
Kiro CLI session through the generated `/loopx` skill facade, and the
activation binds the objective with the native
`/goal --max <N> <task_body> Done when: <criteria>`.

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
`loopx-global-*/SKILL.md`, …) into `<KIRO_HOME>/skills/` using Kiro's per-skill
directory layout. `KIRO_HOME` is the host's own override for that global root,
so LoopX resolves it and falls back to `~/.kiro` when it is unset; install and
uninstall always target the same resolved root. Managed files carry the
`loopx-managed-slash-command` marker and are refreshed by rerunning the
installer; user-owned files are never overwritten.

## Use

From a Kiro CLI session in a connected project, run `/loopx <complex task>`.
The facade instructs the agent to run:

```bash
loopx start-goal --guided --project . --slash-command-arguments="<task>" --host-surface kiro-cli
```

After todo writeback, bind the generated heartbeat task body with
`/goal --max <N> <task_body> Done when: <criteria>` — stating the criteria the
todo already names inside the goal statement, because the host derives its
acceptance criteria from that statement rather than from a flag, and `N` taken
from the remaining quota slots (host default is 5) — steer a running goal in
place rather than expecting a status readback, start every
turn and native goal iteration with `quota should-run` (advisory guidance;
LoopX does not intercept native host iterations), and settle through the
built-in `goal` tool only after LoopX writeback so the cited evidence matches
what LoopX recorded.

Kiro CLI exports `KIRO_SESSION_ID` for every session; it is the stable value a
LoopX thread binding should key on instead of prose.

## Dashboard and Chat agent

Kiro CLI also ships an ACP agent (`kiro-cli acp`), so `loopx dashboard` and
`loopx chat` list **Kiro CLI** as a built-in Agent alongside Codex and Claude
Code. It reuses `loopx.chat_acp.ACPStdioAdapter` rather than a second
transport: probed on 2.21.1, the host answers `initialize` with
`protocolVersion: 1` and `loadSession: true`, and `session/new` returns a
session id, which is exactly what that adapter expects.

```bash
loopx dashboard                                  # Kiro CLI appears when it is on PATH
loopx dashboard --kiro-cli-bin /path/to/kiro-cli # explicit executable
```

Two boundaries this does **not** cross:

- **Owner-managed host permissions.** LoopX Chat answers every interactive ACP
  `session/request_permission` with `cancelled`, exposes no client host tools,
  and launches without `--trust-all-tools`. Kiro can still execute a tool
  without asking when its user, workspace, or agent permission rules already
  say `allow`; LoopX cannot turn those persistent host rules into a read-only
  sandbox. The capability therefore advertises `workspace_write`, and the
  owner must configure Kiro permissions for the desired boundary. A planning
  prompt or a cancelled request is not an authority gate.
- **Not the governed loop.** A dashboard Chat session is one bounded
  conversation. The `/goal` loop above is entered from a Kiro CLI session
  through the installed skill facade; the two surfaces share the host, not the
  loop.

The built-in id `kiro-cli` is reserved in the owner-local endpoint registry so
a hand-registered endpoint cannot silently shadow it.

## Control-plane identity

Serving an Agent row is not the same as being reachable. Three surfaces resolve
a host by identity, and each one needs Kiro CLI in its table:

- **Endpoint to Goal agent.** A durable Goal agent id is operator-chosen, so
  `chat_actions` collapses both onto a host family: Endpoint `kiro-cli`
  resolves a registered `kiro-worker-1`, the same way `codex` resolves
  `codex-main-control`. Without the row, selecting Kiro CLI in the workspace
  raised `agent_binding_required` for an agent the user did register.
- **Host thread binding.** `KIRO_SESSION_ID` is read for the `kiro-cli` host
  surface, so `start-goal` binds the live session instead of leaving the thread
  unbound.
- **Project skills.** `loopx project-skill --surface kiro-cli` delivers into
  `.kiro/skills`, the workspace skills root Kiro discovers per project.

## Layout

- `__init__.py` — host facts: install surface id, fixed skills root resolution,
  the agent-type catalog entry, the activation extras (native goal command,
  host iteration budget, completion tool, advisory quota boundary), and the
  Chat/ACP launch facts the dashboard's built-in Agent row is built from.
