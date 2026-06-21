# APEX-Agents Source Preflight v0

Date: 2026-06-12

Status: source-preflight complete, real run still gated.

## Boundary

This preflight inspected a root-anchored sparse checkout of official
Archipelago source and selected example configuration files. It did not accept
Hugging Face dataset access conditions, download dataset files, load task rows,
read task prompts/rubrics/gold outputs/world archives, run Docker, install
dependencies, invoke Codex/model APIs, run an agent, run grading, upload,
submit, touch leaderboard paths, read raw trajectories, screenshots,
credentials, hidden references, task solution material, task test material, or
inspect shared-host workloads.

The final validated checkout used `GIT_LFS_SKIP_SMUDGE=1`, `--depth=1`, and
root-anchored non-cone sparse patterns against:

- repository: <https://github.com/Mercor-Intelligence/archipelago>
- commit: `77a872577ce1b33cb71817465e844e52eadd3cbe`

The final source envelope contained `43` files, about `2.99 MB`, limited to:

- top-level README/license/citation metadata;
- `agents` README, package metadata, agent registry, runner entrypoint, and
  built-in agent implementation source;
- `environment` README, Docker metadata, FastAPI entrypoint, gateway router,
  data population/snapshot routers, and settings source;
- `grading` README, package metadata, runner entrypoint, model definitions,
  eval registry, and selected `output_llm` filtering/scoring support source;
- APEX example JSON configs only: agent config, MCP config, orchestrator
  config, grading settings, eval configs, and scoring config.

The checkout intentionally excluded the Hugging Face example README, example
runner script, example main Python runner, output directories, dataset files,
task/world manifests, task files, gold files, world archives, trajectories,
snapshots, initial messages, and any generated benchmark outputs.

## Validation

Path guardrails passed: no sparse-checkout file path matched task/world/gold
data directories, output directories, trajectory/snapshot/initial-message
outputs, dataset manifests, or the task-material-bearing example README/main
runner/script paths.

Syntax-only validation passed with `python3 -m py_compile` over selected
source files from:

- `agents/runner`;
- `environment/runner`;
- `grading/runner`;
- selected `grading/runner/evals/output_llm` support modules.

The APEX example JSON configs parsed successfully:

- agent config: `react_toolbelt_agent`, `timeout=3600`, `max_steps=50`;
- MCP config: `calendar_server`, `chat_server`, `code_execution_server`,
  `docs_server`, `filesystem_server`, `mail_server`, `pdf_server`,
  `sheets_server`, `slides_server`;
- orchestrator config: `vertex_ai/gemini-3.1-pro-preview`;
- eval config: `ec_output_llm` / `output_llm`;
- grading settings and scoring config: JSON object schemas present.

## Source Findings

The official runner has no built-in Codex CLI agent today. The agent registry
currently wires built-in `loop_agent` and `react_toolbelt_agent` definitions
with timeout, max-step, tool-call timeout, and LLM-response-timeout fields.
Adding a Codex route inside Archipelago would require a new registry entry and
agent implementation rather than a pure config change.

The agent runner CLI is bridge-friendly at the process boundary: it accepts
`--trajectory-id`, `--initial-messages`, `--mcp-gateway-url`,
`--agent-config`, `--orchestrator-model`, optional extra/custom args, and
`--output`. A Codex-compatible bridge must still produce or convert into the
expected `AgentTrajectoryOutput` shape if it wants to reuse the official
grading runner unchanged.

The environment service exposes the useful no-task boundaries:

- `GET /health` for readiness;
- `POST /apps` to hot-swap MCP server configuration;
- `POST /data/populate` and `POST /data/populate/s3` for data loading;
- `POST /data/snapshot` and `POST /data/snapshot/s3` for final state capture.

Those endpoints make a host-Codex external adapter plausible, but a real task
would still require dataset material and Docker startup. This preflight did not
exercise any endpoint or start the container.

The selected MCP config confirms a broad workplace-tool surface: calendar,
chat, code execution, documents, filesystem, mail, PDF, spreadsheets, and
presentations. This is a good fit for LoopX because failures will likely
involve planning, file discovery, evidence discipline, recovery, artifact
selection, and long-context state rather than just code patching.

The grading runner requires initial snapshot, final snapshot, trajectory,
grading settings, verifiers, eval configs, scoring config, and optional golden
snapshots. It emits scoring results including `final_score`. The selected
`output_llm` artifact filter source supports file-type scoping such as final
answer only, document files, PDFs, spreadsheets, presentations, text/code, and
images. That is promising for a compact reducer, but real grading still needs
LLM judge credentials and task rubric/verifier material.

## Bridge And Reducer Implications

There are two viable next designs:

1. **In-tree `codex_cli_agent`**: implement a new Archipelago agent registry
   entry that shells out to local Codex CLI. This stays close to the official
   runner but risks auth leakage if run inside a Docker/shared-host context.
2. **External host-Codex adapter**: use the environment MCP gateway from the
   trusted local host, keep Codex auth outside Archipelago containers and
   shared machines, then convert the resulting local-private transcript into
   the official trajectory shape required by the grading runner.

The second route is safer for this project. It matches the existing
credential-isolated remote-provider pattern and lets LoopX keep raw
task prompts, trajectories, snapshots, screenshots, generated artifacts, and
grader rationales private while reducing only compact evidence into public
`benchmark_run_v0` / `benchmark_result_v0` rows.

Before a real run, the bridge packet should define:

- how local Codex connects to `/mcp/` without copying `~/.codex`;
- how MCP actions map into Codex-visible tool calls;
- how task instructions are supplied only after owner-approved task-material
  access;
- whether the bridge writes official `AgentTrajectoryOutput` directly or
  converts a local transcript after the run;
- which private files may feed grading;
- which compact fields may be emitted publicly;
- how to prevent upload/submit/leaderboard paths by default.

## Decision

APEX-Agents remains source-ready and high priority, but not e2e-ready. The
official Archipelago code gives enough structure to design a Codex bridge and
result reducer without touching dataset content. The next autonomous step
should be a no-run Codex bridge/reducer packet. A real pilot still requires
explicit owner approval for gated dataset access, task/rubric/gold/world
material, Docker Compose, LLM agent/grader credentials or local Codex bridge,
raw trajectory/snapshot/screenshot handling, and no-upload/no-submit
boundaries.
