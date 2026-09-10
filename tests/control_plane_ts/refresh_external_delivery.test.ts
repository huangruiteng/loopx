import assert from "node:assert/strict";
import test from "node:test";
import { settlementIdentity, type JsonObject } from "../../loopx/control_plane/effect_program.ts";
import { decodeExternalDelivery, EXTERNAL_DELIVERY_EVENT, refreshExternalDelivery } from "../../loopx/control_plane/quota/refresh_external_delivery.ts";

const identity = settlementIdentity({ goal_id: "resume-fixture", agent_id: "builder",
  turn_instance_id: "turn-a", todo_id: "todo_resume", replan_obligation_id: null });
const normal = { suppress: false, resume_key: null };
const suppress = { suppress: true, resume_key: null };
const plan = (events: JsonObject[], request = normal, stage = true) =>
  refreshExternalDelivery(request, identity, events, stage);
function event(result: JsonObject, id: string): JsonObject {
  assert.ok(result.transition);
  return { event_id: id, event_kind: EXTERNAL_DELIVERY_EVENT,
    goal_id: identity.goal_id, agent_id: identity.agent_id, run_id: identity.turn_instance_id,
    todo_id: identity.todo_id, details: result.transition };
}

test("legacy requests and non-delivery callers keep their behavior", () => {
  assert.equal(plan([]).authorized, true);
  assert.equal(plan([]).reason, "legacy_per_call");
  const local = refreshExternalDelivery(null, identity, [], true);
  assert.equal(local.authorized, false);
  assert.equal(local.transition, null);
  assert.equal(decodeExternalDelivery(undefined), null);
  for (const bad of [true, {}, { suppress: "false", resume_key: null },
    { suppress: true, resume_key: "a".repeat(64) }, { ...normal, resume_key: "bad" }]) {
    assert.throws(() => decodeExternalDelivery(bad));
  }
});

test("pause, omission, explicit resume, and repeated acknowledgement", () => {
  const first = plan([], suppress);
  const events = [event(first, "pause-a")];
  assert.equal(first.authorized, false);
  assert.equal(plan(events).error_code, "external_delivery_resume_required");
  assert.equal(plan(events, suppress).transition, null);
  assert.equal(plan(events, suppress).error_code, null);
  const resume = { ...normal, resume_key: String(first.resume_key) };
  const approved = plan(events, resume);
  assert.equal(approved.authorized, true);
  events.push(event(approved, "resume-a"));
  assert.equal(plan(events).authorized, true);
  assert.equal(plan(events, resume).transition, null);
  assert.equal(plan(events, resume).authorized, true);
  const pausedAgain = plan(events, suppress);
  assert.notEqual(pausedAgain.resume_key, first.resume_key);
  events.push(event(pausedAgain, "pause-b"));
  assert.equal(plan(events, resume).error_code, "external_delivery_resume_mismatch");
  assert.equal(plan(events).error_code, "external_delivery_resume_required");
});

test("acknowledgements cannot cross operations or silently initialize a resume", () => {
  const first = plan([], suppress);
  const foreign = settlementIdentity({ ...identity, turn_instance_id: "turn-b" });
  const other = refreshExternalDelivery(suppress, foreign, [], true);
  assert.notEqual(other.resume_key, first.resume_key);
  assert.equal(plan([], { ...normal, resume_key: String(first.resume_key) }).error_code,
    "external_delivery_resume_mismatch");
  const foreignEvent = { ...event(other, "other-pause"), run_id: foreign.turn_instance_id };
  assert.equal(plan([foreignEvent]).authorized, true);
  const events = [event(first, "pause-a")];
  assert.equal(plan(events, { ...normal, resume_key: String(other.resume_key) }).authorized, false);
});

test("receipt-only repair and unspecified callers do not consume acknowledgement", () => {
  const first = plan([], suppress);
  const events = [event(first, "pause-a")];
  const receipt = plan(events, normal, false);
  assert.equal(receipt.authorized, false);
  assert.equal(receipt.error_code, null);
  assert.equal(receipt.transition, null);
  assert.equal(refreshExternalDelivery(null, identity, events, true).error_code, null);
  assert.equal(plan(events, { ...normal, resume_key: String(first.resume_key) }, false).transition, null);
  assert.ok(plan([], suppress, false).transition); // Explicit suppression is still remembered.
});

test("older writers cannot erase a pause; corrupt relevant history never permits sending", () => {
  const first = plan([], suppress);
  const pause = event(first, "pause-a");
  const unrelated = { ...pause, event_kind: "refresh_state", details: {} };
  assert.equal(plan([pause, unrelated]).error_code, "external_delivery_resume_required");
  for (const details of [null, { ...(pause.details as JsonObject), schema_version: "future" },
    { ...(pause.details as JsonObject), state: "ready" },
    { ...(pause.details as JsonObject), settlement_effect_id: "wrong" },
    { ...(pause.details as JsonObject), resume_key: "0".repeat(64) }]) {
    const corrupted = [{ ...pause, details }];
    assert.equal(plan(corrupted).error_code, "external_delivery_history_invalid");
    assert.equal(plan(corrupted, suppress).authorized, false);
    assert.equal(plan(corrupted, suppress).error_code, null);
  }
});
