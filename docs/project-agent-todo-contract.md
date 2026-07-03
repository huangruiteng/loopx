# Project Agent Todo Contract

Project agents should keep operator-facing work out of long chat replies,
review documents, and overloaded `Next Action` paragraphs. LoopX uses
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

External boards and management surfaces, including Lark Kanban, are projections
of this contract. They may show critical status, claims, gates, evidence, and
worker handoff fields, but they should not become the place where agents invent
new task identity. A long-running Codex session can claim visible board work and
continue it; when it needs to fan out, split, supersede, or create successor
work, it writes the new task through the LoopX todo lifecycle and lets the board
sync catch up.

## Write Contract

When read-only analysis, a review packet, a gate checklist, or P0/P1 steering
finds a concrete user or owner action, write it immediately with the todo CLI:

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role user \
  --text "<public-safe user or owner action>"
```

Use `--role agent` for project-agent follow-up work:

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe agent action>"
```

Executable agent work should register its lane instead of relying on text
classification. Use `advancement_task` for a bounded implementation,
validation, benchmark, blocker-writeback, or repair segment:

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe executable agent action>" \
  --task-class advancement_task \
  --action-kind run_eval
```

Use `continuous_monitor` only for watch-only surfaces where an unchanged poll
must stay quiet:

```bash
loopx todo add \
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

For scheduled monitors, keep the contract minimal: `--next-due-at` is the first
eligible time, `--cadence` is the retry interval, `--monitor-target-key` is the
stable idempotency key, and optional `--expires-at` is the hard stop after
which the monitor must not catch up.

Terminology: a `goal_id` is the LoopX control-plane boundary: registry
entry, active-state file, quota lane, status projection, and run-history stream.
A `todo_id` is a structured work item inside that goal. LoopX does not
currently model issues as a separate runtime object.

Multiple agents may share the same project control plane. A todo can carry a
soft owner with `claimed_by`, but ordinary agent todos should not restate the
agent's broad prompt scope. Scope belongs in the automation prompt or sub-agent
handoff; the agent uses that scope to decide which open todo it may claim.
User-gate todos are different: when a user decision only unlocks one registered
agent or lane, record the blocked agent explicitly with `blocks_agent` so quota
does not stop unrelated agents. For convenience, `todo add/update --role user
--task-class user_gate --agent-id <agent>` defaults `blocks_agent` to that agent
when `--blocks-agent` is omitted. In multi-agent goals, open `user_gate` todos
must have exactly one explicit scope: either `blocks_agent=<registered-agent>`
for a lane-scoped decision or `global_gate=true` / `--global-gate` for a
genuine goal-wide owner gate. Unscoped multi-agent user gates are an authoring
error because every registered agent would otherwise see another lane's
question as its own stop condition.

When a user gate only blocks one concrete action, add the blocked todo id with
`unblocks_todo_id=<todo_id>`. When multiple todos share the same broad
`action_kind`, use the schema-backed decision-scope fields instead of relying
on title/body token overlap:

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role user \
  --task-class user_gate \
  --agent-id codex-main-control \
  --decision-scope direction:action:benchmark_target_choice \
  --text "Choose the benchmark target before running that case."

loopx todo update \
  --goal-id <goal-id> \
  --todo-id <agent-todo-id> \
  --required-decision-scope direction:action:benchmark_target_choice
```

Quota treats a gate as covering an agent todo when `decision_scope` matches or
dominates one of that todo's `required_decision_scopes`; otherwise the todo is
independent and can be selected as a safe fallback when the boundary permits it.

Each goal should have one `coordination.primary_agent`: the primary agent owns
final review, verification, merge, publication, and reassignment decisions. All
other registered agents are side agents. Side agents should do repository edits
only in an independent git worktree/branch, never in the primary checkout. Small
AGENTS-eligible validated changes may be self-merged when the side agent records
public-safe evidence; higher-risk or unclear work should create a successor
handoff todo claimed by the primary agent by default. A project may route all
side-agent handoffs through `coordination.side_agent_handoff_agent`, or route a
specific side-agent through
`coordination.agent_profiles.<agent_id>.review_policy.handoff_agent`. First
register the agent ids and primary agent in the goal registry:

`quota should-run --agent-id <side-agent-id>` enforces this as a preflight: when
the side agent is running from the registered primary checkout, a non-git
directory, or an unrelated git worktree, it returns `workspace_guard` and blocks
normal delivery until the agent moves to an independent worktree and reruns the
guard.

Contributor-facing example:

```bash
loopx --format json quota should-run \
  --goal-id <goal-id> \
  --agent-id codex-side-bypass
```

If the response includes
`effective_action=side_agent_workspace_repair` and
`workspace_guard.current_workspace=primary_checkout`, the side agent should not
edit files yet. Create or switch to a separate worktree and rerun the same
guard:

```bash
git worktree add /tmp/<goal-id>-side-agent -b codex/<side-agent-branch>
cd /tmp/<goal-id>-side-agent
loopx --format json quota should-run \
  --goal-id <goal-id> \
  --agent-id codex-side-bypass
```

Only after that rerun returns normal delivery should the side agent claim an
in-scope todo and edit repository files. A primary-owned todo remains
primary-owned even when the side-agent workspace guard passes; the side agent
must pick a todo inside its scope or create a successor handoff todo.
For agent-specific `quota should-run --agent-id <side-agent-id>` payloads, the
todo summary is claim-aware: current-agent claimed todos are preferred, unclaimed
todos remain selectable, and primary/other-agent claimed todos are projected as
blocked-claim context rather than as the side agent's next action. This reduces
accidental collisions without writing scope into todo metadata or turning
`claimed_by` into a lease. When a runnable current-agent or unclaimed
advancement todo exists, quota may also expose
`agent_lane_next_action.schema_version=agent_lane_next_action_v0`. That field is
the side agent's current slice for this turn; it does not overwrite the
goal-level `Next Action` owned by the primary/global route. `loopx status
--agent-id <side-agent-id>` may attach the same derived field to matching status
queue items for observation, while leaving the project-level route unchanged.
When a candidate has `target_capabilities` and missing target bridge
capabilities, quota may mark it `capability_repair_mode=true`; scoped
next-action selection should prefer that repair-mode candidate over ordinary
runnable work in the same claim/priority bucket so capability-building todos do
not require fragile active-state reordering.

Deferred todos may carry a machine-readable resume condition with
`resume_when=<token>`. Supported conditions are:

- `resume_when=todo_done:<todo_id>`: the deferred todo becomes a successor
  replan candidate after the referenced todo reaches `status=done`.
- `resume_when=pr_merged:#532` or
  `resume_when=pr_merged:owner/repo#532`: the deferred todo becomes a successor
  candidate after a structured rollout event records that PR merge.

Open todos may also carry `resume_when` when they are visible but not yet
executable. Until the parsed `resume_condition.satisfied` value is true, status
and quota keep the todo out of `first_executable_items`,
`executable_backlog_items`, `capability_gate.runnable_candidates`, and
`agent_lane_next_action`. When `resume_ready=true`, the open todo may enter the
normal executable lane for its claimed agent.

Status and quota expose deferred todos as a visibility lane after sorted open
todo lanes. This is a deferred gate-resume lane: it is not runnable work, and
it is not evidence that the current agent has no todo, until an agent reopens,
supersedes, or records a no-follow-up rationale for the deferred item.

```bash
loopx register-agent \
  --goal-id <goal-id> \
  --agent-id codex-main-control \
  --agent-id codex-side-bypass \
  --primary-agent codex-main-control \
  --execute
```

Then claim through the dedicated command. `--claimed-by` is required for
`todo claim` and must match one of the registered agent ids:

```bash
loopx todo claim \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-main-control
```

Old projects that do not yet have `coordination.registered_agents` are
intentionally blocked when an agent tries to claim work. The CLI error includes
the `register-agent --agent-id <agent-id> --execute` command so the agent or
controller can register its identity before writing ownership metadata. Agent
registration writes the source registry named by the global projection; if the
shared global registry is not writable, it fails before changing that source so
the control plane does not drift into a half-registered state.

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
loopx refresh-state --goal-id <goal-id> --agent-id <registered-agent>
```

For multi-agent goals, `refresh-state` requires an explicit `--agent-id`.
The default scoped refresh is an agent-lane run: it is useful for keeping the
same turn's writeback/accounting identity intact, but it does not replace the
goal-level status route.

## Lifecycle Contract

Agents should not patch active-state checkboxes directly to move work forward.
Use the lifecycle commands so LoopX can preserve `todo_id`, status,
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
- record a compact no-follow-up rationale with `--no-follow-up` plus `--note`
  / `--reason` / `--evidence`, explaining why the feature is truly finished
  and does not need rollout, audit, docs, or product-path proof.

This keeps the active checklist honest without making LoopX a heavyweight
project-management state machine.

Complete the current todo and atomically register the next executable todo:

```bash
loopx todo complete \
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
loopx todo complete \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-side-bypass \
  --evidence "<public-safe artifact or result>" \
  --next-agent-todo "Review, verify, and merge this side-agent work."
```

If `--claimed-by` names a side agent, broad side-agent completion defaults to
requiring a successor handoff todo. By default that successor is claimed by the
goal's `primary_agent`. A goal may set
`coordination.side_agent_handoff_agent` to another registered agent for the
shared default route, and may override that default for a specific side agent
with `coordination.agent_profiles.<agent_id>.review_policy.handoff_agent`.
`--next-claimed-by` is allowed only when it matches the resolved handoff owner.
Existing registry fields named for review are not aliases for this route. This
keeps broad side-agent handoff visible to the shared control plane without
hard-coding a single follow-up surface for every side-agent lane.

LoopX does not model "review" as a separate kernel object. Review, verification,
or continuation are product-level names for a successor todo. The machine
contract is generic: the generated successor records
`blocks_agent=<side-agent-id>` and
`unblocks_todo_id=<completed-todo-id>`, while `claimed_by` names the agent that
should handle the dependency. Quota and dashboards can prioritize this handoff
without parsing prose or adding a review-specific action kind. Same-agent broad
handoff is rejected; if the completing side agent is allowed to deliver without
another agent, it must use the explicit `--side-agent-self-merged --evidence`
path.

For primary-agent completions and self-merged same-lane continuations, a
successor created with `--next-agent-todo` inherits the completed todo's
effective `claimed_by` unless `--next-claimed-by` explicitly names another
registered agent. This prevents follow-up work from accidentally falling into
the unclaimed pool.

For small changes that satisfy the repository's self-merge rules, the side
agent may self-merge and complete without a successor review todo by making the
exception explicit:

```bash
loopx todo complete \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-side-bypass \
  --side-agent-self-merged \
  --evidence "<public-safe commit, validation, and self-merge summary>"
```

`--side-agent-self-merged` requires `--evidence`. Do not use it for runtime,
benchmark, permission, production, destructive git, publication, public
evidence-policy, or broad coordination changes that need an independent
handoff.
After a validated self-merge, write back the real delivery outcome at the
project level when the slice advanced the public product or case path. An
agent-lane refresh with `--agent-id` is useful for side-lane notes, but it does
not replace the goal-level latest run used by quota and dashboard routing. Do
not append a follow-up goal-level `surface_only` sync after a validated
`outcome_progress` slice; either skip the duplicate sync or mirror the product
progress with:

```bash
loopx refresh-state \
  --goal-id <goal-id> \
  --classification <public-safe-progress-classification> \
  --delivery-batch-scale multi_surface \
  --delivery-outcome outcome_progress \
  --agent-id <primary-agent> \
  --progress-scope goal
```

This keeps validated side-agent product work from being misread as another
surface-only heartbeat turn.
When a self-merged side-agent slice has an obvious same-scope continuation, it
may also atomically add that successor todo and claim it back to the same side
agent:

```bash
loopx todo complete \
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
loopx todo update \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --status blocked \
  --reason "<public-safe blocker>" \
  --task-class blocker
```

Use `--resume-when` when deferring a successor that should wake up after a
machine-readable condition instead of living only in prose:

```bash
loopx todo update \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --status deferred \
  --resume-when todo_done:<blocking_todo_id> \
  --reason "<public-safe deferred rationale>"
```

Use `todo supersede` when the current open todo should be retired and replaced:

```bash
loopx todo supersede \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --reason "<public-safe reason>" \
  --next-agent-todo "<replacement executable action>"
```

If the superseded todo was claimed, the replacement inherits that `claimed_by`.
If it carried `blocks_agent` / `unblocks_todo_id`, the replacement inherits
those unblock fields too. Use `--next-claimed-by <agent-id>` to make a handoff
explicit.

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
optional `action_kind`, `claimed_by`, `required_capabilities`, and
`target_capabilities`. Primary review handoffs may also carry
`blocks_agent`, `unblocks_todo_id`, and `no_followup=true` to show which
agent/todo they release and whether a completed handoff intentionally has no
successor.
Deferred successors may carry `resume_when`, `resume_condition`, and
`resume_ready`; `resume_ready=true` means the deferred item should be considered
for a successor replan before any agent-scoped no-candidate wait, not that
normal delivery may skip the todo lifecycle.
The `todo_id` is first-class when written by the CLI.
`claimed_by` values are normalized public-safe agent ids and should correspond to
`coordination.registered_agents`. Legacy Markdown without metadata still gets a
parser-derived compatibility id from local section/index/text, and the first
lifecycle command will materialize that id back into metadata. Future lease
timestamps, dependency, capability detail, and evidence-link fields should
extend this item shape instead of adding another todo format.
In Markdown, lane metadata is stored as an indented HTML comment directly under
the checkbox, for example:

```markdown
- [ ] Run one validated benchmark case and write back result or blocker.
  <!-- loopx:todo todo_id=todo_8e280be49441 status=open task_class=advancement_task action_kind=run_eval required_capabilities=shell%2Cbenchmark_runner claimed_by=codex-main-control -->
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
loopx todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe executable agent action>" \
  --task-class advancement_task \
  --action-kind run_eval \
  --required-capability shell \
  --required-capability benchmark_runner
```

Use `--target-capability` when the todo is meant to build, repair,
materialize, or parity-check a capability rather than use that capability as a
prerequisite. For example, a benchmark product-path parity todo can hard-require
only shell while targeting the benchmark runner bridge:

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "<public-safe benchmark parity repair action>" \
  --task-class advancement_task \
  --action-kind benchmark_treatment_product_path_parity \
  --required-capability shell \
  --target-capability benchmark_runner
```

`status` projects `required_capabilities` on every visible todo. `quota
should-run` then derives a read-only `capability_gate` from the visible
executable queue, not from a single preselected todo. With multiple P0 or P1
items, it scans the projected queue in order and exposes the candidate set:
capability-satisfied todos appear in `capability_gate.runnable_candidates`,
while blocked higher-priority candidates remain visible in
`capability_gate.blocked_candidates`. The gate does not choose the final todo;
the agent keeps decision authority and must pick from the runnable set during
its steering audit. If no visible executable candidate can run, the gate returns
`repair_bridge`, `ask_owner`, or `skip` according to the missing capability
class.
`target_capabilities` stay visible in runnable candidate payloads. If a target
bridge is absent, the candidate is annotated with `capability_repair_mode=true`
and `missing_target_capabilities`, but that target is not treated as a hard
execution blocker.

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
