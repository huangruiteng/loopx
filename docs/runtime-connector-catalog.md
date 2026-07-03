# Runtime Connector Catalog

Status: public-safe v0 catalog for LoopX host/runtime connectors.

LoopX can run beside many execution surfaces without becoming the execution
runtime. The connector catalog names those surfaces in user-facing terms and
maps each one back to the same kernel contracts: registry, active state, todo,
quota, scheduler hints, gates, evidence, and public/private boundary.

The catalog is not a second source of truth. It is a frontstage index over the
host loops that can wake an agent, ask LoopX whether work is allowed, write back
validated state, and expose enough liveness for users and maintainers to reason
about the work.

## Connector Fields

| Field | Meaning |
| --- | --- |
| `id` | Stable connector id used by docs, status projections, and smokes. |
| `surface` | User-visible host surface or runtime family. |
| `execution_mode` | How the host loop runs: visible TUI, app heartbeat, local scheduler, webhook, or bridge. |
| `wake_triggers` | What starts one LoopX-controlled turn. |
| `state_writeback` | The LoopX write path after validated work. |
| `liveness_signal` | Minimal signal that the host loop is alive without copying raw logs. |
| `stop_reset_policy` | How scheduler hints, final checks, or host stop rules apply. |
| `budget_meter` | How the connector maps work to quota or no-spend monitor policy. |
| `human_visibility` | What the user can see without reading private state. |
| `boundary` | What the connector must not copy, infer, or mutate. |
| `smoke_expectation` | Focused public check that protects the connector contract. |

## Initial Catalog

| id | surface | execution_mode | wake_triggers | state_writeback | liveness_signal | stop_reset_policy | budget_meter | human_visibility | boundary | smoke_expectation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `codex_app_heartbeat` | Codex App automation | Scheduled headless app thread | Codex App heartbeat RRULE; `scheduler_hint.reset_policy.reset_token` | `todo` lifecycle, `refresh-state`, then `quota spend-slot` after validation | Heartbeat run plus quota event | Apply `scheduler_hint.codex_app` reset/backoff; cadence-only changes do not spend | Per-goal/per-agent quota slot after validated writeback | Visible thread, heartbeat XML, concrete user todo when required | Generated heartbeat prompt; scoped `--agent-id`; no project-specific prompt branches | Prompt smoke covers scheduler hint, reset token, identity, and no-spend cadence change. |
| `codex_cli_tui` | Codex CLI TUI | Visible interactive terminal loop | User bootstrap, `/goal`, or visible continuation | Same CLI todo/refresh/spend path | TUI transcript plus compact LoopX status | Final quota/replan check before loop exit when unchanged limit is configured | Quota slot after validated writeback; no spend for exit/final check | User sees the active TUI turn | Do not silently switch to hidden headless execution or copy raw transcripts | TUI prompt/bootstrap smoke covers scoped identity and final-check/self-stop semantics. |
| `claude_code_loop` | Claude Code loop | Visible local agent loop | Slash command, local loop tick, or host loop continuation | Same CLI todo/refresh/spend path | Loop status plus compact transcript pointer | Final quota/replan check before stop when unchanged limit is configured | Quota slot after validated writeback; no spend for stop/final check | User sees local loop status and response | No private material, credentials, production action, or hidden approval bypass | Loop smoke covers scoped identity, unchanged final check, and stop-without-spend. |
| `shell_worker` | Shell, cron, launchd, or service timer | Headless local command | Cron/service/manual shell wakeup | CLI writeback commands from the project checkout | Exit code, run id, and compact status | Obey local `scheduler_hint` backoff/reset; fail closed on missing goal or agent id | Quota slot for delivery; monitor-only polls stay no-spend | Logs or status command, not raw state files | Do not bake local paths, secrets, or project policy into reusable scripts | Command examples use global registry, `--agent-id`, and no-spend monitor behavior. |
| `http_webhook` | HTTP webhook or local daemon | Request-driven bridge | Loopback callback, webhook, or host event | Adapter validates, then emits LoopX todo/gate/evidence events | Request log plus compact status export | Webhooks do not self-poll; scheduler hints are advisory unless a scheduler owns the retry | Quota spend only after accepted writeback | Dashboard/status feed | Loopback by default; write endpoints require explicit dry-run/preview and CLI-equivalent fallback | Loopback smoke rejects remote status/write authority and proves preview-gated writes. |
| `worker_bridge` | Worker bridge | External executor, task container, or remote worker bridge | Worker event, bridge message, or runner sidecar | Bridge emits compact public-safe state, todo, evidence, or benchmark-run payload | Worker heartbeat/status and compact counter trace | Host-specific stop/reset maps back to scheduler hints and outcome policy | Quota event for accepted work; no leaderboard/score claim from bridge-only evidence | Dashboard/frontstage projection and compact evidence timeline | Strip raw logs, local paths, private traces, task text, and credentials | Worker bridge install/status smoke proves source mount, writeback contract, and private-boundary stripping. |
| `computer_use_runtime` | Browser, desktop, or app automation runtime | Visible or replayable UI execution surface | Approved connector plan, bounded todo, host replay event, or user takeover handoff | Compact action plan, observation, receipt, gate, and evidence-handle writeback | Host-owned replay/screenshot pointer plus compact receipt fields | Stop at unknown modal, privacy ambiguity, or final external action; scheduler hints still come from LoopX quota | Quota spend only after validated receipt and LoopX writeback; readiness/profile checks stay no-spend | Review card with intended action, forbidden actions, evidence handle, and takeover path | Do not copy credentials, cookies, raw screenshots, private UI bodies, or perform sends/purchases/production mutations without exact gate | Synthetic capability/action/receipt smokes prove gate-before-write, raw-evidence stripping, and concrete user-question projection. |

## Projection Rules

- LoopX kernel objects remain authoritative: registry, active goal state, todo,
  run history, quota ledger, gates, and evidence pointers.
- A connector may project host facts into status or dashboard cards, but it must
  not store raw transcripts, raw logs, credentials, local absolute paths, or
  private artifacts in public state.
- Every delivery turn starts with `quota should-run` scoped by `goal_id` and
  registered `agent_id`.
- Cadence updates, reset-token handling, final quota checks, loop exits, and
  monitor-only polls do not spend delivery quota.
- User gates must surface concrete user todos or questions. If the payload is
  missing, the connector reports a projection bug instead of silently waiting.
- Validated delivery ends with durable writeback before quota spend:
  todo/state/evidence update, `refresh-state`, and one quota spend event.

## Smoke Expectations

Connector smokes should stay narrow. They protect reusable contracts, not one
maintainer's local automation:

- prompt and bootstrap smokes cover scoped identity, `scheduler_hint`, reset
  policy, and no-spend cadence or final-check behavior;
- local status/server smokes cover loopback-only defaults, read-only browser
  projection, and explicit dry-run/preview before writes;
- bridge smokes cover compact writeback payloads, liveness counters, and
  private-boundary stripping;
- todo/writeback smokes cover the validated-work sequence and prove
  monitor-only or stop-only paths do not spend quota.

## Related Contracts

- [Heartbeat automation prompt](heartbeat-automation-prompt.md)
- [Host integration surface v0](reference/protocols/host-integration-surface-v0.md)
- [Computer-use runtime connector v0](reference/protocols/computer-use-runtime-connector-v0.md)
- [Session runtime to LoopX projection v0](reference/protocols/session-runtime-loopx-projection-v0.md)
- [Worker bridge install contract](worker-bridge-install-contract.md)
- [Quota allocation](quota-allocation.md)
