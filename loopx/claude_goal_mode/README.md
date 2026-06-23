# loopx Claude Code adapter

LoopX is a deterministic (no-LLM) control plane. On Claude Code the **run loop is
Claude Code's native `/loop`**; LoopX provides the control-plane protocol. We do
**not** use `/goal` (it judges completion from the transcript, which conflicts
with LoopX's deterministic gate).

- **Runtime** — native `/loop`, which executes a project `.claude/loop.md`.
- **Control plane** — the LoopX MCP tools `should_run` / `claim_task` /
  `complete_task` (`should_run` is the deterministic per-tick gate).
- **Setup** — the `/loopx` command writes `.claude/loop.md` and registers the
  goal/agent. It only SETS UP a goal; the work runs under native `/loop`.
- **Optional hardening** — an opt-in `PreToolUse` `should_run` gate (`--harden`).

## Install (opt-in)

The adapter is **never** installed by the normal LoopX installer. You enable it
explicitly, and nothing is written to `~/.claude` unless you ask. `install.py`
**requires** an explicit `--scope`; **project** scope is preferred (it only
touches that project's `.claude/`), and **user** scope is announced because it
affects all your Claude Code projects.

### A. via the LoopX installer (opt-in env var, user scope)

```bash
LOOPX_INSTALL_CLAUDE=1 scripts/install-local.sh
```

Installs the MCP server + the `/loopx` command at **user** scope. **No hooks.**
Without `LOOPX_INSTALL_CLAUDE=1` the installer skips the adapter entirely.

### B. directly, with an explicit scope (project preferred)

```bash
# this project only (recommended)
python3 loopx/claude_goal_mode/scripts/install.py --scope project --project /path/to/project

# all your Claude Code projects (announced at install time)
python3 loopx/claude_goal_mode/scripts/install.py --scope user

# preview without writing anything
python3 loopx/claude_goal_mode/scripts/install.py --scope project --project /path/to/project --dry-run
```

### Optional hardening (`--harden`)

Adds an opt-in, **project-scoped** `PreToolUse` `should_run` gate (plus a
statusline). It deterministically **allows** in-scope edits/commands and
**denies** out-of-scope or destructive ones — and denies everything when
`should_run` is false — so `/loop` can run unattended without auto mode. Off by
default.

```bash
python3 loopx/claude_goal_mode/scripts/install.py --scope project --project /path/to/project --harden
```

It **never** deletes existing permission rules: a legacy LoopX credential-deny
(`Read(~/.ssh/**)` / `Read(~/.aws/**)`) gets a printed manual-cleanup suggestion
instead of being removed.

### One-shot connect (set up a goal + project-scoped install)

```bash
python3 loopx/claude_goal_mode/scripts/connect.py \
    --project /path/to/project --goal-id GOAL [--objective "..."] [--harden]
```

After installing, **restart any open Claude Code session** so the command and MCP
server load.

## Use

```
/loopx <task>     # set up a goal for this project + write .claude/loop.md
/loop             # native runtime drives the loop  (or `/loop 10m` for a fixed cadence)
/loopx status     # goal objective, state, and todos
/loopx off        # remove .claude/loop.md (native /loop then has nothing to run)
```

## Uninstall

```bash
claude mcp remove --scope <user|project> loopx        # MCP server
rm <scope>/.claude/commands/loopx.md                  # the /loopx command
```

If you ran `--harden`, remove the loopx `PreToolUse` block (and the `statusLine`)
from `<scope>/.claude/settings.json` by hand — the installer never edits your
existing rules for you.

## Test

```bash
python3 examples/claude-install-optin-smoke.py
```

Proves the normal install does not touch `~/.claude`, that an explicit `--scope`
is required, that project scope is isolated, that hooks are opt-in (`--harden`),
and that existing permission rules are preserved.
