# AgentIssue-Bench `lagent_239` Local Codex Patch-Producer Packet V0

Date: 2026-06-12

## Scope

This packet defines the no-run local Codex patch-producer boundary for
AgentIssue-Bench tag `lagent_239`.

It builds on the public context packet:

- selected tag: `lagent_239`
- selected issue route: `https://github.com/InternLM/lagent/issues/239`
- issue body sha256:
  `f4c8e9fdb337b030730c31e69ea7d62ffa1808fd9843ea17eeb4949d7533bb79`
- issue comments sha256:
  `6602126a5f058a9705f5e733cb4d1d5aad2c483e1a4f9cde114d97dca8fa3357`

This packet does not invoke Codex CLI, call model APIs, generate a patch, sync
source code, pull Docker, start Docker, evaluate a patch, upload, submit,
touch a public ranking path, read credentials, read raw trajectories, open
screenshots, or publish raw issue text, source diffs, generated patches,
solutions, gold material, test patches, or test bodies.

## Trusted-Local Producer Shape

Future execution, if explicitly authorized, should keep the producer and
evaluator as separate actors:

1. **Trusted-local Codex patch producer**
   - runs only on a trusted local host with existing Codex CLI auth;
   - never copies `~/.codex`, auth caches, API keys, shell history, or session
     files to a shared remote host or benchmark container;
   - uses the public issue context and a public `InternLM/lagent` code checkout
     or sparse checkout;
   - writes only the selected patch artifact:
     `Patches/lagent_239/attempt.patch`;
   - records compact metadata and hashes, not raw prompts, completions, source
     diffs, or patch content.
2. **Scoped Docker evaluator**
   - remains disabled in this packet;
   - may later receive only `Patches/lagent_239/` after a separate execution
     gate;
   - must avoid all-tag loops, global Docker cleanup, host credential mounts,
     uploads, submit, and public ranking paths.

## Executable Fixture

The executable fixture is:

```bash
python3 examples/agentissue-bench-lagent239-patch-producer-smoke.py
```

It emits:

- `agentissue_bench_local_codex_patch_producer_packet_v0`;
- `benchmark_run_v0` with
  `mode=local_codex_patch_producer_packet_no_run`;
- `benchmark_result_v0` with
  `official_task_score.status=not_run` and a separate
  `control_plane_score_core_v0`.

The compact `benchmark_run_v0` keeps:

- `source_runner=agentissue-bench`;
- `benchmark_id=agentissue-bench`;
- `source_commit=1d498dec35e347c4e7b9e1c318ef28fc5fa97318`;
- `task_selector_kind=selected_public_tag`;
- `task_selector_hash=lagent_239`;
- expected patch output path `Patches/lagent_239/attempt.patch`;
- `no_codex_cli_invocation=true`;
- `no_model_call=true`;
- `no_patch_generation=true`;
- `no_patch_evaluation=true`;
- `no_docker_pull=true`;
- `no_docker_run=true`;
- `no_upload=true`;
- `no_submit=true`;
- `no_public_ranking_path=true`.

## Validation

Targeted validation:

```bash
python3 examples/agentissue-bench-lagent239-patch-producer-smoke.py
python3 -m py_compile examples/agentissue-bench-lagent239-patch-producer-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-lagent239-patch-producer-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-patch-producer-packet-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts that public outputs contain no raw issue title/body,
comments, source diffs, patch content, problem statements, gold material, test
patches, test bodies, solutions, local paths, credentials, command argv,
environment dumps, Docker output, Codex auth material, raw trajectories,
screenshots, or sessions.

## Next Gate

The next no-run step can be either:

- a public code-source sync plan for `InternLM/lagent` that records only commit
  ids, tree metadata, and redacted file-selection rules; or
- a local execution packet that explicitly separates trusted-local Codex patch
  generation from single-tag Docker evaluation.

A real patch generation/evaluation attempt still needs a separate execution
gate because it would invoke Codex, create a patch artifact, and potentially
pull/run the selected image.
