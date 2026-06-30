# Cross-Runtime Implement/Review Demo

This note defines a LoopX-native demo path for the pattern "Claude Code
implements, Codex reviews" without making either runtime the source of truth.

The comparable product shape is a two-agent coding loop, but LoopX should show
a different strength: durable state, gates, evidence, quota, and handoff across
agent surfaces. The demo should make the role split visible while preserving
LoopX's control-plane boundary.

## Demo Claim

LoopX can coordinate an implementation/review loop across different agent
runtimes:

- Claude Code owns an implementation todo and writes a bounded patch.
- Codex owns a review todo and produces a structured review verdict.
- A verifier command or smoke result is recorded as compact evidence.
- LoopX owns todo claims, gates, evidence, quota, and the next handoff.

The demo must not claim that LoopX is itself a universal executor. Runtime
launch still belongs to the host surface: Claude Code `/loop`, Codex App
heartbeat, Codex CLI TUI goal mode, or an explicit shell bridge.

## Current Public-Safe Flow

```text
user requirement
   │
   ▼
/loopx <implementation goal>
   │
   ▼
LoopX writes two role-scoped todos
   │
   ├─ claude-code-impl claims implementation
   │     └─ patch summary + changed files + validation attempt
   │
   └─ codex-review claims review
         └─ PASS/BLOCK verdict + findings + required verifier
   │
   ▼
review-packet + quota should-run decide next handoff
```

Minimal command surface:

```bash
loopx todo add --goal-id <goal> --role agent \
  --text "[P0] Implement <bounded requirement>." \
  --claimed-by claude-code-impl

loopx todo add --goal-id <goal> --role agent \
  --text "[P0] Review the implementation patch and verifier result." \
  --claimed-by codex-review

loopx --format json quota should-run --goal-id <goal> --agent-id claude-code-impl
loopx todo claim --goal-id <goal> --todo-id <todo_id> --claimed-by claude-code-impl
loopx review-packet --goal-id <goal>
loopx --format json quota should-run --goal-id <goal> --agent-id codex-review
```

For Claude Code, the visible runtime entry remains:

```text
/loopx <implementation goal>
/loop
```

For Codex, the visible review entry remains one of the existing Codex surfaces:

```text
/loopx Review <implementation evidence>
```

or a Codex App heartbeat whose `quota should-run --agent-id codex-review`
selects the review todo.

## State Shape

```yaml
cross_runtime_impl_review_demo_v0:
  goal_id: "public demo goal"
  requirement: "bounded user-visible change"
  roles:
    implementer:
      agent_id: "claude-code-impl"
      runtime: "claude_code"
      owns:
        - patch proposal
        - implementation evidence summary
        - first verifier attempt
      must_not:
        - approve its own review gate
        - publish or merge without owner approval
    reviewer:
      agent_id: "codex-review"
      runtime: "codex"
      owns:
        - review verdict
        - blocker list
        - verifier recommendation
      must_not:
        - rewrite the implementation unless explicitly handed a fix todo
        - treat style preferences as blocking defects
  loopx_control_plane:
    owns:
      - todo claims
      - quota decisions
      - human gates
      - compact evidence
      - review packet
      - next handoff
  verifier:
    command: "project-specific smoke or test command"
    required_before_done: true
  stop_conditions:
    - user gate required
    - source or write boundary unclear
    - verifier missing or inconclusive
    - reviewer BLOCK verdict with no bounded fix todo
```

## Review Verdict Contract

The reviewer output should be compact enough for `review-packet` and dashboards:

| Field | Meaning |
| --- | --- |
| `verdict` | `PASS`, `BLOCK`, or `INCONCLUSIVE`. |
| `blockers` | Objective defects only: failing tests, broken behavior, unmet requirement, unsafe boundary. |
| `suggestions` | Non-blocking style, naming, or follow-up notes. |
| `verifier` | Command or smoke that was run, recommended, or missing. |
| `handoff` | Next todo owner: implementer fix, reviewer accept, user gate, or archive. |

This keeps the demo from becoming an argument between two models. A `BLOCK`
verdict creates or preserves an implementation todo; a `PASS` verdict still
requires verifier evidence before completion.

## Productization Path

1. **Docs/demo only.** README and this note describe the role contract, commands,
   and boundary.
2. **Fixture rehearsal.** Add a public fixture showing implementer evidence,
   reviewer verdict, verifier result, and next handoff without running either
   runtime.
3. **Host adapter packet.** Add a dry-run CLI packet such as
   `loopx demo impl-review --preset claude-codex --dry-run` that writes no
   state and only renders the planned todos and gates.
4. **Opt-in execution.** Only after the packet is stable, launch Claude Code or
   Codex through their native visible surfaces and record compact evidence.

The v0 demo should stop at docs plus fixture validation. That is enough to show
the LoopX advantage over a single-runtime loop: the role split survives across
tools, but human gates and evidence stay centralized.

## Boundary

Allowed public evidence:

- public-safe requirement summary;
- todo ids and agent ids;
- changed-file summary;
- verifier command and pass/fail/inconclusive label;
- review verdict and blocker titles;
- review-packet or dashboard links.

Forbidden evidence:

- raw Claude or Codex transcripts;
- private prompts, credentials, local secrets, or private document links;
- raw benchmark task text, trajectories, logs, or verifier tails;
- unpublished maintainer messages;
- permission changes, merge, publish, or external comments without owner gate.

This makes the demo compatible with LoopX's public/private boundary and with
the existing Claude Code opt-in adapter.
