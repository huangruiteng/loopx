/** Presentation only: the Chat proposal and apply service retain write authority. */
export type ActionReviewIdentity = {
  schemaVersion: "action_review_plan_v0";
  proposalId: string;
  sourceFingerprint: string;
};
export type ActionReviewReason =
  | "ready_stop" | "resume_review" | "delete_review" | "action_review"
  | "protected_action" | "unknown_permission" | "unknown_action"
  | "incomplete_proposal" | "authority_gate" | "stale_proposal"
  | "apply_pending" | "readback_verified" | "readback_unverified"
  | "apply_failed" | "inactive_proposal";

export type ActionReviewPlan = ActionReviewIdentity & (
  | { interaction: "direct"; reason: "ready_stop"; canApply: true }
  | { interaction: "review"; reason: ActionReviewReason; canApply: boolean }
  | { interaction: "gated" | "refresh" | "repair" | "pending" | "completed" | "inactive";
      reason: ActionReviewReason; canApply: false }
);

