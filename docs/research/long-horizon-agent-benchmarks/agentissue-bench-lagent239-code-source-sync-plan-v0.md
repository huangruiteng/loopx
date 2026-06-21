# AgentIssue-Bench `lagent_239` Code-Source Sync Plan V0

Date: 2026-06-12

## Scope

This packet defines the no-run public code-source sync plan for
AgentIssue-Bench tag `lagent_239`.

It builds on:

- selected AgentIssue-Bench tag: `lagent_239`
- selected issue route: `https://github.com/InternLM/lagent/issues/239`
- future patch output path: `Patches/lagent_239/attempt.patch`
- local Codex patch-producer packet:
  `agentissue-bench-lagent239-patch-producer-packet-v0.md`

This packet records only public repository metadata and redacted file-selection
rules. It does not clone the repository, read file contents, read source diffs,
invoke Codex CLI, call model APIs, generate a patch, pull Docker, start Docker,
evaluate a patch, upload, submit, touch public ranking paths, read
credentials, read raw trajectories, open screenshots, or publish raw issue
text, generated patches, solutions, gold material, test patches, or test
bodies.

## Public Source Metadata

Public GitHub metadata captured 2026-06-12:

- target repository: `InternLM/lagent`
- visibility: public
- archived: `false`
- fork: `false`
- license: `Apache-2.0`
- default branch: `main`
- HEAD sha:
  `0ab2e2f550477884743cd63fbca7bc4aa7b00290`
- HEAD commit date: `2026-04-20T07:14:00Z`
- root tree sha:
  `e1fbfc26536a3bdb688c98a9a97732db84a0a2db`
- root tree entry count: `16`
- root tree directory count: `6`
- root tree blob count: `10`
- root tree truncated: `false`
- repository pushed at: `2026-06-12T08:35:00Z`
- repository updated at: `2026-06-11T08:40:16Z`

This is metadata-only evidence. It proves that the public source route is
reachable and has a specific commit/tree anchor, but it is not a source clone,
patch readiness signal, validation signal, or benchmark score.

## Redacted File-Selection Rules

Future execution should keep public writeback at the rule level until a
separate execution gate exists:

1. **Issue-guided public repo search**
   - A future worker may inspect the public repository locally after an
     execution gate.
   - Public artifacts should record only counts, hashes, and patch output
     metadata.
   - Raw paths are not recorded in this plan.
2. **Implementation then validation scope**
   - A future worker should identify candidate implementation and validation
     surfaces locally.
   - Public artifacts should record redacted counts until patch generation is
     approved.
   - Raw file contents and diffs stay out of public artifacts.
3. **No generated or private artifacts**
   - Exclude generated outputs, credentials, sessions, local caches, raw
     trajectories, screenshots, and benchmark result directories from sync and
     writeback.

## Executable Fixture

The executable fixture is:

```bash
python3 examples/agentissue-bench-lagent239-code-source-sync-smoke.py
```

It emits:

- `agentissue_bench_code_source_sync_plan_v0`
- a compact no-run `benchmark_run_v0`

The `benchmark_run_v0` projection keeps:

- `source_runner=agentissue-bench`
- `benchmark_id=agentissue-bench`
- `mode=public_code_source_sync_plan_no_run`
- `target_code_source.repo=InternLM/lagent`
- `target_code_source.head_sha=0ab2e2f550477884743cd63fbca7bc4aa7b00290`
- `target_code_source.tree_sha=e1fbfc26536a3bdb688c98a9a97732db84a0a2db`
- `target_code_source.root_tree_entry_count=16`
- `checkout_performed=false`
- `file_contents_read=false`
- `source_diffs_public=false`
- `raw_issue_text_public=false`
- `raw_source_content_public=false`
- `no_codex_cli_invocation=true`
- `no_model_call=true`
- `no_patch_generation=true`
- `no_patch_evaluation=true`
- `no_docker_pull=true`
- `no_docker_run=true`
- `no_upload=true`
- `no_submit=true`
- `no_public_ranking_path=true`

## Validation

Targeted validation:

```bash
python3 examples/agentissue-bench-lagent239-code-source-sync-smoke.py
python3 -m py_compile examples/agentissue-bench-lagent239-code-source-sync-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-lagent239-code-source-sync-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-code-source-sync-plan-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts that public outputs do not include local paths, credentials,
raw issue text, command argv, environment dumps, raw file contents, source
diffs, patch content, test bodies, Docker output, Codex auth material,
sessions, raw trajectories, or screenshots.

## Next Gate

The next step should stay no-run unless the owner explicitly asks for a real
pilot. Useful no-run follow-up is a local execution gate packet that separates:

- trusted-local Codex patch generation;
- public source checkout location and cleanup;
- single-tag Docker evaluation;
- compact result reduction;
- no-upload/no-submit/no-public-ranking boundaries.

A real attempt still needs a separate execution decision because it would read
source files, invoke Codex, create patch content, and may pull/run the selected
Docker image.
