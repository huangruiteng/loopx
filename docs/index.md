# Welcome to LoopX

LoopX is the local control plane for long-running AI agent work. It keeps
objectives, gates, todos, evidence, quota, and handoffs stable while Codex,
Claude Code, OpenCode, Cursor, or a custom runner executes bounded turns.

## Choose Your Path

<div class="grid cards" markdown>

-   :material-rocket-launch-outline: **Start using LoopX**

    Install the CLI, connect a project, inspect the current gate, and start a
    real goal from your agent.

    [:octicons-arrow-right-24: Getting started](guides/getting-started.md)

-   :material-map-marker-path: **Understand the control plane**

    Learn how goals, user gates, agent todos, quota, evidence, and handoffs fit
    into one durable state kernel.

    [:octicons-arrow-right-24: Concepts](concepts/README.md)

-   :material-book-open-page-variant: **Follow the Developer Book**

    Use a curated bilingual path from control-plane foundations to project
    onboarding and developer contributions.

    [:octicons-arrow-right-24: Developer Book](/loopx/docs/book/)

-   :material-console-line: **Operate a long task**

    Use status, quota, review packets, and the local dashboard without making
    the browser the source of truth.

    [:octicons-arrow-right-24: Operations](operations/README.md)

-   :material-source-branch: **Build or extend LoopX**

    Work from the developer guide, testing policy, protocol references, and
    public/private boundary checks.

    [:octicons-arrow-right-24: Development](development/README.md)

</div>

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor

cd /path/to/your-project
loopx connect
loopx status
```

Then start real work from your agent:

```text
/loopx <complex task>
```

## Core Commands

| Need | Command |
| --- | --- |
| Check installation | `loopx doctor` |
| Inspect current state | `loopx status` |
| Decide whether a turn may run | `loopx quota should-run --goal-id <goal-id>` |
| Manage user and agent todos | `loopx todo --help` |
| Build a handoff packet | `loopx review-packet --goal-id <goal-id>` |
| Serve local dashboard data | `loopx serve-status --global-registry --port 8766` |

## Source Of Truth

The docs site is a published read model over repository Markdown. The canonical
source remains the Markdown in `docs/`, while project-local runtime state stays
ignored and private.

- [Project README](https://github.com/huangruiteng/loopx#readme)
- [Public/private boundary](public-private-boundary.md)
- [Status data contract](status-data-contract.md)
- [Release readiness](product/release-readiness.md)
