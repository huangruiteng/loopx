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

export type OperationReviewContent = {
  title: string;
  subtitle: string;
  focus: string;
  fields: Array<{ label: string; value: string }>;
  warning: string;
};

type OperationReviewFrameBase = {
  schemaVersion: "operation_review_frame_v0";
  operationId: string;
  confirmationDigest: string;
  lifecycleState: "awaiting_confirmation" | "claimed" | "outcome_observed";
  simulated: boolean;
  expiresAt: string;
  content: OperationReviewContent;
};

export type OperationReviewFrame = OperationReviewFrameBase & (
  | {
      kind: "confirmation";
      attentionKind: "authority";
      interactionMode: "confirm_reject";
      decisions: readonly ["confirm", "reject"];
    }
  | {
      kind: "pending";
      attentionKind: "progress";
      interactionMode: "inform";
    }
  | {
      kind: "result";
      attentionKind: "progress";
      interactionMode: "inform";
      resultKind: "rejected" | "simulation_completed" | "completed";
      resultDeliveryVerified: boolean;
      summary: string;
    }
);

type ActionReviewState =
  | { interaction: "direct"; reason: "ready_stop"; canApply: true }
  | { interaction: "review"; reason: ActionReviewReason; canApply: boolean }
  | {
      interaction: "gated" | "refresh" | "repair" | "pending" | "completed" | "inactive";
      reason: ActionReviewReason;
      canApply: false;
    };

export type ActionReviewPlan = ActionReviewIdentity & ActionReviewState & {
  operationFrame?: OperationReviewFrame;
};

type JsonRecord = Record<string, unknown>;

const lifecycleReviewReasons = {
  stop: "ready_stop",
  resume: "resume_review",
  delete: "delete_review",
} as const;

function objectValue(value: unknown): JsonRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as JsonRecord
    : null;
}

function textValue(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function operationContent(parameters: JsonRecord): OperationReviewContent | null {
  const projection = objectValue(parameters.projection);
  if (projection?.schema_version !== "loopx_operation_projection_v0") return null;
  const title = textValue(projection.title);
  const subtitle = textValue(projection.subtitle);
  const focus = textValue(projection.focus);
  const warning = textValue(projection.warning);
  if (!title || !subtitle || !focus || !warning || !Array.isArray(projection.fields)) return null;
  const fields: Array<{ label: string; value: string }> = [];
  for (const raw of projection.fields) {
    const field = objectValue(raw);
    const label = textValue(field?.label);
    const value = textValue(field?.value);
    if (!label || !value) return null;
    fields.push({ label, value });
  }
  return { title, subtitle, focus, fields, warning };
}

export function compileOperationReviewFrame(proposalValue: unknown): OperationReviewFrame | undefined {
  const proposal = objectValue(proposalValue);
  if (proposal?.action_kind !== "operation.execute") return undefined;
  const parameters = objectValue(proposal.normalized_parameters);
  const operation = objectValue(proposal.operation);
  if (!parameters || operation?.schema_version !== "loopx_operation_envelope_v0") return undefined;
  const operationId = textValue(operation.operation_id);
  const confirmationDigest = textValue(operation.confirmation_digest);
  const expiresAt = textValue(operation.expires_at);
  const content = operationContent(parameters);
  if (!operationId || !confirmationDigest || !expiresAt || !content) return undefined;
  if (operationId !== proposal.proposal_id) return undefined;
  const lifecycleState = operation.lifecycle_state;
  if (
    lifecycleState !== "awaiting_confirmation"
    && lifecycleState !== "claimed"
    && lifecycleState !== "outcome_observed"
  ) return undefined;
  const projection = objectValue(parameters.projection)!;
  const base: OperationReviewFrameBase = {
    schemaVersion: "operation_review_frame_v0",
    operationId,
    confirmationDigest,
    lifecycleState,
    simulated: projection.simulated === true,
    expiresAt,
    content,
  };
  if (lifecycleState === "awaiting_confirmation") {
    return {
      ...base,
      kind: "confirmation",
      attentionKind: "authority",
      interactionMode: "confirm_reject",
      decisions: ["confirm", "reject"],
    };
  }
  if (lifecycleState === "claimed") {
    return {
      ...base,
      kind: "pending",
      attentionKind: "progress",
      interactionMode: "inform",
    };
  }
  const outcome = objectValue(operation.outcome);
  if (!outcome) return undefined;
  const rejected = outcome.outcome === "rejected_by_operator";
  const simulated = outcome.simulation === true || base.simulated;
  return {
    ...base,
    kind: "result",
    attentionKind: "progress",
    interactionMode: "inform",
    resultKind: rejected ? "rejected" : simulated ? "simulation_completed" : "completed",
    resultDeliveryVerified: objectValue(operation.result_delivery) !== null,
    summary: textValue(outcome.summary) ?? "",
  };
}

/**
 * Compile provider-neutral presentation semantics from a typed action proposal.
 * This reducer owns no action authority and performs no external effects.
 */
export function compileActionReviewPlan(proposalValue: unknown): ActionReviewPlan {
  const proposal = objectValue(proposalValue) ?? {};
  const identity: ActionReviewIdentity = {
    schemaVersion: "action_review_plan_v0",
    proposalId: typeof proposal.proposal_id === "string" ? proposal.proposal_id : "",
    sourceFingerprint: typeof proposal.expected_state_fingerprint === "string"
      ? proposal.expected_state_fingerprint
      : "",
  };
  const operationFrame = compileOperationReviewFrame(proposal);
  const finish = (state: ActionReviewState): ActionReviewPlan => ({
    ...identity,
    ...state,
    ...(operationFrame ? { operationFrame } : {}),
  });
  const held = (
    interaction: "gated" | "refresh" | "repair" | "pending" | "completed" | "inactive",
    reason: ActionReviewReason,
  ): ActionReviewPlan => finish({ interaction, reason, canApply: false });
  const lifecycle = proposal.action_kind === "goal.lifecycle";
  // Lifecycle uses conservative fact precedence. Generic deferred proposals may
  // retain a historical gate; their existing status-based retry path is preserved.
  if ((lifecycle && proposal.gate != null) || proposal.status === "gated") return held("gated", "authority_gate");
  if ((lifecycle && proposal.stale != null) || proposal.status === "stale") return held("refresh", "stale_proposal");
  if (proposal.status === "applied") {
    const receipt = objectValue(proposal.receipt);
    return receipt?.projection_verified === true
      && (proposal.action_kind !== "operation.execute" || objectValue(objectValue(proposal.operation)?.result_delivery) !== null)
      ? held("completed", "readback_verified")
      : held("repair", "readback_unverified");
  }
  if (proposal.status === "applying") return held("pending", "apply_pending");
  if (proposal.status === "failed" || proposal.error != null) return held("repair", "apply_failed");
  if (proposal.status !== "preview_ready" && proposal.status !== "deferred") return held("inactive", "inactive_proposal");
  const reviewed = (reason: ActionReviewReason, canApply = true): ActionReviewPlan =>
    finish({ interaction: "review", reason, canApply });
  if (proposal.action_kind !== "goal.lifecycle") {
    return reviewed(proposal.permission_classification === "protected" ? "protected_action" : "action_review");
  }
  const evidence = proposal.validation_evidence;
  const transitions = proposal.available_transitions;
  const complete = textValue(proposal.proposal_id) !== null
    && textValue(proposal.expected_state_fingerprint) !== null
    && Array.isArray(evidence)
    && evidence.length > 0
    && evidence.every((item) => textValue(item) !== null)
    && Array.isArray(transitions)
    && transitions.includes("apply");
  if (!complete) return held("refresh", "incomplete_proposal");
  const parameters = objectValue(proposal.normalized_parameters);
  const context = objectValue(proposal.context);
  const operation = parameters?.operation;
  const goalId = textValue(parameters?.goal_id);
  if (!goalId || (context?.goal_id != null && context.goal_id !== goalId)) return held("refresh", "incomplete_proposal");
  if (operation !== "stop" && operation !== "resume" && operation !== "delete") return reviewed("unknown_action", false);
  if (proposal.permission_classification === "protected") return reviewed("protected_action");
  if (proposal.permission_classification !== "durable_write") return reviewed("unknown_permission", false);
  const reason = lifecycleReviewReasons[operation];
  if (reason === "ready_stop" && proposal.status === "preview_ready") {
    return finish({ interaction: "direct", reason, canApply: true });
  }
  return reviewed(reason === "ready_stop" ? "action_review" : reason);
}

/** The existing Chat error envelope, not translated prose, identifies stale state. */
export function isStaleActionFailure(payload: Record<string, unknown>): boolean {
  if (payload.error_code === "action_stale" || payload.error_code === "action_conflict") return true;
  const proposal = objectValue(payload.proposal);
  return proposal?.status === "stale";
}
