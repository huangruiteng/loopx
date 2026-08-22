# Benchmark Toolkit

`benchmark-toolkit` is LoopX's built-in, provider-neutral surface for permission,
artifact, integrity, and reusable agent-runtime boundaries around benchmark
experiments. It does not own benchmark-family runners, result ledgers, or scoring
adapters.

## Source revision admission

A long-running campaign can keep launching from an old installed checkout after
the tracked branch advances. Pinning the source once at controller startup does
not prevent that drift. Immediately before each new benchmark admission, obtain
the current reference head through the runner's provider or network boundary,
then compare it with the clean local checkout and intended pin:

```bash
loopx benchmark source-revision-fence \
  --source-checkout /path/to/pinned-source \
  --expected-revision "$PINNED_REVISION" \
  --observed-reference-revision "$OBSERVED_REFERENCE_REVISION" \
  --require-admitted \
  --format json
```

The command succeeds only when all three identities match and the source root has
no tracked or untracked changes. Its compact receipt records equality, cleanliness,
and a stable reason code without recording the checkout path or any revision value.
Invalid input is also reduced to a path-free fail-closed receipt.

The fence is an admission boundary, not a live-run mutation mechanism. A run that
already passed the fence keeps its immutable revision even if the reference moves
later; the new head blocks only subsequent admissions until the runner installs and
pins an updated source. The caller owns the freshness and authority of the observed
reference value. This capability performs no fetch, provider API call, checkout,
install, process launch, score write, or submission.

## Native Codex Goal runtime

Benchmark adapters that use the Codex app-server Goal API should import
`loopx.capabilities.benchmark_toolkit.native_codex_goal`. The module provides the
real stdio JSON-RPC process transport, the ordered Goal transaction, terminal event
correlation, Goal-status polling across automatic continuation turns, and a
public-safe receipt. A runner supplies its environment, sandbox policy, task bridge,
and timeout; it should not copy the Goal state machine.

On Linux, a host-side runner may use `native_codex_isolation` to build the isolated
process command. Its synthetic root contains a read-only system runtime, fresh
`/proc`, `/run`, and `/tmp`, runner-created work children, one explicitly selected
task workspace at the returned `host-visible` alias, and an optional formal LoopX
profile at its verified absolute path. The surrounding host root, original task
path, ambient host `/tmp`, nested host mounts, symlinked work children, and
`/proc/1/root` escape path are absent. The helper requires unprivileged user, mount,
and PID namespaces plus `pivot_root` and fails closed when its roots overlap.

```python
from loopx.capabilities.benchmark_toolkit.native_codex_isolation import (
    build_native_codex_isolation_envelope,
    rebase_native_codex_loopx_workspace_state,
)

envelope = build_native_codex_isolation_envelope(
    executable="codex",
    process_args=["app-server", "--listen", "stdio://", "--enable", "goals"],
    work_dir=runner_work_dir,
    private_root=controller_private_root,
    workspace_source=task_workspace,
    profile_root=profile.root,
)
# If the selected workspace already contains LoopX control state, relocate its
# generated path references before launch and restore them after termination.
rebase_native_codex_loopx_workspace_state(
    task_workspace,
    source_root=task_workspace,
    target_root=envelope.workspace_alias,
)
# Pass envelope.process_command to probe_native_goal_process or
# run_native_goal_process_until_terminal, and use envelope.workspace_alias as cwd.
# In a finally block after the process terminates:
rebase_native_codex_loopx_workspace_state(
    task_workspace,
    source_root=envelope.workspace_alias,
    target_root=task_workspace,
)
```

The relocation helper is deliberately narrow: it rewrites only LoopX registries
and generated run-history JSON, JSONL, and Markdown under the selected workspace.
It validates every candidate before writing, updates files atomically, rejects
symlinked control-state paths, and leaves task files, model output, trajectories,
verifier evidence, and arbitrary workspace prose untouched. This keeps formally
installed LoopX state readable after the temporary `host-visible` alias disappears.
The two canonical registries form one consistency boundary: both absent means no
control state, while only one present fails closed. If an abrupt process kill skips
the reverse rewrite, a subsequent launch using the same deterministic work
directory first recovers stale alias references.

The profile bind is writable because Codex and an installed LoopX release may need
runtime state. It must therefore be a per-run profile or a runner-restored pinned
snapshot, never ambient state shared across trials.

This is a filesystem/process envelope, not a complete benchmark sandbox. It grants
no model credential, task-command bridge, shell-network policy, evaluator denial,
cross-trial denial, verifier ordering, upload, submission, or scoring authority.
The runner must still attest those boundaries independently. Platforms without the
required Linux namespace primitives must use an equivalent runner-owned isolation
boundary instead of silently falling back to the ambient host.

The runnable source example is
[`benchmark/deepswe/run_native_codex_goal.py`](../../../benchmark/deepswe/run_native_codex_goal.py).
Its `--preflight-only` mode proves a live Codex initialize/thread/Goal attachment
without invoking a model. Full mode starts one turn and waits for a correlated
terminal event, then keeps draining Codex-owned continuation turns until the Goal
leaves `active`. The same total timeout covers the full Goal lifecycle. Add
`--isolate`, `--isolation-work-dir`, and `--private-root` to make this envelope the
real process path; `--profile-root` adds the optional per-run formal profile. The
launcher performs recovery, pre-launch rebase, and `finally` restoration around
both preflight and full Goal modes.

The same adapter publishes `public_trajectory_summary_v0` from the compact
`native_codex_goal_turn_receipt_v0` lifecycle fields. The benchmark toolkit owns
the strict reducer because public/private evidence reduction is already part of
this capability; the DeepSWE research adapter is its first active caller. The
summary carries only typed counts, status labels, and content-free notification
kind counts. It never reopens event payloads, and it marks message and tool-call
semantics unavailable rather than guessing them. Missing, malformed, or
inconsistent lifecycle facts fail closed. The similarly named archived reducer
under `deprecate/benchmark-legacy/` is historical evidence, not a dependency or
compatibility entry point for this native-runner contract.

### Formal installed profile and skill discovery

A treatment that only supplies a Goal prompt and a source-checkout CLI has not
proved the real LoopX product path. The prompt, installed skills, and installed
CLI are three independent inputs. Use `native_codex_profile` to create an isolated
local release through LoopX's shipped `scripts/install-local.sh` instead of copying
skill files or importing an arbitrary checkout:

```python
from loopx.capabilities.benchmark_toolkit.native_codex_goal import NativeGoalConfig
from loopx.capabilities.benchmark_toolkit.native_codex_profile import (
    install_native_codex_profile,
    native_codex_app_server_environment,
    render_native_codex_goal_prompt,
)

profile = install_native_codex_profile(loopx_source, isolated_profile_root)
prompt = render_native_codex_goal_prompt(
    profile,
    project_root=task_visible_cwd,
    goal_id=goal_id,
    agent_id=agent_id,
    runtime_registry_path=case_runtime_registry,
)
config = NativeGoalConfig(
    cwd=task_visible_cwd,
    objective=prompt.task_body,
    task_instruction=task_instruction,
    required_skill_ids=profile.required_skill_ids,
)
process_env = native_codex_app_server_environment(
    profile,
    provider_env_key=runner_provider_env_key,
    base_env=runner_environment,
)
```

The profile installer redirects the release, executable, manual, home, and Codex
skill roots into the supplied isolated directory. It uses the fixed installer path,
including its generated `$loopx` entry skill and packaged workflow-skill readback;
unrelated interactive slash-command surfaces are disabled for this non-interactive
worker. Inspection verifies a release-snapshot CLI, exact source revision, clean
source by default, skill-tree digests, and `doctor --agent-type codex-app-ssh`.

`render_native_codex_goal_prompt` calls `heartbeat-prompt --thin` through the
release-snapshot CLI, requires the `codex_app_ssh_goal` profile and interface budget,
and proves that the returned body names that installed CLI. For an isolated case it
also replaces the generic global-registry token with the explicit case registry.
Use `native_codex_app_server_environment` for app-server so the same profile
supplies `HOME`, `CODEX_HOME`, and `PATH` while exactly one runner-declared model
provider value is restored. The lower-level `native_codex_profile_environment`
remains credential-free by default. The runner must still exclude the provider
key from agent shell and tool environments; this helper grants no such tool
access. Setting `required_skill_ids` makes the native runtime call the real
app-server `skills/list` surface before `thread/start`;
missing skills, discovery errors, or a wrong cwd fail before any model turn. The
path-free profile, prompt, and Goal receipts can then prove all three inputs without
publishing installation paths, prompt text, or skill bodies.

Run the formal installer plus no-model readback smoke with:

```bash
python examples/benchmark-native-goal-installed-profile-smoke.py \
  --require-app-server
```

The helper installs only into its target directory. It grants no credential,
network, task, evaluator, upload, submission, or scoring authority; those remain
runner-owned boundaries.

The toolkit borrows the useful contracts already established by modern benchmark
runners: an ATIF-compatible agent trajectory, a separately owned verifier phase,
explicit attempt accounting, and compact result reduction. LoopX adds the control-
plane pieces that a container runner cannot infer by itself: model-visible source
permissions, host and cross-trial isolation, credential propagation, canonical
case-local state, verifier ordering, public/private evidence reduction, and matched-
pair countability.

## Integrity qualification

Run integrity qualification after the agent phase and after the runner has produced
its isolation attestation. The trajectory and any sensitive values remain private
local inputs:

```bash
export BENCHMARK_PROVIDER_CANARY='a-private-value-known-to-the-controller'

loopx benchmark integrity-qualification \
  --trajectory-json .local/private-run/agent/trajectory.json \
  --runtime-attestation-json .local/private-run/runtime-attestation.json \
  --sensitive-value-env BENCHMARK_PROVIDER_CANARY \
  --require-qualified \
  --format json
```

The command emits `benchmark_integrity_qualification_v0`. It records only stable
labels, counts, reason codes, step ids, and SHA-256 digests. It never emits raw tool
arguments, observations, sensitive values, input paths, task text, verifier output,
or trajectory content. Invalid private input returns a generic fail-closed error so
JSON parser details cannot echo private data.

Qualification rejects a run when it detects any of the following:

- answer, hidden-test, verifier, other-trial, or controller-private source access;
- host escape, credential probing or exposure, or shell network access;
- malformed or incomplete ATIF tool evidence;
- missing runner authority or any required runtime isolation attestation.

Credential-probe detection reads typed command fields, then classifies direct
environment commands, runtime-language enumeration or sensitive-name lookups, and
procfs reads. Neighboring tool prose and commands that only inspect or write source
text are not executed credential reads. Launching a child with an explicit
environment is also not itself a credential read; sensitive values are still
scanned in every tool argument and observation.

Access-request markers are evaluated only on tool calls that can perform or request
resource access. Exact known controller-only calls such as `update_plan` carry
narrative metadata and are excluded from that scan; an actual sensitive value in
their arguments still fails qualification. Unknown tool names remain fail-closed.

`benchmark_cheating_detected` is narrower than `integrity_qualified=false`.
Restricted evaluation or cross-trial access is classified as cheating. Missing
isolation proof or a credential leak still makes the run uncountable, but LoopX does
not relabel that absence of proof as confirmed answer cheating.

### Network access policy

Offline coding benchmarks run with `network_access: "denied"` (the default): shell
network use is a policy violation and the runner must attest
`shell_network_denied: true`. Web-research benchmarks legitimately need network
during the solving phase. A custom policy may declare
`"network_access": "permitted_solving"`; the runner then attests
`network_permitted_solving: true` instead of `shell_network_denied`, and
`external_network_request` evidence is recorded but does not fail the run. The
restricted-resource denials (answer, hidden tests, verifier, other trials,
controller state, host escape, credentials) remain fail-closed in both modes:

```json
{
  "schema_version": "benchmark_integrity_policy_v0",
  "policy_id": "widesearch-permitted-solving",
  "network_access": "permitted_solving"
}
```

`network_access` is validated to `denied` or `permitted_solving`; any other value is
rejected. The qualification receipt exposes the resolved `network_access` and the
attestation checks that actually applied to that mode.

## Runner attestation

The attestation is a compact runner-owned JSON object, not an agent assertion:

```json
{
  "schema_version": "benchmark_runtime_integrity_attestation_v0",
  "authority": "runner",
  "benchmark_id": "fixture@v0",
  "case_id": "case-1",
  "agent_phase_isolated": true,
  "evaluator_sources_denied": true,
  "other_trials_denied": true,
  "controller_state_denied": true,
  "host_escape_denied": true,
  "shell_network_denied": true,
  "provider_credential_shell_excluded": true,
  "case_local_control_state": true,
  "canonical_control_state_root": true,
  "independent_verifier": true,
  "verifier_started_after_agent": true,
  "official_feedback_blinded": true
}
```

Every boolean is required and must be true. A clean trajectory scan cannot prove a
filesystem or namespace permission boundary, so missing attestation fails closed.
Likewise, the attestation alone cannot prove what tool calls actually occurred; both
evidence channels are required.

`benchmark_id`, `case_id`, and a custom policy's `policy_id` are public labels, not
paths. Path-like values fail closed and are emitted only as `redacted`, so a runner
cannot move an operator directory into the public receipt through identifier fields.

### Exact-job container binding

Runtime evidence must belong to the same job as the score. An image-only Docker
lookup is ambiguous as soon as two benchmark arms use the same image concurrently.
Before inspecting isolation settings, bind the container with the runner-owned job
or trial label, the service label, and the expected image:

```python
from loopx.capabilities.benchmark_toolkit import (
    compact_docker_container_binding_receipt,
    select_exact_docker_container,
)

binding = select_exact_docker_container(
    ancestor_image="benchmark-runner:fixture",
    required_labels={
        "com.docker.compose.project": job_id,
        "com.docker.compose.service": "main",
    },
)
container_name = binding.container_name  # private runner state; do not publish
receipt = compact_docker_container_binding_receipt(binding)
```

The selector fails closed unless exactly one running container matches. The compact
`benchmark_exact_container_binding_v0` receipt records only the required label keys,
match count, and a SHA-256 selector digest; it excludes the raw container identity
and label values. The helper grants no Docker or runner authority. Callers that need
a privileged wrapper must supply their own `command_runner` and keep that authority
outside the receipt.

Benchmark-specific private roots can be added without committing them through an
ignored `benchmark_integrity_policy_v0` file:

```json
{
  "schema_version": "benchmark_integrity_policy_v0",
  "policy_id": "local-run-policy",
  "denied_argument_markers": {
    "other_trial_request": ["<private-other-trial-root>"],
    "controller_private_state_request": ["<private-controller-root>"]
  }
}
```

The policy values are used only for in-memory matching and are not copied into the
receipt.

## Experiment lifecycle

A countable experiment uses the toolkit in this order:

1. Read the project experiment board before selecting or launching another case.
2. Declare a `run_permission_policy_v0` and preflight the runner boundary.
3. Upsert the planned or running row, then launch one frozen case/arm; do not expose
   evaluator sources or official feedback.
4. Capture ATIF tool evidence and a runner-owned runtime attestation.
5. During active monitoring, classify exact-job runtime evidence; do not infer
   liveness from an occupied admission slot.
6. Run `integrity-qualification`; stop on any blocker.
7. Run the independent verifier only after the agent phase.
8. Reduce the official result through the benchmark-owned scoring path.
9. Upsert terminal score, countability, effort, treatment fidelity, and insight
   status, then read the matched-comparison projection.
10. Apply attempt-countability, treatment-fidelity, and matched-pair gates before any
   comparison claim.

Integrity qualification is necessary but not sufficient for a score claim. It does
not establish task correctness, official score authority, experiment parity, or a
LoopX advantage. `score_claim_eligible=true` only permits the official score and
matched-pair gates to run; `score_claim_countable` and `matched_pair_countable` stay
false in this receipt. Those remain separate verifier and comparison contracts.

## Experiment board

The project-local experiment board keeps baseline, standard control or treatment,
and diagnostic explore runs in one compact projection. It is not a second score
authority and never stores raw task text, trajectories, logs, hidden evaluation,
verifier output, credentials, or local paths.

An agent using this capability should start or resume a study by reading the board:

```bash
loopx benchmark experiment-board-show \
  --goal-id <goal-id> \
  --format json
```

Preview and then execute an idempotent row update when a run starts or reaches a
terminal state:

```bash
loopx benchmark experiment-board-upsert \
  --goal-id <goal-id> \
  --row-json <compact-row.json> \
  --format json

loopx benchmark experiment-board-upsert \
  --goal-id <goal-id> \
  --row-json <compact-row.json> \
  --execute \
  --format json
```

The default ledger is locked, atomically updated, and keyed by benchmark, study,
case, and run identity. A compact row carries arm role, exact and comparison
protocol ids, model, score metrics, countability, treatment fidelity, bounded
effort, and an optional insight status or public-safe handle. Unknown fields and
path-like references fail closed.

Every non-baseline row names an exact `comparison_anchor_run_id`. Standard control
or treatment rows anchor to a baseline. Explore rows use `diagnostic_only` claim
scope and may anchor to the baseline or fixed standard arm they are examining.
Matched comparisons require compatible benchmark, study, case, model, primary
metric, comparison protocol, score countability, and treatment fidelity. Exact
protocol revisions remain visible as a warning even when a declared comparison
protocol says an older credible score remains semantically comparable.

Full post-run analysis stays in private `benchmark_case_insight_v0` storage. The
board records only its compact status or handle, so reading the board cannot widen
the solving agent's evidence boundary.

## Post-run case insight monitor

Benchmark startup should create one `continuous_monitor` todo that owns both the
campaign score update and the post-run case analysis. Whenever a case reaches a new
material scored state, the monitor first reads the public-safe experiment-board
projection and refreshes the countable baseline, treatment, and matched-pair totals.
It then reports material aggregate changes to the user and, after the solver is
terminal, runs a post-run analyst brief and writes one private
`benchmark_case_insight_v0` artifact. A bounded periodic review while a campaign is
active prevents a long run from silently accumulating results. This monitor is part
of the benchmark lifecycle, not an optional cleanup pass. The catalog entry is a
guidance template rather than a scheduler: the benchmark startup provider creates
the todo, and the registered monitor runtime owns its cadence.

A material user update should include the current countable arm and pair coverage,
aggregate primary metric by arm, binary outcomes when the benchmark exposes them,
improved/flat/regressed pair counts, and the new causal insight or next probe. Derive
these score fields from the experiment board or benchmark-owned scoring projection,
not from raw private evidence. Do not send a repetitive update when no score,
coverage, direction, insight, or material runner state changed.
Only public-safe conclusions from the private post-run insight may enter that user
update; raw evaluation evidence remains private.

During an active-campaign review, distinguish a clean worktree from a lack of
solver progress. `git status` observes only uncommitted changes. Bind the readback
to the exact job, compare its current `HEAD` with the start revision recorded at
admission, and combine that committed delta with the current worktree status.
Correlate those facts with Goal/event freshness, typed runner errors, and the
solver's trajectory phase. A clean worktree or a high raw log-error count alone is
not evidence that a run is stuck. The provider-owned classifier may mark a run
stalled only when committed and uncommitted progress are both absent and either the
trajectory is stale or typed fatal runner evidence is present.

Admission-ledger occupancy is not process liveness. On each bounded active review,
the provider should reduce compact facts through:

```bash
loopx benchmark runtime-observation \
  --admission-active \
  --job-receipt-state resolved \
  --runner-owner-state alive \
  --require-healthy \
  --format json
```

Only a resolved exact-job receipt plus a live exact runner owner is healthy active.
A terminal result, typed fatal runner error, or exact owner missing after the
provider's startup grace produces a reconciliation transition; the provider must
write the terminal classification before releasing its slot. Missing or ambiguous
runtime authority fails closed. The reducer performs no process discovery, writes,
or slot release, and its receipt contains no run identity, process arguments, raw
error, or path.

Every due active-campaign monitor cycle must also advance at least one bounded
solver-trajectory slice, even when no case became terminal. This readback is for
campaign supervision and insight discovery only; it must not expose hidden
evaluator evidence to the solving arm.

Use this analyst hint:

> After the solver has stopped and scoring is complete, read the task, real
> trajectory, final patch or workspace, hidden tests, grader or verifier, and full
> failure and score details; explain the decisive evidence, why the outcome
> happened, whether it was expected, and what LoopX should test or change next.

The solver and analyst are separate roles. The solver remains unable to access
hidden tests, evaluator sources, expected answers, or official feedback. Only the
post-run analyst may read the complete private evaluation evidence, and only after
the solver is terminal and scoring is complete.

The active-campaign monitor may inspect the solver-owned trajectory and exact-job
runtime while the solver is active, but it must not read hidden evaluator evidence
or send its findings back into the solving arm.

Record the result in this compact shape:

```json
{
  "schema_version": "benchmark_case_insight_v0",
  "case": {
    "benchmark_id": "<public-id>",
    "case_id": "<public-id>",
    "arm": "<baseline-or-treatment>"
  },
  "outcome": {
    "status": "<completed-or-runner-invalid>",
    "score": "<official-score-or-null>",
    "countable": "<true-or-false>"
  },
  "evidence_reviewed": [
    "task",
    "real_trajectory",
    "final_patch_or_workspace",
    "hidden_tests",
    "grader_or_verifier",
    "failure_and_score_details"
  ],
  "insight": {
    "approach_summary": "<what-the-solver-tried>",
    "decisive_evidence": ["<specific-observation>"],
    "why_this_outcome": "<causal-explanation>",
    "expectedness": "<expected-surprising-mixed-or-unknown>",
    "baseline_treatment_difference": "<difference-or-not-yet-compared>",
    "loopx_implication": "<reusable-product-or-experiment-insight>",
    "next_probe": "<smallest-discriminating-next-step>"
  },
  "confidence": "<high-medium-or-low>",
  "reuse_boundary": "<diagnostic-only-heldout-generalization-or-declared-feedback>"
}
```

Keep the artifact and its raw evidence in private benchmark storage. Publish only a
redacted reusable conclusion. Do not feed case-specific hidden evidence into a
later scored solver unless the experiment explicitly declares that feedback loop;
use held-out cases before making a general product claim.

## Related commands

```bash
loopx benchmark classify-artifacts <paths...> --format json
loopx benchmark candidate-source-boundary <paths...> --require-clean --format json
```

All commands are local and no-upload by default. `benchmark-toolkit` grants no model,
Docker, runner, upload, submission, publication, or production authority.

The active benchmark research program and current public-safe practice live under
[`benchmark/`](https://github.com/huangruiteng/loopx/blob/main/benchmark/README.md). Historical runners and dated research
packets are retained under [`deprecate/benchmark-legacy/`](https://github.com/huangruiteng/loopx/blob/main/deprecate/benchmark-legacy/README.md)
for source archaeology only.
