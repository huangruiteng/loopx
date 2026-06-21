# TheAgentCompany Setup Readiness v0

Date: 2026-06-12

Status: source-ready, environment-gated.

## Public Sources Checked

- Official repository:
  <https://github.com/TheAgentCompany/TheAgentCompany>
- Paper:
  <https://arxiv.org/abs/2412.14161>
- Official website and leaderboard entry point:
  <https://the-agent-company.com/> and
  <https://the-agent-company.com/#/leaderboard>
- Official setup and evaluation docs in the repository README, `docs/SETUP.md`,
  `evaluation/README.md`, `pyproject.toml`, and `workspaces/README.md`.

Public transport was healthy at the time of this scan:

- repository: `TheAgentCompany/TheAgentCompany`
- default branch: `main`
- HEAD: `98b68ef82a47690c316f42fddb05baafaab56851`
- repository visibility: public
- license: MIT
- latest repository push observed through GitHub metadata:
  `2025-11-17T20:31:16Z`
- repository tree API: non-truncated, 1486 paths

## Difficulty Signal

The current arXiv abstract describes TheAgentCompany as a digital-worker
benchmark where agents browse the web, write code, run programs, and
communicate with coworkers inside a self-contained company-like environment.
The same abstract reports that the most competitive tested agent completes
30% of tasks autonomously.

This is a strong LoopX fit because the failure modes are not just patch
generation. A run has to coordinate service readiness, task initialization,
browser/workspace actions, communication tools, result collection, grading,
trajectory storage, screenshots, and checkpoint recovery.

No direct Codex CLI score was found in the checked official surfaces. Treat
TheAgentCompany as "frontier agents still low-success" evidence, not as a
confirmed Codex CLI success-rate data point.

## Setup Surface

The official quickstart is container-first:

- Docker and Docker Compose are required.
- At least 30 GB of free disk is required for the service setup.
- Mac hosts need Docker host networking enabled.
- The setup instructions change Docker socket permissions so containers can
  mount the host Docker socket.
- The setup script is fetched from the companion backup-data release and starts
  the services.
- The service stack includes GitLab, Plane, ownCloud, RocketChat, and an
  API server with pre-baked data.
- The setup may take from a few minutes to about 30 minutes on first launch.
- The setup docs explicitly call out Mainland-China connectivity problems for
  GitHub and Docker image access.

The official OpenHands evaluation route is also environment-heavy:

- Python `>=3.12,<3.14`.
- Poetry.
- OpenHands `0.42.0` as an evaluation dependency.
- Docker buildx.
- Root account for the evaluation script.
- An evaluation config that carries agent and environment LLM credentials.
- An output directory containing trajectories, scores, final states, and
  screenshots.
- Full evaluation usually takes a few days and can resume from checkpoints.

The manual/non-OpenHands route is possible in principle: each benchmark task
is a Docker image, the task container is started with host networking, the task
environment is initialized, the agent works from the task instruction inside
the container, and grading runs through the task image's evaluation entrypoint.
That route still requires task instruction access, environment LLM
credentials for initialization/grading where applicable, trajectory handling,
and task-image pull/run permission.

## Task Surface Boundary

The official workspace docs state that there are 175 task definitions and 175
published task images. A metadata-only count confirmed 175 task directories
and 175 `task.md` files in the public tree.

Important boundary: even repository tree paths and the workspace README expose
task/image names. Future public-safe preflights should avoid dumping full task
path lists and should use aggregate counts or narrowly sparse source
selection instead.

This scan did not read task instructions, task evaluators, checkpoint files,
scenario files, container contents, raw trajectories, screenshots, hidden
references, credential values, or any task solution/test material.

## Codex CLI Feasibility

The benchmark is not intrinsically tied to a cloud provider. It can host the
company services locally or on a cloud machine if Docker, networking, disk,
and image access work.

The Codex CLI route is plausible but not yet proven:

- OpenHands is the official baseline harness, not Codex CLI.
- The manual route can theoretically wrap host Codex CLI as the worker, but
  the wrapper has to decide where task instructions are read, how workspace
  edits/actions are applied, and how the required trajectory is recorded for
  grading.
- Running the service stack on a shared remote development machine should not
  copy local Codex auth material there. A safer split is local Codex driver
  plus remote services/container commands, or an explicitly isolated remote
  credential decision in a future owner-approved batch.
- Because the benchmark records trajectories and screenshots, artifact
  classification must be in place before any real run.

## Current Gates

Do not start a real TheAgentCompany run from heartbeat until these gates are
explicitly selected and approved:

- Docker service setup, including the socket-permission and host-networking
  implications.
- Pulling server and task images.
- Running the backup-data setup script.
- Running as root for the official evaluation script.
- Creating any credential-bearing LLM config.
- Reading task instructions or evaluator/checkpoint/scenario material.
- Capturing or publishing trajectories, screenshots, task outputs, or raw
  grading artifacts.
- Running on a shared remote host where other users' workloads or local Codex
  auth could be exposed.

## Decision

TheAgentCompany is high-value for LoopX, but it is not an immediate
heartbeat-run candidate. It is local/cloud runnable in principle, yet the first
real execution would cross several meaningful operational boundaries:
Docker service bootstrap, task-image execution, root/OpenHands runtime,
credential-bearing LLM config, task instruction access, and trajectory/
screenshot artifacts.

The next public-safe step is a sparse source preflight that excludes
`workspaces/tasks`, evaluator/checkpoint/scenario material, backup-data setup
execution, Docker image pulls/runs, LLM configs, trajectories, screenshots,
credentials, and any task body. That preflight should answer only whether a
Codex-compatible runner wrapper can be designed from public harness code and
docs without consuming task material.
