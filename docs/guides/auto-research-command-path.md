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

## 0. Prove The Multi-Round Positive Path

The fastest positive check is a lightweight multi-round research kernel. It
tries the baseline and candidate hypotheses on dev, selects the improved
candidate, validates it on holdout, appends public rollout evidence, and reports
the measured gain. It is intentionally small and still does not claim that
visible Codex lanes authored the research result unless a compact live evidence
packet is supplied.

To run the multi-round path and open visible panes through the normal auto-research
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

That command is the user-facing UX for a multi-round visible demo. Generic
launcher internals stay inside LoopX; the operator does not need to know the
module or implementation path.

When this demo is being advanced from a broader productization goal such as
`loopx-meta`, do not change `--goal-id` to that meta goal. Keep
`--goal-id loopx-auto-research-knn` so the visible lanes read the positive
auto-research frontier. Add `--tracking-goal-id loopx-meta` only when the
caller needs metadata that says which parent goal is tracking the product work;
tracking metadata never drives the visible lane frontier.

If you want to inspect before opening visible Codex lanes, start with the
read-only dry-run. It tells the operator which command will run the
multi-round positive path:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass \
  --reasoning-effort high
```

When the dry-run looks right, run the multi-round positive path:

```bash
loopx --registry "$LOOPX_REGISTRY" \
  --runtime-root "$LOOPX_RUNTIME_ROOT" \
  --format json auto-research demo-e2e \
  --goal-id loopx-auto-research-knn \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute
```

Expected minimal E2E result:

- `execution_kind` is `minimal_research_kernel`;
- `result_source` is `deterministic_protected_eval_kernel`;
- `claim_summary.status` is `kernel_precheck_only`;
- `claim_summary.live_worker_claim_allowed` is `false`;
- `research_loop.dev_round_count` is `2`;
- `research_loop.evidence_event_count` is `3`;
- `research_loop.live_codex_lane_authored` is `false`;
- `research_loop.kernel_event_trace` contains the actual protected-eval
  dev/dev/holdout events, not synthetic worker panels;
- `research_loop.selected_hypothesis_id` is `hyp_partial_selection`;
- `research_loop.dev_gain_over_baseline` is `3.0`;
- `research_loop.holdout_gain_over_baseline` is `3.5`;
- `multiround_gain_acceptance.round_count` is `2`;
- `multiround_gain_acceptance.hypotheses_attempted` lists the seed
  full-sort hypothesis and the selected partial-selection hypothesis;
- `multiround_gain_acceptance.evidence_events_appended` is `3`;
- `multiround_gain_acceptance.final_gain_over_seed` is `3.5`;
- `multiround_gain_acceptance.why_better` explains why the final result beats
  the seed/baseline without reading raw logs;
- `protected_eval_result.dev_metric` is `4.0`;
- `protected_eval_result.holdout_metric` is `4.5`;
- dev and holdout exactness are both `true`;
- `protected_scope_clean` is `true`;
- the board is rollout-backed and has at least one promotion candidate;
- `acceptance.ready_for_real_launch` is `true`, meaning the visible launch
  controls and public-safe board are ready for operator rehearsal.

Truth boundary:

- `live_codex_e2e.executed` is `false`;
- `live_codex_e2e.claim_allowed` is `false`;
- `live_codex_e2e.evidence_source` is `not_collected_from_codex_lane_output`;
- `claim_summary.can_claim` is limited to
  `protected_eval_kernel_positive_precheck`;
- `claim_summary.cannot_claim` includes
  `visible_codex_workers_authored_result`;
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

With a valid compact live evidence packet, `live_codex_e2e.claim_allowed`
means only that a live lane-authored dev claim may be projected. Holdout and
promotion claims stay blocked by default: `holdout_claim_allowed=false`,
`promotion_claim_allowed=false`, and the live `holdout_metric` is redacted from
the claim projection. The companion `claim_summary` switches to
`live_worker_dev_evidence_ready`, with `claim_basis=live_codex_lane_output`.
To project a live holdout or promotion claim, the compact
evidence must carry explicit public-safe `claim_authority`, such as
`separate_heldout_live_evidence` or `owner_approval`.

For a full visible demo after an explicit multi-round run, add the visible lane
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
