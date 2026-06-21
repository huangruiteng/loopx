# AgentIssue-Bench Codex CLI Runner Workflow Check V0

This packet adds one no-execute workflow invariant check for the selected
AgentIssue-Bench tag `lagent_239`:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id <goal-id> \
  --tag lagent_239 \
  --workflow-check-root <private-check-root>
```

The command materializes the first-run handoff packet plus
`workflow-check.public.json`. It reads only the public/compact files it just
created inside the selected private root:

```text
runner-flow-plan.public.json
execution-gate.public.json
first-run-handoff.public.json
workflow-check.public.json
benchmark_run.compact.json
```

## Checked Invariants

`workflow-check.public.json` records boolean checks for the pre-run workflow:

- one selected tag and one selected image across runner plan, execution gate,
  and handoff packet;
- `source_extracted_before_codex`: selected-container source extraction is
  planned before host-local `codex exec --ephemeral`;
- `host_codex_auth_not_synced`: Codex auth stays on the host and no Codex home
  is synced to a shared host;
- the Codex worker has no network or Docker access in the rendered command
  contract;
- `Patches/lagent_239/attempt.patch` is produced from the extracted source git
  diff rather than current public HEAD or fixed/oracle material;
- selected-tag eval disables upload, submit, and public ranking paths;
- public outputs are limited to public/compact JSON and Markdown packets.

The packet is still no-run. It does not pull or start Docker, invoke Codex,
call a model API, extract source, initialize git, generate or evaluate a patch,
read credentials, sync auth material, upload, submit, touch public ranking
paths, publish raw issue/task/patch/log/trajectory material, use destructive
git, or take production action.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py
python3 -m py_compile examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-workflow-check-v0.md
```
