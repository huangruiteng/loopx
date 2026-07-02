# Auto-Research Command Path

This guide is the shortest operator path for running the LoopX auto-research
demo from a clean workspace. It explains what to run, which visible digital
employees appear, what artifacts to inspect, and how to stop or take over.

Use the deeper showcase and protocol docs only after this path is clear:

- [Decentralized auto-research showcase](../product/decentralized-auto-research-showcase.md)
- [auto_research_role_state_machine_v0](../reference/protocols/auto-research-role-state-machine-v0.md)
- [auto_research_role_profile_v0](../reference/protocols/auto-research-role-profile-v0.md)

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

The fastest honest positive check is the worker-loop E2E path. It seeds a fresh
demo-local LoopX goal, lets role-compatible workers read quota/frontier state,
complete todo-backed turns, append public rollout evidence, and report the
measured gain. It is intentionally small and still does not claim that visible
Codex lanes authored the research result unless a compact live evidence packet
is supplied.

To run the multi-round path and open visible panes through the normal
auto-research surface, use the human-facing command:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research demo-e2e \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute \
  --replace-existing
```

That command is the user-facing UX for a multi-round visible demo. It creates a
fresh isolated demo goal by default, runs the LoopX worker-loop, launches the
visible tmux lanes, and attaches to the session. Each tmux window should open as
a real interactive Codex CLI TUI role, not as a JSON/status stream. Generic
launcher internals stay inside LoopX; the operator does not need to know the
module or implementation path.

Visible Codex TUI panes default to the caller's current workspace, not to a
demo-local git worktree. The demo registry, runtime root, queue, and evidence
state stay isolated, but the first screen should not be a generated worktree
trust prompt. If you want an explicit scratch location, pass
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
  auto-research demo-e2e \
  --agent-id codex-side-bypass \
  --reasoning-effort high
```

When the dry-run looks right, run the multi-round positive path:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research demo-e2e \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute
```

That command opens and attaches to tmux by default. For JSON-only automation,
make the headless path explicit:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute \
  --headless
```

To start tmux panes but stay in the current shell, use `--no-attach`. Visible
panes default to the Codex CLI TUI. The pane-local `$LOOPX_PANE_LOOPX` wrapper
is for human-readable LoopX commands inside that TUI, and
`$LOOPX_PANE_LOOPX_JSON` is reserved for redirected machine artifacts. Raw JSON
should not be dumped into the first visible screen; future control surfaces can
render those artifacts separately.

Expected minimal E2E result:

- `execution_kind` is `loopx_worker_loop`;
- `result_source` is `loopx_worker_loop_public_evidence`;
- `worker_loop.executed_turn_count` is `4`;
- `worker_loop.selected_actions` is
  `write_research_contract`, `propose_hypothesis`, `run_dev_eval`,
  `run_holdout_eval`;
- `tonight_experience.coordination_pattern` is `decentralized_state_a2a`;
- `tonight_experience.dev_metric` is `4.0`;
- `tonight_experience.holdout_metric` is `4.5`;
- `tonight_experience.positive_result` is `true`;
- `visible_worker_proof.lane_authored_evidence_loaded` is `false` unless a
  compact lane evidence file is passed;
- visible launch controls stay separate from the research result and only prove
  that panes can be inspected, stopped, or retried.

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
  --agent-id codex-side-bypass \
  --lane-count 3 \
  --visible-lanes-accepted \
  --output ./live-codex-e2e-evidence.public.json \
  --execute
```

Then pass that compact evidence packet back to the E2E readback command:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --agent-id codex-side-bypass \
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

For an explicit visible demo command, `--launch-visible --attach` is still
accepted, but it is equivalent to the default `--execute` behavior:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --agent-id codex-side-bypass \
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

## 1. Preview The Research Pack

The quickstart starts read-only. It returns the research contract, protected
files that would be created, and the first runnable hypothesis.

```bash
loopx --format json auto-research quickstart \
  --agent-id codex-side-bypass
```

When the preview is acceptable, create the starter pack in the clean workspace:

```bash
loopx --format json auto-research quickstart \
  --agent-id codex-side-bypass \
  --output-dir auto_research_knn_pack \
  --execute
```

Expected artifacts:

- `auto_research_knn_pack/research_contract.json`
- `auto_research_knn_pack/solution_candidate.py`
- `auto_research_knn_pack/protected_eval.py`
- baseline and README files that describe the public-safe evaluation boundary

## 2. Inspect The Visible Employee Plan

The supervisor is a host launcher, not a leader agent. Start with the dry-run
packet and inspect it before launching Codex.

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-supervisor \
  --goal-id loopx-auto-research-knn \
  --workspace "$PWD"
```

The default visible digital employees are:

| Pane | Role | What it owns |
| --- | --- | --- |
| `codex-product-capability:research-curator` | Research curator | Keeps the research contract, protected boundary, metric, stop policy, evidence review, and operator gates explicit. |
| `codex-side-bypass:hypothesis-mapper` | Hypothesis mapper | Turns ideas into todo-backed hypotheses, successor links, and retirement rationale. |
| `codex-main-control:evidence-runner` | Evidence runner | Executes one selected hypothesis under an isolated attempt boundary when mutation is required and preserves scored or unscored evidence. |
| `codex-value-explorer:evidence-verifier` | Evidence verifier | Checks holdout/verification evidence, classifies claims, and keeps promotion boundaries explicit. |

Each Codex TUI role must route through its own quota/frontier/worker-turn path
inside the pane. The supervisor only makes those roles visible and interactive.
The panes share the same LoopX goal surface: registry, runtime root, frontier,
todo projection, and evidence graph. Do not move every pane into an unrelated
empty workspace; isolate only mutating evidence-runner attempts with a claimed
git worktree or equivalent execution boundary.
Visible Codex TUI panes should default to the caller's workspace or an explicit
user-owned scratch workspace. They should not default into the demo-local
control-plane repository or generated lane worktrees, because that exposes
workspace-trust prompts before the user sees the actual research roles.

For compatibility or product experiments, `--agent` can still name explicit
lanes, including a separate evidence-verifier lane.

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
  --goal-id loopx-auto-research-knn \
  --agent-id codex-product-capability \
  --agent-id codex-side-bypass \
  --agent-id codex-main-control \
  --max-rounds 3
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
  --goal-id loopx-auto-research-knn \
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
  --format json auto-research frontier --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass
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
