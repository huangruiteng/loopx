# Codex CLI Visible Proof Capture Protocol

Status: public-safe protocol for opt-in proof capture.
Primary path: one-message Codex CLI TUI bootstrap.

This protocol turns a promising Codex CLI `resume` / `remote-control` surface
into evidence, not authority. LoopX may only promote later visible
automation after a public-safe proof shows the turn is visible, interruptible,
freshly idle-guarded, and independent of transcripts, session files, stdout,
stderr, credentials, or hidden session mutation.

## When To Use It

Use this protocol only when all of these are true:

- the user has already started from a normal Codex CLI TUI flow or explicitly
  opted into a proof run;
- `quota should-run` allows this LoopX turn;
- the test prompt is public-safe and does not depend on private repo state;
- the candidate surface is one of `visible_resume_prompt`,
  `remote_control_visible_prompt`, or `same_tui_visible_attach`;
- the goal is to prove visibility, not to deliver production work.

If any condition is missing, keep the one-message TUI bootstrap as the product
path and record a blocker instead of attempting a later visible turn.

## Capture Packet

The durable packet is two public-safe fixtures plus the acceptance result.
The public demo bundle in
[Codex CLI Proof-Capture Demo](codex-cli-proof-capture-demo.md) provides sample
fixtures for both a visible `resume` spike and a future same-TUI attach proof.

### Visible-Session Proof Fixture

```json
{
  "observed_surface": "visible_resume_prompt",
  "user_opt_in": true,
  "quota_guard": { "passed": true },
  "idle_guard": {
    "no_active_human_typing": true,
    "no_running_turn": true,
    "checked_before_prompt": true
  },
  "turn_visibility": {
    "visible_to_user": true,
    "prompt_public_safe": true
  },
  "interruptibility": {
    "user_can_interrupt": true,
    "manual_takeover_available": true
  },
  "boundary": {
    "reads_raw_transcripts": false,
    "reads_session_files": false,
    "reads_credentials": false,
    "mutates_hidden_session_state": false,
    "spends_quota_before_writeback": false
  },
  "writeback": { "compact_evidence_planned": true }
}
```

### Runtime-Idle Fixture

```json
{
  "observed_surface": "visible_resume_prompt",
  "idle_guard": {
    "no_active_human_typing": true,
    "no_running_turn": true,
    "checked_before_prompt": true
  },
  "turn_visibility": { "visible_to_user": true },
  "interruptibility": {
    "user_can_interrupt": true,
    "manual_takeover_available": true
  },
  "boundary": {
    "reads_raw_transcripts": false,
    "reads_session_files": false,
    "reads_stdout_stderr": false,
    "reads_credentials": false,
    "mutates_hidden_session_state": false
  }
}
```

Fixtures may include compact public labels such as `operator_initials`,
`proof_started_at`, `proof_result`, or `blocker`, but they must not include
screenshots, raw prompts from private work, raw model output, local session ids,
absolute local paths, credentials, internal document links, or command output
bodies.

## Procedure

1. Pick a public-safe fixture repo or demo goal.
2. Run `quota should-run` with the registered `agent_id`; stop if the user
   channel requires action.
3. Confirm explicit user opt-in for the proof. The user must know the proof is
   testing visibility, not doing production work.
4. Capture or generate fresh runtime-idle evidence immediately before the
   candidate prompt. Unknown turn state, recent typing, or a running turn fails
   closed.
5. Attempt only a visible proof prompt with an allowed command prefix. The
   prompt should say that LoopX is testing visible steering and should
   be safe to interrupt.
6. Record only the compact fixture booleans and public-safe labels above.
7. Validate the fixtures:

```bash
loopx codex-cli-visible-session-proof \
  --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --proof-fixture visible-proof.public.json

loopx codex-cli-runtime-idle-detector \
  --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --idle-fixture runtime-idle.public.json

loopx codex-cli-visible-attach-acceptance \
  --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --proof-fixture visible-proof.public.json \
  --idle-fixture runtime-idle.public.json
```

8. Write back the acceptance result. Spend quota only after the blocker or
   evidence is written back and validation has passed.

## Promotion Rules

`visible_resume_prompt` and `remote_control_visible_prompt` can prove a useful
visible spike, but they do not prove same-open-TUI automation. They remain
experimental until a later proof captures `same_tui_visible_attach`.

Only `same_tui_visible_attach` plus a passing runtime-idle detector may promote
the route toward a same-TUI automation driver. Even then, the next step is a
separate wiring task behind fresh quota guard, fresh idle guard, explicit
command boundary, and compact writeback.

## Stop Conditions

Stop and record a blocker when any of these happen:

- no explicit proof opt-in;
- `interaction_contract.user_channel.action_required=true`;
- runtime-idle state is unknown, recently active, or already running;
- the candidate needs transcript, session-file, stdout/stderr, credential, or
  hidden runtime reads;
- the route writes hidden Codex session state;
- the prompt is not visible, not interruptible, or not manually recoverable;
- the command prefix is not explicitly allowed;
- the proof would expose private repo names, task ids, internal links, local
  paths, screenshots, or raw session material.

The safe fallback is always to keep the one-message TUI bootstrap visible and
write the precise blocker into LoopX.
