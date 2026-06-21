# APEX-Agents Setup Readiness v0

Date: 2026-06-12

Status: setup-readiness complete, real run still gated.

## Boundary

This scan inspected only public benchmark pages, dataset card metadata, and
official Archipelago runner/configuration source. It did not download the
Hugging Face dataset, accept dataset access conditions, load task rows, open
world zip files, read prompts beyond the public example README surface, inspect
rubric/gold output bodies, start Docker, invoke Codex/model APIs, run grading,
upload, submit, touch leaderboard paths, read raw trajectories, screenshots,
credentials, hidden references, task solution material, or task test material.

Public sources checked:

- paper: <https://arxiv.org/abs/2601.14242>
- official leaderboard: <https://www.mercor.com/apex/apex-agents-leaderboard/>
- dataset card: <https://huggingface.co/datasets/mercor/apex-agents>
- official runner repository: <https://github.com/Mercor-Intelligence/archipelago>
- launch blog: <https://www.mercor.com/blog/introducing-apex-agents/>

The official runner source transport is healthy:

- repository: <https://github.com/Mercor-Intelligence/archipelago>
- commit: `77a872577ce1b33cb71817465e844e52eadd3cbe`
- GitHub tree API: non-truncated, `1018` paths observed

The Hugging Face dataset metadata observed via public API reports revision
`92c86856cf1b11f9833a8a076b3a45a63afa3929`, public visibility, automatic
gating, CC-BY-4.0 license metadata, and about `9.04 GB` total file size. The
dataset page requires accepting conditions before content access.

## Benchmark Fit

APEX-Agents is a strong LoopX candidate because it stresses exactly the
kind of long-horizon workplace execution that benefits from recoverability,
state truth, gate discipline, artifact reduction, and bounded operator
intervention.

The official paper describes APEX-Agents as long-horizon, cross-application
professional-services work across investment banking, management consulting,
and corporate law. The dataset card reports `480` tasks across `33` worlds,
binary rubric criteria, gold outputs for every task, included world assets, and
applications such as calendar, chat, code execution, documents, filesystem,
mail, PDFs, spreadsheets, and presentations.

Difficulty is high enough to be useful:

- the arXiv abstract reports the best submitted Pass@1 in the paper at
  `24.0%`;
- the dataset card baseline table reports `GPT-5.2` at `23.0%` Pass@1 and
  `GPT-5` at `18.3%` Pass@1;
- the live Mercor page observed on 2026-06-12 reports newer leaderboard entries
  including `GPT 5.5 (xHigh)` at `38.4% +/- 3.9%`, still far below solved.

No direct host-Codex CLI score was found in the official paper, dataset card,
Mercor leaderboard, Epoch page, Archipelago docs, or the public search results
checked in this scan. Current evidence should therefore be treated as
agent/model leaderboard evidence, not a Codex CLI benchmark result.

## Official Runner Shape

Archipelago has three main components:

- `environment`: a Dockerized MCP gateway and data population/snapshot service;
- `agents`: an extensible agent runner with a registry of agent
  implementations;
- `grading`: snapshot-diff and rubric-based grading.

The official Hugging Face task example is a full e2e runner. Static source
inspection shows it:

1. installs locked `agents` and `grading` dependencies with `uv sync`;
2. downloads task and world metadata manifests from the gated Hugging Face
   dataset;
3. starts a fresh environment with `docker compose down -v` and
   `docker compose up -d --build`;
4. downloads and populates the selected world snapshot;
5. optionally downloads and overlays selected per-task files;
6. configures all MCP servers;
7. writes task prompt-derived initial messages;
8. runs `runner.main` against `http://localhost:8080/mcp/`;
9. saves a raw trajectory and final snapshot;
10. when the agent completes, derives rubric verifiers and runs grading.

The example agent configuration uses `react_toolbelt_agent`, timeout `3600`,
and `max_steps` `50`. The example MCP config starts nine servers: calendar,
chat, code execution, spreadsheets, filesystem, mail, PDF, presentations, and
documents. The sample orchestrator config currently points at a Vertex/Gemini
model, so an OpenAI/Codex route would need an explicit model/agent adapter
rather than running the example unchanged.

## Codex Wrapper Feasibility

There are two plausible Codex routes, neither proven by this setup scan:

1. **In-Archipelago custom agent**: add a new `codex_cli_agent` to the
   official `agents/runner/agents` registry. This would keep the official
   environment/grading lifecycle but requires careful auth isolation and a
   bridge that lets Codex issue MCP actions without copying `~/.codex` into a
   task container or shared remote host.
2. **Host-Codex external adapter**: start only the Archipelago environment and
   MCP gateway, then drive the MCP endpoint from local Codex while keeping raw
   trajectory, screenshots, snapshots, and credentials private. This is more
   aligned with the remote-GPU Route B principle, but needs a concrete MCP
   action bridge and compact result reducer before any task run.

Either route is attractive for LoopX because the benchmark already
generates trajectories, snapshots, verifier results, and final scores. The
public LoopX artifact should ingest only compact fields such as task id
hash/selector, world/domain metadata, runner status, final score, criterion
counts, token/cost fields if available, timeout/failure class, and validation
hashes. Raw task prompts, rubrics, gold outputs, world files, trajectories,
screenshots, and document artifacts must remain private unless separately
approved.

## Real-Run Gates

APEX-Agents should not be launched from heartbeat automation yet. A real pilot
needs explicit approval for:

- accepting the gated Hugging Face dataset conditions and contact-info flow;
- selecting one task while controlling exposure to prompt/rubric/gold/world
  material;
- Docker Compose build/start/volume cleanup behavior on the chosen host;
- LLM credentials for agent and grader, or a Codex CLI bridge that keeps local
  auth out of containers and shared machines;
- raw trajectory, snapshot, screenshot, and generated document handling;
- whether grading may use an LLM judge and which model/provider;
- no-upload/no-submit/no-leaderboard boundaries;
- whether to run locally or through the credential-isolated remote provider
  route.

The official example also logs a prompt preview and writes `initial_messages`,
`trajectory`, `final_snapshot`, `verifiers`, and `grades` under its output
directory. Those paths are useful for a private reducer but must not be copied
into public LoopX docs.

## Next Safe Step

The next autonomous step can be a sparse no-task Archipelago source preflight:

- clone only README/setup/config/runner source needed to validate the agent
  registry, environment health endpoint, MCP config shape, and grading CLI
  source;
- exclude `examples/hugging_face_task/README.md`, task output directories,
  dataset files, and any task/material-bearing paths;
- run syntax-only validation for selected runner modules and shell scripts;
- sketch a no-task Codex bridge contract and compact reducer boundary.

That source preflight still must stop before Hugging Face dataset access, task
selection, Docker build/start, model invocation, grading, uploads, trajectories,
screenshots, credentials, or leaderboard paths.

## Decision

APEX-Agents is a higher-priority benchmark candidate than another generic
fixture because it is public, current, hard, cross-application, objectively
scored, and already has an execution/grading framework. It is not ready for an
autonomous real run because the dataset is gated, the official example consumes
task/gold/world material, and both agent and grader paths need credentials.

Keep it in the active shortlist. Prefer a no-task source preflight next unless
the owner approves one of the real-run gates or asks to pivot to a different
candidate.
