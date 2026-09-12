/** Owner eligibility is shared by acquisition, renewal, transfer and observation.
 * It is not a lease grant: time, mode, proof, CAS and release remain with callers. */
import {EffectRuntimeRequestError} from "../effect_runtime_errors.ts";
import {requireJsonObject} from "../runtime_decode.ts";

export interface LeaseEligibilityTodo {
  readonly status: string;
  readonly claimed_by: string | null;
  readonly excluded_agents: readonly string[];
}

export type LeaseOwnerRejection = "todo_not_found" | "todo_not_open" | "invalid_owner" |
  "owner_not_registered" | "owner_excluded_from_todo" | "owner_conflicts_with_claim";

export function leaseOwnerRejection(todo: LeaseEligibilityTodo | null | undefined,
  owner: string | null, registered: readonly string[]): LeaseOwnerRejection | null {
  if (todo == null) return "todo_not_found";
  if (todo.status !== "open") return "todo_not_open";
  if (!owner) return "invalid_owner";
  if (!registered.includes(owner)) return "owner_not_registered";
  if (todo.excluded_agents.includes(owner)) return "owner_excluded_from_todo";
  if (todo.claimed_by && todo.claimed_by !== owner) return "owner_conflicts_with_claim";
  return null;
}

function strings(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.some(item => typeof item !== "string")) {
    throw new EffectRuntimeRequestError(`${label} must be an array of strings`);
  }
  return value as string[];
}

function nullableString(value: unknown, label: string): string | null {
  if (value == null) return null;
  if (typeof value !== "string") throw new EffectRuntimeRequestError(`${label} must be a string or null`);
  return value;
}

/** A narrow adapter for the still-shipped Python coordination/inspection API.
 * Inputs are normalized facts, not Markdown or a second authority snapshot. */
export function evaluateTaskLeaseOwnerEligibility(value: unknown) {
  const input = requireJsonObject(value, "task lease owner eligibility");
  const raw = input.todo == null ? null : requireJsonObject(input.todo, "todo");
  let todo: LeaseEligibilityTodo | null = null;
  if (raw !== null) {
    if (typeof raw.status !== "string") throw new EffectRuntimeRequestError("todo.status must be a string");
    todo = {status: raw.status, claimed_by: nullableString(raw.claimed_by, "todo.claimed_by"),
      excluded_agents: strings(raw.excluded_agents, "todo.excluded_agents")};
  }
  const code = leaseOwnerRejection(todo, nullableString(input.owner, "owner"),
    strings(input.registered_agents, "registered_agents"));
  return {schema_version: "task_lease_owner_eligibility_v0",
    outcome: code === null ? "apply" : "rejected", code: code ?? "lease_owner_allowed"};
}
