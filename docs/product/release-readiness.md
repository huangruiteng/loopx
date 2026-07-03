# Release Readiness

Status: v0.x maintainer contract.

LoopX can move quickly without making every merged PR feel like a product
release. This note defines the small mental model maintainers should use before
promoting a release snapshot, recommending an install path, or telling users
which control-plane surfaces are safe to build on.

## Supported Install And Update Paths

For a first-time user, prefer the no-clone archive installer:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

The installer and `loopx update` use the public `stable` ref by default. Use
`LOOPX_REF=main` or `loopx update --ref main` only for maintainer/dev repair
when you intentionally want the current repository head instead of the stable
channel.

For a user who already installed from the archive, update through the explicit
CLI flow:

```bash
loopx update --check
loopx update --dry-run
loopx update --execute
loopx doctor
```

Re-running the curl installer remains a repair/fallback path when the wrapper
or local release snapshot is broken. It is not the primary update path for a
healthy archive install.

For contributors, keep the clone-plus-canary path:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
loopx doctor
loopx-canary doctor
```

The no-clone path is the user default. The clone-plus-canary path is the
maintainer validation path.

Before promoting a stable install/update recommendation, maintainers must move
the public `stable` ref to the release commit that passed this gate. Do not
claim stable-channel readiness while `stable` is missing or stale.

## Named Version Contract

LoopX v0.x is distributed from GitHub, but each stable promotion still needs a
package version name. The version source is `loopx.__version__`, mirrored by
`pyproject.toml`; the expected public tag is `vX.Y.Z` for that version.

Before moving `stable`, maintainers should:

- bump `loopx.__version__` and `pyproject.toml` together when user-visible
  release behavior changes;
- create or verify the matching Git tag, for example `v0.1.3`;
- fast-forward `stable` to that tagged commit after the release canary passes;
- confirm `release.json`, `loopx doctor`, and `loopx update --check` report the
  same package version and tag;
- tell existing users to run `loopx update --check`, then
  `loopx update --execute` when the check recommends or when they want to
  refresh to the named stable release.

This is a lightweight GitHub release contract, not a PyPI publishing
requirement. A future package registry can reuse the same version/tag contract
instead of inventing a second release identity.

## Public Release Timeline

The public GitHub release timeline starts at `v0.1.3`. Earlier work should be
treated as pre-public bootstrap for the local control plane, installer, update
path, and canary route rather than as a user-facing release baseline.

- `v0.1.3` on 2026-07-02 14:45 +08:00: initial public stable-channel release
  at commit `10509b06`. This release made LoopX explainable as a no-clone,
  local-first control plane for long-running AI agents: install, update,
  doctor, named version reporting, and the first public status/quota/todo/gate
  surfaces were ready to recommend together.
- `v0.1.4` on 2026-07-03 00:24 +08:00: fast-follow release at commit
  `07d0a753`. This release tightened product-capability monitor projection,
  release-readiness checks, and canary evidence so the first public baseline
  was easier to diagnose and refresh.
- `v0.1.5` on 2026-07-03 13:28 +08:00: long-horizon execution hardening at
  commit `c036d60e`. This release improved quota/status/runtime routing,
  monitor and scheduler projection, release packaging coverage, and
  outcome-floor recovery for stuck or low-progress loops.

When a new public release is promoted, add it here only after the matching tag,
release note, stable ref, update path, and focused release canary agree.

## Compatibility Gate

Before a release snapshot is promoted or a public guide tells users to depend
on a new surface, run the smallest gate that covers the touched surface:

```bash
python3 -m py_compile loopx/*.py
python3 examples/release/codex-cli-no-clone-release-verification-smoke.py
python3 examples/fresh-clone-quickstart-smoke.py
python3 examples/loopx-update-smoke.py
python3 examples/release/release-version-contract-smoke.py
python3 examples/release/release-readiness-doc-smoke.py
git diff --check
loopx check --scan-path README.md --scan-path docs/ --scan-path examples/
```

This is not a universal full suite. Add focused smokes for the changed command,
projection, or workflow. Do not require benchmark raw logs, raw task text,
trajectories, verifier output, credentials, or local private artifact paths as
release evidence.

## Canary Model

A release canary is a catalog-informed readiness slice. It is near-E2E in the
sense that it follows a real promotion or operator path across several seams,
but it is intentionally smaller than a full end-to-end test suite. Its job is
to answer "can the touched public surfaces be promoted under this declared
boundary?" rather than "is every LoopX path correct?"

Choose the canary group from existing interaction pattern families; do not add
new IPs solely to describe a validation bundle:

- status/quota/scheduler changes should include Work Routing checks such as
  `quota should-run`, scheduler hints, and hot-path interface budget;
- state projection or public/private changes should include State And Boundary
  checks such as `loopx check`, task graph or todo detail cold-path contracts;
- dashboard/frontstage changes should include catalog or fixture route checks,
  with browser smokes only when the visual surface itself is being promoted;
- release/install changes should include installer, update, wrapper, doctor,
  and public-boundary checks;
- benchmark or external-evidence changes should use compact lifecycle
  evidence only, never raw task text, raw logs, trajectories, or verifier tails.

The default promotion canary is:

```bash
python3 examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence
```

The default dashboard policy is `--dashboard-mode=auto`: source checkouts run
dashboard demo-readiness when `apps/dashboard` is present, while installed
release snapshots that omit the dashboard app skip that optional surface and
keep the omission visible in the canary output. Use `--dashboard-mode=require`
when the dashboard/frontstage itself is being promoted, and
`--dashboard-mode=skip` only when the release boundary intentionally excludes
the dashboard app.

Use the writeback form only when you intentionally want to append fresh
promotion-readiness evidence:

```bash
python3 examples/canary/canary-promotion-readiness-smoke.py
```

For broader source-checkout regressions, keep `loopx canary smoke-suite` as the
source of truth. Local and LoopX automation should continue to use the runner
payload directly:

```bash
python3 examples/run-smokes.py --suite default-public --module canary
loopx canary smoke-suite --suite default-public --module canary
```

CI may wrap the same runner selection in pytest when JUnit reporting is useful.
The pytest facade still executes each `examples/**/*-smoke.py` through a
subprocess; it is not a migration of legacy smokes into pytest unit tests:

```bash
python3 -m pytest tests/test_smoke_suite.py \
  --loopx-smoke-suite default-public \
  --loopx-smoke-module canary \
  --junitxml smoke-suite.xml
```

If the source checkout has optional frontend dependencies installed, dashboard
readiness can be included in the same canary. If a release snapshot omits the
dashboard app, the canary should degrade gracefully and record that boundary
rather than failing unrelated CLI/install promotion or silently treating the
dashboard path as covered.

## What Is Safe To Depend On

Treat these v0.x surfaces as stable enough for user guides, examples, and
host integrations when their focused smokes pass:

- `loopx doctor`, `loopx update`, `loopx check`, and the no-clone installer;
- project lifecycle commands: `bootstrap`, `connect`, `status`,
  `refresh-state`, `registry`, and `sync-global`;
- todo lifecycle commands: `todo add`, `todo claim`, `todo update`,
  `todo complete`, `todo list`, `todo supersede`, and `todo archive`;
- control-plane read paths: `quota should-run`, `quota spend-slot`,
  `review-packet`, `heartbeat-prompt --thin`, task graph projection, and cold
  todo detail references;
- public slash command names: `/loopx`, `/loopx <goal>`,
  `/loopx-global-summary`, `/loopx-global-gates`, `/loopx-global-todos`, and
  `/loopx-global-risks`;
- ignored local state boundaries under `~/.codex/loopx`, project-local registry
  files, and project-local active-state workbench files recognized by
  `loopx doctor`, `loopx status`, and `loopx check`.

Treat these as experimental until their contract docs say otherwise:

- benchmark runner behavior, scoring, upload, and raw task execution routes;
- host-plugin command registry implementations beyond the published protocol
  contract;
- frontstage/dashboard presentation details that are not part of the public
  status data contract;
- monitor scheduler cadence fields while they are still rolling out across
  todo creation, quota projection, writeback, and migration.

## Release Note Checklist

Every public release note or update note should answer:

- What user-visible capability became more dependable?
- What package version and public tag name this stable release uses?
- Which install/update path should a new user follow?
- Which commands, docs, or smokes prove the claim?
- Are there compatibility or migration notes for existing local state?
- Which surfaces are still experimental or intentionally excluded?
- Did the public/private scan run on the changed docs, examples, and workflow
  files?

The note should link to durable docs or PRs when useful, but public git history
and shipped CLI behavior remain the source of truth.

## Related Docs

- [Codex CLI packaged install path](codex-cli-packaged-install.md)
- [Codex CLI no-clone release verification](codex-cli-no-clone-release-verification.md)
- [Getting started](../guides/getting-started.md)
- [Update notes](../update-notes/README.md)
- [Public/private boundary](../public-private-boundary.md)
- [Interaction pattern catalog](../interaction-pattern-catalog.md)
