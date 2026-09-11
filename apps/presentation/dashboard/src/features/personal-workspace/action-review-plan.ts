import type { TypedActionProposal } from "../../data/chat";

import type { ActionReviewIdentity, ActionReviewPlan, ActionReviewReason } from "./action-review-plan-types";

// These are named presentation rules, not a second Goal legal-action catalog.
const lifecycleReviewReasons = { stop: "ready_stop", resume: "resume_review", delete: "delete_review" } as const;
const hasText = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;

export function compileActionReviewPlan(proposal: TypedActionProposal): ActionReviewPlan {
  const identity: ActionReviewIdentity = {
    schemaVersion: "action_review_plan_v0",
    proposalId: proposal.proposal_id,
    sourceFingerprint: proposal.expected_state_fingerprint,
  };
  const held = (interaction: "gated" | "refresh" | "repair" | "pending" | "completed" | "inactive", reason: ActionReviewReason): ActionReviewPlan =>
    ({ ...identity, interaction, reason, canApply: false });
  // Contradictory gate/stale facts take precedence over a nominally ready status.
  if (proposal.gate != null || proposal.status === "gated") return held("gated", "authority_gate");
  if (proposal.stale != null || proposal.status === "stale") return held("refresh", "stale_proposal");
  if (proposal.status === "applied") return proposal.receipt?.projection_verified === true
    ? held("completed", "readback_verified") : held("repair", "readback_unverified");
  if (proposal.status === "applying") return held("pending", "apply_pending");
  if (proposal.status === "failed" || proposal.error != null) return held("repair", "apply_failed");
  if (proposal.status !== "preview_ready" && proposal.status !== "deferred") return held("inactive", "inactive_proposal");
  const reviewed = (reason: ActionReviewReason, canApply = true): ActionReviewPlan =>
    ({ ...identity, interaction: "review", reason, canApply });
  // Other action owners keep their existing reviewed path in this lifecycle slice.
  if (proposal.action_kind !== "goal.lifecycle") return reviewed(proposal.permission_classification === "protected" ? "protected_action" : "action_review");
  const complete = hasText(proposal.proposal_id) && hasText(proposal.expected_state_fingerprint)
    && proposal.validation_evidence.length > 0 && proposal.available_transitions.includes("apply");
  if (!complete) return held("refresh", "incomplete_proposal");
  const { operation, goal_id: goalId } = proposal.normalized_parameters;
  if (!hasText(goalId) || (proposal.context.goal_id != null && proposal.context.goal_id !== goalId)) return held("refresh", "incomplete_proposal");
  if (operation !== "stop" && operation !== "resume" && operation !== "delete") return reviewed("unknown_action", false);
  if (proposal.permission_classification === "protected") return reviewed("protected_action");
  if (proposal.permission_classification !== "durable_write") return reviewed("unknown_permission", false);
  const reason = lifecycleReviewReasons[operation];
  if (reason === "ready_stop" && proposal.status === "preview_ready") return { ...identity, interaction: "direct", reason, canApply: true };
  return reviewed(reason === "ready_stop" ? "action_review" : reason);
}
