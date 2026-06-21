# SWE-Bench Pro Private Descriptor Blocker v0

Date: 2026-06-12

Purpose: record the remaining launch blocker for the selected SWE-Bench Pro
pilot after the launch-wrapper contract and Route B provider descriptor are
ready. This packet is the compact fallback requested by the active state when
private descriptors cannot be staged without crossing the public/private
boundary.

## What Is Ready

- Selected public instance metadata is compacted.
- Public launch-wrapper/preflight contract is ready.
- Route B is selected as the no-auth helper/provider descriptor.
- Upload, submit, public ranking, Codex auth sync, credential sync, raw
  trajectory, screenshot, and public raw-task surfaces remain disabled.

## Descriptor Probe

The probe was filename-only. It did not open, parse, print, hash, or copy
private task material, patch content, evaluator scripts, credentials, local
absolute paths, shell history, trajectories, screenshots, or other users'
workspace content.

Compact result:

```text
private_sample_descriptor_ready=false
attempt_patch_descriptor_ready=false
evaluator_scripts_descriptor_ready=false
provider_descriptor_ready=true
launch_wrapper_contract_ready=true
pilot_launch_authorized=false
raw_task_material_read=false
patch_content_read=false
evaluator_script_body_read=false
codex_cli_invoked=false
model_api_invoked=false
docker_image_acquired=false
container_started=false
upload_invoked=false
submit_invoked=false
public_ranking_path_touched=false
```

## Blocker

The remaining blocker is no longer a provider-capacity or launch-contract
blocker. It is a private descriptor staging blocker:

- no private sample descriptor is present;
- no attempt patch descriptor is present;
- no evaluator scripts descriptor is present;
- official evaluator launch remains disallowed until those descriptors exist
  in a private-only surface and are reduced to hashes/counts/readiness booleans
  for public writeback.

The evaluator scripts are deliberately not read from public `run_scripts`
material here. The prior source preflight excluded run scripts because they are
outside the public-safe source slice for this benchmark lane.

## Next Gate

The next useful step is one of:

1. create a private-only descriptor staging area for this selected instance,
   then reduce only descriptor hashes/counts/readiness to public artifacts; or
2. defer the SWE-Bench Pro pilot and choose another benchmark lane whose first
   real e2e case does not require raw task/sample/patch/script staging before
   launch.

Until one of those happens, retrying the selected pilot would repeat the same
blocker and should not spend benchmark/model/Docker budget.

## Validation

```bash
python3 examples/swe-bench-pro-private-descriptor-blocker-smoke.py
python3 -m py_compile examples/swe-bench-pro-private-descriptor-blocker-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-private-descriptor-blocker-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-private-descriptor-blocker-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
git diff --check \
  docs/research/long-horizon-agent-benchmarks/README.md \
  docs/research/long-horizon-agent-benchmarks/swe-bench-pro-private-descriptor-blocker-v0.md \
  examples/swe-bench-pro-private-descriptor-blocker-smoke.py
```

## Claim Boundary

This packet may claim only that the remaining SWE-Bench Pro launch blocker is
private descriptor staging. It may not claim a real benchmark run, a patch
attempt, task resolution, image compatibility, official evaluation, upload,
submit, or leaderboard/public ranking result.
