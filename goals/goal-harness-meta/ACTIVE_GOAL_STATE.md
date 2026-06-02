---
status: active-read-only
owner_mode: goal
objective: "Keep the public Goal Harness repo runnable, understandable, and safe to reuse"
updated_at: 2026-06-02T18:32:46+08:00
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

- Run the next tick's steering audit and choose one bounded P0 step. Compare
  `goal-harness todo add --role user|agent`, a Review Packet goal-id mismatch
  guard, and one-click operator decision recording. Prefer the todo CLI unless
  another wrong-goal packet/gate is observed, because user/agent todo injection
  is now the lowest-friction project-agent loop gap after dashboard copy UX was
  simplified.

## Recent Progress

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
  the installed `/Users/bytedance/.codex/skills/goal-harness-project/SKILL.md`
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
