# AgentIssue-Bench `lagent_239` Controlled Pilot Result V0

Date: 2026-06-12

## Scope

This packet records the first real no-upload controlled pilot for the selected
AgentIssue-Bench tag `lagent_239`.

It also narrows the benchmark program: the only active benchmark is now
AgentIssue-Bench, and the only active task is `lagent_239`. ALE, SWE-Bench Pro,
PerfBench, TheAgentCompany, and APEX-Agents remain frozen as historical
candidates or blockers until this single-tag lane either resolves or reaches a
hard blocker.

This pilot crossed the intended execution boundaries in order:

1. public source checkout for `InternLM/lagent`;
2. trusted-local Codex CLI patch generation;
3. selected-image Docker pull and single-tag container evaluation;
4. compact result reduction.

It did not upload, submit, touch public ranking paths, sync Codex auth, copy
`~/.codex`, read credentials, mount host credentials into Docker, publish
issue raw text, publish patch content, publish source diffs, publish raw
container logs, read raw trajectories, or open screenshots.

## Compact Facts

Active focus:

```text
only_active_benchmark=agentissue-bench
only_active_task=lagent_239
frozen_candidates=agents-last-exam,swe-bench-pro,perfbench,theagentcompany,apex-agents
```

Source and patch generation:

```text
agentissue_source_commit=1d498dec35e347c4e7b9e1c318ef28fc5fa97318
target_repo=InternLM/lagent
target_head_sha=0ab2e2f550477884743cd63fbca7bc4aa7b00290
target_checkout_kind=public_current_head
benchmark_buggy_source_aligned=false
codex_cli_invoked=true
codex_ephemeral=true
model_api_invoked=true
codex_auth_copied=false
no_credentials_read=true
patch_generated=true
patch_sha256=e04029b70d5b1d4b461da6b8ba997388fefd614f94705b0a7abc3f847d5c07d3
patch_bytes=635
files_changed=1
hunks=1
no_patch_content_public=true
```

Local source validation before container evaluation:

```text
diff_check_passed=true
py_compile_passed=true
compat_import_simulation_passed=true
pytest_available=false
```

Single-tag Docker evaluation:

```text
image=alfin06/agentissue-bench:lagent_239
image_digest=sha256:792b3a4edae457c429e2797cd6ee5a181accc6cef81291dfd0ae0ab3713eab39
platform=linux/amd64
image_pull_status=success
container_started=true
patch_apply_status=success
test_patched_exit_code=1
success_marker=false
failure_marker=true
private_log_sha256=cdee2058eece77675a1c295edffa8fec9bcf2f1db0e8602d6536efcfd3fa5265
private_log_bytes=2239
raw_log_public=false
```

## Result

The pilot is a real evaluated failure, not a setup-only blocker.

Compact result:

```text
terminal_state=evaluated_unresolved
single_tag_local_eval_resolved=false
single_tag_local_eval_score=0.0
official_leaderboard_claim_allowed=false
```

The generated patch applied cleanly inside the selected container, but the
container test did not verify it.

## Attribution

The first failure attribution is source alignment, not Docker reachability or
patch-mount wiring.

The patch worker generated against the current public `InternLM/lagent` HEAD.
That checkout already differs from the benchmark's buggy snapshot. The selected
container accepted the patch but tested a dependency-file condition from its own
buggy snapshot, so the generated source-level compatibility patch did not
resolve the container oracle.

Failure labels:

```text
current_head_patch_source_mismatch
benchmark_buggy_source_not_checked_out
dependency_constraint_expected_by_container_test
```

No patch amendment was made after the container result, and no oracle or fixed
material is included in this public packet.

## Next Single-Benchmark Step

Continue only on AgentIssue-Bench `lagent_239`.

The next bounded step should align patch generation to the benchmark's buggy
source rather than the public current HEAD, then rerun only this same selected
tag. Do not broaden to other benchmarks until this lane either produces a
resolved single-tag result or a compact hard blocker.

## Validation

```bash
python3 examples/agentissue-bench-lagent239-controlled-pilot-result-smoke.py
python3 -m py_compile examples/agentissue-bench-lagent239-controlled-pilot-result-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-lagent239-controlled-pilot-result-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-controlled-pilot-result-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
git diff --check \
  docs/research/long-horizon-agent-benchmarks/README.md \
  docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-controlled-pilot-result-v0.md \
  examples/agentissue-bench-lagent239-controlled-pilot-result-smoke.py
```

## Claim Boundary

This packet may claim one local, no-upload, single-tag AgentIssue-Bench
evaluation for `lagent_239`, with unresolved result and compact failure
attribution. It may not claim leaderboard score, official submission, broad
benchmark success rate, or any result for other benchmarks.
