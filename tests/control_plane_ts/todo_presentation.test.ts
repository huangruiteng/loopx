import assert from "node:assert/strict";
import test from "node:test";

import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import {
  TODO_CANONICAL_READ_RECORD_SCHEMA,
  TODO_DOMAIN_ITEM_SCHEMA,
  TODO_DOMAIN_READ_RECORD_SCHEMA,
  TODO_ITEM_SCHEMA,
} from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import {
  canonicalTodoRecord,
  compareTodoPresentation,
  materializeTodoRecordForSchema,
  TODO_PRESENTATION_METADATA_SCHEMA,
  todoPresentationMetadata,
} from "../../loopx/control_plane/coordination/todo_presentation.ts";
import {productionScaleCoordinationFixture} from "./production_scale_coordination_fixture.ts";

function domainTodo(overrides: JsonObject = {}): JsonObject {
  return {
    schema_version: TODO_DOMAIN_ITEM_SCHEMA,
    todo_id: "todo-a",
    role: "agent",
    status: "open",
    done: false,
    text: "Canonical display contract",
    archive_state: "active",
    ...overrides,
  };
}

test("presentation metadata treats source location as display input", () => {
  const legacy = {
    ...domainTodo({schema_version: TODO_ITEM_SCHEMA}),
    source_section: "Custom Agent Lane",
    index: 7,
  };
  assert.deepEqual(todoPresentationMetadata(legacy), {
    schema_version: TODO_PRESENTATION_METADATA_SCHEMA,
    todo_id: "todo-a",
    display_section: "Custom Agent Lane",
    display_order: 7,
    order_source: "source_index",
  });
});

test("native records derive display section without persisting a fake index", () => {
  const native = domainTodo({archive_state: "archive"});
  assert.deepEqual(todoPresentationMetadata(native), {
    schema_version: "loopx_todo_presentation_metadata_v0",
    todo_id: "todo-a",
    display_section: "Completed Work Archive",
    display_order: null,
    order_source: "todo_id",
  });
  assert.deepEqual(
    materializeTodoRecordForSchema(native, TODO_DOMAIN_READ_RECORD_SCHEMA),
    native,
  );
});

test("wire-shape materialization is an adapter, not a second domain construction", () => {
  const native = domainTodo();
  const legacy = materializeTodoRecordForSchema(
    native,
    TODO_CANONICAL_READ_RECORD_SCHEMA,
  );
  assert.equal(legacy.schema_version, TODO_ITEM_SCHEMA);
  assert.equal(legacy.source_section, "Agent Todo");
  assert.equal(legacy.index, undefined);
  assert.doesNotThrow(() => canonicalTodoRecord(legacy));
});

test("presentation ordering keeps source coordinates and native time fallback", () => {
  const legacyFirst = {
    ...domainTodo({schema_version: TODO_ITEM_SCHEMA, todo_id: "todo-first"}),
    source_section: "Agent Todo",
    index: 1,
    completed_at: "2026-09-10T10:00:00Z",
  };
  const legacySecond = {
    ...domainTodo({schema_version: TODO_ITEM_SCHEMA, todo_id: "todo-second"}),
    source_section: "Agent Todo",
    index: 2,
    completed_at: "2026-09-10T09:00:00Z",
  };
  assert.equal(compareTodoPresentation(legacyFirst, legacySecond) < 0, true);

  const nativeFirst = domainTodo({todo_id: "todo-first", updated_at: "2026-09-10T10:00:00Z"});
  const nativeSecond = domainTodo({todo_id: "todo-second", updated_at: "2026-09-10T09:00:00Z"});
  assert.equal(compareTodoPresentation(nativeFirst, nativeSecond) > 0, true);
});

test("compact compatibility rows may encode omitted schema fields as null", () => {
  const compact = {
    schema_version: null,
    todo_id: "todo-compact",
    role: "user",
    status: "done",
    archive_state: "active",
    source_section: null,
    index: null,
  };
  assert.deepEqual(todoPresentationMetadata(compact), {
    schema_version: TODO_PRESENTATION_METADATA_SCHEMA,
    todo_id: "todo-compact",
    display_section: "User Todo",
    display_order: null,
    order_source: "todo_id",
  });
});

test("production fixture carries one display contract for both wire shapes", () => {
  const fixture = productionScaleCoordinationFixture("fixture-goal");
  const cases = fixture.presentation_cases;
  assert.deepEqual(todoPresentationMetadata(cases.legacy_display), {
    schema_version: TODO_PRESENTATION_METADATA_SCHEMA,
    todo_id: "todo_fixture_display_legacy",
    display_section: "Agent Todo",
    display_order: 7,
    order_source: "source_index",
  });
  assert.deepEqual(todoPresentationMetadata(cases.native_display), {
    schema_version: TODO_PRESENTATION_METADATA_SCHEMA,
    todo_id: "todo_fixture_display_native",
    display_section: "Completed Work Archive",
    display_order: null,
    order_source: "todo_id",
  });
});
