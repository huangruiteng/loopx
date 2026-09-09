# Contributing To LoopX

You want to help improve LoopX? Great, and thank you. Contributions come in
many shapes, and not all of them are code:

- filing clear bug reports with reproduction steps;
- triaging and reproducing issues;
- improving documentation, examples, and smoke tests;
- answering questions in issues or discussions;
- reviewing pull requests and helping contributors navigate the review flow;
- following the [Code of Conduct](CODE_OF_CONDUCT.md);
- implementing a public task or fixing a bug.

Every one of these helps. The rest of this guide covers finding work, keeping
public/private boundaries intact, validating changes, and getting a pull
request merged.

The best code contributions are small, reviewable, and tied to a public task
or a clear bug.

## Code Of Conduct

Everyone participating in LoopX community spaces, including maintainers and
contributors, is expected to follow the
[Contributor Covenant](CODE_OF_CONDUCT.md). Reports of unacceptable behavior
can be sent to huangrt01@163.com; maintainers review every report promptly and
keep the reporter's identity confidential to the extent possible.

## Find Work

Start with the [current technical directions](docs/project/technical-directions.md)
to understand the active programs and their maturity, then use
[docs/development/contributor-tasks.md](docs/development/contributor-tasks.md) to find public work that is useful,
claimable, and safe to discuss in the repository.

If you do not see a matching task:

1. open a GitHub issue with the contributor task template;
2. explain the problem, proposed scope, touched files, and validation command;
3. wait for maintainer feedback before starting large or behavior-changing
   work.

Small docs typo fixes and obviously safe cleanups can go straight to a pull
request.

## Public And Private Boundaries

LoopX coordinates local agent state, so some files are runtime data and
must stay out of public contributions:

- do not commit `.loopx/`, `.codex/goals/`, or live
  `ACTIVE_GOAL_STATE.md` files;
- do not publish private benchmark traces, verifier output, raw agent sessions,
  credentials, internal document links, or local machine paths;
- do not run or duplicate maintainer-owned benchmark cases unless a maintainer
  has split out a public issue for that work.

Safe contribution surfaces include docs, examples, smoke tests, CLI diagnostics,
schema docs, dashboard UI code, and sanitized fixtures.

Run the public/private scan before sending docs or examples:

```bash
loopx check \
  --scan-path README.md \
  --scan-path CONTRIBUTING.md \
  --scan-path docs/development/contributor-tasks.md \
  --scan-path docs/ \
  --scan-path examples/
```

## Local Development

Use the [developer guide](docs/development/README.md) as the stable entry point.
Before changing scheduler, quota, todo/gate, onboarding, agent-facing output,
or release behavior, read the bilingual
[testing and quality guide](docs/development/testing-and-quality.md).
Before adding or consolidating a public smoke, use the bilingual
[good smoke guide](docs/development/good-smokes.md) to define its durable
invariant, independent oracle, cadence, and public-safe fixture boundary.

Install and verify the checkout:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
loopx demo
```

Common focused checks:

```bash
python -m pip install -e ".[test]"
python -m ruff check tests loopx/canary loopx/control_plane loopx/domain_packs loopx/presentation
python -m mypy
python examples/control_plane/cli-output-budget-regression-smoke.py
python -m pytest -q
loopx canary premerge --from-git-diff
loopx check --scan-path loopx/ --scan-path tests/ --scan-path examples/ --scan-path docs/
git diff --check
```

Choose focused smokes and broader canaries by change risk; do not run every
public smoke or a live model call for every patch. The quality guide explains
the CI, local/manual, and release-only boundaries.

## License And DCO Sign-Off

LoopX's unified open source core is licensed under the
[Apache License 2.0](LICENSE). Unless you explicitly state otherwise before
submission, contributions accepted into this repository are submitted under
Apache-2.0 without additional terms or conditions. LoopX does not require a
copyright assignment or contributor license agreement.

Every pull-request commit must certify the
[Developer Certificate of Origin 1.1](DCO) by including a sign-off trailer:

```text
Signed-off-by: Your Name <your.email@example.com>
```

Create that trailer with Git's `-s` option:

```bash
git commit -s -m "feat: describe the change"
```

The name and email must identify the person making the certification and must
be information you are permitted to publish in the permanent Git history. If a
commit is missing the trailer, amend it with `git commit --amend -s` or use an
interactive rebase to sign the affected commits, then update the pull-request
branch. The `DCO` pull-request check rejects unsigned commits.

Releases through `v0.4.7` remain under their original MIT terms. See the
[licensing and v0.4.8 transition policy](docs/project/licensing.md) for the
historical notice, patent-grant boundary, and open-core scope.

## Experimental Features

Use `loopx/experiments/<experiment-id>/` for an opt-in prototype that does not
yet have a stable caller contract or participate in LoopX's default lifecycle.
Keep its tests, examples, and scripts under matching `experiments/` paths so
the prototype can be evaluated or removed as one unit. Core modules must not
import experimental packages. See the
[experiment placement and promotion policy](loopx/experiments/README.md).

## Host Loops And LoopX Turn

Treat LoopX Turn and a long-running host loop as separate layers:

- `loopx turn run-once` is one atomic governed transaction. It may decide,
  invoke one bounded host segment, validate independently, write back, spend
  once, and project the latest scheduler phase.
- A Turn Loop Controller is an outer runtime owner. It decides when to wake,
  invokes `run-once`, consumes the typed result, applies the shared
  `scheduler_hint`, and either waits, routes a user action, repairs, replans,
  continues, or stops.
- A host adapter translates one typed request and result. It owns the opaque
  host session and tools, but it does not own LoopX state, quota, completion,
  validation, scheduler policy, or replan policy.

Do not add a sleep loop, cron implementation, recurring daemon, operator
notification path, or multi-Turn replan loop inside `run-once`. Do not copy
Codex App heartbeat prompt rules into a second scheduler. Reuse the existing
interaction, scheduler, autonomous-replan, todo, and TurnEnvelope contracts;
only the runtime-specific act of applying a wakeup belongs in a scheduler
adapter.

A `replan_required` result is not permission to invoke the same todo again. A
controller must first record a bounded todo or vision delta, obtain a fresh
TurnEnvelope, and preserve the causal `(goal_id, agent_id, todo_id)` frontier.
An opaque resumable host session is recovery metadata, not authority to bypass
that decision.

Stage host-loop contributions in reviewable slices:

1. characterize current Codex App and Turn behavior with independently derived
   fixtures;
2. add a pure next-disposition decision table with no host or state effects;
3. add one scheduler-owner adapter with a fake clock and fake host;
4. add runtime-specific wakeup, notification, or presentation only after the
   shared transition contract is stable.

For every controller or host-loop change, prove:

- scheduler owner, host surface, and execution mode are explicit and valid;
- `wait`, user action, monitor-only, and cadence-only paths make no model call
  and spend no quota;
- material progress requires independent postcondition validation before
  durable writeback and spend;
- replay and interrupted-phase recovery are idempotent;
- repair and replan remain distinct, and replan produces a fresh frontier
  before another Turn; and
- fixtures contain no raw prompts, transcripts, credentials, private state, or
  host-local paths.

See the [LoopX Turn protocol](docs/reference/protocols/loopx-turn-v0.md) and the
[Contributor Task Board](docs/development/contributor-tasks.md) for the staged controller plan.

## Governance And Attribution

Repository roles and decision authority are defined in
[Governance](.github/GOVERNANCE.md). Creator and contributor attribution is
recorded in [docs/project/authors.md](docs/project/authors.md), while path-scoped maintenance and
preferred review assignments are recorded in the same governance document.
The public Git history records individual contributions. Contribution does not
automatically grant merge or release authority, and an agent or automation
identity is not a human maintainer.

When naming or packaging a fork, integration, or hosted service, follow the
project's [name and marks guidance](docs/project/trademarks.md).

For dashboard changes:

```bash
cd apps/presentation/dashboard
npm install
npm run build
npm run smoke:demo-readiness
```

## Claiming A Task

- Comment on the issue before starting non-trivial work.
- If a maintainer marks it `claimed` or assigns it to you, keep the scope close
  to the issue.
- If you get stuck, comment with the blocker and what you already tried.
- If you need to change the scope, ask first.
- If there is no update for 14 days, maintainers may release the task so
  someone else can pick it up.

## Pull Request Checklist

Before opening a pull request:

- link the issue or task ID when one exists;
- describe the behavior change and the validation you ran;
- keep unrelated formatting or refactors out of the PR;
- include docs or tests when changing user-visible behavior;
- confirm that no private/local runtime state was committed.

Maintainers may ask for a smaller PR if the change mixes unrelated concerns.

### Validation disclosure

Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md) to report facts, not a
self-assessed quality grade. The enum values are author declarations, not an
automated proof or merge gate. `finished` means execution ended, not that all
checks passed or that coverage is sufficient. Record the tested commit; after
changes, rerun affected checks or identify the stale evidence and remaining gap.

Use one row per relevant check, including failures, skips (`not_run`), blocked
checks and work still running. Static checks do not prove runtime behavior;
unit/mocked tests do not prove the public entrypoint or a real backend. State
the behavior checked and why the set covers the changed paths. Refactors need
the real-path and parity evidence required by the
[testing guide](docs/development/testing-and-quality.md#refactor-real-path-gate--重构真实路径门).
Small documentation changes can report a link/render/static check and explain
why runtime testing is not applicable; do not launch unrelated suites to fill rows.

Keep evidence public-safe at the point of entry, including hidden HTML comments
and attachments. Report repository-relative test commands, public fixture names,
aggregate outcomes, backend product/version and isolation mode, or public CI links.
Do not copy commands containing private arguments, raw logs, snapshots, prompts,
private screenshots, infrastructure addresses, connection strings, local paths or
credentials. `authorized_private_read_only` discloses only a data category: it
neither grants permission to access live state nor requires publishing its content,
identifiers or fingerprints. When evidence cannot be shared, describe the tested
behavior and verification limitation; public reproducibility remains an explicit
gap until a safe reproducer or authorized review is available. Never upload private
evidence to make a checkbox green.
