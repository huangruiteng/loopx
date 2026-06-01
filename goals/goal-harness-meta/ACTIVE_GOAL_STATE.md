---
status: active-read-only
owner_mode: goal
objective: "Keep the public Goal Harness repo runnable, understandable, and safe to reuse"
updated_at: 2026-06-02T06:47:35+08:00
---

# Goal Harness Meta Goal

## Objective

Keep the public Goal Harness project healthy enough that another local Codex
thread can bootstrap a goal, inspect registry and run history, check public
boundary safety, and render a first-screen status queue without relying on any
private project context.

## Current Scope

- Keep `scripts/install-local.sh`, `goal-harness bootstrap`,
  `goal-harness check`, `goal-harness status`, `goal-harness archive-runtime`,
  and `goal-harness serve-status` runnable from a fresh clone.
- Keep docs and examples aligned with the current CLI surface.
- Keep public examples sanitized: no local user paths, private documents,
  credentials, raw logs, or internal task identifiers.
- Treat project-specific adapters as private until their contract is generic
  enough to document publicly.

## Next Action

- Add a tiny quota-plan fixture for multi-project allocation: when several
  goals are eligible, the next automatic turn should choose the highest
  `quota.compute` goal, while operator-gated goals stay out of the eligible
  lane. Keep it fixture-only; do not append a real gate or run a real map.

## Recent Progress

- 2026-06-02T06:47:35+08:00: Extended `examples/project-prompt-smoke.py` so the
  actual CLI output path is covered, not only the Python prompt builder. The
  smoke now runs `python -m goal_harness.cli --format json new-project-prompt`
  and the default Markdown `new-project-prompt` output, then verifies both carry
  the quota guard rule: `should_run=false` means no implementation/adapter work
  and no `agent_command`; `should_run=true` plus `agent_command` is required
  before executing that command; otherwise follow `recommended_action` for the
  next safe read-only action. Validation: direct project-prompt smoke passed;
  aggregate public smokes passed with 3 scripts; Python compile passed; public
  contract check passed; `git diff --check` passed. Critic: project-agent prompt
  and CLI output are now guarded; the next P0 gap moves to multi-project
  allocation, where quota plan ordering should be protected by a small fixture.
- 2026-06-02T06:41:59+08:00: Added the project-agent quota guard rule to the
  new-project handoff prompt and public prompt contract. Project agents are now
  told that `quota should-run` is the compute gate: if `should_run=false`, skip
  implementation/adapter work and do not execute any `agent_command`; only when
  `should_run=true` and the payload contains `agent_command` should that command
  be executed; if `should_run=true` without a command, follow
  `recommended_action` for the next safe read-only action. Added
  `examples/project-prompt-smoke.py`, which verifies both the Python prompt
  builder and `docs/new-project-codex-prompt.md` carry the same rule. Validation:
  direct project-prompt smoke passed; aggregate public smokes passed with 3
  scripts; Python compile passed; public contract check passed; `git diff
  --check` passed. Critic: the prompt builder and static doc are now protected,
  but the actual CLI-rendered `new-project-prompt` output should get a tiny
  smoke so the executable path cannot drift from the builder.
- 2026-06-02T06:31:09+08:00: Added quota `should-run` fixture coverage for the
  operator-gate split. The status smoke now calls `build_quota_should_run()` on
  the same temporary approved/rejected/deferred fixtures: approved gates must
  return `should_run=true`, `state=eligible`, `waiting_on=codex`, and the
  approved read-only-map dry-run `agent_command`; rejected and deferred gates
  must return `should_run=false`, `state=operator_gate`,
  `waiting_on=user_or_controller`, the gate reason, and no `agent_command`.
  `build_quota_should_run()` now omits optional `agent_command` and
  `next_handoff_condition` fields unless they have values, so skip payloads do
  not expose null command slots to project agents. Validation: direct status
  smoke passed; aggregate public smokes passed; Python compile passed; public
  contract check passed; `git diff --check` passed. Critic: the status/quota
  mechanics now protect the gate split, but project-agent-facing docs/prompts
  should state this rule plainly so agents do not infer permission from status
  previews.
- 2026-06-02T06:24:46+08:00: Added the complementary fixture smoke for
  rejected/deferred operator gates. `examples/status-markdown-smoke.py` now uses
  one generic operator-gate fixture helper and verifies all three branches:
  planned goals show the local operator-gate dry-run preview before
  `agent_command`; approved gates move to `waiting_on=codex` with the approved
  read-only-map dry-run command; rejected and deferred gates stay in
  `waiting_on=user_or_controller`, keep the operator question visible, and do
  not expose a project-agent `agent_command` or operator-gate dry-run helper.
  All fixtures write only inside a temporary runtime; no real gate is appended
  and no real map is run. Validation: direct status Markdown smoke passed;
  aggregate public smokes passed; Python compile passed; public contract check
  passed; `git diff --check` passed. Critic: status now protects the
  approve/reject/defer split, but automatic agents spend compute through
  `quota should-run`, so that gate split should get a tiny quota-level fixture
  next.
- 2026-06-02T06:17:37+08:00: Added a fixture-backed status smoke for the
  `operator_gate_approved` path. `examples/status-markdown-smoke.py` now first
  verifies the planned high-complexity adapter still shows the operator-gate
  dry-run preview before `agent_command`, then appends a temporary
  `operator_gate_approved` run index fixture and verifies status moves the
  goal to `waiting_on=codex`, hides the operator question, and exposes the
  approved read-only-map dry-run command as `agent_command`. The fixture only
  writes inside a temporary runtime; it does not append a real gate or run a
  real map. Validation: direct status Markdown smoke passed; aggregate public
  smokes passed; Python compile passed; public contract check passed;
  `git diff --check` passed. Critic: approval now has a regression guard, but
  reject/defer should get the complementary guard so denied or delayed gates do
  not accidentally look project-agent executable.
- 2026-06-02T06:11:00+08:00: Completed the browser-level check for the
  tightened planned opt-in `recommended_action`. After rebuilding the static
  dashboard and confirming `/status.local.json` contained the new action text,
  Playwright opened the controller view for `agent-harness-main-control`.
  Browser DOM eval returned `hasNewText=true`, `hasOldText=false`,
  `selectedActionCardHasNewText=true`, and `attentionQueueRowHasNewText=true`.
  The accessibility snapshot also showed the new action text in the selected
  controller card, the attention queue row, and the run-detail queue action.
  The only console error was a harmless missing `favicon.ico`. Validation:
  dashboard production build passed with the existing >500 kB chunk warning;
  static status JSON check passed; Playwright DOM and snapshot checks passed.
  Critic: the planned opt-in human-decision surface is now aligned across
  status, selected action, and attention queue. The next P0 gap is the
  project-agent execution loop after an approval is actually recorded.
- 2026-06-02T05:59:47+08:00: Tightened the planned controller opt-in
  `recommended_action` emitted by `goal-harness status` for planned
  `*_read_only_map_v0` adapters with no run yet. The status layer now says the
  operator judgment happens in Goal Harness first and the project agent only
  executes the read-only map dry-run after approval. Updated the attention queue
  and status data contract examples to match, and extended
  `status-markdown-smoke` to reject the old "review gate, then send project
  agent command" wording in both JSON and Markdown status output. Validation:
  direct status Markdown smoke passed; aggregate public smokes passed; Python
  compile passed; public contract check passed; live global status assertion
  passed for `agent-harness-main-control`; dashboard local status JSON was
  refreshed; `git diff --check` passed. Critic: the source and live JSON are now
  aligned, but a browser-level check should confirm the attention queue and
  selected controller card render the new wording.
- 2026-06-02T05:54:31+08:00: Completed a browser-level first-screen check of
  the dashboard Review Packet path with Playwright against the local static
  dashboard at `127.0.0.1:5173`. The selected `agent-harness-main-control`
  controller review showed `Operator Review Packet`, showed the helper copy
  saying the operator decides in the dashboard/operator view first, did not
  contain the old "send directly to project Agent; human only adds one
  judgment" wording, and kept the single `Packet details` disclosure collapsed
  by default. Validation: Playwright snapshot confirmed the first-screen text;
  DOM eval returned `hasNewCopy=true`, `hasOldCopy=false`, `hasBadge=true`,
  `packetDetailsCount=1`, and `packetDetailsOpen=[false]`. The only console
  error was a harmless missing `favicon.ico`. Critic: the selected-action panel
  is now visually aligned, but the attention queue/recommended action copy
  still says "review gate, then send project agent command" and should be
  tightened to the same after-approval language.
- 2026-06-02T05:43:29+08:00: Tightened the dashboard selected-action
  microcopy for the Review Packet path. The first-screen badge now says
  `Operator Review Packet`, the helper copy now says to decide in the
  dashboard/operator view first and only then use the packet as project-agent
  execution context, and the controller dry-run preview says the project agent
  reports changed files and validation only after approval. The
  `review-packet-smoke` now rejects the old misleading "send directly to
  project Agent; human only adds one judgment" wording and asserts the new
  microcopy. Validation: direct Review Packet smoke passed; aggregate public
  smokes passed; Python compile passed; dashboard production build passed with
  the existing >500 kB chunk warning; public contract check passed. Critic:
  source/build validation protects the copy, but a browser-level first-screen
  check is still useful before declaring the operator surface polished.
- 2026-06-02T05:33:24+08:00: Added the Review Packet source-of-truth boundary
  to the public status data contract and extended `review-packet-smoke` to
  assert that contract text. The contract now says the dashboard/operator view
  owns the human decision, the copied packet is only a bridge, the local
  `operator_gate_dry_run` belongs to the user/controller, and the
  project-agent command is only the after-approval dry-run execution path.
  Validation: direct Review Packet smoke passed; aggregate public smokes
  passed; Python compile passed; public contract check passed; `git diff
  --check` passed. Critic: the docs contract is now explicit, but the dashboard
  selected-action microcopy should be audited next so the first-screen UI does
  not suggest sending the packet to a project agent before the operator
  decision.
- 2026-06-02T05:25:27+08:00: Validated the live planned high-complexity
  opt-in status against the public Review Packet smoke contract. Live status
  exposes one operator question, the local `operator-gate --dry-run` draft
  before the project-agent command, and the project-agent command remains the
  read-only map dry-run path. A private handoff note was recorded outside the
  public repo. Validation: live packet assertion passed; `refresh-state`
  appended a `state_refreshed` run; dashboard local status JSON was refreshed;
  aggregate public smokes passed; Python compile passed; public contract check
  passed; `git diff --check` passed. Critic: the immediate human-decision
  ordering is healthy, but the source-of-truth boundary should be made explicit
  in the public contract so future UI/CLI work does not make users watch every
  project-agent thread.
- 2026-06-02T05:18:18+08:00: Added a public-safe dashboard Review Packet smoke
  for the planned high-complexity controller opt-in path. The smoke scans the
  dashboard source for the operator-facing packet section order, verifies the
  Chinese controller question/reply/boundary text, verifies the local
  `operator-gate --dry-run` and target-agent `read-only-map --dry-run` builders,
  and builds a sanitized packet fixture to assert the human question, local
  gate dry-run draft, and project-agent command appear in that order. The
  aggregate smoke runner now executes both Review Packet and status Markdown
  smokes. Validation: `python3 examples/run-smokes.py` passed with 2 smoke
  scripts; Python compile passed; public contract check passed; `git diff
  --check` passed. Critic: this protects the key human-decision ordering without
  a frontend refactor, but it still source-scans the dashboard instead of
  importing a pure packet builder.
- 2026-06-02T05:07:45+08:00: Added a tiny aggregate public smoke runner at
  `examples/run-smokes.py`. The runner discovers dependency-free
  `examples/*-smoke.py` scripts, prints each script label before execution, and
  exits on the first failure. README now documents `python3 examples/run-smokes.py`
  as the stable smoke entry while keeping `goal-harness check` focused on
  registry, runtime, and public-boundary contract health. Validation: aggregate
  smoke runner passed and executed the status Markdown smoke; Python compile
  passed; public contract check passed; `git diff --check` passed. Critic: this
  closes the smoke discoverability question without creating a framework, so
  the next P0 slice should return to the planned opt-in human decision loop.
- 2026-06-02T05:00:56+08:00: Added a dependency-free status Markdown smoke for
  planned high-complexity read-only-map adapters. The example builds a temporary
  planned `*_read_only_map_v0` registry, asserts the JSON attention item stays
  unchanged, and asserts Markdown prints `operator_gate_dry_run` before
  `agent_command` with a public-safe reason placeholder. README now documents
  the smoke command near the contract check and clarifies the gate-preview line
  is shown before target-agent handoff. Validation: the smoke script passed;
  Python compile passed; public contract check passed; `git diff --check`
  passed. Critic: this protects the immediate Markdown/JSON boundary, but the
  public repo still needs a small decision on whether smoke scripts should stay
  explicit or be reachable through one aggregate runner.
- 2026-06-02T04:53:03+08:00: Added the agent-facing status boundary hint for
  planned high-complexity read-only-map adapters. Markdown `goal-harness status`
  now prints `operator_gate_dry_run` before `agent_command` when a queue item has
  both an operator question and a target-agent command, so CLI-facing project
  agents see that the gate recording preview is user-owned and comes before any
  handoff. Documentation clarifies this hint is Markdown-only, not a JSON
  contract field or project-agent command. Validation: Python compile passed;
  live status for `agent-harness-main-control` shows `operator_gate_dry_run`
  before `agent_command`; public contract check passed; `git diff --check`
  passed; live operator-gate dry-run still reports `appended=False`; current
  dashboard bundle contains the user-owned gate draft section. Critic: this
  closes the immediate misread risk, but the behavior should get a tiny
  regression smoke so future status refactors do not drop the line.
- 2026-06-02T04:45:40+08:00: Added a dashboard-only user-owned operator-gate
  dry-run draft for controller Review Packets. The selected action now keeps
  one `Copy Review Packet` path, adds a `用户本地 Gate 记录草稿` section for
  `goal-harness operator-gate ... --dry-run`, and keeps the project Agent
  section limited to the read-only/dry-run command. The Safe CLI Path panel also
  shows the gate draft as an attached operator preview rather than a second
  primary action. Validation: dashboard production build passed with the
  existing >500 kB chunk warning; `git diff --check` passed; grep confirmed the
  new packet section, draft command, and UI label; public contract check passed.
  Critic: this fixes the dashboard/user review affordance, but the next useful
  check is whether live status/CLI-facing agents still need a compact boundary
  hint.
- 2026-06-02T04:36:53+08:00: Tightened the dashboard controller Review Packet
  prompt for planned opt-in. The human reply now explicitly says
  `同意先做 read-only map dry-run / 暂不同意 + 一句话原因`, and the boundary states
  that this only authorizes the project agent to preview the dry-run path; it
  does not write operator gate, run history, write-control, experiment control,
  or production actions. Validation: dashboard production build passed with
  the existing >500 kB chunk warning; grep confirmed the new reply and boundary
  text; public contract check passed; `git diff --check` passed;
  `refresh-state` appended a `state_refreshed` run and dashboard local status
  JSON was refreshed. Critic: this lowers the human decision cost for
  `agent-harness-main-control`, but durable operator-gate recording is still a
  separate user-owned action path and should not be delegated to the project
  agent.
- 2026-06-02T04:31:05+08:00: Fixed the `refresh-state` Markdown preview wart
  for wrapped `## Next Action` items. `render_state_refresh_markdown()` now
  renders section previews through logical list items, so a bullet plus wrapped
  continuation lines becomes one Markdown bullet instead of several misleading
  bullets. The existing full `Recommended Action` derivation path is unchanged.
  Validation: Python compile passed; synthetic wrapped-bullet smoke passed;
  live `goal-harness refresh-state --goal-id goal-harness-meta --dry-run` shows
  a single full Next Action bullet; public contract check passed;
  `git diff --check` passed; real `refresh-state` appended a
  `state_refreshed` run whose Markdown output also has one full Next Action
  bullet; dashboard local status JSON was refreshed. Critic: this is a small
  but useful agent-facing correctness fix that prevents automatic heartbeats or
  project agents from misreading continuation lines as separate actions.
- 2026-06-02T04:26:13+08:00: Reduced dashboard first-screen review clutter.
  The selected-action share panel now keeps a single primary `Copy Review
  Packet` action visible, shows only the transition summary by default, and
  folds the raw review URL, transition command, and full packet body under a
  collapsed `Packet details` disclosure. This preserves the single Review
  Packet / history lookup path while removing a large always-open technical
  preview from the operator surface. Validation: dashboard production build
  passed with the existing >500 kB chunk warning; local dashboard HTTP returned
  200; public contract check passed; `git diff --check` passed;
  `refresh-state` appended a `state_refreshed` run and dashboard local status
  JSON was refreshed. Critic: this is the right direction for human attention
  cost, but visual screenshot verification was skipped because Codex's own
  window is blocked for computer-use inspection.
- 2026-06-02T04:18:41+08:00: Made rewarded runs easier for project agents to
  notice from CLI status. `goal-harness status` Markdown now expands compact
  `human_reward` fields under the latest run in `Run History`, including
  `recorded_at`, `decision`, `reward`, `reason_summary`, `follow_up`, and the
  standard `goal-harness history --goal-id ... --limit 3` project-agent lookup.
  Updated the status data contract to keep dashboard as the operator surface
  while making CLI status sufficient for agent inspection. Validation: Python
  compile passed; example status Markdown smoke confirms reward detail and
  history lookup render; public contract check passed; `git diff --check`
  passed; `refresh-state` appended a `state_refreshed` run and dashboard local
  status JSON was refreshed. Critic: this avoids fabricating a real human reward
  and improves P0 visibility, but the dashboard first screen still needs a
  separate attention audit for redundant controls.
- 2026-06-02T04:11:09+08:00: Made reward CLI Markdown easier to judge at a
  glance by adding a `Write Effect` section near the top. Dry-runs and real
  appends now summarize the selected run, whether the run overlay was written
  or only previewed, active-state writeback effect, and the one project-agent
  `goal-harness history --goal-id ... --limit 3` lookup before the detailed
  reward fields. Updated status/integration docs. Validation covered Python
  compile, a live reward dry-run bound to an exact `goal-harness-meta`
  `state_refreshed` run, public contract check, grep for the new write-effect
  contract, and `git diff --check`.
- 2026-06-02T04:07:01+08:00: Tightened the dashboard Review Packet handoff for
  reward actions. The UI may still show a local reward dry-run preview, but the
  copied packet no longer asks the target project agent to run reward dry-run
  or append reward on the user's behalf. For reward actions, the project-agent
  section now says not to write reward and provides the standard
  `goal-harness history --goal-id ... --limit 3` lookup through
  `agentVisibilityCommand`; controller and Codex paths still expose their safe
  read-only/dry-run commands. Updated the status contract and state interaction
  model to preserve this source-of-truth boundary. Validation covered
  dashboard production build, Python compile, contract check, text grep for the
  new history-lookup wording, and `git diff --check`.
- 2026-06-02T04:01:56+08:00: Made default operator-gate review text
  human-facing Chinese. Planned read-only map opt-in status now asks
  `是否同意 ... 先执行 read-only map opt-in？` and recommends reviewing the
  gate before sending the project-agent command. New `operator-gate` dry-runs
  also default to Chinese questions and Chinese recommended actions. Status
  localizes legacy default English operator questions from existing compact
  runs, so current dashboard items become Chinese without rewriting history.
  Updated README and status/attention/integration docs. Validation covered
  Python compile, live status assertions for planned and legacy operator gates,
  `operator-gate --dry-run`, state refresh, dashboard status refresh, public
  contract check, `git diff --check`, and a stale-English text scan.
- 2026-06-02T03:56:50+08:00: Fixed a state-truth issue in
  `refresh-state`: deriving `recommended_action` now uses the first
  public-safe `## Next Action` item and joins wrapped continuation lines
  instead of publishing only the first physical line. This prevents dashboard
  and `quota should-run` output from showing truncated actions such as
  "After this ... re-run". Updated README, integration docs, status contract,
  CLI help, and the installed project skill wording from "line" to "item".
  Validation covered Python compile, a direct wrapped-bullet unit smoke, live
  `refresh-state --dry-run` for `goal-harness-meta`, public contract check,
  and `git diff --check`.
- 2026-06-02T03:52:23+08:00: Packaging pass reviewed the public diff for the
  compute-quota guard adoption slice. Scope is limited to
  `goal_harness/project_prompt.py`, `docs/new-project-codex-prompt.md`,
  `skills/goal-harness-project/SKILL.md`, and this meta state file: project
  agents and onboarding prompts now ask `quota should-run` before spending
  automatic compute, and the text preserves gate/reward/write boundaries.
  Final validation passed: Python compile, generated prompt JSON smoke,
  public contract check, and `git diff --check`. Commit is the remaining
  action for this slice.
- 2026-06-02T03:49:59+08:00: Added the same compute-quota guard to the
  generated new-project Codex prompt and the static onboarding prompt doc.
  Newly connected project agents now learn to run
  `goal-harness --format json quota should-run --goal-id <goal-id>` after
  `connect` and before heartbeat, scheduled-tick, long-running adapter, or
  autonomous delivery work. `should_run=false` means skip implementation with
  the public-safe reason; non-zero status collection fails closed through
  `doctor` / `status`; the guard is explicitly not write permission,
  operator-gate bypass, or human reward. Validation covered Python compile,
  generated prompt JSON smoke, and prompt/doc grep. One failed smoke used the
  global `--format` flag after the subcommand; rerunning with
  `goal-harness --format json new-project-prompt ...` passed. Writeback
  appended a `state_refreshed` run and refreshed the local dashboard status
  JSON.
- 2026-06-02T03:45:29+08:00: Added the compute-quota guard to the
  `goal-harness-project` skill template and reinstalled the local skill copy.
  Project agents are now instructed to run
  `goal-harness --format json quota should-run --goal-id <goal-id>` before
  spending heartbeat, scheduled-tick, adapter, or autonomous delivery compute;
  `should_run=false` skips implementation work with the public-safe reason,
  while non-zero status collection fails closed. The skill also states that
  quota is not write permission, not an operator-gate bypass, and not human
  reward. Validation covered local install sync, installed-skill grep,
  Python compile, live `quota should-run` for `goal-harness-meta`, public
  contract check, and `git diff --check`. Writeback appended a
  `state_refreshed` run for `goal-harness-meta` and refreshed the local
  dashboard status JSON.
- 2026-06-02T02:55:47+08:00: Wired the local hourly heartbeat/control prompt
  into the per-goal quota guard. The heartbeat now instructs the agent to run
  `goal-harness quota should-run --goal-id goal-harness-meta` before spending
  compute, to quiet-skip with `DONT_NOTIFY` when `should_run=false`, and to do
  one verified step only when `should_run=true`. While updating it, the
  automation cadence was corrected from an accidental two-minute interval back
  to hourly. Validation: automation TOML shows the new guard protocol and
  `RRULE:FREQ=HOURLY;INTERVAL=1`; live guard currently returns
  `should_run=true` for `goal-harness-meta`.
- 2026-06-02T02:47:28+08:00: Added the per-goal automation guard for compute
  quota. `goal-harness quota should-run --goal-id <goal-id>` now reads the
  same status-derived quota plan and returns a compact `run` or `skip`
  decision. It returns `should_run=true` only for `state=eligible`; known goals
  blocked by operator gates, external evidence, throttling, pause, or health
  issues return `should_run=false` with a public-safe reason. Unknown goals and
  quota/status collection failures fail closed with a non-zero exit code.
  `public_harness_healthy` is now treated as Codex-ready in status so the
  harness self-improvement heartbeat can become eligible after a clean
  self-health run instead of being mistaken for inactive waiting state.
  Updated README and quota/status docs. Validation covered Python compile,
  live operator-gate skip, live external-evidence skip, missing-goal non-zero
  skip, missing-argument non-zero skip, synthetic eligible `run`, public
  contract check, and `git diff --check`.
- 2026-06-02T02:39:24+08:00: Added the first agent-facing quota planner CLI.
  `goal-harness quota status` and `goal-harness quota plan` now derive
  compute groups from the existing status contract instead of inventing a
  separate scheduler truth source. The commands group registered goals under
  `blocked_health`, `operator_gate`, `eligible`, `waiting`, `throttled`, and
  `paused`, expose `summary.next_automatic_turn`, and keep health/operator/
  evidence gates ahead of compute quota. `quota plan` hides empty groups in
  Markdown so automations and project agents get a shorter next-turn view.
  Updated README and quota/status docs. Validation covered Python compile,
  `goal-harness quota status`, `goal-harness quota plan`, JSON quota-plan
  parsing, unchanged status JSON parsing, public contract check, and
  `git diff --check`.
- 2026-06-02T02:25:00+08:00: Added compact compute quota to registry/status and
  trimmed dashboard attention load. Registry inspection now exposes a default
  `quota.compute=1.0` when no project declares one, and status attaches compact
  quota state to registered attention items and run-history goals. The state
  order follows hard gates first: health, operator gate, evidence wait, then
  compute quota. The dashboard schema renders `Quota` chips in User Actions,
  Goal Directory, Queue, and Review Packet without adding a settings page.
  To keep the first screen quieter, the Source/Load controls moved below
  health panels, the duplicate User Review Map panel was removed, and User
  Action cards no longer show raw CLI blocks; detailed commands remain in the
  single Review Packet. Validation covered Python compile, dashboard build,
  JSON example parse, refreshed `status.local.json`, Markdown status quota
  output, `goal-harness check --scan-root .`, `git diff --check`, and
  Playwright smoke for quota chips plus absence of `User Review Map`.
- 2026-06-02T02:06:00+08:00: Surfaced authority-registry coverage in the user
  dashboard path. Status now carries registry-level `authority_registry` on
  `run_history.goals`, so coverage remains visible even when the latest run is
  an operator gate rather than a fresh project map. The dashboard schema,
  User Actions card, Copy Review Packet, run detail, and project-map summary
  all render the same authority coverage line; the bundled example and status
  contract document the goal-level field. Global sync now resolves default
  entries relative to the project repo before writing compact registry
  coverage. Validation covered Python compile, dashboard build, JSON example
  parse, `goal-harness check --scan-root .`, refreshed local status JSON, and
  Playwright smoke on the local dashboard for `Authority coverage`, `default
  entries 7/7`, `risk medium`, and `Copy Review Packet`.
- 2026-06-02T01:46:00+08:00: Added compact authority-registry coverage to the
  read-only map path. Registry inspection now summarizes optional
  `authority_registry`, global sync keeps a compact public-safe summary, and
  `goal-harness read-only-map` writes both full local coverage and compact
  status fields: declared/path/default entries/topic authority/conflict risk.
  Residual risks now use stable `authority_registry_*` labels for missing
  registry files, missing default entries, deprecated sources, or medium/high
  conflict risk. Updated docs and examples. Validation covered Python compile,
  registry and sync-global dry-runs, temporary project dry-run and status
  smoke tests, JSON example parsing, public contract check, sensitive-pattern
  scan, and `git diff --check`; pushed commit `7ee16ec` as
  `huangrt01 <huangrt01@163.com>`.
- 2026-06-01T23:26:41+08:00: Aligned the public status/attention queue with
  the planned-adapter dry-run preview behavior. For a registered
  high-complexity `*_read_only_map_v0` goal with `adapter.status=planned` and
  no run yet, `goal-harness status` now keeps the item in
  `waiting_on=user_or_controller` and recommends
  `goal-harness read-only-map --goal-id <goal> --dry-run` as the opt-in
  preview. This replaces the stale generic action "connect an adapter or run a
  read-only map" without adding a new `waiting_on` value. The attention-queue
  and status-data-contract docs now state that this preview appends nothing and
  is not controller opt-in. Validation proved that `agent-harness-main-control`
  now renders the new action in both JSON and Markdown status, queue summary
  counts it as user/controller work, and Python compile, public contract check,
  and `git diff --check` passed. Refreshed local dashboard status JSON.
- 2026-06-01T23:24:05+08:00: Fixed the agent-facing opt-in path for planned
  complex adapters. `goal-harness read-only-map --dry-run` now succeeds for
  `adapter.status=planned` and returns `opt_in_required=true`, so a copied
  controller packet no longer hands the target Agent a failing command. The
  real append path is still guarded: the same command without `--dry-run` keeps
  failing until the adapter status moves to `read-only-map-ready`,
  `connected-read-only`, or `connected`. README, integration docs, and the
  complex-project read-only adapter doc now state this opt-in preview rule.
  Validation used the live `agent-harness-main-control` global registry entry:
  planned dry-run succeeded with `appended=false`, `opt_in_required=true`, and
  bounded map counts; non-dry-run on the same planned adapter failed with the
  explicit opt-in error. Python compile, public contract check, and
  `git diff --check` passed.
- 2026-06-01T23:18:40+08:00: Simplified the dashboard Review Packet around
  the actual multi-Agent collaboration loop: one copy button, one human
  decision prompt, one target-Agent execution path. Removed the old verbose
  user-fill template, repeated Codex instructions, reward hint noise, and
  visible transition effect bullet list. The copied packet now keeps only
  goal/link/summary, `人只需判断`, `给项目 Agent`, the exact read-only or
  dry-run command, and the write-boundary. Reward packets still include
  `--write-active-state-summary --dry-run`. Validation covered TypeScript/Vite
  build, Python compile, public contract check, refreshed local dashboard JSON,
  and an in-app Browser smoke check proving the old packet sections are gone
  while the simplified human/Agent sections and reward dry-run flags remain.
- 2026-06-01T23:00:12+08:00: Added an explicit active-state summary writeback
  path to `goal-harness reward`. The default behavior is unchanged: reward
  appends only the run-bound `human_reward` overlay. Passing
  `--write-active-state-summary` resolves the registry `state_file` or an
  explicit `--state-file`, inserts the returned Chinese `active_state_summary`
  into `## Progress Ledger`, updates frontmatter `updated_at`, and reports an
  `active_state_update` object. With `--dry-run`, the same flag previews
  `would_write=true` without mutating either the run index or active state.
  The dashboard reward preview now includes
  `--write-active-state-summary --dry-run`, and the Review Packet explains that
  the real command will append the reward overlay plus Progress Ledger summary
  only after explicit user action. Docs and the installed project skill now
  teach the dry-run-first, explicit-write flow. Validation used a temporary
  registry/runtime/state file to prove: no flag leaves state untouched,
  dry-run with the flag previews state write only, real append with the flag
  writes one overlay and one active-state summary, and `history` still merges
  the reward into a single judged run. Python compile, public contract check,
  dashboard build, and Playwright command smoke all passed.
- 2026-06-01T22:45:18+08:00: Made reward submission produce a standard
  coordination surface. `goal-harness reward --dry-run` and real append now
  return a Chinese `active_state_summary` plus
  `project_agent_visibility.history_command`, and `POST /reward/dry-run`
  exposes the same fields for the live dashboard. The dashboard displays the
  summary and one project-agent history command after dry-run validation.
  README, integration, status contract, experiment milestone, state model, and
  dashboard docs now state that the run-bound `human_reward` overlay is the
  durable source of truth while active state is summary-only. Validation used a
  temporary registry/runtime to prove dry-run does not write, append adds one
  overlay row, and `history` merges the reward into the judged run; Python
  compile, public contract check, dashboard build, and live dashboard dry-run
  smoke all passed.
- 2026-06-01T22:12:40+08:00: Collapsed the dashboard's first-screen share
  affordances from several copy buttons into one canonical `Copy Review Packet`.
  The selected packet now follows the selected action card, so three active
  actions can share one copy panel without ambiguity: clicking another card
  changes the packet target and shows a `Selected` badge. The packet combines
  the review link, Chinese user judgment template, project-agent instructions,
  reward/default hint, and a local dry-run preview. Reward previews target an
  exact run-bound `human_reward` overlay via `goal-harness reward --dry-run`;
  controller previews target `read-only-map --dry-run` or the selected safe
  path. README, status data contract, and state interaction docs now state that
  durable reward belongs in the run-bound `human_reward` overlay, while active
  state only summarizes recorded reward and Review Packet is only for
  user-to-agent coordination.
- 2026-06-01T11:43:29+08:00: Added `docs/status-data-contract.md`,
  linked it from README / architecture / attention queue / integration docs,
  pushed the public commit, and saved a compact self-health run with
  `health_check=22/22`.
- 2026-06-01T11:48:36+08:00: Added
  `examples/render-status-dashboard.py`, documented the static dashboard demo,
  and validated that `examples/status.example.json` renders to a local HTML
  dashboard with user/controller, Codex-ready, and external-evidence lanes.
- 2026-06-01T11:59:59+08:00: Added
  `docs/dashboard-frontend-selection.md`, reframed the single-file HTML
  renderer as a diagnostic fallback, and selected a React/Vite/shadcn/TanStack
  stack for the product dashboard after benchmarking observability and
  orchestration consoles.
- 2026-06-01T12:05:18+08:00: Scaffolded `apps/dashboard` as a Vite + React +
  TypeScript app that reads `examples/status.example.json`, validates it with
  Zod, renders status lanes, metrics, a Recharts queue chart, and a sortable
  TanStack Table behind URL-backed TanStack Router filters.
- 2026-06-01T12:15:37+08:00: Validated the dashboard scaffold with
  `npm --prefix apps/dashboard run build`, browser smoke checks for the
  `Goal Operations` screen, and a public contract scan over the repo. Updated
  the contract scanner to skip `node_modules` so the new npm app remains
  compatible with `--scan-root .`.
- 2026-06-01T12:21:11+08:00: Added dashboard status source controls. The app
  now keeps `examples/status.example.json` as a fallback, accepts a
  URL-backed status source through `statusUrl`, loads imported JSON files, and
  validates every loaded payload with the same Zod status data contract.
- 2026-06-01T12:28:37+08:00: Validated the status source path with a generated
  `apps/dashboard/public/status.local.json` export and a browser smoke check at
  `?statusUrl=/status.local.json`. Added dashboard docs plus a `.gitignore`
  guard so local status exports stay untracked.
- 2026-06-01T12:37:47+08:00: Added `goal-harness serve-status`, a loopback HTTP
  server for live dashboard status JSON with `/status.json`, `/healthz`,
  no-store responses, and local CORS headers. The React dashboard now has a
  default `Live` source path for `http://127.0.0.1:8765/status.json`.
- 2026-06-01T12:47:47+08:00: Added compact run-history to the public
  `goal-harness status` contract, stripping local artifact paths while exposing
  recent classifications, health check summaries, and JSON/Markdown artifact
  availability. The React dashboard now lets an operator select an attention
  queue row and inspect the corresponding run-history detail panel.
- 2026-06-01T13:00:03+08:00: Added `contract.checks` to the public status data
  contract, rendered contract health detail in the React dashboard and the
  static HTML fallback, refreshed the dashboard visual baseline toward a
  product control-plane UI, and recorded the next experiment-controller
  milestone in `docs/experiment-controller-milestone.md`.
- 2026-06-01T13:13:04+08:00: Added the first public experiment-controller
  contract slice: `goal-harness status` now whitelists compact `human_reward`
  fields, maps `needs_human_reward`, `inspect_result`, and
  `blocked_by_safety` classifications into the attention queue, and the React
  dashboard plus static HTML fallback show human reward signals in run history.
  Added sanitized experiment-controller run and reward examples.
- 2026-06-01T13:32:10+08:00: Added compact `controller_readiness` to the
  public status contract, React dashboard, and static HTML fallback. Run
  history can now show whether an experiment controller is ready for read-only
  observation, decision advice, or write control, plus the missing gate names
  and compact gate reviews. Updated sanitized examples and milestone docs.
- 2026-06-01T13:44:00+08:00: Added `goal-harness reward`, a generic operator
  feedback writer that appends compact `human_reward` overlays to a goal run
  index without rewriting private run payloads. Updated run-history loading to
  merge later overlay rows for the same run key, documented the command in
  README / integration / status contract / experiment-controller milestone,
  and added private-looking text rejection for reward summaries.
- 2026-06-01T14:45:00+08:00: Added the first multi-project dashboard
  navigation surface. `goal-harness status` now exposes public-safe goal
  `domain` in compact run history, the React dashboard renders a first-screen
  `Goal Directory` across all known goals, and the old queue mix chart was
  removed so attention lanes and run-history drill-down stay focused.
- 2026-06-01T15:00:00+08:00: Added a local-only `Reward CLI Draft` to the
  dashboard run-history panel. It is generated from the selected goal, latest
  compact run timestamp, registry, and runtime root; defaults to `--dry-run`;
  and keeps browser-side reward writes out of scope until the same safety checks
  are enforced locally.
- 2026-06-01T15:08:00+08:00: Added local reward dry-run validation for the
  dashboard. `goal-harness serve-status` now exposes `POST /reward/dry-run`,
  the React run-history panel can validate selected goal/run reward drafts
  against that loopback endpoint, and the response is compact with
  `appended=false` and no private artifact paths.
- 2026-06-01T15:18:00+08:00: Added
  `docs/dashboard-reward-write-boundary.md` to define the future browser reward
  append gate. The design requires an explicit server write flag, loopback-only
  binding, a browser capability token, exact run targeting, a dry-run preview
  handshake, stale-preview rejection, compact responses, and validation that the
  index changes only on a reviewed append path.
- 2026-06-01T15:37:00+08:00: Added queue-level controller gate hints and a
  reusable new-project Codex handoff prompt. `goal-harness status` now lifts
  compact `controller_stage`, `missing_gates`, and `next_handoff_condition`
  into attention queue items so a multi-project operator can see why a watched
  goal is not ready without opening the run payload. The React dashboard,
  static HTML fallback, status contract, and sanitized examples render those
  gate hints. Added `docs/new-project-codex-prompt.md` and linked it from
  README and integration docs.
- 2026-06-01T15:47:30+08:00: Added `goal-harness new-project-prompt`, a CLI
  generator for the Chinese Codex handoff prompt used to connect a project from
  a project folder plus goal document. The generated command defaults to a
  read-only adapter and omits `--next-probe` unless a real read-only pre-tick
  command is provided.
- 2026-06-01T16:04:18+08:00: Added `scripts/install-local.sh` so a fresh local
  checkout can install `goal-harness` into `~/.local/bin` and add that directory
  to the shell profile; `scripts/goal-harness` now resolves symlink targets so
  the installed wrapper still finds the real repository root. Also added
  `connect --goal-doc` as a primary authority source in registry and initial
  state, and updated `new-project-prompt` to run a CLI preflight before project
  connection.
- 2026-06-01T16:12:12+08:00: Added `goal-harness doctor` to diagnose local CLI
  installation, PATH, symlink realpath, wrapper script, and Python import
  health. The installer and new-project handoff now call `goal-harness doctor`
  instead of `--help`, so future connection failures expose a structured fix
  rather than stopping at a missing command.
- 2026-06-01T16:22:59+08:00: Made actionable unregistered runtime goals visible
  in the public attention queue as `unregistered_runtime_goal`. This keeps
  multi-project dashboard status authoritative when a new project has saved run
  history before registry connection, while watch-only legacy records remain in
  run history without becoming queue work.
- 2026-06-01T16:32:48+08:00: Added `goal-harness archive-runtime` as the
  cleanup path for obsolete runtime-only goals. It defaults to dry-run, requires
  `--execute` before moving files, protects registry members by default, and
  moves reviewed runtime directories under `<runtime-root>/archived-goals/`.
- 2026-06-01T16:58:24+08:00: Added `goal-harness refresh-state`, a state-only
  run writer for the case where a controller updated active state, ledger, or
  planning docs without running a project adapter. `status` now maps the compact
  `state_refreshed` classification to Codex-ready work, the new-project handoff
  prompt teaches receiving sessions to run the refresh when dashboard still
  shows an old run, and the latest zero-start project was connected into the
  local multi-project registry so it appears as `state_refreshed -> codex`
  instead of an unregistered runtime goal.
- 2026-06-01T17:07:01+08:00: Replaced the manual multi-project registry patch
  with automatic global-registry sync. `goal-harness connect` and
  `goal-harness refresh-state` now merge local project registry entries into
  `~/.codex/goal-harness/registry.global.json`; `status` falls back to that
  global registry when no project-local registry exists; and
  `goal-harness sync-global` exists for explicit diagnosis or recovery. The
  global registry strips raw authority-source details while keeping local paths
  private under the shared runtime root.
- 2026-06-01T17:16:09+08:00: Added the public
  `skills/goal-harness-project/SKILL.md` and taught `scripts/install-local.sh`
  to install or update it under `~/.codex/skills/goal-harness-project` by
  default. The skill captures the agent-side workflow for project connect,
  state refresh, global sync, validation, private boundary, and Chinese review
  reporting.
- 2026-06-01T17:36:10+08:00: Added global-registry health to the public status
  contract and React dashboard. `goal-harness status` now reports
  `global_registry` findings for stale source registries, missing active state
  files, duplicate goal ids, and local-vs-global scope mismatches. CS-Notes
  pre-tick now reads the global registry first-screen status, so a newly
  connected read-only project appears as `state_refreshed -> codex` instead of
  a local-registry ghost.
- 2026-06-01T17:55:00+08:00: Fixed `status` / `serve-status` default contract
  scan boundaries. Multi-project status can now be run from a private project
  checkout while still checking the public Goal Harness install root by
  default; operators must opt in with `--scan-root` or `--scan-path` before
  scanning a project-specific public surface.
- 2026-06-01T18:02:32+08:00: Improved state-only refresh action quality after
  inspecting a real zero-start project connection. The latest active state had
  a precise next action, but the compact dashboard run still showed the generic
  refresh notice. `refresh-state` now derives the compact `recommended_action`
  from the first public-safe `## Next Action` line, skips private-looking lines
  such as internal document URLs, and falls back to the generic refresh notice
  only when needed. The rendered refresh Markdown also normalizes bullet
  prefixes.
- 2026-06-01T18:24:00+08:00: Added `goal-harness read-only-map`, a generic
  read-only project-map run writer for connected projects. It accepts
  `read_only_project_map_v0` or compatible `*_read_only_map_v0` adapters,
  derives a public-safe dashboard action from active state, records compact map
  counts in run history, and keeps raw project evidence in the private runtime
  payload. Updated status classification, dashboard schema/rendering, docs,
  new-project prompt guidance, and installed skill workflow.
- 2026-06-01T18:36:00+08:00: Added
  `docs/state-interaction-model.md` to define the state boundary between the
  durable goal, Codex App executor, human operator, and dashboard. The document
  names actor ownership, state stores, state transitions, dashboard first-screen
  rules, invariants, and a feature-gate checklist so future work does not add
  isolated commands before the state contract is clear. Linked it from
  `README.md` and `docs/architecture.md`.
- 2026-06-01T18:51:00+08:00: Added lifecycle phases to the public status
  contract and dashboard. `goal-harness status` now derives compact
  `lifecycle_phase` / `lifecycle_flags` for attention items, run-history goals,
  and compact runs. The React dashboard validates those fields and renders a
  human-facing `User Review Map` so users see connected, mapped, refreshed,
  adapter-inspected, reward-judged, controller-gated, and controller-ready
  states separately from raw adapter classifications. The docs now clarify that
  CLI status is agent-facing machine state, while the dashboard is the
  operator-facing interpretation layer.
- 2026-06-01T18:58:00+08:00: Added a selected-goal `Operator Decision` panel
  to the React dashboard. The panel derives a human stance from queue item,
  lifecycle phase, readiness gates, and recommended action: review or authorize,
  let Codex continue, wait for evidence, or fix health first. This keeps
  `goal-harness status` as an agent-facing contract while making the dashboard
  answer the user question before showing run-history details.
- 2026-06-01T19:08:36+08:00: Connected `Operator Decision` to a selected-goal
  `Safe CLI Path`. The dashboard now shows the safe local command class for the
  current stance: status/history inspection, `read-only-map --dry-run`,
  `refresh-state --dry-run`, or a reward-gate handoff to the existing Reward CLI
  Draft. The bridge is explicitly read/dry-run oriented and does not add
  browser-side reward append or approval writes.
- 2026-06-01T19:15:23+08:00: Made the dashboard `Reward CLI Draft` derive
  scenario-specific defaults from the selected `Operator Decision` and missing
  gates. Mapped Codex-ready goals default to `use_read_only_map` with a positive
  handoff reward; external-evidence goals missing `human_reward_capture` default
  to `record_human_reward_gate` with the compact handoff condition; controller
  opt-in goals show their gate label but still avoid a reward command when no
  compact run exists. The panel can reset to these defaults after user edits,
  and browser writes remain disabled.
- 2026-06-01T19:21:38+08:00: Promoted operator-derived actions into a
  first-screen `User Actions` summary. The React dashboard now derives compact
  action cards from the same `Operator Decision` and reward-default logic used
  by selected-goal detail, so reward gates, controller opt-ins, evidence
  watches, Codex handoffs, and blocking health items are visible before opening
  a goal. In the current global status, the first screen shows three cards:
  `Record human reward` for `tiger-team-maiduidui-regauc`, `Review controller
  opt-in` for `agent-harness-main-control`, and `Let Codex use the map` for the
  mapped Codex-ready project.
- 2026-06-01T19:30:27+08:00: Inlined the selected-detail action affordances
  into the first-screen `User Actions` cards. Each card now derives a safe path
  from the same `Safe CLI Path` builder and a compact reward hint from the same
  reward-draft defaults, so the first screen can show status/history,
  read-only-map dry-run, or reward-gate hints without turning the dashboard
  into a writer. README, status contract, and state-interaction docs now state
  that these first-screen hints are user-facing affordances over the
  agent-facing status export.
- 2026-06-01T19:37:04+08:00: Turned first-screen `User Actions` into a focused
  review flow by deriving a local action kind for each card: reward,
  controller, Codex, evidence, or health. The React dashboard now renders a
  compact segmented filter with per-kind counts, filters only the first-screen
  action cards, and keeps the raw status export unchanged. README, status
  contract, and state-interaction docs now clarify that action-kind focus is
  dashboard UI state over the agent-facing status contract.
- 2026-06-01T19:43:08+08:00: Made the `User Actions` action-kind focus
  URL-backed. The dashboard router now accepts `actionKind=all|reward|controller|codex|evidence|health`,
  and the first-screen action filter is driven by that search parameter instead
  of component-local state. Focused review views survive refresh and can be
  shared, including empty focused views such as `actionKind=evidence`, while
  remaining dashboard UI state only. README, status contract, and
  state-interaction docs now describe the URL-backed focus boundary.
- 2026-06-01T19:48:44+08:00: Made the selected goal detail URL-backed as
  `goalId`. All dashboard selection surfaces now update the same search
  parameter: `User Actions`, `Goal Directory`, attention lanes, attention table,
  and the run-history goal selector. If a loaded status source does not contain
  the requested goal, the dashboard falls back to the first available
  run-history goal and normalizes the URL. README, status contract, and
  state-interaction docs now describe selected-goal URL state as a browser
  review affordance, not part of the status export or durable goal truth.
- 2026-06-01T20:04:30+08:00: Added a compact first-screen `Review link`
  affordance to the React dashboard. It builds a canonical browser URL from the
  current `actionKind`, selected `goalId`, `statusUrl`, `lane`, and `severity`,
  displays those as review-state badges, and copies the link with a clipboard
  fallback for local HTTP previews. The control is labeled as UI state only and
  does not write reward, approval, controller opt-in, runtime indexes, or the
  status contract. README, status data contract, and state interaction docs now
  describe the copied link as a user review affordance over agent-facing
  status.
- 2026-06-01T20:12:51+08:00: Turned the copied review state into a first-screen
  operator handoff packet. The React dashboard now derives the selected action
  card from the current selected goal and action-kind lane, then builds a
  copyable packet with selected goal, action type, review link, Chinese review
  action, current judgment, context summary, `Reward/default hint`, and `Safe
  local path` including the command when available. The packet explicitly says
  it does not write reward, approval, controller opt-in, or write-control.
  README, status data contract, and state interaction docs now describe the
  packet as a user-facing project-agent handoff artifact, not a durable state
  transition.
- 2026-06-01T20:30:15+08:00: Moved user-required interaction to the dashboard
  first screen. `User Actions` and `Selected action share` now render before
  source controls, metrics, directory, maps, and raw queues; the share panel
  can copy a review link, operator handoff packet, or project-agent prompt.
  The selected share target now follows the current action filter rather than
  a stale run-history selection, so switching to `Reward` selects the reward
  card's goal. The project-agent prompt tells receiving Codex sessions to run
  `goal-harness doctor`, read the project registry, active state, and run
  history, follow only the safe local path, and report in Chinese.
- 2026-06-01T20:41:35+08:00: Added first-screen Chinese operator response
  templates to `Selected action share`. The React dashboard now derives a
  `Copy User Response` packet from the selected action card and review link,
  with reward cards prompting for "同意记录这次 human reward / 暂不同意", reason,
  and next step, and controller cards prompting for "同意继续
  read-only/controller opt-in / 暂不同意", reason, next step, and an explicit
  no-write-control boundary. Codex/evidence/health cards also get conservative
  copy-only templates. README, status data contract, and state interaction
  docs describe the template as browser UI state, not durable reward,
  approval, controller opt-in, or write-control.

## Validation

- `python3 -m py_compile goal_harness/*.py`
- `python3 -m py_compile goal_harness/status.py examples/render-status-dashboard.py`
- `python3 -m goal_harness.cli --help`
- `python3 -m goal_harness.cli --format json check --scan-root .`
- Parse all JSON examples in `examples/`.
- `python3 -m goal_harness.cli --format json status` includes
  `lifecycle_phase` and `lifecycle_flags` on attention items, run-history
  goals, and compact runs
- Browser DOM smoke: selected-goal detail shows `Operator Decision`; default
  mapped goal shows `Let Codex use the map`; `tiger-team-maiduidui-regauc`
  shows `Wait for evidence` plus missing gate copy; `agent-harness-main-control`
  shows `Review controller opt-in` and `Needs approval`
- Browser DOM smoke: selected-goal detail shows `Safe CLI Path`; default mapped
  goal shows a history handoff command; `tiger-team-maiduidui-regauc` shows a
  watch/status command, reward gate, and handoff condition; `agent-harness-main-control`
  shows `read-only-map --dry-run` and an approval boundary.
- Browser DOM smoke: mapped goal reward draft defaults to
  `use_read_only_map` / `positive`; `tiger-team-maiduidui-regauc` defaults to
  `record_human_reward_gate` / `neutral` with the compact handoff condition;
  `agent-harness-main-control` keeps `needs run` while showing the
  controller-opt-in default source.
- CLI dry-run smoke: `goal-harness reward --dry-run` accepts the derived tiger
  reward-gate fields and returns `ok=True`, `dry_run=True`, `appended=False`.
- Browser DOM smoke: first-screen `User Actions` appears before
  `Goal Directory`, shows `3 actions`, and includes reward gate, controller
  opt-in, and map handoff cards for the current global status.
- Browser DOM smoke: first-screen `User Actions` cards expose `Safe path` and
  `Reward draft`; the global status case shows a status watch command,
  `read-only-map --dry-run`, `goal-harness history`, and the reward decisions
  `record_human_reward_gate`, `controller opt-in / needs run`, and
  `use_read_only_map`.
- Browser DOM smoke: first-screen `User Actions` exposes action-kind filter
  buttons `All`, `Reward`, `Controller`, and `Codex`; clicking each focused
  filter reduces visible cards to the corresponding single action and preserves
  the safe path / reward draft hints.
- Browser DOM smoke: loading `?actionKind=controller` focuses the
  `User Actions` card list on controller work, keeps the URL stable after
  refresh, and clicking `Reward` updates the search parameter to
  `actionKind=reward` while preserving status URL state.
- Browser DOM smoke: loading
  `?actionKind=controller&goalId=agent-harness-main-control` opens the
  controller-focused action card and selected run-history detail; selecting the
  reward card updates `goalId=tiger-team-maiduidui-regauc`, keeps
  `actionKind=reward`, and preserves `statusUrl`.
- Browser DOM smoke: the `Review link` panel is visible, shows `UI state only`,
  copies the current controller/agent-harness review URL into the clipboard,
  preserves `statusUrl`, `lane`, and `severity`, and updates when the operator
  switches to the reward filter and selects `tiger-team-maiduidui-regauc`.
- Browser DOM smoke: `Copy Handoff` copies a Chinese
  `Goal Harness Operator Handoff` packet for `agent-harness-main-control` with
  controller review action, `read-only-map --dry-run`, reward/default hint,
  review link, and explicit no-write boundary; after switching to the reward
  filter and selecting `tiger-team-maiduidui-regauc`, the packet updates to the
  reward goal and `record_human_reward_gate / neutral`.
- Browser DOM smoke: with no explicit `goalId`, `User Actions` appears before
  `Source`, the share target defaults to the first user-required action
  (`tiger-team-maiduidui-regauc`, `Reward`), and `Copy Agent Prompt` is present.
- Browser DOM smoke: with a stale selected goal and `actionKind=reward`, the
  share target follows the reward card and rewrites the review link to
  `goalId=tiger-team-maiduidui-regauc`.
- Browser DOM smoke: agent prompt text includes `goal-harness doctor`,
  `.goal-harness/registry.json`, the selected safe local path, and the
  boundary that the prompt is not reward append, approval, controller opt-in,
  or write-control.
- Browser DOM smoke: reward-focused first screen shows `Copy User Response`,
  `目标：tiger-team-maiduidui-regauc`, and the Chinese
  `同意记录这次 human reward / 暂不同意记录这次 human reward` template with a
  no-write-control boundary.
- Browser DOM smoke: controller-focused first screen shows `Copy User Response`,
  `目标：agent-harness-main-control`, and the Chinese
  `同意继续 read-only/controller opt-in / 暂不同意，原因如下` template with a
  no-write-control boundary.
- Browser DOM smoke: first-screen sharing exposes exactly one
  `Copy Review Packet` button and no `Copy User Response` / `Copy Handoff` /
  `Copy Agent Prompt` buttons; `User Actions` remains before `Source`, shows
  `3 actions`, and the packet includes `Goal Harness Review Packet`, local
  dry-run preview, `human_reward overlay`, and the no-write-control boundary.
- Browser DOM smoke: selecting the controller card switches the shared packet
  target to `agent-harness-main-control`, updates the URL `goalId`, shows the
  `Selected` badge, and includes `read_only_controller_handoff_preview` plus a
  `read-only-map --dry-run` command.
- `python3 -m goal_harness.cli --format json check --scan-path README.md --scan-path docs/dashboard-frontend-selection.md --scan-path docs/status-data-contract.md`
- `cd apps/dashboard && npm run build`
- Browser DOM smoke: load
  `http://127.0.0.1:5173/?lane=all&severity=all&statusUrl=/status.local.json`
  and verify `User Review Map`, human-facing review copy,
  `Controller gated`, `Mapped`, and `Goal Directory`
- `python3 -m goal_harness.cli --format json status > apps/dashboard/public/status.local.json`
- Browser smoke: load `http://127.0.0.1:5173/?statusUrl=/status.local.json`
- `python3 -m goal_harness.cli serve-status --help`
- `curl http://127.0.0.1:8765/healthz`
- `curl http://127.0.0.1:8765/status.json`
- Browser smoke: click `Live` in `apps/dashboard` and verify it loads
  `http://127.0.0.1:8765/status.json`
- `python3 -m goal_harness.cli --format json status` includes `run_history`
  without local path keys
- Browser smoke: click `docs-maintenance-goal` in the attention queue and
  verify the run-history panel switches to the no-run state
- `python3 -m goal_harness.cli --format json status` includes
  `contract.checks`
- `python3 examples/render-status-dashboard.py examples/status.example.json /tmp/goal-status-dashboard.html`
- Browser smoke: verify Contract Health, Checks, and non-wrapping source
  controls in the React dashboard
- `goal-harness status` with a synthetic runtime verifies `human_reward`
  whitelist behavior and does not export unapproved reward keys
- `goal-harness reward` with a synthetic runtime appends a compact reward
  overlay, `status` merges it into one unique run, and private-looking reward
  text is rejected
- Browser smoke: select `experiment-controller-goal` and verify the dashboard
  shows Human reward without private fields
- `python3 -m goal_harness.cli --format markdown status` shows the latest run
  `controller_readiness` classification when present in the compact index
- Browser smoke: select `experiment-controller-goal` and verify the dashboard
  shows Controller readiness and Human reward without private fields
- Browser smoke: verify `Goal Directory` renders bundled examples, hides the
  old `Queue Mix`, switches run history when selecting `docs-maintenance-goal`,
  and renders the live local 5-goal status export with public-safe domains
- Browser smoke: verify `Reward CLI Draft` appears for a selected goal with a
  compact run, includes `--dry-run` and `--run-generated-at`, and selected goals
  without compact runs show `needs run`
- `curl POST /reward/dry-run` against a synthetic loopback server returns
  `ok=true`, `appended=false`, and leaves the run index row count unchanged
- `goal-harness status` for the local multi-project registry shows
  `tiger-team-maiduidui-regauc` with
  `controller_stage=ready_for_read_only_not_decision` and missing gates
  `human_reward_capture`, `aligned_eval_decision_evidence`
- `python3 -m goal_harness.cli new-project-prompt --project
  /tmp/demo-project --goal-doc /tmp/demo-project/GOAL.md` renders a Chinese
  handoff prompt without a placeholder `--next-probe`
- `python3 -m goal_harness.cli --format json new-project-prompt --project
  /tmp/demo-project --goal-doc /tmp/demo-project/GOAL.md` exposes the prompt
  and connect command for scripts
- `HOME=$(mktemp -d) SHELL=/bin/zsh scripts/install-local.sh` creates a
  `~/.local/bin/goal-harness` symlink, adds a Goal Harness PATH block to
  `.zshrc`, and the installed wrapper runs `goal-harness --help`
- `scripts/install-local.sh && command -v goal-harness && goal-harness --help`
  verifies the current user shell can resolve and execute the CLI from any
  project directory
- `goal-harness doctor` and `goal-harness --format json doctor` verify current
  PATH, wrapper, symlink realpath, and Python import health
- `PATH=/usr/bin:/bin python3 -m goal_harness.cli --format json doctor`
  reports `ok=false`, `command_on_path=false`, and a concrete install/PATH fix
- `python3 -m py_compile goal_harness/*.py examples/render-status-dashboard.py`
- Synthetic project: `refresh-state --dry-run` returns `appended=false`, real
  `refresh-state` writes JSON/Markdown/index artifacts, and `status` maps the
  latest run to `state_refreshed -> codex`
- Latest zero-start project registry: `refresh-state --dry-run` reads the
  updated active state with `state_file 1/1`; real refresh appended a
  `state_refreshed` run at `2026-06-01T16:52:57+08:00`
- Multi-project status export now shows the zero-start project as
  `state_refreshed -> codex`
- `python3 -m goal_harness.cli --registry <private-multi-project-registry>
  --runtime-root <shared-runtime> --format json check --scan-path README.md
  --scan-path docs --scan-path examples --scan-path goal_harness --scan-path
  apps/dashboard/src --scan-path goals --scan-path scripts`
- `npm --prefix apps/dashboard run build`
- Browser smoke: load
  `http://127.0.0.1:5173/?lane=all&severity=all&statusUrl=/status.local.json`
  and verify the latest zero-start project row shows `state_refreshed`, Codex,
  and the refreshed-state action
- Synthetic project: `connect` auto-synced `auto-sync-demo` into a temp
  `registry.global.json`; `refresh-state` re-synced it; and `status` from a
  directory without `.goal-harness/registry.json` fell back to that global
  registry and showed `state_refreshed -> codex`
- Real sync: merged a private local registry and the latest zero-start project
  registry into the shared local global registry
- Default global status: `python3 -m goal_harness.cli --runtime-root
  <runtime-root> --format json status --scan-path README.md --scan-path docs`
  returns the global registry path, 6 goals, and 3 attention items
- Browser smoke: dashboard loaded `/status.local.json` generated from the
  global registry and showed the zero-start project as `state_refreshed`
- `HOME=$(mktemp -d) SHELL=/bin/zsh CODEX_HOME=<tmp> scripts/install-local.sh`
  creates both the CLI wrapper and `goal-harness-project` skill symlink
- `scripts/install-local.sh` on the current machine reports a local
  `goal-harness-project` skill install path
- `HOME=$(mktemp -d) SHELL=/bin/zsh scripts/install-local.sh` now validates the
  installed wrapper with `goal-harness doctor`
- `goal-harness status` for the local multi-project registry shows a newly
  connected zero-start project as `unregistered_runtime_goal` with controller
  readiness gates, while watch-only legacy runtime records remain out of the
  attention queue
- `HOME=$(mktemp -d) SHELL=/bin/zsh scripts/install-local.sh` writes the
  `export PATH="$HOME/.local/bin:$PATH"` shell profile block and the installed
  wrapper passes `goal-harness doctor`
- `goal-harness archive-runtime --goal-id orphan-goal` against a synthetic
  runtime returns `dry_run=true` and leaves the source directory in place
- `goal-harness archive-runtime --goal-id orphan-goal --execute` moves the
  synthetic runtime directory under `<runtime-root>/archived-goals/`
- `goal-harness archive-runtime --goal-id registered-goal` rejects a synthetic
  registry member unless `--allow-registered` is explicitly supplied
- `goal-harness archive-runtime --goal-id zero-start-project-goal` dry-runs a
  current unregistered runtime goal cleanup without moving files
- `goal-harness connect --goal-doc docs/GOAL.md` records
  `authority_sources[0].path == "docs/GOAL.md"` in the registry and renders
  `Primary goal document: docs/GOAL.md` in the initial state
- `goal-harness registry` renders `authorities=1` for a goal connected with a
  primary goal document
- Browser smoke: load the dashboard with `/status.local.json`, select
  `tiger-team-maiduidui-regauc`, and verify the queue gate hints plus next
  handoff condition are visible
- Browser smoke: load the React dashboard from a loopback `statusUrl`, click
  `Dry-run Check`, and verify the reward panel shows `validated` with
  `appended=false`
- `docs/dashboard-reward-write-boundary.md` is linked from README, integration,
  status contract, and experiment-controller milestone docs
- `goal-harness --registry ~/.codex/goal-harness/registry.global.json --format
  json status` run from a private project directory returns `ok=true`,
  `contract.summary.errors=0`, and `global_registry.summary.findings=0`
- Synthetic refresh dry-runs prove a public `## Next Action` line becomes the
  compact `recommended_action`, while an internal-document URL line is skipped
  in favor of the next public-safe action
- Real premium refresh at `2026-06-01T18:01:37+08:00` now shows the concrete
  GZXMT evidence-template action in global status and dashboard local JSON

## Guards

- Do not copy private registry entries, project paths, document links, task ids,
  credentials, or raw run payloads into public examples.
- Keep runtime data local; commit only sanitized docs, source, and examples.
- Prefer small, verified public-facing changes over broad rewrites.
