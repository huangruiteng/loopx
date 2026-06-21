# AgentIssue-Bench Codex CLI Runner Flow Plan V0

Date: 2026-06-12

## Scope

This packet turns the AgentIssue-Bench `lagent_239` runner contract into a
deterministic command-flow plan without executing the benchmark.

It is deliberately narrower than a live pilot:

```text
benchmark=agentissue-bench
selected_tag=lagent_239
dry_run_plan_only=true
real_execution_done=false
```

No Codex CLI prompt, model API call, Docker pull, container start, patch
generation, patch evaluation, upload, submit, public ranking path, credential
read, or raw artifact read happened in this step.

## Flow

The runner flow is fixed to one tag and one private job root:

1. prepare a private job root;
2. fetch public issue context into the private `context/` area;
3. pull only `alfin06/agentissue-bench:lagent_239`;
4. extract the selected container's benchmark buggy source;
5. initialize a local git baseline in that extracted source;
6. run host-local Codex CLI from the extracted source;
7. write `Patches/lagent_239/attempt.patch` from that git diff;
8. evaluate only `alfin06/agentissue-bench:lagent_239`;
9. reduce compact hash/count/status evidence.

The key invariant is source alignment: Codex CLI must patch the benchmark buggy
snapshot, not current public `InternLM/lagent` HEAD.

## Command Shapes

The Codex patch worker shape is:

```text
codex exec --ephemeral --ignore-rules --sandbox workspace-write \
  --cd <abs-private-job-root>/buggy-source \
  --add-dir <abs-private-job-root> \
  --output-last-message <abs-private-job-root>/codex-last-message.txt \
  <abs-private-job-root>/context/prompt.md
```

Runner constraints:

- the command runs on the host, not in Docker;
- all runner paths must be absolute in the private job root;
- Codex home/auth is not copied;
- the worker does not use Docker;
- the worker does not use network;
- the worker does not read fixed diff or oracle material.

The single-tag evaluation shape is:

```text
docker run --platform linux/amd64 --rm --entrypoint bash \
  -v <abs-private-job-root>/Patches/lagent_239:/patches:ro \
  alfin06/agentissue-bench:lagent_239 \
  -c <apply_patch_and_test_patched>
```

Runner constraints:

- do not use official helpers that scan all tags;
- do not pass credentials into Docker;
- do not upload, submit, or touch public ranking paths;
- do not publish patch content or raw logs.

## Public Reducer

Only these reduced fields may leave the private job root:

```text
tag
image_digest
patch_sha256
patch_bytes
changed_file_count
hunk_count
exit_code
resolved
duration_seconds
log_sha256
no_upload
no_submit
no_public_ranking_path
```

Raw issue text, patch content, raw logs, absolute paths, trajectories,
screenshots, credentials, hidden references, and fixed/oracle material stay
private.

## Output

The smoke fixture emits:

- `agentissue_bench_codex_cli_runner_flow_plan_v0`;
- compact `benchmark_run_v0` with `real_run=false`;
- compact `benchmark_result_v0` with `official_task_score.status=not_run`;
- a next action to materialize this flow in the private job root or write a
  compact blocker.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-flow-smoke.py
python3 -m py_compile examples/agentissue-bench-codex-cli-runner-flow-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-codex-cli-runner-flow-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-flow-plan-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
git diff --check \
  docs/research/long-horizon-agent-benchmarks/README.md \
  docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-flow-plan-v0.md \
  examples/agentissue-bench-codex-cli-runner-flow-smoke.py
```
