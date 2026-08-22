import type { JsonObject } from "../effect_program.ts";
import {
  requireBoolean,
  requireJsonObject,
  requireStringLiteral,
} from "../runtime_decode.ts";
import {
  evaluateTodoCompletionFence,
  TODO_COMPLETION_FENCE_REQUEST_SCHEMA,
  type TodoCompletionProjectionSource,
} from "./completion_fence.ts";

export const TODO_COMPLETION_VALIDATION_PLAN_REQUEST_SCHEMA =
  "loopx_todo_completion_validation_plan_request_v0";
export const TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA =
  "loopx_todo_completion_validation_plan_result_v0";

export type TodoCompletionValidationPlanResult =
  | (JsonObject & {
      schema_version: typeof TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA;
      effect: "skip";
      reason: "dry_run" | "no_declaration" | "terminal_replay";
    })
  | (JsonObject & {
      schema_version: typeof TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA;
      effect: "run";
      reason: "declared_validation";
      validation_command: string | null;
      validation_argv: readonly string[] | null;
      validation_label: string | null;
      validation_timeout_seconds: number | null;
    })
  | (JsonObject & {
      schema_version: typeof TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA;
      effect: "reject";
      reason: "invalid_declaration";
      status: "declaration_invalid";
      validation_label: string | null;
      summary: string;
    });

function projectionSource(value: unknown): TodoCompletionProjectionSource {
  return requireStringLiteral(
    value,
    ["materialized", "event_log"] as const,
    "projection_source",
  );
}

function optionalOpaqueString(value: unknown, label: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") {
    throw new Error(`${label} must be a string or null`);
  }
  return value;
}

function compactString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const compact = value.trim();
  return compact === "" ? null : compact;
}

function invalidDeclaration(
  summary: string,
  validationLabel: string | null,
): TodoCompletionValidationPlanResult {
  return {
    schema_version: TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA,
    effect: "reject",
    reason: "invalid_declaration",
    status: "declaration_invalid",
    validation_label: validationLabel,
    summary,
  };
}

function validationTimeoutSeconds(
  value: unknown,
): { ok: true; value: number | null } | { ok: false; summary: string } {
  if (value === null || value === undefined || value === "") {
    return { ok: true, value: null };
  }
  if (
    typeof value === "number" &&
    Number.isInteger(value) &&
    Number.isSafeInteger(value)
  ) {
    if (value >= 1 && value <= 29) return { ok: true, value };
    return {
      ok: false,
      summary: "validation_timeout_seconds must be an integer between 1 and 29",
    };
  }
  if (typeof value === "string" && /^[0-9]+$/.test(value.trim())) {
    const parsed = Number(value.trim());
    if (parsed >= 1 && parsed <= 29) return { ok: true, value: parsed };
    return {
      ok: false,
      summary: "validation_timeout_seconds must be an integer between 1 and 29",
    };
  }
  return {
    ok: false,
    summary: "validation_timeout_seconds must be an integer between 1 and 29",
  };
}

function validationArgv(
  value: unknown,
): { ok: true; value: readonly string[] | null } | { ok: false; summary: string } {
  if (value === null || value === undefined || value === "") {
    return { ok: true, value: null };
  }
  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return {
        ok: false,
        summary: "validation_command_argv must be a non-empty string array",
      };
    }
  }
  if (
    Array.isArray(parsed) &&
    parsed.length > 0 &&
    parsed.every((item) => typeof item === "string" && item.length > 0)
  ) {
    return { ok: true, value: [...parsed] };
  }
  return {
    ok: false,
    summary: "validation_command_argv must be a non-empty string array",
  };
}

export function evaluateTodoCompletionValidationPlan(
  value: unknown,
): TodoCompletionValidationPlanResult {
  const request = requireJsonObject(
    value,
    "todo.completion_validation_plan params",
  );
  if (request.schema_version !== TODO_COMPLETION_VALIDATION_PLAN_REQUEST_SCHEMA) {
    throw new Error("Todo completion validation plan request schema mismatch");
  }
  const todo = requireJsonObject(
    request.todo,
    "todo.completion_validation_plan todo",
  );
  const dryRun = requireBoolean(request.dry_run, "dry_run");
  if (dryRun) {
    return {
      schema_version: TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA,
      effect: "skip",
      reason: "dry_run",
    };
  }

  const source = projectionSource(request.projection_source);
  const fence = evaluateTodoCompletionFence({
    schema_version: TODO_COMPLETION_FENCE_REQUEST_SCHEMA,
    projection_source: source,
    todo: {
      status: todo.status,
      no_followup: todo.no_followup,
      completion_continuation: todo.completion_continuation,
      completion_turn_key: todo.completion_turn_key,
      successor_todo_ids: todo.successor_todo_ids,
    },
    requested_no_followup: requireBoolean(
      request.requested_no_followup,
      "requested_no_followup",
    ),
    requested_completion_turn_key: optionalOpaqueString(
      request.requested_completion_turn_key,
      "requested_completion_turn_key",
    ),
    requested_completion_identity_source:
      request.requested_completion_identity_source,
    goal_id: request.goal_id,
    todo_id: request.todo_id,
  });
  if (fence.outcome === "replay") {
    return {
      schema_version: TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA,
      effect: "skip",
      reason: "terminal_replay",
    };
  }

  const validationLabel = optionalOpaqueString(
    todo.validation_label,
    "todo.validation_label",
  );
  const commandRaw = todo.validation_command;
  if (
    commandRaw !== null &&
    commandRaw !== undefined &&
    typeof commandRaw !== "string"
  ) {
    return invalidDeclaration(
      "validation_command must be a non-empty string when declared",
      validationLabel,
    );
  }
  const validationCommand = compactString(commandRaw);
  const argv = validationArgv(todo.validation_command_argv);
  if (!argv.ok) return invalidDeclaration(argv.summary, validationLabel);
  if (validationCommand !== null && argv.value !== null) {
    return invalidDeclaration(
      "validation_command and validation_command_argv are mutually exclusive",
      validationLabel,
    );
  }
  const timeout = validationTimeoutSeconds(todo.validation_timeout_seconds);
  if (!timeout.ok) return invalidDeclaration(timeout.summary, validationLabel);
  if (validationCommand === null && argv.value === null) {
    if (timeout.value !== null) {
      return invalidDeclaration(
        "validation_timeout_seconds requires a validation command declaration",
        validationLabel,
      );
    }
    return {
      schema_version: TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA,
      effect: "skip",
      reason: "no_declaration",
    };
  }

  return {
    schema_version: TODO_COMPLETION_VALIDATION_PLAN_RESULT_SCHEMA,
    effect: "run",
    reason: "declared_validation",
    validation_command: validationCommand,
    validation_argv: argv.value,
    validation_label: validationLabel,
    validation_timeout_seconds: timeout.value,
  };
}
