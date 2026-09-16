import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTHORITY_STATE_CHECKPOINT_INTERVAL,
  AUTHORITY_STATE_DELTA_SCHEMA,
  applyAuthorityStateDelta,
  authorityStateCheckpointCursor,
  authorityStateDelta,
  authorityStateDeltaReconstructs,
  authorityStateDigest,
  authorityStateReplayBudget,
  decodeAuthorityStateDelta,
  isAuthorityStateCheckpoint,
} from "../../loopx/control_plane/coordination/authority_state_log.ts";
import {canonicalAuthorityBytes} from
  "../../loopx/control_plane/coordination/authority_store_codec.ts";

test("authority state deltas reconstruct every committed projection exactly", () => {
  const previous = {
    authority_revision: 3,
    todos: [{todo_id: "a", status: "open"}, {todo_id: "b", status: "open"},
      {todo_id: "c", status: "done"}],
    leases: [],
    nested: {scope: {key: "goal", depth: {value: 1}}},
  };
  const next = {
    authority_revision: 4,
    todos: [{todo_id: "a", status: "done"}, {todo_id: "b", status: "open"},
      {todo_id: "c", status: "done"}, {todo_id: "d", status: "open"}],
    leases: [{todo_id: "a", version: 2}],
    nested: {scope: {key: "goal"}},
  };
  const delta = authorityStateDelta(previous, next);
  assert.equal(delta.schema_version, AUTHORITY_STATE_DELTA_SCHEMA);
  assert.deepEqual(applyAuthorityStateDelta(previous, delta), next);
  assert.deepEqual(authorityStateDelta(next, next).operations, []);
  assert.deepEqual(applyAuthorityStateDelta(next, authorityStateDelta(next, next)), next);
  // Field edits recurse, so an unrelated field never rewrites whole subtrees.
  const fieldEdit = authorityStateDelta(previous, {...previous, authority_revision: 9});
  assert.deepEqual(fieldEdit.operations, [{op: "set", path: ["authority_revision"], value: 9}]);
  // One changed record inside a record array stays one bounded splice.
  const large = {todos: Array.from({length: 64}, (_unused, index) => ({todo_id: `t-${index}`, step: 0}))};
  const added = {...large, todos: large.todos.map((todo, index) =>
    index === 20 ? {...todo, step: 1} : todo)};
  const spliced = authorityStateDelta(large, added);
  assert.equal(spliced.operations.length, 1);
  assert.equal(spliced.operations[0]!.op, "splice");
  assert.deepEqual(applyAuthorityStateDelta(large, spliced), added);
});

test("authority state delta decoding fails closed at the storage boundary", () => {
  const previous = {a: {b: 1}, list: [1, 2, 3]};
  const delta = (operations: unknown): Record<string, unknown> =>
    ({schema_version: AUTHORITY_STATE_DELTA_SCHEMA, operations});
  const rejected: unknown[] = [
    {schema_version: "authority_state_delta_v1", operations: []},
    {...delta([]), extra: true},
    {...delta([]), schema_version: 7},
    delta([{op: "merge", path: ["a"]}]),
    delta([{op: "set", path: [], value: 1}]),
    delta([{op: "set", path: ["a", 0], value: 1}]),
    delta([{op: "set", path: ["a"], value: 1, extra: 2}]),
    delta([{op: "splice", path: ["list"], index: -1, remove: 0, insert: []}]),
    delta([{op: "splice", path: ["list"], index: 0, remove: 0}]),
    delta(["not-an-operation"]),
    {schema_version: AUTHORITY_STATE_DELTA_SCHEMA},
  ];
  for (const value of rejected) {
    assert.throws(() => decodeAuthorityStateDelta(value), /delta|operation|path|splice/u,
      `delta ${JSON.stringify(value)} was accepted`);
    assert.throws(() => applyAuthorityStateDelta(previous, value as never), /delta|operation|path|splice/u);
  }
  // Structurally valid deltas that do not describe this state are refused when
  // they are applied instead of silently producing a partial projection.
  const removable = decodeAuthorityStateDelta(delta([{op: "remove", path: ["a"]}]));
  assert.deepEqual(applyAuthorityStateDelta(previous, removable), {list: [1, 2, 3]});
  // One past the end is a legal append, not an out-of-range splice.
  assert.deepEqual(applyAuthorityStateDelta(previous,
    decodeAuthorityStateDelta(delta([{op: "splice", path: ["list"], index: 3, remove: 0, insert: [4]}]))),
  {a: {b: 1}, list: [1, 2, 3, 4]});
  const inapplicable: unknown[] = [
    delta([{op: "remove", path: ["absent"]}]),
    delta([{op: "splice", path: ["a"], index: 0, remove: 0, insert: []}]),
    delta([{op: "splice", path: ["list"], index: 2, remove: 2, insert: []}]),
    delta([{op: "splice", path: ["list"], index: 4, remove: 0, insert: [4]}]),
    delta([{op: "set", path: ["missing", "leaf"], value: 1}]),
  ];
  for (const value of inapplicable) {
    const decoded = decodeAuthorityStateDelta(value);
    assert.throws(() => applyAuthorityStateDelta(previous, decoded), /path|splice|never stored/u);
    assert.throws(() => applyAuthorityStateDelta({other: 1}, decoded), /path|splice|never stored/u);
  }
});

test("the reconstruction rule answers for every JSON object key and a broken delta", () => {
  // One owner decides "this delta rebuilds exactly this projection" for both
  // the live writer and the V1 migration, so this test is about the rule's own
  // contract: it answers for a projection keyed with `""` or `__proto__`, and a
  // delta that cannot be decoded or applied is a failed reconstruction rather
  // than a thrown error or a partial state.
  const special = JSON.parse(
    '{"": {"marker": "empty"}, "__proto__": {"marker": "proto"}, "todos": [{"id": "a"}]}',
  ) as Record<string, unknown>;
  const nested = JSON.parse('{"scope": {"": {"__proto__": {"depth": 1}}}}') as Record<string, unknown>;
  for (const projection of [{}, special, nested]) {
    assert.equal(authorityStateDeltaReconstructs({}, authorityStateDelta({}, projection), projection), true);
  }
  // A delta that decodes but describes a different projection is a failed
  // reconstruction, not a different outcome the caller has to interpret.
  const mismatched = decodeAuthorityStateDelta({schema_version: AUTHORITY_STATE_DELTA_SCHEMA,
    operations: [{op: "set", path: ["a"], value: 2}]});
  assert.equal(authorityStateDeltaReconstructs({}, mismatched, {a: 1}), false);
  assert.equal(authorityStateDeltaReconstructs({}, mismatched, {a: 2}), true);
  assert.equal(authorityStateDeltaReconstructs({}, mismatched, {}), false);
  // An undecodable delta, and a delta whose path leaves the previous state,
  // both fail closed through the same answer instead of propagating.
  const undecodable = {schema_version: AUTHORITY_STATE_DELTA_SCHEMA,
    operations: [{op: "set", path: [], value: 1}]} as never;
  assert.equal(authorityStateDeltaReconstructs({}, undecodable, {}), false);
  const missingPath = decodeAuthorityStateDelta({schema_version: AUTHORITY_STATE_DELTA_SCHEMA,
    operations: [{op: "splice", path: ["absent"], index: 0, remove: 0, insert: []}]});
  assert.equal(authorityStateDeltaReconstructs({}, missingPath, {}), false);
});

test("authority state digests and checkpoint windows are stable and bounded", () => {
  const left = {b: 2, a: [1, {z: 1, y: 2}]};
  const right = {a: [1, {y: 2, z: 1}], b: 2};
  assert.equal(authorityStateDigest(left), authorityStateDigest(right));
  assert.notEqual(authorityStateDigest(left), authorityStateDigest({...left, b: 3}));
  assert.equal(AUTHORITY_STATE_CHECKPOINT_INTERVAL, 64);
  assert.equal(authorityStateReplayBudget(), AUTHORITY_STATE_CHECKPOINT_INTERVAL - 1);
  // Every commit in one window resumes from the same published checkpoint.
  for (let cursor = 1; cursor <= AUTHORITY_STATE_CHECKPOINT_INTERVAL; cursor += 1) {
    assert.equal(authorityStateCheckpointCursor(BigInt(cursor)), 1n);
  }
  assert.equal(authorityStateCheckpointCursor(65n), 65n);
  assert.equal(authorityStateCheckpointCursor(128n), 65n);
  assert.equal(authorityStateCheckpointCursor(129n), 129n);
  assert.equal(isAuthorityStateCheckpoint(1n), true);
  assert.equal(isAuthorityStateCheckpoint(64n), false);
  assert.throws(() => authorityStateCheckpointCursor(0n), /checkpoint cursor/u);
});

test("authority state deltas keep every JSON key the stored projection could carry", () => {
  // V1 retained a whole projection per commit, so every JSON object key was
  // legal legacy input. The delta codec inherits that contract: an empty key
  // is an ordinary key, and a `__proto__` key is stored data instead of the
  // inherited accessor. Keys that only existed in V1 data would otherwise be
  // copied into the new format and fail on the first read.
  const text = (value: unknown): string => canonicalAuthorityBytes(value).toString("utf8");
  const stored = (previous: unknown, next: unknown): unknown => JSON.parse(
    JSON.stringify(authorityStateDelta(previous as never, next as never))) as unknown;

  const previous = JSON.parse('{"": {"empty": true}, "__proto__": {"own": 1}, "todos": []}') as
    Record<string, unknown>;
  const next = JSON.parse('{"": {"empty": false}, "__proto__": {"own": 2},' +
    ' "nested": {"__proto__": {"deep": true}}, "todos": [{"todo_id": "todo-0"}]}') as
    Record<string, unknown>;
  const applied = applyAuthorityStateDelta(previous, decodeAuthorityStateDelta(stored(previous, next)));
  assert.equal(text(applied), text(next));
  // The reconstruction is an ordinary JSON object: `__proto__` stayed a key.
  assert.equal(Object.getPrototypeOf(applied), Object.prototype);
  assert.deepEqual(Object.keys(applied).sort(), ["", "__proto__", "nested", "todos"]);
  assert.deepEqual(applied[""], {empty: false});
  assert.deepEqual(applied["__proto__"], {own: 2});
  assert.deepEqual(applied["nested"], {["__proto__"]: {deep: true}});

  // Removing a legacy key is legal too, including the empty key and a key that
  // the previous state only carried inside a nested object.
  const trimmed = JSON.parse('{"nested": {}, "todos": []}') as Record<string, unknown>;
  const removal = applyAuthorityStateDelta(next, decodeAuthorityStateDelta(stored(next, trimmed)));
  assert.equal(text(removal), text(trimmed));
  assert.deepEqual(Object.keys(removal).sort(), ["nested", "todos"]);
  assert.equal(Object.hasOwn(removal, "__proto__"), false);

  // A legacy key the delta has to create is an own data property as well.
  const legacyText = '{"__proto__": {"own": 1}, "": 0}';
  const created = applyAuthorityStateDelta({},
    decodeAuthorityStateDelta(stored({}, JSON.parse(legacyText) as Record<string, unknown>)));
  assert.equal(text(created), text(JSON.parse(legacyText)));
  assert.equal(Object.getPrototypeOf(created), Object.prototype);
});
