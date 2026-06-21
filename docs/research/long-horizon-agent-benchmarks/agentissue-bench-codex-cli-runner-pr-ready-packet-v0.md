# AgentIssue-Bench Codex CLI Runner PR-Ready Packet V0

Date: 2026-06-13

## Scope

This packet consolidates the AgentIssue-Bench `lagent_239` Codex CLI runner
route into one public-safe review surface. It does not run Codex, Docker, a
model API, source extraction, patch generation, patch evaluation, upload,
submit, or public ranking paths.

The route is intentionally single-benchmark and single-tag:

```text
benchmark=agentissue-bench
selected_tag=lagent_239
selected_image=alfin06/agentissue-bench:lagent_239
real_run=false
submit_eligible=false
leaderboard_evidence=false
```

## Consolidated Artifacts

The PR-ready packet is complete only when these public artifacts move together:

```text
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-contract-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-flow-plan-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-dry-run-wrapper-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-synthetic-staging-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-execution-gate-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-first-run-handoff-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-workflow-check-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-run-gate-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-target-handoff-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-pr-ready-packet-v0.md
```

And these public smokes:

```text
examples/agentissue-bench-codex-cli-runner-contract-smoke.py
examples/agentissue-bench-codex-cli-runner-flow-smoke.py
examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py
examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py
examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py
examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py
examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py
examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py
examples/agentissue-bench-codex-cli-runner-target-handoff-smoke.py
examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py
```

## Route Summary

The route narrows from high-level contract to no-execute handoff:

```text
contract -> flow plan -> dry-run wrapper -> synthetic staging -> execution gate -> first-run handoff -> workflow check -> run-specific gate -> target-runner handoff -> PR-ready packet
```

The CLI surfaces are:

```text
loopx benchmark agentissue-codex-runner-flow --tag lagent_239
loopx benchmark agentissue-codex-runner-flow --tag lagent_239 --synthetic-staging-root <private-root>
loopx benchmark agentissue-codex-runner-flow --tag lagent_239 --execution-gate-root <private-root>
loopx benchmark agentissue-codex-runner-flow --tag lagent_239 --first-run-handoff-root <private-root>
loopx benchmark agentissue-codex-runner-flow --tag lagent_239 --workflow-check-root <private-root>
loopx benchmark agentissue-codex-runner-flow --tag lagent_239 --run-gate-root <private-root>
loopx benchmark agentissue-codex-runner-flow --tag lagent_239 --target-runner-handoff-root <private-root>
```

All root options are mutually exclusive. They materialize public-safe packet
shapes only; root paths are not recorded in public payloads.

## Public Boundary

The public boundary for this route is:

```text
allowed public evidence: schema/mode, selected tag, selected image label, command shape, relative file names, compact validation booleans, hash/count/status field names
forbidden public evidence: issue body, patch content, raw logs, trajectories, screenshots, local absolute paths, auth files, token names, API keys, fixed/oracle material
```

The later e2e run remains separate from this PR-ready packet. A separate
benchmark execution thread can use the target-runner handoff plus run-specific
gate checklist before triggering a real run, but that real run is not part of
this packet.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py
python3 -m py_compile \
  loopx/benchmark.py \
  loopx/cli.py \
  examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py
loopx check \
  --scan-path loopx/benchmark.py \
  --scan-path loopx/cli.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-pr-ready-packet-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
