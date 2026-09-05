"""Provider-neutral architecture projection for Decision Context."""

from __future__ import annotations

from .assembler import (
    DECISION_CONTEXT_ASSEMBLY_SCHEMA_VERSION,
    DECISION_CURSOR_CHECKPOINT_SCHEMA_VERSION,
    DECISION_CONTEXT_EPHEMERAL_RECALL_SCHEMA_VERSION,
    DECISION_SEMANTIC_REBASE_RECEIPT_SCHEMA_VERSION,
)
from .packets import (
    DECISION_EVIDENCE_PACKET_SCHEMA_VERSION,
    DECISION_OUTCOME_RECEIPT_SCHEMA_VERSION,
    DECISION_PROPOSAL_SCHEMA_VERSION,
    DECISION_REVIEW_RECEIPT_SCHEMA_VERSION,
)
from .cursor_commit import DECISION_CURSOR_COMMIT_RECEIPT_SCHEMA_VERSION
from .sources import (
    DECISION_SOURCE_MANIFEST_SCHEMA_VERSION,
    DECISION_SOURCE_SCAN_RECEIPT_SCHEMA_VERSION,
)

DECISION_CONTEXT_ARCHITECTURE_SCHEMA_VERSION = "decision_context_architecture_v0"


def build_decision_context_architecture_packet() -> dict[str, object]:
    """Render the default-off Stage-0 capability contract."""

    return {
        "schema_version": DECISION_CONTEXT_ARCHITECTURE_SCHEMA_VERSION,
        "status": "experimental",
        "capability": {
            "capability_id": "decision_context",
            "scope": "goal",
            "default_enabled": False,
            "creates_authority": False,
            "mutates_core_state": False,
        },
        "packet_schemas": [
            DECISION_EVIDENCE_PACKET_SCHEMA_VERSION,
            DECISION_PROPOSAL_SCHEMA_VERSION,
            DECISION_REVIEW_RECEIPT_SCHEMA_VERSION,
            DECISION_OUTCOME_RECEIPT_SCHEMA_VERSION,
        ],
        "source_schemas": [
            DECISION_SOURCE_MANIFEST_SCHEMA_VERSION,
            DECISION_SOURCE_SCAN_RECEIPT_SCHEMA_VERSION,
        ],
        "assembly_schemas": [
            DECISION_CONTEXT_ASSEMBLY_SCHEMA_VERSION,
            DECISION_SEMANTIC_REBASE_RECEIPT_SCHEMA_VERSION,
            DECISION_CURSOR_CHECKPOINT_SCHEMA_VERSION,
            DECISION_CURSOR_COMMIT_RECEIPT_SCHEMA_VERSION,
        ],
        "local_private_transient_schemas": [
            DECISION_CONTEXT_EPHEMERAL_RECALL_SCHEMA_VERSION,
        ],
        "provider_boundaries": {
            "decision_source_provider": (
                "bounded_authority_change_detection_and_exact_read"
            ),
            "context_provider": "bounded_advisory_recall",
            "provider_failure_policy": "fail_open_to_current_authority",
        },
        "lifecycle": [
            "recall",
            "exact_read",
            "rebase",
            "propose",
            "review_or_quiet_settlement",
            "commit_cursor",
            "observe_outcome",
        ],
        "invariants": [
            "evidence_and_proposal_remain_separate",
            "accepted_recalled_claims_require_exact_read_and_revision",
            "changed_facts_require_exact_read_authority_revisions",
            "incremental_cursors_advance_only_after_rebase_and_writeback",
            "cursor_commit_exact_reads_a_matching_lifecycle_event",
            "raw_provider_content_never_enters_public_packets",
            "one_off_recall_scope_and_content_are_never_persisted",
            "proposals_require_existing_authority_confirmation",
            "review_settlement_precedes_cursor_commit",
            "outcome_observation_does_not_block_consumed_source_cursors",
            "verified_outcomes_precede_reward_memory_candidates",
        ],
        "next_stage": "private_incremental_source_profile_then_dogfood",
    }
