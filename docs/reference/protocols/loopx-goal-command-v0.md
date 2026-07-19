# loopx_goal_command_v0

`loopx_goal_command_v0` defines the project-local `/loopx` slash command:

| Command | Intent | Mutation policy |
| --- | --- | --- |
| `/loopx` | Inspect or preview project connection. | Read-first; ask before bootstrap/connect writes. |
| `/loopx <goal text>` | Start a concrete goal, plan ranked todos, activate the host loop, and enter the LoopX automation flow. | Explicit invocation may write project-local LoopX state and todos, then must activate or gate the host loop. |

This command is intentionally separate from `/loopx-global-*`: global commands
summarize and manage visible control-plane state across projects, while
`/loopx <goal text>` starts or continues one project goal.

## Goal-Start Flow

When the user provides text after `/loopx`, the host should:

1. Treat the text as explicit user intent to start this project goal.
2. Connect project-local LoopX state if no matching registry goal exists.
3. Plan before writing todos.
4. Write planned todos in exact plan order.
5. Run `refresh-state`.
6. Activate the host loop if it is missing, unknown, or stale:
   - `codex-app`: create or update the Codex App heartbeat automation from the
     generated `heartbeat-prompt` task body.
   - `codex-cli`: set the visible Codex CLI TUI to `/goal <task_body>`.
   - `claude-code`: arm LoopX with `/loopx <task>`, then run native `/loop`.
   - `opencode`: call `loopx_goal_activate` from the installed LoopX OpenCode
     bridge; the bridge gates idle continuation and timer wakes through
     `quota should-run` and completes only on validated terminal no-follow-up.
   - `manual` / `other-agent`: wire the external loop driver described by
     `loopx agent-onboard`.
7. If the host cannot mutate that surface, report the exact pasteable gate
   instead of claiming autonomous setup complete.
8. Run `quota should-run`, then start the first bounded segment only when the
   quota contract allows it.

New hosts should discover exact agent types with:

```bash
loopx agent-onboard --list-agent-types
```

Ambiguous values such as `codex` must fail closed because Codex App and Codex
CLI use different host-loop activation paths.

Agent identity follows the same fail-closed rule. A goal with one registered
agent may select that identity automatically. A goal with multiple registered
agents and no `--agent-id` must project a concrete identity-selection gate with
executable scoped choices; it must not advertise unscoped heartbeat or quota
commands. Once selected, the identity must be preserved across `agent-onboard`,
`bootstrap-command-pack`, `start-goal`, heartbeat prompt, and quota commands.

The command pack preview is still read-only. It describes the commands and
contracts; the slash invocation is what authorizes project-local state writes.
New-user surfaces should also show the compact slash command catalog from the
command pack, or the equivalent `loopx slash-commands` CLI help, so users can
discover `/loopx`, `/loopx <goal text>`, and the `/loopx-global-*` read-only
manager commands.

## Planning Contract

The planner must create an ordered planning checkpoint before any `todo add`,
but the shape depends on how clear the goal already is:

- `open_ended_product_direction`: broad or fuzzy product directions should
  produce 2-5 public-safe todo items so the user can see the main lanes,
  risks, and execution order before LoopX starts working.
- `clear_bounded_problem`: concrete tasks with a clear success condition should
  use a planner-sized ordered todo plan. The model should produce enough
  concise todos to make the approach explicit, without arbitrary item-count
  caps or management-only filler.

Each new item includes:

- `priority`: `P0`, `P1`, or `P2`;
- `text`: a short checkbox title beginning with `[P0]`, `[P1]`, or `[P2]`;
- `task_class`: usually `advancement_task`;
- `action_kind`: a compact action token such as `implement`, `test`,
  `review`, `document`, or `investigate`.

At least one new item should be `P0` unless the first useful step is blocked by
a concrete user gate. User todos are reserved for owner decisions, private
material, credentials, destructive git, or production authorization.

## Priority Ordering

Priority buckets sort as `P0`, then `P1`, then `P2`. Within the same bucket,
the planner's list order is the relative priority.

Hosts must preserve that order while running `loopx todo add`. LoopX status and
quota projections already use todo index as the same-priority tie-breaker, so
the first written `P0` outranks the second written `P0` without adding a new
rank field.

## Issue-Fix Domain Route

When `/loopx <goal text>` contains a public GitHub issue/PR URL or an explicit
issue-fix intent, the planner should preview the dedicated capability route
before writing todos:

```bash
loopx issue-fix workflow-plan \
  --url <github-issue-or-pr-url> \
  --repo-path <approved-repo> \
  --repository-context-json <compact-context.json> \
  --validation-label "<validation command>" \
  --format json
```

The preview maps public metadata, repository context, intake classification,
branch planning, validation labels, the feasibility checkpoint, and PR review
readiness blockers into `/loopx <goal text>`. Repository context pins compact
policy, architecture, change-scope, reproduction, and validation refs to a
revision; memory and external experts stay advisory until repository-verified.
Initially write only metadata classification and the feasibility checkpoint in
priority and planner order. Then record a compact observation and let LoopX
select exactly one route:

```bash
loopx issue-fix feasibility \
  --url <github-issue-url> \
  --reproduction-status <confirmed|planned|missing|blocked> \
  --scope-class <bounded|uncertain|oversized> \
  --repository-context-json <compact-context.json> \
  --goal-id <goal-id> \
  --format json
```

Write only the projected route successor or no-follow-up. User todos or operator
gates must cover private repro material, issue body/comment reads, external
issue comments, PR creation, merge, publish, destructive git, production
actions, and repository-policy approvals.

## Stop Conditions

Stop and ask the user instead of writing or executing when:

- private source material must be read before a public-safe todo can be formed;
- credentials or secrets are required;
- destructive git or production actions are needed;
- the host cannot execute shell/CLI/tool calls or persist LoopX state;
- the host cannot activate or expose the required host loop and no concrete
  pasteable gate can be shown.
