# Codex CLI Same-Open-TUI Continuation Observation

Status: same-open-TUI bootstrap continuation observed; scheduled same-TUI
automation still blocked.
Recorded: 2026-06-21.

This note records a public-safe observation from a live Codex CLI TUI session.
It is intentionally narrower than a new runtime packet contract. The evidence
is about the interactive one-message path staying visible in the same open TUI,
not about a scheduler injecting future prompts into a hidden or detached
session.

## Question

Can a user start LoopX with one Codex CLI TUI message and keep the same
visible TUI as the place to watch, steer, review, and take over through the
initial LoopX guard and steering step?

## Observation

Yes, for the interactive bootstrap continuation path.

In the observed session:

- the operator started from an already visible Codex CLI TUI and explicitly
  asked LoopX to keep that TUI as the primary surface;
- the agent first showed the current goal id, concrete user gate, top user todo,
  top agent todo, and next safe action before running longer work;
- the registered-agent quota guard initially returned a side-agent workspace
  repair, and that repair was handled visibly by switching shell work to an
  independent side-agent worktree rather than using hidden headless execution;
- the same registered-agent quota guard then returned `decision=run` and
  `effective_action=normal_run` from the independent worktree;
- subsequent steering stayed in the same visible TUI session, with no switch to
  headless `codex exec` as the primary path.

The observation did not read raw Codex transcripts, session files, stdout or
stderr streams, credentials, screenshots, local private material, or hidden TUI
buffers. It did not mutate hidden Codex session state.

## Result

`same_open_tui_bootstrap_continuation_observed`: yes.

This proves the manual, user-observed continuation after a one-message TUI
bootstrap can remain in the same open TUI through the first guard, workspace
repair, and steering decision.

`scheduled_same_tui_attach_proven`: no.

The current acceptance packet still requires a public-safe visible-session proof
fixture before promoting a later automated same-TUI steering turn. Local idle
flags alone are insufficient, and the packet correctly returns
`visible_session_proof_required` when no proof fixture is supplied.

## Product Decision

Keep the product path as:

1. user opens Codex CLI TUI in the project repo;
2. user pastes one LoopX bootstrap message;
3. LoopX shows the compact control-plane snapshot and, if quota allows,
   performs one bounded visible segment in that same TUI;
4. later automation remains blocked until visible-session proof and runtime-idle
   evidence pass;
5. `codex exec` remains an explicit headless fallback, not the default
   interactive path.

This keeps the trusted TUI front and center while avoiding a premature claim
that LoopX can safely inject future scheduled turns into the same open
session.

## Validation

Public-safe validation commands for this observation:

```bash
loopx --format json --registry "$HOME/.codex/loopx/registry.global.json" \
  quota should-run --goal-id loopx-meta --agent-id codex-side-bypass
```

From the independent side-agent worktree this returned `decision=run` and
`effective_action=normal_run`.

```bash
loopx --format json codex-cli-visible-attach-acceptance \
  --project . \
  --goal-id loopx-meta \
  --agent-id codex-side-bypass \
  --observed-surface same_tui_visible_attach \
  --turn-state idle \
  --human-input-idle-seconds 30 \
  --min-human-input-idle-seconds 5 \
  --checked-before-prompt \
  --visible-to-user \
  --user-can-interrupt \
  --manual-takeover-available
```

Without a proof fixture this returned `decision=visible_session_proof_required`,
which is the intended blocker for scheduled same-TUI automation.
