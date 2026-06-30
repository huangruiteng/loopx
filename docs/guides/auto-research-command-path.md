# Auto-Research Command Path

This guide is the shortest operator path for running the LoopX auto-research
demo from a clean workspace. It explains what to run, which visible digital
employees appear, what artifacts to inspect, and how to stop or take over.

Use the deeper showcase and protocol docs only after this path is clear:

- [Decentralized auto-research showcase](../product/decentralized-auto-research-showcase.md)
- [auto_research_role_state_machine_v0](../reference/protocols/auto-research-role-state-machine-v0.md)
- [auto_research_role_profile_v0](../reference/protocols/auto-research-role-profile-v0.md)

## Start From A Clean Workspace

Use a user-owned empty directory for the visible demo, while keeping LoopX state
in the normal shared control plane. This keeps research scratch files separate
from the LoopX repository but lets every lane read the same registry, quota,
todo, frontier, and rollout-event state.

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

## 0. Prove The Deterministic Positive Replay

The fastest positive check is a deterministic replay. It proves that the
starter pack, protected evaluator, public rollout evidence, board projection,
and acceptance packet can all produce the expected k-NN result. It is intentionally
fast and does not claim that live Codex lanes authored the research result.

To run the replay and open visible panes through the normal auto-research
surface:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute \
  --launch-visible \
  --launcher tmux \
  --workspace ./loopx-auto-research-demo \
  --create-workspace \
  --attach
```

That command is the user-facing UX for a replay-backed visible demo. Generic
launcher internals stay inside LoopX; the operator does not need to know the
module or implementation path.

If you want to inspect before opening visible Codex lanes, start with the
read-only dry-run. It tells the operator which command will run the
deterministic positive replay:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass \
  --reasoning-effort high
```

When the dry-run looks right, run the deterministic positive replay:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute
```

Expected deterministic replay result:

- `execution_kind` is `deterministic_replay`;
- `result_source` is `generated_quickstart_pack_protected_eval_replay`;
- `replay_result.dev_metric` is `4.0`;
- `replay_result.holdout_metric` is `4.5`;
- dev and holdout exactness are both `true`;
- `protected_scope_clean` is `true`;
- the board is rollout-backed and has at least one promotion candidate;
- `acceptance.ready_for_real_launch` is `true`, meaning the visible launch
  controls and public-safe board are ready for operator rehearsal.

Truth boundary:

- `live_codex_e2e.executed` is `false`;
- `live_codex_e2e.claim_allowed` is `false`;
- `live_codex_e2e.evidence_source` is `not_collected_from_codex_lane_output`;
- `acceptance.ready_for_real_launch` does not mean live Codex lanes already
  produced the positive k-NN evidence;
- `--launch-visible` proves visible panes can start, but pane startup alone is
  not a live Codex research result.

To claim a live Codex lane-authored E2E result, first let the visible lane that
appended evidence capture the compact public-safe live proof:

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

Then pass that compact evidence packet to the E2E acceptance command:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute \
  --live-evidence ./live-codex-e2e-evidence.public.json
```

The capture helper requires `source: live_codex_lane_output`, matching goal and
agent, accepted visible lanes, lane-authored evidence appended to LoopX state,
and zero raw logs, private artifacts, credentials, or local absolute paths in
the payload. Without this packet,
`live_codex_e2e.claim_allowed` stays `false`.

For a full visible demo after an explicit replay step, add the visible lane
launcher:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
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

Each pane must route through its own quota/frontier/bootstrap path. The
supervisor only makes those panes visible. The panes share the same LoopX
goal surface: registry, runtime root, frontier, todo projection, and evidence
graph. Do not move every pane into an unrelated empty workspace; isolate only
mutating evidence-runner attempts with a claimed git worktree or equivalent
execution boundary.

For compatibility or product experiments, `--agent` can still name explicit
lanes, including a separate evidence-verifier lane.

## 3. Render The Acceptance Packet

Use the acceptance packet before a live rehearsal. It tells the user what must
be visible and what remains unsafe.

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research acceptance \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass
```

Accept the demo only when:

- the board/frontier is read-only or rollout-backed;
- the supervisor dry-run shows no hidden state write, quota spend, credential
  access, raw-log read, or session-file read;
- every lane has its own quota and frontier command before Codex starts;
- attach and stop controls are visible.

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

On macOS without tmux, use visible terminal windows instead:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  auto-research demo-supervisor \
  --goal-id loopx-auto-research-knn \
  --workspace "$PWD" \
  --execute \
  --launcher terminal
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
  --format json auto-research frontier --goal-id loopx-auto-research-knn
loopx --registry "$LOOPX_REGISTRY" --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research board --goal-id loopx-auto-research-knn
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
