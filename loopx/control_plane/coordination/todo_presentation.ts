import type { JsonObject } from "../effect_program.ts";
import {
  authorityUnicodeCompare,
  canonicalAuthorityObject,
} from "./authority_store_codec.ts";
import {
  canonicalCoordinationTodoRecord,
  canonicalTodoDomainRecord,
  TODO_CANONICAL_READ_RECORD_SCHEMA,
  TODO_DOMAIN_ITEM_SCHEMA,
  TODO_DOMAIN_READ_RECORD_SCHEMA,
  TODO_ITEM_SCHEMA,
} from "./coordination_state_contract.ts";

export const TODO_PRESENTATION_METADATA_SCHEMA =
  "loopx_todo_presentation_metadata_v0";

/** The index is provenance from the v0 wire shape, not a second domain rule. */
export type TodoPresentationOrderSource = "source_index" | "legacy_index" | "todo_id";

export interface TodoPresentationMetadata extends JsonObject {
  readonly schema_version: typeof TODO_PRESENTATION_METADATA_SCHEMA;
  readonly todo_id: string;
  readonly display_section: string;
  readonly display_order: number | null;
  readonly order_source: TodoPresentationOrderSource;
}

function defaultDisplaySection(todo: JsonObject): string {
  if (todo.archive_state === "archive") return "Completed Work Archive";
  return todo.role === "agent" ? "Agent Todo" : "User Todo";
}

function sourceDisplayOrder(todo: JsonObject): number | null {
  return Number.isSafeInteger(todo.index) && Number(todo.index) >= 0
    ? Number(todo.index)
    : null;
}

/**
 * Return the canonical presentation facts for one authority Todo.
 *
 * `source_section`/`index` are the v0 wire shape's canonical display
 * coordinates. Native records derive the same display section from domain
 * state and deliberately do not receive a fake persisted index. Rendering
 * code may allocate a transient position later.
 */
export function todoPresentationMetadata(
  value: JsonObject,
  label = "Todo presentation metadata",
): TodoPresentationMetadata {
  // Selection/renderer callers may pass a compact, already-decoded row with
  // no schema marker. Treat that as legacy-compatible display input, while
  // still rejecting an explicit unknown version.
  const isLegacy = value.schema_version === TODO_ITEM_SCHEMA ||
    value.schema_version === undefined || value.schema_version === null;
  const isNative = value.schema_version === TODO_DOMAIN_ITEM_SCHEMA;
  if (!isLegacy && !isNative) {
    throw new TypeError(`${label} has unsupported Todo schema`);
  }
  const displaySection = isLegacy && typeof value.source_section === "string" &&
      value.source_section.trim().length > 0
    ? value.source_section
    : defaultDisplaySection(value);
  const displayOrder = isLegacy ? sourceDisplayOrder(value) : null;
  return canonicalAuthorityObject({
    schema_version: TODO_PRESENTATION_METADATA_SCHEMA,
    todo_id: value.todo_id,
    display_section: displaySection,
    display_order: displayOrder,
    order_source: displayOrder === null ? "todo_id" : "source_index",
  }, label) as TodoPresentationMetadata;
}

/** Validate either persisted wire shape through its shared domain contract. */
export function canonicalTodoRecord(
  value: unknown,
  label = "coordination Todo record",
): JsonObject {
  const record = canonicalAuthorityObject(value, label);
  if (record.schema_version === TODO_DOMAIN_ITEM_SCHEMA) {
    return canonicalTodoDomainRecord(record, label);
  }
  if (record.schema_version === TODO_ITEM_SCHEMA) {
    return canonicalCoordinationTodoRecord(record, label);
  }
  throw new TypeError(`${label} has unsupported Todo schema`);
}

/**
 * Materialize one domain record for a selected read-model wire shape.
 * Domain fields are validated once; presentation provenance is added only
 * at the legacy boundary.
 */
export function materializeTodoRecordForSchema(
  value: JsonObject,
  readModelSchema: unknown,
  label = "coordination Todo record",
): JsonObject {
  const domain = canonicalTodoDomainRecord(value, label);
  if (readModelSchema === TODO_DOMAIN_READ_RECORD_SCHEMA) return domain;
  if (readModelSchema !== TODO_CANONICAL_READ_RECORD_SCHEMA) {
    throw new TypeError(`${label} read-model schema is unsupported`);
  }
  return canonicalCoordinationTodoRecord({
    ...domain,
    schema_version: TODO_ITEM_SCHEMA,
    source_section: defaultDisplaySection(domain),
  }, label);
}

function timestamp(value: JsonObject): string {
  return typeof value.completed_at === "string"
    ? value.completed_at
    : typeof value.updated_at === "string" ? value.updated_at : "";
}

/** Stable display ordering that preserves source display coordinates explicitly. */
export function compareTodoPresentation(
  left: JsonObject,
  right: JsonObject,
): number {
  const leftMetadata = todoPresentationMetadata(left);
  const rightMetadata = todoPresentationMetadata(right);
  if (leftMetadata.display_order !== null || rightMetadata.display_order !== null) {
    if (leftMetadata.display_order === null) return 1;
    if (rightMetadata.display_order === null) return -1;
    if (leftMetadata.display_order !== rightMetadata.display_order) {
      return leftMetadata.display_order - rightMetadata.display_order;
    }
  }
  const leftTime = timestamp(left);
  const rightTime = timestamp(right);
  if (leftTime !== rightTime) return authorityUnicodeCompare(leftTime, rightTime);
  return authorityUnicodeCompare(String(left.todo_id), String(right.todo_id));
}
