# LHTB: LoopX generic_cli heartbeat + Codex exec

This directory defines one LHTB treatment arm:

```text
LoopX source from the current checkout (optionally pinned with LOOPX_EXPECTED_COMMIT)
+ runtime profile generic_cli
+ current LoopX external_scheduler_worker.py
+ one fresh codex exec per heartbeat (never exec resume)
+ openai/gpt-5.6-sol, reasoning=max
+ execution_profile.replan_after_completed_todos=3
```

This runner includes one narrow scheduler compatibility fix in
`scripts/external_scheduler_worker.py`: stop packets may omit
`cold_path_detail.local_scheduler`, so the worker consumes the producer-owned
`scheduler_hint.unchanged_poll.local_scheduler=stop` directive before parsing
a cadence that will never be used. Focused unit and public smoke coverage guard
both emitted stop actions.

The runner keeps the LHTB task manifests authoritative for internet and
verifier policy. It adds an internal model-only network for offline task
containers and stages Codex and LoopX without downloading them in the task.
It reuses the repository's existing
`benchmark/swe-marathon/agents/codex_offline.py` staging adapter instead of
owning a second copy. It does not use the app-server heartbeat agent.

## Run

Prerequisites are an LHTB checkout with its Harbor virtual environment, Docker,
the native Codex bundle, a portable Python 3.11+ tree, and Node 22.6+. Copy
`.env.example` to `.env`, set `LHTB_ROOT`, the model gateway, and local runtime
paths, then run from this directory.

The example uses the RFC 5737 documentation range for the configurable
`lhtb-modelonly` bridge. Bind or proxy an OpenAI-compatible endpoint on the
configured bridge gateway, or change `OPENAI_BASE_URL`,
`LHTB_MODELONLY_SUBNET`, and
`LHTB_MODELONLY_GATEWAY` together. The internal bridge is deliberately not a
general internet route.

```bash
cd loopx/benchmark/LHTB

# No model call. Validate all contracts and render a 46-task Harbor config.
./run.sh preflight

# One quick real trial before any full run.
./run.sh smoke tabular-data-feature-covshift

# Full 46-task arm, default concurrency 4.
./run.sh full
```

Override concurrency without editing YAML:

```bash
CONCURRENCY=10 ./run.sh full
```

The full run is intentionally not launched by setup or preflight.

## Execution flow

For every Harbor trial, the agent performs the following sequence inside that
task's container:

```text
stage native Codex + current LoopX source/profile
  -> expose staged Node 22 through BASH_ENV for Codex login shells
  -> create trial-local registry/runtime/task document
  -> bootstrap one trial-local Goal
       -> Harbor adapter marks the connection provider-prevalidated
       -> skip the generic repo-intake onboarding Todo
  -> register lhtb-codex-heartbeat
  -> configure replan_after_completed_todos=3 and read it back
  -> add the current Harbor phase as a claimed advancement Todo
  -> start LoopX external_scheduler_worker.py
       -> quota should-run --runtime-profile generic_cli
       -> when allowed, invoke wake_once.py
            -> create a unique TURN_ID
            -> heartbeat-prompt --thin --runtime-profile generic_cli
            -> require ok=true and a non-empty current task_body
            -> create a new CODEX_HOME
            -> codex exec --json, with task_body on stdin
            -> save JSONL/receipt and any emitted session files
            -> delete the temporary CODEX_HOME
       -> obey LoopX local_scheduler wait/stop hints
  -> Harbor runs interim/final verifier and owns trial termination
```

There is no `codex exec resume` path. A new Codex model conversation starts on
each wake. Only the task workspace and the trial-local LoopX registry/runtime
persist across wakes. Each wake's `invocation.json` records
`fresh_codex_exec=true`, `resume=false`, and its unique Turn ID.

Codex tool commands run through a login shell, which can replace the inherited
`PATH`. The adapter supplies a trial-local `BASH_ENV` that prepends the staged
Node 22 directory, so later `loopx refresh-state` and settlement commands use
the same qualified Effect runtime without replacing files in the task image.

The exact task is not replaced by one shared objective. The objective is a
short control-plane statement; Harbor's current instruction is written to the
trial-local goal document, and the selected P0 Todo points the model to that
document. Registries are inside their own task containers, so no Goal, Todo,
or scheduler state is shared between the 46 trials.

The Harbor adapter has already validated the project bridge and writes the
benchmark phase as an explicit P0 Todo. Bootstrap therefore uses
`--no-onboarding-scan --onboarding-connection-validation
provider-prevalidated`. This suppresses the unrelated generic repo-intake Todo;
it does not suppress successor Todos created while solving the LHTB task.

## Replan cadence

The runner applies and reads back:

```bash
loopx configure-goal \
  --goal-id lhtb-heartbeat-goal \
  --execution-replan-after-todos 3 \
  --execute
```

This does not roll back the third Todo and does not force a plan change. After
three qualifying advancement Todos completed by this agent without a covering
outcome checkpoint, the next quota/frontier evaluation opens a review/replan
obligation. The review may keep a correct plan (`continue`/`no_change`) or
change it. Open Todos, protocol steps, work by another agent, and unqualified
refreshes do not increment or reset this counter.

## LHTB and fairness settings

- 46 tasks, one attempt each.
- 22 task manifests are offline and 24 allow internet.
- Offline task containers attach only to the internal `lhtb-modelonly` network,
  which reaches the model gateway but has no public route.
- Online tasks retain the task-defined public network and also receive the
  model-only interface.
- The task manifests remain authoritative for verifier mode: 44 shared tasks;
  only `langchain-version-migration` and `nbody-accel-iterative` are separate.
- Harbor remains responsible for interim/final verifier calls, total timeout,
  score collection, artifacts, and `result.json`.
- Verifier feedback is binary (`HB_VERIFIER_FEEDBACK_MODE=binary`).
- Codex native Goal is disabled so the measured continuation owner is LoopX.
- Server-side Codex Web Search is disabled for every task.
- Container isolation is the command sandbox; Codex is launched with the same
  external-container trust assumption as the existing LHTB Codex runner.

The shared verifier mode is intentionally the original LHTB policy. This
runner does not claim stronger hidden-test isolation than the underlying
Harbor/LHTB checkout provides.

## Timeouts

Defaults leave cleanup room between nested layers:

| Layer | Default |
| --- | ---: |
| Harbor agent limit | 5400 s |
| LoopX scheduler process | 5080 s |
| One wake command | 4800 s |
| One Codex exec | 4700 s |

The scheduler can perform multiple shorter wakes within 5080 seconds. A single
long Codex wake can consume most of that budget, which is expected; Harbor's
outer timeout and verifier still determine the trial outcome.

## Outputs

Each run writes to `runs/<job-name>/`, with the generated YAML under
`.generated/` and launcher logs/environment receipts under `reports/`.
Per-trial agent logs include:

```text
agent/
  loopx-install.json
  loopx-worker-phase-*.log
  trajectory.json
  wakes/<TURN_ID>/
    heartbeat.json
    task-body.md
    invocation.json
    codex-events.jsonl
    codex-stderr.log
    receipt.json
    sessions/.../*.jsonl  # present only when this Codex build emits them
```

`trajectory.json` aggregates every fresh Codex wake's JSONL event stream into
one ATIF trajectory. Raw per-wake files remain available for auditing the
LoopX decision, exact task body, model invocation, token usage, and settlement.
If Codex also writes local session files under the temporary `CODEX_HOME`, the
runner copies them before deleting that home; `codex-events.jsonl` remains the
authoritative captured stream when it does not.

## Implementation map

- `run.sh`: environment, LHTB networking, preflight, Harbor launch.
- `configs/heartbeat-generic-cli.yaml`: immutable 46-task template.
- `agents/codex_loopx_heartbeat.py`: Harbor lifecycle and LoopX Goal setup.
- `../swe-marathon/agents/codex_offline.py`: shared native Codex staging.
- `runtime/wake_once.py`: unique Turn, thin heartbeat body, fresh Codex exec.
- `scripts/preflight.py`: fail-closed parity and safety checks.
- `harbor_patch/`: opt-in model-only Docker networking patch.
- `verifier-images/`: the two task-declared separate verifier images.

Official Codex CLI documentation describes `codex exec` as the scripted/CI
entry point and `--json` as newline-delimited JSON events:
<https://learn.chatgpt.com/docs/developer-commands#codex-exec>.
