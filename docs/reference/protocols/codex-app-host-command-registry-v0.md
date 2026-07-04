# codex_app_host_command_registry_v0

`codex_app_host_command_registry_v0` defines how a host such as Codex App
should recognize LoopX slash commands before they become ordinary agent chat.
The host owns parsing, project-root resolution, permission framing, and the
structured handoff packet. LoopX CLI remains the source of truth.

This contract sits above:

- [`loopx_goal_command_v0`](loopx-goal-command-v0.md) for the project-local
  `/loopx` status entry and `/loopx <goal text>` start entry.
- [`global_manager_command_v0`](global-manager-command-v0.md) for read-only
  `/loopx-global-*` manager commands.
- [`host_integration_surface_v0`](host-integration-surface-v0.md) for general
  host lifecycle reads and controlled writes.

It is not a replacement for the CLI, a hidden automation runner, or a broad
natural-language router.

## Command Registry

The host registry should expose this minimal command set:

| Command | Canonical target | Default authority |
| --- | --- | --- |
| `/loopx` | `loopx bootstrap-command-pack --project .` | Read/status-first. |
| `/loopx <goal text>` | `loopx bootstrap-command-pack --project . --goal-text "<goal text>"` | Explicit project-local start intent. |
| `/loopx-global-summary` | `global_manager_command_v0` summary request | Read-only global control-plane digest. |
| `/loopx-global-gates` | `global_manager_command_v0` gates request | Read-only gate inbox. |
| `/loopx-global-todos` | `global_manager_command_v0` todos request | Read-only work queue view. |
| `/loopx-global-risks` | `global_manager_command_v0` risks request | Read-only risk view. |

Legacy `/loop-global-*` forms may be accepted during migration, but the host
must canonicalize packets, help, and user-visible labels to `/loopx-global-*`.
Do not add extra summary aliases; `/loopx-global-summary` is the canonical
global progress digest.

Example registry entry:

```json
{
  "schema_version": "codex_app_host_command_registry_v0",
  "host_kind": "codex_app",
  "commands": [
    {
      "command": "/loopx",
      "kind": "project_bootstrap_preview",
      "protocol": "loopx_goal_command_v0",
      "cli_baseline": "loopx bootstrap-command-pack --project .",
      "mutation_policy": "read_first"
    },
    {
      "command": "/loopx <goal text>",
      "kind": "project_task_start",
      "protocol": "loopx_goal_command_v0",
      "cli_baseline": "loopx bootstrap-command-pack --project . --goal-text \"<goal text>\"",
      "mutation_policy": "explicit_goal_start"
    },
    {
      "command": "/loopx-global-summary",
      "kind": "global_manager_summary",
      "protocol": "global_manager_command_v0",
      "legacy_aliases": ["/loop-global-summary"],
      "mutation_policy": "read_only"
    }
  ],
  "unknown_command_policy": "fail_closed_with_slash_help"
}
```

## Host Parse Rules

The host should parse LoopX slash commands before the agent prompt sees the
message:

1. Match only an exact command token at the beginning of the visible user
   message.
2. Canonicalize legacy `/loop-global-*` aliases to `/loopx-global-*`.
3. Treat `/loopx` with no trailing text as bootstrap/status preview.
4. Treat text after `/loopx` as explicit task text. Preserve the exact
   user task text in the handoff packet, but quote it safely for CLI display.
5. Fail closed for unknown `/loopx-*` commands and return `loopx slash-commands`
   help instead of falling through to ordinary chat.

Skill-level recognition may remain a fallback, but the preferred product path
is host parsing. Prompt-only recognition is useful for early testing but can be
polluted by conversation history and should not be the long-term authority.

## Project Root And Agent Identity

Project-local commands require a resolved project root. The host may use the
current workspace, selected file, or explicit project parameter, but it must not
scan unrelated home directories or guess from private paths.

Required fields:

| Field | Rule |
| --- | --- |
| `project_root` | Absolute local root for CLI execution; omit from public packets. |
| `project_root_label` | Public-safe label such as repo name or `current workspace`. |
| `goal_id` | Existing runtime state id field; keep the field name for CLI compatibility, but present it to users as the active state id. |
| `agent_id` | Registered LoopX agent id when the host is acting for an agent. |
| `host_surface` | `chat_box`, `command_palette`, `codex_cli_tui`, or another compact host label. |

If the host cannot resolve a project root, `/loopx` and `/loopx <goal text>`
must produce a setup/help packet, not state writes. Global commands may still
run against the shared global registry when available.

## Handoff Packet

After parsing, the host hands the agent or CLI a compact packet:

```json
{
  "schema_version": "codex_app_host_command_handoff_v0",
  "command": "/loopx",
  "raw_command": "/loopx design an issue-fix workflow",
  "canonical_command": "/loopx <goal text>",
  "task_text": "design an issue-fix workflow",
  "host_surface": "chat_box",
  "project_root_label": "current workspace",
  "goal_id": "loopx-meta",
  "agent_id": "codex-product-capability",
  "protocol": "loopx_goal_command_v0",
  "cli_preview": "loopx bootstrap-command-pack --project . --goal-text \"<goal text>\"",
  "authority": {
    "read_allowed": true,
    "project_local_write_allowed": true,
    "global_control_write_allowed": false,
    "production_action_allowed": false
  },
  "next_step": "run_bootstrap_command_pack_then_plan_before_todo_write"
}
```

The packet may be rendered to the agent prompt, passed to a tool call, or used
to run the CLI directly. It must not contain raw transcripts, credentials,
private document bodies, or local absolute paths in user-visible output.

## Permission Boundary

Host command parsing does not grant new LoopX authority. It only converts
visible user intent into the existing CLI lifecycle:

- `/loopx` can read status and preview command packs. It stops before writes
  that need confirmation.
- `/loopx <goal text>` is explicit intent to start project-local work: plan
  first, write ordered todos, refresh state, run `quota should-run`, and
  execute only when the guard allows.
- `/loopx-global-*` commands are read-only and must not approve gates, add
  todos, spend quota, merge PRs, publish externally, or pause/resume loops.
- Destructive git, credentials, private material reads, production actions, and
  external publication still require explicit user/controller approval.

## CLI Fallback

Every host command must expose a deterministic CLI fallback:

```bash
loopx slash-commands
loopx slash-commands --install
loopx bootstrap-command-pack --project .
loopx bootstrap-command-pack --project . --goal-text "<goal text>"
loopx global-summary
loopx --format json --registry "$HOME/.codex/loopx/registry.global.json" quota should-run --goal-id <goal-id> --agent-id <agent-id>
```

If host command parsing is unavailable, the user or a skill fallback can still
run these commands and preserve the same LoopX state machine.

## Userland Registration Fallback

Until every host exposes a native command registry, LoopX installs slash-command
facades into the user-level discovery locations that current hosts already
support:

- `~/.codex/skills/loopx*/SKILL.md` for explicit Codex command-facade
  invocation through `$loopx` or `/skills`;
- `~/.claude/skills/loopx*/SKILL.md` for Claude Code skill-based slash
  commands.

This fallback does not replace host parsing. It gives users an explicit Codex
skill entry point now, while preserving the same CLI baselines and permission
boundaries defined above. The Codex command facades are explicit-only; the
richer workflow skills remain available for implicit invocation. The installer
overwrites LoopX-managed files and known legacy LoopX-generated command files,
but it skips same-name user files without a LoopX managed marker or legacy
signature.

## Acceptance Checks

A host command registry implementation is acceptable when:

1. `/loopx` and `/loopx <goal text>` route to `loopx_goal_command_v0`.
2. `/loopx-global-summary`, `/loopx-global-gates`, `/loopx-global-todos`, and
   `/loopx-global-risks` route to `global_manager_command_v0`.
3. Legacy `/loop-global-*` inputs canonicalize to `/loopx-global-*`.
4. Unknown `/loopx-*` commands fail closed with `loopx slash-commands` help.
5. The handoff packet includes project root label, optional active state id,
   agent id, protocol, authority, and CLI fallback, without public local
   absolute paths.
6. Host parsing is treated as the preferred path, while skill-level recognition
   remains only a compatibility fallback.
