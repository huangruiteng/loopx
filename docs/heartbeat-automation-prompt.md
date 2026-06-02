# Heartbeat Automation Prompt

This is the public copy-paste template for a Codex App heartbeat automation that
advances one Goal Harness goal without hiding compute policy inside the timer.

The timer only wakes the executor. Goal Harness decides whether that wakeup
should spend delivery compute.

You can generate the task body from the CLI:

```bash
goal-harness heartbeat-prompt \
  --goal-id <GOAL_ID> \
  --active-state <ACTIVE_GOAL_STATE_PATH>
```

## Template

Replace the placeholders before installing the automation:

- `<ACTIVE_GOAL_STATE_PATH>`: the local active state file that carries the goal
  priority stack, recent progress, critic, and next action.
- `<GOAL_ID>`: the stable Goal Harness goal id.
- `<MATERIAL_QUEUE_RULE>`: optional project-specific rule such as "do not
  consume the learning material queue unless the user explicitly asks."

```text
Advance the goal described in <ACTIVE_GOAL_STATE_PATH>.

Before spending delivery compute, run:

goal-harness --format json quota should-run --goal-id <GOAL_ID>

If the result says should_run=false, do not do implementation work, adapter
work, file edits, research, or project exploration in this turn. Return a quiet
heartbeat DONT_NOTIFY response with the skip reason.

If the result says should_run=true:

1. Read the active state and Priority Stack.
2. Choose exactly one bounded, verifiable step.
3. Do that step only. Keep public/private boundaries intact.
4. Run the smallest useful validation.
5. Write back changed files, validation, critic, and next action to the active
   state.
6. If the dashboard or controller needs to see a state-only update, run:

   goal-harness refresh-state --goal-id <GOAL_ID>

7. After validation and required state refresh are complete, append exactly one
   spend event:

   goal-harness quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute

   Do not append spend for should_run=false skips, preflight failures, pure
   dry-run previews, or duplicate accounting attempts.

8. Return a compact final report. Use heartbeat NOTIFY only for meaningful user
   visibility, such as a committed artifact, a user gate, or a real blocker.
   Otherwise use DONT_NOTIFY.

<MATERIAL_QUEUE_RULE>
Do not ask for permissions when the current Codex session is already trusted.
```

## Minimal User-Facing Form

When creating a heartbeat in Codex App, keep the visible instruction short and
put the lifecycle in the automation task body:

```text
Create a heartbeat automation every <INTERVAL> for the current thread.

Task:
Advance <GOAL_ID> using <ACTIVE_GOAL_STATE_PATH>. Before any delivery work, run
`goal-harness --format json quota should-run --goal-id <GOAL_ID>`. If it returns
`should_run=false`, skip quietly with DONT_NOTIFY. If it returns
`should_run=true`, do one bounded verifiable step, validate it, write back
changed files / validation / critic / next action, refresh state if needed, and
append exactly one `goal-harness quota spend-slot --goal-id <GOAL_ID> --slots 1
--source heartbeat --execute` event after the completed turn.
```

## Agent Checklist

For every automatic heartbeat turn, the agent-facing checklist is:

1. Guard first: `quota should-run`.
2. Skip without compute when `should_run=false`.
3. Work small when `should_run=true`.
4. Validate before reporting.
5. Refresh state when the run is state-only.
6. Spend exactly once after the completed turn.
7. Report compactly.

This prompt is intentionally a template rather than a scheduler. It should work
with per-project heartbeats, a shared controller loop, or future Codex goal-mode
automations because they all share the same Goal Harness quota guard.
