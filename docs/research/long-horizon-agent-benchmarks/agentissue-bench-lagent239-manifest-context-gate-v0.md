# AgentIssue-Bench `lagent_239` Manifest And Context Gate

Date: 2026-06-12

Scope: public-safe no-run gate for the selected AgentIssue-Bench first tag,
`lagent_239`. This gate verifies registry manifest metadata and defines the
task-context boundary for a future local Codex patch producer.

This gate did not pull Docker images, start containers, run benchmark tests,
generate patches, evaluate patches, invoke Codex or model APIs, copy
credentials, upload results, read hidden references, inspect raw trajectories,
open screenshots, read issue body text, or consume task body, solution, or
test-body material.

## Inputs

- AgentIssue-Bench source pin:
  `alfin06/AgentIssue-Bench@1d498dec35e347c4e7b9e1c318ef28fc5fa97318`
- Selected Docker image:
  `alfin06/agentissue-bench:lagent_239`
- Selected tag source:
  public helper-script tag constants plus Docker Hub metadata.
- Probable public issue route:
  `https://github.com/InternLM/lagent/issues/239`

The issue route was checked only with an HTTP HEAD-style existence probe. The
issue page content, title/body, comments, linked PRs, code diffs, and tests
were not read.

## Manifest Preflight

Command shape used:

```bash
docker manifest inspect alfin06/agentissue-bench:lagent_239
```

Compact result:

- command succeeded;
- schema version: `2`;
- manifest media type: `application/vnd.oci.image.index.v1+json`;
- manifest-list entries: `2`;
- platforms observed: `linux/amd64` and `unknown/unknown`.

Interpretation: the selected tag has a registry-visible `linux/amd64` image
route, so a future Docker host should be able to pull an architecture-compatible
image. This is not an image-pull, container-start, task-readiness, or scoring
signal.

## Context-Source Gate

The manifest preflight solves only image reachability. It does not solve the
patch-producer context problem.

A Codex patch producer needs enough context to decide what to edit and how to
validate the change. For AgentIssue-Bench, that context can only come from a
future explicitly approved route, such as:

- reading the selected public GitHub issue and linked public repository
  material for `InternLM/lagent#239`;
- pulling and inspecting the selected benchmark container after image-access
  approval;
- reading an upstream-provided task map if the benchmark maintainers expose a
  compact public mapping that does not include solution/test-body material.

Until one of those routes is approved, no Codex patch generation should run.
The current route is therefore manifest-ready but context-gated.

## Shared-Host Safety Boundary

For any future shared remote machine use:

- keep Codex auth and `~/.codex` local;
- do not forward or print API keys, Codex auth, shell history, or environment
  dumps;
- do not run official helper scripts unmodified;
- pull at most the selected image after explicit approval;
- mount only the selected patch directory;
- do not use all-tag loops, host networking, global Docker cleanup, upload,
  leaderboard, or submit paths.

## Decision

`lagent_239` is ready for a future execution approval packet from the registry
and image-metadata perspective, but AgentIssue-Bench should not execute yet.
The remaining blocker is the task-context-source decision: either approve a
public task-context read for `InternLM/lagent#239` and then build the local
Codex patch-producer packet, or treat AgentIssue-Bench as blocked and continue
the benchmark-readiness backlog with PerfBench.
