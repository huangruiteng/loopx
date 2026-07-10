# issue_fix_reviewer_request_v0

`issue_fix_reviewer_request_v0` is the public-safe execution contract for
automatically inviting a reviewer after an issue-fix PR exists. It converts the
read-only reviewer recommendation into one bounded external write and proves
that the request became visible on the pull request.

## Default Behavior

The default strategy is `request_top_requestable_when_authorized`:

1. read live PR metadata;
2. exclude the PR author, bots, explicitly excluded identities, reviewers
   already requested, and people who already reviewed;
3. rank remaining candidates from repository `CODEOWNERS`, exact changed-path
   contribution history, and nearest-module history;
4. request the highest-ranked candidate with a resolvable GitHub handle;
5. read the PR again and require the selected reviewer to appear in the review
   request list;
6. continue PR lifecycle monitoring only after that verification.

The default maximum is one reviewer. Existing requested or completed review
coverage counts toward that maximum, so repeated execution is idempotent and
does not keep adding people. A low-confidence candidate is still eligible when
it is the best requestable, non-author repository-native candidate; confidence
is evidence quality, not an automatic skip rule.

## Authority Model

Review requests are external writes. `--execute` asserts that the host has an
active `external_review_request` authority scope; the existing broader
`publish` authority also satisfies this action in the issue-fix gate. Without
that authority, the command may prepare a request preview from compact PR
metadata but cannot write.

This authority does not authorize comments, pushes, PR creation, merge, or any
other publication action. Long-running agents with standing reviewer-request
authority should call this command automatically after PR creation instead of
asking a human to perform the routine invitation.

## CLI

Execute and verify the default request:

```bash
loopx issue-fix reviewer-request \
  --url https://github.com/owner/repo/pull/123 \
  --repo-path /path/to/approved/repo \
  --base-ref origin/main \
  --identity-map-json verified-identities.json \
  --execute \
  --format json
```

Preview without an external write by supplying compact, caller-approved PR
metadata containing `author`, `reviewRequests`, `reviews`, and `state`:

```bash
loopx issue-fix reviewer-request \
  --url https://github.com/owner/repo/pull/123 \
  --repo-path /path/to/approved/repo \
  --base-ref origin/main \
  --metadata-json pr-metadata.json \
  --format json
```

A preview without complete PR metadata fails closed because author exclusion
cannot be verified. Execute mode applies the same rule if the live provider
response omits the author. The compact metadata payload is never copied into
the output packet.
`--identity-map-json` may carry a human-verified git-display-name to GitHub
handle mapping when the strongest contribution candidate could not be resolved
from public noreply identity evidence. The mapping resolves identity but does
not change the underlying ownership score.

## Output And Transitions

The packet records:

- selected and verified requested reviewer handles;
- whether external-read and external-write actions were performed;
- whether the request was performed and fully verified;
- the recommendation status and public-safe evidence candidates;
- one structured transition.

Successful verified requests emit
`issue_fix_reviewer_request_verified` with `monitor_continuation`. If review is
already covered, execution is a quiet, no-write monitor continuation. Missing
requestable identity produces a runnable identity-resolution successor. Closed
PRs produce structured no-follow-up.

Network, permission, provider, or post-write verification failures produce a
concrete blocker while preserving the selected reviewer for a bounded retry.
The command never reports success solely because the write command returned
zero.

## Public-Safety Boundary

Every packet keeps these fields false:

- `local_paths_captured`
- `raw_provider_payload_captured`
- `raw_git_output_captured`
- `commit_emails_captured`

It stores no credential, local path, raw provider response, raw git log, issue
body, comment body, transcript, or runtime state. Repository history is read
only from the explicitly approved checkout and affects the compact ranking
evidence.

## Validation

Run:

```bash
python3 examples/issue-fix-reviewer-request-smoke.py
```

The generic fixture verifies live-author exclusion, top-candidate selection,
successful request and readback, idempotent already-covered behavior,
permission/network-style blockers, public-safety boundaries, and no-write CLI
preview. It contains no OpenViking-specific branch or candidate.
