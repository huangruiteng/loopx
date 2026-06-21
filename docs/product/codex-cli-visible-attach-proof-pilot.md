# Codex CLI Visible Attach Proof Pilot

Status: blocker recorded, TUI bootstrap remains primary.
Recorded: 2026-06-21.

This note records the first public-safe proof pilot for LoopX steering a
later Codex CLI turn without taking the user out of the visible TUI. It uses the
`codex-cli-visible-attach-acceptance` packet added in PR #383.

## Question

Can LoopX safely add a later steering turn to the same open Codex CLI TUI
session today?

## Result

Not yet.

The current Codex CLI help surface exposes promising `resume` /
`remote-control` style capabilities, so this remains worth exploring. But the
available help-only evidence does not prove a safe same-TUI attach primitive.
The acceptance packet returns:

- `decision`: `visible_session_proof_required`
- `accepted_for_same_tui_automation`: `False`
- `accepted_for_visible_later_turn`: `False`
- `driver_mode`: `visible_resume_or_remote_control_spike`
- blocker: `visible_session_proof_missing`

## Boundary

This pilot did not:

- run Codex CLI delivery;
- read raw transcripts;
- read session files;
- read stdout/stderr streams;
- read credentials;
- mutate a Codex session;
- spend LoopX quota by itself.

## Interpretation

`resume [PROMPT]` and `remote-control` are not enough on their own. They may be
usable as a visible spike, but LoopX should not call them
same-TUI automation until a public-safe proof shows:

- the resulting turn is visible to the user;
- the user can interrupt or take over;
- a runtime idle detector passed immediately before the turn;
- the route does not require transcript/session-file reads;
- compact evidence or a blocker will be written before quota spend.

Until that proof exists, the product-safe path stays:

1. Start from one Codex CLI TUI bootstrap message.
2. Keep later automation in no-execution packet mode.
3. Use `codex exec` only as an explicit opt-in headless fallback.

## Next Step

Run a visible `resume` / `remote-control` proof only when it can be captured as
a public-safe fixture with user opt-in and runtime-idle evidence. If that proof
cannot be captured without reading private session material or racing the TUI,
keep this blocker and continue improving the one-message TUI bootstrap path.
