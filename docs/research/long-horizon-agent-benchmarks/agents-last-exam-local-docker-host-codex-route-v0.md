# Agents Last Exam Local Docker Host Codex Route V0

This note records the non-GCP ALE route that LoopX should use before an
official Google Cloud run is available: local Docker/Colima plus host Codex CLI.
It is a local validation route, not a leaderboard route.

## Source Reading

- The upstream ALE README describes both in-sandbox and out-of-sandbox harness
  shapes, with out-of-sandbox harnesses driving the sandbox through CLI and GUI
  MCP bridges.
- The docs site says VMware and QEMU local providers are planned; until those
  land, Google Cloud is the supported provider. The same page names `static` as
  an interim wrapper for a VM brought up manually.
- The configure page documents `task_data_source: baked_in_sandbox`,
  `gcs_sa_key`, and `output_path: local`; it also warns that local output is
  natural for a local sandbox but fragile for remote large artifacts.
- The source tree includes a Docker provider and Docker executor. For Goal
  Harness, this means a useful local Linux route exists, but it must be treated
  as a scoped local-validation substrate rather than the official GCP path.

## Route

The route is:

1. Run ALE with the Docker provider on the local machine, normally through the
   `ale-kasm` image (`agentslastexam/ale-kasm:latest`) for Linux/CUA-capable
   tasks.
2. Run the already authorized host Codex CLI as the agent executor. Do not
   require OpenRouter, Anthropic, or direct model API keys for this route.
3. Connect host Codex to the sandbox through the local ALE CUA/MCP bridge.
4. Keep `output_path: local` and no-submit/no-upload boundaries for validation.
5. Ingest only compact preflight, run, score, and blocker evidence into Goal
   Harness; do not persist raw trajectories, screenshots, raw logs, credential
   values, or local host paths.

This differs from upstream ALE's in-sandbox `codex` agent path. The upstream
agent can require provider-key configuration inside the sandbox. Our path keeps
Codex auth on the host and uses the bridge as the interface boundary.

## Current Evidence

- The local Docker/CUA substrate has been validated on `agentslastexam/ale-kasm`
  after restoring the local Colima Docker profile and checking published-port
  reachability.
- The `demo/tool_smoke` host-Codex route has completed locally with score `1.0`
  and no upload/submit claim. Treat this as a route canary, not benchmark uplift.
- A formal candidate, `computing_math/os_log_permission_guard_v1`, reached the
  task-data boundary before model work. The important lesson is that
  `requires_task_data=True` cannot blindly rely on
  `task_data_source=baked_in_sandbox` unless baked input presence is verified.

## Task-Data Gate

The local route is allowed only when the task-data substrate is explicit:

- For no-task-data canaries such as `demo/tool_smoke`, pass
  `--requires-task-data false` and keep the route no-upload/no-submit.
- For upstream-current local Docker tasks with `requires_task_data=True`,
  prefer the upstream `configs/environments/docker.yaml` contract:
  `task_data_source: local:task-data`. The host-side `task-data/` directory is
  staged once from the gated Hugging Face archive
  `agents-last-exam-data-archive` by `scripts/fetch_task_data.sh`, then copied
  into each container with `docker cp`.
- Public readiness artifacts may record the sanitized staging route, whether
  `scripts/fetch_task_data.sh` exists, whether `huggingface-cli` is available,
  whether auth was checked, and coarse disk headroom. They must not run the
  fetch, read task-data content, inspect Hugging Face credentials, record local
  paths, or persist archive contents.
- Older `baked_in_sandbox` or `gs://ale-data-public` routes remain valid only
  when the corresponding substrate is explicitly selected and proven. Do not
  silently substitute them for upstream local Docker.
- `task_data_source=none`, missing task-data source, missing local staging, or
  unverified gated-data access must block local launch.

Example public-safe gate:

```bash
loopx benchmark ale-task-material-readiness \
  --source-root <ale-source-root> \
  --selected-task-id demo/tool_smoke \
  --requires-task-data false \
  --task-data-source none \
  --enforce-task-data-source
```

For a formal task:

```bash
loopx benchmark ale-task-material-readiness \
  --source-root <ale-source-root> \
  --selected-task-id computing_math/os_log_permission_guard_v1 \
  --requires-task-data true \
  --task-data-source local:task-data \
  --enforce-task-data-source
```

This command may check the local staging route and tool presence, but public
artifacts must record only booleans, sanitized labels, and coarse disk
headroom.

For a `baked_in_sandbox` candidate, prove the sandbox input directory before
feeding the result into task-material readiness:

```bash
loopx benchmark ale-baked-task-input-readiness \
  --selected-task-id computing_math/os_log_permission_guard_v1 \
  --image agentslastexam/ale-kasm:latest

loopx benchmark ale-task-material-readiness \
  --source-root <ale-source-root> \
  --selected-task-id computing_math/os_log_permission_guard_v1 \
  --requires-task-data true \
  --task-data-source baked_in_sandbox \
  --baked-task-input-readiness-json <compact-baked-input-readiness-json> \
  --enforce-task-data-source
```

To avoid testing one doomed formal task at a time, scan the selected-task pool:

```bash
loopx benchmark ale-baked-task-input-scan \
  --source-root <ale-source-root> \
  --image agentslastexam/ale-kasm:latest
```

The current local scan covered 120 public selected tasks from the official
selected-task lists and found 0 baked-input candidates. Combined with the
candidate task-data scan finding no no-task-data formal candidates in the same
pool, formal local/no-upload ALE runs remain gated on the official
`gs://ale-data-public` substrate proof. These probes start at most tiny Docker
shell checks for directory existence; they do not run tasks, list or read task
data, invoke a model, upload, submit, or record local/container paths.

## CUA And Colima Gate

The local route depends on CUA reachability from host Codex into the sandbox.
On Colima, Docker published-port behavior can require a host-visible readiness
probe or tunnel repair before task launch. This must be a preflight result, not
a manual hidden assumption.

Minimum launch gates:

- Docker CLI and server ready.
- ALE image present or pull explicitly accepted.
- CUA server reachable through the host-visible endpoint.
- Host Codex CLI present and authorized by existing local auth.
- No-task host Codex CUA/MCP E2E passed before task-level work.
- Task-data gate ready for the selected task.
- No upload, no submit, no leaderboard claim.

## Stop Conditions

Stop before launch if any of these is true:

- official GCP execution is required and GCP project/key/bucket prerequisites
  are missing;
- local CUA reachability is unverified;
- the selected task requires data and the task-data gate is not ready;
- executing would require copying host Codex auth material into the sandbox;
- output handling would persist raw trajectories, screenshots, credentials,
  hidden references, raw logs, or local host paths;
- the run would upload, submit, or claim leaderboard evidence.

## Next Action

Use `demo/tool_smoke` as the local route canary and use a formal task only after
the CUA/Colima and task-data gates are both ready. Official GCP quickstart can
resume separately once `gcloud`, `GCP_PROJECT`, `GCP_SA_KEY`, result bucket, and
the default upstream agent key surface are provided.

## Smoke

```bash
python3 examples/agents-last-exam-local-docker-host-codex-route-smoke.py
```
