# Exploration Result Layer

Status: prototype adapter contract v0.

Long-running exploration goals (for example a Codex loop studying an external
software domain through LoopX) produce results that operators want to read as
a topology, not as an agent action log: what has been explored, where the loop
is blocked and why, and what was found.

Role boundaries, in one breath:

- **Explore capability (this layer)** owns the structured exploration
  EVIDENCE: a compact, public-safe, append-only node/edge/finding/blocked-
  frontier log plus bounded read-model projections. This is research
  evidence, not a display artifact -- its downstream consumers are vision
  checkpoints, replanning, successor-todo generation, and user gates first,
  and presentation second. That is why the log lives under
  `loopx/capabilities/explore/`, not under `loopx/presentation/`.
- **Presentation** renders the public-safe explore projection into operator
  surfaces (Mermaid graph, Feishu/Lark Base rows, cards). The reusable
  display implementation lives in
  `loopx.presentation.sinks.lark.explore_results`; the facade under
  `loopx.capabilities.lark` stays intentionally thin, and new display
  behavior must not be added there.
- **Value connectors** remain the boundary for external signal input,
  permissions, and source authority. The Lark explore sink is display only
  and must never be conflated with a connector.

## State Contract

- Reads: `goals/<goal-id>/explore-result-log.jsonl` under the LoopX runtime
  root (`loopx_explore_result_event_v0` events appended by `loopx explore
  node|edge|finding`). Presentation sinks may additionally read local display
  config such as `.loopx/lark-explore.json`.
- Writes: the explore result log (append-only), the local board config
  (`loopx_lark_explore_local_config_v0`, including the result-id to Lark
  record-id map) from the presentation sink, and, only with `--execute`, Lark
  Base rows through `lark-cli`.
- Write owner: the operator-triggered CLI. Agents append result events; only
  an explicit `--execute` run touches the shared Lark surface.
- Proof of transition: every sync payload lists the exact `lark-cli` commands
  it ran or would run, per-row record ids, and the refreshed record map that
  the next sync reuses.

## Result Event Model

One JSONL event per line, `loopx_explore_result_event_v0`, three kinds:

| Kind | Identity | Purpose |
| --- | --- | --- |
| `node` | `--node-id` (or derived from title) | An explored question, area, hypothesis, experiment, or artifact. Status: `open`, `exploring`, `blocked` (requires `--blocked-reason`), `resolved`, `dead_end`. Re-record the same id to update it. |
| `edge` | derived from `from/type/to` | Typed relation: `subtopic_of`, `depends_on`, `answers`, `supports`, `refutes`, `leads_to`. |
| `finding` | `--finding-id` (or derived from title) | A discovery, optionally attached to a node. Status: `tentative`, `confirmed`, `refuted`. |

Events are sanitized at record time: compact text limits, credential-like
markers rejected, and evidence refs must be public relative refs or opaque ids
(for example `ov:doc:lustre-survey`), never local absolute paths.

## Projection And Topology

`loopx explore summary` folds the log into
`loopx_explore_result_projection_v0`: latest state per node/edge/finding,
status counts, the blocked list with reasons, the exploring frontier, a
parent/`subtopic_of` topology tree, and Mermaid flowchart source.
`loopx explore graph --graph-format mermaid|json [--out <file>]` exports the
topology for a Feishu doc, whiteboard, or any Mermaid renderer.

Focused exports are bounded evidence views, not executive decision views by
default. They preserve machine-oriented node identity, edge semantics, and
ancestor context while reducing the amount of canonical topology rendered:

```bash
loopx explore graph \
  --goal-id <id> \
  --status exploring \
  --status blocked \
  --tag executive \
  --graph-format mermaid \
  --out explore-focused-evidence.mmd
```

Repeated statuses match any requested status, repeated tags match any exact
requested tag, and the status and tag groups are combined with AND. Matching
nodes keep their ancestors by default so the focused graph retains explanatory
context; pass `--no-include-ancestors` for a leaf-only view. Filtering changes
only the graph export. It does not mutate the full result projection or the
Lark node, edge, and finding tables.

An owner-facing executive graph is a separate display projection over that
canonical evidence, not a second evidence source. Do not sync a full or focused
canonical export directly into an executive whiteboard merely because it is
smaller. The projection should compress the evidence into the decision roles
the operator needs to see:

- decision contract and primary metric;
- baseline and current incumbent;
- decisive negative or retired evidence;
- active work or capacity slots;
- material risk and guardrails;
- terminal decision gate;
- next decision or evidence gap.

Give the projection explicit node and edge budgets, stable references back to
canonical node ids, and a fail-fast guard that rejects accidental identity with
the canonical export. Before syncing, render it with the target renderer, run
geometry checks for overlap and text overflow, and visually inspect the actual
preview. After syncing, verify the remote source or digest matches the validated
projection. The canonical JSON and Nodes/Edges/Findings tables remain complete
and authoritative throughout this presentation step.

## Experimental Todo Branch Plan

`loopx explore todo-branch-plan` is a narrow experimental harness for
exploration goals that need to try several plausible next todos at once. It
uses a CPU branch-prediction analogy plus a DSpark-inspired scheduler: rank
open agent todos, estimate branch confidence and expected evidence units,
choose a confidence-scheduled verification prefix, select one `primary` branch
plus safe `speculative` branches, and reject branches whose declared write
scopes overlap an already-selected branch.

Accuracy note on the DSpark citation (arXiv:2607.05147): real DSpark truncates
a semi-autoregressive draft block at the first per-step confidence below a
fixed threshold, and uses the cumulative product of per-step confidences only
as a calibration diagnostic. The prefix-survival theta model here (survival
product x throughput curve) is a loopx-specific extension for *serially
dependent* todo chains. It must not be used to size independent parallel
worker lanes -- that misuse capped an early calibration run's treatment arm
at 5 of 10 lanes; worker plans now use `schedule_independent_lanes` instead.

The command is read-only and sits behind the same per-goal opt-in gate as
`worker-branch-plan` (see "Per-Goal Opt-In Gate" below): without
`explore_harness.enabled=true` on the goal's orchestration boundary it returns
a disabled packet, and `--width` is capped by `max_children` in addition to
its own ceiling. It does not claim todos, acquire leases, launch agents,
spend quota, or change the active state. Instead it emits a prediction
packet with:

- selected branches, confidence, hazards, and reason codes;
- a dry-run A/B estimate comparing baseline serial execution with the
  DSpark-style selected prefix (`ab_result.estimated_speedup_vs_baseline`);
- suggested `loopx todo claim` and `loopx task-lease acquire` commands for a
  human operator or registered peer runner to execute explicitly;
- the safety boundary that makes the packet experimental rather than a
  replacement for `quota should-run`.

An advancement todo may opt into typed result diagnostics by attaching one or
more explicit Explore node ids:

```bash
loopx todo add --goal-id <id> --role agent --text "Evaluate the rejected route" \
  --task-class advancement_task --explore-result-node-ref node_rejected_route
```

`todo-branch-plan` resolves only those explicit links. Its bounded
`typed_evidence_audit` reports linked node lifecycle, finding statuses,
relevant `supports`/`refutes` edges, unknown ids, and dead-end/refutation
hazards. The audit is diagnostic-only (`score_delta=0`) and cannot claim,
lease, launch, write state, or spend quota. Unlinked todos retain the prior
planner behavior. Repair a stale link by replacing it with another repeated
`--explore-result-node-ref`, or remove all links with
`loopx todo update ... --clear-explore-result-node-refs`.

Todos without declared write scopes are treated as speculative read or
coordination work by default, because many exploration tasks are read-only.
Use `--no-allow-unscoped-parallel` when the controller wants unknown scopes to
collapse back to single-branch execution.

## Experimental Worker Branch Plan

`loopx explore worker-branch-plan` is the worker-lane version of the same
experiment. It does not treat a branch as one todo. A worker branch is a
predicted lane containing a small bundle of LoopX todos, an objective slice,
required capabilities, write scopes, dependency hints, expected evidence,
confidence, and suggested claim/lease commands.

This command is read-only and opt-in per goal. It is designed to sit on top of
the existing LoopX harness, not beside it and not instead of it:

1. LoopX supplies the harness inputs: quota/status context outside this command,
   the open agent todo projection, explore result projection, ownership,
   capabilities, and write-scope metadata.
2. The experimental planner groups todos into worker-lane candidates and uses
   DSpark-style confidence/prefix/load scoring to pick a worker branch prefix.
3. Execution must return to the normal LoopX path: `quota should-run`,
   `todo claim`, `task-lease acquire`, worker execution, `explore node|edge|finding`,
   `refresh-state`, and `quota spend-slot`.

For goals that have opted in, the packet therefore contains
`harness_compatibility` and `boundary` fields: `replaces_loopx_runtime=false`,
`launches_workers=false`, and `claim_and_lease_are_suggested_only=true`; the
deny-by-default disabled packet carries the `boundary` block plus the opt-in
`required_contract` instead. The packet can be used by a controller or human
operator to decide which workers to start, but it cannot launch workers or
mutate the control plane on its own.

### Per-Goal Opt-In Gate

Both experimental planners — `todo-branch-plan` and `worker-branch-plan` —
are deny-by-default. The gate lives on the registered goal's `spawn_policy`,
the single writable source that the quota/status pipeline projects into
`quota should-run` as `goal_boundary.orchestration`. No other registry key is
honored: a second source would be an authorization surface invisible to the
quota boundary.

```yaml
# inside the registered goal entry
spawn_policy:
  spawn_allowed: false    # "allowed" is the accepted alias
  max_children: 3
  explore_harness:
    enabled: false        # default: both explore planners are disabled;
                          # must be boolean true — anything else fails closed
    profile: generic      # optional pin; overrides the CLI-requested profile
```

Use the incremental configuration path instead of editing the registry:

```bash
loopx configure-goal \
  --goal-id <id> \
  --explore-harness-enabled \
  --explore-harness-profile adaptive-resilient \
  --execute
```

This is analysis-only while spawn permission remains disabled. Use
`--no-explore-harness-enabled` to close the gate again, or
`--clear-explore-harness-profile` to let each planner request its own profile.
Preview without `--execute` shows the exact orchestration delta and preserves
unrelated `spawn_policy` keys.

The planner folds this boundary into an `orchestration_gate` section of the
packet and behaves as follows:

| Boundary state | Planner behavior |
| --- | --- |
| `enabled=false` (or goal unregistered / no boundary) | Explicit disabled packet with `required_contract`; no branches are emitted. |
| `enabled=true`, `spawn_allowed=false` | Read-only ranking and bundle analysis only; every `suggested_commands` list is emptied. |
| `enabled=true`, `spawn_allowed=true`, `max_children>0` | Suggested claim/lease commands are emitted, still dry-run only. |
| any enabled state | Lane width (`--width` / `--worker-width`) is capped by `max_children` in addition to the planner's own ceiling (`MAX_BRANCH_WIDTH` / `MAX_WORKER_LANES`); the binding cap is recorded in `orchestration_gate.width_cap_source`. |

`spawn_allowed=true` with `max_children=0` is treated as a contradiction and
degrades to the analysis-only state rather than granting capacity.

The gate is defense-in-depth for the planning surface, not a substitute for
runtime authority: permission, quota, gates, claims, leases, spend, and state
projection remain owned by the normal LoopX lifecycle regardless of the gate
state. `examples/explore-worker-plan-gate-smoke.py` covers the four states
for both planners, the `max_children` cap, and the CLI default-off path end
to end.

Use this worker-lane planner when the experiment is about dynamic branching:
several Codex workers exploring different routes, each route managing multiple
todos, then verified results merging back into the explore graph. Use
`todo-branch-plan` for the smaller micro-kernel case where the branch is just
one candidate todo.

### Adaptive Resilient Harness Profile

The `adaptive-resilient` worker harness profile captures the useful design
lessons from long-horizon exploration campaigns without copying an
experiment's incidental controls. It is not any single calibration run's
configuration made permanent. The profile keeps the parts that generalized well:

- independent-lane admission for lane count, where `--worker-width` is a
  ceiling and the planner may select fewer lanes -- but only for auditable
  reasons (queue exhaustion or measured interference), recorded per refusal
  in `admission_audit`. Expected evidence across parallel lanes is additive;
  the old cross-lane survival product treated independent worker processes as
  a serial speculative chain and structurally under-filled the width;
- value-first branch packing, where `--max-todos-per-branch` is a ceiling and
  branches are not padded just to look full;
- lane start staggering as runner guidance, because staggered launches reduced
  correlated infrastructure pressure;
- retry/backoff and infrastructure-family cooldown hints for repeated
  transient failures such as a provider service being unreachable;
- explicit A/B metadata so future runs can compare the profile against the
  priority-order baseline.

It deliberately does not control segment duration, does not force N=10, does
not saturate every available branch, and does not enable the earlier
coverage-floor calibration arm by default. Those remain runner or future-experiment decisions, not part of
the generalized harness design.

Retry/backoff and infrastructure cooldown are planner metadata for an external
runner; the generic runtime does not enforce them. Runtime results expose this
boundary explicitly instead of implying that selecting the profile activates a
hidden retry loop.

```text
loopx explore worker-branch-plan \
  --goal-id <id> \
  --harness-profile adaptive-resilient \
  [--worker-width <ceiling>] \
  [--max-todos-per-branch <ceiling>]
```

Use `--branch-fill-policy value-first` explicitly when you want the same
no-forced-fill behavior without the rest of the profile metadata. Use
`bundle-by-affinity` for the older compact grouping behavior.

### MoE Router Harness Profile

The `moe-router` profile treats worker-lane planning as MoE-style routing
under a fixed worker ceiling: task families (affinity keys such as
`scope:artifacts/<task>`) are the experts, todos are the routed tokens, and
lanes are just serving slots. It extends `adaptive-resilient` with a learned,
cross-epoch routing layer fed through `--router-state`:

- **Router state** (`loopx.capabilities.explore.router_state`, schema
  `loopx_explore_router_state_v0`): per-family EMAs of raw value rate
  (deliberately NOT novelty-discounted, so the estimator measures the
  environment rather than the router's own rerun policy), probe duration,
  acceptance rate, and infra failures, plus a global first-seen
  observation-key ledger that supplies each family's novelty prediction.
  The runner owns persistence and calls `observe_epoch` /`advance_epoch` at
  epoch boundaries -- the same cadence as the existing infra cooldown.
- **Routing score vs value bookkeeping** (the DeepSeek-V3 aux-loss-free
  invariant): each branch carries `routing_score = static score x
  (1 + UCB + coverage bonus + bias - infra penalty)` used ONLY for ordering,
  while `calibrated_confidence` (x family accept rate) and
  `novelty_adjusted_evidence_units` (x predicted novelty) feed admission and
  stay bias-free. The bias is a per-family scalar updated +/-gamma from
  coverage/novelty debt and surplus -- not load equality, which has no
  intrinsic value here -- with decay and clamping against windup.
- **Bundle length** is the faithful DSpark analog (arXiv:2607.05147): a
  lane's serial todo bundle is the draft block, and it truncates at the first
  todo whose calibrated acceptance confidence drops below
  `bundle_confidence_threshold` (`confident-prefix` fill policy). A
  wall-clock straggler guard (`bundle_straggler_factor` x median measured
  probe duration) caps the serial tail; it binds only on measured durations
  so cold-start defaults cannot silently force every bundle to length 1.
- **Load calibration**: pass the previous epoch's observed
  `{parallel_wall_minutes, max_branch_minutes, branch_count}` via
  `--load-profile` and lane admission prices measured interference through
  `calibrate_load_factor` instead of the hardcoded 0.2 prior.
- **Opportunistic expansion**: after calibration showed `moe-router` had better
  active-lane efficiency but wasted too many worker slots, the profile keeps
  the theta-peak core lanes and then admits additional positive-yield lanes up
  to a utilization floor. This is not saturated fill: each extra lane must
  clear an auditable independent lane-value floor, and refusals remain in
  `admission_audit`.

```text
loopx explore worker-branch-plan \
  --goal-id <id> \
  --harness-profile moe-router \
  --worker-width <ceiling> \
  [--router-state <router_state.json>] \
  [--load-profile <observed_profile.json>]
```

Without `--router-state` the profile still plans (router disabled, cold
static scoring); passing state to a non-router profile is ignored, which
keeps `adaptive-resilient` clean as the B-min ablation arm.

### Runtime Restart And Item Failures

`run_budget_arm` can write an atomic epoch-boundary checkpoint manifest.
Restart is opt-in: start an arm with `resumable=True` (or an explicit
`checkpoint_path`), then pass `resume=True` to restore completed epochs,
novelty keys, router state, catalog consumption,
cumulative metrics, coverage timestamps, and the next epoch. Missing, corrupt,
or runtime-incompatible manifests fail closed with a concrete `ValueError`;
loose rolling progress files are observability only and are never restart
authority.

Adapter exceptions default to the `record` item failure policy: the failed item
becomes a zero-value structured observation and independent queue lanes keep
running. Concurrency keys are released in every path. Pass
`item_failure_policy="fatal"`, or set the adapter's `item_failure_policy`
attribute to `"fatal"`, to retain exception propagation. These policies isolate
work-item failures; they do not implement the planner profile's retry/backoff or
cooldown guidance.

## Presentation Sink: Lark Mapping

| LoopX concept | Lark surface |
| --- | --- |
| node | `Nodes` table row keyed by `LoopX Result ID`; `Status=blocked` rows carry `Blocked Reason` |
| edge | `Edges` table row keyed by `LoopX Result ID`; `From Node Link` and `To Node Link` are linked-record cells pointing at `Nodes`, so the Base data model itself carries the topology |
| finding | `Findings` table row keyed by `LoopX Result ID`; latest event wins |
| row lineage | `Row Lifecycle`, `Supersedes`, `Superseded By`, `Source ID` columns |
| dashboard card | transport-free interactive card content from the same projection |

Record identity follows the Lark Kanban adapter contract: rows are matched by
the `LoopX Goal ID` + `LoopX Result ID` columns, remembered in the local
config as `result_records`, and the map is rebuilt from the remote table
before executed upserts.

The text `From Node` / `To Node` columns remain stable public ids for
automation and review, while the linked-record columns are the Feishu-native
graph substrate. A Base plugin, relationship-aware view, or Feishu dashboard
component can read those links directly; LoopX must not downgrade the graph
back to a screenshot-only artifact.

This sink is a presentation boundary, not a value connector. Value connectors
own external signal input, permissions, and source authority; presentation
sinks render public-safe explore projections for operators.

## CLI Surface

```text
loopx explore schema
loopx explore node --goal-id <id> --title <t> [--node-id ...] [--status ...] [--blocked-reason ...] [--parent ...]
loopx explore edge --goal-id <id> --from <node> --to <node> --type <edge-type>
loopx explore finding --goal-id <id> --title <t> [--node ...] [--status ...] [--confidence ...]
loopx explore summary --goal-id <id>
loopx explore graph --goal-id <id> [--graph-format mermaid|json] [--out <file>]
loopx explore todo-branch-plan --goal-id <id> [--agent-id <agent>] [--width 3]
loopx explore worker-branch-plan --goal-id <id> [--agent-id <agent>] [--harness-profile generic|adaptive-resilient|moe-router] [--worker-width 3] [--max-todos-per-branch 3] [--router-state <file>] [--load-profile <file>]
loopx explore feishu-setup [--base-url ...] [--execute]
loopx explore feishu-sync --goal-id <id> [--sink-visibility owner-only|shared] [--execute]
loopx explore feishu-card --goal-id <id> [--card-file <file>] [--message-id om_...]
```

`feishu-setup` and `feishu-sync` are dry-run unless `--execute` is set; the
dry-run payload contains the full command plan for review.

## Review Boundary

Rows and cards deliberately exclude raw agent transcripts, worker commands,
credentials, and local absolute paths. Evidence lives behind compact public
refs; the private material itself stays in the goal's normal local state or
memory backend. `--sink-visibility shared` additionally redacts private
links and external ids through the shared Kanban redaction rules before rows
leave the machine. Card content is build-only: sending or updating the actual
Lark message is the job of an approved gateway (bot or lark-cli) after the
operator permits the write.

## Validation

```bash
python3 examples/explore-result-layer-smoke.py
python3 examples/explore-harness-runtime-resume-smoke.py
```

The smoke proves the projection contract (folding, blocked reasons, tree,
Mermaid), record-time path rejection, dry-run default, idempotent second sync
by remembered record id, shared-visibility redaction, transport-free card
content, the experimental todo branch-plan packet, the adaptive resilient
worker harness profile, and the CLI surface against a temp registry, without
live Lark credentials. It additionally proves the worker-lane router
contracts: requested width is no longer silently clamped below the worker
ceiling, idle lanes are queue-exhaustion (not a cap) under independent-lane
admission, the routing bias reorders lanes without touching value
bookkeeping, confident-prefix bundles truncate at the calibrated threshold
and collapse for reject-heavy families, the router-state novelty ledger
dedupes across epochs while coverage debt accrues bias, and observed load
profiles calibrate admission through the CLI flags.
