# How to use this book

This book is for external developers who already use Git, a terminal, and at least one agent development
tool. You do not need to read the LoopX Kernel source or learn every CLI subcommand first.

## What you will accomplish

The first six chapters establish one control-plane model. The book then branches into two independent
practice paths:

```text
Control-plane foundations
├── Connect an existing Git project
└── Make a developer contribution
    ├── Control Plane, Capabilities, and Domain State
    ├── Providers, Hosts/Runners, projections, docs, and fixtures
    └── Extensions and independent package lifecycle
```

The foundation sequence covers:

1. why one session is insufficient for long-running work;
2. which state belongs to an agent session, a Host Goal, and LoopX;
3. canonical state, workbenches, events, and read-only projections;
4. Todo graphs, Gates, claims, leases, authority, and peer collaboration;
5. how one governed Turn is decided, executed, validated, and written back;
6. retry, replan, self-repair, terminal closure, and runtime boundaries.

## How the Dev Book and Control-Plane Course work together

This book and the repository's
[Control-Plane Developer Course](/loopx/docs/development/control-plane-course/)
serve different reading jobs:

- the **Dev Book** gives external developers a complete-enough mechanism model, then helps them onboard a
  project or deliver a public contribution;
- the **Control-Plane Course** serves developers who need to enter Kernel, CLI, state-projection, or
  scheduler implementation through Showcase derivations, decision tables, source walkthroughs,
  experiments, and review questions.

They share the official protocols and source as authority, but do not maintain two copies of the complete
course. The Dev Book explains enough mechanism to predict behavior. Follow its chapter-level pointers into
the course when you need rule precedence, bounded-context placement, or implementation detail. The deep
course is currently maintained in Chinese; the English Dev Book keeps the mechanism needed for its main
paths self-contained.

- **How do short sessions compose into long-running work?** Read Chapters 1 and 2, then descend into the
  [concept primer](/loopx/docs/development/control-plane-course/00-concept-primer/) and
  [Lesson 0](/loopx/docs/development/control-plane-course/00-goal-control-plane-architecture/), then walk
  through a real Loop in [Lesson 1](/loopx/docs/development/control-plane-course/01-first-real-loop/).
- **Who owns state, the work graph, and authority?** Read Chapters 3 and 4, then descend into
  [Lesson 2](/loopx/docs/development/control-plane-course/02-state-substrate/) and
  [Lesson 3](/loopx/docs/development/control-plane-course/03-work-graph-and-peers/).
- **Which rule wins when a Gate, Monitor, and Replan coexist?** Read Chapter 5, then descend into
  [Lesson 4](/loopx/docs/development/control-plane-course/04-quota-decision-kernel/) and
  [Lesson 5](/loopx/docs/development/control-plane-course/05-host-scheduler-and-heartbeat/).
- **How does long-running work avoid drift and local loops?** Read Chapter 6, then descend into
  [long-horizon convergence](/loopx/docs/development/control-plane-course/topic-long-horizon-convergence/)
  and [Lesson 6](/loopx/docs/development/control-plane-course/06-evidence-refresh-and-self-repair/).
- **How do I change a rule and prove it is deliverable?** Read Chapters 10 through 13, then descend into
  [Lesson 7](/loopx/docs/development/control-plane-course/07-engineering-a-control-plane-rule/) and
  [Lesson 8](/loopx/docs/development/control-plane-course/08-autonomous-agent-quality-gates/).
- **How do Extensions, domain capabilities, and the Kernel compose?** Read Chapters 14 through 16, then
  descend into [Lesson 9](/loopx/docs/development/control-plane-course/09-extension-layer/).

After those chapters:

- to manage your own repository, start with
  [Connect an existing Git project](./05-connect-existing-project.md);
- to make any public LoopX contribution, start with the
  [Developer contribution map](./source-protocol-map.md);
- once you know the contribution needs independent installation, activation, and upgrades, continue to
  [Choose the right extension point](./08-extension-placement.md).

The paths share the same foundations but do not depend on each other. Extension lifecycle is one
developer-contribution path, not the default destination for every contribution.

## How chapters are organized

Each chapter prioritizes four questions:

1. What job does the reader need to complete now?
2. What observable result proves success?
3. Which concepts are necessary to predict the behavior?
4. Where should the reader recover when the normal path fails?

Command snippets fall into three categories:

- **Runnable:** checked against the stated LoopX baseline.
- **Based on the official scaffold:** the example focuses on the domain changes, protocol, and validation
  needed for the task without a separate exercise repository.
- **Simplified for explanation:** illustrates a state relationship and must not be pasted into production
  configuration.

## Sources of authority

The English and Chinese editions share the same product facts. The Chinese root edition is the editorial
source of truth; the English edition is organized for English-speaking external developers rather than
maintained as a separate product specification.

| Subject | Authority |
| --- | --- |
| CLI arguments, protocols, and runtime behavior | LoopX releases, current `--help`, and the official repository |
| Learning path, scaffold guidance, explanations, and trade-off guidance | This book |
| Kernel source walkthroughs, combined cases, decision tables, and experiment routes | Control-Plane Developer Course |
| Facts about your project | Git, CI, external services, and project-owned sources |

When the book and a current release disagree, follow the release first and report the documentation drift.
Do not bypass a newer permission or lifecycle check just to make an older example pass.

## Version baseline

The current release anchor is LoopX GitHub release `v0.4.1`. Local command examples were checked against
the installed `loopx 0.4.0` CLI surface. A release tag, installed CLI, and source checkout can be on
different revisions, so verify these surfaces against your actual environment:

- install and update;
- Host activation;
- the `start-goal` guided packet;
- Codex App heartbeat and visible Codex CLI Goal behavior;
- Extension manifest and lifecycle commands.

Before running commands from the book:

```bash
loopx --version
loopx doctor
```

If your version differs, inspect current command help and release notes before deciding whether you found
documentation drift, a release difference, or a product behavior change. This book does not guess what
different version identifiers imply.

## Deliberate scope

The developer-contribution path covers placement, protocol maps, rule changes, Capabilities and Providers,
Hosts and Runners, projections, documentation and fixtures, Extension lifecycle, validation, and PR
delivery. It does not duplicate the complete maintainer course or a full CLI reference.
Production effectful Providers, private organizational cases, and live benchmark operation remain outside
the main path. Use official source, protocol documentation, and the target project's own facts for those
workflows.
