import type { JsonObject } from "../effect_program.ts";
import {AGENT_TODO_TASK_CLASSES as AGENT_TASK_CLASSES, USER_TODO_TASK_CLASSES as USER_TASK_CLASSES} from "../todos/authoring_scope.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityObject,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import {
  compactPythonWhitespace,
  normalizeRegisteredTodoAgents,
  normalizeTodoAgent,
  stripPythonWhitespace,
} from "./todo_agents.ts";

export const TODO_SUCCESSOR_DERIVATION_REQUEST_SCHEMA =
  "loopx_todo_successor_derivation_request_v0";
export const TODO_SUCCESSOR_DERIVATION_RESULT_SCHEMA =
  "loopx_todo_successor_derivation_result_v0";

const TERMINAL_COMMANDS = ["complete", "supersede"] as const;
const TODO_ROLES = ["agent", "user"] as const;
const CONTINUATION_POLICIES = new Set([
  "independent_handoff",
  "same_agent_non_delivery",
]);

type TerminalCommand = typeof TERMINAL_COMMANDS[number];
type TodoRole = typeof TODO_ROLES[number];

export interface TodoSuccessorDerivationInput {
  readonly schema_version: typeof TODO_SUCCESSOR_DERIVATION_REQUEST_SCHEMA;
  readonly command: TerminalCommand;
  readonly predecessor: JsonObject;
  readonly registered_agents: readonly string[];
  readonly actor_agent_id: string | null;
  readonly completion_policy: JsonObject | null;
  readonly successor_intents: readonly JsonObject[];
}

interface NormalizedSuccessorIntent extends JsonObject {
  role: TodoRole;
  text: string;
  task_class: string;
}

function requireLiteral<T extends string>(
  value: unknown,
  allowed: readonly T[],
  label: string,
): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new AuthorityStoreProtocolError(
      `${label} must be one of: ${allowed.join(", ")}`,
    );
  }
  return value as T;
}

function optionalString(value: unknown, label: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value !== "string") {
    throw new AuthorityStoreProtocolError(`${label} must be a string or null`);
  }
  return value;
}

function optionalRegisteredAgent(
  value: unknown,
  label: string,
  registeredAgents: readonly string[],
): string | null {
  const raw = optionalString(value, label);
  if (raw === null) return null;
  const agent = normalizeTodoAgent(raw, label);
  if (!registeredAgents.includes(agent)) {
    throw new AuthorityStoreProtocolError(`${label} is not a registered agent`);
  }
  return agent;
}

function optionalStringArray(value: unknown, label: string): string[] {
  if (value === null || value === undefined) return [];
  if (!Array.isArray(value)) {
    throw new AuthorityStoreProtocolError(`${label} must be an array`);
  }
  const values = value.map((item, index) => {
    if (typeof item !== "string" || compactPythonWhitespace(item).length === 0) {
      throw new AuthorityStoreProtocolError(`${label}[${index}] must be a string`);
    }
    return compactPythonWhitespace(item);
  });
  if (new Set(values).size !== values.length) {
    throw new AuthorityStoreProtocolError(`${label} must contain unique values`);
  }
  return values;
}

function optionalRegisteredAgents(
  value: unknown,
  label: string,
  registeredAgents: readonly string[],
): string[] {
  return optionalStringArray(value, label).map((raw, index) => {
    const agent = normalizeTodoAgent(raw, `${label}[${index}]`);
    if (!registeredAgents.includes(agent)) {
      throw new AuthorityStoreProtocolError(`${label}[${index}] is not registered`);
    }
    return agent;
  });
}

function priorityPrefix(text: string): string | null {
  const match = /^\[(P[0-4])\] /iu.exec(text);
  return match === null ? null : match[1]!.toUpperCase();
}

function inheritPriority(nextText: string, predecessorText: string): string {
  const text = compactPythonWhitespace(nextText);
  if (text.length === 0) {
    throw new AuthorityStoreProtocolError("successor intent text must not be empty");
  }
  if (priorityPrefix(text) !== null) return text;
  const inherited = priorityPrefix(compactPythonWhitespace(predecessorText));
  return inherited === null ? text : `[${inherited}] ${text}`;
}

function normalizeIntent(
  value: unknown,
  index: number,
  registeredAgents: readonly string[],
): NormalizedSuccessorIntent {
  const raw = canonicalAuthorityObject(value, `successor_intents[${index}]`);
  const role = requireLiteral(raw.role, TODO_ROLES, `successor_intents[${index}].role`);
  const rawTaskClass = optionalString(
    raw.task_class,
    `successor_intents[${index}].task_class`,
  );
  const taskClass = rawTaskClass === null
    ? (role === "agent" ? "advancement_task" : "")
    : stripPythonWhitespace(rawTaskClass).toLowerCase();
  if (role === "agent" && !AGENT_TASK_CLASSES.has(taskClass)) {
    throw new AuthorityStoreProtocolError(
      "Agent successor task_class must be advancement_task, continuous_monitor, or blocker",
    );
  }
  if (role === "user" && !USER_TASK_CLASSES.has(taskClass)) {
    throw new AuthorityStoreProtocolError(
      "User successor task_class must be user_action or user_gate",
    );
  }
  const claimedBy = optionalRegisteredAgent(
    raw.claimed_by,
    `successor_intents[${index}].claimed_by`,
    registeredAgents,
  );
  const excludedAgents = optionalRegisteredAgents(
    raw.excluded_agents,
    `successor_intents[${index}].excluded_agents`,
    registeredAgents,
  );
  if (claimedBy !== null && excludedAgents.includes(claimedBy)) {
    throw new AuthorityStoreProtocolError(
      "successor claimed_by cannot also appear in excluded_agents",
    );
  }
  const rawContinuationPolicy = optionalString(
    raw.continuation_policy,
    `successor_intents[${index}].continuation_policy`,
  );
  const continuationPolicy = rawContinuationPolicy === null
    ? null
    : stripPythonWhitespace(rawContinuationPolicy).toLowerCase();
  if (continuationPolicy !== null && !CONTINUATION_POLICIES.has(continuationPolicy)) {
    throw new AuthorityStoreProtocolError(
      "successor continuation_policy is unsupported",
    );
  }
  const requiredCapabilities = optionalStringArray(
    raw.required_capabilities,
    `successor_intents[${index}].required_capabilities`,
  );
  const rawActionKind = optionalString(
    raw.action_kind,
    `successor_intents[${index}].action_kind`,
  );
  const actionKind = rawActionKind === null
    ? null
    : stripPythonWhitespace(rawActionKind).toLowerCase();
  if (actionKind !== null && !/^[a-z][a-z0-9_-]{0,63}$/u.test(actionKind)) {
    throw new AuthorityStoreProtocolError(
      "successor action_kind must be a public-safe token",
    );
  }
  return {
    ...raw,
    role,
    text: optionalString(raw.text, `successor_intents[${index}].text`) ?? "",
    task_class: taskClass,
    ...(claimedBy === null ? {} : {claimed_by: claimedBy}),
    excluded_agents: excludedAgents,
    required_capabilities: requiredCapabilities,
    ...(actionKind === null ? {} : {action_kind: actionKind}),
    ...(continuationPolicy === null ? {} : {continuation_policy: continuationPolicy}),
  };
}

function compactOptionalField(
  target: JsonObject,
  key: string,
  value: unknown,
): void {
  if (value !== null && value !== undefined && value !== "" &&
      (!Array.isArray(value) || value.length > 0)) {
    target[key] = value;
  }
}

function completionPolicyAgent(
  policy: JsonObject,
  field: "effective_claimed_by" | "effective_next_claimed_by",
  registeredAgents: readonly string[],
): string | null {
  return optionalRegisteredAgent(policy[field], `completion_policy.${field}`, registeredAgents);
}

/**
 * Derive terminal successor proposals from caller intent and predecessor facts.
 *
 * This function owns priority, capability/binding, exclusion, and predecessor
 * relation inheritance for both canonical transactions and the legacy facade.
 * It deliberately does not assign provider- or Markdown-specific identities.
 */
export function deriveCoordinationTodoSuccessorProposals(
  rawInput: TodoSuccessorDerivationInput,
): JsonObject[] {
  if (rawInput.schema_version !== TODO_SUCCESSOR_DERIVATION_REQUEST_SCHEMA) {
    throw new AuthorityStoreProtocolError("Todo successor derivation schema mismatch");
  }
  const command = requireLiteral(rawInput.command, TERMINAL_COMMANDS, "command");
  if (!Array.isArray(rawInput.successor_intents)) {
    throw new AuthorityStoreProtocolError("successor_intents must be an array");
  }
  if (rawInput.successor_intents.length === 0) {
    return [];
  }
  const predecessor = canonicalAuthorityObject(rawInput.predecessor, "predecessor");
  const predecessorId = requireAuthorityStoreId(predecessor.todo_id, "predecessor.todo_id");
  const predecessorText = optionalString(predecessor.text, "predecessor.text") ?? "";
  const registeredAgents = normalizeRegisteredTodoAgents(rawInput.registered_agents);
  const actor = optionalRegisteredAgent(
    rawInput.actor_agent_id,
    "actor_agent_id",
    registeredAgents,
  );
  const intents = rawInput.successor_intents.map((intent, index) =>
    normalizeIntent(intent, index, registeredAgents));
  for (const role of TODO_ROLES) {
    if (intents.filter((intent) => intent.role === role).length > 1) {
      throw new AuthorityStoreProtocolError(
        `terminal lifecycle permits at most one generated ${role} successor`,
      );
    }
  }
  const completionPolicy = rawInput.completion_policy === null
    ? null
    : canonicalAuthorityObject(rawInput.completion_policy, "completion_policy");
  if (command === "complete" && completionPolicy === null && intents.length > 0) {
    throw new AuthorityStoreProtocolError(
      "complete successor derivation requires the committed completion policy",
    );
  }
  if (command === "supersede" && completionPolicy !== null) {
    throw new AuthorityStoreProtocolError(
      "supersede successor derivation must not carry a completion policy",
    );
  }

  const proposals: JsonObject[] = [];
  for (const intent of intents) {
    const proposal: JsonObject = {
      role: intent.role,
      text: inheritPriority(intent.text, predecessorText),
      task_class: intent.task_class,
    };
    compactOptionalField(proposal, "created_by", actor);
    if (intent.role === "agent") {
      let claimedBy = optionalRegisteredAgent(
        intent.claimed_by,
        "successor_intent.claimed_by",
        registeredAgents,
      );
      let excludedAgents = optionalRegisteredAgents(
        intent.excluded_agents,
        "successor_intent.excluded_agents",
        registeredAgents,
      );
      if (completionPolicy !== null) {
        claimedBy = completionPolicyAgent(
          completionPolicy,
          "effective_next_claimed_by",
          registeredAgents,
        );
        excludedAgents = optionalRegisteredAgents(
          completionPolicy.effective_next_excluded_agents,
          "completion_policy.effective_next_excluded_agents",
          registeredAgents,
        );
      } else if (claimedBy === null &&
          intent.continuation_policy === "same_agent_non_delivery") {
        claimedBy = optionalRegisteredAgent(
          predecessor.claimed_by,
          "predecessor.claimed_by",
          registeredAgents,
        );
      }
      if (claimedBy !== null && excludedAgents.includes(claimedBy)) {
        throw new AuthorityStoreProtocolError(
          "derived successor claimed_by cannot also appear in excluded_agents",
        );
      }
      compactOptionalField(proposal, "action_kind", intent.action_kind);
      compactOptionalField(
        proposal,
        "capability_binding_ref",
        predecessor.capability_binding_ref,
      );
      compactOptionalField(proposal, "task_repository", intent.task_repository);
      compactOptionalField(
        proposal,
        "required_capabilities",
        intent.required_capabilities,
      );
      compactOptionalField(
        proposal,
        "continuation_policy",
        intent.continuation_policy,
      );
      compactOptionalField(proposal, "claimed_by", claimedBy);
      proposal.excluded_agents = excludedAgents;
      compactOptionalField(
        proposal,
        "unblocks_todo_id",
        command === "complete" ? predecessorId : predecessor.unblocks_todo_id,
      );
    } else {
      let boundAgent: string | null = null;
      if (command === "complete") {
        if (registeredAgents.length > 1 && completionPolicy !== null) {
          boundAgent = completionPolicyAgent(
            completionPolicy,
            "effective_claimed_by",
            registeredAgents,
          );
          if (boundAgent === null) {
            throw new AuthorityStoreProtocolError(
              "multi-agent completion requires an effective completing Agent for its User successor",
            );
          }
        }
      } else {
        boundAgent = optionalRegisteredAgent(
          predecessor.bound_agent ?? predecessor.blocks_agent ??
            predecessor.claimed_by ?? intents.find((candidate) =>
              candidate.role === "agent")?.claimed_by,
          "supersede user successor binding",
          registeredAgents,
        );
        if (registeredAgents.length > 1 && boundAgent === null) {
          throw new AuthorityStoreProtocolError(
            "multi-agent supersede requires an inherited or requested User successor binding",
          );
        }
      }
      compactOptionalField(proposal, "bound_agent", boundAgent);
      if (intent.task_class === "user_gate") {
        compactOptionalField(proposal, "blocks_agent", boundAgent);
        proposal.action_kind = "gate";
      }
    }
    proposals.push(proposal);
  }
  return proposals;
}

/** Pure effect-runtime wire handler used by the legacy Python facade. */
export function evaluateCoordinationTodoSuccessorDerivation(
  value: unknown,
): JsonObject {
  try {
    const input = canonicalAuthorityObject(value, "Todo successor derivation request");
    const proposals = deriveCoordinationTodoSuccessorProposals(
      input as unknown as TodoSuccessorDerivationInput,
    );
    return {
      schema_version: TODO_SUCCESSOR_DERIVATION_RESULT_SCHEMA,
      status: "derived",
      successors: proposals,
    };
  } catch (error) {
    return {
      schema_version: TODO_SUCCESSOR_DERIVATION_RESULT_SCHEMA,
      status: "failed",
      reason_code: "invalid_todo_successor_derivation",
      reason: error instanceof Error ? error.message : "invalid Todo successor derivation",
    };
  }
}
