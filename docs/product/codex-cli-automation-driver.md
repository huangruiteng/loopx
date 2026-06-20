# Codex CLI Automation Driver Audit

Status: product contract and implementation target.

Goal Harness should make Codex CLI feel easy before it feels automated. The
primary path is still the Codex TUI: the user starts from a project repo, sends
one Goal-Harness-generated message, and can keep watching, steering, reviewing,
or taking over. Automation is allowed only when it preserves that visible
control surface or falls back explicitly.

## Current Finding

The current local Codex CLI help surface exposes useful execution and session
primitives:

- `codex [PROMPT]` starts the interactive TUI with an initial prompt.
- `codex resume [SESSION_ID] [PROMPT]` can resume an interactive session and
  start it with a prompt.
- `codex exec [PROMPT]` runs a non-interactive executor loop.
- `codex --remote <ADDR>`, `codex app-server`, and `codex remote-control` expose
  experimental app-server / remote-control surfaces worth probing.

It does not expose a mature native recurring scheduler for Goal Harness. Treat
recurrence as a Goal Harness local-driver concern until Codex provides a
first-class automation primitive.

The important product distinction is:

| Surface | What It Proves | What It Does Not Prove |
| --- | --- | --- |
| `codex [PROMPT]` | one-message TUI bootstrap is viable | scheduled wakeups |
| `codex resume ... [PROMPT]` | a visible resume proof is plausible | safe injection into an already-open TUI |
| `codex exec` | headless fallback is viable | preserved TUI experience |
| `remote-control` / app-server | a future visible-control bridge may exist | production-safe Goal Harness driver semantics |

## Driver Shape

The v0 driver should be explicit and conservative:

1. A scheduler wakes up: manual command, `launchd`, cron, or a future local
   daemon.
2. The driver runs `goal-harness quota should-run --goal-id <goal> --agent-id
   <agent>`.
3. If user action is required, the driver surfaces only the concrete user gate
   and stops.
4. If the side-agent workspace guard fires, the driver relocates to an
   independent worktree before any file edit.
5. The driver runs `goal-harness codex-cli-visible-driver-plan`.
6. If the plan proves a visible attach path, the driver may attempt a visible
   `resume` / remote-control turn behind an idle guard.
7. If no visible attach path is proven, the driver keeps TUI bootstrap primary
   and offers `goal-harness codex-cli-exec-handoff` as an explicit headless
   fallback.
8. The driver spends quota only after validated writeback.

The local driver must never read or publish:

- raw Codex transcripts;
- credentials;
- hidden session files;
- private logs;
- local Goal Harness runtime state that would leak into public docs or
  fixtures.

## Scheduler Options

| Option | Good For | Not Good For | v0 Use |
| --- | --- | --- | --- |
| Manual command | transparent user testing | unattended work | default proof path |
| `launchd` | local recurring wakeups on macOS | cross-platform install, visible TUI attach by itself | first packaged scheduler |
| cron | simple Unix recurrence | user-friendly install, logs, env repair | documented fallback |
| GitHub Actions | public docs/build/status checks | local TUI, local credentials, workstation state | Pages and public bundle only |
| Local daemon | best long-term UX | install/update/auth complexity | later product milestone |

## Success Criteria

- One pasted TUI message can start the Goal Harness loop in a repo.
- A scheduled driver can decide whether work is allowed without reading private
  Codex session data.
- A visible resume / remote-control proof shows the turn is visible,
  interruptible, and idle-guarded before Goal Harness calls it
  session-attached automation.
- Headless `codex exec` remains a named fallback, not the default user story.
- Every automatic turn writes compact evidence or a precise blocker before
  quota spend.

## Current MVP

The dry-run-first local driver planner composes the existing quota, TUI,
visible-driver, and explicit fallback pieces into one operator-facing packet:

```bash
goal-harness codex-cli-local-driver-plan --project . --goal-id <goal> --agent-id <agent>
```

It is intentionally not a scheduler yet. It does not run Codex, read raw
transcripts, inspect session files, mutate a Codex session, or spend Goal
Harness quota. It emits:

- the quota guard command that must run before work;
- the visible-driver decision for TUI bootstrap, visible attach proof,
  resume/remote-control spike, or explicit headless fallback;
- the repo-specific TUI bootstrap message command;
- the explicit `codex exec` fallback generator;
- the idle-guard placeholder that must exist before any same-session attach is
  treated as production automation.

A separate proof harness validates whether a resume or remote-control
observation is strong enough to become a same-session automation candidate:

```bash
goal-harness codex-cli-visible-session-proof \
  --project . \
  --goal-id <goal> \
  --agent-id <agent> \
  --proof-fixture visible-proof.public.json
```

The fixture is public-safe and boolean-only: user opt-in, quota guard, idle
guard, visibility, interruptibility, private-data boundary, and compact
writeback planning. It does not run Codex or inspect session state.

The next v0 packet turns those dry-run pieces into one driver decision without
executing anything:

```bash
goal-harness codex-cli-visible-driver-run --project . --goal-id <goal> --agent-id <agent>
```

This is still a run packet, not a Codex runner. It does not run Codex, read raw
transcripts, inspect session files, mutate a Codex session, or spend Goal
Harness quota. It only chooses the next safe boundary:

- require a public-safe visible-session proof before any resume or
  remote-control path is treated as same-session automation;
- keep the TUI bootstrap as the default when no proof exists;
- require `--allow-headless-fallback` before emitting a headless `codex exec`
  fallback command;
- mark a visible session as a candidate only when the proof fixture confirms
  user opt-in, quota guard, idle guard, visibility, interruptibility, boundary,
  and compact writeback planning.

The first local scheduler-facing spike wraps that packet as a one-shot tick:

```bash
goal-harness codex-cli-local-scheduler-tick --project . --goal-id <goal> --agent-id <agent>
```

This command is still no-execution by design. A launchd/cron/local-daemon
wrapper can call it and receive one of two safe outputs:

- a candidate external command, when visible-session proof or explicit headless
  fallback opt-in is present;
- a precise blocker writeback command, when proof or opt-in is missing.

The tick itself does not run Codex, read transcripts, inspect session files,
mutate sessions, write Goal Harness state, or spend quota. That boundary keeps
the product path honest: first make the scheduler decision visible and
reviewable, then implement the actual external executor only after the proof
and opt-in contract is stable.

## Next Build Slice

Turn the scheduler tick into a real local driver only after the same-session
path has a visible, idle-guarded proof. Until then, the user-facing happy path
stays simple: start in Codex CLI TUI with one Goal Harness message, let the
local tick explain the next safe boundary, and use headless `codex exec` only
as an explicit opt-in fallback.
