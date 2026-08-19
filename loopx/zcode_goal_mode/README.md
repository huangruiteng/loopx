# ZCode goal mode

LoopX adapter for [ZCode](https://github.com/) — a terminal coding agent whose
extension points are markdown skills and hooks, not a goal primitive or a host
automation scheduler.

## What this surface is

ZCode discovers skills the same way the other skill-facade CLI hosts do: a
directory per skill with a `SKILL.md` inside. LoopX therefore reaches a ZCode
session through the generated `/loopx` skill facade only, and the loop driver is
the agent's own turn loop gated by LoopX quota — every continuation enters
through `quota should-run`, and a stop decision ends the session loop.

This is a weaker guarantee than a host-owned loop and is stated as such in the
activation packet; claiming heartbeat support ZCode cannot deliver would be
worse than admitting the agent drives itself.

## Install

```bash
loopx slash-commands --install --surface zcode
```

Writes the managed LoopX skill facades (`loopx`, `loopx-global-*`, …) into
`AGENTS_HOME/skills` (default `~/.agents/skills`; override with
`ZCODE_AGENTS_HOME`). Managed files carry the `loopx-managed-slash-command`
marker and are refreshed by rerunning the installer; user-owned files are never
overwritten.

## Use

From a ZCode session in a connected project, invoke the `loopx` skill (or type
`/loopx <complex task>`). The facade instructs the agent to run:

```bash
loopx start-goal --guided --project . --slash-command-arguments="<task>" --host-surface zcode
```

After todo writeback, carry the generated heartbeat task body as the session
objective and start every following turn with `quota should-run`.

## Layout

- `__init__.py` — host facts: install surface id, skills root resolution, and
  the env override used by the installer and the activation packet.
