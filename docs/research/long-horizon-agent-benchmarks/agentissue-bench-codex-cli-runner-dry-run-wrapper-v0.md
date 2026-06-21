# AgentIssue-Bench Codex CLI Runner Dry-Run Wrapper V0

Date: 2026-06-12

## Scope

This packet materializes the `lagent_239` AgentIssue-Bench Codex CLI runner
flow as a LoopX CLI wrapper:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id loopx-meta \
  --tag lagent_239
```

The command defaults to dry-run. Passing `--execute` appends only a compact
`benchmark_run_v0` readiness event; it still does not invoke Codex CLI, a model
API, Docker, official all-tag helpers, uploads, submit, public ranking paths,
or patch generation.

## Runner Shape

The wrapper renders one selected-tag plan:

```text
benchmark=agentissue-bench
selected_tag=lagent_239
selected_image=alfin06/agentissue-bench:lagent_239
mode=agentissue_codex_cli_runner_dry_run_wrapper
```

The rendered phase order is:

1. prepare a private job root;
2. write public issue context into private `context/`;
3. opt-in pull of only the selected image;
4. opt-in extraction of the selected container's buggy source;
5. initialize a git baseline in the extracted source;
6. opt-in host-local `codex exec` from that extracted source;
7. write `Patches/lagent_239/attempt.patch` from that git diff;
8. opt-in selected-tag eval;
9. reduce compact public evidence.

The default wrapper step stops before every opt-in execution phase. It exists
so future workers can verify command rendering and state writeback before a
private run.

## Command Rendering

The host Codex patch worker shape is:

```text
codex exec --ephemeral --ignore-rules --sandbox workspace-write \
  --cd <abs-private-job-root>/buggy-source \
  --add-dir <abs-private-job-root> \
  --output-last-message <abs-private-job-root>/codex-last-message.txt \
  <abs-private-job-root>/context/prompt.md
```

The selected-tag eval shape is:

```text
docker run --platform linux/amd64 --rm --entrypoint bash \
  -v <abs-private-job-root>/Patches/lagent_239:/patches:ro \
  alfin06/agentissue-bench:lagent_239 \
  -c <apply_patch_and_test_patched>
```

Both shapes are placeholders. The wrapper records that `codex_cli_invoked`,
`model_api_invoked`, `docker_container_started`, `patch_generated`, and
`patch_evaluated` are all false.

## Output

The CLI output includes:

- the append payload from `append_benchmark_run`;
- `benchmark_cli`, recording that no runner, Codex, Docker, auth read, upload,
  submit, or leaderboard action occurred;
- `agentissue_runner_flow`, recording command shapes, staging placeholders,
  stop rules, and reducer boundaries;
- a compact `benchmark_run_v0` with `official_task_score.kind` set to
  `agentissue_bench_single_tag_container_eval_not_run`.

This packet does not claim an official AgentIssue-Bench score or Codex CLI
success rate.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py
python3 -m py_compile examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py
loopx check \
  --scan-path loopx/benchmark.py \
  --scan-path loopx/cli.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-dry-run-wrapper-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
