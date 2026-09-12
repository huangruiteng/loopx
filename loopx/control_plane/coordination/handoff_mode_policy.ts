/** One quiescence rule for the legacy adapter and canonical mode transaction. */
import type {JsonObject} from "../effect_program.ts";
import {requireJsonObject, requireStringArray, requireStringLiteral} from "../runtime_decode.ts";

export const HANDOFF_MODES = ["legacy", "soft_claim", "hard_lease"] as const;
export type HandoffMode = typeof HANDOFF_MODES[number];
export const HANDOFF_MODE_PLAN_SCHEMA = "loopx_handoff_mode_plan_request_v0";

export function planHandoffMode(value: unknown): JsonObject {
  const input = requireJsonObject(value, "handoff mode plan");
  if (input.schema_version !== HANDOFF_MODE_PLAN_SCHEMA) throw new Error("handoff mode plan schema mismatch");
  const previous = requireStringLiteral(input.previous_mode, HANDOFF_MODES, "previous_mode");
  const requested = requireStringLiteral(input.requested_mode, HANDOFF_MODES, "requested_mode");
  const claims = requireStringArray(input.active_claimed_todo_ids, "active_claimed_todo_ids");
  const leases = requireStringArray(input.active_lease_todo_ids, "active_lease_todo_ids");
  const unchanged = previous === requested;
  const rejected = !unchanged && (claims.length > 0 || leases.length > 0);
  return {schema_version: "loopx_handoff_mode_plan_result_v0",
    outcome: unchanged ? "no_change" : rejected ? "rejected" : "apply",
    code: unchanged ? "handoff_mode_unchanged" : rejected ? "handoff_mode_not_quiescent" : "handoff_mode_transition",
    idempotent: unchanged, previous_mode: previous, handoff_mode: requested};
}
