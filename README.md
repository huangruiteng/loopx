# Goal Harness

**Always-on agent teams, governed by human judgment.**

**Gate-aware human-in-the-loop control plane**

**Dynamic goal control plane for long-running agents**

**让多个 agent 昼夜接力，把人的判断留在控制面。**

Goal Harness 把目标、用户决策、agent todo、认领关系、scope、safe fallback、
run history 和 quota 放进同一层状态：该等人的地方明确等人，不该空等的
安全侧路继续推进。

Goal Harness is a local control plane for long-running AI agent projects. It
turns a static agent goal into a dynamic, reviewable state layer: goals, gates,
todos, claims, scopes, run history, quota, evidence, and human decisions stay
visible across many turns, so primary and side agents can keep working on safe
lanes while gated work waits for the person.

[Quick Start](#quick-start) · [Getting Started](docs/guides/getting-started.md) ·
[Showcases](docs/showcases/README.md) · [Hosted Frontstage](https://huangruiteng.github.io/goal-harness/frontstage/) ·
[Community](#community--feedback) · [Product Vision](docs/product/vision.md) · [Architecture](docs/architecture.md) ·
[Dashboard](apps/dashboard/README.md) · [简体中文](README.zh-CN.md)

> Your agents keep the night shift. You keep the judgment.

## What Is It?

Goal Harness does not replace Codex, Claude Code, Cursor, or another agent
runtime. It sits above them and gives humans and agents a shared state layer for
long-running work.

Short answer: Goal Harness is not replacing Codex goal mode. Codex goal,
Codex App automation, and CLI scripts can trigger executor loops; Goal Harness
preserves the dynamic goal state those loops need to keep working across
turns.

| Layer | Role |
| --- | --- |
| Codex / Claude Code / Cursor | Execute an agent loop: read, write, run commands, and respond. |
| Codex goal / automation / CLI scripts | Trigger or schedule the next executor loop. |
| Goal Harness | Preserve the dynamic goal state: gates, todos, run history, quota, evidence, boundaries, and handoff state. |

The product promise is not "more todo lists." It is a better
human-in-the-loop control surface: keep human judgment at high-value decision
points, keep safe fallback work moving when one lane is gated, and stop compute
spend when a turn cannot produce a verified transition.

Put differently: Goal Harness lets a user's agent team keep working across
tools, turns, and off-hours without losing the goal boundary. The technical
contract underneath that promise is explicit: agent identity, todo ownership,
scope, capability gates, quota, evidence writeback, and public/private
boundaries stay visible to the next turn.

![Goal Harness control-plane board](docs/assets/control-plane-board.svg)

## See It In Action

| Case | What It Shows | Public Surface |
| --- | --- | --- |
| [Blocked P0 with safe P1/P2 rotation](docs/showcases/cases/0617-blocked-p0-safe-rotation.md) | A user-gated high-priority lane stays visible while safe fallback work continues. | Reproducible synthetic demo |
| [Goal Harness self-iteration loop](docs/showcases/cases/0619-goal-harness-self-iteration.md) | A side agent improved Goal Harness itself while the primary agent stayed focused on benchmark work. | Commit-backed public evidence case |
| [Dynamic workflow for hardware-agent development](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.md) | A fuzzy multi-agent engineering workflow can converge through one shared control plane. | Redacted public-safe stub |

Start with the [showcase catalog](docs/showcases/README.md): public-safe
cases that show where Goal Harness helps, with reproducible demos where the
evidence allows.

Open the [hosted frontstage](https://huangruiteng.github.io/goal-harness/frontstage/)
for the product-facing view: case cards, narrative motion, efficiency evidence,
and public/private boundary notes rendered from `docs/showcases/`. Live registry
or local status projections are separate ops-mode surfaces, not public demo
content.

<table>
  <tr>
    <td width="62%">
      <img src="docs/assets/frontstage-showcase-first-screen.png" alt="Hosted Goal Harness frontstage showing public-safe showcase cases">
    </td>
    <td width="38%">
      <strong>From AI assist to async agent work.</strong><br><br>
      Traditional AI-assisted development speeds up the active coding session.
      Goal Harness changes the operating model: humans set gates, scope, and
      evidence, while primary and side agents keep safe lanes moving across
      turns and off-hours.<br><br>
      <strong>从“人带着 AI 写代码”，到“agent 团队异步接力”。</strong><br>
      人在关键判断处掌舵，agent 在可验证边界内持续推进。
    </td>
  </tr>
</table>

## Why It Matters

Short agent tasks usually fail because the model makes a bad local choice.
Long-running agent work fails differently: state drifts.

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

Goal Harness makes those questions machine-readable enough for agents and
legible enough for operators.

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
- **Public/private boundary checks**: local scans and docs rules to keep raw
  private state, credentials, logs, traces, and benchmark material out of
  public artifacts.

## Good Fits

Use Goal Harness when agent work spans time, people, projects, or safety
boundaries:

- multi-day or multi-week engineering and research goals;
- recurring heartbeat or monitor-style agent turns;
- benchmark and experiment loops that must wait for evidence;
- projects with owner/SOP gates or human reward judgments;
- controller agents that spawn scoped side agents;
- creator, research, or operations workflows where non-engineering users need
  agent progress translated into clear state, blockers, and feedback prompts;
- public/private boundary checks before publishing artifacts;
- local dashboards that should foreground user decisions before raw logs.

Do not use Goal Harness as an autonomous production controller. It is a local
coordination substrate; project ownership and dangerous permissions stay with
the human/operator.

## Quick Start

Requirements: Python 3.11+, `curl`, `tar`, macOS or Linux shell. Git is only
needed for contributor clone/canary workflows. The Python package has no
runtime dependencies outside the standard library.

The recommended start is agent-first: ask the agent you already use to install,
connect, diagnose, and show the next safe action before doing longer work.

### Codex App

Use this when you are working in Codex App or a Codex App heartbeat-capable
thread. Paste from the project repo:

```text
Install and connect Goal Harness for this project end to end. Do not stop at a
plan. If `goal-harness` is missing, install it with the official no-clone
GitHub installer. Then run doctor, connect or bootstrap this repo, ensure local
Goal Harness state is ignored, and report the goal id, current user gate, top
agent todo, and next safe action before longer work.
```

Success looks like this for every surface:

- `goal-harness doctor` passes;
- the project has `.goal-harness/registry.json`;
- the project has `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`;
- `goal-harness status` shows who should act next;
- local runtime state is ignored, not committed.

For recurring Codex App automation, generate the heartbeat body after the
project is connected:

```bash
goal-harness heartbeat-prompt --thin --goal-id <goal-id> --agent-id <agent-id> --agent-scope "<scope>"
```

### Codex CLI

Use this when you want the human-visible TUI to stay primary. Open Codex CLI
from your project repo and paste one message:

```text
Start Goal Harness for this repo. If `goal-harness` is missing, install it with
the official no-clone GitHub installer, then connect this project. Show me the
current goal, concrete user gate if any, top todos, and next safe action before
running longer work. Keep me in this Codex CLI TUI unless I explicitly accept a
headless fallback. After I paste this, begin the Goal Harness loop; do not stop
after only explaining what Goal Harness is.
```

The first useful response should show the current goal, user gate, top todos,
and next safe action. If the guard permits work, the same visible TUI turn can
claim or choose one runnable agent todo and complete one bounded validated
segment.

After Goal Harness is installed, generate a stricter exact TUI paste block:

```bash
goal-harness codex-cli-bootstrap-message --project . --goal-id <goal-id>
```

For only the pasteable text:

```bash
goal-harness codex-cli-bootstrap-message --project . --goal-id <goal-id> --message-only
```

Headless `codex exec` is an explicit fallback, not the default experience.
Pilot packets, local drivers, idle detection, and same-session proof details
live in [Getting Started](docs/guides/getting-started.md) and the
[Codex CLI TUI-first loop](docs/product/codex-cli-tui-loop.md).

### Other Agents And Manual Shell

For Claude Code, Cursor, another terminal agent, or a manual shell, use the
same no-clone installer:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/goal-harness/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
goal-harness doctor
```

Then ask the agent to connect or run the command yourself:

```bash
cd /path/to/your-project
goal-harness bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

Clone-based install is only for contributors who want the live canary wrapper:

```bash
git clone https://github.com/huangruiteng/goal-harness ~/goal-harness
~/goal-harness/scripts/install-local.sh
goal-harness doctor
```

For the full install, diagnose, connect, heartbeat, dashboard, development, and
command-reference workflow, read
[docs/guides/getting-started.md](docs/guides/getting-started.md).

## Community & Feedback

Goal Harness is still early. The most useful feedback comes from real
long-running agent projects: where the control plane helped, where it felt
heavy, and which user gates or handoffs still disappeared from view.

- Use [GitHub Issues](https://github.com/huangruiteng/goal-harness/issues) for
  reproducible bugs, install problems, and feature requests.
- Open PRs for docs fixes, showcase writeups, and small public-safe examples.
- For Chinese-speaking early users, scan the Lark group first for fast
  onboarding help, feedback loops, and showcase co-creation. A WeChat group QR
  is available as a backup, but QR codes may expire; if one is stale, use Lark
  or open an issue to ask for a refresh.

<table>
  <tr>
    <td align="center" width="240">
      <img src="docs/assets/goal-harness-lark-user-group.png" alt="Goal Harness Lark user group QR code" width="200"><br>
      Lark group
    </td>
    <td align="center" width="240">
      <img src="docs/assets/goal-harness-wechat-user-group.png" alt="Goal Harness WeChat user group QR code" width="200"><br>
      WeChat group, may expire
    </td>
  </tr>
</table>

## Core Workflows

After a project is connected, the daily loop is intentionally small:

```bash
goal-harness status
goal-harness history --goal-id your-project-goal
goal-harness quota should-run --goal-id your-project-goal
```

Users should not need to diagnose Goal Harness by hand. Ask your agent to run
the diagnostic packet and reason from it:

```text
Diagnose Goal Harness for this project end to end. Do not ask me to run shell
commands. Run goal-harness diagnose, tell me whether the project can
self-drive, what blocks it, the exact user/controller question if one exists,
and what you will do next.
```

Common operator actions:

```bash
goal-harness todo add --goal-id your-project-goal --role agent --text "Run the next bounded validation slice."
goal-harness review-packet --goal-id your-project-goal
goal-harness refresh-state --goal-id your-project-goal
```

Automatic turns should check quota before work and spend exactly once after
validated writeback:

```bash
goal-harness quota should-run --goal-id your-project-goal
goal-harness heartbeat-prompt --thin --goal-id your-project-goal
goal-harness quota spend-slot --goal-id your-project-goal --slots 1 --source heartbeat --execute
```

The dashboard is optional and local:

```bash
goal-harness serve-status --global-registry --port 8766 --limit 80
cd ~/goal-harness/apps/dashboard && npm install && npm run dev
```

Before publishing docs or examples, keep the public/private boundary explicit:

```bash
goal-harness check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

More detail lives in [Getting Started](docs/guides/getting-started.md);
contracts live in [Status Data](docs/status-data-contract.md),
[Quota Allocation](docs/quota-allocation.md), and
[Public/Private Boundary](docs/public-private-boundary.md).

## Product Vision

Goal Harness starts with AI coding, research, and benchmark loops because those
workflows make state drift easy to see. The broader product direction is a
dynamic goal control plane for any long-running agent work where humans need
clear progress, gates, feedback, and recovery without reading raw logs.

One medium-term productization case is a creator-operator workflow: a
non-engineering user asks an agent to track social-platform trends, map them to
personal creative preferences, extract insights, draft content, and maintain a
material library. The bottleneck is not only model capability. The product has
to translate agent work into a friendly first screen: what happened, what is
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
  Harness.
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

Goal Harness keeps local active goal state separate from the public repository:
do not commit `.goal-harness/`, `.codex/goals/`, live
`ACTIVE_GOAL_STATE.md`, raw benchmark traces, or private operator artifacts.

Before publishing docs or examples, run:

```bash
goal-harness check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

## Current Status

Goal Harness is early. It is not a full agent platform and not an autonomous
production controller.

The current milestone is a useful local substrate for goal state, run history,
operator gates, human reward, structured todos, quota-aware heartbeats,
read-only project maps, benchmark control-plane evidence, and a small
multi-project dashboard.

The next milestones are stronger project adapters, safer controller/sub-agent
coordination, better benchmark-runner ergonomics, a more polished operator
view, and creator/operator showcases that make the same control-plane value
legible beyond software engineering.

## License

MIT. See [LICENSE](LICENSE).
