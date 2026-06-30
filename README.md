<div align="center">

<img src="docs/assets/loopx-social-preview.png" alt="LoopX loop engineering social preview banner" width="720">

**Loop engineering for long-running AI agents.**

<sub>Manage Codex, Claude Code, Cursor, and other agent runtimes like
reviewable digital workers: goals, gates, todos, quota, evidence, and handoff
state in one local control plane.</sub>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Local first](https://img.shields.io/badge/control--plane-local--first-brightgreen.svg)](docs/public-private-boundary.md)
[![Loop Agents](https://img.shields.io/badge/status-loop%20agents%20early-orange.svg)](docs/product/release-readiness.md)

**把会干活的 Agent，接成可管理、可复盘、可持续改进的数字员工。**

</div>

---

LoopX is a local control plane for agent loops that last longer than one chat
turn. It does not replace Codex, Claude Code, Cursor, or another runtime; it
keeps the shared state those runtimes need to continue safely across hours,
days, handoffs, blocked lanes, and changing human feedback.

Use it when an agent is already useful for one session, but the work is too
long, too gated, or too easy to lose across restarts. LoopX turns that agent
surface into a reviewable Loop Agent: stable objective, explicit gates, scoped
next actions, evidence, cost, and handoff state. The agent still needs a CLI,
goal mode, automation hook, or loop scheduler; LoopX supplies the control
plane, not hidden autonomy.

[How It Works](#how-it-works) · [Quick Start](#quick-start) · [See It In Action](#see-it-in-action) ·
[Capability Surface](#capability-surface) ·
[Getting Started](docs/guides/getting-started.md) · [Showcases](docs/showcases/README.md) ·
[Hosted Frontstage](https://huangruiteng.github.io/loopx/frontstage/) ·
[Release Readiness](docs/product/release-readiness.md) ·
[Update Notes](docs/update-notes/README.md) ·
[Community](#community--feedback) · [Product Vision](docs/product/vision.md) · [Architecture](docs/architecture.md) ·
[Dashboard](apps/dashboard/README.md) · [简体中文](README.zh-CN.md)

> Keep the loop moving. Keep the judgment human.

## How It Works

Under the hood, LoopX keeps goals, gates, todos, claims, scopes, evidence, run
history, quota, and human decisions in one compact layer. Product surfaces fold
those mechanics into five questions a user can act on: what is the goal, what
is next, what needs human judgment, what evidence changed, and whether the loop
can be handed back to the agent.

Short answer: LoopX is not another executor. Codex goal, Codex App
automation, CLI scripts, cron jobs, or a human-visible TUI can trigger the next
executor loop; LoopX keeps the goal, gate, evidence, quota, and handoff contract
stable across those turns.

```text
goal / issue / project
   │
   ▼
LoopX state: objective + gates + todos + scope + evidence + quota
   │
   ├─ human judgment needed? ── yes ─▶ ask / wait with a concrete user todo
   │
   ├─ safe fallback available? ──────▶ run a bounded agent slice
   │
   ▼
Codex / Claude Code / Cursor / shell agent executes one loop
   │
   ▼
write evidence + handoff + next todo ─▶ quota decides the next tick
```

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

LoopX 把一次静态 goal 变成能持续流转的动态 loop：该等人的地方明确等人，
不该空等的安全侧路继续推进，下一轮 agent 总能读到目标、边界、证据和交接。

![LoopX control-plane board](docs/assets/control-plane-board.svg)

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

Start agent-first: paste one setup message for the surface you already use,
then start real work with `/loopx <complex task>`.

Choose your surface:

- **Codex App**
  - Best when: you want a long-running agent that can wake up, re-check gates,
    and keep moving.
  - Start with: paste the setup message below, then ask
    `/loopx <complex task>`.

- **Codex CLI**
  - Best when: you want the visible TUI to stay primary while LoopX keeps the
    state.
  - Start with: run `codex`, paste the setup message, then ask
    `/loopx <complex task>`.

- **Claude Code**
  - Best when: you want Claude Code's native `/loop` to drive each tick.
  - Start with: install the opt-in adapter, run `/loopx <task>`, then `/loop`.

- **Manual shell / other agents**
  - Best when: you want LoopX state without a supported runtime bridge.
  - Start with:
    `curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash`,
    then `loopx doctor` and `loopx bootstrap`.

### Codex App

Best when you want a long-running or decentralized multi-agent workflow without
hand-writing scheduler prompts. Paste this in the current project thread:

```text
Connect the current project to LoopX.
Do not clone the LoopX repository for ordinary use. If `loopx` is not on PATH,
install or repair it with the official no-clone installer:
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"

Then run `loopx doctor`. Work only from the current project root: if LoopX state
already exists, reuse it and do not create or overwrite a goal; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
goal state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. If this is Codex App, set the heartbeat automation to start at 3 minutes.
Automatically refresh it from the LoopX generated task body; do not ask me to
manually run `heartbeat-prompt`. Then stop and report the project connection
status, current user gate, top agent todo, and next safe action.
```

Then start a real E2E exploration in normal language:

```text
/loopx Explore an LLM semantic rerank slice for a recommendation or search
system: build an offline eval set, implement a minimal candidate -> semantic
feature -> rerank -> eval path, add trace/cache/fallback/cost guardrails,
compare baseline vs treatment, and stop for production traffic, private data,
credentials, or AB/canary gates.
```

LoopX will plan before writing state, then create ordered P0/P1/P2 todos that
make the algorithm, infra, validation, and human gates visible.

<details>
<summary>Example visible todos</summary>

```text
[P0] Build the offline eval set: samples, labels, baseline, metrics, leakage check.
[P0] Implement the vertical slice: candidate input -> semantic feature -> rerank -> eval.
[P0] Add infra guardrails: trace schema, cache/fallback, rate limit, latency/cost budget.
[P0] Ask before production traffic, private data, credentials, or AB/canary decisions.
[P1] Compare baseline vs treatment with effect, cost, latency, and failure cases.
[P2] Write the promotion handoff: canary evidence, rollback plan, and next experiment.
```

</details>

After that, each tick reads `quota should-run`: if a user gate blocks the chosen
path, the agent asks a concrete question; if a safe fallback exists, it keeps
working; if nothing material changed, it backs off or quiet-stops instead of
spending compute forever. The agent may use `heartbeat-prompt --thin`
internally to wire Codex App, but users do not need to run that command in the
recommended path. After the 3-minute bootstrap cadence, Codex App cadence
should follow `quota should-run.scheduler_hint` for backoff and reset-to-initial
updates.

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
export PATH="$HOME/.local/bin:$PATH"

Then run `loopx doctor`. Work only from this project root: if LoopX state
already exists, reuse it and do not create or overwrite a goal; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
goal state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. Keep me in this TUI, do not use hidden headless
execution. Then stop and report the project connection status, current user
gate, top agent todo, and next safe action. After that I will start work with
`/loopx <complex task>`.
```

That one message is the install, connect, and status check. The first useful
TUI response should show the current goal, any concrete user gate, top todos,
and next safe action. Hidden `codex exec` is not the default bootstrap path.
Details for generated messages, later same-TUI automation, and proof capture
live in [Getting Started](docs/guides/getting-started.md).

A successful connection looks like this:

- `loopx doctor` passes;
- the project has `.loopx/registry.json`;
- the project has `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`;
- `loopx status` shows who should act next;
- local runtime state is ignored, not committed.

### Claude Code

LoopX runs on Claude Code as **native `/loop` + a LoopX control-plane MCP**: the
`/loop` runtime drives each tick and LoopX's `should_run` gates it. The adapter is
**opt-in** and never writes `~/.claude` unless you ask. Once enabled, drive it from
Claude Code with `/loopx <task>` then `/loop`. Opt-in install, scope choice, the
optional `--harden` gate, and uninstall are in
[loopx/claude_goal_mode/README.md](loopx/claude_goal_mode/README.md).

### Other Agents And Manual Shell

For Cursor, another terminal agent, or a manual shell, use the
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

### Advanced: Dynamic Workflow Scripts

For teams that already have their own agent runner, custom workflow runtime,
tool harness, or multi-agent scheduler, LoopX can be used as the control-plane
API inside that workflow. Your script or supervisor owns the executor loop;
LoopX owns the state contract:

```text
loopx quota should-run      # should any agent act now?
loopx todo claim/update     # who owns this slice, and what changed?
loopx refresh-state         # what evidence or blocker should the next turn see?
loopx quota spend-slot      # account for a completed automatic slice
```

This is the shape used by advanced showcases such as
[dynamic workflow orchestration](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html):
your agents can orchestrate external tools, devices, domain-specific runners,
or side agents, while LoopX keeps goals, gates, todos, evidence, quota, and
handoff state reviewable.

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
  and [dynamic workflow orchestration](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html):
  public-safe evidence that one control plane can coordinate primary agents,
  side agents, and external tools without hiding ownership or scope.

For more cases, open the [showcase catalog](docs/showcases/README.md). For a
full presenter material, see the experimental notes below.

### Experimental: Long-Running Agent App Paths

This is not replacing the first screen. It is an experimental entry point for
users who already understand the control-plane idea and want to pick one useful
LoopX capability today. Each path uses the same goal, todo, quota, evidence,
and review contract, so users can feel the capability lift without learning a
new control plane every time:

| App path | Start with | Expected output | User-visible lift |
| --- | --- | --- | --- |
| Issue / PR fix loop | `/loopx Fix <github-issue-or-pr-url>`<br>`loopx issue-fix workflow-plan` | Branch-ready fix packet with repro, smoke result, remaining review owner, and PR-review-ready evidence. | Review comments and issues become a closed loop instead of reminders humans must shepherd by hand. |
| PR-sized refactor loop | `/loopx <refactor goal>`<br>`loopx canary plan` | Reviewable slice list, validation notes, successor todo, and merge boundary. | More merged changes without turning the next morning into a giant diff audit. |
| Research or experiment loop | `loopx auto-research`<br>`loopx ml-experiment preview --format json` | Hypothesis, source/evidence packet, replay or experiment boundary, and next validated question. | Research becomes a resumable long-horizon loop, not just a one-off report. |
| Multi-agent work routing | `/loopx <goal text>`<br>`loopx quota should-run`<br>`loopx todo claim` | Claimed agent lanes with scope, lease, next action, quota decision, and handoff state. | Multiple agents can work in parallel without hiding ownership or stepping on the same todo. |
| Knowledge / workflow connector | `loopx connect`<br>`loopx lark-kanban`<br>`loopx value-connectors` | LoopX state projected into docs, boards, GitHub, or domain workflows while LoopX remains the source of truth. | Existing work surfaces become agent-aware without copying private state into public artifacts. |
| P0 blocked -> safe fallback | `loopx quota should-run`<br>`loopx todo claim` | Kernel projection of the exact user gate, safe fallback todo, quota decision, and evidence boundary inside an active goal. | Less idle agent time while preserving human judgment on the blocked path. |
| Candidate: Claude implements + Codex reviews | `/loopx <implementation goal>`<br>`loopx todo claim`<br>`loopx review-packet` | Role-scoped implementer todo, reviewer verdict, verifier command, evidence packet, and next handoff in one LoopX goal. | A [two-agent demo](docs/product/cross-runtime-impl-review-demo.md) can show collaboration without making either runtime the source of truth. |
| Candidate: PR conflict resolution | `/loopx Resolve merge conflicts for <github-pr-url>` | Conflict patch, semantic risk note, focused validation, and review handoff before merge. | Less mechanical conflict work after high-throughput agent branches, with humans still judging risky merges. |

Start the goal normally with `/loopx <goal text>`. The commands above are short
entry points, not separate state systems: each adapter still writes into the
same LoopX control-plane contract.

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

## Capability Surface

LoopX has grown beyond a single heartbeat helper. The useful mental model is a
small control-plane kernel plus adapters that project the same state into
agent, operator, and domain-specific surfaces.

| Surface | What it does | Start with |
| --- | --- | --- |
| Goal state and status | Tracks active state, todos, claims, gates, evidence, run history, and first-screen attention. | `loopx status`, `loopx diagnose`, `loopx review-packet` |
| Quota and interaction contract | Decides whether a turn should deliver, ask the user, wait for evidence, self-repair, or stay quiet. | `loopx quota should-run`, [quota allocation](docs/quota-allocation.md) |
| Agent runtime bridges | Keeps Codex App heartbeats, Codex CLI TUI loops, Claude Code `/loop`, and generic worker bridges aligned with the same guard. | `loopx heartbeat-prompt`, `loopx codex-cli-bootstrap-message`, `loopx worker-bridge` |
| Operator surfaces | Renders compact project status for humans without making the browser the source of truth. | `loopx serve-status`, [dashboard](apps/dashboard/README.md), [frontstage](https://huangruiteng.github.io/loopx/frontstage/) |
| External projections | Projects LoopX todos and gates into collaboration surfaces while LoopX remains the state authority. | `loopx lark-kanban`, [Lark Kanban adapter](docs/lark-kanban-control-plane-adapter.md) |
| Domain adapters | Packages repeatable work lanes such as issue fixing, content operations, value connector planning, ML experiment advice, and benchmark evidence. | `loopx issue-fix`, `loopx content-ops`, `loopx value-connectors`, `loopx ml-experiment`, `loopx benchmark` |
| Governance patterns | Captures recurring good/bad interaction shapes so new capabilities do not become one-off prompt branches. | [pattern catalog](docs/interaction-pattern-catalog.md), [state model](docs/state-interaction-model.md) |

Every surface should answer the same core questions: what is current, who owns
the next action, which decision is gated, what evidence changed, and whether
the next agent turn is allowed to spend compute.

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

After a project is connected, LoopX should feel like a small operator checklist,
not a second job. Start by asking your agent to diagnose the loop instead of
debugging the control plane by hand:

```text
Diagnose LoopX for this project end to end. Do not ask me to run shell
commands. Run loopx diagnose, tell me whether the project can
self-drive, what blocks it, the exact user/controller question if one exists,
and what you will do next.
```

For manual inspection, start with:

```bash
loopx status
loopx history --goal-id your-project-goal
loopx quota should-run --goal-id your-project-goal
```

Common operator actions:

```bash
loopx todo add --goal-id your-project-goal --role agent --text "Run the next bounded validation slice."
loopx review-packet --goal-id your-project-goal
loopx refresh-state --goal-id your-project-goal
```

Domain-specific helpers such as `issue-fix`, `content-ops`,
`value-connectors`, `ml-experiment`, `benchmark`, and `lark-kanban` are dry-run,
projection, or advisory lanes by default unless an explicit execute flag or
external permission is present.

Automatic turns should use the thin heartbeat prompt and treat quota as the
source of truth:

```bash
loopx quota should-run --goal-id your-project-goal
loopx heartbeat-prompt --thin --goal-id your-project-goal
loopx quota spend-slot --goal-id your-project-goal --slots 1 --source heartbeat --execute
```

The `next_automatic_turn` reported by `quota plan` is only an advisory
scheduling hint: it chooses the highest-compute eligible goal, while
operator-gated, focus-waiting, waiting, throttled, paused, and health-blocked
goals stay out of the eligible lane.

For stalled control-plane repair, `control_plane.self_repair.enabled=true` lets
`quota should-run` return a bounded `decision=self_repair` contract; missing
policy defaults off. When the payload includes a `gate_prompt` or
`operator_question`, the target heartbeat should proactively ask that concrete
user/controller gate and do not call the turn "no new user action" while they
remain open. Even after a bounded safe-bypass step, its report still has to
list existing open user todos. When `notify_user_on_open_todo=true`, skip
delivery work and quota spend for that blocker-push turn.

When `should_run=false` but `safe_bypass_allowed=true`, the heartbeat may still
do one bounded read-only steering or analysis step. See
`docs/quota-allocation.md` for the full allocation contract. After an automatic
turn actually spends delivery compute, append one spend event. Do not append
spend for quiet `should_run=false` skips, preflight failures, or pure dry-run
previews.

Three rules matter in daily use:

- surface concrete user gates instead of summarizing them as "waiting for
  owner";
- safe fallback work may continue, but it must not bypass the gate;
- append spend only after a validated writeback, not for quiet skips,
  preflights, or dry-run previews.

Optional surfaces such as the local dashboard, Lark Kanban, and domain helpers
should make the loop easier to inspect, but LoopX remains the source of truth:

```bash
loopx serve-status --global-registry --port 8766 --limit 80
cd ~/loopx/apps/dashboard && npm install && npm run dev
```

Before publishing public docs or examples, keep the public/private boundary
explicit:

```bash
loopx check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

More detail lives in [Getting Started](docs/guides/getting-started.md);
contracts live in [Status Data](docs/status-data-contract.md),
[Quota Allocation](docs/quota-allocation.md), and
[Public/Private Boundary](docs/public-private-boundary.md). For the local UI,
see the [dashboard guide](apps/dashboard/README.md).

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
- [Update notes](docs/update-notes/README.md): public-safe two-week progress
  notes, archive, and publication automation plan.
- [Release readiness](docs/product/release-readiness.md): v0.x install/update
  paths, compatibility smoke gate, release-note checklist, and safe-to-depend-on
  surfaces.
- [Architecture](docs/architecture.md): lifetime-goal invariant and core
  control-plane shape.
- [State interaction model](docs/state-interaction-model.md): actor boundaries,
  state stores, interaction contract, and writeback model.
- [Interaction pattern catalog](docs/interaction-pattern-catalog.md): reusable
  routing, gate, evidence, projection, and planning patterns.
- [Codex CLI packaged install](docs/product/codex-cli-packaged-install.md):
  no-clone install/update/start path for Codex CLI users.
- [Worker bridge install contract](docs/worker-bridge-install-contract.md):
  runner-agnostic bridge and edge-worker handoff model.
- [Lark Kanban adapter](docs/lark-kanban-control-plane-adapter.md):
  Feishu/Lark Base projection for todos, claims, gates, and evidence.
- [Integration guide](docs/integration.md): how to connect a project to LoopX
  state.
- [Heartbeat automation prompt](docs/heartbeat-automation-prompt.md) and
  [long-task cadence policy](docs/long-task-cadence-policy.md): recurring
  automation, scheduler backoff, and final-check/self-stop behavior.
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
operator gates, human reward, structured todos, scoped claims, quota-aware
heartbeats, read-only project maps, benchmark control-plane evidence, runtime
bridges, collaboration projections, and a small multi-project dashboard.

The next milestones are a clearer maintainer workflow for issue/PR loops,
stronger project and domain adapters, safer controller/sub-agent coordination,
better benchmark-runner ergonomics, and a more polished management surface that
maps kernel state into the five user questions above.

## Experimental

These surfaces are useful for demos and product iteration, but they are not the
main getting-started path yet.

### Review Agent Work

After a project is connected, LoopX can be used as a read-first management
surface before it is trusted with more control. The local dashboard helps you
inspect all connected projects, search todos, review user gates, compare agent
lanes, and follow evidence without reading raw logs.

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
