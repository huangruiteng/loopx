import type { JsonObject } from "../effect_program.ts";
import { visionAuthoringContract } from "../goals/vision_checkpoint.ts";

function object(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject : null;
}

/** A transport lens, never a replacement for quota admission or vision rules. */
export function projectMcpInteraction(guard: JsonObject): JsonObject {
  const contract = object(guard.interaction_contract);
  if (guard.ok !== true || !contract) return guard;
  const selected = object(guard.selected_todo);
  const ownsDelivery = guard.normal_delivery_allowed === true &&
    typeof selected?.todo_id === "string";
  const cli = object(contract.cli_channel);
  // The raw CLI sequence is the implementation of complete_task, not a second
  // obligation. Replan-only and blocked lanes retain their actual CLI actions.
  let channel = cli;
  if (ownsDelivery && cli) {
    const {settlement_plan: _plan, next_cli_actions: _actions, ...facts} = cli;
    channel = {...facts, next_cli_actions: [], executor: "mcp_complete_task"};
  }
  return {...guard, interaction_contract: {...contract,
    ...(channel ? {cli_channel: channel} : {}),
    mcp_channel: {
      schema_version: "host_mcp_interaction_v0",
      delivery_executor: "complete_task",
      delivery_todo_id: ownsDelivery ? selected!.todo_id : null,
      rule: "For verified Todo delivery, call complete_task INSTEAD OF manual refresh/spend. It owns lifecycle, writeback and accounting. For independent replan, follow the live CLI binding/actions; do not replay an old completion.",
      vision_authoring: visionAuthoringContract(),
      checkpoint_recovery_tool: "review_task_vision",
    },
  }};
}
