---
status: active-read-only
owner_mode: goal
objective: "Keep Goal Harness focused on reducing operator coordination load across multi-project agent work"
updated_at: 2026-06-03T16:45:58+08:00
---

# Goal Harness Meta Goal

## Objective

Keep the public Goal Harness project healthy enough that another local Codex
thread can bootstrap a goal, inspect registry and run history, check public
boundary safety, and render a first-screen status queue without relying on any
private project context.

The core product goal is not to add more automation for its own sake. Goal
Harness should reduce the operator's coordination load by turning each project
line into a manageable project asset with a visible owner, gate, next action,
stop condition, user todo, agent todo, quota, review packet, and latest
validation signal. Features that do not reduce human relay work, improve state
truth, or make project agents easier to guide should be downgraded.

The corresponding design principle is dual anti-overload: the human operator
should not have to read every project-agent thread, relay every packet, or
repeatedly restate context; project agents should not have to ingest stale,
redundant, or low-actionability history before finding the current truth.
Goal Harness should preserve the full valid evidence trail in archival layers
while exposing compact current state, so humans provide high-value decisions
and agents receive the smallest sufficient execution context.

## Current Scope

- Keep `scripts/install-local.sh`, `goal-harness bootstrap`,
  `goal-harness check`, `goal-harness status`, `goal-harness archive-runtime`,
  and `goal-harness serve-status` runnable from a fresh clone.
- Keep docs and examples aligned with the current CLI surface.
- Keep public examples sanitized: no local user paths, private documents,
  credentials, raw logs, or internal task identifiers.
- Treat project-specific adapters as private until their contract is generic
  enough to document publicly.
- Keep status, dashboard, and packets centered on the small set of
  cognitive-load reducers: user todos, agent todos, gates, quota, review
  packets, and project status aggregation.
- Keep human-facing and agent-facing surfaces distinct: user views optimize
  for decision novelty, while agent handoffs optimize for current authority,
  executable next steps, validation context, and explicit stop conditions.
- Keep owner blockers as first-class project-asset state: a quiet project
  should say whether it needs new evidence, an owner decision, a clean
  baseline, or target-agent execution before delivery resumes.
- Treat presentation/docs work as a secondary track: it may explain the system,
  but it should not drive core implementation ahead of the control-plane loop.

## Agent Todo

- [x] [P1-high] Collect 3-5 sanitized aha moments from connected Goal
  Harness-managed project lines for the internal/share narrative. Each example
  should show the previous operator relay burden, the owner/gate/next
  action/reward/todo change after Goal Harness, and the safe evidence surface
  that can be shown without private details.

## Next Action

- The live `goal-harness-hourly-tick` heartbeat automation now uses the
  generated heartbeat prompt branch with `notify_user_on_open_todo`, while
  preserving its 4-minute schedule and current thread target. Next, observe the
  next automatic tick for prompt-shape regressions; if stable, rotate focus
  away from blocker-push plumbing toward target-project dry-run/handoff
  readiness.

## Recent Progress

- 2026-06-03T16:45:58+08:00: Steering audit candidates were: P0 update the
  live heartbeat automation to the generated blocker-push prompt now that the
  local automation config was discoverable, P0 add another runtime/code fixture,
  P0 wait for target project dry-run signals, and P1 dashboard polish.
  Continuation check: this was the final blocker-push plumbing slice; it still
  won because the previous public code and runtime fixture would not affect
  future scheduled heartbeats until the live automation prompt was updated.
  No-progress self-stop check: not triggered because recent turns produced
  commits, validation, and runtime/config artifacts. Bounded output: updated
  Codex App automation `goal-harness-hourly-tick` through the automation API,
  preserving `RRULE:FREQ=MINUTELY;INTERVAL=4`,
  `target_thread_id=019df419-5681-7331-b628-ed206f675b8d`, `status=ACTIVE`, and
  replacing the hand-written body with the generated prompt branch that includes
  global-registry quota guard, `goal-harness doctor`, `notify_user_on_open_todo`,
  blocker-push `NOTIFY`, current-status authority, product bottleneck lens,
  no-progress self-stop, and autonomous public-safe publication boundaries.
  Validation: local automation TOML `rg` confirmed `notify_user_on_open_todo`,
  `goal-harness doctor`, `registry.global.json`,
  `RRULE:FREQ=MINUTELY;INTERVAL=4`, and the preserved thread id; `goal-harness
  --format json check --scan-root .` passed with public boundary scan clean. A
  temporary Python heredoc validation helper failed due to shell quoting, but it
  was redundant with the direct TOML/config checks. Critic: the live automation
  is now synced, so further blocker-push plumbing should stop unless the next
  tick shows a prompt-shape regression. Losing candidate: target-project dry-run
  signals remain high-value and should come back into focus after this sync.
- 2026-06-03T16:41:40+08:00: Steering audit candidates were: P0 update the
  live heartbeat automation to use the generated blocker-push prompt, P0 add a
  sanitized runtime fixture proving the new blocker-push path end to end, P0
  wait for target project dry-run signals, and P1 dashboard/browser polish.
  Continuation check: this was another blocker-push slice, but continuing
  still won because it validated the exact runtime behavior introduced by the
  previous commit rather than adding another presentation layer. No-progress
  self-stop check: not triggered because recent heartbeats produced commits,
  validation, and public artifacts; this turn added a new executable fixture.
  Bounded output: added `examples/blocker-push-runtime-smoke.py`, which builds a
  temporary sanitized registry/runtime/state, keeps a goal in `focus_wait` via
  registry attention, exposes one open owner/user todo, and verifies the real
  CLI path `status -> quota should-run -> heartbeat-prompt` produces
  `notify_user_on_open_todo=true`, `state=focus_wait`, no `agent_command`, and
  a generated no-spend blocker-push `NOTIFY` branch. Validation: `python3
  examples/blocker-push-runtime-smoke.py`, `python3 -m py_compile
  examples/blocker-push-runtime-smoke.py`, `goal-harness --format json check
  --scan-root .`, `git diff --check`, and changed-diff sensitive-pattern scan
  passed. Critic: this is safer than blindly editing the live automation
  because the app automation view did not return a machine-readable full config
  to preserve schedule/thread fields; the live automation update is still the
  next operational step. Losing candidate: target-project dry-run signals
  remain high-value but must arrive from the target project context.
- 2026-06-03T16:34:56+08:00: Steering audit candidates were: P0 generated
  heartbeat/status blocker-push behavior for open owner/user todos, P0 wait for
  target project dry-run signals, P1 dashboard/browser polish, and P2 dreaming
  proposal work. Continuation check: this was another focus-wait / blocker
  slice, but continuing still won because the previous slices made the blocker
  visible while the generated automation path still lacked a data-backed signal
  telling heartbeat agents to notify instead of silently skipping or spending
  delivery compute. No-progress self-stop check: not triggered because recent
  heartbeats produced committed artifacts, validation signals, and concrete
  public control-plane surfaces. Bounded output: `quota should-run` now emits
  `notify_user_on_open_todo=true` plus `open_todo_notify_reason` for
  non-operator-gate waiting lanes such as `focus_wait`, generic waiting, and
  external-evidence waits when open user todos can unlock progress; the
  generated heartbeat prompt now turns that payload into a compact no-spend
  blocker-push `NOTIFY`; and the new-project prompt, skill, README, quota,
  status, and todo contracts document the same behavior. Changed files:
  `goal_harness/quota.py`, `goal_harness/heartbeat_prompt.py`,
  `goal_harness/project_prompt.py`, `examples/heartbeat-prompt-smoke.py`,
  `examples/quota-plan-smoke.py`, `examples/quota-contract-smoke.py`,
  `examples/project-prompt-smoke.py`, `README.md`,
  `docs/heartbeat-automation-prompt.md`, `docs/quota-allocation.md`,
  `docs/status-data-contract.md`, `docs/project-agent-todo-contract.md`,
  `docs/new-project-codex-prompt.md`, and
  `skills/goal-harness-project/SKILL.md`. Validation: `python3
  examples/heartbeat-prompt-smoke.py`, `python3 examples/quota-plan-smoke.py`,
  `python3 examples/quota-contract-smoke.py`, `python3
  examples/project-prompt-smoke.py`, `python3 examples/status-markdown-smoke.py`,
  `python3 -m py_compile goal_harness/quota.py
  goal_harness/heartbeat_prompt.py goal_harness/project_prompt.py
  examples/heartbeat-prompt-smoke.py examples/quota-plan-smoke.py
  examples/quota-contract-smoke.py examples/project-prompt-smoke.py`,
  `goal-harness --format json check --scan-root .`, `git diff --check`, and a
  changed-diff sensitive-pattern scan passed. Critic: this closes the public
  generator/data-contract gap, but the live heartbeat automation may still need
  to be refreshed or fixture-checked so future ticks inherit the generated
  blocker-push branch rather than only this thread's current prompt. Losing
  candidate: target-project dry-run signals remain high-value but must arrive
  from the target project context.
- 2026-06-03T16:20:57+08:00: Steering audit candidates were: P0 dashboard
  action packet / first-screen presentation for `focus_wait` owner blockers,
  P0 generated heartbeat/status blocker-push prompts, P0 target-project dry-run
  signals, and P1 browser-level fixture hardening. Continuation check: this was
  the third focus-wait-related delivery slice, but continuing still won because
  quota and Review Packet already carried the state while the dashboard
  operator path still made quiet Codex-owned goals look generically actionable.
  No-progress self-stop check: not triggered because recent heartbeats produced
  committed artifacts, validation, and concrete user/agent surfaces. Bounded
  output: dashboard quota labels now include `Focus wait`; first-screen action
  cards render `focus_wait` as a `Focus wait owner blocker` card with an owner
  blocker callout; the copy affordance says `Copy Focus Packet`; and the copied
  packet is status/history-only, with no approved handoff, operator-gate draft,
  or read-only map delivery path. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `apps/dashboard/smoke/action-packet-smoke.ts`,
  `examples/review-packet-smoke.py`, and `docs/status-data-contract.md`.
  Validation: `npm --prefix apps/dashboard run smoke:action-packet`,
  `npm --prefix apps/dashboard run build`, `python3
  examples/review-packet-smoke.py`, `python3 examples/review-packet-cli-smoke.py`,
  `goal-harness --format json check --scan-root .`, `git diff --check`,
  changed-diff sensitive-pattern scan, and an in-app browser check against a
  sanitized loopback `focus-wait-owner-blocker` fixture all passed. Critic:
  this closes the dashboard visibility gap, but blocker-push behavior is still
  mostly encoded in the live automation prompt; the public generated heartbeat
  path should learn the same compact NOTIFY policy. Losing candidate:
  target-project dry-run signals remain high-value but must arrive from the
  target project context.
- 2026-06-03T16:10:38+08:00: Steering audit candidates were: P0 Review Packet
  focus-wait owner-blocker presentation, P1 dashboard card/action-packet
  presentation for the same state, P0 target project dry-run signals, and P1
  communication polish. Continuation check: this follows the previous
  focus-wait and blocker-priority slices, but it is the first implementation
  of owner-blocker presentation in a concrete user/agent surface rather than
  another state-only update, so continuing still won. No-progress self-stop
  check: not triggered because recent turns produced commits, validation, and
  concrete contract artifacts, and this slice produced a Review Packet fixture.
  Bounded output: added `focus_wait` Review Packet kind detection from quota
  state, a human section that surfaces the first owner/user todo as an unlock
  condition, and an agent handoff that only permits status/history inspection
  while keeping `focus_wait` until new owner evidence, a clean baseline, or
  external eval changes the state. Changed files:
  `goal_harness/review_packet.py`, `examples/review-packet-cli-smoke.py`, and
  `docs/status-data-contract.md`. Validation: `python3
  examples/review-packet-cli-smoke.py`, `python3 examples/review-packet-smoke.py`,
  `python3 -m py_compile goal_harness/review_packet.py
  examples/review-packet-cli-smoke.py`, `npm --prefix apps/dashboard run
  smoke:action-packet`, `goal-harness --format json check --scan-root .`, `git
  diff --check`, and changed-diff sensitive-pattern scan passed. Critic: this
  makes the owner blocker visible in CLI Review Packet and handoff-only paths,
  but dashboard cards still need the same explicit focus-wait affordance.
  Losing candidate: target project dry-run signals remain high-value but are
  still outside this public control-plane repo.
- 2026-06-03T16:04:37+08:00: User feedback promoted blocker-pushing to a core
  control-plane goal: Goal Harness should not merely avoid noisy updates; it
  should surface the smallest owner question when an owner blocker can unlock a
  project line. Public-safe writeback: updated the active goal state so owner
  blockers are first-class project-asset state, and changed Next Action toward
  a sanitized dashboard / Review Packet fixture for focus-wait plus owner
  blocker prompts. Validation: state-only update; no private project details
  were added to the public repo. Critic: this records the priority but still
  needs a public implementation slice that renders the blocker in the user and
  agent surfaces.
- 2026-06-03T16:01:19+08:00: Steering audit candidates were: P0
  focus-eligibility state/safety because real multi-project observation showed
  a Codex-owned line can remain compute-eligible after its current delivery
  lane is saturated, P0 wait for target project dry-run signals, P1 dashboard
  presentation for quiet/watch states, and P1 communication polish.
  Continuation check: previous slices were handoff/onboarding/status cleanup;
  continuing control-plane state still won because this was a different P0
  gap in allocation safety, not another handoff-only polish pass. No-progress
  self-stop check: not triggered because recent heartbeats produced commits,
  validation, and concrete artifacts, and this slice produced a public
  quota/status contract patch. Bounded output: added `focus_wait` to quota
  ordering and should-run behavior, deriving it from
  `lifecycle_phase=focus_wait` or `continuation_boundary` flags when
  `waiting_on=codex`; status queue enrichment now passes lifecycle fields into
  quota derivation, and stale eligible queue payloads are overridden when they
  carry the focus-wait marker. Changed files: `goal_harness/quota.py`,
  `goal_harness/status.py`, `examples/quota-plan-smoke.py`,
  `docs/quota-allocation.md`, and `docs/status-data-contract.md`. Validation:
  `python3 examples/quota-plan-smoke.py`, `python3 -m py_compile
  goal_harness/quota.py goal_harness/status.py examples/quota-plan-smoke.py`,
  `goal-harness --format json check --scan-root .`, `git diff --check`, and
  changed-file sensitive-pattern scan passed. Critic: this cleanly separates
  compute quota from delivery focus, but dashboard and Review Packet copy still
  need to make `focus_wait` obvious to humans and project agents. Losing
  candidate: target project dry-run signals remain high-value but still depend
  on the target project context rather than this public control-plane slice.
- 2026-06-03T15:49:44+08:00: Steering audit candidates were: P0 new-project
  agent prompt anti-overload because `new-project-prompt` was a fresh consumer
  that did not mention `review-packet --handoff-only`, P0 wait for target
  project dry-run signals, P0 observe the platform-migration controller loop
  per new user feedback, and P1 communication polish. Continuation check:
  recent handoff-only slices should pause unless a new consumer still exposes
  redundant context; `new-project-prompt` qualified because new project agents
  could otherwise reconstruct current state from old chat, old packets, or
  `run_history.latest_runs`. No-progress self-stop check: not triggered because
  recent eligible heartbeats produced commits and validation, and this slice
  produced a public generator/docs/test patch. Bounded output: updated
  `goal_harness/project_prompt.py`, `docs/new-project-codex-prompt.md`, and
  `examples/project-prompt-smoke.py` so newly connected project agents are told
  to use `goal-harness review-packet --goal-id <goal> --handoff-only` when
  handing off current packet or approved command, and to treat
  `attention_queue.items` / `project_asset` as current authority rather than
  old chat, old review packets, or `run_history.latest_runs`. Validation:
  `python3 examples/project-prompt-smoke.py`, `python3 -m py_compile
  goal_harness/project_prompt.py examples/project-prompt-smoke.py`, `git diff
  --check`, `goal-harness --format json check --scan-root .`, and changed-file
  sensitive-pattern scan passed. Critic: this closes a newly found onboarding
  prompt consumer without expanding dashboard/CLI scope; the newest user
  feedback says the next focus should shift to observing actual
  platform-migration controller operation and multi-project takeover priority.
  Losing candidate: target project dry-run signals remain high-value, but
  broad takeover prioritization now has fresher user value.
- 2026-06-03T15:43:28+08:00: Steering audit candidates were: P0 stale-current
  cleanup for a public commit-readiness manifest that still described a
  "current public dirty tree" after the tree had already been published, P0
  wait for the target project agent dry-run signal, P0 inspect another
  status/dashboard consumer only if a fresh mismatch appears, and P1
  communication polish. Continuation check: recent delivery slices consumed the
  handoff-only topic, so continuing that topic lost unless a new consumer
  exposed redundant handoff content; the stale manifest won as a different
  dual anti-overload bottleneck because it preserved useful history while
  preventing future agents from treating old readiness guidance as current
  execution context. No-progress self-stop check: not triggered because recent
  eligible heartbeats produced commits, validation, and concrete relay/UX
  artifacts, and this slice produced a real public doc-state correction.
  Bounded output: retitled `docs/commit-readiness-manifest-20260603.md` as a
  closed historical snapshot and added current-use instructions requiring
  `git status`, latest commit, Goal Harness check, and active state before
  acting on historical clusters. Changed files:
  `docs/commit-readiness-manifest-20260603.md`,
  `goals/goal-harness-meta/ACTIVE_GOAL_STATE.md`; the corresponding private
  state was updated outside the public repo. Validation: `git diff --check`,
  `goal-harness --format json check --scan-root .`, and changed-file
  sensitive-pattern scan passed. Critic: this removes a concrete stale-context
  hazard with minimal churn; residual risk is that older public docs may still
  contain historical language, so future cleanup should be evidence-triggered
  rather than a broad documentation sweep. Losing candidate: target-side
  dry-run remains high-value but must come from the target project agent
  context.
- 2026-06-03T15:38:01+08:00: Steering audit candidates were: P0 dashboard
  copy-path ergonomics for the newly added handoff-only rule, P0 wait for the
  target project agent dry-run signal, P0 inspect another consumer only if a
  fresh stale-current mismatch appears, and P1 communication polish. Continuation
  check: this was another handoff-overload slice, but it was the front-end
  operator path counterpart to the previous CLI slice and closed a real user
  experience bottleneck: dashboard users should not copy a human gate wrapper to
  a target agent after approval. No-progress self-stop check: not triggered
  because recent eligible heartbeats produced commits, validation, and concrete
  UX/CLI artifacts. Bounded output: added dashboard `Copy Handoff` behavior for
  approved Codex actions carrying `agent_command`; its copied payload is the
  target goal guard, compact context rule, forwarding condition, execution
  boundary, stop condition, and command, without the `GH Packet` or
  `用户/Gate` wrapper. Changed files:
  `apps/dashboard/src/data/action-packet.ts`,
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `apps/dashboard/smoke/action-packet-smoke.ts`,
  `examples/dashboard-operator-gate-browser-smoke.mjs`, and
  `docs/status-data-contract.md`. Validation: `npm --prefix apps/dashboard run
  smoke:action-packet`, `npm --prefix apps/dashboard run build`,
  `node examples/dashboard-operator-gate-browser-smoke.mjs`,
  `goal-harness --format json check --scan-root .`, `git diff --check`, and
  changed-file sensitive-pattern scan all passed. Critic: this closes the
  dashboard side of the handoff-only feature, but it still does not produce a
  target-side dry-run result; further same-topic work should pause unless a new
  consumer still exposes redundant handoff content. Losing candidate:
  communication polish remains useful, but front-end and CLI anti-overload
  paths were still P0.
- 2026-06-03T15:26:23+08:00: Steering audit candidates were: P0
  project-agent execution ergonomics by extracting a minimal approved handoff
  from Review Packet output, P0 wait for the target project agent dry-run
  signal, P0 audit another status/dashboard consumer only if a fresh
  current-truth mismatch appears, and P1 communication/polish now that the
  control loop is more stable. Continuation check: recent slices were all
  about current authority and handoff; continuing still won because this slice
  converted a real relay-friction observation into a reusable CLI affordance
  rather than another private packet. No-progress self-stop check: not
  triggered because recent eligible heartbeats produced commits, validation, or
  a concrete relay artifact, and this turn produced a public CLI feature.
  Bounded output: added `review-packet --handoff-only`, which prints only
  `project_agent_handoff` in markdown output and keeps the full JSON payload
  with `handoff_only=true` plus `handoff_text`; updated the installed skill and
  docs so project agents can use the minimal handoff without reading the human
  decision wrapper. Changed files: `goal_harness/cli.py`,
  `examples/review-packet-cli-smoke.py`, `examples/install-local-smoke.py`,
  `docs/status-data-contract.md`, `docs/integration.md`, and
  `skills/goal-harness-project/SKILL.md`. Validation:
  `python3 examples/review-packet-cli-smoke.py`,
  `python3 examples/install-local-smoke.py`,
  `python3 examples/project-agent-adoption-smoke.py`, `python3 -m py_compile
  goal_harness/cli.py examples/review-packet-cli-smoke.py
  examples/install-local-smoke.py`, `goal-harness --format json check
  --scan-root .`, `git diff --check`, and changed-file sensitive-pattern scan
  all passed. Critic: this directly advances dual anti-overload for humans and
  agents, but it still stops before target-side execution; the next new signal
  should be a target agent dry-run result or a different independent P0
  bottleneck. Losing candidate: communication polish remains useful but should
  wait until the target-side execution loop is less manual.
- 2026-06-03T15:19:39+08:00: Steering audit candidates were: P0 real
  adapter-proof handoff for the controller-ready project line, P0 audit another
  concrete status consumer only if a fresh mismatch appears, P1 communication
  artifact polish using the now-stable control loop, and P2 no-progress guard
  tuning. Continuation check: recent slices already closed the current-authority
  split across quota, Review Packet, and dashboard, so continuing consumer
  audits lost. The chosen step moved to the highest-value P0 handoff while
  preserving the explicit boundary not to touch the target project repository.
  No-progress self-stop check: not triggered because recent eligible heartbeats
  produced committed artifacts or validation signals, and this turn produced a
  validated private relay artifact. Bounded output: generated the live
  `agent-harness-main-control` Review Packet from the global Goal Harness
  status and recorded the current `【给项目 Agent】` block as an approved relay
  artifact in private state. Validation: `goal-harness --format json
  review-packet --goal-id agent-harness-main-control` asserted
  `kind=codex`, `waiting_on=codex`, `status=operator_gate_approved`,
  `operator_gate_approved_handoff=true`, no local gate dry-run command, no
  decision-command drafts, and the approved project-agent command. Critic: this
  is a real handoff artifact rather than another fixture, but it deliberately
  stops before executing in or reading the target project; the next useful
  signal must come from that target-side dry-run or another independent P0
  slice. Losing candidate: communication polish can wait because the control
  loop still has a target-side execution gap.
- 2026-06-03T15:14:52+08:00: Steering audit candidates were: P0 dashboard
  action-selection audit for the current-routing-authority split, P0 real
  adapter-proof handoff for a controller-ready project line, P1 communication
  artifact polish using the now-stable control loop, and P2 no-progress guard
  tuning. Continuation check: this was another state-truth slice, but it covered
  the last first-screen hot-path consumer after quota and Review Packet. It won
  because the dashboard is the operator's primary action surface; if it were
  driven by stale `run_history.latest_runs`, the user could still see an old
  approval gate instead of the current approved handoff. No-progress self-stop
  check: not triggered because recent eligible heartbeats produced committed
  artifacts or validation signals, and this turn produced a browser-level
  regression smoke. Bounded output: updated
  `examples/dashboard-operator-gate-browser-smoke.mjs` with a fixture where the
  current `attention_queue` item is `operator_gate_approved` /
  `waiting_on=codex` with an approved `agent_command`, while
  `run_history.latest_runs` deliberately remains `operator_gate_deferred`.
  Validation: `node examples/dashboard-operator-gate-browser-smoke.mjs` passed;
  `npm --prefix apps/dashboard run build` passed with the existing large-chunk
  warning; `goal-harness --format json check --scan-root .` passed with
  warnings=0 and a clean public boundary scan over 82 files; `git diff --check`
  passed. Critic: this closes the three main hot-path current-authority
  consumers without changing dashboard logic, but it is still fixture-based and
  should not expand into more UI tests unless a new mismatch appears. Losing
  candidate: real adapter-proof handoff is now the strongest next candidate.
- 2026-06-03T15:09:08+08:00: Steering audit candidates were: P0 Review Packet
  consumer audit for the current-routing-authority split, P0 dashboard
  action-selection audit, P0 real adapter-proof handoff for a controller-ready
  project line, and P2 no-progress guard tuning. Continuation check: this was
  adjacent state-truth work after the quota guard smoke, but it moved to a
  separate hot-path consumer that can directly package instructions for a
  project agent. Continuing won because a stale Review Packet could re-ask an
  old gate or omit the approved `agent_command` even when the current queue is
  ready. No-progress self-stop check: not triggered because recent eligible
  heartbeats produced committed artifacts or validation signals, and this turn
  produced a bounded regression smoke. Bounded output: updated
  `examples/review-packet-cli-smoke.py` with
  `assert_attention_queue_drives_approved_handoff_over_stale_history`, a
  fixture where `run_history.latest_runs` still looks
  `operator_gate_deferred` while the current `attention_queue` item is
  `operator_gate_approved` / `waiting_on=codex` and carries the approved
  `agent_command`. Validation: `python3 examples/review-packet-cli-smoke.py`
  passed; `python3 -m py_compile goal_harness/review_packet.py
  examples/review-packet-cli-smoke.py` passed; `goal-harness --format json
  check --scan-root .` passed with warnings=0 and a clean public boundary scan
  over 82 files; `git diff --check` passed. Critic: this protects the
  project-agent handoff surface without changing Review Packet logic, but
  dashboard action selection still needs comparable regression coverage.
  Losing candidate: real adapter-proof handoff remains high-value, but should
  not jump ahead of the remaining state-truth consumer audit unless the queue
  needs an immediate handoff.
- 2026-06-03T15:02:47+08:00: Steering audit candidates were: P0 actual consumer
  audit for `quota should-run`, P0 Review Packet consumer audit, P0 dashboard
  action-selection audit, P0 real adapter-proof handoff for a controller-ready
  project line, and P2 no-progress guard tuning. Continuation check: this is a
  third adjacent state-truth slice, but it moved from documentation/generator
  hardening to the most important actual consumer: the heartbeat quota guard.
  Continuing won because a wrong `quota should-run` decision would still
  silently block approved work or re-ask stale gates. No-progress self-stop
  check: not triggered because recent eligible heartbeats produced committed
  artifacts or validation signals, and this turn produced a bounded regression
  smoke. Bounded output: updated `examples/quota-plan-smoke.py` with
  `assert_attention_queue_overrides_stale_run_history`, a fixture where
  run history still looks like an operator gate while the current attention
  queue is `operator_gate_approved` / `waiting_on=codex` / eligible with an
  agent command. Validation: `python3 examples/quota-plan-smoke.py` passed;
  `python3 -m py_compile goal_harness/quota.py examples/quota-plan-smoke.py`
  passed; `goal-harness --format json check --scan-root .` passed with
  warnings=0 and a clean public boundary scan over 82 files; `git diff --check`
  passed. Critic: this locks the highest-risk consumer without broad code
  churn, but it is still one consumer; Review Packet and dashboard selection may
  need the same explicit regression coverage. Losing candidate: real
  adapter-proof handoff remains high-value, but should wait until the current
  routing split is proven through the hot-path consumers.
- 2026-06-03T14:59:00+08:00: Steering audit candidates were: P0 heartbeat
  prompt consumer-hardening for the new routing-authority split, P0 actual
  project-local pre-tick consumer audit, P0 real adapter-proof handoff for a
  controller-ready project line, P1 dashboard duplicate-burden audit, and P2
  no-progress guard tuning. Continuation check: this continued state-truth work
  for one more slice because the previous patch only documented the contract;
  generated automations still needed to carry the rule so future heartbeats do
  not regress into `run_history.latest_runs` as the current gate source.
  No-progress self-stop check: not triggered because recent eligible heartbeats
  produced committed artifacts or validation signals, and this turn produced a
  bounded generator/docs/test patch. Bounded output: updated
  `goal_harness/heartbeat_prompt.py`, `docs/heartbeat-automation-prompt.md`,
  and `examples/heartbeat-prompt-smoke.py` so generated heartbeat task bodies
  tell agents to use `attention_queue.items` / `project_asset` as current
  routing authority and treat `run_history.latest_runs` as evidence only.
  Validation: `python3 examples/heartbeat-prompt-smoke.py` passed; `python3 -m
  py_compile goal_harness/heartbeat_prompt.py
  examples/heartbeat-prompt-smoke.py` passed; `goal-harness --format json
  check --scan-root .` passed with warnings=0 and a clean public boundary scan
  over 82 files; `git diff --check` passed. Critic: this is the right
  follow-up to the contract patch because it changes future agent behavior, not
  only documentation; residual risk is that existing already-created
  automations or private pre-tick scripts may still need separate updates.
  Losing candidate: actual consumer audit remains high-value and should not be
  forgotten.
- 2026-06-03T14:54:45+08:00: Steering audit candidates were: P0 state/safety
  contract gap after a project-local pre-tick consumer was found to rely on a
  limited latest-run slice; P0 real adapter-proof handoff for a controller-ready
  project line; P0 dashboard duplicate-burden audit; P1 dashboard polish; and
  P2 no-progress guard tuning. Continuation check: recent slices consumed
  packet/todo parity focus, so continuing that topic lost unless a fresh
  mismatch appeared. The chosen step fixed the generic state-truth contract
  instead: consumers must route from current `attention_queue.items` /
  `project_asset`, not from truncated `run_history.latest_runs`. No-progress
  self-stop check: not triggered because recent eligible heartbeats produced
  committed artifacts or validation signals, and this turn produced a public
  contract patch. Bounded output: updated `docs/status-data-contract.md` with
  the current-routing-authority rule. Validation: initial `goal-harness check`
  failed only because an isolated shell lacked the preflight PATH; rerun with
  `export PATH="$HOME/.local/bin:$PATH"` passed with warnings=0 and a clean
  public boundary scan over 82 files; `git diff --check` passed; `rg` confirmed
  the new contract text. Critic: this is a small but important anti-overload
  fix because it protects agents from stale evidence while preserving the
  historical evidence surface; residual risk is that some existing consumers
  may still need an audit for this split. Losing candidate: the dashboard
  duplicate-burden audit remains useful, but should wait behind state-truth
  consumers.
- 2026-06-03T14:44:04+08:00: Steering audit candidates were: P0 duplicate
  dashboard packet/panel surface audit, P0 status Markdown versus project-asset
  packet parity, P0 state/safety public-boundary check, P1 dashboard polish, and
  P2 no-progress guard tuning. Continuation check: recent slices consumed
  packet/card anti-overload focus, so continuing only won after the duplicate
  dashboard check found the old `Operator Review Packet`/`Copy Review Packet`
  surface already forbidden by browser smoke and the status Markdown audit found
  a concrete hot-path mismatch: `project_asset` exposed todo counts but not the
  first open user/agent todo text. No-progress self-stop check: not triggered
  because recent eligible heartbeats produced committed artifacts and validation
  signals, and this turn produced a bounded status Markdown parity patch.
  Bounded output: updated `goal_harness/status.py` so Markdown project-asset
  blocks render `asset_user_todo` and `asset_agent_todo` from compact
  `project_asset.*_todos.next`; updated `examples/status-markdown-smoke.py` and
  `docs/status-data-contract.md` to lock and document that hot-path readers get
  the current todo without scanning detailed sections. Validation: `python3
  examples/status-markdown-smoke.py` passed; `python3 -m py_compile
  goal_harness/status.py examples/status-markdown-smoke.py` passed;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and
  a clean public boundary scan over 82 files; `git diff --check` passed.
  Critic: this is a precise anti-overload fix and keeps archival todo detail in
  the colder top-level fields, but this topic has now had enough adjacent
  slices; the next turn should shift away unless it finds a fresh concrete
  mismatch. Losing candidate: a true dashboard detail-vs-first-screen duplicate
  burden audit remains useful, but should be chosen only with a visible
  duplication finding.
- 2026-06-03T12:39:40+08:00: Steering audit candidates were: P0 CLI Review
  Packet parity with the dashboard GH packet for user/agent todo visibility and
  context-source boundaries, P0 duplicate packet/panel surface audit, P0
  status markdown versus packet parity, P1 dashboard polish, and P2
  no-progress guard tuning. Continuation check: this is the third consecutive
  packet/card anti-overload slice, but it covered a separate formatter:
  dashboard copied packets had just gained compact agent todo context while CLI
  `goal-harness review-packet` still generated an independent packet without
  user/agent todos. Continuing won because target agents can receive the CLI
  packet directly, so leaving it stale would preserve the context-overload gap.
  No-progress self-stop check: not triggered because recent eligible heartbeats
  produced committed artifacts and validation signals, and this turn produced a
  bounded CLI formatter parity patch. Bounded output: updated
  `goal_harness/review_packet.py` so it pulls compact user/agent todo text from
  `project_asset.*_todos.next` with fallback to full todo groups, adds user todo
  to the human decision section, adds `Agent 待办` to the project-agent handoff,
  and exposes `user_todo_text` / `agent_todo_text` in JSON output; updated
  `examples/review-packet-cli-smoke.py` to lock both controller and approved
  handoff packets while preserving the read-only/no-runtime-write boundary.
  Validation: `python3 examples/review-packet-cli-smoke.py` passed; `python3 -m
  py_compile goal_harness/review_packet.py
  examples/review-packet-cli-smoke.py` passed; `python3
  examples/project-agent-adoption-smoke.py` passed; `python3
  examples/review-packet-smoke.py` passed; `goal-harness --format json check
  --scan-root .` passed with warnings=0 and a clean public boundary scan over
  82 files; `git diff --check` passed. Critic: this closes the CLI/dashboard
  packet parity gap without expanding packet length with archival context, but
  duplicate packet/panel affordances may still be noisier than needed. Losing
  candidate: duplicate packet/panel surface audit should not be forgotten.
- 2026-06-03T12:34:04+08:00: Steering audit candidates were: P0 user/agent
  todo visibility across status JSON, dashboard cards, and copied packets; P0
  CLI Review Packet parity with the dashboard GH packet; P1 dashboard polish;
  and P2 no-progress guard tuning. Continuation check: recent slices touched
  dashboard first-screen metadata, but this was not another visual polish pass:
  status JSON already exposed `agent_todos`, while the dashboard card and copied
  GH packet only surfaced user todos, leaving target agents to dig through
  status/history for the next safe agent todo. Compute quota allowed another
  run, but focus quota chose this concrete P0 mismatch over broader UI work.
  No-progress self-stop check: not triggered because recent eligible heartbeats
  produced committed artifacts and validation signals, and this turn produced a
  bounded packet/card visibility patch. Bounded output: updated
  `apps/dashboard/src/data/action-packet.ts` and
  `apps/dashboard/src/views/dashboard-page.tsx` so the first open agent todo is
  visible in copied GH packets and action-card metadata; updated
  `apps/dashboard/smoke/action-packet-smoke.ts`,
  `examples/dashboard-operator-gate-browser-smoke.mjs`, and
  `examples/review-packet-smoke.py` to lock the behavior. Validation: `python3
  examples/review-packet-smoke.py` passed; `npm --prefix apps/dashboard run
  smoke:action-packet` passed; `node
  examples/dashboard-operator-gate-browser-smoke.mjs` passed; `npm --prefix
  apps/dashboard run build` passed with the existing Vite large-chunk warning;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and
  a clean public boundary scan over 82 files; `git diff --check` passed.
  Critic: this keeps agent todo context to one line and avoids another panel,
  which supports dual anti-overload; residual risk is that CLI
  `goal-harness review-packet` has a separate formatter and still needs a
  parity audit. Losing candidate: CLI Review Packet parity should not be
  forgotten.
- 2026-06-03T12:28:31+08:00: Steering audit candidates were: P0 dashboard
  first-screen burden and compact `project_asset` projection, P0 user/agent
  todo visibility across status/dashboard/packets, P0 project-agent handoff
  context diet, P1 dashboard polish, and P2 no-progress guard tuning.
  Continuation check: recent slices touched dashboard/status wording and
  project-agent handoff copy, but the previous Next Action explicitly called
  for applying the dual anti-overload lens to the dashboard first screen; this
  turn therefore fixed one concrete first-screen state-truth gap instead of
  adding a new panel. No-progress self-stop check: not triggered because recent
  eligible heartbeats produced committed artifacts and validation signals, and
  this turn produced a bounded dashboard projection patch. Bounded output:
  updated `apps/dashboard/src/data/status.ts` and
  `apps/dashboard/src/views/dashboard-page.tsx` so action summary cards can
  render compact Validation metadata from `project_asset.latest_validation`;
  updated `examples/dashboard-operator-gate-browser-smoke.mjs` and
  `examples/review-packet-smoke.py` to lock the first-screen source and
  rendered text. Validation: `python3 examples/review-packet-smoke.py` passed;
  `node examples/dashboard-operator-gate-browser-smoke.mjs` passed; `npm
  --prefix apps/dashboard run build` passed with the existing Vite large-chunk
  warning; `goal-harness --format json check --scan-root .` passed with
  warnings=0 and a clean public boundary scan over 82 files; `git diff --check`
  passed. Critic: this fills the latest-validation first-screen gap without
  making the dashboard louder; residual risk is that the browser smoke uses a
  fixture rather than a live operator screenshot, so the next slice should avoid
  UI churn and inspect user/agent todo visibility or duplicate packet/panel
  surfaces. Losing candidate: user/agent todo visibility remains the next
  high-value anti-overload candidate.
- 2026-06-03T12:22:40+08:00: Steering audit candidates were: P0 project-agent
  handoff context diet, P0 user/agent todo visibility across status and
  dashboard, P0 dashboard first-screen burden, P1 dashboard polish, and P2
  no-progress guard tuning. Continuation check: recent slices touched several
  dashboard/status wording surfaces, but the user's newest product constraint
  made agent context diet a distinct P0 surface, so this turn chose the
  handoff packet instead of another visual-polish pass. No-progress self-stop
  check: not triggered because recent eligible heartbeats produced committed
  artifacts and validation signals, and this turn produced a bounded packet
  contract patch. Bounded output: updated `goal_harness/review_packet.py` and
  `apps/dashboard/src/data/action-packet.ts` so CLI Review Packets and
  dashboard copied packets tell target project agents to treat the packet as
  minimal current instruction and, when context is needed, read current active
  state/status/history plus command output rather than old chats or old
  packets; updated `docs/status-data-contract.md`,
  `examples/review-packet-cli-smoke.py`,
  `examples/project-agent-adoption-smoke.py`, and
  `apps/dashboard/smoke/action-packet-smoke.ts` to lock that contract.
  Validation: `python3 examples/review-packet-cli-smoke.py` passed; `python3
  examples/project-agent-adoption-smoke.py` passed; `python3 -m py_compile
  goal_harness/review_packet.py examples/review-packet-cli-smoke.py
  examples/project-agent-adoption-smoke.py` passed; `npm --prefix
  apps/dashboard run smoke:action-packet` passed; `goal-harness --format json
  check --scan-root .` passed with warnings=0 and a clean public boundary scan
  over 82 files; `git diff --check` passed. Critic: this improves agent
  handoff context hygiene without adding more hot-path content, but it does not
  yet verify whether the dashboard first screen is compact enough for humans.
  Losing candidate: dashboard first-screen burden remains the next visible
  dual anti-overload candidate.
- 2026-06-03T12:13:42+08:00: Manual product clarification from the user
  upgraded the anti-overload goal from "avoid overwhelming the user" to two
  coupled requirements: protect human attention from redundant notifications
  and protect project agents from stale/redundant context, while preserving all
  valid information in archival evidence layers. State-only writeback updated
  the Objective, Current Scope, and Next Action to make human attention diet and
  agent context diet both P0 criteria. Validation: state patch only; public and
  private `git diff --check` should be run before commit or refresh. Critic:
  this records the product target, but the next delivery slice must still
  inspect one concrete status/dashboard/handoff surface and fix the first real
  mismatch. Losing candidate: generic dashboard polish remains lower priority
  than context-layering for both humans and agents.
- 2026-06-03T12:01:10+08:00: Steering audit candidates were: P0 product
  bottleneck/prioritization rule gap for autonomous goal ticks, P0 user/agent
  todo visibility across status JSON/markdown/dashboard, P1 dashboard visual
  polish, and P2 no-progress guard tuning. Continuation check: recent slices
  fixed quota/defaults/approved handoff/status-markdown micro-contracts; after
  the user asked whether Goal Harness can discover core UX/capability
  bottlenecks and adjust priorities, another local copy fix would be the wrong
  focus. No-progress self-stop check: not triggered because recent eligible
  heartbeats produced committed artifacts and validation signals, and this turn
  produced a reusable heartbeat-lifecycle contract patch. Bounded output:
  updated `goal_harness/heartbeat_prompt.py`,
  `docs/heartbeat-automation-prompt.md`,
  `skills/goal-harness-project/SKILL.md`,
  `docs/state-interaction-model.md`, and
  `examples/heartbeat-prompt-smoke.py` so every generated heartbeat steering
  audit must include a product bottleneck lens over user experience, agent
  capability, evidence quality, adapter readiness, and priority-rule gaps, and
  may promote one concrete bottleneck above the nearest local TODO. Validation:
  `python3 examples/heartbeat-prompt-smoke.py` passed; `python3 -m py_compile
  goal_harness/heartbeat_prompt.py examples/heartbeat-prompt-smoke.py` passed;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and
  a clean public boundary scan over 82 files; `git diff --check` passed.
  Critic: this makes bottleneck discovery part of the reusable lifecycle, but
  it does not itself solve the next UX/capability bottleneck; the next slice
  should apply the lens to one visible project-asset surface. Losing candidate:
  dashboard visual polish remains useful but should be chosen only after the
  lens confirms whether the first-screen burden is the top bottleneck.
- 2026-06-03T11:54:05+08:00: Steering audit candidates were: P0 status-markdown
  project-asset ownership wording, P0 user/agent todo visibility across status
  JSON/markdown/dashboard, P1 dashboard visual polish, and P2 no-progress guard
  tuning. Continuation check: the last two slices consumed approved-handoff
  focus, so this turn left that topic and chose status-markdown project-asset
  truth. No-progress self-stop check: not triggered because recent eligible
  heartbeats produced committed artifacts and validation signals, and this turn
  produced a bounded status-markdown contract fix. Bounded output: updated
  `goal_harness/status.py` so attention queue markdown emits
  `asset_next_action` from `project_asset.next_action`, keeping owner/gate/stop
  and next action together for Markdown consumers; updated
  `examples/status-markdown-smoke.py` to assert planned operator-gate and
  registry-override fixtures expose that line. Validation: `python3
  examples/status-markdown-smoke.py` passed; `python3 -m py_compile
  goal_harness/status.py examples/status-markdown-smoke.py` passed;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and
  a clean public boundary scan over 82 files; `git diff --check` passed.
  Critic: this is a small Markdown state-truth fix, not a broader product
  bottleneck audit; after the user's latest feedback, the next slice should
  explicitly test whether Goal Harness can discover UX/capability bottlenecks
  instead of only following local next-action mismatches. Losing candidate:
  dashboard visual polish remains lower priority than a reusable bottleneck
  discovery/prioritization rule.
- 2026-06-03T11:47:50+08:00: Steering audit candidates were: P0 compare CLI
  Review Packet approved-command copy with the dashboard copied action packet,
  P0 state-only status recheck, P1 dashboard visual polish, and P2 no-progress
  guard tuning. Continuation check: the prior slice fixed the visible approved
  action card, but the copied action packet was a separate project-agent
  handoff surface and still used generic Codex safe-path wording, so one more
  approved-boundary slice won; focus should now leave this topic. No-progress
  self-stop check: not triggered because recent eligible heartbeats produced
  committed artifacts and validation signals, and this turn produced a bounded
  dashboard packet fix. Bounded output: updated
  `apps/dashboard/src/views/dashboard-page.tsx` so copied action packets for
  Codex-ready rows with an approved `agent_command` say to directly forward the
  approved command, use an `Approved agent command` path label, and state the
  read-only/dry-run boundary instead of generic safe-path approval copy; updated
  `examples/review-packet-smoke.py` to lock that source branch and sanitized
  packet shape. Validation: `python3 examples/review-packet-smoke.py` passed;
  `python3 examples/review-packet-cli-smoke.py` passed; `node
  examples/dashboard-operator-gate-browser-smoke.mjs` passed; `npm --prefix
  apps/dashboard run build` passed with the existing Vite large-chunk warning;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and
  a clean public boundary scan over 82 files; `git diff --check` passed.
  Critic: this finishes the approved-command copy alignment without widening
  UI scope; the next slice should not remain on approved handoff unless a fresh
  mismatch appears. Losing candidate: P1 visual polish remains lower priority
  than first-screen state truth.
- 2026-06-03T11:37:09+08:00: Steering audit candidates were: P0 compare
  dashboard action-card wording with `quota should-run` for operator-gate versus
  Codex-ready handoffs, P0 state-only status recheck, P1 dashboard visual
  polish, and P2 no-progress guard tuning. Continuation check: recent slices
  were quota-related, so switching to approved-command handoff wording avoided
  another quota pass while staying on P0 state truth. No-progress self-stop
  check: not triggered because recent eligible heartbeats produced committed
  artifacts and validation signals, and this turn produced a bounded dashboard
  handoff fix. Bounded output: updated `apps/dashboard/src/views/dashboard-page.tsx`
  so Codex-ready rows with an approved `agent_command` render as `Run approved
  agent command` / `Approved handoff` and use the `run_approved_agent_command`
  reward hint instead of generic continuation copy; updated
  `examples/dashboard-operator-gate-browser-smoke.mjs` to assert the pending
  gate and approved handoff states remain visually and semantically distinct.
  Validation: `node examples/dashboard-operator-gate-browser-smoke.mjs` passed;
  `npm --prefix apps/dashboard run build` passed with the existing Vite
  large-chunk warning; `goal-harness --format json check --scan-root .` passed
  with warnings=0 and a clean public boundary scan over 84 files; `git diff
  --check` passed. Critic: this fixes one first-screen handoff wording mismatch
  without broad UI polish; review-packet copy still deserves the next
  comparison against the same approved-command boundary. Losing candidate: P1
  visual polish remains lower priority than status/action wording truth.
- 2026-06-03T11:33:22+08:00: Steering audit candidates were: P0 dashboard/status
  consistency for quota, user todo, and gate fields; P0 state-only status
  recheck; P1 dashboard visual polish; and P2 no-progress guard tuning.
  Continuation check: the previous slice clarified quota preview semantics, so
  continuing into dashboard quota display still won because it checked a
  separate user-visible surface rather than adding more quota docs. No-progress
  self-stop check: not triggered because the recent eligible heartbeats
  produced committed artifacts and validation signals, and this turn produced a
  bounded dashboard parser fix. Bounded output: updated
  `apps/dashboard/src/data/status.ts` so missing `allowed_slots` is derived as
  `window_hours * 60 * compute / slot_minutes` instead of defaulting to `24`,
  preserved `slot_minutes` in the parsed quota payload, and added
  `examples/dashboard-quota-default-browser-smoke.mjs` to verify the dashboard
  renders `Eligible; 12/720 slots` for a half-duty fixture without explicit
  `allowed_slots`. Validation: `node
  examples/dashboard-quota-default-browser-smoke.mjs` passed; `npm --prefix
  apps/dashboard run build` passed with the existing Vite large-chunk warning;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and
  a clean public boundary scan over 89 files; `git diff --check` passed.
  Critic: this is a narrow contract fix rather than UI polish; the next slice
  should compare gate/handoff wording instead of staying on quota. Losing
  candidate: P1 visual polish remains lower priority than first-screen state
  truth.
- 2026-06-03T11:26:23+08:00: Steering audit candidates were: P0 quota
  preview/status truth after the latest spend showed a same-window projection
  while later status stayed flat, P0 state/status truth check only, P1
  dashboard or quickstart polish, and P2 no-progress guard tuning. Continuation
  check: recent slices focused on publication policy, so switching to quota
  state truth was the higher-value P0 lane. No-progress self-stop check: not
  triggered because recent eligible heartbeats produced commits, validation
  evidence, and this turn produced a public quota contract artifact. Bounded
  output: updated `goal_harness/quota.py` so `quota spend-slot` preview
  markdown includes a rolling-window note, updated `docs/quota-allocation.md`
  to explain that before -> after is a same-status-payload projection while
  later status recomputes `spent_slots` from events inside `window_hours`, and
  extended `examples/quota-plan-smoke.py` with a regression where an older
  spend expires as a newer spend remains counted. Validation: `python3
  examples/quota-plan-smoke.py` passed; `python3 -m py_compile
  goal_harness/quota.py examples/quota-plan-smoke.py` passed; `goal-harness
  --format json check --scan-root .` passed with warnings=0 and a clean public
  boundary scan over 88 files; `git diff --check` passed. Critic: the ledger
  algorithm was already correct, but the operator-facing preview needed an
  explicit note to prevent misreading `spent_slots` as a monotonic counter.
  Losing candidate: dashboard polish remains useful and should become the next
  state-truth candidate rather than another quota-doc pass.
- 2026-06-03T11:16:33+08:00: Steering audit candidates were: P0 sync the
  autonomous public publish policy into the reusable heartbeat lifecycle
  generator/docs/skill, P0 state/status truth check only, P1 dashboard or
  quickstart polish, and P2 advanced no-progress guard tuning. Continuation
  check: recent slices included packaging hygiene, but this turn fixed a policy
  regression after the user clarified public commit/push/PR should not be a
  standing gate; it was not another packaging detail pass. No-progress self-stop
  check: not triggered because recent eligible heartbeats produced commits,
  validation evidence, and this reusable contract artifact. Bounded output:
  updated `goal_harness/heartbeat_prompt.py`,
  `docs/heartbeat-automation-prompt.md`,
  `skills/goal-harness-project/SKILL.md`, `README.md`, `docs/integration.md`,
  and `examples/heartbeat-prompt-smoke.py` so public-safe commit, push, and PR
  creation can proceed autonomously after validation and a clean public/private
  boundary scan, while private/company material, credentials, destructive git,
  production actions, and explicit repo rules still stop on a gate. Validation:
  `python3 examples/heartbeat-prompt-smoke.py` passed; `python3 -m py_compile
  goal_harness/heartbeat_prompt.py examples/heartbeat-prompt-smoke.py` passed;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan over 88 files; `git diff --check` passed. Critic:
  the lifecycle should now stop asking the user about public-safe publication,
  but the next heartbeat should move to another P0/P1 control-plane slice to
  avoid over-documenting the same policy. Losing candidate: dashboard polish
  remains useful but lower priority than correcting the reusable publish gate.
- 2026-06-03T11:08:34+08:00: Published the validated public dirty tree to
  GitHub on `main` as `628aae4 Improve heartbeat lifecycle and dashboard
  actions`. Validation before publication covered 18 smoke scripts, heartbeat
  prompt/status/user-todo/contract smoke tests, dashboard build, dashboard
  reward append browser smoke, public boundary check, targeted sensitive scan,
  and diff checks. Bounded output: public commit and push completed; this
  state-only writeback moves Next Action away from packaging hygiene. Critic:
  publication is complete, so the next heartbeat should pick a new bounded P0/P1
  control-plane improvement rather than revalidating the same tree.
- 2026-06-03T11:06:50+08:00: Publication validation passed for the current
  public Goal Harness dirty tree after the autonomous publish policy update.
  Validation: `python3 examples/run-smokes.py` passed 18 smoke scripts;
  `python3 examples/heartbeat-prompt-smoke.py`, `python3
  examples/status-markdown-smoke.py`, `python3
  examples/user-todo-review-material-smoke.py`, and `python3
  examples/contract-reward-overlay-smoke.py` passed; `npm --prefix
  apps/dashboard run build` passed with the existing Vite chunk-size warning;
  `node examples/dashboard-reward-append-browser-smoke.mjs` passed;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan over 88 files; public and private `git diff
  --check` passed; targeted sensitive-pattern scan over candidate files
  produced no findings. Changed files: public source/docs/examples/state plus
  the local-private CS-Notes state. Critic: the tree is safe to commit and push
  to GitHub under the updated public daily iteration policy.
- 2026-06-03T11:05:02+08:00: User clarified the publish boundary again:
  public daily iteration can autonomously commit, push, and create PRs as long
  as no sensitive or company-internal information is involved. The old rule
  that commit/push/PR creation required explicit operator intent was too
  conservative for the public Goal Harness repo. Bounded output: updated
  `docs/commit-readiness-manifest-20260603.md`, this active state, and the
  local-private CS-Notes active state to allow autonomous public publishing
  after clean boundary scans and validation. Validation will be rerun before
  publishing the current dirty tree. Critic: this reduces unnecessary user
  gating while preserving the hard stop on private/company-internal material.
- 2026-06-03T11:02:00+08:00: User corrected the previous packaging boundary:
  asking whether to continue packaging as a User Todo was too conservative.
  The correct gate is narrower: commit, push, and PR creation require explicit
  operator intent, but ordinary heartbeat planning should not ask the operator
  whether packaging should continue. Bounded output: removed the just-added
  packaging User Todo and updated Next Action so future heartbeats move to a
  different bounded P0/P1 control-plane slice unless the operator explicitly
  asks for commit/PR packaging. Validation: follow-up `rg`, `goal-harness
  check`, and diff checks confirm the User Todo is gone and the public boundary
  remains clean. Critic: this fixes a coordination mistake; over-gating is its
  own form of user burden.
- 2026-06-03T11:00:50+08:00: Steering audit candidates were: P0 convert the
  commit/PR packaging decision into a dashboard-visible User Todo, P0 run
  another state/health recheck, P1 dashboard/demo polish, and P2 no-progress
  guard hardening. Continuation check: commit-readiness has consumed recent
  slices, so the right next move was to stop hiding the remaining operator
  decision in Next Action rather than add more packaging detail. Compute quota
  remained eligible; focus quota now shifts away from packaging until the user
  answers. No-progress self-stop check: not triggered because recent eligible
  heartbeats produced public artifacts, validation evidence, and this user-todo
  writeback. Bounded output: used `goal-harness todo add` to add an open User
  Todo asking whether to request commit/PR packaging for the validated dirty
  tree, with instructions to use
  `docs/commit-readiness-manifest-20260603.md` and re-run minimum validation if
  the operator says yes. Validation: `goal-harness todo add --help` confirmed
  the public todo command surface; `rg` confirmed the new User Todo and updated
  timestamp in this state. Changed files: this active state and the
  local-private CS-Notes active state. Critic: this makes the remaining human
  decision first-class in status/dashboard, but no code or packaging was
  changed. Losing candidate: dashboard polish remains parked because an open
  packaging decision should not be buried under more UI expansion.
- 2026-06-03T10:56:57+08:00: Steering audit candidates were: P0
  public-sensitive diff review and staging plan, P0 state/health recheck only,
  P1 dashboard/demo polish, and P2 no-progress guard hardening. Continuation
  check: commit-readiness has consumed recent slices, but this was the
  requested post-validation safety review and staging boundary, not another
  status loop or feature expansion. Compute quota remained eligible; focus
  quota favored release hygiene over new UI work. No-progress self-stop check:
  not triggered because recent eligible heartbeats produced public artifacts,
  validation evidence, and this manifest writeback. Bounded output: appended a
  `Public-Sensitive Diff Review` section to
  `docs/commit-readiness-manifest-20260603.md` covering 13 modified tracked
  files, 5 untracked candidate files, a no-finding sensitive scan, and the
  recommended staging order. Validation: `git status --short`, `git diff
  --name-status`, `git ls-files --others --exclude-standard`, and `git diff
  --stat` characterized the dirty tree; targeted `rg` sensitive scan found no
  private path, internal URL, company-doc marker, sensitive assignment,
  auth-header pattern, or cloud-key pattern in candidate files. Changed files: the
  public manifest, this active state, and the local-private CS-Notes active
  state. Critic: the tree is now safer to stage on request, but no commit/push
  should happen without explicit operator intent and final validation must be
  rerun after hunk staging. Losing candidate: dashboard polish remains parked
  until commit boundaries are accepted or staged.
- 2026-06-03T10:53:49+08:00: Steering audit candidates were: P0 run the
  manifest minimum final validation, P0 public-sensitive diff review, P1
  dashboard/demo polish, and P2 no-progress guard hardening. Continuation
  check: commit-readiness has taken several slices, but this was the validation
  half of the manifest checkpoint and directly reduced release risk without
  expanding the dirty tree. No-progress self-stop check: not triggered because
  recent eligible heartbeats produced public artifacts and this turn produced a
  new validation writeback. Bounded output: updated
  `docs/commit-readiness-manifest-20260603.md` with the final validation run
  result. Validation: `python3 examples/run-smokes.py` passed 18 smoke scripts;
  `python3 examples/heartbeat-prompt-smoke.py`,
  `python3 examples/status-markdown-smoke.py`,
  `python3 examples/user-todo-review-material-smoke.py`, and
  `python3 examples/contract-reward-overlay-smoke.py` passed; `npm --prefix
  apps/dashboard run build` passed with the existing Vite chunk-size warning;
  `node examples/dashboard-reward-append-browser-smoke.mjs` passed;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan over 86 files; public `git diff --check` passed.
  Changed files: the public manifest, this active state, and the local-private
  CS-Notes active state. Critic: the dirty tree is now grouped and validated,
  but no commit or push was attempted because the operator has not asked for
  release packaging. Losing candidate: dashboard polish remains parked until
  commit boundaries are accepted or staged.
- 2026-06-03T10:49:00+08:00: Steering audit candidates were: P0 public dirty
  tree commit-readiness manifest, P0 health/status recheck, and P1
  dashboard/demo polish. Continuation check: checkpoint-only mode is gone, and
  the previous Next Action explicitly asked to turn the public dirty tree into
  reviewable commit boundaries; producing the manifest was real delivery, not a
  repeated status check. No-progress self-stop check: the last 5 eligible
  heartbeats included state/automation/prompt policy changes and a public
  prompt-generator artifact, so this was not a 5-turn no-progress loop and the
  automation was not cancelled. Bounded output: added public
  `docs/commit-readiness-manifest-20260603.md`, grouping the dirty tree into
  four clusters: first-run/heartbeat lifecycle contract,
  runtime/status/contract truth, user-todo review-material reader, and dashboard
  reward append flow. The manifest lists candidate files, remaining validation,
  public/private boundary risks, files that must stay out of commits, and the
  minimum final validation commands. Validation: `rg` confirmed the four
  cluster sections, Do Not Commit, and Minimum Final Validation sections;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan over 84 files; `git diff --check` passed for both
  the public repo and the private state repo. Changed files: the public
  manifest, this active state, and the local-private CS-Notes active state.
  Critic: the manifest reduces dirty-tree coordination load, but the full final
  validation suite has not been rerun from the manifest yet. Losing candidate:
  dashboard polish was deferred to avoid expanding the dirty tree before commit
  boundaries are reviewable.
- 2026-06-03T10:44:00+08:00: Steering audit candidates were: P0 move the
  5-run no-progress self-stop guard into the public heartbeat prompt generator,
  P0 public dirty tree commit-readiness manifest, and P1 dashboard/demo polish.
  Continuation check: checkpoint-only mode was removed by the user, and the
  previous turn only updated the local automation/state policy; publicizing the
  guard in the generator lets other project heartbeats reuse it and directly
  reduces unattended spinning, so it beat switching immediately to the commit
  manifest. No-progress self-stop check: the last 5 eligible heartbeats were not
  all no-progress loops because 10:38/10:40 changed automation/state policy and
  this turn produced a public artifact, so the automation was not cancelled.
  Bounded output: updated public `goal_harness/heartbeat_prompt.py` so generated
  heartbeat task bodies run the no-progress self-stop check after steering
  audit; synchronized `docs/heartbeat-automation-prompt.md`,
  `skills/goal-harness-project/SKILL.md`, and
  `examples/heartbeat-prompt-smoke.py`. Validation: `python3
  examples/heartbeat-prompt-smoke.py` passed; `python3 -m py_compile
  goal_harness/heartbeat_prompt.py examples/heartbeat-prompt-smoke.py` passed;
  `python3 -m compileall -q goal_harness` passed; `goal-harness --format json
  check --scan-root .` passed with warnings=0 and a clean public boundary scan
  over 83 files; `git diff --check` passed for both the public repo and the
  private state repo. Critic: this is the public
  productization of the user's usability feedback; the next useful slice should
  turn the current public dirty tree into a commit-readiness manifest so
  ungrouped changes stop growing. Losing candidate: dashboard/demo polish is
  allowed again, but release/commit hygiene currently reduces coordination load
  more.
- 2026-06-03T10:38:00+08:00: The user explicitly removed the hard constraint
  that said not to continue quickstart/demo/dashboard functionality unless PR or
  release packaging was requested, and proposed a 5-consecutive-no-progress
  automation self-stop guard. Steering audit candidates were: P0 remove stale
  stop constraint, P0 automation no-progress self-stop, and P1 resume concrete
  product/packaging lane. Continuation check: the previous checkpoint-only mode
  had started to confuse the operator, so keeping it would harm Goal Harness
  usability. Bounded output: Next Action now tells future heartbeats to choose a
  real bounded delivery slice from the Priority Stack; the next step is to
  update the `goal-harness-hourly-tick` automation prompt with the 5-run
  no-progress self-stop rule. Validation: this state patch will be followed by
  automation update, `goal-harness check --scan-root .`, both-repo `git diff
  --check`, and state refresh. Critic: this is a product-policy correction, not
  a feature push; the self-stop guard should stop genuine spinning without
  killing small but material state-safety fixes. Losing candidate:
  manager-facing talk track remains parked until explicitly requested.
- 2026-06-03T10:40:00+08:00: After `refresh-state`, the long Next Action was
  truncated in the displayed recommended action, so this tick shortened the
  current Next Action while preserving the three required facts: checkpoint-only
  mode is removed, the next heartbeat should choose a real bounded P0/P1/P2
  delivery slice, and the heartbeat prompt now carries the 5-run no-progress
  self-stop guard.
- 2026-06-03T10:35:00+08:00: Steering audit candidates were: P0
  clarification checkpoint, P0 health-blocker diagnosis, P0 state hygiene
  rollup, and P1 manager-facing talk track. Continuation check: recent
  heartbeats had intentionally stayed on clean checkpoints, but the user's
  "why not continue?" question showed that the stop/continue boundary needed to
  be written back into state rather than left only in chat. Bounded output: no
  public implementation changes; recorded the user-visible explanation and
  updated Next Action to state the exact conditions for continuing. Validation:
  global status returned `ok=true`, goal_count=6, run_count=537, attention
  queue still has 4 items (`agent-harness-main-control`, `goal-harness-meta`,
  `premium-ui-ai-search-rec-migration`, `tiger-team-maiduidui-regauc`),
  contract errors=0/warnings=0, and global findings=0; the public-repo
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan over 83 files; `git diff --check` passed for both
  the public repo and the private state repo. Changed files: this active state
  and the local-private CS-Notes active state only. Critic: this was a needed
  explanatory checkpoint, not a feature push; if the user explicitly says to
  continue, first choose either PR/release packaging or a new concrete cut from
  state. Losing candidate: manager-facing talk track remains parked until the
  user explicitly switches back to share-draft work.
- 2026-06-03T05:06-10:31+08:00: Steering audit candidates were: P0 brief
  status check, P0 health-blocker diagnosis, P0 state hygiene rollup, and P1
  manager-facing talk track. Continuation check: the last five heartbeats had
  recorded the same clean status check, so another duplicate ledger row would
  increase cognitive load without improving state truth. Because status stayed
  clean, this tick compacted those repeated clean-check entries into one
  checkpoint. Bounded output: no public implementation changes; state hygiene
  only, with the next action kept on the same quiet status-check lane.
  Validation: global status returned `ok=true`, goal_count=6, run_count=535,
  attention queue still has 4 items (`agent-harness-main-control`,
  `goal-harness-meta`, `premium-ui-ai-search-rec-migration`,
  `tiger-team-maiduidui-regauc`), contract errors=0/warnings=0, and global
  findings=0; the public-repo `goal-harness --format json check --scan-root .`
  passed with warnings=0 and a clean public boundary scan over 83 files; `git
  diff --check` passed for both the public repo and the private state repo. The
  rechecks from 05:12 through 10:31 stayed clean, so no detailed ledger row was added.
  Changed files: this active state and the local-private CS-Notes active state
  only. Critic: future heartbeats should avoid expanding the ledger for clean
  status checks; record detail only when health, gates, packaging state, or
  validation materially changes, and keep public boundary scans scoped to the
  public repo rather than private workspaces. Losing candidate: manager-facing talk track
  remains parked until the user explicitly switches back to share-draft work.
- 2026-06-03T04:42:00+08:00: Steering audit candidates were: P0 state
  freshness check, P0 health-blocker diagnosis, and P1 manager-facing talk
  track. Continuation check: release/quickstart polish was already closed, and
  the previous next action explicitly said to do only a lightweight state
  freshness check when there is no user packaging request; this beat adding
  functionality. Bounded output: cleaned one stale shared-runtime demo residue.
  `goal-harness status` showed an unregistered runtime goal `demo-goal` had
  re-entered the global attention queue, causing `health_blockers=1`. Ran
  `goal-harness archive-runtime --goal-id demo-goal` as the built-in dry-run and
  confirmed it would only move the unregistered shared runtime directory, then
  executed it to `~/.codex/goal-harness/archived-goals/demo-goal-20260602T204228Z`.
  Changed files: no public implementation changes; moved the shared runtime
  demo directory; updated this active state and the local-private CS-Notes
  active state. Validation: global status attention queue now has 4 items and
  `demo_present=false`; `quota should-run` reports `health_blockers=0`;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan; `git diff --check` passed. Critic: demo/browser
  smokes can still leave runtime residue, so a future commit-readiness manifest
  should list this as residual risk, but current health is clean. Losing
  candidate: manager-facing talk track remains parked until the user explicitly
  asks for share-draft work.
- 2026-06-03T04:38:00+08:00: Steering audit candidates were: P0
  publishability checkpoint, P0 status/contract consistency, and P1
  manager-facing talk track. Continuation check: quickstart/release-readiness
  had consumed several slices, but the previous state asked for exactly one
  dirty-tree checkpoint before stopping; this was closure, not more feature
  polish, and still beat switching to the share draft. Bounded output: no public
  implementation changes. Grouped the public dirty tree into four clusters:
  README first-run docs; state/status/contract truth covering local/global
  runtime, reward-overlay index rows, and status smoke; user-todo review
  material reader covering `goal_harness/materials.py`, status/server,
  dashboard callout, and Python smoke; and dashboard reward append covering the
  dry-run payload lock plus browser append smoke. The single most important
  missing pre-commit validation was the dashboard cluster's production build and
  reward append browser smoke; both were run and passed. Changed files: this
  active state and the local-private CS-Notes active state only. Validation:
  `npm --prefix apps/dashboard run build` passed with only the existing Vite
  chunk-size warning; `node examples/dashboard-reward-append-browser-smoke.mjs`
  passed; the previous slice already had `python3 examples/run-smokes.py`,
  `goal-harness --format json check --scan-root .`, and `git diff --check`
  passing. Critic: publishability checkpoint closes the last quickstart/release
  validation gap; future automatic ticks should not add more release polish
  unless the user asks for PR/release packaging. Losing candidate:
  manager-facing talk track remains valuable, but needs an explicit user switch
  back to share-draft work.
- 2026-06-03T04:31:00+08:00: Steering audit candidates were: P0 public
  release-readiness audit, P0 state/status contract consistency, and P1
  manager-facing talk track. Continuation check: quickstart/demo polish had
  consumed several slices, but the previous state explicitly requested a final
  dirty-tree release audit before switching lanes; doing exactly that closed the
  fresh-user usability lane and still beat share packaging. Bounded output: no
  public implementation changes. Audited the current public dirty tree and the
  README/examples/docs alignment. Found no concrete mismatch that would block a
  willing first-time user from trying Goal Harness. `examples/run-smokes.py` is
  the public dependency-free Python smoke runner and now includes the two new
  Python smoke examples automatically; the browser `.mjs` smoke remains outside
  that runner, which matches the README claims. The reward write API boundary is
  documented by `docs/dashboard-reward-write-boundary.md`. Changed files: this
  active state and the local-private CS-Notes active state only. Validation:
  `python3 examples/run-smokes.py` passed all 18 Python smoke scripts;
  `goal-harness --format json check --scan-root .` passed with warnings=0 and a
  clean public boundary scan; `git diff --check` passed; targeted
  README/docs/examples audit passed; no public/private boundary leak was found.
  Critic: quickstart/release-readiness is good enough; continuing demo or
  dashboard polish would be focus drift. Next useful automatic slice is a
  publishability checkpoint for the dirty tree, not new features. Losing
  candidate: manager-facing talk track remains valuable, but this heartbeat did
  not include a user request to package the share draft.
- 2026-06-03T04:30:00+08:00: Steering audit candidates were: P0 dashboard
  first-screen project-identity verification, P0 release-readiness audit, and
  P1 manager-facing talk track. Continuation check: quickstart polish had
  consumed several slices, but the previous state named exactly one remaining
  verification: confirm the dashboard puts project identity before action text.
  Doing that final check was bounded and directly tied to the user's "project
  is important" feedback, so it still beat switching lanes. Bounded output: no
  public implementation changes. Started a temporary demo `serve-status` on
  port 18765 and dashboard dev server on port 5176, loaded the demo Live URL
  in the in-app browser, and verified the first screen. DOM validation found
  `demo-goal` before the action text (`projectBeforeAction=true`), and the
  screenshot visually showed the card as `Project` / `Selected`, bold
  `demo-goal`, then `Let Codex continue`, with no overlap or truncation.
  Temporary servers were stopped. Changed files: this active state and the
  local-private CS-Notes active state only. Validation: browser DOM snapshot
  and viewport screenshot inspection passed. Critic: the quickstart/demo lane
  now has enough evidence; continuing it would be focus drift. Losing
  candidate: manager-facing talk track remains valuable, but the user has not
  asked to package the share draft in this heartbeat.
- 2026-06-03T04:24:00+08:00: Steering audit candidates were: P0 fresh-user
  README demo/dashboard readthrough, P0 public release/readiness polish, and
  P1 manager-facing talk track. Continuation check: clean-health had just
  closed, and the active next action explicitly named the README demo path; a
  real first-run mismatch would directly hurt open-source usability, so the
  quickstart readthrough still beat switching to share packaging. Bounded
  output: fixed the local/global status mix in the public status layer.
  `collect_history` now accepts `include_runtime_goals`; `collect_status`
  enables runtime orphan discovery only for the global registry view, so a
  project-local/demo registry no longer pulls unrelated shared runtime goals
  into attention queue or quota health. Added a status smoke fixture proving
  project-local status excludes an unregistered runtime orphan and keeps
  `health_blockers=0`. Changed files in this slice: `goal_harness/history.py`,
  `goal_harness/status.py`, `examples/status-markdown-smoke.py`, this active
  state, and the local-private CS-Notes active state. Existing dirty dashboard,
  materials, contract, README, and smoke files were not reverted. Validation:
  `python3 examples/status-markdown-smoke.py` passed; `python3 -m compileall -q
  goal_harness` passed; real `goal-harness demo` passed; demo
  `goal-harness --registry "$registry" status --scan-root "$PWD"` now reports
  `goals=1`, `runs=2`, and one `demo-goal` queue item; demo
  `quota should-run` reports `health_blockers=0`; temporary `serve-status`
  Live JSON assertion passed with only `demo-goal` in queue and run history;
  `python3 examples/demo-cli-smoke.py` passed; `goal-harness --format json
  check --scan-root .` passed with warnings=0; `git diff --check` passed;
  global `goal-harness --format json status` still reports the global view
  (`global_current=true`, `goal_count=7`, `queue_items=5`). Critic: this closes
  the command/status mismatch, but the actual dashboard first screen has not
  yet been visually checked against the cleaned Live JSON. Losing candidate:
  manager-facing talk track remains ready but secondary until the user asks for
  share-draft packaging.
- 2026-06-03T04:12:00+08:00: Steering audit candidates were: P0 clean-health
  status/dashboard validation, P0 fresh-user quickstart readthrough, and P1
  manager-facing talk track. Continuation check: health/state hygiene had
  consumed two recent slices, but after the contract warning fix the
  user-visible status/dashboard layer still needed one clean-health check, so
  this verification still beat switching back to share polish. Bounded output:
  no public implementation changes; validated the clean-health user-facing
  state. Validation: `goal-harness --format json status` asserted
  `contract.summary.warnings=0`, `contract.warnings=[]`, and zero health
  attention items; `npm --prefix apps/dashboard run build` passed with only the
  existing Vite chunk-size warning; `node
  examples/dashboard-throttled-browser-smoke.mjs` passed; `node
  examples/dashboard-operator-gate-browser-smoke.mjs` passed. The first status
  assertion attempt failed because the shell here-doc consumed stdin; rerunning
  the same assertion with `python3 -c` passed. Changed files: this active state
  and the local-private CS-Notes active state only; public implementation files
  were not changed in this slice. Critic: clean-health is now closed enough;
  the next slice should return to fresh-user quickstart usability unless the
  user explicitly asks to package the share draft. Losing candidate:
  manager-facing talk track has a six-image base but remains secondary to P0
  usability.
- 2026-06-03T04:08:00+08:00: Steering audit candidates were: P0 duplicate-index
  warning cleanup, P0 status/dashboard clean-health smoke, and P1
  manager-facing talk track. Continuation check: this was the previous next
  action, and contract health remains P0 state truth/safety, so finishing it
  beat switching back to share polish. Bounded output: identified the
  `goal-harness-meta` duplicate row as an intentional run-bound `human_reward`
  overlay on a prior `state_refreshed` run, not a corrupt duplicate index
  entry. Updated public `goal_harness/contract.py` so duplicate groups that are
  identical except for `human_reward` are recorded as `reward overlay rows`
  checks rather than warnings, while ordinary duplicate rows still warn. Added
  `examples/contract-reward-overlay-smoke.py` to prove both paths: reward
  overlay does not warn; plain duplicate still warns. Changed files:
  `goal_harness/contract.py`, the new smoke example, this active state, and the
  local-private CS-Notes active state. Existing dirty dashboard/status/materials
  files were not part of this slice. Validation: `python3
  examples/contract-reward-overlay-smoke.py` passed; `python3
  examples/reward-append-api-smoke.py` passed; `goal-harness --format json
  check --scan-root .` passed with `warnings=0` and a reward-overlay check;
  `python3 -m compileall -q goal_harness` passed; `git diff --check` passed;
  targeted public-boundary scan passed. Critic: contract health is now clean,
  but the first-screen status/dashboard view has not yet been explicitly
  checked for the clean-health user experience. Losing candidate:
  manager-facing talk track can wait until the user asks to package the share
  draft.
- 2026-06-03T04:01:00+08:00: Steering audit candidates were: P0 split the
  `health_blockers=1` source from the duplicate-index warning, P0 duplicate
  index cleanup, and P1 manager-facing talk track. Continuation check: this was
  the previous next action and state truth/safety beats more quickstart docs or
  share polish. Bounded output: diagnosed the health mismatch and archived the
  disposable demo runtime left by the demo smoke. `status` showed the real
  health blocker was an unregistered runtime-only `demo-goal`, not the
  duplicate-index warning. The goal had one run and was not in the global
  registry. Ran `goal-harness archive-runtime --goal-id demo-goal` dry-run to
  confirm it would only move the shared runtime demo directory, then executed it
  to `~/.codex/goal-harness/archived-goals/demo-goal-20260602T200106Z`.
  Changed files: no public code changed; shared runtime demo directory was
  archived; this active state and the local-private CS-Notes active state were
  updated. Validation: `goal-harness status` attention queue no longer includes
  `demo-goal`; `quota should-run` plan summary reports `health_blockers=0`;
  `goal-harness check --scan-root .` still passes and only reports the
  `goal-harness-meta` duplicate-index warning; archive path exists and the
  source runtime directory is gone. Critic: the status health blocker is gone,
  but the duplicate-index warning still makes contract health look untidy; next
  slice should isolate and fix or explicitly classify that warning. Losing
  candidate: manager-facing talk track can wait until the user asks to package
  the share draft.
- 2026-06-03T03:58:00+08:00: Steering audit candidates were: P0 dashboard
  first-run quickstart checklist, P0 state/health hygiene for the
  `health_blockers=1` / duplicate-index warning, and P1 manager-facing talk
  track. Continuation check: the share/evidence lane is closed, and the
  previous CLI first-run checklist still did not make the dashboard `Live`
  first screen obvious; finishing this P0 quickstart docs gap beat more share
  polish. Bounded output: added a `Dashboard first-run success` checklist under
  README `Try It In 10 Minutes`, covering the demo status server, Vite URL,
  `Live` source, `demo-goal` project id visibility, `User Actions`, actionable
  queue state, and the blank/stale dashboard troubleshooting order. Changed
  files for this slice: public `README.md`, this active state, and the
  local-private CS-Notes active state. Existing dirty dashboard/status/materials
  files were not part of this slice. Validation: `python3
  examples/demo-cli-smoke.py` passed; `git diff --check` passed;
  `goal-harness check --scan-root .` passed with only the known duplicate-index
  warning; README/state targeted boundary scan passed; checklist heading and
  keyword search passed. Critic: this improves first-run docs, but the next
  higher-value P0 step is to explain or clear the `health_blockers=1` /
  duplicate-index warning so status health is trustworthy. Losing candidate:
  manager-facing talk track can wait until the user asks to package the share
  draft.
- 2026-06-03T03:53:00+08:00: Steering audit candidates were: P0 fresh-user
  quickstart usability, P1 assemble the six screenshots into a manager-facing
  talk track, and P0 state/boundary hygiene. Continuation check: the
  share/evidence lane had consumed several recent slices and the six-slot
  evidence set is now closed, so switching back to P0 open-source usability
  beat more share polish. Bounded output: added a first-run success checklist
  under README `Try It In 10 Minutes`, explaining the signals a new user should
  see after `goal-harness demo`: `ok: True`, registry/state bootstrap,
  user/agent todos, refresh-state append, status `waiting_on`, and quota
  eligibility. It also points failed first runs to `goal-harness doctor` before
  project debugging. Changed files for this slice: public `README.md`, this
  active state, and the local-private CS-Notes active state. Existing dirty
  dashboard/status/materials files were not part of this slice. Validation:
  `python3 examples/demo-cli-smoke.py` passed; `git diff --check` passed;
  `goal-harness check --scan-root .` passed with only the known duplicate-index
  warning; README targeted boundary scan passed. Critic: this improves the CLI
  demo first-run path but does not yet make the dashboard Live first run
  equally obvious. Losing candidate: manager-facing talk track can wait until
  the user asks to package the share draft.
- 2026-06-03T03:48:00+08:00: Steering audit candidates were: P1 create the
  remaining two manager-share synthetic evidence panels (read-only-map gate and
  quota/steering), P0 fresh-user quickstart usability, and P1 assemble the
  current four screenshots into the manager-facing talk track. Continuation
  check: the share/evidence lane has consumed several recent slices, but the
  previous critic named exactly two remaining evidence slots; completing them
  closed the six-slot evidence set and created a natural stopping point.
  Bounded output: extended the local-private synthetic evidence HTML with
  read-only-map gate and quota/steering panels, rendered a refreshed full
  screenshot, cropped two clean images, and updated the local-private leader
  draft, intro draft, and redaction plan so the evidence set now contains six
  screenshots. The quota panel uses a stable `slots tracked` label instead of a
  real slot count. Public implementation files did not change. Validation: six
  PNG dimensions checked; the new crops were visually inspected; Markdown image
  paths exist; targeted text and PNG string boundary scans passed; `git diff
  --check` and `goal-harness check --scan-root .` passed with only the known
  duplicate-index warning. Critic: manager-share evidence capture is now
  complete enough; the next slice should either assemble a tighter talk track
  or return to P0 fresh-user quickstart. Losing candidate: fresh-user
  quickstart should be re-raised next.
- 2026-06-03T03:40:00+08:00: Steering audit candidates were: P1 create the
  next two manager-share synthetic evidence panels (`await_eval` and
  run-bound reward), P0 fresh-user quickstart usability, and P1 assemble the
  current screenshots into the leader draft. Continuation check: this remained
  in the leader/share lane, but the previous state explicitly named
  `await_eval` and reward as the remaining evidence gaps; completing that
  bounded evidence set reduced the user's share-prep coordination load more
  directly than switching lanes. Bounded output: extended the local-private
  synthetic HTML with two new panels, rendered a refreshed full screenshot, and
  cropped clean `await_eval` and run-bound reward images. Updated the
  local-private leader draft, intro draft, and redaction plan so the evidence
  set now contains four screenshots. Public implementation files did not
  change. Validation: four PNG dimensions checked; new crops visually
  inspected; targeted text and PNG string boundary scans passed with no local
  paths, private repo/URL markers, token-shaped material, or project-specific
  sensitive terms. Critic: four manager-share screenshots now exist, but the
  read-only-map gate and quota/steering slots are still checklist items.
  Losing candidate: fresh-user quickstart remains important for open-source
  adoption, but finishing the evidence set was the current bounded artifact.
- 2026-06-03T03:24:00+08:00: Steering audit candidates were: P1 visually
  inspect and crop the existing synthetic evidence HTML, P1 create the next
  evidence slots (`await_eval` and reward), and P0 fresh-user quickstart
  usability. Continuation check: this remained in the leader/share lane, but it
  completed the previous turn's explicitly bounded artifact step and avoided
  adding more scope before visual validation. Used Chrome headless to render the
  local-private synthetic HTML, visually inspected the full screenshot, then
  cropped two clean panels: multi-project operator view and user todo +
  review-material. Updated the local-private intro draft and redaction plan with
  the generated image paths. Public implementation files did not change.
  Validation: visual inspection found no private content or layout breakage;
  cropped images are readable; image dimensions and PNG string boundary scan
  passed; text boundary scan passed after generalizing one internal product
  term; `git diff --check` and `goal-harness check --scan-root .` passed with
  only the known duplicate-index warning. Critic: two high-impact
  screenshots now exist, but evidence-waiting and reward slots are still text
  plan only. Losing candidate: fresh-user quickstart remains useful, but
  manager-share evidence capture was the current bounded artifact.
- 2026-06-03T03:19:00+08:00: Steering audit candidates were: P1 create
  sanitized demo evidence for the two highest-impact manager-share slots, P0
  fresh-user quickstart usability, and P1 continue broader evidence slots
  (`await_eval` and reward). Continuation check: this is another leader/share
  slice, but the previous turn explicitly stopped raw screenshots and named the
  safe demo/synthetic step; completing that boundary-preserving step still won
  over switching lanes. Bounded output: created a local-private synthetic HTML
  evidence artifact with two screenshot-ready panels: multi-project operator
  view and user todo + review-material. Updated the local-private intro draft
  and redaction plan to point to the artifact. Public implementation files did
  not change. Validation: synthetic evidence structure check passed; targeted
  boundary scan found no local paths, private repo markers, internal URLs,
  token-shaped material, or project-specific sensitive terms in the HTML.
  Critic: the evidence is now safe and screenshot-ready, but not visually
  inspected or cropped yet. Losing candidate: fresh-user quickstart remains
  important for open-source adoption, but manager-share evidence readiness is
  the active local-private deliverable.
- 2026-06-03T03:13:00+08:00: Steering audit candidates were: P1 capture
  local-private evidence assets for the manager-facing draft, P0 fresh-user
  quickstart usability, and P1 public/demo evidence generation. Chose the
  evidence asset step because the previous slice produced the 3-minute manager
  narrative, but the screenshot/evidence surface was still only a checklist.
  Continuation check: this remains in the leader/share lane for a third slice,
  but it still wins because the work has a clear stop condition and directly
  reduces user preparation load before any Lark/public sync. Inspection of live
  status showed raw screenshots would expose local paths, private goal ids,
  concrete Markdown filenames, and project-specific next-action text, so the
  stop condition fired. Bounded output: created a local-private redaction plan
  with six evidence slots, required redactions, safe alternatives, capture
  rules, validation checklist, and next safe demo-evidence step. Public
  implementation files did not change. Validation: redaction-plan structure is
  present and targeted boundary scan found no obvious concrete private
  paths/internal URLs/token-shaped material. Critic: no screenshots were
  captured, by design; next step should use demo/synthetic evidence for the
  operator-view and user-todo/review-material slots. Losing candidate:
  fresh-user quickstart remains important for open-source adoption, but this
  slice protected the manager-share evidence boundary first.
- 2026-06-03T03:09:00+08:00: Steering audit candidates were: P1 convert the
  collected aha moments into a manager-facing 3-minute version, P0 fresh-user
  quickstart usability, and P1 local screenshot/evidence capture. Chose the
  3-minute version because the prior slice produced story material but not a
  short manager-ready narrative, and this remained the smallest bounded step
  serving the user's latest leader-share priority. Updated the local-private
  internal intro draft with a new manager-facing section: first minute problem,
  second minute control-plane answer, third minute current evidence and next
  milestone, plus a six-item screenshot/evidence checklist and redaction rules.
  Public implementation files did not change. Validation: draft heading numbers
  are sequential, the new 3-minute/evidence sections exist, and a targeted scan
  found no obvious concrete private paths/internal URLs/token-shaped material in
  the local-private draft. Critic: the story and short narrative are now usable,
  but the screenshot/evidence assets are still a checklist rather than captured
  artifacts. Losing candidate: fresh-user quickstart remains important for
  open-source adoption, but it is lower priority than completing the
  manager-share evidence surface.
- 2026-06-03T03:05:00+08:00: Steering audit candidates were: P1 collect
  sanitized project aha moments for the leader/share narrative, P0 fresh-user
  quickstart usability, and P0/P1 dashboard evidence polish. Chose the P1
  collection slice because the prior live material-reader validation closed the
  immediate P0 gap, and the open agent todo explicitly asked for vivid examples
  from managed project lines. Updated the local-private internal intro draft
  with five sanitized aha moments: user-todo review materials, evidence-waiting
  experiment state, read-only map before complex controller handoff, run-bound
  human reward, and quota versus steering/focus. Public implementation files did
  not change. Validation: heading numbering for the local-private draft is
  sequential, the draft has no obvious concrete private paths/internal URLs from
  the targeted scan, `git diff --check` passes, and `goal-harness check
  --scan-root .` passes with only the known duplicate-index warning. Critic: the examples are now story-shaped,
  but they still need a shorter manager-facing version and a screenshot/evidence
  checklist before the draft is presentation-ready. Losing candidate: fresh-user
  quickstart remains valuable for open-source adoption, but the user's latest
  explicit priority is the leader/share draft.
- 2026-06-03T03:01:00+08:00: Steering audit candidates were: P0 live
  connected-goal validation for the new user-todo review-material surface, P1
  sanitized aha-moment collection for the leader/share narrative, and P1
  fresh-user quickstart usability. Continuation check: the previous slice added
  review-material extraction and dashboard rendering, but only synthetic
  coverage existed, so one live connected-goal validation was still the best
  bounded P0 step. Validation result: global `status` projected one open user
  todo with one Markdown review material on a connected private project; a
  temporary loopback `serve-status` instance returned non-empty Markdown content
  through `GET /review-material?goal_id=...&path=...`; an absolute-path read was
  rejected with HTTP 400. No implementation files changed this slice; only goal
  state was updated and the server was stopped. Critic: the local reader path is
  now live-validated, but the next useful product/narrative step is no longer
  more reader polish; resume collecting sanitized aha moments. Losing
  candidate: fresh-user quickstart remains useful, but it is lower priority
  than turning real multi-project control-plane wins into shareable examples.
- 2026-06-03T02:55:00+08:00: User identified a control-plane gap: user todos
  can say that the operator should read key Markdown material, but Goal Harness
  did not make those materials readable from the user todo surface. Bounded
  fix: added `goal_harness/materials.py` to extract backticked/linked Markdown
  references from active-state todo text, resolve them only inside the goal
  repo/state/runtime roots, and cap local reads. Status now adds
  `review_materials` to todo items and renders `review_material` hints in
  status Markdown. `serve-status` now exposes a loopback-only
  `GET /review-material?goal_id=...&path=...` endpoint for local Markdown
  reading. The dashboard schema and User Actions card now preserve
  `review_materials`, show Review material chips under the next user todo, and
  inline-read the Markdown from a live loopback status URL. Added
  `examples/user-todo-review-material-smoke.py`, proving status projection,
  local Markdown read, absolute path rejection, and relative `../` path
  rejection. Validation: `python3 examples/user-todo-review-material-smoke.py`,
  `npm --prefix apps/dashboard run build`, `node
  examples/dashboard-operator-gate-browser-smoke.mjs`, `python3
  examples/reward-append-api-smoke.py`, `node
  examples/dashboard-reward-append-browser-smoke.mjs`, `python3 -m compileall
  -q goal_harness`, `git diff --check`, and `PATH="$HOME/.local/bin:$PATH"
  goal-harness check --scan-root .` pass. Known warnings remain: Vite
  chunk-size warning and duplicate index rows in the global runtime. Changed
  files: dashboard status schema/view, `goal_harness/materials.py`,
  `goal_harness/status.py`, `goal_harness/status_server.py`, the new material
  smoke, this active state, and the private CS-Notes state. Critic: the feature
  is covered synthetically and by dashboard build/browser smoke, but it still
  needs a live connected-goal validation to catch the exact Markdown reference
  shape used in real project user todos. Losing candidate: the aha-moment
  leader/share collection remains high priority and should resume after the
  live material-reader check.
- 2026-06-03T02:41:00+08:00: Steering audit candidates were: P0 dashboard
  reward browser proof, P1 leader/share aha-moment case collection, and P1
  fresh-user quickstart readthrough. Continuation check: reward submission had
  just gained API proof but no browser click proof, so finishing the P0
  human-decision-loop proof still won; the user's new request was captured as a
  high-priority agent todo and promoted to the next action. Bounded fix: added
  `examples/dashboard-reward-append-browser-smoke.mjs`, which starts a temporary
  registry/runtime, serves status with `--enable-reward-write-api`, opens the
  dashboard, clicks Reward dry-run and append, then polls status until the
  selected run exposes `human_reward` and `reward_judged`. The smoke exposed a
  real UI/API mismatch: preview ids included dry-run `recorded_at`, but the
  append request recomputed a new timestamp and failed as stale. Fixed the
  dashboard Reward panel to lock the dry-run request body, including
  `recorded_at`, and reuse that exact payload on append. Validation:
  `node examples/dashboard-reward-append-browser-smoke.mjs`,
  `python3 examples/reward-append-api-smoke.py`,
  `npm --prefix apps/dashboard run build`, `git diff --check`, and
  `PATH="$HOME/.local/bin:$PATH" goal-harness check --scan-root .` pass; build
  still has the known Vite chunk-size warning, and contract check still has the
  known duplicate index rows warning. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/dashboard-reward-append-browser-smoke.mjs`, this active state, and
  the private CS-Notes state. Critic: the browser-level reward loop is now
  proven, but the internal/share narrative still lacks vivid project examples;
  next slice should collect sanitized aha moments instead of adding more UI.
  Losing candidate: the fresh-user quickstart readthrough remains useful, but
  the user's latest priority is richer leader/share examples.
- 2026-06-03T02:08:00+08:00: Steering audit candidates were: P0
  human-decision loop proof, P1 front-end reward submit usability, and P0
  status/agent reward visibility. Chose the proof slice because the user
  suggested mocking human reward on this goal, and the smallest valuable step
  was to prove the existing writer/status stack before adding more UI. A
  mock run-bound reward was appended to `goal-harness-meta` run
  `2026-06-03T01:26:33+08:00` with
  `decision=mock_frontend_reward_capture`, then history/status confirmed
  `human_reward` and `lifecycle_phase=reward_judged`. Existing code inspection
  showed `serve-status --enable-reward-write-api` and the dashboard reward
  panel already support dry-run -> append. Validation:
  `python3 examples/reward-append-api-smoke.py`,
  `npm --prefix apps/dashboard run build`, `git diff --check`, and
  `goal-harness check --scan-root .` pass. Changed files: this active state;
  runtime index gained one explicit mock `human_reward` overlay. Critic: API
  and build coverage are strong, but there is still no browser-level e2e smoke
  that clicks through the dashboard Reward panel and verifies the refreshed
  status; that should be the next bounded proof. Losing candidate: the
  fresh-user quickstart readthrough remains useful, but reward submission is a
  higher-value P0 human-decision-loop proof after the user's feedback.
- 2026-06-03T01:24:55+08:00: Steering audit candidates were: P0
  state/status truth, P1 dashboard docs/operator-copy wording, P1 quickstart
  smoke, and P2 broader dashboard polish. Chose the dashboard docs wording
  slice because the previous turn connected `goal-harness demo` to the
  dashboard, but `apps/dashboard/README.md` still described the old
  `Copy Review Packet` affordance even though the real first-screen cards now
  expose a single `Copy` button and a compact `【GH Packet】`. Bounded fix:
  updated the dashboard README to describe the current card-level `Copy`
  affordance and the short copied handoff contents: user todo, gate, safety
  boundary, safe path, command, and project-agent stop rule. Validation:
  targeted `rg` confirms `Copy Review Packet`, `Operator Review Packet`, and
  old packet names now appear only in
  `examples/dashboard-operator-gate-browser-smoke.mjs` forbidden-text guards;
  `node examples/dashboard-operator-gate-browser-smoke.mjs` passes;
  `git diff --check` and `goal-harness check --scan-root .` pass. Changed
  files: `apps/dashboard/README.md`, this active state, and the private
  CS-Notes state. Critic: this removes the stale docs/UI mismatch, but the
  public quickstart still relies on a readthrough rather than a full fresh-clone
  rehearsal; next slice should audit that flow and fix one concrete mismatch.
- 2026-06-03T01:19:21+08:00: Steering audit candidates were: P0
  state/status truth, P1 fresh-user demo-to-dashboard usability, P1 stale
  dashboard docs/copy wording, and P2 broader dashboard polish. Chose the
  fresh-user demo-to-dashboard slice because `goal-harness demo` created a demo
  goal and printed status/quota commands, but did not show a willing first-time
  user how to inspect the same goal in the dashboard. Bounded fix:
  `goal_harness/demo.py` now prints a `Dashboard Option` with Terminal 1
  `serve-status` commands from the demo project, Terminal 2 dashboard startup
  commands, and the live status URL; `README.md` now tells users the 10-minute
  demo includes that dashboard bridge; `examples/demo-cli-smoke.py` asserts the
  dashboard handoff fields. While validating the public smoke suite, the run
  exposed an old action-packet contract in `examples/review-packet-smoke.py`,
  so that smoke was aligned with the new compact `【GH Packet】` /
  `【用户/Gate】` / `【给项目 Agent】` packet shape. Validation: real
  `goal-harness demo --project /tmp/goal-harness-demo-heartbeat-check`, live
  `serve-status` curl confirming the demo goal appears in
  `attention_queue.items`, `python3 examples/demo-cli-smoke.py`, `python3
  examples/review-packet-smoke.py`, `python3 examples/run-smokes.py` with 15
  smoke scripts, `python3 -m compileall -q goal_harness`, `git diff --check`,
  and `goal-harness check --scan-root .`. Changed files: `README.md`,
  `goal_harness/demo.py`, `examples/demo-cli-smoke.py`,
  `examples/review-packet-smoke.py`, this active state, and the private
  CS-Notes state. Critic: this makes the first demo-to-dashboard path much more
  followable, but it still requires two terminals and npm; next slice should
  align stale dashboard docs/copy wording before considering a one-command
  dashboard helper.
- 2026-06-03T01:09:09+08:00: Steering audit candidates were: P0
  copied-packet length/readability, P0 status/state truth, P1 public first-try
  usability, and P2 broader dashboard cleanup. Continuation check: several
  recent slices stayed on the human-decision loop, but the last critic named
  copied-packet length as the remaining user relay cost, so finishing that
  slice won before pivoting. Bounded fix: shortened
  `buildActionPacket()` into a compact transfer packet: `【GH Packet】`, concise
  goal/status, one `【用户/Gate】` section with todo-before-gate cue, boundary,
  and one `【给项目 Agent】` handoff with safe path, command, and stop/report
  rule. The packet now drops quota/authority prose from the copied text and
  tightens truncation limits while preserving gate, todo, boundary, safe path,
  command, and validation handoff context. Validation:
  `npm run smoke:action-packet` in `apps/dashboard` reports
  `action-packet smoke ok (623 chars)`, `npm run build` in `apps/dashboard`
  passes with only the known Vite chunk-size warning, `node
  examples/dashboard-operator-gate-browser-smoke.mjs`, `git diff --check`, and
  `goal-harness check --scan-root .` all pass. Changed files:
  `apps/dashboard/src/data/action-packet.ts`,
  `apps/dashboard/smoke/action-packet-smoke.ts`, this active state, and the
  private CS-Notes state. Critic: the copied packet is now short and covered by
  deterministic smoke, but the proof is still synthetic; next slice should
  shift to public first-try usability unless a real connected goal regresses on
  status, hidden todos, or packet length.
- 2026-06-03T00:54:42+08:00: Steering audit candidates were: P0
  dashboard/operator-view human-decision loop, P0 status/state truth, P1 public
  first-try usability, and P2 broader dashboard cleanup. Continuation check:
  the last slices fixed CLI/skill/report todo consumption, so continuing on
  dashboard interaction won because the remaining user pain was visible action
  duplication and inconsistent packet copy affordances. Bounded fix: hardened
  `examples/dashboard-operator-gate-browser-smoke.mjs` into a real first-screen
  User Actions regression: it now checks pending all-actions, focused
  controller, and approved Codex-ready views for one card-level `Copy`
  affordance, no legacy `Operator Review Packet` / `Copy Review Packet` panel,
  no stale suggested-decision white card, and no approved view that still says
  "Agent command ready after approval". The smoke was also made robust against
  the Playwright CLI wrapper by using bounded `eval` reads of the User Actions
  section instead of hanging `run-code` / `networkidle` waits. Dashboard UI now
  labels approved commands as `Approved agent command` instead of the stale
  after-approval badge. Validation: `node
  examples/dashboard-operator-gate-browser-smoke.mjs`, `npm run build` in
  `apps/dashboard`, `npm run smoke:action-packet` in `apps/dashboard`,
  `git diff --check`, and `goal-harness check --scan-root .`. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/dashboard-operator-gate-browser-smoke.mjs`, this active state, and
  the private CS-Notes state. Critic: the visible card duplication/copy-entry
  regression is now covered, but the copied packet body itself may still be too
  long for the user to paste comfortably; next slice should trim the packet
  content rather than add another panel.
- 2026-06-03T00:16:08+08:00: Steering audit candidates were: P0
  project-agent consumption proof, P0 dashboard/operator-view human-decision
  loop, P1 public usability polish, and P2 broader UI cleanup. Continuation
  check: after the last two slices exposed `agent_todo_summary` in JSON and
  aligned the installed skill, the remaining proof was interaction-level: does
  the visible report actually name the relevant todo items. The bounded fix
  updated `render_quota_should_run_markdown()` so `quota should-run` Markdown
  prints `user_todo_next[...]` and `agent_todo_next[...]` for the first open
  items, not only open/total counts. Added smoke assertions that an
  operator-gate quota report names both the user todo and the agent safe
  follow-up. Real validation on the connected migration goal now shows the
  default Markdown report listing the first three open user todos and first
  three open agent todos. Validation: `python3 examples/quota-plan-smoke.py`,
  `python3 examples/run-smokes.py` with 15 scripts,
  `python3 -m compileall -q goal_harness`, `git diff --check`,
  `goal-harness check --scan-root .`, and real global-registry
  `quota should-run --goal-id premium-ui-ai-search-rec-migration` Markdown.
  Changed files: `goal_harness/quota.py`,
  `examples/quota-plan-smoke.py`, this active state, and the private CS-Notes
  state. Critic: the CLI/report path now consumes and names user/agent todo
  items, but the dashboard/operator view may still have duplicated yellow/white
  cards and uneven packet copy affordances; that is the next highest-value
  human-decision-loop slice.
- 2026-06-03T00:09:18+08:00: Steering audit candidates were: P0 project-agent
  consumption proof, P0 installed-skill/state truth, P1 public usability polish,
  and P2 dashboard copy cleanup. Continuation check: the previous slice exposed
  `agent_todo_summary` in quota JSON/Markdown, but real project agents load the
  installed `~/.codex/skills/goal-harness-project/SKILL.md`; that skill was
  still on the old contract and only told agents to read `user_todo_summary`.
  This meant the CLI field existed but a real agent using the current skill
  could still ignore its own agent todos. Bounded fix: synced the installed
  `goal-harness-project` skill with the public skill contract so it reads
  `agent_todo_summary`, uses it as the safe follow-up checklist, and treats
  shared global registry as the source for operator gates, user todos, agent
  todos, and quota state. Also kept the public skill template wording aligned.
  Validation: installed skill and public skill now diff clean; `rg` confirms
  both mention `agent_todo_summary`, `agent todos`, and safe follow-up
  checklist; real `quota should-run --goal-id premium-ui-ai-search-rec-migration`
  still returns `user_todo_summary.open_count=3` and
  `agent_todo_summary.open_count=5`; `goal-harness check --scan-root .`
  reports public boundary clean; `python3 examples/run-smokes.py` passes 15
  smoke scripts; `git diff --check` passes. Changed files:
  `skills/goal-harness-project/SKILL.md`, installed global
  `~/.codex/skills/goal-harness-project/SKILL.md`, this active state, and the
  private CS-Notes state. Critic: this closes the “project agent reads stale
  skill” gap, but the remaining proof is interaction-level: a real heartbeat or
  operator-gate report must visibly include the relevant user/agent todo items
  instead of merely having access to them.
- 2026-06-03T00:03:57+08:00: Steering audit candidates were: P0
  project-agent loop proof on a real connected goal, P0 state-truth/global
  registry freshness, P1 first-run/public PR usability, and P2 dashboard copy
  polish. Continuation check: first-run usability had consumed recent slices,
  and the state explicitly pointed back to real connected-goal adoption. The
  bounded proof found a concrete project-agent usability gap: real
  `premium-ui-ai-search-rec-migration` quota output already exposed
  `user_todo_summary`, but dropped `agent_todo_summary`, even though status
  showed five open agent todos. Root cause: `build_quota_plan()` copied
  `user_todos` from the attention item but did not forward `agent_todos`, so
  `build_quota_should_run()` never had the field. Fixed the forwarding path,
  added `agent_todo_summary` to JSON and Markdown `quota should-run` output,
  updated generated heartbeat/new-project prompts, docs, the project skill, and
  smoke coverage. Validation: `python3 examples/run-smokes.py` passed 15 smoke
  scripts, `python3 -m compileall -q goal_harness`, `git diff --check`,
  `goal-harness check --scan-root .`, and a real global-registry
  `quota should-run --goal-id premium-ui-ai-search-rec-migration` now returns
  `agent_todo_summary.open_count=5` alongside the existing open user todos.
  Changed files: `README.md`, `docs/attention-queue.md`,
  `docs/heartbeat-automation-prompt.md`, `docs/new-project-codex-prompt.md`,
  `docs/quota-allocation.md`, `docs/status-data-contract.md`,
  `examples/project-agent-adoption-smoke.py`,
  `examples/quota-contract-smoke.py`, `examples/quota-plan-smoke.py`,
  `goal_harness/heartbeat_prompt.py`, `goal_harness/project_prompt.py`,
  `goal_harness/quota.py`, `skills/goal-harness-project/SKILL.md`, plus this
  active state; private state also updated. Critic: the CLI/status contract now
  exposes both user and agent work, but the next proof should verify a real
  project agent or operator-gate report consumes those summaries in its
  visible interaction, not merely that the fields exist.
- 2026-06-02T23:47:30+08:00: Steering audit candidates were: P1 fresh-clone
  trial audit for first-run usability, P0 live connected-goal adoption and
  user/agent todo projection, and P2 richer dashboard/demo polish. Continuation
  check: first-run usability had already consumed recent slices, but a clean
  clone/temp-HOME audit was the explicit stop condition before adding more
  features. The audit first found a real public friction: install, doctor,
  `goal-harness demo`, and smokes passed, but `goal-harness check --scan-root .`
  failed in an unconnected source checkout because the implicit
  `.goal-harness/registry.json` was missing. Fixed the false failure by letting
  implicit missing registries become warnings for `check`, while explicit
  missing `--registry` paths remain errors. Added
  `examples/check-public-boundary-smoke.py` for the fresh no-registry path and
  documented the expected warning in README. Fresh-clone validation after commit
  passed install, `goal-harness doctor`, `goal-harness --runtime-root <tmp>
  demo`, `python3 examples/demo-cli-smoke.py`, `python3 examples/run-smokes.py`
  with 15 scripts, `goal-harness check --scan-root .`, and clean cloned repo
  status. Changed files: `README.md`, `goal_harness/cli.py`,
  `goal_harness/contract.py`, `examples/check-public-boundary-smoke.py`, plus
  this active state; private state also updated. Additional validation:
  `python3 -m compileall -q goal_harness`, direct no-registry JSON check in a
  temp HOME, and `git diff --check`. Critic: first-run/source-check friction is
  now low enough to stop polishing the demo path; the next higher-value slice is
  proving that real connected project agents can see and use user/agent todo
  surfaces without making the user read chat threads.
- 2026-06-02T23:34:46+08:00: Steering audit candidates were: P1 first-run
  `goal-harness demo` command, P0 live connected-goal adoption check, and P2
  richer dashboard/demo polish. Continuation check: first-run usability has now
  consumed two consecutive slices, but the previous slice explicitly left the
  path as copy-paste heavy; implementing a one-command demo is the smallest
  direct reduction in public trial friction and stays within the current PR
  usability goal. Added `goal_harness/demo.py` and `goal-harness demo`, which
  creates a disposable local project, writes `GOAL.md`, bootstraps `demo-goal`
  without global sync, adds one user todo and one agent todo, refreshes state,
  summarizes status/quota, and prints next commands. Updated `README.md`
  `Try It In 10 Minutes` from a long copy-paste block to `goal-harness demo`.
  Added `examples/demo-cli-smoke.py` so the public smoke runner validates the
  one-command path, local registry use, user/agent todo projection, refresh,
  quota eligibility, and no global-registry sync. Changed files: `README.md`,
  `goal_harness/cli.py`, `goal_harness/demo.py`, `examples/demo-cli-smoke.py`,
  plus this active state; private `.local` state also updated. Validation:
  `python3 examples/demo-cli-smoke.py`, `python3 examples/run-smokes.py` now
  passes 14 smoke scripts, `python3 -m compileall -q goal_harness`,
  installed-wrapper smoke `goal-harness --runtime-root <tmp> demo --project
  <tmp>/project --goal-id wrapper-demo-goal`, `goal-harness check --scan-root
  .`, and `git diff --check`. A manual default-runtime demo was archived and
  its temp project removed. Critic: the public try path is now one command, but
  it has not yet been tested from a clean clone/HOME after install; the next
  quality step should be a fresh-clone trial audit rather than more feature
  work. Losing candidate to remember: live connected-goal adoption remains a
  stronger P0 control-plane proof after first-run UX is no longer embarrassing.
- 2026-06-02T23:18:37+08:00: User feedback after the open-source PR draft
  shifted this slice from internal prompt polish to external usability: willing
  first-time users should feel Goal Harness is "usable enough" after a quick
  try. Steering audit candidates were: P0 generated-prompt link to the
  project-agent todo contract, P1 README first-run usability, and P0 public
  smoke health. Continuation check: the todo contract was useful but too
  internal-facing for the PR moment, so continuing only on prompts would be
  locally greedy; the README trial path and green smoke entry reduce real
  first-user friction. Added `README.md` `Try It In 10 Minutes` with a
  disposable local project flow that exports PATH, bootstraps with
  `--no-global-sync`, adds one user todo and one agent todo through the
  project-local registry, refreshes state, prints status, and checks quota.
  Also linked `docs/project-agent-todo-contract.md` from generated heartbeat and
  new-project prompts, updated their smoke assertions, and repaired a stale
  `examples/review-packet-smoke.py` expectation so the public
  `examples/run-smokes.py` entry is green after the action-packet extraction.
  Changed files: `README.md`, `docs/heartbeat-automation-prompt.md`,
  `docs/new-project-codex-prompt.md`, `goal_harness/heartbeat_prompt.py`,
  `goal_harness/project_prompt.py`, `examples/heartbeat-prompt-smoke.py`,
  `examples/project-prompt-smoke.py`, `examples/review-packet-smoke.py`, plus
  this active state; private `.local` state also updated. Validation: real temp
  demo ran `bootstrap`, `todo add` for user and agent, `refresh-state`, `status`,
  and `quota should-run` with a project-local registry, then archived the temp
  `demo-goal` runtime; `python3 examples/run-smokes.py` passed 13 smoke scripts;
  `python3 -m compileall -q goal_harness`; `goal-harness check --scan-root .`;
  `git diff --check`. Critic: the PR-facing path is now copy-paste runnable, but
  still not one-command; the next usability win is a demo command/script or a
  fresh-clone trial audit, not another internal contract paragraph. Losing
  candidate to remember: a live connected-goal adoption check is still useful
  after first-run UX is less manual.
- 2026-06-02T22:13:39+08:00: Steering audit candidates were: P0 state/plan
  hygiene because the previous next action partly overlapped already-existing
  todo CLI smokes, P0 project-agent execution loop contract, and P1 docs polish.
  Continuation check: UI packet work is now guarded, so this slice pivoted back
  to the agent-facing todo loop. Chose the contract doc because the mechanics
  already existed but were scattered across the attention queue, generated
  prompts, skill, and smokes; a short canonical doc reduces the chance that a
  target project agent hides user work in `Next Action` again. Added
  `docs/project-agent-todo-contract.md` and linked it from the README daily-use
  section. The contract distinguishes `Next Action`, user todos, agent todos,
  and production blockers/gates, and points to the existing todo/adoption
  smokes. Changed files: `README.md`,
  `docs/project-agent-todo-contract.md`, plus this active state; private
  `.local` state also updated. Validation: `python3 examples/todo-cli-smoke.py`,
  `python3 examples/project-agent-adoption-smoke.py`, `goal-harness check
  --scan-root .`, and `git diff --check`. Critic: this centralizes the
  contract but generated prompt surfaces do not yet point directly at the new
  doc; the next slice should only wire that link where it helps agents, not
  duplicate the whole contract text. Losing candidate to remember: a live
  connected-goal adoption check is still useful after the public prompt surface
  is coherent.
- 2026-06-02T22:06:40+08:00: Steering audit candidates were: P0
  project-agent todo contract, P0 deterministic action-packet regression guard,
  and P1 communication polish. Continuation check: dashboard/UI work has taken
  several recent delivery slices, but the previous payload fix explicitly left
  one unguarded regression risk; chose this final bounded UI smoke before
  pivoting back to the project-agent loop. Extracted the action-packet builder
  to `apps/dashboard/src/data/action-packet.ts`, left the React page as a thin
  adapter, and added `npm run smoke:action-packet` with a user-todo/gate
  fixture that asserts the packet sections, ordering, safety boundary, and rough
  length without using a browser clipboard. Changed files:
  `apps/dashboard/package.json`, `apps/dashboard/src/data/action-packet.ts`,
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `apps/dashboard/smoke/action-packet-smoke.ts`, plus this active state;
  private `.local` state also updated. Validation: `npm run
  smoke:action-packet` in `apps/dashboard` reported `action-packet smoke ok
  (855 chars)`, `npm run build` in `apps/dashboard`, `goal-harness check
  --scan-root .`, and `git diff --check`. Critic: packet generation now has a
  deterministic guard; further UI polish should wait for new user evidence.
  Next work should help target project agents put user-facing todos into the
  right Goal Harness fields.
- 2026-06-02T21:58:00+08:00: Steering audit candidates were: P0 state-truth
  follow-up, P0 action packet payload quality, and P1 communication polish.
  Chose packet payload quality because the UI now has a single visible packet
  affordance, so the remaining user burden is whether the copied content is
  short and decision-shaped. Tightened `buildHumanFriendlyActionPacket` so the
  copied payload is structured as status, user action/gate, boundary, and safe
  project-agent handoff. It no longer dumps separate summary/next-action lines
  that made Codex-ready user-todo cards feel like raw dashboard detail. Long
  todo/question/boundary text is compacted before copy. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx` plus this active state; private
  `.local` state also updated. Validation: `npm run build` in
  `apps/dashboard`, `goal-harness check --scan-root .`, `git diff --check`, and
  browser reload showing the live platform-migration action card and Copy
  button still present. Browser clipboard readback was not available because
  the current in-app browser reported that its virtual clipboard is not
  installed; `pbpaste` still contained unrelated old text, so the packet content
  validation relied on the source diff and build. Critic: the payload shape is
  better, but the lack of deterministic packet-generation smoke means future
  regressions could slip through without a browser clipboard; next tick should
  add that small fixture-level guard.
- 2026-06-02T21:49:28+08:00: Steering audit candidates were: P0 state-truth
  recheck, P0 human-decision UI duplicate-surface removal, and P1 docs polish.
  Continued the UI cleanup because the previous empty-filter fix made the
  single visible packet affordance reachable, and the remaining risk was stale
  code reviving the old lower packet surface. Confirmed by `rg` that
  `ReviewLinkPanel` had no render path, then removed the unmounted
  `ReviewLinkPanel`, `buildReviewPacket`, `OperatorTransitionPreview`, and
  related transition/markdown helpers. The visible `User Actions` copy path was
  left intact. Changed files: `apps/dashboard/src/views/dashboard-page.tsx`
  plus this active state; private `.local` state also updated. Validation:
  `npm run build` in `apps/dashboard`, stale-keyword `rg` returned no matches
  for `ReviewLinkPanel`, `Copy Review Packet`, `Operator Review Packet`, or
  `Packet details`, in-app browser reload showed those old labels absent while
  `User Actions` Copy buttons and the platform-migration `Next user todo 2/13
  open` card remained visible, `goal-harness check --scan-root .`, and
  `git diff --check`. Critic: duplicate packet surfaces are now structurally
  removed; next improvement should target the copied packet payload quality, not
  more layout changes.
- 2026-06-02T21:42:53+08:00: Steering audit candidates were: P0 state truth
  verification, P0 human-decision UI surface cleanup, and P1 communication
  polish. State truth had just been verified, so chose one bounded P0 UI cleanup
  from the live dashboard: when the URL/filter is stuck on a now-empty action
  kind such as `actionKind=controller` with zero controller actions, the
  `User Actions` panel now shows a short empty-filter notice and falls back to
  all active actions instead of hiding every actionable card and copy button.
  This keeps Codex-ready goals and `Next user todo` cards reachable after a
  gate is cleared. Changed files: `apps/dashboard/src/views/dashboard-page.tsx`
  plus this active state; private `.local` state also updated. Validation:
  `npm run build` in `apps/dashboard`, `goal-harness check --scan-root .`,
  in-app browser reload on the live `actionKind=controller` URL showing the
  fallback notice, visible Copy buttons, and the platform-migration
  `Next user todo 2/13 open` card. Critic: the real empty-filter trap is fixed,
  but the source still contains an unmounted old `ReviewLinkPanel` / lower
  packet component; removing that stale code is the next smallest way to keep
  the UI from regressing into duplicate packet surfaces.
- 2026-06-02T21:33:01+08:00: Steering audit candidates were: P0 live
  dashboard verification after the global attention-override fix, P0 duplicate
  dashboard/panel cleanup, and P1 communication polish. Chose live dashboard
  verification because the previous code fix was correct in CLI but the user
  was looking at an in-app browser backed by `/status.local.json`. Verified
  global CLI first: platform migration now reports `status=state_refreshed`,
  `waiting_on=codex`, `quota_state=eligible`, and `user_todos.open_count=2`.
  The in-app browser initially still showed stale `owner_sop_review_pending`
  because `apps/dashboard/public/status.local.json` was an old 18:20 snapshot
  with 4 open todos. Refreshed `apps/dashboard/public/status.local.json` from
  live global status, mirrored it to `apps/dashboard/dist/status.local.json`,
  and reloaded the browser. The visible dashboard now shows the platform
  migration goal as `state_refreshed / Codex`, not `owner_sop_review_pending`.
  Changed files: this active state only; refreshed `status.local.json` files are
  local ignored dashboard snapshots. Validation: global `quota should-run`
  returned `should_run=true`; curl/JQ against `/status.local.json` showed
  `state_refreshed`, `waiting_on=codex`, `quota_state=eligible`, and 2 open
  user todos; in-app browser reload showed no `owner_sop_review_pending` and
  the platform-migration card under Codex-ready status. Critic: state truth and
  live snapshot are clean; the remaining product issue is UI duplication and
  wording, especially preventing production-write gates from looking like user
  todos.
- 2026-06-02T21:24:10+08:00: Field bug from the platform-migration controller:
  local status and latest run correctly showed `waiting_on=codex` after the
  owner/SOP gate was approved for safe-local/offline work, but the global
  registry still preserved stale `waiting_on=user_or_controller` and
  `attention_status=owner_sop_review_pending`; as a result,
  `quota should-run --registry ~/.codex/goal-harness/registry.global.json`
  returned a stale operator gate. Root cause: global sync preserved attention
  overrides whenever the later source omitted those fields, even when the later
  source was the same source registry that had become authoritative again.
  Fixed `sync-global` so cross-source overrides are preserved, but same-source
  sync omission clears stale override fields. Updated the data contract and
  smoke coverage. Applied the fixed sync to the live platform-migration global
  registry. Changed files: `goal_harness/global_registry.py`,
  `examples/global-registry-sync-smoke.py`, `docs/status-data-contract.md`, and
  this active state. Validation: `python examples/global-registry-sync-smoke.py`,
  `python examples/status-markdown-smoke.py`, `python examples/quota-plan-smoke.py`,
  `python examples/quota-contract-smoke.py`, `python -m compileall -q
  goal_harness`, `git diff --check`, live `sync-global` for
  `premium-ui-ai-search-rec-migration`, and live global
  `quota should-run` now returning `should_run=true`, `waiting_on=codex`,
  `status=state_refreshed`, source `latest_run`. Critic: this fixes the state
  truth bug; the next useful work is visual verification and UI wording, not
  more prompt churn.
- 2026-06-02T21:18:31+08:00: Steering audit candidates were: P0 dashboard
  project-asset consumption, P0 human-decision loop/copy surface cleanup, and
  P1 internal-introduction polish. Chose dashboard project-asset consumption
  because the previous slice created the compact status projection and the
  existing dashboard WIP was aligned with the user-todo-before-gate problem.
  Dashboard schemas now preserve `project_asset`; first-screen action cards
  prefer `project_asset.quota`, `project_asset.user_todos`,
  `project_asset.agent_todos`, `project_asset.next_action`, and
  `project_asset.stop_condition` before falling back to detailed queue fields.
  The browser smoke fixture now proves that a user todo present only in
  `project_asset` still appears before an operator gate. Clarified the field
  distinction exposed by the platform-migration case: `User Todo` is the
  operator-facing checklist, while project-local production blockers are
  write-safety gates and must not be counted as user todos. Changed files:
  `apps/dashboard/src/data/status.ts`,
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/dashboard-operator-gate-browser-smoke.mjs`,
  `examples/review-packet-smoke.py`, and this active state. Validation: `npm
  run build`, `python examples/review-packet-smoke.py`, `python
  examples/status-markdown-smoke.py`, `python examples/quota-contract-smoke.py`,
  `node examples/dashboard-operator-gate-browser-smoke.mjs`, `python -m
  compileall -q goal_harness`, `goal-harness check --scan-root .`, and `git
  diff --check`. Critic: the data and first-screen UI now consume the compact
  project asset; remaining work should reduce duplicate panels/copy surfaces
  and avoid wording that makes production-write blockers look like user todos.
- 2026-06-02T21:04:34+08:00: Steering audit candidates were: P0 status
  project-asset projection, P0 human decision loop dashboard polish, and P1
  internal-introduction polish. Chose the status projection because it is the
  lowest-risk way to make owner, gate, next action, stop condition, todo state,
  quota, and latest validation available from one public-safe field without
  touching the dirty dashboard WIP. Extended `project_asset` so attention items
  keep the existing `owner`, `gate`, `next_action`, and `stop_condition`, and
  may also carry compact `user_todos`, `agent_todos`, `quota`, and
  `latest_validation` summaries. Changed files: `goal_harness/status.py`,
  `examples/status-markdown-smoke.py`, `examples/quota-contract-smoke.py`,
  `docs/status-data-contract.md`, and this active state. Validation: `python
  examples/status-markdown-smoke.py`, `python examples/quota-contract-smoke.py`,
  `python -m compileall -q goal_harness`, `goal-harness check --scan-root .`,
  `git diff --check`, and live `goal-harness --format json status` showing the
  field goal's project asset now includes open user todos, agent todos, quota,
  and latest validation. Critic: this solves the data contract layer; the UI
  still needs to consume this single projection without adding more panels or
  copy surfaces.
- 2026-06-02T21:01:21+08:00: Steering audit candidates were: P0 real-heartbeat
  adoption proof for the newly globalized quota guard, P0 dashboard/status
  project-asset projection, and P1 internal-introduction polish. Chose the
  real-heartbeat proof because the previous slice's critic required evidence
  from the actual connected project thread, not another local command replay.
  The real project heartbeat now runs its guard with the shared global registry,
  reads `state=operator_gate` instead of the project-local eligible state, and
  sends a concise operator notification listing the existing open user todos.
  Changed files: this active state only. Validation: inspected the connected
  thread session after the updated automation ran; the guard command included
  `--registry "$HOME/.codex/goal-harness/registry.global.json"`, the JSON
  returned `should_run=false`, `notify_user_on_gate=true`, and open user todos,
  and the final heartbeat message surfaced those todos in Chinese. Critic: the
  state-truth/user-todo adoption issue is now proven on a real connected goal;
  the next value is the project-asset status/dashboard surface, not more
  prompt churn.
- 2026-06-02T20:52:33+08:00: Verified the previous user-todo notification fix
  against the real connected project thread and found a smaller state-truth
  root cause: the heartbeat ran from the target project cwd, so its unqualified
  `quota should-run` read the project-local registry and returned
  `should_run=true`, while the dashboard/operator view uses the shared global
  registry and still reports `state=operator_gate` with open user todos. Fixed
  the heartbeat/new-project generator so quota guard and quota spend commands
  explicitly use `--registry "$HOME/.codex/goal-harness/registry.global.json"`.
  Kept the boundary narrow: compute/operator guard reads global control-plane
  state, while `todo add`, `refresh-state`, adapter runs, and project-file reads
  still use the project-local state and sync public-safe projections back to
  global. Updated the live project heartbeat automation and re-ran the local
  install script so the installed `goal-harness-project` skill matches the repo
  skill. Changed files: `goal_harness/project_prompt.py`,
  `docs/heartbeat-automation-prompt.md`, `docs/new-project-codex-prompt.md`,
  `docs/quota-allocation.md`, `docs/status-data-contract.md`,
  `docs/attention-queue.md`, `README.md`,
  `skills/goal-harness-project/SKILL.md`,
  `examples/heartbeat-prompt-smoke.py`, `examples/project-prompt-smoke.py`,
  `examples/install-local-smoke.py`, `examples/quota-contract-smoke.py`, and
  this active state. Validation: `python examples/heartbeat-prompt-smoke.py`,
  `python examples/project-prompt-smoke.py`, `python
  examples/install-local-smoke.py`, `python examples/quota-contract-smoke.py`,
  `python -m compileall -q goal_harness`, `goal-harness check --scan-root .`,
  `git diff --check`, installed-skill diff clean, live guard from the target
  project cwd with the explicit global registry returning `operator_gate`,
  `should_run=False`, `notify_user_on_gate=True`, and open user todos. Critic:
  this is the right state-truth fix, but the next proof should be the actual
  heartbeat thread output, not another local command replay.
- 2026-06-02T20:32:20+08:00: Fixed a field failure in the user-todo
  notification loop: `quota should-run` already exposed open user todos for a
  real operator-gated goal, but an existing heartbeat prompt could still
  compress the turn into "no new user action" after the gate had been surfaced.
  Updated the heartbeat generator and installed project skill so
  `user_todo_summary.open_count > 0` must be reported as existing user-visible
  work, even when no newly discovered user action exists. Added a compact
  `project_asset` status projection with `owner`, `gate`, `next_action`, and
  `stop_condition` so agents and dashboards do not reconstruct that control
  state from scattered fields. Updated the live heartbeat automation for the
  connected field goal to the regenerated prompt. Changed files:
  `goal_harness/status.py`, `goal_harness/heartbeat_prompt.py`,
  `docs/status-data-contract.md`, `docs/heartbeat-automation-prompt.md`,
  `docs/quota-allocation.md`, `skills/goal-harness-project/SKILL.md`,
  `README.md`, `examples/status-markdown-smoke.py`,
  `examples/heartbeat-prompt-smoke.py`, and `examples/quota-contract-smoke.py`.
  Validation: `python examples/status-markdown-smoke.py`, `python
  examples/heartbeat-prompt-smoke.py`, `python examples/quota-contract-smoke.py`,
  `python -m compileall -q goal_harness`, `goal-harness check --scan-root .`,
  `git diff --check`, live `quota should-run` confirming
  `notify_user_on_gate=True`, `user_todo_summary.open_count=5`, and a
  `gate_prompt` containing user todos. Follow-up refinement in the same slice:
  the safe-bypass report path now has the same rule, so an agent that spends a
  bounded non-gated steering turn after a surfaced gate must still list
  existing open user todos instead of saying there is no user action. Critic:
  this fixes the agent-facing and automation-prompt contract; the next useful
  check is whether the actual heartbeat thread now presents the todos in
  concise Chinese instead of burying them in a long packet.
- 2026-06-02T20:21:44+08:00: Promoted cognitive-load reduction from a
  useful framing into an explicit design principle. Goal Harness should make
  humans stop reading every project-agent thread, relaying every packet, and
  restating context; the human should provide high-value decisions while the
  system carries state refresh, handoff, validation, and quota bookkeeping.
  Changed files: this active state and the private internal-introduction draft.
  Validation: targeted grep/readback. Critic: this is a principle/narrative
  calibration, not a replacement for the next P0 project-asset status slice.
- 2026-06-02T20:14:23+08:00: Re-centered the meta goal around reducing
  operator coordination load. The product target is now a multi-project control
  plane that turns each line of work into a project asset with explicit owner,
  gate, next action, stop condition, user todo, agent todo, quota, review
  packet, and validation signal. Presentation and external narrative work are
  recorded as secondary tracks that explain the system but should not drive P0
  implementation. Changed files: this active state and the private controller
  state. Validation: section-level readback/grep. Critic: this is a goal
  calibration slice; the next implementation slice should add a minimal
  project-asset status/dashboard projection rather than continuing generic UI
  polish.
- 2026-06-02T20:02:48+08:00: Steering audit candidates: P0 live state/safety
  adoption check for the platform-migration goal, P0 human-decision loop
  dashboard/operator-gate affordance, and P1 dashboard polish. Chose the live
  adoption check because the previous slice proved the public fixture, but the
  real premium-ui migration goal was the field case that originally exposed the
  gap. Ran live `goal-harness status` and `goal-harness quota should-run
  --goal-id premium-ui-ai-search-rec-migration` without editing the target
  project. Result: adoption is now working. The attention item is
  `owner_sop_review_pending`, `waiting_on=user_or_controller`, and carries
  `user_todos` from `User Todo / Owner Review Reading Queue` with 12 total,
  8 done, and 4 open items. The first open items include owner review worksheet
  recording, P0 column semantics/routing, latest-code invert validation
  tracking, and item-embedding field/prompt drift. The quota guard also exposes
  `todo_write_hint` with the exact `goal-harness todo add --role user` command
  template, plus a `gate_prompt` that lists the first open user todos before
  asking for the owner/SOP gate decision. Changed files: this active state
  only. Validation: live `goal-harness --format json status`, live
  `goal-harness --format json quota should-run --goal-id
  premium-ui-ai-search-rec-migration`, `git status`, and the global registry
  entry for the goal. Critic: the agent-facing adoption issue is no longer the
  current blocker for this real goal; the next higher-value P0 work is the
  human decision/recording surface, so the user can complete the visible todos
  and gate judgment with less relay overhead.
- 2026-06-02T19:53:50+08:00: Steering audit candidates: P0 state/safety live
  check that `todo_write_hint` is present in guard output, P0 project-agent loop
  adoption proof across guard -> todo CLI -> status projection -> approved
  handoff, and P1 dashboard display polish. Chose the adoption-proof smoke
  because the previous slice added the contract, but had not proved an executor
  could actually follow it end to end. Added
  `examples/project-agent-adoption-smoke.py`, a sanitized temporary project
  fixture that starts as a planned read-only-map goal, verifies
  `quota should-run` exposes `todo_write_hint`, uses `goal-harness todo add
  --role user` to write an owner/user action, confirms `goal-harness status`
  projects that checkbox into `user_todos`, records an approved operator gate,
  and confirms `review-packet` emits only the short approved handoff with the
  approved read-only/dry-run `agent_command` and no local gate draft. Changed
  files: `examples/project-agent-adoption-smoke.py` and this active state.
  Validation: `python examples/project-agent-adoption-smoke.py`, `python
  examples/todo-cli-smoke.py`, `python examples/review-packet-cli-smoke.py`,
  `python examples/quota-plan-smoke.py`, `python examples/run-smokes.py`
  showing 13 smoke scripts, `python -m compileall -q goal_harness`,
  `goal-harness check --scan-root .`, and `git diff --check`. Critic: the
  public sanitized adoption path is now covered; next value is one live
  public-safe adoption check on a real connected goal, without touching target
  project code or taking over its controller.
- 2026-06-02T19:38:12+08:00: Steering audit candidates: P0 approved-command
  handoff after durable operator gate approval, P0 user-todo writeback
  friendliness for project agents, and P1 dashboard affordance polish. I began
  with the approved-command handoff, then the user surfaced a sharper field
  failure: a project agent had analyzed P0 owner/user work but hid it in
  `Next Action` / review docs instead of adding dashboard-visible user todos.
  Kept the slice within the same P0 project-agent execution loop and made the
  contract agent-facing rather than UI-only. `review-packet` now detects
  `operator_gate_approved` plus `agent_command` and emits a short
  goal-id-guarded handoff that says the gate is already approved, only the
  listed read-only/dry-run command may run, and write/run-history/production
  escalation must stop. `quota should-run` now always returns a
  `todo_write_hint` with exact `goal-harness todo add --role user|agent`
  command templates, so agents who only read the guard JSON see how to write
  newly discovered user/owner work into the canonical active-state section.
  New-project and heartbeat prompts now explicitly forbid hiding user todos in
  `Next Action`, review docs, or chat, and tell agents to use the todo CLI plus
  `refresh-state` when dashboard needs the update. Changed files:
  `goal_harness/review_packet.py`, `goal_harness/quota.py`,
  `goal_harness/project_prompt.py`, `goal_harness/heartbeat_prompt.py`,
  `docs/new-project-codex-prompt.md`,
  `docs/heartbeat-automation-prompt.md`, `docs/quota-allocation.md`,
  `examples/review-packet-cli-smoke.py`,
  `examples/project-prompt-smoke.py`,
  `examples/heartbeat-prompt-smoke.py`,
  `examples/quota-plan-smoke.py`, `examples/quota-contract-smoke.py`, and
  this active state. Validation: `python examples/project-prompt-smoke.py`,
  `python examples/heartbeat-prompt-smoke.py`, `python
  examples/quota-plan-smoke.py`, `python examples/quota-contract-smoke.py`,
  `python examples/review-packet-cli-smoke.py`, `python examples/run-smokes.py`,
  `python -m compileall -q goal_harness`, `goal-harness check --scan-root .`,
  `git diff --check`, and live `goal-harness --format json quota should-run
  --goal-id goal-harness-meta` showing `todo_write_hint`. Critic: this fixes
  the contract that made agents miss user todos, but the next proof should
  inspect a target-project run/automation prompt or sanitized fixture to ensure
  adoption, not keep adding more textual guidance.
- 2026-06-02T19:17:00+08:00: Steering audit candidates: P0 dashboard copy
  surface for durable gate recording, P0 project-agent approved-command
  handoff, and P1 dashboard polish. Chose the dashboard copy slice because the
  previous CLI packet slice exposed approve/reject/defer commands, but the
  first-screen `Goal Harness Action` copy still omitted the durable recording
  rule. Added a compact controller-only `durableOperatorGateRecordRule()` to
  the dashboard action packet: it tells the user to preview with local
  `operator-gate --dry-run`, remove `--dry-run` only for an intentional durable
  append, and use `reject` / `defer` with a public-safe reason when not
  approving. The default action packet still does not include the full
  `operator-gate` command, so it remains a single short first-screen copy
  surface rather than a second panel. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/review-packet-smoke.py`, and this active state. Validation:
  `python examples/review-packet-smoke.py`, `python
  examples/review-packet-cli-smoke.py`, `npm --prefix apps/dashboard run
  build`, `python examples/run-smokes.py`, `goal-harness check --scan-root .`,
  and `git diff --check`. Critic: this finishes the minimal durable gate
  recording text across CLI and dashboard copy surfaces, but actual one-click
  append is still future work; the next higher-value slice is the after-approval
  project-agent handoff.
- 2026-06-02T19:11:33+08:00: Steering audit candidates: P0 human-decision
  loop durable operator-gate recording, P0 project-agent approved-command
  handoff, and P1 dashboard polish/internal narrative. Chose the operator-gate
  recording slice because state/gate truth is already good enough, but the
  user still has to bridge a human approve/defer/reject judgment into a durable
  `operator_gate_*` run. Extended CLI Review Packets for controller actions:
  the Markdown stays compact with the default approve `operator-gate --dry-run`
  command plus one rule saying to keep `--dry-run` for preview, remove it only
  for intentional durable append, and use `reject` / `defer` with a public-safe
  reason when not approving. The JSON payload now also exposes
  `operator_gate_decision_commands` for `approve`, `reject`, and `defer`, so a
  dashboard or script can copy exact dry-run commands without parsing prose.
  Changed files: `goal_harness/review_packet.py`,
  `examples/review-packet-cli-smoke.py`, and this active state. Validation:
  `python examples/review-packet-cli-smoke.py`, `python
  examples/review-packet-smoke.py`, `python -m compileall -q goal_harness`,
  `python examples/run-smokes.py`, `goal-harness check --scan-root .`, `git
  diff --check`, plus live `goal-harness review-packet --goal-id
  premium-ui-ai-search-rec-migration` showing the record rule and live JSON
  showing `approve/defer/reject` commands. Critic: this improves CLI/script
  handoff but the dashboard copy surface still needs to surface the same
  durable-gate rule without resurrecting extra panels.
- 2026-06-02T19:06:03+08:00: Heartbeat preflight is healthy with
  `$HOME/.local/bin` on PATH and `quota should-run` returned eligible. Steering
  audit candidates: P0 state/safety Review Packet goal-id mismatch guard, P0
  human-decision one-click/durable operator decision recording, and P0
  project-agent approved-command handoff. Chose the goal-id guard because it is
  the smallest state/safety slice after the recent cross-project confusion:
  project agents must reject a packet that belongs to another active goal.
  Added a `target_goal_guard()` to the CLI Review Packet `给项目 Agent` section
  for reward, controller, and codex handoffs, explicitly saying the packet only
  applies to the target `goal_id` and to stop if the agent's active goal or
  registry entry differs. Updated the CLI smoke to assert the guard and its
  order before any command. Changed files: `goal_harness/review_packet.py`,
  `examples/review-packet-cli-smoke.py`, and this active state. Validation:
  `python examples/review-packet-cli-smoke.py`, `python
  examples/review-packet-smoke.py`, `python -m compileall -q goal_harness`,
  `python examples/run-smokes.py`, `goal-harness check --scan-root .`, `git
  diff --check`, and a live `goal-harness review-packet --goal-id
  agent-harness-main-control` snippet showing the target guard before
  `read-only-map`. Critic: this does not solve the whole project-agent
  execution loop, but it removes a high-risk handoff ambiguity without adding
  user-facing complexity.
- 2026-06-02T18:59:02+08:00: User objected that the heartbeat PATH skip should
  be self-resolved instead of surfaced as a visible skip message. Fixed the
  root cause rather than relying on a one-off absolute path. The current
  `goal-harness-hourly-tick` automation was already hot-patched to export
  `$HOME/.local/bin`; this slice updated the public generators so future
  heartbeat and new-project prompts do the same. `render_cli_preflight()` now
  prepends `$HOME/.local/bin` before testing `command -v goal-harness`, so an
  already installed wrapper is found even when the automation shell starts with
  a minimal PATH. `heartbeat-prompt` now embeds the CLI preflight plus
  `goal-harness doctor` before quota guard, and explicitly treats remaining
  preflight failure as a no-work/no-spend quiet failure. Updated docs, smoke
  tests, and repo/installed skill guidance. Changed files:
  `goal_harness/project_prompt.py`, `goal_harness/heartbeat_prompt.py`,
  `docs/heartbeat-automation-prompt.md`, `docs/new-project-codex-prompt.md`,
  `examples/heartbeat-prompt-smoke.py`, `examples/project-prompt-smoke.py`,
  and `skills/goal-harness-project/SKILL.md`. Validation: `python
  examples/heartbeat-prompt-smoke.py`, `python examples/project-prompt-smoke.py`,
  `python examples/run-smokes.py`, `python -m compileall -q goal_harness`,
  `goal-harness check --scan-root .`, `git diff --check`, and a real preflight
  command with `export PATH="$HOME/.local/bin:$PATH"; goal-harness --format json
  quota should-run --goal-id goal-harness-meta` all passed. Critic: current and
  future heartbeat prompts are now PATH-self-healing; no quota spend was
  appended for the earlier failed preflight, correctly matching the accounting
  rule.
- 2026-06-02T18:42:16+08:00: Steering audit candidates: P0 state/safety for
  heartbeat PATH preflight, P0 project-agent execution loop via structured
  todo injection, and P1 one-click operator decision recording. Chose the todo
  CLI because the previous dashboard slice already made user todos visible,
  but project agents still had to know Markdown section names to add them.
  Added `goal-harness todo add --goal-id <goal> --role user|agent --text ...`,
  resolving the active state from registry `repo/state_file`, creating
  canonical `User Todo / Owner Review Reading Queue` or `Agent Todo` sections
  when absent, avoiding duplicate exact todo text, supporting `--dry-run`, and
  updating frontmatter `updated_at` on real writes. Updated the attention-queue
  doc plus the repo skill and installed local skill guidance so agents prefer
  the CLI over hand-editing sections. Changed files:
  `goal_harness/todos.py`, `goal_harness/cli.py`,
  `examples/todo-cli-smoke.py`, `docs/attention-queue.md`, and
  `skills/goal-harness-project/SKILL.md`. Validation: `python
  examples/todo-cli-smoke.py`, `python examples/run-smokes.py`, `python -m
  compileall -q goal_harness`, `goal-harness check --scan-root .`, a real
  dry-run against `goal-harness-meta`, and `git diff --check` passed. Critic:
  the first preflight command in this heartbeat failed because the automation
  shell PATH did not include `~/.local/bin`; I continued with the installed
  absolute wrapper, but the next slice should fix generated heartbeat prompts
  or PATH setup before adding more product surface.
- 2026-06-02T18:32:46+08:00: User pointed out three dashboard UX failures:
  packet copy was not available on every relevant action, the copied packet was
  too long and machine-oriented, and the separate yellow gate box plus lower
  white packet panel made one user decision look like two objects. Simplified
  the dashboard around one first-screen action-card model. Each visible
  `User Actions` card now has its own `Copy` button, the default copied packet
  is a short Chinese `Goal Harness Action` with only the decision, current
  state, safe path, and after-approval agent command, and the right-side
  `Operator Review Packet` panel is no longer rendered on the first screen.
  Controller/user-gated cards use a single amber action-card treatment, with
  user todo and operator question embedded in the same card. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx` and
  `examples/review-packet-smoke.py`. Validation: `npm --prefix apps/dashboard
  run build`, `python examples/review-packet-smoke.py`, `python
  examples/review-packet-cli-smoke.py`, `python examples/status-markdown-smoke.py`,
  `python examples/run-smokes.py`, `goal-harness check --scan-root .`, and
  `git diff --check` passed; Chrome live check at
  `http://127.0.0.1:5173/?statusUrl=%2Fstatus.local.json&actionKind=controller&goalId=agent-harness-main-control&lane=all&severity=all`
  confirmed a single `User Actions` panel, per-card copy, no rendered
  `Operator Review Packet` panel, and one unified action card for the platform
  migration gate/todo. Critic: the UI is now much less split-brained, but the
  next project-agent loop gap is still how agents add user/agent todos without
  hand-editing Markdown section names.
- 2026-06-02T18:21:18+08:00: User pointed out that the platform migration
  heartbeat UX was still poor: when a real gate exists, the agent should
  proactively ask the user which gate decision or todo progress is needed,
  instead of silently saying `should_run=false`. Refined the operator-gate
  contract again. `quota should-run` now carries `operator_question`,
  `gate_prompt`, `notify_user_on_gate`, and a compact `user_todo_summary` for
  `state=operator_gate`, while still omitting `agent_command` and returning
  `should_run=false`. Heartbeat and new-project prompts now say to send a
  concise Chinese `NOTIFY` gate question unless the same unresolved gate was
  already asked recently; safe-bypass work is only the follow-up path after the
  gate has already been surfaced. Also fixed quota accounting so a completed
  safe-bypass turn can preview/spend a quota slot even though the goal remains
  `state=operator_gate`. Updated README, quota/status/attention/heartbeat/new
  project docs, repo skill, installed local skill, and smoke tests. Validation:
  `python examples/run-smokes.py`, `goal-harness check --scan-root .`, live
  `quota should-run --goal-id premium-ui-ai-search-rec-migration` showing
  `notify_user_on_gate=true`, the real owner/SOP `gate_prompt`, and
  `user_todo_summary.open_count=9`; live `quota spend-slot --source heartbeat`
  dry-run for that gated goal now returns `ok=true` and
  `safe_bypass_spend=true`. Critic: this fixes the thread-level gate UX, but
  the dashboard still needs pruning so the same gate/todo is visible without
  extra panels or copy affordances.
- 2026-06-02T18:03:00+08:00: User challenged the platform migration guard
  wording: `human or target-controller gate must clear before spending compute`
  was too strict because an operator gate should not freeze unrelated high-value
  P0 analysis while the user is deciding. Refined the contract from a global
  freeze to a scoped blocker. `quota should-run` still returns
  `should_run=false` for `state=operator_gate` and still omits
  `agent_command`, but now includes `safe_bypass_allowed=true`,
  `blocked_action_scope=gated_delivery`, and a policy saying the heartbeat may
  do one independent read-only steering/analysis/documentation step that does
  not depend on the gate. Updated heartbeat/new-project prompts, README, quota
  docs, attention/status contracts, repo skill, and the installed local skill.
  Changed files: `goal_harness/quota.py`, `goal_harness/heartbeat_prompt.py`,
  `goal_harness/project_prompt.py`, `skills/goal-harness-project/SKILL.md`,
  docs, and smoke tests. Validation: `python examples/run-smokes.py`,
  `goal-harness check --scan-root .`, `npm --prefix apps/dashboard run build`,
  and live `quota should-run --goal-id premium-ui-ai-search-rec-migration`
  showing `should_run=false`, `state=operator_gate`,
  `safe_bypass_allowed=true`, and no `agent_command`. Critic: this fixes the
  overly conservative executor policy, but dashboard should eventually make
  the safe-bypass lane visible so the user can see that a gated project is not
  completely frozen.
- 2026-06-02T17:49:00+08:00: Recorded the user's approval for
  `agent-harness-main-control` to run only `read-only-map --dry-run`, with no
  write-control or main-control takeover. The durable operator gate appended
  `operator_gate_approved` at `2026-06-02T17:44:44+08:00`, and live status now
  reports `waiting_on=codex`, `quota.state=eligible`, and
  `agent_command=goal-harness read-only-map --goal-id agent-harness-main-control
  --dry-run`. While validating, found that the dry-run map still emitted
  `opt_in_required=true` because it only looked at registry adapter status
  `planned`; fixed `project_map.py` so planned adapter dry-runs read the latest
  `read_only_map_opt_in` operator gate and clear the opt-in risk after an
  approval, while real non-dry-run maps remain blocked for planned adapters.
  Added `examples/project-map-smoke.py`. Validation: `python
  examples/project-map-smoke.py`, `python examples/run-smokes.py`,
  `goal-harness check --scan-root .`, and `npm --prefix apps/dashboard run
  build` passed; a real dry-run for `agent-harness-main-control` now returns
  `opt_in_required=false`, `appended=false`, and residual risk only
  `project_local_goal_state_not_detected`. Critic: approval plumbing is now
  consistent, but agent-harness still needs project-local `.goal-harness` /
  `.codex/goals` state before it stops looking like a remote-only control
  target.
- 2026-06-02T17:40:00+08:00: User noticed the platform migration controller
  thread appeared to be blocked on an agent-harness-style `read-only map`
  user todo. Diagnosis: the platform heartbeat body and CLI Review Packet were
  correctly scoped to `premium-ui-ai-search-rec-migration`, but `read-only map`
  was a generic Goal Harness controller dry-run phrase and the dashboard
  first-screen operator banner selected the first global controller gate rather
  than preferring the selected URL `goalId`. Fixed both confusion sources:
  the first-screen `Needs decision` banner now prefers the selected goal's
  controller gate, and controller Review Packet suggestions/replies/operator
  gate dry-run reasons include the target goal id. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `goal_harness/review_packet.py`, `examples/review-packet-smoke.py`, and
  `examples/review-packet-cli-smoke.py`. Validation: `python
  examples/review-packet-smoke.py`, `python examples/review-packet-cli-smoke.py`,
  `python examples/run-smokes.py`, `goal-harness check --scan-root .`, and
  `npm --prefix apps/dashboard run build` passed; regenerated
  `apps/dashboard/public/status.local.json` and `apps/dashboard/dist/status.local.json`.
  Critic: this fixes visible/copyable cross-goal ambiguity, but the next
  stronger guard should make project agents reject any Review Packet whose
  `goal_id` differs from their active goal id.
- 2026-06-02T17:28:00+08:00: Added structured active-state todo extraction to
  status and dashboard. Registered goals now carry `repo` / `state_file` into
  status collection, `goal-harness status` parses checkbox sections named
  `## User Todo / Owner Review Reading Queue` and `## Agent Todo`, and
  attention items can include `user_todos`, `agent_todos`, and
  `todo_state_file`. The dashboard schema and `User Actions` panel now surface
  the first unfinished user todo before generic gate prose. Updated
  `goal_harness/history.py`, `goal_harness/status.py`,
  `apps/dashboard/src/data/status.ts`,
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/status-markdown-smoke.py`, `docs/status-data-contract.md`,
  `docs/attention-queue.md`, and `skills/goal-harness-project/SKILL.md`.
  Validation: `python examples/status-markdown-smoke.py`, `python
  examples/run-smokes.py`, `goal-harness check --scan-root .`, and
  `npm --prefix apps/dashboard run build` all passed; a real status refresh for
  the platform migration goal produced `user_todos.open_count=9` and first todo
  `Read the core Lark document section 8 first`; in-app browser was opened to
  `goalId=premium-ui-ai-search-rec-migration&actionKind=controller` and
  confirmed `Next user todo`, `9/9 open`, and the first todo are visible.
  Critic: the checkbox-section convention is intentionally low-friction, but a
  future `goal-harness todo add --role user|agent` command would be better for
  project agents because it avoids requiring them to know section names or
  Markdown formatting.
- 2026-06-02T17:11:07+08:00: Added a first-screen operator decision banner to
  the dashboard `User Actions` panel. When any action item is waiting on
  `user_or_controller` or `controller`, the panel now shows a compact
  `Needs decision` banner before the filters and cards, including gate count,
  selected goal id, quota chip, and the first operator question. Clicking the
  banner switches to the controller filter and selects that goal. Changed file:
  `apps/dashboard/src/views/dashboard-page.tsx`. Validation: `npm --prefix
  apps/dashboard run build` passed with the existing chunk-size warning;
  refreshed local `status.local.json` from live status; the live status source
  contains the real operator question and `quota.state=operator_gate` for the
  gated migration goal; source scan confirms the banner text is in the first
  screen component. Browser automation was unavailable in this tick because
  local Playwright was not installed and Chrome accessibility timed out.
  Critic: this improves the human decision loop with one visible banner, but a
  final browser screenshot/pass would still be useful before considering the
  dashboard polish fully done.
- 2026-06-02T17:03:54+08:00: Added registry-level attention overrides for
  registered goals. Optional public-safe registry fields now flow through
  history/status: `waiting_on`, `attention_status`, `recommended_action`,
  `operator_question`, and `next_handoff_condition`. `goal-harness status`
  respects `waiting_on` before latest-run classification, so a fresh
  `state_refreshed` run can still remain in `waiting_on=user_or_controller`
  when the real next gate is a human or target-controller decision; quota
  then returns `state=operator_gate` and `should_run=false`. Global registry
  sync now also preserves an existing attention override when another local
  source for the same goal syncs later without one, preventing a project-local
  registry from wiping the controller gate. Updated `goal_harness/status.py`,
  `goal_harness/history.py`, `goal_harness/registry.py`,
  `goal_harness/global_registry.py`, `examples/status-markdown-smoke.py`,
  `examples/global-registry-sync-smoke.py`, `docs/status-data-contract.md`,
  and `docs/attention-queue.md`. Private validation applied the override to
  one connected read-only migration goal without copying private evidence into
  this public state. Validation: status smoke, global-sync smoke, Python
  compileall for `goal_harness`, the full smoke suite, private registry sync,
  live `goal-harness status` / `quota should-run` assertions for the gated
  goal, `goal-harness check --scan-root .`, and `git diff --check`. Critic:
  agent-facing state truth is now corrected, but the dashboard still needs to
  make operator-gated cards obvious enough for a human to review from the first
  screen.
- 2026-06-02T16:36:11+08:00: Fixed the CS-Notes private wrapper registry view
  for the premium-ui migration goal. The private registry now includes
  `premium-ui-ai-search-rec-migration` as a connected read-only controller with
  project-local state and source-registry pointers; no private document URL or
  production evidence was copied into this public active state. Validation:
  the private registry parses as JSON, `goal-harness sync-global` from that
  registry succeeded with `source_goal_count=5`, targeted `goal-harness check`
  passed, local pre-tick now reports premium-ui as `registry_member=True` and
  `legacy_runtime_goal=False`, and global status reports findings=0. Critic:
  this resolves the registry truth gap, but the next state-truth issue is that
  premium-ui still appears as `eligible/codex` in status even though its current
  action text says owner/SOP decisions are the blocker; the next slice should
  decide whether that should become an operator-gated status.
- 2026-06-02T16:25:14+08:00: Corrected compute quota semantics after user
  feedback. `compute=1.0` is now the full 24-hour duty cycle rather than a
  24-event cap: the default slot budget is
  `window_hours * 60 / slot_minutes * compute`, with `slot_minutes=1`.
  Therefore `1.0` derives `1440` default minute-slots per 24h, `0.5` derives
  `720`, and `0.3` derives `432`. Removed the temporary
  `goal-harness-meta.quota.allowed_slots=1000000` override from the local
  source registry and shared global registry so full quota is expressed by
  plain `compute=1.0`. Changed files: `goal_harness/quota.py`,
  `README.md`, `docs/quota-allocation.md`, `docs/status-data-contract.md`,
  `docs/attention-queue.md`, `docs/codex-subagent-orchestration.md`,
  `docs/heartbeat-automation-prompt.md`, `skills/goal-harness-project/SKILL.md`,
  `examples/status.example.json`, `examples/quota-slot-spend-event.example.json`,
  dashboard quota smoke fixtures, and this active state. Validation:
  `python3 examples/quota-plan-smoke.py`, `python3
  examples/quota-contract-smoke.py`, and `python3
  examples/heartbeat-quota-flow-smoke.py` passed; live
  `goal-harness --format json quota should-run --goal-id goal-harness-meta`
  returns `should_run=true`, `allowed_slots=1440`, `spent_slots=25`.
  Critic: slot accounting is still an approximation of compute time; the
  default is now product-correct for minute-based heartbeats, while coarser
  controllers should spend the number of scheduler minutes they reserve.
- 2026-06-02T13:47:48+08:00: Ran the required steering audit after the
  platform migration heartbeat was re-activated. Candidates considered: P0
  state/safety observation of the actual platform migration heartbeat firing,
  P0 registry-truth correction for the CS-Notes wrapper registry still showing
  `premium-ui-ai-search-rec-migration` as a legacy runtime goal, and P1
  dashboard attention-cost reduction. Chose the actual heartbeat observation
  because the previous slice only restored ACTIVE status. Observation result:
  the platform migration automation is still `ACTIVE`, points at thread
  `019e822b-7e71-7a32-9dd2-d86b194ba5dd`, and the shared runtime now has
  `premium-ui-ai-search-rec-migration` runs at 13:45:42
  (`state_refreshed`) and 13:45:51 (`operator_gate_deferred`). Validation:
  `goal-harness --format json quota should-run --goal-id
  premium-ui-ai-search-rec-migration` still returns `should_run=false`,
  `state=operator_gate`; no `quota_slot_spent` artifact exists for that goal.
  Critic: this confirms the corrected platform-controller heartbeat path is
  live and gate-respecting. The next higher-value state-truth slice is to
  reconcile the local wrapper registry so premium-ui no longer appears as a
  legacy runtime goal.
- 2026-06-02T13:40:20+08:00: Ran the required steering audit after reverting
  the premature agent-harness main-control automation migration. Candidates
  considered: P0 state/safety observation of the platform migration heartbeat
  under its operator gate, P0 human-decision recording for the
  `agent-harness-main-control` read-only-map opt-in, and P1 dashboard
  attention-cost reduction. Chose the platform migration heartbeat observation
  because it is the user's latest corrected target and should prove the new
  heartbeat lifecycle before any complex-controller migration. Observation
  found that the platform migration automation had returned to PAUSED even
  though its target thread and generated prompt were correct. Re-activated it
  through the Codex App automation API and confirmed the local automation file
  now shows status `ACTIVE`. Validation: `goal-harness --format json quota
  should-run --goal-id premium-ui-ai-search-rec-migration` returned
  `should_run=false`, `state=operator_gate`, so the target heartbeat should
  fail-close and quiet-skip until the human or target controller clears the
  owner/SOP gate. Critic: this is a state-stability correction rather than new
  product capability, but it protects the real platform migration integration.
- 2026-06-02T12:39:08+08:00: User corrected the previous automation migration:
  `agent-harness-main-control` is still too complex to migrate, while the
  platform migration controller should receive the generated Goal Harness
  heartbeat first. Reverted the local agent-harness main-control automation to
  its original short prompt and created a new platform migration heartbeat for
  `premium-ui-ai-search-rec-migration` using the generated lifecycle: quota
  should-run guard, quiet skip, steering audit, bounded work, validation,
  refresh-state, and exactly one spend-slot after a completed turn. Validation:
  local automation config now shows the agent-harness main-control prompt back
  to the original short form; the new platform migration heartbeat points at
  `premium-ui-ai-search-rec-migration` and its project active state. Critic:
  keep agent-harness main-control on manual/operator-gated read-only opt-in
  until its complexity is handled deliberately.
- 2026-06-02T12:29:18+08:00: Migrated one stale local main-control automation
  from a short "advance TODO" style prompt to the generated Goal Harness
  heartbeat lifecycle. The updated automation now advances
  `agent-harness-main-control`, runs `goal-harness --format json quota
  should-run --goal-id agent-harness-main-control` before delivery work,
  refreshes state when needed, and appends at most one heartbeat spend event
  after a completed turn. Validation: the automation file now contains the
  generated lifecycle prompt; `goal-harness --format json quota should-run
  --goal-id agent-harness-main-control` returns `should_run=false` with
  `state=operator_gate`, so the automation will quietly skip until the user or
  target controller clears the read-only map opt-in. Losing high-value
  candidate: updating every old automation at once would be broader than this
  heartbeat slice. Critic: this improves state/safety by preventing the old
  main-control automation from bypassing Goal Harness, but it also means real
  agent-harness delivery now depends on the explicit operator decision.
- 2026-06-02T12:25:10+08:00: User clarified that project goal prompts and
  automations should converge across projects; the screenshot showed a short
  visible goal text (`按 ACTIVE_GOAL_STATE.md，基于 Goal Harness 体系，推进项目`)
  while the Goal Harness heartbeat uses a much richer lifecycle prompt. The
  design decision is two layers: keep visible Codex goal text short and
  human-scannable, but make recurring heartbeat automation bodies nearly
  identical and generated by `goal-harness heartbeat-prompt`, with only
  `goal_id`, `active_state`, and narrow project boundary rules changing.
  Updated `docs/heartbeat-automation-prompt.md`, `docs/integration.md`, and
  `skills/goal-harness-project/SKILL.md` with this rule, and extended
  `examples/heartbeat-prompt-smoke.py` to protect it. Reinstalled the local
  skill copy. Changed files: `docs/heartbeat-automation-prompt.md`,
  `docs/integration.md`, `skills/goal-harness-project/SKILL.md`,
  `examples/heartbeat-prompt-smoke.py`, and this active state. Validation:
  `python3 examples/heartbeat-prompt-smoke.py` passed; `python3
  examples/run-smokes.py` passed with 9 scripts; `scripts/install-local.sh`
  synced installed skill; `goal-harness check --scan-root .` passed; `git diff
  --check` passed. Critic: this documents the rule, but existing older
  automations such as short "advance TODO" prompts still need migration to the
  generated lifecycle when the target goal is ready.
- 2026-06-02T12:15:46+08:00: Used the required steering audit after adding the
  CLI-visible Review Packet. Candidates considered: P0 real adapter proof for
  `agent-harness-main-control`, P0 dashboard attention-cost reduction, and P0
  project-agent skill guidance. Real adapter proof still requires user or
  controller opt-in; attention-cost reduction should be a deliberate UI
  deletion/merge slice, not another panel. Chose project-agent skill guidance
  because Review Packet was now available from CLI but new project agents would
  not discover it during normal Goal Harness setup. Added a `Generate A Review
  Packet` section to `skills/goal-harness-project/SKILL.md`, documenting
  `goal-harness review-packet --goal-id <goal>` and
  `goal-harness --format json review-packet --goal-id <goal>` as read-only
  packet inspection commands, and clarifying that local gate drafts are for the
  user/controller rather than the target project agent. Extended
  `examples/install-local-smoke.py` so the installer must copy this guidance
  into the installed Codex skill. Reinstalled the local skill copy under
  `$HOME/.codex/skills/goal-harness-project`. Losing
  high-value candidate: real adapter proof should resume only after controller
  opt-in; attention-cost reduction should remove or merge existing UI
  attention, not add more. Changed files:
  `skills/goal-harness-project/SKILL.md`, `examples/install-local-smoke.py`,
  and this active state. Validation: `python3 examples/install-local-smoke.py`
  passed; `scripts/install-local.sh` synced the installed skill;
  `rg "Generate A Review Packet|review-packet --goal-id|target project agent must not run" $HOME/.codex/skills/goal-harness-project/SKILL.md`
  confirmed installed guidance; `python3 examples/run-smokes.py` passed with 9
  scripts; `goal-harness check --scan-root .` passed; `git diff --check`
  passed. Critic: this closes the discoverability gap for target project
  agents. Further packet work should wait for real project usage.
- 2026-06-02T12:10:25+08:00: Used the required steering audit after clarifying
  project-agent packet boundaries. Candidates considered: P0 real adapter
  proof, P0 attention-cost reduction, and P0 CLI-visible packet formatter.
  Real adapter proof remains gated on controller opt-in; attention-cost
  reduction requires a deliberate UI deletion/merge decision. Chose the
  CLI-visible packet formatter because the previous packet improvements were
  still browser-only, while project agents and controller threads need a
  read-only command they can run from status. Added
  `goal_harness/review_packet.py` and the `goal-harness review-packet` CLI
  command. It collects status, infers reward/controller/codex/evidence/health
  packet kind, emits a Markdown packet or JSON payload, includes the same human
  decision boundary and project-agent forwarding/execution/stop conditions, and
  never writes registry or runtime history. Added
  `examples/review-packet-cli-smoke.py`, README usage, and status-contract
  wording that the CLI packet remains read-only packaging, not durable
  approval. Losing high-value candidate: real adapter proof should resume only
  after controller opt-in; attention-cost reduction should be a product
  deletion/merge slice. Changed files: `goal_harness/review_packet.py`,
  `goal_harness/cli.py`, `examples/review-packet-cli-smoke.py`, `README.md`,
  `docs/status-data-contract.md`, and this active state. Validation: `python3
  examples/review-packet-cli-smoke.py` passed; `python3
  examples/review-packet-smoke.py` passed; `python3 -m py_compile
  goal_harness/review_packet.py goal_harness/cli.py
  examples/review-packet-cli-smoke.py` passed; `goal-harness review-packet
  --help` works; `python3 examples/run-smokes.py` passed with 9 scripts;
  `goal-harness check --scan-root .` passed; `git diff --check` passed.
  Critic: the packet is now usable outside the browser. Further packet work
  should move into installed project-agent guidance or wait for a real
  controller opt-in, not keep polishing packet prose.
- 2026-06-02T12:04:21+08:00: Used the required steering audit after approved
  gate browser coverage. Candidates considered: P0 project-agent packet
  legibility, P0 real adapter proof, and P0 attention-cost reduction. Chose
  project-agent packet legibility because real adapter proof still requires a
  controller opt-in, while the copied Review Packet could make the target
  project agent infer too much from the human-facing context. Updated
  `buildProjectAgentPacketText()` so each project-agent section names a
  forwarding condition, execution boundary, and stop condition before showing a
  command. Controller packets now say they are forwarded only after explicit
  read-only/controller dry-run agreement, the project agent must not run the
  local gate draft, and it must stop for real approval, write-control,
  run-history append, production action, or command failure. Updated the
  Review Packet smoke and status data contract to protect that shape. Losing
  high-value candidate: real adapter proof should resume only after controller
  opt-in, and attention-cost reduction needs a deliberate UI deletion/merge
  decision. Changed files: `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/review-packet-smoke.py`, `docs/status-data-contract.md`, and this
  active state. Validation: `python3 examples/review-packet-smoke.py` passed;
  dashboard `npm run build` passed; `python3 examples/run-smokes.py` passed
  with 8 scripts; `goal-harness check --scan-root .` passed; `git diff
  --check` passed. Critic: this lowers target-agent ambiguity without adding
  UI. The next adjacent work should only continue packet mechanics if it makes
  packets available through CLI/status rather than more browser-only text.
- 2026-06-02T12:00:21+08:00: Used the required steering audit after the
  suggested-decision dashboard slice. Candidates considered: P0 approved-gate
  transition coverage, P0 real adapter proof, and P0 project-agent packet
  legibility. Chose approved-gate transition coverage because real adapter
  proof still requires a controller opt-in, while the dashboard contract needed
  to prove that an approved operator gate becomes a Codex-ready handoff rather
  than remaining user-gated. Extended
  `examples/dashboard-operator-gate-browser-smoke.mjs` with an approved
  operator-gate fixture. The smoke now loads both pending and approved status
  payloads: pending must show controller approval copy and hide Codex-ready
  copy; approved must show a Codex action, the approved agent command, and hide
  operator-question / approval copy. Losing high-value candidate: project-agent
  packet legibility remains the next P0 slice if no controller opt-in arrives.
  Changed files: `examples/dashboard-operator-gate-browser-smoke.mjs` and this
  active state. Validation: `node
  examples/dashboard-operator-gate-browser-smoke.mjs` passed; `python3
  examples/run-smokes.py` passed with 8 scripts; `goal-harness check
  --scan-root .` passed; `git diff --check` passed. Critic: this improves
  confidence in the human-decision state transition without expanding the UI;
  the next work should either make the packet easier for project agents or wait
  for a real controller opt-in.
- 2026-06-02T11:52:53+08:00: Used the required steering audit after the
  global-registry sync slice. Candidates considered: P0 human-decision
  dashboard simplification, P0 real adapter proof, and P0 project-agent packet
  legibility. Chose human-decision simplification because the dashboard already
  exposed a single review packet, but the user still had to infer the actual
  recommended judgment from surrounding copy. Added a compact suggested
  decision line to controller review packets and the right-side Review Packet
  panel. For read-only-map controller opt-ins it now says the operator can
  approve a dry-run only, without granting writes or controller takeover.
  Losing high-value candidate: real adapter proof should resume only after the
  controller opt-in gate is answered. Changed files:
  `apps/dashboard/src/views/dashboard-page.tsx`,
  `examples/dashboard-operator-gate-browser-smoke.mjs`, and this active state.
  Validation: `npm run build` passed in the dashboard app; `node
  examples/dashboard-operator-gate-browser-smoke.mjs` passed; `python3
  examples/status-markdown-smoke.py` passed; `python3 examples/run-smokes.py`
  passed with 8 scripts; `goal-harness check --scan-root .` passed; `git diff
  --check` passed. Critic: this is deliberately a small review-cost reduction,
  not another dashboard feature expansion. The next UI work should remove or
  merge attention cost, or cover the approved-gate transition, rather than add
  more panels.
- 2026-06-02T11:40:00+08:00: Ran the required steering audit after two P1
  intro-writing slices and recent prompt/skill work. Candidates considered:
  P0 state truth/safety (`quota_slot_spent` was masking current status in
  `quota should-run` and dashboard attention), P0 human-decision/dashboard
  simplification, and P0 real adapter proof. Chose state truth/safety because
  accounting events were becoming the visible current work classification,
  which pollutes both operator-facing dashboard state and agent-facing quota
  guards. Made `quota_slot_spent` status-neutral: run history and quota
  counting still see the event, but status/attention/`should-run` use the
  latest non-accounting run. Also fixed the deeper same-second artifact
  collision by writing quota spend artifacts with a `-quota-slot-spent`
  suffix and a unique fallback, so a post-refresh spend cannot overwrite the
  refresh run. Losing high-value candidate: dashboard/review-packet
  simplification remains the next likely P0 slice now that the state source is
  trustworthy. Changed files: `goal_harness/status.py`,
  `goal_harness/history.py`, `goal_harness/quota.py`,
  `examples/status-markdown-smoke.py`,
  `examples/heartbeat-quota-flow-smoke.py`,
  `docs/status-data-contract.md`, and `docs/quota-allocation.md`.
  Validation: `python3 examples/status-markdown-smoke.py` passed; `python3
  examples/heartbeat-quota-flow-smoke.py` passed; `python3
  examples/quota-plan-smoke.py` passed; `python3 examples/run-smokes.py`
  passed with 8 scripts; `python3 -m py_compile goal_harness/status.py
  goal_harness/history.py goal_harness/quota.py
  examples/status-markdown-smoke.py examples/heartbeat-quota-flow-smoke.py`
  passed; `goal-harness check --scan-root .` passed; `goal-harness --format
  json quota should-run --goal-id goal-harness-meta` now reports
  `status=state_refreshed` while retaining `spent_slots=13/24`; `git diff
  --check` passed. Critic: this closes a real state-truth bug uncovered by the
  heartbeat flow; next work should move back to human-decision/dashboard or
  real adapter proof rather than keep polishing quota internals.
- 2026-06-02T11:17:38+08:00: Used the new steering audit on the first automatic
  tick after `3b1083f`. Candidates considered: P0 project-agent loop
  hardening, P0 human-decision/dashboard simplification, and P1 public
  storytelling. Chose project-agent loop hardening because installed project
  agents still needed to learn that `quota should-run` is compute quota only;
  `should_run=true` must trigger a cross-lane steering audit before work. Added
  that rule to `skills/goal-harness-project/SKILL.md` and extended
  `examples/install-local-smoke.py` so temporary installs verify the shipped
  skill contains steering-audit, continuation-check, and compute-vs-focus quota
  guidance. Losing high-value candidate: dashboard/review-packet simplification
  remains important for the human decision loop, but should be re-compared on
  the next tick rather than selected by inertia. Validation:
  `python3 examples/install-local-smoke.py` passed; `python3
  examples/heartbeat-prompt-smoke.py` passed; `python3 -m py_compile
  examples/install-local-smoke.py` passed; `goal-harness check --scan-root .`
  passed; `git diff --check` passed.
- 2026-06-02T11:11:23+08:00: Operationalized the steering audit in the
  heartbeat prompt path. `goal_harness/heartbeat_prompt.py` now tells automatic
  ticks to read recent progress and critic, list at least three plausible
  P0/P1/P2 candidates when useful, apply a continuation check for repeated
  topics, keep compute quota separate from focus quota, and record losing
  high-value candidates before choosing exactly one bounded step. Updated
  `docs/heartbeat-automation-prompt.md` and
  `examples/heartbeat-prompt-smoke.py` so the public copy-paste template and
  smoke protect the same contract. Updated the live
  `goal-harness-hourly-tick` Codex App heartbeat prompt to the generated
  steering-audit task body while preserving the one-minute cadence. Validation:
  `python3 examples/heartbeat-prompt-smoke.py` passed; `python3 -m py_compile
  goal_harness/heartbeat_prompt.py examples/heartbeat-prompt-smoke.py` passed;
  CLI JSON generation for `goal-harness-meta` includes the steering audit and
  spend command. Critic: this closes the prompt-path gap, but future ticks must
  prove the audit is actually used for cross-lane selection rather than
  continuing the nearest adjacent cleanup by inertia.
- 2026-06-02T10:59:10+08:00: Added a steering audit contract to
  `docs/state-interaction-model.md` and clarified the README quota section.
  The new rule names the failure observed in the overnight quota chain:
  `quota should-run` is a compute guard, not a strategy selector. Autonomous
  goal ticks should list at least three plausible candidates across different
  lanes, choose by the priority stack rather than the previous adjacent critic,
  run a continuation check when one topic has consumed several recent slices,
  separate compute quota from focus quota, and record losing high-value
  candidates when useful. Follow-up clarification: the continuation check is
  not a hard WIP cap; large topics may continue when they still win the
  cross-lane priority comparison. Validation: README links the quota guard back to the state
  interaction model; `rg` confirms the steering audit and compute-guard
  boundary are present; public contract check and smoke validation will run
  before commit. Critic: documentation fixes the decision boundary, but future
  heartbeats still need the prompt path to require this audit before executing
  another local slice.
- 2026-06-02T09:29:11+08:00: Added
  `examples/dashboard-operator-gate-browser-smoke.mjs`, a browser-level
  dashboard smoke for planned high-complexity operator-gate visibility. The
  smoke writes a temporary public-safe status fixture, starts the dashboard
  Vite server, opens the first screen through Playwright CLI, and verifies the
  goal appears as `Controller` / `Review controller opt-in` with an
  `Operator question`, `Quota 0.5`, and `Agent command ready after approval`.
  It also rejects `0 actions`, `No user-facing action is active`, and
  Codex-ready copy such as `Let Codex continue`. Documented explicit browser
  smoke entrypoints in `apps/dashboard/README.md`. Validation: new
  operator-gate browser smoke passed; existing throttled browser smoke passed;
  aggregate public smokes passed with 8 scripts; Python compile passed; public
  contract check passed; `git diff --check` passed. Critic: planned opt-in is
  now protected from CLI guard through browser first screen; the paired
  approved-gate transition still needs dashboard coverage so the UI can safely
  distinguish "preview only" from "approval recorded".
- 2026-06-02T09:22:14+08:00: Tightened the planned high-complexity opt-in
  contract so preview commands stay human-facing and do not leak into
  executor-facing skip payloads. `build_quota_should_run()` now returns
  `agent_command` only when `should_run=true`; `examples/status-markdown-smoke.py`
  now asserts that the initial planned read-only-map preview stays
  `waiting_on=user_or_controller`, renders `operator_gate_dry_run` before
  `agent_command`, and still returns `should_run=false`, `state=operator_gate`,
  with no `agent_command` in the quota guard. Updated
  `docs/status-data-contract.md` and `docs/attention-queue.md` to name the
  status-display versus executor-guard split. Validation: direct status
  markdown smoke passed; review packet smoke passed; quota plan smoke passed;
  quota contract smoke passed; aggregate public smokes passed with 8 scripts;
  Python compile passed; public contract check passed; `git diff --check`
  passed. Critic: the CLI/agent-facing guard is now cleaner, but the dashboard
  first screen should get a browser-level smoke so the human UI cannot collapse
  planned opt-in preview into Codex-ready work.
- 2026-06-02T09:10:47+08:00: Added
  `examples/install-local-smoke.py`, a temp-HOME installer smoke. The smoke
  runs `scripts/install-local.sh` with isolated `HOME`, `CODEX_HOME`,
  `GOAL_HARNESS_BIN_DIR`, and shell profile; verifies the installed wrapper
  symlink resolves to `scripts/goal-harness`; checks the generated shell profile
  contains the Goal Harness PATH block once; reads the installed
  `goal-harness-project` skill and verifies `Set Up Recurring Heartbeats`,
  `goal-harness heartbeat-prompt`, and `--source heartbeat --execute`; then
  runs the installed CLI wrapper to generate a JSON `heartbeat-prompt` payload
  and checks the guard/spend commands plus `DONT_NOTIFY` boundary. Validation:
  direct install-local smoke passed; aggregate public smokes passed with 8
  scripts; Python compile passed; public contract check passed; `git diff
  --check` passed. Critic: heartbeat automation setup is now covered from docs
  to generator to install path; the next P0 gap should move back to
  human/controller gate visibility rather than more heartbeat polish.
- 2026-06-02T09:04:50+08:00: Taught project agents and project-connection docs
  to discover `goal-harness heartbeat-prompt` without reading README first.
  Added a `Set Up Recurring Heartbeats` section to
  `skills/goal-harness-project/SKILL.md`, documented the generated task-body
  workflow in `docs/integration.md`, and updated both the static and generated
  new-project handoff prompts so connected projects know to generate a Codex
  App heartbeat task body instead of hand-copying the quota guard and spend
  protocol. Extended `examples/heartbeat-prompt-smoke.py` and
  `examples/project-prompt-smoke.py` so the skill, integration doc, static
  prompt, generated CLI prompt, and heartbeat prompt contract all mention the
  generator. Ran `scripts/install-local.sh` on the current machine and verified
  the installed local `goal-harness-project` skill
  includes `Set Up Recurring Heartbeats`, `goal-harness heartbeat-prompt`, and
  `--source heartbeat --execute`. Validation: direct heartbeat prompt smoke
  passed; direct project prompt smoke passed; aggregate public smokes passed
  with 7 scripts; Python compile passed; public contract check passed; `git
  diff --check` passed. Critic: the current-machine installed skill is synced,
  but the install-path guarantee should be protected in a temp-HOME installer
  smoke so future edits cannot silently drop the skill guidance.
- 2026-06-02T08:58:10+08:00: Added a public
  `goal-harness heartbeat-prompt` CLI generator. The new
  `goal_harness/heartbeat_prompt.py` builder emits a guarded Codex App
  heartbeat task body from `--goal-id` and `--active-state`, reusing the same
  quota guard and heartbeat spend commands as other prompts. Wired the command
  into `goal_harness/cli.py`, documented it in README and
  `docs/heartbeat-automation-prompt.md`, and extended
  `examples/heartbeat-prompt-smoke.py` to verify the builder, CLI JSON, CLI
  Markdown, docs link, README link, skip-without-compute boundary,
  `refresh-state`, and exactly-once `quota spend-slot --source heartbeat
  --execute`. Validation: direct heartbeat prompt smoke passed; aggregate
  public smokes passed with 7 scripts; Python compile passed; public contract
  check passed; `git diff --check` passed. Critic: the CLI now removes
  copy/paste drift, but future Codex sessions will discover it most reliably
  only after the installed `goal-harness-project` skill and connection docs
  mention the command.
- 2026-06-02T08:51:28+08:00: Added
  `docs/heartbeat-automation-prompt.md`, a public copy-paste Codex App
  heartbeat template for the guarded quota lifecycle: pre-turn
  `quota should-run`, `should_run=false` skip-without-compute, exactly one
  bounded verifiable step, validation, active-state writeback, optional
  `refresh-state`, exactly one post-turn `quota spend-slot --source heartbeat
  --execute`, and compact heartbeat reporting. Linked it from README and added
  `examples/heartbeat-prompt-smoke.py` to protect the prompt structure,
  ordering, skip boundary, refresh command, and spend-once command. Validation:
  direct heartbeat prompt smoke passed; aggregate public smokes passed with 7
  scripts; Python compile passed; public contract check passed; `git diff
  --check` passed. Critic: the public template now prevents prompt drift, but
  project agents still need a CLI generator so they can produce the same
  guarded task body with the right goal id and active-state path.
- 2026-06-02T08:40:09+08:00: Added
  `examples/heartbeat-quota-flow-smoke.py`, an executable dependency-free smoke
  for the full heartbeat quota lifecycle. The smoke creates a temporary
  public-safe project, registry, runtime, and active state; runs CLI
  `quota should-run` and verifies the goal is eligible at 0/2 slots; writes a
  bounded heartbeat work marker; validates it with `goal-harness check`; appends
  a state-only `refresh-state` run; asserts no spend event was written before
  accounting; executes exactly one `quota spend-slot --source heartbeat
  --execute`; verifies the runtime index has exactly one `quota_slot_spent`
  event; runs a follow-up `quota should-run` and observes derived
  `spent_slots=1/2` with `status=quota_slot_spent`; and checks the registry
  stayed byte-for-byte unchanged. Validation: direct heartbeat quota flow smoke
  passed; aggregate public smokes passed with 6 scripts; Python compile passed;
  public contract check passed; `git diff --check` passed. Critic: the
  lifecycle is now executable, but scheduled heartbeat setup still needs a
  reusable prompt/template so other goals do not have to rediscover the guard
  and post-turn spend order.
- 2026-06-02T08:31:45+08:00: Standardized the post-turn spend accounting
  protocol in agent-facing prompts and public docs. The generated
  `new-project-prompt` now includes both the pre-turn `quota should-run` guard
  and the post-turn `quota spend-slot --execute` rule: only append one spend
  event after the turn actually spent delivery compute and after validation
  plus any needed `refresh-state`; do not account `should_run=false` skips,
  preflight failures, pure dry-run previews, or duplicate attempts. Updated the
  copy-paste prompt doc, README, and quota allocation contract with the same
  boundary. Extended `examples/project-prompt-smoke.py` and
  `examples/quota-contract-smoke.py` so the generated prompt, CLI markdown,
  docs, README, and contract text all preserve the protocol. Validation:
  direct project-prompt smoke passed; direct quota-contract smoke passed;
  aggregate public smokes passed with 5 scripts; Python compile passed; public
  contract check passed; `git diff --check` passed. Critic: the protocol is
  now visible to project agents, but it is still text-level guidance; next
  step should prove a full heartbeat lifecycle in an executable smoke.
- 2026-06-02T08:23:25+08:00: Taught status/quota planning to derive current
  `spent_slots` from compact `quota_slot_spent` runtime events. Added
  `goal_quota_with_spend_ledger()` so `collect_history()` builds per-goal quota
  from registry policy plus runtime spend events in the current quota window.
  `quota_slot_spent` is now a status-visible classification, so appending a
  spend event does not make a Codex-ready goal disappear from the attention
  queue. The quota smoke fixture no longer stores `spent_slots` in registry;
  it writes compact index rows plus JSON quota events, verifies the derived
  near-limit and throttled lanes, executes a real `quota spend-slot --execute`
  in a temp runtime, proves the next `quota should-run` turns throttled, and
  checks the registry file stayed byte-for-byte unchanged. Updated
  `docs/quota-allocation.md` and `docs/status-data-contract.md` to name the
  source-of-truth split: registry is policy, runtime events are the spend
  ledger. Validation: direct quota-plan smoke passed; direct quota contract
  smoke passed; aggregate public smokes passed with 5 scripts; Python compile
  passed; public contract check passed; `git diff --check` passed. Critic:
  spend derivation is now real, but automatic executors still need a standard
  post-turn accounting protocol so successful heartbeats reliably append one
  spend event after validation/writeback.
- 2026-06-02T08:12:26+08:00: Implemented the smallest append-only quota slot
  spend writer. `goal-harness quota spend-slot --goal-id <goal-id> --slots 1`
  now defaults to dry-run, while `--execute` appends a compact
  `quota_slot_spent` runtime event after a fresh eligible `quota should-run`
  decision. The writer records before/after quota state, source, slot count,
  JSON/Markdown paths, and index entry; it leaves registry, reward overlays,
  operator gates, write-control, private evidence, and production identifiers
  untouched. Updated `docs/quota-allocation.md` to document the default dry-run
  and explicit execute behavior, and extended `examples/quota-plan-smoke.py` to
  verify both default dry-run and execute over a temporary public-safe
  registry/runtime. Validation: direct quota-plan smoke passed; direct quota
  contract smoke passed; aggregate public smokes passed with 5 scripts; Python
  compile passed; public contract check passed; `git diff --check` passed.
  Critic: the writer now creates durable spend events, but status/quota still
  does not derive current spent slots from those events, so the next executable
  gap is spend-ledger derivation rather than another write command.
- 2026-06-02T08:03:30+08:00: Defined the public runtime event contract for a
  future real quota slot spend write path. `docs/quota-allocation.md` now names
  `classification=quota_slot_spent`, the nested `quota_event` fields, the
  public/private boundary, and the validation rule: only write after a fresh
  eligible `quota should-run`, require positive slots, require
  `after.spent_slots = before.spent_slots + slots`, mark the after state
  throttled when the window is exhausted, and keep human reward/operator
  gate/write-control/private evidence out of the event. Added the sanitized
  fixture `examples/quota-slot-spend-event.example.json`, and extended
  `examples/quota-contract-smoke.py` to parse and validate that fixture.
  Validation: direct quota contract smoke passed; aggregate public smokes
  passed with 5 scripts; fixture JSON parsed through `python3 -m json.tool`;
  Python compile passed; public contract check passed; `git diff --check`
  passed. Critic: the write-path contract is now protected, but no command
  appends this event yet, so real automatic turns still cannot durably advance
  spent slots.
- 2026-06-02T07:56:55+08:00: Added a preview-only quota slot accounting path.
  `goal-harness quota spend-slot --goal-id <goal-id> --slots 1 --dry-run`
  now reports the before/after `quota should-run` decision for an eligible
  goal without mutating registry, runtime history, reward overlays, or operator
  gates. The public smoke fixture adds a `near-limit-half` goal at 11/12 slots
  and verifies that a one-slot dry-run would move it from `eligible` to
  `throttled`, while a follow-up real `quota should-run` over the same fixture
  remains `eligible` at 11/12 slots. Changed files:
  `goal_harness/quota.py`, `goal_harness/cli.py`,
  `examples/quota-plan-smoke.py`, and `docs/quota-allocation.md`. Validation:
  direct quota-plan smoke passed; aggregate public smokes passed with 5
  scripts; Python compile passed; dashboard production build passed with the
  existing >500 kB chunk warning; public contract check passed; `git diff
  --check` passed. Critic: quota accounting now has a safe preview surface, but
  real slot spending still lacks a compact runtime event contract and write
  path, so controllers cannot yet update `spent_slots` durably after a real
  automatic turn.
- 2026-06-02T07:46:31+08:00: Added
  `examples/dashboard-throttled-browser-smoke.mjs`, a standalone browser-level
  smoke that creates a temporary public-safe throttled status fixture, starts
  the dashboard dev server, opens it through Playwright CLI, and verifies the
  first screen shows the throttled quota chip/review line while User Actions
  stays at `0 actions`. The script deletes its temporary fixture and
  `.playwright-cli/` output; `.gitignore` now ignores that generated output
  directory. Validation: the new browser smoke passed; aggregate public smokes
  passed with 5 scripts; Python compile passed; dashboard production build
  passed with the existing >500 kB chunk warning; public contract check passed;
  `git diff --check` passed. Critic: throttled quota is now protected from
  planner to CLI to source-level dashboard logic to real browser rendering; the
  next P0 gap is actual slot accounting, because `should-run` can only throttle
  if spent slots are updated by a standard accounting path.
- 2026-06-02T07:37:58+08:00: Tightened the dashboard User Actions builder so a
  `waiting_on=codex` item with `quota.state=throttled` is treated as quiet
  scheduling state instead of a human-facing Codex action. The selected goal can
  still show the throttled quota chip/review line, but the first-screen action
  queue no longer tells the user or project agent that Codex should continue
  when compute quota is spent. Extended `examples/review-packet-smoke.py` to
  protect the throttled quota labels and the ordering that filters throttled
  Codex items before the generic Codex action branch. Validation: direct
  Review Packet smoke passed; aggregate public smokes passed with 5 scripts;
  Python compile passed; dashboard production build passed with the existing
  >500 kB chunk warning; public contract check passed; `git diff --check`
  passed. Critic: the source and smoke now protect the no-extra-user-action
  boundary; the next narrow gap is a browser-level check with a public-safe
  throttled status fixture.
- 2026-06-02T07:33:20+08:00: Extended `examples/quota-plan-smoke.py` to cover
  the executable `quota should-run --format json` path for a throttled goal.
  The smoke now builds a temporary public-safe registry/runtime/project,
  invokes `python -m goal_harness.cli --format json quota should-run --goal-id
  throttled-half`, and verifies the project-agent-facing skip payload exposes
  `state=throttled`, `should_run=false`, `decision=skip`, spent/allowed slots
  `12/12`, no `agent_command`, and the same `plan_summary.next_automatic_turn`
  as the quota plan. Validation: direct quota-plan smoke passed; aggregate
  public smokes passed with 5 scripts; Python compile passed; public contract
  check passed; `git diff --check` passed. Critic: throttled quota behavior is
  now guarded across planner, CLI plan, in-process should-run, and CLI
  should-run; the remaining nearby P0 gap is making the human-facing
  status/dashboard surface show throttled quota as quiet scheduling state, not
  as another user decision.
- 2026-06-02T07:29:50+08:00: Extended `examples/quota-plan-smoke.py` with a
  public-safe throttled quota fixture. The fixture adds `throttled-half` with
  `quota.compute=0.5` and spent slots equal to allowed slots, verifies the goal
  lands in the `throttled` lane, stays out of `eligible`, does not become
  `summary.next_automatic_turn`, and returns `should_run=false` through
  `build_quota_should_run()`. The CLI quota-plan fixture now carries the same
  throttled project in its temporary registry/runtime. Validation: direct
  quota-plan smoke passed; aggregate public smokes passed with 5 scripts;
  Python compile passed; public contract check passed; `git diff --check`
  passed. Critic: quota throttling behavior is now guarded for planner and
  in-process should-run logic; the remaining narrow gap is executable
  `quota should-run --format json` CLI output for the throttled skip payload.
- 2026-06-02T07:22:35+08:00: Tightened the quota-plan note in
  `docs/status-data-contract.md` to name the same lane boundary as
  `docs/quota-allocation.md`: `next_automatic_turn` is advisory, may only name
  the first eligible goal, and operator-gated, waiting, throttled, paused, and
  health-blocked goals must stay out of the eligible lane even with high
  `quota.compute`. Extended `examples/quota-contract-smoke.py` to assert that
  status-contract wording. Validation: direct quota contract smoke passed;
  aggregate public smokes passed with 5 scripts; Python compile passed; public
  contract check passed; `git diff --check` passed. Critic: the quota boundary
  is now consistent across README, quota allocation docs, and status data
  contract; the next P0 gap is behavior coverage for quota throttling, not more
  prose.
- 2026-06-02T07:17:33+08:00: Extended `examples/quota-contract-smoke.py` so the
  same public text smoke now also covers `docs/status-data-contract.md`. It
  asserts that quota status and quota plan derive their grouping from the status
  payload, `quota should-run` derives the per-goal guard from that grouping, the
  quota commands are read-only views rather than a separate source of truth, and
  scripts must treat `summary.next_automatic_turn` as advisory while still
  respecting health, operator, and evidence gates. Validation: direct quota
  contract smoke passed; aggregate public smokes passed with 5 scripts; Python
  compile passed; public contract check passed; `git diff --check` passed.
  Critic: the status contract is now smoke-protected, but its wording is less
  explicit than the quota allocation contract about throttled, paused, waiting,
  operator-gated, and health-blocked lanes.
- 2026-06-02T07:12:32+08:00: Added
  `examples/quota-contract-smoke.py`, a dependency-free text smoke that reads
  `README.md` and `docs/quota-allocation.md`. It protects the public quota
  allocation contract wording: `quota plan` is advisory, does not grant
  permission, does not clear operator gates or record human reward, keeps
  non-eligible lanes out of the eligible lane, sorts only eligible goals by
  `quota.compute`, and tells executors to skip delivery work when
  `quota should-run` returns `should_run=false`. Validation: direct quota
  contract smoke passed; aggregate public smokes passed with 5 scripts; Python
  compile passed; public contract check passed; `git diff --check` passed.
  Critic: README and quota allocation docs are now guarded; the remaining
  nearby drift risk is `docs/status-data-contract.md`, which also describes the
  quota-plan advisory boundary.
- 2026-06-02T07:06:47+08:00: Added the public quota allocation contract note to
  `docs/quota-allocation.md` and the README quota CLI entry point. The contract
  states that `quota plan` reports an advisory `next_automatic_turn`, does not
  grant permission or clear operator gates, keeps `blocked_health`,
  `operator_gate`, `waiting`, `throttled`, and `paused` goals outside the
  eligible lane, and sorts only eligible goals by effective `quota.compute`.
  Validation: direct quota-plan smoke passed; aggregate public smokes passed
  with 4 scripts; public contract check passed; `git diff --check` passed; `rg`
  confirmed the new allocation-contract and README entry text. Critic: behavior
  and docs now agree, but a tiny smoke assertion should protect the public docs
  wording so future README or contract edits do not imply that quota allocation
  is permission.
- 2026-06-02T06:59:21+08:00: Extended `examples/quota-plan-smoke.py` to cover
  the executable CLI path. The smoke now writes a temporary public-safe
  registry/runtime/project fixture, runs `python -m goal_harness.cli --format
  json quota plan` and default Markdown `quota plan`, and verifies both preserve
  the same multi-project allocation rule as `build_quota_plan()`: the highest
  compute eligible goal becomes `next_automatic_turn`, eligible goals stay
  sorted by compute, and the operator-gated goal stays in the `operator_gate`
  lane. Validation: direct quota-plan smoke passed; aggregate public smokes
  passed with 4 scripts; Python compile passed; public contract check passed;
  `git diff --check` passed. Critic: planner and CLI paths are now guarded; the
  allocation rule should be stated in the public quota contract so project
  agents and users understand it is advisory compute allocation, not permission.
- 2026-06-02T06:53:21+08:00: Added `examples/quota-plan-smoke.py`, a pure
  fixture smoke for multi-project allocation. The fixture creates three
  eligible goals with compute shares `1.0`, `0.5`, and `0.3`, plus one
  `operator_gate` goal with compute `1.0`. It verifies `build_quota_plan()`
  selects the `1.0` eligible goal as `next_automatic_turn`, keeps eligible goals
  sorted by compute, and leaves the operator-gated goal in the
  `operator_gate` lane rather than the eligible lane. Validation: direct quota
  plan smoke passed; aggregate public smokes passed with 4 scripts; Python
  compile passed; public contract check passed; `git diff --check` passed.
  Critic: the Python quota planner is now covered by a multi-project fixture,
  but the actual `goal-harness quota plan` CLI output should get the same
  executable-path coverage.
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
