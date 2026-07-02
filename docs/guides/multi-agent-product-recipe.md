# Multi-Agent Product Recipe

This guide is the product-author path for building a LoopX multi-agent
composition without copying auto-research internals. The target shape is:

1. **User layer:** a few intent fields.
2. **Product preset:** a small domain recipe.
3. **Multi-agent kernel:** every reusable runner and state mechanic.

The public promise of "launch multi-agent auto-research in the fewest lines" is
a forcing function for this split. It is not enough to make the user command
short if the auto-research preset becomes a second runner. Both the user layer
and the product preset must stay thin, so another product can reuse the same
kernel with a different role list, skill snippet, and evidence loop.

Use this with:

- [Multi-agent visible launcher v0](../reference/protocols/multi-agent-visible-launcher-v0.md)
- [Three-layer minimality contract](../reference/protocols/multi-agent-three-layer-minimality-v0.md)
- [Auto-research command path](auto-research-command-path.md)

## Layer Rule

| Layer | Keep It Small By Owning | Must Not Own |
| --- | --- | --- |
| User | Topic, objective, rounds, optional role overrides, and optional data or eval entrypoint. | Tmux, Codex TUI launch flags, pane-local tick commands, quota/frontier plumbing, machine JSON routing, or role bootstrap scripts. |
| Product preset | Domain role list, agent scope, handoff/todo hints, worker skill snippet, default seed todos, and domain evidence or metric adapter. | Generic multi-agent runner, real Codex TUI panes, workspace/trust-safe launch, pane-local A2A tick, todo/evidence/status protocol, attach/stop/retry, or JSON visibility policy. |
| Kernel | Multi-agent runner, true interactive Codex panes, pane-local A2A tick, workspace/trust-safe launch, todo/evidence/status protocol, compact human status, role prompt scaffolding, and host lifecycle controls. | Research, support, benchmark, sales, or other product-specific semantics. |

If a second product would need the same code, move that code into the kernel.
If the logic names a domain result, domain role, metric, artifact type, or
handoff meaning, keep it in the preset.

## Product Preset Shape

A preset should be close to data plus one or two small adapters. It should not
construct tmux commands, Codex invocation strings, or pane wrapper scripts.

The minimum preset fields are:

- `product_id`: stable product namespace, such as `auto-research`;
- `objective_fields`: user-facing intent fields the product accepts;
- `roles`: role list with `agent_id`, `role_id`, `lane_id`, and agent scope;
- `skill`: worker-local skill snippet or source path for each role;
- `handoff_hints`: how a role creates or completes LoopX todos for the next
  role;
- `seed_todos`: first todo titles or action kinds for a fresh run;
- `evidence_adapter`: tiny domain writeback or metric loop, if the product
  has scored evidence.

Example product recipe:

```json
{
  "schema_version": "generic_multi_agent_launch_spec_v0",
  "goal_id": "loopx-demo-goal",
  "session_name": "loopx-product-team",
  "default_reasoning_effort": "high",
  "roles": [
    {
      "lane_id": "planner",
      "agent_id": "codex-main-control",
      "role_id": "planner",
      "scope": "Turn the objective into one bounded todo and a review handoff.",
      "skill": {
        "name": "product-planner",
        "source": "skills/planner/SKILL.md"
      },
      "handoff_hints": [
        "Create a LoopX todo for builder when the plan is ready."
      ]
    },
    {
      "lane_id": "builder",
      "agent_id": "codex-side-bypass",
      "role_id": "builder",
      "scope": "Claim the selected todo, execute the bounded work, and write evidence.",
      "skill": {
        "name": "product-builder",
        "source": "skills/builder/SKILL.md"
      },
      "handoff_hints": [
        "Complete the todo or create a focused review todo with compact evidence."
      ]
    }
  ]
}
```

The kernel expands that spec into a visible launcher packet with role profiles,
scoped LoopX wrappers, `$LOOPX_PANE_A2A_TICK`, artifact-only machine JSON, and
tmux host controls.

## Worker Skill Snippet

Each role should receive a small worker-local skill. The skill explains domain
behavior, not runner mechanics.

Good skill snippet:

```markdown
# product-builder

Use when this pane has a selected builder todo.

1. Read your selected frontier through LoopX state.
2. Work only inside the selected todo and role scope.
3. Write public-safe evidence before completing the todo.
4. If another role should continue, create a focused LoopX todo and name the
   target role in the handoff hint.
```

Avoid putting these in a product skill:

- how to start tmux;
- how to run Codex;
- how to write pane wrapper scripts;
- how to hide or redirect machine JSON;
- how quota/frontier/status files are routed;
- how attach, stop, retry, or workspace trust is implemented.

Those are kernel responsibilities.

## Handoff And Todo Hints

The product preset should describe handoff in LoopX terms, not as a hidden
workflow engine. A role can:

- complete the selected todo after writing compact evidence;
- create a successor todo with `claimed_by` or target role metadata when the
  next role is known;
- leave blocker rationale when no safe action is available;
- write a public-safe evidence pointer for the next role to read.

The preset should not directly call another agent, inject text into another
pane, or keep private side-channel state. Agents coordinate by reading and
writing the shared LoopX state surface: registry, runtime root, todo projection,
quota/frontier, run history, and public-safe evidence.

## One-Command Launch

For a custom composition, the generic path is:

```bash
loopx multi-agent launch \
  --spec ./multi-agent-spec.public.json \
  --workspace "$PWD" \
  --execute \
  --attach
```

For the auto-research preset, the product path remains:

```bash
loopx auto-research demo-e2e \
  --agent-id codex-side-bypass \
  --reasoning-effort high \
  --execute \
  --replace-existing
```

Both commands should open real interactive Codex CLI TUI panes. The first
screen should be the role TUI, not raw JSON, shell streams, a hidden executor,
or a generated worktree trust prompt.

## Attach, Stop, Retry

Every visible multi-agent product should expose the same host controls:

```bash
tmux attach -t <session-name>
tmux kill-session -t <session-name>
```

Retry means rerun the product command after refreshing quota/frontier/bootstrap
state. It must not replay stale hidden prompts or assume a previous pane still
has authority. Use `--replace-existing` only when the operator intentionally
wants to replace a session with the same name.

Inside any pane, the user may interrupt the role and type normally. The pane is
a real Codex CLI agent, not a passive log viewer.

## Acceptance Checklist

A new product preset is healthy when:

- the user-facing entrypoint is intent plus a few options;
- the preset defines role list, agent scope, skill snippet, handoff/todo hints,
  seed todos, and optional evidence adapter;
- the preset imports the generic multi-agent kernel instead of duplicating
  runner, TUI, tick, workspace, status, or JSON policy code;
- every visible pane starts as an interactive Codex CLI TUI;
- each role's first action is the pane-local A2A tick;
- machine JSON is written to public artifacts or an explicit machine channel,
  not dumped into the first visible screen;
- todos and evidence are the only handoff authority;
- attach, stop, and retry are available without product-specific host logic;
- no raw logs, credentials, private material, absolute local paths, or
  generated transcripts enter committed docs or fixtures.

## Auto-Research As The Reference Preset

Auto-research should stay a reference preset, not the kernel. Its preset owns:

- research roles such as curator, hypothesis mapper, evidence runner, and
  verifier;
- role-specific allowed actions;
- research handoff hints;
- metric/evidence loop defaults;
- seed todo wording for the demo.

It should not own:

- multi-agent runner lifecycle;
- real Codex TUI pane startup;
- pane-local A2A tick implementation;
- workspace trust handling;
- generic todo/evidence/status protocol;
- attach, stop, retry, or machine JSON visibility rules.

When auto-research needs a new generic capability, implement it in the
multi-agent kernel first, then let the auto-research preset consume it through a
small role or evidence adapter. That is the path toward a reusable, lightweight
kernel and a small promotional example.
