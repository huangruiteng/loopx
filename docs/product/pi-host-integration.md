# pi Host Integration

LoopX supports pi through an opt-in host type and a native pi package. LoopX
remains the durable control plane; pi remains the visible interactive executor.

## Install

Requirements:

- LoopX 0.2.7 or newer on `PATH`;
- pi 0.80.10 or newer;
- Python 3.11 or newer.

From a LoopX checkout or release snapshot:

```bash
loopx-pi-install
```

Contributors can run `scripts/install-pi-package.sh` directly from a checkout.
Run `/reload` in an already open pi session. The installer copies the reviewed
package into the stable managed path `~/.local/share/loopx/pi-package` and
delegates to `pi install` with that path. A management marker prevents it from
replacing an unrelated directory. It does not install a scheduler, timer,
heartbeat automation, Codex skill, Claude Code adapter, or slash command for
another host.

Review the package before installation because pi extensions run with the
user's local permissions.

## Host Contract

The canonical LoopX agent type is `pi`, with aliases `pi-cli` and
`pi coding agent`. Its host activation surface is
`pi_interactive_bounded_turns`:

1. `/loopx <goal>` creates or reuses local LoopX state and a ranked todo
   frontier.
2. `/loopx-turn` runs exactly one quota-gated bounded segment.
3. `/loopx-status` refreshes a compact read-only status widget.
4. `loopx_control` exposes allow-listed structured CLI actions. Mutations remain
   previews unless `execute=true` is explicit.

pi is an interactive host. LoopX scheduler hints remain data for hosts that own
schedulers; the pi package does not apply or acknowledge them.

## Accountable Delivery

LoopX 0.2.7 binds a material refresh and quota spend to the Git checkout that
produced the delivery.

- Use `project` for the connected goal registry.
- Set `deliveryWorkspace` when implementation occurs in another checkout or
  worktree.
- Pass the same `deliveryWorkspace` to `refresh_state` and `spend_slot`.
- A workspace guard failure must stop accounting until the correct checkout is
  selected.

Material refreshes also require an agent vision checkpoint. The first material
refresh writes a bounded baseline with `visionState`, `visionSummary`,
`visionRoleScope`, `visionAcceptance`, and continuation fields. Later refreshes
may use `visionUnchangedReason` only when that baseline still matches the active
acceptance boundary.

## Compatibility Boundary

pi support is additive:

- normal `scripts/install-local.sh` and `scripts/install-from-github.sh`
  behavior is unchanged;
- the pi package is installed only by `loopx-pi-install`, the source
  `scripts/install-pi-package.sh`, or an explicit `pi install`;
- Codex App keeps heartbeat automation activation;
- Codex IDE and Codex CLI keep visible `/goal` activation;
- Claude Code keeps native `/loop` activation;
- manual and custom agents keep external loop-driver activation;
- pi-specific TypeScript and skill resources live under `integrations/pi` and
  are not imported by the Python runtime.

The core regression test locks the existing activation methods while testing
the new pi branch separately.

## Validation

Run the focused package and host tests:

```bash
python3 -m pytest -q tests/test_host_loop_activation.py tests/test_pi_host_integration.py tests/control_plane/test_start_goal_compact_projection.py
python3 examples/control_plane/agent-onboard-host-loop-activation-smoke.py
loopx-pi-install --dry-run
```

After local installation, reload pi and use `/loopx-status` before starting a
real goal.
