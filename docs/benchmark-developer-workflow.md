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

Use the shared snapshot helper for routine polling instead of ad hoc SSH
commands:

```bash
python3 scripts/benchmark_run_status_snapshot.py \
  --run-root <cloud-run-root> \
  --label <terminal-bench-run-label> \
  --label <skillsbench-run-label> \
  --label <swe-marathon-run-label> \
  --record-rollout-event \
  --goal-id goal-harness-meta \
  --agent-id codex-main-control \
  --pattern Working \
  --pattern timed\ out \
  --pretty
```

The snapshot reports `status.env`, pid liveness, compact result summaries,
standard artifact presence, and optional keyword booleans for tmux captures. It
does not emit task text, trajectories, raw logs, or capture content. With
`--record-rollout-event`, it also appends one aggregate `benchmark_status`
event to the rollout log so the control plane can see that a poll happened
without seeing host paths or capture text.

For local `launchd` or similar scheduler jobs, treat benchmark case launches as
one-shot observable runs. Do not use `KeepAlive` to rerun a case label
automatically: a successful compact closeout or a terminal compact failure must
unload/disable the scheduler label before any rerun is considered. The snapshot
adds an `observable_handle_policy` per run with these public-safe decisions:

- `monitor_poll_allowed=true`: keep observing the pid/job handle.
- `cleanup_required=true`: unload/disable the one-shot label, then ingest the
  compact closeout or write the precise blocker named by `next_action`.
- `blocker_required_before_rerun=true`: the observable handle ended or vanished
  without a compact closeout; write that blocker before any rerun.

This keeps reruns explicit and countable while preserving enough handle state
for another developer or heartbeat to resume polling without chat memory.

### Goal Rollout Event Log

Each benchmark case should leave a compact Goal Harness rollout trail, separate
from raw Codex sessions or benchmark runner logs. Use the rollout event log when
you need to explain the lifecycle of a case or an agent workflow:

- `quota_should_run`: the controller allowed a bounded slice.
- `todo_claim`: an agent claimed the work item.
- `benchmark_launch` / `benchmark_status`: a case was launched or polled.
- `validation`: a smoke, reducer, or official verifier finished.
- `compact_case_result` / `compact_blocker`: public-safe case outcome.
- `refresh_state` / `quota_spend`: Goal Harness writeback and spend.
- `codex_session_observed`: a private Codex session source exists, but raw
  session contents and file paths are not recorded.

Core Goal Harness CLI lifecycle commands append compact events automatically:
`todo` transitions, `refresh-state`, and `quota should-run` /
`quota monitor-poll` / `quota spend-slot` / `quota void-slot` all write to the
rollout event log when they run through the CLI. This makes the log closer to a
Codex session ledger for Goal Harness itself: agents do not need to remember to
record routine GH control-plane transitions by hand.

Compact benchmark history writes also append automatically when they are
executed through the CLI. `goal-harness history append-benchmark-run
--execute`, `goal-harness history append-benchmark-result --execute`, and the
`goal-harness benchmark ... --execute` fixture/ingest path write
`compact_case_result` or `compact_blocker` events derived only from the compact
`benchmark_run_v0` / `benchmark_result_v0` payload. This is the default path for
case-level observation: launch/poll scripts may keep their own private raw
artifacts, but Goal Harness should observe the public-safe compact writeback.

Use the script for external benchmark transitions, backfills, or operator-side
facts that happen outside those core CLI paths:

```bash
python3 scripts/goal_rollout_event_log.py append \
  --goal-id goal-harness-meta \
  --event-kind compact_case_result \
  --agent-id codex-main-control \
  --todo-id todo_406bb256efd8 \
  --benchmark-id terminal-bench@2.0 \
  --case-id build-cython-ext \
  --status precise_blocker \
  --summary "Official verifier failed before a countable agent result." \
  --artifact-ref docs/research/long-horizon-agent-benchmarks/benchmark-case-analysis.json
```

Summarize the current trail without reading private sources:

```bash
python3 scripts/goal_rollout_event_log.py summarize \
  --goal-id goal-harness-meta \
  --limit 12 \
  --pretty
```

Codex session JSONL files can help local debugging, but treat them as private
source material. Record only their existence/count, never transcript bodies,
paths, prompts, tool output, or token-bearing content:

```bash
python3 scripts/goal_rollout_event_log.py observe-codex-sessions \
  --goal-id goal-harness-meta \
  --agent-id codex-main-control
```

The canonical log lives under the Goal Harness runtime root for the goal, for
example `goals/<goal-id>/rollout-event-log.jsonl`. It is a local control-plane
artifact, not a raw evidence file to commit. Public docs and ledgers may cite
compact event ids, case ids, run ids, and artifact refs, but must keep raw task
text, logs, trajectories, Codex session transcripts, credentials, and absolute
host paths out.

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

Temporary patches to an upstream benchmark checkout are allowed during route
bring-up only when they are explicit, reversible, and recorded as route
substrate. Keep the upstream checkout clean enough to rebase: prefer a small
patch file, wrapper script, or sidecar module over editing scorer, task truth,
or prompts in place. After patching a remote checkout, record the compact
metadata another developer needs: upstream repo/ref, patch purpose, files
touched by category, whether scoring/task truth changed, validation command,
and rollback command. Do not publish the raw patched checkout, task text, raw
logs, private paths, or internal hostnames. Once a patch repeats, promote it to
one of three durable surfaces: an upstreamable PR, a Goal Harness wrapper, or a
documented benchmark-host SOP.

When the host has both a system disk and a data disk, move every large runner
cache onto the data disk before calling the host ready. Docker `data-root`
alone is not enough: containerd snapshot state can still fill the system disk
while Docker reports the expected data-root. Verify both paths after setup:

```bash
docker info --format '{{.DockerRootDir}}'
df -h / /data /var/lib/docker /var/lib/containerd
```

If `/var/lib/containerd` is already large on the system disk, stop Docker and
containerd, copy it to the data disk, replace the original directory with a
symlink or bind mount, then restart both services. Keep the pre-migration copy
only until `docker images`, `docker ps`, and a tiny runner smoke prove the
runtime still sees existing images.

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

After the host is ready, decide the benchmark-specific agent runtime layer
before launching an official case. The common rule is: agent runtime is
preinstalled as a stable layer; the case container only runs the task and the
benchmark scorer. Generate the public-safe profile plan:

```bash
python3 scripts/benchmark_agent_runtime_layer.py \
  --benchmark all \
  --workspace ~/goal-harness-bench \
  --pretty
```

Terminal-Bench and SWE-Marathon are Harbor-family profiles. They share the
`harbor_codex_cli_tools` layer mounted at `/opt/harbor-agent-tools`.
SkillsBench is a BenchFlow-family profile. It needs a separate
`benchflow_js_agent_runtime` layer for Node.js and `codex-acp`, mounted at
`/opt/benchflow`. Treat verifier dependency prewarm as a separate oracle
concern; the runtime layer is only about making the agent process start without
per-case downloads.

For Harbor-based SWE or Terminal-style runners, avoid downloading nvm, npm
packages, or Codex inside every task container. Materialize a host-side
preinstalled tools bundle and mount it read-only at Harbor's conventional
agent-tools path:

```bash
python3 scripts/harbor_agent_tools_bundle.py \
  --output ~/goal-harness-bench/harbor-agent-tools \
  --pretty
```

Then add the mount to the Harbor job config or CLI launch:

```yaml
environment:
  type: docker
  mounts:
    - type: bind
      source: ~/goal-harness-bench/harbor-agent-tools
      target: /opt/harbor-agent-tools
      read_only: true
```

For a Harbor CLI launch, pass the same mount explicitly:

```bash
MOUNTS='[{"type":"bind","source":"<workspace>/harbor-agent-tools","target":"/opt/harbor-agent-tools","read_only":true}]'
UV_LINK_MODE=copy uv run --no-default-groups harbor run \
  --env docker \
  --agent codex-api-key-no-search \
  --mounts "$MOUNTS" \
  --jobs-dir <run-dir>/jobs \
  -p <task-dir>
```

When running SWE-Marathon on a constrained cloud host, prefer invoking Harbor
from an already materialized local Harbor checkout and pointing `-p` at the
SWE-Marathon task directory. Running `uv run harbor` from the SWE-Marathon
checkout can fetch Harbor from GitHub and may install default cloud/GPU extras
before the benchmark case starts. That is dependency materialization noise, not
case progress. Use `uv run --no-default-groups harbor run` for the runner layer
unless the selected environment backend explicitly needs extra Harbor groups.

After any Harbor-family job finishes, reduce the job directory with the generic
Harbor reducer and pass the benchmark id explicitly:

```bash
python3 scripts/harbor_job_result_reducer.py \
  --job-dir <jobs-dir>/<job-name> \
  --benchmark-id swe-marathon \
  --output-json <jobs-dir>/<job-name>/goal_harness_harbor_result.compact.json \
  --pretty
```

Do not rely on the older Terminal-Bench-named Harbor ingest path for
SWE-Marathon or other path-based Harbor tasks; when Harbor is launched with
`-p <task-dir>` rather than `--dataset`, the job lock may not carry enough
benchmark identity to infer the right `benchmark_id`.

When Harbor's preinstalled in-container Codex surface fails before a real
solution attempt, switch to the host Codex Goal custom agent instead of
continuing to rebuild or reinstall Codex in every case container:

```bash
export PYTHONPATH=<goal-harness-checkout>:<goal-harness-checkout>/scripts:${PYTHONPATH:-}
UV_LINK_MODE=copy uv run --no-default-groups harbor run \
  --env docker \
  --agent-import-path harbor_host_codex_goal_agent:HarborHostCodexGoalAgent \
  --agent-kwarg goal_timeout_sec=1200 \
  --agent-kwarg task_workdir=/app \
  --jobs-dir <run-dir>/jobs \
  -p <task-dir>
```

When wrapping that launch in `tmux`, `launchd`, or a generated `run.sh`, put the
same `PYTHONPATH` export inside the wrapper script, not only in the interactive
shell that creates it. Otherwise Harbor can create a job shell but fail before
trial execution with `No module named 'harbor_host_codex_goal_agent'`. A reusable
wrapper should look like:

```bash
#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=<goal-harness-checkout>:<goal-harness-checkout>/scripts:${PYTHONPATH:-}
python3 - <<'PY'
import importlib
importlib.import_module("harbor_host_codex_goal_agent")
importlib.import_module("goal_harness.benchmark_core.loop_protocol")
PY

cd <harbor-checkout>
set +e
UV_LINK_MODE=copy uv run --no-default-groups harbor run \
  --config <run-dir>/config.json \
  > <run-dir>/harbor.run.log 2>&1
status=$?
set -e

printf "exit_status=%s\n" "$status" > <run-dir>/status.env

if [ -d <run-dir>/jobs/<job-name> ]; then
  python3 <goal-harness-checkout>/scripts/harbor_job_result_reducer.py \
    --job-dir <run-dir>/jobs/<job-name> \
    --benchmark-id swe-marathon \
    --output-json <run-dir>/jobs/<job-name>/harbor_job_result.compact.json \
    --pretty
fi

exit "$status"
```

Treat a wrapper-level import failure as a launcher blocker, not a benchmark case
failure: no trial ran, no verifier reward exists, and the next step is to fix the
host-agent import surface before spending another case attempt.

The agent starts Codex native Goal mode on the benchmark host and exposes a
host command named `harbor-env-exec`. Codex is instructed to call
`harbor-env-exec --cwd <task_workdir> -- <command>`; set `task_workdir` per
benchmark family instead of hardcoding `/app` in runner patches. Commands issued
through that bridge are forwarded to Harbor's `environment.exec()`, so the
benchmark environment remains the task/scoring surface while Codex login, model
access, tmux, and runtime state stay on the stable host layer.
The Harbor app-server agent drains app-server turn events while the async
runner loop continues to serve `harbor-env-exec` bridge requests. Its compact
turn file records bridge request count, marker observation, `turn/completed`
observation, and assistant-message counters without raw task text, raw logs, or
raw trajectories. Do not make `turn/completed` the benchmark success gate for
Harbor-family runs: the official environment result and the host completion
marker are the scoring path, while app-server completion events are diagnostic
only.

For the current SWE-Marathon experiment axis, keep the same task, model,
timeout, environment, jobs directory shape, and no-upload boundary across arms:

- baseline: native Codex app-server Goal mode;
- test: Goal Harness prompt-driven polling with scheduled continuations.

A single Goal Harness access-packet run is not the test arm by itself. It adds
planning/checkpoint context to the same host app-server Goal worker, but remains
packet-only observation unless an outer polling controller records the scheduled
rounds:

```bash
export PYTHONPATH=<goal-harness-checkout>:<goal-harness-checkout>/scripts:${PYTHONPATH:-}
UV_LINK_MODE=copy uv run --no-default-groups harbor run \
  --env docker \
  --agent-import-path harbor_host_codex_goal_agent:HarborHostCodexGoalAgent \
  --agent-kwarg goal_surface=app_server \
  --agent-kwarg reasoning_effort=high \
  --agent-kwarg app_server_wait_for_completion=true \
  --agent-kwarg app_server_response_timeout_sec=90 \
  --agent-kwarg goal_timeout_sec=<seconds> \
  --agent-kwarg task_workdir=/app \
  --agent-kwarg goal_harness_mode=codex_goal_harness \
  --agent-kwarg goal_harness_access_packet_mode=compact \
  --agent-kwarg goal_harness_cli_bridge_enabled=true \
  --agent-kwarg goal_harness_goal_id=<goal-id> \
  --agent-kwarg goal_harness_registry_arg=<registry.global.json> \
  --agent-kwarg goal_harness_runtime_root_arg=<runtime-root> \
  --agent-kwarg goal_harness_scan_path=<public-scan-path> \
  --agent-kwarg goal_harness_classification=<public-classification> \
  --agent-kwarg goal_harness_experiment_protocol=packet_only_observation \
  --agent-kwarg goal_harness_max_rounds=5 \
  --jobs-dir <run-dir>/jobs \
  --job-name <matched-treatment-job-name> \
  -p <task-dir>
```

The packet is intentionally lightweight: it gives the host Codex worker Goal
Harness planning/checkpoint commands and boundary reminders, while the task
solution still goes through `harbor-env-exec` and the official Harbor verifier
remains authoritative. It is useful as route-safety evidence, but on its own it
must be labeled `packet_only_observation`, not the prompt-driven test arm.

The prompt-driven test contract is shared in
`goal_harness.benchmark_core.loop_protocol` so SkillsBench historical rows,
SWE-Marathon tests, and future Terminal-Bench tests use one semantics instead of
parallel old/new definitions. The contract requires:

- `max_rounds_budget=5`;
- `official_feedback_forwarded=false`;
- scheduled continuation prompts must not reveal reward, pass/fail, verifier
  errors, or verifier output;
- the compact result must include public-safe controller/round evidence such as
  `round_rewards`, `first_success_round`, `official_feedback_blinded_count`, and
  the loop contract;
- if a Harbor/app-server route cannot provide that controller trace, classify it
  as packet-only route-safety evidence and do not compare it as test.

When launching the actual test arm, the outer controller should set
`goal_harness_experiment_protocol=max5_blind_loop_no_feedback`, inject a fresh
Goal Harness packet before each scheduled prompt, keep official feedback
blinded, and record the public-safe controller trace. The route name for new
SWE-Marathon/Terminal-Bench work is `goal-harness-prompt-polling-test`; the old
SkillsBench route name `goal-harness-blind-loop-treatment` is a backward-
compatible alias for the same no-feedback polling semantics.

For Harbor-family runners, the host agent enables this controller when the
experiment protocol is explicit:

```bash
--agent-kwarg goal_harness_mode=codex_goal_harness \
--agent-kwarg goal_harness_access_packet_mode=compact \
--agent-kwarg goal_harness_experiment_protocol=max5_blind_loop_no_feedback \
--agent-kwarg goal_harness_max_rounds=5 \
--agent-kwarg goal_harness_prompt_polling_rounds=5 \
--agent-kwarg goal_harness_prompt_polling_round_timeout_sec=900
```

That path starts native Codex app-server Goal once, then uses follow-up
`turn/start` calls in the same thread for scheduled continuation prompts. It
does not expose official reward, pass/fail status, verifier errors, or verifier
output to the worker. The per-round timeout is separate from the full job
timeout: if a single app-server turn does not hand control back, the controller
must close out with a compact
`harbor_prompt_polling_round_timeout_before_completion` blocker instead of
waiting for the whole job timeout. If these controller fields are missing from
compact evidence, classify the run as packet-only observation.

The treatment path must also install a case-local Goal Harness surface before
the worker starts. Harbor's host agent seeds
`/app/.codex/goals/<benchmark-case-goal-id>/ACTIVE_GOAL_STATE.md`, installs a
task-environment CLI at `/app/.local/bin/goal-harness`, seeds
`todo_benchmark_case_main`, and writes public-safe lifecycle events to the
case-local `rollout-event-log.jsonl`. The product-path treatment proof is
prompt-driven: before planning or editing, the worker should call the
case-local CLI through `harbor-env-exec` for `quota should-run` and
`todo claim`/`todo update`. The controller may still run the same case-local CLI
as deterministic preflight, scheduler, and closeout fallback:
`check`, `quota should-run`, and `todo claim` before the first agent turn;
`quota should-run` and `todo update` around scheduled continuations; and
`status`, `refresh-state`, and `quota spend-slot` during closeout. That
scheduler route is not sufficient for a strict treatment claim by itself.
Compact evidence must distinguish both surfaces:
`goal_harness_prompt_driven_case_cli_call_count`,
`goal_harness_prompt_driven_event_counts`,
`goal_harness_prompt_driven_lifecycle_observed`, and
`goal_harness_prompt_driven_trace.public.json` for worker self-calls, plus
`goal_harness_case_scheduler_command_count`,
`goal_harness_case_rollout_event_counts`, and
`goal_harness_case_rollout_trace.public.json` for controller fallback. If the
prompt-driven lifecycle is absent, classify the run with
`prompt_driven_goal_harness_lifecycle_absent` instead of claiming uplift.
Global Goal Harness commands are optional context only; they must not select
todos for the benchmark case. This keeps parallel cases isolated and prevents
the main project goal or side-agent lane from leaking into benchmark treatment
control.

This is not a submit/upload path and should still be reduced to compact public
evidence before ledger ingestion.

The Harbor bundle requires `codex` and `rg`. `curl` is intentionally optional:
host-copied dynamic curl binaries can fail inside Ubuntu task images because of
shared-library differences. Use the task image's curl, a static curl, or
`--include-curl` only when a runner explicitly depends on it. Before an
official attempt, run a container-local preflight equivalent to:

```bash
PATH=/opt/harbor-agent-tools/bin:$PATH \
  command -v codex >/dev/null && codex --version >/dev/null && \
  command -v rg >/dev/null && rg --version >/dev/null
```

Prefer Harbor's preinstalled Codex agent variant when available, for example
`codex-api-key-no-search`, because it prefixes `/opt/harbor-agent-tools/bin`
during both setup and execution. A plain `codex` agent may pass setup if it
finds the bundle, but still fail execution if the runner shell resets PATH.
If the task container cannot reach the model endpoint after this, classify that
as agent egress/proxy readiness, not as nvm/npm dependency materialization.

For SkillsBench, do not let every task container download Node.js from
`nodejs.org` and then `npm install` the ACP agent. Prewarm a BenchFlow-family
runtime layer once, mount it at `/opt/benchflow`, prefix
`/opt/benchflow/bin:/opt/benchflow/js-agents/bin:/opt/benchflow/node/bin`, and
run the `codex-acp` launch preflight before a real case. Until that preflight is
green, classify SkillsBench as agent-runtime readiness blocked rather than
spending more official attempts.

Use the SkillsBench materializer with host-side cached sources:

```bash
python3 scripts/skillsbench_agent_runtime_layer.py \
  --output ~/goal-harness-bench/benchflow-agent-runtime \
  --node-root ~/goal-harness-bench/cache/node-v22.20.0-linux-x64 \
  --codex-acp-bin ~/goal-harness-bench/cache/codex-acp \
  --pretty
```

If the host has no cached `codex-acp` binary but may use network outside the
case container, use `--use-default-codex-acp-package` once during host
bootstrap. Record that as host dependency materialization, not as a benchmark
case step.

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

### Remote Checkout Patch Protocol

Some benchmark checkouts need a small remote-host patch before they are usable
as a repeated developer runner. Treat that as a first-class, replayable
checkout patch, not as a hidden shell edit:

1. Keep an `upstream-clean` checkout or source archive with a recorded upstream
   repo and commit. Do not patch task text, prompts, scorers, hidden tests, or
   official result parsing.
2. Apply the patch only to a run-work checkout or a clearly marked remote
   checkout. The patch must be generated by a Goal Harness script or a compact
   patch artifact that another developer can re-run after a fresh checkout.
3. Record the patch command, upstream commit, patch purpose, and validation
   smoke in this repo. Record only compact handles in public docs; raw panes,
   logs, task text, trajectories, verifier output, and host paths stay private.
4. Classify the patch as one of:
   `runner_startup_patch`, `dependency_source_patch`,
   `task_image_bootstrap_patch`, or `temporary_upstream_candidate_patch`.
   Anything outside those classes needs separate review before it enters the
   benchmark route.
5. After upstream updates, recreate the run-work checkout, replay the patch
   command, rerun the focused smoke, and update the active case-status note.
   Do not keep layering manual edits on a stale remote tree.

For Terminal-Bench, the current reusable startup patch is the no-rebuild guard:

```bash
python3 scripts/terminal_bench_no_rebuild_guard.py \
  --terminal-bench-root <terminal-bench-checkout> \
  --apply --pretty
```

This patch teaches older checkout shapes to run Compose with `--no-build` when
the operator has explicitly selected `--no-rebuild`. It is allowed because it
only changes runner startup behavior around prewarmed images; it does not
change task contents, scoring, tests, prompts, or result reduction. Pair it
with `examples/terminal-bench-no-rebuild-guard-smoke.py` before relying on it
for a real case.

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

Avoid putting `uvx --from git+https://...` or equivalent Git dependency fetches
in the hot path of repeated benchmark case launches. A wrapper can return
success while the detached runner is still stuck in dependency acquisition, so
the public signal must include job-root/result materialization, not only
process start. Prefer a pre-materialized runner checkout with a local virtual
environment, or stage the dependency source from the operator machine and run
from that checkout. If the process tree shows the runner blocked in Git fetch
before job materialization, classify it as dependency-fetch readiness, not a
benchmark score result.

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

- verify the task directory before launching. Some materialized Terminal-Bench
  checkouts store tasks under `original-tasks/`, not the CLI default `tasks/`.
  For those checkouts pass `--dataset-path original-tasks`; a correct task id
  with the wrong dataset path fails before the agent reaches the case;
- use an all-lowercase run id with only letters, digits, hyphens, or
  underscores; Docker Compose rejects project names with uppercase timestamp
  separators such as `T`. Generate it with the public-safe guard instead of
  hand-formatting timestamps:

  ```bash
  python3 scripts/terminal_bench_safe_run_id.py \
    --prefix <task-id>-host-codex-goal \
    --pretty
  ```
- pass `--output-path` as the parent runs directory and let Terminal-Bench
  create the run-id subdirectory itself; pre-creating that directory can make
  the runner think it is resuming a run and fail before execution;
- keep `--no-upload-results` explicit for every developer smoke;
- start with `--no-rebuild` only after the task image already exists, otherwise
  record the image/build blocker instead of hiding it behind a score result.

Before trusting `--no-rebuild`, guard the local Terminal-Bench checkout:

```bash
python3 scripts/terminal_bench_no_rebuild_guard.py \
  --terminal-bench-root <terminal-bench-checkout> \
  --apply --pretty
```

Terminal-Bench skips the explicit `docker compose build` step when
`--no-rebuild` is set, but older checkout shapes still call
`docker compose up -d` without `--no-build`. Because task compose files usually
include `build:`, Compose can silently rebuild anyway and strand a case in
BuildKit. The guard is a local runner-startup patch only: it does not change
task text, scoring, verifier behavior, or official result parsing.

If `compose up --no-build` starts the prewarmed image but Terminal-Bench reports
that runner utilities such as `tmux` or `asciinema` are missing, derive a
task-image bootstrap layer once and retag it to the Terminal-Bench client image
name:

```bash
python3 scripts/terminal_bench_task_image_bootstrap.py \
  --source-image <prebuilt-task-image> \
  --target-image tb__<task-id>__client \
  --work-dir <workspace>/image-bootstrap/<task-id> \
  --network-host \
  --execute --pretty
```

Use a bounded timeout and a known mirror for apt-based images. This is still a
task-image startup prerequisite, not per-case agent runtime installation and
not a scoring or verifier change.

When the task image is ready but Codex auth and runtime should stay on the
benchmark host, run Terminal-Bench through the host Codex Goal custom agent:

```bash
export PYTHONPATH=<goal-harness-checkout>/scripts:${PYTHONPATH:-}
RUN_ID=$(python3 <goal-harness-checkout>/scripts/terminal_bench_safe_run_id.py \
  --prefix <task-id>-host-codex-goal | python3 -c 'import json,sys; print(json.load(sys.stdin)["safe_run_id"])')
tb run \
  --dataset-path <tasks-dir> \
  --task-id <task-id> \
  --output-path <run-parent> \
  --run-id "$RUN_ID" \
  --no-upload-results \
  --no-rebuild \
  --agent-import-path terminal_bench_host_codex_goal_agent:HostCodexGoalAgent \
  --agent-kwarg goal_surface=app_server \
  --agent-kwarg goal_timeout_sec=1200
```

This uses Codex native Goal mode on the host through the app-server Goal API
and instructs it to operate on the task container through `docker exec`. It
keeps Codex login state, model access, and agent runtime outside the benchmark
case container while the container remains responsible for task files and
official tests. The TUI `/goal` surface is a manual fallback only; do not count
it as the default baseline when app-server `thread/goal/set`,
`thread/goal/get`, and `turn/start` are available.

For a Goal Harness prompt-polling treatment arm, keep the same host agent and
explicitly request the case lifecycle packet:

```bash
tb run \
  ... \
  --agent-import-path terminal_bench_host_codex_goal_agent:HostCodexGoalAgent \
  --agent-kwarg goal_surface=app_server \
  --agent-kwarg goal_timeout_sec=1200 \
  --agent-kwarg goal_harness_mode=codex_goal_harness \
  --agent-kwarg goal_harness_access_packet_mode=compact \
  --agent-kwarg goal_harness_case_id=<task-id> \
  --agent-kwarg goal_harness_arm_id=goal_harness_prompt_polling_test \
  --agent-kwarg goal_harness_max_rounds=5
```

This injects the shared `benchmark_case_lifecycle_contract` into the worker
prompt and compact app-server metadata. A Terminal-Bench treatment run remains
incomplete evidence until the per-case Goal Harness lifecycle can be observed:
`quota_should_run`, `todo_claim_or_update`, bounded work/continuation, official
case result or validation, `refresh_state`, and `quota_spend`.
The app-server host agent treats the benchmark completion marker and official
verifier as the success path. It drains app-server events opportunistically and
writes a compact turn file with `turn_completed_observed`,
assistant-message counters, and `completion_marker_observed`, but missing or
late `turn/completed` is diagnostic only. Do not use `turn/completed` as a hard
failure gate for Terminal-Bench: doing so can change execution semantics by
terminating a still-running Goal turn before the marker or verifier has a chance
to reflect the case outcome.

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

When Terminal-Bench reaches official closeout, reduce the official result before
writing the run ledger. The official `results.json` may include trial-level
fields such as task instruction, parser details, and recording paths, so use the
metadata-only route by default:

```bash
python3 scripts/terminal_bench_official_result_reducer.py \
  --metadata-only \
  --run-metadata-json <terminal-bench-run>/run_metadata.json \
  --mode terminal_bench_host_codex_app_server_goal \
  --pretty
```

The reducer emits both `terminal_bench_official_result_reducer_v0` and a
compact `benchmark_run_v0` projection suitable for
`goal-harness benchmark run-ledger-upsert`. If a run needs `results.json`, pass
it explicitly and rely only on the reducer's top-level summary / allowlisted
trial counters; never publish trial instruction, parser output, recording
paths, raw logs, task text, trajectories, or command argv.

For Harbor-backed Terminal-Bench launches on a cloud host, keep the operator
loop explicit:

1. Launch inside `tmux` with a lowercase job name and private runner log.
2. Write `status.env` and a bounded public file list even on non-zero exit;
   use `set +e` around the runner so the status file is not skipped.
3. Treat wrapper exit code, process state, job root, job lock, and compact
   result as separate facts. `rc=0` for the wrapper only means the wrapper
   completed; it does not prove the benchmark case reached the agent.
4. Validate that the task filter matches the selected dataset before spending
   an agent attempt. A filter that matches zero tasks is a launch-shape
   blocker, not model or benchmark performance.
5. If `tasks/<name>` is passed as a relative path, run Harbor from the checkout
   that actually contains that `tasks/` tree. A wrong current directory can
   fail before Docker or Codex start and should be fixed locally, not reported
   upstream.

For SkillsBench, prove the verifier dependency substrate before claiming a
no-upload task result. A timeout-looking failure can actually be a missing
verifier launcher surface: the verifier may need minimal Python, pip, curl,
certificates, `uv`, and `uvx` before it can run the official oracle sanity path.
Do not repair that first by globally extending timeouts.

For the Codex baseline arm, use the native app-server Goal route instead of the
older slash-prefix experiment. The SkillsBench route name is
`codex-app-server-goal-baseline`; it requires host Codex app-server Goal
methods `thread/start`, `thread/goal/set`, `thread/goal/get`, and `turn/start`.
Generate the public-safe plan first:

```bash
python3 scripts/skillsbench_automation_loop.py \
  --task-id llm-prefix-cache-replay \
  --route codex-app-server-goal-baseline \
  --plan-only
```

The plan must show
`agent_execution_mode=host_codex_app_server_goal_worker`,
`codex_app_server_goal_worker_turn_start_required=true`, and
`codex_app_server_goal_worker_remote_command_file_bridge_required=true`.
By default it should also show
`codex_app_server_goal_worker_remote_command_file_bridge_ready=false` and
`codex_app_server_goal_worker_runner_integration_ready=false`.

There are two distinct gates for a real scored launch:

1. Materialize a bounded command/file bridge so the host Codex app-server Goal
   worker can operate on the BenchFlow sandbox where task files and edits live.
   A host cwd that cannot see the sandbox is not a valid fallback.
2. Wire that host worker through BenchFlow's ACP transport so official task
   staging and verification still run through BenchFlow.

The second gate is implemented through the host-local ACP relay. In
`codex-app-server-goal-baseline`, pass `--host-local-acp-launch` only after the
bridge probe is green; the launcher then starts
`scripts/skillsbench_local_acp_relay.py --app-server-goal-worker`, and the
relay delegates each ACP `session/prompt` to
`scripts/skillsbench_host_codex_goal_worker.py`. This preserves BenchFlow as
the official task stager/verifier while Codex runs through native app-server
Goal methods on the host:

```bash
python3 scripts/skillsbench_automation_loop.py \
  --task-id llm-prefix-cache-replay \
  --route codex-app-server-goal-baseline \
  --remote-command-file-bridge-ready \
  --host-local-acp-launch \
  --plan-only
```

With both flags, the plan should show
`codex_app_server_goal_worker_remote_command_file_bridge_ready=true` and
`codex_app_server_goal_worker_runner_integration_ready=true`. Without
`--host-local-acp-launch`, a real launch must still fail closed as
`SkillsBenchNativeGoalWorkerIntegrationPending`.

A full launch of this route must fail closed rather than falling back to
`codex-acp`, a slash-prefix `/goal` prompt, or a host-only workspace. The
host-side worker surface is:

```bash
python3 scripts/skillsbench_host_codex_goal_worker.py \
  --task-id <task-id> \
  --contract-only
```

When the worker is launched from a benchmark host wrapper rather than from the
Goal Harness checkout, set the import path explicitly so shared driver modules
are resolved from the shipped checkout:

```bash
PYTHONPATH=<goal-harness-checkout>:<goal-harness-checkout>/scripts \
  python3 <goal-harness-checkout>/scripts/skillsbench_host_codex_goal_worker.py \
    --task-id <task-id> \
    --contract-only
```

When used for a private case, the same worker reads the private prompt file and
workspace path on the benchmark host, invokes Codex app-server Goal mode, waits
for `turn/completed`, and writes the assistant response only to a private
response file for the surrounding runner. The public JSON records compact turn
proof, assistant-message hash/size, and method counters only. Do not copy raw
task text, raw assistant response, raw trajectory, raw logs, Goal Harness state,
credentials, or host paths into the compact result. Keep
`codex-goal-mode-baseline` for historical slash-prefix probes only; it is not a
scored Codex Goal baseline.

For a scored SkillsBench route, the worker should be called with an explicit
private output target:

```bash
python3 scripts/skillsbench_host_codex_goal_worker.py \
  --task-id <task-id> \
  --work-dir <private-case-workdir> \
  --prompt-file <private-prompt-file> \
  --response-text-file <private-agent-response-file> \
  --output-json <private-compact-worker-json>
```

For the Goal Harness treatment arm, pass the same private files plus the
per-case/arm lifecycle packet parameters. The packet is public-safe control
context only: it names the isolated case goal, required lifecycle events, and
round budget, while the official SkillsBench verifier remains authoritative
and hidden from the agent loop:

```bash
python3 scripts/skillsbench_host_codex_goal_worker.py \
  --task-id <task-id> \
  --work-dir <private-case-workdir> \
  --prompt-file <private-prompt-file> \
  --response-text-file <private-agent-response-file> \
  --output-json <private-compact-worker-json> \
  --goal-harness-mode codex_goal_harness \
  --goal-harness-access-packet-mode compact \
  --goal-harness-case-id <task-id> \
  --goal-harness-arm-id goal_harness_prompt_polling_test \
  --goal-harness-max-rounds 5
```

The compact worker JSON must then show
`goal_harness_case_lifecycle_packet_injected=true` and a
`benchmark_case_lifecycle_contract` with
`case_isolation_scope=per_benchmark_case_arm`. A baseline run should keep
`goal_harness_access_packet_mode=none` and should not include Goal Harness
lifecycle state.

The compact worker JSON is safe to inspect for lifecycle debugging, but the
response text file is private task execution material and must stay out of
public docs, ledgers, rollout logs, and PRs.

For the host-local ACP relay, materialize public trace as early as the relay
lifecycle, not only after a completed worker turn. The relay should write
compact `relay_lifecycle` traces for `initialize`, `session_new`, and
`prompt_received` when `--worker-public-trace-dir` is configured. These traces
are pure observation: they record stage names and boundary booleans only, never
task text, ACP payloads, stdout/stderr, session ids, response text, or host
paths. Reducers must not treat lifecycle-only traces as solver evidence. A
status such as `worker_connected_no_prompt_trace` or
`worker_prompt_received_no_turn_trace` remains a failed native-worker evidence
check; it only narrows attribution from "trace directory missing" to "BenchFlow
connected but did not reach a countable Goal worker turn."

Use `--remote-command-file-bridge-ready` only after a public-safe bridge probe
has passed. That flag updates only the plan's bridge readiness fields;
`codex_app_server_goal_worker_runner_integration_ready` must remain `false`
until the BenchFlow transport is requested through `--host-local-acp-launch`.
If the full route exits with
`SkillsBenchNativeGoalWorkerIntegrationPending`, the next fix belongs in the
host-worker-to-ACP transport, not in verifier timeout, Docker setup, or model
behavior.

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

SkillsBench runner exceptions need a second look before they become blockers.
BenchFlow can sometimes write official `result.json`/`timing.json` before a
later runner exception. In that case, reduce the official compact result and
mark the runner exception as recovery metadata instead of losing the result.
If no official result exists, close out with a compact runner-error blocker and
do not infer verifier or model behavior from raw logs.

Keep these boundaries:

- do not modify official task truth, scorer, prompt, or leaderboard behavior;
- do not publish raw verifier output, task text, trajectories, local paths, or
  remote run directories;
- record only compact fields such as dependency-prewarm ready/blocked, oracle
  sanity pass/fail, and the next blocker label
  `skillsbench_verifier_dependency_prewarm_required`.

### Upstream Issue Escalation

Open an upstream benchmark issue only after ruling out local route mistakes:
wrong current directory, wrong config schema, missing data-root migration,
missing runner dependency prewarm, stale Goal Harness tool copy, missing Codex
auth, or a launcher that failed to write status. The issue should include a
compact reproduction command shape, upstream commit, runner version, no-upload
boundary, and sanitized blocker label. Do not paste raw task text, raw logs,
trajectories, verifier output, credentials, private hostnames, or local paths.

Good issue candidates are repeated upstream-close failures where the command
schema and working directory match the README, dependencies are
pre-materialized or publicly reachable, and the runner still fails before a
compact result for reasons the benchmark maintainers own.

### SSH Session Hygiene

When the benchmark host is reached through a jump host, GSSAPI, or another
access path with expensive handshakes, do not make every probe open a fresh SSH
session. Keep one SSH multiplexed master warm for the benchmark slice and run
remote commands through that connection. This is an operator workflow
convention, not a Goal Harness protocol requirement.

For repeated benchmark work, prefer a host-local SSH config stanza instead of
spelling the multiplexing flags on every command:

```sshconfig
Host benchmark-host-alias
  ControlMaster auto
  ControlPath ~/.ssh/cm/%C
  ControlPersist 8h
  ServerAliveInterval 30
  ServerAliveCountMax 6
  BatchMode yes
  LogLevel ERROR
```

Use a hashed `ControlPath` such as `%C` so the socket does not expose host
names and is unlikely to exceed path-length limits. `BatchMode yes` keeps
automation from hanging on an interactive auth prompt; `LogLevel ERROR` avoids
known-host chatter in compact run logs when the operator intentionally uses an
ephemeral known-host policy. Keep the real host name, jump path, identity file,
and control socket directory in private operator config.

```bash
BENCHMARK_HOST_ALIAS=<your-ssh-config-alias>
mkdir -p ~/.ssh/cm
chmod 700 ~/.ssh/cm

ssh -MNf "$BENCHMARK_HOST_ALIAS" || ssh -O check "$BENCHMARK_HOST_ALIAS"
ssh -O check "$BENCHMARK_HOST_ALIAS"
ssh "$BENCHMARK_HOST_ALIAS" 'hostname && docker --version && codex --version'
```

Keep commands through the master connection mostly serial when the access path
is sensitive to concurrent authentication. Do not commit SSH aliases, host
names, private keys, jump-host details, raw shell history, or local control-path
values into public benchmark evidence. Public docs should preserve the shape:
create or reuse one master, route bounded probes and launch commands through it,
then let `ControlPersist` expire or close it explicitly with `ssh -O exit` when
the benchmark slice is done.

Long-running benchmark jobs should not live in a foreground SSH session. Start a
stable remote `tmux` session and send benchmark launch commands into it, then
poll with `capture-pane` or compact artifact files:

```bash
BENCHMARK_TMUX_SESSION=gh-bench

ssh "$BENCHMARK_HOST_ALIAS" \
  'tmux has-session -t gh-bench 2>/dev/null || tmux new-session -d -s gh-bench -c "$HOME"'

ssh "$BENCHMARK_HOST_ALIAS" \
  'tmux send-keys -t gh-bench "cd benchmark-work && ./run-no-upload-smoke.sh" C-m'

ssh "$BENCHMARK_HOST_ALIAS" \
  'tmux capture-pane -pt gh-bench -S -120'
```

This gives the operator a durable remote workspace even if the local Codex app,
laptop network, or SSH master connection restarts. Treat `tmux` as benchmark
host bootstrap tooling: installing it on the host is an operations step, not a
benchmark result. Public evidence may say that a long run used a persistent
remote session; raw panes, host paths, task text, verifier output, and command
history still stay private.

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

### Goal Harness Prompt-Polling Test Gate

The comparable Goal Harness test arm is **not** the native Codex Goal baseline
with one extra packet. It is a prompt-driven polling route: an outer controller
injects Goal Harness context, schedules bounded continuation prompts, withholds
official reward/pass-fail/verifier output from the agent, and records a
public-safe controller trace.

Use the shared protocol in `goal_harness.benchmark_core.loop_protocol` across
benchmarks:

| Benchmark family | Baseline arm | Test arm | Shared surface | Benchmark-specific glue |
| --- | --- | --- | --- | --- |
| SkillsBench | `codex-app-server-goal-baseline` for native Goal, or historical `codex-acp-blind-loop-baseline` for old ACP studies | `goal-harness-prompt-polling-test` (`goal-harness-blind-loop-treatment` is a historical alias) | `max5_blind_loop_no_feedback`, `round_rewards`, `official_feedback_blinded_count`, controller trace | BenchFlow `BaseUser` schedules continuation prompts and observes verifier reward only outside the agent-facing prompt |
| SWE-Marathon | host Codex app-server Goal baseline through Harbor | Goal Harness prompt-polling test through the same Harbor task/workdir/no-upload boundary | same protocol id, max-round budget, packet-only blocker classification | host/Harbor controller must restart or continue app-server turns and re-inject prompts without exposing official verifier feedback |
| Terminal-Bench | host Codex app-server Goal baseline or official no-upload runner baseline | Goal Harness prompt-polling test through the same official result/reducer path | same protocol id, max-round budget, compact official result fields | terminal runner glue must use official scorer/reducer after each attempt and keep raw panes/logs private |

The shared layer is intentionally small: route ids, max-round budget, feedback
blinding fields, packet-only classification, and public trace counters. Do not
force every benchmark into the same runner implementation when its upstream
surface differs. Do force every benchmark to use the same labels before a result
is compared: baseline is native Goal mode; test is prompt-driven polling; a
single access packet without scheduled controller trace is only
`packet_only_observation`.

For the test arm, also require the shared per-case lifecycle contract from
`goal_harness.benchmark_case_state`. Each benchmark/case/arm must have an
isolated `benchmark_case_lifecycle_contract` with
`case_isolation_scope=per_benchmark_case_arm`, a canonical
`/app/.codex/goals/<case-arm>/ACTIVE_GOAL_STATE.md` state path, and the public
lifecycle sequence `quota_should_run -> todo_claim_or_update ->
bounded_agent_turn -> validation_or_case_result -> refresh_state ->
quota_spend`. Harbor-family agents inject this contract into the Goal Harness
access packet and compact metadata; other adapters should reuse the same
contract rather than inventing benchmark-specific state markers. A runner that
only performs internal prompt polling without this lifecycle remains
`packet_only_observation` or incomplete treatment evidence.

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
