# loopx_goal_command_v0

`loopx_goal_command_v0` defines the project-local `/loopx` slash command:

| Command | Intent | Mutation policy |
| --- | --- | --- |
| `/loopx` | Inspect or preview project connection. | Read-first; ask before bootstrap/connect writes. |
| `/loopx <goal text>` | Start a concrete goal, plan ranked todos, and enter the LoopX automation flow. | Explicit invocation may write project-local LoopX state and todos. |

This command is intentionally separate from `/loopx-global-*`: global commands
summarize and manage visible control-plane state across projects, while
`/loopx <goal text>` starts or continues one project goal.

## Goal-Start Flow

When the user provides text after `/loopx`, the host should:

1. Treat the text as explicit user intent to start this project goal.
2. Connect project-local LoopX state if no matching registry goal exists.
3. Plan before writing todos.
4. Write planned todos in exact plan order.
5. Run `refresh-state`, then `quota should-run`, then start the first bounded
   segment only when the quota contract allows it.

The command pack preview is still read-only. It describes the commands and
contracts; the slash invocation is what authorizes project-local state writes.

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

## Stop Conditions

Stop and ask the user instead of writing or executing when:

- private source material must be read before a public-safe todo can be formed;
- credentials or secrets are required;
- destructive git or production actions are needed;
- the host cannot execute shell/CLI/tool calls or persist LoopX state.
