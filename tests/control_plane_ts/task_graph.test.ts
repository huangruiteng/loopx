import assert from "node:assert/strict";
import test from "node:test";
import { projectTaskGraphTopology, TASK_GRAPH_TOPOLOGY_REQUEST } from "../../loopx/control_plane/work_items/task_graph.ts";
import { projectRelations, todoRef } from "../../loopx/control_plane/work_items/planning_relations.ts";
import type { JsonObject } from "../../loopx/control_plane/effect_program.ts";
import { productionScaleCoordinationFixture } from "./production_scale_coordination_fixture.ts";

const row = (todo_id: string, extra: JsonObject = {}): JsonObject =>
  ({ todo_id, done: true, successor_todo_ids: [], ...extra });
function graph(items: JsonObject[], extra: JsonObject = {}): JsonObject {
  return projectTaskGraphTopology({ schema_version: TASK_GRAPH_TOPOLOGY_REQUEST,
    selected_todo_id: "todo_root", predecessor_limit: 4, source_truncated: false, items, ...extra });
}

test("known Todo conditions only: opaque route/capability refs cannot become graph edges", () => {
  for (const value of ["route:todo_fake", "capacity_available:todo_fake", "unknown:todo_fake", "pr_merged:todo_fake"]) {
    assert.equal(todoRef(value), null);
  }
  assert.equal(todoRef("todo_real"), "todo_real");
  assert.equal(todoRef("monitor_changed:todo_real"), "todo_real");
  assert.equal(todoRef("todo_done:todo_real"), "todo_real");
});

test("shared catalog preserves lineage, lifecycle and condition as distinct knowledge", () => {
  const relations = projectRelations([{todo_id: "todo_root", successor_todo_ids: ["todo_child", "todo_child"],
    unblocks_todo_id: "todo_parent", resume_when: "monitor_changed:todo_monitor"}]);
  assert.deepEqual(relations.map(r => [r.relation, r.enforcement]), [
    ["successor", "lineage_only"], ["unblocks", "typed_lifecycle"], ["resumes_when", "typed_condition"],
  ]);
});

test("budget saturation retains every edge between admitted diamond vertices", () => {
  const rows = [row("todo_root", {done: false}),
    row("todo_a", {successor_todo_ids: ["todo_root"]}),
    row("todo_b", {successor_todo_ids: ["todo_root"]}),
    row("todo_shared", {successor_todo_ids: ["todo_a", "todo_b"]}),
    row("todo_aaa_overflow", {successor_todo_ids: ["todo_b"]})];
  const result = graph(rows, {predecessor_limit: 3});
  assert.deepEqual(result.predecessor_todo_ids, ["todo_a", "todo_b", "todo_shared"]);
  assert.deepEqual((result.edges as JsonObject[]).map(e => [e.from_todo_id, e.to_todo_id]), [
    ["todo_root", "todo_a"], ["todo_root", "todo_b"],
    ["todo_a", "todo_shared"], ["todo_b", "todo_shared"],
  ]);
  assert.equal((result.completeness as JsonObject).predecessor_truncated, true);
  assert.deepEqual(graph([...rows].reverse(), {predecessor_limit: 3}), result);
});

test("cycles and parallel semantic edges terminate without duplicating nodes", () => {
  const result = graph([row("todo_root", {resume_when: "todo_done:todo_parent", successor_todo_ids: ["todo_parent"]}),
    row("todo_parent", {successor_todo_ids: ["todo_root"]})]);
  assert.deepEqual(result.predecessor_todo_ids, ["todo_parent"]);
  assert.equal((result.edges as JsonObject[]).length, 3);
  assert.equal((result.completeness as JsonObject).topology_complete, true);
});

test("missing, source truncation and display truncation are independent", () => {
  const result = graph([row("todo_root", {resume_when: "todo_done:todo_missing"})]);
  assert.deepEqual(result.completeness, {predecessor_limit: 4, emitted_predecessor_count: 0,
    predecessor_truncated: false, source_truncated: false, missing_predecessor_count: 1, topology_complete: false});
  assert.equal((graph([row("todo_root")], {source_truncated: true}).completeness as JsonObject).topology_complete, false);
  const omitted = graph([row("todo_root"), row("todo_parent", {successor_todo_ids: ["todo_root"]})], {predecessor_limit: 0});
  assert.equal((omitted.completeness as JsonObject).predecessor_truncated, true);
  assert.equal((omitted.completeness as JsonObject).missing_predecessor_count, 0);
});

test("open predecessor remains an expansion boundary, but not a dropped node", () => {
  const result = graph([row("todo_root"), row("todo_parent", {done: false, successor_todo_ids: ["todo_root"]}),
    row("todo_ancestor", {successor_todo_ids: ["todo_parent"]})]);
  assert.deepEqual(result.predecessor_todo_ids, ["todo_parent"]);
  assert.equal((result.completeness as JsonObject).topology_complete, true);
});

test("thousands of unrelated rows and deep ancestry keep projection bounded", () => {
  const rows = [row("todo_root"), ...Array.from({length: 4096}, (_, i) => row(`todo_unrelated_${i}`)),
    ...Array.from({length: 512}, (_, i) => row(`todo_chain_${i}`, {
      successor_todo_ids: [i === 0 ? "todo_root" : `todo_chain_${i - 1}`],
    }))];
  const result = graph(rows);
  assert.equal((result.predecessor_todo_ids as string[]).length, 4);
  assert.equal((result.edges as JsonObject[]).length, 4);
  assert.equal((result.completeness as JsonObject).predecessor_truncated, true);
});

test("invalid wire input fails at the typed boundary", () => {
  assert.throws(() => graph([row("todo_root"), row("todo_root")]), /Duplicate/);
  for (const predecessor_limit of [-1, 33, 0.5]) assert.throws(() => graph([], {predecessor_limit}));
  assert.throws(() => graph([row("todo_root", {done: "false"})]), /boolean/);
  assert.throws(() => graph([], {schema_version: "unknown"}), /schema/);
});

test("production-scale canonical fixture supports mixed ancestry without changing authority", () => {
  const fixture = productionScaleCoordinationFixture("graph-goal");
  const before = JSON.stringify(fixture.projection);
  const records = fixture.projection.todos as JsonObject[];
  assert.equal(records.length, fixture.expected_initial_todo_count);
  // Add a small, explicit relationship overlay to the existing mixed status,
  // claim, Monitor and User-gate fixture; do not replace it with a small mock.
  const rows = records.map(r => row(r.todo_id as string, {done: r.done === true}));
  const root = fixture.completion_todo_id;
  const parent = rows[0].todo_id as string;
  rows[0].successor_todo_ids = [root];
  rows[1].successor_todo_ids = [parent];
  rows.find(r => r.todo_id === root)!.resume_when = `monitor_changed:${rows[2].todo_id}`;
  const result = graph(rows, {selected_todo_id: root});
  assert.equal((result.predecessor_todo_ids as string[]).length, 3);
  assert.deepEqual(new Set((result.edges as JsonObject[]).map(e => e.enforcement)),
    new Set(["lineage_only", "typed_condition"]));
  assert.equal(JSON.stringify(fixture.projection), before);
});
