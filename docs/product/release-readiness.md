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

## Merged Is Not Runtime-Active

A post-merge check proves behavior on the tested source commit. It does not
prove that an installed LoopX runtime contains that commit. This distinction
matters when a fix reaches `main` after the latest named release: package
versions may still match while the installed source commit is behind.

Use `loopx update --check --ref main` for maintainer qualification. Its
`runtime_activation_qualification` result compares the release-manifest source
commit with the trusted source lineage reported by `loopx doctor`:

- `runtime_active` means the installed commit is the target commit or contains it;
- `release_or_install_successor_required` means the installed commit is behind
  or diverged, so a release/install successor must remain explicit;
- `activation_qualification_required` means commit lineage is unavailable or
  belongs to a different `repo/ref`; the runtime-active claim must fail closed
  until identity is refreshed.

Closing a PR monitor after latest-`main` validation is valid, but the closeout
must not say the fix is active in the installed runtime unless this receipt is
`runtime_active`. Publishing a release remains a separate maintainer action.
When the qualification command itself runs from newer source code, pass a local
snapshot from the older installed CLI with `--installed-doctor-json`; this
option is read-only and accepted only by `update --check`.

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
- `v0.1.6` on 2026-07-03 17:07 +08:00: visible multi-agent startup hardening
  at commit `1e3df9df`. This release made auto-research startup easier to see
  and trigger, clarified decentralized pane routing, tightened monitor and
  scheduler projection, and expanded the Codex CLI first-run release checks.
- `v0.1.7` on 2026-07-04 12:52 +08:00: command-entry integration release at
  the matching `v0.1.7` tag. This release made the supported entry layer
  explicit: Codex installs LoopX command-facade skills such as `$loopx`, Claude
  Code gets matching skill entries, legacy prompt shims are retired, and the
  rich workflow skills remain available for implicit LoopX behavior.
- `v0.1.8` on 2026-07-04 16:53 +08:00: deterministic host-loop activation
  release at the matching `v0.1.8` tag. This release gives new agent hosts an explicit
  `agent-onboard` contract for choosing `codex-app`, `codex-cli`,
  `claude-code`, `opencode`, `manual`, or `other-agent`, rejects ambiguous inputs such as
  `codex`, and makes `/loopx <task>` activate or gate the correct host loop
  after todo writeback.
- `v0.1.9` on 2026-07-05 21:45 +08:00: real auto-research and agent-scoped
  evidence release at the matching `v0.1.9` tag. This release removes fake
  auto-research demo metrics, makes the KNN preset use a real benchmark
  workspace with public-safe evidence writeback, exposes role-named visible
  research panes, wires agent-scoped evidence read hints into replan, and
  hardens successor/frontier recovery when completed advancement has no next
  executable todo.
- `v0.1.10` on 2026-07-06 11:50 +08:00: scoped user-gate and agent-management
  release at the matching `v0.1.10` tag. This release makes blocking owner
  todos explicitly typed as `user_gate` or non-blocking `user_action`, scopes
  per-agent gates with `blocks_agent`, adds read-only live agent-management
  status projections, and continues moving quota, todo, scheduler, review
  packet, and handoff rules into bounded control-plane contexts with focused
  canary coverage.
- `v0.1.11` on 2026-07-06 19:38 +08:00: vision-replan and recovery-routing
  release at the matching `v0.1.11` tag. This release makes goal-vision gaps
  participate in the quota/replan decision plane, preserves continuation audits
  in quota and interaction contracts, supersedes stale vision checkpoint gaps
  when newer evidence closes them, and adds judge guidance for when a vision
  gap is real work versus stale state. It also promotes the latest control-plane
  bounded-context cleanup, auto-research successor/evidence fixes, connector
  source-map packets, structured run-index classification, and Codex CLI/TUI
  recovery fixes.
- `v0.1.12` on 2026-07-08 02:05 +08:00: presentation/read-model and frontier
  recovery release at the matching `v0.1.12` tag. This release moves large
  status, goal-channel, dashboard, and Lark rendering paths into bounded
  presentation/read-model modules, fixes monitor-only plus open-vision frontier
  replan gaps, makes installer reruns overwrite stale wrappers/files safely,
  exposes premerge canary progress earlier, and promotes auto-research visible
  worker/successor routing plus selected public benchmark route/profile and
  SkillsBench helper hardening.
- `v0.1.13` on 2026-07-08 18:15 +08:00: guided onboarding and multi-agent
  control-plane release at the matching `v0.1.13` tag. This release makes new
  project setup more repairable with guided start-goal previews (#1631, #1633),
  non-destructive write-scope migration (#1636), delivery-scale aliases, and
  clearer refresh-state diagnostics (#1641); routes primary controllers toward
  subagent orchestration (#1622) behind an explicit default-off feature switch
  (#1643); improves scheduler ACK/backoff recovery and heartbeat migration
  (#1626, #1639); splits quota/status fixture hot paths, Lark projection row
  helpers, and content-ops markdown renderers into narrower modules (#1640,
  #1642, #1644, #1646); adds public-safe external ML task ledgers (#1627);
  hardens SkillsBench source/countability/launcher evidence (#1612, #1620,
  #1621, #1625); and relaxes local `next_action` / `recommended_action` text to
  allow local project routing references while still rejecting inline
  credentials (#1645).
- `v0.1.14` on 2026-07-09 11:49 +08:00: developer-contributed exploration
  topology and monitor/quota recovery release at the matching `v0.1.14` tag.
  This release promotes the software exploration result layer (#1546): public
  explore node/edge/finding records, Lark presentation mapping, graph exports,
  router/load-profile planning primitives, and deny-by-default
  `explore_harness` worker/todo branch planners gated by each goal's
  `spawn_policy`. It also ships the monitor scheduler cadence repairs that
  keep quiet monitor polls from collapsing back to short intervals (#1699 and
  related scheduler fixes), plus quota/status/todo read-model hardening for
  user-gate counts, completed-todo successors, evidence-log counts, delivery
  lineage, and compact agent-lane status summaries (#1707-#1716).
- `v0.1.15` on 2026-07-10: actionable routing and long-run reliability release
  at the matching `v0.1.15` tag. This release makes the agent-facing current
  action and quota-selected todo more explicit, centralizes primary-action
  resolution, and preserves replan acknowledgements, filtered resumes, vision
  lifecycle state, and due monitors across bounded progress (#1720, #1731,
  #1751, #1757, #1764-#1766, #1769-#1770). It hardens external monitor and
  multi-agent continuation through quiet-timeout handling, identity/capability
  gates, no-handoff lane fidelity, and typed continuation policies (#1722-#1724,
  #1745, #1747, #1754, #1773). Experimental issue-fix and SkillsBench routes
  gain feasibility, lifecycle, evidence, failure-attribution, cache/proxy,
  prewarm, and ledger-closeout improvements (#1726, #1734, #1738-#1744,
  #1748-#1750, #1753, #1756, #1759-#1763, #1767-#1768, #1771-#1772). The
  release also adds and repairs the parallel full-public smoke sweep, fixes
  direct-install doctor behavior, clarifies Explore's measurable-metric fit,
  and closes the todo CLI ownership-budget regression (#1721, #1725, #1727-#1730,
  #1735, #1743, #1752, #1774).
- `v0.1.16` on 2026-07-10: archive-install provenance hotfix at the matching
  `v0.1.16` tag. This release isolates release-manifest generation from the
  caller's working directory and inherited Python path, so running an update
  from an older LoopX checkout cannot stamp that checkout's package version
  into the new stable snapshot. The no-clone release gate now covers this
  stale-checkout invocation directly (#1776). No product capability or state
  migration changes in this hotfix.
- `v0.2.0` on 2026-07-11: peer-agent runtime and issue-fix control-plane
  release at the matching `v0.2.0` tag. This release completes the v0.2
  runtime cutover from hierarchical agent ownership toward equal peer agents:
  task claims are soft routing signals, independent handoff uses
  `continuation_policy=independent_handoff` plus `excluded_agents`, and stale
  legacy review continuation paths are rejected or migrated. It also promotes
  the issue-fix capability from feasibility planning into a fuller public
  maintainer loop with caller-repo branch preparation, acceptance artifacts,
  reviewer request fallback, PR lifecycle observation, and domain-state
  writeback. Explore Harness and long-run benchmark projections gain stronger
  public result contracts, while install/update, release provenance, quota,
  todo, scheduler, and protocol-action smokes were swept under the full-public
  suite for the 0.2 release cut.
- `v0.2.1` on 2026-07-12: agent-facing quality and long-run reliability
  fast-follow at the matching `v0.2.1` tag. This release makes bounded turn
  context explicit through TurnEnvelope contracts, adds trajectory-hygiene
  and packet-duplication measurements, and preserves action contracts while
  trimming repeated hot-path material. Issue-Fix gains repository snapshots,
  decision-useful memory, Explore projection, reviewer/CI receipts, impact
  metrics, and guarded promotion of newly discovered public defects. Optional
  Explore planning now preserves independent experiment lanes and supports
  resource-aware portfolio decisions. Peer routing is hardened across task
  lease validity, advisory agent profiles, deferred successor exclusions, and
  non-blocking user actions. The repository also establishes parallel pytest,
  Ruff, strict typing, import-boundary, coverage-floor, and release-promotion
  concurrency checks so these broader capabilities remain maintainable.
- `v0.2.2` on 2026-07-12: visible execution and projection reliability
  fast-follow at the matching `v0.2.2` tag. Explore gains recoverable execution
  episodes and ReplayPoint-based counterfactual branches, plus an optional
  owner-facing visual sink and real graph examples in the public entry
  surfaces (#1892, #1962, #1965-#1966, #1971). Visible multi-agent runs now
  wake only lanes whose runnable state changed and freeze the newest compatible
  host Codex CLI before launch (#1967, #1973). Diagnose capability projection,
  terminal PR-gate reconciliation, and vision replanning under monitor load are
  repaired (#1963-#1964, #1969). Benchmark comparison, report, learning-ledger,
  and result read models move into their control-plane runtime owner while
  preserving compatibility imports and restoring the full-public smoke shard
  (#1961, #1968, #1970, #1972). No persisted-state migration is required;
  Explore execution and visual sinks remain explicit opt-ins.
- `v0.2.3` on 2026-07-13: control-plane truthfulness and maintainer-surface
  release at the matching `v0.2.3` tag. LoopX adds a provider-neutral
  model-behavior qualification contract with public-safe corpus and decision
  receipts plus an optional direct provider actor (#1994, #1998-#1999, #2001,
  #2003). Optional capability discovery and the Lark event inbox/collector
  become clearer product surfaces without adding mandatory first-run
  configuration (#1978, #1986, #1997, #2000). Monitor, todo, quota, and vision
  routing now preserve capabilities and attribution, prefer advancement over
  stale monitor pressure, keep future waits quiet, and correlate material
  transition receipts (#1989-#1993, #2008, #2011, #2013-#2015). Explore graph
  activation now respects run-scoped sink authority (#1995, #2016), while
  deterministic update notes and project governance make the public repository
  easier to maintain (#1983, #1996, #2012). No persisted-state migration is
  required; optional provider, Lark, semantic-preference, and Explore surfaces
  remain opt-in.
- `v0.2.4` on 2026-07-14: Explore presentation and delivery-reliability
  release at the matching `v0.2.4` tag. Explore board layout is now a
  first-class `board_style` product parameter with two supported values:
  `auto_flow` uses Mermaid's automatic graph layout for topology-oriented
  views, while `semantic_lane_columns` emits deterministic stage SVGs for
  operator boards with meaningful parallel lanes (#2062). The Lark visual
  sink can publish one managed board per evidence stage, project the selected
  style into every stage, keep labels inside lane nodes, retry eventual visual
  readback, and reconcile generated document sections so stale or duplicate
  stages do not accumulate (#2051, #2063, #2065-#2066, #2068). The same
  canonical Explore result graph remains authoritative for both styles, and
  existing Mermaid-only configs continue to resolve as `auto_flow`. This
  release also includes same-source canonical/executive views, explicit
  issue-fix semantic-preference call sites, provider diagnostics, and further
  monitor, scheduler, installer, onboarding, and public-smoke hardening
  (#2002, #2005-#2006, #2018-#2021, #2027-#2028, #2032, #2036, #2052-#2061).
  No persisted-state migration is required; Explore and its Lark visual sinks
  remain opt-in.
- `v0.2.5` on 2026-07-15: reward-memory and cross-runtime reliability release
  at the matching `v0.2.5` tag. LoopX now ships a provider-neutral Reward
  Memory path from reviewed corpus and health contracts through candidate
  review, opt-in recall/application, evaluation, dogfood controls, and explicit
  actor-peer routing at the Issue-Fix planning boundary (#2076-#2085, #2096,
  #2100, #2103, #2128). Runtime projection routes become a first-class source
  of truth for material events, refreshes, and Explore commands across shared
  runtimes, with source-mirror ambiguity and compact diagnostics repaired
  (#2091, #2094, #2097, #2099, #2102, #2129). Issue-Fix gains stronger commit
  evidence, evidence-backed close counts, candidate dedupe, reviewer fallback,
  and delivery-window queuing (#2071, #2087, #2098, #2105, #2107, #2111).
  Monitor, scheduler, peer-replan, Lark inbox, Explore readback, and long-running
  SkillsBench paths are hardened against repeated host failures, scoped gates,
  transport loss, setup drift, and countability ambiguity (#2101, #2104,
  #2108-#2127, #2130-#2131). No persisted-state migration is required; Reward
  Memory and advanced fixer execution remain explicitly activated and bounded.
- `v0.2.6` on 2026-07-16: typed interaction authority and isolated Turn runtime
  release at the matching `v0.2.6` tag. Scheduler decisions now follow the
  typed interaction contract, exact blocked successors can trigger bounded
  autonomous replanning, and user gates no longer deadlock unrelated agent
  lanes ([#2136](https://github.com/huangruiteng/loopx/pull/2136),
  [#2177](https://github.com/huangruiteng/loopx/pull/2177),
  [#2187](https://github.com/huangruiteng/loopx/pull/2187),
  [#2188](https://github.com/huangruiteng/loopx/pull/2188),
  [#2198](https://github.com/huangruiteng/loopx/pull/2198),
  [#2203](https://github.com/huangruiteng/loopx/pull/2203),
  [#2204](https://github.com/huangruiteng/loopx/pull/2204)). LoopX Turn becomes
  a shipped isolated-headless route with executable envelopes, session
  recovery, independent validation, real CLI qualification, and a SkillsBench
  integration ([#2158](https://github.com/huangruiteng/loopx/pull/2158),
  [#2166](https://github.com/huangruiteng/loopx/pull/2166),
  [#2169](https://github.com/huangruiteng/loopx/pull/2169),
  [#2171](https://github.com/huangruiteng/loopx/pull/2171),
  [#2173](https://github.com/huangruiteng/loopx/pull/2173),
  [#2193](https://github.com/huangruiteng/loopx/pull/2193),
  [#2199](https://github.com/huangruiteng/loopx/pull/2199),
  [#2202](https://github.com/huangruiteng/loopx/pull/2202)). New-user
  onboarding is protected by deterministic lifecycle canaries and repeated
  one-arm Doubao qualification of the actual default packet, while CLI output
  budgets and release outcome contracts make semantic regressions visible
  before promotion ([#2144](https://github.com/huangruiteng/loopx/pull/2144),
  [#2148](https://github.com/huangruiteng/loopx/pull/2148),
  [#2153](https://github.com/huangruiteng/loopx/pull/2153),
  [#2157](https://github.com/huangruiteng/loopx/pull/2157),
  [#2159](https://github.com/huangruiteng/loopx/pull/2159),
  [#2167](https://github.com/huangruiteng/loopx/pull/2167),
  [#2168](https://github.com/huangruiteng/loopx/pull/2168),
  [#2201](https://github.com/huangruiteng/loopx/pull/2201)). Explore source
  reconciliation, optional Reward Memory experiments and reviewer gates, and
  Lark delivery are also hardened without making them first-run requirements
  ([#2200](https://github.com/huangruiteng/loopx/pull/2200)). No persisted-state
  migration is required; advanced capabilities remain explicitly activated.

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

After the individual lanes pass, bind their compact receipts to the exact clean
release checkout before tagging or moving `stable`:

```bash
loopx canary release-qualification \
  --manifest-json release-qualification.json \
  --repo-root .
```

The `exact_release_commit_qualification_manifest_v0` contract requires the
same Git commit, Git tree id, package version, and version tag across pytest,
Ruff, mypy, risk-based canary, full-public, install/upgrade/host,
public-boundary, and actual-default one-arm Doubao receipts. The command also
checks the current checkout and rejects dirty or rebased source. It only
reduces existing bounded receipts: it does not execute tests, call a provider,
move refs, create tags, or publish a release.

Matched stable/candidate outcome evidence is required only when the release
claims benchmark or long-horizon outcome uplift. A normal release without that
claim must record the pair as not required, not keep a retired second product
arm alive or imply that the expensive comparison ran.

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
dashboard demo-readiness when `apps/presentation/dashboard` is present, while installed
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

For larger source-checkout sweeps, use the runner's bounded parallelism instead
of moving smoke semantics into a second test framework. `--jobs` keeps the
LoopX runner payload as the source of truth while preserving serial execution
for smokes that declare a scheduling-sensitive surface:

```bash
python3 -m loopx.cli canary smoke-suite --profile public-smoke-watch --jobs 4 --timeout-seconds 60
python3 examples/run-smokes.py --suite full-public --jobs 4 --timeout-seconds 60
```

For repeatable canary/refactor batches, prefer named smoke-suite profiles over
hand-curated script lists. Profiles expand to the same runner payload as
`--module`, `--script`, catalog selectors, and the pytest facade:

```bash
loopx canary smoke-profiles
loopx canary smoke-suite --profile core-control-plane --no-execute
loopx canary smoke-suite --profile core-control-plane --offset 20 --limit 20 --timeout-seconds 60
loopx canary smoke-suite --profile canary-runner --timeout-seconds 60
python3 examples/run-smokes.py --profile public-entry-install-release --no-execute
```

Use `--offset` with `--limit` to sweep large profiles in stable windows without
rerunning the same prefix batch on every heartbeat.

Default `pytest` is the fast unit and contract lane. The smoke-suite facade is
explicitly opt-in so a normal PR test run does not silently expand into the
canary matrix. CI may wrap an explicit runner selection in pytest when JUnit
reporting is useful. The facade still executes each selected
`examples/**/*-smoke.py` through a subprocess; it is not a migration of legacy
smokes into pytest unit tests:

```bash
python3 -m pytest tests/test_smoke_suite.py \
  --loopx-smoke-suite default-public \
  --loopx-smoke-profile canary-runner \
  --loopx-smoke-offset 0 \
  --junitxml smoke-suite.xml
```

The required Python test workflow keeps `tests/**`, `canary/**`,
`control_plane/**`, `domain_packs/**`, and `presentation/**` Ruff-clean. It also
enforces an initial 19.6% package coverage floor.
The floor is intentionally a regression guard, not a claim that 19.6% is
sufficient; raise it as durable behavior moves from subprocess smokes into
focused tests. An architecture test also prevents new control-plane dependencies
on presentation, CLI, capability, or benchmark-adapter layers while preserving
one explicit quota-Markdown migration debt edge. Existing source-wide lint debt
is characterized separately. Strict mypy checking covers twelve characterized
kernel and runtime contracts and should expand only as each next boundary
becomes clean;
expand the protected namespace list only after a bounded cleanup, rather than
mass-fixing unrelated code merely to make a broad gate green.

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

Organize every public release note into the following stable groups. Omit an
empty group instead of inventing filler:

1. **State Kernel & Control Plane** for state, todo, quota, scheduler, gate,
   peer-routing, and runtime authority changes.
2. **Capabilities & Workflows** for shipped user workflows such as Issue-Fix,
   Explore, Reward Memory, onboarding, and LoopX Turn.
3. **Quality & Testing** for deterministic tests, canaries, output budgets,
   model-behavior qualification, and release gates.
4. **Benchmarks & Integrations** for benchmark adapters, Lark, host runtimes,
   and other external boundaries.
5. **Documentation & Compatibility** for public contracts, install/update
   guidance, migrations, defaults, and intentional exclusions.

Bilingual releases must preserve these same group boundaries in both
languages. Under `## 中文摘要`, use the matching headings **状态内核与控制面**,
**能力与工作流**, **质量与测试**, **基准与集成**, and **文档与兼容性**. The Chinese
copy may be shorter, but it must not collapse several groups into a generic
highlights list or omit a non-empty English group.

Within each non-empty group, every material claim must carry one or more direct
GitHub pull-request links such as
`[#2051](https://github.com/huangruiteng/loopx/pull/2051)`. A compare link is
still useful at the end, but it does not replace per-claim PR attribution.
Avoid bare PR ranges as the only evidence because ranges can hide omitted or
unrelated changes.

Every public release note or update note should also answer:

- What user-visible capability became more dependable?
- What package version and public tag name this stable release uses?
- Which install/update path should a new user follow?
- Which commands, docs, or smokes prove the claim?
- Are there compatibility or migration notes for existing local state?
- Which surfaces are still experimental or intentionally excluded?
- For every new or materially changed experimental, default-off, or opt-in
  capability, include an **Optional capability activation** entry in both
  languages: name its scope, read-only preview, exact enable and disable
  commands, prerequisites or safety gates, and canonical docs. If no persistent
  switch exists, say that opt-in is per command or preset instead.
- Did the public/private scan run on the changed docs, examples, and workflow
  files?
- Did full `pytest`, focused release/install contracts, risk-based canary, and
  promotion-readiness/public-boundary checks pass on the exact release commit?
- Did `loopx canary release-qualification` confirm that every required compact
  receipt matches the same clean commit, Git tree, package version, and tag?
- Did the low-frequency live model gate run against the actual default
  agent-facing packet with at least two repeats? Record the model id, behavior
  decisions checked, call count, failures, and skips, but never retain raw
  prompts, packets, responses, credentials, or local paths. This remains a
  local/manual release gate rather than ordinary CI.
- If the release claims benchmark or long-horizon outcome improvement, did a
  matched stable-versus-candidate outcome baseline pass? If no outcome claim is
  made, state that this expensive gate was not required rather than implying it
  ran.
- For Chinese-speaking operators, include a compact `## 中文摘要` section that
  mirrors the English group structure and material claims in neutral product
  language. Keep each group shorter than its English counterpart while
  preserving direct PR attribution and compatibility boundaries.

### Capability Narrative Gate

For every new or materially changed capability, write the release claim in
three explicit layers:

1. **User outcome**: say what a user can now accomplish in product language,
   before naming protocols, providers, renderers, or other implementation
   mechanisms.
2. **Shipped layer**: identify whether the release provides a control-plane or
   protocol kernel, a built-in adapter or presentation layer, or a complete
   end-to-end workflow. Name the commands, docs, or smokes that prove that
   layer.
3. **Last-mile boundary**: name any default profile, collector, scheduler,
   destination, credential setup, or publication step that is still absent or
   explicitly opt-in. Do not overclaim a complete workflow, but do not hide a
   shipped core behind mechanism-only wording either.

A built-in capability is not an optional extension merely because some of its
collectors, renderers, sinks, or providers are optional. Describe the built-in
outcome and its lifecycle separately from provider activation. When a release
ships successive layers of one outcome, such as a report kernel followed by an
HTML presentation layer, attribute and explain each layer instead of folding
both into a generic integrations bullet.

The Chinese summary must preserve the same user outcome, shipped layer, and
last-mile boundary. Translation may be shorter, but it must not replace the
user-facing outcome with architecture-only terminology.

The release PR and final GitHub release body must use the same grouping and
validation receipt. Re-run the gates after rebasing or merging any additional
runtime change; results from an earlier commit do not qualify a later tag.
Public git history and shipped CLI behavior remain the source of truth.

## Related Docs

- [Codex CLI packaged install path](codex-cli-packaged-install.md)
- [Codex CLI no-clone release verification](codex-cli-no-clone-release-verification.md)
- [Getting started](../guides/getting-started.md)
- [Update notes](../update-notes/README.md)
- [Public/private boundary](../public-private-boundary.md)
- [Interaction pattern catalog](../interaction-pattern-catalog.md)
