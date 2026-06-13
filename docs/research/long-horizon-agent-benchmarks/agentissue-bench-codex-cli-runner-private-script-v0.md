# AgentIssue-Bench Codex CLI Runner Private Script V0

Date: 2026-06-13

## Scope

This packet adds a no-execute materializer for the trusted-local
AgentIssue-Bench `lagent_239` runner script:

```bash
goal-harness benchmark agentissue-codex-runner-flow \
  --goal-id goal-harness-meta \
  --tag lagent_239 \
  --private-runner-root <private-runner-root>
```

The generator materializes:

```text
run-lagent239.private.sh
private-runner.public.json
benchmark_run.compact.json
```

It also reuses the existing first-run handoff and execution-gate files in the
same private root. The generator itself does not invoke Codex CLI, Docker, a
model API, source extraction, patch generation, patch evaluation, upload,
submit, or public ranking paths.

## Runner Script Contract

The private script is the first repeatable local entrypoint for the already
validated `lagent_239` flow. It encodes these phases in order:

```text
prepare_private_job_root
extract_buggy_source_from_selected_container
initialize_git_baseline_in_buggy_source
run_host_local_codex_cli_patch_worker
write_attempt_patch_from_buggy_source_git_diff
evaluate_selected_tag_container
write_compact_public_evidence
reduce_compact_public_evidence
```

The script requires the operator to provide a private `context/prompt.md`
before execution. It rejects the synthetic placeholder prompt, keeps Codex
auth on the trusted host, extracts only the selected `lagent_239` image source,
exports the attempt patch from the buggy-source git diff, evaluates the same
selected image through `apply_patch` plus `test_patched`, writes
`benchmark_run.compact.json` and `benchmark_result.compact.json`, then calls
the compact-only `--real-result-root` reducer.

History append is opt-in inside the script through `APPEND_HISTORY=1`; the
default script run reduces compact evidence without appending run history. The
script can pull the selected image only when `ALLOW_DOCKER_PULL=1`; otherwise a
missing local image is a blocker.

## Public Manifest

`private-runner.public.json` records only:

```text
schema_version
selected_tag
selected_image
relative script/output filenames
phase_order
script_checks
generator_boundary
later_script_boundary
```

It keeps `path_recorded=false`, `root_path_recorded=false`, and
`script_content_public=false`. The public manifest says the generator did not
run Codex, Docker, model APIs, uploads, submits, or public ranking paths. It
also records that a later script execution will invoke host-local Codex and
start only the selected container, while still keeping uploads, submits,
public ranking, auth sync, raw logs, and patch content disabled.

## Compact Event

The compact event uses:

```text
mode=agentissue_codex_cli_runner_private_script
real_run=false
submit_eligible=false
leaderboard_evidence=false
official_score_claim_allowed=false
control_plane_score_applicable=true
```

Validation fields assert that the private script and public manifest were
materialized, the script executable bit is set, phase order and all runner
phases are rendered, script content is not public, the script path is relative
only, and the generator performed no Codex execution, Docker execution, model
API call, upload, submit, public ranking path, auth material sync, raw-log
publication, patch-content publication, or absolute private path publication.

This is not a scored benchmark run and not a public leaderboard claim. It is
the repeatable runner entrypoint needed before controlled script execution or a
low-frequency real Codex CLI regression.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-private-script-smoke.py
python3 -m py_compile \
  goal_harness/benchmark.py \
  goal_harness/cli.py \
  goal_harness/status.py \
  examples/agentissue-bench-codex-cli-runner-private-script-smoke.py
goal-harness check \
  --scan-path goal_harness/benchmark.py \
  --scan-path goal_harness/cli.py \
  --scan-path goal_harness/status.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-private-script-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-private-script-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
