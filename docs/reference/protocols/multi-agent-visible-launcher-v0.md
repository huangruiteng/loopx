# multi_agent_visible_launcher_v0

`multi_agent_visible_launcher_v0` is the generic LoopX contract for starting
several visible local agent panes for one shared goal. It is the reusable layer
under domain demos such as auto-research: LoopX owns the goal surface, lane
identity, quota/frontier/bootstrap guards, visible host controls, and public
acceptance; the domain capability owns only role semantics and evidence
writeback.

This contract intentionally sits between two existing surfaces:

- `local_agent_launch_plan_v0` previews what could be launched and remains
  `mode=dry_run` only.
- Domain capabilities, such as auto-research, provide role profiles, frontier
  commands, and evidence packets.

The visible launcher may plan or start panes, but it must not become a leader
agent, hidden scheduler, promotion authority, or second source of truth.

## Ownership Split

| Surface | Owns | Does not own |
| --- | --- | --- |
| LoopX control plane | goal id, registered agents, todo claims, quota, gates, run history, and public/private boundary. | Domain-specific research, benchmark, or product semantics. |
| Multi-agent visible launcher | pane layout, environment projection, visible start commands, attach/stop/retry controls, acceptance checks. | Todo truth, promotion decisions, hidden session injection, or write permission. |
| Domain capability | lane roles, frontier command, role profile schema, domain artifact/evidence writeback. | Generic host process lifecycle, global quota, or cross-domain launcher policy. |
| Host shell or app | Actual tmux/terminal/window process control after explicit local execution. | Authority to bypass LoopX guards or hide work from the user. |

The launcher is a host convenience surface. Each pane remains a normal LoopX
agent lane that must read the same goal state and pass its own guard.

## Packet Shape

```json
{
  "schema_version": "multi_agent_visible_launcher_v0",
  "mode": "dry_run | execute",
  "goal_id": "loopx-meta",
  "session_name": "loopx-visible-goal",
  "reasoning_contract": {
    "default_reasoning_effort": "high",
    "codex_cli_config_key": "model_reasoning_effort"
  },
  "shared_goal_surface": {
    "shared_goal_id": "loopx-meta",
    "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
    "shared_frontier": true,
    "lane_identity_source": "role_profile_plus_agent_scoped_quota",
    "all_lane_workspace_isolation": false,
    "mutation_isolation_policy": "only mutating attempts require a claimed worktree or equivalent execution boundary"
  },
  "interactive_tui_contract": {
    "schema_version": "multi_agent_visible_interactive_tui_contract_v0",
    "human_pane": [
      "codex_cli_tui",
      "role_prompt_inside_codex",
      "normal_user_typing",
      "normal_codex_tool_output",
      "takeover_controls"
    ],
    "machine_artifacts": [
      "quota.public.json",
      "frontier.public.json",
      "bootstrap-prompt.public.txt",
      "role_local_public_artifacts"
    ],
    "machine_json_policy": "file_or_explicit_machine_channel_only",
    "visible_json_policy": "not_printed_before_tui",
    "codex_surface": "interactive_cli_tui"
  },
  "lanes": [],
  "commands": {
    "start_script": [],
    "attach": "tmux attach -t loopx-visible-goal",
    "stop": "tmux kill-session -t loopx-visible-goal",
    "retry": "rerun the same packet after quota/frontier refresh"
  },
  "acceptance": {},
  "boundary": {}
}
```

Required top-level fields:

- `schema_version`: exactly `multi_agent_visible_launcher_v0`;
- `mode`: `dry_run` for inspect-only packets, or `execute` only after a local
  host explicitly starts panes;
- `goal_id` and `session_name`;
- `reasoning_contract`;
- `shared_goal_surface`;
- `interactive_tui_contract`;
- `lanes[]`;
- `commands.attach`, `commands.stop`, and `commands.retry`;
- `acceptance`;
- `boundary`.

## Shared Goal Surface

Visible lanes share the target **goal surface**, not necessarily the same file
mutation area. The shared surface is:

- the registry selected by `LOOPX_REGISTRY`;
- the runtime root selected by `LOOPX_RUNTIME_ROOT`;
- the `goal_id`;
- agent-scoped `quota should-run`;
- todo projection, frontier projection, and run history for that goal;
- public-safe evidence and rollout-event projections.

`all_lane_workspace_isolation=false` is the normal LoopX multi-agent shape:
agents cooperate on one goal surface. Isolation is applied only to the lane or
attempt that mutates files, typically through an independent git worktree,
scratch directory, or equivalent execution boundary. The launcher must make that
policy explicit instead of silently moving every lane into unrelated state.
Visible Codex TUI panes must not default into a generated demo-local git
worktree or control-plane repository. By default they should start in the
caller-selected workspace, or in an explicit user-owned scratch workspace, so a
user sees the agent role TUI instead of a generated workspace trust prompt.

## Lane Shape

Each lane is small enough to inspect before the agent starts:

```json
{
  "lane_id": "evidence-runner",
  "agent_id": "codex-side-bypass",
  "role_id": "evidence_runner",
  "responsibility": "Run one bounded evidence attempt.",
  "role_profile": {
    "schema_version": "domain_role_profile_v0"
  },
  "quota_guard": "loopx ... quota should-run --goal-id ... --agent-id ...",
  "frontier": "loopx ... <domain> frontier --goal-id ... --agent-id ...",
  "bootstrap_message": "loopx codex-cli-bootstrap-message ...",
  "visible_launch_command": "...",
  "reasoning_effort": "high",
  "lane_timeline": []
}
```

Required lane fields:

- `lane_id`, `agent_id`, `role_id`, and `responsibility`;
- `role_profile` or `role_profile_ref`;
- `quota_guard`;
- `frontier`;
- `bootstrap_message`;
- `visible_launch_command` or host-equivalent command ref;
- `reasoning_effort`;
- `lane_timeline`.

The pane title is cosmetic. The role profile plus agent-scoped quota/frontier
packet is the lane identity authority.

## Start Order

Every visible lane follows the same generic start order:

1. Prepare the role profile, scoped LoopX wrappers, and bootstrap prompt as
   local artifacts without printing raw JSON or shell marker streams.
2. Start one fresh interactive Codex CLI TUI per role window with
   `codex -c model_reasoning_effort=<effort> -C "$LOOPX_PROJECT" "$PROMPT"`.
3. Let the Codex role read quota/frontier/todo state through the pane-local
   LoopX wrapper inside the TUI.
4. Stop inside that Codex role if
   `interaction_contract.user_channel.action_required=true`, delivery is
   disallowed, quota is false, the frontier is contradictory, or the role would
   bypass LoopX todo/evidence writeback.
5. Keep the pane interactive so the user can type, interrupt, close, or retry
   manually like a normal Codex CLI session.

The launcher must not inject prompts into an existing hidden session, print raw
control-plane JSON as the first screen, or continue a lane after a user gate is
projected.

## Interactive TUI Contract

The first screen of each visible pane is the Codex CLI TUI itself. Users should
feel that they opened several normal Codex agents, one per role, and can type
into any of them. Raw quota, frontier, role profile, bootstrap prompt, and
machine JSON belong in public-safe artifacts or an explicit machine channel,
not in the initial tmux viewport.

Required runtime shape:

- one tmux window per role;
- no extra frontier/status JSON window by default;
- every role window executes the interactive Codex CLI, not `codex exec`;
- no pre-Codex character stream, marker transcript, raw JSON dump, or copied
  role profile appears before the TUI;
- no generated demo-local worktree trust prompt should be the first visible
  screen;
- the role prompt instructs Codex to use the pane-local LoopX wrapper for
  quota/frontier/todo/evidence work;
- users can interact with each role through ordinary Codex CLI controls.

The TUI may later show human-readable LoopX summaries when the Codex role runs
commands. It should not dump raw JSON, credentials, private logs, raw
transcripts, or absolute local artifact paths into the visible pane.

## Host Controls

The packet must expose:

- `attach`: how the user observes or takes over the whole session;
- `stop`: how the user kills the whole session;
- per-pane interrupt path using normal terminal controls;
- `retry`: the safe retry shape, which must recompute quota/frontier/bootstrap
  first instead of replaying stale hidden state;
- visible acceptance proof that each pane was created as an interactive Codex
  CLI TUI role and remains attachable or inspectable.

Host commands are public-safe command shapes. They must not include credentials,
auth headers, raw transcript paths, private document ids, or local absolute
paths in committed docs or fixtures.

## Boundary

Required boundary fields:

```json
{
  "starts_visible_processes": false,
  "runs_agent_processes": false,
  "writes_loopx_state": false,
  "spends_loopx_quota": false,
  "reads_raw_transcripts": false,
  "reads_session_files": false,
  "reads_credentials": false,
  "hidden_prompt_injection": false,
  "shared_goal_surface": true,
  "all_lane_workspace_isolation": false,
  "public_safe_redaction": true
}
```

For `mode=dry_run`, process and write fields must stay false. For
`mode=execute`, `starts_visible_processes` and `runs_agent_processes` may become
true only when the host actually starts visible panes; LoopX state write and
quota spend still happen through the normal agent lane after validated
writeback, not through the launcher packet itself.

## Domain Adapter Responsibilities

A domain capability that uses this contract supplies:

- role profile schema and role-specific allowed actions;
- frontier command and blocked-reason shape;
- domain evidence or artifact writeback command;
- domain-specific acceptance criteria;
- public-safe demo fixture or deterministic positive seed when needed.

The domain capability should not own generic attach/stop/retry, shared goal
surface, high-reasoning launch flags, or pane survival checks.

## Acceptance Checks

A public fixture or implementation satisfies the contract when:

1. the packet or protocol names `multi_agent_visible_launcher_v0`;
2. it distinguishes `local_agent_launch_plan_v0` preview from visible launch;
3. it says the launcher is not a leader agent, scheduler, promotion authority,
   or second source of truth;
4. it exposes shared goal surface through registry, runtime root, goal id,
   agent-scoped quota, todo/frontier projection, run history, and evidence;
5. it requires per-lane role identity, quota guard, frontier, bootstrap message,
   high reasoning, lane timeline, and visible launch command;
6. it requires attach, stop, retry, pane interrupt, and visible acceptance proof
   for interactive Codex CLI TUI role windows;
7. it has an interactive TUI contract that keeps raw machine JSON in artifacts
   or explicit machine channels instead of printing it before Codex starts;
8. dry-run mode starts no process, runs no agent, writes no LoopX state, and
   spends no quota;
9. execute mode still writes state and spends quota only through normal LoopX
   writeback after validation;
10. it keeps workspace isolation scoped to mutating attempts rather than
   splitting the shared goal surface; and
11. public docs and fixtures contain no raw transcripts, credentials, private
    links, internal project names, or local absolute paths.
