# Codex CLI TUI-First Goal Harness Loop

Status: product contract and implementation target.

Goal Harness should make Codex CLI easy to adopt without taking away the
interactive TUI that users already trust. The target is not "run a hidden
daemon instead of Codex." The target is:

1. A user opens Codex CLI TUI inside a project repo.
2. The user sends one short message.
3. Codex discovers or installs Goal Harness without requiring a manual repo
   clone, connects the repo, reads quota and todo state, and enters the Goal
   Harness loop.
4. Later automation can steer the same visible session when safe, while the
   user can still watch, interrupt, review, or take over.

## Product Goal

The best first-run experience is one TUI message:

```text
Start Goal Harness for this repo. If `goal-harness` is missing, install it with
the official no-clone GitHub installer, then connect this project. Show me the
current goal, concrete user gate if any, top todos, and next safe action before
running longer work. Keep me in this Codex CLI TUI unless I explicitly accept a
headless fallback.
```

That message should be enough for a terminal agent to:

- run `goal-harness doctor`;
- install or repair the local CLI if it is missing, using the no-clone archive
  installer before asking the user to clone the Goal Harness repo;
- connect or bootstrap the repo;
- read onboarding candidates and ask the user what to accept when required;
- run `quota should-run`;
- claim an in-scope todo with its registered agent id;
- execute one bounded, validated segment;
- write back status and spend quota only after evidence exists.

The user should not need to understand registry paths, runtime roots, active
state files, quota JSON, or heartbeat prompts before seeing value.

## Runtime Split

| Layer | Owns | Must Not Do |
| --- | --- | --- |
| Codex CLI TUI | visible user interaction, local tool execution, steering, review, manual takeover | hide user decisions inside Goal Harness state |
| Goal Harness | goal state, user gates, agent todos, claims, quota, writeback, compact evidence | replace the Codex CLI runtime or store raw transcripts |
| Local driver or scheduler | wakeups, idle checks, session attachment attempts, fallback launch | inject into an active user turn or bypass a gate |

Goal Harness should be the control plane. Codex CLI should remain the executor
and the user's live console.

## Operating Modes

### 1. TUI Bootstrap

This is the first supported path. The user starts in Codex CLI TUI and pastes a
single Goal Harness bootstrap request. The agent performs install/connect,
surfaces onboarding decisions, and starts a bounded Goal Harness turn in the
same conversation.

This mode preserves the TUI completely because the human explicitly starts the
loop there.

Current prototype:

```bash
goal-harness codex-cli-bootstrap-message --project . --goal-id <goal-id>
```

Copy the generated message into Codex CLI TUI. The message tells the agent to
repair/install Goal Harness if needed, connect the repo conservatively, run the
quota/status guard, obey `interaction_contract`, preserve the visible TUI, and
spend quota only after validated writeback.

The first useful TUI response should be a control-plane snapshot, not a lecture
about internals:

- current goal id;
- concrete user gate, or "none";
- top user todo, or "none";
- top agent todo;
- next safe action.

Registry paths, runtime roots, JSON payloads, local-driver plans,
clone/canary setup, and visible-session proof fixtures are follow-up
diagnostics. They should not be required before a first-time user sees the
current goal/gate/todo state.

### 2. Session-Attached Automation

This is the preferred automation target. A scheduler wakes up, runs
`quota should-run`, then attempts to add a visible Goal Harness steering turn to
the same Codex CLI session.

A valid attachment needs:

- a stable session identifier or resume handle;
- an idle guard so automation does not race a human-typed message;
- a visible injected prompt that says why Goal Harness is steering now;
- a hard stop when `interaction_contract.user_channel.action_required=true`;
- writeback and spend only after the session produces validated evidence.

If Codex CLI cannot expose a safe session attachment primitive, Goal Harness
should not fake it by writing hidden state. It should fall back to a transparent
mode.

Current probe:

```bash
goal-harness codex-cli-session-probe
```

The probe is help-only by default: it checks public Codex CLI command surfaces
such as `codex --help`, `codex exec --help`, and `codex resume --help`. It does
not read raw transcripts, credentials, local session files, or mutate a Codex
session. The key distinction is deliberate: `exec` or `resume` support can be a
useful fallback, but it is not evidence that Goal Harness can inject a visible
turn into the same open TUI. Same-session automation requires an explicit
visible attach/inject primitive plus an idle guard. A visible `resume [PROMPT]`
or experimental `remote-control` surface is stronger than plain headless
fallback, but it still belongs in a separate spike until Goal Harness proves the
turn is visible, idle-guarded, interruptible, and not racing a human-typed TUI
message.

Current driver-plan prototype:

```bash
goal-harness codex-cli-visible-driver-plan --project . --goal-id <goal-id>
```

This command turns the probe result into a dry-run driver plan. It does not run
Codex, read raw transcripts, read session files, mutate a Codex session, or
spend Goal Harness quota. Its job is to choose one of four next modes:

- `session_attached_visible_turn`: a future local driver may try the detected
  visible attach primitive, but only behind quota guard and idle guard.
- `visible_resume_or_remote_control_spike`: `resume [PROMPT]` or
  `remote-control` exists, but it must prove that the turn is visible and
  interruptible before Goal Harness treats it as session-attached automation.
- `explicit_headless_fallback_after_tui_bootstrap`: keep the one-message TUI
  bootstrap as the main path and use `codex exec` only when the user knowingly
  accepts a headless fallback.
- `tui_bootstrap_only`: ask the user to start inside Codex CLI TUI.

Current local-driver planner:

```bash
goal-harness codex-cli-local-driver-plan --project . --goal-id <goal-id> --agent-id <agent-id>
```

This command is the conservative MVP for automation setup. It composes the
quota guard, visible-driver plan, TUI bootstrap command, explicit headless
fallback command, and idle-guard requirement into a single dry-run packet. It
does not run Codex, read transcripts, read session files, mutate a session, or
spend quota.

Current visible-session proof harness:

```bash
goal-harness codex-cli-visible-session-proof \
  --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --proof-fixture visible-proof.public.json
```

The proof fixture must be public-safe. It records booleans for user opt-in,
quota guard, idle guard, turn visibility, interruptibility, private-data
boundaries, and compact writeback planning. Passing this proof only means a
future local driver may try that visible surface behind the same guards; it
does not mean Goal Harness may read transcripts, read session files, mutate
hidden session state, or bypass user gates.

### 3. Headless Fallback

`codex exec` remains useful for scheduled or CI-like work, but it is not the
primary product experience for interactive users. A headless driver is allowed
when:

- the user knowingly opted into background execution;
- the goal boundary permits it;
- the work is independent of an active TUI decision;
- the driver writes compact evidence back into Goal Harness.

Headless fallback should never be the only way to start Goal Harness.

Current explicit fallback generator:

```bash
goal-harness codex-cli-exec-handoff --project . --goal-id <goal-id>
```

This command prints a `codex exec` handoff script that embeds the same
Goal-Harness-aware bootstrap message. It does not run Codex, read transcripts,
read credentials, read session files, mutate a session, or spend quota. Use it
only when the user knowingly chooses a headless fallback or when a future
driver decides that same-session attachment is unavailable and the goal
boundary permits background execution.

## Session-Attached Turn Algorithm

```text
1. Resolve repo, goal_id, registered agent_id, and current Codex session.
2. Run `goal-harness quota should-run --goal-id <goal> --agent-id <agent>`.
3. If user action is required, inject or display only the concrete user gate.
4. If workspace_guard blocks delivery, move the side agent to an independent
   worktree before editing.
5. Choose among current-agent claimed advancement todos and runnable unclaimed
   candidates; monitor todos are context unless they produce a material event.
6. Inject a visible steering prompt into the idle TUI session, or fall back to
   an explicit headless run when the user has allowed it.
7. After validation, run `refresh-state` and `quota spend-slot --execute`.
8. If validation fails, write a compact blocker instead of spending success
   prose.
```

The actual todo choice remains the agent's steering decision. Goal Harness
projects runnable candidates; it should not over-specify the model's local plan.

## Safety Rules

- Do not store raw Codex transcripts, credentials, private local paths, raw
  logs, or production artifacts in Goal Harness state.
- Do not inject automation into a session while the user is actively typing or
  while a previous turn is still running.
- Do not answer a user gate on the user's behalf.
- Do not let a side agent edit from the primary checkout; obey
  `workspace_guard`.
- Prefer a visible TUI prompt over silent background mutation.
- Treat session-attachment failure as an explicit fallback decision, not as a
  reason to lose the Goal Harness loop.

## Implementation Roadmap

1. **Bootstrap prompt**: ship a concise Codex CLI TUI paste message in README
   and getting-started docs.
2. **No-clone install repair**: make the first-run agent path able to install
   the CLI and reusable skills from a GitHub archive, while reserving
   clone-plus-canary setup for contributors.
3. **Bootstrap command**: add a Goal Harness command that prints a tailored
   Codex CLI bootstrap message for the current repo.
4. **Session probe**: document whether current Codex CLI exposes a stable
   session id, resume handle, or safe injection primitive. The current
   implementation is `goal-harness codex-cli-session-probe`; it separates
   `exec` fallback support, visible resume / remote-control spike surfaces, and
   true same-open-TUI visible injection.
5. **Visible driver plan**: generate a dry-run plan with
   `goal-harness codex-cli-visible-driver-plan` so the next local driver knows
   whether to attempt visible attach, run a resume/remote-control proof, or
   fall back explicitly.
6. **Local driver planner**: ship
   `goal-harness codex-cli-local-driver-plan` as the dry-run command that
   composes quota, visible-driver, TUI bootstrap, explicit fallback, and
   idle-guard requirements.
7. **Visible-session proof harness**: validate public-safe observations with
   `goal-harness codex-cli-visible-session-proof` before promoting
   resume/remote-control into any same-session automation path.
8. **Visible driver run packet**: add
   `goal-harness codex-cli-visible-driver-run` as the no-execution packet that
   decides whether the next turn needs visible proof, TUI bootstrap, explicit
   headless opt-in, or a proven visible-session candidate.
9. **Local scheduler tick**: add
   `goal-harness codex-cli-local-scheduler-tick` as the first executor-facing
   one-shot packet. It emits either an external command candidate or a precise
   blocker writeback command, but does not run Codex, read session files, or
   write Goal Harness state itself.
10. **Local driver executor**: prototype a scheduler that runs quota, checks
   session idle state, and either attaches visibly or falls back explicitly.
11. **Validation harness**: add a public-safe fixture that proves the driver
   never stores raw transcript text and never spends quota before writeback.
12. **Claude Code follow-up**: port the same product contract only after the
   Codex CLI path is credible.

## Success Criteria

- A first-time user can start in Codex CLI TUI with one message and see a
  current goal, user gate, agent todo, and next safe action without reading
  Goal Harness docs first.
- A returning user can keep the TUI open while Goal Harness automation performs
  bounded turns that are visible, interruptible, and reviewable.
- When session attachment is unavailable, the fallback is explicit and safe
  rather than pretending the same TUI session was preserved.
- Goal Harness state remains compact, public/private-safe, and independent of
  raw Codex CLI transcript storage.
