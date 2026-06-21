# SWE-Bench Pro Setup Readiness

Date: 2026-06-12

Scope: public-safe setup-readiness scan for SWE-Bench Pro. This scan used the
paper, Scale leaderboard/blog pages, the official GitHub repository metadata,
the official README, Hugging Face dataset metadata, Docker Hub tag metadata,
and a third-party direct Codex result report.

It did not run the benchmark, clone the dataset, pull Docker images, start
containers, invoke Codex or model APIs, submit to a leaderboard, upload
artifacts, or persist task-row details. The Hugging Face web UI can render
task-row previews, including patch and problem-statement fields; future probes
must avoid row viewers and use metadata-only APIs until public task-row access
is explicitly approved.

## Public Sources

- Scale public leaderboard:
  https://labs.scale.com/leaderboard/swe_bench_pro_public
- Paper HTML: https://arxiv.org/html/2509.16941v1
- Scale blog: https://scale.com/blog/swe-bench-pro
- Official repository: https://github.com/scaleapi/SWE-bench_Pro-os
- Hugging Face dataset metadata:
  https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro
- Augment third-party Codex/Auggie run report:
  https://www.augmentcode.com/blog/auggie-tops-swe-bench-pro

## Difficulty And Codex Signal

SWE-Bench Pro is a strong LoopX candidate because it is explicitly
designed for long-horizon, multi-file, professional software engineering tasks.
The paper describes 1,865 total problems across 41 active repositories, with a
public set of 731 tasks from 11 repositories plus held-out and commercial
subsets.

The initial public-set results are low enough to be useful for LoopX
uplift measurement. The paper reports Pass@1 public-set resolution of `23.3%`
for OpenAI GPT-5, `22.7%` for Claude Opus 4.1, `17.6%` for Claude Sonnet 4,
`4.9%` for OpenAI GPT-4o, and `3.4%` for Qwen-3 32B under a unified SWE-Agent
scaffold. Scale's public page summarizes the same central point: top models
were around `23%` on SWE-Bench Pro public versus `70%+` on SWE-Bench Verified.

There is also a newer direct Codex-adjacent public signal, unlike several other
candidate benchmarks. Augment reports running OpenAI Codex with
`GPT-5.2-codex` on the same 731 public problems and obtaining `46.47%`, while
Auggie with Claude Opus 4.5 reached `51.80%`. Treat this as a third-party
agent/scaffold result rather than an official Scale leaderboard claim, but it
is still useful evidence that Codex-class agents remain far from saturated on
this benchmark.

Current score interpretation needs pinning. The official repository news says
leaderboard issues were identified on `05/18`, unit tests were removed on
`2/9`, and some run scripts were updated on `1/7`. Therefore any future
comparison must pin:

- repository commit;
- Hugging Face dataset revision;
- public versus commercial/held-out split;
- leaderboard or local harness version;
- scaffold and turn/cost limits.

## Setup Findings

Source transport is healthy:

- `git ls-remote https://github.com/scaleapi/SWE-bench_Pro-os.git HEAD`
  resolved to `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`;
- GitHub API returned HTTP 200 for the repository and root contents;
- repository metadata reports `scaleapi/SWE-bench_Pro-os`, public visibility,
  default branch `main`, MIT license, and latest push timestamp
  `2026-05-18T18:59:22Z`;
- root contents include `README.md`, `.gitmodules`, `SWE-agent`,
  `mini-swe-agent`, `helper_code`, `run_scripts`, `swe_bench_pro_eval.py`, and
  `requirements.txt`;
- `.gitmodules` points to Scale-maintained `SWE-agent` on branch
  `scale-customizations` and `scaleapi/mini-swe-agent`;
- Docker Hub metadata for `jefzda/sweap-images` returned HTTP 200 with `1002`
  visible tags; a sampled tag was about `1.02 GB`, but no image was pulled;
- Hugging Face API metadata for `ScaleAI/SWE-bench_Pro` returned revision
  `7ab5114912baf22bb098818e604c02fe7ad2c11f`, last modified
  `2026-02-23T20:54:47Z`, and a single parquet data file.

The official README supports both Modal and local Docker:

- Python dependencies are installed from `requirements.txt`;
- Docker is required for reproducible evaluations;
- Modal is recommended and requires credentials in `~/.modal.toml`;
- local Docker is marked beta and selected with `--use_local_docker`;
- prebuilt images are expected from `jefzda/sweap-images`;
- patch generation is harness-agnostic, with official SWE-agent and
  mini-swe-agent routes available;
- evaluation consumes gathered patch JSON plus run scripts through
  `swe_bench_pro_eval.py`.

## Boundary And Runner Risks

The benchmark is runnable in principle, but the next step should still be
no-task and no-Docker:

- selecting a real instance requires reading at least dataset row metadata such
  as `instance_id` and `dockerhub_tag`; the same rows also contain problem
  statements, gold patches, test patches, and test lists, so row access needs a
  public-task-material approval gate;
- the repository itself contains run-script directories and helper data that
  may encode instance-level task identifiers or evaluation data; sparse source
  checkout is safer than cloning the full tree for a no-task preflight;
- Modal is not appropriate for autonomous heartbeat work because it requires
  credentials and may create cloud cost;
- local Docker is preferable for no-upload pilots, but image pulls are large
  and should start only after a selected public task route is approved;
- leaderboard claims are unstable unless the exact leaderboard/date/scaffold
  and dataset revision are pinned.

## Decision

SWE-Bench Pro is runner-source ready and remains a high-priority benchmark lane.
It is harder than SWE-Bench Verified, has a public dataset and official runner,
has local-Docker beta support, and has a direct public Codex-class result. The
next autonomous step should be a sparse, no-task, no-Docker source preflight of
the official runner that excludes `run_scripts`, trajectory folders, task-row
data, and credential paths.

Do not proceed to dataset-row selection, Docker image pull/run, Codex/model
invocation, patch generation, patch evaluation, upload, leaderboard, submit,
raw trajectory inspection, screenshot inspection, or hidden/private references
without a separate explicit approval.
