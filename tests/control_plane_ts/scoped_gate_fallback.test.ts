import assert from "node:assert/strict";
import test from "node:test";
import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import {fallbackGateRelation, selectScopedGateFallback} from "../../loopx/control_plane/todos/decision_scope.ts";
import {productionScaleCoordinationFixture} from "./production_scale_coordination_fixture.ts";

const gate = (extra: JsonObject = {}): JsonObject => ({todo_id: "todo_gate", status: "open", done: false,
  blocks_agent: "agent-a", action_kind: "publish_report", ...extra});
const work = (extra: JsonObject = {}): JsonObject => ({todo_id: "todo_work", status: "open", done: false,
  task_class: "advancement_task", action_kind: "inspect_report", priority_rank: 1, persisted_index: 1, ...extra});
const select = (extra: JsonObject = {}) => selectScopedGateFallback({gates: [gate({unblocks_todo_id: "todo_publish"})], candidates: [work()],
  agent_id: "agent-a", monitor_debt_backoff_active: false, allow_unrelated_gate: true, ...extra});

test("legacy action comparison is exact and independent of language and prose", () => {
  for (const text of ["publish report inspect approve", "请检查报告，不要发布", ""]) {
    assert.equal(fallbackGateRelation(gate({text}), work({text})).state, "projection_repair_required");
    assert.equal(fallbackGateRelation(gate({action_kind: "检查报告"}), work({action_kind: "检查报告", text})).state, "gate_covers_action");
    assert.equal(fallbackGateRelation(gate({action_kind: " INSPECT_REPORT "}), work({text})).state, "gate_covers_action");
  }
  assert.equal(fallbackGateRelation(gate({action_kind: null}), work()).source, "missing_dependency_scope");
  assert.equal(select({gates: [gate({action_kind: null})]}), null);
  assert.equal(select({gates: [gate({action_kind: "approve_release"})],
    candidates: [work({action_kind: "release"})]}), null);
});

test("typed exact/scope/global relations precede compatibility labels", () => {
  const scope = {kind: "write_scope", granularity: "action", scope_key: "release"};
  const dependent = work({required_decision_scopes: [scope]});
  assert.equal(select({gates: [gate({global_gate: true})]}), null);
  assert.equal(select({gates: [gate({unblocks_todo_id: "todo_work"})]}), null);
  assert.equal(select({gates: [gate({decision_scope: scope})], candidates: [dependent]}), null);
  const contradiction = gate({decision_scope: scope, unblocks_todo_id: "todo_other"});
  assert.equal(fallbackGateRelation(contradiction, dependent).state, "projection_repair_required");
  assert.equal(select({gates: [contradiction], candidates: [dependent]}), null);
  assert.ok(select({gates: [gate({unblocks_todo_id: "todo_other", action_kind: "inspect_report"})]}));
});

test("eligibility independently enforces retained lifecycle and actor facts", () => {
  for (const restriction of [{status: "done"}, {status: "blocked"}, {done: true}, {archive_state: "archive"},
    {claimed_by: "agent-b"}, {bound_agent: "agent-b"}, {excluded_agents: ["agent-a"]}, {removed: true},
    {status: "deferred", resume_ready: false}]) {
    assert.equal(select({candidates: [work(restriction)]}), null, JSON.stringify(restriction));
  }
  assert.equal(select({candidates: [work({status: "deferred", done: true, resume_ready: true})]})?.deferred_replan, true);
  assert.equal(select({gates: [gate({blocks_agent: "agent-b"})]}), null);
  assert.equal(select({gates: [gate({status: "done"})]}), null);
  // An unrelated claim cannot cancel an explicit gate addressed to this lane.
  assert.equal(select({gates: [gate({claimed_by: "agent-b", global_gate: true})]}), null);
  assert.ok(select({agent_id: null}));
});

test("production-scale mixed lifecycle facts are unchanged by fallback selection", () => {
  const fixture = productionScaleCoordinationFixture("goal-a");
  const records = fixture.projection.todos as JsonObject[];
  const candidates = records.filter(row => row.role === "agent").map((row, index) => work({
    ...row, action_kind: "publish_report", required_decision_scopes: [{kind: "direction", granularity: "action", scope_key: "delivery"}], priority_rank: 1, persisted_index: index,
  }));
  candidates.push(work({todo_id: "todo_independent_tail", persisted_index: candidates.length + 1}));
  const before = JSON.stringify({fixture, candidates});
  const result = select({candidates, allow_unrelated_gate: false,
    gates: [gate({decision_scope: {kind: "direction", granularity: "action", scope_key: "delivery"}})]});
  assert.equal(result?.selected_index, candidates.length - 1);
  assert.ok(Number(result?.blocked_count) > 3);
  assert.equal((result?.blocked as JsonObject[]).length, 3);
  assert.equal(JSON.stringify({fixture, candidates}), before);
});

test("selection is stable, debt only breaks same-priority ties, and source identities survive deduplication", () => {
  const candidates = [work({todo_id: "todo_monitor", task_class: "continuous_monitor", persisted_index: 1}),
    work({todo_id: "todo_delivery", persisted_index: 2}), work({todo_id: "todo_delivery", persisted_index: 0})];
  assert.equal(select({candidates})?.selected_index, 0);
  assert.equal(select({candidates, monitor_debt_backoff_active: true})?.selected_index, 1);
  assert.equal(select({candidates: [work({priority_rank: 0}), ...candidates], monitor_debt_backoff_active: true})?.selected_index, 0);
  assert.equal(select({candidates: [work(), work({todo_id: "todo_second"})]})?.selected_index, 0);
  assert.equal(select({candidates: []}), null);
});

test("all candidates are evaluated before display limits and independent work remains available", () => {
  const scope = {kind: "direction", granularity: "action", scope_key: "delivery"};
  const candidates = Array.from({length: 500}, (_, i) => work({todo_id: `todo_blocked_${i}`, required_decision_scopes: [scope], persisted_index: i}));
  candidates.push(work({todo_id: "todo_last", persisted_index: 501}));
  const result = select({candidates, allow_unrelated_gate: false, gates: [gate({decision_scope: scope})]});
  assert.equal(result?.selected_index, 500);
  assert.equal((result?.blocked as JsonObject[]).length, 3);
  assert.equal(result?.blocked_count, 500);
  assert.equal(result?.has_blocking_gate, true);
  assert.equal(select({allow_unrelated_gate: false}), null);
});
