# Terms and command entrypoints

This appendix routes readers; it does not replace the LoopX CLI reference. Run
`loopx <command> --help` for complete arguments in the installed version.

## Core terms

| Term | Meaning in this book |
| --- | --- |
| Agent | Executor that plans and performs one bounded action in a Host/runtime |
| Host | Product or runtime that owns sessions, model turns, and wake-up surfaces |
| Goal | Long-running project outcome and state boundary identified by a stable `goal_id` |
| Agent identity | Peer or lane identified by `agent_id`; it is not the Goal and does not prove the Host |
| Vision | A bounded execution-routing contract for one `agent_id`, including role scope, direction, acceptance summary, and replan trigger |
| Acceptance | Observable conditions that prove the Goal is complete |
| Todo | Schedulable work item with identity |
| Frontier | Todos currently runnable after dependency, Gate, capability, and boundary checks |
| Claim | Soft ownership of a Todo |
| Lease | Time-bound exclusive reservation that prevents conflicting execution |
| Gate | Blocking decision with explicit scope and authority |
| Evidence | Verifiable material that supports a judgment |
| Receipt | Durable record of an accepted action or lifecycle transition |
| Projection | Read model derived from canonical state |
| Quota | Contract that decides whether a turn may run and records validated spend |
| Monitor | Todo that observes an external condition on a cadence and advances only on material change |
| Capability | Caller-facing outcome contract |
| Provider | Implementation or external-system caller that returns a bounded result |
| Extension | Installation, activation, upgrade, rollback, and compatibility lifecycle for a Provider or package |
| Kernel | Core that accepts transitions and owns durable control-plane state |

## Core protocol index

Choose a protocol from the developer job rather than reading the full directory alphabetically:

| Problem | Start with |
| --- | --- |
| `/loopx <goal text>`, Goal selection, fresh Agent identity, and Host activation | [`loopx_goal_command_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/loopx-goal-command-v0.md) |
| Long-running Agent sources, projections, concurrent lanes, and lifecycle | [`long_horizon_agent_state_protocol_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/long-horizon-agent-state-protocol-v0.md) |
| Agent-scoped chronology before replan or handoff | [`agent_scoped_evidence_ledger_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/agent-scoped-evidence-ledger-v0.md) |
| Canonical events, replay, and privacy | [`event_sourced_state_contract_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/event-sourced-state-contract-v0.md) |
| Typed read model over the active-state workbench | [`active_state_structured_projection_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/active-state-structured-projection-v0.md) |
| Todo, Gate, dependency, and handoff graph | [`task_graph_projection_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/task-graph-projection-v0.md) |
| Gate coverage and scoped authority | [`decision_scope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/decision-scope-v0.md) |
| Per-Agent Vision and replan | [`goal_vision_replan_contract_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/goal-vision-replan-contract-v0.md) |
| Equal peers, claims, and continuation | [`peer_agent_runtime_v1`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/peer-agent-runtime-v1.md) |
| One governed execution transaction, currently experimental | [`loopx_turn_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/loopx-turn-v0.md) |
| Opt-in bounded projection for an already-arbitrated decision | [`turn_envelope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/turn-envelope-v0.md) |
| Host capability, controlled write, and fallback | [`host_integration_surface_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/host-integration-surface-v0.md) |
| Read-only first-screen projection for a session runtime | [`session_runtime_loopx_projection_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/session-runtime-loopx-projection-v0.md) |
| Controlled session-runtime metadata writeback, currently draft | [`session_runtime_controlled_writeback_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/session-runtime-controlled-writeback-v0.md) |
| Revision, idempotency, and local write correctness | [`local_state_write_correctness_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/local-state-write-correctness-v0.md) |

Use the official
[Protocol Contracts index](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/README.md)
for the complete current set.

## Common read-only entrypoints

```bash
loopx doctor
loopx registry
loopx status
loopx todo list --goal-id <goal-id>
loopx history --goal-id <goal-id>
loopx evidence-log --goal-id <goal-id> --agent-id <agent-id> --thin --limit 30
loopx quota should-run --goal-id <goal-id> --agent-id <agent-id>
loopx extension list --format json
```

## Project onboarding entrypoints

```bash
loopx connect

loopx start-goal --guided --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --goal-text "<goal text>" \
  --host-surface codex-app

loopx start-goal --guided --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --goal-text "<goal text>" \
  --host-surface codex-cli-tui
```

On first run, omit `--goal-id`, `--agent-id`, or `--host-surface` to receive the corresponding read-only
Goal, fresh-Agent, or Host selection Gate. Rerun the exact command provided by the packet. Do not infer a
Goal from similar text or take over the only existing Agent automatically. Register a new identity with a
`register-agent --goal-id <goal-id> --agent-id <new-agent-id>` preview followed by atomic `--execute`; use
an existing identity only for an explicitly authorized takeover.

## Safe upgrade runbook

For a no-clone installation, `loopx update` is the primary path. Do not overwrite a release snapshot by
hand:

Run `loopx update --check` for a read-only freshness check, then
`loopx update --dry-run` for the install preview. Neither command installs.

A normal upgrade needs only:

```bash
loopx update --check
loopx update --dry-run
loopx update --execute
loopx doctor
```

Use the full flow below when you need pre-upgrade evidence, Host or Extension migration checks, or a
rollback path.

```bash
# 1. Record current facts
command -v loopx
loopx --version
loopx --format json doctor > /tmp/loopx-doctor-before.json

# 2. Inspect stable ref, freshness, and the recommendation
loopx update --check

# 3. Preview the ref, release id, and rollback target
loopx update --dry-run

# 4. Run the archive installer and post-update doctor
loopx update --execute

# 5. Recheck commands, skills, Host integration, and project state
loopx --version
loopx doctor
loopx slash-commands
loopx slash-commands --install
loopx status
```

The public `stable` ref is the default source. `--ref main` is a maintainer or development qualification
path, not the ordinary user default. `update --execute` installs a release snapshot and runs doctor; a
successful exit does not prove that every Host automation, Goal migration, or Extension Provider is
updated.

Validate the surfaces you use:

- `loopx doctor`: wrapper, release manifest, Python import, skill delivery, and Host integration;
- `loopx slash-commands --install`: updates only LoopX-managed command files and skips user-owned
  collisions;
- `loopx quota should-run` or `loopx upgrade-plan`: peer-runtime and heartbeat-prompt migrations;
- `loopx extension list` plus executed `extension doctor`: readiness for each active revision;
- `loopx status` and `history`: registry, Goal, Todo, and projection continuity.

Before a risky migration, scheduler change, or runtime repair, preview and create a private local backup:

```bash
loopx backup-state --project .
loopx backup-state --project . --execute
```

The archive contains local runtime and project state. It is private recovery material and must not be
committed or published.

When a new release blocks normal work, inspect current `loopx update --help`, then select a recorded release
id or use:

```bash
loopx update --rollback previous
loopx doctor
```

Rollback restores the LoopX release snapshot only. Project state already written by the new version,
external effects, and separately installed Extension packages may need their own migrations or rollback.
Do not describe wrapper rollback as whole-system rollback.

## Scheduler convergence entrypoint

When a Codex App packet reports `stateful_backoff.apply_needed=true`, have the Host apply
`recommended_rrule`, read back the actual result, and then run the packet's full `ack_hint.cli_args`.
The current route is typically:

```bash
loopx quota scheduler-ack-current <packet-bound-args...>
```

After an apply failure or timeout, do not ACK; run `failure_hint.cli_args` once. When
`apply_needed=false` and `ack_needed=true`, exact Host readback already matches the target cadence, so skip
the no-op update and run the bound ACK. Proposal, Host apply, readback, and ACK are all required for
convergence, and cadence changes do not consume delivery spend.

## Extension lifecycle entrypoints

```bash
loopx extension init <extension-id>
loopx extension install --manifest <extension.toml>
loopx extension doctor <extension-id>
loopx extension run <extension-id> --input-json <request.json>
loopx extension disable <extension-id>
loopx extension enable <extension-id>
loopx extension upgrade --manifest <extension.toml>
loopx extension rollback <extension-id>
```

Lifecycle commands normally preview by default. Inspect current `--help` and add `--execute` only when you
intend to mutate state or invoke the Provider.

## Source contribution entrypoints

- [Contributor Task Board](https://github.com/huangruiteng/loopx/blob/main/CONTRIBUTOR_TASKS.md)
- [Contributing](https://github.com/huangruiteng/loopx/blob/main/CONTRIBUTING.md)
- [Control-Plane Developer Course](https://github.com/huangruiteng/loopx/tree/main/docs/development/control-plane-course)
- [Core Control-Plane Graphs](https://github.com/huangruiteng/loopx/tree/main/docs/product/core-control-plane)
- [Testing and Quality](https://github.com/huangruiteng/loopx/blob/main/docs/development/testing-and-quality.md)

## Official sources

- [LoopX repository](https://github.com/huangruiteng/loopx)
- [Getting Started](https://github.com/huangruiteng/loopx/blob/main/docs/guides/getting-started.md)
- [Extensions and Capabilities](https://github.com/huangruiteng/loopx/blob/main/docs/reference/extensions.md)
