# AgentIssue-Bench One-Tag No-Run Launch Packet

Date: 2026-06-12

Scope: public-safe launch packet for the first AgentIssue-Bench pilot shape.
This is still no-run: it selects one public primary tag from script constants
and Docker Hub metadata, defines a Codex CLI patch-file wrapper contract, and
replaces unsafe helper-script behavior with scoped command boundaries.

This packet did not pull Docker images, start containers, run benchmark tests,
generate patches, evaluate patches, invoke Codex or model APIs, copy
credentials, upload results, read hidden references, inspect raw trajectories,
open screenshots, or consume task body, solution, or test-body material.

## Source Pin

- Official repository: https://github.com/alfin06/AgentIssue-Bench
- Local readiness clone pin:
  `alfin06/AgentIssue-Bench@1d498dec35e347c4e7b9e1c318ef28fc5fa97318`
- Freshness check on 2026-06-12: fetched upstream HEAD matched the local pin.
- Docker Hub source:
  https://hub.docker.com/r/alfin06/agentissue-bench/tags

## Selected Tag

Selected first tag: `lagent_239`

Selection evidence:

- `lagent_239` is in the 50-tag primary list from the official helper scripts.
- Docker Hub public metadata reports all 50 primary tags present.
- Docker Hub public metadata reports `lagent_239` as the smallest primary tag
  in this scan, with `full_size=88274422` bytes and last update
  `2025-10-10T21:20:04.719906Z`.

Rationale: starting from the smallest primary tag minimizes shared-host disk and
pull risk once a future execution gate permits image access. This is only a
capacity/route choice; it is not task-difficulty evidence and does not imply a
score expectation.

## Safe Command Boundary

Allowed before owner approval for execution:

- parse script-level tag constants;
- query Docker Hub tag metadata;
- optionally run a manifest-only check for the selected image;
- write launch packets, wrapper contracts, and compact preflight evidence.

Forbidden in this launch packet:

- `python pull_images.py`;
- `python test_agentissue_bench.py`;
- `python eval_patches.py`;
- `python remove_images.py` unless cleaning a known owned tag after an
  explicitly approved future run;
- `docker pull`;
- `docker run`;
- global Docker cleanup such as removing every visible image;
- credential prompts or environment dumps;
- task body, solution, test-body, raw trajectory, screenshot, hidden reference,
  upload, leaderboard, or submit paths.

The next no-run command, if needed, should be manifest-only:

```bash
docker manifest inspect alfin06/agentissue-bench:lagent_239
```

Do not run that command from an automation unless the selected environment is
known to tolerate registry metadata access and the command output is reduced to
compact booleans, image name, tag, media type, digest count, and size hints.

## Codex CLI Patch-File Wrapper Contract

AgentIssue-Bench patch evaluation expects patch files under:

```text
Patches/{tag}/attempt.patch
```

The LoopX wrapper should therefore model the future pilot as two
separate actors:

1. **Local Codex patch producer**
   - Runs only on a trusted host where Codex CLI is already authenticated.
   - Keeps Codex auth, sessions, `~/.codex`, API keys, and shell history local.
   - Emits only patch files and compact run metadata into an isolated artifacts
     directory.
   - Does not copy Codex credentials into Docker images or the shared remote
     host.
2. **Scoped Docker evaluator**
   - Receives only the selected tag and patch artifact after explicit execution
     approval.
   - Pulls and runs at most `alfin06/agentissue-bench:lagent_239`.
   - Mounts only `Patches/lagent_239/`.
   - Does not use all-tag loops, host networking, global Docker cleanup,
     credential prompts, upload, leaderboard, or submit paths.

The task-context source is not yet execution-ready. A future pilot must first
define a public-safe context route for the selected tag, such as an approved
container/source inspection step after image access is allowed. Until that
route exists, do not invoke Codex for this benchmark.

## Future Execution Shape

After explicit owner approval for a no-upload pilot, the smallest safe run
should be:

1. Manifest-only preflight for `lagent_239`.
2. Capacity check for available disk before image pull.
3. Approved task-context route for the selected tag.
4. Local Codex CLI patch generation into `Patches/lagent_239/attempt.patch`.
5. Scoped Docker evaluation for that single tag.
6. Compact `benchmark_run_v0` / `benchmark_result_v0` writeback with:
   - `benchmark=agentissue-bench`;
   - `source_commit=1d498dec35e347c4e7b9e1c318ef28fc5fa97318`;
   - `tag=lagent_239`;
   - `official_score_claim=false` unless the upstream protocol is followed
     exactly;
   - `upload=false`;
   - `leaderboard=false`;
   - `submit=false`;
   - `docker_pull_count<=1`;
   - `docker_run_count<=1`;
   - `global_docker_cleanup=false`;
   - `codex_auth_copied=false`;
   - `raw_artifacts_published=false`.

## Decision

The one-tag launch packet is ready as a no-run route document. AgentIssue-Bench
should not move to execution yet; the next bounded step is a manifest-only
preflight plus a task-context-source gate for `lagent_239`, still stopping
before Docker pull/run, model/Codex invocation, task material consumption,
upload, leaderboard, submit, credentials, raw trajectories, screenshots,
hidden references, solutions, or test-body surfaces.
