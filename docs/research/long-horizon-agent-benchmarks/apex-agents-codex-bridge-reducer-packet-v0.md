# APEX-Agents Codex Bridge Reducer Packet v0

Date: 2026-06-12

Status: no-run bridge/reducer packet ready, real run still gated.

## Boundary

This packet is a no-run design artifact. It does not accept Hugging Face
dataset conditions, load task rows, select a real task, read task prompts,
rubrics, gold outputs, world archives, task files, screenshots, trajectories,
credentials, hidden references, task solutions, or task tests. It does not
start Docker, install dependencies, invoke Codex/model APIs, run an agent, run
grading, upload, submit, touch leaderboard paths, or inspect shared-host
workloads.

It builds only on the public setup and source preflights:

- `apex-agents-setup-readiness-v0.md`
- `apex-agents-source-preflight-v0.md`
- official runner source:
  `Mercor-Intelligence/archipelago@77a872577ce1b33cb71817465e844e52eadd3cbe`

## Decision

Prefer the **external host-Codex adapter** as the first APEX-Agents route.

Do not make an in-tree `codex_cli_agent` the first route. It is architecturally
possible, but it encourages running Codex inside the Archipelago agent process
or container and makes credential isolation harder on local Docker or shared
remote hosts.

The preferred shape is:

1. Keep Codex CLI auth/session material on the trusted local host only.
2. Run Archipelago environment services only after a separate Docker approval.
3. Expose the Archipelago MCP gateway locally or through a controlled tunnel.
4. Let a local host process translate Codex actions to MCP calls.
5. Store all raw transcripts, task instructions, generated artifacts,
   snapshots, screenshots, and grader rationales in a local-private run
   directory.
6. Emit only compact public-safe `benchmark_run_v0` /
   `benchmark_result_v0` evidence after a reducer pass.

## Bridge Contract

The bridge should be split into three layers.

### Provider Layer

Purpose: own environment lifecycle and endpoint discovery.

Allowed future actions after approval:

- start one Archipelago environment instance;
- wait for `GET /health`;
- apply one MCP server config through `POST /apps`;
- capture redacted service readiness facts.

Forbidden by default:

- dataset download or task selection;
- Docker image pull/build/run from heartbeat automation;
- broad Docker cleanup;
- upload/submit/leaderboard calls;
- copying `~/.codex`, API keys, shell history, `.env` files, SSH private keys,
  raw trajectories, screenshots, task files, gold files, or world archives to a
  shared host.

Provider compact facts:

```text
provider_kind=archipelago_environment_mcp
archipelago_commit=77a872577ce1b33cb71817465e844e52eadd3cbe
environment_health_observed=<bool>
mcp_servers_configured_count=<int>
mcp_server_names_hash=<hash-or-stable-redacted-list>
docker_started=<bool>
dataset_material_loaded=<bool>
codex_auth_copied=false
upload_enabled=false
submit_enabled=false
leaderboard_enabled=false
```

### Action Bridge Layer

Purpose: convert between local Codex execution and the Archipelago MCP gateway.

The action bridge must run on the trusted local host. It may create a local
private transcript but should not expose raw prompt, file, screenshot, or task
artifact content in public LoopX output.

Minimum responsibilities:

- connect to the MCP gateway URL;
- enumerate available tools without persisting raw task/tool payloads publicly;
- pass local Codex tool decisions to MCP calls;
- record whether tool-call errors, timeouts, or missing tools occurred;
- produce either an official `AgentTrajectoryOutput`-compatible JSON or a
  private transcript that can be converted to that shape.

Bridge compact facts:

```text
bridge_kind=host_codex_external_mcp_adapter
codex_surface=local_cli
codex_auth_location=trusted_local_host_only
agent_output_shape=agent_trajectory_output_or_private_convertible_transcript
raw_transcript_private=true
task_prompt_public=false
rubric_public=false
gold_output_public=false
world_files_public=false
screenshots_public=false
```

### Grading/Reducer Layer

Purpose: keep official scoring and public LoopX evidence separate.

After an approved real run, grading may use private initial/final snapshots,
trajectory, verifiers, eval configs, scoring config, and optional golden
snapshots. Public artifacts must not include grader prompts, grader rationales,
raw verifier criteria, raw changed documents, raw screenshots, or generated
work products unless a later boundary pass explicitly allows them.

The reducer should produce:

- one private raw run directory;
- one private grading output directory;
- one public compact `benchmark_run_v0` event;
- optionally one public compact `benchmark_result_v0` event.

## Public Event Shape

`benchmark_run_v0` for APEX-Agents should reuse the existing passive contract
but adapt source fields:

```text
schema_version=benchmark_run_v0
source_runner=archipelago
benchmark_id=apex-agents
benchmark_revision=92c86856cf1b11f9833a8a076b3a45a63afa3929
archipelago_commit=77a872577ce1b33cb71817465e844e52eadd3cbe
mode=host_codex_external_mcp_adapter
task_selector_kind=redacted_single_task
task_selector_hash=<hash>
domain=<banking|consulting|law|unknown>
world_selector_hash=<hash>
agent.codex_surface=local_cli
agent.model_label=<public-label-only>
progress.total=1
progress.completed=<0-or-1>
progress.errored=<0-or-1>
metrics.input_tokens=<if-runner-provides-compact-value>
metrics.cache_tokens=<if-runner-provides-compact-value>
metrics.output_tokens=<if-runner-provides-compact-value>
metrics.cost_usd=<if-runner-provides-compact-value>
trials[0].task_hash=<hash>
trials[0].runner_status=<completed|failed|timeout|blocked|error>
trials[0].final_score=<0..1-or-null>
trials[0].criterion_count=<int-or-null>
trials[0].criterion_pass_count=<int-or-null>
trials[0].exception_type=<public-class-or-null>
validation.no_upload=true
validation.no_submit=true
validation.no_leaderboard=true
validation.raw_artifacts_private=true
```

Do not include task names, prompts, rubrics, gold-output file names, world zip
names, document names, generated file contents, raw MCP payloads, raw
trajectory messages, screenshot paths, local absolute paths, credential names,
or provider account details in public events.

`benchmark_result_v0` should keep official task score and LoopX control
value separate:

```text
official_task_score.final_score=<same compact score as official grading>
official_task_score.source=archipelago_grading
official_task_score.leaderboard_claim=false
control_plane_score.schema_version=control_plane_score_core_v0
control_plane_score.components.restartability=<0..1>
control_plane_score.components.stale_state_avoidance=<0..1>
control_plane_score.components.evidence_discipline=<0..1>
control_plane_score.components.boundary_safety=<0..1>
control_plane_score.components.writeback_quality=<0..1>
control_plane_score.components.gate_compliance=<0..1>
control_plane_score.components.failure_attribution=<0..1>
control_plane_score.components.overhead=<0..1>
```

## First No-Run Implementation Slice

The next implementation step should still be no-run. It can add a deterministic
local fixture and smoke contract that proves only the bridge/reducer shape:

- fake one redacted APEX task selector hash;
- fake one MCP server readiness map;
- fake one private trajectory metadata object without raw messages;
- fake one grading summary with `final_score`, criterion counts, and no
  rationale text;
- reduce the fixture to `benchmark_run_v0` and `benchmark_result_v0`;
- assert all forbidden raw fields are absent.

This fixture must not import Archipelago, start Docker, use Hugging Face,
invoke Codex, call a model, or read environment credentials. It should be a
LoopX contract smoke only.

## Real-Run Gate

A real APEX-Agents pilot requires an explicit owner decision for all of:

- accepting the gated Hugging Face dataset conditions and contact-info flow;
- selecting exactly one task while controlling prompt/rubric/gold/world
  exposure;
- Docker Compose build/start and cleanup boundaries on the chosen host;
- whether the grader may call an LLM judge and which credential surface it may
  use;
- whether the action bridge may invoke local Codex CLI and with which model
  label;
- where raw trajectory/snapshot/screenshot/generated-artifact files live;
- whether the run is local-only or local-driver plus remote provider;
- no-upload/no-submit/no-leaderboard defaults.

Until that decision exists, APEX-Agents should remain bridge/reducer-ready but
not execution-ready.

## Stop Conditions

Stop immediately if a next step would:

- require accepting or bypassing gated dataset conditions;
- reveal task prompt, rubric, gold output, world file, document name, or task
  selector in public output;
- start Docker or install dependencies without an explicit run selection;
- copy Codex auth/session material away from the trusted local host;
- call an LLM agent or grader;
- write raw trajectory, screenshot, snapshot, generated document, or grader
  rationale into public docs;
- upload, submit, or interact with a leaderboard.

## Decision

The APEX-Agents path is now ready for a no-run LoopX implementation
slice: build a deterministic bridge/reducer fixture and smoke test. That is
the best next autonomous step because it advances reusable LoopX
benchmark capability while preserving every real-run gate.
