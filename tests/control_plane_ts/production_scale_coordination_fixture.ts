import {readFileSync} from "node:fs";

import {authorityUnicodeCompare, canonicalAuthoritySha256} from
  "../../loopx/control_plane/coordination/authority_store_codec.ts";
import {
  TODO_ITEM_SCHEMA,
} from "../../loopx/control_plane/coordination/coordination_state_contract.ts";
import {
  authorityProjectionFixture,
  projectionFixtureAsSchema,
  type AuthorityProjectionSchema,
} from "./authority_projection_fixture.ts";

const envelope = JSON.parse(readFileSync(new URL(
  "../fixtures/control_plane/coordination_production_scale_v0.json",
  import.meta.url,
), "utf8")) as {
  schema_version: string;
  agent_status_counts: Record<string, number>;
  user_status_counts: Record<string, number>;
  agent_status_order: string[];
  user_status_order: string[];
  current_lease_count: number;
  retired_lease_count: number;
  standing_user_decision_count: number;
  scoped_without_outcome_count: number;
  linked_decision_count: number;
  completion_target_index: number;
  supersede_target_index: number;
  semantic_cases: Record<string, Record<string, unknown>>;
  presentation_cases: Record<string, Record<string, unknown>>;
};

export const PRODUCTION_SCALE_FIXTURE_SCHEMA =
  "loopx_coordination_production_scale_fixture_v0";
export const PRODUCTION_SCALE_VALIDATION_DECLARATION = {
  validation_command: null,
  validation_command_argv: ["python3", "-c", "raise SystemExit(0)"],
  validation_label: "production-scale fixture validation",
  validation_timeout_seconds: 5,
};

export interface ProductionScaleCoordinationFixture {
  readonly projection: Record<string, unknown>;
  readonly registered_agents: readonly string[];
  readonly completion_todo_id: string;
  readonly supersede_todo_id: string;
  readonly completion_lease_idempotency_key: string;
  readonly completion_lease_expected_version: number;
  readonly supersede_lease_idempotency_key: string;
  readonly supersede_lease_expected_version: number;
  readonly expected_initial_todo_count: number;
  readonly expected_current_lease_count: number;
  readonly expected_agent_archive_count_after_terminals: number;
  readonly expected_user_archive_count: number;
  readonly expected_standing_user_decision_count: number;
  readonly semantic_cases: Readonly<Record<string, Record<string, unknown>>>;
  readonly presentation_cases: Readonly<Record<string, Record<string, unknown>>>;
}

function statusSeries(
  counts: Record<string, number>,
  order: readonly string[],
  role: string,
): string[] {
  const keys = Object.keys(counts).sort();
  const orderedKeys = [...order].sort();
  if (keys.length !== orderedKeys.length || keys.some((key, index) => key !== orderedKeys[index])) {
    throw new Error(`${role} production fixture status order does not cover its counts`);
  }
  return order.flatMap(status => {
    const count = counts[status];
    if (!Number.isSafeInteger(count) || count < 0) {
      throw new Error(`${role} production fixture count is not a non-negative safe integer`);
    }
    return Array.from({length: count}, () => status);
  });
}

function todoId(role: "agent" | "user", index: number): string {
  return `todo_fixture_${role}_${String(index).padStart(3, "0")}`;
}

function observedAt(index: number): string {
  return new Date(Date.UTC(2025, 0, 1, 0, index)).toISOString().replace(/\.\d{3}Z$/u, "Z");
}

function todoRecords(
  goalId: string,
  role: "agent" | "user",
  counts: Record<string, number>,
  order: readonly string[],
): Record<string, unknown>[] {
  return statusSeries(counts, order, role).map((status, index) => {
    const done = status === "done" || status === "deferred";
    const record: Record<string, unknown> = {
      schema_version: TODO_ITEM_SCHEMA,
      todo_id: todoId(role, index),
      role,
      status,
      done,
      text: `Synthetic ${role} Todo ${String(index).padStart(3, "0")}`,
      archive_state: "active",
      source_section: role === "agent" ? "Agent Todo" : "User Todo",
      index: index + 1,
      task_class: role === "agent"
        ? index % 4 === 0 ? "continuous_monitor" : "advancement_task"
        : index % 3 === 0 ? "user_gate" : "user_action",
      ...(done ? {updated_at: observedAt(index), completed_at: observedAt(index)} : {}),
      ...(status === "deferred" ? {resume_when: "material_change"} : {}),
    };
    if (role === "agent" && status !== "done" && status !== "deferred") {
      record.claimed_by = index % 2 === 0 ? "agent-a" : "agent-b";
    }
    if (role === "agent" && record.task_class === "advancement_task") {
      // Full requirement declarations survive unrelated transitions and archive;
      // editing a declaration must not change an existing execution grant.
      Object.assign(record, {action_kind: "implement", task_domain: "code",
        task_repository: "git:github.com/example/project",
        required_write_scopes: ["src/**", "tests/**"], required_capabilities: ["code_review"],
        target_capabilities: ["delivery"], explore_result_node_refs: [`Node:fixture-${index}`]});
    }
    if (record.task_class === "continuous_monitor") {
      // Durable mixed-source observation shapes: bounded and watch-only,
      // untouched and previously changed, with cadence and retained generation.
      Object.assign(record, {target_key: `synthetic-watch-${index}`, cadence: "1h",
        last_checked_at: observedAt(index), next_due_at: "2025-02-01T00:00:00Z",
        result_hash: `synthetic-result-${index}`, material_change_generation: index % 3,
        consecutive_no_change: String(index % 5), material_change: String(index % 3 === 0),
        ...(index % 8 === 0 ? {watch_only: "true"} : {max_no_change_before_replan: "5"})});
    }
    if (role === "agent" && status === "done" && index < 3) {
      record.successor_todo_ids = [todoId("agent", envelope.completion_target_index + index)];
      record.completion_continuation = "successor";
    }
    if (role === "user" && index < envelope.standing_user_decision_count) {
      record.task_class = "user_gate";
      record.decision_scope = {kind: "direction", granularity: "goal", scope_key: goalId};
      record.decision_outcome = "approve";
      record.global_gate = true;
      record.goal_bound = true;
    }
    // Long-lived histories include scoped gates without an explicit outcome
    // and exact-action approvals. Neither is reusable standing authority.
    const partialEnd = envelope.standing_user_decision_count + envelope.scoped_without_outcome_count;
    if (role === "user" && index >= envelope.standing_user_decision_count &&
        index < partialEnd + envelope.linked_decision_count) {
      record.task_class = "user_gate";
      record.blocks_agent = "agent-a";
      record.decision_scope = {kind: "direction", granularity: "goal", scope_key: goalId};
      if (index >= partialEnd) {
        record.decision_outcome = "approve";
        record.unblocks_todo_id = todoId("agent", envelope.completion_target_index);
      }
    }
    return record;
  });
}

export function productionScaleCoordinationFixture(
  goalId: string,
  schema: AuthorityProjectionSchema = "legacy",
): ProductionScaleCoordinationFixture {
  if (envelope.schema_version !== PRODUCTION_SCALE_FIXTURE_SCHEMA) {
    throw new Error("production-scale fixture envelope schema mismatch");
  }
  const agents = todoRecords(
    goalId, "agent", envelope.agent_status_counts, envelope.agent_status_order,
  );
  const users = todoRecords(
    goalId, "user", envelope.user_status_counts, envelope.user_status_order,
  );
  const archiveDependent = [...agents].reverse().find(item => item.status === "open")!;
  archiveDependent.task_class = "advancement_task";
  archiveDependent.resume_when = `todo_done:${todoId("agent", 3)}`;
  const completionTodo = agents[envelope.completion_target_index]!;
  const supersedeTodo = agents[envelope.supersede_target_index]!;
  completionTodo.task_class = "advancement_task";
  completionTodo.claimed_by = "agent-a";
  completionTodo.completion_validation_required = true;
  completionTodo.completion_validation_sha256 = canonicalAuthoritySha256(
    PRODUCTION_SCALE_VALIDATION_DECLARATION,
  );
  supersedeTodo.task_class = "advancement_task";
  supersedeTodo.claimed_by = "agent-b";
  const todos = [...agents, ...users]
    .sort((left, right) => authorityUnicodeCompare(String(left.todo_id), String(right.todo_id)));
  const leasedIds = [
    String(completionTodo.todo_id),
    String(supersedeTodo.todo_id),
    ...agents.map((todo) => String(todo.todo_id)),
  ]
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, envelope.current_lease_count);
  const leases = leasedIds.map((leasedTodoId, index) => ({
    schema_version: "task_lease_v0",
    goal_id: goalId,
    todo_id: leasedTodoId,
    owner: leasedTodoId === completionTodo.todo_id ? "agent-a" : "agent-b",
    idempotency_key: `fixture-lease-${index}`,
    write_scopes: ["loopx/control_plane/**"],
    version: index + 1,
    lease_epoch: index + 1,
    acquired_at: observedAt(index),
    updated_at: observedAt(index),
    expires_at: index < 2 ? "2027-01-01T00:00:00Z" : observedAt(index + 1),
    status: index < 2 ? "active" : "released",
  })).sort((left, right) => authorityUnicodeCompare(left.todo_id, right.todo_id));
  const completionLease = leases.find((lease) => lease.todo_id === completionTodo.todo_id)!;
  const supersedeLease = leases.find((lease) => lease.todo_id === supersedeTodo.todo_id)!;
  const legacyProjection = authorityProjectionFixture(
    goalId,
    todos as Record<string, unknown>[],
    leases as Record<string, unknown>[],
    "legacy",
    {source_authority: "synthetic_production_scale_fixture", handoff_mode: "hard_lease"},
  );
  const expectedAgentDone = agents.filter(todo => todo.status === "done").length;
  const expectedUserDone = users.filter(todo => todo.status === "done").length;
  const expectedStanding = users.filter(todo =>
    todo.task_class === "user_gate" && todo.decision_outcome === "approve" &&
    todo.global_gate === true && todo.goal_bound === true,
  ).length;
  return {
    projection: schema === "legacy"
      ? legacyProjection
      : projectionFixtureAsSchema(legacyProjection, schema),
    registered_agents: ["agent-a", "agent-b"],
    completion_todo_id: String(completionTodo.todo_id),
    supersede_todo_id: String(supersedeTodo.todo_id),
    completion_lease_idempotency_key: completionLease.idempotency_key,
    completion_lease_expected_version: completionLease.version,
    supersede_lease_idempotency_key: supersedeLease.idempotency_key,
    supersede_lease_expected_version: supersedeLease.version,
    expected_initial_todo_count: todos.length,
    expected_current_lease_count: leases.length,
    expected_agent_archive_count_after_terminals: expectedAgentDone + 2 - 5,
    expected_user_archive_count: expectedUserDone - 5,
    expected_standing_user_decision_count: expectedStanding,
    semantic_cases: envelope.semantic_cases,
    presentation_cases: envelope.presentation_cases,
  };
}

export const PRODUCTION_SCALE_RETIRED_LEASE_COUNT = envelope.retired_lease_count;
