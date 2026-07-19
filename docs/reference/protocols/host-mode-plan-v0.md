# host_mode_plan_v0

`host_mode_plan_v0` is a public-safe host-mode selector for LoopX workflows. It
sits above the shipped [LoopX Turn](loopx-turn-v0.md) and
[runtime connector catalog](../../runtime-connector-catalog.md): it chooses the
user-facing host mode from intent and advertised host capabilities, then prints
the matching preview command. It is not a launcher, scheduler, permission grant,
validator, or second source of truth.

The problem it solves is operational ambiguity. A user may say "keep working
when I close the visible UI", "let chat create work", or "wake from a timer".
Those are different host modes, but all must preserve the same LoopX invariants:
scoped agent identity, quota guard before work, no-spend quiet checks,
independent validation, durable writeback, and quota spend only after validated
writeback.

## Boundary

The selector returns `mode=dry_run_host_mode_selector`. It must not start a
process, open a session, arm a timer, call a chat gateway, validate a result,
write LoopX state, or spend quota. For any execution path, `loopx_turn_v0`,
TurnEnvelope, registry, quota, todo projection, and run history remain
authoritative.

For headless execution, the selector maps to `loopx turn plan` and then the
existing Turn lifecycle:

```text
LoopX decides -> host adapter executes -> independent validator proves -> LoopX commits
```

That mapping is the key product value: the selector makes mode choice visible
without inventing a parallel runner or a second workflow authority.

## Modes

| mode | connector / contract | good fit | required capability |
| --- | --- | --- | --- |
| `visible_tui` | `codex_cli_tui` connector | user wants to watch or steer each turn | `visible_session` |
| `isolated_headless_turn` | `loopx_turn_v0` with `generic-cli` and `isolated-headless` | bounded unattended work through typed host results | `loopx_turn`, `typed_host_adapter`, `independent_validator` |
| `im_gateway` | gateway/webhook connector | chat or another surface should create durable work | `chat_gateway` |
| `shell_service` | shell worker plus LoopX Turn | cron, launchd, service timer, or manual shell wakeup | `service_timer`, `shell`, `loopx_turn` |
| `hybrid_handoff` | explicit transition contract | one mode should escalate or continue in another | at least two concrete modes ready |

## Intent And Capability Signals

Public-safe `user_intent` signals fail closed when unknown:

- `watch_each_turn` -> `visible_tui`;
- `continue_without_ui` -> `isolated_headless_turn`;
- `intake_from_chat` -> `im_gateway`;
- `timer_keepalive` -> `shell_service`;
- `escalate_between_modes` -> `hybrid_handoff`.

Public-safe `host_capabilities` signals are:

- `visible_session`;
- `loopx_turn`;
- `typed_host_adapter`;
- `independent_validator`;
- `chat_gateway`;
- `service_timer`;
- `shell`.

The first intent selects `selected_mode`. Every mode option still reports
`capability_ready` so an operator can see whether the selected host can actually
run the desired mode.

## Shape

```json
{
  "schema_version": "host_mode_plan_v0",
  "mode": "dry_run_host_mode_selector",
  "agent_model": "peer_v1",
  "goal_id": "loopx-meta",
  "agent_id": "codex-main-control",
  "selected_mode": "isolated_headless_turn",
  "selected_connector_id": "loopx_turn",
  "selected_turn_mapping": {
    "host": "generic-cli",
    "execution_mode": "isolated-headless",
    "scheduler_owner": "outer_controller",
    "plan_command": "loopx turn plan --goal-id loopx-meta --agent-id codex-main-control --host generic-cli --execution-mode isolated-headless --scheduler-owner outer_controller"
  },
  "next_preview_command": "loopx turn plan ...",
  "mode_options": [],
  "identity_contract": {},
  "no_spend_policy": {},
  "turn_contract": {},
  "transitions": [],
  "boundary": {},
  "truth_contract": {}
}
```

Each `mode_options[]` entry includes the connector id, readiness, required
host capabilities, Turn mapping when one exists, scheduler execution context,
quota guard command, and required proofs.

## Functional Points

The selector provides four concrete functions:

1. **Mode choice:** turn user intent into a named host mode instead of forcing
   users and agents to infer visible/headless/gateway/timer behavior manually.
2. **Turn mapping:** for unattended execution, print the exact `loopx turn plan`
   preview that preserves host, execution mode, scheduler owner, agent id, and
   available capabilities.
3. **Readiness surface:** report which advertised capabilities are missing
   before a mode can be trusted.
4. **Safe handoff plan:** name transitions such as visible bootstrap to
   isolated headless Turn, headless user-gate escalation back to visible TUI,
   gateway intake to Turn, and shell timer to visible escalation.

## Acceptance Checks

A fixture or implementation is acceptable when:

1. `schema_version=host_mode_plan_v0` and `mode=dry_run_host_mode_selector`;
2. the five canonical modes are present and intent selects the expected mode;
3. `isolated_headless_turn` maps to `loopx turn plan --host generic-cli
   --execution-mode isolated-headless --scheduler-owner outer_controller`;
4. scoped identity flows into Turn and quota preview commands as `--agent-id`;
5. the no-spend policy covers selector previews, Turn plan previews, quiet
   monitors, cadence-only changes, and final/readiness checks;
6. the boundary says the selector does not execute, write, spend, infer
   production permission, infer credential access, or infer destructive
   authority;
7. handoffs preserve the selected agent id and expose target readiness; and
8. unknown intent or host capability values fail closed with suggestions.
