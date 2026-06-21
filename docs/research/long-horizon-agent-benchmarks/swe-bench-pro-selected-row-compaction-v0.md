# SWE-Bench Pro Selected-Row Compaction V0

Date: 2026-06-12

## Scope

This packet records the owner-delegated public task-row access for one
SWE-Bench Pro public row. The row was accessed through Hugging Face's public
datasets-server API and reduced to compact metadata, field lengths, and hashes.

This packet does not reproduce the raw problem statement, gold patch, test
patch, test list, requirements, interface, setup command, or any file content.
It also does not pull Docker images, start containers, invoke Codex CLI, call
model APIs, generate patches, evaluate patches, upload, submit, touch public
ranking paths, read credentials, inspect raw trajectories, or open
screenshots.

## Source Evidence

- Dataset: `ScaleAI/SWE-bench_Pro`
- Dataset revision: `7ab5114912baf22bb098818e604c02fe7ad2c11f`
- Config: `default`
- Split: `test`
- Number of examples from metadata: `731`
- Runner repository: `scaleapi/SWE-bench_Pro-os`
- Runner source commit: `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`

Selected row:

- offset: `0`
- row index: `0`
- repository: `NodeBB/NodeBB`
- instance id:
  `instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan`
- base commit: `1e137b07052bc3ea0da44ed201702c94055b8ad2`
- Docker Hub tag:
  `nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5`
- repository language: `js`

## Hash-Only Row Material

The following row fields were reduced to character counts and SHA-256 hashes:

| Field | Chars | SHA-256 |
| --- | ---: | --- |
| `problem_statement` | 1330 | `e063181d444133d67464e5bdd49c8effc4f8952af9826cabf04416823c369994` |
| `patch` | 12620 | `5604a864308d779c632e64c67c1c9b2eb0562c58bf4aeabc1fabfd43ff7a8f32` |
| `test_patch` | 1436 | `7b598b250cd12c68108906f35916b9a4d2b447f24fa0f46e49e25fa39e69e030` |
| `fail_to_pass` | 408 | `f681e11d42023528dca57e74351bb1bd7824d0b41ccd50c5197638a3a6201732` |
| `pass_to_pass` | 45764 | `b4b2cc243da9a4b3d853df392a7ae14c083bbb9679540fe13b04a5a5e458bd86` |
| `requirements` | 3654 | `0ab84fee799da450cf1692dbb8ec3ea9d7ba93c5c08b676f733b4b222171409a` |
| `interface` | 971 | `83e94192ed741e8a9d1429f5efa484d60e8579de35e85aadf2376cd7686e77df` |
| `selected_test_files_to_run` | 68 | `d87bd02ab80f6965d45f6ddc4b21c682345e3f7fdf537759e7c1585d63d480b0` |
| `before_repo_set_cmd` | 226 | `7d4300a48ae64e2bd9c4c1fb5641d56385c24ee8308044fdb5ba9bf385a1a8f1` |
| `issue_categories` | 102 | `24fc694a174aea52f75f6a39fd95eb34cd76f1f2e4cc79227a901ccf8a0e80e6` |
| `issue_specificity` | 34 | `0e2b7fa112012020628280b45c410dbb66ed714ed5c285c51980d70bc1250aec` |

## Executable Fixture

The executable fixture is:

```bash
python3 examples/swe-bench-pro-selected-row-compaction-smoke.py
```

It emits:

- `swe_bench_pro_selected_row_compaction_v0`;
- a no-run `benchmark_run_v0` projection with
  `mode=public_selected_row_hash_only_no_run`.

The `benchmark_run_v0` projection keeps:

- source runner: `swe-bench-pro`;
- dataset revision;
- runner source commit;
- selected `instance_id`;
- selected `dockerhub_tag`;
- selected repository and base commit;
- one pending blocked trial;
- `raw_problem_statement_public=false`;
- `raw_patch_public=false`;
- `raw_test_patch_public=false`;
- `raw_test_list_public=false`;
- `no_docker_pull=true`;
- `no_docker_run=true`;
- `no_codex_cli_invocation=true`;
- `no_model_call=true`;
- `no_upload=true`;
- `no_submit=true`;
- `no_public_ranking_path=true`.

## Validation

Targeted validation:

```bash
python3 examples/swe-bench-pro-selected-row-compaction-smoke.py
python3 -m py_compile examples/swe-bench-pro-selected-row-compaction-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-selected-row-compaction-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-selected-row-compaction-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts that public outputs do not contain local paths,
credentials, raw row material, patch content, test bodies, Docker output,
Codex auth material, sessions, raw trajectories, screenshots, command argv, or
environment dumps.

## Decision

SWE-Bench Pro has a selected public instance route ready for no-run launch
packet work. The next safe step is a one-instance launch packet that estimates
or records Docker image metadata, defines local-Docker boundaries, and keeps
raw task material, Docker pull/run, Codex/model invocation, patch generation,
patch evaluation, uploads, submit, public ranking paths, credentials,
trajectories, and screenshots behind a separate execution gate.
