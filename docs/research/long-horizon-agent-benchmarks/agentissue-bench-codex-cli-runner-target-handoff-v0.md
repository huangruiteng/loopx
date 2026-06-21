# AgentIssue-Bench Codex CLI Runner Target Handoff V0

This packet adds one no-execute target-runner handoff for the selected
AgentIssue-Bench tag `lagent_239`:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id <goal-id> \
  --tag lagent_239 \
  --target-runner-handoff-root <private-handoff-root>
```

The command materializes the run-specific gate plus
`target-runner-handoff.public.json` and `target-runner-handoff.md`. It is a
handoff packet for a separate benchmark execution thread, not a benchmark run
and not permission for the meta heartbeat thread to execute.

## Execution Boundary

The packet records:

- `handoff_target=separate_benchmark_execution_thread`
- `meta_heartbeat_must_not_execute=true`
- `real_run_authorized_by_packet=false`
- `ready_for_real_run=false`

The target execution thread must satisfy the run-specific gate before any real
run: private job root selection, explicit real-run trigger, selected-container
source extraction, private git baseline, host-local `codex exec --ephemeral`
from the extracted buggy source, attempt-patch export, selected-tag eval with
no upload/submit/ranking path, compact public reducer, and host-local Codex auth
isolation.

## Public Boundary

The packet is still no-run. It does not pull or start Docker, invoke Codex,
call a model API, extract source, initialize git, generate or evaluate a patch,
read credentials, sync auth material, upload, submit, touch public ranking
paths, publish raw issue/task/patch/log/transcript material, use destructive
git, or take production action.

Allowed public artifacts are limited to relative-path public/compact JSON and
Markdown handoff packets:

- `benchmark_run.compact.json`
- `run-specific-gate.public.json`
- `target-runner-handoff.public.json`
- `target-runner-handoff.md`

Private execution artifacts must be reduced before any public writeback.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-target-handoff-smoke.py
python3 -m py_compile examples/agentissue-bench-codex-cli-runner-target-handoff-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-codex-cli-runner-target-handoff-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-target-handoff-v0.md
```
