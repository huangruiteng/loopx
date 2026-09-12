import assert from "node:assert/strict";
import test from "node:test";
import {deflateSync} from "node:zlib";
import {projectAdvancementFrontier, evaluateLongTodoChain} from "../../loopx/control_plane/todos/frontier_revision.ts";

function row(id: string, claim: string | null = null, excluded: string[] = []) {
  return {id, claim, excluded, advancement: true, updated: "2026-09-01T00:00:00.000001Z",
    serialized: JSON.stringify({task_class: "advancement_task", todo_id: id})};
}
function project(rows: ReturnType<typeof row>[], agent_id: string | null = null) {
  return projectAdvancementFrontier({schema_version: "todo_frontier_revision_request_v0",
    operation: "select", rows, agent_id}).checkpoint as Record<string, unknown>;
}
function observe(overrides: Record<string, unknown> = {}) {
  return evaluateLongTodoChain({schema_version: "long_todo_chain_request_v0", operation: "observe",
    agent_id: "worker-a", summary: {current_agent_claimed_open_count: 15, unclaimed_open_count: 0},
    frontier_counts: {current_agent_claimed_advancement_count: 15, unclaimed_advancement_count: 0},
    rows: [row("todo_a", "worker-a")], ...overrides});
}

test("lossless compressed rows preserve index and ACK semantics and reject malformed transport", () => {
  const rows = [row("todo_a", "worker-a"), row("todo_b", null, ["worker-a"])];
  const compressed = {encoding: "deflate-base64-json-v0",
    data: deflateSync(JSON.stringify(rows)).toString("base64")};
  for (const operation of ["index", "select"]) {
    const request = {schema_version: "todo_frontier_revision_request_v0", operation, agent_id: "worker-a"};
    assert.deepEqual(projectAdvancementFrontier({...request, rows: compressed}),
      projectAdvancementFrontier({...request, rows}));
  }
  assert.deepEqual(observe({rows: compressed}), observe({rows}));
  for (const invalid of [
    {...compressed, encoding: "unknown"}, {...compressed, data: "!"},
    {...compressed, data: "AAAA"},
    {...compressed, data: deflateSync("{}").toString("base64")},
    {...compressed, data: deflateSync("x".repeat(64 * 1024 * 1024 + 1)).toString("base64")},
  ]) {
    assert.throws(() => projectAdvancementFrontier({schema_version: "todo_frontier_revision_request_v0",
      operation: "index", rows: invalid}));
  }
});

test("revision is order-independent and maintenance timestamps do not change material identity", () => {
  const rows = [row("todo_b"), row("todo_a")];
  assert.deepEqual(project(rows), project([...rows].reverse()));
  const changed = [{...rows[0], updated: "2026-09-02T00:00:00Z"}, rows[1]];
  assert.equal(project(rows).frontier_revision, project(changed).frontier_revision);
  assert.notEqual(project(rows).frontier_updated_at, project(changed).frontier_updated_at);
});

test("excluded-only agents receive an explicit checkpoint instead of the unclaimed fallback", () => {
  const rows = [row("todo_a"), row("todo_b", null, ["worker-a"])];
  const index = projectAdvancementFrontier({schema_version: "todo_frontier_revision_request_v0",
    operation: "index", rows}).index;
  const read = projectAdvancementFrontier({schema_version: "todo_frontier_revision_request_v0",
    operation: "read", index, agent_id: "worker-a"}).checkpoint;
  assert.deepEqual(read, project([rows[0]], "worker-a"));
  assert.notDeepEqual(read, project(rows));
});

test("duplicate identities and malformed or absent revision facts cannot authorize an ACK", () => {
  for (const rows of [[], [row("todo_a"), row("todo_a")], [{...row("todo_a"), updated: "bad"}]]) {
    assert.deepEqual(project(rows), {complete: false});
  }
  const result = observe({summary: {advancement_frontier_revision_index: {schema_version: "bad"}}});
  assert.equal((result.observation as Record<string, unknown>).frontier_revision_complete, false);
  assert.deepEqual(result.decision, {acknowledged: false, rearmed_after_obligation_id: null});
});

test("long-chain thresholds remain 15 advancement or 20 selectable with advancement", () => {
  assert.notEqual(observe().observation, null);
  assert.equal(observe({frontier_counts: {current_agent_claimed_advancement_count: 14}}).observation, null);
  const open = {current_agent_claimed_open_count: 20, unclaimed_open_count: 0};
  assert.notEqual(observe({summary: open, frontier_counts: {unclaimed_advancement_count: 1}}).observation, null);
  assert.equal(observe({summary: open, frontier_counts: {}}).observation, null);
});

test("only exact accepted checkpoint suppresses a repeated trigger; material change rearms", () => {
  const observation = observe().observation as Record<string, unknown>;
  const ack = {recorded: true, semantic_delta: {accepted: true, obligation_id: "replan-0123456789abcdef",
    trigger_kinds: ["long_todo_chain"], trigger_checkpoints: [{kind: "long_todo_chain",
      frontier_revision: observation.frontier_revision}]}};
  assert.deepEqual(observe({ack}).decision, {acknowledged: true, rearmed_after_obligation_id: null});
  assert.deepEqual(observe({ack, rows: [row("todo_new", "worker-a")]}).decision,
    {acknowledged: false, rearmed_after_obligation_id: "replan-0123456789abcdef"});
  for (const invalid of [null, {...ack, recorded: false}, {...ack, semantic_delta: {...ack.semantic_delta,
    accepted: false}}, {...ack, semantic_delta: {...ack.semantic_delta, trigger_kinds: "long_todo_chain"}}]) {
    assert.equal((observe({ack: invalid}).decision as Record<string, unknown>).acknowledged, false);
  }
});

test("duplicate agent checkpoints fail closed instead of selecting the first receipt", () => {
  const entry = {agent_id: "worker-a", ...project([row("todo_a")])};
  const index = {schema_version: "todo_frontier_revision_index_v0", by_agent: [entry, entry]};
  assert.deepEqual(projectAdvancementFrontier({schema_version: "todo_frontier_revision_request_v0",
    operation: "read", index, agent_id: "worker-a"}).checkpoint, {complete: false});
});

test("the typed transport rejects unsupported operations and missing source codec facts", () => {
  assert.throws(() => projectAdvancementFrontier({schema_version: "old"}));
  assert.throws(() => projectAdvancementFrontier({schema_version: "todo_frontier_revision_request_v0",
    operation: "index", rows: [{}]}));
  assert.throws(() => evaluateLongTodoChain({schema_version: "long_todo_chain_request_v0", operation: "unknown"}));
});
