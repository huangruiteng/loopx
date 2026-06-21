# TheAgentCompany Source Preflight v0

Date: 2026-06-12

Status: source-preflight ready, real run still gated.

## Boundary

This preflight inspected only public harness and documentation files from the
official repository. It did not read task instructions, task evaluator files,
checkpoint files, scenario files, task container contents, service password
tables, raw trajectories, screenshots, hidden references, credential values,
task solution material, or task test material. It did not start Docker, pull
images, run setup scripts, invoke Codex/model calls, upload, submit, or touch
leaderboard paths.

The source was pinned to:

- repository: <https://github.com/TheAgentCompany/TheAgentCompany>
- commit: `98b68ef82a47690c316f42fddb05baafaab56851`

The safe checkout used `--filter=blob:none`, `GIT_LFS_SKIP_SMUDGE=1`, and a
root-anchored `--no-cone` sparse checkout. An earlier unanchored sparse pattern
materialized unrelated README paths, including task-directory README files; no
task-directory files from that broad checkout were read. The corrected checkout
contained only:

- `README.md`
- `pyproject.toml`
- `docs/SETUP.md`
- `docs/EVALUATION.md`
- `evaluation/README.md`
- `evaluation/run_eval.sh`
- `evaluation/run_eval.py`
- `evaluation/build_oh_runtime_images.sh`
- `evaluation/summarise_results.py`

## Validation

No dependency installation was needed. Syntax-only validation passed:

- `python3 -m py_compile evaluation/run_eval.py evaluation/summarise_results.py`
- `bash -n evaluation/run_eval.sh evaluation/build_oh_runtime_images.sh`

Checkout guardrails also passed:

- `workspaces/tasks` was absent from the corrected sparse checkout.
- `evaluation/config.toml` was absent.
- `outputs` was absent.

## Runner Findings

The official baseline runner is OpenHands-oriented. It configures an OpenHands
runtime with host networking, mounts an output path into the sandbox, records a
trajectory, initializes the task container, optionally logs into required
services, runs the controller with a short task-file instruction, then invokes
the in-container evaluator and moves compact result plus trajectory files back
to the host output directory.

The official evaluation script is not a safe first-run wrapper for LoopX:

- It iterates over all task directories.
- It relies on task-directory metadata such as scenario presence.
- It constructs task-image names from task-directory names.
- It runs real evaluation.
- It removes task images, OpenHands runtime images, volumes, and Docker system
  leftovers after each task.

The runtime-image prebuild helper is similarly not a safe first-run path because
it iterates over all task directories, pulls every selected task image, and
builds OpenHands runtime images.

The result summarizer is useful as a future reducer pattern, but it reads raw
trajectory files and task dependency metadata. It should not be pointed at real
outputs until artifact classification decides which fields can become public
`benchmark_run_v0` / `benchmark_result_v0` evidence.

## Codex Wrapper Feasibility

A Codex CLI route is feasible in design, but not proven by this no-task
preflight. The likely safe shape is:

1. Keep Codex CLI and Codex auth on the local trusted host.
2. Run the company service stack only after an owner-approved Docker/service
   setup boundary.
3. Select one task image only after task-material access is approved.
4. Start and initialize one task container with the approved environment LLM
   config.
5. Read or route the task instruction only inside the approved task-material
   boundary.
6. Drive the task through a local host-Codex adapter that can issue scoped
   shell/container/browser/file actions without copying Codex auth into the
   task container or a shared remote host.
7. Record raw trajectory and screenshots as local-private artifacts.
8. Run the evaluator only after environment credentials, public default-service
   credentials, and evaluator-key handling are explicitly scoped.
9. Reduce the output to compact score/result metadata before any LoopX
   public artifact, status projection, or report claim.

The official docs also allow agents to browse from outside the container, so a
host-side Codex/browser route is plausible. It still needs a concrete action
adapter and artifact reducer before any real task run.

## First Real-Run Gate

Before TheAgentCompany can become an e2e benchmark candidate, create a separate
single-task launch packet. That packet must specify:

- one selected task image;
- where services run;
- whether the runner is local-only or local-driver plus remote services;
- how task instructions are delivered to Codex without leaking task material;
- how shell/browser/file actions are routed;
- how raw trajectory and screenshots are stored privately;
- which compact result fields may be public;
- what Docker cleanup is allowed;
- how local Codex auth stays out of shared hosts and task containers.

Until that launch packet exists and the owner approves the gated surfaces,
TheAgentCompany should remain a source-ready candidate rather than a heartbeat
execution target.

## Decision

The no-task source preflight answers the wrapper question positively but not
the execution question. There is enough public harness source to design a
Codex-compatible runner wrapper, and the official OpenHands runner provides a
clear reference for initialization, trajectory, evaluation, and result
reduction. However, every useful e2e run still crosses task-material,
credential, Docker-service, image-pull, trajectory, screenshot, and possibly
shared-host boundaries.

Next autonomous benchmark work should move to another public-safe candidate
setup-readiness scan unless the owner explicitly approves TheAgentCompany's
single-task launch-packet boundary.
