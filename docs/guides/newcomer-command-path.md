# Newcomer Command Path

LoopX should feel like one product path before it feels like a CLI catalog.
For a first-time user, the default surface is:

1. Install or repair the CLI.
2. Ask an agent to connect the current project.
3. Use `/loopx <goal>` to start useful work.

The full command set remains available for operators and contributors, but it
should not be the first thing a newcomer has to understand.

## The Two Commands To Remember

| Need | Use | Expected result |
| --- | --- | --- |
| Check whether this project is connected and what is waiting. | `/loopx` | The agent reads LoopX status, gates, todos, and next safe action without starting a new delivery path. |
| Start a concrete long-running goal. | `/loopx <goal text>` | The agent plans first, writes ordered todos, then advances one bounded, validated slice at a time. |

Examples:

```text
/loopx fix the open PR review feedback and keep the patch reviewable
/loopx split this refactor into PR-sized slices and stop at unsafe gates
```

## One CLI Quickstart

Use this when an agent asks for the manual shell path, or when you are setting
up a fresh terminal without an agent driving the first step:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
loopx bootstrap-command-pack --project .
```

The command pack is a bridge from manual shell setup back to the agent surface:
paste the generated instruction into Codex, Claude Code, or another compatible
agent that can run shell commands from the project root.

## Multi-Project Manager Commands

Keep these out of the first two commands, but do show them once a user has more
than one LoopX project or agent lane:

| Need | Use |
| --- | --- |
| See the cross-project progress digest. | `/loopx-global-summary` |
| See only user or owner gates. | `/loopx-global-gates` |
| See runnable project-agent work. | `/loopx-global-todos` |
| See risks and blocked lanes. | `/loopx-global-risks` |

These are manager views. They should summarize and route work across projects;
they should not replace `/loopx <goal>` as the way to start useful work inside
one repository.

## When To Use More Commands

| If you are trying to... | Use this surface first | Only then reach for... |
| --- | --- | --- |
| Start work on a goal | `/loopx <goal text>` | `loopx bootstrap-command-pack --goal-text ...` when manually bootstrapping an agent. |
| Understand several LoopX projects at once | `/loopx-global-summary` | `/loopx-global-gates`, `/loopx-global-todos`, or `/loopx-global-risks` when you need a focused manager view. |
| Understand why work is paused | `/loopx` | `loopx diagnose --goal-id <goal-id>` when the agent needs a deeper evidence packet. |
| Review a handoff or gate | The agent's LoopX status summary | `loopx review-packet --goal-id <goal-id>` for a copyable operator packet. |
| Operate recurring work | Codex App heartbeat or visible Codex CLI goal | `loopx heartbeat-prompt --thin --goal-id <goal-id>` when installing or repairing the loop. |
| Debug the control plane | The specific error or blocked todo | `loopx status`, `loopx history`, `loopx quota should-run`, or `loopx check`. |

## Reference Boundary

The command catalog is reference material. Keep it useful, but keep it below
the product path:

- New users should not need to scan every command before trying LoopX.
- Public examples should prefer `/loopx <goal>` unless they are teaching
  installation, debugging, or maintainer workflows.
- Contributors may still use the full command reference in
  [Getting started](getting-started.md#command-reference).
