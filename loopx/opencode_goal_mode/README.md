# LoopX OpenCode adapter

LoopX uses OpenCode's visible session as the executor and keeps scheduling truth
in `loopx quota should-run`. The adapter wraps `opencode-goal-plugin@0.6.5`
instead of loading that package directly, so every idle continuation and timer
wake passes through the LoopX quota contract first.

## Install

```bash
loopx slash-commands --install --surface opencode
```

The installer writes:

- `~/.config/opencode/commands/loopx*.md` for the LoopX command family;
- `~/.config/opencode/plugins/loopx-goal.js` for the local bridge;
- `~/.config/opencode/loopx/goal-bridge-runtime.mjs` for the tested runtime;
- pinned bridge dependencies in `~/.config/opencode/package.json`.

OpenCode runs `bun install` for config-directory dependencies at startup, so
the LoopX installer does not invoke a package manager. Restart OpenCode after
installation so it installs the pinned dependencies and loads the bridge.

Remove any direct `opencode-goal-plugin` entry from `opencode.json` or
`opencode.jsonc` before installation. Loading the npm plugin and the LoopX local
bridge together would create two independent goal runtimes, so installation
fails closed while that conflict exists.

## Goal start

Run `/loopx <task>` in OpenCode. After LoopX has planned and written todos, the
agent uses the returned host activation packet to call `loopx_goal_activate`
with `goalId` from the packet's goal id and `objective` from its heartbeat task
body. Pass `agentId`, `registryPath`, and `availableCapabilities` when those
optional values are present.

The bridge then applies this lifecycle:

1. `scheduler_hint.action=run_now` or `should_run=true`: allow one OpenCode goal
   continuation.
2. Quiet wait or user gate: make no model call and schedule a bounded local
   recheck using LoopX's unchanged-poll cadence.
3. Repeated unchanged decisions: apply the advertised progression and final
   replan limit without spending quota.
4. Validated `terminal_no_followup`: submit completion through the goal plugin;
   the custom auditor reruns LoopX quota and rejects any earlier completion.
5. User message, denied permission, or session error: pause automatic resume
   until the user explicitly resumes the goal.

The bridge also suppresses OpenCode 1.18's reflected `$ARGUMENTS` chat event for
the just-executed `/goal` command. Without that compatibility guard, the
underlying plugin interprets its own command payload as a new user intervention
and pauses a newly created goal before the first continuation.

Bindings are private per-session JSON files under
`$LOOPX_OPENCODE_STATE_DIR`, or under
`$XDG_STATE_HOME/loopx/opencode` by default, and are written with mode `0600`.
OpenCode's one-shot `opencode run` process cannot own timers after it exits; use
the visible TUI or a persistent OpenCode server for recurring goal operation.

## Uninstall

```bash
loopx slash-commands --uninstall --surface opencode
```

Uninstall removes only LoopX-managed command and bridge files. It preserves
`package.json` dependencies because user-owned local plugins may share them.
