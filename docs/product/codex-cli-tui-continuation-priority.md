# Codex CLI TUI Continuation Priority

Status: scheduling contract for the next Codex CLI product slice.

This note exists because a side-agent can drift toward visible, easy-to-ship
frontstage work even when the user has just steered the product priority back
to Codex CLI TUI adoption. Frontstage and showcase work are important support
surfaces, but they must not outrank a runnable Codex CLI TUI continuation task.

## Product Priority

The near-term product promise is:

1. a user opens Codex CLI TUI in a project repo;
2. one pasted LoopX message starts the loop;
3. LoopX can later steer or resume work through the same visible TUI
   whenever Codex exposes a safe attach primitive;
4. the user can keep watching, interrupt, steer, review, or take over.

The first message is already documented. The next priority is the second half:
prove a later visible steering turn after the first TUI bootstrap, or record the
exact blocker that prevents it.

## Scheduling Rule

When LoopX chooses between runnable productization tasks:

- Codex CLI TUI continuation wins over frontstage polish, showcase copy, or
  dashboard route work when the continuation task is runnable and in scope.
- Frontstage and showcase work can run first only when the TUI continuation is
  concretely gated by missing proof, missing CLI capability, user decision, or
  a higher-risk runtime boundary.
- If LoopX selects frontstage work while a Codex CLI TUI continuation
  task is runnable, the agent should treat that as a planning drift and run
  self-repair before writing code.

This is not a permanent global priority. It is a current product-stage rule:
the most valuable external-developer path is fast Codex CLI adoption without
losing the trusted TUI.

## Acceptance Target

The next useful Codex CLI TUI continuation slice should produce public-safe
evidence for one of these outcomes:

- `same_tui_continuation_proven`: a later LoopX steering prompt is added
  to the same open Codex CLI TUI session, with visible proof and runtime idle
  evidence.
- `same_tui_continuation_blocked`: the current Codex CLI surface cannot safely
  accept a later visible turn; the blocker names the missing primitive and the
  fallback remains manual paste or explicit `codex exec`.
- `same_tui_continuation_gated`: the task cannot run because it would require
  raw transcripts, session files, private material, credentials, or production
  actions.

The evidence must stay transcript-free. It may use public-safe fixtures,
boolean capability probes, visible-window metadata, and compact writeback
records, but must not read raw Codex transcripts, session files, hidden TUI
buffers, credentials, or private project state.

## Agent Reminder

If a heartbeat, quota summary, or claimed advancement lane recommends
frontstage while recent user steering says Codex CLI TUI continuation should
come first, the agent should:

1. inspect the current runnable todo list;
2. prefer the Codex CLI TUI continuation todo if it is runnable;
3. write back the reason if it is not runnable;
4. only then advance frontstage or showcase support work.

This keeps fancy demo surfaces aligned with the more important adoption path:
LoopX should be easy to start from inside the TUI that developers
already trust.
