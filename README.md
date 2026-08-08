<div align="center">

<h1 align="center">LoopX</h1>

<img src="docs/assets/loopx-social-preview.png" alt="LoopX loop engineering social preview banner" width="560">

**The local control plane for long-running AI agent work.**

<sub>Keep objectives, gates, todos, evidence, quota, and handoffs stable while Codex, Claude Code, Cursor, or your own runtime executes bounded turns.</sub>

<a href="https://trendshift.io/repositories/102379?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-102379"><img src="https://trendshift.io/api/badge/repositories/102379" alt="huangruiteng/loopx on Trendshift" width="220" height="48"></a>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Release](https://img.shields.io/github/v/release/huangruiteng/loopx?display_name=tag)](https://github.com/huangruiteng/loopx/releases/latest) [![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/XmGgQyCFZd) [![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml) [![Local first](https://img.shields.io/badge/control--plane-local--first-brightgreen.svg)](docs/public-private-boundary.md) [![Loop Agents](https://img.shields.io/badge/status-loop%20agents%20early-orange.svg)](docs/product/release-readiness.md)

[Public website](https://huangruiteng.github.io/loopx/) · [Docs](https://huangruiteng.github.io/loopx/docs/) · [Try LoopX](#try-loopx) · [See real loops](#evidence) · [How it works](#why-loopx) · [User manual](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg) · [简体中文](README.zh-CN.md)

**把会干活的 Agent，接成可管理、可复盘、可持续改进的数字员工。**

</div>

---

A lightweight state kernel and agent-agnostic local control plane for loop
engineering, LoopX keeps long-running work reviewable, restartable, and easier
to hand off across turns, tools, and agents. It does not replace your agent
runtime.

**Loop engineering for long-running AI agents and peer agent teams.**

> Keep the loop moving. Keep the judgment human.

<a id="how-it-works"></a>

## Why LoopX

An agent can finish a task in one session. Long-running work is harder:
objectives change, owner decisions appear, evidence goes stale, agents hand work
to peers, and a scheduler can keep spending after no useful transition remains.
Chat memory and a timer are not enough to govern that.

LoopX keeps the durable control state in one compact layer:

```text
objective / issue / project
   │
   ▼
LoopX state: objective + gates + todos + scope + evidence + quota
   │
   ├─ human judgment needed? ── yes ─▶ ask a concrete question and wait
   │
   ├─ safe fallback available? ──────▶ run one bounded agent slice
   │
   ▼
Codex / Claude Code / Cursor / shell agent executes one turn
   │
   ▼
write evidence + handoff + next todo ─▶ quota decides the next tick
```

![LoopX control-plane board](docs/assets/control-plane-board.svg)

A useful mental model is an
**[agent-native Kanban for long-running work](docs/development/control-plane-course/00-concept-primer.md)**.
Cards carry identity, authority, evidence, and continuation. Moves are validated
operators such as claim, gate, monitor, and writeback. The board is a
projection; LoopX state remains the source of truth.

Registered agents are peers. Claims, leases, task boundaries, capabilities, and
typed continuation decide who acts next; no durable leader identity is
required.

LoopX is useful when you run:

- multi-day engineering, research, benchmark, or experiment objectives;
- issue and PR loops that must preserve scope, evidence, and review state;
- recurring heartbeat or monitor work;
- projects with owner, safety, publication, or private-data gates;
- peer-agent teams where ownership, leases, and handoff matter;
- creator, research, or operations workflows whose progress must remain
  legible to a non-engineering operator.

LoopX is not an autonomous production controller. Dangerous permissions,
publishing, production writes, and final ownership stay with the human.

<a id="see-it-in-action"></a>

## Evidence

These are not one-turn demos. The OpenViking Issue-Fix and Auto ML trajectories
each span **200+ hours of elapsed loop lifetime** across many bounded turns,
decisions, and evidence updates. Elapsed lifetime is wall-clock project time,
not 200 hours of continuous model execution or a claim of unattended
production autonomy. Open each visual to inspect the public-safe graph,
evidence branches, and decisions preserved across turns.

### Open-Source Issue Fix

**200+ hour public contribution arc: PR delivery and reusable fix knowledge
evolve together.**

<a href="docs/assets/long-running-loop-openviking-trajectory.png">
  <img src="docs/assets/long-running-loop-openviking-trajectory.png" alt="Open-source issue-fix trajectory linking focused PR delivery with reusable LoopX capabilities" width="420">
</a>

LoopX's creator uses this path as an
[OpenViking contributor](https://github.com/volcengine/OpenViking/pulls?q=is%3Apr+author%3Ahuangruiteng).
The represented public contribution sequence spans more than 200 elapsed hours
from its first PR creation to the latest represented review or update. The
[Issue-Fix capability](docs/capabilities/issue-fix/README.md) keeps rolling
repository context, revision-stamped fix knowledge, and reviewer-facing
preferences separate; linked PRs plus current checkout source and tests remain
authoritative.

### Auto ML Experiment

**200+ hour owner-run experiment arc: hypotheses, matched evidence, invalid
lineages, running replicates, and promote/stop gates remain visible in one
graph.**

<a href="docs/assets/long-running-loop-ml-experiment-trajectory.png">
  <img src="docs/assets/long-running-loop-ml-experiment-trajectory.png" alt="Auto ML Experiment trajectory with experiment lineages, evidence gates, and promotion decisions" width="760">
</a>

The redacted public-safe graph preserves decision lineage across that 200+ hour
elapsed window. It is trajectory evidence, not a claim of continuous compute,
independent reproduction, or a production result.

### Auto Research

**Proposer, executor, and evaluator/promoter agents iterate in parallel while
todo, quota, evidence, and targeted wake remain visible.**

<a href="docs/assets/auto-research-multi-agent-showcase.png">
  <img src="docs/assets/auto-research-multi-agent-showcase.png" alt="Auto Research multi-agent workspace with proposer, executor, evaluator/promoter, todo, quota, evidence, and targeted wake activity">
</a>

More inspectable surfaces:

- the [public homepage](https://huangruiteng.github.io/loopx/) for the product
  narrative, quick start, and long-running evidence;
- the [showcase catalog](docs/showcases/README.md), including
  [blocked-P0 safe rotation](docs/showcases/cases/0617-blocked-p0-safe-rotation.md),
  [LoopX self-iteration](docs/showcases/cases/0619-loopx-self-iteration.md), and
  [dynamic workflow orchestration](docs/showcases/cases/0619-dynamic-workflow-hardware-agent.html);
- the [cross-runtime implementation review demo](docs/product/use-cases/cross-runtime/cross-runtime-impl-review-demo.md);
- the public [user manual](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg).

<a id="quick-start"></a>

## Try LoopX

Requirements: Python 3.11+, `curl`, `tar`, and a macOS or Linux shell. Git is
only needed for contributor clone/canary workflows. The Python package has no
runtime dependencies outside the standard library.

Install without cloning:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

Then connect from your project root:

```bash
cd /path/to/your-project
loopx connect
loopx status
```

If the project has not been initialized and `connect` tells you state is
missing, use the guided path:

```bash
loopx start-goal --guided --project . --goal-text "Your long-running objective"
```

LoopX should reuse existing state rather than overwrite it. Keep `.loopx/`,
`.codex/goals/`, and `.local/` ignored.

### Start From Your Agent

| Host | Recommended start | Loop driver |
| --- | --- | --- |
| Codex App | Ask the agent to connect this project to LoopX, run `loopx doctor`, preserve existing state, and report the current gate and next todo. Then use `$loopx <complex task>` or choose `loopx` from `/skills`. | Codex App heartbeat automation, refreshed from `quota should-run.scheduler_hint` |
| Codex App over SSH | `loopx agent-onboard --agent-type codex-app-ssh --project .` | The returned visible `/goal <task_body>` |
| Codex CLI | Start `codex` in the project, ask it to connect and diagnose LoopX, then use `$loopx <complex task>` or `/skills`. | Visible `/goal <task_body>`; no hidden headless execution by default |
| Claude Code | Install the opt-in adapter, then run `/loopx <task>` followed by `/loop`. | Native Claude Code `/loop` gated by LoopX |
| OpenCode | Install the static command facade; opt in to `--with-goal-bridge` for recurring goals. | OpenCode command facade and explicit goal bridge |
| Pi | Install the opt-in goal extension with `loopx slash-commands --install --surface pi`, then use `/loopx <task>` from a trusted Pi session. | Visible Pi goal extension gated by LoopX quota (`loopx_goal_activate` + `agent_settled` continuation) |
| Cursor, shell, or custom runner | Use the installer and `loopx doctor`; connect manually or call LoopX from your runner. | Your shell, scheduler, or runner |

The exact, copy-ready setup messages and host recovery paths live in
[Getting Started](docs/guides/getting-started.md). Host integrations can inspect
the [Codex App host command registry contract](docs/reference/protocols/codex-app-host-command-registry-v0.md),
the [Codex CLI packaged install path](docs/product/runtimes/codex-cli/codex-cli-packaged-install.md),
or the [Claude Code adapter](loopx/claude_goal_mode/README.md).

For custom runners, read
[Embed LoopX in Your Agent Runner](docs/guides/custom-agent-runner-integration.md)
and the [worker bridge install contract](docs/integrations/worker-bridge-install-contract.md).
The core tick is deliberately small:

```text
loopx quota should-run      # should this registered agent act now?
loopx todo claim            # who owns this slice?
loopx todo update           # what changed?
loopx refresh-state         # what should the next turn see?
loopx quota spend-slot      # account for a completed, validated slice
```

A successful connection has:

- `loopx doctor` passing;
- `.loopx/registry.json` and a projected active goal state;
- `loopx status` showing the current objective, concrete user gate, and next
  agent todo;
- a visible loop driver or an exact activation instruction;
- local runtime state ignored rather than committed.

Clone-based install is only for contributors who want the live canary wrapper:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
loopx doctor
```

<a id="capability-surface"></a>

## Capabilities

LoopX folds its control-plane mechanics into five questions:

| Question | What LoopX keeps visible |
| --- | --- |
| What is the objective? | The active goal, explicit scope, and current authority. |
| What happens next? | Ordered user and agent todos, ownership, claims, and leases. |
| What needs human judgment? | Concrete user gates instead of a vague "waiting for owner." |
| What evidence changed? | Compact run history, validation, blockers, and accepted writeback. |
| May the loop continue? | Quota, capabilities, safe fallback, scheduler hints, and stop conditions. |

### Control-Plane Surface

| Surface | What it does | Start with |
| --- | --- | --- |
| Goal state and status | Tracks active state, todos, claims, gates, evidence, run history, and first-screen attention. | `loopx status`, `loopx diagnose`, `loopx review-packet` |
| Quota and interaction contract | Decides whether a turn should deliver, ask, wait, self-repair, or stay quiet. | `loopx quota should-run`, [quota allocation](docs/quota-allocation.md) |
| Agent runtime bridges | Keeps Codex App, Codex CLI, Claude Code, and generic workers aligned with the same guard. | `loopx heartbeat-prompt`, `loopx codex-cli-bootstrap-message`, `loopx worker-bridge` |
| Operator surfaces | Renders compact status without making the browser the state authority. | `loopx serve-status`, [dashboard](apps/presentation/dashboard/README.md) |
| Session dash | Starts a live single-page panel that tracks fleet progress: sessions, their goals, and each goal's status/todo progress, with result statistics; auto-refreshes in place. | `loopx dash`, [session dash design](docs/product/surfaces/session-dash-panel-design.md) |
| External projections | Projects todos and gates into collaboration surfaces while LoopX remains authoritative. | `loopx lark-kanban`, [Lark Kanban adapter](docs/integrations/lark-kanban-control-plane-adapter.md) |
| Domain capabilities | Packages repeatable work lanes such as issue fixing, content operations, value connector planning, ML experiment advice, benchmark evidence, and Explore. | `loopx issue-fix`, `loopx content-ops`, `loopx value-connectors`, `loopx ml-experiment`, `loopx benchmark`, [Explore](docs/capabilities/explore/README.md) |
| Experimental context learning | Lets named registered agents trial provider-neutral Reward Memory through ignored, default-off project configuration. OpenViking is one provider option, not a global dependency. | `loopx reward-memory experiment-status`, [Reward Memory architecture](docs/reference/protocols/reward-memory-architecture-v0.md) |
| Governance patterns | Captures reusable routing, gate, evidence, projection, and planning shapes. | [interaction patterns](docs/concepts/interaction-pattern-catalog.md), [state model](docs/state-interaction-model.md) |

The shipped primitives include lifetime goals, concrete user gates, audited safe
fallbacks, peer todo ownership, quota and steering, compact run history,
evidence-backed handoff, a read-first management surface, project-level value
signals, and public/private boundary checks.

### Runtime Responsibilities

| Role | Responsibility |
| --- | --- |
| **Agent** | Plans, analyzes, uses tools, and performs one bounded action through a host/runtime. |
| **Provider** | Calls external systems and returns observations, effect results, and readback. |
| **Capability** | Defines the caller outcome, normalizes provider output, validates it, and proposes a typed transition. |
| **Kernel** | Owns durable todos, gates, monitors, accepted writeback, quota, recovery, and scheduling. |

The execution path is `Agent -> Capability -> Provider`; the control path
returns `Provider readback -> Capability transition -> Kernel`. An extension is
how an optional provider is packaged and managed, not another control-plane
owner. See [Architecture](docs/architecture.md) and
[Extensions and Capabilities](docs/reference/extensions.md).

## Advanced Paths

The first useful loop does not require every optional surface. Add these only
when the work needs them.

Inspect the current goal's read-only capability catalog before enabling an
advanced path:

```bash
loopx configure-goal --goal-id <goal-id>
```

Without `--execute`, this reports current/default state, fit, boundaries, and
copyable commands without changing project state.

### Presets and Auto Research

Safe presets cover daily triage, changelog drafts, and PR watching. The
one-command research path coordinates proposer, executor, and
evaluator/promoter roles while keeping quota and evidence visible. See the
[beginner preset guide](docs/product/foundations/beginner-loop-presets.md) and
[Auto Research command path](docs/guides/auto-research-command-path.md).

```bash
loopx preset list
loopx preset show daily-triage
```

Preset inspection is read-only. For a connected recurring goal,
`loopx ready-score --goal-id <goal-id> --agent-id <agent-id>` reports whether
the loop is ready to run repeatedly.

### Governed Turns

LoopX can generate one pure, bounded turn decision from a validated receipt,
fresh quota state, and a provider-neutral budget. The current Codex CLI
quickstart and activation contract are documented in
[LoopX Turn for Codex CLI](docs/product/runtimes/codex-cli/loopx-turn-codex-cli-quickstart.md).

### Explore Graph and Harness

Explore is supported, optional, and default-off. It works best when a task has
a measurable offline evaluation, baseline, treatment, and guardrails; it is not
a substitute for production approval. Start with the
[Explore capability](docs/capabilities/explore/README.md) and its
[Lark presentation mapping](docs/capabilities/explore/README.md#presentation-sink-lark-mapping).

### Review Agent Work

Use `loopx review-packet` for a compact owner-facing view of decisions,
evidence, validation, and unresolved gates. The
[intelligent management surface](docs/product/surfaces/intelligent-management-surface.md)
describes the operator model; the
[project-level reward model](docs/product/foundations/project-level-reward-model.md)
describes conservative value signals across output quantity, quality, token
cost, and user attention cost.

For one concrete peer workflow, see the
[cross-runtime implementation review demo](docs/product/use-cases/cross-runtime/cross-runtime-impl-review-demo.md):
Claude implements and Codex reviews while LoopX keeps ownership, evidence,
quota, and handoff explicit.

### App and Projection Paths

- Local read-first UI: [dashboard guide](apps/presentation/dashboard/README.md)
- Public product overview: [public homepage](https://huangruiteng.github.io/loopx/)
- Documentation portal: [hosted docs](https://huangruiteng.github.io/loopx/docs/)
- Feishu/Lark projection: [Lark Kanban adapter](docs/integrations/lark-kanban-control-plane-adapter.md)
- Generic host integration: [integration guide](docs/integration.md)
- Custom multi-agent runner:
  [custom runner integration](docs/guides/custom-agent-runner-integration.md)

Optional projections make state easier to inspect; they do not become the
source of truth.

### Operating and Recovery

Start daily inspection with:

```bash
loopx status
loopx history --goal-id your-project-goal
loopx quota should-run --goal-id your-project-goal
```

Automatic turns must check quota first and append spend only after validated
writeback. Quiet skips, preflight failures, and dry-run previews do not spend.
When a user gate blocks one lane, a separately audited safe fallback may
continue, but it must not bypass the gate.

Peer agents use `loopx todo claim` before delivery and `loopx todo update`
after validation so ownership and evidence remain visible.

Scheduler cadence follows `quota should-run.scheduler_hint`; installed Codex
App automations acknowledge the current hint through the returned
`ack_hint.cli_args`. Collision recovery, monitor semantics, self-repair, and
the exact operator commands are maintained in
[Getting Started](docs/guides/getting-started.md),
[Quota Allocation](docs/quota-allocation.md), and
[Long-Task Cadence Policy](docs/operations/long-task-cadence-policy.md).

Before publishing public docs or examples:

```bash
loopx check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

## Advanced Documentation

Start with the path that matches your role. Use the hosted
[documentation portal](https://huangruiteng.github.io/loopx/docs/) for the
published docs site; the [documentation index](docs/README.md) remains the
complete source map.

### Use and Operate

- [Getting Started](docs/guides/getting-started.md): install, connect,
  diagnose, daily workflow, heartbeats, dashboard, development, and commands.
- [User Manual](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg):
  public onboarding, concepts, FAQ, and selected cases.
- [Showcase Catalog](docs/showcases/README.md): public-safe cases and evidence
  labels.
- [Update Notes](docs/update-notes/README.md): public-safe progress notes.
- [Release Readiness](docs/product/release-readiness.md): install/update paths,
  compatibility gates, release notes, and safe-to-depend-on surfaces.
- [Dashboard](apps/presentation/dashboard/README.md) and
  [Status Data Contract](docs/status-data-contract.md).

### Understand the Control Plane

- [Architecture](docs/architecture.md): lifetime-goal invariant and kernel.
- [State Interaction Model](docs/state-interaction-model.md): actors, stores,
  interaction contract, and writeback.
- [Interaction Pattern Catalog](docs/concepts/interaction-pattern-catalog.md):
  reusable routing, gate, evidence, projection, and planning patterns.
- [Loop Engineering Principles and Pitfalls](docs/product/foundations/loop-engineering-principles-and-pitfalls.md)
  and the
  [Chinese version](docs/product/foundations/loop-engineering-principles-and-pitfalls.zh.md).
- [Control-Plane Developer Course](docs/development/control-plane-course/README.md):
  nine Chinese, code-led lectures.
- [Product Vision](docs/product/vision.md): the broader Loop Agent direction.

### Integrate and Extend

- [Integration Guide](docs/integration.md)
- [Custom Agent Runner Integration](docs/guides/custom-agent-runner-integration.md)
- [Worker Bridge Install Contract](docs/integrations/worker-bridge-install-contract.md)
- [Extensions and Capabilities](docs/reference/extensions.md)
- [Codex App Host Command Registry](docs/reference/protocols/codex-app-host-command-registry-v0.md)
- [Heartbeat Automation Prompt](docs/heartbeat-automation-prompt.md)
- [Lark Kanban Adapter](docs/integrations/lark-kanban-control-plane-adapter.md)
- [Reward Memory Architecture](docs/reference/protocols/reward-memory-architecture-v0.md)

### Validate and Govern

- [Quota Allocation](docs/quota-allocation.md)
- [Public/Private Boundary](docs/public-private-boundary.md)
- [Benchmark Developer Workflow](docs/development/benchmark-developer-workflow.md)
- [Project-Level Reward Model](docs/product/foundations/project-level-reward-model.md)
- [Project Governance](GOVERNANCE.md)
- [Authors and Contributors](AUTHORS.md)
- [Project History](docs/project/history.md)
- [Name and Marks](TRADEMARKS.md)

## Partner Projects

LoopX welcomes collaboration with other open-source projects to build the
long-running agent ecosystem. Our confirmed partners include:

- [OpenViking](https://github.com/volcengine/OpenViking) - Self-evolving
  context database for AI agents
- [NoKV](https://github.com/NoKV-Lab/NoKV) - AI native distributed file system

<a id="community--feedback"></a>

## Community and Feedback

LoopX is still early. The most useful feedback comes from real long-running
agent projects: where the control plane helped, where it felt heavy, and which
gates or handoffs disappeared from view.

- Use [GitHub Issues](https://github.com/huangruiteng/loopx/issues) for
  reproducible bugs, install problems, and feature requests.
- Open PRs for docs fixes, showcase writeups, and small public-safe examples.
- Join the [Discord community](https://discord.gg/XmGgQyCFZd), or use Lark or
  WeChat below.

See [Support](SUPPORT.md) for channel routing and service boundaries, and
[Communications](COMMUNICATIONS.md) for official publication sources.

<p align="center">
  <a href="docs/assets/loopx-lark-developer-group.png"><img src="docs/assets/loopx-lark-developer-group.png" alt="LoopX Lark developer group QR code" width="280"></a>
  <a href="docs/assets/loopx-wechat-contact.png"><img src="docs/assets/loopx-wechat-contact.png" alt="LoopX WeChat contact QR code" width="220"></a>
</p>
<p align="center">
  <sub><strong>Lark:</strong> scan to join directly<br><strong>WeChat: <code>huangrt00</code></strong> · mention LoopX in the friend request</sub>
</p>

## Contributing

External contributors should start with
[Contributor Tasks](CONTRIBUTOR_TASKS.md) for public, claimable work and
[Contributing](CONTRIBUTING.md) for setup, validation, and boundary rules.
Project roles and public history are recorded in [Governance](GOVERNANCE.md),
[Authors and Contributors](AUTHORS.md), and
[Project History](docs/project/history.md).

LoopX keeps local active state separate from the public repository. Do not
commit `.loopx/`, `.codex/goals/`, live `ACTIVE_GOAL_STATE.md`, raw benchmark
traces, credentials, private logs, or operator artifacts.

## Current Status

The v0.4.x line is an early but usable local control plane for long-running
agent work. It is not a full agent platform, an agent runtime, or an autonomous
production controller.

Today LoopX ships a durable state kernel for goals, typed todos and decision
scopes, peer claims and leases, evidence and writeback, quota-aware scheduling,
and cross-turn continuation. Guided start, recurring heartbeat, isolated Codex
CLI turns, evidence-backed Issue-Fix admission, optional Explore and auto
research paths, public validation canaries, and a read-first multi-project
dashboard build on that shared control state.

Support levels remain explicit. The state and CLI contracts are the stable
center; several host integrations and advanced paths are optional, default-off,
or experimental. LoopX does not grant credentials, approve destructive or
production actions, publish on a user's behalf without authorization, or turn
an unverified run into evidence of success.

The next milestones are simpler installation and host packaging, broader typed
runtime adapters, stronger terminal acceptance across repeated public loops,
independent adoption and outcome evidence, and a more polished management
surface.

## Star History

<p align="center">
  <a href="https://github.com/huangruiteng/loopx/stargazers"><img src="https://huangruiteng.github.io/loopx/site-assets/star-history.svg" alt="LoopX GitHub star history from verified snapshots" width="900"></a><br>
  <sub>Generated every six hours from GitHub's official stargazer timestamps using a repository-authorized workflow. A snapshot is published only when the fetched rows match GitHub's current star count; GitHub's image cache may delay refreshes.</sub>
</p>

## License

MIT. See [LICENSE](LICENSE).

[osai-verify: eb42dd9cf910399988f0]: #
