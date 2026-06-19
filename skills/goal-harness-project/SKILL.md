---
name: goal-harness-project
description: Use when connecting a repository or project goal document to Goal Harness, maintaining project-local goal state, refreshing stale dashboard status, syncing local projects into the shared global registry, or diagnosing Goal Harness CLI/PATH/status/history issues across multiple repos. For registering durable project materials such as Lark/wiki/design docs, prefer the narrower goal-harness-doc-registry skill.
---

# Goal Harness Project Workflow

Use this skill when the task mentions Goal Harness, goal-harness, a project goal
document, multi-project dashboard/status, stale latest run,
`.goal-harness/registry.json`, `.codex/goals`, `refresh-state`,
`sync-global`, or connecting a new repo. If the task is mainly about reading,
remembering, recording, indexing, or registering a durable project material,
load `goal-harness-doc-registry` and use that narrower workflow first.

Goal Harness has two layers:

- **Project-local state**: each repo owns `.goal-harness/registry.json` and
  `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`.
- **Shared local control plane**: `~/.codex/goal-harness` stores run history and
  `registry.global.json` for multi-project status.

Do not manually copy one project's registry entry into another project. Local
`connect` and `refresh-state` should sync into the shared global registry
automatically.

## Register Project Authority And Material Sources

When a project agent discovers a durable design document, research note,
benchmark paper, owner packet, migration report, or external material that
future agents may need for routing, validation, or conflict resolution, treat
that as a doc-registry skill trigger. Identify the target project and goal
first; do not register material into the current meta goal just because this
worker found it.

For material owned by the current project, update the project-local doc registry
or equivalent authority map first, then register the compact redacted source
contract in the same project's ignored `.goal-harness/registry.json`:

```bash
goal-harness register-authority-source --goal-id <STABLE_GOAL_ID> ...
```

For another project's DOC_REGISTRY-style map, import only the compact authority
summary instead of copying raw paths, document ids, URLs, comments, or source
bodies:

```bash
goal-harness import-doc-registry-authority --goal-id <STABLE_GOAL_ID> ...
```

After registration, refresh status or state so review packets, read-only maps,
and heartbeat workers can find the new authority without relying on chat
memory. Stop and write a project-local todo or blocker when the target project
is ambiguous, the source cannot be represented as public-safe metadata, or the
next step would require reading a gated source body.

## Preflight

From the target project shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
goal-harness doctor
```

If `goal-harness` is not on PATH:

```bash
install_script="$HOME/goal-harness/scripts/install-local.sh"
if [ -x "$install_script" ]; then
  "$install_script"
  export PATH="$HOME/.local/bin:$PATH"
fi
goal-harness doctor
```

If this still fails, report the exact missing piece and do not fake a successful
connection.

## Diagnose For The User

When the user asks whether Goal Harness is working, whether a project can
self-drive, why it is stuck, or says "diagnose Goal Harness", do not hand the
user shell commands. Run the diagnostic surfaces yourself and then reason from
the evidence.

Prefer the agent-facing packet:

```bash
goal-harness diagnose
```

If the target goal is known:

```bash
goal-harness diagnose --goal-id <STABLE_GOAL_ID>
```

The `diagnose` command is not the final judge. It returns compact
`status`, `quota should-run`, todo, interaction-contract, and boundary signals
plus a reasoning checklist. Use those signals as evidence, then answer in your
own words:

- whether the project can currently self-drive;
- what evidence supports that conclusion;
- what blocks autonomous delivery or self-repair;
- the exact user/controller question, if one is projected;
- what the agent will do next.

Only claim autonomous readiness when your reasoning confirms that the user gate
does not block the selected path, quota permits a turn, `goal_boundary` allows
the work, and there is a concrete agent todo or recommended action. If
`diagnose` cannot read status/quota, repair installation, PATH, registry path,
or project connection first; do not infer readiness from chat memory.

## Before Spending Automatic Compute

Before a heartbeat, scheduled tick, long-running adapter, or autonomous project
agent spends another delivery turn, ask Goal Harness whether this goal is
eligible:

```bash
goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id <STABLE_GOAL_ID>
```

If the response has `state=operator_gate`, treat it as a user/controller
interaction, not a silent skip. Read `gate_prompt`, `operator_question`,
`recommended_action`, `next_handoff_condition`, `missing_gates`, and
`user_todo_summary` and `agent_todo_summary` when present, then ask the concrete gate in Chinese unless
the same unresolved question was already surfaced in the recent visible thread.
Only when `interaction_contract.user_channel.action_required=true` or
`user_todo_summary.open_count > 0`, the notification must name concrete payload
todo(s)/questions, never only "owner gate"; if those required user-facing items
are not projected, say "具体 user todo 未投影，需修复 Goal Harness 状态投影"; never
say "no new user action" for this case. When
`interaction_contract.user_channel.action_required=false` and
`user_todo_summary.open_count=0`, allow "无用户待办/无需通知" or a quiet
no-notification result; do not imply a state projection bug. Do not run
`agent_command`, adapter work,
write-control, production actions, or the gated path while asking.

Prefer the guard's `interaction_contract` when present. It is the current
machine-readable protocol for the user / agent / Goal Harness CLI split:
`interaction_contract.user_channel` says whether to ask the user,
`agent_channel` says whether Codex must attempt work or may quiet no-op, and
`cli_channel` says which CLI transition and spend policy apply. Treat older
fields such as `execution_obligation`, `heartbeat_recommendation`,
`work_lane_contract`, and `goal_boundary` as compatibility/drill-down fields
under that contract, not as competing sources of truth.

If the response has `should_run=false` and not `safe_bypass_allowed=true`, do
not run implementation or adapter work for that goal in this turn. When
`effective_action=monitor_quiet_skip`, append at most one no-spend
`quota monitor-poll --goal-id <STABLE_GOAL_ID> --source heartbeat --execute`
event, rerun `quota should-run`, and follow
`autonomous_replan_required` / `execution_obligation.must_attempt_work=true` if
the next guard exposes it; otherwise quietly report or record the public-safe
`reason` only when there is no operator gate to ask. Keep the heartbeat
automation active: unchanged monitor-only polls are liveness-preserving no-ops,
not self-stop signals. If the command exits non-zero, fail closed: run
`goal-harness doctor` / `goal-harness status` and fix status collection before
spending compute.

If the response has `state=operator_gate` and `safe_bypass_allowed=true`, the
gate blocks only the gated delivery path. After the gate has already been
surfaced, you may still read the active state and do one bounded safe-bypass
step from the Priority Stack, such as read-only steering analysis,
documentation, or another P0/P1 item that does not depend on that gate. If that
safe-bypass step actually spends automatic compute, validate it, write back
progress/critic/next action, optionally refresh state, and append one quota
spend event. If `user_todo_summary.open_count > 0`, the safe-bypass report must
include those existing open user todos and must not say there is "no new user
action". If `agent_todo_summary.open_count > 0`, use it as the project agent's
safe follow-up checklist instead of mining chat history or an overlong Next
Action.

If the response has `safe_bypass_kind=outcome_floor_recovery` or
`heartbeat_recommendation.recommended_mode=outcome_floor_recovery`, the outcome
floor blocks surface-only delivery but permits one bounded recovery attempt:
produce the required ranker/cross-domain evidence artifact named by
`quota.must_advance`, or write back the concrete blocker that prevents that
artifact. Avoid summary/queue/contract propagation and synthetic-only test
chains. Spend exactly once only after validated evidence/blocker writeback.

This guard is only a compute-allocation check. It does not grant write
permission, bypass operator gates, or replace run-bound human reward. Operator
gates block the gated delivery path, not unrelated safe steering work.
For an eligible current goal, dependency or sibling-goal todos must not consume the whole eligible turn.
Record or surface those todos as dependency blockers,
but continue the steering audit and choose a gate-independent
P0/P1/P2 candidate for the current goal when one exists. Stop before delivery
only when the open user/owner todo belongs to the current goal's guard payload
or project asset and blocks the selected delivery path.
Routine public repo publication is a boundary decision, not a standing operator
gate: when the active state permits the step, validation passes, and the
public/private boundary scan is clean, commit, push, and PR creation can proceed
autonomously. Stop for private or company-internal material, credentials,
destructive git operations, production actions, or repository rules that
explicitly require review.
Use the shared global registry for this guard so the project agent reads the
same operator gates, user todos, agent todos, and quota state as the dashboard. This does
not mean all project work is global: `todo add`, `refresh-state`, adapter runs,
and project-file reads still use the project-local state/registry and then sync
the public-safe projection back into the global control plane. If two projects
share a `goal_id`, treat that as a registry health bug and fix the id/source
mapping.

If `should_run=true`, do not simply continue the nearest previous TODO. Read the
active state's Priority Stack, recent progress, and critic, then run a short
steering audit before choosing work: list at least three plausible next-action
candidates across different P0/P1/P2 lanes when useful; if the same topic has
consumed several recent delivery slices, apply a continuation check and state
why continuing still wins; keep compute quota separate from focus quota; record
any losing high-value candidate that should not be forgotten. Include a product
bottleneck lens: ask whether the core goal is currently bottlenecked by user
experience, agent capability, evidence quality, adapter readiness, or
priority-rule gaps, and promote one concrete bottleneck candidate when it should
outrank the nearest local TODO. Then choose exactly one bounded, verifiable step
from that audit.

When you tell the user a connected Goal Harness plan, top-todo list, priority
stack, or route change, treat that as a writeback trigger, not chat memory. If
the plan contains concrete future P0/P1/P2 work, user actions, route decisions,
or deprecations, update active-state todos / Next Action / `refresh-state`
before the final response, or explicitly say why the plan is only speculative
and was not written. Use `goal-harness todo add` / `todo update` for durable
work items; do not leave them only in prose, a review doc, or a Lark/chat
reply.

For connected delivery goals, also read `goal_boundary` from the
`quota should-run` payload before choosing a step. It carries the registry's
adapter status, allowed write scope, parent-approval scopes, guards, and stop
condition. Treat it as the project-specific boundary contract so automation
prompts can stay short instead of repeating long per-project protected-scope
lists.
When reading status or quota routing, use `attention_queue.items` and
`project_asset` as current authority only when the item is project-asset-backed.
If `project_asset` is absent or the source is legacy/raw fallback, do not infer
owner, gate, or stop-condition authority from raw queue fields.

## Set Up Recurring Heartbeats

When a user or controller wants a recurring Codex App heartbeat for a connected
goal, prefer the generator instead of hand-copying the quota lifecycle:

```bash
goal-harness heartbeat-prompt --goal-id <STABLE_GOAL_ID>
```

For live Codex App automations, prefer the thin body as the local machine
default when the target Codex agent can inspect Goal Harness state and CLI
output itself:

```bash
goal-harness heartbeat-prompt --thin --goal-id <STABLE_GOAL_ID>
```

Use the compact body after reviewing the full generated contract when the
installed prompt should carry more lifecycle detail inline:

```bash
goal-harness heartbeat-prompt --compact --goal-id <STABLE_GOAL_ID>
```

If the installed automation body still needs to be smaller, use the brief body:

```bash
goal-harness heartbeat-prompt --brief --goal-id <STABLE_GOAL_ID>
```

For connected goals, omit `--active-state`; the CLI resolves the active state
from the registry goal `state_file`, which keeps installed automations from
pinning a stale path. Pass `--active-state <ACTIVE_GOAL_STATE_PATH>` only for
detached state files, migration checks, or compatibility tests.

Copy the generated task body into the Codex App heartbeat automation. The full
body is the audit source and compatibility default. The thin body is the daily
driver for trusted local workers: it keeps the automation prompt project-agnostic
and tells Codex to re-read registry/global quota truth, active state,
status/run history, repo state, and project signals on each wakeup. The compact
body is useful when context pressure matters but the installed prompt should
still carry the quota, gate, blocker-push, recommendation, steering-audit,
writeback, refresh, and spend lifecycle inline. The brief body keeps only
preflight/guard, core invariants, and spend accounting in the installed prompt
while delegating detailed branches back to the generated compact/full contracts.
The generated guard and spend commands explicitly use the shared global
registry so project heartbeats read the same operator gates and user todos as
the dashboard, regardless of their current repo. Completed heartbeat delivery
spends through `quota spend-slot --source heartbeat --execute`, not through a
natural-language report. Quota slots are minute-granularity by default: minute
heartbeats spend `--slots 1`, while coarser fixed-interval automations should
spend the scheduler minutes consumed by that completed turn.

Keep project-specific behavior out of the automation prompt. Encode local
differences in the project registry, `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`,
adapter output, or narrow public/private boundary rules. If a lifecycle rule is
useful across projects, update `goal-harness heartbeat-prompt` and its smoke
contract rather than hand-editing one heartbeat automation.
For delivery-specific boundaries, prefer the registry fields surfaced in
`quota should-run.goal_boundary`; the automation prompt only needs to say to
obey that payload and stop when useful work falls outside it.

When a Goal Harness client/prompt contract changes, update the matching smoke
coverage in the same patch. Interface-budget and regression constraints belong
in lightweight smoke scripts such as `examples/heartbeat-prompt-smoke.py`,
`examples/quota-plan-smoke.py`, or `examples/quota-contract-smoke.py`; heavier
Codex CLI plus Goal Harness end-to-end checks should stay explicit or
low-frequency instead of becoming the default heartbeat path.

The quota guard returns `execution_obligation` and
`heartbeat_recommendation`. Read `execution_obligation` before deciding on a
quiet no-op: `heartbeat_recommendation.notify` is only the user-notification
policy, not an execution gate. If
`execution_obligation.must_attempt_work=true`, attempt one bounded progress
batch or segment even when `notify=DONT_NOTIFY`; a quiet no-op requires
`execution_obligation.must_attempt_work=false` and no
`notify_user_on_open_todo=true` blocker-push notification. New connected read-only goals
should follow `recommended_mode=run_first_read_only_map`: run one real
`goal-harness read-only-map --goal-id <STABLE_GOAL_ID>`, validate the saved
`read_only_project_map`, spend exactly once after validation, then sync or
refresh state if needed. Already mapped goals should follow
`recommended_mode=mapped_noop_if_unchanged`: if there is no new instruction,
owner evidence, agent todo, stale source, or safe handoff, return a quiet no-op
without another dry-run, file edit, or quota spend.

The generated task body also carries a no-progress self-repair guard. More
importantly, `quota should-run` may expose a hard
`autonomous_replan_obligation` / `execution_obligation.must_attempt_work=true`
contract when active state or public run history shows 2 consecutive stalled
turns. `quota_monitor_poll` events are no-spend stall evidence for this
detector. Obey that machine contract before another quiet no-op: run one
bounded self-repair/replan batch through implementation, validation, and
writeback when that boundary is clear, then spend once. Do not stop at the first
tiny substep when the repair has an obvious validation boundary. Cancel or
pause the heartbeat automation only when that repair path is itself stuck for 2
more eligible turns, explain the no-progress loop with `NOTIFY`, and skip quota
spend for that self-cancel turn.
The same generated task body also makes routine public commit, push, and PR
creation autonomous after validation plus a clean public/private boundary scan.
Do not reintroduce a user gate for public-safe publication itself.
It also respects `notify_user_on_open_todo=true`: open user todos in
focus-wait, waiting, or external-evidence lanes should become a compact
blocker-push `NOTIFY` with at most three items, while skipping delivery work
and quota spend for that blocker-push turn. If the payload includes
`open_todo_notification_policy=repeat_until_resolved`, repeat
that `NOTIFY` on every such poll until the todo is done, deferred, or replaced;
do not suppress it as a recently surfaced blocker. Other blocker-push cases may
still be de-duplicated when the same blocker was already surfaced recently.
Eligible monitor-only no-transition polls keep user todos visible in the
payload but should stay quiet unless a material transition appears.

Keep the Codex App visible goal text short, for example
`按 ACTIVE_GOAL_STATE.md，基于 Goal Harness 体系，推进项目`. Do not use that short
text as the automation body. Across projects, the automation body should be the
same generated lifecycle prompt with only `goal_id`, `active_state`, and narrow
project boundary rules changed. When a project appears to need a custom
automation branch, treat that as a Goal Harness product gap first, not as a
reason to paste one-off control logic into the scheduler.

## Generate A Review Packet

When a project agent, controller thread, or local shell needs the current
operator packet, prefer the CLI packet over asking the user to find a dashboard
copy button:

```bash
goal-harness review-packet --goal-id <STABLE_GOAL_ID>
```

For machine-readable inspection, put the global format flag before the
subcommand:

```bash
goal-harness --format json review-packet --goal-id <STABLE_GOAL_ID>
```

When the human/controller decision is already approved and the only remaining
step is to relay the target-agent instruction, use the minimal handoff form:

```bash
goal-harness review-packet --goal-id <STABLE_GOAL_ID> --handoff-only
```

This command is read-only. It packages the current status into the same Review
Packet shape as the dashboard; it does not append human reward, append an
operator gate, refresh state, grant write-control, or authorize production
actions. `--handoff-only` only strips the human decision wrapper from markdown
output; JSON output returns a minimized handoff payload with `handoff_text`
instead of the full operator packet. If the selected queue item is legacy/raw
fallback rather than project-asset-backed, do not treat raw queue fields as
owner, gate, or stop-condition authority.

Read the packet in order:

- `人只需判断`: the user or controller decides in the dashboard/operator view or
  trusted local shell. A target project agent cannot self-approve this section.
- `用户本地 Gate 记录草稿`: a local preview for the user/controller. The target
  project agent must not run this draft as its own command.
- `给项目 Agent`: the executable handoff context only after the packet's
  forwarding condition is already satisfied. If its stop condition fires, stop
  and report the exact blocker instead of continuing.

## Connect A New Project

1. Read the project goal document and inspect the repo narrowly.
2. Extract a stable `goal_id`, one-line `objective`, `domain`, authority
   sources, validation surfaces, first safe action, and public/private
   boundary.
3. Run `connect` from the project root. Prefer read-only until the goal doc
   explicitly authorizes mutation:

```bash
goal-harness connect \
  --goal-id <STABLE_GOAL_ID> \
  --objective "<OBJECTIVE_FROM_GOAL_DOC>" \
  --domain <DOMAIN> \
  --goal-doc <GOAL_DOC_PATH> \
  --adapter-kind read_only_project_map_v0 \
  --adapter-status connected-read-only
```

`connect` should create or update the local registry/state and auto-sync the
public-safe entry into `~/.codex/goal-harness/registry.global.json`.

One repository can host multiple goals, such as a main controller and a
low-conflict bypass lane. Run `connect` once per stable `goal_id`; keep one
shared `.goal-harness/registry.json`, but use one active state per goal:

```text
.codex/goals/<main-goal-id>/ACTIVE_GOAL_STATE.md
.codex/goals/<bypass-goal-id>/ACTIVE_GOAL_STATE.md
```

Do not reuse one `state_file` for two goal ids. `goal-harness registry` treats
that as a health error, and `read-only-map` checks the selected goal's own
`.codex/goals/<goal-id>/` directory so a healthy main lane does not hide a
missing bypass state.

If the goal state or registry contains private evidence, add `.goal-harness/`
and `.codex/goals/` to that project's `.gitignore`.

For a generic read-only connection, create the first non-generic map run:

```bash
goal-harness read-only-map --goal-id <STABLE_GOAL_ID>
```

This reads registry metadata, the active state, and a bounded project-file
inventory, then appends a `read_only_project_map` run. Use it before writing a
project-specific adapter when the dashboard would otherwise stay on
`state_refreshed` or `connected_without_run`.

For a planned high-complexity adapter, preview the same bounded map before
controller opt-in:

```bash
goal-harness read-only-map --goal-id <STABLE_GOAL_ID> --dry-run
```

If the adapter status is `planned`, only the `--dry-run` preview is allowed and
the result should include `opt_in_required=true`. Do not append a real map until
the user or target controller has moved the adapter to `read-only-map-ready`,
`connected-read-only`, or `connected`. Relay the returned `residual_risks`
labels directly; do not invent a separate free-form risk summary.

When the user or target controller answers the opt-in gate, record that answer
before handing the command to another project agent:

```bash
goal-harness operator-gate \
  --goal-id <STABLE_GOAL_ID> \
  --decision approve \
  --reason-summary "<PUBLIC_SAFE_CHINESE_REASON>" \
  --dry-run
```

Use `approve`, `reject`, or `defer`. The dry-run writes nothing; the real append
creates an `operator_gate_*` compact run so `goal-harness status` and the
dashboard can tell whether the project agent may run the approved command. This
is not a human reward signal and does not grant write-control.

## Refresh State After Non-Adapter Work

If the agent updated `ACTIVE_GOAL_STATE.md`, a progress ledger, a planning doc,
or external coordination state without producing a new adapter run, append a
state-only refresh:

```bash
goal-harness refresh-state --goal-id <STABLE_GOAL_ID>
```

If that refresh records a validated progress artifact rather than a pure
state-only note, include a public-safe classification and explicit delivery
hints so status, review packets, and quota guards do not infer scale/outcome
from the classification name:

```bash
goal-harness refresh-state \
  --goal-id <STABLE_GOAL_ID> \
  --classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION> \
  --delivery-batch-scale multi_surface \
  --delivery-outcome outcome_progress
```

Use `delivery_outcome` as a machine enum, not as prose:

- `surface_only`: docs, contracts, smokes, setup, or preparation moved, but the
  primary product/case result did not.
- `outcome_gap`: the run should have advanced the primary result but ended with
  a concrete blocker or missing outcome.
- `outcome_progress`: primary result evidence advanced materially, but the
  selected stage is not fully complete.
- `primary_goal_outcome`: the selected stage's primary result is complete,
  validated, and written back.

Do not rely on `classification` names such as `*_contract_v0_delivered` to carry
this meaning. `classification` is a human/history label; `delivery_outcome` is
the control-plane signal consumed by quota, status, and review packets.

This fixes stale dashboards where the latest run still shows an old
`ready_for_controller_opt_in` or similar state. It also auto-syncs the project
entry into the global registry. If you do not pass `--recommended-action`, the
refresh run should publish the first public-safe item from `## Next Action` as
the compact dashboard action, including wrapped continuation lines; keep raw
evidence and private links in the state file, not in that action item.

For complex projects, do not pack a whole user reading queue into
`## Next Action`. Keep the first Next Action item as one routing sentence, then
use the CLI to write explicit checkbox sections instead of hand-editing section
names:

```bash
goal-harness todo add \
  --goal-id <STABLE_GOAL_ID> \
  --role user \
  --text "Read the short review packet before approving delivery."

goal-harness todo add \
  --goal-id <STABLE_GOAL_ID> \
  --role agent \
  --text "Build the next read-only worksheet after the user decision is recorded."
```

The CLI creates the canonical section when needed and avoids duplicate exact
todo text. The resulting Markdown shape is:

```md
## User Todo / Owner Review Reading Queue

- [ ] Read the short review packet.
- [ ] Record the owner decision in the worksheet.

## Agent Todo

- [ ] Build the next read-only worksheet after the user decision is recorded.
```

`goal-harness status` lifts those sections into `user_todos` and `agent_todos`.
The dashboard uses `user_todos` for the first-screen human checklist; project
agents should read `agent_todos` only after health, operator gates, evidence,
and quota allow execution.

For non-trivial feature work, prefer todo succession over extra lifecycle
states. When a slice merges or validates, complete the current todo only after
creating the next concrete agent/user todo for rollout, product-path audit,
docs, telemetry, benchmark proof, or operator decision; if there is truly no
follow-up, write a compact no-follow-up rationale in the completion note.

## Record Human Reward

When the user gives a clear reward judgment for an exact run, first validate
the overlay and active-state writeback:

```bash
goal-harness reward \
  --goal-id <STABLE_GOAL_ID> \
  --run-generated-at <RUN_GENERATED_AT> \
  --decision <DECISION_LABEL> \
  --reward positive \
  --reason-summary "<PUBLIC_SAFE_CHINESE_REASON>" \
  --follow-up "<PUBLIC_SAFE_NEXT_ACTION>" \
  --write-active-state-summary \
  --dry-run
```

Only after the user has explicitly approved recording the reward, rerun without
`--dry-run`. The durable source of truth is still the run-bound
`human_reward` overlay. The active-state writeback is a `Progress Ledger`
summary for future agents; project agents should read the reward through the
returned `project_agent_visibility.history_command`.

## Multi-Project Status

Inside a project:

```bash
goal-harness status
```

Outside a project, `goal-harness status` should fall back to:

```text
~/.codex/goal-harness/registry.global.json
```

Use explicit sync only for diagnosis or recovery:

```bash
goal-harness sync-global
```

If status shows `unregistered_runtime_goal`:

- If the project is active, run `goal-harness sync-global` or reconnect from
  that project's local registry.
- If the runtime record is obsolete, preview cleanup with
  `goal-harness archive-runtime --goal-id <GOAL_ID>` and only execute cleanup
  when that is clearly intended.

## Validation

After connect or refresh, run the smallest useful set:

```bash
goal-harness registry
goal-harness status
goal-harness check --scan-path <PUBLIC_SAFE_FILE_OR_DIR>
```

For multi-project UI updates, refresh the dashboard status JSON from the global
registry:

```bash
goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" \
  --format json status > <dashboard>/public/status.local.json
```

## Reporting

Report in Chinese when the user is reviewing:

- changed files and whether they are public or local-private;
- validation commands and results;
- how the goal appears in dashboard or attention queue;
- the next safe action;
- any missing gates before decision-advisor or write-controller behavior.

Never include credentials, private docs, raw internal links, production task
ids, or raw local evidence in public repo docs or examples.
