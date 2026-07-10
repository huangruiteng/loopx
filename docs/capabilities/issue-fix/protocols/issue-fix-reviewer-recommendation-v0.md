# issue_fix_reviewer_recommendation_v0

`issue_fix_reviewer_recommendation_v0` is the public-safe contract for ranking
people or teams who may be appropriate reviewers for an issue-fix change. It
turns repository-native ownership evidence into an explainable recommendation;
it does not itself assign a reviewer, request review, or grant publication
authority. Its default downstream policy is to let the separately authorized
`reviewer-request` command invite the top requestable candidate.

## Product Intent

A long-running issue-to-PR agent should not stop after producing a correct
patch. It should also prepare a credible review route that helps the change
reach a maintainer. Reviewer selection is therefore part of issue-fix planning,
while the external GitHub review request remains a separately authorized,
verified write.

The contract must answer four questions:

1. Which changed paths support this candidate?
2. Is the candidate backed by repository policy, a repository-declared
   maintainer map, contribution history, or a combination?
3. Can the candidate be resolved to a requestable GitHub handle?
4. Which public source reference explains the route, and how fresh is it?
5. What human or repository-policy check remains before requesting review?

## Evidence Order

The first implementation uses this conservative authority order:

1. the last matching rule from the repository's first supported `CODEOWNERS`
   file: `.github/CODEOWNERS`, `CODEOWNERS`, then `docs/CODEOWNERS`;
2. caller-verified repository maintainer maps whose most-specific path route
   names a primary contact;
3. author history for each exact changed path;
4. author history for the nearest module directory when a new path has no
   usable exact-path history;
5. repository-declared fallback or cross-module contacts when no more-specific
   route applies, or when the primary contact is excluded.

`CODEOWNERS` receives dominant scoring weight because it expresses executable
repository policy. A maintainer map is stronger routing evidence than
familiarity alone, but remains caller-verified and freshness-qualified rather
than branch-protection authority. Git history is advisory familiarity evidence:
commit count or recency does not by itself prove maintainer authority, current
availability, or consent to review.

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
  --identity-map-json verified-identities.json \
  --reviewer-sources-json reviewer-sources.json \
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
  --reviewer-sources-json reviewer-sources.json \
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
- `identity_map_json`: optional public-safe, human-verified mapping from git
  display names to GitHub handles; the raw mapping is not retained, while the
  resolved handle and `caller_verified_github_identity` evidence are visible;
- `reviewer_sources_json`: optional
  `issue_fix_reviewer_sources_input_v0` packet. Each source has a stable id,
  `maintainer_map` kind, public HTTPS or repo-relative reference,
  `authoritative|verified|advisory` trust, `current|stale|unknown` freshness,
  a timezone-aware `observed_at`, and bounded routes. Routes use `path_prefix`,
  `path_glob`, or
  `repository_fallback`, and name primary and/or fallback GitHub handles;
- `execute`: whether local repository state may be read.

LoopX does not fetch or copy the linked page. The caller reads an approved
public source, supplies only the compact route mapping, and keeps the source
URL as provenance. This makes a GitHub maintainer-map issue, a repository doc,
or a checked-in ownership file usable through one provider-neutral contract
without storing the raw body.

Example:

```json
{
  "schema_version": "issue_fix_reviewer_sources_input_v0",
  "sources": [
    {
      "source_id": "repository-maintainer-map",
      "source_kind": "maintainer_map",
      "reference": "https://github.com/owner/repo/issues/10",
      "trust": "verified",
      "freshness": "current",
      "observed_at": "2026-07-10T00:00:00Z",
      "routes": [
        {
          "route_id": "service-module",
          "match_kind": "path_prefix",
          "pattern": "src/service",
          "primary_reviewers": ["@service-owner"],
          "fallback_reviewers": ["@cross-module-owner"]
        },
        {
          "route_id": "repository-fallback",
          "match_kind": "repository_fallback",
          "primary_reviewers": [],
          "fallback_reviewers": ["@cross-module-owner"]
        }
      ]
    }
  ]
}
```

Here the `reference` is evidence lineage, not an instruction to scrape the
page. `path_prefix` and `path_glob` routes bind people to changed files;
`repository_fallback` supplies a lower-ranked cross-module route only when no
scoped route matches.

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
  `CODEOWNERS` patterns, history count, recency rank, path coverage, confidence,
  compact `reviewer_source_evidence`, and deduplicated `source_refs`;
- `evidence_summary` describing the authority order and fallbacks;
- `policy` stating that recommendation is not assignment, the default request
  strategy is `request_top_requestable_when_authorized`, the default maximum is
  one reviewer, and external-review-request authority is required;
- public-safety and side-effect flags.

Candidates without a verified GitHub handle remain visible as familiarity
evidence but are marked `requestable: false` with
`github_identity_resolution_required`. The packet never exposes the underlying
commit email.

A human may resolve an ambiguous display name once. The caller-verified handle
then becomes requestable and is reranked using the candidate's original
repository contribution evidence; the human assertion resolves identity only
and does not fabricate ownership or contribution evidence.

## Ranking Rules

- Each matching `CODEOWNERS` path adds a dominant ownership score.
- For each maintainer-map source, only the most-specific matching path route is
  used; a repository fallback is used only when no scoped route matches.
- A current verified primary contact ranks above history-only familiarity but
  below a matching CODEOWNERS owner. Fallback contacts receive lower weight.
- Trust and freshness reduce maintainer-map weight when the source is advisory,
  unknown, or stale; they never remove the external-write gate.
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
- `raw_reviewer_source_input_captured: false`
- `automatic_review_request_allowed: true`
- `automatic_request_policy: request_top_requestable_when_authorized`
- `external_review_request_authority_required: true`

`private_repo_state_read` is `false` in preview and `true` only after an
explicit `--execute` against the caller-approved checkout. No raw `CODEOWNERS`
file, maintainer-map body, raw git log, credentials, private material, or
runtime state belongs in the packet. Public source references and the compact
matched route evidence are retained because they are the audit trail.

## Human And Repository Policy Gate

Before any external review request, the host agent or human must verify:

- the PR author and unavailable reviewers are excluded;
- the repository permits the request and any team handle is requestable;
- each declared source is public, belongs to the intended repository context,
  and has an honest trust/freshness label;
- the recommendation still matches the final diff;
- ownership is not being inferred solely from a large historical commit count;
- sensitive or architectural changes receive any additional mandatory review.

`loopx issue-fix reviewer-request` consumes the same evidence after fetching
live PR metadata. The command must record a separate external-write decision,
exclude the live author and existing reviewers, and verify the provider state.
This recommendation schema must never be used as implicit review-request
authority. See [issue_fix_reviewer_request_v0](issue-fix-reviewer-request-v0.md).

## Planned Extensions

Future versions may add repository-native signals with real call sites:

- maintainer availability and explicit opt-out;
- review-response and approval history;
- automatic discovery of checked-in reviewer-source packets;
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
`CODEOWNERS`, most-specific maintainer-map routes, repository fallback, source
references, trust/freshness, exact-path history, module fallback, author
exclusion, CLI execution, identity handling, and the no-external-write
boundary.
