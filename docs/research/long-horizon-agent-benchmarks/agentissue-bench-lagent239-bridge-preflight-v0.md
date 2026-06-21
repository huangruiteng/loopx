# AgentIssue-Bench `lagent_239` Bridge Preflight V0

Date: 2026-06-12

## Scope

This packet advances the selected AgentIssue-Bench `lagent_239` lane from a
no-run execution gate to a bridge preflight. It checks the trusted-local Codex
producer surface, Docker metadata surface, selected image manifest route, and
private patch staging shape without crossing into patch generation, image
pull/run, or evaluation.

This preflight did not read raw issue text, source file contents, source diffs,
patch content, tests, hidden references, credentials, shell history, Codex auth,
raw trajectories, screenshots, or other users' workspace content. It did not
invoke a Codex prompt, call a model API, pull a Docker image, start a
container, evaluate a patch, upload, submit, or touch public ranking paths.

## Observed Compact Facts

Trusted-local Codex producer surface:

```text
codex_cli_present=true
codex_cli_version=0.128.0
codex_auth_read=false
codex_prompt_sent=false
model_api_invoked=false
patch_generated=false
```

Docker metadata surface:

```text
docker_reachable=true
docker_client_version=29.2.0
docker_server_version=28.4.0
docker_server_os=linux
docker_server_arch=arm64
docker_image_pulled=false
docker_container_started=false
```

Selected manifest route:

```text
image=alfin06/agentissue-bench:lagent_239
schema_version=2
media_type=application/vnd.oci.image.index.v1+json
manifest_count=2
platforms=linux/amd64,unknown/unknown
linux_amd64_present=true
```

Patch staging surface:

```text
private_patch_staging_dir_created=true
patch_output_contract=Patches/lagent_239/attempt.patch
attempt_patch_exists=false
patch_content_read=false
patch_content_public=false
```

## Bridge Decision

The bridge is ready for a future no-upload pilot at the interface level:

1. local Codex CLI exists on the trusted host;
2. Docker metadata access works;
3. the selected image has a registry-visible `linux/amd64` route;
4. the private patch staging shape can hold only the selected tag's
   `Patches/lagent_239/attempt.patch` output.

This still does not authorize the real pilot. A future pilot must separately
cross these execution gates in order:

1. public source checkout/content read for `InternLM/lagent`;
2. local Codex prompt/model invocation;
3. patch generation into the selected patch path;
4. Docker pull/run for only `alfin06/agentissue-bench:lagent_239`;
5. patch evaluation and compact result reduction.

No upload, submit, or public ranking path is allowed by this packet.

## Validation

```bash
python3 examples/agentissue-bench-lagent239-bridge-preflight-smoke.py
python3 -m py_compile examples/agentissue-bench-lagent239-bridge-preflight-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-lagent239-bridge-preflight-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-bridge-preflight-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
git diff --check \
  docs/research/long-horizon-agent-benchmarks/README.md \
  docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-bridge-preflight-v0.md \
  examples/agentissue-bench-lagent239-bridge-preflight-smoke.py
```

## Claim Boundary

This packet may claim only bridge/preflight readiness for the selected
AgentIssue-Bench tag. It may not claim a patch attempt, Docker task execution,
official score, task resolution, upload, submit, or leaderboard/public ranking
result.
