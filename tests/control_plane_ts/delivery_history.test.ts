import assert from "node:assert/strict";
import test from "node:test";
import type { JsonObject } from "../../loopx/control_plane/effect_program.ts";
import { projectDeliveryHistory } from "../../loopx/control_plane/work_items/delivery_history.ts";
import { validateDeliveryClaim } from "../../loopx/control_plane/work_items/delivery_outcome.ts";

function run(fields: JsonObject = {}): JsonObject {
  return { delivery_outcome: "", delivery_batch_scale: "", delivery_turn_kind: "",
    todo_id: "", replan_obligation_id: "", outcome_followthrough_required: false,
    progress_observation: null, ...fields };
}

function project(runs: JsonObject[], configured = true): JsonObject {
  return projectDeliveryHistory({ schema_version: "delivery_history_request_v0",
    runs, outcome_floor_configured: configured });
}

function signal(fields: JsonObject): JsonObject {
  return (project([run(fields)]).runs as JsonObject[])[0];
}

test("typed outcomes have distinct follow-through meaning, independent of arbitrary narrative", () => {
  const cases = [
    ["surface_only", "contract_only_preparation", true],
    ["outcome_gap", "outcome_gap", true],
    ["outcome_progress", "compact_evidence", false],
    ["primary_goal_outcome", "product_path_execution", false],
    ["future_outcome", "unknown", false],
  ] as const;
  for (const [outcome, kind, required] of cases) {
    const fields = { delivery_outcome: outcome, classification: "blocked contract merged",
      health_check: "unblocked", recommended_action: "ship", compact_evidence: { result: "success" } };
    const actual = signal(fields);
    assert.equal(actual.delivery_turn_kind, kind);
    assert.equal(actual.outcome_followthrough !== null, required);
    assert.deepEqual(actual, signal({ delivery_outcome: outcome }));
  }
});

test("missing floor is elided while unsupported evidence remains unknown", () => {
  const rows = (project([run(), run({ delivery_outcome: "future" })], false).runs as JsonObject[]);
  assert.equal(rows[0].delivery_outcome, "not_configured");
  assert.equal(rows[1].delivery_outcome, "unknown");
  assert.equal(rows[0].delivery_turn_kind, "unknown");
});

test("unsupported kind suppresses inference; explicit obligations do not override primary outcome", () => {
  assert.equal(signal({ delivery_outcome: "outcome_progress", delivery_turn_kind: "future" }).delivery_turn_kind, "unknown");
  assert.equal(signal({ delivery_outcome: "primary_goal_outcome", outcome_followthrough_required: true }).outcome_followthrough, null);
  assert.notEqual(signal({ outcome_followthrough_required: true }).outcome_followthrough, null);
  assert.equal(signal({ delivery_outcome: "outcome_gap", delivery_turn_kind: "blocker_writeback" }).outcome_followthrough, null);
  assert.notEqual(signal({ delivery_outcome: "outcome_gap", delivery_turn_kind: "blocker_writeback", outcome_followthrough_required: true }).outcome_followthrough, null);
});

test("unknown breaks consecutive streaks; aliases retain their small-scale meaning", () => {
  const gap = run({ delivery_outcome: "surface_only", delivery_batch_scale: "single_segment" });
  const small = run({ delivery_outcome: "outcome_gap", delivery_batch_scale: "bounded_segment" });
  assert.equal(project([gap, small]).small_scale_streak, 2);
  assert.equal(project([gap, small]).outcome_gap_streak, 2);
  assert.equal(project([gap, run(), small]).small_scale_streak, 1);
  assert.equal(project([gap, run(), small]).outcome_gap_streak, 1);
  assert.equal(project([gap, small], false).outcome_gap_streak, 0);
  assert.equal(project([]).outcome_gap_streak, 0);
  assert.equal(project([]).small_scale_streak, 0);
});

test("blocker evidence must bind exactly one valid Todo or replan identity", () => {
  const observation = { schema_version: "typed_progress_observation_v0", result_class: "blocked",
    work_item_id: "todo-a", blocker_id: "blocker-a", evidence_ids: ["evidence-a"] };
  const fields = { delivery_outcome: "outcome_gap", todo_id: "todo-a", progress_observation: observation };
  assert.equal(signal(fields).delivery_turn_kind, "blocker_writeback");
  assert.equal(signal({ ...fields, todo_id: "", replan_obligation_id: "todo-a" }).delivery_turn_kind, "blocker_writeback");
  for (const patch of [{ todo_id: "" }, { todo_id: "different" }, { replan_obligation_id: "todo-a" }]) {
    assert.equal(signal({ ...fields, ...patch }).delivery_turn_kind, "outcome_gap");
  }
  for (const patch of [ { work_item_id: "other" }, { evidence_ids: [] }, { evidence_ids: ["valid", "bad id"] },
    { blocker_id: "" }, { result_class: "advanced" }, { schema_version: "future" } ]) {
    const actual = signal({ ...fields, progress_observation: { ...observation, ...patch } });
    assert.equal(actual.delivery_turn_kind, "outcome_gap");
    assert.notEqual(actual.outcome_followthrough, null);
  }
});

test("batch is immutable, ordered and not limited to a presentation cap", () => {
  const rows = Array.from({ length: 257 }, () => run({ delivery_outcome: "outcome_gap", delivery_batch_scale: "test_only" }));
  const before = structuredClone(rows);
  const result = project(rows);
  assert.equal(result.small_scale_streak, 257);
  assert.equal(result.outcome_gap_streak, 257);
  assert.equal((result.runs as unknown[]).length, 257);
  assert.deepEqual(rows, before);
});

test("wire faults fail closed, not a fallback to untyped history", () => {
  for (const input of [null, {}, { schema_version: "future", runs: [] },
    { schema_version: "delivery_history_request_v0", runs: [], outcome_floor_configured: "true" }]) {
    assert.throws(() => projectDeliveryHistory(input));
  }
  for (const fields of [{ delivery_outcome: true }, { outcome_followthrough_required: 1 },
    { progress_observation: [] }, { todo_id: null }]) {
    const rows = [run(fields)];
    assert.throws(() => project(rows));
  }
});

test("contradictory historical declarations are diagnostic, not progress or new obligations", () => {
  for (const fields of [
    { delivery_outcome: "outcome_progress", delivery_turn_kind: "contract_only_preparation" },
    { delivery_outcome: "primary_goal_outcome", delivery_turn_kind: "blocker_writeback" },
    { delivery_outcome: "primary_goal_outcome", outcome_followthrough_required: true },
    { delivery_outcome: "primary_goal_outcome", progress_observation: {
      schema_version: "typed_progress_observation_v0", result_class: "blocked" } },
  ]) {
    const record = run(fields);
    const before = structuredClone(record);
    assert.equal(validateDeliveryClaim(record).valid, false);
    const projected = signal(record);
    assert.equal(projected.delivery_outcome, "unknown");
    assert.equal(projected.delivery_turn_kind, "unknown");
    assert.equal(projected.outcome_followthrough, null);
    assert.deepEqual(projected.delivery_claim_conflicts, validateDeliveryClaim(record).conflicts);
    assert.deepEqual(record, before);
  }
  for (const fields of [
    { delivery_outcome: "outcome_progress", delivery_turn_kind: "product_path_execution" },
    { delivery_outcome: "primary_goal_outcome", delivery_turn_kind: "compact_evidence" },
    { delivery_outcome: "outcome_gap", delivery_turn_kind: "blocker_writeback" },
    {},
  ]) assert.equal(validateDeliveryClaim(run(fields)).valid, true);
});
