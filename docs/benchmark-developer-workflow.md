# Benchmark Developer Workflow

Goal Harness treats benchmark execution as a developer workflow, not only as a
research activity. A benchmark runner should be something a contributor can
inspect, dry-run, diagnose, and improve without reading maintainer `.local`
state or raw benchmark trajectories.

This document is the stable product entry point for benchmark work. Research
packets and dated route notes still live under
`docs/research/long-horizon-agent-benchmarks/`, but reusable runner behavior
belongs in `goal_harness/`, `examples/`, and this guide.

## Product Shape

The benchmark workflow has four layers:

1. **Select** a benchmark family, task, and arm without exposing private task
   text or reward leakage.
2. **Launch** through an explicit route contract. The default route is now an
   exclusive cloud benchmark host where Codex CLI, the benchmark runner, Docker
   or compatible container runtime, task data, and compact reduction all run in
   one isolated environment. Split-control routes remain useful for constrained
   hosts or route research, but they are not the first choice when a dedicated
   cloud host is available.
3. **Observe** the run through compact handles: pid or job state, readiness
   re-check, materialization, result or blocker, and cleanup state.
4. **Ingest** only public-safe evidence into Goal Harness history, ledger, and
   case analysis.

The user-facing product promise is simple: a developer should be able to tell
what ran, why it was allowed, what blocked it, and what can be tried next,
without seeing credentials, raw logs, raw trajectories, or local machine paths.

## Golden Path

From a fresh checkout:

```bash
python3 -m py_compile goal_harness/*.py goal_harness/benchmark_core/*.py
python3 examples/benchmark-split-control-remote-executor-smoke.py
goal-harness benchmark --help
```

For a real benchmark slice, use this sequence:

1. Run a source and boundary preflight for the target benchmark.
2. Prepare or select the benchmark host route:
   - prefer the default cloud Codex route when the host is dedicated, has
     enough CPU/memory/disk, and can run Codex CLI plus containers directly;
   - use a split-control route only when host credentials, local policy, or
     runner constraints make a single cloud host unsuitable.
3. Prove the comparison baseline before any treatment claim. The preferred
   baseline is real Codex Goal mode, not a hand-rolled polling loop and not a
   prompt that merely starts with `/goal`. If the runner cannot prove that Codex
   entered a persistent goal state through a supported Codex surface, park the
   A/B baseline and continue only readiness, runner, or blocker work.
4. Produce a launch plan or runner batch only after a fresh readiness re-check.
5. Build benchmark-specific command-adapter facts when the route still needs a
   Goal Harness adapter, such as
   `goal-harness benchmark terminal-bench-command-adapter terminal-bench`.
   When Terminal-Bench uses a remote executor, first reduce the local-driver
   request plus private remote launch result through the launch adapter:
   `goal-harness benchmark terminal-bench-remote-launch-adapter terminal-bench --request-json <private-json> --launch-result-json <private-json>`.
   The launch adapter emits only field presence and compact blocker state; it
   never executes SSH, Docker, Codex, model calls, uploads, or submits. If a
   lower-level private runner already produced remote-executor handles, reduce
   them through a materializer such as
   `goal-harness benchmark terminal-bench-remote-materializer terminal-bench --handle-manifest-json <private-json>`.
   The materializer emits only handle field presence, never handle values. For
   Terminal-Bench, handle presence is still not enough: the payload must prove
   that a local Codex driver owns agent/model/auth and that the remote executor
   does not require agent or Codex runtime. Then build the execution seam from
   those facts. The seam should expose both a `local_driver_contract` and a
   `remote_sandbox_contract`; treat missing command adapters, missing
   launch-adapter results, missing local-driver materializers, missing sandbox
   contracts, remote-agent-runtime requirements, or compact reducers as
   blockers instead of launching a private script.
6. Run the smallest no-upload dry-run or mini-pair that can answer the current
   product question.
7. Ingest a compact result or precise blocker.
8. Update Goal Harness todo/state so the next developer sees the current route.

Do not start from a raw shell command hidden in a local note. If a benchmark
cannot be launched through a documented route, the next product task is to
build that route, not to keep a one-off script alive.

## Capture The Process While Running

Do not wait for a benchmark family to be fully solved before documenting how it
runs. Each real run should improve the developer workflow in the same batch as
the result or blocker:

1. Before launch, write down the intended route, boundary, command shape,
   expected compact artifacts, and stop conditions.
2. During launch, preserve only observable handles that another developer can
   use: pid or job basename, readiness state, poll command, cleanup state, and
   compact artifact refs.
3. After launch, update the workflow or adapter notes with what changed:
   product-path pass, precise blocker, cleanup rule, or stale assumption.
4. If the run required a private local script, turn the reusable part into a
   public command, fixture, or adapter contract before relying on it again.

The goal is a living runner guide. Repeated benchmark attempts should make the
next attempt easier to launch and debug, not only add more private evidence.

## Cloud ECS Benchmark Host Route

Use the cloud ECS benchmark host route as the default for Terminal-Bench,
SkillsBench, ALE, and other Docker-heavy benchmark families when a dedicated
ECS-style cloud VM is available. This is a developer operations pattern: put
Codex CLI, benchmark source, container runtime, task data, raw artifacts, and
compact reducers on one isolated cloud host, then publish only public-safe
control-plane evidence back to Goal Harness.

| Owner | Responsibility |
| --- | --- |
| Cloud ECS benchmark host | Codex CLI, benchmark source checkout, runner dependencies, container runtime, task-data staging, no-upload run execution, compact result reduction, and private raw artifacts. |
| Goal Harness repo | Public-safe route contracts, reducer schemas, benchmark ledger ingestion, todo/state writeback, public docs, and focused smokes. |
| Operator | Codex login on the cloud host, benchmark data gates, upload/leaderboard decisions, and any private-material or credential approval. |

The route is intentionally simpler than split-control: SSH reaches the ECS
host, then Codex CLI runs there like a normal developer would. Goal Harness
should not need to understand SSH internals, jump hosts, or remote file bridges
in the hot path. It should only record compact route readiness, result handles,
blockers, and no-upload boundaries.

### ECS Host Bootstrap SOP

Treat remote benchmark host fixes as product assets only after they become one
of three reusable surfaces:

- a documented SOP step that another developer can repeat;
- a script or CLI entrypoint that emits compact JSON;
- a reducer that turns private runner state into a public-safe blocker or
  ingest action.

Runtime-only tweaks such as Docker registry mirrors, loopback proxy sessions,
cached base images, source tarballs, dependency prewarm, and run directories
are useful operator substrate. Do not let them become hidden Goal Harness
truth. Record only the compact fact: ready, blocked, or needs operator setup.
The concrete mirror URL, proxy port, shell history, raw logs, and local host
paths stay outside public evidence.

Recommended cloud host layout:

```text
goal-harness-bench/
  sources/
  runs/
  cache/
  artifacts/public/
  artifacts/private/
```

Run the bootstrap probe on the cloud host before a benchmark slice:

```bash
python3 scripts/benchmark_ecs_bootstrap.py \
  --workspace ~/goal-harness-bench \
  --min-free-gib 80 \
  --create-dirs \
  --pretty
```

The probe checks command presence, Docker server reachability, disk budget, and
the standard workspace shape. It intentionally emits only command names,
version first lines, booleans, counts, and the workspace basename.

Benchmark source materialization should stay close to upstream:

- prefer a real git checkout or fork when the benchmark source must be patched
  or rebased;
- if a source tree is only a materialized copy, add a `.goal-harness-upstream`
  marker with upstream repo and commit, and do not treat it as a fork branch;
- keep wrapper scripts, reducer sidecars, and runbooks in this repository
  unless the change is clearly upstreamable;
- never mix temporary runner probes, raw evidence, local auth setup, or private
  benchmark artifacts into upstream benchmark source trees.

For cloud hosts that cannot reliably fetch public Git sources, stage sources as
archives from the operator machine. Prefer one compressed archive over many
small-file transfers, and on macOS disable copyfile metadata and xattrs:

```bash
COPYFILE_DISABLE=1 tar --no-xattrs -C /tmp -czf benchmark-source.tgz upstream-checkout
scp benchmark-source.tgz "$BENCHMARK_HOST_ALIAS":~/goal-harness-bench/cache/
```

After extraction, verify the upstream commit and clean status. If the staged
archive includes `.git` and Git reports a dubious ownership boundary, add a
bounded remote `safe.directory` entry for that checkout or restage it as a
source-only archive with a `.goal-harness-upstream` marker. Do not commit the
host-specific path or exception.

When a benchmark pins a runner dependency to a public Git repository and the
cloud host cannot fetch that dependency, stage the dependency source separately
and patch only a temporary run-work copy to use a local `path` source. Keep the
upstream-clean checkout unchanged, record the dependency commit, and classify
the result as dependency readiness or a precise dependency-fetch blocker. Do
not patch official scorer, task, prompt, or runner behavior merely to work
around network fetch.

Remote bootstrap snippets should assume a small base image: use `grep`, `find`,
`git`, `python`, and the benchmark runner itself unless the bootstrap probe has
confirmed extra tools such as `rg`.

For Terminal-Bench, the first product-path launcher should be no-upload and
probe-only:

```bash
python3 scripts/terminal_bench_no_upload_smoke.py \
  --task-id hello-world \
  --jobs-dir ~/goal-harness-bench/runs/terminal-bench/jobs \
  --run-root ~/goal-harness-bench/runs/terminal-bench/no-upload-smoke \
  --pretty
```

That command is a dry-run by default. Add `--execute` only after Codex auth,
network, Docker, source, and task-data readiness are known. It emits command
shape and boundary facts, not argv values or raw runner output.

For direct `tb run` smoke runs on the cloud host, keep the runner invocation
boring and Docker-compose-safe:

- use an all-lowercase run id with only letters, digits, hyphens, or
  underscores; Docker Compose rejects project names with uppercase timestamp
  separators such as `T`;
- pass `--output-path` as the parent runs directory and let Terminal-Bench
  create the run-id subdirectory itself; pre-creating that directory can make
  the runner think it is resuming a run and fail before execution;
- keep `--no-upload-results` explicit for every developer smoke;
- start with `--no-rebuild` only after the task image already exists, otherwise
  record the image/build blocker instead of hiding it behind a score result.

When a Terminal-Bench launch produces only startup or materialization state,
reduce it before writing Goal Harness evidence:

```bash
python3 scripts/terminal_bench_compose_startup_reducer.py \
  --post-launch-json ~/goal-harness-bench/runs/terminal-bench/no-upload-smoke/post_launch_summary.public.json \
  --pretty
```

The reducer classifies compact startup blockers such as missing jobs directory,
missing job root, missing job lock, ended worker without trial result, or stale
active job without trial result. It does not read raw logs, task text,
trajectories, credentials, or command argv. If a blocker repeats, improve the
SOP or script in the same batch instead of preserving a private one-off shell
fragment.

For SkillsBench, prove the verifier dependency substrate before claiming a
no-upload task result. A timeout-looking failure can actually be a missing
verifier launcher surface: the verifier may need minimal Python, pip, curl,
certificates, `uv`, and `uvx` before it can run the official oracle sanity path.
Do not repair that first by globally extending timeouts.

Preview the public-safe prewarm plan:

```bash
python3 scripts/skillsbench_verifier_prewarm_plan.py \
  --task-id hello-world \
  --pretty
```

The plan is deliberately not an upstream patch. Apply it only to a temporary
task copy, wrapper layer, or derived sandbox image, then run a one-attempt
oracle no-upload sanity task. Claim SkillsBench case readiness only after the
oracle run reaches reward `1.0` with verifier errors cleared. If the sanity run
still times out after the dependency substrate is present, classify it as a
real verifier timeout and consider a bounded timeout increase for that tier.

Keep these boundaries:

- do not modify official task truth, scorer, prompt, or leaderboard behavior;
- do not publish raw verifier output, task text, trajectories, local paths, or
  remote run directories;
- record only compact fields such as dependency-prewarm ready/blocked, oracle
  sanity pass/fail, and the next blocker label
  `skillsbench_verifier_dependency_prewarm_required`.

### SSH Session Hygiene

When the benchmark host is reached through a jump host, GSSAPI, or another
access path with expensive handshakes, use one SSH multiplexed master for the
benchmark slice and run remote commands through that connection. This is an
operator workflow convention, not a Goal Harness protocol requirement.

```bash
BENCHMARK_HOST_ALIAS=<your-ssh-config-alias>
CONTROL_PATH=/tmp/goal-harness-ssh-cm/benchmark-host
mkdir -p "$(dirname "$CONTROL_PATH")"

ssh -M -S "$CONTROL_PATH" \
  -o ControlPersist=600 \
  -fN \
  -o BatchMode=yes \
  -o ConnectTimeout=20 \
  "$BENCHMARK_HOST_ALIAS"

ssh -S "$CONTROL_PATH" -o BatchMode=yes "$BENCHMARK_HOST_ALIAS" \
  'hostname && docker --version && codex --version'

ssh -S "$CONTROL_PATH" -O exit "$BENCHMARK_HOST_ALIAS" || true
```

Keep commands through the master connection mostly serial when the access path
is sensitive to concurrent authentication. Do not commit SSH aliases, host
names, private keys, jump-host details, raw shell history, or local control-path
values into public benchmark evidence. Public docs should preserve the shape:
create one short-lived master, reuse it for bounded probes or run launch, then
close it during cleanup.

### Codex Goal Baseline Gate

The primary comparison target is **Codex Goal mode** running on the benchmark
host. A benchmark route may call itself a Codex Goal baseline only when it has
evidence for all of the following:

- the installed Codex build exposes `features.goals=true` or an equivalent
  enabled Goal feature;
- the runner starts Goal mode through a supported Codex surface. Prefer the
  Codex app-server goal API for automation: initialize with
  `capabilities.experimentalApi=true`, `thread/start` the benchmark workspace,
  then call `thread/goal/set` with `objective`, `status: active`, and an
  optional `tokenBudget`. The interactive CLI slash command `/goal` remains the
  manual fallback, not the preferred benchmark automation seam;
- the run evidence shows a persistent goal attached to the active thread, not
  only a prompt string whose first token is `/goal`;
- the route does not add Goal Harness state, access packets, reward feedback,
  or polling semantics to the baseline arm.

`codex exec` is still useful as a tiny connectivity smoke on the cloud host,
but a successful `codex exec` run is not by itself a Codex Goal baseline. Do not
rename a polling loop, resume loop, or prompt-prefixed `/goal` experiment into a
Goal baseline without `thread/goal/get` or equivalent persistent-goal evidence.

If these facts are not available, classify the result as a runner/readiness
probe or unverified slash-goal prompt experiment, not as a Codex Goal baseline.
In that state, do not launch matched Goal Harness treatment for uplift claims;
instead record the exact trigger gap and keep working on cloud host, runner,
task-data, or compact-result readiness.

For Terminal-Bench launcher work, use the fail-closed app-server Goal surface
when validating this boundary:

```bash
python3 -m goal_harness.cli --format json benchmark launch-terminal-bench-run \
  terminal-bench \
  --mode codex-app-server-goal \
  --include-task-name hello-world \
  --jobs-dir '<private-jobs-dir>' \
  --run-root terminal-bench-app-server-goal-probe \
  --job-name terminal_bench_app_server_goal_probe \
  --wait-seconds 0 \
  --materialization-wait-seconds 0
```

The app-server Goal launcher now exposes a public worker contract for
`thread/goal/set`, `thread/goal/get`, and `turn/start`. Until a real
Terminal-Bench case launch returns compact `turn/start` proof plus no-upload
case proof, this mode must still return `execution_ready=false`,
`first_blocker=terminal_bench_app_server_goal_turn_start_proof_missing`, and
`codex_goal_mode_baseline_claim_allowed=false`. The older `codex-goal-mode`
launcher remains a slash-command fallback and must not be used as a scored
Codex Goal baseline.

Default cloud ECS host readiness:

- SSH access works through the operator's approved access path.
- Codex CLI is installed on the host; auth is completed by the operator on that
  host and is not copied from another machine.
- `git`, Python, `uv`, Node/npm when required, and Docker or a Docker-compatible
  runtime are available.
- Container image pulls use a documented reachable registry or mirror.
- The benchmark workspace is dedicated and private enough for raw artifacts.
- The first task is a no-upload dry-run or mini-pair that writes compact
  `benchmark_run_v0` / `benchmark_result_v0` evidence before any score claim.

Cloud-host Codex connectivity is its own preflight, separate from benchmark
runner readiness. A host can have a valid Codex login and still fail model calls
because its network egress cannot reach the provider endpoints. Before blaming
the benchmark runner, prove three layers in order:

1. **Auth**: `codex login status` or equivalent reports an authenticated local
   user on the benchmark host.
2. **Network**: a bounded model-provider probe reaches the endpoint through the
   operator-approved route. If direct egress is unavailable, use an approved
   loopback-only proxy or tunnel instead of copying credentials or embedding
   proxy details in public docs.
3. **Execution**: `codex exec` can complete a tiny read-only smoke in a scratch
   directory and write a compact last-message or exit-code artifact.

The reusable trick is the shape, not the private wiring: keep the concrete SSH
jump path, local ports, auth-cache handling, and proxy process command in a
local-private runbook, then expose only these public-safe facts to Goal Harness:
auth ready, network route ready or blocked, `codex exec` smoke result, and the
next benchmark-family blocker. Prefer per-command tunnels or short-lived
operator-managed proxy sessions for benchmark slices; long-running unattended
network bridges should have an explicit owner and cleanup rule.

Keep upstream benchmark sources clean:

- Use upstream `main` or a pinned upstream commit for official runner code.
- Keep any internal convenience changes on a tiny, rebased adapter branch.
- Prefer wrapper scripts, environment files, and reducer sidecars over editing
  upstream benchmark logic.
- Fork only when we need to preserve a small reusable patch set; keep the fork
  close enough that upstream pulls remain routine.
- Do not mix Goal Harness runner experiments, local bridge probes, raw logs, or
  credential setup into benchmark forks.

## Split-Control Route

The split-control route is now a fallback and research route, not the default
when a dedicated cloud host exists.

Use it when Codex auth cannot live on the execution host, when the host is
shared, or when the product question is specifically about a local Goal Harness
controller using a separate Docker substrate.

| Owner | Responsibility |
| --- | --- |
| Local agent | Codex CLI, auth, model invocation, planning, patch generation, Goal Harness state, quota, todo, and evidence filtering. |
| Remote executor | Docker runtime, runner dependencies, task-data or image staging, bounded command/file execution, and compact result reduction. |

The remote executor is not an agent-auth environment. Missing remote Codex,
Codex ACP, or model credentials is not a benchmark blocker. Real blockers are
things like missing split-control adapter, missing runner tooling, missing task
data or images, missing remote node runtime when a specific runner requires it,
or a failed cleanup/readiness check.

Historical split-control work is still useful: it records which boundaries
matter when credentials cannot move, and it produced adapter/reducer seams that
can be reused for compact evidence. Do not continue adding split-control bridge
layers when a cloud-host route can answer the benchmark question directly.

Treat split-control assets as a retained research branch, not a live default:

- keep durable contracts, reducers, and boundary smokes that still protect
  public behavior;
- do not add new bridge layers unless a cloud-host run is blocked by a concrete
  auth, policy, or host gate;
- move future local-Codex / remote-executor experiments to an explicitly named
  experimental branch or research issue;
- remove or defer mainline split-control code once the cloud-host route has
  equivalent compact evidence for the same benchmark family.

See
[`benchmark-split-control-remote-executor-v0.md`](research/long-horizon-agent-benchmarks/benchmark-split-control-remote-executor-v0.md)
for the current machine contract, and
[`benchmark-route-transition-retrospective-20260619.md`](research/long-horizon-agent-benchmarks/benchmark-route-transition-retrospective-20260619.md)
for the split-control retention, branch-hygiene, and retirement runbook.

## Current Benchmark Families

| Family | Product-path target | Current maturity |
| --- | --- | --- |
| Terminal-Bench | Cloud Codex CLI runs the task on a dedicated benchmark host; Goal Harness ingests compact no-upload evidence. | Prior split-control adapters remain useful reducers, but the next run should prefer direct cloud-host Codex plus container runtime. |
| SkillsBench | Cloud Codex CLI and BenchFlow run on the same dedicated host; Goal Harness records compact base/test mini-pair evidence. | Prior host-local ACP relay work is historical route-repair evidence. Do not add more bridge layers before trying the cloud-host path. |
| Agents' Last Exam | Cloud Codex CLI drives the local-Docker-capable ALE route on the dedicated host; Goal Harness ingests compact no-upload evidence. | Formal task runs still need task-data and public-claim gates, but Docker/Codex colocation should replace the earlier local-host split-control assumption. |

This table is intentionally about runner maturity, not leaderboard score.
Score claims require separate public-safe result ingestion and review.

### SkillsBench Split-Control Preflight

This preflight is retained for historical split-control debugging and for
shared-host environments where Codex auth cannot live on the runner host. It is
not the default route when a dedicated cloud benchmark host is available.

SkillsBench currently uses BenchFlow's ACP stdio worker protocol for Codex-like
agents. For split-control runs, Codex auth, model invocation, and goal state
stay local. Before launching a split-control mini-pair, run:

```bash
python3 scripts/skillsbench_automation_loop.py \
  --local-driver-worker-handshake-preflight \
  --local-codex-cli-participant-ready \
  --local-acp-relay-probe \
  --host-local-acp-transport-probe
```

The preflight is successful only when BenchFlow is importable, the default
Codex agent is registered as ACP, the local Codex CLI participant was already
materialized, the local ACP relay completes `initialize`, `session/new`,
`session/set_model`, and `session/prompt`, BenchFlow's own `ACPClient` can
drive that relay over host-local stdio, and a bounded remote command/file
bridge exists for the sandbox side. The default relay and transport probes are
dry-run: they do not invoke Codex, read task text, copy credentials, record raw
logs, or launch a benchmark task.

Do not treat a successful relay probe as mini-pair readiness. It only proves
the local ACP server shape. The host-local transport probe proves BenchFlow can
talk to that local server without `ContainerTransport`. A no-upload mini-pair
is product-path evidence only after the remote bridge is also materialized, so
the preflight may legitimately return `skillsbench_remote_command_file_bridge_missing`
after both local probes pass.

For the remote bridge, prefer a machine-verifiable probe over a manual
readiness flag:

```bash
python3 scripts/skillsbench_automation_loop.py \
  --local-driver-worker-handshake-preflight \
  --local-codex-cli-participant-ready \
  --local-acp-relay-probe \
  --host-local-acp-transport-probe \
  --remote-command-file-bridge-probe \
  --remote-command-file-bridge-probe-command '<private-remote-bridge-command>'
```

The bridge command reads a fixed JSON request from stdin and writes compact JSON
to stdout. It must prove four bounded operations: `exec`, `write_file`,
`read_file`, and `cleanup`. Its public result records only operation kinds,
statuses, and boundary flags; it must not return raw commands, stdout, stderr,
task text, paths, credentials, logs, trajectories, uploads, or submissions.
`scripts/skillsbench_remote_command_file_bridge.py --serve-probe` is only a
local fake bridge for smoke tests and adapter development. It is not evidence
that a real remote executor is ready.

## Evidence Contract

Benchmark evidence may include:

- benchmark id, task id or public-safe case id;
- arm or mode label;
- readiness gate result;
- process or job handle basename;
- compact result fields such as `score`, `best_score`, `final_score`,
  `first_success_round`, `duration_s`, and `blocker`;
- cleanup state;
- links to public docs or compact JSON/Markdown artifacts.

Benchmark evidence must not include:

- raw task text, hidden task files, verifier body output, or solution material;
- raw trajectories, transcripts, screenshots, stdout, stderr, or shell argv;
- credentials, tokens, local absolute paths, remote absolute paths, or private
  hostnames;
- uploads, submit paths, or leaderboard claims unless a specific public release
  gate has approved them.

## Developer Checklist

Before a PR that changes benchmark behavior:

- Name which layer changed: selection, launch, observe, ingest, scoring, or
  docs.
- Keep benchmark-specific runner details inside the adapter.
- Preserve the split-control boundary when a remote executor is involved.
- Add or update a focused smoke for the durable contract.
- Run `goal-harness check --scan-path <changed-public-path>` for public docs or
  examples.
- Do not commit `.local`, raw logs, private run directories, active state, or
  local runner configs.

## Roadmap

Near-term work should make the benchmark workflow feel like a small product:

- expose a single developer-facing command path for readiness and runner batch
  planning;
- add observable launch handles so long runs can be polled without chat memory;
- align Terminal-Bench, SkillsBench, and Agents' Last Exam on the same
  launch/observe/ingest lifecycle;
- document the no-upload dry-run path before chasing broad score matrices;
- make compact blockers first-class, so a failed launch still teaches the next
  developer exactly what to repair.
