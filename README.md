<div align="center">

<img src="docs/assets/loopx-social-preview.png" alt="LoopX loop engineering social preview banner" width="480">

**Loop engineering for long-running AI agents and peer agent teams.**

<sub>A lightweight state kernel and agent-agnostic local control plane for
Codex, Claude Code, Cursor, and other runtimes: objectives, gates, todos,
quota, scheduler hints, evidence, and typed continuation in one reviewable loop.</sub>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/huangruiteng/loopx?display_name=tag)](https://github.com/huangruiteng/loopx/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Local first](https://img.shields.io/badge/control--plane-local--first-brightgreen.svg)](docs/public-private-boundary.md)
[![Loop Agents](https://img.shields.io/badge/status-loop%20agents%20early-orange.svg)](docs/product/release-readiness.md)

**把会干活的 Agent，接成可管理、可复盘、可持续改进的数字员工。**

</div>

---

LoopX is a lightweight state kernel and local control plane for loop engineering:
it keeps goals, todos, gates, quota, scheduler hints, evidence, and handoffs
stable while Codex, Claude Code, Cursor, or another runtime executes each
bounded turn. It does not replace your agent runtime; it makes long-running
agent work reviewable, restartable, and easier to hand off.

Registered agents are peers. Claims and leases, task boundaries, capabilities,
and typed continuation decide who acts next; no durable leader identity is
required.

Start with the agent runtime you already use and one useful loop. Safe presets
cover daily triage, changelog drafts, and PR watching. Advanced fixers are also
ready for public use, with explicit activation, isolated worktrees, verifier
checks, quota/cost limits, and human review. No optional capability is required
for the first run.

[Quick Start](#quick-start) · [User Manual](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg) · [How It Works](#how-it-works) · [See It In Action](#see-it-in-action) ·
[Hosted Frontstage](https://huangruiteng.github.io/loopx/frontstage/) · [Architecture](docs/architecture.md) ·
[简体中文](README.zh-CN.md)

<details>
<summary>More docs and project links</summary>

[Capability Surface](#capability-surface) · [Getting Started](docs/guides/getting-started.md) ·
[User Manual](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg) ·
[Showcases](docs/showcases/README.md) · [Release Readiness](docs/product/release-readiness.md) ·
[Update Notes](docs/update-notes/README.md) · [Community](#community--feedback) ·
[Product Vision](docs/product/vision.md) · [Dashboard](apps/presentation/dashboard/README.md)

</details>

> Keep the loop moving. Keep the judgment human.

## How It Works

Under the hood, LoopX keeps objectives, gates, todos, claims, scopes, evidence, run
history, quota, and human decisions in one compact layer. Product surfaces fold
those mechanics into five questions a user can act on: what is the objective, what
is next, what needs human judgment, what evidence changed, and whether the loop
can be handed back to the agent.

Short answer: LoopX is not another executor. Codex `/goal`, Codex App
automation, CLI scripts, cron jobs, or a human-visible TUI can trigger the next
executor loop; LoopX keeps the objective, gate, evidence, quota, and handoff contract
stable across those turns.

```text
objective / issue / project
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
| Task mode / automation / CLI scripts / TUI | Trigger or schedule the next executor loop. |
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

LoopX 把一次静态目标变成能持续流转的动态 loop：该等人的地方明确等人，
不该空等的安全侧路继续推进，下一轮 agent 总能读到目标、边界、证据和交接。

![LoopX control-plane board](docs/assets/control-plane-board.svg)

## Who Should Try It

LoopX is for people who already have an agent that can do useful work, and now
need that work to continue without turning into stale chat memory.

Start here if you are running:

- multi-day engineering, research, benchmark, or experiment objectives;
- issue/PR fixing loops where the agent must preserve scope, evidence, and
  review state across turns;
- recurring heartbeat or monitor-style agent work;
- projects with owner/SOP gates, human reward judgments, or public/private
  boundary checks;
- peer-agent teams where todo ownership, leases, and handoff matter;
- creator, research, or operations workflows where non-engineering users need
  agent progress translated into clear state, blockers, and feedback prompts.

LoopX is not an autonomous production controller. It is a local coordination
substrate: dangerous permissions, publishing, production writes, and final
ownership stay with the human/operator.

## Real Long-Running Loops

Open each visual to inspect the underlying graph or workspace, including
evidence branches and decisions preserved across agent turns.

**Open-source issue fix: PR delivery and reusable capability evolve together.**

<a href="docs/assets/openviking-issue-fix-explore.png">
  <img src="docs/assets/openviking-issue-fix-explore.png" alt="Open-source issue-fix Explore graph linking focused PR delivery with reusable LoopX capabilities">
</a>

LoopX's creator uses this path as an
[OpenViking contributor](https://github.com/volcengine/OpenViking/pulls?q=is%3Apr+author%3Ahuangruiteng)
for a recurring issue-to-PR fix loop. The
[Issue-Fix capability](docs/capabilities/issue-fix/README.md) keeps rolling
repository context, revision-stamped fix knowledge, and reviewer-facing
semantic preferences separate; current checkout source and tests remain
authoritative.

**Auto ML Experiment: hypotheses, matched evidence, invalid lineages, running
replicates, and promote/stop gates remain visible in one graph.**

<a href="docs/assets/auto-ml-experiment-explore.jpg">
  <img src="docs/assets/auto-ml-experiment-explore.jpg" alt="Auto ML Experiment Explore graph with experiment lineages, evidence gates, and promotion decisions" width="760">
</a>

**Auto Research: proposer, executor, and evaluator/promoter agents iterate in
parallel while todo, quota, evidence, and targeted wake remain visible.**

<a href="docs/assets/auto-research-multi-agent-showcase.png">
  <img src="docs/assets/auto-research-multi-agent-showcase.png" alt="Auto Research multi-agent workspace with proposer, executor, evaluator/promoter, todo, quota, evidence, and targeted wake activity">
</a>

## Quick Start

Requirements: Python 3.11+, `curl`, `tar`, macOS or Linux shell. Git is only
needed for contributor clone/canary workflows. The Python package has no
runtime dependencies outside the standard library.

Start agent-first: paste one setup message for the surface you already use,
then start real work through the LoopX command entry for that host.
Agents and host integrations can make this deterministic with
`loopx agent-onboard --list-agent-types`, then pass an exact runtime such as
`codex-app`, `codex-cli`, or `claude-code`. Ambiguous values such as `codex`
are intentionally rejected because Codex App automation and Codex CLI `/goal`
use different host-loop activation paths.

Choose your surface:

- **Codex App**: best for a long-running agent that can wake up, re-check gates,
  and keep moving. Paste the setup message below, then invoke `$loopx
  <complex task>` or choose `loopx` from `/skills`.
- **Codex CLI**: best when the visible TUI should stay in the foreground while
  LoopX keeps the state. Run `codex`, paste the setup message, then invoke `$loopx
  <complex task>` or choose `loopx` from `/skills`; after todos are written,
  LoopX must activate the visible `/goal <task_body>` loop or show the exact
  pasteable gate.
- **Claude Code**: best when Claude Code's native `/loop` should drive each tick.
  Install the opt-in adapter, run `/loopx <task>`, then `/loop`.
- **Manual shell / other agents**: best when you want LoopX state without a
  supported runtime bridge. Install from the no-clone installer, then run
  `loopx doctor` and `loopx bootstrap`.

Command registration is host-specific, but the state path is not. Codex
surfaces may expose LoopX through `$loopx` or `/skills` command facades before
native `/loopx` exists; Claude Code can expose `/loopx <task>` after its opt-in
adapter is installed. If a host command is missing, run `loopx slash-commands`
for the current catalog or start the same agent-safe path from a shell with
`loopx start-goal --guided --project . --goal-text "<task>"`. Host and plugin
integrations that need the lower-level handoff packet can still use
`loopx bootstrap-command-pack --project . --goal-text "<task>"`. Full routing and
recovery details live in [Getting Started](docs/guides/getting-started.md) and the
[host command registry contract](docs/reference/protocols/codex-app-host-command-registry-v0.md).

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
already exists, reuse it and do not create or overwrite a goal or the active objective; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
project state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. If this is Codex App, set the heartbeat automation to start at 3 minutes.
Automatically refresh it from the LoopX generated task body; do not ask me to
manually run `heartbeat-prompt`. Then stop and report the project connection
status, current user gate, top agent todo, and next safe action.
```

Then start a real E2E exploration in normal language:

```text
$loopx Explore an LLM semantic rerank slice for a recommendation or search
system: build an offline eval set, implement a minimal candidate -> semantic
feature -> rerank -> eval path, add trace/cache/fallback/cost guardrails,
compare baseline vs treatment, and stop for production traffic, private data,
credentials, or AB/canary gates.
```

LoopX will plan before writing state, then create ordered P0/P1/P2 todos that
make the algorithm, infra, validation, and human gates visible.

This Explore-style harness works best when the task has a measurable offline
eval, baseline, treatment, and guardrail metrics. It is not recommended for
open-ended tasks or scenarios where the evaluation metric cannot be quantified
reliably, because the loop depends on comparable metrics to decide whether an
exploration branch actually improved the result.

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

Best when the visible TUI should stay in the foreground. Open Codex CLI from
your project repo:

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
already exists, reuse it and do not create or overwrite a goal or the active objective; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
project state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. Keep me in this TUI, do not use hidden headless
execution. Then stop and report the project connection status, current user
gate, top agent todo, and next safe action. After that I will start work with
`$loopx <complex task>` or the `loopx` skill from `/skills`. When that task
writes LoopX todos, generate the thin task body and set this visible TUI to
`/goal <task_body>`; if you cannot mutate `/goal`, show me the exact text to
paste instead of saying the loop is active.
```

That one message is the install, connect, and status check. The first useful
TUI response should show the current objective, any concrete user gate, top todos,
and next safe action. Hidden `codex exec` is not the default bootstrap path.
Details for generated messages, later same-TUI automation, and proof capture
live in [Getting Started](docs/guides/getting-started.md).

A successful connection looks like this:

- `loopx doctor` passes;
- the project has `.loopx/registry.json`;
- the project has `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`;
- `loopx status` shows who should act next;
- Codex CLI has `/goal <task_body>` active, or the agent reported the exact
  pasteable gate for setting it;
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
as shell/CLI execution, a task command, an automation or heartbeat hook,
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
  --objective "Improve this project through bounded, verified segments." \
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
or peer agents, while LoopX keeps goals, gates, todos, evidence, quota, and
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

Want proof before reading the control-plane details? Start with the public
manual, then use the short proof surfaces:

- [User Manual (Feishu/Lark)](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg):
  the public onboarding manual with Quick Start, product concepts, technical
  concepts, FAQ, and selected real-world cases.
- [Hosted Frontstage](https://huangruiteng.github.io/loopx/frontstage/):
  the public showcase homepage with the canonical case cards.
- [Blocked P0 with safe P1/P2 rotation](docs/showcases/cases/0617-blocked-p0-safe-rotation.md):
  a reproducible synthetic demo where a human gate stays visible while safe
  fallback work continues.
- [LoopX self-iteration](docs/showcases/cases/0619-loopx-self-iteration.md)
  and [dynamic workflow orchestration](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html):
  public-safe evidence that one control plane can coordinate peer agents and
  external tools without hiding ownership or scope.

For more cases, open the [showcase catalog](docs/showcases/README.md). For a
full presentation, see the optional capabilities below.

## Optional Capabilities

These paths stay below the core onboarding path so the first run remains small.
Explore Graph and Explore Harness are supported opt-in features that remain
default-off. Auto Research and newer adapters are opt-in paths whose UX, safety
defaults, and evidence contracts continue to mature across more repositories.
None is required to start a useful loop.

The first useful loop requires no optional configuration. When a concrete task
would benefit from bounded child agents, Explore Graph, or Explore Harness,
inspect the goal's read-only catalog first:

```bash
loopx configure-goal --goal-id <goal-id>
```

The catalog reports current and default state, when each feature is useful,
what it does not authorize, and copyable preview/apply/disable/verify command
templates. Use `loopx configure-goal --help` for the complete settings surface.
Preview changes without `--execute`; do not enable a feature only because it is
available.

An applied `configure-goal` change also refreshes the registry-declared shared
read model. Without `--runtime-root`, LoopX resolves the authoritative shared
runtime from the goal's existing global `source_registry` route; an explicit
runtime override remains authoritative. JSON and Markdown responses name the
selected global registry and report exact goal-digest readback, so a project
runtime and its heartbeat runtime cannot silently diverge.

### Start With A Useful Loop

Use a preset to see LoopX's value before wiring up a full automation:

```bash
loopx doctor
loopx preset list
loopx preset show daily-triage
loopx start-goal --guided --project . --goal-text 'Run Daily Triage L1 for this repository: inspect LoopX status, active todos, open gates, stale signals, and next actions; write a compact report and ask before code edits or external writes.'
```

The preset output is read-only: it renders real `/loopx`, `start-goal`,
`quota should-run`, and `heartbeat-prompt` command packets without writing
project state, installing automation, editing docs, or opening PRs. When the
project is connected, `loopx ready-score --goal-id <goal-id> --agent-id
<agent-id>` gives a read-only readiness report for recurring loops.

Good first demos:

- **Daily Triage L1**: a safe project digest from status, todos, gates, and the
  single next action.
- **Changelog Draft L1**: a release-note draft grounded in merged work and PR
  links.
- **PR Watch L1**: review/CI/merge-blocker monitoring without auto-merge.
- **CI Sweeper L2** and **Dependency Sweeper L2**: high-value opt-in fix lanes
  that start with dry-run or policy reports before any bounded patch attempt.

### Auto Research One-Click Start

Auto research is the reference experimental preset for agent teams: the user
provides one open question, the preset supplies research roles and seed todos,
and the generic multi-agent kernel launches visible Codex CLI panes with
frontier, quota, evidence, and takeover controls.

```bash
loopx auto-research "How should we evaluate whether multi-agent auto research creates value?"
loopx auto-research start "How should we evaluate whether multi-agent auto research creates value?" --execute
```

The first command renders the contract and next launch packet. The `start`
command creates an isolated research frontier and launches the visible lanes;
lane-authored evidence still has to be written back through LoopX state before
the run can claim progress. See
[Auto-research command path](docs/guides/auto-research-command-path.md) for the
full stop, attach, retry, and evidence boundary.

### Explore Graph And Harness (Supported, Optional, Default-Off)

For longer investigations, LoopX provides a supported Explore Result Layer and
an opt-in Explore Harness. The result layer records public-safe
`node`/`edge`/`finding` events as an append-only exploration graph, then folds
them into summaries, blocked-frontier views, Mermaid graphs, and optional
operator sinks. The harness path reads that graph plus open todos and produces
read-only branch or worker-lane plans.

Board layout is independent from evidence truth: use `auto_flow` for generic
topologies and `semantic_lane_columns` for operator boards with meaningful
parallel lanes. Both render the same canonical Nodes, Edges, and Findings;
visual and Lark sinks remain opt-in. See the
[Explore presentation contract](docs/capabilities/explore/README.md#presentation-sink-lark-mapping).

```bash
loopx explore node --goal-id <goal-id> --title "Map the next frontier"
loopx explore finding --goal-id <goal-id> --title "Confirmed reusable contract" --node <node-id>
loopx explore summary --goal-id <goal-id>
loopx explore graph --goal-id <goal-id> --graph-format mermaid
loopx explore worker-branch-plan --goal-id <goal-id> --harness-profile generic
```

This is intentionally default-off. `todo-branch-plan` and
`worker-branch-plan` only become active when the registered goal opts in through
`spawn_policy.explore_harness.enabled=true`; even then they do not claim todos,
acquire leases, start workers, mutate state, or spend quota. They emit request
packets and suggested commands for a host runtime or human to execute through
the normal LoopX lifecycle. See the
[Explore capability guide](docs/capabilities/explore/README.md) for the event
model, per-goal gate, adaptive-resilient profile, and MoE router profile.

### Review Agent Work

Use the management surface as a read-first experimental entry after a project is
connected. It lets operators inspect connected projects, user gates, agent
lanes, todos, and evidence before granting more control.

```bash
loopx serve-status --global-registry --port 8766 --limit 80
cd apps/presentation/dashboard && npm run dev
```

This path is intentionally conservative: CLI state remains the source of truth,
browser writes require explicit local opt-in, and review signals stay separate
from execution permission. See the
[intelligent management surface](docs/product/intelligent-management-surface.md),
[project-level reward model](docs/product/project-level-reward-model.md), and
[3-minute demo script](docs/outreach/frontstage-demo-script.md).

### Long-Running Agent App Paths

This is not replacing the first screen. It is an experimental entry point for
users who already understand the control-plane idea and want to pick one useful
LoopX capability today. Each path uses the same objective, todo, quota, evidence,
and review contract, so users can feel the capability lift without learning a
new control plane every time:

| App path | Start with | Expected output | User-visible lift |
| --- | --- | --- | --- |
| [Issue / PR fix loop](docs/capabilities/issue-fix/README.md) | LoopX slash entry: `Fix <github-issue-or-pr-url>`<br>`loopx issue-fix workflow-plan` | Branch-ready fix packet with repro, smoke result, explainable reviewer recommendation, and PR-lifecycle evidence. | Review comments and issues become a monitored closed loop instead of reminders humans must shepherd by hand. |
| PR-sized refactor loop | LoopX slash entry: `<refactor task>`<br>`loopx canary plan` | Reviewable slice list, validation notes, successor todo, and merge boundary. | More merged changes without turning the next morning into a giant diff audit. |
| Research or experiment loop | `loopx auto-research start "<open question>" --execute`<br>`loopx ml-experiment preview --format json` | Hypothesis, source/evidence packet, replay or experiment boundary, and next validated question. | Research becomes a resumable long-horizon loop, not just a one-off report. |
| Explore result / harness loop | `loopx explore node\|edge\|finding`<br>`loopx explore worker-branch-plan --goal-id <id>` | Public-safe exploration graph, blocked frontier, Mermaid/exportable projection, and default-off worker branch plan. | Long-running exploration becomes inspectable topology and opt-in worker planning instead of hidden notes. |
| Multi-agent work routing | LoopX slash entry: `<task text>`<br>`loopx quota should-run`<br>`loopx todo claim` | Claimed agent lanes with scope, lease, next action, quota decision, and handoff state. | Multiple agents can work in parallel without hiding ownership or stepping on the same todo. |
| Knowledge / workflow connector | `loopx connect`<br>`loopx lark-kanban`<br>`loopx value-connectors` | LoopX state projected into docs, boards, GitHub, or domain workflows while LoopX remains the source of truth. | Existing work surfaces become agent-aware without copying private state into public artifacts. |
| P0 blocked -> safe fallback | `loopx quota should-run`<br>`loopx todo claim` | Kernel projection of the exact user gate, safe fallback todo, quota decision, and evidence boundary inside an active project loop. | Less idle agent time while preserving human judgment on the blocked path. |
| Candidate: Claude implements + Codex reviews | LoopX slash entry: `<implementation task>`<br>`loopx todo claim`<br>`loopx review-packet` | Role-scoped implementer todo, reviewer verdict, verifier command, evidence packet, and next handoff in one LoopX state thread. | A [two-agent demo](docs/product/cross-runtime-impl-review-demo.md) can show collaboration without making either runtime the source of truth. |
| Candidate: PR conflict resolution | LoopX slash entry: `Resolve merge conflicts for <github-pr-url>` | Conflict patch, semantic risk note, focused validation, and review handoff before merge. | Less mechanical conflict work after high-throughput agent branches, with humans still judging risky merges. |

Start through the host's LoopX slash-command entry point: `$loopx` or `/skills`
in current Codex surfaces, `/loopx` where a host exposes native slash commands.
The commands above are short entry points, not separate state systems: each
adapter still writes into the same LoopX control-plane contract.

## User Mental Model

LoopX has more kernel concepts than a user should have to think about every
day. The product surface should collapse them into five questions:

| User question | Kernel objects behind it | What the user should see |
| --- | --- | --- |
| Objective | objective state, scope | What are we trying to move, and what is out of bounds? |
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
work. Once the objective changes, the user gives feedback, an owner gate appears, or
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

- **Lifetime goals**: durable project intentions that outlive one chat
  thread, run, todo, or implementation plan. A lifetime goal does not
  grant open-ended autonomy: only the next bounded transition is executable.
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
| Operator surfaces | Renders compact project status for humans without making the browser the source of truth. | `loopx serve-status`, [dashboard](apps/presentation/dashboard/README.md), [frontstage](https://huangruiteng.github.io/loopx/frontstage/) |
| External projections | Projects LoopX todos and gates into collaboration surfaces while LoopX remains the state authority. | `loopx lark-kanban`, [Lark Kanban adapter](docs/lark-kanban-control-plane-adapter.md) |
| Domain adapters | Packages repeatable work lanes such as issue fixing, content operations, value connector planning, ML experiment advice, and benchmark evidence. | `loopx issue-fix`, `loopx content-ops`, `loopx value-connectors`, `loopx ml-experiment`, `loopx benchmark` |
| Experimental context learning | Lets named registered agents trial provider-neutral Reward Memory with an ignored project config. Config v1 binds one provider once, assigns explicit compatible corpus sets to module-owned surfaces, and exposes default-off automatic ingest/recall hooks. Agent-scoped quota and status read the same authoritative config as `experiment-status` and expose a path-free config/runtime route receipt. Hooks run only at wired module boundaries, preserve bounded queries, exact readback, receipts, and fail-open base output; they do not capture raw streams or create a background router. Issue Fix currently wires `reviewer_artifact.summary` for reviewer-facing Chinese summaries and `reviewer_notification.before_send` for a structured, verified delivery-policy decision immediately before a configured secondary send. The runtime accepts v1 only; migrate local ignored configs explicitly. OpenViking is one provider option, not a global dependency. | `loopx configure-goal --reward-memory-config ... --reward-memory-agent ...`, `loopx reward-memory experiment-status`, [architecture](docs/reference/protocols/reward-memory-architecture-v0.md) |
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
- For Chinese-speaking users and contributors, use the Lark developer group for
  onboarding help, feedback, implementation questions, and contributor
  coordination. To join the WeChat group, add `huangrt00` and include `LoopX`
  in the friend request; you will be invited after it is accepted.

<table>
  <tr>
    <td align="center" width="280">
      <img src="docs/assets/loopx-lark-developer-group.png" alt="LoopX Lark developer group QR code" width="240"><br>
      Lark developer group
    </td>
    <td align="center" width="280">
      <img src="docs/assets/loopx-wechat-contact.png" alt="LoopX WeChat contact QR code" width="240"><br>
      WeChat: <code>huangrt00</code><br>
      Add as a friend and mention LoopX for a group invitation
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
self-drive, what blocks it, the exact user/operator question if one exists,
and what you will do next.
```

For manual inspection, start with:

```bash
loopx status
loopx history --goal-id your-project-goal
loopx quota should-run --goal-id your-project-goal
```

Quota/monitor artifacts and generic history appenders use an atomic JSON
reservation so concurrent writers cannot claim the same JSON/Markdown pair.
Legacy index identity collisions are never auto-deleted: preview an exact
rebuild plan, review its rows and digest, then explicitly supply that plan to
preserve every compact todo/target event under a distinct recovery artifact:

```bash
loopx --format json history rebuild-index-collisions \
  --goal-id your-project-goal | jq '.review_plan' > reviewed-plan.json
loopx history rebuild-index-collisions --goal-id your-project-goal \
  --review-plan-json reviewed-plan.json --execute
```

The execute path keeps a pre-rebuild index backup and does not claim that an
ambiguous legacy artifact belongs to any recovered row. A truncated plan is
not executable; increase `--limit` and review the complete digest first.

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

For shared-control-plane or agent-team goals, generate the automation with a
registered identity, for example
`loopx heartbeat-prompt --thin --goal-id your-project-goal --agent-id codex-research --agent-scope "peer task claims and bounded delivery"`.
After `configure-goal` or the control-plane UI changes `registered_agents`, use
the returned `heartbeat_prompt_migration` commands to refresh installed Codex
App automation bodies. A v0.1 hierarchy upgrade instead appears once as a
blocking `automation_prompt_upgrade` with a stable migration id: update the
host automation idempotently, then run its completion command. Repeating that
completion acknowledgement is a no-op. Scheduler cadence updates
should run `scheduler_hint.codex_app.ack_hint.cli_args`; current payloads use
`quota scheduler-ack-current`, which re-reads the latest hint instead of making
agents copy short-lived reset tokens.

The `next_automatic_turn` reported by `quota plan` is only an advisory
scheduling hint: it chooses the highest-compute eligible goal, while
operator-gated, focus-waiting, waiting, throttled, paused, and health-blocked
goals stay out of the eligible lane.

For stalled control-plane repair, `control_plane.self_repair.enabled=true` lets
`quota should-run` return a bounded `decision=self_repair` contract; missing
policy defaults off. When the payload includes a `gate_prompt` or
`operator_question`, the target heartbeat should proactively ask that concrete
user/operator gate and do not call the turn "no new user action" while they
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
cd ~/loopx/apps/presentation/dashboard && npm install && npm run dev
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
see the [dashboard guide](apps/presentation/dashboard/README.md).

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
- [User manual](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg):
  public Feishu/Lark onboarding guide with Quick Start, concepts, FAQ, and
  selected cases.
- [Documentation index](docs/README.md): stable docs grouped by audience.
- [Control-plane developer course](docs/development/control-plane-course/README.md):
  nine Chinese, code-led lectures covering the real CLI path, state kernel,
  quota, scheduler, evidence, rule changes, layered quality gates, and optional
  extensions.
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
- [Project governance](GOVERNANCE.md), [authors and contributors](AUTHORS.md),
  [project history](docs/project/history.md), and [name and marks](TRADEMARKS.md):
  maintainer authority, attribution, public milestones, and identity guidance.

## Contributing

External contributors should start with
[CONTRIBUTOR_TASKS.md](CONTRIBUTOR_TASKS.md) for public, claimable work and
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, and boundary rules.
Project roles and public history are recorded in [GOVERNANCE.md](GOVERNANCE.md),
[AUTHORS.md](AUTHORS.md), and [docs/project/history.md](docs/project/history.md).

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

The current v0.2.x milestone is a useful local substrate for goal state, run
history, operator gates, structured todos, peer claims and leases, quota-aware
host loops, evidence-backed Issue-Fix outcomes, supported default-off Explore
Graph and Harness, runtime and collaboration projections, and a read-first
multi-project dashboard.

The next milestones are simpler host packaging, stronger terminal acceptance
across repeated public issue-fix and research loops, measured knowledge and
reward usefulness across independent tasks, better benchmark-runner ergonomics,
and a more polished management surface around the five user questions above.

## License

MIT. See [LICENSE](LICENSE).
