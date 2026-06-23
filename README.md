# LoopX

<img align="right" src="docs/assets/loopx-logo.png" alt="LoopX loop engineering logo" width="148">

**Loop engineering for long-running AI agents.**

**Manage long-running agents like digital workers.**

**把会干活的 Agent，接成可管理、可复盘、可持续改进的数字员工。**

LoopX is a local control plane for loop engineering. It helps Codex,
Claude Code, Cursor, and other agent runtimes keep working on goals that span
hours, days, handoffs, and changing human feedback.

Use it when an agent is already useful for one session, but the work is too
long, too gated, or too easy to lose across restarts. LoopX turns that agent
surface into a reviewable Loop Agent: stable objective, explicit gates, scoped
next actions, evidence, cost, and handoff state. The agent still needs a CLI,
goal mode, automation hook, or loop scheduler; LoopX supplies the control
plane, not hidden autonomy.

Under the hood, LoopX keeps goals, gates, todos, claims, scopes, evidence, run
history, quota, and human decisions in one compact layer. Product surfaces fold
those mechanics into five questions a user can act on: what is the goal, what
is next, what needs human judgment, what evidence changed, and whether the loop
can be handed back to the agent.

LoopX 把一次静态 goal 变成能持续流转的动态 loop：该等人的地方明确等人，
不该空等的安全侧路继续推进，下一轮 agent 总能读到目标、边界、证据和交接。

[Quick Start](#quick-start) · [Who Should Try It](#who-should-try-it) · [See It In Action](#see-it-in-action) ·
[Getting Started](docs/guides/getting-started.md) · [Showcases](docs/showcases/README.md) ·
[Hosted Frontstage](https://huangruiteng.github.io/loopx/frontstage/) ·
[Community](#community--feedback) · [Product Vision](docs/product/vision.md) · [Architecture](docs/architecture.md) ·
[Dashboard](apps/dashboard/README.md) · [简体中文](README.zh-CN.md)

> Keep the loop moving. Keep the judgment human.

## Who Should Try It

LoopX is for people who already have an agent that can do useful work, and now
need that work to continue without turning into stale chat memory.

Start here if you are running:

- multi-day engineering, research, benchmark, or experiment goals;
- issue/PR fixing loops where the agent must preserve scope, evidence, and
  review state across turns;
- recurring heartbeat or monitor-style agent work;
- projects with owner/SOP gates, human reward judgments, or public/private
  boundary checks;
- controller/side-agent workflows where todo ownership and handoff matter;
- creator, research, or operations workflows where non-engineering users need
  agent progress translated into clear state, blockers, and feedback prompts.

LoopX is not an autonomous production controller. It is a local coordination
substrate: dangerous permissions, publishing, production writes, and final
ownership stay with the human/operator.

## Quick Start

Requirements: Python 3.11+, `curl`, `tar`, macOS or Linux shell. Git is only
needed for contributor clone/canary workflows. The Python package has no
runtime dependencies outside the standard library.

The easiest start is agent-first: ask the agent you already use to install,
connect, diagnose, and show the next safe action before doing longer work.

### Codex App

Best when you want LoopX to keep working through Codex App heartbeats. Paste
this in the current project thread:

```text
Connect the current project to LoopX.
Do not clone the LoopX repository for ordinary use. If `loopx` is not on PATH,
install or repair it with the official no-clone installer:
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash

Then run `loopx doctor`. Work only from the current project root: if LoopX state
already exists, reuse it and do not create or overwrite a goal; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
goal state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. After the project is connected, set or refresh this
thread's heartbeat automation from `loopx heartbeat-prompt --thin`. Then stop
and report the goal id, current user gate, top agent todo, and next safe
action.
```

The generated heartbeat body is the recurring Codex App work surface:

```bash
loopx heartbeat-prompt --thin --goal-id <goal-id> --agent-id <agent-id> --agent-scope "<scope>"
```

### Codex CLI

Best when the visible TUI should stay primary. Open Codex CLI from your project
repo:

```bash
cd /path/to/your-project
codex
```

Then paste one setup message:

```text
Connect this repo to LoopX from this visible Codex CLI TUI. Do not clone the
LoopX repository for ordinary use. If `loopx` is not on PATH, install or repair
it with the official no-clone installer:
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash

Then run `loopx doctor`. Work only from this project root: if LoopX state
already exists, reuse it and do not create or overwrite a goal; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
goal state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. Keep me in this TUI, do not use hidden headless
execution. After the project is connected, generate the thin heartbeat prompt
and set the current Codex CLI goal to `/goal <thin task_body>`. Then stop and
report the goal id, current user gate, top agent todo, and next safe action.
```

That one message is the install, connect, heartbeat setup, and status check.
The first useful TUI response should show the current goal, any concrete user
gate, top todos, and next safe action. Hidden `codex exec` is not the default
bootstrap path. Details for generated messages, later same-TUI automation, and
proof capture live in [Getting Started](docs/guides/getting-started.md).

A successful connection looks like this:

- `loopx doctor` passes;
- the project has `.loopx/registry.json`;
- the project has `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`;
- `loopx status` shows who should act next;
- local runtime state is ignored, not committed.

### Other Agents And Manual Shell

For Claude Code, Cursor, another terminal agent, or a manual shell, use the
same no-clone installer. Be cautious with non-Codex agents: LoopX can only
drive the agent path if that surface has at least one usable control hook, such
as shell/CLI execution, a goal/task command, an automation or heartbeat hook,
or its own loop/scheduler. If the agent has none of those capabilities, LoopX
can still track the project state, but the user must run the shell commands
manually.

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

Then ask the agent to connect or run the command yourself:

```bash
cd /path/to/your-project
loopx bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

Clone-based install is only for contributors who want the live canary wrapper:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
loopx doctor
```

For the full install, diagnose, connect, heartbeat, dashboard, development, and
command-reference workflow, read
[docs/guides/getting-started.md](docs/guides/getting-started.md).

## See It In Action

Want proof before reading the control-plane details? Use three short entry
points:

- [Hosted Frontstage](https://huangruiteng.github.io/loopx/frontstage/):
  the public showcase homepage with the canonical case cards.
- [Blocked P0 with safe P1/P2 rotation](docs/showcases/cases/0617-blocked-p0-safe-rotation.md):
  a reproducible synthetic demo where a human gate stays visible while safe
  fallback work continues.
- [LoopX self-iteration](docs/showcases/cases/0619-loopx-self-iteration.md)
  and the [hardware-agent workflow](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.md):
  public-safe evidence that one control plane can coordinate primary and side
  agents without hiding ownership or scope.

For more cases, open the [showcase catalog](docs/showcases/README.md). For a
full presenter material, see the experimental notes below.

## What Is It?

LoopX does not replace Codex, Claude Code, Cursor, or another agent
runtime. It sits above them as a loop-engineering control plane: the runtime
executes bounded agent loops, while LoopX preserves the dynamic goal state those
loops need to keep working without losing the plot.

Short answer: LoopX is not another executor. Codex goal, Codex App
automation, CLI scripts, cron jobs, or a human-visible TUI can trigger the next
executor loop; LoopX keeps the goal, gate, evidence, quota, and handoff contract
stable across those turns.

| Layer | Role |
| --- | --- |
| Codex / Claude Code / Cursor | Execute a bounded agent loop: read, write, run commands, and respond. |
| Goal mode / automation / CLI scripts / TUI | Trigger or schedule the next executor loop. |
| LoopX | Preserve the dynamic loop state: gates, todos, run history, quota, evidence, boundaries, and handoff state. |

The product promise is not "more todo lists." It is a practical foundation for
loop engineering: keep human judgment at high-value decision points, keep safe
fallback work moving when one lane is gated, and stop compute spend when a turn
cannot produce a verified transition.

Put differently: LoopX lets a user's agent team keep working across tools,
turns, and off-hours without turning the project into a pile of hidden scripts
and stale prompts. The technical contract underneath that promise is explicit:
agent identity, todo ownership, scope, capability gates, quota, evidence
writeback, and public/private boundaries stay visible to the next turn.

![LoopX control-plane board](docs/assets/control-plane-board.svg)

## User Mental Model

LoopX has more kernel concepts than a user should have to think about every
day. The product surface should collapse them into five questions:

| User question | Kernel objects behind it | What the user should see |
| --- | --- | --- |
| Goal | goal state, scope | What are we trying to move, and what is out of bounds? |
| Next step | todo, claim, quota | What small action can the agent or human take now? |
| Judgment | user gate, boundary authority | What needs human approval, route choice, or reward feedback? |
| Evidence | run history, artifacts, validation | Why should we believe the state changed? |
| Handoff | active state, handoff packet | Can the next agent turn continue safely, and from where? |

The CLI keeps the full contract available for debugging. The dashboard and
frontstage should start from these five questions, not from raw logs.

## Why Loop Engineering Needs A Control Plane

Short agent tasks usually fail because the model makes a bad local choice.
Long-running loops fail differently: state drifts.

Loop engineering often begins with a timer, a long prompt, a shell script, or a
visible TUI session. That can prove the idea, but it is not enough for real
work. Once the goal changes, the user gives feedback, an owner gate appears, or
multiple agents touch the same repo, the loop needs shared state instead of
chat memory.

After several runs, several projects, or several handoffs, the hard questions
become:

- What is the current objective, and what is explicitly out of scope?
- Which owner decision, source document, run artifact, or benchmark result is
  the current authority?
- What did the last agent run actually do, and how was it validated?
- Which next action belongs to the human, and which belongs to the agent?
- Which actions are safe read-only work, and which cross write, production,
  private-data, or publication boundaries?
- How does human feedback survive into the next run?

LoopX makes those questions machine-readable enough for agents and legible
enough for operators, so a loop can run longer without becoming less
accountable.

The value model is broader than a single task score: LoopX aims to make a
Loop Agent reviewable by output quantity, output quality, token cost, and user
attention cost. See the
[project-level reward model](docs/product/project-level-reward-model.md) for
the conservative schema and benchmark boundary.

For a short version of the operating model, read
[Loop Engineering principles and pitfalls](docs/product/loop-engineering-principles-and-pitfalls.md)
or the
[Chinese version](docs/product/loop-engineering-principles-and-pitfalls.zh.md).

## What You Get

- **Lifetime goals**: durable project intentions that outlive one chat thread,
  run, todo, or implementation plan. A lifetime goal does not grant open-ended
  autonomy: only the next bounded transition is executable.
- **User gates**: concrete human decisions that stay visible instead of
  disappearing into chat.
- **Safe fallback**: audited side paths that can continue when one lane is
  gated, without bypassing the gate.
- **Todo ownership**: user and agent todos with `claimed_by` for multi-agent
  coordination.
- **Quota and steering**: a guard that says whether an automatic turn should
  run, wait, ask the user, self-repair, or stay quiet.
- **Run history and evidence**: compact append-only events for progress,
  validation, blockers, reward, benchmark results, and quota spend.
- **Read-first management surface**: a local dashboard for project selection,
  todo search, agent lanes, user gates, evidence, and review signals.
- **Performance review**: project-level value signals across output quantity,
  output quality, token cost, and user attention cost.
- **Public/private boundary checks**: local scans and docs rules to keep raw
  private state, credentials, logs, traces, and benchmark material out of
  public artifacts.

## Community & Feedback

LoopX is still early. The most useful feedback comes from real
long-running agent projects: where the control plane helped, where it felt
heavy, and which user gates or handoffs still disappeared from view.

- Use [GitHub Issues](https://github.com/huangruiteng/loopx/issues) for
  reproducible bugs, install problems, and feature requests.
- Open PRs for docs fixes, showcase writeups, and small public-safe examples.
- For Chinese-speaking early users, scan the Lark group first for fast
  onboarding help, feedback loops, and showcase co-creation. A WeChat group QR
  is available as a backup, but QR codes may expire; if one is stale, use Lark
  or open an issue to ask for a refresh.

<table>
  <tr>
    <td align="center" width="240">
      <img src="docs/assets/loopx-lark-user-group.png" alt="LoopX Lark user group QR code" width="200"><br>
      Lark group
    </td>
    <td align="center" width="240">
      <img src="docs/assets/loopx-wechat-user-group.png" alt="LoopX WeChat user group QR code" width="200"><br>
      WeChat group, may expire
    </td>
  </tr>
</table>

## Core Workflows

After a project is connected, the daily loop is intentionally small:

```bash
loopx status
loopx history --goal-id your-project-goal
loopx quota should-run --goal-id your-project-goal
```

Users should not need to diagnose LoopX by hand. Ask your agent to run
the diagnostic packet and reason from it:

```text
Diagnose LoopX for this project end to end. Do not ask me to run shell
commands. Run loopx diagnose, tell me whether the project can
self-drive, what blocks it, the exact user/controller question if one exists,
and what you will do next.
```

Common operator actions:

```bash
loopx todo add --goal-id your-project-goal --role agent --text "Run the next bounded validation slice."
loopx review-packet --goal-id your-project-goal
loopx refresh-state --goal-id your-project-goal
```

Automatic turns should check quota before work and spend exactly once after
validated writeback:

```bash
loopx quota should-run --goal-id your-project-goal
loopx heartbeat-prompt --thin --goal-id your-project-goal
loopx quota spend-slot --goal-id your-project-goal --slots 1 --source heartbeat --execute
```

The `next_automatic_turn` reported by `quota plan` is only an advisory
scheduling hint: it chooses the highest-compute eligible goal. operator-gated, focus-waiting, waiting, throttled, paused, and health-blocked goals stay out of the eligible lane. When a control-plane repair is explicitly enabled,
`control_plane.self_repair.enabled=true` lets `quota should-run` return a
bounded `decision=self_repair` contract instead of normal delivery; missing
policy defaults off.

If quota returns a `gate_prompt` or `operator_question`, the target heartbeat
should proactively ask that concrete user/controller gate. If open user todos
are projected, do not call the turn "no new user action" while they remain open;
even during safe bypass, its report still has to list existing open user todos.
When `notify_user_on_open_todo=true`, skip delivery work and quota spend for
that blocker-push turn. With `safe_bypass_allowed=true`, the heartbeat may
still do one bounded read-only steering or analysis step. See
`docs/quota-allocation.md` for the full allocation contract.

After an automatic turn actually spends delivery compute, append one spend
event. Do not append spend for quiet `should_run=false` skips, preflight
failures, or pure dry-run previews.

The dashboard is optional and local:

```bash
loopx serve-status --global-registry --port 8766 --limit 80
cd ~/loopx/apps/dashboard && npm install && npm run dev
```

Before publishing docs or examples, keep the public/private boundary explicit:

```bash
loopx check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

More detail lives in [Getting Started](docs/guides/getting-started.md);
contracts live in [Status Data](docs/status-data-contract.md),
[Quota Allocation](docs/quota-allocation.md), and
[Public/Private Boundary](docs/public-private-boundary.md).

## Product Vision

LoopX starts with AI coding, research, and benchmark loops because those
workflows make state drift easy to see. The broader product direction is a
dynamic goal control plane for any long-running agent work where humans need
clear progress, gates, feedback, and recovery without reading raw logs.

The near-term open-source path is maintainer-first: help people manage agents
that read issues, propose fixes, open PRs, resolve review feedback, run
benchmarks, and keep evidence attached to the work. That path is valuable even
before LoopX controls execution, because it gives maintainers a readable queue
of goals, gates, todos, evidence, cost, and feedback.

The broader product shape is a Loop Agent: an agent with a relatively stable
responsibility, a continuing stream of external signals, and a recurring need
to prove that its output quality, cost, and human-attention footprint are
improving. A Loop Agent could be a coding maintainer, an experiment optimizer,
a research assistant, or a creator/operator assistant. LoopX is the control
plane that keeps those loops reviewable before they become more autonomous.
LoopX makes the "digital worker" idea operational: goals, gates, evidence,
cost, and feedback stay reviewable over time.

A medium-term productization case is a creator-operator workflow: a
non-engineering user asks an agent to track social-platform trends, map them to
personal creative preferences, extract insights, draft content, and maintain a
material library. The same control-plane shape applies: what happened, what is
happening, where it is blocked, what comes next, and how user feedback changes
the plan.

See [Product Vision](docs/product/vision.md) for the planned creator-operator
case, non-technical status model, fake-data demo path, and feedback/boundary
contract.

## Documentation Map

- [Getting started](docs/guides/getting-started.md): install, connect,
  diagnose, daily workflow, heartbeats, dashboard, development, and command
  reference.
- [Documentation index](docs/README.md): stable docs grouped by audience.
- [Architecture](docs/architecture.md): lifetime-goal invariant and core
  control-plane shape.
- [Codex CLI packaged install](docs/product/codex-cli-packaged-install.md):
  no-clone install/update/start path for Codex CLI users.
- [Integration guide](docs/integration.md): how to connect a project to Goal
  LoopX state.
- [Showcase catalog](docs/showcases/README.md): public-safe cases and future
  frontend data.
- [Benchmark developer workflow](docs/benchmark-developer-workflow.md):
  public-safe benchmark setup, cloud-host execution, and evidence rules.
- [Status data contract](docs/status-data-contract.md): dashboard/status JSON
  contract.
- [Quota allocation](docs/quota-allocation.md): `should-run` and spend
  semantics.
- [Public/private boundary](docs/public-private-boundary.md): what may be
  committed, published, or retained.
- [Contributor tasks](CONTRIBUTOR_TASKS.md): public, claimable work.

## Contributing

External contributors should start with
[CONTRIBUTOR_TASKS.md](CONTRIBUTOR_TASKS.md) for public, claimable work and
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, and boundary rules.

LoopX keeps local active goal state separate from the public repository:
do not commit `.loopx/`, `.codex/goals/`, live
`ACTIVE_GOAL_STATE.md`, raw benchmark traces, or private operator artifacts.

Before publishing docs or examples, run:

```bash
loopx check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

## Current Status

LoopX is early. It is not a full agent platform and not an autonomous
production controller.

The current milestone is a useful local substrate for goal state, run history,
operator gates, human reward, structured todos, quota-aware heartbeats,
read-only project maps, benchmark control-plane evidence, and a small
multi-project dashboard.

The next milestones are a clearer maintainer workflow for issue/PR loops,
stronger project adapters, safer controller/sub-agent coordination, better
benchmark-runner ergonomics, and a more polished management surface that maps
kernel state into the five user questions above.

## Experimental

These surfaces are useful for demos and product iteration, but they are not the
main getting-started path yet.

### Review Agent Work

After a project is connected, LoopX can be used as a read-first management
surface before it is trusted with more control. The local dashboard helps you
inspect all connected projects, search todos, review user gates, compare agent
lanes, and follow evidence without reading raw logs.

```bash
loopx serve-status --global-registry --port 8766 --limit 80
cd ~/loopx/apps/dashboard && npm install && npm run dev
```

This surface is intentionally conservative: CLI state remains the source of
truth, browser writes require explicit local opt-in, and review signals are
kept separate from execution permission. See the
[intelligent management surface](docs/product/intelligent-management-surface.md)
and [project-level reward model](docs/product/project-level-reward-model.md)
for the longer product direction.

For a timed presenter walkthrough, use the
[3-minute demo script](docs/outreach/frontstage-demo-script.md).

## License

MIT. See [LICENSE](LICENSE).
