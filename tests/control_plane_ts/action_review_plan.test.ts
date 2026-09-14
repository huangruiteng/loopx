import assert from "node:assert/strict";
import test from "node:test";

import {
  compileActionReviewPlan,
  compileOperationReviewFrame,
  isStaleActionFailure,
} from "../../loopx/control_plane/presentation/action_review_plan.ts";

function operationProposal(
  lifecycleState: "awaiting_confirmation" | "claimed" | "outcome_observed",
) {
  return {
    schema_version: "loopx_chat_action_proposal_v1",
    proposal_id: "operation-1",
    action_kind: "operation.execute",
    permission_classification: "protected",
    status: lifecycleState === "outcome_observed" ? "applied" : "gated",
    expected_state_fingerprint: "state-1",
    normalized_parameters: {
      projection: {
        schema_version: "loopx_operation_projection_v0",
        title: "Review simulated order",
        subtitle: "Bound Goal Channel request",
        focus: "BUY 1 SYNTH @ 10 TEST",
        fields: [{ label: "Order", value: "Limit · GTC" }],
        warning: "Simulation only.",
        simulated: true,
      },
    },
    operation: {
      schema_version: "loopx_operation_envelope_v0",
      lifecycle_state: lifecycleState,
      operation_id: "operation-1",
      confirmation_digest: "confirmation-1",
      expires_at: "2026-01-02T00:00:00Z",
      outcome: lifecycleState === "outcome_observed"
        ? {
            outcome: "executed",
            simulation: true,
            summary: "Simulation completed.",
          }
        : null,
      result_delivery: lifecycleState === "outcome_observed"
        ? { receipt_id: "delivery-1" }
        : null,
    },
  };
}

test("operation frame preserves exact confirmation identity and bounded content", () => {
  const frame = compileOperationReviewFrame(operationProposal("awaiting_confirmation"));

  assert.deepEqual(frame, {
    schemaVersion: "operation_review_frame_v0",
    operationId: "operation-1",
    confirmationDigest: "confirmation-1",
    lifecycleState: "awaiting_confirmation",
    simulated: true,
    expiresAt: "2026-01-02T00:00:00Z",
    content: {
      title: "Review simulated order",
      subtitle: "Bound Goal Channel request",
      focus: "BUY 1 SYNTH @ 10 TEST",
      fields: [{ label: "Order", value: "Limit · GTC" }],
      warning: "Simulation only.",
    },
    kind: "confirmation",
    attentionKind: "authority",
    interactionMode: "confirm_reject",
    decisions: ["confirm", "reject"],
  });
});

test("operation frame projects pending and verified result states", () => {
  const pending = compileOperationReviewFrame(operationProposal("claimed"));
  assert.equal(pending?.kind, "pending");
  assert.equal(pending?.interactionMode, "inform");

  const completed = compileActionReviewPlan(operationProposal("outcome_observed"));
  assert.equal(completed.interaction, "repair");
  assert.equal(completed.operationFrame?.kind, "result");
  if (completed.operationFrame?.kind !== "result") assert.fail("expected result frame");
  assert.equal(completed.operationFrame.resultKind, "simulation_completed");
  assert.equal(completed.operationFrame.resultDeliveryVerified, true);
  assert.equal(completed.operationFrame.summary, "Simulation completed.");
});

test("operation frame rejects identity drift and malformed projection fields", () => {
  const mismatched = operationProposal("awaiting_confirmation");
  mismatched.operation.operation_id = "another-operation";
  assert.equal(compileOperationReviewFrame(mismatched), undefined);

  const malformed = operationProposal("awaiting_confirmation");
  malformed.normalized_parameters.projection.fields = [{ label: "Order", value: "" }];
  assert.equal(compileOperationReviewFrame(malformed), undefined);
});

test("generic action review keeps state precedence and stale classification", () => {
  const proposal = {
    proposal_id: "preview-1",
    action_kind: "goal.lifecycle",
    normalized_parameters: { goal_id: "goal-1", operation: "stop" },
    context: { goal_id: "goal-1" },
    expected_state_fingerprint: "revision-1",
    permission_classification: "durable_write",
    validation_evidence: ["Validated"],
    available_transitions: ["apply", "cancel"],
    status: "preview_ready",
  };
  assert.equal(compileActionReviewPlan(proposal).interaction, "direct");
  assert.equal(
    compileActionReviewPlan({ ...proposal, stale: { actual: "revision-2" } }).interaction,
    "refresh",
  );
  assert.equal(isStaleActionFailure({ error_code: "action_conflict" }), true);
  assert.equal(isStaleActionFailure({ error: "unrelated conflict text" }), false);
});
