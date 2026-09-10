/** Read lenses over one full Todo snapshot; never an execution grant. */
import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import { requireJsonObject, optionalNonEmptyString, requireStringArray } from "../runtime_decode.ts";
import { leaseIsActive, leaseEpoch, TaskLeaseAcquireError } from "../work_items/task_lease_acquire.ts";
import { normalizeTodoAgent } from "../coordination/todo_agents.ts";
import { AuthorityStoreProtocolError } from "../coordination/authority_store_codec.ts";

export function sharedGoalWorkFacts(value: unknown, agent: string, observedAt: unknown): JsonObject {
  if (typeof observedAt !== "string" || !Number.isFinite(Date.parse(observedAt))) {
    throw new EffectRuntimeRequestError("shared goal work requires a valid observed_at");
  }
  const now = new Date(observedAt);
  if (!Array.isArray(value)) throw new EffectRuntimeRequestError("shared goal work_items must be an array");
  const seen = new Set<string>();
  const current: JsonObject[] = [], unclaimed: JsonObject[] = [], peers: JsonObject[] = [];
  const inventory: JsonObject[] = [];
  for (const entry of value) {
    const item = requireJsonObject(entry, "shared goal work item");
    const id = optionalNonEmptyString(item.todo_id, "todo_id");
    if (!id) continue; // Historical Markdown can contain unaddressable rows.
    if (!/^todo_[a-z0-9_-]{3,64}$/.test(id)) throw new EffectRuntimeRequestError("invalid shared goal Todo id");
    if (seen.has(id)) throw new EffectRuntimeRequestError("duplicate Todo in shared goal snapshot");
    seen.add(id);
    const status = optionalNonEmptyString(item.status, "status") ?? "open";
    if (!["open", "done", "blocked", "deferred"].includes(status)) {
      throw new EffectRuntimeRequestError("invalid shared goal Todo status");
    }
    for (const field of ["done", "resume_ready"]) {
      if (item[field] != null && typeof item[field] !== "boolean") throw new EffectRuntimeRequestError(`${field} must be boolean`);
    }
    if (item.archive_state === "archive" || item.done === true || status !== "open" ||
      (item.resume_when && item.resume_ready !== true)) continue;
    const claim = optionalNonEmptyString(item.claimed_by, "claimed_by");
    const bound = optionalNonEmptyString(item.bound_agent, "bound_agent");
    const taskClass = optionalNonEmptyString(item.task_class, "task_class");
    inventory.push({todo_id: id, status: "open", task_class: taskClass, claimed_by: claim, bound_agent: bound});
    if (taskClass !== "advancement_task") continue;
    const excluded = requireStringArray(item.excluded_agents ?? [], "excluded_agents").includes(agent);
    if (claim && claim !== agent) peers.push(item);
    else if (!excluded) (claim ? current : unclaimed).push(item);
  }
  return {
    frontier_counts: {current_agent_claimed_advancement_count: current.length,
      unclaimed_advancement_count: unclaimed.length, other_agent_claimed_advancement_count: peers.length},
    claims: current.map((item) => {
      if (item.lease_read_error != null) {
        throw new EffectRuntimeRequestError(`cannot read selected claim lease: ${item.todo_id}`);
      }
      const lease = item.lease == null ? null : requireJsonObject(item.lease, "claim lease");
      let epoch: number | null = null, owner: string | null = null;
      try {
        if (leaseIsActive(lease, now)) {
          owner = normalizeTodoAgent(lease?.owner, "active task lease owner");
          epoch = leaseEpoch(lease);
        }
      } catch (error) {
        if (error instanceof AuthorityStoreProtocolError) {
          throw new EffectRuntimeRequestError("active task lease has no valid owner");
        }
        if (error instanceof TaskLeaseAcquireError) {
          throw new EffectRuntimeRequestError(error.message);
        }
        throw error;
      }
      return {todo_id: item.todo_id, claimed_by: item.claimed_by, lease_epoch: epoch, lease_owner: owner};
    }),
    unclaimed_eligible: unclaimed.map((item) => ({todo_id: item.todo_id, task_class: "advancement_task"})),
    peer_claimed_bound_todo_ids: peers.filter((item) => item.bound_agent === agent).map((item) => item.todo_id),
    goal_todo_inventory: inventory,
  };
}
