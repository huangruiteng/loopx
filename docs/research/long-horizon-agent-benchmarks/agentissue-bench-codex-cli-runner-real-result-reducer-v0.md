# AgentIssue-Bench Codex CLI Runner Real-Result Reducer V0

Date: 2026-06-13

## Scope

This packet adds a compact-only reduction step for an already completed
private AgentIssue-Bench `lagent_239` real run:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id loopx-meta \
  --tag lagent_239 \
  --real-result-root <private-real-result-root>
```

The reducer reads only these compact files from the private result root:

```text
benchmark_run.compact.json
benchmark_result.compact.json
```

It materializes:

```text
real-result.public.json
```

The reducer does not invoke Codex CLI, a model API, Docker, source extraction,
git baseline creation, patch generation, patch evaluation, upload, submit, or
public ranking paths. It also does not read raw issue text, source diffs,
patch content, raw logs, trajectories, screenshots, credentials, or absolute
private workspace paths.

## CLI Contract

`--real-result-root` is mutually exclusive with:

```text
--synthetic-staging-root
--execution-gate-root
--first-run-handoff-root
```

The compact inputs must prove:

```text
selected_image_only=true
single_tag_only=true
buggy_source_extracted=true
fixed_source_not_extracted_to_host=true
host_codex_cli_invoked=true
patch_exported_from_buggy_source_git_diff=true
no_upload=true
no_submit=true
no_public_ranking_path=true
raw_logs_public=false
patch_content_public=false
credential_values_recorded=false
codex_auth_synced_to_container_or_remote=false
```

The output packet keeps `path_recorded=false`, records only hash/count/status
fields, and exposes the selected single-tag official container score as
compact control-plane evidence. It is not a public leaderboard submission and
does not make an official native Codex CLI comparison claim.

`patch_applied_in_container`, `patched_eval_exit_zero`, and
`patched_eval_success_marker` remain result fields, not prerequisites for
reading the packet: they distinguish malformed-patch, complete-unresolved, and
resolved attempts. Missing phase proof is a reducer error; a false eval-result
field is an official unresolved score with failure attribution.

Passing `--execute` appends the derived compact `benchmark_run_v0` event to
LoopX run history. The payload also includes a compact
`benchmark_result_v0` object for consumers that want to append or compare
result-layer evidence separately.

## Compact Event

The compact event uses:

```text
mode=agentissue_codex_cli_runner_real_result_reducer
real_run=true
submit_eligible=false
leaderboard_evidence=false
official_score_claim_allowed=false
control_plane_score_applicable=true
```

Validation fields assert compact-only reads, selected-tag consistency,
selected image only, single-tag only, buggy source extraction, no fixed-source
host extraction, host Codex invocation, patch export from the buggy-source git
diff, container patch application, no upload, no submit, no public ranking
path, no raw logs public, no patch content public, no absolute private paths
public, no Codex auth sync, no credential value recording, and no reducer-side
Codex or Docker execution.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-real-result-smoke.py
python3 regression/agentissue-lagent239-real-codex-runner.py
python3 -m py_compile \
  loopx/benchmark.py \
  loopx/cli.py \
  examples/agentissue-bench-codex-cli-runner-real-result-smoke.py \
  regression/agentissue-lagent239-real-codex-runner.py
loopx check \
  --scan-path loopx/benchmark.py \
  --scan-path loopx/cli.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-real-result-smoke.py \
  --scan-path regression/agentissue-lagent239-real-codex-runner.py \
  --scan-path regression/README.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-real-result-reducer-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
