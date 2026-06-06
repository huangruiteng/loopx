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

The command resolves the active state from the project registry, creates the
canonical section when needed, updates `updated_at`, and avoids duplicate exact
todo text. If a dashboard or controller needs the new checklist immediately,
refresh the status projection after the write:

```bash
goal-harness refresh-state --goal-id <goal-id>
```

## Parsed Schema

Projects may keep writing ordinary Markdown checkboxes, but readers should use
the structured projection emitted by status/quota when available. Todo summaries
carry `schema_version=todo_summary_v0`; individual items carry
`schema_version=todo_item_v0`, `todo_id`, `role`, `status`, `priority`,
`title`, `archive_state`, `source_section`, `index`, and `text`. The `todo_id`
is parser-derived from the local section/index/text, so it is stable enough for
local selection and regression checks but not a durable database id across major
rewrites. Future timestamp, dependency, and evidence-link fields should extend
this item shape instead of adding another todo format.

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
python3 examples/project-agent-adoption-smoke.py
```

The first verifies the todo CLI writes canonical active-state sections. The
second verifies an executor-facing path from quota guard hint, to user todo
write, to status projection, to approved project-agent handoff.
