# Auto-Research Command Path

This guide is the shortest operator path for running the LoopX auto-research
demo from a clean workspace. It explains what to run, which visible digital
employees appear, what artifacts to inspect, and how to stop or take over.

Use the deeper showcase and protocol docs only after this path is clear:

- [Multi-agent product recipe](multi-agent-product-recipe.md)
- [Decentralized auto-research showcase](../product/decentralized-auto-research-showcase.md)
- [auto_research_role_state_machine_v0](../reference/protocols/auto-research-role-state-machine-v0.md)
- [auto_research_role_profile_v0](../reference/protocols/auto-research-role-profile-v0.md)

Implementation boundary: auto-research is a thin preset over the generic
multi-agent kernel. `loopx/capabilities/auto_research/preset.py` owns only the
research roles, handoff hints, metric/evidence loop defaults, and seed todo
phrasing. The generic kernel owns the real Codex TUI panes, pane-local A2A
tick, workspace/trust-safe launch, todo/evidence/status protocol, and compact
human status. The developer-facing recipe proof also follows that boundary:
`preset.py` calls the generic `multi_agent.recipe` helper instead of defining
decentralized A2A proof mechanics itself.
Use the [multi-agent product recipe](multi-agent-product-recipe.md) when a new
product wants to copy the pattern without copying auto-research code.

## Promotion Decision

The validated visible proof is promoted into this existing command path, not
into a second auto-research runner. The public recipe remains:

- the operator runs one command;
- the user layer supplies only topic, objective, rounds, reasoning effort, and
  optional role overrides;
- the auto-research preset supplies research roles, handoff hints, seed todos,
  and evidence defaults;
- the generic multi-agent kernel supplies runner, wake, pane-local tick, status,
  attach, retry, and stop mechanics.

A visible proof is ready for this path only when the configured roles open as
real interactive Codex CLI panes, the fixed-prompt wake causes each pane to run
its local A2A tick, role output is summarized through LoopX todo/evidence/status
artifacts, and any live evidence packet is compact and public-safe. The proof
must not depend on raw logs, private artifacts, credentials, local absolute
paths, or a product-specific launcher hidden inside the auto-research preset.

## User Contract Entrypoint

The smallest user-facing auto-research contract is one open question:

```bash
loopx auto-research "<open question>"
```

This command does not launch panes or claim that research has been completed.
It renders the fixed contract the visible multi-agent run must satisfy:

- `research_brief`: what has been read, what has not been read, and the claim
  boundary;
- `action_plan`: P0/P1/P2 work, capped at five todos;
- `evidence_refs`: code, docs, benchmarks, issues, and pull requests;
- `next_executable_step`: whether the next step can run automatically;
- `gate`: the exact user judgment needed before crossing a boundary.

This keeps the user layer and the auto-research preset thin. The user supplies
one open question; auto-research supplies a fixed output contract; the generic
kernel owns the runner, real Codex TUI panes, pane-local A2A tick, and
todo/evidence/status protocol.

The contract also includes the next one-command launch surface:

```bash
loopx auto-research start "<open question>" --execute
```

Without `--execute`, `start` returns the same contract-anchored runner packet as
a dry-run preview. With `--execute`, it creates an isolated research frontier
and starts the visible Codex TUI lanes through the generic multi-agent kernel.
The launcher then broadcasts the fixed pane-local A2A wake prompt so each pane
runs its own `$LOOPX_PANE_A2A_TICK` against LoopX quota/frontier state and writes
compact public evidence before the operator takes over. This is still
decentralized A2A, not a workflow driver: the broadcaster does not select todos,
run worker turns, or write LoopX state.
The launcher pre-tick summary is prior evidence for the pane to read, not a
skip gate for the fixed wake. Later wake rounds still ask each role to check its
own LoopX state and tick when runnable work remains.

The user still only supplies one open question; agent ids, pane-local tick
commands, evidence schemas, and runner wiring stay inside the kernel. Pass
`--attach` when you want to skip the default evidence-first wake and immediately
enter the tmux session.
By default, visible panes open in a stable user-owned workspace under
`~/loopx-auto-research/<run>/visible-workspace` so the first screen does not
land in a generated temp directory. Pass `--workspace` to choose a different
scratch directory.

## Start From A Clean Workspace

Use a user-owned directory for the visible demo, while keeping LoopX state in
the normal shared control plane. This keeps research scratch files separate
from the LoopX repository but lets every lane read the same registry, quota,
todo, frontier, and rollout-event state. For the smoothest first run, start
from a directory the Codex CLI already trusts, or from a plain non-git demo
directory you own.

```bash
mkdir -p loopx-auto-research-demo
cd loopx-auto-research-demo
export LOOPX_REGISTRY="$HOME/.codex/loopx/registry.global.json"
export LOOPX_RUNTIME_ROOT="$HOME/.codex/loopx"
```

Install or repair the CLI when needed:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

## 0. Prove The Worker-Loop Positive Path

The fastest honest positive check is the one-question start path. It seeds a
fresh demo-local LoopX goal, lets role-compatible workers read quota/frontier
state, opens visible Codex TUI panes by default, and keeps the first output tied
to the fixed user contract. It is intentionally small and still does not claim
that visible Codex lanes authored the research result unless a compact live
evidence packet is supplied.

To run the normal human-facing path and open visible panes:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research start "How should we evaluate autonomous research agents?" \
  --execute \
  --replace-existing
```

That command is the user-facing UX for auto-research. It creates a fresh
isolated demo goal by default, launches the visible tmux lanes, broadcasts the
fixed decentralized A2A wake prompt, and records compact wake/tick evidence
before user takeover. Each tmux window should open as a real interactive Codex
CLI TUI role, not as a JSON/status stream. Generic launcher internals stay
inside LoopX; the operator does not need to know `demo-e2e`, agent ids, wake
flags, or implementation paths.

Visible Codex TUI panes default to a stable
`~/loopx-auto-research/<run>/visible-workspace`, not to a demo-local git
worktree or generated temp directory. The demo registry, runtime root, queue,
and evidence state stay isolated, but the first screen should not be a
generated worktree trust prompt. If you want an explicit scratch location, pass
`--workspace "$HOME/loopx-auto-research-demo" --create-workspace`; avoid
pointing `--workspace` at the demo-local control-plane directory.

When this demo is being advanced from a broader productization goal such as
`loopx-meta`, do not change `--goal-id` to that meta goal. Omit `--goal-id` for
an isolated demo goal, or pass a purpose-built research frontier goal when you
want visible lanes to read an existing target. Add `--tracking-goal-id loopx-meta`
only when the caller needs metadata that says which parent goal is tracking the
product work; tracking metadata never drives the visible lane frontier.

If you want to inspect before opening visible Codex lanes, start with the
read-only dry-run. It tells the operator which command will run the
multi-round positive path:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research start "How should we evaluate autonomous research agents?"
```

When the dry-run looks right, run the multi-round positive path:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research start "How should we evaluate autonomous research agents?" \
  --execute
```

That command starts visible panes, wakes each pane with the fixed
decentralized A2A prompt, and keeps the current shell available for the compact
JSON result. To attach immediately instead, pass `--attach`; that means
operator takeover first and skips the default evidence-first wake:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research start "How should we evaluate autonomous research agents?" \
  --execute \
  --attach
```

For JSON-only automation, make the headless path explicit:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research start "How should we evaluate autonomous research agents?" \
  --execute \
  --headless
```

Visible panes default to the Codex CLI TUI and the product start path stays in
the current shell after recording wake evidence. The pane-local
`$LOOPX_PANE_LOOPX` wrapper is for human-readable LoopX commands inside that TUI, and
`$LOOPX_PANE_LOOPX_JSON` is reserved for redirected machine artifacts. Raw JSON
should not be dumped into the first visible screen; future control surfaces can
render those artifacts separately.

Expected minimal E2E result:

- `execution_kind` is `loopx_worker_loop`;
- `result_source` is `loopx_worker_loop_public_evidence`;
- `worker_loop.executed_turn_count` is at least `6`;
- `worker_loop.selected_actions` is
  `write_research_contract`, `propose_hypothesis`, `run_dev_eval`,
  `summarize_evidence`,
  `run_holdout_eval`, and `write_evaluation_summary`;
- `tonight_experience.coordination_pattern` is `decentralized_state_a2a`;
- `tonight_experience.dev_metric` is `4.0`;
- `tonight_experience.holdout_metric` is `4.5`;
- `tonight_experience.positive_result` is `true`;
- `visible_worker_proof.lane_authored_evidence_loaded` is `false` unless a
  compact lane evidence file is passed;
- visible launch controls stay separate from the research result and only prove
  that panes can be inspected, stopped, or retried.

Maintainer acceptance for this path is:

```bash
python3 examples/auto-research-layered-e2e-acceptance-smoke.py
```

That smoke checks the shortest layered contract, the visible Codex TUI runner
contract, todo handoff, public evidence writes, and two metric-improving rounds
without making the auto-research preset own generic runner machinery.

Concrete KNN proof command:

```bash
loopx --format json auto-research start \
  "How can the KNN baseline improve holdout metric?" \
  --preset knn-demo \
  --execute \
  --headless \
  --worker-loop-rounds 4 \
  --demo-run-id knn-multiround-proof
```

This is the maintainer proof for state-mediated continuation, not the visible
operator experience. The matching visible path is still the one-command start:

```bash
loopx auto-research start \
  "How can the KNN baseline improve holdout metric?" \
  --preset knn-demo \
  --execute
```

`--preset knn-demo` is the public signal that the baseline metric, holdout
split, and protected metric scope come from the built-in KNN demo fixture. The
open question names the research topic; it does not smuggle the baseline into
the system through natural-language inference.

The validated KNN run demonstrates that the second round is carried by LoopX
state and role-declared successor todos: the evidence runner owns
`run_holdout_eval` after dev evidence is summarized, and the verifier owns
`write_evaluation_summary` after holdout evidence exists. A generic continuation
projector is not required for this preset; the role skill declares the next todo
target and the kernel validates the target agent before writing state.

KNN proof acceptance:

- baseline metric is `1.0`;
- dev metric is `4.0`;
- holdout metric is `4.5`;
- selected actions include `run_dev_eval`, `run_holdout_eval`, and
  `write_evaluation_summary`;
- the coordination pattern remains `decentralized_state_a2a`;
- the public boundary records no raw logs, private artifacts, credentials, or
  local absolute paths.

Remaining boundary: the headless KNN proof validates the LoopX todo/state
multi-round path. It is not, by itself, a claim that visible Codex panes authored
the research result. That higher claim still needs compact lane-authored evidence
or a visible readiness packet loaded through the public evidence path below.

Evidence boundary:

- `visible_worker_proof.visible_lanes_launched` reports whether panes were
  started;
- `visible_worker_proof.visible_lanes_accepted` reports whether the launcher
  observed healthy panes;
- `visible_worker_proof.lane_authored_evidence_loaded` reports whether compact
  lane evidence was provided;
- the default visible launch proves panes can start, but pane startup alone is
  not a live Codex research result.

To attach compact lane-authored evidence to the E2E result, first let the
visible lane that appended evidence capture the public-safe evidence summary:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research capture-live-evidence \
  --packet ./evidence.public.json \
  --append-result ./append-result.public.json \
  --agent-id research-executor \
  --lane-count 4 \
  --visible-lanes-accepted \
  --output ./live-codex-e2e-evidence.public.json \
  --execute
```

Then pass that compact evidence packet back to the E2E readback command:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --agent-id auto-research-operator \
  --reasoning-effort high \
  --execute \
  --headless \
  --live-evidence ./live-codex-e2e-evidence.public.json
```

The capture helper requires `source: live_codex_lane_output`, matching goal and
agent, accepted visible lanes, lane-authored evidence appended to LoopX state,
and zero raw logs, private artifacts, credentials, or local absolute paths in
the payload. With this packet, the E2E result includes `live_worker_evidence`
and flips `visible_worker_proof.lane_authored_evidence_loaded=true`.

For maintainer-level rehearsal, `demo-e2e --launch-visible --attach` is still
accepted as a lower-level command. It is not the user-facing product path; the
short `auto-research start "<open question>" --execute` command owns the
default evidence-first wake behavior.

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --agent-id auto-research-operator \
  --reasoning-effort high \
  --execute \
  --launch-visible \
  --launcher tmux \
  --attach
```

If a previous visible rehearsal is still alive, retry with
`--replace-existing` or stop it first:

```bash
tmux kill-session -t loopx-auto-research
```

The one-command E2E path must not record raw logs, private artifacts,
credentials, or local absolute workspace paths. It writes only public rollout
evidence through the normal LoopX runtime root when `--execute` is present.

## 1. Preview The One-Command Start

The default user path starts from one open question and previews the visible
Codex TUI lane packet without starting processes.

```bash
loopx --format json auto-research start \
  "How should we evaluate autonomous research agents?"
```

When the preview is acceptable, launch the visible lanes:

```bash
loopx --format json auto-research start \
  "How should we evaluate autonomous research agents?" \
  --execute
```

The visible lanes use the same tiny kernel path as the maintainer E2E proof:
frontier/todo selection, role-local worker-turn, rollout append, and compact
live evidence. Raw JSON is written only to local artifacts. Lower-level
`demo-e2e` commands remain available for maintainers, but they are not the
user-facing entrypoint.

## 2. Inspect The Visible Employee Plan

The supervisor is a host launcher, not a leader agent. Start with the dry-run
packet and inspect it before launching Codex.

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-supervisor \
  --goal-id loopx-auto-research-demo \
  --workspace "$PWD"
```

The default visible digital employees are:

| Pane | Role | What it owns |
| --- | --- | --- |
| `research-curator:research-curator` | Research curator | Keeps the research contract, protected boundary, metric, stop policy, evidence review, and operator gates explicit. |
| `hypothesis-proposer:hypothesis-proposer` | Hypothesis proposer | Turns ideas into todo-backed hypotheses, successor links, and retirement rationale. |
| `research-executor:research-executor` | Research executor | Executes selected hypotheses under an isolated attempt boundary when mutation is required and preserves scored or unscored evidence. |
| `evaluator-promoter:evaluator-promoter` | Evaluator/promoter | Checks holdout/verification evidence, classifies claims, and keeps promotion boundaries explicit. |

Each Codex TUI role must route through its own quota/frontier/worker-turn path
inside the pane. The supervisor only makes those roles visible and interactive.
The panes share the same LoopX goal surface: registry, runtime root, frontier,
todo projection, and evidence graph. Do not move every pane into an unrelated
empty workspace; isolate only mutating research-executor attempts with a claimed
git worktree or equivalent execution boundary.
Visible Codex TUI panes should default to the caller's workspace or an explicit
user-owned scratch workspace. They should not default into the demo-local
control-plane repository or generated lane worktrees, because that exposes
workspace-trust prompts before the user sees the actual research roles.

For compatibility or product experiments, `--agent` can still name explicit
lanes, including a separate evaluator-promoter lane.

## 3. Run The Worker Loop

The visible panes should do work through the same CLI path a heartbeat worker
uses: each turn re-reads quota, frontier, todo projection, and rollout evidence
before writing anything.
The user-facing terminal should first show the Codex CLI TUI. Role progress,
selected todo, action, and blocker summaries should appear as normal Codex
interaction when the role runs LoopX commands; raw JSON belongs in
`.public.json` artifacts, not on the first visible screen.

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research worker-loop \
  --goal-id loopx-auto-research-demo \
  --agent-id research-curator \
  --agent-id hypothesis-proposer \
  --agent-id research-executor \
  --agent-id evaluator-promoter \
  --max-rounds 4
```

When the dry-run shows the selected lane work is safe, add `--execute` and
`--complete-selected-todo`. This is the smallest real multi-agent loop: it is
state-mediated, not a hidden leader workflow.

## 4. Launch A Visible Rehearsal

Use tmux when available so the user can watch several Codex CLI TUIs in one
place:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research demo-supervisor \
  --goal-id loopx-auto-research-demo \
  --workspace "$PWD" \
  --execute \
  --launcher tmux \
  --attach
```

The user can stop a tmux rehearsal with:

```bash
tmux kill-session -t loopx-auto-research
```

Or take over a lane by attaching, interrupting the pane, and continuing from
the visible prompt:

```bash
tmux attach -t loopx-auto-research
```

## 5. Inspect Progress

Useful read-only checks:

```bash
loopx --registry "$LOOPX_REGISTRY" --runtime-root "$LOOPX_RUNTIME_ROOT" status
loopx --registry "$LOOPX_REGISTRY" --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research frontier --goal-id loopx-auto-research-demo \
  --agent-id auto-research-operator
```

The demo is healthy when the user can identify the active hypothesis, see which
lane owns the next transition, inspect evidence or retry rationale, and stop or
take over before any private material, credential, protected file, or
production action is needed.

## Boundary

This command path is for local, visible, user-takeover rehearsals. It is not a
claim that a research result is production-ready, not a public first-screen
approval, and not permission to publish private evidence. Promotion still
requires rollout-backed evidence, held-out checks when relevant, and normal
LoopX gate/writeback rules.
