# Getting Started With LoopX

This guide carries the operational detail that used to live in the root
README. The root README is now the short product landing page; this page is the
hands-on path for installation, project connection, diagnosis, heartbeats,
dashboard use, development checks, and command discovery.

If you are new to LoopX, start with the shorter
[Newcomer command path](newcomer-command-path.md): it reduces the product
surface to the host LoopX task entry, project connection, and one manual CLI
quickstart. This page keeps the full operator and contributor detail.

## Codex App And Other Agent Setup

If you already use Codex, Claude Code, Cursor, or another terminal agent, paste
this into the agent while it is already operating in the project root:

Compatibility check for non-Codex agents: the agent surface needs at least one
control hook for LoopX to drive it, such as shell/CLI execution, a goal/task
command, an automation or heartbeat hook, or its own loop/scheduler. Without
one of those, use the manual shell commands instead; LoopX can preserve project
state, but it cannot make an agent continue automatically.

```text
Connect the current project to LoopX.
Do not clone the LoopX repository for ordinary use. If `loopx` is not on PATH,
install or repair it with the official no-clone installer:
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"

Then run `loopx doctor`. Work only from the current project root:
1. If LoopX state already exists, reuse it and do not create or overwrite a
   goal or the active objective.
2. If the project is not connected, prefer `loopx connect`; use
   `loopx bootstrap` only when project state clearly needs initialization.
3. Ensure `.loopx/`, `.codex/goals/`, and `.local/` are ignored.
4. Set up the thin LoopX heartbeat for this surface. For Codex App, start the
   recurring automation at 3 minutes, then follow
   `quota should-run.scheduler_hint` for backoff and self-stop behavior.
5. Stop after setup and report the active state id, current user gate, top
   agent todo, and next safe action.

Do not commit `.loopx/`, `.codex/goals/`, `.local/`, live ACTIVE_GOAL_STATE
files, runtime registries, raw logs, credentials, or private local paths. Do
not start longer delivery work in this setup turn.
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

## Command Skill Registration

The installer also registers the LoopX command family for host surfaces that
can discover user-installed skills:

- Codex CLI / IDE / App: explicit LoopX command-facade skills under
  `~/.codex/skills/loopx*`. Codex does not currently support user-defined
  native top-level `/loopx` slash commands, so invoke the project command
  through `$loopx` or `/skills`. The primary `LoopX` command facade and
  `LoopX Project` workflow skill are separate entries: command facades set
  `allow_implicit_invocation: false`, while richer workflow skills such as
  `loopx-project` and `loopx-pr-review` keep their normal implicit behavior.
- Claude Code: lightweight user skills under `~/.claude/skills/loopx*`, so the
  command family can appear as Claude Code slash commands without enabling the
  opt-in MCP/hook adapter.
- OpenCode: static command files under `~/.config/opencode/commands/` expose
  native `/loopx` slash commands after restart. The executable goal bridge
  (timer-based idle continuation gated by LoopX quota) requires an explicit
  `--with-goal-bridge` install.

The command family is the same across surfaces, even when the host-specific
entry point is different:

| Command family | Host entry | CLI fallback |
| --- | --- | --- |
| Project goal start | `/loopx <goal text>` where the host exposes native slash commands; `$loopx <goal text>` or the `LoopX` command skill in Codex surfaces that use explicit skills. | `loopx start-goal --guided --project . --goal-text "<goal text>" --host-surface <exact-host>` |
| Global manager views | `/loopx-global-summary`, `/loopx-global-gates`, `/loopx-global-todos`, `/loopx-global-risks`. | `loopx slash-commands`, then run the listed global manager command for the view you need. |
| PR review queue | `/loopx-pr-review`. | `loopx pr-review` |

Treat the slash or skill entry as a UI convenience. The CLI remains the source
of truth, and recovery should use the CLI instead of inventing a second state
path. If a command disappears after an upgrade, first inspect and refresh the
registered command files:

To refresh those files after an upgrade, run:

```bash
loopx slash-commands
loopx slash-commands --install
```

The command updates files that LoopX owns, including older LoopX-generated
files with known legacy signatures. If a same-name file has no LoopX managed
marker or legacy signature, LoopX leaves it untouched and reports
`skipped_user_file`.

If a project-local goal command still cannot be invoked through the host, run
the equivalent guided start preview from the project root:

```bash
loopx start-goal --guided --project . --goal-text "<goal text>" \
  --host-surface codex-cli-tui
```

That preserves the `/loopx <goal text>` semantics while keeping mutation under
the agent's control: preserve the exact task text, inspect or connect state,
plan before todo writeback, refresh state, activate the correct host loop, run
`quota should-run`, and continue only when the guard allows. Host and plugin
integrations that need the lower-level handoff packet can use
`loopx bootstrap-command-pack --project . --goal-text "<goal text>"`. For global
manager or PR review commands, use `loopx slash-commands` to print the current
canonical command list and fallback CLI shapes.

Use `codex-app`, `codex-ide-plugin`, `codex-cli-tui`, or `opencode` for the
corresponding host. Select `codex-ide-plugin` only when LoopX is running through the
installed IDE plugin; using Codex beside an editor does not make the host an IDE
plugin. If the exact host is not known, omit `--host-surface` once: LoopX
returns a read-only selection gate with exact rerun commands and does not write
project state. The legacy `codex-ide` value remains an accepted compatibility
alias but is no longer advertised. This prevents an upgrade from silently
routing an IDE plugin or terminal start to a desktop-app heartbeat.

## Local State Backup

Before risky migrations, local scheduler changes, or release-install repair,
preview the state archive:

```bash
loopx backup-state --project .
```

Write the archive only when the preview looks right:

```bash
loopx backup-state --project . --execute
```

The backup is written under `~/.codex/loopx/backups` by default. It captures the
shared LoopX runtime root, Codex App automations, installed `loopx-*` skills,
the current project's state, and every reachable project's `.loopx`,
`.codex/goals`, `.claude/goals`, `.local/goals`, registry-declared active state,
and source registry discovered from the global registry. Missing or stale
project routes remain visible in the manifest. Use `--current-project-only`
only when a deliberately narrow archive is sufficient. Treat the archive and
manifest as private local recovery material; do not commit them or publish
their contents.

The preview reports **logical source bytes before compression**, not the final
archive footprint. Full runtime history and project-local goal evidence are
included intentionally so the archive can support a faithful rollback. The
category breakdown shows which surface contributes the bytes, while contained
target overlap identifies exact recovery targets such as active-state or
source-registry files that are also covered by a parent project directory.
After `--execute`, use `archive_size_bytes` and the archive/logical ratio to
judge the actual storage cost.

## Codex CLI TUI Setup

For Codex CLI users, the product target is: start in the Codex TUI, send one
LoopX setup message, and let the agent install or reuse LoopX,
connect the project, and stop with the current gate/todo/next-action report.
As part of that setup, the agent sets the current Codex goal to the thin
heartbeat prompt so the user immediately feels the loop is live. Later
automation should stay visible and interruptible in that TUI whenever the CLI
exposes a safe session-attachment primitive. The first-run path should not
require you to understand registry paths, runtime roots, JSON payloads, session
files, or heartbeat prompt syntax.

First-run path:

```text
Connect this repo to LoopX from this visible Codex CLI TUI. Do not clone the
LoopX repository for ordinary use. If `loopx` is not on PATH, install or repair
it with the official no-clone installer:
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash

Then run `loopx doctor`. Work only from this project root: if LoopX state
already exists, reuse it and do not create or overwrite a goal or the active objective; if the project
is not connected, prefer `loopx connect`, and use `loopx bootstrap` only when
project state clearly needs initialization. Ensure `.loopx/`, `.codex/goals/`,
and `.local/` are ignored. Keep me in this TUI, do not use hidden headless
execution. After the project is connected, generate the thin heartbeat prompt
and set the current Codex CLI task body with `/goal <thin task_body>`. Then
stop and report the active state id, current user gate, top agent todo, and
next safe action.
```

The generated paste block is a setup-first rewrite of the App onboarding
experience, not the heartbeat body itself. The first useful response should
show the current state id, concrete user gate if one exists, top user todo if
any, top agent todo, and next safe action before longer delivery work. The
setup turn should not spend quota for delivery unless the user explicitly asks
it to do delivery in the setup turn. The agent should still generate
`heartbeat-prompt --thin` and install that body into the surface during setup:
Codex CLI gets `/goal <thin task_body>`, while Codex App gets a heartbeat
automation body that starts at 3 minutes and then follows
`scheduler_hint`.

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
`~/.local/bin`, installs the `man loopx` page under
`~/.local/share/man`, and installs the reusable LoopX skills under
`~/.codex/skills`.

`loopx doctor` reports `install_freshness`. For a productized upgrade path, use
the explicit self-update interface:

```bash
loopx update --check
loopx update --dry-run
loopx update --execute
```

`--check` and `--dry-run` are read-only. For a GitHub repo/ref source,
`--check` also performs a bounded version read from that exact ref. If the
network is unavailable, it keeps the local health result and says that the
latest source version could not be confirmed; a custom archive URL skips the
comparison because LoopX cannot assume it matches the configured repo/ref.
`--execute` reruns the no-clone installer, reports the source archive, keeps the
previous release snapshot as a rollback target when possible, and validates the
result with `loopx doctor`.

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
- `~/.local/share/man/man1/loopx.1.gz`, so `man loopx` opens the short
  operator manual after the shell profile reloads;
- the LoopX Codex skills under `~/.codex/skills`.

Those global skills are the intended product surface for reusable LoopX
agent behavior; project-specific state and private decisions stay in the local
registry and active goal files.

Use the canary wrapper for one or two selected controllers before promoting a
checkout to the default local release.

## Global Skill Install, Update, Repair, And Cleanup

`scripts/install-local.sh` manages three reusable local surfaces:

- the CLI wrappers under `~/.local/bin`;
- the local manual page under `~/.local/share/man`;
- the LoopX Codex skills under `~/.codex/skills`.

For a no-clone install, use `loopx update` to refresh the release snapshot and
skills:

```bash
loopx update --check
loopx update --execute
```

For a contributor checkout, re-run the installer to update both surfaces from
the current clean `origin/main` checkout:

```bash
cd ~/loopx
git pull --ff-only
./scripts/install-local.sh
loopx doctor
```

The installer treats default promotion as a release boundary. A clean checkout
at `origin/main` promotes automatically. A dirty checkout or another branch
updates only `loopx-canary` and leaves the default CLI, installed skills, and
manual untouched. After validating that checkout, promote it explicitly:

```bash
LOOPX_PROMOTE_DEFAULT=1 ./scripts/install-local.sh
```

The release manifest and `loopx doctor` record whether promotion came from the
trusted-main path, a trusted GitHub archive, or an explicit override.

Use `loopx-canary` when you want to test the live checkout before making
it the default release snapshot. `loopx doctor` reports whether the
default wrapper points at a release snapshot, whether the canary wrapper points
at the live checkout, and whether the required skills are installed.

If an agent says it cannot find LoopX, repair in this order:

1. Ensure `~/.local/bin` is on `PATH`.
2. On a clean `origin/main`, re-run `~/loopx/scripts/install-local.sh`; from any
   other checkout, use `loopx-canary` until explicitly promoting it.
3. Run `loopx doctor`.
4. If a recurring automation is stale, regenerate it with
   `loopx heartbeat-prompt --thin --goal-id <goal-id> --agent-id <agent-id> --agent-scope "<scope>"`.

The reusable skills have intentionally narrow jobs:

| Skill | Use it for | Do not use it for |
| --- | --- | --- |
| `loopx-project` | Connecting projects, reading status/quota/history, diagnosing LoopX, generating heartbeat/review packets, and refreshing state. | Reading private project documents by default or replacing the CLI as source of truth. |
| `loopx-pr-review` | Running `/loopx-pr-review`, preserving the `loopx pr-review` packet, and guiding per-PR five-block reviews. | Approving, commenting on, merging, self-merging, or admin-bypassing a PR. |
| `loopx-doc-registry` | Registering durable project material and redacted authority-source metadata. | Copying raw doc bodies, internal URLs, or private comments into public repo docs. |
| `loopx-self-repair` | Repairing surprising control-plane behavior, stale projection, tiny turns, or contradictory guard payloads. | Lowering gates, guessing around missing authority, or committing private runtime state. |

Auto-research role guidance is worker-local: the visible worker launcher owns
the `loopx-auto-research` playbook after it has projected a role profile,
quota packet, and frontier item. It is not installed as a global LoopX skill.

Keep three layers separate:

- **Global skill behavior** belongs in `skills/` and is installed under
  `~/.codex/skills`.
- **Project state** belongs in `.loopx/`, `.codex/goals/`, and
  `~/.codex/loopx`; keep it local unless a sanitized fixture is
  intentionally committed.
- **Repository rules** belong in `AGENTS.md`, `CONTRIBUTING.md`, and public
  docs. They can constrain contributors and agents in this repository, but they
  should not silently become global skill policy for every project.

To disconnect only the current project from LoopX, use the project-local
uninstall command from that project root. It defaults to a dry-run preview and
refuses to operate directly on the shared global registry:

```bash
loopx uninstall-project
loopx uninstall-project --goal-id <goal-id> --archive-state --execute
```

`uninstall-project` removes the selected goal from `.loopx/registry.json` and
from the shared global registry only when the global entry's `source_registry`
points back to this project. It does not uninstall the LoopX CLI and does not
delete other projects' runtime history. Pass `--archive-state` to move this
project's `.codex/goals/<goal-id>/` directory under
`.loopx/archived-project-state/` instead of leaving it in place.

For manual cleanup of the reusable LoopX CLI and skill surfaces, remove only
the pieces you intend to drop:

```bash
rm -f ~/.local/bin/loopx ~/.local/bin/loopx-canary
rm -rf ~/.codex/skills/loopx-project \
       ~/.codex/skills/loopx-pr-review \
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

Treat live objective state and registries as local runtime data. Add these paths to
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
- a project-local registry and active objective state were created under
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

Generate a guarded Codex App heartbeat body. First-run Codex App onboarding
should install this body on a 3-minute bootstrap cadence unless the user
explicitly asks for a different interval; later waits should follow
`quota should-run.scheduler_hint`:

```bash
loopx heartbeat-prompt --thin --goal-id your-project-goal
```

For shared-control-plane agents, pass identity and scope in the automation
prompt, then let the agent soft-claim matching todos with a registered
`--claimed-by` id:

```bash
loopx register-agent --goal-id your-project-goal \
  --agent-id codex-main-control \
  --agent-id codex-side-bypass \
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
For a hierarchy-era registry, the next `quota should-run` and `upgrade-plan`
return a stable peer-runtime migration id, one heartbeat command per registered
peer, and a completion command. Update installed automations idempotently with
that migration id, then run the completion command once. Repeating the same
completion acknowledgement is a no-op, and later quota checks do not project
the completed migration again.

`register-agent` resolves the existing global entry's `source_registry`, writes
the project-local source of truth, and then syncs the shared global projection.
If `~/.codex/loopx/registry.global.json` is not writable, the command fails
before changing the source registry and reports a `global_registry_write_denied`
health error. Fix the shared runtime permission or run from a host that can
write the LoopX runtime root, then rerun the command. Use `--no-global-sync`
only when you intentionally want an explicit local-only connection.

Registered agents use `agent_model=peer_v1`: no identity is the durable leader.
Todo claims or task leases select the current owner. A repository-writing peer
uses an independent worktree when task or goal policy requires it, and
`workspace_guard` fails closed when that isolation is missing. Small
AGENTS-eligible validated changes may be self-merged with explicit LoopX
evidence. Higher-risk work should create an independent successor or an
ordinary `independent_handoff` with `action_kind=review`; use
`excluded_agents` only when executor separation must be enforced.

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
cd ~/loopx/apps/presentation/dashboard
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

See [apps/presentation/dashboard/README.md](../../apps/presentation/dashboard/README.md).

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
- user-specific active objective state and local registries;
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
python3 examples/control_plane/todo-cli-smoke.py
python3 examples/control_plane/todo-lifecycle-cli-smoke.py
python3 examples/control_plane/quota-contract-smoke.py
python3 examples/control_plane/review-packet-cli-smoke.py
python3 examples/benchmark-run-v0-append-cli-smoke.py
git diff --check
```

For dashboard work:

```bash
cd apps/presentation/dashboard
npm install
npm run build
npm run smoke:demo-readiness
```

For release-promotion readiness:

```bash
python3 examples/canary/canary-promotion-readiness-smoke.py
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
- [Long-task cadence hint](../long-task-cadence-policy.md)
- [Public/private boundary](../public-private-boundary.md)
- [Benchmark developer workflow](../benchmark-developer-workflow.md)
- [Public launch narrative draft](../outreach/public-launch-narrative-draft.md)
- [Xiaohongshu launch draft](../outreach/xiaohongshu-launch-draft.md)
- [Dashboard status contract](../status-data-contract.md)
- [Codex peer task orchestration](../codex-subagent-orchestration.md)
- [Benchmark long-run design](../research/long-horizon-agent-benchmarks/codex-cli-long-run-benchmark-design.md)

## Command Reference

New users should start with the
[Newcomer command path](newcomer-command-path.md). The catalog below is
reference material for operators and contributors who already know which path
they are debugging or extending.

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
uninstall-project       disconnect the current project without removing other projects
sync-global             merge project registry into the global registry
check                   run contract and public/private boundary checks
```

Use `loopx commands` for the grouped CLI reference, `loopx <command> --help`
for command-specific flags, or `man loopx` for the installed operator manual.

## Repository Quality Guard

This repository should stay readable to a new contributor. Treat these as
periodic maintainer checks:

- the README first screen explains the product before internal operations;
- quick start commands still run on a clean checkout;
- live local state is not committed;
- public/private scan is clean before docs or examples are published;
- docs linked from the README still exist and describe current CLI behavior;
- smoke commands cover the highest-risk control-plane contracts.
