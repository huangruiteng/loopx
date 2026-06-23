# Getting Started With LoopX

This guide carries the operational detail that used to live in the root
README. The root README is now the short product landing page; this page is the
hands-on path for installation, project connection, diagnosis, heartbeats,
dashboard use, development checks, and command discovery.

## Codex App And Other Agent Setup

If you already use Codex, Claude Code, Cursor, or another terminal agent, paste
this into the agent from your project repo:

Compatibility check for non-Codex agents: the agent surface needs at least one
control hook for LoopX to drive it, such as shell/CLI execution, a goal/task
command, an automation or heartbeat hook, or its own loop/scheduler. Without
one of those, use the manual shell commands instead; LoopX can preserve project
state, but it cannot make an agent continue automatically.

```text
Install and connect LoopX for this project end to end. Do not stop at a
plan.

If `loopx` is not on PATH:
- install it without making me clone the repo:

curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"

Then:
1. Run `loopx doctor`.
2. Choose a stable goal id from this repo name unless I gave one explicitly.
3. Read the project goal doc if present (`GOAL.md`, `README.md`, or the doc I
   name); otherwise ask me for a one-sentence objective.
4. Run `loopx connect` or `loopx bootstrap` for this repo with
   that goal id, objective, domain, and goal doc.
5. Read the `Onboarding Scan`, `Proposed Onboarding Candidates`,
   `Accept Candidate Commands`, and `Autonomy Choice` from the connect output.
   Briefly explain the candidate agent todos to me and ask:
   - which candidates I accept, edit, or reject;
   - whether `autonomous=yes`, meaning you may start the first accepted agent
     todo after the quota guard passes.
   Do not make me run the acceptance commands manually; run the accepted
   `loopx todo add ...` commands yourself. If I choose
   `autonomous=no`, stop after `loopx refresh-state`.
6. Ensure `.loopx/` and `.codex/goals/` are ignored in this project.
7. Run `loopx registry`, `loopx status`, and
   `loopx check --scan-root .`.
8. Report the goal id, created files, current user todo, current agent todo,
   and next safe action.

Do not commit `.loopx/`, `.codex/goals/`, live ACTIVE_GOAL_STATE files,
runtime registries, raw logs, credentials, or private local paths.
```

For a longer generated handoff prompt, install once and run:

```bash
loopx new-project-prompt \
  --project /path/to/your-project \
  --goal-doc /path/to/your-project/GOAL.md
```

The command output is meant to be pasted into Codex or Claude Code. It contains
the full guard, quota, todo, and heartbeat protocol for a new project.

Success looks like this:

- `loopx doctor` passes;
- the project has `.loopx/registry.json`;
- the project has `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`;
- `loopx status` shows the goal and who should act next;
- local runtime state is ignored, not committed.

## Codex CLI TUI Setup

For Codex CLI users, the product target is: start in the Codex TUI, send one
LoopX setup message, and let the agent install or reuse LoopX,
bootstrap/connect the project, then set the current Codex goal to the thin
heartbeat prompt. Later automation should stay visible and interruptible in
that TUI whenever the CLI exposes a safe session-attachment primitive. The
first-run path should not require you to understand registry paths, runtime
roots, JSON payloads, session files, or heartbeat prompt syntax.

First-run path:

```text
Install and connect LoopX for this repo from this visible Codex CLI TUI.
If `loopx` is missing, install it with the official no-clone GitHub
installer; if it is already installed, reuse it. Bootstrap or connect this
project, then generate the thin heartbeat prompt and set the current Codex CLI
goal to `/goal <thin task_body>`. Show me the current goal, concrete user gate
if any, top todos, and next safe action before longer work. Keep me in this TUI
and do not use hidden headless execution.
```

The generated paste block is a setup-first rewrite of the App onboarding
experience, not the heartbeat body itself. After the project is connected, the
agent generates `heartbeat-prompt --thin` and installs that body into the
surface: Codex CLI gets `/goal <thin task_body>`, while Codex App gets a
heartbeat automation body. The first useful response should show the current
goal id, concrete user gate if one exists, top user todo if any, top agent
todo, and next safe action before longer delivery work. The setup turn should
not spend quota for delivery unless the user explicitly asks it to do delivery
after loop activation.

Once `loopx` is installed, generate a stricter repo-specific setup
message:

```bash
loopx codex-cli-bootstrap-message --project . --goal-id <goal-id>
```

Keep that as the preferred interactive path: the human watches and steers in
Codex CLI TUI, while LoopX owns quota/status/todos/gates/writeback. The
generated packet also shows the no-clone install-repair command, the
post-bootstrap thin prompt generation command, and a transcript-free validation
checklist, so a fresh repo path can be reviewed without touching raw Codex
session data.

If the user only wants the pasteable TUI text, omit the wrapper:

```bash
loopx codex-cli-bootstrap-message --project . --goal-id <goal-id> --message-only
```

To review the whole one-message loop contract without running Codex, generate a
pilot packet:

```bash
loopx codex-cli-one-message-loop-pilot --project . --goal-id <goal-id> --agent-id <agent-id>
```

The pilot ties the first TUI paste message to the later
`codex-cli-local-scheduler-exec` bridge. It stays dry-run by default and is for
operators/contributors validating the path, not a prerequisite for first-time
users.

To review the returning-user local-driver loop without touching a real Codex
session, generate the visible local-driver pilot packet:

```bash
loopx codex-cli-visible-local-driver-pilot --project . --goal-id <goal-id> --agent-id <agent-id>
```

This keeps the first-message TUI start primary, then models later scheduler
ticks, visible proof, idle guard, guarded execution, blocker writeback, and
no-transcript boundaries as public-safe metadata.

The later-turn rule is intentionally stricter than the first message: LoopX may
add a visible steering turn only after public-safe visible proof,
runtime idle evidence, a fresh guard, and explicit execution bounds. Without
that proof, the driver should write a compact blocker or keep the one-message
setup bootstrap as the product path.

The commands below are optional automation checks after the setup path
works. To evaluate future same-session automation support without touching
transcripts or session files, run:

```bash
loopx codex-cli-session-probe
```

To turn that probe into a dry-run driver decision without mutating a Codex
session, run:

```bash
loopx codex-cli-visible-driver-plan --project . --goal-id <goal-id>
```

To see the full local automation setup plan in one packet, including quota
guard, visible-driver decision, TUI bootstrap command, the headless-disabled
boundary, and idle-guard requirement, run:

```bash
loopx codex-cli-local-driver-plan --project . --goal-id <goal-id> --agent-id <agent-id>
```

This is still dry-run-only. It does not run Codex, read transcripts, read
session files, mutate a session, or spend quota.

When the driver plan says `resume [PROMPT]` or `remote-control` might support a
visible same-session path, validate a public-safe proof fixture before treating
that path as automation:

```bash
loopx codex-cli-visible-session-proof \
  --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --proof-fixture visible-proof.public.json
```

The fixture should contain only booleans and public-safe labels proving user
opt-in, quota guard, idle guard, visible turn, interruptibility, no transcript
or session-file reads, and compact writeback planning.

The default Codex CLI setup-then-`/goal` product path does not offer a headless fallback.
For compatibility, the old handoff command only reports the disabled boundary
and points back to the message-only TUI bootstrap:

```bash
loopx codex-cli-exec-handoff --project . --goal-id <goal-id>
```

See the [Codex CLI TUI-first loop](../product/codex-cli-tui-loop.md) contract
for the bootstrap, session-attached automation, and headless-disabled boundary.
The [Codex CLI first-run rehearsal](../product/codex-cli-first-run-rehearsal.md)
keeps the shortest user-facing route in one place: no-clone install,
one-message setup bootstrap, and proof-capture fixtures for later automation.
For current product scheduling, the
[Codex CLI TUI continuation priority](../product/codex-cli-tui-continuation-priority.md)
keeps same-open-TUI continuation ahead of frontstage or showcase polish when
both are runnable.

Maintainers can validate the public fresh-clone path with:

```bash
python3 examples/fresh-clone-quickstart-smoke.py
```

## No-Clone Install

Install or update LoopX without cloning the repository:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

The installer downloads a GitHub archive, writes a stable local release snapshot
under `~/.local/share/loopx/releases/`, installs the CLI wrapper under
`~/.local/bin`, and installs the reusable LoopX skills under
`~/.codex/skills`.

`loopx doctor` reports `install_freshness`. For a productized upgrade path, use
the explicit self-update interface:

```bash
loopx update --check
loopx update --dry-run
loopx update --execute
```

`--check` and `--dry-run` are read-only. `--execute` reruns the no-clone
installer, reports the source archive, keeps the previous release snapshot as a
rollback target when possible, and validates the result with `loopx doctor`.

This is the recommended install repair path for Codex CLI users because an
agent can run it from inside the TUI without asking the user to clone this
repository first.

## Contributor Install

Install one shared local checkout when you want to develop LoopX itself
or test a live canary wrapper:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
loopx doctor
```

The checkout installer creates:

- `~/.local/bin/loopx`, pointing at a stable local release snapshot;
- `~/.local/bin/loopx-canary`, pointing at the live checkout;
- the LoopX Codex skills under `~/.codex/skills`.

Those global skills are the intended product surface for reusable LoopX
agent behavior; project-specific state and private decisions stay in the local
registry and active goal files.

Use the canary wrapper for one or two selected controllers before promoting a
checkout to the default local release.

## Global Skill Install, Update, Repair, And Cleanup

`scripts/install-local.sh` manages two reusable local surfaces:

- the CLI wrappers under `~/.local/bin`;
- the LoopX Codex skills under `~/.codex/skills`.

For a no-clone install, use `loopx update` to refresh the release snapshot and
skills:

```bash
loopx update --check
loopx update --execute
```

For a contributor checkout, re-run the installer to update both surfaces from
the current checkout:

```bash
cd ~/loopx
git pull --ff-only
./scripts/install-local.sh
loopx doctor
```

Use `loopx-canary` when you want to test the live checkout before making
it the default release snapshot. `loopx doctor` reports whether the
default wrapper points at a release snapshot, whether the canary wrapper points
at the live checkout, and whether the required skills are installed.

If an agent says it cannot find LoopX, repair in this order:

1. Ensure `~/.local/bin` is on `PATH`.
2. Re-run `~/loopx/scripts/install-local.sh`.
3. Run `loopx doctor`.
4. If a recurring automation is stale, regenerate it with
   `loopx heartbeat-prompt --thin --goal-id <goal-id> --agent-id <agent-id> --agent-scope "<scope>"`.

The reusable skills have intentionally narrow jobs:

| Skill | Use it for | Do not use it for |
| --- | --- | --- |
| `loopx-project` | Connecting projects, reading status/quota/history, diagnosing LoopX, generating heartbeat/review packets, and refreshing state. | Reading private project documents by default or replacing the CLI as source of truth. |
| `loopx-doc-registry` | Registering durable project material and redacted authority-source metadata. | Copying raw doc bodies, internal URLs, or private comments into public repo docs. |
| `loopx-self-repair` | Repairing surprising control-plane behavior, stale projection, tiny turns, or contradictory guard payloads. | Lowering gates, guessing around missing authority, or committing private runtime state. |

Keep three layers separate:

- **Global skill behavior** belongs in `skills/` and is installed under
  `~/.codex/skills`.
- **Project state** belongs in `.loopx/`, `.codex/goals/`, and
  `~/.codex/loopx`; keep it local unless a sanitized fixture is
  intentionally committed.
- **Repository rules** belong in `AGENTS.md`, `CONTRIBUTING.md`, and public
  docs. They can constrain contributors and agents in this repository, but they
  should not silently become global skill policy for every project.

There is no dedicated uninstall command yet. For manual cleanup, remove only
the reusable surfaces you intend to drop:

```bash
rm -f ~/.local/bin/loopx ~/.local/bin/loopx-canary
rm -rf ~/.codex/skills/loopx-project \
       ~/.codex/skills/loopx-doc-registry \
       ~/.codex/skills/loopx-self-repair
```

This does not archive connected project state or runtime history. Archive or
remove `.loopx/`, `.codex/goals/`, and `~/.codex/loopx` only when
you intentionally want to retire those local project records.

## Connect A Project Manually

From the project repository:

```bash
cd /path/to/your-project
loopx bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

`connect` is an alias for `bootstrap`:

```bash
loopx connect --goal-id your-project-goal
```

This creates or connects:

```text
your-project/
  .loopx/registry.json
  .codex/goals/your-project-goal/ACTIVE_GOAL_STATE.md

~/.codex/loopx/
  goals/<goal-id>/runs/
```

Treat live goal state and registries as local runtime data. Add these paths to
the connected project `.gitignore` before committing:

```gitignore
.loopx/
.codex/goals/
goals/**/ACTIVE_GOAL_STATE.md
```

Commit only sanitized templates or examples, not a controller's live
`ACTIVE_GOAL_STATE.md`.

## Diagnose From Your Agent

Users should not need to run diagnostic commands by hand. Ask your Codex,
Claude Code, Cursor, or terminal agent:

```text
Diagnose LoopX for this project end to end. Do not ask me to run shell
commands.

If `loopx` is missing, install or repair it first. Then run
`loopx diagnose` yourself, read the diagnostic packet, and use your own
reasoning to tell me:
- whether this project can currently self-drive;
- what evidence supports that answer;
- what is blocking it, if anything;
- the exact question I need to answer, if a user/controller gate exists;
- what you will do next.

Do not treat LoopX machine signals as the final verdict. They are
evidence for your diagnosis.
```

`loopx diagnose` is intentionally an agent-facing evidence packet. It
collects compact `status`, `quota should-run`, todo, interaction-contract, and
boundary signals, then gives the agent a reasoning checklist. The agent makes
the diagnosis in natural language.

If you want to try LoopX before connecting a real repo, create a
disposable demo goal:

```bash
export PATH="$HOME/.local/bin:$PATH"
loopx demo
```

Expected first-run signals:

- the output contains `ok: True`;
- a project-local registry and active goal state were created under
  `/tmp/loopx-demo`;
- one user todo and one agent todo are visible;
- `refresh-state` appended a compact run;
- `quota should-run` returns `should_run=True` and `state=eligible`.

Inspect the demo:

```bash
cd /tmp/loopx-demo
loopx status
loopx quota should-run --goal-id demo-goal
loopx history --goal-id demo-goal
```

## Daily Workflow

Inspect installation and registry health:

```bash
loopx doctor
loopx registry
loopx check --scan-root .
```

Read status and history:

```bash
loopx status
loopx history --goal-id your-project-goal
```

Add explicit work:

```bash
loopx todo add \
  --goal-id your-project-goal \
  --role user \
  --text "Review the owner checklist."

loopx todo add \
  --goal-id your-project-goal \
  --role agent \
  --text "Summarize the safe read-only evidence." \
  --task-class advancement_task \
  --action-kind evidence_summary
```

Complete an agent todo and atomically add the next executable item:

```bash
loopx todo complete \
  --goal-id your-project-goal \
  --todo-id todo_ab12cd34ef56 \
  --evidence "Validated with examples/demo-cli-smoke.py" \
  --next-agent-todo "Run the next bounded validation slice." \
  --next-task-class advancement_task \
  --next-action-kind validation \
  --execute
```

Append a state-only refresh after local state or docs change:

```bash
loopx refresh-state --goal-id your-project-goal
```

Generate a compact handoff packet for an agent:

```bash
loopx review-packet --goal-id your-project-goal
```

Record an operator gate decision or run-bound reward:

```bash
loopx operator-gate \
  --goal-id your-project-goal \
  --decision approve \
  --reason-summary "Approve read-only map opt-in"

loopx reward \
  --goal-id your-project-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "validation improved and the route is worth extending"
```

## Heartbeats And Quota

Quota is compute eligibility, not strategy. It answers whether an automatic
turn may run now, and what kind of turn is allowed.

```bash
loopx quota status
loopx quota plan
loopx quota should-run --goal-id your-project-goal
```

The `next_automatic_turn` reported by `quota plan` is only an advisory
scheduling hint: it chooses the highest-compute eligible goal, while
operator-gated, focus-waiting, waiting, throttled, paused, and health-blocked
goals stay out of the eligible lane.

`quota should-run` returns the machine contract a heartbeat should obey:

- `should_run`: whether delivery work may run now;
- `waiting_on`: user, controller, Codex, external evidence, health, or quota;
- `work_lane_contract`: the next executable lane or monitor/blocker lane;
- `execution_obligation`: whether the agent must attempt a bounded segment;
- user and agent todo summaries;
- safe-bypass or self-repair hints, when enabled;
- the exact spend policy.

Agent todo summaries separate `first_executable_items` from
`monitor_open_items`: executable items drive the selected goal's primary
action, while monitor items stay visible as supplemental observation context
and only spend compute when they produce a material transition or blocker.

Registry entries can expose per-goal `control_plane` policy. For example,
`control_plane.self_repair.enabled=true` lets `quota should-run` return a
bounded `decision=self_repair` contract for repairable control-plane stalls;
missing policy defaults off, so other goals keep their normal skip or wait
behavior.

If `quota should-run` returns a `gate_prompt` or `operator_question`, the
target heartbeat should proactively ask that concrete user/controller gate. If
open user todos are present, do not call the turn "no new user action" while
they remain open; its report still has to list existing open user todos.

When `safe_bypass_allowed=true`, the heartbeat may still do one bounded
read-only steering or analysis step that is independent of the blocked gate.
See [quota allocation](../quota-allocation.md) for the full allocation
contract.

After an automatic turn actually spends delivery compute, append one spend
event:

```bash
loopx quota spend-slot \
  --goal-id your-project-goal \
  --slots 1 \
  --source heartbeat \
  --execute
```

Do not append spend for quiet `should_run=false` skips, preflight failures, or
pure dry-run previews.

Generate a guarded Codex App heartbeat body:

```bash
loopx heartbeat-prompt --thin --goal-id your-project-goal
```

For shared-control-plane agents, pass identity and scope in the automation
prompt, then let the agent soft-claim matching todos with a registered
`--claimed-by` id:

```bash
loopx configure-goal --goal-id your-project-goal \
  --registered-agent codex-main-control \
  --registered-agent codex-side-bypass \
  --primary-agent codex-main-control \
  --execute

loopx heartbeat-prompt --compact --goal-id your-project-goal \
  --agent-id codex-side-bypass \
  --agent-scope "control-plane coordination"
```

Once `coordination.registered_agents` is set, `heartbeat-prompt` fails closed
when called without `--agent-id`; this makes stale Codex App automations
surface an upgrade error instead of silently running without identity or
scope. Old goal registries without `coordination.registered_agents` also fail
closed when a scoped heartbeat or todo claim names an agent; register the agent
identity first instead of letting workers invent claim ids.

Set exactly one `coordination.primary_agent`: that primary agent owns final
review, verification, merge, publication, and high-risk side-agent review. Side
agents are prompted to work in separate worktrees, and `quota should-run
--agent-id <side-agent-id>` fails closed with `workspace_guard` when a side
agent runs from the primary checkout. Small AGENTS-eligible
validated changes may be self-merged with explicit LoopX evidence;
higher-risk or unclear work should still be handed back through a primary
review todo.

See [heartbeat automation prompt](../heartbeat-automation-prompt.md) and
[project agent todo contract](../project-agent-todo-contract.md).

## Dashboard

Dashboard status is an experimental operator preview. The CLI and
`loopx status` remain the canonical daily workflow; the React dashboard
is useful for demos, public-safe fixtures, and local inspection.

Serve status JSON:

```bash
loopx serve-status --port 8765
```

Run the dashboard:

```bash
cd ~/loopx/apps/dashboard
npm install
npm run dev
```

For the shared multi-project view:

```bash
loopx serve-status --global-registry --port 8766 --limit 80
```

On macOS, keep the global feed and built dashboard running after login:

```bash
~/loopx/scripts/macos-dashboard-launchagent.sh install
~/loopx/scripts/macos-dashboard-launchagent.sh status
```

The dashboard should answer, before raw log drill-down:

- what the human needs to judge;
- what Codex can do next;
- what is waiting on evidence;
- what boundary cannot be crossed yet.

See [apps/dashboard/README.md](../../apps/dashboard/README.md).

## Public / Private Boundary

Safe to publish:

- registry schema and runtime layout;
- adapter lifecycle and generic control-plane contracts;
- sanitized examples and smoke fixtures;
- generic validation commands.

Keep private:

- real local paths;
- task ids and internal document links;
- production logs and raw experiment metrics;
- credentials and auth material;
- user-specific active goal state and local registries;
- raw agent sessions or benchmark traces.

Run the public/private scan before publishing docs or examples:

```bash
loopx check \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

See [public/private boundary](../public-private-boundary.md).

## Development

Run the focused CLI and contract smokes from the repository root:

```bash
python3 -m py_compile loopx/*.py
python3 examples/demo-cli-smoke.py
python3 examples/todo-cli-smoke.py
python3 examples/todo-lifecycle-cli-smoke.py
python3 examples/quota-contract-smoke.py
python3 examples/review-packet-cli-smoke.py
python3 examples/benchmark-run-v0-append-cli-smoke.py
git diff --check
```

For dashboard work:

```bash
cd apps/dashboard
npm install
npm run build
npm run smoke:demo-readiness
```

For release-promotion readiness:

```bash
python3 examples/canary-promotion-readiness-smoke.py
loopx promotion-gate --format json
loopx upgrade-plan --format json
```

## Documentation Map

Start here:

- [Documentation index](../README.md)
- [Showcase catalog](../showcases/README.md)
- [State interaction model](../state-interaction-model.md)
- [Interaction pattern catalog](../interaction-pattern-catalog.md)
- [Integration guide](../integration.md)
- [Attention queue](../attention-queue.md)
- [Project agent todo contract](../project-agent-todo-contract.md)
- [Quota allocation](../quota-allocation.md)
- [Heartbeat automation prompt](../heartbeat-automation-prompt.md)
- [Long-task cadence policy](../long-task-cadence-policy.md)
- [Public/private boundary](../public-private-boundary.md)
- [Benchmark developer workflow](../benchmark-developer-workflow.md)
- [Public launch narrative draft](../outreach/public-launch-narrative-draft.md)
- [Xiaohongshu launch draft](../outreach/xiaohongshu-launch-draft.md)
- [Dashboard status contract](../status-data-contract.md)
- [Codex subagent orchestration](../codex-subagent-orchestration.md)
- [Benchmark long-run design](../research/long-horizon-agent-benchmarks/codex-cli-long-run-benchmark-design.md)

## Command Reference

```text
bootstrap / connect     connect a project-local goal
new-project-prompt      generate a Codex prompt for project connection
demo                    create a disposable local demo goal
doctor                  diagnose installation and import health
update                  check or execute a no-clone LoopX self-update
registry                inspect registered goals
registry-boundary       classify registry local/public boundary and push policy
status                  show first-screen operator status
diagnose                build an agent-facing diagnostic evidence packet
history                 read run history
refresh-state           append a state-only run
read-only-map           map a project without mutating files
operator-gate           record a human gate decision
reward                  append run-bound human reward
todo                    add, claim, complete, update, supersede, or archive todos
quota                   inspect or account for automatic agent turns
heartbeat-prompt        generate Codex App heartbeat task bodies
upgrade-plan            plan local default-upgrade heartbeat propagation
review-packet           package a CLI-visible handoff packet
serve-status            serve local status JSON for the dashboard
archive-runtime         archive obsolete runtime-only goal history
sync-global             merge project registry into the global registry
check                   run contract and public/private boundary checks
```

Use `loopx <command> --help` for command-specific flags.

## Repository Quality Guard

This repository should stay readable to a new contributor. Treat these as
periodic maintainer checks:

- the README first screen explains the product before internal operations;
- quick start commands still run on a clean checkout;
- live local state is not committed;
- public/private scan is clean before docs or examples are published;
- docs linked from the README still exist and describe current CLI behavior;
- smoke commands cover the highest-risk control-plane contracts.
