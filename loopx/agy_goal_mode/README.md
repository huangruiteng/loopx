# Antigravity CLI goal mode

LoopX adapter for the [Antigravity CLI](https://antigravity.google/docs/cli/using/)
(binary `agy`) — Google's terminal coding agent whose extension points are
markdown skills and MCP config, not a goal primitive or a host automation
scheduler.

## What this surface is

Antigravity CLI discovers skills the same way the other skill-facade CLI hosts
do: a directory per skill with a `SKILL.md` inside, rooted at
`~/.gemini/antigravity-cli/skills`. LoopX therefore reaches an `agy` session
through the generated `/loopx` skill facade only, and the loop driver is the
agent's own turn loop gated by LoopX quota — every continuation enters through
`quota should-run`, and a stop decision ends the session loop.

This is a weaker guarantee than a host-owned loop and is stated as such in the
activation packet; claiming heartbeat support `agy` cannot deliver would be
worse than admitting the agent drives itself.

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
objective and start every following turn with `quota should-run`.

## Layout

- `__init__.py` — host facts: install surface id, skills root resolution, and
  the env override used by the installer and the activation packet.
