import assert from "node:assert/strict";
import { normalizeCollaborationRequest } from "../../loopx/control_plane/collaboration/semantic_request.ts";

const target = { goal_id: "allocation", agent_id: "reviewer" };
const brief = {
  schema_version: "collaboration_brief_v0", purpose: "Review the allocation",
  context: "Proportional rounding was rejected. Preserve the reserve.",
  constraints: ["No real orders"], inputs: [{ ref: "outputs/plan.json", description: "Candidate plan" }],
  acceptance: ["Budget and shared stock hold"], return_requirement: "Return independent findings",
};
assert.deepEqual(normalizeCollaborationRequest(target), target);
assert.deepEqual(normalizeCollaborationRequest({ ...target, brief }), { ...target, brief });
for (const request of [
  { ...target, priority: "P0" }, { ...target, agent_id: "../reviewer" },
  { ...target, brief: { ...brief, acceptance: [] } },
  { ...target, brief: { ...brief, authority: "owner" } },
  { ...target, brief: { ...brief, inputs: [{ ref: "../secrets", description: "Outside" }] } },
  { ...target, brief: { ...brief, inputs: [{ ref: "file:///secret", description: "Outside" }] } },
  { ...target, brief: { ...brief, inputs: [{ ref: "inputs/a", description: "Input", sha256: "unverified" }] } },
  { ...target, brief: { ...brief, context: "字".repeat(6000) } },
]) assert.throws(() => normalizeCollaborationRequest(request));
console.log("semantic collaboration contract passed");
