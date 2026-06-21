# SWE-Bench Pro Route B Provider Descriptor v0

Date: 2026-06-12

Purpose: stage the provider descriptor required by the SWE-Bench Pro
launch-wrapper contract, using the already-redacted Route B provider and
runner-plumbing proofs. This packet selects Route B only as a no-auth remote
helper/provider surface. It does not authorize the selected pilot yet.

## Inputs

This descriptor consumes only compact public-safe evidence already recorded in
the benchmark research folder:

- `remote-gpu-noauth-provider-probe-v0.md`;
- `remote-gpu-route-ab-proof-v0.md`;
- `remote-gpu-route-b-sync-install-proof-v0.md`;
- `remote-gpu-route-b-runner-plumbing-preflight-v0.md`;
- `swe-bench-pro-launch-wrapper-contract-v0.md`.

It does not read or copy the local Codex auth directory, API keys, shell
history, SSH private keys, raw task material, private sample contents, patch
contents, evaluator script bodies, trajectories, screenshots, or other users'
workspace content.

## Descriptor

```text
provider_descriptor_ready=true
selected_provider=remote_gpu_route_b_noauth_helper
provider_selection_scope=no_auth_helper_and_runner_plumbing
codex_auth_sync_allowed=false
credential_sync_allowed=false
remote_codex_invocation_allowed=false
remote_model_api_invocation_allowed=false
private_material_sync_allowed=false
raw_task_material_public=false
upload_allowed=false
submit_allowed=false
public_ranking_allowed=false
```

Compact provider facts inherited from earlier redacted proofs:

```text
ssh_connectivity_proven=true
workspace_private_proven=true
sync_install_proven=true
runner_plumbing_proven=true
remote_docker_available=true
remote_gpu_visible=true
remote_high_capacity=true
temporary_registry_runtime_supported=true
image_pull_or_container_start_proven=false
selected_image_platform_final_preflight_done=false
```

## Launch Impact

This clears the `provider_not_selected` blocker from the prior
`swe_bench_pro_launch_wrapper_contract_result_v0` state. It does not clear the
remaining launch blockers:

- private sample descriptor missing;
- attempt patch descriptor missing;
- evaluator scripts descriptor missing;
- selected image acquisition/container preflight still not performed.

Therefore the selected pilot remains `not_run`, with no official score claim.
The next useful SWE-Bench Pro step is to stage the private descriptors through a
private-only surface, or to write a compact blocker if those descriptors cannot
be prepared without leaking raw task or credential material.

## Validation

```bash
python3 examples/swe-bench-pro-route-b-provider-descriptor-smoke.py
python3 -m py_compile examples/swe-bench-pro-route-b-provider-descriptor-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-route-b-provider-descriptor-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-route-b-provider-descriptor-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
git diff --check \
  docs/research/long-horizon-agent-benchmarks/README.md \
  docs/research/long-horizon-agent-benchmarks/swe-bench-pro-route-b-provider-descriptor-v0.md \
  examples/swe-bench-pro-route-b-provider-descriptor-smoke.py
```

## Claim Boundary

This packet may claim only that the public provider descriptor is ready for the
no-auth Route B helper surface. It may not claim a real SWE-Bench Pro run, a
resolved task, image compatibility, patch quality, official evaluation, upload,
submit, or leaderboard/public ranking result.
