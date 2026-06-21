# AgentIssue-Bench Codex CLI Runner Contract V0

Date: 2026-06-12

## Scope

This packet replaces ad hoc agent execution with a Codex CLI benchmark runner
contract for AgentIssue-Bench.

The current focus is deliberately narrow:

```text
only_active_benchmark=agentissue-bench
initial_tag=lagent_239
no_other_benchmarks_until=agentissue_codex_cli_runner_e2e_clean
```

Other benchmark candidates remain frozen until this runner can execute one
clean AgentIssue-Bench single-tag loop end to end.

## Official Codex CLI Metric

No official AgentIssue-Bench Codex CLI metric was found in the current public
leaderboard or official repository scan.

The official public leaderboard currently lists:

```text
AutoCodeRover + Claude 3.5 Sonnet: 4.67%
Agentless + Claude 3.5 Sonnet: 4.00%
Agentless + GPT-4o: 3.33%
SWE-agent + Claude 3.5 Sonnet: 2.00%
AutoCodeRover + GPT-4o: 1.33%
SWE-agent + GPT-4o: 0.67%
```

So any Codex CLI result from this repo should be labeled as a local no-upload
Codex CLI reproduction result, not an official leaderboard metric.

Sources checked:

- https://alfin06.github.io/AgentIssue-Bench-Leaderboard/
- https://github.com/alfin06/AgentIssue-Bench

## Runner Principle

Codex CLI must run against the benchmark buggy snapshot, not the latest public
repository HEAD.

The failed exploratory pilot showed why: a patch generated against current
`InternLM/lagent` HEAD can apply cleanly in the selected container yet still
fail the container oracle, because the benchmark tests a different buggy
snapshot. The runner must therefore extract the buggy source from the selected
container, initialize a local git baseline, and only then call Codex CLI.

## Execution Flow

### 1. Prepare Isolated Job

Create a private job root with:

```text
context/
source/
buggy-source/
Patches/lagent_239/
logs/
reduced/
```

The job root is private/local. Public writeback may include only counts, hashes,
status labels, and reduced scores.

### 2. Fetch Public Issue Context

Fetch the selected public issue and comments into the private job root.

Public artifacts may record:

- issue URL;
- title/body/comment lengths;
- hashes;
- timestamps;
- comment count.

Public artifacts must not reproduce raw issue text.

### 3. Pull Only The Selected Image

Pull only:

```text
alfin06/agentissue-bench:lagent_239
```

Do not call official all-tag helper scripts. Do not run global Docker cleanup.

### 4. Extract Buggy Source

Use a selected-tag container to copy the benchmark buggy source to the host
private job root.

Required policy:

- copy only the buggy source tree needed for patch generation;
- do not copy fixed source, hidden references, or result artifacts;
- initialize a local git baseline in the extracted source;
- do not use current public repository HEAD as the patch-generation source.

### 5. Run Codex CLI As Patch Worker

Invoke host-local Codex CLI only after buggy-source extraction:

```text
codex exec --ephemeral --ignore-rules --sandbox workspace-write \
  --cd <buggy-source> \
  --add-dir <job-root> \
  --output-last-message <job-root>/codex-last-message.txt \
  <prompt-file>
```

Worker constraints:

- Codex auth stays local-only;
- never sync `~/.codex`;
- never mount credentials into Docker;
- worker does not use Docker;
- worker does not use network;
- worker does not read fixed diff or oracle material;
- worker leaves source changes unstaged.

### 6. Write Attempt Patch

After Codex exits, write:

```text
Patches/lagent_239/attempt.patch
```

from the extracted buggy-source git diff.

Public writeback may include patch hash, bytes, changed-file count, and hunk
count. It must not include patch content.

### 7. Evaluate Single Tag

Evaluate only the generated patch against the selected image:

```text
docker run --platform linux/amd64 --rm --entrypoint bash \
  -v <patch-dir>:/patches:ro \
  alfin06/agentissue-bench:lagent_239 \
  -c '<apply_patch_and_test_patched>'
```

Do not pass API keys or `.env` values to this container. Do not use official
helpers that scan all tags or require model/search credentials.

### 8. Compact Reducer

Write compact private-to-public reduction:

```text
tag
image_digest
patch_sha256
patch_bytes
exit_code
resolved
duration_seconds
log_sha256
no_upload
no_submit
no_public_ranking_path
```

Raw logs, patch content, local paths, raw issue text, trajectories, screenshots,
credentials, and command argv stay private.

## Stop Rules

Stop the runner before public writeback if any of these happens:

- Codex auth or credentials would be copied to a shared host or container;
- the worker would run on current public HEAD instead of benchmark buggy
  source;
- the worker would read fixed diff, hidden references, or oracle material
  before patch generation;
- official helper scripts would run all tags, global cleanup, credential
  prompts, upload, submit, or public ranking paths;
- compact reducer cannot separate patch/log hashes from raw content.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-contract-smoke.py
python3 -m py_compile examples/agentissue-bench-codex-cli-runner-contract-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-codex-cli-runner-contract-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-contract-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
git diff --check \
  docs/research/long-horizon-agent-benchmarks/README.md \
  docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-contract-v0.md \
  examples/agentissue-bench-codex-cli-runner-contract-smoke.py
```
