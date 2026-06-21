# AgentIssue-Bench Setup Readiness

Date: 2026-06-12

Scope: public-safe, no-run readiness scan for AgentIssue-Bench. This scan used
the official repository, paper, leaderboard, Docker Hub public metadata, and
script-level inspection from a temporary source clone pinned at
`1d498dec35e347c4e7b9e1c318ef28fc5fa97318`.

It did not pull Docker images, start containers, run benchmark tests, generate
patches, evaluate patches, invoke Codex or model APIs, copy credentials, upload
results, read hidden references, inspect raw trajectories, open screenshots, or
consume task body, solution, or test-body material.

## Public Sources

- Official repository: https://github.com/alfin06/AgentIssue-Bench
- Official Docker Hub repository:
  https://hub.docker.com/r/alfin06/agentissue-bench/tags
- Paper: https://arxiv.org/pdf/2505.20749
- OpenReview entry: https://openreview.net/forum?id=N9HLe9iPhj
- Leaderboard: https://alfin06.github.io/AgentIssue-Bench-Leaderboard/

## Readiness Findings

AgentIssue-Bench is a strong LoopX candidate, but not ready for a direct
shared-host execution without a safer wrapper.

The benchmark is relevant because it targets agent-system bugs, the same class
of failures LoopX is meant to reduce: provider integration, tool use,
memory, workflow, dependencies, and agent-runtime maintenance. Public difficulty
is also low enough to be useful: the paper and OpenReview summary report only
`0.67%` to `4.67%` correct resolution across studied SE agents on the current
AgentIssue-Bench version, and the public leaderboard's top listed result is
`4.67%`. No direct Codex CLI score was found in this scan.

The official runner surface is Docker-centric. The README says the benchmark
contains 50 reproducible issues and that each issue is containerized as a Docker
image under `alfin06/agentissue-bench`. The script-level tag lists in
`pull_images.py`, `test_agentissue_bench.py`, and `remove_images.py` agree on
50 primary tags. Docker Hub public metadata currently exposes 85 tags total;
the sampled metadata shows image sizes ranging from about 88 MB to about
4.10 GB, so first execution should start with a single small tag after a
manifest-only or capacity preflight.

Patch evaluation is objective in shape: generated patches are expected under
`Patches/{tag_name}/...`, and `eval_patches.py` runs the image with a patch
mounted into the container, calls the container test entrypoint to apply the
patch, and then calls the patched-test entrypoint. This is compatible with a
Codex CLI wrapper that produces patch files, but that wrapper does not exist
yet for this benchmark.

## Safety Notes

The official helper scripts are not safe enough to run unmodified on a shared
remote machine:

- `pull_images.py` pulls an image and immediately starts a container; despite
  the README wording, it is not a pull-only helper.
- `test_agentissue_bench.py` prompts for model/search credentials, pulls and
  runs every primary image, and includes a global command that removes all
  Docker images visible to the invoking user before the run.
- `eval_patches.py` pulls images and runs containers to apply and test patches.
  One special-case path uses host networking.
- `remove_images.py` removes benchmark images and containers by tag; it is
  safer than the global removal command but still needs scoped invocation.

These properties make the benchmark feasible, but they require a LoopX
launch packet that replaces global Docker cleanup, disables credential prompts,
restricts to one explicit public tag, and records no-upload/no-submit evidence.

## Recommended Route

Treat AgentIssue-Bench as the next strong candidate after SWE-Marathon local
capacity blocked, but gate real execution behind one more no-run packet:

1. Build a no-pull launch packet for one explicit primary tag, preferably a
   small public tag identified from Docker Hub metadata.
2. Write a wrapper contract that asks Codex CLI to emit one or more patch files
   under `Patches/{tag}/`, without copying host Codex auth into the container or
   the shared remote machine.
3. Replace benchmark helpers with scoped commands:
   - no global `docker rmi`;
   - no all-tag loops;
   - no credential prompts in shared terminal output;
   - no host networking unless a tag-specific public reason is documented.
4. Run only a manifest/capacity preflight before any Docker pull.
5. After explicit launch approval, run at most one tag as a no-upload,
   no-leaderboard pilot and ingest only compact `benchmark_run_v0` /
   `benchmark_result_v0` evidence.

## Stop Conditions

Stop before Docker pull/run, benchmark test execution, patch generation,
patch evaluation, model/Codex invocation, upload, leaderboard, submit,
credential transfer/read/print, raw trajectory, screenshot, hidden reference,
task body, solution file, or test-body material unless the owner explicitly
authorizes the next bounded execution step.

## Decision

AgentIssue-Bench remains on the shortlist and is more directly aligned with
LoopX than generic SWE benchmarks, but the next automatic step should
be a no-run one-tag launch packet and wrapper contract, not an immediate e2e
run. It is especially attractive because low public success rates leave room
for LoopX to demonstrate value through restartability, evidence
discipline, wrapper safety, scoped validation, and failure attribution rather
than only raw coding strength.
