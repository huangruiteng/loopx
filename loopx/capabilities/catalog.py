from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .registry import CapabilityRegistry
from ..extensions.runtime import extension_catalog_entries


CAPABILITY_CATALOG_SCHEMA_VERSION = "loopx_capability_catalog_v0"
CAPABILITY_DETAIL_SCHEMA_VERSION = "loopx_capability_detail_v0"


BUILTIN_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "issue-fix",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Repo issue-fix loop",
        "status": "active-preview",
        "real_world_anchor": "open-source issue/PR solver",
        "user_value": (
            "Turn a public GitHub issue or PR signal into a caller-approved "
            "local issue branch with validation evidence and a PR-review packet."
        ),
        "entry_command": "loopx issue-fix workflow-plan --url <github-issue-url> --format json",
        "commands": [
            {
                "command": "loopx content-ops issue-fix-metadata-preview --url <github-issue-url> --fetch-metadata --format json",
                "purpose": "Fetch body-free public GitHub issue/PR metadata.",
                "write_boundary": "read-only external metadata; no issue comment, PR, or todo write",
            },
            {
                "command": "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --fetch-metadata --format json",
                "purpose": "Use the compatibility CLI to fetch the issue-fix-owned public GitHub probe packet.",
                "write_boundary": "public metadata read only; no issue bodies, comments, PRs, account changes, or writes",
            },
            {
                "command": "loopx value-connectors github-reply-monitor --issue-url <github-issue-or-pr-url> --after-comment-url <github-issue-comment-url> --fetch-metadata --format json",
                "purpose": "Use the compatibility CLI to detect public maintainer replies through the issue-fix provider.",
                "write_boundary": "public comment metadata read only; no comment bodies, thread bump, or external write",
            },
            {
                "command": "loopx content-ops issue-fix-intake --format json",
                "purpose": "Project public issue metadata into an issue-fix intake packet.",
                "write_boundary": "fixture-only; no external read or write",
            },
            {
                "command": "loopx issue-fix workflow-plan --url <github-issue-url> --repo-path <repo> --repository-context-json <context.json> --format json",
                "purpose": "Compose metadata, repository context, intake, feasibility, validation labels, and PR review readiness blockers.",
                "write_boundary": "preview-only; no todo write, repo execution, external comment, PR creation, merge, or publish",
            },
            {
                "command": "loopx issue-fix feasibility --url <github-issue-url> --reproduction-status <state> --scope-class <scope> --repository-context-json <context.json> --goal-id <goal-id> --format json",
                "purpose": "Select one route and persist its compact repository evidence basis with feasibility domain state.",
                "write_boundary": "writes compact project-local domain state with goal or ledger context; no raw issue/comment/log capture or external write",
            },
            {
                "command": "loopx issue-fix reviewer-plan --repo-path <repo> --repo <owner/repo> --base-ref <base-ref> --execute --format json",
                "purpose": "Rank explainable reviewer candidates from CODEOWNERS and changed-path/module history.",
                "write_boundary": "approved local repo read only; no external review request",
            },
            {
                "command": "loopx issue-fix reviewer-request --url <github-pr-url> --repo-path <repo> --base-ref <base-ref> [--notification-sinks-json <local-private.json>] --execute --format json",
                "purpose": "Under reviewer-notification authority, exclude the live PR author, establish canonical GitHub coverage, and optionally deliver the same reviewer through verified project-dedicated sinks.",
                "write_boundary": "one formal GitHub review request, or one reviewer-tagging comment only after confirmed permission denial; optional configured secondary sends consume local-private identity/destination data without copying it; no arbitrary comment, push, merge, or publish",
            },
            {
                "command": "loopx issue-fix reviewer-notification-drain --goal-id <goal-id> --project <project> --execute --format json",
                "purpose": "Drain one bounded review-required state bucket after live PR verification while preserving one PR per group message.",
                "write_boundary": "verified configured secondary sends plus compact receipt or stale-queue state writeback; no per-PR continuous monitor, arbitrary comment, push, merge, or publish",
            },
            {
                "command": "loopx issue-fix pr-lifecycle --url <github-pr-url> --goal-id <goal-id> --format json",
                "purpose": "Project public PR lifecycle state into a successor, monitor continuation, user gate, or no-follow-up transition.",
                "write_boundary": "writes compact project-local domain state when goal or ledger context is provided; no external comment, PR creation, merge, raw logs, or body/comment capture",
            },
            {
                "command": "loopx issue-fix outcome --goal-id <goal-id> --repo <owner/repo> --issue-ref <issue-ref> --pr-ref <pr-ref> --format json",
                "purpose": "Compose one operator-facing issue status/output card from existing feasibility, repository context, optional delivery evidence, and PR lifecycle state.",
                "write_boundary": "read-only derived projection; writes no source ledger and performs no external action",
            },
            {
                "command": "loopx issue-fix acceptance-fixture --format json",
                "purpose": "Prove the failure-before/fix-after acceptance loop on a deterministic fixture.",
                "write_boundary": "temporary local fixture only",
            },
            {
                "command": "loopx issue-fix repo-branch-fixture --format json",
                "purpose": "Exercise the same loop through a temporary git issue branch.",
                "write_boundary": "temporary local git fixture only",
            },
            {
                "command": "loopx issue-fix caller-repo-branch --repo-path <repo> --validation-command <cmd> --execute --format json",
                "purpose": "Create or claim a caller-approved local issue branch and run caller-declared validation.",
                "write_boundary": "approved local repo only; no external comment, PR creation, merge, or publish",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "github_public_channel_probe_packet_v0",
                "module": "loopx.capabilities.issue_fix.github_public",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "github_public_reply_monitor_packet_v0",
                "module": "loopx.capabilities.issue_fix.github_public",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "github_issue_metadata_preview_v0",
                "module": "loopx.capabilities.issue_fix.metadata_preview",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_issue_fix_metadata_preview_packet_v0",
                "module": "loopx.capabilities.issue_fix.intake_surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_issue_fix_intake_packet_v0",
                "module": "loopx.capabilities.issue_fix.intake_surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "issue_fix_intake_v0",
                "module": "loopx.capabilities.issue_fix.intake_surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "issue_fix_workflow_plan_packet_v0",
                "module": "loopx.capabilities.issue_fix.workflow_plan",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md",
            },
            {
                "schema_version": "issue_fix_repository_context_v0",
                "module": "loopx.capabilities.issue_fix.repository_context",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md",
            },
            {
                "schema_version": "issue_fix_feasibility_v0",
                "module": "loopx.capabilities.issue_fix.feasibility",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md",
            },
            {
                "schema_version": "issue_fix_discovered_issue_promotion_v0",
                "module": "loopx.capabilities.issue_fix.discovered_issue_promotion",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-discovered-issue-promotion-v0.md",
            },
            {
                "schema_version": "issue_fix_pr_lifecycle_monitor_v0",
                "module": "loopx.capabilities.issue_fix.pr_lifecycle",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md",
            },
            {
                "schema_version": "issue_fix_maintainer_correction_input_v0",
                "module": "loopx.capabilities.issue_fix.pr_lifecycle",
                "doc": "docs/capabilities/issue-fix/README.md",
            },
            {
                "schema_version": "issue_fix_reviewer_recommendation_v0",
                "module": "loopx.capabilities.issue_fix.reviewer_recommendation",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-recommendation-v0.md",
            },
            {
                "schema_version": "issue_fix_reviewer_request_v0",
                "module": "loopx.capabilities.issue_fix.reviewer_request",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-request-v0.md",
            },
            {
                "schema_version": "issue_fix_reviewer_notification_sinks_result_v0",
                "module": "loopx.capabilities.issue_fix.reviewer_notification",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-notification-sinks-v0.md",
            },
            {
                "schema_version": "issue_fix_reviewer_notification_drain_v0",
                "module": "loopx.capabilities.issue_fix.reviewer_notification_drain",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-notification-sinks-v0.md",
            },
            {
                "schema_version": "issue_fix_outcome_projection_v0",
                "module": "loopx.capabilities.issue_fix.outcome_projection",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md",
            },
            {
                "schema_version": "issue_fix_validated_outcome_memory_writeback_v0",
                "module": "loopx.capabilities.issue_fix.repository_memory_provider",
                "doc": "docs/capabilities/issue-fix/README.md",
            },
            {
                "schema_version": "issue_fix_acceptance_loop_v0",
                "module": "loopx.capabilities.issue_fix.acceptance_loop",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            },
            {
                "schema_version": "issue_fix_validated_fix_artifact_v0",
                "module": "loopx.capabilities.issue_fix.acceptance_loop",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            },
            {
                "schema_version": "issue_fix_caller_repo_branch_packet_v0",
                "module": "loopx.capabilities.issue_fix.acceptance_loop",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/value-connectors-github-public-probe-smoke.py",
            "python3 examples/issue-fix-workflow-plan-smoke.py",
            "python3 examples/issue-fix-repository-context-smoke.py",
            "python3 examples/issue-fix-feasibility-smoke.py",
            "python3 examples/issue-fix-discovered-issue-promotion-smoke.py",
            "python3 examples/issue-fix-pr-lifecycle-smoke.py",
            "python3 examples/issue-fix-maintainer-correction-smoke.py",
            "python3 examples/issue-fix-outcome-projection-smoke.py",
            "python3 examples/issue-fix-validated-memory-writeback-smoke.py",
            "python3 examples/issue-fix-reviewer-recommendation-smoke.py",
            "python3 examples/issue-fix-reviewer-request-smoke.py",
            "python3 examples/issue-fix-json-input-boundary-smoke.py",
            "python3 examples/issue-fix-reviewer-notification-sink-smoke.py",
            "python3 examples/content-ops-issue-fix-metadata-preview-smoke.py",
            "python3 examples/content-ops-issue-fix-intake-smoke.py",
            "python3 examples/issue-fix-acceptance-loop-smoke.py",
        ],
        "docs": [
            "docs/capabilities/issue-fix/README.md",
            "docs/reference/protocols/value-connector-plan-v0.md",
            "docs/capabilities/issue-fix/openviking-pilot-handoff.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-discovered-issue-promotion-v0.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-recommendation-v0.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-request-v0.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-notification-sinks-v0.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            "docs/reference/protocols/content-ops-surface-v0.md",
            "docs/reference/protocols/issue-fix-acceptance-loop-v0.md",
        ],
        "boundaries": [
            "GitHub issue body, comments, timeline, and raw provider payloads are gated and not copied.",
            "Caller repo mode reads and writes only the explicitly approved local git repo.",
            "Arbitrary external comments, PR creation, merge, publish, and destructive git remain separately gated; reviewer-request may use one reviewer-tagging comment only as a verified permission-denial fallback under the same narrow authority.",
            "Secondary reviewer sinks require an explicit project-dedicated identity and local-private destination/member mapping; no credential, raw roster, provider response, or private identifier enters public state.",
        ],
        "next_real_step": (
            "Exercise route selection and continuation on a public issue-fix pilot, "
            "while keeping external PR/comment actions explicit."
        ),
    },
    {
        "id": "semantic-preference",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Optional semantic preference hook",
        "status": "active-preview",
        "real_world_anchor": "provider-neutral preference recall before domain work",
        "user_value": (
            "Let any LoopX module recall provider-owned semantic preferences and "
            "record a compact application receipt without creating a second memory ledger."
        ),
        "entry_command": "loopx semantic-preference recall --config <ignored-config.json> --surface <module.surface> --format json",
        "commands": [
            {
                "command": "loopx semantic-preference doctor --config <ignored-config.json> --execute --format json",
                "purpose": "Check a configured provider entry point and optional read-only probe, then return explicit install/config guidance when unavailable.",
                "write_boundary": "read-only discovery; never installs packages, starts services, changes config, or writes credentials",
            },
            {
                "command": "loopx semantic-preference recall --config <ignored-config.json> --surface <module.surface> --execute --format json",
                "purpose": "Send one bounded recall request to a configured command_json_v0 provider.",
                "write_boundary": "provider read only; LoopX does not persist recalled semantic content",
            },
            {
                "command": "loopx semantic-preference receipt --surface <module.surface> --application-id <id> --outcome applied --format json",
                "purpose": "Build a compact receipt with hashed preference references for existing evidence/state writeback.",
                "write_boundary": "stateless output only; no provider, file, or external write",
            },
            {
                "command": "loopx semantic-preference maintenance-receipt --trigger explicit_feedback --outcome verified --corpus-id <id> --format json",
                "purpose": "Build a compact receipt after a provider-owned corpus maintenance decision and readback closure.",
                "write_boundary": "stateless output only; scope references are hashed and semantic content is excluded",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "module": "loopx.capabilities.semantic_preference.contract",
                "doc": "docs/capabilities/semantic-preference/README.md",
            },
            {
                "schema_version": "semantic_preference_provider_request_v0",
                "module": "loopx.capabilities.semantic_preference.contract",
                "doc": "docs/capabilities/semantic-preference/README.md",
            },
            {
                "schema_version": "semantic_preference_provider_doctor_v0",
                "module": "loopx.capabilities.semantic_preference.contract",
                "doc": "docs/capabilities/semantic-preference/README.md",
            },
            {
                "schema_version": "semantic_preference_application_receipt_v0",
                "module": "loopx.capabilities.semantic_preference.contract",
                "doc": "docs/capabilities/semantic-preference/README.md",
            },
            {
                "schema_version": "semantic_preference_maintenance_guidance_v0",
                "module": "loopx.capabilities.semantic_preference.contract",
                "doc": "docs/capabilities/semantic-preference/README.md",
            },
            {
                "schema_version": "semantic_preference_maintenance_receipt_v0",
                "module": "loopx.capabilities.semantic_preference.contract",
                "doc": "docs/capabilities/semantic-preference/README.md",
            },
        ],
        "smokes": [
            "python3 examples/semantic-preference-hook-smoke.py",
            "python3 examples/openviking-extension-runtime-smoke.py",
        ],
        "docs": ["docs/capabilities/semantic-preference/README.md"],
        "boundaries": [
            "The hook is disabled until an enabled local-private config is supplied.",
            "Surface ids and queries are domain-owned configuration; the runtime has no issue-fix branch.",
            "LoopX does not persist recalled semantic content, receipts, provider commands, config paths, or raw errors.",
            "Provider failures follow explicit fail-open/fail-closed policy and do not become user gates automatically.",
            "Provider setup remains guidance-only: package, service, config, and credential writes require an explicit operator action.",
        ],
        "next_real_step": (
            "Keep the hook opt-in until a second domain module proves useful recall and existing-state receipt writeback."
        ),
    },
    {
        "id": "reward-memory",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Reward-memory candidate, recall, and application foundation",
        "status": "active-preview",
        "real_world_anchor": (
            "typed feedback memory, provider-owned corpus health, and pilot/meta delegation"
        ),
        "user_value": (
            "Keep run judgments, policies, preferences, reusable experience, and "
            "working context distinct; derive policy content from verified contributor "
            "signals without inventing or widening authority."
        ),
        "entry_command": "loopx reward-memory architecture --format json",
        "commands": [
            {
                "command": "loopx reward-memory architecture --format json",
                "purpose": "Render the five-class Stage-0 architecture, lifecycle, precedence, and staged ownership contract.",
                "write_boundary": "stateless contract output only; no memory, provider, state, or external write",
            },
            {
                "command": "loopx reward-memory route-check --case pr-3237 --format json",
                "purpose": "Exercise deterministic safety guards for the public PR #3237 regression; this fixture is not the live reasoning router.",
                "write_boundary": "stateless public guard fixture only; no issue body, memory content, repository, provider, or external write",
            },
            {
                "command": "loopx reward-memory corpus-registry --format json",
                "purpose": "Render the Stage-1 corpus ownership, authority, scope, freshness, lifecycle, and maintenance registry.",
                "write_boundary": "stateless read model only; provider content stays at its source of truth",
            },
            {
                "command": "loopx reward-memory health-check --case wrong-project --format json",
                "purpose": "Exercise deterministic project, surface, freshness, index, retrieval, readback, and application health states.",
                "write_boundary": "public fixture classification only; no memory, index, receipt, state, or external write",
            },
            {
                "command": "loopx reward-memory candidate-review --case issue-fix-verified-contributor --decision accept --format json",
                "purpose": "Exercise the Stage-2 shared candidate/review seam through the mapping-only Issue Fix adapter.",
                "write_boundary": "stateless decision output only; persistence stays with the declared corpus owner and this command performs no provider or external write",
            },
            {
                "command": "loopx reward-memory evaluate --format json",
                "purpose": "Run the Stage-4 provider-neutral core-contract suite and compact release gate over the real recall/application seam.",
                "write_boundary": "bounded local fixture reads only; no provider, memory, repository, state, model API, or external write",
            },
            {
                "command": "loopx reward-memory dogfood-evaluate --input <compact-observations.json> --format json",
                "purpose": "Bind verified Issue Fix and LoopX module outcomes to compact hit, miss, refute, cost, intervention, and bot-feedback receipts after the Stage-4 gate.",
                "write_boundary": "reads compact receipts only; no raw provider content, memory write, operator write, automatic recall, or external write",
            },
            {
                "command": "loopx reward-memory operator-control --input <reviewed-record.json> --action edit --control-ref <ref> --reasoning-summary <summary> --edited-content-summary <summary> --format json",
                "purpose": "Prepare an authority-matched edit or retirement decision for a reviewed active record.",
                "write_boundary": "returns a control decision and next-step receipt only; the declared corpus owner must perform and exactly read back any provider write",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "reward_memory_architecture_v0",
                "module": "loopx.capabilities.reward_memory.architecture",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_pilot_meta_route_v0",
                "module": "loopx.capabilities.reward_memory.architecture",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_corpus_registry_v0",
                "module": "loopx.capabilities.reward_memory.registry",
                "doc": "docs/reference/protocols/reward-memory-corpus-registry-v0.md",
            },
            {
                "schema_version": "reward_memory_corpus_health_v0",
                "module": "loopx.capabilities.reward_memory.health",
                "doc": "docs/reference/protocols/reward-memory-corpus-registry-v0.md",
            },
            {
                "schema_version": "reward_memory_candidate_v0",
                "module": "loopx.capabilities.reward_memory.candidate_review",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_candidate_review_v0",
                "module": "loopx.capabilities.reward_memory.candidate_review",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "issue_fix_reward_memory_candidate_adapter_v0",
                "module": "loopx.capabilities.reward_memory.candidate_review",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "scoped_feedback_reward_memory_event_v0",
                "module": "loopx.capabilities.reward_memory.scoped_feedback",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": (
                    "scoped_feedback_reward_memory_candidate_adapter_v0"
                ),
                "module": "loopx.capabilities.reward_memory.scoped_feedback",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_active_record_v0",
                "module": "loopx.capabilities.reward_memory.application",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_recall_request_v0",
                "module": "loopx.capabilities.reward_memory.application",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_recall_v0",
                "module": "loopx.capabilities.reward_memory.application",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_application_receipt_v0",
                "module": "loopx.capabilities.reward_memory.application",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "issue_fix_reward_memory_application_v0",
                "module": "loopx.capabilities.issue_fix.reward_memory",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": ("semantic_preference_reward_memory_application_v0"),
                "module": "loopx.capabilities.semantic_preference.reward_memory",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_evaluation_v0",
                "module": "loopx.capabilities.reward_memory.evaluation",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_release_gate_v0",
                "module": "loopx.capabilities.reward_memory.evaluation",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_dogfood_receipt_v0",
                "module": "loopx.capabilities.reward_memory.dogfood",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_dogfood_batch_v0",
                "module": "loopx.capabilities.reward_memory.dogfood",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
            {
                "schema_version": "reward_memory_operator_control_v0",
                "module": "loopx.capabilities.reward_memory.dogfood",
                "doc": "docs/reference/protocols/reward-memory-architecture-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/reward-memory-architecture-smoke.py",
            "python3 examples/reward-memory-corpus-registry-smoke.py",
            "python3 examples/reward-memory-candidate-review-smoke.py",
            "python3 examples/reward-memory-recall-application-smoke.py",
            "python3 examples/reward-memory-evaluation-smoke.py",
            "python3 examples/reward-memory-dogfood-smoke.py",
        ],
        "docs": [
            "docs/reference/protocols/reward-memory-architecture-v0.md",
            "docs/reference/protocols/reward-memory-corpus-registry-v0.md",
        ],
        "boundaries": [
            "Run-bound reward is outcome evidence; future influence requires compact candidate derivation and an activation policy.",
            "Verified owner or core-contributor feedback may derive hard-policy content only inside independently verified repository and action authority scope.",
            "Deterministic code enforces authority, scope, privacy, freshness, verification, and conflict guards; model reasoning owns interpretation and trade-offs inside those guards.",
            "Retrieval without current-artifact verification has zero patch authority.",
            "OpenViking cases are evaluation fixtures, provider soul text is not action authority, and session working memory remains continuation context.",
            "LoopX fresh execution context already exists and Stage 2 must reuse it rather than add another context system.",
            "Corpus presence, index presence, retrieval success, readback, and applied receipts are distinct health states.",
            "Project or surface mismatch fails closed before provider availability can influence application.",
            "Stages 0-1 write no corpus, candidate, provider memory, evaluation result, or external artifact.",
            "Stage 2 returns inspectable candidate/review decisions only; accept or retire still requires the caller to use the corpus owner's declared write authority and verify readback.",
            "Issue Fix and generic scoped-feedback adapters map compact domain evidence into the shared core and own no parallel lifecycle, store, scheduler, or recall path.",
            "Stage 3 recalls only after an explicit exact-corpus, module-surface request and a matching read-authority checkpoint; it never scans every corpus automatically.",
            "Function-boundary recall permits one caller-owned query; bounded agentic search permits at most three caller/model-owned queries and contains no semantic router.",
            "Provider and application failures preserve the base output, emit compact receipts or setup hints, and never become user gates automatically.",
            "Private corpus summaries stay transient in-process; public packets retain opaque references and compact lineage only.",
            "Stage 4 proves bounded core-contract invariants only; its fixture pass does not claim semantic uplift or authorize production rollout.",
            "Stage 5 receipts are derived from Stage-3 application receipts and verified module outcomes; hit or refute requires exact provider readback plus current-artifact verification.",
            "Stage 5 trial readiness requires Issue Fix, two distinct LoopX domains, hit/miss/refute coverage, and authority-matched edit/retire controls; it still does not authorize production rollout.",
        ],
        "next_real_step": (
            "Feed one corpus-owner-approved, exactly read-back record through the "
            "bounded OpenViking Issue Fix pilot and write back compact bot feedback "
            "without widening the Stage-5 trial-only claim."
        ),
    },
    {
        "id": "periodic-report",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Provider-neutral periodic and progress report runs",
        "status": "active-preview",
        "real_world_anchor": "scheduled and milestone project reports with verified archive and delivery",
        "user_value": (
            "Give projects one deterministic trigger, report run, receipt, "
            "partial-state, and retry contract without hard-coding a domain, "
            "provider, cadence, or destination."
        ),
        "entry_command": "loopx periodic-report evaluate-trigger --request-json <request.json> --format json",
        "commands": [
            {
                "command": "loopx periodic-report evaluate-trigger --request-json <request.json> --format json",
                "purpose": "Select, coalesce, cool down, and deduplicate cadence or material progress triggers without provider effects.",
                "write_boundary": "local trigger decision only; no source read, schedule mutation, rendering, archive write, message delivery, or provider write",
            },
            {
                "command": "loopx periodic-report compose-run --request-json <request.json> --format json",
                "purpose": "Normalize one typed report attempt and derive stable run/sink idempotency, state, and retry evidence.",
                "write_boundary": "local contract output only; no source read, rendering, archive write, message delivery, or provider write",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "periodic_report_trigger_decision_v0",
                "module": "loopx.capabilities.periodic_report.triggers",
                "doc": "docs/reference/protocols/periodic-report-v0.md",
            },
            {
                "schema_version": "periodic_report_v0",
                "module": "loopx.capabilities.periodic_report.core",
                "doc": "docs/reference/protocols/periodic-report-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/periodic-report-smoke.py",
            "python3 examples/periodic-report-adapters-smoke.py",
        ],
        "docs": [
            "docs/capabilities/periodic-report/README.md",
            "docs/reference/protocols/periodic-report-v0.md",
        ],
        "boundaries": [
            "The core owns material trigger classification, coalescing, cooldown/deduplication, period/profile binding, deterministic identity, receipts, run state, and retry projection.",
            "Profiles own schedule calculation, enabled trigger kinds, minimum interval, timezone, sections, audience, and project policy.",
            "Adapters own domain source collection; renderers and sinks own all provider effects and verified readback.",
            "Raw content, messages, logs, transcripts, credentials, secrets, and private paths are rejected.",
        ],
        "next_real_step": (
            "Prove one project-owned profile and exact delivery/archive retry readback "
            "without adding project semantics or schedule policy to the core."
        ),
    },
    {
        "id": "content-ops",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Creator/content operations loop",
        "status": "active-preview",
        "real_world_anchor": "self-media operations and public/private source intake",
        "user_value": (
            "Collect public handles and approved private-connector metadata into "
            "reviewable source, angle, draft, feedback, and publish-gate packets."
        ),
        "entry_command": "loopx content-ops aggregate-packets --format json",
        "commands": [
            {
                "command": "loopx content-ops exploration-plan --format json",
                "purpose": "Plan source lanes before reading connector material.",
                "write_boundary": "fixture-only; no source read",
            },
            {
                "command": "loopx content-ops observe-public-handle --url <public-url> --source-item-id <id> --format json",
                "purpose": "Create a metadata-only public source item.",
                "write_boundary": "public HEAD-only metadata read unless --no-fetch is used",
            },
            {
                "command": "loopx content-ops project-private-connector-gate --format json",
                "purpose": "Represent a private connector as an owner gate before metadata intake.",
                "write_boundary": "no private connector read",
            },
            {
                "command": "loopx content-ops project-chatview-report --format json",
                "purpose": "Summarize approved ChatView connector counts without raw chat content.",
                "write_boundary": "compact counts only; no raw message text",
            },
            {
                "command": "loopx content-ops aggregate-packets --format json",
                "purpose": "Merge public source packets and private owner gates into a control-plane surface.",
                "write_boundary": "local packet aggregation only",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "content_ops_surface_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "source_item_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_private_connector_owner_gate_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_packet_aggregation_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_chatview_connector_report_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_social_browser_x_provider_v0",
                "module": "loopx.capabilities.content_ops.social_browser_x",
                "doc": "docs/capabilities/content-ops/README.md",
            },
        ],
        "smokes": [
            "python3 examples/content-ops-exploration-plan-smoke.py",
            "python3 examples/content-ops-public-handle-observation-smoke.py",
            "python3 examples/content-ops-private-connector-gate-smoke.py",
            "python3 examples/content-ops-chatview-report-smoke.py",
            "python3 examples/content-ops-packet-aggregation-smoke.py",
        ],
        "docs": [
            "docs/capabilities/content-ops/README.md",
            "docs/reference/protocols/content-ops-surface-v0.md",
        ],
        "boundaries": [
            "Private connectors enter as owner gates or compact approved counts first.",
            "Raw chats, transcripts, auth material, logs, and local paths are not copied into public packets.",
            "Publish remains blocked until an explicit user decision.",
        ],
        "next_real_step": (
            "Turn the aggregated surface into a small review/feed UI where a user "
            "can score source items, angles, and drafts."
        ),
    },
    {
        "id": "value-connectors",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Value connector compatibility facade",
        "status": "compatibility-facade",
        "real_world_anchor": "external channel intake for revenue, cost, demand, and connector reuse",
        "user_value": (
            "Keep existing connector commands and packet schemas stable while "
            "each profile moves to the outcome capability that serves callers."
        ),
        "entry_command": "loopx value-connectors source-map --format json",
        "commands": [
            {
                "command": "loopx value-connectors install-check --format json",
                "purpose": "Show connector starter install/use commands and local dependency status.",
                "write_boundary": "local check only; no external read or write",
            },
            {
                "command": "loopx value-connectors source-map --format json",
                "purpose": "Give agents a read-first source-map packet for all currently surfaced connector profiles.",
                "write_boundary": "packet only; no external read, write, account setup, or raw payload capture",
            },
            {
                "command": "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --format json",
                "purpose": "Validate a public GitHub channel URL and build a connector call packet.",
                "write_boundary": "no network read unless --fetch-metadata is provided",
                "compatibility_for": "issue-fix",
            },
            {
                "command": "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --fetch-metadata --format json",
                "purpose": "Fetch allowlisted public GitHub metadata without body/comment/timeline content.",
                "write_boundary": "public metadata read only; no comments, PRs, account changes, or writes",
                "compatibility_for": "issue-fix",
            },
            {
                "command": "loopx value-connectors github-reply-monitor --issue-url <github-issue-or-pr-url> --after-comment-url <github-issue-comment-url> --fetch-metadata --format json",
                "purpose": "Detect public maintainer replies after a LoopX comment without capturing comment bodies.",
                "write_boundary": "public comment metadata read only; no comment bodies, thread bump, or external write",
                "compatibility_for": "issue-fix",
            },
            {
                "command": "loopx value-connectors plan --connector-id <id> ... --format json",
                "purpose": "Plan gated account setup, external replies, sends, or future connector calls.",
                "write_boundary": "plan-only; external writes and account setup require exact approval",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "value_connector_plan_v0",
                "module": "loopx.capabilities.value_connectors.planner",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "connector_call_intent_v0",
                "module": "loopx.capabilities.value_connectors.planner",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "connector_approval_gate_v0",
                "module": "loopx.capabilities.value_connectors.planner",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "value_connector_install_check_packet_v0",
                "module": "loopx.capabilities.value_connectors.install_check",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "value_connector_source_map_packet_v0",
                "module": "loopx.capabilities.value_connectors.source_map",
                "doc": "docs/capabilities/value-connectors/agent-reach-ops-source-map.md",
            },
        ],
        "smokes": [
            "python3 examples/value-connectors-github-public-probe-smoke.py",
        ],
        "docs": [
            "docs/capabilities/value-connectors/README.md",
            "docs/reference/protocols/value-connector-plan-v0.md",
        ],
        "boundaries": [
            "The GitHub starter copies allowlisted public metadata only, not bodies, comments, timelines, raw provider payloads, auth material, or local paths.",
            "The reply monitor reads or accepts comment metadata only: author, association, timestamps, and URL; it never bumps a thread.",
            "Account signup, email sends, community posts, public replies, private reads, paid services, and production actions remain gated exact-call actions.",
            "Every connector call must include a money, cost, demand, or capability metric plus a kill condition.",
        ],
        "next_real_step": (
            "Move one mapped profile at a time to its declared outcome capability, "
            "keeping this CLI and its packet schemas stable until callers migrate."
        ),
    },
    {
        "id": "explore",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Explore evidence topology",
        "status": "active-preview",
        "real_world_anchor": (
            "goal-scoped questions, hypotheses, experiments, findings, and result projections"
        ),
        "user_value": (
            "Keep exploration outcomes queryable and attributable instead of leaving them "
            "only in chat or a presentation sink."
        ),
        "entry_command": "loopx explore summary --goal-id <goal-id> --format json",
        "commands": [
            {
                "command": "loopx explore finding --goal-id <goal-id> --title <finding> --evidence-ref <ref> --format json",
                "purpose": "Append one public-safe, attributable finding to the canonical result log.",
                "write_boundary": "goal-scoped local result log only; no sink or external write",
            },
            {
                "command": "loopx explore summary --goal-id <goal-id> --format json",
                "purpose": "Fold canonical result events into the bounded operator projection.",
                "write_boundary": "read-only projection over the goal result log",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "loopx_explore_result_event_v0",
                "module": "loopx.capabilities.explore.result_log",
                "doc": "docs/capabilities/explore/README.md",
            },
            {
                "schema_version": "loopx_explore_result_projection_v0",
                "module": "loopx.capabilities.explore.result_log",
                "doc": "docs/capabilities/explore/README.md",
            },
        ],
        "smokes": [
            "python3 examples/explore-result-layer-smoke.py",
            "python3 examples/explore-todo-result-node-linkage-smoke.py",
        ],
        "docs": ["docs/capabilities/explore/README.md"],
        "boundaries": [
            "Canonical result events are the source of truth; Lark and other sinks render projections only.",
            "Evidence refs must be public-safe relative refs or opaque ids, never credentials, raw private payloads, or local absolute paths.",
        ],
        "next_real_step": (
            "Register findings and terminal outcomes through the result log before refreshing any display sink."
        ),
    },
    {
        "id": "auto-research",
        "origin": "builtin",
        "visibility": "public",
        "provider_id": "loopx-core",
        "title": "Decentralized auto-research preset",
        "status": "experimental",
        "real_world_anchor": (
            "one-question research contracts with role-scoped workers, evidence packets, and a visible frontier"
        ),
        "user_value": (
            "Launch a thin multi-agent research recipe while reusing LoopX todo, quota, "
            "history, evidence, and continuation contracts."
        ),
        "entry_command": "loopx auto-research <open-question>",
        "commands": [
            {
                "command": "loopx auto-research <open-question>",
                "purpose": "Render the fixed one-question contract, bounded plan, and exact start command.",
                "write_boundary": "stateless contract output only",
            },
            {
                "command": "loopx auto-research start <open-question> --execute",
                "purpose": "Create an isolated goal and launch visible role-scoped workers through the shared multi-agent runtime.",
                "write_boundary": "local goal, workspace, and visible launcher state; no publication, benchmark submission, or protected external action",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "auto_research_user_contract_v0",
                "module": "loopx.capabilities.auto_research.user_contract",
                "doc": "docs/guides/auto-research-command-path.md",
            },
            {
                "schema_version": "decentralized_auto_research_projection_v0",
                "module": "loopx.capabilities.auto_research.research_state",
                "doc": "docs/reference/protocols/decentralized-auto-research-state-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/auto-research-user-contract-entry-smoke.py",
            "python3 examples/auto-research-worker-turn-smoke.py",
        ],
        "docs": [
            "docs/guides/auto-research-command-path.md",
            "docs/product/decentralized-auto-research-showcase.md",
        ],
        "boundaries": [
            "The preset reuses shared control-plane and multi-agent contracts; it is not a second scheduler or runner.",
            "Completion and uplift require role-authored evidence and projected outcomes; the launcher does not manufacture research results.",
        ],
        "next_real_step": (
            "Use the one-question entrypoint for bounded research and preserve every promoted or rejected outcome in canonical evidence."
        ),
    },
)

# Preserve the original import surface while routing all reads through the registry.
CAPABILITIES = BUILTIN_CAPABILITIES


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "origin": record["origin"],
        "visibility": record["visibility"],
        "provider_id": record["provider_id"],
        "provider_state": record["provider_state"],
        "real_world_anchor": record["real_world_anchor"],
        "entry_command": record["entry_command"],
        "implemented_protocol_count": len(record.get("implemented_protocols") or []),
        "implementation_provider_count": len(
            record.get("implementation_providers") or []
        ),
        "smoke_count": len(record.get("smokes") or []),
        "next_real_step": record["next_real_step"],
    }


def build_capability_registry(
    extension_manifest_paths: Iterable[str | Path] = (),
    *,
    extension_state_file: str | Path | None = None,
) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register_provider(
        {
            "id": "loopx-core",
            "origin": "builtin",
            "declared": True,
            "installed": True,
            "enabled": True,
            "ready": True,
        }
    )
    for record in BUILTIN_CAPABILITIES:
        registry.register_capability(record)
    for manifest in extension_catalog_entries(
        extension_manifest_paths,
        state_file=extension_state_file,
    ):
        registry.register_provider(manifest["provider"])
        for record in manifest["capabilities"]:
            registry.register_capability(record)
        for implementation in manifest["implementations"]:
            registry.register_implementation(implementation)
    return registry


def capability_ids(
    extension_manifest_paths: Iterable[str | Path] = (),
    *,
    include_internal: bool = False,
    extension_state_file: str | Path | None = None,
) -> list[str]:
    return build_capability_registry(
        extension_manifest_paths,
        extension_state_file=extension_state_file,
    ).capability_ids(
        include_internal=include_internal
    )


def get_capability(
    capability_id: str,
    extension_manifest_paths: Iterable[str | Path] = (),
    *,
    include_internal: bool = False,
    extension_state_file: str | Path | None = None,
) -> dict[str, Any]:
    return build_capability_registry(
        extension_manifest_paths,
        extension_state_file=extension_state_file,
    ).get(
        capability_id,
        include_internal=include_internal,
    )


def build_capability_catalog_packet(
    extension_manifest_paths: Iterable[str | Path] = (),
    *,
    extension_state_file: str | Path | None = None,
) -> dict[str, Any]:
    registry = build_capability_registry(
        extension_manifest_paths,
        extension_state_file=extension_state_file,
    )
    return {
        "ok": True,
        "schema_version": CAPABILITY_CATALOG_SCHEMA_VERSION,
        "capabilities": [_summary(record) for record in registry.records()],
        "providers": registry.providers(),
    }


def build_capability_detail_packet(
    capability_id: str,
    extension_manifest_paths: Iterable[str | Path] = (),
    *,
    extension_state_file: str | Path | None = None,
) -> dict[str, Any]:
    record = get_capability(
        capability_id,
        extension_manifest_paths,
        extension_state_file=extension_state_file,
    )
    return {
        "ok": True,
        "schema_version": CAPABILITY_DETAIL_SCHEMA_VERSION,
        "capability": record,
    }


def render_capability_catalog_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LoopX Capabilities", ""]
    for item in payload.get("capabilities") or []:
        if not isinstance(item, Mapping):
            continue
        lines.extend(
            [
                f"## {item.get('id')}: {item.get('title')}",
                "",
                f"- status: `{item.get('status')}`",
                f"- provider: `{item.get('provider_id')}` ({item.get('origin')})",
                f"- provider_state: `{item.get('provider_state')}`",
                f"- visibility: `{item.get('visibility')}`",
                f"- anchor: {item.get('real_world_anchor')}",
                f"- entry: `{item.get('entry_command')}`",
                f"- implemented_protocol_count: `{item.get('implemented_protocol_count')}`",
                f"- implementation_provider_count: `{item.get('implementation_provider_count')}`",
                f"- smoke_count: `{item.get('smoke_count')}`",
                f"- next: {item.get('next_real_step')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_capability_detail_markdown(payload: dict[str, Any]) -> str:
    record = payload.get("capability")
    if not isinstance(record, Mapping):
        return "# LoopX Capability\n\nNo capability found.\n"
    lines = [
        f"# LoopX Capability: {record.get('title')}",
        "",
        f"- id: `{record.get('id')}`",
        f"- status: `{record.get('status')}`",
        f"- provider: `{record.get('provider_id')}` ({record.get('origin')})",
        f"- provider_state: `{record.get('provider_state')}`",
        f"- visibility: `{record.get('visibility')}`",
        f"- anchor: {record.get('real_world_anchor')}",
        f"- value: {record.get('user_value')}",
        f"- entry: `{record.get('entry_command')}`",
        "",
        "## Commands",
        "",
    ]
    for item in record.get("commands") or []:
        if not isinstance(item, Mapping):
            continue
        lines.extend(
            [
                f"- `{item.get('command')}`",
                f"  - purpose: {item.get('purpose')}",
                f"  - boundary: {item.get('write_boundary')}",
            ]
        )
    lines.extend(["", "## Implemented Protocols", ""])
    for item in record.get("implemented_protocols") or []:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"- `{item.get('schema_version')}` in `{item.get('module')}` "
            f"([{item.get('doc')}]({item.get('doc')}))"
        )
    lines.extend(["", "## Smokes", ""])
    for smoke in record.get("smokes") or []:
        lines.append(f"- `{smoke}`")
    lines.extend(["", "## Boundaries", ""])
    for boundary in record.get("boundaries") or []:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Next Real Step", "", str(record.get("next_real_step"))])
    return "\n".join(lines).rstrip() + "\n"
