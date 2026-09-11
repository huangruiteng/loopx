/** Bounded, read-only capability contributions to coordinator lifecycle context. */
import { createHash } from "node:crypto";
import type { JsonObject } from "./effect_program.ts";
import { requireJsonObject, requireNonEmptyString } from "./runtime_decode.ts";

export const AGENT_CONTEXT_PHASES = [
  "before_plan", "before_delegate", "after_delegate_result",
] as const;
export type AgentContextPhase = typeof AGENT_CONTEXT_PHASES[number];
export interface AgentContextInput {
  phase: AgentContextPhase;
  scope: JsonObject;
  capabilities: JsonObject;
  observations: JsonObject;
}
export interface AgentContextProvider {
  hookId: string;
  capabilityId: string;
  revision: string;
  phases: readonly AgentContextPhase[];
  produce: (input: AgentContextInput, config: JsonObject) => JsonObject;
}

const MAX_BYTES = 3_072;
const CONTRIBUTION_BYTES = 2_048;
function identifier(value: unknown): string {
  const text = requireNonEmptyString(value, "context identifier");
  if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$/u.test(text)) {
    throw new Error("invalid context identifier");
  }
  return text;
}
function bytes(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value), "utf8");
}
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => [key, canonical(item)]));
  }
  return value;
}

/** Only in-process providers registered by capability owners run; no script DSL. */
export function projectAgentContext(
  value: unknown, providers: readonly AgentContextProvider[],
): JsonObject | null {
  const input = requireJsonObject(value, "agent context input");
  const phase = input.phase as AgentContextPhase;
  if (!AGENT_CONTEXT_PHASES.includes(phase)) throw new Error("unsupported context phase");
  const rawScope = requireJsonObject(input.scope, "agent context scope");
  const scope: JsonObject = {
    goal_id: identifier(rawScope.goal_id), agent_id: identifier(rawScope.agent_id),
    todo_id: rawScope.todo_id == null ? null : identifier(rawScope.todo_id),
  };
  const capabilities = requireJsonObject(input.capabilities, "capabilities");
  const observations = requireJsonObject(input.observations ?? {}, "observations");
  const contributions: JsonObject[] = [];
  const failures: JsonObject[] = [];
  const packet: JsonObject = {
    schema_version: "loopx_agent_context_v0", phase, scope,
    target: "coordinator", authority: "guidance_only", delivery: "projected",
    contributions, failures,
  };
  const seen = new Set<string>();
  for (const provider of providers) {
    const config = capabilities[provider.capabilityId];
    if (!config || typeof config !== "object" || Array.isArray(config)
      || (config as JsonObject).enabled !== true || !provider.phases.includes(phase)) continue;
    try {
      identifier(provider.hookId);
      identifier(provider.capabilityId);
      identifier(provider.revision);
      if (seen.has(provider.hookId)) throw new Error("duplicate hook");
      seen.add(provider.hookId);
      const result = requireJsonObject(provider.produce(
        structuredClone({ phase, scope, capabilities, observations }), structuredClone(config as JsonObject),
      ), "context contribution");
      if (Object.keys(result).some(key => !["guidance", "facts", "source_refs"].includes(key))) {
        throw new Error("unsupported contribution field");
      }
      for (const key of ["guidance", "source_refs"]) {
        const items = result[key];
        if (!Array.isArray(items) || items.length === 0 || items.length > 8
          || items.some(item => typeof item !== "string" || !item.trim() || item.length > 400)) {
          throw new Error("invalid context text");
        }
      }
      requireJsonObject(result.facts, "context facts");
      const contribution: JsonObject = {
        hook_id: provider.hookId, capability_id: provider.capabilityId,
        revision: provider.revision, ...result,
      };
      contribution.context_id = createHash("sha256").update(JSON.stringify(canonical({
        phase, scope, contribution,
      }))).digest("hex").slice(0, 24);
      if (bytes(contribution) > CONTRIBUTION_BYTES
        || bytes({ ...packet, contributions: [...contributions, contribution] }) > MAX_BYTES - 256) {
        throw new Error("context budget exceeded");
      }
      contributions.push(contribution);
    } catch {
      // Error messages may contain provider-private text. Never project them.
      const failure = { hook_id: /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$/u.test(provider.hookId)
        ? provider.hookId : "invalid_hook", code: "context_provider_failed" };
      if (failures.length < 8 && bytes({ ...packet, failures: [...failures, failure] }) <= MAX_BYTES) {
        failures.push(failure);
      }
    }
  }
  return contributions.length || failures.length ? packet : null;
}
