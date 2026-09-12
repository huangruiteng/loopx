/** Typed decision metadata for ordinary Todo planning updates.
 *
 * Decision outcomes remain terminal/effect-owned.  This module only validates
 * the two declarative fields that describe who may be waiting on what: a
 * user-gate decision_scope and an agent Todo's required_decision_scopes.
 */
import type {JsonObject} from "../effect_program.ts";
import {EffectRuntimeRequestError} from "../effect_runtime_errors.ts";
import {requireJsonObject} from "../runtime_decode.ts";
import {normalizeTodoId} from "../work_items/task_lease_acquire.ts";
import {compactPythonWhitespace, stripPythonWhitespace} from "../coordination/todo_agents.ts";

export const TODO_DECISION_SCOPE_SCHEMA_VERSION = "decision_scope_v0";
export const TODO_DECISION_SCOPE_KINDS = [
  "private_read", "write_scope", "resource", "production", "public_claim", "direction", "other",
] as const;
export const TODO_DECISION_SCOPE_GRANULARITIES = ["action", "lane", "goal", "project", "global"] as const;
export const TODO_DECISION_SCOPE_KIND_SET: ReadonlySet<string> = new Set(TODO_DECISION_SCOPE_KINDS);
export const TODO_DECISION_SCOPE_GRANULARITY_SET: ReadonlySet<string> = new Set(TODO_DECISION_SCOPE_GRANULARITIES);
export const TODO_DECISION_SCOPE_KEY_PATTERN = /^(?:\*|[a-z0-9][a-z0-9_.:@*/-]{0,95})$/u;

export const TODO_DECISION_METADATA_FIELDS = ["decision_scope", "required_decision_scopes"] as const;

export interface TodoDecisionScope extends JsonObject {
  readonly schema_version: typeof TODO_DECISION_SCOPE_SCHEMA_VERSION;
  readonly kind: string;
  readonly granularity: string;
  readonly scope_key: string;
  readonly decision_id?: string;
}

function fail(message: string): never {
  throw new EffectRuntimeRequestError(message);
}

function scopeObject(value: unknown, label: string): JsonObject {
  if (typeof value === "string") {
    const parts = compactPythonWhitespace(value).toLowerCase().split(":");
    if (parts.length < 3) fail(`${label} must use kind:granularity:scope_key`);
    return {kind: parts[0], granularity: parts[1], scope_key: parts.slice(2).join(":")};
  }
  return requireJsonObject(value, label);
}

/** Normalize one public decision-scope value without preserving unknown keys. */
export function normalizeTodoDecisionScope(value: unknown, label = "decision_scope"): TodoDecisionScope | null {
  if (value === null || value === undefined) return null;
  const raw = scopeObject(value, label);
  const unknown = Object.keys(raw).filter(key =>
    !["schema_version", "kind", "granularity", "scope_key", "decision_id"].includes(key));
  if (unknown.length) fail(`${label} has unsupported fields: ${unknown.sort().join(", ")}`);
  if (raw.schema_version !== undefined && raw.schema_version !== TODO_DECISION_SCOPE_SCHEMA_VERSION) {
    fail(`${label}.schema_version must be ${TODO_DECISION_SCOPE_SCHEMA_VERSION}`);
  }
  const kind = typeof raw.kind === "string" ? compactPythonWhitespace(raw.kind).toLowerCase() : "";
  const granularity = typeof raw.granularity === "string"
    ? compactPythonWhitespace(raw.granularity).toLowerCase() : "";
  const scopeKey = typeof raw.scope_key === "string"
    ? compactPythonWhitespace(raw.scope_key).toLowerCase() : "";
  if (!TODO_DECISION_SCOPE_KIND_SET.has(kind)) fail(`${label}.kind is not a supported decision-scope kind`);
  if (!TODO_DECISION_SCOPE_GRANULARITY_SET.has(granularity)) {
    fail(`${label}.granularity is not a supported decision-scope granularity`);
  }
  if (!TODO_DECISION_SCOPE_KEY_PATTERN.test(scopeKey)) {
    fail(`${label}.scope_key must be a public-safe decision-scope key`);
  }
  const result: JsonObject = {
    schema_version: TODO_DECISION_SCOPE_SCHEMA_VERSION, kind, granularity, scope_key: scopeKey,
  };
  if (raw.decision_id !== undefined) {
    if (typeof raw.decision_id !== "string" || stripPythonWhitespace(raw.decision_id) !== raw.decision_id) {
      fail(`${label}.decision_id must be a public-safe Todo id`);
    }
    result.decision_id = normalizeTodoId(raw.decision_id, `${label}.decision_id`);
  }
  return result as TodoDecisionScope;
}

function identity(scope: TodoDecisionScope): string {
  return `${scope.kind}\u0000${scope.granularity}\u0000${scope.scope_key}`;
}

/** Normalize the list form while preserving first-seen order and removing exact duplicates. */
export function normalizeTodoRequiredDecisionScopes(
  value: unknown,
  label = "required_decision_scopes",
): TodoDecisionScope[] | null {
  if (value === null || value === undefined) return null;
  const rawValues = typeof value === "string"
    ? compactPythonWhitespace(value).split(/[,;|]/u).filter(Boolean)
    : value;
  if (!Array.isArray(rawValues)) fail(`${label} must be an array or compact scope list`);
  const result: TodoDecisionScope[] = [];
  const seen = new Set<string>();
  rawValues.forEach((raw, index) => {
    let scope: TodoDecisionScope | null;
    try {
      scope = normalizeTodoDecisionScope(raw, `${label}[${index}]`);
    } catch (error) {
      // Keep the legacy CLI's aggregate validation contract while retaining
      // the offending index for native callers and diagnostics.
      const detail = error instanceof Error ? ` (${error.message})` : "";
      const aggregateLabel = label.replace(/\[\d+\]$/u, "");
      fail(`${aggregateLabel} must contain kind:granularity:scope_key tokens; invalid item ${index}${detail}`);
    }
    if (scope === null) fail(`${label}[${index}] must be a decision scope`);
    const key = identity(scope);
    if (!seen.has(key)) {
      seen.add(key);
      result.push(scope);
    }
  });
  return result;
}

/** Validate role ownership for ordinary planning edits; no permission is granted here. */
export function validateTodoDecisionMetadata(todo: JsonObject, intent: JsonObject): JsonObject {
  const role = todo.role;
  const taskClass = Object.hasOwn(intent, "task_class")
    ? intent.task_class : todo.task_class;
  if (Object.hasOwn(intent, "decision_scope")) {
    if (intent.decision_scope !== null && (role !== "user" || taskClass !== "user_gate")) {
      fail("decision_scope is only valid for user_gate todos");
    }
  }
  if (Object.hasOwn(intent, "required_decision_scopes")) {
    if (role !== "agent" && intent.required_decision_scopes !== null) {
      fail("required_decision_scopes is only valid for agent todos");
    }
  }
  return {};
}
