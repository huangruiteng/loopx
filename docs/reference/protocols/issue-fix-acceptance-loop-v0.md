# issue_fix_acceptance_loop_v0

`issue_fix_acceptance_loop_v0` is the first executable LoopX protocol for repo
issue fix work. Its goal is acceptance, not display: given a public issue/PR
metadata signal, the loop must prove that an agent can move from signal to a
validated fix artifact.

The initial implementation is a deterministic fixture command:

```bash
loopx issue-fix acceptance-fixture --format json
```

The command creates a temporary fixture workspace, runs a focused repro that
fails, applies a minimal code patch, reruns the same focused validation, and
returns an `issue_fix_validated_fix_artifact_v0`. The artifact is ready only
when the repro failed before the patch and validation passed after the patch.

The next fixture exercises the same repair path through a real temporary git
repository and issue branch:

```bash
loopx issue-fix repo-branch-fixture --format json
```

It initializes a local fixture repo, commits the failing baseline, creates
`codex/issue-123-public-metadata-fixture`, runs the repro, patches the branch,
reruns validation, confirms the branch-local patch diff without exposing raw
git output, and returns the same validated fix artifact shape with an extra
`issue_fix_repo_branch_artifact_v0` section.

## Product Contract

The user-facing value is the validated repair path:

1. public metadata intake establishes the repo/issue signal without copying
   issue body text or comment body text;
2. a repro command proves the bug is currently present;
3. a code route names the files and reason for the minimal patch;
4. the patch is applied in the fixture workspace;
5. focused validation passes;
6. a PR-review packet is ready, but no external comment, PR creation, merge, or
   publish action is performed by this fixture.

This keeps the protocol useful for automation while preserving safe defaults.
The packet is evidence of a completed repair loop, not a substitute for the
repair loop.

## Public-Safe Fields

The top-level packet must report:

- `external_reads_performed: false`
- `external_writes_performed: false`
- `issue_body_captured: false`
- `comment_bodies_captured: false`
- `local_paths_captured: false`
- `private_repo_state_read: false`
- `destructive_git_used: false`

Validation command output is summarized with pass/fail and exit code only. The
fixture does not expose stdout, stderr, local temporary paths, or raw provider
payloads in the artifact.

## Next Promotion

The next implementation step is a caller-provided repo-local branch mode. It
should accept a public issue URL plus an already-approved local repository,
create or claim an issue branch, derive or run a focused repro, patch code
through the agent, run validation, and prepare PR evidence. That mode may
perform local repository reads and branch writes, but it still must not post
external comments, create a PR, merge, or publish without the caller choosing
that action explicitly.

## Smoke

The durable smoke is:

```bash
python3 examples/issue-fix-acceptance-loop-smoke.py
```

It exercises the CLI, checks the failure-before/fix-after validation sequence,
and rejects local path exposure in the public artifact.
