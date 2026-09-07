import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import {
  requireBoolean,
  requireJsonObject,
  requireNonEmptyString,
  requireStringArray,
} from "../runtime_decode.ts";

export const TODO_COMPLETION_POLICY_REQUEST_SCHEMA =
  "loopx_todo_completion_policy_request_v0";
export const TODO_COMPLETION_POLICY_RESULT_SCHEMA =
  "loopx_todo_completion_policy_result_v0";

const AGENT_ID_PATTERN = /^[a-z][a-z0-9_.:@-]{0,79}$/u;
const CONTINUATION_POLICIES = [
  "independent_handoff",
  "same_agent_non_delivery",
] as const;

interface LinkedSuccessor {
  readonly todo_id: string;
  readonly role: string | null;
  readonly status: string | null;
}

interface CompletionPolicyRequest {
  readonly goal_id: string;
  readonly agent_model: string | null;
  readonly claimed_by: unknown;
  readonly registered_agents: readonly string[];
  readonly next_claimed_by: unknown;
  readonly next_agent_todo: string | null;
  readonly next_continuation_policy: string | null;
  readonly next_excluded_agents: readonly unknown[];
  readonly self_merged: boolean;
  readonly evidence: string | null;
  readonly linked_successors: readonly LinkedSuccessor[];
}

export interface TodoCompletionPolicyResult extends JsonObject {
  readonly schema_version: typeof TODO_COMPLETION_POLICY_RESULT_SCHEMA;
  readonly effective_claimed_by: string | null;
  readonly registered_agents: readonly string[];
  readonly effective_next_claimed_by: string | null;
  readonly effective_next_excluded_agents: readonly string[];
  readonly self_merged: boolean;
  readonly linked_successor_id: string | null;
}

function optionalString(value: unknown, label: string): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") {
    throw new EffectRuntimeRequestError(`${label} must be a string or null`);
  }
  return value;
}

function normalizeAgentId(value: unknown): string | null {
  const compact = String(value ?? "").trim().split(/\s+/u).join(" ");
  const candidate = compact.toLowerCase().replaceAll(" ", "-");
  return candidate && AGENT_ID_PATTERN.test(candidate) ? candidate : null;
}

function requireRegisteredAgent(
  value: unknown,
  field: string,
  request: CompletionPolicyRequest,
): string {
  const normalized = normalizeAgentId(value);
  if (normalized === null) {
    throw new EffectRuntimeRequestError(
      `${field} must be a public-safe registered agent id`,
    );
  }
  if (request.registered_agents.length === 0) {
    throw new EffectRuntimeRequestError(
      `${field}='${normalized}' cannot be used because goal '${request.goal_id}' ` +
        "has no coordination.registered_agents list. Register this peer identity first: " +
        `loopx configure-goal --goal-id ${request.goal_id} ` +
        `--registered-agent ${normalized} --execute`,
    );
  }
  if (!request.registered_agents.includes(normalized)) {
    throw new EffectRuntimeRequestError(
      `${field}='${normalized}' is not registered for goal '${request.goal_id}'; ` +
        `registered_agents=${request.registered_agents.join(", ")}`,
    );
  }
  return normalized;
}

function decodeLinkedSuccessors(value: unknown): LinkedSuccessor[] {
  if (!Array.isArray(value)) {
    throw new EffectRuntimeRequestError("linked_successors must be an array");
  }
  return value.map((raw, index) => {
    const successor = requireJsonObject(raw, `linked_successors[${index}]`);
    return {
      todo_id: requireNonEmptyString(
        successor.todo_id,
        `linked_successors[${index}].todo_id`,
      ),
      role: optionalString(successor.role, `linked_successors[${index}].role`),
      status: optionalString(
        successor.status,
        `linked_successors[${index}].status`,
      ),
    };
  });
}

function decodeRequest(value: unknown): CompletionPolicyRequest {
  const request = requireJsonObject(value, "todo completion policy request");
  if (request.schema_version !== TODO_COMPLETION_POLICY_REQUEST_SCHEMA) {
    throw new EffectRuntimeRequestError(
      "Todo completion policy request schema mismatch",
    );
  }
  const registeredAgents = requireStringArray(
    request.registered_agents,
    "registered_agents",
  );
  if (!Array.isArray(request.next_excluded_agents)) {
    throw new EffectRuntimeRequestError(
      "next_excluded_agents must be an array",
    );
  }
  return {
    goal_id: requireNonEmptyString(request.goal_id, "goal_id"),
    agent_model: optionalString(request.agent_model, "agent_model"),
    claimed_by: request.claimed_by,
    registered_agents: registeredAgents,
    next_claimed_by: request.next_claimed_by,
    next_agent_todo: optionalString(request.next_agent_todo, "next_agent_todo"),
    next_continuation_policy: optionalString(
      request.next_continuation_policy,
      "next_continuation_policy",
    ),
    next_excluded_agents: request.next_excluded_agents,
    self_merged: requireBoolean(request.self_merged, "self_merged"),
    evidence: optionalString(request.evidence, "evidence"),
    linked_successors: decodeLinkedSuccessors(request.linked_successors),
  };
}

function requireExcludedAgents(
  values: readonly unknown[],
  request: CompletionPolicyRequest,
): string[] {
  const normalized = new Set<string>();
  for (const value of values) {
    const agentId = normalizeAgentId(value);
    if (agentId === null) {
      throw new EffectRuntimeRequestError(
        "next_excluded_agents must contain public-safe agent tokens such as " +
          "codex-side-bypass",
      );
    }
    normalized.add(agentId);
  }
  return [...normalized]
    .sort()
    .map((agentId) =>
      requireRegisteredAgent(agentId, "next_excluded_agents", request)
    );
}

function continuationPolicy(
  value: string | null,
): typeof CONTINUATION_POLICIES[number] {
  const candidate = String(value ?? "").trim().toLowerCase();
  return CONTINUATION_POLICIES.some((policy) => policy === candidate)
    ? candidate as typeof CONTINUATION_POLICIES[number]
    : "independent_handoff";
}

function firstOpenAgentSuccessor(
  successors: readonly LinkedSuccessor[],
): string | null {
  return successors.find((successor) =>
    successor.role === "agent" &&
    Boolean(successor.todo_id) &&
    (successor.status === null || successor.status === "" ||
      successor.status === "open")
  )?.todo_id ?? null;
}

/** Resolve successor ownership inside the coarse Todo completion transaction. */
export function resolveTodoCompletionPolicy(
  value: unknown,
): TodoCompletionPolicyResult {
  const request = decodeRequest(value);
  const effectiveClaimedBy = request.claimed_by === null ||
      request.claimed_by === undefined || request.claimed_by === ""
    ? null
    : requireRegisteredAgent(request.claimed_by, "claimed_by", request);
  if (
    request.agent_model !== null && request.agent_model !== "" &&
    request.agent_model !== "peer_v1" &&
    request.agent_model !== "legacy_hierarchy"
  ) {
    throw new EffectRuntimeRequestError(
      "coordination.agent_model must be peer_v1",
    );
  }
  let effectiveNextClaimedBy = request.next_claimed_by === null ||
      request.next_claimed_by === undefined || request.next_claimed_by === ""
    ? null
    : requireRegisteredAgent(
      request.next_claimed_by,
      "next_claimed_by",
      request,
    );
  const effectiveNextExcludedAgents = requireExcludedAgents(
    request.next_excluded_agents,
    request,
  );
  if (request.self_merged && !String(request.evidence ?? "").trim()) {
    throw new EffectRuntimeRequestError(
      "--self-merged requires --evidence with the merge, commit, and " +
        "validation summary",
    );
  }
  if (
    request.next_agent_todo !== null && effectiveNextClaimedBy === null &&
    continuationPolicy(request.next_continuation_policy) ===
      "same_agent_non_delivery"
  ) {
    effectiveNextClaimedBy = effectiveClaimedBy;
  }
  if (
    effectiveNextClaimedBy !== null &&
    effectiveNextExcludedAgents.includes(effectiveNextClaimedBy)
  ) {
    throw new EffectRuntimeRequestError(
      `next_claimed_by='${effectiveNextClaimedBy}' cannot also appear in ` +
        "next_excluded_agents",
    );
  }
  if (effectiveNextClaimedBy !== null && request.next_agent_todo === null) {
    throw new EffectRuntimeRequestError(
      "--next-claimed-by requires --next-agent-todo",
    );
  }
  if (
    effectiveNextExcludedAgents.length > 0 && request.next_agent_todo === null
  ) {
    throw new EffectRuntimeRequestError(
      "--next-excluded-agent requires --next-agent-todo",
    );
  }
  return {
    schema_version: TODO_COMPLETION_POLICY_RESULT_SCHEMA,
    effective_claimed_by: effectiveClaimedBy,
    registered_agents: [...request.registered_agents],
    effective_next_claimed_by: effectiveNextClaimedBy,
    effective_next_excluded_agents: effectiveNextExcludedAgents,
    self_merged: request.self_merged,
    linked_successor_id: firstOpenAgentSuccessor(request.linked_successors),
  };
}
