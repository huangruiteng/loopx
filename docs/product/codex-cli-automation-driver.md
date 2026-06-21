# Codex CLI Automation Driver Audit

Status: product contract and implementation target.

LoopX should make Codex CLI feel easy before it feels automated. The
primary path is still the Codex TUI: the user starts from a project repo, sends
one Goal-Harness-generated message, and can keep watching, steering, reviewing,
or taking over. Automation is allowed only when it preserves that visible
control surface. The default `/goal` product path does not offer headless
fallback.

## Current Finding

The current local Codex CLI help surface exposes useful execution and session
primitives:

- `codex [PROMPT]` starts the interactive TUI with an initial prompt.
- `codex resume [SESSION_ID] [PROMPT]` can resume an interactive session and
  start it with a prompt.
- `codex exec [PROMPT]` runs a non-interactive executor loop.
- `codex --remote <ADDR>`, `codex app-server`, and `codex remote-control` expose
  experimental app-server / remote-control surfaces worth probing.

It does not expose a mature native recurring scheduler for LoopX. Treat
recurrence as a LoopX local-driver concern until Codex provides a
first-class automation primitive.

The important product distinction is:

| Surface | What It Proves | What It Does Not Prove |
| --- | --- | --- |
| `codex [PROMPT]` | one-message TUI bootstrap is viable | scheduled wakeups |
| `codex resume ... [PROMPT]` | a visible resume proof is plausible | safe injection into an already-open TUI |
| `codex exec` | non-interactive execution exists | preserved TUI experience or default LoopX fallback |
| `remote-control` / app-server | a future visible-control bridge may exist | production-safe LoopX driver semantics |

## Driver Shape

The v0 driver should be explicit and conservative:

1. A scheduler wakes up: manual command, `launchd`, cron, or a future local
   daemon.
2. The driver runs `loopx quota should-run --goal-id <goal> --agent-id
   <agent>`.
3. If user action is required, the driver surfaces only the concrete user gate
   and stops.
4. If the side-agent workspace guard fires, the driver relocates to an
   independent worktree before any file edit.
5. The driver runs `loopx codex-cli-visible-driver-plan`.
6. If the plan proves a visible attach path, the driver may attempt a visible
   `resume` / remote-control turn behind an idle guard.
7. If no visible attach path is proven, the driver keeps TUI bootstrap primary.
   `loopx codex-cli-exec-handoff` reports the disabled boundary and does
   not print a runnable `codex exec` script.
8. The driver spends quota only after validated writeback.

The local driver must never read or publish:

- raw Codex transcripts;
- credentials;
- hidden session files;
- private logs;
- local LoopX runtime state that would leak into public docs or
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

- One pasted TUI message can start the LoopX loop in a repo.
- A scheduled driver can decide whether work is allowed without reading private
  Codex session data.
- A visible resume / remote-control proof shows the turn is visible,
  interruptible, and idle-guarded before LoopX calls it
  session-attached automation.
- Headless `codex exec` is disabled for the default `/goal` product path, not a
  named fallback.
- Every automatic turn writes compact evidence or a precise blocker before
  quota spend.

## Current MVP

The dry-run-first local driver planner composes the existing quota, TUI,
visible-driver, and headless-disabled boundary into one operator-facing packet:

```bash
loopx codex-cli-local-driver-plan --project . --goal-id <goal> --agent-id <agent>
```

It is intentionally not a scheduler yet. It does not run Codex, read raw
transcripts, inspect session files, mutate a Codex session, or spend Goal
Harness quota. It emits:

- the quota guard command that must run before work;
- the visible-driver decision for TUI bootstrap, visible attach proof, or
  resume/remote-control spike;
- the repo-specific TUI bootstrap message command;
- the disabled `codex exec` boundary;
- the idle-guard placeholder that must exist before any same-session attach is
  treated as production automation.

A separate proof harness validates whether a resume or remote-control
observation is strong enough to become a same-session automation candidate:

```bash
loopx codex-cli-visible-session-proof \
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
loopx codex-cli-visible-driver-run --project . --goal-id <goal> --agent-id <agent>
```

This is still a run packet, not a Codex runner. It does not run Codex, read raw
transcripts, inspect session files, mutate a Codex session, or spend Goal
Harness quota. It only chooses the next safe boundary:

- require a public-safe visible-session proof before any resume or
  remote-control path is treated as same-session automation;
- keep the TUI bootstrap as the default when no proof exists;
- never emit a headless `codex exec` fallback command from the default `/goal`
  product path;
- mark a visible session as a candidate only when the proof fixture confirms
  user opt-in, quota guard, idle guard, visibility, interruptibility, boundary,
  and compact writeback planning.

The first local scheduler-facing spike wraps that packet as a one-shot tick:

```bash
loopx codex-cli-local-scheduler-tick --project . --goal-id <goal> --agent-id <agent>
```

This command is still no-execution by design. A launchd/cron/local-daemon
wrapper can call it and receive one of two safe outputs:

- a candidate external command, when visible-session proof is present;
- a precise blocker writeback command, when proof is missing.

The tick itself does not run Codex, read transcripts, inspect session files,
mutate sessions, write LoopX state, or spend quota. That boundary keeps
the product path honest: first make the scheduler decision visible and
reviewable, then implement the actual external executor only after the proof
and opt-in contract is stable.

The next wrapper is the first explicit executor mode:

```bash
loopx codex-cli-local-scheduler-exec --project . --goal-id <goal> --agent-id <agent>
```

By default it still executes nothing. It builds the same scheduler tick and
prints an executor packet. A local scheduler may opt into exactly one side
effect:

```bash
loopx codex-cli-local-scheduler-exec \
  --project . \
  --goal-id <goal> \
  --agent-id <agent> \
  --guard-checked \
  --execute-candidate \
  --candidate-command-prefix "codex resume"
```

or:

```bash
loopx codex-cli-local-scheduler-exec \
  --project . \
  --goal-id <goal> \
  --agent-id <agent> \
  --guard-checked \
  --execute-blocker-writeback
```

`--guard-checked` is an explicit assertion that the local scheduler just ran the
fresh quota/user-gate guard. Candidate execution additionally requires an
allowed command prefix, so a public-safe proof fixture cannot smuggle an
arbitrary shell command into the scheduler. The wrapper discards command
stdout/stderr, reports only return code and timeout, never reads transcripts or
session files, never mutates hidden Codex session state, and never spends Goal
Harness quota. Quota spend remains the responsibility of the validated
post-turn writeback path.

## Next Build Slice

Use the executor wrapper as the smallest local-driver bridge, then move toward
the real product loop: one TUI message starts LoopX, recurring wakeups
run the guard, a visible same-session turn is attempted only after proof and
idle checks, and headless `codex exec` remains disabled for the default
`/goal` path.
