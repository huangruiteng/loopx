# AgentIssue-Bench `lagent_239` Public Context Packet V0

Date: 2026-06-12

## Scope

This packet records the owner-delegated public task-context read for
AgentIssue-Bench tag `lagent_239`.

The selected public issue route is:

```text
https://github.com/InternLM/lagent/issues/239
```

This packet did read the public issue title, body, and comments through
GitHub's public API, but it records only hashes, lengths, counts, state, and
timestamps. It does not reproduce the raw issue title/body/comment text in the
public artifact.

No Docker image was pulled or started. No benchmark test ran. No patch was
generated or evaluated. No Codex CLI or model API was invoked. No upload,
submit, leaderboard/public ranking path, credential, raw trajectory,
screenshot, hidden reference, solution, gold material, test patch, or test body
surface was touched.

## Source Evidence

- AgentIssue-Bench source pin:
  `alfin06/AgentIssue-Bench@1d498dec35e347c4e7b9e1c318ef28fc5fa97318`
- Selected tag: `lagent_239`
- Selected image: `alfin06/agentissue-bench:lagent_239`
- Manifest-only gate from the previous packet: registry-visible `linux/amd64`
  route, without pull/run.
- Public context source:
  `https://github.com/InternLM/lagent/issues/239`

GitHub API compact metadata captured 2026-06-12:

- issue number: `239`
- issue state: `closed`
- issue locked: `false`
- created at: `2024-08-21T10:43:51Z`
- updated at: `2024-08-28T07:04:09Z`
- closed at: `2024-08-28T07:04:09Z`
- title chars: `57`
- title sha256:
  `9a0600fe2e0c88d886847e3afe433508b458463e978a99eb86e0d743102408b2`
- body chars: `125`
- body sha256:
  `f4c8e9fdb337b030730c31e69ea7d62ffa1808fd9843ea17eeb4949d7533bb79`
- comment count: `1`
- comments chars: `168`
- comments sha256:
  `6602126a5f058a9705f5e733cb4d1d5aad2c483e1a4f9cde114d97dca8fa3357`
- label count: `0`
- pull request: `false`

## Packet Boundary

The executable fixture is
`examples/agentissue-bench-lagent239-public-context-smoke.py`.

It emits an `agentissue_bench_public_context_packet_v0` object and a compact
`benchmark_run_v0` no-run projection with:

- `source_runner=agentissue-bench`;
- `benchmark_id=agentissue-bench`;
- `mode=public_context_hash_only_no_run`;
- `task_selector_kind=selected_public_tag`;
- `task_selector_hash=lagent_239`;
- one pending blocked trial;
- `public_issue_context_available=true`;
- `raw_issue_text_public=false`;
- `raw_patch_or_test_material_public=false`;
- `no_docker_pull=true`;
- `no_docker_run=true`;
- `no_model_call=true`;
- `no_upload=true`;
- `no_submit=true`;
- `no_public_ranking_path=true`.

The fixture asserts that public outputs do not contain raw issue title/body,
raw comments, local paths, credentials, problem statements, gold patches, test
patches, test lists, solutions, Docker output, raw trajectories, screenshots,
or Codex auth material.

## Decision

The previous context gate is cleared for this selected tag at the public issue
metadata layer. The next safe AgentIssue-Bench step is a no-run local Codex
patch-producer packet:

1. Use the public issue route as redacted/hash-backed task context.
2. Define a trusted-local Codex patch producer that can later write only
   `Patches/lagent_239/attempt.patch`.
3. Keep code-source sync, Docker pull/run, Codex/model invocation, patch
   generation, patch evaluation, uploads, submit, public ranking paths,
   credentials, raw issue text, raw patch/test material, trajectories, and
   screenshots out of public artifacts until a future execution-specific gate.
