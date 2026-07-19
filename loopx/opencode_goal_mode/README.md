# LoopX OpenCode adapter

LoopX exposes two separate OpenCode layers: a static command facade and an
optional executable goal bridge. Ordinary command installation never activates
the runtime bridge.

## Install

The default `all` surface installs only static files under
`~/.config/opencode/commands/`:

```bash
loopx slash-commands --install
```

Enable the goal bridge explicitly:

```bash
loopx slash-commands --install --surface opencode --with-goal-bridge
```

Before writing any OpenCode file, bridge installation validates
`opencode.json`, `opencode.jsonc`, and `package.json`. It fails closed if a
config is invalid or directly registers `opencode-goal-plugin`, because loading
that plugin beside the LoopX wrapper would start two independent goal runtimes.

After preflight succeeds, the installer writes the command facade plus:

- `~/.config/opencode/plugins/loopx-goal.js`;
- `~/.config/opencode/loopx/goal-bridge-runtime.mjs`;
- pinned bridge dependencies in `~/.config/opencode/package.json`.

OpenCode runs `bun install` for config-directory dependencies at startup.
Restart OpenCode after bridge installation so it installs those dependencies
and loads the local plugin.

## Runtime

Run `/loopx <task>`, then activate the returned host packet through
`loopx_goal_activate`. The runtime flow is:

```text
OpenCode idle event -> loopx quota should-run
  -> run_now: continue once
  -> wait: schedule a bounded local recheck without a model call
  -> pause: remain stopped for user, permission, or session intervention
  -> terminal_no_followup: submit completion and revalidate it in the auditor
```

Bindings are private per-session JSON files under
`$LOOPX_OPENCODE_STATE_DIR`, or `$XDG_STATE_HOME/loopx/opencode` by default,
and use mode `0600`. OpenCode's one-shot `opencode run` process cannot own
timers after exit; recurring operation requires the visible TUI or a persistent
OpenCode server.

## Uninstall

Remove only the static command facade:

```bash
loopx slash-commands --uninstall --surface opencode
```

Remove the static facade and LoopX-managed bridge files:

```bash
loopx slash-commands --uninstall --surface opencode --with-goal-bridge
```

Bridge uninstall preserves `package.json` dependencies because user-owned
local plugins may share them.
