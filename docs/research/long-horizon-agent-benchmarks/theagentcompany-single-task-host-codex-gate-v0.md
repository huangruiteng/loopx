# TheAgentCompany Single-Task Host-Codex Gate v0

Date: 2026-06-12

Status: no-run gate packet validated; real single-task execution still gated.

## Scope

This packet prepares the smallest public-safe gate before a future
TheAgentCompany single-task host-Codex pilot. It is not a benchmark run and it
does not select a task. Its purpose is to turn the earlier setup-readiness and
source-preflight notes into a deterministic contract for what must remain
private or explicitly scoped before any e2e execution.

The packet keeps all raw task material, selected task paths, service
credentials, task container contents, raw trajectories, screenshots, generated
patches or outputs, hidden references, Docker actions, Codex/model calls,
uploads, submit actions, public ranking paths, and production actions out of
public artifacts.

## Source Evidence

Fresh public-source metadata on 2026-06-12 confirmed:

- repository: <https://github.com/TheAgentCompany/TheAgentCompany>
- default branch: `main`
- HEAD: `98b68ef82a47690c316f42fddb05baafaab56851`
- license: MIT
- recursive tree truncated: `false`
- recursive tree path count: `1486`
- aggregate task-directory tree count: `182`
- aggregate task markdown count: `175`
- evaluation README present: `true`
- evaluation runner entry present: `true`

No task path list or task body was dumped into this artifact. The aggregate
counts are enough for readiness routing and do not create a task-material
surface.

Prior local artifacts:

- `theagentcompany-setup-readiness-v0.md`
- `theagentcompany-source-preflight-v0.md`

## Gate Phases

Source metadata phase: public repository metadata is ready and enough to prove
the runner source is reachable. The tree was not truncated. Task names, task
instructions, evaluator task files, scenario/checkpoint files, configs,
outputs, trajectories, and screenshots remain unread.

Service stack phase: real execution requires a Docker service setup boundary,
including host-networking and socket/permission implications. This packet does
not pull images, start services, run OpenHands/root plumbing, or inspect any
shared-host workload. On a shared remote machine, Codex auth remains local and
unsynced unless a future credential-isolation decision changes that.

Single-task selection phase: no task is selected in this packet. A future pilot
must choose exactly one task inside an approved private or hash-only selector
flow. Raw task material and task instructions stay behind an execution-scope
and task-material boundary.

Host-Codex worker phase: a local Codex CLI route remains plausible because the
official design allows an agent to interact from outside the task container.
However, no Codex CLI or model call was invoked, and no action adapter is
implemented here. A future pilot still needs scoped container shell, browser,
and file-action routing that never copies Codex auth into a task container or
shared host.

Artifact and reducer phase: raw trajectories and screenshots remain private.
The public reducer contract is limited to compact fields such as source
commit, task-selector hash, image-reference hash, runner status, official
score status, duration, and no-upload/no-submit/no-public-ranking booleans.

## Executable Fixture

The deterministic fixture is:

- `examples/theagentcompany-single-task-host-codex-gate-smoke.py`

It emits a no-run packet plus compact `benchmark_run_v0` and
`benchmark_result_v0` projections:

- packet schema: `theagentcompany_single_task_host_codex_gate_packet_v0`
- run schema: `benchmark_run_v0`
- result schema: `benchmark_result_v0`
- official task score status: `not_run`
- control-plane score schema: `control_plane_score_core_v0`
- terminal state: `blocked_before_single_task_execution_scope`

The fixture asserts that no task was selected, no task material was read, no
service stack was started, no Docker action occurred, no Codex/model call was
made, no raw trajectory or screenshot was read, no credential was touched, and
no upload/submit/public-ranking path was used.

Validation commands:

```bash
python3 examples/theagentcompany-single-task-host-codex-gate-smoke.py
python3 -m py_compile examples/theagentcompany-single-task-host-codex-gate-smoke.py
loopx check \
  --scan-path examples/theagentcompany-single-task-host-codex-gate-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/theagentcompany-single-task-host-codex-gate-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

## Decision

TheAgentCompany is now a source-ready and gate-packet-ready low-success
long-horizon benchmark candidate. It is not yet execution-ready. The next safe
step is a route choice:

- request a separate execution-scope decision for either SWE-Bench Pro or
  TheAgentCompany;
- or prepare another reachable low-success benchmark gate packet.

Any TheAgentCompany real pilot must still explicitly approve the service-stack
route, one-task material boundary, host-Codex action adapter, credential
isolation, private artifact handling, compact result reducer, and
no-upload/no-submit/no-public-ranking scope.
