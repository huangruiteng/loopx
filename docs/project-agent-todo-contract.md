# Project Agent Todo Contract

Project agents should keep operator-facing work out of long chat replies,
review documents, and overloaded `Next Action` paragraphs. Goal Harness uses
separate fields so the dashboard and quota guard can show the right work to the
right actor.

## Field Roles

- `Next Action` is one routing sentence for the next bounded step. It is not a
  reading queue, blocker dump, or checklist.
- `User Todo / Owner Review Reading Queue` is the human-facing checklist. Use
  it for concrete user, owner, or controller input that the agent cannot
  complete by itself.
- `Agent Todo` is the project-agent checklist. Use it for safe follow-up work
  the agent can do after health, operator gates, evidence, and quota allow
  execution.
- Production blockers, missing write approvals, and safety risks are gates or
  stop conditions. Do not count them as user todos unless a specific human
  action can clear them.

## Write Contract

When read-only analysis, a review packet, a gate checklist, or P0/P1 steering
finds a concrete user or owner action, write it immediately with the todo CLI:

```bash
goal-harness todo add \
  --goal-id <goal-id> \
  --role user \
  --text "<public-safe user or owner action>"
```

Use `--role agent` for project-agent follow-up work:

```bash
goal-harness todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe agent action>"
```

Executable agent work should register its lane instead of relying on text
classification. Use `advancement_task` for a bounded implementation,
validation, benchmark, blocker-writeback, or repair segment:

```bash
goal-harness todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe executable agent action>" \
  --task-class advancement_task \
  --action-kind run_eval
```

Use `continuous_monitor` only for watch-only surfaces where an unchanged poll
must stay quiet:

```bash
goal-harness todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe monitor action>" \
  --task-class continuous_monitor \
  --action-kind monitor
```

`--action-kind` is a public-safe token. Known generic tokens such as
`run_eval`, `validate`, `rebuild`, `writeback`, `monitor`, and `poll` help the
CLI project the lane consistently, but explicit `--task-class` is the authority
when both are present. If an exact todo already exists, `todo add` updates or
inserts the metadata comment instead of creating a duplicate checkbox.
`--task-class user_gate` and `--task-class blocker` are non-executable control
lanes for owner input and concrete blockers; quota/executor code must not treat
them as advancement work.

Terminology: a `goal_id` is the Goal Harness control-plane boundary: registry
entry, active-state file, quota lane, status projection, and run-history stream.
A `todo_id` is a structured work item inside that goal. Goal Harness does not
currently model issues as a separate runtime object.

Multiple agents may share the same project control plane. A todo can carry a
soft owner with `claimed_by`, but the todo itself should not carry the agent's
scope. Scope belongs in the automation prompt or sub-agent handoff; the agent
uses that scope to decide which open todo it may claim. Each goal should have
one `coordination.primary_agent`: the primary agent owns final review,
verification, merge, publication, high-risk side-agent review, and reassignment
decisions. All other registered agents are side agents. Side agents should do
repository edits only in an independent git worktree/branch, never in the
primary checkout. Small AGENTS-eligible validated changes may be self-merged
when the side agent records public-safe evidence; higher-risk or unclear work
should be handed back through a primary-agent review todo. First register the
agent ids and primary agent in the goal registry:

```bash
goal-harness configure-goal \
  --goal-id <goal-id> \
  --registered-agent codex-main-control \
  --registered-agent codex-side-bypass \
  --primary-agent codex-main-control \
  --execute
```

Then claim through the dedicated command. `--claimed-by` is required for
`todo claim` and must match one of the registered agent ids:

```bash
goal-harness todo claim \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-main-control
```

Old projects that do not yet have `coordination.registered_agents` are
intentionally blocked when an agent tries to claim work. The CLI error includes
the `configure-goal --registered-agent <agent-id> --execute` command so the
agent or controller can register its identity before writing ownership metadata.

Use `--clear-claim` when the controller reassigns a todo or an agent releases
work. `claimed_by` is visibility, not a runtime lease: it does not bypass quota,
user gates, write-scope checks, or validation. `todo add/update/complete` also
accept `--claimed-by`, but the value is checked against the same registered
agent list. Claimed completion also requires `coordination.primary_agent`, so
old projects fail closed before side-agent handoff semantics become ambiguous.
`todo claim` is non-destructive: if another registered agent already owns the
todo, it fails closed instead of silently replacing `claimed_by`. Transfer
ownership with an explicit `todo update --clear-claim` or
`todo update --claimed-by <agent-id>` decision. The CLI writes claim changes and
completion handoffs under the same active-state file lock as todo
add/update/complete, so concurrent CLI writers re-read the latest state before
editing instead of overwriting a stale snapshot.

The command resolves the active state from the project registry, creates the
canonical section when needed, updates `updated_at`, and avoids duplicate exact
todo text. If a dashboard or controller needs the new checklist immediately,
refresh the status projection after the write:

```bash
goal-harness refresh-state --goal-id <goal-id>
```

## Lifecycle Contract

Agents should not patch active-state checkboxes directly to move work forward.
Use the lifecycle commands so Goal Harness can preserve `todo_id`, status,
classification metadata, timestamps, and idempotency in one write.

Todo lifecycle should stay simple. Do not add a separate feature state machine
such as `slice_done`, `rolled_out`, or `proven_in_product_path` unless the
product has a concrete UI/runtime need for it. For ordinary project work, use
**todo succession** instead: complete the implementation slice, then create the
next concrete todo for rollout, product-path audit, benchmark proof, docs,
telemetry, or operator decision.

A non-trivial feature todo is done only as a slice. Before or during completion,
the agent should do one of two things:

- create the next public-safe agent or user todo with `--next-agent-todo`,
  `--next-user-todo`, or a follow-up `todo add`;
- record a compact no-follow-up rationale in the completion note, explaining why
  the feature is truly finished and does not need rollout, audit, docs, or
  product-path proof.

This keeps the active checklist honest without making Goal Harness a heavyweight
project-management state machine.

Complete the current todo and atomically register the next executable todo:

```bash
goal-harness todo complete \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --evidence "<public-safe artifact or result>" \
  --next-agent-todo "<public-safe next executable action>" \
  --next-task-class advancement_task \
  --next-action-kind run_eval
```

If an agent takes ownership at completion time, include the claim in the same
locked lifecycle write:

```bash
goal-harness todo complete \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-side-bypass \
  --evidence "<public-safe artifact or result>" \
  --next-agent-todo "Primary agent review, verify, and merge this side-agent work." \
  --next-claimed-by codex-main-control
```

If `--claimed-by` names a side agent, broad side-agent completion defaults to
requiring a successor primary review todo and defaults that successor todo's
`claimed_by` to the goal's `primary_agent`. Passing `--next-claimed-by` is
allowed only when it matches the primary agent. This keeps broad side-agent
handoff visible to the shared control plane.

For small changes that satisfy the repository's self-merge rules, the side
agent may self-merge and complete without a successor review todo by making the
exception explicit:

```bash
goal-harness todo complete \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-side-bypass \
  --side-agent-self-merged \
  --evidence "<public-safe commit, validation, and self-merge summary>"
```

`--side-agent-self-merged` requires `--evidence`. Do not use it for runtime,
benchmark, permission, production, destructive git, publication, public
evidence-policy, or broad coordination changes that need primary review.
When a self-merged side-agent slice has an obvious same-scope continuation, it
may also atomically add that successor todo and claim it back to the same side
agent:

```bash
goal-harness todo complete \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-side-bypass \
  --side-agent-self-merged \
  --evidence "<public-safe commit, validation, and self-merge summary>" \
  --next-agent-todo "Continue the next small docs/productization slice." \
  --next-claimed-by codex-side-bypass
```

Without `--side-agent-self-merged`, a side-agent successor remains a primary
review handoff and must stay claimed by the primary agent.

Use `todo update` for lower-level status changes:

```bash
goal-harness todo update \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --status blocked \
  --reason "<public-safe blocker>" \
  --task-class blocker
```

Use `todo supersede` when the current open todo should be retired and replaced:

```bash
goal-harness todo supersede \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --reason "<public-safe reason>" \
  --next-agent-todo "<replacement executable action>"
```

`todo complete` and `todo supersede` are intentionally idempotent for repeated
heartbeats: if the old todo is already complete and the next todo already
exists with the same metadata, the command returns `changed=false` and does not
duplicate the next checkbox. `todo archive-completed` is only a hygiene command:
it moves already-completed active todos into `Completed Work Archive`; it does
not mark open todos as done.

## Parsed Schema

Projects may keep writing ordinary Markdown checkboxes, but readers should use
the structured projection emitted by status/quota when available. Todo summaries
carry `schema_version=todo_summary_v0`; individual items carry
`schema_version=todo_item_v0`, `todo_id`, `role`, `status`, `priority`,
`title`, `archive_state`, `source_section`, `index`, `text`, `task_class`, and
optional `action_kind`, `claimed_by`, and `required_capabilities`. The `todo_id`
is first-class when written by the CLI. `claimed_by` values are normalized
public-safe agent ids and should correspond to
`coordination.registered_agents`. Legacy Markdown without metadata still gets a
parser-derived compatibility id from local section/index/text, and the first
lifecycle command will materialize that id back into metadata. Future lease
timestamps, dependency, capability detail, and evidence-link fields should
extend this item shape instead of adding another todo format.
In Markdown, lane metadata is stored as an indented HTML comment directly under
the checkbox, for example:

```markdown
- [ ] Run one validated benchmark case and write back result or blocker.
  <!-- goal-harness:todo todo_id=todo_8e280be49441 status=open task_class=advancement_task action_kind=run_eval required_capabilities=shell%2Cbenchmark_runner claimed_by=codex-main-control -->
```

Plain checkbox text remains a compatibility fallback. New automation-facing
work should prefer the CLI metadata path so quota and dashboard consumers do
not need project-specific word lists.

Executable agent todos may declare per-todo environment needs with
`--required-capability`. Keep this field near the todo, not in a global agent
profile: the same agent may have shell/filesystem capability for docs work, but
lack `benchmark_runner`, `external_evidence_poll`, `network`, or another bridge
for a specific step.

```bash
goal-harness todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe executable agent action>" \
  --task-class advancement_task \
  --action-kind run_eval \
  --required-capability shell \
  --required-capability benchmark_runner
```

`status` projects `required_capabilities` on every visible todo. `quota
should-run` then derives a read-only `capability_gate` from the visible
executable queue, not from a single preselected todo. With multiple P0 or P1
items, it scans the projected queue in order: if the first P0 is capability
blocked but the second P0 can run, the second P0 is selected; only when the
visible P0 candidates are blocked does it fall through to the first runnable
P1/P2 candidate. Blocked higher-priority candidates remain visible in
`capability_gate.blocked_candidates`. If no visible executable candidate can
run, the gate returns `repair_bridge`, `ask_owner`, or `skip` according to the
missing capability class.

## Execution Order

1. Run the quota guard against the shared global registry before spending
   automatic delivery compute.
2. If the guard or review packet exposes open user todos, surface them to the
   user instead of reporting "no new user action".
3. If the guard sets `notify_user_on_open_todo=true`, treat the open todos as a
   blocker-push notification: ask at most three items, skip delivery work, and
   skip quota spend unless the same blocker was already surfaced recently.
4. Do not execute `agent_command`, adapter work, write-control, or production
   actions while the relevant gate is still unresolved.
5. After the user todo is completed or explicitly deferred, the project agent
   may continue only through the safe path allowed by the current guard or
   review packet.

## Public Smokes

Two dependency-free public fixtures cover this contract:

```bash
python3 examples/todo-cli-smoke.py
python3 examples/todo-lifecycle-cli-smoke.py
python3 examples/project-agent-adoption-smoke.py
python3 examples/todo-concurrent-write-lock-smoke.py
python3 examples/capability-gate-smoke.py
```

The first verifies the todo CLI writes canonical active-state sections. The
second verifies lifecycle transitions by `todo_id`, including claimed
completion, supersede, idempotent next-todo insertion, and non-executable
blocker lanes.
The third verifies an executor-facing path from quota guard hint, to user todo
write, to status projection, to approved project-agent handoff.
The fourth verifies concurrent todo writers wait on the active-state lock and
preserve both claim metadata and unrelated updates.
The fifth verifies per-todo `required_capabilities`, including multiple P0/P1
candidate selection, bridge repair, and owner-gated capability misses.
