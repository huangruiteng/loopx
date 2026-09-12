/** Host-local observations, never Goal configuration or an authorization grant. */
import {createHash} from "node:crypto";
import {readFile} from "node:fs/promises";
import {join} from "node:path";
import type {JsonObject} from "../effect_program.ts";
import {durableWriteJson, withFileMutationLock} from "../effect_runtime_io.ts";
import {requireBoolean, requireJsonObject, requireNonEmptyString, requireStringArray} from "../runtime_decode.ts";
import {OBSERVABLE_RUNTIME_CAPABILITIES} from "./capability_gate.ts";

const SCHEMA = "agent_runtime_capabilities_v0";
const observable = (value: string) => OBSERVABLE_RUNTIME_CAPABILITIES.has(value);
const unique = (values: string[]) => [...new Set(values)].sort();

export async function agentCapabilityMemory(request: JsonObject): Promise<JsonObject> {
  if (request.schema_version !== "agent_runtime_capability_request_v0") {
    throw new TypeError("agent runtime capability request schema mismatch");
  }
  const root = requireNonEmptyString(request.runtime_root, "runtime_root");
  const scope = {
    registry: requireNonEmptyString(request.registry, "registry"),
    goal_id: requireNonEmptyString(request.goal_id, "goal_id"),
    agent_id: requireNonEmptyString(request.agent_id, "agent_id"),
  };
  const registered = requireStringArray(request.registered_agents, "registered_agents");
  if (!registered.includes(scope.agent_id)) throw new TypeError("agent must be registered for this Goal");
  const supplied = unique(requireStringArray(request.available ?? [], "available"));
  const available = supplied.filter(observable);
  const unavailable = unique(requireStringArray(request.unavailable ?? [], "unavailable"));
  const forget = unique(requireStringArray(request.forget ?? [], "forget"));
  if ([...unavailable, ...forget].some(c => !observable(c))) {
    throw new TypeError("only observable runtime capabilities can be marked unavailable or forgotten");
  }
  if (available.some(c => unavailable.includes(c) || forget.includes(c)) || unavailable.some(c => forget.includes(c))) {
    throw new TypeError("capability updates must not contradict each other");
  }
  const execute = requireBoolean(request.execute, "execute");
  const key = createHash("sha256").update(JSON.stringify(scope)).digest("hex");
  const path = join(root, "agent-runtime-capabilities", `${key}.json`);
  const read = async (): Promise<JsonObject> => {
    let bytes: string;
    try { bytes = await readFile(path, "utf8"); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return {};
      throw error;
    }
    const state = requireJsonObject(JSON.parse(bytes), "agent runtime capability state");
    if (state.schema_version !== SCHEMA || Object.entries(scope).some(([k, v]) => state[k] !== v)) {
      throw new TypeError("agent runtime capability state scope/schema mismatch");
    }
    const observations = requireJsonObject(state.observations, "observations");
    for (const [capability, value] of Object.entries(observations)) {
      if (!observable(capability) || (value !== "available" && value !== "unavailable")) {
        throw new TypeError("invalid agent runtime capability observation");
      }
    }
    return observations;
  };
  const update = async (): Promise<JsonObject> => {
    const previous = await read();
    const next = {...previous};
    for (const c of available) next[c] = "available";
    for (const c of unavailable) next[c] = "unavailable";
    for (const c of forget) delete next[c];
    const changed = JSON.stringify(Object.entries(previous).sort()) !== JSON.stringify(Object.entries(next).sort());
    if (execute && changed) await durableWriteJson(path, {schema_version: SCHEMA, ...scope, observations: next});
    const project = (observations: JsonObject) => ({
      available: Object.keys(observations).filter(c => observations[c] === "available").sort(),
      unavailable: Object.keys(observations).filter(c => observations[c] === "unavailable").sort(),
    });
    return {
      schema_version: SCHEMA, goal_id: scope.goal_id, agent_id: scope.agent_id,
      scope: "host_registry_goal_agent", source: "agent_runtime_observation",
      ...project(execute ? next : previous),
      ...(changed && !execute ? {proposed: project(next)} : {}),
      invocation_only: supplied.filter(c => !observable(c)),
      written: execute && changed, durable_grant_written: false,
    };
  };
  return execute && (available.length || unavailable.length || forget.length)
    ? withFileMutationLock(path, update) : update();
}
