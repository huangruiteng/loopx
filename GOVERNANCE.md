# LoopX Project Governance

This document defines the public project roles and decision process for LoopX.
It governs the repository and its releases. It is separate from LoopX runtime
concepts such as agent peers, todo claims, quota, gates, and write scopes.

## Current Maintainer

| Person | Role | Since | Public evidence |
| --- | --- | --- | --- |
| [`@huangruiteng`](https://github.com/huangruiteng) | Creator and lead maintainer | 2026-05-31 | [Initial public commit](https://github.com/huangruiteng/loopx/commit/7dcdc9dc79226d157ba57d3e8ff4bae664f020c1) |

The lead maintainer is currently the final decision maker for releases,
maintainer appointments, security-sensitive handling, and changes to this
governance model. That tie-break role should be revisited when the active
maintainer group grows.

## Project Roles

### Maintainers

Maintainers may review and merge pull requests, publish releases, triage
security reports, and make repository governance decisions. They are expected
to protect compatibility, the public/private boundary, contributor trust, and
the quality of LoopX's control-plane contracts.

Maintainer authority is explicit: it comes from this document and repository
permissions, not from commit count, a runtime todo claim, or an agent role.

### Contributors

Anyone who improves code, tests, documentation, design, issues, or reviews is a
contributor. Accepted commits and co-authored commits are credited through the
public Git history and GitHub contributor views. Contribution does not by
itself grant merge, release, or governance authority.

### Agents And Automation

Agents and automation may prepare changes, run validation, or appear in commit
provenance. They do not become human maintainers and cannot grant themselves
repository authority. A human maintainer remains accountable for merges,
releases, and boundary decisions.

## How Decisions Are Made

- Routine changes use pull-request review, focused validation, and maintainer
  judgment. Silence is not approval when a change requires an explicit gate.
- Changes to persisted state, public contracts, defaults, permissions,
  evidence policy, or compatibility should explain the behavioral impact and
  include proportionate regression coverage.
- Significant product or governance changes should be discussed in a public
  issue or pull request before they are finalized.
- Security reports, credentials, private evidence, and other sensitive matters
  must not be posted in a public issue. Ask a maintainer for a private contact
  path without including the sensitive details.
- Releases are cut by a maintainer after the documented release checks pass.
  Exceptions and known skips should be recorded in the release or pull request.
- When consensus is not reached, the lead maintainer records the decision and
  rationale in the relevant issue or pull request.

## Becoming A Maintainer

Maintainers are selected from contributors who have shown sustained technical
judgment, reliable review, respect for project boundaries, and care for other
contributors. An active maintainer nominates the candidate; the active
maintainers approve the appointment; and the change is recorded here through a
pull request.

A maintainer may step down at any time. Inactive or emeritus status, when
needed, should likewise be recorded in this file rather than inferred from
recent commit activity.

## Accountability And Scope

Important decisions should leave durable public rationale in an issue, pull
request, release, or stable project document. Private incident details and raw
agent trajectories do not belong in that public record.

This charter does not create a legal entity, employment relationship,
copyright assignment, or trademark registration. See [AUTHORS.md](AUTHORS.md)
for attribution, [TRADEMARKS.md](TRADEMARKS.md) for name and mark usage, and
[CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow.
