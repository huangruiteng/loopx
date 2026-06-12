# AgentIssue-Bench Codex CLI Runner Run Gate V0

This packet adds one no-execute run-specific gate for the selected
AgentIssue-Bench tag `lagent_239`:

```bash
goal-harness benchmark agentissue-codex-runner-flow \
  --goal-id <goal-id> \
  --tag lagent_239 \
  --run-gate-root <private-gate-root>
```

The command materializes the workflow check plus
`run-specific-gate.public.json` and `run-specific-gate.md`. It is a gate packet,
not a benchmark run.

## Gate Separation

`run-specific-gate.public.json` separates gates into two groups:

- already covered by no-run public packets: selected tag/image lock, host Codex
  auth isolation, patch-output relative path, no-upload/no-submit/no-ranking
  eval, compact/public artifact policy, and raw-artifact/auth leak stop rules;
- still blocking a real run: private job root selection, explicit real-run
  trigger, selected-container source extraction, private git baseline creation,
  and host-local `codex exec --ephemeral` from the extracted buggy source.

The packet records `real_run_authorized=false` and `ready_for_real_run=false`.
It is only `ready_for_operator_review=true`.

## Public Boundary

The packet is still no-run. It does not pull or start Docker, invoke Codex,
call a model API, extract source, initialize git, generate or evaluate a patch,
read credentials, sync auth material, upload, submit, touch public ranking
paths, publish raw issue/task/patch/log/trajectory material, use destructive
git, or take production action.

Allowed public artifacts are limited to relative-path public/compact JSON and
Markdown gate packets.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py
python3 -m py_compile examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py
goal-harness check \
  --scan-path examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-run-gate-v0.md
```
