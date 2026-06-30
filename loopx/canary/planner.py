from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CANARY_PROFILE_SCHEMA_VERSION = "catalog_canary_profile_v0"
CANARY_DOMAIN_PROFILE_SCHEMA_VERSION = "catalog_canary_domain_profile_v0"
CANARY_PROFILES_SCHEMA_VERSION = "catalog_canary_profiles_v0"
CANARY_PLAN_SCHEMA_VERSION = "catalog_canary_plan_v0"
CANARY_COVERAGE_AUDIT_SCHEMA_VERSION = "catalog_canary_coverage_audit_v0"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "docs" / "interaction-pattern-catalog.md"


FAMILY_CHECKS: dict[str, list[dict[str, str]]] = {
    "Work Routing": [
        {
            "command": "python3 examples/quota-plan-smoke.py",
            "reason": "exercises quota should-run routing, fallback, and execution obligation projection",
        },
        {
            "command": "python3 examples/quota-work-lane-policy-smoke.py",
            "reason": "checks advancement, monitor, and no-work lane policy selection",
        },
        {
            "command": "python3 examples/monitor-scheduler-contract-smoke.py",
            "reason": "guards due-monitor routing without requiring real external polling",
        },
        {
            "command": "python3 examples/heartbeat-prompt-smoke.py",
            "reason": "checks heartbeat prompt and scheduler guidance for controller loops",
        },
    ],
    "Human Decision": [
        {
            "command": "python3 examples/todo-user-gate-scope-smoke.py",
            "reason": "checks scoped user-gate projection instead of global prose gates",
        },
        {
            "command": "python3 examples/operator-gate-resume-contract-smoke.py",
            "reason": "exercises operator gate preview and resume behavior",
        },
        {
            "command": "python3 examples/reward-gate-direct-write-contract-smoke.py",
            "reason": "guards reward/gate write boundaries before agent continuation",
        },
        {
            "command": "python3 examples/quota-agent-scoped-user-gate-smoke.py",
            "reason": "checks that agent-scoped user gates do not block unrelated lanes",
        },
    ],
    "State And Boundary": [
        {
            "command": "python3 examples/todo-contract-smoke.py",
            "reason": "checks todo metadata shape consumed by status and quota",
        },
        {
            "command": "python3 examples/active-state-structured-projection-smoke.py",
            "reason": "guards active-state structured projection from Markdown drift",
        },
        {
            "command": "python3 examples/task-graph-projection-fixture-smoke.py",
            "reason": "checks task graph projection and lineage without private sources",
        },
        {
            "command": "python3 examples/check-public-boundary-smoke.py",
            "reason": "guards public/private boundary scanning for touched files",
        },
    ],
    "Evidence Lifecycle": [
        {
            "command": "python3 examples/benchmark-run-ledger-smoke.py",
            "reason": "checks compact benchmark/run evidence without raw logs",
        },
        {
            "command": "python3 examples/benchmark-case-analysis-smoke.py",
            "reason": "checks reusable case-analysis projections from compact artifacts",
        },
        {
            "command": "python3 examples/benchmark-artifact-path-filter-smoke.py",
            "reason": "guards raw/private artifact path exclusion",
        },
        {
            "command": "python3 examples/content-ops-public-handle-observation-smoke.py",
            "reason": "checks public-handle evidence observation without private connector reads",
        },
    ],
    "Planning Governance": [
        {
            "command": "python3 examples/autonomous-replan-obligation-smoke.py",
            "reason": "guards stalled-turn autonomous replan obligations",
        },
        {
            "command": "python3 examples/monitor-poll-writeback-smoke.py",
            "reason": "checks monitor poll writeback and no-spend replan triggers",
        },
        {
            "command": "python3 examples/refresh-state-write-correctness-smoke.py",
            "reason": "checks refresh-state writeback correctness and projection updates",
        },
        {
            "command": "python3 examples/dreaming-dry-run-proposal-smoke.py",
            "reason": "checks planning proposal preview remains dry-run and machine-visible",
        },
    ],
}


FAMILY_SELECTOR_HINTS: dict[str, tuple[str, ...]] = {
    "Work Routing": (
        "quota",
        "should-run",
        "status",
        "review-packet",
        "heartbeat",
        "scheduler",
        "work-lane",
        "monitor",
        "handoff",
        "loopx/quota.py",
        "loopx/status.py",
        "loopx/review_packet.py",
        "loopx/heartbeat_prompt.py",
    ),
    "Human Decision": (
        "user todo",
        "operator-gate",
        "reward",
        "decision-scope",
        "deferred",
        "gate",
        "loopx/operator_gate.py",
        "loopx/decision_scope.py",
        "loopx/feedback.py",
    ),
    "State And Boundary": (
        "active state",
        "todo",
        "task graph",
        "authority",
        "boundary",
        "connector",
        "public/private",
        "loopx/todos.py",
        "loopx/todo_contract.py",
        "loopx/status.py",
        "loopx/state_projection.py",
        "loopx/boundary_authority.py",
        "loopx/authority.py",
    ),
    "Evidence Lifecycle": (
        "benchmark",
        "evidence",
        "ledger",
        "artifact",
        "public handle",
        "ci",
        "content-ops",
        "worker_bridge",
        "loopx/benchmark",
        "loopx/worker_bridge.py",
        "loopx/capabilities/content_ops",
    ),
    "Planning Governance": (
        "replan",
        "repair",
        "cadence",
        "dreaming",
        "plan-to-todo",
        "refresh-state",
        "monitor-poll",
        "loopx/dreaming.py",
        "loopx/state_refresh.py",
        "loopx/long_task_cadence.py",
    ),
}


CURRENT_REPO_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "pr-review-and-merge",
        "title": "PR review and merge workflow",
        "purpose": "Check public PR review packets, public-handle evidence, and merge-gate boundaries without approving or merging anything.",
        "catalog_families": ["Human Decision", "Evidence Lifecycle", "State And Boundary"],
        "trigger_hints": ("pr-review", "pull request", "github pr", "self-merge", "merge policy", "public pr metadata"),
        "checks": [
            {
                "command": "python3 examples/pr-review-command-smoke.py",
                "tier": "default",
                "reason": "checks the public-safe /loopx-pr-review packet and review-card contract",
            },
            {
                "command": "python3 examples/value-connectors-github-public-probe-smoke.py",
                "tier": "default",
                "reason": "guards public GitHub issue/PR metadata probes without raw body capture",
            },
            {
                "command": "python3 examples/check-public-boundary-smoke.py",
                "tier": "deep",
                "reason": "runs broader public/private boundary checks when review artifacts are promoted",
            },
        ],
    },
    {
        "id": "release-promotion",
        "title": "Release promotion readiness",
        "purpose": "Check whether the release/canary promotion path is ready without mutating the install.",
        "catalog_families": ["Work Routing", "Planning Governance", "State And Boundary"],
        "trigger_hints": ("release", "promotion", "canary-promotion", "install", "upgrade"),
        "checks": [
            {
                "command": "python3 examples/canary-promotion-readiness-smoke.py",
                "tier": "default",
                "reason": "checks promotion readiness from compact run history",
            },
            {
                "command": "python3 examples/canary-promotion-no-write-contract-smoke.py",
                "tier": "default",
                "reason": "guards no-write promotion readiness behavior",
            },
            {
                "command": "python3 examples/canary-promotion-readiness-writeback-smoke.py",
                "tier": "deep",
                "reason": "exercises promotion readiness writeback after explicit opt-in",
            },
        ],
    },
    {
        "id": "install-update",
        "title": "Install and update safety",
        "purpose": "Check local install, packaged install, update planning, rollback, and uninstall safety before install/update changes ship.",
        "catalog_families": ["State And Boundary", "Work Routing", "Planning Governance"],
        "trigger_hints": (
            "install",
            "installer",
            "packaged install",
            "install-local",
            "install-from-github",
            "loopx update",
            "self-update",
            "update command",
            "upgrade",
            "rollback",
            "uninstall",
            "scripts/install-local.sh",
            "scripts/install-from-github.sh",
            "loopx/self_update.py",
            "loopx/cli_commands/update",
        ),
        "checks": [
            {
                "command": "python3 examples/install-local-smoke.py",
                "tier": "default",
                "reason": "guards the local installer wrapper, skill installation, and install freshness reporting",
            },
            {
                "command": "python3 examples/codex-cli-packaged-install-smoke.py",
                "tier": "default",
                "reason": "checks packaged GitHub/archive install behavior in a temporary home",
            },
            {
                "command": "python3 examples/loopx-update-smoke.py",
                "tier": "default",
                "reason": "checks update planning, check-only behavior, rollback planning, and rollback execution fixtures",
            },
            {
                "command": "python3 examples/rollback-packet-protocol-smoke.py",
                "tier": "deep",
                "reason": "validates the public rollback packet protocol and fixture boundary",
            },
            {
                "command": "python3 examples/project-uninstall-smoke.py",
                "tier": "deep",
                "reason": "samples project-local uninstall safety with isolated fixture registries",
            },
            {
                "command": "python3 examples/worker-bridge-install-contract-smoke.py",
                "tier": "deep",
                "reason": "checks generic worker bridge install contracts without exposing private runtime material",
            },
        ],
    },
    {
        "id": "control-plane-refactor",
        "title": "Control-plane refactor safety",
        "purpose": "Sample hot-path route, policy seam, and interface budget checks for quota/status refactors.",
        "catalog_families": ["Work Routing", "State And Boundary", "Planning Governance"],
        "trigger_hints": (
            "refactor",
            "quota.py",
            "status.py",
            "control-plane",
            "policy seam",
            "work-lane policy",
            "resume_when",
            "resume_ready",
            "loopx/policies/monitor_todo.py",
        ),
        "checks": [
            {
                "command": "python3 examples/control-plane-risk-characterization-smoke.py",
                "tier": "default",
                "reason": "characterizes shared control-plane routing risks",
            },
            {
                "command": "python3 examples/hot-path-interface-budget-smoke.py",
                "tier": "default",
                "reason": "keeps hot-path payload and module growth bounded",
            },
            {
                "command": "python3 examples/quota-resume-gated-open-todo-smoke.py",
                "tier": "default",
                "reason": "guards resume_when-gated open todos from entering executable quota lanes early",
            },
            {
                "command": "python3 examples/work-lane-contract-smoke.py",
                "tier": "deep",
                "reason": "covers broad work-lane policy interactions after larger refactors",
            },
        ],
    },
    {
        "id": "status-read-path",
        "title": "Status read-path contract",
        "purpose": "Check scoped status reads, markdown rendering, and goal-channel status export before status/read-path changes ship.",
        "catalog_families": ["Work Routing", "State And Boundary"],
        "trigger_hints": (
            "read-path",
            "status --goal-id",
            "status data",
            "goal status",
            "loopx/status.py",
            "loopx/cli_commands/status",
        ),
        "checks": [
            {
                "command": "python3 examples/status-goal-filter-smoke.py",
                "tier": "default",
                "reason": "guards scoped status projection and global default status behavior",
            },
            {
                "command": "python3 examples/status-markdown-smoke.py",
                "tier": "default",
                "reason": "checks operator-facing markdown status rendering",
            },
            {
                "command": "python3 examples/goal-channel-status-export-smoke.py",
                "tier": "default",
                "reason": "guards goal-channel status export consumed by non-hot-path readers",
            },
            {
                "command": "python3 examples/status-quota-perf-budget-smoke.py",
                "tier": "deep",
                "reason": "runs the broader status/quota performance budget sample when explicitly requested",
            },
        ],
    },
    {
        "id": "review-packet-read-path",
        "title": "Review-packet read-path contract",
        "purpose": "Check operator review packets, handoff-only payloads, and task-graph lineage before review-packet/read-path changes ship.",
        "catalog_families": ["Work Routing", "Human Decision", "State And Boundary"],
        "trigger_hints": (
            "review-packet",
            "review packet",
            "handoff-only",
            "project-agent handoff",
            "operator packet",
            "loopx/review_packet.py",
            "loopx/cli_commands/status",
            "docs/status-data-contract.md",
        ),
        "checks": [
            {
                "command": "python3 examples/review-packet-cli-smoke.py",
                "tier": "default",
                "reason": "guards CLI-visible review-packet and handoff-only JSON contracts",
            },
            {
                "command": "python3 examples/review-packet-smoke.py",
                "tier": "default",
                "reason": "checks dashboard/operator packet copy and public-safe handoff text",
            },
            {
                "command": "python3 examples/task-graph-projection-fixture-smoke.py",
                "tier": "default",
                "reason": "guards task-graph lineage consumed by review packets without private sources",
            },
            {
                "command": "python3 examples/control-plane-integrated-canary-smoke.py",
                "tier": "deep",
                "reason": "samples the bounded status -> quota -> review-packet event read path",
            },
            {
                "command": "python3 examples/hot-path-interface-budget-smoke.py",
                "tier": "deep",
                "reason": "checks review-packet handoff interface budgets after hot-path changes",
            },
        ],
    },
    {
        "id": "event-sourced-read-path",
        "title": "Event-sourced read-path contract",
        "purpose": "Check event projection, status read path, downstream read surfaces, and migration gates before event-store/read-path changes ship.",
        "catalog_families": ["Work Routing", "State And Boundary", "Planning Governance"],
        "trigger_hints": (
            "event-sourced",
            "event sourced",
            "event projection",
            "event read-path",
            "downstream read",
            "event-store",
            "event store",
            "loopx/event_sourced_state.py",
            "loopx/rollout_event_log.py",
            "docs/reference/protocols/event-store-migration-bridge-v0.md",
        ),
        "checks": [
            {
                "command": "python3 examples/event-sourced-state-api-smoke.py",
                "tier": "default",
                "reason": "guards event append/replay API behavior used by read-path projections",
            },
            {
                "command": "python3 examples/event-sourced-status-read-path-smoke.py",
                "tier": "default",
                "reason": "checks status consumption of event projection with Markdown fallback",
            },
            {
                "command": "python3 examples/event-sourced-downstream-read-path-smoke.py",
                "tier": "default",
                "reason": "checks downstream read surfaces consume event projection without private state",
            },
            {
                "command": "python3 examples/event-store-migration-bridge-smoke.py",
                "tier": "deep",
                "reason": "samples the migration bridge gates before bounded event read-path canaries",
            },
            {
                "command": "python3 examples/event-sourced-replay-compaction-smoke.py",
                "tier": "deep",
                "reason": "checks replay compaction when broader event-store changes are promoted",
            },
        ],
    },
    {
        "id": "cli-command-contract",
        "title": "CLI command module contract",
        "purpose": "Check command-module boundaries, ownership budgets, and compatibility for LoopX CLI refactors.",
        "catalog_families": ["State And Boundary", "Planning Governance"],
        "trigger_hints": (
            "loopx/cli.py",
            "loopx/cli_commands",
            "cli command",
            "command modularization",
            "command-module",
        ),
        "checks": [
            {
                "command": "python3 examples/cli-version-command-modularization-smoke.py",
                "tier": "default",
                "reason": "guards a low-risk command migration plus old version invocations",
            },
            {
                "command": "python3 examples/cli-control-plane-command-modularization-smoke.py",
                "tier": "default",
                "reason": "samples todo/quota command compatibility after CLI command refactors",
            },
        ],
    },
    {
        "id": "todo-lifecycle",
        "title": "Todo lifecycle contract",
        "purpose": "Check todo metadata, lifecycle transitions, and event/list projection before todo read/write CLI changes ship.",
        "catalog_families": ["State And Boundary", "Human Decision", "Planning Governance"],
        "trigger_hints": (
            "todo lifecycle",
            "todo claim",
            "todo list",
            "todo complete",
            "todo supersede",
            "todo metadata",
            "todo detail",
            "loopx/todos.py",
            "loopx/todo_contract.py",
            "loopx/cli_commands/todo",
        ),
        "checks": [
            {
                "command": "python3 examples/todo-contract-smoke.py",
                "tier": "default",
                "reason": "guards the public todo status and metadata helper contract",
            },
            {
                "command": "python3 examples/todo-cli-smoke.py",
                "tier": "default",
                "reason": "checks agent-facing todo add/update/list behavior on fixture state",
            },
            {
                "command": "python3 examples/todo-lifecycle-cli-smoke.py",
                "tier": "default",
                "reason": "exercises claim, completion, successor, and handoff lifecycle transitions by todo_id",
            },
            {
                "command": "python3 examples/todo-list-event-projection-smoke.py",
                "tier": "default",
                "reason": "guards event-sourced todo list projection with Markdown fallback",
            },
            {
                "command": "python3 examples/todo-concurrent-write-lock-smoke.py",
                "tier": "deep",
                "reason": "samples lock behavior for concurrent todo writes",
            },
            {
                "command": "python3 examples/todo-detail-cold-path-contract-smoke.py",
                "tier": "deep",
                "reason": "checks the cold-path todo detail contract when detail surfaces are promoted",
            },
        ],
    },
    {
        "id": "monitor-scheduler",
        "title": "Monitor scheduler routing",
        "purpose": "Check monitor due/quiet/replan behavior without polling external targets by default.",
        "catalog_families": ["Work Routing", "Planning Governance"],
        "trigger_hints": ("monitor", "scheduler", "next_due_at", "monitor-poll", "continuous_monitor"),
        "checks": [
            {
                "command": "python3 examples/monitor-scheduler-contract-smoke.py",
                "tier": "default",
                "reason": "checks due monitor selection, expiry, and priority behavior",
            },
            {
                "command": "python3 examples/monitor-poll-writeback-smoke.py",
                "tier": "default",
                "reason": "guards no-spend monitor poll writeback and replan triggers",
            },
            {
                "command": "python3 examples/heartbeat-quota-flow-smoke.py",
                "tier": "deep",
                "reason": "runs a broader heartbeat/quota control-flow sample",
            },
        ],
    },
    {
        "id": "state-write-correctness",
        "title": "State write correctness",
        "purpose": "Check local state writes, refresh-state, and todo write paths before touching writer internals.",
        "catalog_families": ["State And Boundary", "Planning Governance", "Human Decision"],
        "trigger_hints": ("state write", "refresh-state", "todo write", "idempotency", "revision", "lease"),
        "checks": [
            {
                "command": "python3 examples/local-state-write-correctness-contract-smoke.py",
                "tier": "default",
                "reason": "checks local state write correctness contract fixtures",
            },
            {
                "command": "python3 examples/refresh-state-write-correctness-smoke.py",
                "tier": "default",
                "reason": "guards refresh-state update behavior and projection writes",
            },
            {
                "command": "python3 examples/todo-concurrent-write-lock-smoke.py",
                "tier": "deep",
                "reason": "samples lock behavior for concurrent todo writes",
            },
        ],
    },
    {
        "id": "product-entry-workflows",
        "title": "Product entry workflows",
        "purpose": (
            "Check user-facing product entry routes for issue-fix, content-ops, "
            "update notes, and cross-runtime demo surfaces without reading private sources."
        ),
        "catalog_families": ["Human Decision", "Evidence Lifecycle", "State And Boundary", "Work Routing"],
        "trigger_hints": (
            "product-entry",
            "product entry",
            "issue-fix",
            "issue fix",
            "content-ops",
            "content ops",
            "update-note",
            "update note",
            "update-notes",
            "update notes",
            "cross-runtime",
            "impl-review",
            "claude implements",
            "codex reviews",
            "README.md",
            "docs/product/cross-runtime-impl-review-demo.md",
            "docs/capabilities/issue-fix",
            "docs/capabilities/content-ops",
            "docs/update-notes",
            "loopx/capabilities/issue_fix",
            "loopx/capabilities/content_ops",
            "loopx/cli_commands/issue_fix",
            "loopx/cli_commands/content_ops",
            "scripts/update_notes_release_job.py",
        ),
        "checks": [
            {
                "command": "python3 examples/issue-fix-workflow-contract-smoke.py",
                "tier": "default",
                "reason": "guards the public issue-fix workflow contract, gated metadata preview, and todo writeback preview",
            },
            {
                "command": "python3 examples/content-ops-issue-fix-intake-smoke.py",
                "tier": "default",
                "reason": "checks content-ops issue-fix intake from public metadata without external reads or writes",
            },
            {
                "command": "python3 examples/readme-demo-surface-smoke.py",
                "tier": "default",
                "reason": "guards the README and cross-runtime implement/review demo entry surface",
            },
            {
                "command": "python3 examples/update-notes-archive-smoke.py",
                "tier": "default",
                "reason": "checks public update-note archive, automation wiring, and private-boundary exclusions",
            },
            {
                "command": "python3 examples/issue-fix-workflow-e2e-smoke.py",
                "tier": "deep",
                "reason": "runs the fuller issue-fix metadata-to-plan-to-review-packet product path",
            },
            {
                "command": "python3 examples/issue-fix-acceptance-loop-smoke.py",
                "tier": "deep",
                "reason": "samples the heavier caller-repo branch and acceptance-loop fixture",
            },
            {
                "command": "python3 examples/content-ops-private-connector-gate-smoke.py",
                "tier": "deep",
                "reason": "checks private connector owner-gate projection for content operations",
            },
        ],
    },
    {
        "id": "cross-runtime-impl-review-demo",
        "title": "Cross-runtime implementation/review demo",
        "purpose": (
            "Check the Claude Code implementation + Codex review demo packet "
            "without writing state or launching either runtime."
        ),
        "catalog_families": [
            "Human Decision",
            "Work Routing",
            "Evidence Lifecycle",
            "State And Boundary",
        ],
        "trigger_hints": (
            "cross-runtime",
            "impl-review",
            "claude implements",
            "codex reviews",
            "claude-code-impl",
            "codex-review",
            "loopx demo impl-review",
            "cross_runtime_impl_review_demo_packet_v0",
            "docs/product/cross-runtime-impl-review-demo.md",
            "loopx/capabilities/cross_runtime",
            "loopx/cli_commands/starter.py",
        ),
        "checks": [
            {
                "command": "python3 examples/cross-runtime-impl-review-demo-smoke.py",
                "tier": "default",
                "reason": "guards the dry-run packet, CLI route, role split, and no-write boundary",
            },
            {
                "command": "python3 examples/readme-demo-surface-smoke.py",
                "tier": "default",
                "reason": "guards the public README and product note entry points for the demo",
            },
        ],
    },
    {
        "id": "host-command-entry",
        "title": "Host command entry and slash-command discovery",
        "purpose": (
            "Check slash-command discovery, Codex App host command routing, "
            "and global manager command entry surfaces without mutating project state."
        ),
        "catalog_families": ["Human Decision", "Work Routing", "State And Boundary"],
        "trigger_hints": (
            "slash-command",
            "slash command",
            "slash-commands",
            "/loopx-global-summary",
            "/loopx-global-gates",
            "/loopx-global-todos",
            "/loopx-global-risks",
            "global-manager",
            "global manager",
            "host command",
            "host command registry",
            "codex app host command",
            "docs/reference/protocols/codex-app-host-command-registry-v0.md",
            "docs/reference/protocols/global-manager-command-v0.md",
            "loopx/cli_commands/slash_commands.py",
            "loopx/cli_commands/summary_all.py",
        ),
        "checks": [
            {
                "command": "python3 examples/slash-command-catalog-smoke.py",
                "tier": "default",
                "reason": "guards public slash-command discovery and legacy alias visibility",
            },
            {
                "command": "python3 examples/codex-app-host-command-registry-smoke.py",
                "tier": "default",
                "reason": "guards Codex App host command routing and fail-closed slash-command help",
            },
            {
                "command": "python3 examples/global-manager-command-protocol-smoke.py",
                "tier": "default",
                "reason": "checks read-only global manager command protocol and aliases",
            },
        ],
    },
    {
        "id": "frontstage-rollout",
        "title": "Frontstage rollout projection",
        "purpose": "Check public frontstage/showcase projection data before visual browser smokes.",
        "catalog_families": ["State And Boundary", "Evidence Lifecycle", "Human Decision"],
        "trigger_hints": ("frontstage", "showcase", "rollout", "dashboard", "visual"),
        "checks": [
            {
                "command": "python3 examples/frontstage-rollout-projections-fixture-smoke.py",
                "tier": "default",
                "reason": "checks reusable frontstage rollout projection fixtures",
            },
            {
                "command": "python3 examples/showcase-animation-prototype-smoke.py",
                "tier": "default",
                "reason": "guards showcase animation projection data without a browser",
            },
            {
                "command": "node examples/dashboard-frontstage-browser-smoke.mjs",
                "tier": "deep",
                "reason": "runs browser-level visual route validation when UI is promoted",
            },
        ],
    },
    {
        "id": "auto-research-demo",
        "title": "Auto-research demo and frontier route",
        "purpose": (
            "Check visible auto-research demo routing, deterministic E2E replay, "
            "and shared frontier projection without launching real Codex lanes by default."
        ),
        "catalog_families": ["Work Routing", "Evidence Lifecycle", "State And Boundary", "Human Decision"],
        "trigger_hints": (
            "auto-research",
            "auto research",
            "demo-supervisor",
            "demo e2e",
            "frontier",
            "visible launcher",
            "one-click",
            "loopx/capabilities/auto_research",
            "loopx/cli_commands/auto_research",
        ),
        "checks": [
            {
                "command": "python3 examples/auto-research-demo-e2e-smoke.py",
                "tier": "default",
                "reason": "checks the deterministic positive demo route, route contract, and no-live-claim boundary",
            },
            {
                "command": "python3 examples/auto-research-one-click-ux-smoke.py",
                "tier": "default",
                "reason": "checks the one-command visible UX packet with fake tmux/Codex binaries",
            },
            {
                "command": "python3 examples/decentralized-auto-research-frontier-smoke.py",
                "tier": "default",
                "reason": "checks shared frontier, evidence graph, board projection, and public boundary fixtures",
            },
            {
                "command": "python3 examples/auto-research-demo-supervisor-smoke.py",
                "tier": "deep",
                "reason": "samples the full dry-run supervisor packet and lane bootstrap contract",
            },
            {
                "command": "python3 examples/auto-research-visible-launcher-smoke.py",
                "tier": "deep",
                "reason": "runs the fake visible launcher acceptance path without starting real Codex work",
            },
            {
                "command": "python3 examples/auto-research-rollout-readpath-smoke.py",
                "tier": "deep",
                "reason": "checks rollout event read-path projection into live evidence graphs",
            },
            {
                "command": "python3 examples/auto-research-live-codex-claim-boundary-smoke.py",
                "tier": "deep",
                "reason": "guards that live E2E claims require lane-authored public evidence",
            },
            {
                "command": "python3 examples/auto-research-live-evidence-capture-smoke.py",
                "tier": "deep",
                "reason": "checks compact live evidence capture fixtures for visible lanes",
            },
        ],
    },
    {
        "id": "benchmark-adapter-readiness",
        "title": "Benchmark adapter readiness",
        "purpose": "Check public adapter contracts and evidence boundaries without launching benchmark jobs by default.",
        "catalog_families": ["Evidence Lifecycle", "State And Boundary", "Work Routing"],
        "trigger_hints": ("benchmark", "adapter", "runner", "ledger", "skillsbench", "terminal-bench"),
        "checks": [
            {
                "command": "python3 examples/benchmark-core-adapter-contract-smoke.py",
                "tier": "default",
                "reason": "checks shared benchmark adapter contract behavior",
            },
            {
                "command": "python3 examples/benchmark-artifact-path-filter-smoke.py",
                "tier": "default",
                "reason": "guards raw/private benchmark artifact path exclusion",
            },
            {
                "command": "python3 examples/skillsbench-benchmark-run-smoke.py",
                "tier": "deep",
                "reason": "runs the heavier SkillsBench integration smoke only when explicitly requested",
            },
        ],
    },
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _parse_markdown_table(lines: list[str]) -> list[dict[str, str]]:
    rows = [_split_table_row(line) for line in lines if line.strip().startswith("|")]
    if len(rows) < 3:
        return []
    headers = rows[0]
    parsed: list[dict[str, str]] = []
    for row in rows[2:]:
        if len(row) != len(headers):
            continue
        parsed.append({headers[index]: value for index, value in enumerate(row)})
    return parsed


def _first_table_after(text: str, marker: str) -> list[dict[str, str]]:
    index = text.find(marker)
    if index < 0:
        return []
    table_lines: list[str] = []
    in_table = False
    for line in text[index:].splitlines():
        if line.strip().startswith("|"):
            table_lines.append(line)
            in_table = True
        elif in_table:
            break
    return _parse_markdown_table(table_lines)


def _pattern_ids(value: str) -> list[str]:
    return sorted(set(re.findall(r"\bIP-\d{3}\b", value)))


def _split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def _read_catalog(catalog_path: Path | None = None) -> tuple[Path, str]:
    path = (catalog_path or DEFAULT_CATALOG_PATH).expanduser()
    return path, path.read_text(encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_catalog_canary_profiles(catalog_path: Path | None = None) -> dict[str, Any]:
    path, text = _read_catalog(catalog_path)
    archetype_rows = _first_table_after(text, "| Canary Archetype |")
    family_rows = _first_table_after(text, "| Family |")

    archetypes = []
    for row in archetype_rows:
        name = row.get("Canary Archetype", "")
        archetypes.append(
            {
                "id": _slug(name),
                "name": name,
                "primary_question": row.get("Primary Question", ""),
                "trigger_surface": row.get("Typical Trigger Surface", ""),
                "fixture_depth": row.get("Fixture Depth", ""),
                "cost_tier": row.get("Cost Tier", ""),
                "failure_meaning": row.get("Failure Usually Means", ""),
            }
        )

    profiles = []
    for row in family_rows:
        family = row.get("Family", "")
        archetype_names = _split_semicolon(row.get("Default Canary Archetypes", ""))
        profiles.append(
            {
                "schema_version": CANARY_PROFILE_SCHEMA_VERSION,
                "id": _slug(family),
                "family": family,
                "pattern_ids": _pattern_ids(row.get("P0/P1 Pattern Coverage", "")),
                "default_archetypes": [
                    {
                        "id": _slug(name),
                        "name": name,
                    }
                    for name in archetype_names
                ],
                "trigger_surfaces": row.get("Trigger Surfaces", ""),
                "minimum_useful_fixture": row.get("Minimum Useful Fixture", ""),
                "failure_meaning": row.get("Failure Meaning", ""),
                "candidate_checks": FAMILY_CHECKS.get(family, []),
            }
        )

    domain_profiles = []
    for profile in CURRENT_REPO_PROFILES:
        domain_profiles.append(
            {
                "schema_version": CANARY_DOMAIN_PROFILE_SCHEMA_VERSION,
                **profile,
                "checks": list(profile.get("checks", [])),
            }
        )

    return {
        "ok": bool(archetypes and profiles),
        "schema_version": CANARY_PROFILES_SCHEMA_VERSION,
        "source": _display_path(path),
        "dry_run": True,
        "executes_checks": False,
        "archetype_count": len(archetypes),
        "profile_count": len(profiles),
        "domain_profile_count": len(domain_profiles),
        "archetypes": archetypes,
        "profiles": profiles,
        "domain_profiles": domain_profiles,
    }


def _catalog_pattern_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _split_table_row(line)
        if len(cells) < 3:
            continue
        if cells[0] not in {"P0", "P1", "P2"} or not re.fullmatch(r"IP-\d{3}", cells[1]):
            continue
        rows.append(
            {
                "importance": cells[0],
                "pattern_id": cells[1],
                "name": cells[2],
            }
        )
    return rows


def _coverage_exception_rows(text: str) -> dict[str, dict[str, str]]:
    table = _first_table_after(text, "| Pattern ID | Canary Coverage Status |")
    exceptions: dict[str, dict[str, str]] = {}
    for row in table:
        pattern_id = next(iter(_pattern_ids(row.get("Pattern ID", ""))), "")
        if not pattern_id:
            continue
        status = _slug(row.get("Canary Coverage Status", ""))
        if status not in {"non-applicable", "not-applicable", "deferred"}:
            continue
        exceptions[pattern_id] = {
            "pattern_id": pattern_id,
            "status": "non-applicable" if status == "not-applicable" else status,
            "rationale": row.get("Rationale", ""),
            "owner": row.get("Owner", ""),
        }
    return exceptions


def _coverage_exception_is_valid(exception: dict[str, str]) -> bool:
    status = exception.get("status")
    rationale = bool(str(exception.get("rationale") or "").strip())
    owner = bool(str(exception.get("owner") or "").strip())
    if status == "non-applicable":
        return rationale
    if status == "deferred":
        return rationale and owner
    return False


def build_catalog_canary_coverage_audit(
    *,
    catalog_path: Path | None = None,
    priorities: list[str] | None = None,
) -> dict[str, Any]:
    path, text = _read_catalog(catalog_path)
    profile_packet = build_catalog_canary_profiles(catalog_path)
    required_priorities = tuple(priorities or ["P0", "P1"])
    pattern_rows = [
        row
        for row in _catalog_pattern_rows(text)
        if row.get("importance") in required_priorities
    ]
    profile_coverage: dict[str, list[str]] = {}
    for profile in profile_packet.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id") or "")
        for pattern_id in profile.get("pattern_ids", []):
            if isinstance(pattern_id, str):
                profile_coverage.setdefault(pattern_id, []).append(profile_id)
    exceptions = _coverage_exception_rows(text)

    covered: list[dict[str, Any]] = []
    excepted: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    invalid_exceptions: list[dict[str, Any]] = []
    for row in pattern_rows:
        pattern_id = row["pattern_id"]
        profile_ids = profile_coverage.get(pattern_id, [])
        if profile_ids:
            covered.append({**row, "profile_ids": profile_ids})
            continue
        exception = exceptions.get(pattern_id)
        if exception and _coverage_exception_is_valid(exception):
            excepted.append({**row, **exception})
            continue
        if exception:
            invalid_exceptions.append({**row, **exception})
        else:
            missing.append(row)

    drift_count = len(missing) + len(invalid_exceptions)
    return {
        "ok": bool(profile_packet.get("ok")) and drift_count == 0,
        "schema_version": CANARY_COVERAGE_AUDIT_SCHEMA_VERSION,
        "source": _display_path(path),
        "dry_run": True,
        "executes_checks": False,
        "priorities": list(required_priorities),
        "required_pattern_count": len(pattern_rows),
        "covered_count": len(covered),
        "excepted_count": len(excepted),
        "missing_count": len(missing),
        "invalid_exception_count": len(invalid_exceptions),
        "drift_count": drift_count,
        "covered_patterns": covered,
        "excepted_patterns": excepted,
        "missing_patterns": missing,
        "invalid_exceptions": invalid_exceptions,
        "note": (
            "Coverage means each selected catalog pattern is listed in a canary "
            "family profile, or has an explicit non-applicable rationale or "
            "deferred owner in a catalog coverage exception table. This audit "
            "reports drift only; it does not force one giant canary or execute checks."
        ),
    }


def _selector_blob(changed_files: list[str], surfaces: list[str]) -> str:
    return "\n".join([*changed_files, *surfaces]).lower()


def _selection_reasons(profile: dict[str, Any], selector_blob: str) -> list[str]:
    family = str(profile.get("family") or "")
    family_lc = family.lower()
    reasons: list[str] = []
    if family_lc and family_lc in selector_blob:
        reasons.append(f"selector names catalog family `{family}`")
    for hint in FAMILY_SELECTOR_HINTS.get(family, ()):
        if hint.lower() in selector_blob:
            reasons.append(f"selector matches `{hint}`")
    trigger_surfaces = str(profile.get("trigger_surfaces") or "").lower()
    for token in re.findall(r"[a-z][a-z0-9_-]{2,}", selector_blob):
        if token in trigger_surfaces and f"trigger surface mentions `{token}`" not in reasons:
            reasons.append(f"trigger surface mentions `{token}`")
    return reasons


def _domain_selection_reasons(profile: dict[str, Any], selector_blob: str) -> list[str]:
    reasons: list[str] = []
    profile_id = str(profile.get("id") or "")
    title = str(profile.get("title") or "")
    if profile_id and profile_id in selector_blob:
        reasons.append(f"selector names profile `{profile_id}`")
    if title and title.lower() in selector_blob:
        reasons.append(f"selector names profile `{title}`")
    for hint in profile.get("trigger_hints", []):
        hint_text = str(hint or "").lower()
        if hint_text and hint_text in selector_blob:
            reasons.append(f"selector matches `{hint}`")
    for family in profile.get("catalog_families", []):
        family_text = str(family or "").lower()
        if family_text and family_text in selector_blob:
            reasons.append(f"selector matches family `{family}`")
    return reasons


def _domain_profile_with_checks(
    profile: dict[str, Any],
    *,
    include_deep_checks: bool,
    max_checks: int,
) -> dict[str, Any]:
    checks = [
        dict(check)
        for check in profile.get("checks", [])
        if include_deep_checks or check.get("tier") != "deep"
    ]
    copied = dict(profile)
    copied["checks"] = checks[: max(1, max_checks)]
    copied["deep_checks_available"] = any(
        isinstance(check, dict) and check.get("tier") == "deep"
        for check in profile.get("checks", [])
    )
    copied["deep_checks_included"] = bool(include_deep_checks)
    return copied


def build_catalog_canary_plan(
    *,
    catalog_path: Path | None = None,
    changed_files: list[str] | None = None,
    surfaces: list[str] | None = None,
    families: list[str] | None = None,
    profiles: list[str] | None = None,
    include_deep_checks: bool = False,
    max_checks_per_family: int = 3,
    max_checks_per_profile: int = 3,
) -> dict[str, Any]:
    packet = build_catalog_canary_profiles(catalog_path)
    changed_files = changed_files or []
    surfaces = surfaces or []
    requested_families = {_slug(family) for family in (families or []) if family.strip()}
    requested_profiles = {_slug(profile) for profile in (profiles or []) if profile.strip()}
    selector_blob = _selector_blob(changed_files, surfaces)
    max_checks = max(1, max_checks_per_family)
    max_profile_checks = max(1, max_checks_per_profile)

    selected_profiles: list[dict[str, Any]] = []
    for profile in packet["profiles"]:
        if requested_profiles and not requested_families and not selector_blob:
            continue
        reasons = _selection_reasons(profile, selector_blob)
        if requested_families and _slug(str(profile.get("family") or "")) not in requested_families:
            continue
        if not requested_families and selector_blob and not reasons:
            continue
        profile_copy = dict(profile)
        profile_copy["candidate_checks"] = list(profile_copy.get("candidate_checks", []))[:max_checks]
        profile_copy["selection_reasons"] = reasons or [
            "selected because no narrower selector was provided",
        ]
        selected_profiles.append(profile_copy)

    selected_domain_profiles: list[dict[str, Any]] = []
    for profile in packet["domain_profiles"]:
        reasons = _domain_selection_reasons(profile, selector_blob)
        if requested_profiles and _slug(str(profile.get("id") or "")) not in requested_profiles:
            continue
        if not requested_profiles and selector_blob and not reasons:
            continue
        if not requested_profiles and not selector_blob:
            continue
        profile_copy = _domain_profile_with_checks(
            profile,
            include_deep_checks=include_deep_checks,
            max_checks=max_profile_checks,
        )
        profile_copy["selection_reasons"] = reasons or [
            "selected because this profile was explicitly requested",
        ]
        selected_domain_profiles.append(profile_copy)

    return {
        "ok": True,
        "schema_version": CANARY_PLAN_SCHEMA_VERSION,
        "source": packet["source"],
        "dry_run": True,
        "executes_checks": False,
        "selection_inputs": {
            "changed_files": changed_files,
            "surfaces": surfaces,
            "families": families or [],
            "profiles": profiles or [],
            "include_deep_checks": include_deep_checks,
            "max_checks_per_family": max_checks,
            "max_checks_per_profile": max_profile_checks,
        },
        "profile_count": len(selected_profiles),
        "domain_profile_count": len(selected_domain_profiles),
        "profiles": selected_profiles,
        "domain_profiles": selected_domain_profiles,
        "note": (
            "This planner only selects and explains candidate canary checks. "
            "It does not execute smoke tests or create new runtime contracts. "
            "Plan from existing public runtime/status contracts first; when a "
            "new runtime contract seems necessary, stop at an owner-review "
            "necessity/risk packet before implementation."
        ),
    }


def render_catalog_canary_profiles_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Catalog Canary Profiles",
        "",
        f"- source: `{payload.get('source')}`",
        f"- archetypes: `{payload.get('archetype_count')}`",
        f"- profiles: `{payload.get('profile_count')}`",
        "- dry_run: `true`",
        "- executes_checks: `false`",
        "",
    ]
    for profile in payload.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        lines.extend(
            [
                f"## {profile.get('family')}",
                f"- patterns: `{', '.join(profile.get('pattern_ids') or [])}`",
                "- archetypes: "
                + ", ".join(
                    f"`{item.get('name')}`"
                    for item in profile.get("default_archetypes", [])
                    if isinstance(item, dict)
                ),
                f"- trigger surfaces: {profile.get('trigger_surfaces')}",
                f"- minimum fixture: {profile.get('minimum_useful_fixture')}",
                f"- failure meaning: {profile.get('failure_meaning')}",
                "",
            ]
        )
    if payload.get("domain_profiles"):
        lines.extend(["## Current Repo Profiles", ""])
        for profile in payload.get("domain_profiles", []):
            if not isinstance(profile, dict):
                continue
            default_count = sum(
                1 for check in profile.get("checks", []) if isinstance(check, dict) and check.get("tier") != "deep"
            )
            deep_count = sum(
                1 for check in profile.get("checks", []) if isinstance(check, dict) and check.get("tier") == "deep"
            )
            lines.extend(
                [
                    f"### {profile.get('title')}",
                    f"- id: `{profile.get('id')}`",
                    f"- catalog families: `{', '.join(profile.get('catalog_families') or [])}`",
                    f"- purpose: {profile.get('purpose')}",
                    f"- default checks: `{default_count}`",
                    f"- deep checks: `{deep_count}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_catalog_canary_plan_markdown(payload: dict[str, Any]) -> str:
    inputs = payload.get("selection_inputs") if isinstance(payload.get("selection_inputs"), dict) else {}
    lines = [
        "# Catalog Canary Plan",
        "",
        f"- source: `{payload.get('source')}`",
        "- dry_run: `true`",
        "- executes_checks: `false`",
        f"- selected_profiles: `{payload.get('profile_count')}`",
        f"- selected_domain_profiles: `{payload.get('domain_profile_count')}`",
        f"- changed_files: `{', '.join(inputs.get('changed_files') or [])}`",
        f"- surfaces: `{', '.join(inputs.get('surfaces') or [])}`",
        f"- families: `{', '.join(inputs.get('families') or [])}`",
        f"- profiles: `{', '.join(inputs.get('profiles') or [])}`",
        f"- include_deep_checks: `{str(inputs.get('include_deep_checks')).lower()}`",
        "",
        str(payload.get("note") or ""),
        "",
    ]
    for profile in payload.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        lines.extend(
            [
                f"## {profile.get('family')}",
                f"- patterns: `{', '.join(profile.get('pattern_ids') or [])}`",
                "- selected because: "
                + "; ".join(str(reason) for reason in profile.get("selection_reasons", [])),
                "- archetypes: "
                + ", ".join(
                    f"`{item.get('name')}`"
                    for item in profile.get("default_archetypes", [])
                    if isinstance(item, dict)
                ),
                f"- minimum fixture: {profile.get('minimum_useful_fixture')}",
                f"- failure meaning: {profile.get('failure_meaning')}",
                "- suggested checks:",
            ]
        )
        for check in profile.get("candidate_checks", []):
            if isinstance(check, dict):
                lines.append(f"  - `{check.get('command')}` - {check.get('reason')}")
        lines.append("")
    for profile in payload.get("domain_profiles", []):
        if not isinstance(profile, dict):
            continue
        lines.extend(
            [
                f"## {profile.get('title')}",
                f"- id: `{profile.get('id')}`",
                f"- catalog families: `{', '.join(profile.get('catalog_families') or [])}`",
                "- selected because: "
                + "; ".join(str(reason) for reason in profile.get("selection_reasons", [])),
                f"- purpose: {profile.get('purpose')}",
                f"- deep checks available: `{str(profile.get('deep_checks_available')).lower()}`",
                f"- deep checks included: `{str(profile.get('deep_checks_included')).lower()}`",
                "- suggested checks:",
            ]
        )
        for check in profile.get("checks", []):
            if isinstance(check, dict):
                lines.append(
                    f"  - `{check.get('command')}` [{check.get('tier')}] - {check.get('reason')}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_catalog_canary_coverage_audit_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Catalog Canary Coverage Audit",
        "",
        f"- source: `{payload.get('source')}`",
        "- dry_run: `true`",
        "- executes_checks: `false`",
        f"- priorities: `{', '.join(payload.get('priorities') or [])}`",
        f"- required_patterns: `{payload.get('required_pattern_count')}`",
        f"- covered: `{payload.get('covered_count')}`",
        f"- excepted: `{payload.get('excepted_count')}`",
        f"- missing: `{payload.get('missing_count')}`",
        f"- invalid_exceptions: `{payload.get('invalid_exception_count')}`",
        f"- drift: `{payload.get('drift_count')}`",
        "",
        str(payload.get("note") or ""),
        "",
    ]
    if payload.get("missing_patterns"):
        lines.extend(["## Missing Coverage", ""])
        for row in payload.get("missing_patterns", []):
            if isinstance(row, dict):
                lines.append(
                    f"- `{row.get('pattern_id')}` {row.get('name')} ({row.get('importance')})"
                )
        lines.append("")
    if payload.get("invalid_exceptions"):
        lines.extend(["## Invalid Exceptions", ""])
        for row in payload.get("invalid_exceptions", []):
            if isinstance(row, dict):
                lines.append(
                    f"- `{row.get('pattern_id')}` {row.get('status')}: "
                    f"rationale={row.get('rationale')!r}; owner={row.get('owner')!r}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
