import { compileActionReviewPlan, isStaleActionFailure } from "../src/features/personal-workspace/action-review-plan.js";
import { typedActionProposalSchema, type TypedActionProposal } from "../src/data/chat.js";

const proposal: TypedActionProposal = {
  schema_version: "loopx_chat_action_proposal_v1", proposal_id: "preview-1",
  action_kind: "goal.lifecycle", summary: "Stop sample Goal",
  normalized_parameters: { goal_id: "sample-goal", operation: "stop" },
  context: { kind: "goal_directory", goal_id: "sample-goal" },
  expected_state_fingerprint: "revision-1", permission_classification: "durable_write",
  validation_evidence: ["Canonical bounded shape validated"], available_transitions: ["apply", "cancel"],
  status: "preview_ready", receipt: null, stale: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};
function check(condition: boolean, description: string) { if (!condition) throw new Error(description); }
const compile = (patch: Partial<TypedActionProposal> = {}) => compileActionReviewPlan({ ...proposal, ...patch });
check(compile().interaction === "direct", "A validated ready stop preserves the direct path");
for (const validation_evidence of [[null], [""], [" \t"], [{}], ["valid", null], ["valid", {}], ["valid", ""]]) {
  const raw = { ...proposal, validation_evidence };
  check(!typedActionProposalSchema.safeParse(raw).success, "Transport must reject every malformed evidence element");
  check(compileActionReviewPlan(raw as unknown as TypedActionProposal).interaction !== "direct", "Unparsed malformed evidence cannot become direct");
}
check(typedActionProposalSchema.parse({ ...proposal, validation_evidence: ["  Canonical validation  "] }).validation_evidence[0] === "  Canonical validation  ", "Validation preserves evidence text");
for (const operation of ["resume", "delete"]) {
  const result = compile({ normalized_parameters: { goal_id: "sample-goal", operation } });
  check(result.interaction === "review" && result.canApply, `${operation} requires review`);
}
// Mutate each fact independently. None may preserve direct presentation.
const unsafe: Array<Partial<TypedActionProposal>> = [
  { permission_classification: "protected" }, { permission_classification: "unknown" },
  { action_kind: "goal.update" }, { normalized_parameters: { goal_id: "sample-goal", operation: "unknown" } },
  { normalized_parameters: { operation: "stop" } }, { expected_state_fingerprint: "" },
  { proposal_id: "" }, { validation_evidence: [] }, { available_transitions: ["cancel"] },
  { gate: { kind: "authority_required" } }, { stale: { actual: "revision-2" } },
  { error: { message: "failed validation" } },
  { context: { goal_id: "another-goal" } },
];
for (const patch of unsafe) check(compile(patch).interaction !== "direct", `Unsafe fact must remove direct path: ${JSON.stringify(patch)}`);
for (const status of ["gated", "stale", "applying", "applied", "failed", "rejected", "deferred", "cancelled"] as const) {
  check(compile({ status }).interaction !== "direct", `${status} is never direct`);
}
check(compile({ status: "applied", receipt: { projection_verified: true } }).interaction === "completed", "Only verified applied state completes");
for (const receipt of [null, {}, { projection_verified: false }, { projection_verified: "true" }]) {
  const result = compile({ status: "applied", receipt });
  check(result.interaction === "repair" && !result.canApply, "Unverified receipt cannot complete or repeat apply");
}
check(compile({ status: "preview_ready", receipt: { projection_verified: true } }).interaction !== "completed", "Receipt alone cannot complete");
check(compile({ status: "applied", receipt: { projection_verified: true }, stale: {} }).interaction === "refresh", "Stale wins over nominal success");
check(compile({ status: "applied", receipt: { projection_verified: true }, gate: {} }).interaction === "gated", "Gate wins over nominal success");
for (const action_kind of ["goal.create", "goal.update", "todo.create", "todo.update", "agent.bind", "heartbeat.bind", "monitor.create", "monitor.update", "gate.resolve", "run.correct"] as const) {
  for (const status of ["preview_ready", "deferred"] as const) {
    const result = compile({ action_kind, status, validation_evidence: [] });
    check(result.interaction === "review" && result.canApply, `${action_kind} keeps existing reviewed behavior`);
    if (status === "deferred") check(compile({ action_kind, status, gate: { kind: "previous_gate" } }).canApply, "Generic deferred retries retain historical gate without losing the apply path");
  }
}
check(compile().sourceFingerprint === "revision-1" && compile().proposalId === "preview-1", "Preserve exact identity and fingerprint");
const frozen = JSON.stringify(proposal);
check(JSON.stringify(compile()) === JSON.stringify(compile()), "Deterministic compilation");
check(JSON.stringify(proposal) === frozen, "No input mutation");
console.log("PASS: action review parity, negative fact mutations, state precedence and verified readback");

check(isStaleActionFailure({ error_code: "action_stale" }), "Typed stale errors offer refresh");
check(isStaleActionFailure({ error_code: "action_conflict" }), "Typed conflicts offer refresh");
check(isStaleActionFailure({ proposal: { status: "stale" } }), "Typed stale proposal survives error wrapping");
check(!isStaleActionFailure({ error_code: "canonical_action_failed", error: "conflict with unrelated external service" }), "Error wording cannot classify source state");
