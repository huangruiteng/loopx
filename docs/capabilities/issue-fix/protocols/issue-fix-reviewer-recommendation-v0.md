# issue_fix_reviewer_recommendation_v0

`issue_fix_reviewer_recommendation_v0` is the public-safe contract for ranking
people or teams who may be appropriate reviewers for an issue-fix change. It
turns repository-native ownership evidence into an explainable recommendation;
it does not assign a reviewer, request review, or grant publication authority.

## Product Intent

A long-running issue-to-PR agent should not stop after producing a correct
patch. It should also prepare a credible review route that helps the change
reach a maintainer. Reviewer selection is therefore part of issue-fix planning,
while the external GitHub review request remains a separately authorized write.

The contract must answer four questions:

1. Which changed paths support this candidate?
2. Is the candidate backed by repository policy, contribution history, or both?
3. Can the candidate be resolved to a requestable GitHub handle?
4. What human or repository-policy check remains before requesting review?

## Evidence Order

The first implementation uses this conservative authority order:

1. the last matching rule from the repository's first supported `CODEOWNERS`
   file: `.github/CODEOWNERS`, `CODEOWNERS`, then `docs/CODEOWNERS`;
2. author history for each exact changed path;
3. author history for the nearest module directory when a new path has no
   usable exact-path history.

`CODEOWNERS` receives dominant scoring weight because it expresses repository
policy. Git history is advisory familiarity evidence: commit count or recency
does not by itself prove maintainer authority, current availability, or consent
to review.

The pattern matcher intentionally supports a common, deterministic subset of
`CODEOWNERS` syntax. The packet reports
`codeowners_pattern_support: common_subset`; repositories that depend on more
specialized matching semantics must verify the recommendation against their
native platform policy.

## CLI

Preview without reading the local repository:

```bash
loopx issue-fix reviewer-plan \
  --repo-path /path/to/approved/repo \
  --repo owner/repo \
  --changed-file src/service.py \
  --exclude-reviewer @pull-request-author \
  --exclude-author-name "PR Author Git Name" \
  --format json
```

Read only the caller-approved local checkout and derive changed paths from a
base ref:

```bash
loopx issue-fix reviewer-plan \
  --repo-path /path/to/approved/repo \
  --repo owner/repo \
  --base-ref origin/main \
  --exclude-reviewer @pull-request-author \
  --exclude-author-name "PR Author Git Name" \
  --execute \
  --format json
```

`--execute` authorizes local repository inspection only. It does not authorize
network access, a GitHub review request, a comment, a push, or a merge.

## Input Contract

- `repo_path`: caller-approved local git checkout; never copied into output;
- `repo`: compact public-safe repository label;
- `changed_files`: optional explicit repo-relative paths;
- `base_ref`: diff base used when changed files are not supplied;
- `history_limit`: bounded history depth per path;
- `max_candidates`: bounded result count;
- `exclude_reviewers`: GitHub handles that must not be recommended, normally
  including the PR author and known unavailable identities;
- `exclude_author_names`: git display-name aliases for an excluded handle when
  identity resolution is unavailable; only the count is retained in output;
- `execute`: whether local repository state may be read.

Changed paths must be non-empty and repo-relative. Preview mode does not
inspect `repo_path` and returns `recommendation_status: preview_only`.

## Output Contract

The packet uses `schema_version: issue_fix_reviewer_recommendation_v0` and
contains:

- `recommendation_status`: `preview_only`, `candidates_ready`,
  `identity_resolution_required`, or `no_candidates`;
- `changed_files` and `changed_file_count` using repo-relative paths only;
- ranked `candidates` with stable candidate id, optional GitHub handle,
  requestability, score, source kinds, reason codes, matched paths,
  `CODEOWNERS` patterns, history count, recency rank, path coverage, and
  confidence;
- `evidence_summary` describing the authority order and fallbacks;
- `policy` stating that recommendation is not assignment and automatic review
  request is forbidden;
- public-safety and side-effect flags.

Candidates without a verified GitHub handle remain visible as familiarity
evidence but are marked `requestable: false` with
`github_identity_resolution_required`. The packet never exposes the underlying
commit email.

## Ranking Rules

- Each matching `CODEOWNERS` path adds a dominant ownership score.
- Exact-path and module history at the selected base revision add bounded,
  recency-weighted familiarity scores; feature-branch commits are not counted.
- Bot-like identities found only in git history are excluded; an explicit
  repository ownership rule remains authoritative.
- Evidence from multiple changed paths raises path coverage.
- A candidate supported by both ownership policy and history receives high
  confidence; single-source evidence remains medium or low.
- Excluded handles are removed before ranking.

Scores only order evidence inside this packet. They must not be interpreted as
a universal maintainer ranking or a performance metric.

## Required Boundaries

Every valid packet preserves:

- `external_reads_performed: false`
- `external_writes_performed: false`
- `review_request_performed: false`
- `local_paths_captured: false`
- `raw_git_output_captured: false`
- `commit_emails_captured: false`
- `automatic_review_request_allowed: false`

`private_repo_state_read` is `false` in preview and `true` only after an
explicit `--execute` against the caller-approved checkout. No raw `CODEOWNERS`
file, raw git log, credentials, private material, or runtime state belongs in
the packet.

## Human And Repository Policy Gate

Before any external review request, the host agent or human must verify:

- the PR author and unavailable reviewers are excluded;
- the repository permits the request and any team handle is requestable;
- the recommendation still matches the final diff;
- ownership is not being inferred solely from a large historical commit count;
- sensitive or architectural changes receive any additional mandatory review.

A later authority-gated connector may consume this packet, but the connector
must record a separate external-write decision. This schema must never be used
as implicit review-request authority.

## Planned Extensions

Future versions may add repository-native signals with real call sites:

- maintainer availability and explicit opt-out;
- review-response and approval history;
- semantic module mapping for generated or moved files;
- risk-class or sensitive-path reviewer requirements;
- load balancing and fallback escalation after a stale review request;
- repository-host identity resolution for teams and non-noreply authors.

These signals should extend the explainable evidence packet, not introduce an
OpenViking-specific adapter or an independent reviewer state machine.

## Validation

Run:

```bash
python3 examples/issue-fix-reviewer-recommendation-smoke.py
```

The smoke uses a temporary non-project-specific repository to verify
`CODEOWNERS`, exact-path history, module fallback, author exclusion, CLI
execution, identity handling, and the no-external-write boundary.
