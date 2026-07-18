# LoopX Pi Adapter

Opt-in pi package for using LoopX as the durable control plane while pi performs
visible, bounded interactive work.

## Install

From a LoopX checkout or release snapshot:

```bash
loopx-pi-install
```

Contributors can run `scripts/install-pi-package.sh` directly from a checkout.

Then run `/reload` in an already open pi session. The script syncs the reviewed
package into the stable managed path `~/.local/share/loopx/pi-package` before
registering it, so LoopX release snapshot updates do not create a new pi package
identity. It refuses to replace an unmarked existing directory. The script does
not change LoopX's Codex, Claude Code, manual, or custom-agent integrations.

## Resources

- `extensions/loopx.ts`: `/loopx`, `/loopx-turn`, `/loopx-status`, and the
  structured `loopx_control` tool.
- `skills/loopx-pi/SKILL.md`: pi-specific lifecycle, quota, todo, vision,
  writeback, and safety rules.

## Requirements

- pi 0.80.10+
- LoopX 0.2.7+ on `PATH`
- Python 3.11+

The adapter is an interactive loop driver. It never installs a scheduler,
timer, heartbeat automation, or hidden background process. Each `/loopx-turn`
runs at most one quota-gated work segment.

For delivery in a repository other than the connected goal project, pass
`deliveryWorkspace` to `refresh_state` and `spend_slot`. Material refreshes must
also provide a valid agent vision patch, or `visionUnchangedReason` after a
baseline exists.

## Environment

- `LOOPX_BIN`: override the LoopX executable (default: `loopx`).
- `LOOPX_PI_AGENT_ID`: override the registered LoopX agent id (default:
  `pi-main`).
